"""O CONTRATO DO PEDIDO DO SITE, assinado em Meus pedidos (LEIA-ME-V10, seção 145).

O pedido do dono: "se ele comprar pelo site, devemos também fazer o esquema
de assinaturas após tudo pago certinho, isso em meus pedidos".

É a TERCEIRA ORIGEM do `DocumentoAssinatura` (as outras: o orçamento e a
ordem de serviço). O retrato congelado, o hash, a página de assinar, o
comprovante e o PDF são os mesmos de `documento_assinatura.py`; o texto do
contrato é o de `contrato.py` (o do modelo da empresa, seção 141). Aqui
mora só o que é do pedido:

  * QUAIS COMPRAS PEDEM CONTRATO: as que levam máquina ou brinquedo --
    inclusive dentro de combo ou promoção. Pedido só de peças e kits NÃO
    pede (e Meus pedidos não mostra o passo). A regra é a da lista de
    montagem (`montagem.linhas_do_pedido`: o que vira máquina ou brinquedão).
  * QUANDO NASCE: no toque do cliente em "Assinar o contrato", com o pedido
    TOTALMENTE PAGO. Nunca no webhook do pagamento.
  * O COMPRADOR: a conta do site (nome, telefone, e-mail), o endereço de
    entrega do pedido e o CPF/CNPJ que o cliente CONFERE OU DIGITA antes de
    assinar (validado pelos dígitos; vem preenchido quando o checkout já o
    trouxe). O cadastro da conta e o checkout não mudam.
  * O VALOR: o total do pedido e, quando foi no cartão com acréscimo, o
    acréscimo e o valor cobrado, discriminados na condição de pagamento.
  * A ASSINATURA NÃO TRAVA NADA: produção e entrega seguem como já seguiam.
  * Cancelado, o contrato que ainda espera assinatura fica suspenso.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from . import contrato
from . import documento_assinatura as svc
from .models import DadosContrato, DocumentoAssinatura
from .utils import ErroDeFormulario
from .validacoes import chave_documento, documento_valido

from core.models import Pedido

#: As trilhas da lista de montagem que são "máquina ou brinquedo".
TRILHAS_COM_CONTRATO = ("maquina", "projeto")
ZERO = Decimal("0.00")


def numero_do_pedido(pedido) -> str:
    """"P0012/2026": o número do contrato do pedido do site (o "P" o separa do orçamento)."""
    ano = pedido.criacao.year if pedido.criacao else timezone.localdate().year
    return f"P{(pedido.pk or 0):04d}/{ano}"


def pede_contrato(pedido, regras=None) -> bool:
    """O pedido leva máquina ou brinquedo (direto, ou dentro de combo ou promoção)?"""
    from . import montagem

    try:
        linhas = montagem.linhas_do_pedido(pedido, regras)
    except Exception:  # noqa: BLE001 -- sem conseguir ler os itens, não oferece o contrato
        return False
    return any(linha.trilha in TRILHAS_COM_CONTRATO for linha in linhas)


def cpf_sugerido(pedido) -> str:
    """O CPF/CNPJ que o checkout já trouxe (o do carrinho), pontuado; "" sem ele."""
    chave = chave_documento(pedido.documento_da_venda or "")
    return svc.documento_pontuado(chave) if documento_valido(chave) else ""


def documento_atual_do_pedido(pedido):
    """O contrato que vale: o assinado, ou o que espera assinatura."""
    return (
        DocumentoAssinatura.objects
        .filter(pedido=pedido)
        .exclude(situacao=DocumentoAssinatura.Situacao.SUBSTITUIDO)
        .order_by("-id")
        .first()
    )


def motivo_da_suspensao_do_pedido(documento, pedido=None) -> str:
    """"pedido" quando o pedido foi cancelado depois de o contrato sair; "" se não."""
    pedido = pedido or documento.pedido
    return "pedido" if pedido.status == "cancelado" else ""


def motivo_para_nao_assinar(pedido) -> str:
    """Por que este pedido ainda não tem o passo de assinar; "" quando tem."""
    if pedido.status == "cancelado":
        return "O pedido foi cancelado."
    if not pedido.pago:
        return "O contrato fica disponível depois que o pagamento for confirmado."
    if not pede_contrato(pedido):
        return "Este pedido (peças e kits) não precisa de contrato."
    return ""


# ----------------------------------------------------------------------
# O RETRATO
# ----------------------------------------------------------------------
def _foto(item) -> str:
    """A foto do item, a mesma de Meus pedidos; "" sem foto (a folha desenha o quadro com o nome)."""
    from core.fotos import reduzir_imagem, url_da_imagem

    try:
        produto = item.item_original if item.content_type_id and item.object_id else None
        imagem = None
        if produto is not None:
            modelo = item.content_type.model
            if modelo == "brinquedos":
                imagem = produto.imagem_brinquedo
            elif modelo == "combos":
                imagem = produto.imagem_combo
            elif modelo == "promocoes":
                imagem = produto.imagem_promocao or (
                    produto.brinquedos.imagem_brinquedo if produto.brinquedos_id else None
                )
            elif modelo == "pecasreposicao":
                principal = produto.imagem_principal
                imagem = principal.imagem if principal else None
        url = url_da_imagem(imagem) if imagem else ""
        return reduzir_imagem(url, contrato.LARGURA_DA_FOTO) if url else ""
    except Exception:  # noqa: BLE001 -- foto que não abre vira "sem foto", nunca derruba o contrato
        return ""


def itens_do_pedido(pedido) -> list[dict]:
    from core.formatos import dinheiro

    itens = []
    for item in pedido.itens.all():
        adesivo = (getattr(item, "adesivo", "") or "").strip()
        itens.append({
            "descricao": item.nome_item,
            "detalhes": [],
            "quantidade": item.quantidade,
            "valor_unitario": f"{Decimal(item.preco_unitario or 0).quantize(Decimal('0.01')):.2f}",
            "subtotal": f"{Decimal(item.subtotal or 0).quantize(Decimal('0.01')):.2f}",
            "valor_unitario_texto": dinheiro(item.preco_unitario),
            "foto": _foto(item),
            "adesivo": adesivo,
            "adesivo_no_nome": bool(adesivo) and contrato._normalizar(adesivo) in contrato._normalizar(item.nome_item),
        })
    return itens


def valores_do_pedido(pedido) -> dict:
    """O total do pedido e, à parte, o acréscimo do cartão e o valor cobrado."""
    total = Decimal(pedido.total_final or pedido.total_liquido or 0).quantize(Decimal("0.01"))
    cobrado = Decimal(pedido.valor_cobrado).quantize(Decimal("0.01")) if pedido.valor_cobrado is not None else total
    acrescimo = max(cobrado - total, ZERO)
    return {"total": total, "cobrado": cobrado, "acrescimo_cartao": acrescimo}


def condicao_de_pagamento(pedido) -> str:
    """A Cláusula 2ª: como foi pago -- com o acréscimo do cartão discriminado."""
    from core.formatos import dinheiro

    valores = valores_do_pedido(pedido)
    forma = {"pix": "Pix", "cartao": "cartão de crédito", "boleto": "boleto bancário"}.get(
        (pedido.forma_pagamento or "").lower(), pedido.get_forma_pagamento_display() if pedido.forma_pagamento else "",
    )
    partes = ["pagamento pelo site" + (f", por {forma}" if forma else "")]
    vezes = pedido.parcelas or 1
    if (pedido.forma_pagamento or "").lower() == "cartao" and vezes > 1:
        partes.append(f"em {vezes} parcelas")
    if valores["acrescimo_cartao"] > 0:
        partes.append(
            f"total dos itens e da entrega de {dinheiro(valores['total'], prefixo='R$')}, mais "
            f"{dinheiro(valores['acrescimo_cartao'], prefixo='R$')} de acréscimo do cartão: "
            f"valor cobrado de {dinheiro(valores['cobrado'], prefixo='R$')}"
        )
    quando = timezone.localtime(pedido.pago_em).strftime("%d/%m/%Y") if pedido.pago_em else ""
    partes.append("quitado" + (f" em {quando}" if quando else ""))
    return ", ".join(partes)


def _endereco(pedido) -> str:
    if pedido.retirada or not (pedido.rua or pedido.cidade):
        return ""
    rua = ", ".join(p for p in ((pedido.rua or "").strip(), (pedido.numero or "").strip()) if p)
    cidade = "/".join(p for p in ((pedido.cidade or "").strip(), (pedido.estado or "").strip()) if p)
    partes = [rua, (pedido.bairro or "").strip(), cidade]
    if pedido.cep:
        partes.append(f"CEP {pedido.cep}")
    return " – ".join(p for p in partes if p)


def _prazo(pedido) -> dict:
    dias = pedido.prazo_producao_dias
    if dias is None:
        try:
            from . import montagem

            prazo = montagem.prazo_de_entrega(pedido)
            if prazo is not None and prazo.dias_max:
                return contrato.prazo_em_dias(prazo.dias_max, padrao=True)
        except Exception:  # noqa: BLE001 -- sem a lista, o padrão do contrato
            pass
        return contrato.prazo_em_dias(contrato.PRAZO_DE_ENTREGA_PADRAO, padrao=True)
    return contrato.prazo_em_dias(dias)


def retrato_do_pedido(pedido, cpf_cnpj, dados=None) -> dict:
    """O contrato do pedido do site, inteiro, como será assinado."""
    dados = dados or DadosContrato.atual()
    perfil = pedido.cliente
    conta = getattr(perfil, "user", None) if perfil else None
    nome = (
        (getattr(perfil, "nome_completo", "") or "").strip()
        or (conta.get_full_name().strip() if conta else "")
        or (conta.get_username() if conta else "")
        or "Cliente do site"
    )
    valores = valores_do_pedido(pedido)
    agora = timezone.localtime()
    return {
        "modelo": svc.VERSAO_DO_MODELO,
        "origem": "pedido",
        **contrato.partes(
            dados, total=valores["total"], condicao=condicao_de_pagamento(pedido),
            prazo=_prazo(pedido), quando=agora,
        ),
        "emitido_em": agora.isoformat(timespec="seconds"),
        "emitido_em_texto": agora.strftime("%d/%m/%Y às %H:%M"),
        "empresa": svc._empresa(),
        "cliente": {
            "nome": nome,
            "documento": svc.documento_pontuado(chave_documento(cpf_cnpj)),
            "telefone": (getattr(perfil, "telefone", "") or "").strip(),
            "email": (conta.email if conta else "") or "",
            "endereco": _endereco(pedido),
        },
        # A folha lê o número daqui (a mesma chave do contrato do orçamento).
        "orcamento": {
            "id": pedido.pk,
            "numero": numero_do_pedido(pedido),
            "codigo": "",
            "versao": 1,
            "data": svc._data_br(pedido.criacao),
            "aprovado_em": svc._data_br(pedido.pago_em),
            "responsavel": "Loja Lazer & Sport (site)",
        },
        "itens": itens_do_pedido(pedido),
        "valores": {
            "subtotal": svc._dinheiro(pedido.total_bruto or valores["total"]),
            "frete": svc._dinheiro(pedido.valor_frete or 0),
            "desconto": svc._dinheiro(pedido.valor_desconto or 0),
            "acrescimo": svc._dinheiro(0),
            "total": svc._dinheiro(valores["total"]),
            # o cartão, à parte (a decisão do dono: "os dois, discriminados")
            "acrescimo_cartao": svc._dinheiro(valores["acrescimo_cartao"]),
            "cobrado": svc._dinheiro(valores["cobrado"]),
            "pago": svc._dinheiro(valores["cobrado"]),
            "saldo": svc._dinheiro(0),
        },
        "pagamento": {
            "situacao": "Pago",
            "quitado": True,
            "pago_em": svc._data_br(pedido.pago_em),
            "forma": pedido.get_forma_pagamento_display() if pedido.forma_pagamento else "",
            "observacao": "",
        },
        "condicoes": {
            "forma_envio": "Retirada na fábrica" if pedido.retirada else "Entrega no endereço do comprador",
            "observacoes": "",
        },
    }


def gerar_do_pedido(pedido, cpf_cnpj, usuario=None):
    """O contrato do pedido pago, com o CPF/CNPJ que o cliente conferiu. Devolve o documento.

    Já assinado: devolve o assinado (ele é o documento). Esperando
    assinatura com o MESMO CPF/CNPJ: devolve o que espera (tocar duas vezes
    não cria dois). Com outro CPF/CNPJ: o anterior vira "substituído".
    """
    chave = chave_documento(cpf_cnpj)
    if not documento_valido(chave):
        raise ErroDeFormulario("CPF ou CNPJ inválido. Confira os números.", campo="cpf_cnpj")
    with transaction.atomic():
        pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)
        motivo = motivo_para_nao_assinar(pedido)
        if motivo:
            raise ErroDeFormulario(motivo)
        anteriores = list(
            DocumentoAssinatura.objects.select_for_update()
            .filter(pedido=pedido)
            .exclude(situacao=DocumentoAssinatura.Situacao.SUBSTITUIDO)
        )
        for anterior in anteriores:
            if anterior.assinado:
                return anterior
        for anterior in anteriores:
            if chave_documento(((anterior.conteudo or {}).get("cliente") or {}).get("documento", "")) == chave:
                return anterior
        for anterior in anteriores:
            anterior.situacao = DocumentoAssinatura.Situacao.SUBSTITUIDO
            anterior.save(update_fields=["situacao", "atualizado"])
        conteudo = retrato_do_pedido(pedido, chave)
        documento = DocumentoAssinatura.objects.create(
            pedido=pedido,
            conteudo=conteudo,
            hash_conteudo=svc.hash_do_retrato(conteudo),
            criado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
        )
    svc.anotar(documento, "gerado", por="cliente, em Meus pedidos")
    return documento


def anotar_nos_pedidos(pedidos) -> None:
    """Põe em cada pedido de Meus pedidos o que a tela mostra do contrato.

    `pedido.contrato` = None (não pede contrato) ou um dicionário com a
    situação, o que falta e os endereços. UMA consulta para todos os
    documentos; a regra de "pede contrato" usa os itens que a tela já leu.
    """
    from django.urls import reverse

    from . import montagem

    pedidos = list(pedidos)
    documentos = {}
    if pedidos:
        for documento in (
            DocumentoAssinatura.objects
            .filter(pedido__in=[p.pk for p in pedidos])
            .exclude(situacao=DocumentoAssinatura.Situacao.SUBSTITUIDO)
            .defer("assinatura_png", "diario", "conteudo")
            .order_by("id")
        ):
            documentos[documento.pedido_id] = documento
    regras = montagem.Regras.agora() if pedidos else None
    if regras is not None:
        # as categorias dos brinquedos de TODOS os pedidos, numa consulta só
        # (a regra "é brinquedão?" as lê; nunca uma consulta por pedido)
        try:
            regras.carregar_categorias([
                item.item_original
                for pedido in pedidos if pedido.pk not in documentos and pedido.status != "cancelado"
                for item in pedido.itens.all()
                if item.content_type_id and item.object_id and item.content_type.model == "brinquedos"
                and item.item_original is not None
            ])
        except Exception:  # noqa: BLE001 -- sem as categorias em lote, cada pedido lê as dele
            pass
    for pedido in pedidos:
        documento = documentos.get(pedido.pk)
        pedido.contrato = None
        if documento is None and (pedido.status == "cancelado" or not pede_contrato(pedido, regras)):
            continue
        if documento is not None and documento.assinado:
            pedido.contrato = {
                "situacao": "assinado",
                "assinado_em": documento.assinado_em,
                "assinante": documento.assinante_nome,
                "url": reverse("documento_assinado_publico", args=[documento.codigo_publico]),
            }
        elif pedido.status == "cancelado":
            continue
        elif not pedido.pago:
            pedido.contrato = {"situacao": "aguardando_pagamento"}
        else:
            pedido.contrato = {
                "situacao": "assinar",
                "cpf": cpf_sugerido(pedido),
                "url": reverse("assinar_contrato_do_pedido", args=[pedido.pk]),
                "ja_gerado": documento is not None,
            }
