"""A tela da Lista de montagem (LEIA-ME-V10, seção 112).

"Lista de montagem com todos os brinquedos que tem pra montar": as
máquinas dos pedidos pagos do site e dos orçamentos aprovados, juntas,
uma linha por unidade. A regra (a fila, as etapas, os avisos) mora em
`montagem.py`; aqui só o que a tela mostra e o que ela pede:

  * EM PRODUÇÃO, agrupadas por brinquedo ("Air Game Kids · 4 na fila, 1 em
    montagem"), cada máquina com as etapas em chips (rádios dentro de
    <label>: a etapa marcada é a última feita) e a data prevista de cada;
  * NA FILA, máquinas e brinquedões separados, com a posição, a previsão,
    a origem e as setas de subir e descer;
  * PRONTAS, esperando a entrega (o orçamento ganha o "Entregue"; o pedido
    anda pelo painel de Pedidos);
  * AS REGRAS (capacidade, fila, m³, dias, o que é brinquedão), que a
    Produção e a Gestão mudam -- e as previsões se recalculam.

QUEM (permissoes.capacidades: lista_montagem, lista_montagem_editar e
lista_montagem_tudo -- as mesmas do menu). A lista é da ENGENHARIA DE
PRODUÇÃO: só ela (e o superusuário) marca as etapas, mexe na fila e nas
regras. Gestão e Financeiro veem tudo, sem mexer. Vendas e o Ambulante
veem só o andamento e a previsão do que eles venderam (os orçamentos de
que são responsáveis). Quem não tem nenhuma das funções volta para a tela
dela. O cliente de cada máquina é dado da equipe: nunca sai daqui para o
site.
"""

from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import View

from . import montagem
from .models import ConfiguracaoProducao, UnidadeMontagem
from .permissoes import AMBULANTE, FINANCEIRO, GESTAO, PRODUCAO, VENDAS, capacidades
from .views import InternoRequiredMixin

QUEM_VE = (PRODUCAO, GESTAO, FINANCEIRO, VENDAS, AMBULANTE)

S = UnidadeMontagem.Situacao

#: Os filtros da situação (chips): o padrão é o que ainda não foi entregue.
FILTROS = (
    ("ativas", "Tudo o que falta", "bi-hourglass-split"),
    ("producao", "Em produção", "bi-tools"),
    ("fila", "Na fila", "bi-list-ol"),
    ("prontas", "Prontas", "bi-box-seam"),
    ("entregues", "Entregues", "bi-flag-fill"),
)
SITUACOES_DO_FILTRO = {
    "ativas": (S.FILA, S.PRODUCAO, S.PRONTA),
    "producao": (S.PRODUCAO,),
    "fila": (S.FILA,),
    "prontas": (S.PRONTA,),
    "entregues": (S.ENTREGUE,),
}
LINHAS = (
    ("", "Todas", "bi-grid"),
    ("maquina", "Máquinas", "bi-joystick"),
    ("projeto", "Brinquedões", "bi-bricks"),
    ("peca", "Peças e kits", "bi-gear"),
)


def pode_mexer(user) -> bool:
    return capacidades(user)["lista_montagem_editar"]


def ve_tudo(user) -> bool:
    return capacidades(user)["lista_montagem_tudo"]


def unidades_que_ve(user, consulta):
    """Vendas e o Ambulante: só as máquinas dos orçamentos deles."""
    if ve_tudo(user):
        return consulta
    return consulta.filter(producao__orcamento__responsavel=user)


def chave_do_brinquedo(unidade) -> str:
    if unidade.brinquedo_id:
        return f"b{unidade.brinquedo_id}"
    return "n" + montagem.sem_acento(unidade.nome).replace(" ", "-")[:60]


def nome_do_grupo(unidade) -> str:
    if unidade.brinquedo_id and unidade.brinquedo is not None:
        return unidade.brinquedo.nome_brinquedo
    return unidade.nome


def _dm(dia):
    return dia.strftime("%d/%m") if dia else ""


def etapas_da_unidade(unidade):
    """Os chips de uma máquina: feitas (com o dia), a de agora e as próximas (com a previsão)."""
    feitas = unidade.etapas_em or {}
    vistas, atual = [], False
    for chave, nome, icone in montagem.etapas_da(unidade.trilha):
        if chave in feitas:
            momento = montagem._momento(feitas[chave])
            vistas.append({"chave": chave, "nome": nome, "icone": icone, "estado": "feita",
                           "nota": _dm(montagem.dia_local(momento)) if momento else "",
                           "marcada": chave == unidade.etapa})
            continue
        estado = "futura"
        if unidade.situacao == S.PRODUCAO and not atual:
            estado, atual = "atual", True
        prevista = montagem._data((unidade.previstas or {}).get(chave))
        vistas.append({"chave": chave, "nome": nome, "icone": icone, "estado": estado,
                       "nota": f"prev. {_dm(prevista)}" if prevista else "", "marcada": False})
    return vistas


def origem_da_unidade(unidade):
    """Pedido nº / orçamento nº, o cliente (só para a equipe) e para onde o toque leva."""
    producao = unidade.producao
    if producao.pedido_id:
        pedido = producao.pedido
        perfil = pedido.cliente
        conta = getattr(perfil, "user", None) if perfil else None
        cliente = (
            (getattr(perfil, "nome_completo", "") or "").strip()
            or (conta.get_full_name() if conta else "")
            or (conta.username if conta else "")
            or "Cliente do site"
        )
        return {
            "tipo": "pedido", "id": pedido.pk, "rotulo": f"Pedido #{pedido.pk}", "cliente": cliente,
            "icone": "bi-bag-check", "retirada": pedido.retirada, "situacao": pedido.situacao_texto,
            "url": reverse("pedidos_inner", urlconf="sistema_interno.urls") + "?filtro=todos",
            "etiquetas": reverse("etiquetas_maquinas", args=["pedido", pedido.pk], urlconf="sistema_interno.urls"),
        }
    orcamento = producao.orcamento
    return {
        "tipo": "orcamento", "id": orcamento.pk, "rotulo": f"Orçamento nº {orcamento.numero_documento}",
        "cliente": orcamento.destinatario, "icone": "bi-file-earmark-text", "retirada": False,
        "situacao": orcamento.get_status_display(),
        "url": reverse("orcamentos_inner", urlconf="sistema_interno.urls") + f"?q={orcamento.pk}",
        "etiquetas": reverse("etiquetas_maquinas", args=["orcamento", orcamento.pk], urlconf="sistema_interno.urls"),
    }


def _previsao(unidade):
    return montagem.texto_da_previsao(unidade.previsao_de, unidade.previsao_ate).replace("previsão ", "")


def _volume(unidade):
    volume = getattr(unidade.brinquedo, "metros_cubicos", None) if unidade.brinquedo_id else None
    if volume is None:
        return ""
    return f"{volume:.2f}".replace(".", ",") + " m³"


def preparar(unidade):
    """Os dados de uma linha da tela, já escritos."""
    unidade.origem = origem_da_unidade(unidade)
    unidade.etapas_vista = etapas_da_unidade(unidade) if unidade.situacao != S.FILA else []
    unidade.previsao_texto = _previsao(unidade)
    unidade.volume_texto = _volume(unidade)
    unidade.grupo_chave = chave_do_brinquedo(unidade)
    unidade.grupo_nome = nome_do_grupo(unidade)
    unidade.trilha_texto = unidade.get_trilha_display()
    unidade.dias_texto = montagem.texto_dos_dias(unidade.dias) if unidade.dias else ""
    return unidade


class ListaMontagemView(InternoRequiredMixin, View):
    funcoes_necessarias = QUEM_VE
    template_name = "lista_montagem_inner.html"

    def get(self, request):
        # a rede de segurança: o que devia estar na lista e ainda não está, as
        # previsões do dia (a fila anda com o calendário) e os avisos guardados
        montagem.sincronizar_tudo()
        config = montagem.configuracao()
        montagem.distribuir(config=config)
        montagem.avisar_pendentes()

        filtro = request.GET.get("filtro") or "ativas"
        if filtro not in SITUACOES_DO_FILTRO:
            filtro = "ativas"
        linha = request.GET.get("linha") or ""
        if linha not in dict((v, r) for v, r, _ in LINHAS):
            linha = ""
        brinquedo = (request.GET.get("brinquedo") or "").strip()

        base = unidades_que_ve(request.user, (
            UnidadeMontagem.objects.exclude(situacao=S.CANCELADA)
            .select_related(
                "producao__pedido__cliente__user", "producao__orcamento__cliente", "brinquedo",
            )
        ))
        todas = [preparar(u) for u in base.exclude(situacao=S.ENTREGUE).order_by("chegada", "id")]
        if filtro == "entregues":
            todas += [preparar(u) for u in base.filter(situacao=S.ENTREGUE).order_by("-atualizado")[:120]]

        # AS CONTAGENS POR BRINQUEDO ("Air Game Kids: 4 na fila, 1 em montagem")
        por_brinquedo = OrderedDict()
        for unidade in sorted(todas, key=lambda u: montagem.sem_acento(u.grupo_nome)):
            if unidade.situacao == S.ENTREGUE:
                continue
            grupo = por_brinquedo.setdefault(unidade.grupo_chave, {
                "chave": unidade.grupo_chave, "nome": unidade.grupo_nome,
                "fila": 0, "producao": 0, "pronta": 0, "total": 0,
            })
            grupo[unidade.situacao] = grupo.get(unidade.situacao, 0) + 1
            grupo["total"] += 1
        for grupo in por_brinquedo.values():
            partes = []
            if grupo["fila"]:
                partes.append(f"{grupo['fila']} na fila")
            if grupo["producao"]:
                partes.append(f"{grupo['producao']} em montagem")
            if grupo["pronta"]:
                partes.append(f"{grupo['pronta']} pronta{'s' if grupo['pronta'] != 1 else ''}")
            grupo["resumo"] = ", ".join(partes)

        def passa(unidade):
            if unidade.situacao not in SITUACOES_DO_FILTRO[filtro]:
                return False
            if linha == "peca" and unidade.trilha not in ("peca", "kit"):
                return False
            if linha and linha != "peca" and unidade.trilha != linha:
                return False
            if brinquedo and unidade.grupo_chave != brinquedo:
                return False
            return True

        visiveis = [u for u in todas if passa(u)]
        grupos = OrderedDict()
        for unidade in sorted(
            (u for u in visiveis if u.situacao == S.PRODUCAO),
            key=lambda u: (montagem.sem_acento(u.grupo_nome), u.entrou_em or u.chegada, u.pk),
        ):
            grupo = grupos.setdefault(unidade.grupo_chave, {
                "nome": unidade.grupo_nome,
                "resumo": por_brinquedo.get(unidade.grupo_chave, {}).get("resumo", ""),
                "unidades": [],
            })
            grupo["unidades"].append(unidade)
        fila_maquinas = sorted((u for u in visiveis if u.situacao == S.FILA and u.trilha == "maquina"),
                               key=lambda u: (u.posicao or 10 ** 6, u.chegada))
        fila_projetos = sorted((u for u in visiveis if u.situacao == S.FILA and u.trilha == "projeto"),
                               key=lambda u: (u.posicao or 10 ** 6, u.chegada))
        prontas = [u for u in visiveis if u.situacao == S.PRONTA]
        entregues = [u for u in visiveis if u.situacao == S.ENTREGUE]

        # as vagas são da fábrica inteira (não dizem de quem é cada máquina)
        if ve_tudo(request.user):
            ativas = [u for u in todas if u.situacao in (S.FILA, S.PRODUCAO, S.PRONTA)]
        else:
            ativas = list(UnidadeMontagem.objects.filter(situacao__in=(S.FILA, S.PRODUCAO, S.PRONTA)).only(
                "trilha", "situacao",
            ))
        em_montagem = sum(1 for u in ativas if u.trilha == "maquina" and u.situacao == S.PRODUCAO)
        projetos_montagem = sum(1 for u in ativas if u.trilha == "projeto" and u.situacao == S.PRODUCAO)
        projetos_fila = sum(1 for u in ativas if u.trilha == "projeto" and u.situacao == S.FILA)
        cartoes = (
            ("?filtro=producao&linha=maquina", filtro == "producao" and linha == "maquina",
             "Máquinas em montagem", f"{em_montagem} de {config.capacidade_maquinas}",
             "bi-tools", "blue", "vagas ocupadas agora"),
            ("?filtro=fila", filtro == "fila" and not linha,
             "Na fila", sum(1 for u in ativas if u.situacao == S.FILA),
             "bi-list-ol", "yellow", f"máquinas: {config.fila_min_dias} a {config.fila_max_dias} dias úteis"),
            ("?filtro=ativas&linha=projeto", filtro == "ativas" and linha == "projeto",
             "Brinquedões", f"{projetos_montagem} de {config.capacidade_projetos}",
             "bi-bricks", "violet", f"{projetos_fila} na fila · {config.dias_projeto} dias úteis cada"),
            ("?filtro=prontas", filtro == "prontas" and not linha,
             "Prontas", sum(1 for u in ativas if u.situacao == S.PRONTA),
             "bi-box-seam", "green", "esperando a entrega"),
        )
        from core.models import CategoriasBrinquedos

        marcadas = set(config.categorias_projeto.values_list("pk", flat=True))
        return render(request, self.template_name, {
            "filtro_ativo": filtro,
            "filtros": FILTROS,
            "linha_ativa": linha,
            "linhas": LINHAS,
            "brinquedo_ativo": brinquedo,
            "por_brinquedo": list(por_brinquedo.values()),
            "grupos": list(grupos.values()),
            "fila_maquinas": fila_maquinas,
            "fila_projetos": fila_projetos,
            "prontas": prontas,
            "entregues": entregues,
            "nada": not (grupos or fila_maquinas or fila_projetos or prontas or entregues),
            "cartoes": cartoes,
            "config": config,
            "categorias": [
                {"pk": c.pk, "nome": c.nome_categoria or f"Categoria {c.pk}", "marcada": c.pk in marcadas}
                for c in CategoriasBrinquedos.objects.order_by("nome_categoria")
            ],
            "pode_mexer": pode_mexer(request.user),
            "ve_tudo": ve_tudo(request.user),
            "limite_texto": f"{config.limite_m3:.2f}".replace(".", ","),
        })

    # ------------------------------------------------------------------ POST
    def post(self, request):
        if not pode_mexer(request.user):
            return self.erro(
                request,
                "A lista de montagem é da Engenharia de produção: só ela marca as etapas, a fila e as regras.",
                403,
            )
        acao = request.POST.get("action") or ""
        try:
            if acao == "etapa":
                return self.etapa(request)
            if acao == "fila":
                return self.fila(request)
            if acao == "entregue":
                return self.entregue(request)
            if acao == "regras":
                return self.regras(request)
        except ValueError as erro:
            return self.erro(request, str(erro))
        return self.erro(request, "Ação desconhecida.")

    @staticmethod
    def erro(request, mensagem, status=400):
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"status": "erro", "msg": mensagem}, status=status)
        messages.error(request, mensagem)
        return redirect("lista_montagem")

    @staticmethod
    def certo(request, mensagem, **extra):
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"status": "sucesso", "msg": mensagem, **extra})
        messages.success(request, mensagem)
        return redirect("lista_montagem")

    @staticmethod
    def unidade(request):
        pk = request.POST.get("id") or ""
        unidade = UnidadeMontagem.objects.select_related("producao").filter(pk=pk if str(pk).isdigit() else 0).first()
        if unidade is None:
            raise Http404("Esta máquina não está na lista.")
        return unidade

    def etapa(self, request):
        unidade = self.unidade(request)
        etapa = (request.POST.get("etapa") or "").strip()
        montagem.concluir_ate(unidade, etapa, usuario=request.user)
        unidade.refresh_from_db()
        if not etapa:
            frase = f"{unidade.nome} ({unidade.numero}/{unidade.de}): nenhuma etapa feita."
        elif unidade.situacao == S.PRONTA:
            frase = f"{unidade.nome} ({unidade.numero}/{unidade.de}) está pronta."
        else:
            frase = f"{unidade.nome} ({unidade.numero}/{unidade.de}): {montagem.NOME_DA_ETAPA[etapa]} feita."
        producao = unidade.producao
        producao.refresh_from_db()
        if producao.pedido_id and producao.situacao == producao.Situacao.PRONTA:
            pedido = producao.pedido
            pedido.refresh_from_db()
            frase += f" Pedido #{pedido.pk}: {pedido.situacao_texto.lower()}."
        return self.certo(request, frase, situacao=unidade.situacao, etapa=unidade.etapa)

    def fila(self, request):
        unidade = self.unidade(request)
        direcao = -1 if request.POST.get("direcao") == "subir" else 1
        if unidade.situacao != S.FILA:
            raise ValueError("Esta máquina não está mais na fila.")
        if not montagem.mover_na_fila(unidade, direcao):
            raise ValueError("Ela já está na ponta da fila.")
        unidade.refresh_from_db()
        return self.certo(request, f"{unidade.nome}: agora é a {unidade.posicao or 1}ª da fila.")

    def entregue(self, request):
        unidade = self.unidade(request)
        producao = unidade.producao
        if producao.pedido_id:
            raise ValueError(
                "O pedido do site é entregue pelo painel de Pedidos (Finalizado): a lista acompanha sozinha."
            )
        if producao.situacao != producao.Situacao.PRONTA:
            raise ValueError("Só a compra com todas as máquinas prontas é marcada como entregue.")
        montagem.marcar_entregue(producao)
        return self.certo(request, f"Orçamento nº {producao.orcamento.numero_documento}: entregue.")

    def regras(self, request):
        config = montagem.configuracao()
        inteiros = {
            "dias_ate_limite": (1, 60), "dias_acima_limite": (1, 60), "dias_pecas": (1, 60),
            "dias_projeto": (1, 250), "capacidade_maquinas": (1, 50), "capacidade_projetos": (1, 20),
            "fila_min_dias": (0, 250), "fila_max_dias": (0, 250),
        }
        valores = {}
        for campo, (minimo, maximo) in inteiros.items():
            texto = (request.POST.get(campo) or "").strip()
            if not texto.isdigit() or not (minimo <= int(texto) <= maximo):
                rotulo = ConfiguracaoProducao._meta.get_field(campo).verbose_name
                raise ValueError(f"“{rotulo}”: um número de {minimo} a {maximo}.")
            valores[campo] = int(texto)
        if valores["fila_min_dias"] > valores["fila_max_dias"]:
            raise ValueError("O mínimo da fila não pode passar do máximo.")
        try:
            limite = Decimal((request.POST.get("limite_m3") or "").replace(",", "."))
        except InvalidOperation:
            limite = None
        if limite is None or not (Decimal("0.10") <= limite <= Decimal("99")):
            raise ValueError("O limite de m³ é um número de 0,10 a 99 (ex.: 2,5).")
        for campo, valor in valores.items():
            setattr(config, campo, valor)
        config.limite_m3 = limite.quantize(Decimal("0.01"))
        config.palavras_projeto = (request.POST.get("palavras_projeto") or "").strip()[:2000]
        config.save()
        escolhidas = [int(pk) for pk in request.POST.getlist("categorias_projeto") if str(pk).isdigit()]
        config.categorias_projeto.set(escolhidas)
        montagem.distribuir(timezone.now(), config)
        montagem.mudou()
        return self.certo(request, "Regras da produção salvas: as previsões foram recalculadas.")
