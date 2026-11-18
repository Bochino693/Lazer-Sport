"""A conferência de um documento enviado: o CONTEÚDO, e não só o nome.

Um "rg.pdf" que é um executável renomeado, um "comprovante.jpg" que é uma
página HTML, um PDF com JavaScript dentro: nada disso entra. A conferência
lê os primeiros bytes (a assinatura de cada formato), abre o arquivo com a
biblioteca do formato (pypdf para PDF, Pillow para imagem) e só então
aceita. A extensão do nome tem de bater com o que o arquivo É.

Aceitos: PDF, JPG, PNG e WEBP, até 10 MB.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import logging
import re
import unicodedata
from dataclasses import dataclass

from django.core.exceptions import ValidationError

TAMANHO_MAXIMO = 10 * 1024 * 1024
#: Uma foto de documento de celular tem 12 a 50 megapixels; acima de 80
#: é bomba de descompressão, não documento.
PIXELS_MAXIMOS = 80_000_000

TIPOS = {
    "pdf": ("application/pdf", (".pdf",)),
    "jpeg": ("image/jpeg", (".jpg", ".jpeg")),
    "png": ("image/png", (".png",)),
    "webp": ("image/webp", (".webp",)),
}
EXTENSAO_PADRAO = {"pdf": ".pdf", "jpeg": ".jpg", "png": ".png", "webp": ".webp"}
ACEITOS_NO_CAMPO = ".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp"

#: O que não pode existir num PDF de documento pessoal: script e ação que
#: abre programa ou arquivo ao abrir o PDF. Procurados nos bytes (marcas
#: longas o bastante para não aparecer por acaso dentro de um fluxo
#: comprimido) e no catálogo, já lido pelo pypdf (pega o que está dentro de
#: fluxos de objetos).
PDF_PROIBIDO = (b"/JavaScript", b"/Launch", b"/EmbeddedFile")
#: Ação automática (ao abrir o PDF) que só se aceita se for "ir para a
#: página": o Word e o "Imprimir em PDF" põem um /OpenAction de destino.
ACOES_PROIBIDAS = ("/JavaScript", "/Launch", "/ImportData", "/SubmitForm", "/URI", "/GoToR", "/GoToE")


def _obj(valor):
    return valor.get_object() if hasattr(valor, "get_object") else valor


def _acao_ativa(acao) -> bool:
    acao = _obj(acao)
    if not hasattr(acao, "get"):
        return False  # destino de página: [página /Fit]
    if str(acao.get("/S", "")) in ACOES_PROIBIDAS:
        return True
    seguinte = acao.get("/Next")
    if seguinte is None:
        return False
    seguinte = _obj(seguinte)
    if isinstance(seguinte, list):
        return any(_acao_ativa(item) for item in seguinte)
    return _acao_ativa(seguinte)


@dataclass(frozen=True)
class ArquivoConferido:
    formato: str
    tipo_conteudo: str
    extensao: str
    tamanho: int
    sha256: str
    nome_original: str
    dados: bytes


def nome_seguro(nome: str) -> str:
    """O nome que a pessoa deu ao arquivo, só para mostrar: sem caminho nem controle."""
    nome = (nome or "").replace("\\", "/").rsplit("/", 1)[-1]
    nome = unicodedata.normalize("NFC", nome)
    nome = "".join(c for c in nome if c.isprintable() and c not in '<>:"|?*')
    nome = re.sub(r"\s+", " ", nome).strip(" .")
    return (nome or "documento")[:150]


def _formato_pela_assinatura(cabeca: bytes) -> str | None:
    if b"%PDF-" in cabeca[:1024]:
        return "pdf"
    if cabeca.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if cabeca.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if cabeca[:4] == b"RIFF" and cabeca[8:12] == b"WEBP":
        return "webp"
    return None


@contextlib.contextmanager
def _pypdf_calado():
    """O pypdf avisa no log cada PDF torto que lê; aqui o aviso vira a nossa frase."""
    registro = logging.getLogger("pypdf")
    antes = registro.level
    registro.setLevel(logging.ERROR)
    try:
        yield
    finally:
        registro.setLevel(antes)


def _conferir_pdf(dados: bytes):
    for marca in PDF_PROIBIDO:
        if marca in dados:
            raise ValidationError(
                "Este PDF tem script ou anexo embutido e não pode ser guardado. "
                "Imprima em PDF de novo (ou escaneie) e envie.",
                code="pdf_ativo",
            )
    try:
        from pypdf import PdfReader

        with _pypdf_calado():
            leitor = PdfReader(io.BytesIO(dados), strict=False)
            if leitor.is_encrypted:
                raise ValidationError(
                    "O PDF está protegido por senha. Envie a versão sem senha.",
                    code="pdf_senha",
                )
            paginas = len(leitor.pages)
        if paginas < 1:
            raise ValidationError("O PDF não tem nenhuma página.", code="pdf_vazio")
        catalogo = _obj(leitor.trailer.get("/Root")) or {}
        nomes = _obj(catalogo.get("/Names")) or {}
        extras = _obj(catalogo.get("/AA")) or {}
        ativo = (
            _acao_ativa(catalogo.get("/OpenAction"))
            or any(_acao_ativa(acao) for acao in extras.values())
            or any(chave in nomes for chave in ("/JavaScript", "/EmbeddedFiles"))
        )
        if ativo:
            raise ValidationError(
                "Este PDF tem script ou anexo embutido e não pode ser guardado. "
                "Imprima em PDF de novo (ou escaneie) e envie.",
                code="pdf_ativo",
            )
    except ValidationError:
        raise
    except Exception as erro:  # noqa: BLE001 -- qualquer falha de leitura é PDF quebrado
        raise ValidationError(
            "Não foi possível abrir este PDF: o arquivo parece corrompido.",
            code="pdf_corrompido",
        ) from erro


def _conferir_imagem(dados: bytes, formato: str):
    from PIL import Image

    try:
        with Image.open(io.BytesIO(dados)) as imagem:
            achado = (imagem.format or "").lower()
            largura, altura = imagem.size
            imagem.verify()
    except Image.DecompressionBombError as erro:
        raise ValidationError("A imagem é grande demais para um documento.", code="imagem_bomba") from erro
    except Exception as erro:  # noqa: BLE001
        raise ValidationError(
            "Não foi possível abrir esta imagem: o arquivo parece corrompido.",
            code="imagem_corrompida",
        ) from erro
    if achado != formato:
        raise ValidationError("O conteúdo da imagem não corresponde ao formato.", code="imagem_formato")
    if largura * altura > PIXELS_MAXIMOS:
        raise ValidationError("A imagem é grande demais para um documento.", code="imagem_bomba")
    if largura < 64 or altura < 64:
        raise ValidationError("A imagem é pequena demais para ler o documento.", code="imagem_pequena")


def conferir(arquivo) -> ArquivoConferido:
    """Lê o envio inteiro (até 10 MB), confere e devolve o que gravar.

    Levanta ValidationError com uma frase que a pessoa entende.
    """
    if arquivo is None:
        raise ValidationError("Escolha o arquivo do documento.", code="vazio")
    tamanho_declarado = getattr(arquivo, "size", None)
    if tamanho_declarado is not None and tamanho_declarado > TAMANHO_MAXIMO:
        raise ValidationError("O arquivo passa de 10 MB. Envie uma versão menor (ou escaneie em PDF).", code="grande")

    if hasattr(arquivo, "seek"):
        arquivo.seek(0)
    dados = arquivo.read(TAMANHO_MAXIMO + 1)
    if len(dados) > TAMANHO_MAXIMO:
        raise ValidationError("O arquivo passa de 10 MB. Envie uma versão menor (ou escaneie em PDF).", code="grande")
    if not dados:
        raise ValidationError("O arquivo está vazio.", code="vazio")

    nome = nome_seguro(getattr(arquivo, "name", "") or "")
    extensao = ("." + nome.rsplit(".", 1)[-1].lower()) if "." in nome else ""

    formato = _formato_pela_assinatura(dados[:2048])
    if formato is None:
        raise ValidationError(
            "Formato não aceito. Envie PDF, JPG, PNG ou WEBP.",
            code="formato",
        )
    tipo_conteudo, extensoes = TIPOS[formato]
    if extensao and extensao not in extensoes:
        raise ValidationError(
            f"O nome diz “{extensao}”, mas o arquivo é {formato.upper()}. "
            "Confira se escolheu o arquivo certo.",
            code="extensao",
        )

    if formato == "pdf":
        _conferir_pdf(dados)
    else:
        _conferir_imagem(dados, formato)

    return ArquivoConferido(
        formato=formato,
        tipo_conteudo=tipo_conteudo,
        extensao=EXTENSAO_PADRAO[formato],
        tamanho=len(dados),
        sha256=hashlib.sha256(dados).hexdigest(),
        nome_original=nome,
        dados=dados,
    )
