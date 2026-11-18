"""Entrada de nota fiscal no estoque (LEIA-ME-V10, seção 115).

O PEDIDO: "na entrada, devemos lançar uma nota com os materiais, auto
criando se não existir e registrando o estoque, dia de entrada e soma se
houver juntos. o financeiro dá entrada pela função".

TRÊS TELAS:

  * `NotasEntradaView` (/estoque/notas/) -- subir o PDF (DANFE) ou o XML da
    NF-e, e a lista das notas (Lista ou Cards): em conferência e lançadas.
  * `NotaEntradaView` (/estoque/notas/<id>/) -- a CONFERÊNCIA, estilo app:
    o fornecedor, a nota e cada item ligado a um material (ou "novo, será
    criado", ou "não entra no estoque"), com quantidade, unidade e local
    para ajustar e a data de entrada já com hoje. "Lançar no estoque"
    confirma; depois de lançada, a mesma tela mostra o que entrou.
  * `ArquivoNotaEntradaView` -- o arquivo da nota, só por aqui (cofre
    privado, sem endereço público, `no-store`).

QUEM: lança quem paga a compra -- `capacidades["entrada_nota"]`
(Financeiro, Gestão e o superusuário). A Engenharia de produção, dona do
estoque, VÊ as notas lançadas (`entrada_nota_ver`), sem lançar nem ver as
que ainda estão em conferência.
"""

from __future__ import annotations

import logging

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .context_processors import invalidar_avisos
from .models import ItemNotaEntrada, Material, NotaEntrada
from .notas_entrada import lancamento, leitura
from .notas_entrada.ligacao import locais_de_guarda
from .permissoes import FINANCEIRO, GESTAO, PRODUCAO, capacidades
from .utils import ErroDeFormulario, data, inteiro
from .views import InternoRequiredMixin

logger = logging.getLogger(__name__)

#: Ações perigosas no PDF guardado: script e programa que abre sozinho.
PDF_ATIVO = (b"/JavaScript", b"/Launch")

#: O rótulo do chip de unidade: curto, para os nove caberem numa linha.
UNIDADE_CURTA = {"un": "un", "pc": "pç", "m": "m", "m2": "m²", "kg": "kg", "l": "L", "cx": "cx", "rl": "rolo", "par": "par"}


class _BaseNotas(InternoRequiredMixin):
    # Quem passa da porta do painel; o que cada um faz dentro é a capacidade.
    funcoes_necessarias = (FINANCEIRO, GESTAO, PRODUCAO)

    def dispatch(self, request, *args, **kwargs):
        if getattr(request, "is_interno", False) and request.user.is_authenticated:
            self.acesso = capacidades(request.user)
        else:
            self.acesso = {}
        return super().dispatch(request, *args, **kwargs)

    @property
    def pode_lancar(self):
        return bool(self.acesso.get("entrada_nota"))

    def recusar_sem_permissao(self, request):
        if not self.acesso.get("entrada_nota_ver"):
            return redirect(self.destino_do_usuario(request.user))
        messages.error(request, "Lançar nota fiscal é do Financeiro (ou da Gestão). Aqui você só consulta.")
        return redirect("notas_entrada")


# ======================================================================
# A LISTA E O ENVIO DO ARQUIVO
# ======================================================================
class NotasEntradaView(_BaseNotas):
    template_name = "notas_entrada_inner.html"
    POR_PAGINA = 30
    FILTROS = ("todas", "conferencia", "lancada")

    def get(self, request):
        if not self.acesso.get("entrada_nota_ver"):
            return redirect(self.destino_do_usuario(request.user))

        visiveis = NotaEntrada.objects.all()
        if not self.pode_lancar:
            # A Produção vê o que ENTROU; a conferência é de quem lança.
            visiveis = visiveis.filter(situacao=NotaEntrada.Situacao.LANCADA)

        filtro = (request.GET.get("situacao") or "todas").strip()
        if filtro not in self.FILTROS:
            filtro = "todas"
        busca = (request.GET.get("q") or "").strip()[:80]
        lista = visiveis
        if filtro != "todas":
            lista = lista.filter(situacao=filtro)
        if busca:
            digitos = leitura.so_digitos(busca)
            filtro_busca = (
                Q(fornecedor_nome__icontains=busca)
                | Q(fornecedor__nome__icontains=busca)
                | Q(itens__descricao__icontains=busca)
            )
            if digitos:
                filtro_busca |= Q(numero=digitos.lstrip("0") or "0") | Q(chave_acesso__contains=digitos) | Q(
                    fornecedor_cnpj__contains=digitos
                )
            # Por subconsulta: o filtro pelos itens não pode multiplicar a
            # contagem de itens de cada nota, logo abaixo.
            lista = lista.filter(pk__in=NotaEntrada.objects.filter(filtro_busca).values("pk"))
        lista = (
            lista.select_related("fornecedor", "lancada_por", "enviada_por")
            .annotate(total_itens=Count("itens"))
            .order_by("-criacao", "-id")
        )

        pagina = Paginator(lista, self.POR_PAGINA).get_page(request.GET.get("page"))
        inicio_do_mes = timezone.localdate().replace(day=1)
        consulta = visiveis
        lancadas = consulta.filter(situacao=NotaEntrada.Situacao.LANCADA)
        filtros = request.GET.copy()
        filtros.pop("page", None)
        return render(request, self.template_name, {
            "notas": pagina.object_list,
            "pagina": pagina,
            "filtros_url": filtros.urlencode(),
            "filtro": filtro,
            "busca": busca,
            "pode_lancar": self.pode_lancar,
            "tamanho_maximo_mb": leitura.TAMANHO_MAXIMO // (1024 * 1024),
            "total_conferencia": consulta.filter(situacao=NotaEntrada.Situacao.CONFERENCIA).count(),
            "total_lancadas": lancadas.count(),
            "lancado_no_mes": lancadas.filter(data_entrada__gte=inicio_do_mes).aggregate(
                soma=Sum("valor_total"),
            )["soma"] or 0,
            "notas_no_mes": lancadas.filter(data_entrada__gte=inicio_do_mes).count(),
        })

    def post(self, request):
        """Recebe o PDF ou o XML, lê e abre a conferência."""
        if not self.pode_lancar:
            return self.recusar_sem_permissao(request)
        arquivo = request.FILES.get("arquivo")
        if arquivo is None:
            messages.error(request, "Escolha o arquivo da nota: o PDF (DANFE) ou o XML da NF-e.")
            return redirect("notas_entrada")
        nome = (arquivo.name or "nota")[:150]
        # O tamanho é conferido ANTES de ler: o arquivo enorme não chega a
        # ocupar a memória do servidor só para ser recusado.
        if arquivo.size > leitura.TAMANHO_MAXIMO:
            messages.error(
                request,
                f"O arquivo passa de {leitura.TAMANHO_MAXIMO // (1024 * 1024)} MB. Uma nota fiscal "
                "não chega perto disso: confira se escolheu o arquivo certo.",
            )
            return redirect("notas_entrada")
        try:
            conteudo = arquivo.read()
        finally:
            arquivo.close()

        try:
            formato = leitura.formato_do_arquivo(nome, conteudo)
            if formato == "pdf" and any(marca in conteudo for marca in PDF_ATIVO):
                raise leitura.NotaRecusada(
                    "Este PDF tem script embutido e não pode ser guardado. Envie o XML da nota, "
                    "ou o PDF que o fornecedor mandou por e-mail."
                )
            nota_lida = leitura.ler(nome, conteudo)
            nota, substituida = lancamento.abrir_conferencia(nota_lida, conteudo, nome, request.user)
        except lancamento.NotaJaLancada as exc:
            messages.error(request, str(exc), extra_tags="modal; titulo:Nota já lançada; icone:arquivo-x")
            return redirect("nota_entrada", pk=exc.nota.pk)
        except (leitura.NotaRecusada, ErroDeFormulario) as exc:
            messages.error(request, str(exc))
            return redirect("notas_entrada")
        finally:
            del conteudo

        recado = (
            f"Nota {nota.numero_e_serie} lida: {nota.itens.count()} linha(s) para conferir."
        )
        if substituida:
            recado += " A leitura anterior desta nota, que ainda não tinha sido lançada, foi trocada por esta."
        messages.success(request, recado)
        return redirect("nota_entrada", pk=nota.pk)


# ======================================================================
# A CONFERÊNCIA (e, depois de lançada, o que entrou)
# ======================================================================
class NotaEntradaView(_BaseNotas):
    template_name = "nota_entrada_inner.html"

    def nota_ou_404(self, pk):
        nota = get_object_or_404(
            NotaEntrada.objects.select_related("fornecedor", "lancada_por", "enviada_por", "compra"), pk=pk,
        )
        if not self.acesso.get("entrada_nota_ver"):
            raise Http404("Nota não encontrada.")
        if not nota.lancada and not self.pode_lancar:
            raise Http404("Nota não encontrada.")
        return nota

    def get(self, request, pk):
        if not self.acesso.get("entrada_nota_ver"):
            return redirect(self.destino_do_usuario(request.user))
        nota = self.nota_ou_404(pk)
        editar = self.pode_lancar and not nota.lancada
        itens = list(
            nota.itens.select_related("material", "movimento", "movimento__estoque").order_by("ordem", "pk")
        )
        for item in itens:
            # O valor do campo escondido da ligação: o id do material, "novo" ou "fora".
            if item.ligacao == ItemNotaEntrada.Ligacao.FORA:
                item.escolha = "fora"
            else:
                item.escolha = str(item.material_id) if item.material_id else "novo"
        contexto = {
            "nota": nota,
            "itens": itens,
            "editar": editar,
            "pode_lancar": self.pode_lancar,
            "unidades": [(valor, rotulo, UNIDADE_CURTA.get(valor, valor)) for valor, rotulo in Material.Unidade.choices],
            "hoje": timezone.localdate(),
            "resumo": self.resumo(nota, itens),
        }
        if editar:
            locais, padrao = locais_de_guarda()
            contexto.update({
                "locais": locais[:40],
                "local_padrao": padrao,
                "fornecedor_cadastrado": lancamento.fornecedor_pelo_documento(nota.fornecedor_cnpj),
                "materiais_dados": self.materiais_para_escolha(),
            })
        return render(request, self.template_name, contexto)

    @staticmethod
    def resumo(nota, itens):
        estoque = [item for item in itens if item.ligacao != ItemNotaEntrada.Ligacao.FORA]
        return {
            "linhas": len(itens),
            "linhas_nota": sum(len(item.linhas_somadas) or 1 for item in itens),
            "somadas": sum(1 for item in itens if len(item.linhas_somadas) > 1),
            "novos": sum(1 for item in estoque if not item.material_id),
            "parecidos": sum(1 for item in estoque if item.ligacao == ItemNotaEntrada.Ligacao.PARECIDO),
            "fora": len(itens) - len(estoque),
            "pecas": sum(item.quantidade for item in estoque),
        }

    @staticmethod
    def materiais_para_escolha():
        """Os materiais ativos para a busca da conferência (no aparelho)."""
        from .busca_local import sem_acento

        materiais = (
            Material.objects.filter(ativo=True)
            .prefetch_related("estoque")
            .order_by("nome_material", "pk")
        )
        return [
            {
                "id": material.pk,
                "nome": material.nome_material,
                "codigo": material.codigo_interno,
                "unidade": material.unidade,
                "unidade_nome": material.get_unidade_display(),
                "saldo": sum(local.quantidade for local in material.estoque.all()),
                "busca": sem_acento(f"{material.nome_material} {material.codigo_interno}"),
            }
            for material in materiais
        ]

    def post(self, request, pk):
        if not self.pode_lancar:
            return self.recusar_sem_permissao(request)
        nota = self.nota_ou_404(pk)
        acao = (request.POST.get("action") or "").strip()
        if acao == "descartar":
            return self.descartar(request, nota)
        if acao not in ("lancar", "guardar"):
            messages.error(request, "Ação inválida.")
            return redirect("nota_entrada", pk=nota.pk)
        if nota.lancada:
            messages.error(request, lancamento.descrever_lancamento(nota))
            return redirect("nota_entrada", pk=nota.pk)

        try:
            problemas = lancamento.guardar_conferencia(nota, self.dados_do_envio(request, nota))
        except ErroDeFormulario as exc:
            messages.error(request, str(exc))
            return redirect("nota_entrada", pk=nota.pk)
        if problemas:
            messages.error(request, problemas[0])
            return redirect("nota_entrada", pk=nota.pk)
        if acao == "guardar":
            messages.success(request, "Conferência salva. A nota continua aqui, esperando o lançamento.")
            return redirect("nota_entrada", pk=nota.pk)

        try:
            nota, feito = lancamento.lancar(nota.pk, request.user)
        except ErroDeFormulario as exc:
            messages.error(request, str(exc))
            return redirect("nota_entrada", pk=nota.pk)
        except IntegrityError:
            # A trava do banco: a mesma nota lançada por outra pessoa no
            # mesmo instante (a conferência acima já pega o caso comum).
            logger.warning("Nota de entrada %s recusada pela unicidade do banco", nota.pk)
            messages.error(request, "Esta nota acabou de ser lançada por outra pessoa. Confira a lista de notas.")
            return redirect("notas_entrada")

        invalidar_avisos(request.user)
        partes = [f"{feito['pecas']} unidade(s) em {feito['entradas']} entrada(s) no estoque"]
        if feito["materiais_novos"]:
            partes.append(f"{feito['materiais_novos']} material(is) novo(s) cadastrado(s)")
        if feito["fornecedor_novo"]:
            partes.append(f"fornecedor {nota.fornecedor.nome} cadastrado")
        if feito["fora"]:
            partes.append(f"{feito['fora']} linha(s) fora do estoque")
        messages.success(
            request,
            f"Nota {nota.numero_e_serie} lançada: " + "; ".join(partes)
            + f". A compra de R$ {_moeda(nota.valor_total)} está no Financeiro.",
        )
        return redirect("nota_entrada", pk=nota.pk)

    def descartar(self, request, nota):
        if nota.lancada:
            messages.error(request, "Nota já lançada não se descarta: ela é o registro da entrada no estoque.")
            return redirect("nota_entrada", pk=nota.pk)
        numero = nota.numero_e_serie
        lancamento.descartar(nota)
        messages.success(request, f"Leitura da nota {numero} descartada. Nada entrou no estoque.")
        return redirect("notas_entrada")

    @staticmethod
    def dados_do_envio(request, nota):
        """O POST da conferência, convertido. Valor ilegível vira problema, não 500."""
        problemas = []
        dados = {"problemas": problemas, "itens": {}}
        try:
            dados["data_entrada"] = data(request.POST.get("data_entrada"), "Data de entrada")
        except ErroDeFormulario as exc:
            problemas.append(str(exc))
        if not request.POST.get("data_entrada"):
            problemas.append("Informe a data de entrada.")
        try:
            dados["emissao"] = data(request.POST.get("emissao"), "Data de emissão")
        except ErroDeFormulario as exc:
            problemas.append(str(exc))
        for campo, limite in (("fornecedor_nome", 120), ("fornecedor_cnpj", 20), ("numero", 12), ("serie", 3)):
            if campo in request.POST:
                dados[campo] = (request.POST.get(campo) or "").strip()[:limite]
        for item in nota.itens.all():
            prefixo = f"item-{item.pk}-"
            if f"{prefixo}material" not in request.POST:
                continue
            valor = {
                "material": request.POST.get(f"{prefixo}material", ""),
                "nome": request.POST.get(f"{prefixo}nome", ""),
                "unidade": request.POST.get(f"{prefixo}unidade", ""),
                "local": request.POST.get(f"{prefixo}local", ""),
            }
            bruto = request.POST.get(f"{prefixo}quantidade")
            if bruto is not None:
                try:
                    valor["quantidade"] = inteiro(
                        bruto, f"Quantidade do item {item.ordem}", obrigatorio=True, minimo=0, maximo=2_000_000_000,
                    )
                except ErroDeFormulario as exc:
                    problemas.append(str(exc))
            dados["itens"][item.pk] = valor
        return dados


def _moeda(valor):
    from core.formatos import dinheiro

    return dinheiro(valor)


# ======================================================================
# O ARQUIVO DA NOTA
# ======================================================================
class ArquivoNotaEntradaView(_BaseNotas):
    def get(self, request, pk):
        nota = NotaEntrada.objects.filter(pk=pk).first()
        if nota is None or not self.acesso.get("entrada_nota_ver") or (not nota.lancada and not self.pode_lancar):
            raise Http404("Nota não encontrada.")
        if not nota.arquivo:
            raise Http404("Esta nota não tem arquivo guardado.")
        try:
            with nota.arquivo.open("rb") as arquivo:
                dados = arquivo.read()
        except (FileNotFoundError, OSError):
            messages.error(request, "O arquivo desta nota não foi encontrado no armazenamento.")
            return redirect("nota_entrada", pk=nota.pk)
        pdf = nota.formato == NotaEntrada.Formato.PDF
        resposta = HttpResponse(dados, content_type="application/pdf" if pdf else "application/xml")
        nome = f"nota-{nota.numero or nota.pk}.{nota.formato}"
        disposicao = "inline" if pdf and request.GET.get("baixar") != "1" else "attachment"
        resposta["Content-Disposition"] = f'{disposicao}; filename="{nome}"'
        resposta["X-Content-Type-Options"] = "nosniff"
        resposta["Content-Security-Policy"] = "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; sandbox"
        resposta["Referrer-Policy"] = "no-referrer"
        resposta["Cache-Control"] = "no-store, private"
        return resposta

