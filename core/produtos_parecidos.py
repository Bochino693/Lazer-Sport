"""Este projeto já existe como produto? O paralelo entre um projeto e a loja.

Um projeto (um brinquedão, um espaço esportivo kids feito sob medida) muitas
vezes é a mesma máquina que já está no catálogo, em outra cor ou outro
tamanho. Aqui o projeto é comparado com cada brinquedo cadastrado:

  - pelas PALAVRAS do título e da descrição (as raras pesam mais: "tobogã"
    diz mais que "brinquedo"), com os sinônimos da casa juntos
    ("parquinho" = "playground", "cama elástica" = "trampolim");
  - pelas MEDIDAS, quando os dois têm (altura, largura e profundidade);

e sai uma nota de 0 a 100 com os motivos ("tobogã, piscina de bolinhas;
medidas parecidas"). É uma sugestão para a equipe confirmar com um clique,
não uma ligação automática: duas máquinas podem ter o mesmo nome e ser
diferentes.
"""

from __future__ import annotations

import math
import re
import unicodedata

PARADAS = set("""
a o as os um uma uns umas de da do das dos e em no na nos nas para pra por com sem ao aos
que se sua seu suas seus mais muito muita ate como ou ja tem ser sao foi este esta esse essa isso
the and for with
cada todo toda todos todas entre sobre sob onde quando qual quais
""".split())

#: Palavras que querem dizer a mesma coisa no catálogo (tudo sem acento).
SINONIMOS = {
    "parquinho": "playground", "brinquedao": "playground", "brinquedoes": "playground", "playgrounds": "playground",
    "trampolins": "trampolim", "elastica": "trampolim", "jump": "trampolim",
    "escorrega": "escorregador", "escorregadores": "escorregador",
    "toboga": "toboga", "tobogas": "toboga",
    "bolinhas": "bolinha", "bolas": "bolinha", "bola": "bolinha",
    "kids": "infantil", "criancas": "infantil", "crianca": "infantil", "infantis": "infantil", "baby": "infantil",
    "esportivo": "esporte", "esportiva": "esporte", "esportes": "esporte",
    "quadras": "quadra", "futebol": "futebol", "basquete": "basquete",
    "torres": "torre", "andares": "andar", "niveis": "andar", "nivel": "andar",
    "redes": "rede", "tubos": "tubo", "labirintos": "labirinto",
    "indoor": "indoor", "interno": "indoor", "interna": "indoor",
}


def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto or "") if not unicodedata.combining(c))


def palavras(texto):
    """As palavras que contam, normalizadas (sem acento, singular simples, sinônimo da casa)."""
    saida = []
    for palavra in re.findall(r"[a-z0-9]+", _sem_acento(texto).lower()):
        if len(palavra) < 3 or palavra in PARADAS or palavra.isdigit():
            continue
        palavra = SINONIMOS.get(palavra, palavra)
        if len(palavra) > 4 and palavra.endswith("s") and not palavra.endswith("ss"):
            palavra = SINONIMOS.get(palavra[:-1], palavra[:-1])
        saida.append(palavra)
    return saida


_MEDIDA = r"(\d+(?:[.,]\d+)?)"


def medidas_no_texto(texto):
    """{"largura", "profundidade", "altura"} (m) escritas na descrição, do que der para ler.

    Lê "6 x 4 x 3,2 m" (largura x profundidade x altura), "6,00 x 4,00 m"
    (largura x profundidade) e "altura: 3,2 m" / "largura de 6 m" soltos.
    Centímetros ("320 cm") viram metros.
    """
    texto = _sem_acento(texto or "").lower()
    saida = {}

    def metros(valor, unidade):
        numero = float(valor.replace(",", "."))
        if unidade and unidade.startswith("cm"):
            numero /= 100
        elif unidade and unidade.startswith("mm"):
            numero /= 1000
        return round(numero, 3) if 0.1 <= numero <= 200 else None

    tres = re.search(_MEDIDA + r"\s*(m|cm|mm)?\s*[x×]\s*" + _MEDIDA + r"\s*(m|cm|mm)?\s*[x×]\s*" + _MEDIDA + r"\s*(m|cm|mm)?", texto)
    dois = re.search(_MEDIDA + r"\s*(m|cm|mm)?\s*[x×]\s*" + _MEDIDA + r"\s*(m|cm|mm)\b", texto)
    if tres:
        unidade = tres.group(6) or tres.group(4) or tres.group(2) or "m"
        for chave, valor in zip(("largura", "profundidade", "altura"), (tres.group(1), tres.group(3), tres.group(5))):
            numero = metros(valor, unidade)
            if numero:
                saida[chave] = numero
    elif dois:
        unidade = dois.group(4) or "m"
        for chave, valor in zip(("largura", "profundidade"), (dois.group(1), dois.group(3))):
            numero = metros(valor, unidade)
            if numero:
                saida[chave] = numero
    for chave, nomes in (("altura", "altura"), ("largura", "largura"), ("profundidade", "profundidade|comprimento")):
        achado = re.search(r"(?:" + nomes + r")\s*(?:de|:)?\s*" + _MEDIDA + r"\s*(m|cm|mm)?\b", texto)
        if achado and chave not in saida:
            numero = metros(achado.group(1), achado.group(2) or "m")
            if numero:
                saida[chave] = numero
    return saida


def _vetor(lista, idf):
    contagem = {}
    for palavra in lista:
        contagem[palavra] = contagem.get(palavra, 0) + 1
    vetor = {p: (1 + math.log(n)) * idf.get(p, 1.0) for p, n in contagem.items()}
    norma = math.sqrt(sum(v * v for v in vetor.values())) or 1.0
    return {p: v / norma for p, v in vetor.items()}


def _parecenca_das_medidas(a, b):
    """0..1: quanto as medidas se parecem (1 = iguais), só com o que os dois têm."""
    pares = []
    for chave in ("altura", "largura", "profundidade"):
        x, y = a.get(chave), b.get(chave)
        if x and y:
            pares.append(min(x, y) / max(x, y))
    if len(pares) < 2:
        return None
    return sum(pares) / len(pares)


def documento_do_brinquedo(brinquedo):
    """As palavras de um brinquedo do catálogo: o nome pesa três vezes."""
    categorias = " ".join(c.nome_categoria for c in brinquedo.categorias_brinquedos.all())
    return palavras(brinquedo.nome_brinquedo) * 3 + palavras(categorias) * 2 + palavras(brinquedo.descricao)


def medidas_do_brinquedo(brinquedo):
    def numero(valor):
        try:
            return float(valor) if valor else None
        except (TypeError, ValueError):
            return None

    return {
        chave: valor for chave, valor in (
            ("altura", numero(brinquedo.altura_m)),
            ("largura", numero(brinquedo.largura_m)),
            ("profundidade", numero(brinquedo.profundidade_m)),
        ) if valor
    }


def parecidos(titulo, descricao, brinquedos, medidas=None, quantos=6):
    """Os brinquedos mais parecidos com o projeto, do mais para o menos.

    Cada um: {"brinquedo", "nota" (0..100), "motivos": [...]}. Fica de fora o
    que não tem nada em comum (nota abaixo de 8).
    """
    brinquedos = list(brinquedos)
    if not brinquedos:
        return []
    documentos = [documento_do_brinquedo(b) for b in brinquedos]
    total = len(documentos)
    frequencia = {}
    for doc in documentos:
        for palavra in set(doc):
            frequencia[palavra] = frequencia.get(palavra, 0) + 1
    idf = {p: math.log((1 + total) / (1 + n)) + 1 for p, n in frequencia.items()}
    projeto = palavras(titulo) * 2 + palavras(descricao)
    vetor_projeto = _vetor(projeto, idf)
    medidas = medidas or medidas_no_texto(f"{titulo} {descricao}")

    saida = []
    for brinquedo, doc in zip(brinquedos, documentos):
        vetor = _vetor(doc, idf)
        comuns = sorted(
            (p for p in vetor_projeto if p in vetor),
            key=lambda p: -(vetor_projeto[p] * vetor[p]),
        )
        texto = sum(vetor_projeto[p] * vetor[p] for p in comuns)
        motivos = []
        if comuns:
            motivos.append(", ".join(comuns[:4]))
        nota = texto
        med = _parecenca_das_medidas(medidas, medidas_do_brinquedo(brinquedo)) if medidas else None
        if med is not None:
            nota = 0.75 * texto + 0.25 * med
            if med >= 0.8:
                motivos.append("medidas parecidas")
        nota = round(min(1.0, nota) * 100)
        if nota >= 8:
            saida.append({"brinquedo": brinquedo, "nota": nota, "motivos": motivos})
    saida.sort(key=lambda item: -item["nota"])
    return saida[:quantos]
