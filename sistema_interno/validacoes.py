"""Validações brasileiras sem consulta externa nem vazamento de cadastro.

CPF e CNPJ são conferidos pelo formato e pelos dígitos verificadores. Isso
detecta erro de digitação e documento inventado, mas não consulta situação
cadastral na Receita Federal. O CNPJ aceita tanto o formato numérico antigo
quanto o alfanumérico adotado em 2026.
"""

from __future__ import annotations

import re


def somente_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def chave_documento(valor: str) -> str:
    """CPF numérico ou CNPJ alfanumérico, sem pontuação e em maiúsculas."""
    return re.sub(r"[^0-9A-Z]", "", (valor or "").upper())[:14]


def _digito_modulo_11(valores, pesos) -> int:
    resto = sum(valor * peso for valor, peso in zip(valores, pesos)) % 11
    return 0 if resto < 2 else 11 - resto


def cpf_valido(valor: str) -> bool:
    numero = somente_digitos(valor)
    if len(numero) != 11 or len(set(numero)) == 1:
        return False
    base = [int(c) for c in numero[:9]]
    primeiro = _digito_modulo_11(base, range(10, 1, -1))
    segundo = _digito_modulo_11(base + [primeiro], range(11, 1, -1))
    return numero[-2:] == f"{primeiro}{segundo}"


def cnpj_valido(valor: str) -> bool:
    """Valida o CNPJ clássico e o alfanumérico da Receita Federal.

    As doze primeiras posições aceitam 0-9/A-Z. O valor de cada caractere
    é seu código ASCII menos 48; os dois dígitos finais continuam numéricos
    e usam módulo 11.
    """
    numero = chave_documento(valor)
    if len(numero) != 14 or not numero[-2:].isdigit():
        return False
    if not re.fullmatch(r"[0-9A-Z]{12}[0-9]{2}", numero):
        return False
    if len(set(numero)) == 1:
        return False

    base = [ord(c) - 48 for c in numero[:12]]
    primeiro = _digito_modulo_11(base, (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    segundo = _digito_modulo_11(
        base + [primeiro], (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    )
    return numero[-2:] == f"{primeiro}{segundo}"


def documento_valido(valor: str) -> bool:
    chave = chave_documento(valor)
    if len(chave) == 11 and chave.isdigit():
        return cpf_valido(chave)
    if len(chave) == 14:
        return cnpj_valido(chave)
    return False


def tipo_documento(valor: str) -> str:
    chave = chave_documento(valor)
    if len(chave) == 11 and chave.isdigit():
        return "CPF"
    if len(chave) == 14:
        return "CNPJ"
    return "documento"


def telefone_valido(valor: str) -> bool:
    numero = somente_digitos(valor)
    if numero.startswith("55") and len(numero) in (12, 13):
        numero = numero[2:]
    return len(numero) in (10, 11) and numero[:2] != "00"


def telefone_celular(valor: str) -> bool:
    numero = somente_digitos(valor)
    if numero.startswith("55") and len(numero) == 13:
        numero = numero[2:]
    return len(numero) == 11 and numero[2] == "9"


def mascarar_documento(valor: str) -> str:
    """Oculta o miolo do documento no comprovante público."""
    chave = chave_documento(valor)
    if len(chave) == 11:
        return f"{chave[:3]}.***.***-{chave[-2:]}"
    if len(chave) == 14:
        return f"{chave[:2]}.***.***/****-{chave[-2:]}"
    return "Documento protegido"
