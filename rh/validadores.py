"""As conferências da ficha do colaborador, sem consulta externa.

CPF e PIS/NIS são conferidos pelos dígitos verificadores: pega erro de
digitação e número inventado, mas não diz se o documento está regular na
Receita ou na Caixa. O CPF reaproveita a conta de `sistema_interno.validacoes`
(a mesma do cadastro de clientes); o PIS (que também é o NIS, o NIT e o
PASEP: é um número só) tem a sua aqui.

Tudo que é número é guardado SÓ COM OS DÍGITOS. A máscara é coisa da tela.
"""

from __future__ import annotations

import re
from datetime import date

from django.core.exceptions import ValidationError

from sistema_interno.validacoes import cpf_valido, somente_digitos, telefone_valido

#: As 27 unidades da federação.
UFS = (
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
)

#: Idade mínima por vínculo. CLT, PJ e temporário: maior de idade (a
#: fábrica não contrata aprendiz por aqui). Estágio: 16 anos, o mínimo da
#: Lei 11.788/2008 para o estágio do ensino médio.
IDADE_MINIMA = {"clt": 18, "pj": 18, "temporario": 18, "estagio": 16}

#: Ninguém tem 100 anos na linha de produção: data assim é digitação errada.
IDADE_MAXIMA = 100


def pis_valido(valor: str) -> bool:
    """PIS/PASEP/NIS/NIT: 11 dígitos, o último é o verificador (módulo 11)."""
    numero = somente_digitos(valor)
    if len(numero) != 11 or len(set(numero)) == 1:
        return False
    pesos = (3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    resto = sum(int(d) * p for d, p in zip(numero[:10], pesos)) % 11
    digito = 0 if resto < 2 else 11 - resto
    return int(numero[10]) == digito


def validar_cpf(valor):
    if not cpf_valido(valor):
        raise ValidationError("CPF inválido: confira os 11 números (os dois últimos são o dígito verificador).", code="cpf")


def validar_pis(valor):
    if valor and not pis_valido(valor):
        raise ValidationError("PIS/NIS inválido: confira os 11 números (o último é o dígito verificador).", code="pis")


def validar_cep(valor):
    """Guardado só com os dígitos: exatamente 8, nem um a mais."""
    if valor and not re.fullmatch(r"\d{8}", str(valor)):
        raise ValidationError("O CEP tem 8 números.", code="cep")


def validar_uf(valor):
    if valor and valor.upper() not in UFS:
        raise ValidationError("UF inválida: use a sigla do estado (SP, MG, RJ...).", code="uf")


def validar_telefone(valor):
    if valor and not telefone_valido(valor):
        raise ValidationError("Telefone inválido: DDD + número (10 ou 11 números).", code="telefone")


def idade_em(nascimento: date, dia: date) -> int:
    anos = dia.year - nascimento.year
    if (dia.month, dia.day) < (nascimento.month, nascimento.day):
        anos -= 1
    return anos


def formatar_cpf(valor: str) -> str:
    n = somente_digitos(valor)
    if len(n) != 11:
        return valor or ""
    return f"{n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}"


def mascarar_cpf(valor: str) -> str:
    n = somente_digitos(valor)
    if len(n) != 11:
        return ""
    return f"{n[:3]}.***.***-{n[9:]}"


def formatar_pis(valor: str) -> str:
    n = somente_digitos(valor)
    if len(n) != 11:
        return valor or ""
    return f"{n[:3]}.{n[3:8]}.{n[8:10]}-{n[10]}"


def formatar_cep(valor: str) -> str:
    n = somente_digitos(valor)
    return f"{n[:5]}-{n[5:]}" if len(n) == 8 else (valor or "")


def formatar_telefone(valor: str) -> str:
    n = somente_digitos(valor)
    if len(n) == 11:
        return f"({n[:2]}) {n[2:7]}-{n[7:]}"
    if len(n) == 10:
        return f"({n[:2]}) {n[2:6]}-{n[6:]}"
    return valor or ""
