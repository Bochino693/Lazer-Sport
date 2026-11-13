"""Transportadoras recomendadas: os estados, os números e os atalhos.

POR QUE ISTO EXISTE. O frete saiu do site: o cliente retira na fábrica ou
contrata a transportadora por conta própria. Máquina de fliperama, mesa
de air hockey, pista de boliche e playground não cabem num envio comum,
e a pergunta que chega ao comercial passa a ser "quem leva isto até
Recife?". A resposta precisa estar a um toque de quem atende: escolher o
estado, ver quem atende, chamar no WhatsApp com a cotação já escrita.

O QUE MORA AQUI. Só regra pura, sem banco: a lista dos 27 estados, a
leitura e a escrita da lista de UFs que a transportadora atende, o
telefone em dígitos e o mesmo telefone formatado para gente, e os links
de WhatsApp, ligação, e-mail e Instagram. O modelo (`models.Transportadora`)
e a tela (`views_transportadoras.py`) usam estas funções -- e os testes
também, sem precisar de banco.

POR QUE A LISTA DE UFs É TEXTO E NÃO UMA TABELA. Os estados são um
conjunto fechado (27 siglas, as mesmas desde 1988) e ninguém cadastra
estado novo. Uma tabela de UFs com relação muitos-para-muitos traria
uma migração de dados só para criar 27 linhas que nunca mudam, uma
junção em toda consulta e um formulário mais pesado -- para guardar o
que cabe em "BA,PE,SE". O texto é validado na entrada (só sigla
conhecida, sem repetir, na ordem do mapa), e "atende o Brasil inteiro"
é um campo próprio (`atende_todo_brasil`), e não 27 siglas marcadas à
mão: uma transportadora nacional não deixa de aparecer em Roraima porque
alguém esqueceu um quadradinho.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import quote, urlencode

from django.core.exceptions import ValidationError


# ----------------------------------------------------------------------
# OS ESTADOS
# ----------------------------------------------------------------------
#: (sigla, nome, região) na ordem do mapa: de norte a sul, e em ordem
#: alfabética dentro da região. É a ordem dos botões na tela e a ordem em
#: que a lista de UFs é gravada.
UFS = (
    ("AC", "Acre", "Norte"),
    ("AM", "Amazonas", "Norte"),
    ("AP", "Amapá", "Norte"),
    ("PA", "Pará", "Norte"),
    ("RO", "Rondônia", "Norte"),
    ("RR", "Roraima", "Norte"),
    ("TO", "Tocantins", "Norte"),
    ("AL", "Alagoas", "Nordeste"),
    ("BA", "Bahia", "Nordeste"),
    ("CE", "Ceará", "Nordeste"),
    ("MA", "Maranhão", "Nordeste"),
    ("PB", "Paraíba", "Nordeste"),
    ("PE", "Pernambuco", "Nordeste"),
    ("PI", "Piauí", "Nordeste"),
    ("RN", "Rio Grande do Norte", "Nordeste"),
    ("SE", "Sergipe", "Nordeste"),
    ("DF", "Distrito Federal", "Centro-Oeste"),
    ("GO", "Goiás", "Centro-Oeste"),
    ("MS", "Mato Grosso do Sul", "Centro-Oeste"),
    ("MT", "Mato Grosso", "Centro-Oeste"),
    ("ES", "Espírito Santo", "Sudeste"),
    ("MG", "Minas Gerais", "Sudeste"),
    ("RJ", "Rio de Janeiro", "Sudeste"),
    ("SP", "São Paulo", "Sudeste"),
    ("PR", "Paraná", "Sul"),
    ("RS", "Rio Grande do Sul", "Sul"),
    ("SC", "Santa Catarina", "Sul"),
)

SIGLAS = tuple(sigla for sigla, _nome, _regiao in UFS)
NOME_DA_UF = {sigla: nome for sigla, nome, _regiao in UFS}
REGIAO_DA_UF = {sigla: regiao for sigla, _nome, regiao in UFS}
POSICAO_DA_UF = {sigla: posicao for posicao, sigla in enumerate(SIGLAS)}
REGIOES = ("Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul")

#: As escolhas do campo de UF da sede, em ordem alfabética do nome --
#: é como a pessoa procura numa lista suspensa.
def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


UF_CHOICES = tuple(
    (sigla, f"{sigla} · {nome}")
    for sigla, nome, _regiao in sorted(UFS, key=lambda uf: _sem_acento(uf[1]))
)


def uf_valida(valor) -> str:
    """A sigla em maiúsculas, ou "" quando não é um estado."""
    sigla = (valor or "").strip().upper()
    return sigla if sigla in NOME_DA_UF else ""


def ler_ufs(valor) -> list[str]:
    """"ba, PE,se" -> ["BA", "PE", "SE"]. Sigla desconhecida levanta.

    Aceita texto (separado por vírgula, espaço ou ponto e vírgula) ou
    uma lista -- o formulário manda as caixas marcadas como lista.
    Devolve sem repetição e na ordem do mapa, para que a mesma escolha
    seja sempre gravada do mesmo jeito.
    """
    if not valor:
        return []
    if isinstance(valor, str):
        partes = re.split(r"[\s,;/]+", valor)
    else:
        partes = list(valor)
    vistas = set()
    desconhecidas = []
    for parte in partes:
        sigla = (parte or "").strip().upper()
        if not sigla:
            continue
        if sigla not in NOME_DA_UF:
            desconhecidas.append(sigla)
            continue
        vistas.add(sigla)
    if desconhecidas:
        raise ValidationError(
            "Estado desconhecido: %(siglas)s. Use as siglas das UFs (SP, PE, AM...).",
            params={"siglas": ", ".join(desconhecidas)},
            code="uf_desconhecida",
        )
    return sorted(vistas, key=POSICAO_DA_UF.__getitem__)


def gravar_ufs(valor) -> str:
    """A forma gravada no banco: "BA,PE,SE"."""
    return ",".join(ler_ufs(valor))


def validar_lista_de_ufs(valor):
    """Validador do campo: só siglas conhecidas, já na forma gravada."""
    if not valor:
        return
    if gravar_ufs(valor) != valor:
        raise ValidationError(
            "Grave as UFs em maiúsculas, separadas por vírgula, sem repetir "
            "e na ordem do mapa (ex.: BA,PE,SE).",
            code="ufs_fora_do_formato",
        )


def filtro_da_uf(sigla: str) -> str:
    """Expressão regular que acha a sigla dentro da lista gravada.

    "^|," antes e ",|$" depois: a busca por "PA" não pode casar com o
    "AP" de "AM,AP" nem com nada no meio de outra sigla. Funciona igual
    no SQLite dos testes e no PostgreSQL do servidor.
    """
    return rf"(^|,){re.escape(sigla)}(,|$)"


# ----------------------------------------------------------------------
# TELEFONE: DÍGITOS NO BANCO, FORMATADO NA TELA
# ----------------------------------------------------------------------
def so_digitos(valor) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def _sem_ddi(digitos: str) -> str:
    """Tira o 55 de quem colou o número com o país (+55 11 ...)."""
    if len(digitos) in (12, 13) and digitos.startswith("55"):
        return digitos[2:]
    return digitos


def _eh_numero_nacional(digitos: str) -> bool:
    """0800, 0300, 0500 e 0900: discagem nacional, sem DDD."""
    return len(digitos) == 11 and digitos.startswith("0")


def _eh_numero_unico(digitos: str) -> bool:
    """3003-xxxx, 4003-xxxx, 4004-xxxx...: o número único das capitais."""
    return len(digitos) == 8 and digitos[0] in "34"


def normalizar_telefone(valor) -> str:
    """O que a pessoa digitou ("(11) 2188-9000", "+55 11 ...") em dígitos."""
    return _sem_ddi(so_digitos(valor))


def validar_telefone(valor):
    """Só dígitos: DDD + número, 0800/0300 ou o número único de 8 dígitos."""
    if not valor:
        return
    if not valor.isdigit():
        raise ValidationError("Telefone: grave só os dígitos.", code="telefone_digitos")
    if _eh_numero_nacional(valor) or _eh_numero_unico(valor):
        return
    if len(valor) in (10, 11) and valor[0] != "0":
        return
    raise ValidationError(
        "Telefone incompleto: use DDD + número (10 ou 11 dígitos), um 0800/"
        "0300 ou um número único como 4003-3277.",
        code="telefone_invalido",
    )


def validar_whatsapp(valor):
    """WhatsApp é sempre DDD + número: 0800 e 4003 sozinhos não têm conta."""
    if not valor:
        return
    if not valor.isdigit():
        raise ValidationError("WhatsApp: grave só os dígitos.", code="whatsapp_digitos")
    if len(valor) not in (10, 11) or valor[0] == "0":
        raise ValidationError(
            "WhatsApp: use DDD + número, com 10 ou 11 dígitos (ex.: 11 91366-2652).",
            code="whatsapp_invalido",
        )


def formatar_telefone(valor) -> str:
    """Dígitos -> como se lê em voz alta.

        08007753333 -> 0800 775 3333
        40033277    -> 4003-3277
        1121889000  -> (11) 2188-9000
        11991004606 -> (11) 99100-4606
    """
    digitos = normalizar_telefone(valor)
    if not digitos:
        return ""
    if _eh_numero_nacional(digitos):
        return f"{digitos[:4]} {digitos[4:7]} {digitos[7:]}"
    if _eh_numero_unico(digitos):
        return f"{digitos[:4]}-{digitos[4:]}"
    if len(digitos) == 10:
        return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
    if len(digitos) == 11:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
    return digitos


def link_telefone(valor) -> str:
    """O `tel:` que o celular disca.

    Com DDD vai com o +55 (funciona de qualquer operadora e até de chip
    de fora). 0800 e o número único de 8 dígitos vão como estão: são
    discagem nacional e não aceitam o código do país.
    """
    digitos = normalizar_telefone(valor)
    if not digitos:
        return ""
    if _eh_numero_nacional(digitos) or _eh_numero_unico(digitos):
        return f"tel:{digitos}"
    return f"tel:+55{digitos}"


def numero_whatsapp(valor) -> str:
    """"(11) 91366-2652" -> "5511913662652"; "" se não serve para WhatsApp."""
    digitos = normalizar_telefone(valor)
    if len(digitos) not in (10, 11) or digitos[0] == "0":
        return ""
    return "55" + digitos


def link_whatsapp(valor, mensagem: str = "") -> str:
    numero = numero_whatsapp(valor)
    if not numero:
        return ""
    if not mensagem:
        return f"https://wa.me/{numero}"
    return f"https://wa.me/{numero}?text={quote(mensagem, safe='')}"


# ----------------------------------------------------------------------
# INSTAGRAM, E-MAIL E A MENSAGEM DA COTAÇÃO
# ----------------------------------------------------------------------
_PERFIL = re.compile(r"^[A-Za-z0-9._]{1,30}$")


def normalizar_instagram(valor) -> str:
    """"@braspress", "instagram.com/braspress/" e o link inteiro -> "braspress"."""
    perfil = (valor or "").strip()
    perfil = re.sub(r"^(https?://)?(www\.)?instagram\.com/", "", perfil, flags=re.I)
    perfil = perfil.split("?")[0].strip("/").lstrip("@").strip()
    return perfil


def validar_instagram(valor):
    if valor and not _PERFIL.match(valor):
        raise ValidationError(
            "Instagram: só o nome do perfil (letras, números, ponto e _), sem o @.",
            code="instagram_invalido",
        )


def link_instagram(perfil) -> str:
    perfil = normalizar_instagram(perfil)
    return f"https://instagram.com/{perfil}" if perfil else ""


def iniciais(nome) -> str:
    """"Expresso São Miguel" -> "ES", "Braspress" -> "BR": o selo sem logotipo."""
    palavras = [p for p in re.split(r"[\s&/.()-]+", nome or "") if p[:1].isalnum()]
    if len(palavras) == 1:
        return palavras[0][:2].upper()
    return "".join(p[0] for p in palavras[:2]).upper() or "?"


def termos_de_busca(busca) -> list[str]:
    """As palavras procuradas, sem acento e sem a última letra das longas.

    "aéreo" acha "carga aérea" e "peças" acha "peça": a busca é de
    quem atende o telefone, e masculino, feminino e plural não podem
    esconder a transportadora certa. O mesmo corte é feito no navegador
    (transportadoras.js), para a busca instantânea dar o mesmo resultado.
    """
    termos = []
    for palavra in sem_acento(busca).split():
        termos.append(palavra[:-1] if len(palavra) > 4 else palavra)
    return termos


def sem_acento(texto) -> str:
    return _sem_acento(str(texto or "")).casefold()


#: A fábrica é a origem de toda cotação (Zona Norte de São Paulo).
ORIGEM = "São Paulo/SP"


def mensagem_cotacao(uf: str = "") -> str:
    """O texto que já vai escrito no WhatsApp e no e-mail.

    Peso e volume ficam em branco de propósito: são da máquina que o
    cliente comprou, e quem manda a mensagem completa antes de enviar.
    A cidade também -- o estado vem da escolha na tela.
    """
    sigla = uf_valida(uf)
    destino = f"___/{sigla}" if sigla else "___"
    return (
        "Olá! Somos da Lazer & Sport (fábrica de brinquedos em SP). "
        f"Gostaria de uma cotação de frete de {ORIGEM} para {destino} "
        "de uma máquina de aproximadamente ___ kg / ___ m³."
    )


def assunto_cotacao(uf: str = "") -> str:
    sigla = uf_valida(uf)
    destino = f" para {NOME_DA_UF[sigla]} ({sigla})" if sigla else ""
    return f"Cotação de frete: {ORIGEM}{destino} - Lazer & Sport"


def link_email(email, uf: str = "") -> str:
    if not email:
        return ""
    consulta = urlencode(
        {"subject": assunto_cotacao(uf), "body": mensagem_cotacao(uf)},
        quote_via=quote,
    )
    return f"mailto:{email}?{consulta}"
