"""O arquivo aberto: .docx, PDF com texto e .txt, nas mesmas linhas numeradas.

O .docx e o PDF passam pelo leitor do orçamento (`importacao_word/leitor`):
o Word com zipfile + xml.etree, o PDF com o pypdf, aqui no servidor. O .txt
(o que sai de sistema antigo, de e-mail copiado, do bloco de notas) é lido
como uma página de PDF em "layout": duas ou mais colunas separadas por
espaço viram células, e a tabela de peças é remontada pelas colunas.

AS RECUSAS DIZEM O QUE FAZER, em português de quem está no balcão, e nunca
falam de orçamento (a mensagem do leitor do orçamento é ajustada aqui).
PDF que é foto (digitalização) e imagem (.jpg, .png) não têm texto: aqui
não há OCR, e o documento do cliente não sai do servidor para ser lido
fora. A recusa diz isso e pede o arquivo com texto.

O REPETIDO. Dois SHA-256: o do arquivo (o mesmo arquivo de novo) e o do
TEXTO normalizado -- só letras e números, sem acento --, que pega o mesmo
documento salvo de novo (o Word muda os bytes a cada "Salvar") e, quase
sempre, o PDF exportado do mesmo Word.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from io import BytesIO

from ..importacao_word import leitor
from . import campos

TAMANHO_MAXIMO = leitor.TAMANHO_MAXIMO
TXT_MAXIMO = 2 * 1024 * 1024

ArquivoRecusado = leitor.ArquivoRecusado

MENSAGEM_PDF_IMAGEM = (
    "Este PDF é uma imagem (digitalização ou foto da página): não há texto para ler, e o "
    "documento do cliente não sai do servidor para ser lido por fora. Envie o Word, ou um PDF "
    "salvo direto do Word ou do sistema que fez a O.S."
)
MENSAGEM_IMAGEM = (
    "“{nome}” é uma foto ou imagem: não há texto para ler nela. Envie o Word (.docx), um PDF "
    "salvo direto do Word ou do sistema, ou um .txt."
)
_IMAGENS = ("jpg", "jpeg", "png", "gif", "bmp", "heic", "heif", "webp", "tif", "tiff")
_PLANILHAS = ("xls", "xlsx", "ods", "csv")


def _para_os(mensagem: str) -> str:
    """A recusa do leitor do orçamento, falando de O.S."""
    trocas = (
        ("das páginas do orçamento", "das páginas da O.S."),
        ("só a parte do orçamento", "só a parte da O.S."),
        ("um orçamento", "uma O.S."),
        ("Divida o orçamento", "Divida o documento"),
        ("o orçamento", "o documento"),
        ("O orçamento", "O documento"),
        ("Salve o orçamento", "Salve o documento"),
        ("que fez o orçamento", "que fez a O.S."),
    )
    for velho, novo in trocas:
        mensagem = mensagem.replace(velho, novo)
    return mensagem


def formato(nome: str, conteudo: bytes) -> str:
    """"docx", "pdf" ou "txt" -- ou a recusa, com a frase do que fazer."""
    if not conteudo:
        raise ArquivoRecusado("O arquivo chegou vazio. Escolha o documento de novo.")
    extensao = (nome or "").rsplit(".", 1)[-1].lower() if "." in (nome or "") else ""
    if extensao in _IMAGENS:
        raise ArquivoRecusado(MENSAGEM_IMAGEM.format(nome=nome))
    if extensao in _PLANILHAS:
        raise ArquivoRecusado(
            f"“{nome}” é uma planilha. Copie a O.S. para o Word e salve como .docx (ou PDF)."
        )
    if extensao == "txt":
        if len(conteudo) > TXT_MAXIMO:
            raise ArquivoRecusado("O .txt passa de 2 MB: não parece uma O.S. Envie só a parte da O.S.")
        if b"\x00" in conteudo[:4096] or conteudo[:4] in (b"PK\x03\x04", b"%PDF"):
            raise ArquivoRecusado(f"“{nome}” tem nome de .txt, mas não é texto. Envie o arquivo original.")
        return "txt"
    if extensao not in ("docx", "pdf", "doc"):
        raise ArquivoRecusado(
            f"“{nome}” não é Word (.docx), PDF nem .txt. Salve o documento num desses formatos e "
            "envie de novo."
        )
    try:
        return leitor.conferir_arquivo(nome, conteudo)
    except ArquivoRecusado as exc:
        raise ArquivoRecusado(_para_os(str(exc))) from exc


def _decodificar(conteudo: bytes) -> str:
    for codificacao in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return conteudo.decode(codificacao)
        except UnicodeDecodeError:
            continue
    return conteudo.decode("utf-8", "replace")


def _linhas_do_texto(paginas: list[str]) -> list[dict]:
    preparadas = [campos.preparar_texto_corrido(pagina) for pagina in paginas]
    return leitor._linhas_do_pdf(preparadas)  # noqa: SLF001 -- a mesma remontagem do PDF, de propósito


def _paginas_do_pdf(nome: str, conteudo: bytes) -> list[str]:
    try:
        leitor.conferir_pdf(nome, conteudo)
    except ArquivoRecusado as exc:
        raise ArquivoRecusado(_para_os(str(exc))) from exc
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
                    "O PDF está protegido por senha. Salve uma cópia sem senha, ou envie o Word."
                ) from exc
        paginas = [
            pagina.extract_text(extraction_mode="layout") or ""
            for pagina in documento.pages[:leitor.PAGINAS_MAXIMAS_PDF]
        ]
    except ArquivoRecusado:
        raise
    except Exception as exc:  # noqa: BLE001 -- PDF quebrado chega de todo jeito
        raise ArquivoRecusado(
            "O PDF está corrompido e não abriu. Gere o PDF de novo ou envie o Word."
        ) from exc
    if len(re.sub(r"\s", "", "".join(paginas))) < 20:
        raise ArquivoRecusado(MENSAGEM_PDF_IMAGEM)
    return paginas


def _conferir_tamanho(linhas: list[dict]):
    if not any(l["parte"] in ("corpo", "caixa") for l in linhas):
        raise ArquivoRecusado(
            "O documento não tem texto para ler. Se a O.S. é uma imagem colada no Word (foto ou "
            "captura de tela), digite o conteúdo ou peça o arquivo original."
        )
    if len(linhas) > leitor.LINHAS_MAXIMAS or sum(len(l["texto"]) for l in linhas) > leitor.CARACTERES_MAXIMOS:
        raise ArquivoRecusado(
            "O documento é longo demais para uma O.S. Envie só a parte da O.S., sem anexos e catálogos."
        )


def ler(nome: str, conteudo: bytes) -> dict:
    """{"formato", "linhas", "sha256", "texto_sha256"} -- ou ArquivoRecusado."""
    tipo = formato(nome, conteudo)
    if tipo == "docx":
        try:
            linhas = leitor.ler_docx(conteudo, nome)
        except ArquivoRecusado as exc:
            raise ArquivoRecusado(_para_os(str(exc))) from exc
    elif tipo == "pdf":
        linhas = _linhas_do_texto(_paginas_do_pdf(nome, conteudo))
    else:
        linhas = _linhas_do_texto([_decodificar(conteudo)])
    _conferir_tamanho(linhas)
    return {
        "formato": tipo,
        "linhas": linhas,
        "sha256": hashlib.sha256(conteudo).hexdigest(),
        "texto_sha256": hash_do_texto(linhas),
    }


def hash_do_texto(linhas: list[dict]) -> str:
    """O SHA-256 do texto: só letras e números, sem acento e em minúsculas."""
    texto = "".join(l["texto"] for l in linhas)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    texto = re.sub(r"[^a-z0-9]", "", texto)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest() if len(texto) >= 20 else ""
