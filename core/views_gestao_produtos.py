"""Painel administrativo: peças de reposição e engajamento do catálogo.

Duas telas que faltavam no /adm/:

* **Peças de reposição** -- eram vendidas no site e no aplicativo, mas só
  podiam ser cadastradas pelo /system/ do Django. Aqui entram no mesmo
  padrão dos brinquedos: busca, filtro, modal de cadastro, galeria e
  exclusão com confirmação por texto.
* **Curtidas e desejos** -- o que o público marca no site e no app, com
  ranking por produto, para a decisão de estoque e vitrine parar de ser
  no chute.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from .models import (
    Brinquedos,
    CategoriaPeca,
    Favorito,
    ImagemPeca,
    PecasReposicao,
)
from .views import AdminOnlyMixin, ErroDeFormulario


logger = logging.getLogger(__name__)

MAX_IMAGENS_PECA = 8
MAX_TAMANHO_IMAGEM = 15 * 1024 * 1024  # 15 MB, igual ao dos brinquedos


def _decimal_br(valor) -> str:
    """Formata para o padrão brasileiro; vazio quando não há valor."""
    if valor is None:
        return ""
    numero = Decimal(valor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return (
        f"{numero:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def _para_decimal(valor, campo: str):
    """Aceita '1.234,56', '1234.56' e vazio -- o painel é digitado à mão."""
    texto = (str(valor or "")).strip().replace("R$", "").strip()
    if not texto:
        return None

    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")

    try:
        numero = Decimal(texto)
    except (InvalidOperation, ValueError) as erro:
        raise ErroDeFormulario(f"{campo}: valor inválido.") from erro

    if numero < 0:
        raise ErroDeFormulario(f"{campo}: não pode ser negativo.")

    return numero.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class PecaAdminView(AdminOnlyMixin, View):
    """CRUD de peças de reposição, no padrão do painel de brinquedos."""

    template_name = "gestao/pecas_adm.html"

    # ------------------------------------------------------------------
    # Leitura
    # ------------------------------------------------------------------
    def get(self, request):
        categoria = (request.GET.get("categoria") or "todas").strip()
        busca = (request.GET.get("q") or "").strip()
        situacao = (request.GET.get("situacao") or "todas").strip()

        pecas = (
            PecasReposicao.objects
            .prefetch_related("categoria_peca", "imagem_peca_reposicao")
            .annotate(
                curtidas=Count(
                    "favoritos",
                    filter=Q(favoritos__tipo=Favorito.Tipo.CURTIDA),
                    distinct=True,
                ),
                desejos=Count(
                    "favoritos",
                    filter=Q(favoritos__tipo=Favorito.Tipo.DESEJO),
                    distinct=True,
                ),
            )
            .order_by("nome", "id")
        )

        if categoria.isdigit():
            pecas = pecas.filter(categoria_peca__id=int(categoria)).distinct()

        if busca:
            pecas = pecas.filter(
                Q(nome__icontains=busca) | Q(descricao_peca__icontains=busca)
            )

        if situacao == "ativas":
            pecas = pecas.filter(ativo=True)
        elif situacao == "inativas":
            pecas = pecas.filter(ativo=False)
        elif situacao == "sem_foto":
            pecas = pecas.filter(imagem_peca_reposicao__isnull=True)
        elif situacao == "sem_preco":
            pecas = pecas.filter(preco_venda__isnull=True)

        pagina = Paginator(pecas, 40).get_page(request.GET.get("page"))

        dados = []
        for peca in pagina:
            fotos = [
                {
                    "id": foto.id,
                    "url": foto.imagem.url,
                    "posicao": foto.get_posicao_display(),
                    "ordem": foto.ordem,
                }
                for foto in peca.imagem_peca_reposicao.all()
                if foto.imagem
            ]

            dados.append({
                "id": peca.id,
                "nome": peca.nome,
                "descricao_peca": peca.descricao_peca or "",
                "preco_venda": _decimal_br(peca.preco_venda),
                "preco_fornecedor": _decimal_br(peca.preco_fornecedor),
                "ganho_potencial": _decimal_br(peca.ganho_potencial),
                "ativo": peca.ativo,
                "curtidas": peca.curtidas,
                "desejos": peca.desejos,
                "capa": fotos[0]["url"] if fotos else "",
                "imagens": fotos,
                "categorias_ids": [c.id for c in peca.categoria_peca.all()],
                "categorias_nomes": [
                    c.nome_categoria_peca for c in peca.categoria_peca.all()
                ],
            })

        todas = PecasReposicao.objects.all()
        contexto = {
            "pecas": dados,
            "page_obj": pagina,
            "categorias": CategoriaPeca.objects.order_by(
                "nome_categoria_peca",
            ),
            "posicoes": ImagemPeca.PosicaoImagem.choices,
            "filtro_categoria": categoria,
            "filtro_busca": busca,
            "filtro_situacao": situacao,
            "max_imagens": MAX_IMAGENS_PECA,
            "total_pecas": todas.count(),
            "total_ativas": todas.filter(ativo=True).count(),
            "total_sem_foto": todas.filter(
                imagem_peca_reposicao__isnull=True,
            ).distinct().count(),
            "total_sem_preco": todas.filter(preco_venda__isnull=True).count(),
        }

        return render(request, self.template_name, contexto)

    # ------------------------------------------------------------------
    # Escrita
    # ------------------------------------------------------------------
    @staticmethod
    def _pede_json(request) -> bool:
        return (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.POST.get("resposta") == "json"
        )

    def _erro(self, request, mensagem, status=400):
        # A falha vira resposta em vez de exceção, então o rollback do
        # @transaction.atomic precisa ser pedido na mão.
        transaction.set_rollback(True)

        if self._pede_json(request):
            return JsonResponse(
                {"status": "erro", "msg": mensagem},
                status=status,
            )

        messages.error(request, mensagem)
        return redirect("pecas_admin")

    def _sucesso(self, request, mensagem, peca_id=None):
        messages.success(request, mensagem)

        if self._pede_json(request):
            return JsonResponse({
                "status": "sucesso",
                "msg": mensagem,
                "id": peca_id,
            })

        return redirect("pecas_admin")

    @transaction.atomic
    def post(self, request):
        acao = request.POST.get("action", "save")

        try:
            if acao == "delete":
                return self._excluir(request)
            if acao == "categoria":
                return self._nova_categoria(request)
            if acao == "imagem_excluir":
                return self._excluir_imagem(request)
            if acao == "alternar_ativo":
                return self._alternar_ativo(request)
            if acao != "save":
                raise ErroDeFormulario("Ação inválida.")

            return self._salvar(request)

        except ErroDeFormulario as exc:
            return self._erro(request, str(exc))

        except Exception:
            logger.exception("Erro ao salvar peça no painel administrativo")
            return self._erro(
                request,
                "Não foi possível salvar a peça. Tente de novo.",
                status=500,
            )

    def _salvar(self, request):
        peca_id = (request.POST.get("id") or "").strip()
        nome = (request.POST.get("nome") or "").strip()
        descricao = (request.POST.get("descricao_peca") or "").strip()

        if not nome:
            raise ErroDeFormulario("Informe o nome da peça.")
        if len(nome) > 120:
            raise ErroDeFormulario("O nome da peça passa de 120 caracteres.")
        if not descricao:
            raise ErroDeFormulario("Descreva a peça: é o que o cliente lê.")

        preco_venda = _para_decimal(
            request.POST.get("preco_venda"),
            "Preço de venda",
        )
        preco_fornecedor = _para_decimal(
            request.POST.get("preco_fornecedor"),
            "Preço do fornecedor",
        )

        if peca_id:
            peca = get_object_or_404(PecasReposicao, pk=peca_id)
        else:
            peca = PecasReposicao()

        peca.nome = nome
        peca.descricao_peca = descricao
        peca.preco_venda = preco_venda
        peca.preco_fornecedor = preco_fornecedor
        peca.ativo = request.POST.get("ativo") in ("1", "true", "on")
        peca.save()

        categorias = request.POST.getlist("categorias")
        peca.categoria_peca.set(
            CategoriaPeca.objects.filter(
                id__in=[c for c in categorias if str(c).isdigit()],
            )
        )

        self._guardar_imagens(request, peca)

        return self._sucesso(
            request,
            f"Peça '{peca.nome}' salva com sucesso.",
            peca.id,
        )

    def _guardar_imagens(self, request, peca):
        arquivos = request.FILES.getlist("imagens")
        if not arquivos:
            return

        ja_tem = peca.imagem_peca_reposicao.count()
        se_couber = MAX_IMAGENS_PECA - ja_tem
        if se_couber <= 0:
            raise ErroDeFormulario(
                f"A peça já tem {MAX_IMAGENS_PECA} fotos. "
                "Apague uma antes de subir outra."
            )

        posicao = request.POST.get("posicao_imagem") or (
            ImagemPeca.PosicaoImagem.FRENTE
        )
        posicoes_validas = {op for op, _ in ImagemPeca.PosicaoImagem.choices}
        if posicao not in posicoes_validas:
            posicao = ImagemPeca.PosicaoImagem.FRENTE

        for indice, arquivo in enumerate(arquivos[:se_couber]):
            if arquivo.size > MAX_TAMANHO_IMAGEM:
                raise ErroDeFormulario(
                    f"A imagem '{arquivo.name}' passa de 15 MB."
                )

            ImagemPeca.objects.create(
                peca_reposicao=peca,
                imagem=arquivo,
                posicao=posicao,
                ordem=ja_tem + indice + 1,
            )

    def _excluir_imagem(self, request):
        imagem = get_object_or_404(
            ImagemPeca,
            pk=request.POST.get("imagem_id"),
        )
        peca_id = imagem.peca_reposicao_id
        imagem.delete()

        return self._sucesso(request, "Foto removida da galeria.", peca_id)

    def _alternar_ativo(self, request):
        peca = get_object_or_404(PecasReposicao, pk=request.POST.get("id"))
        peca.ativo = not peca.ativo
        peca.save(update_fields=["ativo", "atualizado"])

        estado = "publicada" if peca.ativo else "escondida do site"
        return self._sucesso(request, f"Peça {estado}.", peca.id)

    def _excluir(self, request):
        peca = get_object_or_404(PecasReposicao, pk=request.POST.get("id"))
        nome = peca.nome or "Peça"

        # Mesma trava dos brinquedos: exclusão só com o nome digitado.
        esperado = f"CONFIRMAR EXCLUSÃO {nome}"
        informado = (request.POST.get("confirmacao_exclusao") or "").strip()
        if informado != esperado:
            raise ErroDeFormulario(
                "Exclusão cancelada: o texto de confirmação não corresponde "
                "ao nome da peça."
            )

        peca.delete()
        return self._sucesso(request, f"Peça '{nome}' excluída.")

    def _nova_categoria(self, request):
        nome = (request.POST.get("nome_categoria_peca") or "").strip()
        if not nome:
            raise ErroDeFormulario("Informe o nome da categoria.")

        categoria, criada = CategoriaPeca.objects.get_or_create(
            nome_categoria_peca__iexact=nome,
            defaults={"nome_categoria_peca": nome},
        )

        if self._pede_json(request):
            return JsonResponse({
                "status": "sucesso",
                "msg": (
                    f"Categoria '{categoria.nome_categoria_peca}' "
                    + ("criada." if criada else "já existia.")
                ),
                "id": categoria.id,
                "nome": categoria.nome_categoria_peca,
            })

        messages.success(request, "Categoria salva.")
        return redirect("pecas_admin")


class EngajamentoAdminView(AdminOnlyMixin, View):
    """O que o público curte e guarda -- no site e no aplicativo."""

    template_name = "gestao/engajamento_adm.html"

    PERIODOS = {
        "7dias": 7,
        "30dias": 30,
        "90dias": 90,
    }

    def get(self, request):
        periodo = (request.GET.get("periodo") or "geral").strip()
        dias = self.PERIODOS.get(periodo)

        favoritos = Favorito.objects.all()
        if dias:
            favoritos = favoritos.filter(
                criacao__gte=timezone.now() - timedelta(days=dias)
            )
        else:
            periodo = "geral"

        def _ranking(modelo, campo, tipo, rotulo):
            marcados = (
                modelo.objects
                .annotate(
                    total=Count(
                        "favoritos",
                        filter=Q(favoritos__in=favoritos, favoritos__tipo=tipo),
                        distinct=True,
                    )
                )
                .filter(total__gt=0)
                .order_by("-total", campo)[:10]
            )
            return [
                {
                    "nome": getattr(item, campo),
                    "total": item.total,
                    "rotulo": rotulo,
                    "id": item.id,
                }
                for item in marcados
            ]

        contexto = {
            "periodo": periodo,
            "total_curtidas": favoritos.filter(
                tipo=Favorito.Tipo.CURTIDA,
            ).count(),
            "total_desejos": favoritos.filter(
                tipo=Favorito.Tipo.DESEJO,
            ).count(),
            "total_pelo_app": favoritos.filter(
                origem=Favorito.Origem.APP,
            ).count(),
            "total_pelo_site": favoritos.filter(
                origem=Favorito.Origem.SITE,
            ).count(),
            "total_com_conta": favoritos.filter(
                usuario__isnull=False,
            ).count(),
            "total_sem_conta": favoritos.filter(usuario__isnull=True).count(),
            "aparelhos": (
                favoritos
                .exclude(dispositivo="")
                .values("dispositivo")
                .distinct()
                .count()
            ),
            "brinquedos_curtidos": _ranking(
                Brinquedos,
                "nome_brinquedo",
                Favorito.Tipo.CURTIDA,
                "Brinquedo",
            ),
            "brinquedos_desejados": _ranking(
                Brinquedos,
                "nome_brinquedo",
                Favorito.Tipo.DESEJO,
                "Brinquedo",
            ),
            "pecas_curtidas": _ranking(
                PecasReposicao,
                "nome",
                Favorito.Tipo.CURTIDA,
                "Peça",
            ),
            "pecas_desejadas": _ranking(
                PecasReposicao,
                "nome",
                Favorito.Tipo.DESEJO,
                "Peça",
            ),
            "ultimos": (
                favoritos
                .select_related("brinquedo", "peca", "usuario")
                .order_by("-criacao", "-id")[:25]
            ),
        }

        return render(request, self.template_name, contexto)
