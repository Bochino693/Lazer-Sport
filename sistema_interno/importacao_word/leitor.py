"""O .docx aberto à mão: zipfile + xml.etree, sem biblioteca nova.

POR QUE NÃO python-docx. Ele não está instalado, e o que a importação
precisa é pouco e preciso: o texto de cada parágrafo e de cada célula, na
ordem em que aparecem, com um endereço estável. Um .docx é um zip com XML
dentro (`word/document.xml`, `word/header1.xml`...), e ler esse XML direto
deixa claro o que entra e o que fica de fora -- o que importa quando o
próximo passo é afirmar "este valor está escrito na célula T1L3C4".

O QUE ENTRA, NA ORDEM DE LEITURA DE QUEM ABRE O DOCUMENTO:
  * cabeçalho ("CAB-P1", "CAB-T1L1C2"),
  * corpo: parágrafos ("P1") e tabelas célula a célula ("T1L3C4" = tabela
    1, linha 3, coluna 4 -- a coluna é a da grade, então uma célula
    mesclada ocupa o número da primeira coluna que cobre),
  * caixas de texto, logo depois do parágrafo em que estão ancoradas
    ("CX-P1"),
  * rodapé ("ROD-P1").

O QUE FICA DE FORA, DE PROPÓSITO:
  * texto riscado no controle de alterações (`w:del`) -- foi apagado;
  * texto oculto (`w:vanish`) -- quem abre o Word não vê, e um preço
    antigo escondido não pode virar o preço da proposta;
  * a cópia de segurança das caixas de texto (`mc:Fallback`) -- o Word
    grava a mesma caixa duas vezes, em DrawingML e em VML, e ler as duas
    duplicaria cada item que estivesse dentro de uma.

Linha vazia não ganha id: o texto numerado é para ler, e mil "P" vazios
só atrapalham.
"""

from __future__ import annotations

import re
import zipfile
from io import BytesIO
from xml.etree import ElementTree as ET

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"


def _w(tag):
    return f"{{{W}}}{tag}"


#: O maior arquivo aceito. Orçamento com logotipo e fotos de brinquedo
#: passa de 2 MB com facilidade; 10 MB cobre catálogo com foto em cada
#: linha sem abrir a porta para o upload de qualquer coisa.
TAMANHO_MAXIMO = 10 * 1024 * 1024

#: Teto de cada XML DESCOMPACTADO. Um zip de 1 MB pode se expandir para
#: gigabytes (a "bomba de zip"); o texto de um orçamento cabe com folga.
XML_MAXIMO = 20 * 1024 * 1024

#: Teto do texto lido. Recusar é melhor que cortar: um documento cortado
#: em silêncio perderia justamente a última linha -- a do total.
CARACTERES_MAXIMOS = 120_000
LINHAS_MAXIMAS = 4000

_ESPACOS = re.compile(r"[ \t   ]+")


class ArquivoRecusado(Exception):
    """O arquivo não é um .docx que dê para ler. A mensagem vai para a tela."""


def _ligado(elemento) -> bool:
    """`<w:vanish/>` liga; `<w:vanish w:val="0"/>` desliga."""
    if elemento is None:
        return False
    return elemento.get(_w("val"), "true").lower() not in ("0", "false", "off")


def conferir_arquivo(nome: str, conteudo: bytes) -> str:
    """"docx" ou "pdf" -- ou a recusa, com uma frase que diz o que fazer.

    EXTENSÃO E CONTEÚDO TÊM DE CONCORDAR. A extensão diz o que a pessoa
    acha que enviou; os primeiros bytes dizem o que o arquivo é. Um .doc
    antigo renomeado para .docx continua sendo o formato antigo, e um
    "orçamento.pdf" que não começa com %PDF- não é PDF -- é outra coisa
    com nome de PDF, e não vai para a IA nem para o leitor.
    """
    if not conteudo:
        raise ArquivoRecusado("O arquivo chegou vazio. Escolha o .docx ou o PDF de novo.")
    if len(conteudo) > TAMANHO_MAXIMO:
        raise ArquivoRecusado(
            "O arquivo passa de 10 MB. Salve uma cópia sem as fotos (ou com "
            "as fotos compactadas) e importe de novo."
        )

    extensao = (nome or "").rsplit(".", 1)[-1].lower() if "." in (nome or "") else ""
    inicio = conteudo[:8]
    if inicio.startswith(b"\xd0\xcf\x11\xe0"):
        raise ArquivoRecusado(
            "Este é um .doc antigo (Word 97-2003), que não dá para ler aqui. "
            "Abra no Word, vá em Arquivo > Salvar como e escolha "
            "\"Documento do Word (.docx)\"; depois importe o .docx."
        )
    if inicio.startswith(b"{\\rtf"):
        raise ArquivoRecusado(
            "Este é um arquivo RTF. Abra no Word e salve como .docx (ou como PDF)."
        )
    if extensao == "pdf":
        if not inicio.startswith(b"%PDF-"):
            raise ArquivoRecusado(
                f"“{nome}” tem nome de PDF, mas o conteúdo não é de um PDF. Gere o PDF "
                "de novo (no Word: Arquivo > Salvar como > PDF) ou importe o .docx."
            )
        return "pdf"
    if extensao == "docx":
        if inicio.startswith(b"%PDF-"):
            raise ArquivoRecusado(
                f"“{nome}” tem nome de .docx, mas é um PDF. Renomeie para .pdf "
                "ou importe o .docx original."
            )
        if not inicio.startswith(b"PK"):
            raise ArquivoRecusado(
                f"“{nome}” não é um documento do Word (.docx) de verdade. Abra no Word, "
                "salve como .docx e importe de novo."
            )
        return "docx"
    if extensao == "doc":
        raise ArquivoRecusado(
            "Este é um .doc antigo (Word 97-2003), que não dá para ler aqui. "
            "Abra no Word, vá em Arquivo > Salvar como e escolha "
            "\"Documento do Word (.docx)\"; depois importe o .docx."
        )
    raise ArquivoRecusado(
        f"“{nome}” não é Word (.docx) nem PDF. Salve o orçamento num dos dois "
        "formatos e importe de novo."
    )


def _ler_parte(arquivo: zipfile.ZipFile, nome: str):
    """Lê um XML do zip com teto de tamanho e sem DTD.

    Documento do Word não tem DOCTYPE nem ENTITY. Recusar os dois antes
    de entregar ao parser fecha a porta da expansão de entidades -- o
    XML que se multiplica em memória até derrubar o servidor --, que é o
    único truque que um .docx forjado teria contra este leitor.
    """
    info = arquivo.getinfo(nome)
    if info.file_size > XML_MAXIMO:
        raise ArquivoRecusado(
            "O documento é grande demais para importar. Divida o orçamento "
            "em partes menores."
        )
    with arquivo.open(info) as fluxo:
        dados = fluxo.read(XML_MAXIMO + 1)
    if len(dados) > XML_MAXIMO:
        raise ArquivoRecusado(
            "O documento é grande demais para importar. Divida o orçamento "
            "em partes menores."
        )
    if b"<!DOCTYPE" in dados or b"<!ENTITY" in dados:
        raise ArquivoRecusado(
            "O arquivo tem uma estrutura que o Word não produz. Abra no Word, "
            "salve como .docx de novo e importe essa cópia."
        )
    try:
        return ET.fromstring(dados)
    except ET.ParseError as exc:
        raise ArquivoRecusado(
            "O .docx está corrompido e não abriu. Abra no Word, salve uma "
            "cópia e importe essa cópia."
        ) from exc


def _numero_da_parte(nome: str) -> int:
    achado = re.search(r"(\d+)\.xml$", nome)
    return int(achado.group(1)) if achado else 0


class _Leitor:
    """Anda pelo XML e enfileira as linhas, cada uma com o seu id."""

    def __init__(self):
        self.linhas: list[dict] = []
        self.paragrafos: dict[str, int] = {}
        self.tabelas: dict[str, int] = {}

    # ------------------------------------------------------------ blocos
    def bloco(self, elemento, prefixo: str, parte: str):
        for filho in elemento:
            tag = filho.tag
            if tag == _w("p"):
                self.paragrafo(filho, prefixo, parte)
            elif tag == _w("tbl"):
                self.tabela(filho, prefixo, parte)
            elif tag == _w("sdt"):
                # Controle de conteúdo (o "campo" de modelo do Word): o
                # que interessa é o que está dentro.
                conteudo = filho.find(_w("sdtContent"))
                if conteudo is not None:
                    self.bloco(conteudo, prefixo, parte)
            elif tag in (_w("customXml"), _w("ins"), _w("moveTo")):
                self.bloco(filho, prefixo, parte)
            elif tag == f"{{{MC}}}AlternateContent":
                escolha = filho.find(f"{{{MC}}}Choice")
                if escolha is not None:
                    self.bloco(escolha, prefixo, parte)

    def _texto(self, elemento):
        """Texto de um parágrafo e as caixas de texto que ele ancora."""
        pedacos: list[str] = []
        caixas = []

        def andar(no):
            for filho in no:
                tag = filho.tag
                if tag in (_w("pPr"), _w("rPr"), _w("del"), _w("moveFrom")):
                    # pPr guarda as PARADAS de tabulação (`w:tab` também),
                    # que não são texto; del/moveFrom é texto apagado.
                    continue
                if tag == f"{{{MC}}}Fallback":
                    continue
                if tag == _w("txbxContent"):
                    caixas.append(filho)
                    continue
                if tag == _w("r"):
                    propriedades = filho.find(_w("rPr"))
                    if propriedades is not None and _ligado(
                        propriedades.find(_w("vanish"))
                    ):
                        continue
                    andar(filho)
                    continue
                if tag == _w("t"):
                    pedacos.append(filho.text or "")
                elif tag in (_w("tab"), _w("ptab")):
                    pedacos.append(" ")
                elif tag in (_w("br"), _w("cr")):
                    pedacos.append("\n")
                elif tag == _w("noBreakHyphen"):
                    pedacos.append("-")
                else:
                    andar(filho)

        andar(elemento)
        return "".join(pedacos), caixas

    @staticmethod
    def _limpar(texto: str) -> str:
        return _ESPACOS.sub(" ", texto.replace("​", "")).strip()

    def _novo_id_paragrafo(self, prefixo: str) -> str:
        self.paragrafos[prefixo] = self.paragrafos.get(prefixo, 0) + 1
        return f"{prefixo}P{self.paragrafos[prefixo]}"

    def paragrafo(self, p, prefixo: str, parte: str):
        texto, caixas = self._texto(p)
        # Quebra de linha dentro do parágrafo (Shift+Enter) separa coisas
        # diferentes -- "Cliente: X" numa linha e "CPF: Y" na outra. Cada
        # uma ganha o seu id, para a fonte apontar a linha certa.
        for pedaco in texto.split("\n"):
            limpo = self._limpar(pedaco)
            if limpo:
                self.linhas.append({
                    "id": self._novo_id_paragrafo(prefixo),
                    "texto": limpo,
                    "parte": parte,
                    "tabela": "",
                    "linha": 0,
                    "coluna": 0,
                })
        for caixa in caixas:
            self.bloco(caixa, "CX-", "caixa")

    def tabela(self, tbl, prefixo: str, parte: str):
        self.tabelas[prefixo] = self.tabelas.get(prefixo, 0) + 1
        id_tabela = f"{prefixo}T{self.tabelas[prefixo]}"

        numero_linha = 0
        for tr in self._filhos(tbl, "tr"):
            numero_linha += 1
            coluna = 1
            propriedades = tr.find(_w("trPr"))
            if propriedades is not None:
                antes = propriedades.find(_w("gridBefore"))
                if antes is not None:
                    coluna += self._inteiro(antes.get(_w("val")), 0)

            for tc in self._filhos(tr, "tc"):
                propriedades_celula = tc.find(_w("tcPr"))
                largura = 1
                continuacao = False
                if propriedades_celula is not None:
                    vao = propriedades_celula.find(_w("gridSpan"))
                    if vao is not None:
                        largura = max(1, self._inteiro(vao.get(_w("val")), 1))
                    mescla = propriedades_celula.find(_w("vMerge"))
                    # vMerge sem valor (ou "continue") é a continuação de
                    # uma mesclagem vertical: o texto mora na de cima.
                    if mescla is not None and mescla.get(_w("val"), "continue") != "restart":
                        continuacao = True

                textos, aninhadas, caixas = [], [], []
                for filho in tc:
                    if filho.tag == _w("p"):
                        texto, caixas_do_paragrafo = self._texto(filho)
                        caixas.extend(caixas_do_paragrafo)
                        texto = " / ".join(
                            parte_limpa
                            for parte_limpa in (self._limpar(t) for t in texto.split("\n"))
                            if parte_limpa
                        )
                        if texto:
                            textos.append(texto)
                    elif filho.tag == _w("tbl"):
                        aninhadas.append(filho)
                    elif filho.tag == _w("sdt"):
                        conteudo = filho.find(_w("sdtContent"))
                        if conteudo is not None:
                            for neto in conteudo:
                                if neto.tag == _w("p"):
                                    texto, caixas_do_paragrafo = self._texto(neto)
                                    caixas.extend(caixas_do_paragrafo)
                                    texto = self._limpar(texto.replace("\n", " / "))
                                    if texto:
                                        textos.append(texto)

                texto_celula = " / ".join(textos)
                if texto_celula and not continuacao:
                    self.linhas.append({
                        "id": f"{id_tabela}L{numero_linha}C{coluna}",
                        "texto": texto_celula,
                        "parte": parte,
                        "tabela": id_tabela,
                        "linha": numero_linha,
                        "coluna": coluna,
                    })
                # Tabela dentro de célula é comum em modelo de orçamento:
                # a tabela de itens mora dentro da tabela de diagramação.
                # Ela vira uma tabela própria, com o seu cabeçalho, em vez
                # de virar texto corrido dentro da célula de fora.
                for interna in aninhadas:
                    self.tabela(interna, prefixo, parte)
                for caixa in caixas:
                    self.bloco(caixa, "CX-", "caixa")
                coluna += largura

    @staticmethod
    def _filhos(elemento, nome):
        """Filhos diretos com esse nome, atravessando sdt e customXml."""
        for filho in elemento:
            if filho.tag == _w(nome):
                yield filho
            elif filho.tag in (_w("sdt"), _w("customXml")):
                conteudo = filho.find(_w("sdtContent"))
                alvo = conteudo if conteudo is not None else filho
                for neto in alvo:
                    if neto.tag == _w(nome):
                        yield neto

    @staticmethod
    def _inteiro(valor, padrao):
        try:
            return int(valor)
        except (TypeError, ValueError):
            return padrao


def ler_docx(conteudo: bytes, nome: str = "documento.docx") -> list[dict]:
    """As linhas numeradas do documento, na ordem de leitura."""
    if conferir_arquivo(nome, conteudo) != "docx":
        raise ArquivoRecusado(f"“{nome}” não é um .docx.")
    try:
        arquivo = zipfile.ZipFile(BytesIO(conteudo))
    except zipfile.BadZipFile as exc:
        raise ArquivoRecusado(
            "O .docx está corrompido e não abriu. Abra no Word, salve uma "
            "cópia e importe essa cópia."
        ) from exc

    with arquivo:
        nomes = set(arquivo.namelist())
        if "word/document.xml" not in nomes:
            raise ArquivoRecusado(
                f"“{nome}” não tem o conteúdo de um documento do Word. Se for "
                "planilha ou apresentação, copie o orçamento para o Word e "
                "salve como .docx."
            )

        leitor = _Leitor()
        cabecalhos = sorted(
            (n for n in nomes if re.fullmatch(r"word/header\d*\.xml", n)),
            key=_numero_da_parte,
        )
        rodapes = sorted(
            (n for n in nomes if re.fullmatch(r"word/footer\d*\.xml", n)),
            key=_numero_da_parte,
        )

        def parte_sem_repetir(nome_parte, prefixo, rotulo, vistos):
            # O Word guarda até três cabeçalhos (primeira página, pares e
            # padrão) e quase sempre os três dizem a mesma coisa. Repetir
            # triplicaria o CNPJ da empresa no texto -- e a chance de ele
            # ser lido como se fosse o do cliente.
            antes = len(leitor.linhas)
            contadores = (dict(leitor.paragrafos), dict(leitor.tabelas))
            leitor.bloco(_ler_parte(arquivo, nome_parte), prefixo, rotulo)
            conteudo_parte = tuple(l["texto"] for l in leitor.linhas[antes:])
            if not conteudo_parte or conteudo_parte in vistos:
                del leitor.linhas[antes:]
                leitor.paragrafos, leitor.tabelas = contadores
                return
            vistos.add(conteudo_parte)

        vistos_cabecalho: set = set()
        for nome_parte in cabecalhos:
            parte_sem_repetir(nome_parte, "CAB-", "cabecalho", vistos_cabecalho)

        documento = _ler_parte(arquivo, "word/document.xml")
        corpo = documento.find(_w("body"))
        if corpo is not None:
            leitor.bloco(corpo, "", "corpo")

        vistos_rodape: set = set()
        for nome_parte in rodapes:
            parte_sem_repetir(nome_parte, "ROD-", "rodape", vistos_rodape)

    linhas = leitor.linhas
    if not any(l["parte"] in ("corpo", "caixa") for l in linhas):
        raise ArquivoRecusado(
            "O documento não tem texto para ler. Se o orçamento é uma imagem "
            "colada no Word (foto ou captura de tela), digite o conteúdo ou "
            "peça o arquivo original."
        )
    if len(linhas) > LINHAS_MAXIMAS or sum(len(l["texto"]) for l in linhas) > CARACTERES_MAXIMOS:
        raise ArquivoRecusado(
            "O documento é longo demais para um orçamento (mais de "
            f"{CARACTERES_MAXIMOS // 1000} mil caracteres). Importe só a "
            "parte do orçamento, sem anexos e catálogos."
        )
    return linhas


# ======================================================================
# PDF: o texto vem da transcrição da IA, no mesmo formato de linhas
# ======================================================================
#: Teto de páginas de um PDF de orçamento. A API aceita muito mais; um
#: orçamento de cem páginas é catálogo, e o custo e a espera crescem com
#: cada página.
PAGINAS_MAXIMAS_PDF = 100
_ID_TRANSCRITO = re.compile(r"^(CAB-|ROD-|CX-)?(?:P(\d+)|T(\d+)L(\d+)C(\d+))$")


def paginas_do_pdf(conteudo: bytes) -> int:
    """Quantas páginas o PDF declara (0 quando não dá para contar sem abrir).

    Conta os objetos "/Type /Page" -- e não "/Pages", que é a árvore. PDF
    com páginas dentro de fluxo comprimido devolve 0, e aí o limite fica
    por conta do tamanho do arquivo.
    """
    return len(re.findall(rb"/Type\s*/Page(?![s\w])", conteudo or b""))


def conferir_pdf(nome: str, conteudo: bytes) -> None:
    if conferir_arquivo(nome, conteudo) != "pdf":
        raise ArquivoRecusado(f"“{nome}” não é um PDF.")
    if b"%%EOF" not in conteudo:
        raise ArquivoRecusado(
            f"“{nome}” parece um PDF cortado (o arquivo não termina). Baixe ou gere "
            "o PDF de novo e importe outra vez."
        )
    if paginas_do_pdf(conteudo) > PAGINAS_MAXIMAS_PDF:
        raise ArquivoRecusado(
            f"O PDF tem mais de {PAGINAS_MAXIMAS_PDF} páginas. Importe só as páginas do "
            "orçamento, sem catálogo e anexos."
        )


def linhas_transcritas(transcricao: list[dict]) -> list[dict]:
    """A transcrição do PDF feita pela IA, no formato das linhas do .docx.

    O PDF não tem as tags do Word que dizem "isto é uma célula": quem lê a
    página e separa parágrafo de célula é a IA, com os mesmos ids (P12,
    T1L3C4, CAB-P1). Aqui só passa o que tem id no formato certo e texto,
    e cada id uma vez -- citação a um id que não passou não acha a fonte,
    e o valor citado não entra.
    """
    linhas: list[dict] = []
    vistos: set[str] = set()
    for item in transcricao or []:
        identificador = str(item.get("id") or "").strip().strip("[]").upper()
        texto = _Leitor._limpar(str(item.get("texto") or "").replace("\n", " / "))
        achado = _ID_TRANSCRITO.match(identificador)
        if not achado or not texto or identificador in vistos:
            continue
        vistos.add(identificador)
        prefixo = achado.group(1) or ""
        linha = {
            "id": identificador,
            "texto": texto,
            "parte": {"CAB-": "cabecalho", "ROD-": "rodape", "CX-": "caixa"}.get(prefixo, "corpo"),
            "tabela": "", "linha": 0, "coluna": 0,
        }
        if achado.group(3):
            linha.update(tabela=f"{prefixo}T{achado.group(3)}", linha=int(achado.group(4)),
                         coluna=int(achado.group(5)))
        linhas.append(linha)
    if len(linhas) > LINHAS_MAXIMAS or sum(len(l["texto"]) for l in linhas) > CARACTERES_MAXIMOS:
        raise ArquivoRecusado(
            "O PDF é longo demais para um orçamento. Importe só as páginas do orçamento."
        )
    return linhas


# ======================================================================
# PDF COM TEXTO: lido aqui mesmo, sem IA
# ======================================================================
class PdfSemTexto(ArquivoRecusado):
    """PDF que é imagem (digitalização, foto): não há texto para ler aqui."""


MENSAGEM_PDF_IMAGEM = (
    "Este PDF é uma imagem (digitalização ou foto da página), e não dá para ler o texto "
    "dele. Envie o arquivo do Word, ou um PDF salvo direto do Word ou do sistema que fez "
    "o orçamento."
)
_SEGMENTO = re.compile(r"\S+(?: \S+)*")


def _segmentos(linha: str) -> list[tuple[int, int, str]]:
    """Pedaços separados por dois ou mais espaços, com a posição de cada um.

    É assim que o texto do PDF em "layout" mostra as colunas: "Pula-pula"
    e "R$ 1.234,00" na mesma altura viram dois pedaços com dez espaços
    entre eles, e a posição diz a coluna.
    """
    return [(achado.start(), achado.end(), achado.group(0)) for achado in _SEGMENTO.finditer(linha)]


def _linhas_do_pdf(paginas: list[str]) -> list[dict]:
    """O texto das páginas no mesmo formato das linhas do .docx.

    Tabela de itens: o cabeçalho é reconhecido pelos nomes das colunas
    (Descrição, Qtd, Valor unitário...), e cada linha abaixo vira células
    pela posição -- célula quebrada em várias linhas (descrição comprida
    numa coluna estreita) é juntada de volta. Linha "Rótulo   valor" sem
    dois-pontos (ficha de cadastro) vira par de células, como no Word.
    Texto que se repete igual em todas as páginas é cabeçalho ou rodapé
    e entra uma vez só.
    """
    from .deterministica import _mapear_cabecalho, campo_do_rotulo

    repetidas = set()
    if len(paginas) >= 2:
        contagem: dict[str, int] = {}
        for pagina in paginas:
            for texto in {_ESPACOS.sub(" ", l).strip() for l in pagina.splitlines() if l.strip()}:
                contagem[texto] = contagem.get(texto, 0) + 1
        repetidas = {texto for texto, vezes in contagem.items() if vezes == len(paginas)}

    linhas: list[dict] = []
    vistas_repetidas: set[str] = set()
    paragrafos = 0
    tabelas = 0
    tabela = None  # {"id", "colunas": [(inicio, fim)], "linha": n, "ultima": {coluna: indice em linhas}}

    def nova_celula(numero_linha, coluna, texto):
        linhas.append({
            "id": f"{tabela['id']}L{numero_linha}C{coluna}", "texto": texto, "parte": "corpo",
            "tabela": tabela["id"], "linha": numero_linha, "coluna": coluna,
        })
        return len(linhas) - 1

    def coluna_de(inicio, fim):
        centro = (inicio + fim) / 2
        colunas = tabela["colunas"]
        for posicao in range(len(colunas)):
            limite = (colunas[posicao][1] + colunas[posicao + 1][0]) / 2 if posicao + 1 < len(colunas) else 10**6
            if centro < limite:
                return posicao + 1
        return len(colunas)

    for numero_pagina, pagina in enumerate(paginas):
        texto_linhas = pagina.splitlines()
        for posicao_linha, bruta in enumerate(texto_linhas):
            limpa = _ESPACOS.sub(" ", bruta).strip()
            if not limpa:
                continue
            if limpa in repetidas:
                if limpa in vistas_repetidas:
                    continue
                vistas_repetidas.add(limpa)
                parte = "cabecalho" if posicao_linha < len(texto_linhas) / 2 else "rodape"
                paragrafos += 1
                linhas.append({"id": f"{'CAB' if parte == 'cabecalho' else 'ROD'}-P{paragrafos}",
                               "texto": limpa, "parte": parte, "tabela": "", "linha": 0, "coluna": 0})
                continue
            pedacos = _segmentos(bruta)

            if tabela is not None:
                if len(pedacos) >= 2:
                    tabela["linha"] += 1
                    celulas: dict[int, list[str]] = {}
                    for inicio, fim, texto in pedacos:
                        celulas.setdefault(coluna_de(inicio, fim), []).append(texto)
                    tabela["ultima"] = {
                        coluna: nova_celula(tabela["linha"], coluna, " ".join(textos))
                        for coluna, textos in sorted(celulas.items())
                    }
                    continue
                inicio, fim, texto = pedacos[0]
                coluna = coluna_de(inicio, fim)
                colunas = tabela["colunas"]
                # Continuação cabe na coluna: começa nela e termina antes
                # da próxima. Um parágrafo depois da tabela atravessa várias.
                dentro = colunas[coluna - 1][0] - 2 <= inicio and (
                    coluna == len(colunas) or fim <= colunas[coluna][0] + 2
                )
                if dentro and coluna in tabela["ultima"] and not re.search(r"R\$|\d+,\d{2}", texto):
                    # Continuação da célula de cima: "Cama elástica 3" /
                    # "m com rede de" / "proteção".
                    linhas[tabela["ultima"][coluna]]["texto"] += " " + texto
                    continue
                tabela = None

            celulas_cabecalho = {i + 1: {"texto": texto} for i, (_, _, texto) in enumerate(pedacos)}
            if len(pedacos) >= 3 and _mapear_cabecalho(celulas_cabecalho):
                tabelas += 1
                tabela = {"id": f"T{tabelas}", "colunas": [(a, b) for a, b, _ in pedacos],
                          "linha": 1, "ultima": {}}
                for coluna, (_, _, texto) in enumerate(pedacos, start=1):
                    nova_celula(1, coluna, texto)
                continue
            if len(pedacos) == 2 and campo_do_rotulo(pedacos[0][2].rstrip(" :")):
                # "Nome          Marina Souza": a ficha em duas colunas.
                tabelas += 1
                tabela_par = {"id": f"T{tabelas}", "colunas": [], "linha": 1, "ultima": {}}
                anterior, tabela = tabela, tabela_par
                nova_celula(1, 1, pedacos[0][2])
                nova_celula(1, 2, pedacos[1][2])
                tabela = anterior
                continue
            paragrafos += 1
            linhas.append({"id": f"P{paragrafos}", "texto": limpa, "parte": "corpo",
                           "tabela": "", "linha": 0, "coluna": 0})
    return linhas


def ler_pdf_local(conteudo: bytes, nome: str = "documento.pdf") -> list[dict]:
    """As linhas de um PDF que tem texto -- sem IA, como o .docx.

    PDF digitalizado (só imagem) levanta `PdfSemTexto`, com uma frase que
    diz o que enviar no lugar.
    """
    conferir_pdf(nome, conteudo)
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover -- está no requirements
        raise ArquivoRecusado("Não consegui abrir PDFs agora. Envie o arquivo do Word.") from exc
    try:
        documento = PdfReader(BytesIO(conteudo))
        if documento.is_encrypted:
            try:
                documento.decrypt("")
            except Exception as exc:  # noqa: BLE001
                raise ArquivoRecusado(
                    "O PDF está protegido por senha. Salve uma cópia sem senha, ou envie o "
                    "arquivo do Word."
                ) from exc
        paginas = []
        for pagina in documento.pages[:PAGINAS_MAXIMAS_PDF]:
            paginas.append(pagina.extract_text(extraction_mode="layout") or "")
    except ArquivoRecusado:
        raise
    except Exception as exc:  # noqa: BLE001 -- PDF quebrado chega de todo jeito
        raise ArquivoRecusado(
            "O PDF está corrompido e não abriu. Gere o PDF de novo ou envie o arquivo do Word."
        ) from exc
    if len(re.sub(r"\s", "", "".join(paginas))) < 20:
        raise PdfSemTexto(MENSAGEM_PDF_IMAGEM)
    linhas = _linhas_do_pdf(paginas)
    if len(linhas) > LINHAS_MAXIMAS or sum(len(l["texto"]) for l in linhas) > CARACTERES_MAXIMOS:
        raise ArquivoRecusado(
            "O PDF é longo demais para um orçamento. Importe só as páginas do orçamento."
        )
    return linhas


def mapa_de_linhas(linhas: list[dict]) -> dict[str, dict]:
    return {linha["id"]: linha for linha in linhas}


ROTULO_DA_PARTE = {
    "cabecalho": "CABEÇALHO DO DOCUMENTO",
    "corpo": "CORPO DO DOCUMENTO",
    "caixa": "CORPO DO DOCUMENTO",
    "rodape": "RODAPÉ DO DOCUMENTO",
}


def texto_numerado(linhas: list[dict]) -> str:
    """O documento como texto, cada linha e cada célula com o seu id.

    Uma linha de tabela fica numa linha só, célula ao lado de célula:

        [T1L2C1] Cama elástica 3 m | [T1L2C2] 2 | [T1L2C3] R$ 280,00

    É assim que quem lê -- a IA ou uma pessoa conferindo -- enxerga a
    tabela como tabela, e ainda consegue citar a célula exata.
    """
    saida: list[str] = []
    secao = None
    linha_atual = None
    tabela_atual = None
    pendentes: list[str] = []

    def despejar():
        if pendentes:
            saida.append("  " + " | ".join(pendentes))
            pendentes.clear()

    for linha in linhas:
        rotulo = ROTULO_DA_PARTE.get(linha["parte"], "CORPO DO DOCUMENTO")
        if rotulo != secao:
            despejar()
            saida.append(f"=== {rotulo} ===")
            secao = rotulo
            tabela_atual = None
        if linha["tabela"]:
            if linha["tabela"] != tabela_atual:
                despejar()
                saida.append(f"Tabela {linha['tabela']}:")
                tabela_atual = linha["tabela"]
                linha_atual = None
            if linha["linha"] != linha_atual:
                despejar()
                linha_atual = linha["linha"]
            pendentes.append(f"[{linha['id']}] {linha['texto']}")
        else:
            despejar()
            tabela_atual = None
            saida.append(f"[{linha['id']}] {linha['texto']}")
    despejar()
    return "\n".join(saida)
