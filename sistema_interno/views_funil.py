"""O funil de vendas no painel: andamento, tempo de produção e etiquetas.

"Veja a interseção de orçamento e pedidos: pedidos vêm do site, orçamento a
gente faz aqui manual, os dois devem virar vendas após a finalização. O
tempo de produção a gente deve poder informar em cada pedido ou orçamento.
Também devemos imprimir a etiqueta (...) a partir de um orçamento ou pedido
-- ponha nos dois e na venda." (LEIA-ME-V10, seção 89.)

Quatro portas, todas pequenas:

  * o ANDAMENTO do pedido do site (pago -> em preparação -> saiu para
    entrega -> finalizado, ou cancelado), que até aqui só mudava pelo
    admin do Django. A venda acompanha (`Pedido.mudar_situacao`);
  * o PRAZO DE PRODUÇÃO do pedido e do orçamento, digitado na própria
    linha (ou na janela) e gravado sem recarregar a tela;
  * a FICHA DAS ETIQUETAS (JSON): as máquinas, o prazo e quantas cabem na
    folha -- é dela que a folha de cópias do painel se desenha;
  * a IMPRESSÃO: as etiquetas em folhas A4, prontas para a impressora.

QUEM PODE. Produção informa o prazo e imprime as etiquetas (é ela quem
fabrica e quem embala); Financeiro e Gestão também, e são os únicos que
mexem no andamento do pedido (cancelar tira a venda da receita). No
orçamento vale, além da Produção, quem já enxerga aquele orçamento (o
Ambulante, só os dele) -- a mesma regra da tela de Orçamentos.
"""

from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import View

from core.models import Pedido, Venda
from core.producao import ler_prazo, texto_dos_dias

from . import etiquetas_maquinas as etq
from .models import Orcamento
from .permissoes import (
    AMBULANTE,
    FINANCEIRO,
    GESTAO,
    PRODUCAO,
    VENDAS,
    pode_acessar_orcamento,
    tem_funcao,
)
from .views import InternoRequiredMixin
from .views_etiquetas import EtiquetasInnerView, identidade_da_empresa

#: Quem cuida do pedido do site depois de pago.
EQUIPE_DO_PEDIDO = (PRODUCAO, FINANCEIRO, GESTAO)
#: Quem mexe no andamento (cancelar tira a venda da receita).
ANDAMENTO_DO_PEDIDO = (FINANCEIRO, GESTAO)

TIPOS = ("pedido", "orcamento", "venda")


def _erro(mensagem, status=400):
    return JsonResponse({"status": "erro", "msg": mensagem}, status=status)


def pode_cuidar(user, objeto) -> bool:
    """Prazo e etiquetas: a Produção, e quem já cuida daquela origem."""
    if isinstance(objeto, Orcamento):
        return tem_funcao(user, PRODUCAO) or pode_acessar_orcamento(user, objeto)
    return tem_funcao(user, *EQUIPE_DO_PEDIDO)


def buscar_origem(tipo, pk):
    """O pedido, o orçamento ou a venda pelo número -- ou 404."""
    if tipo == "pedido":
        objeto = (
            Pedido.objects.select_related("cliente__user")
            .prefetch_related("itens").filter(pk=pk).first()
        )
    elif tipo == "orcamento":
        objeto = (
            Orcamento.objects.select_related("cliente")
            .prefetch_related("itens", "cliente__enderecos").filter(pk=pk).first()
        )
    elif tipo == "venda":
        objeto = (
            Venda.objects.select_related("pedido__cliente__user", "orcamento__cliente")
            .filter(pk=pk).first()
        )
    else:
        objeto = None
    if objeto is None:
        raise Http404("Não encontrado.")
    return objeto


def ficha_de(objeto):
    if isinstance(objeto, Pedido):
        return etq.ficha_do_pedido(objeto)
    if isinstance(objeto, Orcamento):
        return etq.ficha_do_orcamento(objeto)
    return etq.ficha_da_venda(objeto)


def dados_do_prazo(objeto) -> dict:
    """O prazo como a tela mostra: dias, previsão e a nota curta."""
    from django.urls import reverse

    tipo = "pedido" if isinstance(objeto, Pedido) else "orcamento"
    previsao = objeto.previsao_producao
    dias = objeto.prazo_producao_dias
    if dias is None:
        nota = "Informe em dias úteis"
    elif previsao is not None:
        nota = f"Previsão {previsao:%d/%m/%Y}"
    elif tipo == "orcamento":
        nota = f"{texto_dos_dias(dias).capitalize()} após a aprovação"
    else:
        nota = f"{texto_dos_dias(dias).capitalize()} após o pagamento"
    return {
        "dias": dias,
        "previsao": f"{previsao:%d/%m/%Y}" if previsao else "",
        "inicio": (
            f"{objeto.inicio_da_producao:%d/%m/%Y}" if objeto.inicio_da_producao else ""
        ),
        "nota": nota,
        "texto": objeto.texto_producao,
        "url": reverse(
            "prazo_producao", args=[tipo, objeto.pk], urlconf="sistema_interno.urls",
        ),
    }


def prazo_editavel(objeto) -> bool:
    """O prazo só muda enquanto ele ainda significa alguma coisa.

    Pedido cancelado e proposta recusada, expirada ou substituída são
    história: o prazo deles fica como estava.
    """
    if isinstance(objeto, Pedido):
        return objeto.status != "cancelado"
    return objeto.status not in (
        Orcamento.Status.RECUSADO,
        Orcamento.Status.EXPIRADO,
        Orcamento.Status.SUBSTITUIDO,
    )


class FunilMixin(InternoRequiredMixin):
    """Entra quem é da equipe de alguma das pontas; o objeto confere o resto."""

    funcoes_necessarias = (PRODUCAO, VENDAS, AMBULANTE, FINANCEIRO, GESTAO)

    def origem_permitida(self, request, tipo, pk):
        objeto = buscar_origem(tipo, pk)
        alvo = objeto.origem_objeto if isinstance(objeto, Venda) else objeto
        if isinstance(objeto, Venda) and not tem_funcao(request.user, FINANCEIRO, GESTAO):
            # A venda é do Financeiro e da Gestão; a Produção chega à mesma
            # máquina pelo pedido ou pelo orçamento, não pelo dinheiro.
            return objeto, None
        if alvo is None or not pode_cuidar(request.user, alvo):
            return objeto, None
        return objeto, alvo


# ======================================================================
# O PRAZO DE PRODUÇÃO
# ======================================================================
class PrazoProducaoView(FunilMixin, View):
    """Grava o prazo (dias úteis) de um pedido ou orçamento. Só POST."""

    def post(self, request, tipo, pk):
        if tipo not in ("pedido", "orcamento"):
            raise Http404
        objeto, alvo = self.origem_permitida(request, tipo, pk)
        if alvo is None:
            return _erro("Seu acesso não inclui este prazo de produção.", status=403)
        if not prazo_editavel(alvo):
            return _erro(
                "Este registro já é história (cancelado, recusado ou "
                "substituído): o prazo dele não muda mais.",
            )
        try:
            dias = ler_prazo(request.POST.get("prazo"))
        except ValueError as erro:
            return _erro(str(erro))

        campos = ["prazo_producao_dias", "atualizado"]
        alvo.prazo_producao_dias = dias
        if isinstance(alvo, Orcamento):
            if alvo.marcar_inicio_da_producao():
                campos.append("producao_inicio")
        elif alvo.pago and alvo.producao_inicio is None:
            alvo.producao_inicio = alvo.inicio_da_producao
            campos.append("producao_inicio")
        # `save` com a lista: o sinal do pedido só olha mudança de situação.
        alvo.save(update_fields=campos)

        dados = dados_do_prazo(alvo)
        if dias is None:
            mensagem = "Prazo de produção apagado."
        elif dados["previsao"]:
            mensagem = f"Produção: {texto_dos_dias(dias)} — previsão {dados['previsao']}."
        else:
            mensagem = f"Produção: {texto_dos_dias(dias)}."
        return JsonResponse({"status": "sucesso", "msg": mensagem, "prazo": dados})


# ======================================================================
# O ANDAMENTO DO PEDIDO DO SITE
# ======================================================================
ROTULO_DO_PASSO = {
    "pago": ("Pago", "bi-check2-circle"),
    "em_preparacao": ("Em preparação", "bi-tools"),
    "saiu_entrega": ("Saiu para entrega", "bi-truck"),
    "finalizado": ("Finalizado", "bi-flag-fill"),
    "cancelado": ("Cancelado", "bi-x-circle"),
}


def opcoes_de_andamento(pedido) -> list[dict]:
    """Os passos que a folha do painel oferece, na ordem do andamento."""
    return [
        {
            "valor": passo,
            "rotulo": ROTULO_DO_PASSO[passo][0],
            "icone": ROTULO_DO_PASSO[passo][1],
        }
        for passo in pedido.proximas_situacoes()
    ]


class AndamentoPedidoView(InternoRequiredMixin, View):
    """Leva o pedido ao próximo passo (ou volta um) e acerta a venda."""

    funcoes_necessarias = ANDAMENTO_DO_PEDIDO

    def post(self, request, pk):
        pedido = Pedido.objects.filter(pk=pk).first()
        if pedido is None:
            raise Http404
        nova = (request.POST.get("status") or "").strip()
        try:
            acao, venda_id = pedido.mudar_situacao(nova)
        except ValueError as erro:
            return _erro(str(erro))
        pedido.refresh_from_db()

        frase = f"Pedido #{pedido.pk}: {pedido.get_status_display().lower()}."
        if acao == "criada":
            frase += f" Registrado como venda #{venda_id}."
        elif acao == "desfeita":
            frase += f" A venda #{venda_id} saiu da receita."
        return JsonResponse({
            "status": "sucesso",
            "msg": frase,
            "situacao": pedido.status,
            "rotulo": pedido.get_status_display(),
            "venda": venda_id if pedido.pago else None,
            "venda_acao": acao,
            "opcoes": opcoes_de_andamento(pedido),
        })


# ======================================================================
# AS ETIQUETAS POR MÁQUINA
# ======================================================================
class EtiquetasDaOrigemView(FunilMixin, View):
    """A ficha que a folha de cópias desenha (JSON)."""

    def get(self, request, tipo, pk):
        from django.urls import reverse

        if tipo not in TIPOS:
            raise Http404
        objeto, alvo = self.origem_permitida(request, tipo, pk)
        if alvo is None:
            return _erro("Seu acesso não inclui as etiquetas deste registro.", status=403)
        ficha = ficha_de(objeto)
        if ficha is None:
            return _erro("Esta venda não tem pedido nem orçamento de origem.", status=404)
        prazo = dados_do_prazo(alvo)
        prazo["editavel"] = prazo_editavel(alvo)
        return JsonResponse({
            "status": "sucesso",
            "tipo": tipo,
            "id": objeto.pk,
            "titulo": ficha["titulo"],
            "nome": ficha["nome"],
            "referencia": ficha["referencia"],
            "pronta": ficha["pronta"],
            "motivo": ficha["motivo"],
            "maquinas": [maquina.como_dado() for maquina in ficha["maquinas"]],
            "tamanhos": [
                {"valor": valor, "rotulo": rotulo, "nota": nota, "por_folha": etq.POR_FOLHA[valor]}
                for valor, rotulo, nota in etq.TAMANHOS
            ],
            "tamanho": etq.TAMANHO_PADRAO,
            "copias_maximas": etq.COPIAS_MAXIMAS,
            "etiquetas_maximas": etq.ETIQUETAS_MAXIMAS,
            "prazo": prazo,
            "imprimir": reverse(
                "etiquetas_maquinas_imprimir", args=[tipo, objeto.pk],
                urlconf="sistema_interno.urls",
            ),
        })


class EtiquetasImpressaoView(FunilMixin, View):
    """As etiquetas em folhas A4: a página que vai para a impressora.

    As cópias chegam no endereço (`c=<máquina>:<cópias>`, uma por linha),
    e não por POST: imprimir de novo é recarregar, e o "voltar" do
    navegador não pergunta se pode reenviar um formulário.
    """

    template_name = "etiquetas_impressao.html"

    def get(self, request, tipo, pk):
        if tipo not in TIPOS:
            raise Http404
        objeto, alvo = self.origem_permitida(request, tipo, pk)
        if alvo is None:
            raise Http404
        ficha = ficha_de(objeto)
        if ficha is None:
            raise Http404

        tamanho = request.GET.get("tamanho")
        if tamanho not in etq.POR_FOLHA:
            tamanho = etq.TAMANHO_PADRAO
        por_folha = etq.POR_FOLHA[tamanho]
        copias = etq.ler_copias(request.GET.getlist("c"), ficha["maquinas"])
        total = etq.contar(ficha["maquinas"], copias)

        problema = ficha["motivo"] if not ficha["pronta"] else ""
        if not problema and total == 0:
            problema = "Nenhuma etiqueta: escolha ao menos uma cópia de uma máquina."
        if not problema and total > etq.ETIQUETAS_MAXIMAS:
            problema = (
                f"São {total} etiquetas. Imprima no máximo "
                f"{etq.ETIQUETAS_MAXIMAS} de uma vez (divida as máquinas)."
            )

        etiquetas = [] if problema else etq.montar_etiquetas(
            ficha, copias, hoje=timezone.localdate(),
        )
        aviso_principal = next(
            (rotulo, icone) for _, rotulo, icone, padrao in EtiquetasInnerView.AVISOS if padrao
        )
        return render(request, self.template_name, {
            "ficha": ficha,
            "empresa": identidade_da_empresa(),
            "tamanho": tamanho,
            "por_folha": por_folha,
            "folhas": etq.em_folhas(etiquetas, por_folha),
            "total": len(etiquetas),
            "total_folhas": etq.folhas_necessarias(len(etiquetas), por_folha),
            "problema": problema,
            "aviso_principal": {"rotulo": aviso_principal[0], "icone": aviso_principal[1]},
            "imprimir_ja": request.GET.get("imprimir") == "1" and not problema,
        }, status=400 if problema else 200)
