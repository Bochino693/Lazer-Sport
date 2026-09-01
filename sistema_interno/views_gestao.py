"""Financeiro, orçamentos e produção do painel interno.

Ficam separados de `views.py` — que cuida de estoque, materiais e das telas
operacionais — só por tamanho: os mixins de acesso e de resposta JSON são
reaproveitados de lá, então a regra de quem entra no subdomínio continua
escrita em um lugar só.
"""

import json
import logging
import re
import unicodedata
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from urllib.parse import quote

from django.contrib import messages
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from core.email_utils import (
    cnpj_empresa,
    dados_bancarios_empresa,
    diagnostico_smtp,
    nome_empresa,
    remetente,
    responder_para,
    smtp_configurado,
)
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import (
    Case,
    Count,
    DecimalField,
    F,
    IntegerField,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Greatest
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import View

from core.models import (
    Brinquedos,
    CategoriaPeca,
    CategoriasBrinquedos,
    Estabelecimentos,
    PecasReposicao,
)

from .busca_local import montar_indice
from . import clientes as svc_clientes
from . import etapas_padrao
from . import financeiro as fin
from .models import (
    AtividadeOrcamento,
    Cliente,
    Colaborador,
    EnvioOrcamento,
    ItemOrdemServico,
    ExecucaoEtapaProducao,
    GuiaEtapaProducao,
    HistoricoProducao,
    ImagemGuiaProducao,
    ItemFichaTecnica,
    ItemOrcamento,
    Material,
    AvaliacaoBlocoOrcamento,
    Orcamento,
    OrdemServico,
    OrdemProducao,
    ProdutoInterno,
    Setores,
)
from .exclusoes import forcando, pode_excluir, remover
from . import pecas as svc_pecas
from .permissoes import (
    capacidades,
    limitar_orcamentos,
    origem_padrao_orcamento,
    pode_excluir_orcamento,
)
from .utils import (
    ErroDeFormulario,
    data,
    decimal_br,
    endereco_do_site,
    exigir_confirmacao_exclusao,
    inteiro,
    texto,
)
from .views import (
    FinanceiroInternoRequiredMixin,
    InternoRequiredMixin,
    OrcamentoInternoRequiredMixin,
    OrdemServicoInternoRequiredMixin,
    ProducaoInternoRequiredMixin,
    RespostaJSONMixin,
)

ZERO = Decimal("0.00")


def moeda_br(valor):
    """Dinheiro para mensagens fora dos templates: 4666.33 -> 4.666,33."""
    numero = Decimal(valor or ZERO).quantize(Decimal("0.01"))
    return f"{numero:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def registrar_atividade_orcamento(orcamento, request, tipo, resumo=""):
    """Notifica os colegas sem transformar o histórico em ponto de falha.

    Se uma implantação ainda não executou a migration nova, salvar a proposta
    continua funcionando e o erro fica explícito no log. Depois do migrate, o
    mesmo caminho passa a alimentar o sino normalmente.
    """
    try:
        return AtividadeOrcamento.registrar(
            orcamento,
            request.user,
            tipo,
            resumo=resumo,
        )
    except Exception:
        logging.getLogger(__name__).exception(
            "Não consegui registrar a atividade do orçamento %s",
            getattr(orcamento, "pk", None),
        )
        return None


# ======================================================================
# FINANCEIRO
# ======================================================================
class FinanceiroInnerView(FinanceiroInternoRequiredMixin, View):
    """Receita, saída, lucro e composição das despesas.

    Os gráficos são SVG/CSS montados a partir de números já calculados no
    servidor: a tela abre desenhada, sem esperar script de biblioteca.

    Exige gestor, e não só conta de equipe: faturamento, margem e despesa
    são mais sensíveis do que a lista de produtos, que já pedia gestor.
    Quem monta brinquedo continua entrando pela Minha Produção.
    """

    JANELAS = (6, 12, 24)

    def get(self, request):
        try:
            janela = int(request.GET.get("meses", 12))
        except (TypeError, ValueError):
            janela = 12

        if janela not in self.JANELAS:
            janela = 12

        meses = fin.janela_de_meses(janela)
        serie = fin.montar_series(meses)
        teto = fin.aplicar_alturas(serie)

        ctx = {
            "janela": janela,
            "janelas": self.JANELAS,
            "serie": serie,
            "teto": teto,
            "curva": fin.curva_de_lucro(serie),
            "categorias": fin.despesas_por_categoria(meses[0]),
            "funil": fin.funil_de_orcamentos(meses[0]),
            "origens_comerciais": fin.orcamentos_por_origem(meses[0]),
            "inicio": meses[0],
            "fim": meses[-1],
        }
        ctx.update(fin.indicadores(serie))

        return render(request, "financeiro_inner.html", ctx)


# ======================================================================
# ORÇAMENTOS
# ======================================================================
class OrcamentosInnerView(RespostaJSONMixin, OrcamentoInternoRequiredMixin, View):
    """Lista e monta orçamentos, com os itens em uma requisição só.

    Gestor também: aqui se vê preço de cliente e margem, e daqui se cria
    proposta em nome da empresa.
    """

    rota_padrao = "orcamentos_inner"

    # O envio registra a tentativa -- inclusive quando falha. Dentro da
    # transação, o rollback do erro levaria o registro junto e o histórico
    # perderia justamente a linha que explica o "não chegou".
    ACOES_SEM_TRANSACAO = ("enviar",)

    # ------------------------------------------------------------ leitura
    #: Quantas propostas por página.
    #:
    #: A tela NÃO era paginada, e cada linha carrega muito: os itens, o
    #: texto pronto do WhatsApp e a proposta inteira em JSON para o modal
    #: de edição. Com 400 propostas isso dava 2 MB de HTML; com alguns
    #: milhares o servidor estourava o tempo do gunicorn e a resposta virava
    #: 502. O peso agora é o da página, e não o do histórico da empresa.
    POR_PAGINA = 25

    #: Soma dos itens de UMA proposta, sem multiplicar linhas.
    #:
    #: Como subconsulta, e não como `annotate` com join: a busca já entra
    #: por `itens__descricao`, e um segundo join faria a soma contar o
    #: mesmo item várias vezes -- o total apareceria inflado justamente
    #: quando alguém filtrasse por texto.
    @staticmethod
    def _subtotal_por_proposta():
        return Subquery(
            ItemOrcamento.objects
            .filter(orcamento=OuterRef("pk"))
            .values("orcamento")
            .annotate(
                soma=Sum(
                    F("quantidade") * F("valor_unitario"),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            )
            .values("soma")[:1],
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )

    @classmethod
    def resumo_do_filtro(cls, consulta):
        """Os números do topo somam o FILTRO INTEIRO, não a página.

        "Aprovado" é o que a empresa fechou; se mudasse ao virar de página
        deixaria de responder qualquer coisa.
        """
        zero = Value(Decimal("0.00"), output_field=DecimalField(max_digits=12, decimal_places=2))
        com_total = (
            consulta
            .annotate(_subtotal=Coalesce(cls._subtotal_por_proposta(), zero))
            .annotate(
                _total=Greatest(
                    F("_subtotal")
                    + Coalesce(F("frete"), zero)
                    - Coalesce(F("desconto"), zero),
                    zero,
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            )
        )
        em_aberto = Q(status__in=Orcamento.EM_ABERTO)
        aprovado = Q(status=Orcamento.Status.APROVADO)
        aguardando = Q(status=Orcamento.Status.AGUARDANDO_RESPOSTA)
        negociacao = Q(status=Orcamento.Status.EM_NEGOCIACAO)
        recusado = Q(status=Orcamento.Status.RECUSADO)
        expirado = Q(status=Orcamento.Status.EXPIRADO)
        substituido = Q(status=Orcamento.Status.SUBSTITUIDO)
        pagamento_pendente = aprovado & ~Q(
            status_pagamento=Orcamento.StatusPagamento.PAGO
        )
        pago = Q(status_pagamento=Orcamento.StatusPagamento.PAGO)

        return com_total.aggregate(
            quantidade=Count("pk", distinct=True),
            quantidade_atual=Count(
                "pk", filter=~substituido, distinct=True,
            ),
            total_aprovado=Coalesce(Sum("_total", filter=aprovado), zero),
            total_em_aberto=Coalesce(Sum("_total", filter=em_aberto), zero),
            quantidade_aprovado=Count("pk", filter=aprovado, distinct=True),
            quantidade_aberto=Count("pk", filter=em_aberto, distinct=True),
            quantidade_rascunho=Count(
                "pk", filter=Q(status=Orcamento.Status.RASCUNHO), distinct=True,
            ),
            quantidade_aguardando=Count("pk", filter=aguardando, distinct=True),
            quantidade_negociacao=Count("pk", filter=negociacao, distinct=True),
            quantidade_recusado=Count("pk", filter=recusado, distinct=True),
            quantidade_expirado=Count("pk", filter=expirado, distinct=True),
            quantidade_substituido=Count("pk", filter=substituido, distinct=True),
            quantidade_pagamento_pendente=Count(
                "pk", filter=pagamento_pendente, distinct=True,
            ),
            quantidade_pago=Count("pk", filter=pago, distinct=True),
            total_recebido=Coalesce(Sum("valor_pago", filter=pago | aprovado), zero),
            total_a_receber=Coalesce(
                Sum(
                    Greatest(
                        F("_total") - Coalesce(F("valor_pago"), zero),
                        zero,
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    ),
                    filter=aprovado,
                ),
                zero,
            ),
            quantidade_interno=Count(
                "pk", filter=Q(origem=Orcamento.Origem.INTERNO), distinct=True,
            ),
            quantidade_ambulante=Count(
                "pk", filter=Q(origem=Orcamento.Origem.AMBULANTE), distinct=True,
            ),
        )

    def indice_de_busca(self, consulta):
        """Os mesmos campos que a busca do servidor percorre.

        Se as duas listas divergirem, a pessoa vê um resultado ao digitar
        e outro ao apertar "Trazer todos" -- e passa a não confiar em
        nenhum dos dois.
        """
        base = list(
            consulta.values_list("pk", "nome_cliente", "cliente__nome_cliente",
                                 "contato", "observacoes")
        )
        # Os itens vêm numa consulta só, e não uma por proposta.
        itens = defaultdict(list)
        for orcamento_id, descricao in ItemOrcamento.objects.filter(
            orcamento_id__in=[linha[0] for linha in base]
        ).values_list("orcamento_id", "descricao"):
            itens[orcamento_id].append(descricao)

        return montar_indice(
            (pk, [str(pk), nome, nome_cadastro, contato, observacoes]
                 + itens.get(pk, []))
            for pk, nome, nome_cadastro, contato, observacoes in base
        )

    def get(self, request):
        busca = (request.GET.get("q") or "").strip()
        filtro_card = (request.GET.get("filtro") or "todos").strip()
        origem = (request.GET.get("origem") or "").strip()

        orcamentos = limitar_orcamentos(request.user, (
            Orcamento.objects
            .select_related(
                "cliente", "cliente__parceiro", "responsavel",
                "orcamento_anterior", "orcamento_refeito", "ordem_servico",
            )
            .prefetch_related(
                "cliente__enderecos",
                Prefetch(
                    "avaliacoes_blocos",
                    queryset=AvaliacaoBlocoOrcamento.objects.select_related(
                        "avaliador"
                    ),
                ),
                Prefetch(
                    "itens",
                    queryset=ItemOrcamento.objects
                    .select_related("brinquedo", "produto__brinquedo", "peca")
                    .prefetch_related("peca__imagem_peca_reposicao"),
                )
            )
        ))

        if busca:
            filtro = (
                Q(nome_cliente__icontains=busca)
                | Q(cliente__nome_cliente__icontains=busca)
                | Q(contato__icontains=busca)
                | Q(observacoes__icontains=busca)
                | Q(itens__descricao__icontains=busca)
            )
            if busca.isdigit():
                filtro |= Q(pk=int(busca))
            orcamentos = orcamentos.filter(filtro).distinct()

        if origem in Orcamento.Origem.values:
            orcamentos = orcamentos.filter(origem=origem)

        # As quantidades dos cards vêm da busca, antes de aplicar o card
        # selecionado. Assim cada card continua mostrando o tamanho real
        # da sua fila e não vira zero depois do clique.
        resumo_cards = self.resumo_do_filtro(orcamentos)

        filtros_cards = {
            # "Todos" mostra as propostas vigentes. Versões substituídas
            # continuam disponíveis, mas somente no filtro dedicado; misturar
            # as duas fazia a mesma negociação parecer vários orçamentos.
            "todos": ~Q(status=Orcamento.Status.SUBSTITUIDO),
            "rascunhos": Q(status=Orcamento.Status.RASCUNHO),
            "aguardando": Q(status=Orcamento.Status.AGUARDANDO_RESPOSTA),
            "negociacao": Q(status=Orcamento.Status.EM_NEGOCIACAO),
            "aprovados": Q(status=Orcamento.Status.APROVADO),
            "recusados": Q(status=Orcamento.Status.RECUSADO),
            "expirados": Q(status=Orcamento.Status.EXPIRADO),
            "substituidos": Q(status=Orcamento.Status.SUBSTITUIDO),
            "a_receber": Q(status=Orcamento.Status.APROVADO) & ~Q(
                status_pagamento=Orcamento.StatusPagamento.PAGO
            ),
            "pagos": Q(status_pagamento=Orcamento.StatusPagamento.PAGO),
        }
        if filtro_card not in filtros_cards:
            filtro_card = "todos"
        orcamentos = orcamentos.filter(filtros_cards[filtro_card])

        # O RESUMO SAI DO FILTRO INTEIRO, a página é só o que se desenha.
        resumo = self.resumo_do_filtro(orcamentos)

        # O ÍNDICE TAMBÉM SAI DO FILTRO INTEIRO. A tela desenha 25 linhas,
        # mas quem digita procura entre todas: sem isto o navegador diria
        # "nada encontrado" sobre uma proposta que existe na página 2.
        indice_busca = self.indice_de_busca(orcamentos)

        hoje = timezone.localdate()
        vencendo = list(
            orcamentos.filter(
                status__in=Orcamento.EM_ABERTO,
                validade__gte=hoje,
                validade__lte=hoje + timedelta(days=3),
            ).order_by("validade", "pk")[:20]
        )

        pagina = Paginator(orcamentos, self.POR_PAGINA).get_page(
            request.GET.get("page")
        )
        orcamentos = list(pagina.object_list)

        # LINK E CONVERSA JÁ VÊM PRONTOS DO SERVIDOR.
        #
        # Antes o modal pedia os dois por POST ao abrir. Qualquer tropeço
        # nessa ida -- e bastou uma tabela de histórico ainda não migrada
        # para derrubá-la -- deixava a tela com "Link indisponível" e o
        # botão do WhatsApp girando sem fim, num orçamento que estava
        # perfeito. Montados aqui, aparecem na hora e não dependem de mais
        # nada; o POST continua existindo, mas só para registrar o envio.
        base_publica = endereco_do_site(request)
        for orcamento in orcamentos:
            avaliacoes = {
                avaliacao.bloco: avaliacao
                for avaliacao in orcamento.avaliacoes_blocos.all()
            }
            orcamento.bloco_comercial = avaliacoes.get(
                AvaliacaoBlocoOrcamento.Bloco.COMERCIAL
            )
            orcamento.bloco_financeiro = avaliacoes.get(
                AvaliacaoBlocoOrcamento.Bloco.FINANCEIRO
            )
            orcamento.blocos_aprovados = all(
                avaliacao
                and avaliacao.status == AvaliacaoBlocoOrcamento.Status.APROVADO
                for avaliacao in (
                    orcamento.bloco_comercial,
                    orcamento.bloco_financeiro,
                )
            )
            # O LINK SÓ EXISTE DEPOIS DE A PROPOSTA SAIR DO RASCUNHO.
            #
            # A página do cliente recusa rascunho com 404. Entregar o
            # endereço mesmo assim fazia a janela de envio abrir já com o
            # botão "Abrir" apontando para uma página de erro -- e quem
            # conferia antes de mandar concluía que o sistema tinha
            # quebrado. Vazio aqui, a janela mostra "Gerando link seguro…"
            # e o próprio envio devolve o endereço quando ele passa a
            # valer.
            orcamento.link_publico = (
                f"{base_publica}{orcamento.caminho_publico}"
                if orcamento.publicado else ""
            )
            orcamento.mensagem_whatsapp = (
                self.mensagem_da_proposta(orcamento, orcamento.link_publico)
                if orcamento.link_publico else ""
            )
            orcamento.conversa_url = self.conversa_whatsapp(
                orcamento.whatsapp_destinatario,
                orcamento.mensagem_whatsapp,
            )
            orcamento.pode_excluir = pode_excluir_orcamento(
                request.user,
                orcamento,
            )
            # O superusuário enxerga o botão em qualquer proposta: ele
            # tem a palavra final. `protegida` diz à janela de confirmação
            # que ali a exclusão passa POR CIMA de uma regra, e que vai
            # ficar registrada -- apagar histórico não pode ter a mesma
            # cara de apagar um rascunho.
            orcamento.protegida = not orcamento.pode_excluir
            if not orcamento.pode_excluir and request.user.is_superuser:
                orcamento.pode_excluir = True

        buffets = list(
            Cliente.objects.filter(tipo=Cliente.Tipo.BUFFET).order_by("nome_cliente")
        )

        acesso = capacidades(request.user)
        ctx = {
            "orcamentos": orcamentos,
            "busca": busca,
            "filtro_ativo": filtro_card,
            "cards": (
                ("todos", "Todos", resumo_cards["quantidade_atual"], "bi-grid"),
                ("rascunhos", "Rascunhos", resumo_cards["quantidade_rascunho"], "bi-pencil-square"),
                ("aguardando", "Aguardando resposta", resumo_cards["quantidade_aguardando"], "bi-hourglass-split"),
                ("negociacao", "Em negociação", resumo_cards["quantidade_negociacao"], "bi-arrow-repeat"),
                ("aprovados", "Aprovados", resumo_cards["quantidade_aprovado"], "bi-patch-check"),
                ("recusados", "Recusados", resumo_cards["quantidade_recusado"], "bi-x-circle"),
                ("expirados", "Expirados", resumo_cards["quantidade_expirado"], "bi-calendar-x"),
                ("substituidos", "Versões anteriores", resumo_cards["quantidade_substituido"], "bi-clock-history"),
                ("a_receber", "A receber", resumo_cards["quantidade_pagamento_pendente"], "bi-wallet2"),
                ("pagos", "Pagos", resumo_cards["quantidade_pago"], "bi-cash-coin"),
            ),
            "status_opcoes": Orcamento.Status.choices,
            # O prazo padrão vem do modelo, não escrito de novo no
            # template: o atalho da tela, o texto de ajuda e o valor que o
            # servidor aplica quando o campo chega vazio são o mesmo
            # número, e mudá-lo é mexer num lugar só.
            "validade_padrao_dias": Orcamento.DIAS_DE_VALIDADE_PADRAO,
            "origem_ativa": origem,
            "origem_opcoes": Orcamento.Origem.choices,
            "origem_nova": origem_padrao_orcamento(request.user),
            "origem_nova_rotulo": dict(Orcamento.Origem.choices)[
                origem_padrao_orcamento(request.user)
            ],
            # O CATÁLOGO É A ORIGEM PADRÃO DOS ITENS. Antes o seletor só
            # oferecia ProdutoInterno -- o que a fábrica monta --, e quem
            # orça aluguel de brinquedo tinha de digitar tudo à mão, com
            # nome e preço fora do que está publicado no site.
            "total_itens_disponiveis": (
                Brinquedos.objects.count()
                + ProdutoInterno.objects.filter(ativo=True).count()
                + PecasReposicao.objects.filter(ativo=True).count()
            ),
            "categorias": CategoriasBrinquedos.objects.order_by("nome_categoria"),
            "categorias_peca": CategoriaPeca.objects.order_by("nome_categoria_peca"),
            "hoje": timezone.localdate(),
            "page_obj": pagina,
            "indice_busca": indice_busca,
            "total_orcamentos": resumo["quantidade"],
            "total_aprovado": resumo["total_aprovado"],
            "total_em_aberto": resumo["total_em_aberto"],
            "quantidade_aberto": resumo["quantidade_aberto"],
            "quantidade_aprovado": resumo["quantidade_aprovado"],
            "quantidade_interno": resumo["quantidade_interno"],
            "quantidade_ambulante": resumo["quantidade_ambulante"],
            "total_recebido": resumo_cards["total_recebido"],
            "total_a_receber": resumo_cards["total_a_receber"],
            "orcamentos_dados": [self.serializar(o) for o in orcamentos],
            # A busca de item vem por endpoint e nunca despeja o catálogo
            # inteiro nesta página. b:/p:/r: identificam brinquedo,
            # produção e reposição quando a linha é enviada.
            "tipos_cliente": Cliente.Tipo.choices,
            # O gestor precisa saber ANTES de tentar que o e-mail não sai
            # daqui: sem isso, "enviei e não chegou" vira mistério.
            "email_configurado": smtp_configurado(),
            "email_diagnostico": diagnostico_smtp(),
            "buffets": buffets,
            "estabelecimentos": Estabelecimentos.objects.order_by(
                "nome_estabelecimento"
            ),
            # A página do cliente mora no site principal, não aqui.
            "base_publica": endereco_do_site(request),
            # O AVISO DE VENCIMENTO OLHA O FILTRO INTEIRO, não a página.
            #
            # Varrer só a página esconderia justamente a proposta que
            # vence amanhã e caiu na página 3 -- que é a única para a
            # qual este aviso existe.
            "vencendo": vencendo,
            "pode_criar_orcamento": acesso["orcamentos_criar"],
            "pode_editar_comercial": acesso["orcamentos_editar_comercial"],
            "pode_editar_financeiro": acesso["orcamentos_editar_financeiro"],
            "pode_avaliar_blocos": acesso["avaliar_blocos_orcamento"],
            "pode_ordens_servico": acesso["ordens_servico"],
            "blocos_opcoes": AvaliacaoBlocoOrcamento.Bloco.choices,
            "avaliacao_status_opcoes": (
                (AvaliacaoBlocoOrcamento.Status.APROVADO, "Aprovar"),
                (AvaliacaoBlocoOrcamento.Status.AJUSTES, "Solicitar ajustes"),
            ),
        }
        return render(request, "orcamentos_inner.html", ctx)

    @staticmethod
    def serializar(orcamento):
        """Payload que o modal usa para reabrir um orçamento já salvo."""
        return {
            "id": orcamento.id,
            "cliente": orcamento.cliente_id or "",
            "cliente_opcao": (
                svc_clientes.opcao_de_busca(orcamento.cliente)
                if orcamento.cliente_id and orcamento.cliente else None
            ),
            "nome_cliente": orcamento.nome_cliente,
            "contato": orcamento.contato,
            "whatsapp_cliente": orcamento.whatsapp_destinatario,
            "email_cliente": orcamento.email_destinatario,
            "status": orcamento.status,
            "pode_editar": orcamento.pode_editar,
            "versao": orcamento.versao,
            "orcamento_anterior": orcamento.orcamento_anterior_id or "",
            # AS VERSÕES ANTERIORES VIAJAM COM A PROPOSTA, E NÃO NA LISTA.
            #
            # Na lista elas continuam fora do "todos": misturadas, a
            # mesma negociação parece três orçamentos. Mas sumir da lista
            # não é sumir -- quando o cliente liga perguntando do preço
            # antigo, é aqui dentro que se responde. Só a corrente vem:
            # número, versão, situação, total e data, que é o suficiente
            # para achar e abrir a que interessa.
            "versoes": [
                {
                    "id": versao.pk,
                    "versao": versao.versao,
                    "status": versao.status,
                    "rotulo": versao.get_status_display(),
                    "total": f"{versao.total:.2f}".replace(".", ","),
                    "quando": (
                        timezone.localtime(versao.criacao).strftime("%d/%m/%Y")
                        if versao.criacao else ""
                    ),
                    "motivo": versao.motivo_negociacao,
                    "atual": versao.pk == orcamento.pk,
                    # A PRÉVIA, E NÃO O MODAL.
                    #
                    # A versão substituída não está na lista da página --
                    # é justamente por isso que ela precisa aparecer
                    # aqui. Mandar o modal reabri-la pelo id acharia
                    # nada e desenharia um formulário em branco como se
                    # fosse proposta nova. A prévia lê do servidor e
                    # serve a qualquer versão, em qualquer situação.
                    "previa": reverse(
                        "orcamento_previa_inner", args=[versao.pk],
                        urlconf="sistema_interno.urls",
                    ),
                }
                for versao in orcamento.cadeia_de_versoes()
            ] if orcamento.versao > 1 or orcamento.orcamento_anterior_id else [],
            "motivo_negociacao": orcamento.motivo_negociacao,
            "status_pagamento": orcamento.status_pagamento,
            "valor_pago": f"{orcamento.valor_pago:.2f}".replace(".", ","),
            "saldo_pagamento": f"{orcamento.saldo_pagamento:.2f}".replace(".", ","),
            "total": f"{orcamento.total:.2f}".replace(".", ","),
            "pode_receber_pagamento": orcamento.pode_receber_pagamento,
            "origem": orcamento.origem,
            "origem_rotulo": orcamento.get_origem_display(),
            "bloco_comercial": OrcamentosInnerView.serializar_avaliacao(
                getattr(orcamento, "bloco_comercial", None)
            ),
            "bloco_financeiro": OrcamentosInnerView.serializar_avaliacao(
                getattr(orcamento, "bloco_financeiro", None)
            ),
            "blocos_aprovados": getattr(orcamento, "blocos_aprovados", False),
            "validade": orcamento.validade.isoformat() if orcamento.validade else "",
            "desconto": f"{orcamento.desconto:.2f}".replace(".", ","),
            "frete": f"{orcamento.frete:.2f}".replace(".", ","),
            "forma_pagamento": orcamento.forma_pagamento,
            "forma_envio": orcamento.forma_envio,
            "observacoes": orcamento.observacoes,
            "itens": [
                {
                    "descricao": item.descricao,
                    "brinquedo": item.brinquedo_id or "",
                    "produto": item.produto_id or "",
                    "peca": item.peca_id or "",
                    "opcao": OrcamentosInnerView.opcao_do_item(item),
                    "quantidade": item.quantidade,
                    "valor_unitario": f"{item.valor_unitario:.2f}".replace(".", ","),
                }
                for item in orcamento.itens.all()
            ],
        }

    @staticmethod
    def serializar_avaliacao(avaliacao):
        if not avaliacao:
            return {
                "status": AvaliacaoBlocoOrcamento.Status.PENDENTE,
                "rotulo": AvaliacaoBlocoOrcamento.Status.PENDENTE.label,
                "observacao": "",
            }
        return {
            "status": avaliacao.status,
            "rotulo": avaliacao.get_status_display(),
            "observacao": avaliacao.observacao,
            "avaliado_em": (
                timezone.localtime(avaliacao.avaliado_em).strftime("%d/%m/%Y %H:%M")
                if avaliacao.avaliado_em else ""
            ),
            "avaliador": (
                avaliacao.avaliador.get_full_name()
                or avaliacao.avaliador.username
                if avaliacao.avaliador else ""
            ),
        }

    @staticmethod
    def _url_imagem(arquivo):
        try:
            return arquivo.url if arquivo else ""
        except (AttributeError, ValueError):
            return ""

    @classmethod
    def opcao_brinquedo(cls, brinquedo):
        return {
            "valor": f"b:{brinquedo.id}",
            "rotulo": brinquedo.nome_brinquedo,
            "grupo": "Brinquedos",
            "detalhe": (brinquedo.descricao or "Brinquedo do catálogo")[:90],
            "valorDireita": (
                f"R$ {brinquedo.valor_brinquedo:.2f}".replace(".", ",")
                if brinquedo.valor_brinquedo is not None else "sob consulta"
            ),
            "preco": (
                f"{brinquedo.valor_brinquedo:.2f}".replace(".", ",")
                if brinquedo.valor_brinquedo is not None else ""
            ),
            "imagem": cls._url_imagem(brinquedo.imagem_brinquedo),
        }

    @classmethod
    def opcao_produto(cls, produto):
        imagem = (
            produto.brinquedo.imagem_brinquedo
            if produto.brinquedo_id and produto.brinquedo else None
        )
        return {
            "valor": f"p:{produto.id}",
            "rotulo": produto.nome,
            "grupo": "Produção",
            "detalhe": (
                produto.descricao[:90]
                if produto.descricao else produto.get_categoria_display()
            ),
            "valorDireita": (
                f"R$ {produto.preco_venda:.2f}".replace(".", ",")
                if produto.preco_venda is not None else "sem preço"
            ),
            "preco": (
                f"{produto.preco_venda:.2f}".replace(".", ",")
                if produto.preco_venda is not None else ""
            ),
            "imagem": cls._url_imagem(imagem),
        }

    @classmethod
    def opcao_peca(cls, peca):
        imagem = peca.imagem_principal
        de_manutencao = peca.uso == PecasReposicao.Uso.MANUTENCAO
        return {
            "valor": f"r:{peca.id}",
            "rotulo": peca.nome,
            # O grupo é o que separa, na lista, o que a loja vende do que
            # a oficina consome. Sem ele os dois viram a mesma linha, e o
            # custo interno entra numa proposta sem ninguém notar.
            "grupo": (
                "Itens de manutenção" if de_manutencao
                else "Peças de reposição"
            ),
            "detalhe": (
                peca.descricao_peca
                or ("Item de manutenção" if de_manutencao else "Peça da loja")
            )[:90],
            "valorDireita": (
                f"R$ {peca.preco_venda:.2f}".replace(".", ",")
                if peca.preco_venda is not None else "sem preço"
            ),
            "preco": (
                f"{peca.preco_venda:.2f}".replace(".", ",")
                if peca.preco_venda is not None else ""
            ),
            "imagem": cls._url_imagem(imagem.imagem if imagem else None),
        }

    @classmethod
    def opcao_do_item(cls, item):
        if item.brinquedo_id and item.brinquedo:
            return cls.opcao_brinquedo(item.brinquedo)
        if item.produto_id and item.produto:
            return cls.opcao_produto(item.produto)
        if item.peca_id and item.peca:
            return cls.opcao_peca(item.peca)
        return None

    # ------------------------------------------------------------- ações
    @staticmethod
    def _orcamento_do_usuario(request, pk):
        return get_object_or_404(
            limitar_orcamentos(request.user, Orcamento.objects.all()),
            pk=pk,
        )

    @staticmethod
    def _validade(request, *, novo):
        """Até quando a proposta vale -- nunca para trás, nunca vazia por esquecimento.

        DUAS REGRAS, E CADA UMA RESOLVE UM PROBLEMA DIFERENTE.

        1. Proposta nova sem prazo escolhido nasce com cinco dias. Antes o
           campo vinha vazio, e proposta sem prazo não entra na fila de
           cobrança da central de avisos: ficava parada esperando uma
           resposta que ninguém ia cobrar. Quem quiser outro prazo escreve
           no campo, e quem quiser mesmo sem prazo tem o botão "Sem prazo"
           -- a diferença é que agora isso é uma ESCOLHA, e não um
           esquecimento.

        2. Data já passada é recusada. Um orçamento com validade de ontem
           sai da fábrica vencido: o cliente abre a página e lê "proposta
           expirada" num documento que acabou de receber. A tela já evita
           (o campo tem `min` de hoje e o atalho de 5 dias), mas a tela é
           sugestão -- quem decide é aqui, que é o único caminho por onde
           os dados entram.
        """
        escolhida = data(request.POST.get("validade"), "Validade")

        if escolhida is None:
            return Orcamento.validade_padrao() if novo else None

        if escolhida < timezone.localdate():
            raise ErroDeFormulario(
                "A validade não pode ser anterior a hoje: a proposta sairia "
                "vencida. Use o atalho de "
                f"{Orcamento.DIAS_DE_VALIDADE_PADRAO} dias ou escolha outra data."
            )
        return escolhida

    def acao_save(self, request):
        orcamento_id = request.POST.get("id")
        acesso = capacidades(request.user)
        novo = not bool(orcamento_id)
        if novo and not acesso["orcamentos_criar"]:
            return self.erro(
                request,
                "O Financeiro participa de propostas existentes; a criação cabe ao Comercial.",
                status=403,
            )

        orcamento = (
            self._orcamento_do_usuario(request, orcamento_id)
            if orcamento_id else Orcamento()
        )
        if orcamento.pk and not orcamento.pode_editar:
            return self.erro(
                request,
                (
                    "Uma proposta já enviada não pode ser sobrescrita. "
                    "Use ‘Refazer proposta’ para criar uma nova versão e "
                    "preservar o que o cliente recebeu."
                ),
                status=409,
            )
        comercial_antes = self._assinatura_comercial(orcamento) if orcamento.pk else None
        financeiro_antes = self._assinatura_financeira(orcamento) if orcamento.pk else None

        if acesso["orcamentos_editar_comercial"]:
            cliente_id = (request.POST.get("cliente") or "").strip()
            orcamento.cliente = (
                get_object_or_404(Cliente, pk=cliente_id)
                if cliente_id.isdigit() else None
            )
            orcamento.nome_cliente = texto(request, "nome_cliente", limite=120)
            orcamento.contato = texto(request, "contato", limite=120)
            orcamento.whatsapp_cliente = texto(request, "whatsapp_cliente", limite=24)
            orcamento.email_cliente = texto(request, "email_cliente", limite=254)

            if orcamento.email_cliente:
                try:
                    validate_email(orcamento.email_cliente)
                except ValidationError:
                    raise ErroDeFormulario("Informe um e-mail válido para o cliente.")
            if not orcamento.cliente and not orcamento.nome_cliente:
                raise ErroDeFormulario(
                    "Escolha um cliente cadastrado ou escreva o nome do destinatário."
                )

            # Situação não é campo de edição: rascunho vira aguardando
            # resposta ao enviar; decisão e negociação têm ações próprias.
            orcamento.status = Orcamento.Status.RASCUNHO
            orcamento.validade = self._validade(request, novo=novo)
            orcamento.forma_envio = texto(request, "forma_envio", limite=120)
            orcamento.observacoes = texto(request, "observacoes")

        if acesso["orcamentos_editar_financeiro"]:
            orcamento.desconto = decimal_br(
                request.POST.get("desconto"), "Desconto",
                limite=Decimal("9999999999.99"),
            ) or ZERO
            orcamento.frete = decimal_br(
                request.POST.get("frete"), "Frete",
                limite=Decimal("9999999999.99"),
            ) or ZERO
            orcamento.forma_pagamento = texto(
                request, "forma_pagamento", limite=120,
            )

        if not orcamento.pk:
            orcamento.responsavel = request.user
            orcamento.origem = origem_padrao_orcamento(request.user)

        orcamento.save()
        if acesso["orcamentos_editar_comercial"]:
            self._gravar_itens(orcamento, request.POST.get("itens"))

        comercial_mudou = novo or comercial_antes != self._assinatura_comercial(orcamento)
        financeiro_mudou = novo or financeiro_antes != self._assinatura_financeira(orcamento)
        if comercial_mudou:
            self._reabrir_bloco(orcamento, AvaliacaoBlocoOrcamento.Bloco.COMERCIAL)
        if financeiro_mudou:
            self._reabrir_bloco(orcamento, AvaliacaoBlocoOrcamento.Bloco.FINANCEIRO)

        registrar_atividade_orcamento(
            orcamento,
            request,
            (
                AtividadeOrcamento.Tipo.CRIADO
                if novo else AtividadeOrcamento.Tipo.ALTERADO
            ),
        )

        mapa = orcamento.sincronizar_cliente_aprovado()

        complemento = ""
        if mapa and mapa.latitude and mapa.longitude:
            complemento = " Cliente atualizado no mapa do site."
        elif orcamento.status == Orcamento.Status.APROVADO and orcamento.cliente_id:
            complemento = " Para aparecer no mapa, complete o endereço do cliente."

        return self.sucesso(
            request,
            f"Orçamento #{orcamento.pk} salvo — total {orcamento.total}.{complemento}",
            id=orcamento.pk,
            mapa_publicado=bool(mapa and mapa.latitude and mapa.longitude),
        )

    @staticmethod
    def _assinatura_comercial(orcamento):
        if not orcamento.pk:
            return None
        itens = tuple(
            orcamento.itens.order_by("id").values_list(
                "descricao", "brinquedo_id", "produto_id", "peca_id",
                "quantidade", "valor_unitario",
            )
        )
        return (
            orcamento.cliente_id, orcamento.nome_cliente, orcamento.contato,
            orcamento.whatsapp_cliente, orcamento.email_cliente,
            orcamento.status, orcamento.validade, orcamento.forma_envio,
            orcamento.observacoes, itens,
        )

    @staticmethod
    def _assinatura_financeira(orcamento):
        if not orcamento.pk:
            return None
        return orcamento.desconto, orcamento.frete, orcamento.forma_pagamento

    @staticmethod
    def _reabrir_bloco(orcamento, bloco):
        AvaliacaoBlocoOrcamento.objects.update_or_create(
            orcamento=orcamento,
            bloco=bloco,
            defaults={
                "status": AvaliacaoBlocoOrcamento.Status.PENDENTE,
                "observacao": "",
                "avaliador": None,
                "avaliado_em": None,
            },
        )

    def _gravar_itens(self, orcamento, bruto):
        """Recebe os itens como JSON e regrava a lista inteira.

        Regravar é mais simples e mais seguro do que casar item a item: o
        modal sempre envia a lista completa, então uma linha removida na tela
        some do banco sem precisar de um "delete" separado que poderia
        divergir do que o usuário está vendo.
        """
        if bruto is None:
            return

        try:
            linhas = json.loads(bruto or "[]")
        except (TypeError, ValueError):
            raise ErroDeFormulario("Não consegui ler os itens do orçamento.")

        if not isinstance(linhas, list):
            raise ErroDeFormulario("Formato inválido na lista de itens.")

        if not linhas:
            raise ErroDeFormulario("Adicione pelo menos um item ao orçamento.")

        if len(linhas) > 60:
            raise ErroDeFormulario("Um orçamento aceita no máximo 60 itens.")

        novos = []
        for posicao, linha in enumerate(linhas, start=1):
            if not isinstance(linha, dict):
                raise ErroDeFormulario(f"Item {posicao}: formato inválido.")

            descricao = (linha.get("descricao") or "").strip()
            if not descricao:
                raise ErroDeFormulario(f"Item {posicao}: informe a descrição.")

            quantidade = inteiro(
                str(linha.get("quantidade") or ""),
                f"Item {posicao}: quantidade",
                obrigatorio=True,
                minimo=1,
                maximo=100000,
            )
            valor = decimal_br(
                str(linha.get("valor_unitario") or ""),
                f"Item {posicao}: valor unitário",
                obrigatorio=True,
                limite=Decimal("9999999999.99"),
            )

            # Catálogo primeiro: é de onde vem quase todo item. Se a
            # linha aponta para um brinquedo, o produto de fábrica é
            # ignorado -- catálogo, produção e reposição são origens
            # exclusivas (ver ItemOrcamento.clean).
            brinquedo_id = str(linha.get("brinquedo") or "").strip()
            brinquedo = (
                Brinquedos.objects.filter(pk=brinquedo_id).first()
                if brinquedo_id.isdigit() else None
            )

            produto = None
            peca = None
            if brinquedo is None:
                produto_id = str(linha.get("produto") or "").strip()
                produto = (
                    ProdutoInterno.objects.filter(pk=produto_id).first()
                    if produto_id.isdigit() else None
                )

            if brinquedo is None and produto is None:
                peca_id = str(linha.get("peca") or "").strip()
                peca = (
                    PecasReposicao.objects.filter(pk=peca_id).first()
                    if peca_id.isdigit() else None
                )

            novos.append(ItemOrcamento(
                orcamento=orcamento,
                descricao=descricao[:180],
                brinquedo=brinquedo,
                produto=produto,
                peca=peca,
                quantidade=quantidade,
                valor_unitario=valor,
            ))

        orcamento.itens.all().delete()
        ItemOrcamento.objects.bulk_create(novos)

    def acao_status(self, request):
        if not capacidades(request.user)["orcamentos_editar_comercial"]:
            return self.erro(
                request, "Somente o setor Comercial altera a situação da proposta.",
                status=403,
            )
        orcamento = self._orcamento_do_usuario(request, request.POST.get("id"))
        status = (request.POST.get("status") or "").strip()

        permitidos = {
            Orcamento.Status.APROVADO,
            Orcamento.Status.RECUSADO,
            Orcamento.Status.EXPIRADO,
            Orcamento.Status.EM_NEGOCIACAO,
        }
        if status not in permitidos:
            raise ErroDeFormulario("Situação inválida para o orçamento.")

        if orcamento.status == Orcamento.Status.SUBSTITUIDO:
            raise ErroDeFormulario(
                "Esta versão foi substituída e permanece somente no histórico."
            )
        if hasattr(orcamento, "ordem_servico") and status != orcamento.status:
            raise ErroDeFormulario(
                "A proposta já liberou uma O.S. e permanece congelada no "
                "histórico comercial. Atualize somente a Ordem de Serviço."
            )

        if status == Orcamento.Status.EM_NEGOCIACAO:
            orcamento.motivo_negociacao = texto(request, "motivo")

        orcamento.status = status
        orcamento.save(update_fields=["status", "motivo_negociacao", "atualizado"])
        registrar_atividade_orcamento(
            orcamento,
            request,
            AtividadeOrcamento.Tipo.SITUACAO,
            resumo=orcamento.get_status_display(),
        )
        mapa = orcamento.sincronizar_cliente_aprovado()

        complemento = ""
        if mapa and mapa.latitude and mapa.longitude:
            complemento = " O cliente já está no mapa do site."
        elif status == Orcamento.Status.APROVADO and orcamento.cliente_id:
            complemento = " Complete o endereço do cliente para publicá-lo no mapa."

        return self.sucesso(
            request,
            f"Orçamento #{orcamento.pk} marcado como {orcamento.get_status_display()}.{complemento}",
            mapa_publicado=bool(mapa and mapa.latitude and mapa.longitude),
        )

    def acao_refazer(self, request):
        """Clona a proposta para negociar sem apagar a versão enviada."""
        if not capacidades(request.user)["orcamentos_editar_comercial"]:
            return self.erro(
                request, "Somente o Comercial pode refazer uma proposta.", status=403,
            )

        anterior = self._orcamento_do_usuario(request, request.POST.get("id"))
        if anterior.status == Orcamento.Status.RASCUNHO:
            raise ErroDeFormulario("Este orçamento ainda é rascunho e pode ser editado.")
        if hasattr(anterior, "ordem_servico"):
            raise ErroDeFormulario(
                "Esta proposta já originou uma O.S. e não pode ganhar outra "
                "versão. Os dois históricos permanecem congelados e separados."
            )
        if anterior.quitado:
            # Refazer marca a atual como SUBSTITUIDO. Contra esta aqui o
            # dinheiro já entrou: substituí-la apagaria o documento que
            # explica o valor recebido. Quem quer outra coisa depois de
            # pagar está pedindo uma proposta nova, não outra versão.
            raise ErroDeFormulario(
                "Esta proposta já está paga e não ganha outra versão: "
                "o pagamento recebido precisa continuar apontando para "
                "ela. Para o que vier depois, abra uma proposta nova."
            )
        if hasattr(anterior, "orcamento_refeito"):
            nova = anterior.orcamento_refeito
            return self.sucesso(
                request,
                f"A versão {nova.versao} desta proposta já existe.",
                id=nova.pk,
            )

        with transaction.atomic():
            anterior = Orcamento.objects.select_for_update().get(pk=anterior.pk)
            nova = Orcamento.objects.create(
                cliente=anterior.cliente,
                nome_cliente=anterior.nome_cliente,
                contato=anterior.contato,
                whatsapp_cliente=anterior.whatsapp_cliente,
                email_cliente=anterior.email_cliente,
                origem=anterior.origem,
                validade=anterior.validade,
                desconto=anterior.desconto,
                frete=anterior.frete,
                forma_pagamento=anterior.forma_pagamento,
                forma_envio=anterior.forma_envio,
                observacoes=anterior.observacoes,
                responsavel=request.user,
                orcamento_anterior=anterior,
                versao=anterior.versao + 1,
                status=Orcamento.Status.RASCUNHO,
            )
            ItemOrcamento.objects.bulk_create([
                ItemOrcamento(
                    orcamento=nova,
                    descricao=item.descricao,
                    brinquedo=item.brinquedo,
                    produto=item.produto,
                    peca=item.peca,
                    quantidade=item.quantidade,
                    valor_unitario=item.valor_unitario,
                )
                for item in anterior.itens.select_related(
                    "brinquedo", "produto", "peca"
                )
            ])
            anterior.status = Orcamento.Status.SUBSTITUIDO
            anterior.save(update_fields=["status", "atualizado"])
            self._reabrir_bloco(nova, AvaliacaoBlocoOrcamento.Bloco.COMERCIAL)
            self._reabrir_bloco(nova, AvaliacaoBlocoOrcamento.Bloco.FINANCEIRO)
            registrar_atividade_orcamento(
                nova,
                request,
                AtividadeOrcamento.Tipo.REFEITO,
                resumo=f"Versão {nova.versao} da proposta #{anterior.pk}",
            )

        return self.sucesso(
            request,
            f"Nova proposta #{nova.pk} criada sem alterar a anterior. Ajuste e envie quando estiver pronta.",
            id=nova.pk,
        )

    def acao_pagamento(self, request):
        if not capacidades(request.user)["orcamentos_editar_financeiro"]:
            return self.erro(
                request, "Somente Financeiro ou Gestão registra pagamentos.", status=403,
            )
        orcamento = self._orcamento_do_usuario(request, request.POST.get("id"))
        if orcamento.status != Orcamento.Status.APROVADO:
            raise ErroDeFormulario(
                "O pagamento só é registrado depois da aprovação definitiva."
            )
        valor = decimal_br(
            request.POST.get("valor_pago"),
            "Valor pago",
            obrigatorio=True,
            limite=Decimal("9999999999.99"),
        )
        orcamento.registrar_pagamento(
            valor, texto(request, "observacao_pagamento", limite=240),
        )
        registrar_atividade_orcamento(
            orcamento,
            request,
            AtividadeOrcamento.Tipo.PAGAMENTO,
            resumo=orcamento.get_status_pagamento_display(),
        )
        return self.sucesso(
            request,
            f"Pagamento do orçamento #{orcamento.pk} atualizado para "
            f"{orcamento.get_status_pagamento_display().lower()}.",
            status_pagamento=orcamento.status_pagamento,
            valor_pago=f"{orcamento.valor_pago:.2f}".replace(".", ","),
            saldo=f"{orcamento.saldo_pagamento:.2f}".replace(".", ","),
        )

    def acao_gerar_ordem_servico(self, request):
        """Não gera mais -- e diz onde a O.S. nasce agora.

        POR QUE SAIU. A O.S. criada a partir da proposta nascia pela
        metade: tipo "instalação" chutado, equipamento montado colando a
        descrição dos quatro primeiros itens, sem defeito relatado, sem
        técnico e sem agenda. Alguém tinha de abrir e refazer tudo -- e
        quem não abria deixava esse documento seguir para o cliente.

        Orçamento é negociação; O.S. é execução. Elas se encontram no
        cliente, não no botão: a O.S. nasce onde tem contexto, que é o
        chamado de manutenção (equipamento, defeito e endereço já
        preenchidos) ou a abertura direta.

        A ação continua existindo, e responde. Sumir dela devolveria
        "ação desconhecida" para quem tivesse a tela velha aberta numa
        aba -- e "ação desconhecida" não ensina nada.
        """
        return self.erro(
            request,
            (
                "A Ordem de Serviço não é mais gerada a partir do "
                "orçamento: ela nascia sem equipamento, sem defeito e sem "
                "agenda, e alguém tinha de refazer tudo. Abra a O.S. pelo "
                "chamado de manutenção, que já traz esses dados, ou crie "
                "uma nova em Ordens de Serviço."
            ),
            status=400,
        )

    def acao_avaliar_bloco(self, request):
        if not capacidades(request.user)["avaliar_blocos_orcamento"]:
            return self.erro(
                request, "Somente o superadministrador avalia os blocos.",
                status=403,
            )

        orcamento = get_object_or_404(Orcamento, pk=request.POST.get("id"))
        bloco = (request.POST.get("bloco") or "").strip()
        status = (request.POST.get("status") or "").strip()
        observacao = texto(request, "observacao")
        if bloco not in AvaliacaoBlocoOrcamento.Bloco.values:
            raise ErroDeFormulario("Escolha o bloco Comercial ou Financeiro.")
        if status not in (
            AvaliacaoBlocoOrcamento.Status.APROVADO,
            AvaliacaoBlocoOrcamento.Status.AJUSTES,
        ):
            raise ErroDeFormulario("Escolha aprovar ou solicitar ajustes.")
        if status == AvaliacaoBlocoOrcamento.Status.AJUSTES and not observacao:
            raise ErroDeFormulario("Explique o ajuste necessário para o setor responsável.")

        avaliacao, _ = AvaliacaoBlocoOrcamento.objects.update_or_create(
            orcamento=orcamento,
            bloco=bloco,
            defaults={
                "status": status,
                "observacao": observacao,
                "avaliador": request.user,
                "avaliado_em": timezone.now(),
            },
        )
        registrar_atividade_orcamento(
            orcamento,
            request,
            AtividadeOrcamento.Tipo.AVALIACAO,
            resumo=(
                f"{avaliacao.get_bloco_display()}: "
                f"{avaliacao.get_status_display()}"
            ),
        )
        return self.sucesso(
            request,
            f"Bloco {avaliacao.get_bloco_display()} marcado como "
            f"{avaliacao.get_status_display().lower()}.",
        )

    def acao_delete(self, request):
        orcamento = self._orcamento_do_usuario(request, request.POST.get("id"))

        # A regra normal protege o histórico comercial: proposta enviada,
        # respondida ou expirada não some da linha do tempo. Ela continua
        # valendo para todo mundo -- menos para quem responde pela
        # empresa, que precisa poder limpar um registro errado sem mexer
        # no banco por fora. Ver `exclusoes.py`.
        regra = pode_excluir_orcamento(request.user, orcamento)
        if not pode_excluir(request.user, regra):
            return self.erro(
                request,
                (
                    "Somente rascunhos podem ser excluídos. Em Vendas, "
                    "você só pode excluir os rascunhos criados por você."
                ),
                status=403,
            )

        exigir_confirmacao_exclusao(request)
        numero = orcamento.pk
        forcada = forcando(request.user, regra)
        itens = orcamento.itens.count()

        arrastados = remover(
            orcamento,
            autor=request.user,
            tipo="Orçamento",
            identificacao=f"#{numero} — {orcamento.destinatario}",
            resumo=(
                f"Situação: {orcamento.get_status_display()}. "
                f"{itens} item(ns). Total: R$ {orcamento.total}."
            ),
            motivo=texto(request, "motivo_exclusao", limite=240),
            forcada=forcada,
        )

        recado = f"Orçamento #{numero} removido."
        if forcada:
            recado += " Não era um rascunho: a exclusão ficou registrada."
        if arrastados:
            recado += f" Levou junto: {', '.join(arrastados)}."
        return self.sucesso(request, recado)

    # ------------------------------------------------ enviar ao cliente
    def acao_enviar(self, request):
        """Entrega a proposta pelo canal escolhido e registra o envio."""
        if not capacidades(request.user)["orcamentos_editar_comercial"]:
            return self.erro(
                request, "Somente o Comercial envia a proposta ao cliente.",
                status=403,
            )
        orcamento_id = (request.POST.get("id") or "").strip()
        if not orcamento_id.isdigit():
            raise ErroDeFormulario(
                "Não consegui identificar o orçamento. Feche esta janela, "
                "recarregue a página e toque em Enviar novamente."
            )
        orcamento = self._orcamento_do_usuario(request, int(orcamento_id))

        if not orcamento.itens.exists():
            raise ErroDeFormulario(
                "Este orçamento não tem itens. Adicione ao menos um antes de enviar."
            )

        link = f"{endereco_do_site(request)}{orcamento.caminho_publico}"
        canal = (request.POST.get("canal") or "link").strip().lower()

        if canal not in ("preparar", "link", "whatsapp", "email"):
            raise ErroDeFormulario("Escolha WhatsApp, e-mail ou copiar link.")

        # O toque em "Enviar orçamento" precisa entregar um link que já
        # funcione. Antes, `preparar` devolvia uma string vazia para rascunho:
        # a janela abria, mas copiar era impossível. Publicar aqui tira a
        # proposta do rascunho sem inventar um envio por WhatsApp/e-mail; o
        # histórico de canal continua sendo registrado somente quando a
        # pessoa realmente escolhe um deles.
        if canal == "preparar":
            orcamento.marcar_enviado()

        link_visivel = link
        mensagem = self.mensagem_da_proposta(orcamento, link)

        extras = {
            "link": link_visivel,
            "mensagem": mensagem,
            # O modal não tenta adivinhar os dados olhando uma cópia antiga
            # no JavaScript. O cadastro vinculado é a fonte padrão; os
            # campos continuam editáveis antes do envio.
            "destinatario": orcamento.destinatario,
            "whatsapp": orcamento.whatsapp_destinatario,
            "email": orcamento.email_destinatario,
            "preview_url": request.build_absolute_uri(
                reverse(
                    "orcamento_previa_inner",
                    args=[orcamento.pk],
                    urlconf="sistema_interno.urls",
                )
            ),
        }

        # Preparar publica o endereço, mas não registra um canal de envio:
        # abrir a janela não significa que WhatsApp, e-mail ou cópia foram
        # realmente usados.
        if canal == "preparar":
            extras["envios"] = self.historico_de_envio(orcamento)
            extras["email_configurado"] = smtp_configurado()
            extras["email_diagnostico"] = diagnostico_smtp()
            return self.sucesso(
                request,
                f"Proposta #{orcamento.pk} pronta para compartilhar.",
                id=orcamento.pk,
                situacao=orcamento.status,
                **extras,
            )

        if canal == "whatsapp":
            telefone = texto(request, "whatsapp", limite=24) or orcamento.whatsapp_destinatario
            digitos = re.sub(r"\D", "", telefone or "")
            if len(digitos) < 10:
                raise ErroDeFormulario("Informe o WhatsApp do cliente com DDD.")
            if len(digitos) in (10, 11):
                digitos = "55" + digitos

            orcamento.whatsapp_cliente = telefone
            orcamento.save(update_fields=["whatsapp_cliente", "atualizado"])
            extras["whatsapp_url"] = self.conversa_whatsapp(telefone, mensagem)

        elif canal == "email":
            email = texto(request, "email", limite=254) or orcamento.email_destinatario
            try:
                validate_email(email)
            except ValidationError:
                raise ErroDeFormulario("Informe um e-mail válido para enviar a proposta.")

            orcamento.email_cliente = email
            orcamento.save(update_fields=["email_cliente", "atualizado"])
            contexto = {
                "orcamento": orcamento,
                "itens": orcamento.itens.all(),
                "link": link,
                "total_formatado": moeda_br(orcamento.total),
                "empresa_nome": nome_empresa(),
                "empresa_cnpj": cnpj_empresa(),
                "dados_bancarios": dados_bancarios_empresa(),
            }
            html = render(request, "emails/orcamento_enviado.html", contexto).content.decode()
            texto_email = (
                f"Olá, {orcamento.destinatario}.\n\n"
                f"Preparamos a proposta Lazer & Sport nº {orcamento.pk}, "
                f"no total de R$ {moeda_br(orcamento.total)}.\n\n"
                "Abra o endereço abaixo para conferir itens, fotos e condições "
                "e registrar sua aprovação ou pedido de ajustes:\n"
                f"{link}\n\n"
                "Se precisar, basta responder a este e-mail.\n\n"
                f"{nome_empresa()}\nCNPJ {cnpj_empresa()}"
            )
            if not smtp_configurado():
                self.registrar_envio(
                    request, orcamento, canal, email,
                    sucesso=False,
                    detalhe="SMTP não configurado na hospedagem.",
                )
                raise ErroDeFormulario(
                    "O envio por e-mail ainda não está configurado na "
                    "hospedagem (EMAIL_HOST_USER e EMAIL_HOST_PASSWORD). "
                    "Use o WhatsApp ou copie o link enquanto isso."
                )

            # O "de" é sempre a conta autenticada no SMTP -- provedor
            # nenhum deixa assinar com outro endereço. Quem recebe a
            # resposta do cliente é quem está enviando agora.
            mensagem = EmailMultiAlternatives(
                subject=f"Sua proposta Lazer & Sport #{orcamento.pk}",
                body=texto_email,
                from_email=remetente(),
                to=[email],
                reply_to=responder_para(request.user),
            )
            mensagem.attach_alternative(html, "text/html")
            try:
                enviados = mensagem.send(fail_silently=False)
            except Exception as erro:
                # O motivo do provedor vai para o registro: "não chegou"
                # deixa de ser mistério e vira "535 senha recusada".
                self.registrar_envio(
                    request, orcamento, canal, email,
                    sucesso=False,
                    detalhe=f"{type(erro).__name__}: {erro}"[:240],
                )
                tipo = type(erro).__name__.lower()
                if "authentication" in tipo:
                    motivo = "o servidor recusou o usuário ou a senha do e-mail"
                elif "recipient" in tipo or "sender" in tipo:
                    motivo = "o servidor recusou o endereço de remetente ou destinatário"
                elif "timeout" in tipo or "connection" in tipo:
                    motivo = "o servidor de e-mail não respondeu a tempo"
                else:
                    motivo = "o provedor não confirmou o envio"
                raise ErroDeFormulario(
                    f"Não foi possível enviar: {motivo}. A tentativa ficou "
                    "registrada; confira o SMTP ou use o WhatsApp/copiar link."
                )

            if enviados != 1:
                self.registrar_envio(
                    request, orcamento, canal, email,
                    sucesso=False,
                    detalhe="O servidor aceitou a conexão e não confirmou o envio.",
                )
                raise ErroDeFormulario("O servidor de e-mail não confirmou o envio.")

            extras["email"] = email

        orcamento.marcar_enviado()

        self.registrar_envio(
            request,
            orcamento,
            canal,
            extras.get("email") if canal == "email" else (
                orcamento.whatsapp_destinatario if canal == "whatsapp" else ""
            ),
        )
        registrar_atividade_orcamento(
            orcamento,
            request,
            AtividadeOrcamento.Tipo.ENVIADO,
            resumo=("E-mail" if canal == "email" else (
                "WhatsApp" if canal == "whatsapp" else "Link"
            )),
        )

        # Se o operador editou um canal neste mesmo pedido, devolvemos o
        # valor recém-salvo para o modal continuar coerente.
        extras["whatsapp"] = orcamento.whatsapp_destinatario
        extras["email"] = orcamento.email_destinatario
        extras["envios"] = self.historico_de_envio(orcamento)
        extras["email_configurado"] = smtp_configurado()
        extras["email_diagnostico"] = diagnostico_smtp()

        return self.sucesso(
            request,
            (
                f"Orçamento #{orcamento.pk} enviado por e-mail."
                if canal == "email"
                else f"Orçamento #{orcamento.pk} pronto para enviar."
            ),
            id=orcamento.pk,
            # `situacao`, e não `status`: a chave `status` é a que diz se a
            # requisição deu certo, e mandar a situação do orçamento nela
            # fazia o painel ler um envio bem sucedido como falha.
            situacao=orcamento.status,
            **extras,
        )

    # --------------------------------- cadastrar brinquedo sem sair daqui
    def acao_brinquedo_novo(self, request):
        """Cria um brinquedo no catálogo do site, de dentro do orçamento.

        POR QUE AQUI. Cliente pede algo que ainda não está cadastrado e a
        alternativa era digitar a descrição à mão: o item entrava solto, sem
        foto na proposta e sem virar catálogo. Na vez seguinte, tudo de novo.
        Cadastrando na hora, a mesma digitação já vira registro.

        Nasce fora da loja (`exibir_na_loja=False`) de propósito: publicar
        na vitrine é decisão de quem cuida do site, com foto e texto de
        venda prontos. Aqui o que se quer é poder orçar hoje.
        """
        if not capacidades(request.user)["orcamentos_editar_comercial"]:
            return self.erro(request, "Cadastro de item pertence ao Comercial.", status=403)
        nome = texto(request, "nome", obrigatorio=True, rotulo="o nome do brinquedo", limite=150)

        if Brinquedos.objects.filter(nome_brinquedo__iexact=nome).exists():
            raise ErroDeFormulario(
                f"Já existe um brinquedo chamado “{nome}”. Procure na lista."
            )

        valor = decimal_br(
            request.POST.get("valor"), "Valor",
            limite=Decimal("9999999999.99"),
        )

        brinquedo = Brinquedos.objects.create(
            nome_brinquedo=nome,
            descricao=texto(request, "descricao", limite=999) or nome,
            valor_brinquedo=valor,
            # Campos que o modelo exige e que não cabem numa criação
            # rápida. avaliacao é obrigatória no cadastro; zero significa
            # "ainda não avaliado" e não polui a média da vitrine, já que
            # o brinquedo nasce fora dela.
            avaliacao=ZERO,
            voltz=texto(request, "voltz", limite=10),
            # DUAS TRAVAS, PORQUE SÃO DUAS PORTAS. `exibir_na_loja` tira
            # da vitrine; `ativo` tira de todo o resto -- busca do site,
            # API do aplicativo, sitemap. Uma só deixava o brinquedo
            # criado às pressas alcançável por fora da vitrine. É a mesma
            # regra da peça, que já nascia desligada.
            ativo=False,
            exibir_na_loja=False,
        )

        categoria_id = (request.POST.get("categoria") or "").strip()
        if categoria_id.isdigit():
            categoria = CategoriasBrinquedos.objects.filter(pk=categoria_id).first()
            if categoria:
                brinquedo.categorias_brinquedos.add(categoria)

        return self.sucesso(
            request,
            f"“{brinquedo.nome_brinquedo}” entrou no catálogo.",
            brinquedo={
                "id": brinquedo.id,
                "nome": brinquedo.nome_brinquedo,
                "valor": (
                    f"{brinquedo.valor_brinquedo:.2f}".replace(".", ",")
                    if brinquedo.valor_brinquedo is not None else ""
                ),
            },
        )

    # --------------------------- cadastrar peça sem sair do orçamento
    def acao_peca_nova(self, request):
        """Cria a peça e devolve-a para a linha atual. Ver `pecas.cadastrar`.

        A regra mora em `sistema_interno/pecas.py` porque a Ordem de
        Serviço faz exatamente a mesma coisa: se "nasce fora da vitrine"
        valesse só num dos dois caminhos, o outro voltaria a publicar
        peça no site sem ninguém pedir. Aqui fica só quem pode.
        """
        if not capacidades(request.user)["orcamentos_editar_comercial"]:
            return self.erro(request, "Cadastro de item pertence ao Comercial.", status=403)

        peca = svc_pecas.cadastrar(request)
        return self.sucesso(
            request, svc_pecas.recado(peca), peca=svc_pecas.resumo(peca),
        )


    # ----------------------------------------- a mensagem e o link prontos
    @staticmethod
    def mensagem_da_proposta(orcamento, link):
        """O texto que vai no WhatsApp: curto, com o essencial e o link.

        É mensagem de gente, não de robô: quem recebe precisa entender em
        três linhas o que é, quanto custa e onde clica.
        """
        itens = list(orcamento.itens.all())
        linhas = [
            f"Olá, {orcamento.destinatario}! 👋",
            "",
            f"Aqui é da Lazer & Sport. Preparamos sua *proposta nº {orcamento.pk}*.",
            "",
            "*Resumo*",
        ]

        # Até três itens no corpo; o resto a pessoa vê na página. Uma lista
        # comprida no WhatsApp vira parede de texto e ninguém lê.
        for item in itens[:3]:
            # A vírgula entra só no dinheiro. Trocar ponto por vírgula na
            # linha inteira estragava descrições como "Bola 3.5" -- o
            # cliente recebia um item com nome errado.
            linhas.append(
                f"• {item.quantidade}x {item.descricao} — R$ {moeda_br(item.subtotal)}"
            )
        if len(itens) > 3:
            linhas.append(f"• e mais {len(itens) - 3} item(ns) na proposta")

        linhas.append("")
        linhas.append(f"*Total: R$ {moeda_br(orcamento.total)}*")

        if orcamento.forma_pagamento:
            linhas.append(f"Pagamento: {orcamento.forma_pagamento}")
        if orcamento.validade:
            linhas.append(
                f"Válida até {orcamento.validade.strftime('%d/%m/%Y')}"
            )

        linhas.extend([
            "",
            "Abra a proposta completa para conferir fotos, itens e condições. "
            "Por essa mesma página você pode *aprovar ou pedir ajustes*:",
            link,
            "",
            "Se tiver qualquer dúvida, responda esta mensagem. 😊",
            f"{nome_empresa()} · CNPJ {cnpj_empresa()}",
        ])

        return "\n".join(linhas)

    @staticmethod
    def conversa_whatsapp(telefone, mensagem):
        """Endereço que abre a conversa já escrita. Vazio se o número não serve."""
        digitos = re.sub(r"\D", "", telefone or "")
        if len(digitos) < 10:
            return ""
        if len(digitos) in (10, 11):
            digitos = "55" + digitos
        return f"https://wa.me/{digitos}?text={quote(mensagem, safe='')}"

    # ---------------------------------- registro de quem recebeu o quê
    @staticmethod
    def registrar_envio(request, orcamento, canal, destino, sucesso=True, detalhe=""):
        """Guarda a tentativa, tenha dado certo ou não.

        "O cliente disse que não recebeu" é a frase mais comum do
        comercial. Sem registro ninguém responde se saiu, para onde e o
        que o servidor respondeu.
        """
        # O registro é histórico, não é o trabalho. Se ele falhar -- tabela
        # ainda não migrada no servidor, banco em manutenção --, a proposta
        # tem de sair do mesmo jeito. Foi exatamente isso que derrubou o
        # envio uma vez: a tela dizia "Link indisponível" porque o log não
        # conseguia gravar.
        try:
            EnvioOrcamento.objects.create(
                orcamento=orcamento,
                canal=canal if canal in EnvioOrcamento.Canal.values else (
                    EnvioOrcamento.Canal.LINK
                ),
                destino=(destino or "")[:254],
                sucesso=sucesso,
                detalhe=detalhe[:240],
                responsavel=request.user if request.user.is_authenticated else None,
            )
        except Exception:
            logging.getLogger(__name__).exception(
                "Não consegui registrar o envio do orçamento %s", orcamento.pk
            )

    @staticmethod
    def historico_de_envio(orcamento, limite=6):
        """As últimas tentativas, prontas para o modal mostrar."""
        try:
            return [
                {
                    "canal": envio.get_canal_display(),
                    "destino": envio.destino,
                    "sucesso": envio.sucesso,
                    "detalhe": envio.detalhe,
                    "quando": timezone.localtime(envio.criacao).strftime(
                        "%d/%m/%Y %H:%M"
                    ) if envio.criacao else "",
                    "por": (
                        envio.responsavel.get_full_name()
                        or envio.responsavel.username
                    ) if envio.responsavel else "",
                }
                for envio in orcamento.envios.select_related("responsavel")[:limite]
            ]
        except Exception:
            # Mesma regra do registro: histórico indisponível não pode
            # impedir ninguém de mandar a proposta.
            logging.getLogger(__name__).exception(
                "Não consegui ler o histórico de envio do orçamento %s",
                orcamento.pk,
            )
            return []

    # ------------------------------- cadastrar cliente sem sair daqui
    def acao_cliente_novo(self, request):
        """Cria o cliente de dentro do orçamento.

        POR QUE AQUI. A proposta quase sempre nasce de quem ligou pela
        primeira vez. Mandar a pessoa para a aba Clientes e voltar
        significaria perder o orçamento meio montado -- ou, o que
        acontecia de verdade, deixar o campo vazio e digitar o nome à
        mão, criando uma proposta sem dono no histórico.

        A validação é a mesma da aba Clientes (sistema_interno/clientes.py):
        cadastro rápido não pode nascer com regra mais frouxa.
        """
        if not capacidades(request.user)["orcamentos_editar_comercial"]:
            return self.erro(request, "Cadastro de cliente pertence ao Comercial.", status=403)
        cliente = svc_clientes.salvar_cliente(request)
        svc_clientes.salvar_endereco(request, cliente)

        return self.sucesso(
            request,
            f"“{cliente.nome_cliente}” entrou na lista de clientes.",
            cliente=svc_clientes.opcao_de_busca(cliente),
        )


class OrcamentoPreviaInnerView(OrcamentoInternoRequiredMixin, View):
    """Mostra o documento antes do envio, inclusive quando é rascunho.

    A página pública esconde rascunhos por segurança. A prévia, por sua vez,
    vive no subdomínio autenticado e nunca aceita a decisão do cliente; assim
    a equipe confere o documento real sem precisar marcar como enviado.
    """

    def get(self, request, pk):
        from core.views_orcamento import (
            carregar_orcamento_exibicao,
            contexto_orcamento,
        )

        # A prévia também é uma rota direta: a carteira individual do
        # Ambulante precisa valer aqui, não apenas na lista visual.
        get_object_or_404(
            limitar_orcamentos(
                request.user,
                Orcamento.objects.only("pk", "responsavel_id"),
            ),
            pk=pk,
        )
        orcamento = carregar_orcamento_exibicao(pk=pk)
        contexto = contexto_orcamento(
            orcamento, previsualizacao=True, request=request
        )
        return render(request, "orcamento_publico.html", contexto)


class BuscaItensOrcamentoView(OrcamentoInternoRequiredMixin, View):
    """Busca pequena e relevante para o seletor do orçamento.

    Nenhum catálogo inteiro cruza a rede. Com termo vazio aparecem os mais
    usados; digitando, igualdade e começo do nome vêm antes de ocorrências no
    meio da descrição. Cada origem traz no máximo oito linhas.
    """

    LIMITE_POR_ORIGEM = 8

    #: O que esta busca oferece. A O.S. usa a mesma máquina com uma lista
    #: menor -- ver `BuscaItensOrdemServicoView`.
    ORIGENS = ("brinquedos", "pecas", "produtos")

    @staticmethod
    def _prioridade(campo, termo):
        return Case(
            When(**{f"{campo}__iexact": termo, "then": Value(0)}),
            When(**{f"{campo}__istartswith": termo, "then": Value(1)}),
            default=Value(2),
            output_field=IntegerField(),
        )

    @staticmethod
    def _padrao_sem_acento(termo):
        base = "".join(
            caractere for caractere in unicodedata.normalize("NFD", termo.lower())
            if unicodedata.category(caractere) != "Mn"
        )
        grupos = {
            "a": "[aáàâãä]",
            "e": "[eéèêë]",
            "i": "[iíìîï]",
            "o": "[oóòôõö]",
            "u": "[uúùûü]",
            "c": "[cç]",
        }
        return "".join(
            r"\s+" if caractere.isspace()
            else grupos.get(caractere, re.escape(caractere))
            for caractere in base
        )

    def get(self, request):
        termo = (request.GET.get("q") or "").strip()[:80]
        limite = self.LIMITE_POR_ORIGEM

        brinquedos = Brinquedos.objects.all()
        produtos = ProdutoInterno.objects.filter(ativo=True).select_related("brinquedo")
        # AQUI DENTRO, `ativo` NÃO É O FILTRO CERTO.
        #
        # `ativo` responde "está anunciada no site?". Quem monta um
        # documento não está perguntando isso: está perguntando o que
        # pode cobrar. Filtrar por `ativo` escondia justamente os itens
        # de manutenção -- que nascem desligados de propósito -- de quem
        # acabou de cadastrá-los para usar na linha seguinte.
        #
        # O que o painel oferece é tudo o que dá para cobrar: peça da
        # loja e item de manutenção, separados por grupo, para ninguém
        # colocar custo interno numa proposta sem perceber.
        pecas = PecasReposicao.objects.prefetch_related("imagem_peca_reposicao")

        if termo:
            padrao = self._padrao_sem_acento(termo)
            brinquedos = (
                brinquedos.filter(
                    Q(nome_brinquedo__iregex=padrao)
                    | Q(descricao__iregex=padrao)
                    | Q(categorias_brinquedos__nome_categoria__iregex=padrao)
                )
                .annotate(_prioridade=self._prioridade("nome_brinquedo", termo))
                .order_by("_prioridade", "nome_brinquedo")
                .distinct()
            )
            produtos = (
                produtos.filter(
                    Q(nome__iregex=padrao)
                    | Q(codigo__iregex=padrao)
                    | Q(descricao__iregex=padrao)
                )
                .annotate(_prioridade=self._prioridade("nome", termo))
                .order_by("_prioridade", "nome")
            )
            pecas = (
                pecas.filter(
                    Q(nome__iregex=padrao)
                    | Q(descricao_peca__iregex=padrao)
                    | Q(categoria_peca__nome_categoria_peca__iregex=padrao)
                )
                .annotate(_prioridade=self._prioridade("nome", termo))
                .order_by("_prioridade", "nome")
                .distinct()
            )
        else:
            # Sem digitação, os usados recentemente são atalhos; não uma
            # lista infinita fingindo ser busca.
            brinquedos = brinquedos.annotate(
                _uso=Count("itens_orcamento")
            ).order_by("-_uso", "nome_brinquedo")
            produtos = produtos.annotate(
                _uso=Count("itens_orcamento")
            ).order_by("-_uso", "nome")
            pecas = pecas.annotate(
                _uso=Count("itens_orcamento")
            ).order_by("-_uso", "nome")

        monta = {
            "brinquedos": (brinquedos, OrcamentosInnerView.opcao_brinquedo),
            "pecas": (pecas, OrcamentosInnerView.opcao_peca),
            "produtos": (produtos, OrcamentosInnerView.opcao_produto),
        }
        opcoes = [
            opcao(obj)
            for origem in self.ORIGENS
            for obj in monta[origem][0][:limite]
            for opcao in (monta[origem][1],)
        ]

        resposta = JsonResponse({
            "status": "sucesso",
            "opcoes": opcoes,
            "termo": termo,
            "limite": len(opcoes),
        })
        resposta["Cache-Control"] = "private, max-age=60"
        return resposta


class BuscaItensOrdemServicoView(
    OrdemServicoInternoRequiredMixin, BuscaItensOrcamentoView
):
    """A mesma busca, para quem monta a O.S. -- e sem passar pelo orçamento.

    POR QUE NÃO REAPROVEITAR A ROTA DO ORÇAMENTO DIRETO.

    Ela é do Comercial e do Financeiro; a O.S. é da Produção. Quem faz
    manutenção não tem (e não devia ter) acesso à tela de propostas, e
    apontar a linha da O.S. para aquela rota daria 403 justamente para o
    técnico que está montando o serviço.

    A lista também é menor de propósito. Um brinquedo inteiro não é linha
    de ordem de serviço: o que se cobra ali é peça, item de manutenção e
    mão de obra. Sobram as duas origens que se consomem.
    """

    # A O.S. cobra peça da loja e item de manutenção. Os dois vivem em
    # PecasReposicao e se distinguem por `uso`; ProdutoInterno é ficha de
    # produção, não peça consumida no atendimento.
    ORIGENS = ("pecas",)

    def get(self, request):
        """Busca curta e estável, sem depender das outras origens do orçamento.

        A O.S. abre este endpoint ao focar o campo, antes mesmo de a pessoa
        digitar. Por isso a consulta vazia também precisa ser barata e válida.
        """
        termo = (request.GET.get("q") or "").strip()[:80]
        pecas = PecasReposicao.objects.prefetch_related(
            "imagem_peca_reposicao",
        )

        if termo:
            pecas = (
                pecas.filter(
                    Q(nome__icontains=termo)
                    | Q(descricao_peca__icontains=termo)
                    | Q(categoria_peca__nome_categoria_peca__icontains=termo)
                )
                .annotate(_prioridade=self._prioridade("nome", termo))
                .order_by("_prioridade", "nome")
                .distinct()
            )
        else:
            pecas = pecas.order_by("nome")

        limite = self.LIMITE_POR_ORIGEM * 4
        opcoes = [
            OrcamentosInnerView.opcao_peca(peca)
            for peca in pecas[:limite]
        ]
        resposta = JsonResponse({
            "status": "sucesso",
            "opcoes": opcoes,
            "termo": termo,
            "limite": len(opcoes),
        })
        resposta["Cache-Control"] = "private, max-age=60"
        return resposta


class EstadoOrcamentosView(OrcamentoInternoRequiredMixin, View):
    """GET /orcamentos/estados/?ids=1,2,3 -> a situação de cada proposta.

    POR QUE ISSO EXISTE. O cliente responde pela página pública, e quem
    está no painel só via a mudança ao recarregar -- na prática, ao sair e
    entrar de novo, porque a sessão dura o dia inteiro. Um "aprovado" que
    demora meia hora para aparecer na tela é um cliente esperando meia
    hora por um retorno que já podia ter saído.

    Só volta o que a tela desenha: situação, rótulo, cor e a linha de
    "quem respondeu quando". Nada de proposta inteira -- é uma consulta
    que se repete, e leveza aqui é o que a torna repetível.

    O limite de ids não é medo de abuso, é o tamanho da página: 25 linhas.
    Pedir mais que isso significa que alguém montou o pedido à mão.
    """

    #: Duas páginas cheias, com folga para a tela crescer.
    LIMITE = 60

    #: Cor de cada situação. A MESMA lista do template -- se divergirem, a
    #: linha muda de cor ao atualizar e ninguém entende por quê.
    COR = {
        Orcamento.Status.APROVADO: "success",
        Orcamento.Status.RECUSADO: "danger",
        Orcamento.Status.AGUARDANDO_RESPOSTA: "info",
        Orcamento.Status.EM_NEGOCIACAO: "warning",
        Orcamento.Status.SUBSTITUIDO: "neutral",
        Orcamento.Status.EXPIRADO: "warning",
    }

    def get(self, request):
        cru = (request.GET.get("ids") or "").strip()
        ids = []
        for pedaco in cru.split(",")[: self.LIMITE]:
            pedaco = pedaco.strip()
            if pedaco.isdigit():
                ids.append(int(pedaco))

        if not ids:
            return JsonResponse({"orcamentos": {}})

        # limitar_orcamentos: quem só enxerga a própria carteira não
        # descobre a situação da carteira do colega perguntando por id.
        consulta = limitar_orcamentos(
            request.user, Orcamento.objects.filter(pk__in=ids)
        ).only(
            "id", "status", "validade", "respondido_em", "respondido_por",
            "enviado_em", "status_pagamento",
        )

        estados = {}
        for orcamento in consulta:
            estados[str(orcamento.pk)] = {
                "status": orcamento.status,
                "status_pagamento": orcamento.status_pagamento,
                "rotulo": orcamento.get_status_display(),
                "cor": self.COR.get(orcamento.status, "neutral"),
                "vencido": orcamento.vencido,
                "respondido_por": orcamento.respondido_por or "",
                "respondido_em": (
                    timezone.localtime(orcamento.respondido_em).strftime("%d/%m %H:%M")
                    if orcamento.respondido_em else ""
                ),
                "enviado_em": (
                    timezone.localtime(orcamento.enviado_em).strftime("%d/%m")
                    if orcamento.enviado_em else ""
                ),
            }

        resposta = JsonResponse({"orcamentos": estados})
        resposta["Cache-Control"] = "no-store, private"
        return resposta


class BuscaClientesOrcamentoView(OrcamentoInternoRequiredMixin, View):
    """Autocompletar de clientes sem despejar a carteira inteira no HTML."""

    LIMITE = 20

    def get(self, request):
        termo = (request.GET.get("q") or "").strip()[:80]
        clientes = Cliente.objects.select_related("parceiro").prefetch_related(
            "enderecos"
        )

        if termo:
            clientes = svc_clientes.buscar(clientes, termo).annotate(
                _prioridade=Case(
                    When(nome_cliente__iexact=termo, then=Value(0)),
                    When(nome_cliente__istartswith=termo, then=Value(1)),
                    default=Value(2),
                    output_field=IntegerField(),
                )
            ).order_by("_prioridade", "nome_cliente")
        else:
            clientes = clientes.annotate(
                _uso=Count("orcamentos")
            ).order_by("-_uso", "nome_cliente")

        opcoes = [
            svc_clientes.opcao_de_busca(cliente)
            for cliente in clientes[:self.LIMITE]
        ]
        resposta = JsonResponse({"status": "sucesso", "opcoes": opcoes})
        resposta["Cache-Control"] = "private, max-age=60"
        return resposta


# ======================================================================
# PRODUÇÃO — produtos e ficha técnica
# ======================================================================
class ProdutosProducaoView(RespostaJSONMixin, ProducaoInternoRequiredMixin, View):
    """O que a fábrica produz, do que é feito e quanto dá para montar hoje."""

    rota_padrao = "produtos_producao"

    def get(self, request):
        busca = (request.GET.get("q") or "").strip()
        categoria = (request.GET.get("categoria") or "").strip()

        produtos = (
            ProdutoInterno.objects
            .select_related("brinquedo")
            .prefetch_related(
                Prefetch(
                    "ficha",
                    queryset=ItemFichaTecnica.objects
                    .select_related("material")
                    .prefetch_related("material__estoque"),
                )
            )
        )

        if busca:
            produtos = produtos.filter(
                Q(nome__icontains=busca)
                | Q(codigo__icontains=busca)
                | Q(descricao__icontains=busca)
            )

        if categoria in ProdutoInterno.Categoria.values:
            produtos = produtos.filter(categoria=categoria)

        produtos = list(produtos)

        # `possivel_produzir` depende do saldo de vários locais de guarda,
        # então é resolvido em Python sobre o prefetch e não em SQL.
        prontos = [
            p for p in produtos
            if p.possivel_produzir is not None and p.possivel_produzir > 0
        ]
        travados = [
            p for p in produtos
            if p.possivel_produzir is not None and p.possivel_produzir == 0
        ]
        sem_ficha = [p for p in produtos if p.possivel_produzir is None]

        ctx = {
            "produtos": produtos,
            "busca": busca,
            "categoria_ativa": categoria,
            "categorias": ProdutoInterno.Categoria.choices,
            # prefetch do estoque: o template lê `quantidade_total` de cada
            # material para montar o mapa de saldos usado no modal da ficha.
            "materiais": Material.objects.filter(ativo=True).prefetch_related("estoque"),
            "total_produtos": len(produtos),
            "total_prontos": len(prontos),
            "total_travados": len(travados),
            "total_sem_ficha": len(sem_ficha),
            "produtos_dados": [self.serializar(p) for p in produtos],
        }
        return render(request, "produtos_producao.html", ctx)

    @staticmethod
    def serializar(produto):
        return {
            "id": produto.id,
            "nome": produto.nome,
            "codigo": produto.codigo,
            "categoria": produto.categoria,
            "descricao": produto.descricao,
            "horas_producao": f"{produto.horas_producao:.2f}".replace(".", ","),
            "preco_venda": f"{produto.preco_venda:.2f}".replace(".", ","),
            "ativo": produto.ativo,
            "ficha": [
                {
                    "id": item.id,
                    "material": item.material_id,
                    "material_nome": item.material.nome_material,
                    "quantidade": f"{item.quantidade:.3f}".replace(".", ","),
                    "observacao": item.observacao,
                }
                for item in produto.ficha.all()
            ],
        }

    # ------------------------------------------------------------- ações
    def acao_save(self, request):
        produto_id = request.POST.get("id")
        produto = (
            get_object_or_404(ProdutoInterno, pk=produto_id)
            if produto_id else ProdutoInterno()
        )

        produto.nome = texto(request, "nome", obrigatorio=True, rotulo="o nome", limite=120)
        produto.codigo = texto(request, "codigo", limite=30)
        produto.descricao = texto(request, "descricao")

        categoria = (request.POST.get("categoria") or "").strip()
        if categoria not in ProdutoInterno.Categoria.values:
            raise ErroDeFormulario("Escolha a categoria do produto.")
        produto.categoria = categoria

        produto.horas_producao = decimal_br(
            request.POST.get("horas_producao"), "Horas de montagem",
            limite=Decimal("9999.99"),
        ) or ZERO
        produto.preco_venda = decimal_br(
            request.POST.get("preco_venda"), "Preço de venda",
            limite=Decimal("9999999999.99"),
        ) or ZERO
        produto.ativo = request.POST.get("ativo") in ("1", "true", "on")

        produto.save()
        return self.sucesso(request, f"{produto.nome} salvo.", id=produto.pk)

    def acao_ficha(self, request):
        """Regrava a ficha técnica inteira do produto."""
        produto = get_object_or_404(ProdutoInterno, pk=request.POST.get("id"))

        try:
            linhas = json.loads(request.POST.get("ficha") or "[]")
        except (TypeError, ValueError):
            raise ErroDeFormulario("Não consegui ler a ficha técnica.")

        if not isinstance(linhas, list):
            raise ErroDeFormulario("Formato inválido na ficha técnica.")

        if len(linhas) > 120:
            raise ErroDeFormulario("Uma ficha técnica aceita no máximo 120 materiais.")

        vistos = set()
        novos = []

        for posicao, linha in enumerate(linhas, start=1):
            if not isinstance(linha, dict):
                raise ErroDeFormulario(f"Material {posicao}: formato inválido.")

            material_id = str(linha.get("material") or "").strip()
            if not material_id.isdigit():
                raise ErroDeFormulario(f"Material {posicao}: escolha o material.")

            if material_id in vistos:
                raise ErroDeFormulario(
                    "O mesmo material aparece duas vezes na ficha. "
                    "Some as quantidades em uma linha só."
                )
            vistos.add(material_id)

            quantidade = decimal_br(
                str(linha.get("quantidade") or ""),
                f"Material {posicao}: quantidade",
                obrigatorio=True,
                limite=Decimal("999999.999"),
            )
            if quantidade <= 0:
                raise ErroDeFormulario(
                    f"Material {posicao}: a quantidade precisa ser maior que zero."
                )

            novos.append(ItemFichaTecnica(
                produto=produto,
                material=get_object_or_404(Material, pk=material_id),
                quantidade=quantidade,
                observacao=(linha.get("observacao") or "").strip()[:150],
            ))

        produto.ficha.all().delete()
        ItemFichaTecnica.objects.bulk_create(novos)

        return self.sucesso(
            request,
            f"Ficha técnica de {produto.nome} salva com {len(novos)} material(is).",
            id=produto.pk,
        )

    def acao_delete(self, request):
        produto = get_object_or_404(ProdutoInterno, pk=request.POST.get("id"))

        if produto.ordens.exists():
            raise ErroDeFormulario(
                "Este produto tem ordens de produção registradas. "
                "Desative-o em vez de apagar, para não perder o histórico."
            )

        nome = produto.nome
        produto.delete()
        return self.sucesso(request, f"{nome} removido.")


# ======================================================================
# PRODUÇÃO — guias visuais por produto
# ======================================================================
class GuiasProducaoView(RespostaJSONMixin, ProducaoInternoRequiredMixin, View):
    rota_padrao = "guias_producao"
    MAX_IMAGENS_ETAPA = 12
    MAX_TAMANHO_IMAGEM = 10 * 1024 * 1024

    def get(self, request):
        produtos = list(
            ProdutoInterno.objects
            .filter(ativo=True)
            .annotate(total_guias=Count("guias_producao"))
            .order_by("nome")
        )
        produto_id = (request.GET.get("produto") or "").strip()
        produto = (
            next((p for p in produtos if str(p.pk) == produto_id), None)
            or (produtos[0] if produtos else None)
        )

        etapas = []
        if produto:
            etapas = list(
                produto.guias_producao
                .prefetch_related("imagens")
                .order_by("ordem", "id")
            )

        return render(request, "guias_producao.html", {
            "produtos": produtos,
            "produto": produto,
            "etapas": etapas,
            "etapas_dados": [self.serializar(etapa) for etapa in etapas],
            "categorias_produto": ProdutoInterno.Categoria.choices,
            # Brinquedo do site que ainda não virou produto de produção:
            # é dele que quase todo manual novo nasce.
            "opcoes_brinquedos": self.opcoes_brinquedos(),
            "opcoes_copiar": [
                {
                    "valor": str(p.pk),
                    "rotulo": p.nome,
                    "detalhe": (
                        f"{p.total_guias} etapa"
                        f"{'s' if p.total_guias != 1 else ''}"
                    ),
                }
                for p in produtos
                if p.total_guias and (not produto or p.pk != produto.pk)
            ],
            "roteiro_previsto": (
                len(etapas_padrao.roteiro_de(produto)) if produto else 0
            ),
        })

    @staticmethod
    def opcoes_brinquedos():
        """Catálogo do site para a busca do cadastro rápido de produto."""
        return [
            {
                "valor": str(b.id),
                "rotulo": b.nome_brinquedo,
                "detalhe": "Brinquedo do catálogo do site",
            }
            for b in Brinquedos.objects
            .only("id", "nome_brinquedo")
            .order_by("nome_brinquedo")
        ]

    @staticmethod
    def serializar(etapa):
        return {
            "id": etapa.pk,
            "ordem": etapa.ordem,
            "titulo": etapa.titulo,
            "instrucoes": etapa.instrucoes,
            "criterio_conclusao": etapa.criterio_conclusao,
            "tempo_estimado_min": etapa.tempo_estimado_min or "",
            "ativo": etapa.ativo,
        }

    def acao_save(self, request):
        produto = get_object_or_404(
            ProdutoInterno,
            pk=request.POST.get("produto"),
        )
        etapa_id = (request.POST.get("id") or "").strip()
        etapa = (
            get_object_or_404(GuiaEtapaProducao, pk=etapa_id, produto=produto)
            if etapa_id else GuiaEtapaProducao(produto=produto)
        )

        etapa.ordem = inteiro(
            request.POST.get("ordem"), "Ordem da etapa",
            obrigatorio=True, minimo=1, maximo=999,
        )
        etapa.titulo = texto(
            request, "titulo", obrigatorio=True,
            rotulo="o título da etapa", limite=120,
        )
        etapa.instrucoes = texto(
            request, "instrucoes", obrigatorio=True,
            rotulo="as instruções do guia",
        )
        etapa.criterio_conclusao = texto(request, "criterio_conclusao")
        etapa.tempo_estimado_min = inteiro(
            request.POST.get("tempo_estimado_min"),
            "Tempo estimado", minimo=1, maximo=100000,
        )
        etapa.ativo = request.POST.get("ativo") in {"1", "on", "true"}
        etapa.save()

        arquivos = request.FILES.getlist("imagens")
        if etapa.imagens.count() + len(arquivos) > self.MAX_IMAGENS_ETAPA:
            raise ErroDeFormulario(
                f"Cada etapa aceita no máximo {self.MAX_IMAGENS_ETAPA} imagens."
            )

        legenda = texto(request, "legenda", limite=160)
        proxima_ordem = etapa.imagens.count() + 1
        for posicao, arquivo in enumerate(arquivos, start=proxima_ordem):
            if arquivo.size > self.MAX_TAMANHO_IMAGEM:
                raise ErroDeFormulario(
                    f"A imagem {arquivo.name} ultrapassa o limite de 10 MB."
                )
            if not (getattr(arquivo, "content_type", "") or "").startswith("image/"):
                raise ErroDeFormulario(f"{arquivo.name} não é uma imagem válida.")
            ImagemGuiaProducao.objects.create(
                etapa=etapa,
                imagem=arquivo,
                legenda=legenda,
                ordem=posicao,
            )

        return self.sucesso(
            request,
            f"Etapa {etapa.ordem} · {etapa.titulo} salva.",
            id=etapa.pk,
        )

    # ------------------------------- criar o produto sem sair da tela
    def acao_produto_novo(self, request):
        """Cria o produto de produção na hora, de dentro do manual.

        POR QUE AQUI. O manual é escrito quando o brinquedo aparece --
        muitas vezes um item do site que nunca teve ficha de produção.
        Mandar a pessoa para a tela de produtos e voltar é o passo em que
        a montagem do guia era abandonada.
        """
        nome = texto(
            request, "nome", obrigatorio=True,
            rotulo="o nome do produto", limite=120,
        )

        if ProdutoInterno.objects.filter(nome__iexact=nome).exists():
            raise ErroDeFormulario(
                f"Já existe um produto chamado “{nome}”. Procure na lista."
            )

        categoria = (request.POST.get("categoria") or "").strip()
        if categoria not in ProdutoInterno.Categoria.values:
            categoria = ProdutoInterno.Categoria.BRINQUEDO

        brinquedo_id = (request.POST.get("brinquedo") or "").strip()
        brinquedo = (
            Brinquedos.objects.filter(pk=brinquedo_id).first()
            if brinquedo_id.isdigit() else None
        )

        produto = ProdutoInterno.objects.create(
            nome=nome,
            categoria=categoria,
            brinquedo=brinquedo,
            codigo=texto(request, "codigo", limite=30),
            preco_venda=decimal_br(
                request.POST.get("preco_venda"),
                "Preço de venda",
                limite=Decimal("9999999999.99"),
            ) or ZERO,
        )

        criadas = 0
        if request.POST.get("gerar_etapas") in {"1", "on", "true"}:
            criadas = etapas_padrao.gerar(produto)

        recado = f"“{produto.nome}” criado."
        if criadas:
            recado += f" {criadas} etapas do roteiro padrão já entraram."

        return self.sucesso(request, recado, produto=produto.pk, id=produto.pk)

    # ------------------------------------- gerar e copiar o roteiro
    def acao_gerar_padrao(self, request):
        """Escreve o roteiro base da fábrica para este produto."""
        produto = get_object_or_404(
            ProdutoInterno,
            pk=request.POST.get("produto") or request.POST.get("id"),
        )

        criadas = etapas_padrao.gerar(produto)

        if not criadas:
            raise ErroDeFormulario(
                "O roteiro padrão já está inteiro neste produto. Edite as "
                "etapas ou crie uma nova pelo botão “Nova etapa”."
            )

        return self.sucesso(
            request,
            f"{criadas} etapa{'s' if criadas > 1 else ''} do roteiro padrão "
            f"{'entraram' if criadas > 1 else 'entrou'} em {produto.nome}. "
            "Ajuste o texto para o que este produto tem de específico.",
            produto=produto.pk,
        )

    def acao_copiar_etapas(self, request):
        """Traz o manual de um produto parecido, sem as fotos."""
        destino = get_object_or_404(
            ProdutoInterno,
            pk=request.POST.get("produto"),
        )
        origem = get_object_or_404(
            ProdutoInterno,
            pk=request.POST.get("origem"),
        )

        copiadas = etapas_padrao.copiar(origem, destino)

        if not copiadas:
            raise ErroDeFormulario(
                f"Nada veio de {origem.nome}: as etapas dele já existem "
                "aqui, ou o produto escolhido é este mesmo."
            )

        return self.sucesso(
            request,
            f"{copiadas} etapa{'s' if copiadas > 1 else ''} copiada"
            f"{'s' if copiadas > 1 else ''} de {origem.nome}. As fotos não "
            "vêm junto: imagem de outro produto engana quem monta.",
            produto=destino.pk,
        )

    def acao_delete_imagem(self, request):
        imagem = get_object_or_404(
            ImagemGuiaProducao,
            pk=request.POST.get("id"),
        )
        produto_id = imagem.etapa.produto_id
        imagem.delete()
        return self.sucesso(request, "Imagem removida.", produto=produto_id)

    def acao_delete(self, request):
        etapa = get_object_or_404(
            GuiaEtapaProducao,
            pk=request.POST.get("id"),
        )
        if etapa.execucoes.exists():
            etapa.ativo = False
            etapa.save(update_fields=["ativo", "atualizado"])
            return self.sucesso(
                request,
                "A etapa já possui histórico e foi desativada, sem apagar o guia.",
            )
        etapa.delete()
        return self.sucesso(request, "Etapa removida.")


# ======================================================================
# PRODUÇÃO — ordens
# ======================================================================
class OrdensProducaoView(RespostaJSONMixin, ProducaoInternoRequiredMixin, View):
    """Registro do que foi montado, com baixa automática no estoque."""

    rota_padrao = "ordens_producao"

    def get(self, request):
        status = (request.GET.get("status") or "").strip()

        ordens = (
            OrdemProducao.objects
            .select_related(
                "produto", "setor", "responsavel", "colaborador",
            )
            .prefetch_related(
                "produto__ficha__material__estoque",
                "etapas_execucao__guia_etapa",
            )
        )

        if status in OrdemProducao.Status.values:
            ordens = ordens.filter(status=status)

        ordens = list(ordens[:200])

        resumo = (
            OrdemProducao.objects
            .values("status")
            .annotate(itens=Count("id"))
        )
        contagem = {linha["status"]: linha["itens"] for linha in resumo}

        produzido = sum(
            o.quantidade for o in ordens
            if o.status == OrdemProducao.Status.CONCLUIDA
        )

        ctx = {
            "ordens": ordens,
            "status_ativo": status,
            "status_opcoes": OrdemProducao.Status.choices,
            "produtos": (
                ProdutoInterno.objects
                .filter(ativo=True)
                .prefetch_related("ficha__material__estoque")
            ),
            "setores": Setores.objects.all(),
            "colaboradores": (
                Colaborador.objects.filter(ativo=True).order_by("nome")
            ),
            "hoje": timezone.localdate(),
            "total_planejadas": contagem.get(OrdemProducao.Status.PLANEJADA, 0),
            "total_producao": contagem.get(OrdemProducao.Status.EM_PRODUCAO, 0),
            "total_concluidas": contagem.get(OrdemProducao.Status.CONCLUIDA, 0),
            "total_unidades": produzido,
        }
        return render(request, "ordens_producao.html", ctx)

    # ------------------------------------------------------------- ações
    def acao_save(self, request):
        ordem_id = request.POST.get("id")
        ordem = (
            get_object_or_404(OrdemProducao, pk=ordem_id)
            if ordem_id else OrdemProducao()
        )

        if ordem.pk and ordem.baixa_aplicada:
            raise ErroDeFormulario(
                "Ordem já concluída não pode ser editada: o estoque dela já foi baixado."
            )

        produto_id = texto(request, "produto", obrigatorio=True, rotulo="o produto")
        produto = get_object_or_404(ProdutoInterno, pk=produto_id)
        produto_anterior_id = ordem.produto_id

        if not produto.guias_producao.filter(ativo=True).exists():
            raise ErroDeFormulario(
                "Cadastre o guia e suas etapas antes de criar uma ordem "
                f"para {produto.nome}."
            )

        if (
            ordem.pk
            and produto_anterior_id != produto.pk
            and ordem.etapas_execucao.exclude(
                status=ExecucaoEtapaProducao.Status.AGUARDANDO
            ).exists()
        ):
            raise ErroDeFormulario(
                "O produto não pode ser trocado depois que uma etapa foi iniciada."
            )
        ordem.produto = produto

        ordem.quantidade = inteiro(
            request.POST.get("quantidade"), "Quantidade",
            obrigatorio=True, minimo=1, maximo=100000,
        )

        if not ordem.pk:
            ordem.status = OrdemProducao.Status.PLANEJADA

        setor_id = (request.POST.get("setor") or "").strip()
        ordem.setor = (
            get_object_or_404(Setores, pk=setor_id)
            if setor_id.isdigit() else None
        )

        colaborador_id = (request.POST.get("colaborador") or "").strip()
        if not colaborador_id.isdigit():
            raise ErroDeFormulario("Escolha o colaborador responsável pela produção.")
        colaborador = get_object_or_404(
            Colaborador,
            pk=colaborador_id,
            ativo=True,
        )
        ordem.colaborador = colaborador

        ordem.prevista_para = data(request.POST.get("prevista_para"), "Data prevista")
        ordem.observacoes = texto(request, "observacoes")

        nova = not ordem.pk
        if nova:
            ordem.responsavel = request.user

        ordem.save()

        if produto_anterior_id and produto_anterior_id != produto.pk:
            ordem.etapas_execucao.all().delete()
        ordem.preparar_etapas()

        HistoricoProducao.objects.create(
            ordem_producao=ordem,
            usuario=request.user,
            evento=(
                HistoricoProducao.Evento.ORDEM_CRIADA
                if nova else HistoricoProducao.Evento.ORDEM_EDITADA
            ),
            status_novo=ordem.status,
            observacao=f"Colaborador da montagem: {colaborador.nome}",
        )
        return self.sucesso(request, f"Ordem #{ordem.pk} salva.", id=ordem.pk)

    def acao_colaborador_save(self, request):
        """Cria o nome operacional sem inventar uma conta de acesso."""
        nome = texto(
            request,
            "nome_colaborador",
            obrigatorio=True,
            rotulo="o nome do colaborador",
            limite=90,
        )
        existente = Colaborador.objects.filter(nome__iexact=nome).first()
        if existente:
            if not existente.ativo:
                existente.ativo = True
                existente.save(update_fields=["ativo", "atualizado"])
            colaborador = existente
        else:
            colaborador = Colaborador.objects.create(nome=nome)
        return self.sucesso(
            request,
            f"Colaborador “{colaborador.nome}” disponível na ordem.",
            colaborador={"id": colaborador.pk, "nome": colaborador.nome},
        )

    @transaction.atomic
    def acao_concluir(self, request):
        ordem = get_object_or_404(OrdemProducao, pk=request.POST.get("id"))
        if ordem.etapas_execucao.exists():
            raise ErroDeFormulario(
                "Conclua a ordem pelo acompanhamento das etapas. "
                "Assim nenhuma fase do guia será pulada."
            )
        ordem.concluir(usuario=request.user)

        return self.sucesso(
            request,
            (
                f"Ordem #{ordem.pk} concluída: {ordem.quantidade} x "
                f"{ordem.produto.nome}. Estoque baixado pela ficha técnica."
            ),
        )

    def acao_cancelar(self, request):
        ordem = get_object_or_404(OrdemProducao, pk=request.POST.get("id"))

        if ordem.baixa_aplicada:
            raise ErroDeFormulario(
                "Ordem concluída não pode ser cancelada: registre uma entrada "
                "de estoque se os materiais voltaram."
            )

        ordem.status = OrdemProducao.Status.CANCELADA
        ordem.save(update_fields=["status", "atualizado"])
        HistoricoProducao.objects.create(
            ordem_producao=ordem,
            usuario=request.user,
            evento=HistoricoProducao.Evento.ORDEM_CANCELADA,
            status_novo=OrdemProducao.Status.CANCELADA,
        )
        return self.sucesso(request, f"Ordem #{ordem.pk} cancelada.")

    def acao_delete(self, request):
        ordem = get_object_or_404(OrdemProducao, pk=request.POST.get("id"))

        if ordem.baixa_aplicada:
            raise ErroDeFormulario(
                "Ordem concluída faz parte do histórico do estoque e não pode "
                "ser apagada."
            )

        numero = ordem.pk
        ordem.delete()
        return self.sucesso(request, f"Ordem #{numero} removida.")


# ======================================================================
# PRODUÇÃO — acompanhamento do colaborador
# ======================================================================
def _ordens_permitidas(user):
    # Colaborador não é login. Quem possui a função Produção acompanha o
    # chão de fábrica inteiro; o usuário da ação fica no histórico.
    return OrdemProducao.objects.all()


class MinhaProducaoView(ProducaoInternoRequiredMixin, View):
    def get(self, request):
        status = (request.GET.get("status") or "").strip()
        ordens = (
            _ordens_permitidas(request.user)
            .select_related("produto", "colaborador", "setor")
            .prefetch_related("etapas_execucao__guia_etapa")
        )
        if status in OrdemProducao.Status.values:
            ordens = ordens.filter(status=status)

        ordens = list(ordens[:200])
        for ordem in ordens:
            etapas = list(ordem.etapas_execucao.all())
            ordem.total_etapas_tela = len(etapas)
            ordem.etapas_concluidas_tela = sum(
                etapa.status == ExecucaoEtapaProducao.Status.CONCLUIDA
                for etapa in etapas
            )
            ordem.etapa_atual_tela = next(
                (
                    etapa for etapa in etapas
                    if etapa.status != ExecucaoEtapaProducao.Status.CONCLUIDA
                ),
                None,
            )

        return render(request, "minha_producao.html", {
            "ordens": ordens,
            "status_ativo": status,
            "status_opcoes": OrdemProducao.Status.choices,
            "eh_gestor": True,
            "total_ativas": sum(
                ordem.status not in (
                    OrdemProducao.Status.CONCLUIDA,
                    OrdemProducao.Status.CANCELADA,
                )
                for ordem in ordens
            ),
            "total_bloqueadas": sum(
                ordem.status == OrdemProducao.Status.BLOQUEADA
                for ordem in ordens
            ),
        })


class OrdemProducaoDetalheView(ProducaoInternoRequiredMixin, View):
    def get(self, request, pk):
        ordem = get_object_or_404(
            _ordens_permitidas(request.user)
            .select_related("produto", "colaborador", "setor")
            .prefetch_related(
                "etapas_execucao__guia_etapa__imagens",
                "historico__usuario",
                "historico__etapa__guia_etapa",
            ),
            pk=pk,
        )
        etapas = list(ordem.etapas_execucao.all())
        atual = next(
            (
                etapa for etapa in etapas
                if etapa.status != ExecucaoEtapaProducao.Status.CONCLUIDA
            ),
            None,
        )
        for etapa in etapas:
            etapa.eh_atual = bool(atual and atual.pk == etapa.pk)

        return render(request, "producao_ordem_detalhe.html", {
            "ordem": ordem,
            "etapas": etapas,
            "etapa_atual": atual,
            "historico": ordem.historico.all()[:40],
            "eh_gestor": True,
        })


class AtualizarEtapaProducaoView(ProducaoInternoRequiredMixin, View):
    def post(self, request, pk, etapa_id):
        ordem = get_object_or_404(_ordens_permitidas(request.user), pk=pk)
        execucao = get_object_or_404(
            ExecucaoEtapaProducao,
            pk=etapa_id,
            ordem_producao=ordem,
        )
        acao = (request.POST.get("acao") or "").strip()
        observacao = (request.POST.get("observacao") or "").strip()

        try:
            atualizada = ExecucaoEtapaProducao.registrar_acao(
                execucao.pk,
                acao,
                request.user,
                observacao,
            )
            messages.success(
                request,
                f"{atualizada.guia_etapa.titulo}: "
                f"{atualizada.get_status_display()}.",
            )
        except (ValueError, ExecucaoEtapaProducao.DoesNotExist) as exc:
            messages.error(request, str(exc))

        return redirect("producao_ordem_detalhe", pk=ordem.pk)
