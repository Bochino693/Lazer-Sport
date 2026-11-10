"""Os nomes do catálogo em maiúsculas e minúsculas: "BOLICHE VIRTUAL" -> "Boliche Virtual".

POR QUE. Metade do catálogo foi cadastrada com o Caps Lock ligado: "AIR GAME
KIDS", "CAIXA DE SOM MULTIMÍDIA KNUP RGB PULSE 2.0", "BOLICHE VIRTUAL" (a
categoria). Ao lado de "Brinquedão Modelo 2" e "Fliperama", os nomes em
caixa-alta gritam no card, quebram o tamanho dos títulos e não combinam com
o resto do site. A migração 0147 passa os nomes que estão TODOS em
maiúsculas (ou todos em minúsculas) por `nome_bonito`; o que já tem as duas
caixas foi escrito de propósito e fica como está.

AS REGRAS (as do português, mais as do catálogo):
  * cada palavra com a primeira letra maiúscula, os acentos como estão;
  * os conectivos em minúsculas -- de, da, do, das, dos, e, com, para,
    por, em, na, no... -- menos quando abrem o nome ("De Volta");
  * as siglas e as unidades ficam como se escrevem: HDMI, RGB, USB, LED,
    TV, VR, PC, 3D, 4K, 110V, 2.0, 32"; números, como estão;
  * as marcas que têm grafia própria: XBOX -> Xbox, PLAYSTATION ->
    PlayStation, WIFI -> Wi-Fi;
  * palavra com hífen ou barra, cada pedaço: ALL-STARS -> All-Stars.

O nome não muda de identidade: nada no site procura um brinquedo pelo nome
exato em maiúsculas (a Arena 3D, o cadastro dos modelos e a busca comparam
sem acento e sem caixa: `core/arena.py`, `_normalizar`), e os endereços
são pelo número (/brinquedo/<id>/, /categoria/<id>/).
"""

from __future__ import annotations

import re

#: As palavras que ficam em minúsculas no meio do nome.
CONECTIVOS = frozenset(
    """
    a à ao aos as às o os e ou
    de da das do dos
    em na nas no nos num numa
    com sem para pra pro por pela pelas pelo pelos
    """.split()
)

#: As siglas que se escrevem em maiúsculas (comparadas sem caixa).
SIGLAS = frozenset(
    """
    hdmi rgb rgbw usb led leds lcd tv vr pc cd dvd hd fhd uhd sd ssd hdd gps
    abs pvc eva mdf pp mp3 mp4 nfc rfid dj vip ps ps2 ps3 ps4 ps5 cpu gpu
    ii iii iv vi vii viii ix xi xii xiii
    """.split()
)

#: As marcas e palavras com grafia própria.
GRAFIAS = {
    "xbox": "Xbox",
    "playstation": "PlayStation",
    "wifi": "Wi-Fi",
    "wi-fi": "Wi-Fi",
    "iphone": "iPhone",
    "ipad": "iPad",
    "youtube": "YouTube",
}

#: As unidades depois de um número ("110V", "20M", "1080P"): como se escrevem.
UNIDADES = {
    "v": "V", "w": "W", "kw": "kW", "a": "A", "mah": "mAh", "hz": "Hz", "khz": "kHz",
    "mm": "mm", "cm": "cm", "m": "m", "km": "km", "m2": "m²", "m²": "m²",
    "g": "g", "kg": "kg", "ml": "ml", "l": "L",
    "gb": "GB", "tb": "TB", "mb": "MB", "k": "K", "d": "D", "p": "p", "x": "x",
    "pol": "pol", "h": "h", "min": "min",
}

_LETRA = re.compile(r"[^\W\d_]", re.UNICODE)
_PEDACOS = re.compile(r"([-/])")
_NUMERO_E_UNIDADE = re.compile(r"^(\d+(?:[.,]\d+)?)([^\W\d_]+\d?)$", re.UNICODE)


def precisa_arrumar(texto: str | None) -> bool:
    """O nome está todo em maiúsculas (ou todo em minúsculas)? Só esse é arrumado."""
    letras = _LETRA.findall(texto or "")
    if len(letras) < 2:
        return False
    tem_maiuscula = any(c.isupper() for c in letras)
    tem_minuscula = any(c.islower() for c in letras)
    return not (tem_maiuscula and tem_minuscula)


def _capitalizar(pedaco: str) -> str:
    """A primeira LETRA maiúscula e o resto minúsculo, pulando o que vem antes ('"', "(")."""
    for i, c in enumerate(pedaco):
        if c.isalpha():
            return pedaco[:i] + c.upper() + pedaco[i + 1:].lower()
    return pedaco


def _miolo(pedaco: str) -> tuple[str, str, str]:
    """Separa a pontuação de fora: '(PAR)' -> ('(', 'PAR', ')')."""
    inicio = re.match(r"^[^\w]*", pedaco, re.UNICODE).group(0)
    fim = re.search(r"[^\w]*$", pedaco[len(inicio):], re.UNICODE).group(0)
    return inicio, pedaco[len(inicio):len(pedaco) - len(fim)], fim


def _palavra(pedaco: str, ponta: bool, vizinhos_numericos: bool) -> str:
    inicio, miolo, fim = _miolo(pedaco)
    if not miolo:
        return pedaco
    baixa = miolo.lower()
    if baixa in GRAFIAS:
        return inicio + GRAFIAS[baixa] + fim
    if baixa in SIGLAS:
        return inicio + miolo.upper() + fim
    # o "x" das medidas: "3 X 3" -> "3 x 3"
    if baixa == "x" and vizinhos_numericos:
        return inicio + "x" + fim
    # número com unidade: "110V", "20M", "1080P", "3X3"
    numero = _NUMERO_E_UNIDADE.match(miolo)
    if numero and numero.group(2).lower() in UNIDADES:
        return inicio + numero.group(1) + UNIDADES[numero.group(2).lower()] + fim
    if re.fullmatch(r"\d+[xX]\d+", miolo):
        return inicio + miolo.lower() + fim
    # letras e números juntos ("F1", "T5", "MK2"): é código de modelo, fica como está
    if any(c.isdigit() for c in miolo):
        return inicio + miolo.upper() + fim
    if baixa in CONECTIVOS and not ponta:
        return inicio + baixa + fim
    return inicio + _capitalizar(miolo) + fim


def nome_bonito(texto: str | None) -> str | None:
    """O nome em maiúsculas e minúsculas, se ele estiver todo numa caixa só.

    >>> nome_bonito("CAIXA DE SOM MULTIMÍDIA KNUP RGB PULSE 2.0")
    'Caixa de Som Multimídia Knup RGB Pulse 2.0'
    >>> nome_bonito("Brinquedão Modelo 2")  # já está bom: fica
    'Brinquedão Modelo 2'
    """
    if texto is None:
        return None
    if not precisa_arrumar(texto):
        return texto
    palavras = texto.split()
    if not palavras:
        return texto
    numerico = [bool(re.fullmatch(r"[\d.,]+\W*", p)) for p in palavras]
    saida = []
    for i, palavra in enumerate(palavras):
        vizinhos = (i > 0 and numerico[i - 1]) and (i + 1 < len(palavras) and numerico[i + 1])
        # "ALL-STARS", "110V/220V": cada pedaço; "WI-FI" é uma grafia inteira
        if palavra.lower().strip("()[]\"'.,:;!?") in GRAFIAS:
            saida.append(_palavra(palavra, i == 0, vizinhos))
            continue
        pedacos = _PEDACOS.split(palavra)
        feitos = []
        for j, pedaco in enumerate(pedacos):
            if pedaco in ("-", "/"):
                feitos.append(pedaco)
                continue
            # a primeira e a última palavra nunca são conectivo ("De Volta", "Tipo A"); depois
            # do hífen, a palavra continua com maiúscula ("All-Stars")
            ponta = (i == 0 and j == 0) or i == len(palavras) - 1 or j > 0
            feitos.append(_palavra(pedaco, ponta, vizinhos))
        saida.append("".join(feitos))
    # os espaços repetidos viram um só
    return " ".join(saida)
