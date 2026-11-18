"""Da nota lida ao estoque: a conferência guardada e o lançamento.

TRÊS PASSOS, cada um numa transação:

  1. `abrir_conferencia` -- a nota lida (PDF ou XML) vira uma NotaEntrada
     EM CONFERÊNCIA, com o arquivo no cofre privado e as linhas já ligadas
     aos materiais e somadas (`ligacao.agrupar`). A mesma nota JÁ LANÇADA
     é recusada aqui, antes de qualquer conferência; a mesma nota ainda em
     conferência é substituída pela leitura nova (o XML depois do PDF, por
     exemplo).
  2. `guardar_conferencia` -- o que a pessoa escolheu na tela (material,
     "novo", "não entra", quantidade, unidade, local, data de entrada)
     fica gravado ANTES de lançar. Se o lançamento recusar alguma coisa, a
     tela volta com tudo como a pessoa deixou -- e não com a leitura crua.
  3. `lancar` -- tudo ou nada: o fornecedor (pelo CNPJ) e os materiais que
     faltam são criados, cada material entra no estoque pelo MESMO caminho
     das outras entradas (`MovimentoEstoque.registrar`, com a data, a nota
     e quem lançou), os itens do mesmo material e local viram UMA entrada,
     e a compra vai para o Financeiro (`ComprasMensais`, que a tela
     Financeiro já soma como "compras de material" do mês).

POR QUE COMPRA, E NÃO DESPESA. O Financeiro soma, mês a mês, as despesas
(`DespesasMensais`, com categoria: aluguel, luz...) e as compras de
material (`ComprasMensais` + `ItensCompra`, item a item com o material).
Nota de fornecedor de material é compra; lançar também uma despesa
contaria o mesmo dinheiro duas vezes no "saídas" do mês. A compra entra no
mês da DATA DE ENTRADA.
"""

from __future__ import annotations

import hashlib
import re
from collections import OrderedDict
from datetime import datetime, time
from decimal import Decimal

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ..utils import ErroDeFormulario
from ..validacoes import chave_documento, documento_valido
from . import leitura
from .ligacao import Catalogo, agrupar, chave_de_nome, nome_para_material


# ======================================================================
# A MESMA NOTA
# ======================================================================
def notas_iguais(chave="", cnpj="", numero="", serie=""):
    """As notas com a mesma chave -- ou, sem chave, o mesmo CNPJ + número + série."""
    from ..models import NotaEntrada

    filtro = Q()
    if chave:
        filtro |= Q(chave_acesso=chave)
    if cnpj and numero:
        mesma = Q(fornecedor_cnpj=cnpj, numero=numero)
        if serie:
            mesma &= Q(serie=serie)
        filtro |= mesma
    if not filtro:
        return NotaEntrada.objects.none()
    return NotaEntrada.objects.filter(filtro)


def descrever_lancamento(nota) -> str:
    quem = ""
    if nota.lancada_por_id:
        quem = nota.lancada_por.get_full_name() or nota.lancada_por.get_username()
    quando = timezone.localtime(nota.lancada_em).strftime("%d/%m/%Y") if nota.lancada_em else ""
    partes = [f"Esta nota (NF-e {nota.numero_e_serie}) já foi lançada no estoque"]
    if quando:
        partes.append(f"em {quando}")
    if quem:
        partes.append(f"por {quem}")
    return " ".join(partes) + ". A mesma nota não entra duas vezes."


class NotaJaLancada(ErroDeFormulario):
    def __init__(self, nota):
        self.nota = nota
        super().__init__(descrever_lancamento(nota))


# ======================================================================
# 1. ABRIR A CONFERÊNCIA
# ======================================================================
def abrir_conferencia(nota_lida: leitura.NotaLida, conteudo: bytes, nome_arquivo: str, usuario):
    """Grava a leitura como NotaEntrada em conferência. Devolve (nota, substituída?)."""
    from ..models import ItemNotaEntrada, NotaEntrada

    iguais = notas_iguais(
        nota_lida.chave, nota_lida.fornecedor_cnpj, nota_lida.numero, nota_lida.serie,
    ).select_related("lancada_por")
    lancada = iguais.filter(situacao=NotaEntrada.Situacao.LANCADA).first()
    if lancada:
        raise NotaJaLancada(lancada)

    substituida = False
    nome_seguro = re.sub(r"[^\w.\- ]", "", (nome_arquivo or "").rsplit("/", 1)[-1])[:150] or f"nota.{nota_lida.formato}"
    with transaction.atomic():
        for antiga in iguais.filter(situacao=NotaEntrada.Situacao.CONFERENCIA):
            descartar(antiga)
            substituida = True

        nota = NotaEntrada(
            formato=nota_lida.formato,
            nome_arquivo=nome_seguro,
            tamanho_arquivo=len(conteudo),
            sha256=hashlib.sha256(conteudo).hexdigest(),
            fornecedor_nome=(nota_lida.fornecedor_nome or "")[:120],
            fornecedor_cnpj=(nota_lida.fornecedor_cnpj or "")[:14],
            numero=(nota_lida.numero or "")[:9],
            serie=(nota_lida.serie or "")[:3],
            emissao=nota_lida.emissao,
            chave_acesso=nota_lida.chave,
            valor_produtos=(nota_lida.valor_produtos if nota_lida.valor_produtos is not None else nota_lida.soma_dos_itens),
            valor_total=(nota_lida.valor_total if nota_lida.valor_total is not None else nota_lida.soma_dos_itens),
            data_entrada=timezone.localdate(),
            avisos=list(nota_lida.avisos)[:30],
            enviada_por=usuario if getattr(usuario, "pk", None) else None,
        )
        nota.fornecedor = fornecedor_pelo_documento(nota.fornecedor_cnpj)
        nota.arquivo.save(f"nota.{nota_lida.formato}", ContentFile(conteudo), save=False)
        nome_guardado = nota.arquivo.name
        armazenamento = nota.arquivo.storage
        # O arquivo já está no cofre; se o banco recusar o resto, ele não
        # pode ficar órfão lá.
        try:
            nota.save()
            catalogo = Catalogo(nota.fornecedor_cnpj)
            ItemNotaEntrada.objects.bulk_create([
                ItemNotaEntrada(nota=nota, **linha) for linha in agrupar(nota_lida.itens, catalogo)
            ])
        except Exception:
            armazenamento.delete(nome_guardado)
            raise
    return nota, substituida


def descartar(nota) -> None:
    """Apaga uma nota EM CONFERÊNCIA e o arquivo dela (depois do commit)."""
    from ..models import NotaEntrada

    if nota.situacao != NotaEntrada.Situacao.CONFERENCIA:
        raise ErroDeFormulario("Nota já lançada não se descarta: ela é o registro da entrada no estoque.")
    nome = nota.arquivo.name if nota.arquivo else ""
    armazenamento = nota.arquivo.storage if nota.arquivo else None
    nota.delete()
    if nome and armazenamento is not None:
        transaction.on_commit(lambda: armazenamento.delete(nome))


def fornecedor_pelo_documento(documento: str):
    """O fornecedor cadastrado com este CNPJ/CPF, escrito de qualquer jeito."""
    from ..models import Fornecedor

    documento = chave_documento(documento)
    if not documento:
        return None
    for fornecedor in Fornecedor.objects.exclude(cnpj="").order_by("-ativo", "pk"):
        if chave_documento(fornecedor.cnpj) == documento:
            return fornecedor
    return None


def documento_formatado(documento: str) -> str:
    if len(documento) == 14:
        return f"{documento[:2]}.{documento[2:5]}.{documento[5:8]}/{documento[8:12]}-{documento[12:]}"
    if len(documento) == 11:
        return f"{documento[:3]}.{documento[3:6]}.{documento[6:9]}-{documento[9:]}"
    return documento


# ======================================================================
# 2. GUARDAR O QUE A PESSOA CONFERIU
# ======================================================================
def guardar_conferencia(nota, dados: dict) -> list[str]:
    """Grava as escolhas da tela. Devolve os problemas achados (vazio = ok).

    `dados`: data_entrada, fornecedor_nome, fornecedor_cnpj, numero, serie,
    emissao (já convertidos pela view, None quando ilegíveis) e `itens`:
    {pk: {material: "novo"|"fora"|"<id>", nome, unidade, quantidade, local}}.
    Item que não veio no envio fica como estava.
    """
    from ..models import ItemNotaEntrada, Material, NotaEntrada

    if nota.situacao != NotaEntrada.Situacao.CONFERENCIA:
        raise ErroDeFormulario("Esta nota já foi lançada; a conferência dela não muda mais.")
    problemas = list(dados.get("problemas") or [])

    if dados.get("data_entrada"):
        nota.data_entrada = dados["data_entrada"]
    if dados.get("emissao"):
        nota.emissao = dados["emissao"]
    if "fornecedor_nome" in dados:
        nota.fornecedor_nome = (dados["fornecedor_nome"] or nota.fornecedor_nome)[:120]
    if not nota.chave_acesso:
        # Com a chave, número, série e CNPJ saem dela: não se editam.
        if dados.get("fornecedor_cnpj") is not None:
            nota.fornecedor_cnpj = chave_documento(dados["fornecedor_cnpj"])
        if dados.get("numero") is not None:
            numero = re.sub(r"\D", "", dados["numero"])
            nota.numero = str(int(numero))[:9] if numero else ""
        if dados.get("serie") is not None:
            serie = re.sub(r"\D", "", dados["serie"])
            nota.serie = str(int(serie))[:3] if serie else ""
    nota.fornecedor = fornecedor_pelo_documento(nota.fornecedor_cnpj)
    nota.save()

    escolhidos = {
        int(valor["material"]) for valor in (dados.get("itens") or {}).values()
        if str(valor.get("material") or "").isdigit()
    }
    materiais = Material.objects.filter(pk__in=escolhidos).in_bulk()
    for item in nota.itens.all():
        valor = (dados.get("itens") or {}).get(item.pk)
        if not valor:
            continue
        escolha = str(valor.get("material") or "").strip()
        if escolha == "fora":
            item.material, item.ligacao, item.semelhanca = None, ItemNotaEntrada.Ligacao.FORA, 0
        elif escolha == "novo":
            item.material, item.ligacao, item.semelhanca = None, ItemNotaEntrada.Ligacao.NOVO, 0
        elif escolha.isdigit():
            material = materiais.get(int(escolha))
            if material is None:
                problemas.append(f"Item {item.ordem}: o material escolhido não existe mais. Escolha outro.")
            elif material.pk != item.material_id:
                item.material, item.ligacao, item.semelhanca = material, ItemNotaEntrada.Ligacao.MANUAL, 0
            elif item.ligacao in (ItemNotaEntrada.Ligacao.NOVO, ItemNotaEntrada.Ligacao.FORA):
                item.ligacao = ItemNotaEntrada.Ligacao.MANUAL
        nome = re.sub(r"\s+", " ", str(valor.get("nome") or "")).strip()
        if nome:
            item.nome_material = nome[:90]
        unidade = str(valor.get("unidade") or "").strip()
        if unidade in Material.Unidade.values:
            item.unidade = unidade
        quantidade = valor.get("quantidade")
        if isinstance(quantidade, int) and quantidade >= 0:
            item.quantidade = quantidade
        if "local" in valor:
            item.local = re.sub(r"\s+", " ", str(valor.get("local") or "")).strip()[:90]
        item.save()
    return problemas


# ======================================================================
# 3. LANÇAR
# ======================================================================
def _rotulo(item) -> str:
    descricao = item.descricao if len(item.descricao) <= 40 else item.descricao[:38] + "…"
    return f"Item {item.ordem} ({descricao})"


def _obter_fornecedor(nota):
    """O fornecedor da nota: pelo CNPJ; sem ele cadastrado, cria (ou completa)."""
    from ..models import Fornecedor

    documento = chave_documento(nota.fornecedor_cnpj)
    if documento and not documento_valido(documento):
        raise ErroDeFormulario(f"O CNPJ/CPF do fornecedor ({documento_formatado(documento)}) não é válido. Confira.")
    existente = fornecedor_pelo_documento(documento)
    if existente:
        return existente, False
    nome = re.sub(r"\s+", " ", nota.fornecedor_nome or "").strip()[:120]
    if not nome:
        if not documento:
            raise ErroDeFormulario("Informe o fornecedor da nota (nome ou CNPJ).")
        nome = f"Fornecedor {documento_formatado(documento)}"
    formatado = documento_formatado(documento)
    mesmo_nome = Fornecedor.objects.filter(nome__iexact=nome).first()
    if mesmo_nome:
        if not chave_documento(mesmo_nome.cnpj):
            # O cadastro feito à mão, sem CNPJ: é ele. A nota completa.
            if documento:
                mesmo_nome.cnpj = formatado
                mesmo_nome.save(update_fields=["cnpj", "atualizado"])
            return mesmo_nome, False
        if not documento:
            return mesmo_nome, False
        # Mesmo nome, outro CNPJ (outra filial): o nome leva o CNPJ junto,
        # senão o cadastro (nome único) recusaria.
        nome = f"{nome[:120 - len(formatado) - 3]} ({formatado})"
        mesmo_nome = Fornecedor.objects.filter(nome__iexact=nome).first()
        if mesmo_nome:
            return mesmo_nome, False
    fornecedor = Fornecedor.objects.create(
        nome=nome,
        cnpj=formatado,
        observacoes=f"Cadastrado pela entrada da nota fiscal {nota.documento}.",
    )
    return fornecedor, True


def _meio_dia(dia):
    return timezone.make_aware(datetime.combine(dia, time(12, 0)))


@transaction.atomic
def lancar(nota_id, usuario):
    """Lança a nota conferida. Tudo ou nada; devolve a nota e um resumo."""
    from ..models import (
        ComprasMensais,
        EstoqueMaterial,
        ItemNotaEntrada,
        ItensCompra,
        Material,
        MovimentoEstoque,
        NotaEntrada,
    )

    nota = NotaEntrada.objects.select_for_update().get(pk=nota_id)
    if nota.situacao != NotaEntrada.Situacao.CONFERENCIA:
        raise ErroDeFormulario(descrever_lancamento(nota))

    hoje = timezone.localdate()
    if not nota.data_entrada:
        raise ErroDeFormulario("Informe a data de entrada.")
    if nota.data_entrada > hoje:
        raise ErroDeFormulario("A data de entrada não pode ser depois de hoje.")
    if not nota.numero:
        raise ErroDeFormulario("Informe o número da nota.")

    repetida = (
        notas_iguais(nota.chave_acesso, nota.fornecedor_cnpj, nota.numero, nota.serie)
        .filter(situacao=NotaEntrada.Situacao.LANCADA)
        .exclude(pk=nota.pk)
        .select_related("lancada_por")
        .first()
    )
    if repetida:
        raise NotaJaLancada(repetida)

    itens = list(nota.itens.select_related("material").order_by("ordem", "pk"))
    if not itens:
        raise ErroDeFormulario("A nota não tem itens para lançar.")

    # ------------------------------------------------ conferir cada linha
    grupos: "OrderedDict[tuple, list]" = OrderedDict()
    trocar_unidade = {}
    for item in itens:
        if item.ligacao == ItemNotaEntrada.Ligacao.FORA:
            continue
        if item.quantidade < 1:
            raise ErroDeFormulario(
                f"{_rotulo(item)}: informe quantas unidades entram no estoque "
                "(ou marque “não entra no estoque”)."
            )
        if not item.local.strip():
            raise ErroDeFormulario(f"{_rotulo(item)}: informe o local de guarda.")
        if item.unidade not in Material.Unidade.values:
            raise ErroDeFormulario(f"{_rotulo(item)}: escolha a unidade.")
        if item.material_id:
            material = item.material
            if material.unidade != item.unidade:
                saldo = sum(local.quantidade for local in material.estoque.all())
                if saldo:
                    raise ErroDeFormulario(
                        f"{_rotulo(item)}: “{material.nome_material}” já tem {saldo} em estoque contado(s) "
                        f"em {material.get_unidade_display().lower()}. Deixe a unidade assim e converta a "
                        "quantidade (por exemplo, 1 caixa com 200 = 200)."
                    )
                trocar_unidade[material.pk] = item.unidade
            alvo = ("material", material.pk)
        else:
            nome = (item.nome_material or nome_para_material(item.descricao)).strip()
            if not nome:
                raise ErroDeFormulario(f"{_rotulo(item)}: dê um nome ao material novo.")
            item.nome_material = nome[:90]
            alvo = ("novo", chave_de_nome(nome) or nome.casefold())
        grupos.setdefault((alvo, item.local.strip().casefold()), []).append(item)

    # Linhas que vão para o mesmo material são somadas -- então têm de estar
    # contadas na mesma unidade (2 caixas + 10 unidades não dão 12 de nada).
    por_material = {}
    for (alvo, _), membros in grupos.items():
        for item in membros:
            unidade = por_material.setdefault(alvo, item.unidade)
            if unidade != item.unidade:
                raise ErroDeFormulario(
                    f"{_rotulo(item)}: vai para o mesmo material de outra linha, mas em outra unidade. "
                    "Deixe as duas na mesma unidade (convertendo a quantidade)."
                )

    fornecedor, fornecedor_novo = _obter_fornecedor(nota)

    # ------------------------------------------------ materiais novos
    novos = {}
    criados = 0
    if any(alvo[0] == "novo" for alvo, _ in grupos):
        por_nome = {}
        for material in Material.objects.filter(ativo=True).order_by("pk"):
            por_nome.setdefault(chave_de_nome(material.nome_material), material)
        for (alvo, _), membros in grupos.items():
            if alvo[0] != "novo" or alvo[1] in novos:
                continue
            primeiro = membros[0]
            material = por_nome.get(alvo[1])
            if material is None:
                material = Material.objects.create(
                    nome_material=primeiro.nome_material,
                    descricao=(primeiro.descricao if primeiro.descricao != primeiro.nome_material else "")[:150] or None,
                    unidade=primeiro.unidade,
                )
                criados += 1
            novos[alvo[1]] = material
    for pk, unidade in trocar_unidade.items():
        Material.objects.filter(pk=pk).update(unidade=unidade, atualizado=timezone.now())

    # ------------------------------------------------ a entrada no estoque
    entradas = 0
    pecas = 0
    itens_compra = []
    for (alvo, _), membros in grupos.items():
        material = novos[alvo[1]] if alvo[0] == "novo" else membros[0].material
        local = membros[0].local.strip()
        quantidade = sum(item.quantidade for item in membros)
        total = sum((item.valor_total for item in membros), Decimal("0.00"))
        estoque = (
            EstoqueMaterial.objects.filter(material=material, descricao_local__iexact=local)
            .order_by("pk").first()
        )
        if estoque is None:
            estoque = EstoqueMaterial.objects.create(
                material=material,
                descricao_local=local,
                quantidade=0,
                saldo_valor=Decimal("0.00"),
                preco_fornecedor=Decimal("0.00"),
                fornecedor=fornecedor,
                nota_fiscal=nota.documento,
                comprado_em=nota.data_entrada,
            )
        linhas = ", ".join(item.linhas_nota or str(item.ordem) for item in membros)
        movimento = MovimentoEstoque.registrar(
            estoque,
            MovimentoEstoque.Tipo.ENTRADA,
            quantidade,
            valor_unitario=(total / quantidade).quantize(Decimal("0.01")),
            valor_total=total,
            fornecedor=fornecedor,
            data_compra=nota.data_entrada,
            documento=nota.documento,
            motivo=f"Entrada da nota fiscal (linha{'s' if ',' in linhas else ''} {linhas} da nota)"[:150],
            responsavel=usuario,
            nota_entrada=nota,
        )
        entradas += 1
        pecas += quantidade
        for item in membros:
            item.material = material
            item.movimento = movimento
            item.local = estoque.descricao_local
            # (a unidade do item já é a do material -- conferida acima, ou a
            # nova, quando o material sem saldo trocou de unidade)
            item.save(update_fields=["material", "movimento", "local", "nome_material", "atualizado"])
        itens_compra.append(ItensCompra(material=material, quantidade=quantidade, subtotal=total))

    for item in itens:
        if item.ligacao == ItemNotaEntrada.Ligacao.FORA:
            itens_compra.append(ItensCompra(
                material=None,
                quantidade=max(int(item.quantidade_nota.to_integral_value()), 1),
                subtotal=item.valor_total,
            ))

    # ------------------------------------------------ a compra no Financeiro
    soma = sum((item.valor_total for item in itens), Decimal("0.00"))
    compra = ComprasMensais.objects.create(
        descricao_compra=f"{nota.documento} · {fornecedor.nome}"[:120],
        valor=nota.valor_total or soma,
    )
    for item_compra in itens_compra:
        item_compra.compra = compra
    ItensCompra.objects.bulk_create(itens_compra)
    # O Financeiro soma as compras pelo mês de `criacao`: a compra entra no
    # mês em que a mercadoria ENTROU, e não no dia em que alguém digitou.
    ComprasMensais.objects.filter(pk=compra.pk).update(criacao=_meio_dia(nota.data_entrada))

    nota.situacao = NotaEntrada.Situacao.LANCADA
    nota.fornecedor = fornecedor
    nota.fornecedor_nome = fornecedor.nome if not nota.fornecedor_nome else nota.fornecedor_nome
    nota.lancada_por = usuario if getattr(usuario, "pk", None) else None
    nota.lancada_em = timezone.now()
    nota.compra = compra
    nota.save()

    return nota, {
        "entradas": entradas,
        "pecas": pecas,
        "materiais_novos": criados,
        "fornecedor_novo": fornecedor_novo,
        "fora": sum(1 for item in itens if item.ligacao == ItemNotaEntrada.Ligacao.FORA),
    }
