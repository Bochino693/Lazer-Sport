"""Financeiro, orçamentos e produção do painel interno.

Ficam separados de `views.py` — que cuida de estoque, materiais e das telas
operacionais — só por tamanho: os mixins de acesso e de resposta JSON são
reaproveitados de lá, então a regra de quem entra no subdomínio continua
escrita em um lugar só.
"""

import json
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.generic import View

from . import financeiro as fin
from .models import (
    Cliente,
    ItemFichaTecnica,
    ItemOrcamento,
    Material,
    Montadores,
    Orcamento,
    OrdemProducao,
    ProdutoInterno,
    Setores,
)
from .utils import ErroDeFormulario, data, decimal_br, inteiro, texto
from .views import InternoRequiredMixin, RespostaJSONMixin

ZERO = Decimal("0.00")


# ======================================================================
# FINANCEIRO
# ======================================================================
class FinanceiroInnerView(InternoRequiredMixin, View):
    """Receita, saída, lucro e composição das despesas.

    Os gráficos são SVG/CSS montados a partir de números já calculados no
    servidor: a tela abre desenhada, sem esperar script de biblioteca.
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
            "inicio": meses[0],
            "fim": meses[-1],
        }
        ctx.update(fin.indicadores(serie))

        return render(request, "financeiro_inner.html", ctx)


# ======================================================================
# ORÇAMENTOS
# ======================================================================
class OrcamentosInnerView(RespostaJSONMixin, InternoRequiredMixin, View):
    """Lista e monta orçamentos, com os itens em uma requisição só."""

    rota_padrao = "orcamentos_inner"

    # ------------------------------------------------------------ leitura
    def get(self, request):
        busca = (request.GET.get("q") or "").strip()
        status = (request.GET.get("status") or "").strip()

        orcamentos = (
            Orcamento.objects
            .select_related("cliente", "responsavel")
            .prefetch_related("itens")
        )

        if busca:
            orcamentos = orcamentos.filter(
                Q(nome_cliente__icontains=busca)
                | Q(cliente__nome_cliente__icontains=busca)
                | Q(contato__icontains=busca)
                | Q(observacoes__icontains=busca)
                | Q(itens__descricao__icontains=busca)
            ).distinct()

        if status in Orcamento.Status.values:
            orcamentos = orcamentos.filter(status=status)

        orcamentos = list(orcamentos)

        aprovados = [o for o in orcamentos if o.status == Orcamento.Status.APROVADO]
        em_aberto = [
            o for o in orcamentos
            if o.status in (Orcamento.Status.RASCUNHO, Orcamento.Status.ENVIADO)
        ]

        ctx = {
            "orcamentos": orcamentos,
            "busca": busca,
            "status_ativo": status,
            "status_opcoes": Orcamento.Status.choices,
            "clientes": Cliente.objects.order_by("nome_cliente"),
            "produtos": ProdutoInterno.objects.filter(ativo=True),
            "hoje": timezone.localdate(),
            "total_orcamentos": len(orcamentos),
            "total_aprovado": sum((o.total for o in aprovados), ZERO),
            "total_em_aberto": sum((o.total for o in em_aberto), ZERO),
            "quantidade_aberto": len(em_aberto),
            "quantidade_aprovado": len(aprovados),
            "orcamentos_dados": [self.serializar(o) for o in orcamentos],
        }
        return render(request, "orcamentos_inner.html", ctx)

    @staticmethod
    def serializar(orcamento):
        """Payload que o modal usa para reabrir um orçamento já salvo."""
        return {
            "id": orcamento.id,
            "cliente": orcamento.cliente_id or "",
            "nome_cliente": orcamento.nome_cliente,
            "contato": orcamento.contato,
            "status": orcamento.status,
            "validade": orcamento.validade.isoformat() if orcamento.validade else "",
            "desconto": f"{orcamento.desconto:.2f}".replace(".", ","),
            "frete": f"{orcamento.frete:.2f}".replace(".", ","),
            "observacoes": orcamento.observacoes,
            "itens": [
                {
                    "descricao": item.descricao,
                    "produto": item.produto_id or "",
                    "quantidade": item.quantidade,
                    "valor_unitario": f"{item.valor_unitario:.2f}".replace(".", ","),
                }
                for item in orcamento.itens.all()
            ],
        }

    # ------------------------------------------------------------- ações
    def acao_save(self, request):
        orcamento_id = request.POST.get("id")
        orcamento = (
            get_object_or_404(Orcamento, pk=orcamento_id)
            if orcamento_id else Orcamento()
        )

        cliente_id = (request.POST.get("cliente") or "").strip()
        orcamento.cliente = (
            get_object_or_404(Cliente, pk=cliente_id)
            if cliente_id.isdigit() else None
        )

        orcamento.nome_cliente = texto(request, "nome_cliente", limite=120)
        orcamento.contato = texto(request, "contato", limite=120)

        if not orcamento.cliente and not orcamento.nome_cliente:
            raise ErroDeFormulario(
                "Escolha um cliente cadastrado ou escreva o nome do destinatário."
            )

        status = (request.POST.get("status") or Orcamento.Status.RASCUNHO).strip()
        if status not in Orcamento.Status.values:
            raise ErroDeFormulario("Situação inválida para o orçamento.")
        orcamento.status = status

        orcamento.validade = data(request.POST.get("validade"), "Validade")
        orcamento.desconto = decimal_br(
            request.POST.get("desconto"), "Desconto",
            limite=Decimal("9999999999.99"),
        ) or ZERO
        orcamento.frete = decimal_br(
            request.POST.get("frete"), "Frete",
            limite=Decimal("9999999999.99"),
        ) or ZERO
        orcamento.observacoes = texto(request, "observacoes")

        if not orcamento.pk:
            orcamento.responsavel = request.user

        orcamento.save()

        self._gravar_itens(orcamento, request.POST.get("itens"))

        return self.sucesso(
            request,
            f"Orçamento #{orcamento.pk} salvo — total {orcamento.total}.",
            id=orcamento.pk,
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

            produto_id = str(linha.get("produto") or "").strip()
            produto = (
                ProdutoInterno.objects.filter(pk=produto_id).first()
                if produto_id.isdigit() else None
            )

            novos.append(ItemOrcamento(
                orcamento=orcamento,
                descricao=descricao[:180],
                produto=produto,
                quantidade=quantidade,
                valor_unitario=valor,
            ))

        orcamento.itens.all().delete()
        ItemOrcamento.objects.bulk_create(novos)

    def acao_status(self, request):
        orcamento = get_object_or_404(Orcamento, pk=request.POST.get("id"))
        status = (request.POST.get("status") or "").strip()

        if status not in Orcamento.Status.values:
            raise ErroDeFormulario("Situação inválida para o orçamento.")

        orcamento.status = status
        orcamento.save(update_fields=["status", "atualizado"])

        return self.sucesso(
            request,
            f"Orçamento #{orcamento.pk} marcado como {orcamento.get_status_display()}.",
        )

    def acao_delete(self, request):
        orcamento = get_object_or_404(Orcamento, pk=request.POST.get("id"))
        numero = orcamento.pk
        orcamento.delete()
        return self.sucesso(request, f"Orçamento #{numero} removido.")


# ======================================================================
# PRODUÇÃO — produtos e ficha técnica
# ======================================================================
class ProdutosProducaoView(RespostaJSONMixin, InternoRequiredMixin, View):
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
# PRODUÇÃO — ordens
# ======================================================================
class OrdensProducaoView(RespostaJSONMixin, InternoRequiredMixin, View):
    """Registro do que foi montado, com baixa automática no estoque."""

    rota_padrao = "ordens_producao"

    def get(self, request):
        status = (request.GET.get("status") or "").strip()

        ordens = (
            OrdemProducao.objects
            .select_related("produto", "montador", "setor", "responsavel")
            .prefetch_related("produto__ficha__material__estoque")
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
            "montadores": Montadores.objects.all(),
            "setores": Setores.objects.all(),
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
        ordem.produto = get_object_or_404(ProdutoInterno, pk=produto_id)

        ordem.quantidade = inteiro(
            request.POST.get("quantidade"), "Quantidade",
            obrigatorio=True, minimo=1, maximo=100000,
        )

        status = (request.POST.get("status") or OrdemProducao.Status.PLANEJADA).strip()
        if status not in OrdemProducao.Status.values:
            raise ErroDeFormulario("Situação inválida para a ordem.")
        if status == OrdemProducao.Status.CONCLUIDA:
            raise ErroDeFormulario(
                "Para concluir use o botão 'Concluir': é ele que dá baixa no estoque."
            )
        ordem.status = status

        montador_id = (request.POST.get("montador") or "").strip()
        ordem.montador = (
            get_object_or_404(Montadores, pk=montador_id)
            if montador_id.isdigit() else None
        )

        setor_id = (request.POST.get("setor") or "").strip()
        ordem.setor = (
            get_object_or_404(Setores, pk=setor_id)
            if setor_id.isdigit() else None
        )

        ordem.prevista_para = data(request.POST.get("prevista_para"), "Data prevista")
        ordem.observacoes = texto(request, "observacoes")

        if not ordem.pk:
            ordem.responsavel = request.user

        ordem.save()
        return self.sucesso(request, f"Ordem #{ordem.pk} salva.", id=ordem.pk)

    @transaction.atomic
    def acao_concluir(self, request):
        ordem = get_object_or_404(OrdemProducao, pk=request.POST.get("id"))
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
