"""A leitura da nota fiscal de compra: o XML da NF-e ou o PDF do DANFE.

"Vai vir PDF ou XML" -- as duas portas dão no MESMO `NotaLida`, e daí em
diante (conferência, soma dos repetidos, lançamento) não se sabe mais de
onde a nota veio.

O XML É A FONTE BOA. É o documento fiscal de verdade (o PDF é só a
representação impressa dele): cada campo tem nome, e o leitor só precisa
achar a etiqueta. Lido com a biblioteca padrão (xml.etree), SEM DTD: um
XML com DOCTYPE ou ENTITY é recusado antes de chegar ao parser -- é o que
fecha a porta da entidade externa (ler arquivo do servidor) e da bomba de
expansão (o XML que se multiplica até derrubar a memória). NF-e não tem
nenhum dos dois.

O PDF DO DANFE É LIDO PELO TEXTO. O DANFE tem leiaute padrão (Manual de
Orientação do Contribuinte, anexo do DANFE): o canhoto "RECEBEMOS DE
<emitente> OS PRODUTOS...", o quadro do emitente, a CHAVE DE ACESSO de 44
dígitos, "DESTINATÁRIO / REMETENTE", "CÁLCULO DO IMPOSTO" e o quadro
"DADOS DOS PRODUTOS / SERVIÇOS", uma linha por item:

    CÓDIGO  DESCRIÇÃO  NCM/SH  CST  CFOP  UNID  QUANT  V.UNIT  V.TOTAL  ...

O texto sai do pypdf em modo "layout" (as colunas viram espaços, como no
importador de orçamento), e cada linha de item é reconhecida por regra:
três números seguidos (quantidade, valor unitário, valor total) depois da
unidade, com NCM/CST/CFOP antes. Quando o gerador do DANFE usa outra
ordem de colunas, vale a regra de reserva: a trinca em que
quantidade x unitário = total.

A CHAVE DE ACESSO É A ÂNCORA. Ela carrega o CNPJ do emitente, a série e o
número da nota, e tem dígito verificador (módulo 11): quando o PDF traz a
chave, esses três campos saem dela -- e o que estiver escrito no papel só
serve para conferir.

NADA AQUI CONHECE O DJANGO. Entra bytes (ou texto), sai `NotaLida`; quem
cadastra é `lancamento.py`. É o que deixa os testes lerem um DANFE
sintético sem banco, e o leitor ser rodado à parte num arquivo de fora.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from io import BytesIO
from xml.etree import ElementTree as ET

#: O maior arquivo aceito. O XML de uma NF-e com 990 itens (o máximo da
#: nota) passa pouco de 2 MB; o DANFE em PDF de uma nota grande, menos.
TAMANHO_MAXIMO = 10 * 1024 * 1024
PAGINAS_MAXIMAS = 80
ITENS_MAXIMOS = 990

NS_NFE = "http://www.portalfiscal.inf.br/nfe"
CENTAVO = Decimal("0.01")


class NotaRecusada(Exception):
    """O arquivo não dá para ler como nota fiscal. A mensagem vai para a tela."""


@dataclass
class ItemLido:
    numero: int
    codigo: str
    descricao: str
    unidade: str
    quantidade: Decimal
    valor_unitario: Decimal
    valor_total: Decimal
    ncm: str = ""
    complemento: str = ""


@dataclass
class NotaLida:
    formato: str
    fornecedor_nome: str = ""
    fornecedor_cnpj: str = ""
    numero: str = ""
    serie: str = ""
    emissao: date | None = None
    chave: str = ""
    valor_produtos: Decimal | None = None
    valor_total: Decimal | None = None
    itens: list[ItemLido] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    @property
    def soma_dos_itens(self) -> Decimal:
        return sum((item.valor_total for item in self.itens), Decimal("0.00"))


# ======================================================================
# A CHAVE DE ACESSO
# ======================================================================
def _valor_do_caractere(caractere: str) -> int:
    # CNPJ alfanumérico (2026): o valor é o código ASCII menos 48 -- o
    # mesmo cálculo de `validacoes.cnpj_valido`. Para dígito, dá o dígito.
    return ord(caractere) - 48


def digito_da_chave(quarenta_e_tres: str) -> int:
    """Módulo 11, pesos de 2 a 9 da direita para a esquerda."""
    soma, peso = 0, 2
    for caractere in reversed(quarenta_e_tres):
        soma += _valor_do_caractere(caractere) * peso
        peso = 2 if peso == 9 else peso + 1
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def chave_valida(chave: str) -> bool:
    chave = (chave or "").upper()
    if not re.fullmatch(r"[0-9]{6}[0-9A-Z]{12}[0-9]{26}", chave):
        return False
    return digito_da_chave(chave[:43]) == int(chave[43])


def partes_da_chave(chave: str) -> dict:
    """cUF, AAMM, CNPJ, modelo, série, número, forma de emissão, código e DV."""
    return {
        "uf": chave[0:2],
        "ano_mes": chave[2:6],
        "cnpj": chave[6:20],
        "modelo": chave[20:22],
        "serie": str(int(chave[22:25])),
        "numero": str(int(chave[25:34])),
    }


def chave_formatada(chave: str) -> str:
    return " ".join(chave[i:i + 4] for i in range(0, len(chave), 4))


# ======================================================================
# NÚMEROS E DATAS
# ======================================================================
def numero_br(texto: str) -> Decimal | None:
    """'1.262,20' -> 1262.20; '5,0000' -> 5.0000; '1.000' -> 1000."""
    bruto = (texto or "").strip()
    if not bruto:
        return None
    if "," in bruto:
        bruto = bruto.replace(".", "").replace(",", ".")
    else:
        bruto = bruto.replace(".", "")
    try:
        valor = Decimal(bruto)
    except InvalidOperation:
        return None
    return valor if valor.is_finite() else None


def numero_xml(texto: str | None) -> Decimal | None:
    """O XML usa ponto decimal e nada de milhar: '1262.20'."""
    bruto = (texto or "").strip()
    if not bruto:
        return None
    try:
        valor = Decimal(bruto)
    except InvalidOperation:
        return None
    return valor if valor.is_finite() else None


def _data_br(texto: str) -> date | None:
    achado = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", (texto or "").strip())
    if not achado:
        return None
    dia, mes, ano = (int(parte) for parte in achado.groups())
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def _data_iso(texto: str | None) -> date | None:
    """'2026-11-18T16:42:16-03:00' -> 18/11/2026 (a data como a nota diz)."""
    achado = re.match(r"(\d{4})-(\d{2})-(\d{2})", (texto or "").strip())
    if not achado:
        return None
    ano, mes, dia = (int(parte) for parte in achado.groups())
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def so_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def documento_do_emitente(texto: str) -> str:
    """CNPJ (inclusive o alfanumérico) ou CPF, sem pontuação."""
    return re.sub(r"[^0-9A-Z]", "", (texto or "").upper())[:14]


def _espacos(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def bate(quantidade: Decimal, unitario: Decimal, total: Decimal) -> bool:
    """quantidade x unitário dá o total, com a folga do arredondamento.

    O unitário da nota tem até 10 casas e o DANFE imprime 4: 15 x 1,9830 =
    29,745, e a nota diz 29,75. A folga é de meio centavo por unidade
    impressa a menos -- mais um centavo de arredondamento do próprio total.
    """
    calculado = quantidade * unitario
    folga = max(Decimal("0.011"), (quantidade * Decimal("0.00005")).copy_abs() + Decimal("0.011"))
    return (calculado - total).copy_abs() <= folga


# ======================================================================
# QUE ARQUIVO É ESTE
# ======================================================================
def _sem_bom(conteudo: bytes) -> bytes:
    if conteudo.startswith(b"\xef\xbb\xbf"):
        return conteudo[3:]
    return conteudo


def formato_do_arquivo(nome: str, conteudo: bytes) -> str:
    """"pdf" ou "xml" -- pelo CONTEÚDO, com a extensão tendo de concordar."""
    if not conteudo:
        raise NotaRecusada("O arquivo chegou vazio. Escolha o PDF ou o XML da nota de novo.")
    if len(conteudo) > TAMANHO_MAXIMO:
        raise NotaRecusada(
            f"O arquivo passa de {TAMANHO_MAXIMO // (1024 * 1024)} MB. Uma nota fiscal "
            "não chega perto disso: confira se escolheu o arquivo certo."
        )
    extensao = (nome or "").rsplit(".", 1)[-1].lower() if "." in (nome or "") else ""
    inicio = _sem_bom(conteudo[:2048]).lstrip()
    if conteudo[:1024].find(b"%PDF-") != -1:
        formato = "pdf"
    elif inicio.startswith(b"<"):
        formato = "xml"
    else:
        raise NotaRecusada(
            "Este arquivo não é PDF nem XML. Envie o DANFE em PDF ou o XML da NF-e "
            "(o fornecedor manda os dois no e-mail da nota)."
        )
    if extensao and extensao != formato:
        raise NotaRecusada(
            f"O nome diz “.{extensao}”, mas o arquivo é {formato.upper()}. Confira se "
            "escolheu o arquivo certo."
        )
    return formato


def ler(nome: str, conteudo: bytes) -> NotaLida:
    """A porta única: decide o formato e devolve a nota lida e conferida."""
    formato = formato_do_arquivo(nome, conteudo)
    nota = ler_xml(conteudo) if formato == "xml" else ler_pdf(conteudo)
    if not nota.itens:
        if formato == "pdf":
            raise NotaRecusada(
                "Não achei os itens da nota neste PDF. Ele é o DANFE (a nota impressa)? "
                "Se for, envie o XML da NF-e, que o fornecedor manda junto."
            )
        raise NotaRecusada("O XML não tem nenhum item (det/prod). Confira se é o XML da NF-e.")
    if len(nota.itens) > ITENS_MAXIMOS:
        raise NotaRecusada("A nota tem itens demais para uma NF-e. Confira o arquivo.")
    conferir(nota)
    return nota


# ======================================================================
# XML DA NF-e
# ======================================================================
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _filho(no, nome):
    if no is None:
        return None
    for filho in no:
        if _local(filho.tag) == nome:
            return filho
    return None


def _texto(no, *caminho) -> str:
    for nome in caminho:
        no = _filho(no, nome)
        if no is None:
            return ""
    return (no.text or "").strip()


def ler_xml(conteudo: bytes) -> NotaLida:
    dados = _sem_bom(conteudo)
    # Recusa ANTES do parser: NF-e não tem DTD nem entidade. Com isso não
    # há entidade externa para resolver nem expansão para multiplicar.
    cabeca = dados.upper()
    if b"<!DOCTYPE" in cabeca or b"<!ENTITY" in cabeca:
        raise NotaRecusada(
            "Este XML tem uma estrutura que a NF-e não usa (DOCTYPE/ENTITY) e foi "
            "recusado por segurança. Baixe o XML de novo no portal ou peça ao fornecedor."
        )
    try:
        raiz = ET.fromstring(dados)
    except ET.ParseError as exc:
        raise NotaRecusada(
            "O XML está corrompido e não abriu. Baixe de novo ou envie o PDF da nota."
        ) from exc

    espaco = raiz.tag[1:].split("}", 1)[0] if raiz.tag.startswith("{") else ""
    if espaco and espaco != NS_NFE:
        raise NotaRecusada("Este XML não é de uma NF-e (o espaço de nomes é outro).")

    inf = next((no for no in raiz.iter() if _local(no.tag) == "infNFe"), None)
    if inf is None:
        raise NotaRecusada(
            "Este XML não é de uma NF-e (não tem infNFe). Envie o XML da nota de "
            "compra, ou o PDF do DANFE."
        )

    nota = NotaLida(formato="xml")
    ide = _filho(inf, "ide")
    emit = _filho(inf, "emit")
    nota.numero = str(int(_texto(ide, "nNF"))) if _texto(ide, "nNF").isdigit() else _texto(ide, "nNF")
    nota.serie = str(int(_texto(ide, "serie"))) if _texto(ide, "serie").isdigit() else _texto(ide, "serie")
    nota.emissao = _data_iso(_texto(ide, "dhEmi") or _texto(ide, "dEmi"))
    nota.fornecedor_nome = _espacos(_texto(emit, "xNome"))
    nota.fornecedor_cnpj = documento_do_emitente(_texto(emit, "CNPJ") or _texto(emit, "CPF"))

    chave = (inf.get("Id") or "").upper()
    chave = chave[3:] if chave.startswith("NFE") else chave
    protocolo = next((no for no in raiz.iter() if _local(no.tag) == "chNFe"), None)
    if not chave_valida(chave) and protocolo is not None:
        chave = (protocolo.text or "").strip().upper()
    if chave_valida(chave):
        nota.chave = chave
    elif chave:
        nota.avisos.append("A chave de acesso do XML não confere (dígito verificador).")

    total = _filho(_filho(inf, "total"), "ICMSTot")
    nota.valor_produtos = numero_xml(_texto(total, "vProd"))
    nota.valor_total = numero_xml(_texto(total, "vNF"))

    for indice, det in enumerate((no for no in inf if _local(no.tag) == "det"), start=1):
        prod = _filho(det, "prod")
        quantidade = numero_xml(_texto(prod, "qCom"))
        unitario = numero_xml(_texto(prod, "vUnCom"))
        total_item = numero_xml(_texto(prod, "vProd"))
        if quantidade is None or total_item is None:
            nota.avisos.append(f"O item {indice} do XML está sem quantidade ou valor e ficou de fora.")
            continue
        if unitario is None:
            unitario = (total_item / quantidade) if quantidade else Decimal("0")
        numero = det.get("nItem") or str(indice)
        nota.itens.append(ItemLido(
            numero=int(numero) if numero.isdigit() else indice,
            codigo=_espacos(_texto(prod, "cProd"))[:60],
            descricao=_espacos(_texto(prod, "xProd"))[:250],
            unidade=_espacos(_texto(prod, "uCom"))[:6],
            quantidade=quantidade,
            valor_unitario=unitario,
            valor_total=total_item.quantize(CENTAVO),
            ncm=_texto(prod, "NCM")[:8],
            complemento=_espacos(_texto(det, "infAdProd"))[:250],
        ))
    return nota


# ======================================================================
# PDF DO DANFE
# ======================================================================
def texto_do_pdf(conteudo: bytes) -> str:
    """O texto de cada página em modo "layout", separadas por \\f."""
    import logging

    if b"%%EOF" not in conteudo:
        raise NotaRecusada("O PDF parece cortado (o arquivo não termina). Baixe a nota de novo.")
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover -- está no requirements
        raise NotaRecusada("Não consegui abrir PDF agora. Envie o XML da nota.") from exc

    registro = logging.getLogger("pypdf")
    nivel = registro.level
    registro.setLevel(logging.ERROR)
    try:
        documento = PdfReader(BytesIO(conteudo), strict=False)
        if documento.is_encrypted:
            try:
                documento.decrypt("")
            except Exception as exc:  # noqa: BLE001
                raise NotaRecusada("O PDF está protegido por senha. Envie o XML da nota.") from exc
        if len(documento.pages) > PAGINAS_MAXIMAS:
            raise NotaRecusada(
                f"O PDF tem mais de {PAGINAS_MAXIMAS} páginas: não parece um DANFE. "
                "Envie o XML da nota."
            )
        paginas = [pagina.extract_text(extraction_mode="layout") or "" for pagina in documento.pages]
    except NotaRecusada:
        raise
    except Exception as exc:  # noqa: BLE001 -- PDF torto chega de todo jeito
        raise NotaRecusada("O PDF está corrompido e não abriu. Envie o XML da nota.") from exc
    finally:
        registro.setLevel(nivel)
    texto = "\f".join(paginas)
    if len(re.sub(r"\s", "", texto)) < 40:
        raise NotaRecusada(
            "Este PDF é uma imagem (foto ou digitalização), sem texto para ler. Envie o "
            "XML da NF-e, ou o PDF que o fornecedor mandou por e-mail."
        )
    return texto


def ler_pdf(conteudo: bytes) -> NotaLida:
    nota = ler_texto_danfe(texto_do_pdf(conteudo))
    nota.formato = "pdf"
    return nota


#: Número com vírgula decimal, como o DANFE imprime ("1.262,20", "5,0000").
_NUM = r"\d{1,3}(?:\.\d{3})+,\d{1,10}|\d+,\d{1,10}"
#: A quantidade pode vir sem casas ("5") em geradores mais simples.
_QTD = r"\d{1,3}(?:\.\d{3})+(?:,\d{1,4})?|\d+(?:,\d{1,4})?"
#: A unidade tem letra ("UN", "PÇ", "M2", "CE", "KG").
_UNIDADE = r"(?=[^\s\d]|\d*[A-Za-zÀ-ÿ²³])[^\s]{1,6}"

_ITEM = re.compile(
    r"^\s*(?P<codigo>\S{1,60})\s+(?P<descricao>.*?\S)\s+"
    r"(?P<ncm>\d{8}|\d{4}\.\d{2}\.\d{2}|00)\s+"
    r"(?P<cst>\d{2,4}|\d/\d{2,3})\s+"
    r"(?P<cfop>\d\.?\d{3})\s+"
    rf"(?P<unidade>{_UNIDADE})\s+"
    rf"(?P<quantidade>{_QTD})\s+(?P<unitario>{_NUM})\s+(?P<total>{_NUM})(?=\s|$)"
)
#: A segunda metade de um item quebrado (o texto "simples" do PDF põe o
#: código e a descrição numa linha e os números na de baixo).
_CAUDA = re.compile(
    r"^\s*(?:\d{8}|\d{4}\.\d{2}\.\d{2}|00)\s+(?:\d{2,4}|\d/\d{2,3})\s+\d\.?\d{3}\s+"
    rf"{_UNIDADE}\s+(?:{_QTD})\s+(?:{_NUM})\s+(?:{_NUM})(?=\s|$)"
)

_INICIO_ITENS = re.compile(r"DADOS\s+D[OE]S?\s+PRODUTOS?\s*/\s*SERVI[ÇC]OS?", re.I)
_FIM_ITENS = re.compile(
    r"C[ÁA]LCULO\s+DO\s+ISSQN|DADOS\s+ADICIONAIS|INFORMA[ÇC][ÕO]ES\s+COMPLEMENTARES"
    r"|RESERVADO\s+AO\s+FISCO",
    re.I,
)
_PALAVRAS_DO_CABECALHO = re.compile(
    r"C[ÓO]DIGO|DESCRI[ÇC][ÃA]O|NCM|CFOP|UNID|QUANT|VALOR|AL[ÍI]Q|B\.\s*C[ÁA]LC|"
    r"\bPRODUTO\b|\bUNIT\b|\bTOTAL\b|\bICMS\b|\bIPI\b|\bCST\b|\bCSOSN\b|\bO/CST\b",
    re.I,
)
_LIXO_DO_QUADRO = re.compile(r"CONTINUA|CONTINUA[ÇC][ÃA]O|FOLHA\s+\d+\s*/\s*\d+", re.I)


def _cabecalho_da_tabela(linha: str) -> bool:
    return bool(_PALAVRAS_DO_CABECALHO.search(linha)) and not re.search(_NUM, linha)


def _item_da_linha(linha: str) -> tuple[ItemLido, dict] | None:
    """A linha inteira de um item -- ou None. Devolve também onde as colunas caíram."""
    if _CAUDA.match(linha):
        # Só os números (NCM, CST, CFOP...): é a metade de baixo de um item
        # quebrado, e não um item cujo "código" seria o NCM.
        return None
    achado = _ITEM.match(linha)
    if achado:
        quantidade = numero_br(achado["quantidade"])
        unitario = numero_br(achado["unitario"])
        total = numero_br(achado["total"])
        if None in (quantidade, unitario, total):
            return None
        item = ItemLido(
            numero=0,
            codigo=achado["codigo"],
            descricao=_espacos(achado["descricao"]),
            unidade=achado["unidade"],
            quantidade=quantidade,
            valor_unitario=unitario,
            valor_total=total.quantize(CENTAVO),
            ncm=so_digitos(achado["ncm"]),
        )
        return item, {"fim_descricao": achado.end("descricao"), "inicio_ncm": achado.start("ncm")}
    return _item_pela_trinca(linha)


def _item_pela_trinca(linha: str) -> tuple[ItemLido, dict] | None:
    """A regra de reserva: código, descrição e a trinca que fecha a conta.

    Gerador de DANFE que muda a ordem das colunas (ou que não imprime NCM)
    ainda imprime a unidade e, logo depois, quantidade, valor unitário e
    valor total. A trinca só vale se quantidade x unitário = total -- é o
    que impede de pegar três números quaisquer da linha.
    """
    pedacos = [(m.start(), m.end(), m.group(0)) for m in re.finditer(r"\S+", linha)]
    if len(pedacos) < 6:
        return None
    for k in range(2, len(pedacos) - 2):
        textos = [pedacos[k + i][2] for i in range(3)]
        if not (re.fullmatch(_QTD, textos[0]) and re.fullmatch(_NUM, textos[1]) and re.fullmatch(_NUM, textos[2])):
            continue
        unidade = pedacos[k - 1][2]
        if not re.fullmatch(_UNIDADE, unidade):
            continue
        quantidade, unitario, total = (numero_br(t) for t in textos)
        if None in (quantidade, unitario, total) or not quantidade or not bate(quantidade, unitario, total):
            continue
        # a descrição vai do segundo pedaço até o primeiro código fiscal
        # (NCM de 8 dígitos) ou, sem ele, até a unidade
        fim = k - 1
        for j in range(2, k - 1):
            if re.fullmatch(r"\d{8}|\d{4}\.\d{2}\.\d{2}", pedacos[j][2]):
                fim = j
                break
        while fim > 2 and re.fullmatch(r"[\d/.]+", pedacos[fim - 1][2]):
            fim -= 1  # CST e CFOP soltos antes da unidade
        if fim < 2:
            return None
        descricao = linha[pedacos[1][0]:pedacos[fim - 1][1]]
        ncm = next((so_digitos(p[2]) for p in pedacos[fim:k - 1] if re.fullmatch(r"\d{8}|\d{4}\.\d{2}\.\d{2}", p[2])), "")
        item = ItemLido(
            numero=0,
            codigo=pedacos[0][2][:60],
            descricao=_espacos(descricao),
            unidade=unidade,
            quantidade=quantidade,
            valor_unitario=unitario,
            valor_total=total.quantize(CENTAVO),
            ncm=ncm,
        )
        return item, {"fim_descricao": pedacos[fim - 1][1], "inicio_ncm": pedacos[fim][0]}
    return None


def _regioes_de_itens(paginas: list[str]) -> list[list[str]]:
    """As linhas do quadro de produtos, página a página."""
    regioes = []
    for pagina in paginas:
        linhas = pagina.splitlines()
        dentro = False
        atual: list[str] = []
        for linha in linhas:
            if _INICIO_ITENS.search(linha):
                dentro = True
                atual = []
                regioes.append(atual)
                continue
            if dentro and _FIM_ITENS.search(linha):
                dentro = False
                continue
            if dentro:
                atual.append(linha)
    return regioes


def _itens_da_regiao(linhas: list[str]) -> list[ItemLido]:
    linhas = [linha.rstrip() for linha in linhas if linha.strip()]
    # Cabeçalho repetido e "continua na folha 2" saem -- mas só a linha que
    # não é item: "FITA CONTINUA 3M" é material, não aviso de página.
    linhas = [
        linha for linha in linhas
        if _item_da_linha(linha) or not (_cabecalho_da_tabela(linha) or _LIXO_DO_QUADRO.search(linha))
    ]
    itens: list[ItemLido] = []
    colunas_do_ultimo: dict = {}
    i = 0
    while i < len(linhas):
        linha = linhas[i]
        lido = _item_da_linha(linha)
        if lido:
            item, colunas_do_ultimo = lido
            itens.append(item)
            i += 1
            continue
        # Item quebrado em duas (ou três) linhas: código e descrição numa,
        # os números na outra -- e, no meio, o complemento do item. Só vale
        # se a linha de baixo NÃO for um item sozinha: senão esta linha é a
        # continuação do item de cima, e não a cabeça de um novo.
        juntou = False
        for salto in (1, 2):
            if i + salto >= len(linhas):
                break
            meio = linhas[i + 1:i + salto]
            cauda = linhas[i + salto]
            if any(_item_da_linha(l) for l in meio) or _item_da_linha(cauda):
                break
            if not _CAUDA.match(cauda):
                continue
            junto = _item_da_linha(linha.rstrip() + " " + cauda.strip())
            if junto:
                item, _ = junto
                item.complemento = _espacos(" ".join(meio))
                itens.append(item)
                colunas_do_ultimo = {}
                i += salto + 1
                juntou = True
                break
        if juntou:
            continue
        if itens:
            _continuacao(itens[-1], linha, colunas_do_ultimo)
        i += 1
    return itens


def _continuacao(item: ItemLido, linha: str, colunas: dict) -> None:
    """A linha de baixo de um item: a descrição que não coube, ou o complemento.

    No DANFE, a coluna da descrição quebra a linha quando o texto não cabe
    (a descrição da NF-e tem até 120 caracteres), e é ali também que entra
    a "informação adicional do produto" (infAdProd: lote, referência...).
    A diferença está no papel: a descrição que quebrou ENCOSTOU na coluna
    do NCM; a que acabou cedo deixou espaço -- e aí a linha de baixo é
    complemento, não nome do material.
    """
    texto = _espacos(linha)
    if not texto:
        return
    encostou = bool(colunas) and colunas.get("inicio_ncm", 0) - colunas.get("fim_descricao", 0) <= 3 and "  " in linha
    if encostou and not item.complemento:
        item.descricao = _espacos(f"{item.descricao} {texto}")[:250]
    else:
        item.complemento = _espacos(f"{item.complemento} {texto}")[:250]


# ---------------------------------------------------------------- campos
_CNPJ_FORMATADO = re.compile(r"(?<![0-9A-Z])([0-9A-Z]{2}\.[0-9A-Z]{3}\.[0-9A-Z]{3}/[0-9A-Z]{4}-\d{2})(?!\d)")
_DATA = re.compile(r"(?<!\d)(\d{2}/\d{2}/\d{4})(?!\d)")
_CHAVE = re.compile(r"(?<!\d)(\d{4}(?:[ .]?\d{4}){10})(?!\d)")


def _achar_chave(texto: str) -> str:
    for achado in _CHAVE.finditer(texto):
        chave = so_digitos(achado.group(1))
        if len(chave) == 44 and chave_valida(chave):
            return chave
    return ""


def _valor_rotulado(linhas: list[str], rotulo: re.Pattern, padrao: str) -> str:
    """O valor que o DANFE imprime embaixo (ou ao lado) de um rótulo.

    No texto em layout, o rótulo e o valor estão na mesma coluna, em
    linhas seguidas; numa linha de vários rótulos ("VALOR DO FRETE ...
    VALOR TOTAL DA NOTA"), o valor certo é o que está mais perto do meio
    do rótulo.
    """
    for indice, linha in enumerate(linhas):
        achado = rotulo.search(linha)
        if not achado:
            continue
        resto = linha[achado.end():]
        ao_lado = re.match(rf"\s*[:\-]?\s*(?:R\$\s*)?({padrao})", resto)
        if ao_lado:
            return ao_lado.group(1)
        centro = (achado.start() + achado.end()) / 2
        vistas = 0
        for seguinte in linhas[indice + 1:indice + 6]:
            if not seguinte.strip():
                continue
            vistas += 1
            candidatos = [
                (abs((m.start(1) + m.end(1)) / 2 - centro), m.group(1))
                for m in re.finditer(rf"(?<![\d,.])({padrao})(?![\d,])", seguinte)
            ]
            if candidatos:
                return min(candidatos)[1]
            if vistas >= 2:
                break
    return ""


_PALAVRAS_DO_DANFE = re.compile(
    r"^(DANFE|DOCUMENTO\s+AUXILIAR|DA\s+NOTA\s+FISCAL|ELETR[ÔO]NICA|CHAVE\s+DE\s+ACESSO|"
    r"\d\s*-\s*(ENTRADA|SA[ÍI]DA)|N[º°o]\.?|S[ÉE]RIE|FOLHA|IDENTIFICA)",
    re.I,
)
_ENDERECO = re.compile(
    r"^(RUA|R\.|AV\.?|AVENIDA|ROD\.?|RODOVIA|ESTRADA|ESTR\.|AL\.?|ALAMEDA|PRA[ÇC]A|TRAVESSA|"
    r"TV\.|LARGO|VIA|SETOR|QUADRA|CEP|FONE|TEL)\b|\d{5}-?\d{3}",
    re.I,
)


def _nome_do_emitente(texto: str, linhas: list[str]) -> str:
    canhoto = re.search(r"RECEBEMOS\s+DE\s+(.+?)\s+OS\s+PRODUTOS", texto, re.I | re.S)
    if canhoto:
        nome = _espacos(canhoto.group(1))
        if 2 <= len(nome) <= 160:
            return nome
    for indice, linha in enumerate(linhas):
        if not re.search(r"IDENTIFICA[ÇC][ÃA]O\s+DO\s+EMITENTE", linha, re.I):
            continue
        partes = []
        for seguinte in linhas[indice + 1:indice + 8]:
            pedacos = [p for p in re.split(r"\s{2,}", seguinte.strip()) if p]
            if not pedacos:
                continue
            primeiro = pedacos[0]
            if _ENDERECO.search(primeiro):
                break
            if _PALAVRAS_DO_DANFE.search(primeiro):
                continue
            partes.append(primeiro)
        return _espacos(" ".join(partes))[:160]
    return ""


def _cnpj_do_emitente(texto: str) -> str:
    """O primeiro CNPJ válido antes do quadro do destinatário."""
    destinatario = re.search(r"DESTINAT[ÁA]RIO\s*/\s*REMETENTE", texto, re.I)
    trecho = texto[:destinatario.start()] if destinatario else texto
    for achado in _CNPJ_FORMATADO.finditer(trecho):
        documento = documento_do_emitente(achado.group(1))
        if _cnpj_ok(documento):
            return documento
    return ""


def _cnpj_ok(documento: str) -> bool:
    # o mesmo cálculo de `validacoes.cnpj_valido`, sem importar o Django
    if len(documento) != 14 or not documento[-2:].isdigit() or len(set(documento)) == 1:
        return False

    def digito(valores, pesos):
        resto = sum(v * p for v, p in zip(valores, pesos)) % 11
        return 0 if resto < 2 else 11 - resto

    base = [ord(c) - 48 for c in documento[:12]]
    primeiro = digito(base, (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    segundo = digito(base + [primeiro], (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    return documento[-2:] == f"{primeiro}{segundo}"


def ler_texto_danfe(texto: str) -> NotaLida:
    """O DANFE já em texto (páginas separadas por \\f) -> NotaLida."""
    nota = NotaLida(formato="pdf")
    paginas = (texto or "").split("\f")
    linhas = (texto or "").replace("\f", "\n").splitlines()

    nota.chave = _achar_chave(texto)
    numero_escrito = ""
    # O DANFE imprime o número como 000.000.000; o "Nº" solto pode ser o do
    # endereço ("RUA X, Nº 355"), por isso ele só vale sem o primeiro.
    achado = re.search(r"N[º°o]\.?\s*:?\s*(\d{3}\.\d{3}\.\d{3})(?!\d)", texto) or re.search(
        r"N[º°o]\.?\s*:?\s*(\d{1,3}(?:\.\d{3}){1,2}|\d{1,9})(?!\d)", texto
    )
    if achado:
        numero_escrito = str(int(so_digitos(achado.group(1))))
    serie_escrita = ""
    achado = re.search(r"S[ÉE]RIE\s*:?\s*(\d{1,3})(?!\d)", texto, re.I)
    if achado:
        serie_escrita = str(int(achado.group(1)))

    if nota.chave:
        partes = partes_da_chave(nota.chave)
        nota.fornecedor_cnpj = partes["cnpj"]
        nota.numero = partes["numero"]
        nota.serie = partes["serie"]
        if numero_escrito and numero_escrito != nota.numero:
            nota.avisos.append(
                f"O número impresso ({numero_escrito}) não é o da chave de acesso ({nota.numero}); "
                "valeu o da chave."
            )
    else:
        nota.numero = numero_escrito
        nota.serie = serie_escrita
        nota.fornecedor_cnpj = _cnpj_do_emitente(texto)
        nota.avisos.append("Não achei a chave de acesso no PDF: confira número, série e CNPJ.")

    nota.fornecedor_nome = _nome_do_emitente(texto, linhas)

    emissao = _valor_rotulado(linhas, re.compile(r"DATA\s+D[AE]\s+EMISS[ÃA]O", re.I), r"\d{2}/\d{2}/\d{4}")
    if not emissao:
        achado = re.search(r"EMISS[ÃA]O\s*:?\s*(\d{2}/\d{2}/\d{4})", texto, re.I)
        emissao = achado.group(1) if achado else ""
    nota.emissao = _data_br(emissao)

    total = _valor_rotulado(linhas, re.compile(r"VALOR\s+TOTAL\s+DA\s+NOTA", re.I), _NUM)
    if not total:
        achado = re.search(rf"VALOR\s+TOTAL\s*:?\s*(?:R\$\s*)?({_NUM})", texto, re.I)
        total = achado.group(1) if achado else ""
    nota.valor_total = numero_br(total)
    nota.valor_produtos = numero_br(
        _valor_rotulado(linhas, re.compile(r"VALOR\s+TOTAL\s+DOS\s+PRODUTOS", re.I), _NUM)
    )

    regioes = _regioes_de_itens(paginas)
    itens: list[ItemLido] = []
    for regiao in regioes:
        itens.extend(_itens_da_regiao(regiao))
    if not regioes:
        # DANFE sem o título do quadro: só a regra estrita, linha a linha
        # (a de reserva, solta pela página inteira, acharia trinca em
        # qualquer canto).
        for linha in linhas:
            achado = _ITEM.match(linha)
            if achado:
                lido = _item_da_linha(linha)
                if lido:
                    itens.append(lido[0])
    for numero, item in enumerate(itens, start=1):
        item.numero = numero
    nota.itens = itens
    return nota


# ======================================================================
# A CONFERÊNCIA DAS CONTAS
# ======================================================================
def conferir(nota: NotaLida) -> NotaLida:
    """As contas que a nota tem de fechar. O que não fecha vira aviso na tela."""
    for item in nota.itens:
        if item.quantidade <= 0:
            nota.avisos.append(f"Item {item.numero} ({item.descricao}): quantidade zero.")
        elif not bate(item.quantidade, item.valor_unitario, item.valor_total):
            nota.avisos.append(
                f"Item {item.numero} ({item.descricao}): {item.quantidade.normalize()} x "
                f"{item.valor_unitario.normalize()} não dá o total de {item.valor_total}."
            )
    soma = nota.soma_dos_itens
    if nota.valor_produtos is not None and soma != nota.valor_produtos:
        nota.avisos.append(
            f"A soma dos itens lidos (R$ {_br(soma)}) não bate com o total dos produtos da "
            f"nota (R$ {_br(nota.valor_produtos)}): confira se algum item ficou de fora."
        )
    if nota.valor_total is None:
        nota.valor_total = nota.valor_produtos if nota.valor_produtos is not None else soma
    if nota.chave and nota.fornecedor_cnpj and partes_da_chave(nota.chave)["cnpj"] != nota.fornecedor_cnpj:
        nota.avisos.append("O CNPJ do emitente não é o da chave de acesso. Confira a nota.")
    return nota


def _br(valor: Decimal) -> str:
    numero = Decimal(valor or 0).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    return f"{numero:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
