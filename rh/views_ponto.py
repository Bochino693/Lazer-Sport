"""O ponto nas telas: bater (celular ou PC), comprovante, ajuste e espelho."""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from core.registro_cadastro import ip_da_requisicao
from sistema_interno.permissoes import FINANCEIRO, GESTAO
from sistema_interno.utils import destino_de_retorno

from . import acesso, importacao_ponto, ponto, servicos
from .forms import AjusteForm
from .models import AjustePonto, CartaoPonto, Colaborador, MarcacaoPonto, RegistroRH, Situacao, TipoMarcacao
from .views import BaseRH, sem_cache

ROTULO_DO_BOTAO = {
    TipoMarcacao.ENTRADA: ("Registrar entrada", "bi-box-arrow-in-right"),
    TipoMarcacao.SAIDA_INTERVALO: ("Sair para o intervalo", "bi-cup-hot"),
    TipoMarcacao.VOLTA_INTERVALO: ("Voltar do intervalo", "bi-arrow-repeat"),
    TipoMarcacao.SAIDA: ("Registrar saída", "bi-box-arrow-right"),
}


def contexto_do_dia(colaborador):
    hoje = timezone.localdate()
    marcacoes = ponto.marcacoes_do_dia(colaborador, hoje)
    permitidas = ponto.proximas_do_dia(marcacoes)
    botoes = [
        {"tipo": t, "rotulo": ROTULO_DO_BOTAO[t][0], "icone": ROTULO_DO_BOTAO[t][1]}
        for t in permitidas
    ]
    ultima = marcacoes[-1] if marcacoes else None
    if ultima is None:
        estado = ("fora", "Ainda sem registro hoje")
    elif ultima.tipo in ponto.ABRE:
        estado = ("trabalhando", f"Trabalhando desde {ultima.hora_local:%H:%M}")
    elif ultima.tipo == TipoMarcacao.SAIDA_INTERVALO:
        estado = ("intervalo", f"Em intervalo desde {ultima.hora_local:%H:%M}")
    else:
        estado = ("encerrado", f"Dia encerrado às {ultima.hora_local:%H:%M}")
    return {
        "c": colaborador,
        "hoje": hoje,
        "marcacoes": marcacoes,
        "botoes": botoes,
        "estado": estado,
        "pode": colaborador.pode_bater_ponto,
        "feriado": ponto.feriados_nacionais(hoje.year).get(hoje, ""),
        "jornada_hoje": " · ".join(f"{a:%H:%M}–{b:%H:%M}" for a, b in colaborador.pares_do_dia(hoje))
        if colaborador.jornada_semana else (
            f"{colaborador.jornada_inicio:%H:%M}–{colaborador.jornada_fim:%H:%M}, intervalo "
            f"{colaborador.jornada_intervalo_min} min" if colaborador.trabalha_no_dia(hoje) else ""
        ),
    }


def _por_script(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


class MeuPontoView(BaseRH):
    aba = "ponto"

    def get(self, request):
        meu = self.meu(request)
        if meu is None:
            return self.responder(request, "rh/meu_ponto.html", sem_ficha=True)
        hoje = timezone.localdate()
        recentes = (
            MarcacaoPonto.objects.filter(colaborador=meu, data__gte=hoje - timedelta(days=6))
            .order_by("-momento")[:30]
        )
        espelho = ponto.espelho(meu, hoje.year, hoje.month, com_integridade=False)
        return self.responder(
            request, "rh/meu_ponto.html",
            dia=contexto_do_dia(meu),
            recentes=recentes,
            ajustes=meu.ajustes.select_related("marcacao", "decidido_por")[:12],
            totais=espelho.totais, e=espelho, alertas=espelho.alertas,
            mes_texto=ponto.nome_do_mes(hoje.year, hoje.month),
            agora_servidor=int(timezone.now().timestamp() * 1000),
            tipos_marcacao=TipoMarcacao.choices,
            motivos=AjustePonto.Motivo.choices,
            hoje=hoje,
        )


class MarcarPontoView(BaseRH):
    http_method_names = ["post"]

    def post(self, request):
        meu = self.meu(request)
        if meu is None:
            return JsonResponse({"status": "erro", "msg": "Sua conta não está ligada a uma ficha de colaborador."}, status=403)
        ip, _ = ip_da_requisicao(request)
        consentiu = request.POST.get("localizacao") == "1"
        try:
            marcacao = ponto.registrar(
                meu,
                request.POST.get("tipo") or None,
                ip=ip,
                navegador=request.META.get("HTTP_USER_AGENT", ""),
                latitude=request.POST.get("lat") if consentiu else None,
                longitude=request.POST.get("lng") if consentiu else None,
                precisao=request.POST.get("precisao") if consentiu else None,
            )
        except ponto.ErroDePonto as erro:
            if not _por_script(request):
                messages.error(request, str(erro))
                return redirect("rh_ponto")
            return JsonResponse({"status": "erro", "msg": str(erro)}, status=409)
        if not _por_script(request):
            # Sem JavaScript o formulário ainda funciona: volta para a tela.
            messages.success(
                request,
                f"{marcacao.get_tipo_display()} registrada às {marcacao.hora_local:%H:%M:%S} · "
                f"comprovante {marcacao.codigo}.",
            )
            return redirect("rh_ponto")
        html = render_to_string("rh/partes/ponto_hoje.html", {"dia": contexto_do_dia(meu)}, request=request)
        return JsonResponse({
            "status": "sucesso",
            "msg": f"{marcacao.get_tipo_display()} registrada às {marcacao.hora_local:%H:%M:%S}.",
            "codigo": marcacao.codigo,
            "nsr": marcacao.nsr,
            "hora": f"{marcacao.hora_local:%H:%M:%S}",
            "comprovante": reverse("rh_comprovante", args=[marcacao.pk]),
            "localizacao": marcacao.tem_localizacao,
            "html": html,
        })


class ComprovanteView(BaseRH):
    def get(self, request, pk):
        marcacao = MarcacaoPonto.objects.select_related("colaborador").filter(pk=pk).first()
        if marcacao is None or not acesso.pode_ver_ponto(request.user, marcacao.colaborador):
            raise Http404("Comprovante não encontrado.")
        from .termo import dados_da_empresa

        return sem_cache(render(request, "rh/folha_comprovante.html", {
            "m": marcacao,
            "c": marcacao.colaborador,
            "empresa": dados_da_empresa(),
            "voltar_url": reverse("rh_ponto") if acesso.eh_o_proprio(request.user, marcacao.colaborador)
            else reverse("rh_espelho", args=[marcacao.colaborador_id]),
            "imprimir_ao_abrir": request.GET.get("imprimir") == "1",
        }))


class PedirAjusteView(BaseRH):
    """O colaborador pede para si; a Gestão pode lançar para alguém (já decidido)."""

    http_method_names = ["post"]

    def post(self, request):
        meu = self.meu(request)
        alvo_id = request.POST.get("colaborador")
        gere = acesso.gere(request.user)
        voltar = destino_de_retorno(request, request.POST.get("voltar"), reverse("rh_ponto"))
        if alvo_id and gere and (meu is None or str(meu.pk) != alvo_id):
            colaborador = Colaborador.objects.filter(pk=alvo_id).first() if str(alvo_id).isdigit() else None
            if colaborador is None:
                return self.falhou(request, "Escolha de quem é o abono.", titulo="Falta escolher a pessoa",
                                   campo="colaborador", voltar=voltar)
        elif meu is not None:
            colaborador = meu
        elif gere:
            return self.falhou(request, "Escolha de quem é o abono.", titulo="Falta escolher a pessoa",
                               campo="colaborador", voltar=voltar)
        else:
            raise Http404("Sem ficha.")
        form = AjusteForm(request.POST)
        if not form.is_valid():
            return self.falhou_form(request, form, titulo="O pedido não foi registrado", voltar=voltar)
        try:
            ajuste = form.montar(colaborador, request.user)
        except ValidationError as erro:
            campo, mensagens = next(iter(erro.message_dict.items())) if hasattr(erro, "message_dict") else ("", erro.messages)
            return self.falhou(request, mensagens[0], titulo="O pedido não foi registrado",
                               campo="" if campo == "__all__" else campo, voltar=voltar)
        with transaction.atomic():
            ajuste.save()
            lancado_pela_gestao = gere and colaborador != meu and request.POST.get("aprovar") == "1"
            if lancado_pela_gestao:
                decidir(ajuste, request, aprovar=True, resposta="Lançado e aprovado pela Gestão.")
        if lancado_pela_gestao:
            return self.ok(request, f"Ajuste lançado e aprovado para {colaborador.primeiro_nome}.", voltar=voltar)
        return self.ok(request, "Pedido de ajuste enviado. A Gestão decide e você vê a resposta aqui.", voltar=voltar)


def decidir(ajuste, request, *, aprovar, resposta=""):
    """Aprova ou recusa. Ninguém decide o PRÓPRIO ajuste (o superusuário pode)."""
    if ajuste.situacao != AjustePonto.Estado.PENDENTE:
        raise PermissionDenied("Esse ajuste já foi decidido.")
    if ajuste.colaborador.usuario_id == request.user.pk and not request.user.is_superuser:
        raise PermissionDenied("Ninguém decide o próprio ajuste: outra pessoa da Gestão decide.")
    ajuste.situacao = AjustePonto.Estado.APROVADO if aprovar else AjustePonto.Estado.RECUSADO
    ajuste.decidido_por = request.user
    ajuste.decidido_em = timezone.now()
    ajuste.resposta = (resposta or "").strip()[:500]
    ajuste.save()
    servicos.registrar(
        request, RegistroRH.Acao.AJUSTE_DECIDIDO, colaborador=ajuste.colaborador,
        descricao=f"{'Aprovou' if aprovar else 'Recusou'}: {ajuste.resumo} em {ajuste.data:%d/%m/%Y}",
    )
    return ajuste


class DecidirAjusteView(BaseRH):
    funcoes_necessarias = (GESTAO,)
    http_method_names = ["post"]

    def post(self, request, pk):
        ajuste = get_object_or_404(AjustePonto.objects.select_related("colaborador", "marcacao"), pk=pk)
        voltar = destino_de_retorno(request, request.POST.get("voltar"), reverse("rh_ponto_equipe"))
        aprovar = request.POST.get("decisao") == "aprovar"
        resposta = request.POST.get("resposta", "")
        if not aprovar and len(resposta.strip()) < 5:
            return self.falhou(request, "Para recusar, escreva o motivo: é o que o colaborador vai ler.",
                               titulo="Falta o motivo", campo="resposta", voltar=voltar)
        try:
            with transaction.atomic():
                decidir(ajuste, request, aprovar=aprovar, resposta=resposta)
        except PermissionDenied as erro:
            return self.falhou(request, str(erro), titulo="Não dá para decidir", voltar=voltar, status=409)
        return self.ok(
            request, f"Ajuste de {ajuste.colaborador.primeiro_nome} {'aprovado' if aprovar else 'recusado'}.",
            voltar=voltar,
        )


# ======================================================================
# O PERÍODO (o mês, ou o período do cartão do relógio)
# ======================================================================
LIMITE_DO_PERIODO = 62


def _data(texto):
    try:
        return date.fromisoformat(str(texto or "")[:10])
    except ValueError:
        return None


def periodo_da_requisicao(request):
    """(de, até, {texto, mes, anterior, seguinte, livre}). ?de=&ate= vale até 62 dias; senão o ?mes=."""
    de, ate = _data(request.GET.get("de")), _data(request.GET.get("ate"))
    if de and ate and de <= ate and (ate - de).days <= LIMITE_DO_PERIODO:
        livre = not (de.day == 1 and ate == date(ate.year, ate.month, calendar.monthrange(ate.year, ate.month)[1])
                     and (de.year, de.month) == (ate.year, ate.month))
        ano, mes = de.year, de.month
    else:
        ano, mes = ponto.mes_do_texto(request.GET.get("mes"))
        de = date(ano, mes, 1)
        ate = date(ano, mes, calendar.monthrange(ano, mes)[1])
        livre = False
    texto = f"{de:%d/%m} a {ate:%d/%m/%Y}" if livre else ponto.nome_do_mes(ano, mes)
    return de, ate, {
        "texto": texto, "livre": livre, "mes": f"{ano}-{mes:02d}",
        "anterior": "%d-%02d" % ponto.mes_anterior(ano, mes), "seguinte": "%d-%02d" % ponto.mes_seguinte(ano, mes),
        "de": de, "ate": ate, "query": f"de={de:%Y-%m-%d}&ate={ate:%Y-%m-%d}",
    }


def periodos_importados(consulta, limite=6):
    """Os períodos dos cartões do relógio já importados, para os chips."""
    vistos, saida = set(), []
    for inicio, fim in consulta.filter(situacao=CartaoPonto.Estado.IMPORTADO).order_by("-inicio").values_list("inicio", "fim")[:40]:
        if (inicio, fim) in vistos:
            continue
        vistos.add((inicio, fim))
        mes_inteiro = (inicio.day == 1 and fim == date(fim.year, fim.month, calendar.monthrange(fim.year, fim.month)[1])
                       and (inicio.year, inicio.month) == (fim.year, fim.month))
        saida.append({
            "de": inicio, "ate": fim,
            "texto": ponto.nome_do_mes(inicio.year, inicio.month).capitalize() if mes_inteiro
            else f"{inicio:%d/%m} a {fim:%d/%m/%Y}",
            "query": f"de={inicio:%Y-%m-%d}&ate={fim:%Y-%m-%d}",
        })
        if len(saida) >= limite:
            break
    return saida


def _regua(espelho):
    inicio, fim = espelho.regua
    passo = 120 if fim - inicio > 10 * 60 else 60
    marcas = []
    hora = inicio
    while hora <= fim:
        marcas.append({"texto": f"{hora // 60:02d}h", "esquerda": f"{(hora - inicio) * 100 / max(1, fim - inicio):.2f}"})
        hora += passo
    return (inicio, fim), marcas


def dias_com_linha(espelho):
    regua, marcas = _regua(espelho)
    return [{"d": d, "linha": ponto.linha_do_tempo(d, regua)} for d in espelho.dias], marcas


class PontoEquipeView(BaseRH):
    """O ponto da equipe no período: números, quem pede atenção, a fita de cada um e os cartões do relógio."""

    aba = "ponto_equipe"
    funcoes_necessarias = (GESTAO, FINANCEIRO)

    def get(self, request):
        de, ate, periodo = periodo_da_requisicao(request)
        gere = acesso.gere(request.user)
        pessoas = list(Colaborador.objects.exclude(situacao=Situacao.DESLIGADO).order_by("nome"))
        todos = ponto.espelhos(pessoas, de, ate)
        linhas = []
        soma = {"trabalhado": 0, "extras": 0, "debito": 0, "faltas": 0, "atrasos": 0, "incompletos": 0,
                "longas": 0, "saldo": 0}
        contagem = {"alerta": 0, "falta": 0, "incompleto": 0, "longa": 0, "atraso": 0, "relogio": 0}
        for pessoa in pessoas:
            e = todos[pessoa.pk]
            t = e.totais
            alertas = e.alertas
            marcas = {a["chave"] for a in alertas}
            if t["do_relogio"]:
                marcas.add("relogio")
            if any(a["nivel"] in ("perigo", "alerta") for a in alertas):
                marcas.add("alerta")
            for chave in contagem:
                if chave in marcas:
                    contagem[chave] += 1
            soma["trabalhado"] += t["trabalhado_minutos"]
            soma["extras"] += t["extras_minutos"]
            soma["debito"] += t["debito_minutos"]
            soma["saldo"] += t["saldo_minutos"]
            soma["faltas"] += t["faltas"]
            soma["atrasos"] += t["atrasos"]
            soma["incompletos"] += t["incompletos"]
            soma["longas"] += t["jornadas_longas"]
            linhas.append({"c": pessoa, "e": e, "t": t, "alertas": alertas, "marcas": " ".join(sorted(marcas))})
        pendentes = (
            AjustePonto.objects.filter(situacao=AjustePonto.Estado.PENDENTE)
            .select_related("colaborador", "marcacao", "solicitado_por").order_by("data", "id")
        ) if gere else AjustePonto.objects.none()
        pendentes = list(pendentes)
        cartoes_pendentes = list(
            CartaoPonto.objects.filter(situacao=CartaoPonto.Estado.PENDENTE)
            .select_related("colaborador").order_by("-importacao__enviado_em")[:12]
        ) if gere else []
        return self.responder(
            request, "rh/ponto_equipe.html",
            linhas=linhas, soma={k: (ponto.hm(v) if k in ("trabalhado", "extras", "debito", "saldo") else v)
                                 for k, v in soma.items()},
            saldo_negativo=soma["saldo"] < 0, contagem=contagem,
            pendentes=pendentes, gere=gere, periodo=periodo,
            mes=periodo["mes"], mes_texto=periodo["texto"], anterior=periodo["anterior"], seguinte=periodo["seguinte"],
            importados=periodos_importados(CartaoPonto.objects.all()),
            cartoes_pendentes=cartoes_pendentes,
            hoje=ponto.situacao_de_hoje(),
            pessoas=pessoas, motivos=AjustePonto.Motivo.choices, hoje_data=timezone.localdate(),
        )


def _espelho_visivel(request, pk, *, com_integridade=True):
    colaborador = Colaborador.objects.filter(pk=pk).first()
    if colaborador is None or not acesso.pode_ver_ponto(request.user, colaborador):
        raise Http404("Espelho não encontrado.")
    de, ate, periodo = periodo_da_requisicao(request)
    return colaborador, ponto.espelho_periodo(colaborador, de, ate, com_integridade=com_integridade), periodo


class EspelhoView(BaseRH):
    """O acompanhamento de uma pessoa: números, alertas, linha do tempo e o cartão do relógio ao lado."""

    aba = "ponto_equipe"

    def get(self, request, pk):
        colaborador, espelho, periodo = _espelho_visivel(request, pk)
        proprio = acesso.eh_o_proprio(request.user, colaborador)
        gere = acesso.gere(request.user)
        if proprio:
            self.aba = "ponto"
        cartoes = list(colaborador.cartoes_ponto.filter(situacao=CartaoPonto.Estado.IMPORTADO)
                       .select_related("importacao", "documento").order_by("-inicio")[:12])
        comparacoes = []
        for cartao in cartoes:
            if cartao.inicio > periodo["ate"] or cartao.fim < periodo["de"]:
                continue
            mesmo = (cartao.inicio, cartao.fim) == (periodo["de"], periodo["ate"])
            comparacoes.append({
                "cartao": cartao,
                "r": importacao_ponto.comparar(cartao, espelho if mesmo else None),
                "mesmo_periodo": mesmo,
            })
        dias, regua = dias_com_linha(espelho)
        return self.responder(
            request, "rh/espelho.html",
            c=colaborador, e=espelho, t=espelho.totais, dias=dias, regua=regua, alertas=espelho.alertas,
            periodo=periodo, mes=periodo["mes"], mes_texto=periodo["texto"],
            anterior=periodo["anterior"], seguinte=periodo["seguinte"],
            importados=periodos_importados(colaborador.cartoes_ponto.all()),
            comparacoes=comparacoes, gere=gere, proprio=proprio,
            hm=ponto.hm, motivos=AjustePonto.Motivo.choices, tipos_marcacao=TipoMarcacao.choices,
        )


class EspelhoImprimirView(BaseRH):
    def get(self, request, pk):
        colaborador, espelho, periodo = _espelho_visivel(request, pk)
        from .termo import dados_da_empresa

        servicos.registrar(
            request, RegistroRH.Acao.ESPELHO_IMPRESSO, colaborador=colaborador,
            descricao=f"Espelho de {periodo['texto']}",
        )
        return sem_cache(render(request, "rh/folha_espelho.html", {
            "c": colaborador, "e": espelho, "t": espelho.totais,
            "mes_texto": periodo["texto"], "empresa": dados_da_empresa(),
            "gerado_em": timezone.localtime(),
            "voltar_url": reverse("rh_espelho", args=[colaborador.pk]) + "?" + periodo["query"],
            "imprimir_ao_abrir": request.GET.get("imprimir") == "1",
        }))
