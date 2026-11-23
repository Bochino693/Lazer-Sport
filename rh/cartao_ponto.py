"""O cartão de ponto do relógio (REP-P), lido do PDF -- aqui mesmo, sem serviço de fora.

O PEDIDO (LEIA-ME-V10, seção 125): "esta é a folha de ponto, adapte para
enviar o arquivo pdf e auto preencher os campos e informações do
colaborador em questão no pdf".

O FORMATO. O "Cartão de Ponto" que o sistema do relógio (Control iD, REP-P)
exporta em PDF (feito pelo wkhtmltopdf). Por página:

  * o cabeçalho: "Página 01 de 01", "Emitido em dd/mm/aaaa às hh:mm", o
    período "DE dd/mm/aaaa ATÉ dd/mm/aaaa", e os rótulos NOME DA EMPRESA,
    CNPJ DA EMPRESA, INSCRIÇÃO ESTADUAL DA EMPRESA, NOME DO FUNCIONÁRIO, CPF
    DO FUNCIONÁRIO, PIS DO FUNCIONÁRIO, DATA DE ADMISSÃO DO FUNCIONÁRIO e
    NÚMERO DE MATRÍCULA, cada um seguido do valor;
  * o quadro "HORÁRIO DE TRABALHO": SEG a DOM com ENT. 1, SAÍ. 1, ENT. 2,
    SAÍ. 2 (vazio no dia de folga);
  * a tabela dos dias: "dd/mm/aaaa - QUI", o PREVISTO ("08:00-12:00
    13:00-18:00"), as marcações (HH:MM, às vezes com a marca do relógio ao
    lado -- (I) incluído, (P) pré-assinalado, (M) coletor mobile/web, (C)
    coletor iDFace/iDFlex) ou as palavras "Folga", "Falta" (por marcação
    ou no dia inteiro), "Feriado"; e as colunas TOTAL NORMAIS, TOTAL
    NOTURNO, DIA FALTA, FALTA E ATRASO, ABONO, EXTRA 50%D, EXTRA 50%N,
    EXTRA DIURNA, EXTRA NOTURNA, BANCO TOTAL e BANCO SALDO -- ESPARSAS (a
    célula vazia não aparece no texto);
  * a linha TOTAIS, a legenda e as "Alterações" ("Feriado em dd/mm/aaaa").

Um arquivo pode ter várias páginas e várias pessoas ("Página 01 de NN").

COMO SE LÊ. Pela POSIÇÃO de cada pedaço de texto na página (o pypdf entrega
x e y de cada um), e não pela ordem: como as colunas de total são
esparsas, "00:53" só se sabe se é noturno ou extra pela coluna em que
está. O cabeçalho da tabela diz onde cada coluna começa (as células são
alinhadas à esquerda); cada valor vai para a coluna cujo começo está
logo à esquerda dele. Se o PDF não der as posições (outro gerador), a
mesma conta roda sobre o texto "em layout" do pypdf, com a coluna de
caracteres no lugar do x.

PDF ESCANEADO (imagem, sem texto) não tem o que ler: a leitura recusa
com uma frase clara.

Este módulo só LÊ: não grava nada. Quem casa com a ficha e importa é
`importacao_ponto.py`. O arquivo enviado é dado não confiável: ele já
passou pela conferência de `arquivos.conferir` (PDF de verdade, sem
script, sem senha), e aqui só se extrai texto.
"""

from __future__ import annotations

import io
import logging
import re
import statistics
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, time

DIAS_DA_SEMANA = {"SEG": 1, "TER": 2, "QUA": 3, "QUI": 4, "SEX": 5, "SAB": 6, "DOM": 7}

#: Palavras que o relógio escreve no lugar da hora.
PALAVRAS = {
    "FOLGA": "folga",
    "FALTA": "falta",
    "FERIADO": "feriado",
    "FERIAS": "ferias",
    "ATESTADO": "atestado",
    "ABONO": "abono",
    "ABONADO": "abono",
    "AFASTAMENTO": "afastamento",
    "AFASTADO": "afastamento",
    "LICENCA": "afastamento",
    "COMPENSADO": "folga",
    "COMPENSACAO": "folga",
    "DSR": "folga",
    "FOLGA COMPENSATORIA": "folga",
}

#: Rótulos do cabeçalho (sem acento, maiúsculos) -> chave.
ROTULOS = (
    ("NOME DA EMPRESA", "empresa_nome"),
    ("RAZAO SOCIAL", "empresa_nome"),
    ("CNPJ DA EMPRESA", "empresa_cnpj"),
    ("CPF DA EMPRESA", "empresa_cnpj"),
    ("INSCRICAO ESTADUAL DA EMPRESA", "empresa_ie"),
    ("INSCRICAO ESTADUAL", "empresa_ie"),
    ("NOME DO FUNCIONARIO", "nome"),
    ("NOME DO COLABORADOR", "nome"),
    ("CPF DO FUNCIONARIO", "cpf"),
    ("CPF DO COLABORADOR", "cpf"),
    ("PIS DO FUNCIONARIO", "pis"),
    ("PIS/PASEP DO FUNCIONARIO", "pis"),
    ("PIS DO COLABORADOR", "pis"),
    ("DATA DE ADMISSAO DO FUNCIONARIO", "admissao"),
    ("DATA DE ADMISSAO", "admissao"),
    ("NUMERO DE MATRICULA", "matricula"),
    ("MATRICULA", "matricula"),
)

#: O que cada coluna de total quer dizer (o nome do cabeçalho, junto).
COLUNAS_FIXAS = {
    "DIA": "dia",
    "DATA": "dia",
    "PREVISTO": "previsto",
    "HORARIO PREVISTO": "previsto",
    "TOTAL NORMAIS": "normais",
    "NORMAIS": "normais",
    "HORAS NORMAIS": "normais",
    "TOTAL NOTURNO": "noturno",
    "NOTURNO": "noturno",
    "ADICIONAL NOTURNO": "noturno",
    "DIA FALTA": "dia_falta",
    "FALTA E ATRASO": "falta_atraso",
    "FALTAS E ATRASOS": "falta_atraso",
    "ATRASO": "falta_atraso",
    "ABONO": "abono",
    "EXTRA DIURNA": "extra_diurna",
    "EXTRA NOTURNA": "extra_noturna",
    "BANCO TOTAL": "banco_total",
    "BANCO SALDO": "banco_saldo",
}

#: Os nomes que a tela usa para os totais do cartão.
ROTULOS_DOS_TOTAIS = {
    "normais": "Horas normais",
    "noturno": "Noturno",
    "dia_falta": "Dias de falta",
    "falta_atraso": "Falta e atraso",
    "abono": "Abono",
    "extra_diurna": "Extra diurna",
    "extra_noturna": "Extra noturna",
    "banco_total": "Banco (total)",
    "banco_saldo": "Banco (saldo)",
}


class CartaoIlegivel(Exception):
    """O PDF não é um cartão de ponto que dê para ler. A frase vai para a tela."""

    def __init__(self, mensagem, titulo="Cartão de ponto não reconhecido"):
        super().__init__(mensagem)
        self.titulo = titulo


# ======================================================================
# O QUE SAI DA LEITURA
# ======================================================================
@dataclass
class Marca:
    coluna: str            # "ent1", "sai1", "ent2"...
    hora: time | None = None
    marcador: str = ""     # I, P, M, C (ou vazio)
    palavra: str = ""      # "falta", "folga", "feriado"... quando não é hora

    def para_json(self):
        dados = {"coluna": self.coluna}
        if self.hora is not None:
            dados["hora"] = f"{self.hora:%H:%M}"
            if self.marcador:
                dados["marcador"] = self.marcador
        if self.palavra:
            dados["palavra"] = self.palavra
        return dados


@dataclass
class DiaLido:
    data: date
    semana: str = ""
    previsto: list = field(default_factory=list)   # [(time, time), ...]
    marcas: list = field(default_factory=list)     # [Marca], na ordem das colunas
    ocorrencia: str = ""                           # o dia inteiro: folga, falta, feriado...
    totais: dict = field(default_factory=dict)     # minutos (dia_falta: contagem)
    outros: list = field(default_factory=list)     # texto que não coube em coluna nenhuma

    @property
    def horas(self):
        return [m for m in self.marcas if m.hora is not None]

    @property
    def marcas_faltando(self):
        """Quantas marcações o relógio deu como "Falta" num dia trabalhado."""
        if not self.horas:
            return 0
        return sum(1 for m in self.marcas if m.palavra == "falta")

    def para_json(self):
        dados = {
            "data": self.data.isoformat(),
            "semana": self.semana,
            "previsto": [[f"{a:%H:%M}", f"{b:%H:%M}"] for a, b in self.previsto],
            "marcas": [m.para_json() for m in self.marcas],
            "totais": self.totais,
        }
        if self.ocorrencia:
            dados["ocorrencia"] = self.ocorrencia
        if self.outros:
            dados["outros"] = self.outros
        return dados


@dataclass
class CartaoLido:
    empresa_nome: str = ""
    empresa_cnpj: str = ""
    empresa_ie: str = ""
    nome: str = ""
    cpf: str = ""
    pis: str = ""
    admissao: date | None = None
    matricula: str = ""
    inicio: date | None = None
    fim: date | None = None
    emitido_em: datetime | None = None
    paginas: list = field(default_factory=list)
    horario: dict = field(default_factory=dict)   # {1: [(time, time), ...], ...}
    colunas: list = field(default_factory=list)
    dias: list = field(default_factory=list)
    totais: dict = field(default_factory=dict)
    alteracoes: list = field(default_factory=list)
    feriados: list = field(default_factory=list)  # datas citadas como feriado nas alterações
    avisos: list = field(default_factory=list)

    @property
    def chave(self):
        return (self.cpf or self.nome, self.inicio, self.fim)

    def soma_dos_dias(self) -> dict:
        soma = {}
        for dia in self.dias:
            for chave, valor in dia.totais.items():
                soma[chave] = soma.get(chave, 0) + valor
        return soma

    def para_json(self):
        return {
            "empresa": {"nome": self.empresa_nome, "cnpj": self.empresa_cnpj, "ie": self.empresa_ie},
            "funcionario": {
                "nome": self.nome, "cpf": self.cpf, "pis": self.pis,
                "admissao": self.admissao.isoformat() if self.admissao else "",
                "matricula": self.matricula,
            },
            "periodo": {
                "inicio": self.inicio.isoformat() if self.inicio else "",
                "fim": self.fim.isoformat() if self.fim else "",
            },
            "emitido_em": self.emitido_em.isoformat(timespec="minutes") if self.emitido_em else "",
            "paginas": self.paginas,
            "horario": {
                str(dia): [[f"{a:%H:%M}", f"{b:%H:%M}"] for a, b in pares]
                for dia, pares in sorted(self.horario.items())
            },
            "colunas": self.colunas,
            "dias": [d.para_json() for d in self.dias],
            "totais": self.totais,
            "alteracoes": self.alteracoes,
            "feriados": [f.isoformat() for f in self.feriados],
            "avisos": self.avisos,
        }


@dataclass
class Leitura:
    cartoes: list
    paginas: int
    avisos: list = field(default_factory=list)


# ======================================================================
# TEXTO
# ======================================================================
def normalizar(texto: str) -> str:
    """Maiúsculo, sem acento, espaços simples: "Saí. 1" -> "SAI. 1"."""
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().upper()


def digitos(texto: str) -> str:
    return re.sub(r"\D", "", str(texto or ""))


def _data(texto):
    achado = re.search(r"(\d{2})/(\d{2})/(\d{4})", str(texto or ""))
    if not achado:
        return None
    try:
        return date(int(achado.group(3)), int(achado.group(2)), int(achado.group(1)))
    except ValueError:
        return None


RE_HORA = re.compile(r"^(\d{1,2}):(\d{2})\s*(?:\(\s*([A-Za-z])\s*\))?\s*\*?$")
RE_MARCA_ANTES = re.compile(r"^\(\s*([A-Za-z])\s*\)\s*(\d{1,2}):(\d{2})$")
RE_DURACAO = re.compile(r"^(-)?\s*(\d{1,4}):(\d{2})$")
RE_DIA = re.compile(r"^(\d{2}/\d{2}/\d{4})(?:\s*-\s*([A-Za-zÁ-ú]{3}))?")
RE_PERIODO = re.compile(r"DE (\d{2}/\d{2}/\d{4}) ATE (\d{2}/\d{2}/\d{4})")
RE_EMITIDO = re.compile(r"EMITIDO EM (\d{2}/\d{2}/\d{4})(?: AS (\d{1,2}):(\d{2}))?")
RE_PAGINA = re.compile(r"PAGINA (\d+) DE (\d+)")
RE_PREVISTO = re.compile(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})")
RE_TOKEN_DE_MARCA = re.compile(r"\d{1,2}:\d{2}(?:\s*\(\s*[A-Za-z]\s*\))?\*?|[A-Za-zÀ-ú]+")


def _hora(h, m):
    h, m = int(h), int(m)
    if h > 23 or m > 59:
        return None
    return time(h, m)


def ler_marca(texto: str, coluna: str) -> Marca | None:
    bruto = str(texto or "").strip()
    if not bruto:
        return None
    achado = RE_HORA.match(bruto)
    if achado:
        hora = _hora(achado.group(1), achado.group(2))
        if hora is not None:
            return Marca(coluna=coluna, hora=hora, marcador=(achado.group(3) or "").upper())
    achado = RE_MARCA_ANTES.match(bruto)
    if achado:
        hora = _hora(achado.group(2), achado.group(3))
        if hora is not None:
            return Marca(coluna=coluna, hora=hora, marcador=achado.group(1).upper())
    palavra = PALAVRAS.get(normalizar(bruto))
    if palavra:
        return Marca(coluna=coluna, palavra=palavra)
    return Marca(coluna=coluna, palavra="outro:" + bruto[:40])


def ler_duracao(texto: str):
    achado = RE_DURACAO.match(str(texto or "").strip())
    if not achado:
        return None
    minutos = int(achado.group(2)) * 60 + int(achado.group(3))
    return -minutos if achado.group(1) else minutos


def hm(minutos) -> str:
    """Como o cartão escreve: 143:20, -01:30."""
    if minutos is None:
        return ""
    sinal = "-" if minutos < 0 else ""
    minutos = abs(int(minutos))
    return f"{sinal}{minutos // 60:02d}:{minutos % 60:02d}"


# ======================================================================
# OS PEDAÇOS DE TEXTO DA PÁGINA, COM POSIÇÃO
# ======================================================================
@dataclass
class Pedaco:
    x: float
    y: float
    texto: str

    @property
    def norm(self):
        return normalizar(self.texto)


def _pedacos_por_posicao(pagina) -> list[Pedaco]:
    pedacos = []

    def visitar(texto, cm, tm, fonte, tamanho):
        for linha in str(texto or "").split("\n"):
            if not linha.strip():
                continue
            # posição do texto na página: a matriz do texto (tm) dentro da
            # matriz corrente (cm)
            a, b, c, d, e, f = cm
            x = tm[4] * a + tm[5] * c + e
            y = tm[4] * b + tm[5] * d + f
            pedacos.append(Pedaco(x=round(x, 2), y=round(y, 2), texto=linha.strip()))

    pagina.extract_text(visitor_text=visitar)
    return pedacos


def _pedacos_do_layout(pagina) -> list[Pedaco]:
    """Sem posição (outro gerador de PDF): o texto em layout, x = coluna do caractere."""
    texto = pagina.extract_text(extraction_mode="layout") or ""
    pedacos = []
    for numero, linha in enumerate(texto.splitlines()):
        for achado in re.finditer(r"\S+(?: \S+)*", linha):
            pedacos.append(Pedaco(x=float(achado.start()), y=float(-numero * 10), texto=achado.group(0)))
    return pedacos


# ======================================================================
# UMA PÁGINA
# ======================================================================
@dataclass
class _Pagina:
    numero: int
    cabecalho: dict
    horario: dict
    colunas: list          # [(x, chave, nome)]
    dias: list
    totais: dict
    alteracoes: list
    feriados: list
    total_paginas: int = 0
    avisos: list = field(default_factory=list)


def _mesma_linha(a: float, b: float, tolerancia: float) -> bool:
    return abs(a - b) <= tolerancia


def _cabecalho(pedacos: list[Pedaco], limite_x: float, tolerancia: float) -> dict:
    """Os rótulos "NOME DO FUNCIONÁRIO: ..." e o valor de cada um."""
    dados = {}
    ordenados = sorted((p for p in pedacos if p.x < limite_x), key=lambda p: (-p.y, p.x))
    rotulos_norm = sorted(ROTULOS, key=lambda r: -len(r[0]))
    for i, pedaco in enumerate(ordenados):
        texto = pedaco.norm
        for rotulo, chave in rotulos_norm:
            if not texto.startswith(rotulo):
                continue
            resto = texto[len(rotulo):]
            if resto and not resto.lstrip().startswith(":") and resto[0] not in " :":
                continue
            valor_original = pedaco.texto
            dois_pontos = valor_original.find(":")
            valor = valor_original[dois_pontos + 1:].strip() if dois_pontos >= 0 else ""
            if not valor:
                # o valor é o pedaço seguinte da mesma linha (que não é outro rótulo)
                for seguinte in ordenados[i + 1:]:
                    if not _mesma_linha(seguinte.y, pedaco.y, tolerancia):
                        break
                    if seguinte.x <= pedaco.x:
                        continue
                    if any(seguinte.norm.startswith(r) for r, _ in ROTULOS):
                        break
                    valor = seguinte.texto.strip()
                    break
            if chave not in dados:
                dados[chave] = valor
            break
    return dados


def _horario(pedacos: list[Pedaco], tolerancia: float):
    """O quadro "HORÁRIO DE TRABALHO": {1: [(08:00, 12:00), (13:00, 18:00)], ...}."""
    titulo = next((p for p in pedacos if "HORARIO DE TRABALHO" in p.norm), None)
    if titulo is None:
        return {}, None
    colunas = sorted(
        (p for p in pedacos
         if re.fullmatch(r"(ENT|SAI)\.? ?\d", p.norm) and p.y < titulo.y and titulo.y - p.y < tolerancia * 6
         and p.x >= titulo.x - 40),
        key=lambda p: p.x,
    )
    if not colunas:
        return {}, titulo.x
    y_colunas = colunas[0].y
    colunas = [c for c in colunas if _mesma_linha(c.y, y_colunas, tolerancia)]
    primeira_x = colunas[0].x
    dias = [
        p for p in pedacos
        if p.norm in DIAS_DA_SEMANA and p.y < y_colunas and p.x < primeira_x and p.x >= titulo.x - 80
    ]
    horario = {}
    for dia in dias:
        celulas = {}
        for p in pedacos:
            if p is dia or not _mesma_linha(p.y, dia.y, tolerancia) or p.x < primeira_x - 4:
                continue
            indice = max((i for i, c in enumerate(colunas) if c.x <= p.x + 4), default=None)
            if indice is None:
                continue
            achado = re.match(r"^(\d{1,2}):(\d{2})$", p.texto.strip())
            if achado:
                celulas[indice] = _hora(achado.group(1), achado.group(2))
        horas = [celulas[i] for i in sorted(celulas) if celulas[i] is not None]
        pares = [(horas[i], horas[i + 1]) for i in range(0, len(horas) - 1, 2)]
        horario[DIAS_DA_SEMANA[dia.norm]] = pares
    return horario, min(titulo.x, min((d.x for d in dias), default=titulo.x)) - 6


def _chave_da_coluna(nome: str) -> str:
    nome = normalizar(nome)
    achado = re.fullmatch(r"(ENT|SAI)\.? ?(\d)", nome)
    if achado:
        return f"{achado.group(1).lower()}{achado.group(2)}"
    if nome in COLUNAS_FIXAS:
        return COLUNAS_FIXAS[nome]
    achado = re.fullmatch(r"EXTRA (\d{2,3}) ?%? ?(D|N)", nome)
    if achado:
        return f"extra_{achado.group(1)}{achado.group(2).lower()}"
    return re.sub(r"[^a-z0-9]+", "_", nome.lower()).strip("_") or "coluna"


def _colunas_da_tabela(pedacos: list[Pedaco], tolerancia: float, linha: float):
    """O cabeçalho da tabela (uma ou duas linhas), pelo x de cada coluna."""
    ancora = None
    for p in pedacos:
        if p.norm in ("PREVISTO", "HORARIO PREVISTO"):
            ancora = p
            break
    if ancora is None:
        ancora = next((p for p in pedacos if re.fullmatch(r"ENT\.? ?1", p.norm)
                       and any(q.norm in ("DIA", "DATA") and _mesma_linha(q.y, p.y, tolerancia) for q in pedacos)),
                      None)
    if ancora is None:
        return [], None
    y_base = ancora.y
    faixa = [p for p in pedacos if y_base - tolerancia <= p.y <= y_base + linha * 1.25]
    grupos = []
    for p in sorted(faixa, key=lambda p: p.x):
        if grupos and abs(grupos[-1][0] - p.x) <= max(1.0, tolerancia * 0.8):
            grupos[-1][1].append(p)
        else:
            grupos.append([p.x, [p]])
    colunas = []
    for x, membros in grupos:
        nome = " ".join(m.texto.strip() for m in sorted(membros, key=lambda m: -m.y))
        colunas.append((x, _chave_da_coluna(nome), normalizar(nome)))
    chaves = {c[1] for c in colunas}
    if "dia" not in chaves or "ent1" not in chaves:
        return [], None
    return colunas, y_base


def _coluna_de(x: float, colunas: list, folga: float):
    escolhida = None
    for cx, chave, _ in colunas:
        if cx <= x + folga:
            escolhida = chave
        else:
            break
    return escolhida


def _ler_pagina(pagina, numero: int, *, por_layout=False) -> _Pagina | None:
    pedacos = _pedacos_do_layout(pagina) if por_layout else _pedacos_por_posicao(pagina)
    if not pedacos:
        return None
    # a distância entre linhas da tabela: medida nas datas dos dias
    datas = sorted({p.y for p in pedacos if RE_DIA.match(p.texto.strip())}, reverse=True)
    diferencas = [round(datas[i] - datas[i + 1], 2) for i in range(len(datas) - 1) if datas[i] - datas[i + 1] > 0.5]
    linha = statistics.median(diferencas) if diferencas else 10.0
    tolerancia = max(0.5, min(3.0, linha * 0.3))
    folga = 0.6 if por_layout else 3.0

    textos = " | ".join(p.norm for p in pedacos)
    if "CARTAO" not in textos and "PONTO" not in textos:
        return None

    horario, limite_horario = _horario(pedacos, tolerancia)
    limite_cabecalho = limite_horario if limite_horario is not None else float("inf")
    colunas, y_tabela = _colunas_da_tabela(pedacos, tolerancia, linha)
    acima_da_tabela = [p for p in pedacos if y_tabela is None or p.y > y_tabela + linha * 1.25]
    cabecalho = _cabecalho(acima_da_tabela, limite_cabecalho, tolerancia)
    for p in pedacos:
        n = p.norm
        if "periodo" not in cabecalho:
            achado = RE_PERIODO.search(n)
            if achado:
                cabecalho["periodo"] = (_data(achado.group(1)), _data(achado.group(2)))
        if "emitido" not in cabecalho:
            achado = RE_EMITIDO.search(n)
            if achado:
                dia = _data(achado.group(1))
                hora = _hora(achado.group(2), achado.group(3)) if achado.group(2) else None
                if dia:
                    cabecalho["emitido"] = datetime.combine(dia, hora or time(0, 0))
        if "pagina" not in cabecalho:
            achado = RE_PAGINA.search(n)
            if achado:
                cabecalho["pagina"] = (int(achado.group(1)), int(achado.group(2)))

    resultado = _Pagina(numero=numero, cabecalho=cabecalho, horario=horario, colunas=colunas,
                        dias=[], totais={}, alteracoes=[], feriados=[],
                        total_paginas=cabecalho.get("pagina", (0, 0))[1])
    if not colunas:
        return resultado if cabecalho.get("nome") or cabecalho.get("cpf") else None

    x_dia = next(cx for cx, chave, _ in colunas if chave == "dia")
    abaixo = [p for p in pedacos if p.y < y_tabela - tolerancia]
    linhas_de_dia = []
    linha_totais = None
    for p in abaixo:
        if abs(p.x - x_dia) > max(6.0, folga * 2):
            continue
        achado = RE_DIA.match(p.texto.strip())
        if achado:
            linhas_de_dia.append((p, achado))
        elif p.norm in ("TOTAIS", "TOTAL", "TOTAL GERAL") and linha_totais is None:
            linha_totais = p

    usados = set()
    for ancora, achado in sorted(linhas_de_dia, key=lambda item: -item[0].y):
        dia = _data(achado.group(1))
        if dia is None:
            continue
        lido = DiaLido(data=dia, semana=normalizar(achado.group(2) or "")[:3])
        celulas = []
        for p in abaixo:
            if p is ancora or id(p) in usados or not _mesma_linha(p.y, ancora.y, tolerancia):
                continue
            chave = _coluna_de(p.x, colunas, folga)
            if chave is None or chave == "dia":
                if p.texto.strip() != achado.group(0):
                    resto = p.texto.strip()
                    if resto:
                        lido.outros.append(resto[:60])
                continue
            usados.add(id(p))
            celulas.append((p.x, chave, p.texto.strip()))
        # No texto em layout, a marca do relógio ("07:58 (I)") empurra a hora
        # seguinte para junto dela: "07:58 (I)12:00" -- uma célula com duas
        # horas vira duas, nas colunas de marcação seguintes, em ordem.
        colunas_de_marca = [chave for _, chave, _ in colunas if re.fullmatch(r"(ent|sai)\d", chave)]
        separadas = []
        for x, chave, texto in sorted(celulas):
            if chave in colunas_de_marca:
                partes = RE_TOKEN_DE_MARCA.findall(texto)
                conhecidas = all(re.match(r"\d", p) or normalizar(p) in PALAVRAS for p in partes)
                if len(partes) > 1 and conhecidas:
                    inicio = colunas_de_marca.index(chave)
                    for deslocamento, parte in enumerate(partes):
                        alvo = inicio + deslocamento
                        if alvo < len(colunas_de_marca):
                            separadas.append((x + deslocamento * 0.01, colunas_de_marca[alvo], parte.strip()))
                        else:
                            lido.outros.append(parte.strip()[:60])
                    continue
            separadas.append((x, chave, texto))
        for _, chave, texto in sorted(separadas):
            if chave == "previsto":
                lido.previsto = [
                    (_hora(a, b), _hora(c, d)) for a, b, c, d in RE_PREVISTO.findall(texto)
                    if _hora(a, b) and _hora(c, d)
                ]
            elif re.fullmatch(r"(ent|sai)\d", chave):
                marca = ler_marca(texto, chave)
                if marca:
                    lido.marcas.append(marca)
            elif chave == "dia_falta":
                if texto.isdigit():
                    lido.totais["dia_falta"] = int(texto)
            else:
                minutos = ler_duracao(texto)
                if minutos is not None:
                    lido.totais[chave] = minutos
                else:
                    lido.outros.append(texto[:60])
        ordem = {chave: i for i, (_, chave, _) in enumerate(colunas)}
        lido.marcas.sort(key=lambda m: ordem.get(m.coluna, 99))
        palavras = {m.palavra for m in lido.marcas if m.palavra}
        if not lido.horas and palavras:
            principal = next((p for p in ("feriado", "ferias", "atestado", "afastamento", "abono", "folga", "falta")
                              if p in palavras), sorted(palavras)[0])
            lido.ocorrencia = principal
        resultado.dias.append(lido)

    if linha_totais is not None:
        for p in abaixo:
            if p is linha_totais or not _mesma_linha(p.y, linha_totais.y, tolerancia):
                continue
            chave = _coluna_de(p.x, colunas, folga)
            if chave in (None, "dia", "previsto") or re.fullmatch(r"(ent|sai)\d", chave or ""):
                continue
            texto = p.texto.strip()
            if chave == "dia_falta":
                if texto.isdigit():
                    resultado.totais["dia_falta"] = int(texto)
                continue
            minutos = ler_duracao(texto)
            if minutos is not None:
                resultado.totais[chave] = minutos

    # As alterações: as linhas logo abaixo do título "Alterações".
    titulo = next((p for p in pedacos if p.norm.startswith("ALTERACOES")), None)
    if titulo is not None:
        anterior = titulo.y
        for p in sorted((p for p in pedacos if p.y < titulo.y - tolerancia and p.x > titulo.x + 1),
                        key=lambda p: (-p.y, p.x)):
            if anterior - p.y > linha * 2.2:
                break
            texto = re.sub(r"\s+", " ", p.texto).strip()
            if texto:
                resultado.alteracoes.append(texto[:160])
                for achado in re.finditer(r"FERIADO EM (\d{2}/\d{2}/\d{4})", normalizar(texto)):
                    data_feriado = _data(achado.group(1))
                    if data_feriado:
                        resultado.feriados.append(data_feriado)
            anterior = p.y
    return resultado


# ======================================================================
# O ARQUIVO INTEIRO
# ======================================================================
def _pdf(dados: bytes):
    from pypdf import PdfReader

    registro = logging.getLogger("pypdf")
    antes = registro.level
    registro.setLevel(logging.ERROR)
    try:
        leitor = PdfReader(io.BytesIO(dados), strict=False)
        if leitor.is_encrypted:
            raise CartaoIlegivel("O PDF está protegido por senha. Exporte o cartão de novo, sem senha.")
        return leitor
    except CartaoIlegivel:
        raise
    except Exception as erro:  # noqa: BLE001 -- PDF quebrado
        raise CartaoIlegivel("Não deu para abrir este PDF: o arquivo parece corrompido.") from erro
    finally:
        registro.setLevel(antes)


def _hora_ou_none(valor):
    return valor if isinstance(valor, time) else None


def ler(dados: bytes) -> Leitura:
    """Todos os cartões do arquivo (um por pessoa e período)."""
    leitor = _pdf(dados)
    registro = logging.getLogger("pypdf")
    antes = registro.level
    registro.setLevel(logging.ERROR)
    paginas = []
    tem_texto = False
    try:
        for numero, pagina in enumerate(leitor.pages, start=1):
            lida = None
            try:
                lida = _ler_pagina(pagina, numero)
                if lida is None or (not lida.colunas and not lida.cabecalho.get("cpf")):
                    alternativa = _ler_pagina(pagina, numero, por_layout=True)
                    if alternativa is not None and (alternativa.colunas or lida is None):
                        lida = alternativa
            except CartaoIlegivel:
                raise
            except Exception:  # noqa: BLE001 -- uma página estranha não derruba o arquivo
                lida = None
            if lida is not None:
                tem_texto = True
                paginas.append(lida)
            elif (pagina.extract_text() or "").strip():
                tem_texto = True
    finally:
        registro.setLevel(antes)

    if not tem_texto:
        raise CartaoIlegivel(
            "Este PDF não tem texto: parece uma imagem escaneada ou foto. Exporte o cartão de ponto "
            "direto do sistema do relógio (o PDF que ele gera tem o texto e dá para ler).",
            titulo="PDF sem texto",
        )

    cartoes: list[CartaoLido] = []
    atual = None
    for pagina in paginas:
        cab = pagina.cabecalho
        cpf = digitos(cab.get("cpf"))
        nome = re.sub(r"\s+", " ", cab.get("nome") or "").strip()
        periodo = cab.get("periodo") or (None, None)
        continua = atual is not None and (
            (not cpf and not nome)
            or ((cpf or nome) and (cpf or nome) == (atual.cpf or atual.nome) and periodo == (atual.inicio, atual.fim))
        )
        if not continua:
            if not (cpf or nome) and not pagina.dias:
                continue
            atual = CartaoLido(
                empresa_nome=re.sub(r"\s+", " ", cab.get("empresa_nome") or "").strip(),
                empresa_cnpj=digitos(cab.get("empresa_cnpj")),
                empresa_ie=(cab.get("empresa_ie") or "").strip(),
                nome=nome, cpf=cpf, pis=digitos(cab.get("pis")),
                admissao=_data(cab.get("admissao")),
                matricula=(cab.get("matricula") or "").strip(),
                inicio=periodo[0], fim=periodo[1],
                emitido_em=cab.get("emitido"),
            )
            cartoes.append(atual)
        atual.paginas.append(pagina.numero)
        if pagina.horario and not atual.horario:
            atual.horario = pagina.horario
        if pagina.colunas and not atual.colunas:
            atual.colunas = [nome_coluna for _, _, nome_coluna in pagina.colunas]
        ja = {d.data for d in atual.dias}
        atual.dias.extend(d for d in pagina.dias if d.data not in ja)
        for chave, valor in pagina.totais.items():
            atual.totais[chave] = valor
        atual.alteracoes.extend(a for a in pagina.alteracoes if a not in atual.alteracoes)
        atual.feriados.extend(f for f in pagina.feriados if f not in atual.feriados)

    cartoes = [c for c in cartoes if c.dias or c.cpf]
    if not cartoes:
        raise CartaoIlegivel(
            "Não achei um cartão de ponto neste PDF (a tabela dos dias com ENT. 1, SAÍ. 1... e o "
            "cabeçalho do funcionário). Confira se é o \"Cartão de Ponto\" exportado do relógio.",
        )

    for cartao in cartoes:
        cartao.dias.sort(key=lambda d: d.data)
        if cartao.dias and not cartao.inicio:
            cartao.inicio = cartao.dias[0].data
        if cartao.dias and not cartao.fim:
            cartao.fim = cartao.dias[-1].data
        _conferir(cartao)
    return Leitura(cartoes=cartoes, paginas=len(leitor.pages))


def _conferir(cartao: CartaoLido):
    """O que a leitura acha estranho: vai como aviso, não como erro."""
    if not cartao.cpf:
        cartao.avisos.append("O cartão não traz o CPF do funcionário: a ficha não tem como ser achada.")
    if cartao.inicio and cartao.fim:
        fora = [d.data for d in cartao.dias if not (cartao.inicio <= d.data <= cartao.fim)]
        if fora:
            cartao.avisos.append(f"{len(fora)} dia(s) fora do período do cartão foram ignorados.")
            cartao.dias = [d for d in cartao.dias if cartao.inicio <= d.data <= cartao.fim]
        esperados = (cartao.fim - cartao.inicio).days + 1
        if 0 < len(cartao.dias) < esperados:
            cartao.avisos.append(
                f"O cartão vai de {cartao.inicio:%d/%m} a {cartao.fim:%d/%m/%Y} ({esperados} dias), "
                f"mas só {len(cartao.dias)} linhas de dia foram lidas."
            )
    soma = cartao.soma_dos_dias()
    for chave, total in cartao.totais.items():
        if soma.get(chave, 0) != total:
            cartao.avisos.append(
                f"A linha TOTAIS diz {hm(total) if chave != 'dia_falta' else total} em "
                f"{ROTULOS_DOS_TOTAIS.get(chave, chave)}, e a soma dos dias dá "
                f"{hm(soma.get(chave, 0)) if chave != 'dia_falta' else soma.get(chave, 0)}."
            )


# ======================================================================
# DE VOLTA DO JSON (o que fica guardado em CartaoPonto.dados)
# ======================================================================
def hora_de(texto):
    if not texto:
        return None
    achado = re.fullmatch(r"(\d{1,2}):(\d{2})", str(texto))
    return _hora(achado.group(1), achado.group(2)) if achado else None


def dias_do_json(dados: dict) -> list[DiaLido]:
    dias = []
    for item in dados.get("dias") or []:
        try:
            dia = date.fromisoformat(item["data"])
        except (KeyError, ValueError, TypeError):
            continue
        marcas = []
        for m in item.get("marcas") or []:
            marcas.append(Marca(
                coluna=m.get("coluna", ""), hora=hora_de(m.get("hora")),
                marcador=m.get("marcador", ""), palavra=m.get("palavra", ""),
            ))
        dias.append(DiaLido(
            data=dia, semana=item.get("semana", ""),
            previsto=[(hora_de(a), hora_de(b)) for a, b in item.get("previsto") or [] if hora_de(a) and hora_de(b)],
            marcas=marcas, ocorrencia=item.get("ocorrencia", ""), totais=item.get("totais") or {},
            outros=item.get("outros") or [],
        ))
    return dias


def horario_do_json(dados: dict) -> dict:
    horario = {}
    for dia, pares in (dados.get("horario") or {}).items():
        try:
            horario[int(dia)] = [(hora_de(a), hora_de(b)) for a, b in pares if hora_de(a) and hora_de(b)]
        except (TypeError, ValueError):
            continue
    return horario
