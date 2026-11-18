"""O ponto nas telas: bater (celular ou PC), comprovante, ajuste e espelho."""

from __future__ import annotations

from datetime import timedelta

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

from . import acesso, ponto, servicos
from .forms import AjusteForm
from .models import AjustePonto, Colaborador, MarcacaoPonto, RegistroRH, Situacao, TipoMarcacao
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
        espelho = ponto.espelho(meu, hoje.year, hoje.month)
        return self.responder(
            request, "rh/meu_ponto.html",
            dia=contexto_do_dia(meu),
            recentes=recentes,
            ajustes=meu.ajustes.select_related("marcacao", "decidido_por")[:12],
            totais=espelho.totais,
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
        if alvo_id and gere and (meu is None or str(meu.pk) != alvo_id):
            colaborador = get_object_or_404(Colaborador, pk=alvo_id)
        elif meu is not None:
            colaborador = meu
        else:
            raise Http404("Sem ficha.")
        voltar = destino_de_retorno(request, request.POST.get("voltar"), reverse("rh_ponto"))
        form = AjusteForm(request.POST)
        if not form.is_valid():
            erros = "; ".join(f"{m}" for lista in form.errors.values() for m in lista)
            messages.error(request, f"O pedido não foi registrado: {erros}")
            return redirect(voltar)
        try:
            ajuste = form.montar(colaborador, request.user)
        except ValidationError as erro:
            messages.error(request, "O pedido não foi registrado: " + "; ".join(erro.messages))
            return redirect(voltar)
        with transaction.atomic():
            ajuste.save()
            lancado_pela_gestao = gere and colaborador != meu and request.POST.get("aprovar") == "1"
            if lancado_pela_gestao:
                decidir(ajuste, request, aprovar=True, resposta="Lançado e aprovado pela Gestão.")
        if lancado_pela_gestao:
            messages.success(request, f"Ajuste lançado e aprovado para {colaborador.primeiro_nome}.")
        else:
            messages.success(request, "Pedido de ajuste enviado. A Gestão decide e você vê a resposta aqui.")
        return redirect(voltar)


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
        aprovar = request.POST.get("decisao") == "aprovar"
        resposta = request.POST.get("resposta", "")
        if not aprovar and len(resposta.strip()) < 5:
            messages.error(request, "Para recusar, escreva o motivo: é o que o colaborador vai ler.")
        else:
            try:
                with transaction.atomic():
                    decidir(ajuste, request, aprovar=aprovar, resposta=resposta)
                messages.success(
                    request,
                    f"Ajuste de {ajuste.colaborador.primeiro_nome} {'aprovado' if aprovar else 'recusado'}.",
                )
            except PermissionDenied as erro:
                messages.error(request, str(erro))
        return redirect(destino_de_retorno(request, request.POST.get("voltar"), reverse("rh_ponto_equipe")))


class PontoEquipeView(BaseRH):
    aba = "ponto_equipe"
    funcoes_necessarias = (GESTAO, FINANCEIRO)

    def get(self, request):
        ano, mes = ponto.mes_do_texto(request.GET.get("mes"))
        pessoas = list(Colaborador.objects.exclude(situacao=Situacao.DESLIGADO).order_by("nome"))
        linhas = []
        for pessoa in pessoas:
            espelho = ponto.espelho(pessoa, ano, mes, com_integridade=False)
            linhas.append({"c": pessoa, "t": espelho.totais})
        pendentes = (
            AjustePonto.objects.filter(situacao=AjustePonto.Estado.PENDENTE)
            .select_related("colaborador", "marcacao", "solicitado_por").order_by("data", "id")
        )
        return self.responder(
            request, "rh/ponto_equipe.html",
            linhas=linhas, pendentes=pendentes, gere=acesso.gere(request.user),
            mes=f"{ano}-{mes:02d}", mes_texto=ponto.nome_do_mes(ano, mes),
            anterior="%d-%02d" % ponto.mes_anterior(ano, mes), seguinte="%d-%02d" % ponto.mes_seguinte(ano, mes),
            hoje=ponto.situacao_de_hoje(),
            pessoas=pessoas, motivos=AjustePonto.Motivo.choices,
        )


def _espelho_visivel(request, pk):
    colaborador = Colaborador.objects.filter(pk=pk).first()
    if colaborador is None or not acesso.pode_ver_ponto(request.user, colaborador):
        raise Http404("Espelho não encontrado.")
    ano, mes = ponto.mes_do_texto(request.GET.get("mes"))
    return colaborador, ponto.espelho(colaborador, ano, mes), ano, mes


class EspelhoView(BaseRH):
    aba = "ponto_equipe"

    def get(self, request, pk):
        colaborador, espelho, ano, mes = _espelho_visivel(request, pk)
        if acesso.eh_o_proprio(request.user, colaborador):
            self.aba = "ponto"
        return self.responder(
            request, "rh/espelho.html",
            c=colaborador, e=espelho, t=espelho.totais, mes=f"{ano}-{mes:02d}",
            mes_texto=ponto.nome_do_mes(ano, mes),
            anterior="%d-%02d" % ponto.mes_anterior(ano, mes), seguinte="%d-%02d" % ponto.mes_seguinte(ano, mes),
            gere=acesso.gere(request.user), proprio=acesso.eh_o_proprio(request.user, colaborador),
            hm=ponto.hm, motivos=AjustePonto.Motivo.choices, tipos_marcacao=TipoMarcacao.choices,
        )


class EspelhoImprimirView(BaseRH):
    def get(self, request, pk):
        colaborador, espelho, ano, mes = _espelho_visivel(request, pk)
        from .termo import dados_da_empresa

        servicos.registrar(
            request, RegistroRH.Acao.ESPELHO_IMPRESSO, colaborador=colaborador,
            descricao=f"Espelho de {ponto.nome_do_mes(ano, mes)}",
        )
        return sem_cache(render(request, "rh/folha_espelho.html", {
            "c": colaborador, "e": espelho, "t": espelho.totais,
            "mes_texto": ponto.nome_do_mes(ano, mes), "empresa": dados_da_empresa(),
            "gerado_em": timezone.localtime(),
            "voltar_url": reverse("rh_espelho", args=[colaborador.pk]) + f"?mes={ano}-{mes:02d}",
            "imprimir_ao_abrir": request.GET.get("imprimir") == "1",
        }))
