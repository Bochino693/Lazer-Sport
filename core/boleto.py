"""O boleto do checkout (LEIA-ME seção 100).

O dono: "pode colocar" -- o boleto pelo preço do Pix, à vista, vencendo em 3
dias, com o pedido reservado até lá. É a forma mais barata da conta (R$ 3,49
por boleto, contra 0,99% do Pix) e a que muita empresa usa.

Como o Pix, é um `payment` do Mercado Pago (payment_method_id "bolbradesco",
payment_type_id "ticket") preso ao pedido reservado: o webhook e a consulta
do checkout confirmam quando é pago (1 a 3 dias úteis depois) e devolvem os
itens ao carrinho quando ele morre (o Mercado Pago cancela o boleto vencido).
O banco exige o pagador completo: nome, CPF ou CNPJ e o endereço.

Aqui ficam só as regras (validar, montar o pagador, ler a resposta); a
conversa com o Mercado Pago e a reserva moram em core/views.py (gerar_boleto).
"""

import re
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

VENCIMENTO_DIAS = 3
FUSO = ZoneInfo("America/Sao_Paulo")
METODO = "bolbradesco"

UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
    "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}


class DadosInvalidos(ValueError):
    """O que o cliente digitou não serve para o banco registrar o boleto."""


def _texto(valor, limite=120):
    return re.sub(r"\s+", " ", str(valor or "")).strip()[:limite]


def validar(dados):
    """Os dados do formulário, limpos. DadosInvalidos com a frase para o cliente."""
    from sistema_interno.validacoes import chave_documento, documento_valido

    documento = chave_documento(dados.get("documento"))
    if not documento_valido(documento):
        raise DadosInvalidos("Confira o CPF ou o CNPJ: o número não é válido.")

    nome = _texto(dados.get("nome"), 120)
    if len(nome) < 3 or (len(documento) == 11 and len(nome.split()) < 2):
        raise DadosInvalidos(
            "Escreva o nome completo (no CNPJ, a razão social), como vai no boleto."
        )

    cep = re.sub(r"\D", "", str(dados.get("cep") or ""))
    if len(cep) != 8:
        raise DadosInvalidos("O CEP tem 8 números.")

    uf = _texto(dados.get("uf"), 2).upper()
    if uf not in UFS:
        raise DadosInvalidos("Escolha o estado (UF) do endereço.")

    campos = {
        "rua": _texto(dados.get("rua"), 120),
        "numero": _texto(dados.get("numero"), 20),
        "bairro": _texto(dados.get("bairro"), 80),
        "cidade": _texto(dados.get("cidade"), 80),
    }
    faltando = [nome_campo for nome_campo, valor in campos.items() if not valor]
    if faltando:
        rotulos = {"rua": "a rua", "numero": "o número", "bairro": "o bairro", "cidade": "a cidade"}
        raise DadosInvalidos("Falta " + ", ".join(rotulos[c] for c in faltando) + " do endereço.")

    return {"documento": documento, "nome": nome, "cep": cep, "uf": uf, **campos}


def pagador(email, dados):
    """O `payer` que o Mercado Pago pede para registrar o boleto."""
    partes = dados["nome"].split()
    primeiro = partes[0]
    resto = " ".join(partes[1:]) or primeiro
    return {
        "email": email,
        "first_name": primeiro,
        "last_name": resto,
        "identification": {
            "type": "CPF" if len(dados["documento"]) == 11 else "CNPJ",
            "number": dados["documento"],
        },
        "address": {
            "zip_code": dados["cep"],
            "street_name": dados["rua"],
            "street_number": dados["numero"],
            "neighborhood": dados["bairro"],
            "city": dados["cidade"],
            "federal_unit": dados["uf"],
        },
    }


def vencimento(agora=None):
    """Daqui a 3 dias, às 23:59:59 de Brasília (o formato do Mercado Pago)."""
    agora = (agora or timezone.now()).astimezone(FUSO)
    dia = (agora + timedelta(days=VENCIMENTO_DIAS)).replace(
        hour=23, minute=59, second=59, microsecond=0,
    )
    return dia


def vencimento_mp(dia):
    return dia.strftime("%Y-%m-%dT%H:%M:%S.000%z")[:-2] + ":" + dia.strftime("%z")[-2:]


def dados_da_resposta(payment):
    """{url, linha, vencimento} do boleto que o Mercado Pago devolveu."""
    detalhes = payment.get("transaction_details") or {}
    codigo = payment.get("barcode") or {}
    linha = (
        detalhes.get("digitable_line")
        or codigo.get("content")
        or ""
    )
    vence = None
    bruto = payment.get("date_of_expiration")
    if bruto:
        try:
            from django.utils.dateparse import parse_datetime

            vence = parse_datetime(bruto)
        except (TypeError, ValueError):
            vence = None
    return {
        "url": detalhes.get("external_resource_url") or "",
        "linha": str(linha),
        "vencimento": vence,
    }


def e_boleto(payment):
    return (payment or {}).get("payment_type_id") == "ticket"


def preencher(request, carrinho=None):
    """O que já se sabe do cliente para o formulário não começar vazio."""
    from .models import Pedido

    perfil = getattr(request.user, "perfil", None)
    nome = (getattr(perfil, "nome_completo", "") or request.user.get_full_name() or "").strip()
    documento = (getattr(carrinho, "cpf_cnpj", "") or "").strip()
    endereco = {}
    anterior = (
        Pedido.objects.filter(cliente=perfil, cep__isnull=False)
        .exclude(cep="").order_by("-id").first()
        if perfil else None
    )
    if anterior:
        endereco = {
            "cep": anterior.cep or "", "rua": anterior.rua or "", "numero": anterior.numero or "",
            "bairro": anterior.bairro or "", "cidade": anterior.cidade or "",
        }
    return {"nome": nome, "documento": documento, **endereco}
