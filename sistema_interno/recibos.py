"""O recibo de pagamento: quando emitir, por quanto, e como conferir.

O QUE FALTAVA. O painel registrava o dinheiro (`valor_pago`, o selo
"Pago" na lista) e parava ali. O cliente que precisa prestar contas --
buffet, condomínio, prefeitura, empresa que vai lançar a despesa --
pedia "manda o recibo", e alguém da equipe escrevia um à mão num modelo
de Word, com o número do orçamento copiado de cabeça. Documento sem
número conferível, sem valor por extenso e sem carimbo de quem emitiu.

O DINHEIRO JÁ ESTAVA GRAVADO; O QUE FALTAVA ERA O PAPEL. Por isso este
módulo não recebe valor nenhum: ele lê o que o financeiro registrou e
transforma em documento. Não existe caminho para emitir recibo de um
valor que o sistema não recebeu -- se o papel e a planilha pudessem
divergir, o papel deixaria de valer como prova.

A PARCELA, E NÃO O SALDO. Cada recibo cobre o que entrou DESDE o recibo
anterior. Uma proposta paga em duas vezes vira dois recibos que somam a
venda; se cada um trouxesse o acumulado, os dois papéis somariam mais do
que o cliente pagou -- e é a soma dos recibos que a contabilidade lança.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from core.email_utils import cnpj_empresa, nome_empresa
from core.formatos import por_extenso

from .models import Orcamento, ReciboOrcamento
from .validacoes import mascarar_documento


class ReciboIndisponivel(Exception):
    """Não há o que documentar -- a view transforma isto em recado."""


def _dinheiro(valor) -> str:
    return f"{Decimal(valor or 0):.2f}"


def valor_ja_documentado(orcamento) -> Decimal:
    """Quanto dos recebimentos desta proposta já virou recibo.

    Soma em Python, e não com `aggregate`: a lista de orçamentos já traz
    os recibos por prefetch, e um `Sum` aqui faria uma consulta por linha
    da tela -- que é como a página de orçamentos já estourou o tempo do
    servidor uma vez.
    """
    return sum(
        (recibo.valor for recibo in orcamento.recibos.all()),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))


def valor_a_documentar(orcamento) -> Decimal:
    """Quanto entrou e ainda não tem recibo. Zero quer dizer "em dia"."""
    if not orcamento.pode_emitir_recibo:
        return Decimal("0.00")
    return max(
        (orcamento.valor_pago or Decimal("0.00")) - valor_ja_documentado(orcamento),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))


def conteudo_canonico(recibo) -> dict:
    """O que o recibo afirma, sem PK, token nem outro identificador interno.

    É esta forma -- e não o HTML da página -- que entra no hash. O texto
    do documento pode ganhar uma linha nova amanhã sem invalidar os
    recibos já entregues; o que não pode mudar é o valor, quem pagou,
    por que pagou e quando.
    """
    return {
        "empresa": nome_empresa(),
        "empresa_cnpj": cnpj_empresa(),
        "orcamento": recibo.orcamento.numero_documento,
        "sequencia": recibo.sequencia,
        "pagador": recibo.pagador_nome,
        "pagador_documento": recibo.pagador_documento,
        "referencia": recibo.referencia,
        "forma_pagamento": recibo.forma_pagamento,
        "observacao": recibo.observacao,
        "valor": _dinheiro(recibo.valor),
        "valor_acumulado": _dinheiro(recibo.valor_acumulado),
        "total_documento": _dinheiro(recibo.total_documento),
        "quitacao": recibo.quitacao,
        "emitido_em": recibo.emitido_em.isoformat() if recibo.emitido_em else "",
    }


def hash_recibo(recibo) -> str:
    serializado = json.dumps(
        conteudo_canonico(recibo),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serializado).hexdigest()


def _documento_do_pagador(orcamento) -> str:
    """O CPF/CNPJ de quem pagou, mascarado, quando o sistema o conhece.

    Vem do aceite eletrônico (foi ali que o cliente digitou o próprio
    documento ao aprovar) ou do cadastro. Mascarado porque o recibo é um
    documento que circula por e-mail e por WhatsApp: o miolo do CPF não
    precisa viajar junto para o papel identificar quem pagou.
    """
    aceite = getattr(orcamento, "aceite_eletronico", None)
    if aceite and aceite.assinante_documento:
        return mascarar_documento(aceite.assinante_documento)
    cliente = orcamento.cliente if orcamento.cliente_id else None
    documento = getattr(cliente, "documento", "") if cliente else ""
    return mascarar_documento(documento) if documento else ""


def _referencia(orcamento) -> str:
    """A frase do "referente a" -- a parte que um recibo à mão erra.

    Um recibo precisa dizer POR QUE o dinheiro entrou. Sem isso o papel
    prova um pagamento sem prova de quê, e é justamente o que a
    prestação de contas do cliente vai perguntar.
    """
    itens = list(orcamento.itens.all())
    if not itens:
        return f"Orçamento nº {orcamento.numero_documento}"
    primeiro = itens[0].descricao.strip()
    if len(itens) > 1:
        resto = len(itens) - 1
        primeiro = f"{primeiro} e mais {resto} {'itens' if resto > 1 else 'item'}"
    return f"{primeiro} — orçamento nº {orcamento.numero_documento}"[:240]


def emitir_recibo(orcamento, usuario=None) -> ReciboOrcamento:
    """Cria o recibo do que entrou e ainda não tinha documento.

    Chamar duas vezes seguidas NÃO gera dois papéis: sem dinheiro novo
    desde o último recibo não há o que documentar, e a segunda chamada
    recusa. Foi de propósito -- dois recibos do mesmo pagamento, cada um
    com seu número, é a forma mais silenciosa de duplicar receita na
    contabilidade de quem recebe.

    Quem chama abre a transação: entre medir o que falta documentar e
    gravar o recibo não pode caber outro registro de pagamento.
    """
    if orcamento.status != Orcamento.Status.APROVADO:
        raise ReciboIndisponivel(
            "O recibo sai depois da aprovação: antes dela não há pagamento "
            "registrado para documentar."
        )

    valor = valor_a_documentar(orcamento)
    if valor <= 0:
        if not orcamento.pode_emitir_recibo:
            raise ReciboIndisponivel(
                "Nenhum valor recebido nesta proposta. Registre o pagamento "
                "primeiro; o recibo sai do que entrou."
            )
        raise ReciboIndisponivel(
            "Todo o valor recebido já tem recibo. Registre o novo pagamento "
            "para emitir o recibo da próxima parcela."
        )

    acumulado = (valor_ja_documentado(orcamento) + valor).quantize(Decimal("0.01"))
    sequencia = orcamento.recibos.count() + 1
    nome = "Sistema"
    if getattr(usuario, "is_authenticated", False):
        nome = usuario.get_full_name() or usuario.get_username()

    recibo = ReciboOrcamento(
        orcamento=orcamento,
        sequencia=sequencia,
        valor=valor,
        valor_acumulado=acumulado,
        total_documento=orcamento.total,
        # Quitação é a conta do dinheiro, não o carimbo do painel: o
        # recibo que fecha a venda diz "quitação" mesmo que a situação de
        # pagamento ainda não tenha sido salva como "pago".
        quitacao=acumulado >= orcamento.total,
        pagador_nome=orcamento.destinatario[:120],
        pagador_documento=_documento_do_pagador(orcamento),
        referencia=_referencia(orcamento),
        forma_pagamento=(orcamento.forma_pagamento or "")[:120],
        observacao=(orcamento.observacao_pagamento or "")[:240],
        emitido_por=usuario if getattr(usuario, "is_authenticated", False) else None,
        emitido_por_nome=nome[:150],
    )
    recibo.save()
    # O hash só existe depois de gravar: `emitido_em` faz parte do que ele
    # protege. Como o modelo recusa a segunda gravação, o carimbo entra
    # por UPDATE direto -- é a única escrita que o recibo aceita depois de
    # nascer, e ela não muda nenhum valor do documento.
    recibo.conteudo_hash = hash_recibo(recibo)
    ReciboOrcamento.objects.filter(pk=recibo.pk).update(
        conteudo_hash=recibo.conteudo_hash
    )
    return recibo


def conferir(recibo) -> bool:
    """O documento continua sendo o que foi emitido?

    Usado pela página do recibo para carimbar "conferido". Um recibo com
    hash diferente do conteúdo é um recibo mexido no banco, e o cliente
    tem o direito de ver isso na tela em vez de descobrir na auditoria.
    """
    return bool(recibo.conteudo_hash) and recibo.conteudo_hash == hash_recibo(recibo)


def valor_escrito(recibo) -> str:
    """O valor do recibo por extenso, como todo recibo escreve."""
    return por_extenso(recibo.valor)
