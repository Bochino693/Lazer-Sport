"""A descrição de um projeto (ou evento) organizada para a ficha do site.

A equipe escreve a descrição livre no painel, do jeito que vem na cabeça:

    Playground indoor compacto projetado para ...
    Principais atrações
    🧗 Área com obstáculos suspensos ...
    🟡 Elementos rotativos ...
    Características
    Estrutura tubular resistente
    Revestimento acolchoado e seguro
    Indicado para buffets infantis, brinquedotecas, escolas e áreas kids
    💡 Este playground cria um ambiente lúdico ...

No site isso saía num parágrafo só, com os emojis no meio da frase (e, no
Windows, os emojis mais novos viravam quadradinhos). Aqui o texto vira:

    {"lead": [parágrafos de abertura],
     "secoes": [{"titulo", "icone", "itens": [...], "etiquetas": bool}],
     "fecho": [parágrafos finais]}

Funciona com as quebras de linha e também sem elas (texto colado numa linha
só): os emojis marcam o começo de cada item e os títulos conhecidos
("Principais atrações", "Características", "Indicado para"...) abrem seção.
Os emojis saem do texto: cada item ganha o ícone da seção, igual em todas.
"""

import re

#: Os títulos que abrem uma seção, e o ícone (Font Awesome) de cada uma.
TITULOS = (
    ("Principais atrações", "fa-star"),
    ("Atrações", "fa-star"),
    ("Destaques", "fa-star"),
    ("Diferenciais", "fa-trophy"),
    ("Características", "fa-list-check"),
    ("Especificações", "fa-ruler-combined"),
    ("Medidas", "fa-ruler-combined"),
    ("Dimensões", "fa-ruler-combined"),
    ("Benefícios", "fa-heart"),
    ("Itens inclusos", "fa-box-open"),
    ("Inclui", "fa-box-open"),
    ("Indicado para", "fa-location-dot"),
    ("Ideal para", "fa-location-dot"),
    ("Brinquedos usados", "fa-gamepad"),
)
#: Seções cujo conteúdo é uma lista de lugares/públicos: viram etiquetas.
EM_ETIQUETAS = ("Indicado para", "Ideal para")

_EMOJI = re.compile(
    "(?:[\U0001F000-\U0001FAFF☀-➿⬀-⯿⌀-⏿■-◿←-⇿⤀-⥿㊗㊙]"
    "[️‍\U0001F3FB-\U0001F3FF⃣]*)+"
)
_MARCADOR = re.compile(r"^\s*(?:[•·▪●◦\-–—*✓✔]\s+|\d{1,2}[.)]\s+)")
_TITULO = re.compile(
    r"(?<![\w])(" + "|".join(re.escape(t) for t, _ in sorted(TITULOS, key=lambda par: -len(par[0]))) + r")\s*:?",
    re.IGNORECASE,
)
#: Item ou frase? Acima disto, com ponto final, é parágrafo.
_FRASE = 140


def _icone(titulo):
    for nome, icone in TITULOS:
        if nome.lower() == titulo.lower():
            return icone
    return "fa-circle-check"


def _limpo(texto):
    texto = _EMOJI.sub(" ", texto)
    texto = re.sub(r"\s+", " ", texto).strip(" \t-–—:;,")
    return texto


def _quebrar_sem_pontuacao(texto):
    """Uma lista colada numa linha só ("Estrutura tubular resistente Revestimento
    acolchoado..."): quebra onde uma palavra minúscula é seguida de uma Maiúscula."""
    if ". " in texto or len(texto) < 30:
        return [texto]
    partes = re.split(r"(?<=[a-zà-ÿ0-9)])\s+(?=[A-ZÀ-ÖØ-Þ][a-zà-ÿ])", texto)
    return [p for p in partes if p] if len(partes) > 1 else [texto]


def _etiquetas(texto):
    """"buffets infantis, brinquedotecas, escolas e áreas kids" -> uma etiqueta cada."""
    texto = re.sub(r"^(?:para\s+)", "", texto.strip(), flags=re.IGNORECASE)
    partes = re.split(r",\s*|\s+e\s+(?=[^,]+$)", texto.rstrip("."))
    return [p.strip() for p in partes if p.strip()]


def estruturar(texto):
    texto = (texto or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    vazio = {"lead": [], "secoes": [], "fecho": []}
    if not texto:
        return vazio

    # cada título conhecido vira uma linha própria (só quando é título mesmo: com
    # maiúscula, no começo da linha ou com dois-pontos -- "ideal para" no meio de
    # uma frase continua frase); cada emoji começa um item
    def _titulo(m):
        antes = texto[:m.start()]
        comeco = not antes.strip() or antes.rstrip(" \t").endswith("\n")
        if m.group(1)[0].isupper() or comeco or m.group(0).rstrip().endswith(":"):
            return "\n\x00T" + m.group(1) + "\n"
        return m.group(0)
    marcado = _TITULO.sub(_titulo, texto)
    marcado = _EMOJI.sub(lambda m: "\n\x00I", marcado)
    linhas = []
    for bruta in marcado.split("\n"):
        if not bruta.strip():
            continue
        if bruta.startswith("\x00T"):
            linhas.append(("titulo", bruta[2:].strip()))
            continue
        item = bruta.startswith("\x00I")
        conteudo = bruta.replace("\x00I", " ")
        if _MARCADOR.match(conteudo):
            item = True
            conteudo = _MARCADOR.sub("", conteudo)
        conteudo = _limpo(conteudo)
        if conteudo:
            linhas.append(("item" if item else "texto", conteudo))

    resultado = {"lead": [], "secoes": [], "fecho": []}
    atual = None
    for tipo, conteudo in linhas:
        if tipo == "titulo":
            nome = next((t for t, _ in TITULOS if t.lower() == conteudo.lower()), conteudo)
            atual = {"titulo": nome, "icone": _icone(nome), "itens": [], "etiquetas": nome in EM_ETIQUETAS}
            resultado["secoes"].append(atual)
            continue
        longo = len(conteudo) > _FRASE and conteudo.rstrip().endswith((".", "!"))
        if atual is None:
            if tipo == "item":
                # itens antes de qualquer título: uma seção "Destaques"
                atual = {"titulo": "Destaques", "icone": "fa-star", "itens": [], "etiquetas": False}
                resultado["secoes"].append(atual)
                atual["itens"].append(conteudo)
            else:
                resultado["lead"].append(conteudo)
            continue
        if longo:
            # a frase de fechamento ("Este playground cria um ambiente...")
            resultado["fecho"].append(conteudo)
            continue
        if atual["etiquetas"]:
            atual["itens"].extend(_etiquetas(conteudo))
        elif tipo == "texto":
            atual["itens"].extend(_quebrar_sem_pontuacao(conteudo))
        else:
            atual["itens"].append(conteudo)

    resultado["secoes"] = [s for s in resultado["secoes"] if s["itens"]]
    resultado["lead"] = [p for bloco in resultado["lead"] for p in _paragrafos(bloco)]
    return resultado


def _paragrafos(texto, tamanho=280):
    """Um bloco comprido vira parágrafos de duas ou três frases (lê melhor na ficha)."""
    if len(texto) <= tamanho:
        return [texto]
    frases = re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Þ])", texto)
    blocos, atual = [], ""
    for frase in frases:
        if atual and len(atual) + len(frase) > tamanho:
            blocos.append(atual)
            atual = frase
        else:
            atual = (atual + " " + frase).strip()
    if atual:
        blocos.append(atual)
    return blocos


def resumo(texto, limite=170):
    """A primeira frase (ou o começo) da descrição, sem emojis: para os cartões."""
    ficha = estruturar(texto)
    base = " ".join(ficha["lead"]) or " ".join(ficha["fecho"]) or ""
    if not base and ficha["secoes"]:
        base = ficha["secoes"][0]["itens"][0]
    if len(base) <= limite:
        return base
    corte = base[:limite].rsplit(" ", 1)[0]
    return corte.rstrip(",;:") + "…"
