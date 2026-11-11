"""Os estados (e os países) do mapa da home, coloridos pelo nível de pedidos.

O Brasil vai pelos estados; fora dele, cada país inteiro.

O QUE CONTA: SÓ O QUE TEM ALFINETE.
  Cada cliente publicado no mapa conta as propostas aprovadas dele (pelo
  menos 1: está no mapa porque comprou), no estado ou país onde o
  ALFINETE dele está -- pela coordenada, contra a mesma malha que o mapa
  desenha. Proposta ou compra de quem não está no mapa não pinta nada:
  antes o Paraná saía colorido por um pedido de alguém que não aparecia
  no mapa, e o mapa contava um alfinete que não estava lá.

O SITE MOSTRA A FAIXA, NUNCA O NÚMERO. O número exato de pedidos por
estado é informação comercial; a página pública só recebe o nível (1 a 5)
e o rótulo da faixa ("3 a 5 pedidos"). A conta inteira roda ao montar o
cache da home, e não a cada visita.
"""

from __future__ import annotations

import json
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path

#: As faixas da legenda, da mais clara à mais escura. O último limite é
#: aberto ("21 ou mais").
FAIXAS = ((1, 2), (3, 5), (6, 10), (11, 20), (21, None))

UFS = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal",
    "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão",
    "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco",
    "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima",
    "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe",
    "TO": "Tocantins",
}


def _sem_acento(texto: str) -> str:
    normal = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in normal if not unicodedata.combining(c)).casefold().strip()


_POR_NOME = {_sem_acento(nome): uf for uf, nome in UFS.items()}


def uf_de(valor) -> str:
    """'SP', 'sp', 'São Paulo', 'Sao Paulo ' -> 'SP'; o que não for estado -> ''."""
    texto = (valor or "").strip()
    if not texto:
        return ""
    if texto.upper() in UFS:
        return texto.upper()
    return _POR_NOME.get(_sem_acento(texto), "")


def nivel_de(quantidade: int) -> int:
    """0 sem pedido; 1 a len(FAIXAS) pela faixa."""
    if quantidade <= 0:
        return 0
    for indice, (_minimo, maximo) in enumerate(FAIXAS, start=1):
        if maximo is None or quantidade <= maximo:
            return indice
    return len(FAIXAS)


def rotulo_da_faixa(minimo: int, maximo) -> str:
    if maximo is None:
        return f"{minimo} ou mais pedidos"
    if minimo == maximo:
        return f"{minimo} pedido" + ("" if minimo == 1 else "s")
    return f"{minimo} a {maximo} pedidos"


#: Os jeitos de escrever "Brasil" no endereço: esses vão pelos estados.
_BRASIL = {"brasil", "brazil", "br", "bra", "republica federativa do brasil"}

#: Abreviações comuns que o nome do país no mapa não traz.
_APELIDOS_DE_PAIS = {
    "eua": "estados unidos", "usa": "estados unidos", "us": "estados unidos",
    "estados unidos da america": "estados unidos", "uk": "reino unido",
    "inglaterra": "reino unido",
}


def pais_de(valor) -> str:
    """O país do endereço, normalizado (sem acento, minúsculo); '' para o
    Brasil ou vazio -- o Brasil vai pelos estados."""
    texto = _sem_acento(valor or "")
    if not texto or texto in _BRASIL:
        return ""
    return _APELIDOS_DE_PAIS.get(texto, texto)


# ---------------------------------------------------------------------
# Em que estado (ou país) o ALFINETE está -- pela coordenada dele
# ---------------------------------------------------------------------
# A cor tem de bater com o alfinete: se o endereço diz "SP" mas o ponto
# cai no Paraná, quem pinta é o Paraná, onde o alfinete aparece. Por isso
# a região sai da coordenada, testada contra a mesma malha que o mapa
# desenha (core/static/site/dados/), e o texto do endereço só desempata
# um ponto que caia fora de tudo (no mar, rente à costa).
_DADOS = Path(__file__).resolve().parent / "static" / "site" / "dados"


def _carregar_malha(nome):
    geo = json.loads((_DADOS / nome).read_text(encoding="utf-8"))
    regioes = []
    for feature in geo["features"]:
        poligonos = feature["geometry"]["coordinates"]
        xs = [x for poligono in poligonos for anel in poligono for x, _ in anel]
        ys = [y for poligono in poligonos for anel in poligono for _, y in anel]
        regioes.append((feature["id"], (min(xs), min(ys), max(xs), max(ys)), poligonos))
    return regioes


@lru_cache(maxsize=None)
def _malha_estados():
    return _carregar_malha("estados-br.json")


@lru_cache(maxsize=None)
def _malha_paises():
    return _carregar_malha("paises.json")


def _dentro_do_anel(x, y, anel):
    dentro = False
    j = len(anel) - 1
    for i in range(len(anel)):
        xi, yi = anel[i]
        xj, yj = anel[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi:
            dentro = not dentro
        j = i
    return dentro


def _dentro(x, y, poligonos):
    for poligono in poligonos:
        if _dentro_do_anel(x, y, poligono[0]) and not any(
            _dentro_do_anel(x, y, buraco) for buraco in poligono[1:]
        ):
            return True
    return False


def _distancia(x, y, poligonos):
    return min(
        ((x - px) ** 2 + (y - py) ** 2) ** 0.5
        for poligono in poligonos for anel in poligono for px, py in anel
    )


def _dentro_de_algum(malha, x, y):
    for chave, (x0, y0, x1, y1), poligonos in malha:
        if x0 <= x <= x1 and y0 <= y <= y1 and _dentro(x, y, poligonos):
            return chave
    return ""


def _mais_perto(malha, x, y, folga):
    perto = [
        (_distancia(x, y, poligonos), chave)
        for chave, (x0, y0, x1, y1), poligonos in malha
        if x0 - folga <= x <= x1 + folga and y0 - folga <= y <= y1 + folga
    ]
    perto = [item for item in perto if item[0] <= folga]
    return min(perto)[1] if perto else ""


def regiao_do_ponto(lat, lng, estado="", pais=""):
    """("estado", "SP"), ("pais", "PY") ou ("", "") para o alfinete.

    Pela coordenada. Ponto fora de toda a malha (no mar rente à costa, numa
    ilha que a malha simplificou -- Fernando de Noronha): vale o estado do
    endereço se ele estiver por perto; senão, o estado mais próximo.
    """
    try:
        x, y = float(lng), float(lat)
    except (TypeError, ValueError):
        x = y = None
    uf_do_endereco = "" if pais_de(pais) else uf_de(estado)
    if x is not None:
        uf = _dentro_de_algum(_malha_estados(), x, y)
        if uf:
            return "estado", uf
        iso = _dentro_de_algum(_malha_paises(), x, y)
        if iso:
            return "pais", iso
        if uf_do_endereco:
            regiao = next((p for chave, _caixa, p in _malha_estados() if chave == uf_do_endereco), None)
            if regiao and _distancia(x, y, regiao) <= 4:
                return "estado", uf_do_endereco
        uf = _mais_perto(_malha_estados(), x, y, folga=0.35)
        if uf:
            return "estado", uf
        iso = _mais_perto(_malha_paises(), x, y, folga=0.6)
        if iso:
            return "pais", iso
    if uf_do_endereco:
        return "estado", uf_do_endereco
    return "", ""


def _contar(clientes_no_mapa):
    """(por estado, por país): SÓ o que tem alfinete no mapa.

    Cada cliente publicado conta as propostas aprovadas dele (pelo menos 1:
    ele está no mapa porque comprou), no estado ou país onde o alfinete
    dele está. Proposta ou compra de quem não está no mapa não pinta nada:
    um estado colorido sem alfinete nenhum seria um mapa mentindo.

    `clientes_no_mapa`: (cliente_id, tipo, chave), com tipo/chave de
    `regiao_do_ponto`.
    """
    from sistema_interno.models import Orcamento

    clientes = [tuple(c) for c in clientes_no_mapa]
    ids = {c[0] for c in clientes if c[0] is not None}
    aprovadas = Counter(
        Orcamento.objects
        .filter(status=Orcamento.Status.APROVADO, cliente_id__in=ids)
        .values_list("cliente_id", flat=True)
    ) if ids else Counter()

    por_uf: Counter = Counter()
    por_pais: Counter = Counter()
    for cliente_id, tipo, chave in clientes:
        if not chave:
            continue
        peso = max(1, aprovadas.get(cliente_id, 0))
        (por_uf if tipo == "estado" else por_pais)[chave] += peso
    return por_uf, por_pais


def pedidos_por_estado(clientes_no_mapa=()) -> Counter:
    """Quantos pedidos de brinquedos cada estado (UF) tem no mapa."""
    return _contar(clientes_no_mapa)[0]


def pedidos_por_pais(clientes_no_mapa=()) -> Counter:
    """O mesmo para os países fora do Brasil (chave: a sigla ISO)."""
    return _contar(clientes_no_mapa)[1]


def dados_do_mapa(clientes_no_mapa=()) -> dict:
    """O que a página recebe: só o nível de cada estado e país e a legenda."""
    por_uf, por_pais = _contar(clientes_no_mapa)
    return {
        "niveis": {uf: nivel_de(n) for uf, n in sorted(por_uf.items()) if n > 0},
        "paises": {nome: nivel_de(n) for nome, n in sorted(por_pais.items()) if n > 0},
        "nomes": UFS,
        "faixas": [
            {"nivel": i, "rotulo": rotulo_da_faixa(minimo, maximo)}
            for i, (minimo, maximo) in enumerate(FAIXAS, start=1)
        ],
    }
