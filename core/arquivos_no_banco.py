"""OS ARQUIVOS MORAM NO NOSSO BANCO (LEIA-ME-V10, seção 130).

O QUE ACONTECEU. Em 23/11/2026 o Cloudinary desativou a conta
("401 cloud_name dgikjmki8 is disabled"): toda foto que só existia lá
sumiu do site, e TODO ENVIO de arquivo (a foto de um produto, o cartão de
ponto do RH, o documento de uma O.S., a nota fiscal) voltava 500. O dono:
"isso não pode ser vulnerável, eu desenvolvo pras empresas, deve ser as
fotos fixas e sempre disponíveis, sem deixar os micro serviços quebrar
tudo ou atrapalhar tudo."

A DECISÃO. O banco (PostgreSQL do Supabase) já é o ponto único de verdade
do sistema: sem ele nada abre. Guardar os arquivos nele não acrescenta um
ponto de falha -- tira um. O Cloudinary vira só LEGADO: os nomes antigos
continuam montando o endereço dele (sem ida à rede), e o espelho
(`core/espelho_midia.py`) copia cada um para cá assim que a conta voltar.

COMO É GUARDADO. Uma linha de `ArquivoNoBanco` por arquivo: o nome (que
SEMPRE começa com "banco/" seguido do caminho de antes -- as conferências
antigas pelo nome continuam valendo), os bytes, o tipo, o tamanho, o
SHA-256 e se é público. A foto grande (mais de 2400 px ou de ~700 KB) entra
como WebP de até 2400 px, boa qualidade: o banco guarda o que o site usa.

COMO É ENTREGUE. `/midia/banco/<caminho>` nos dois endereços (www. e
interno.), atendido por `MidiaNoBancoMiddleware` ANTES da sessão, do login e
dos registros -- uma foto não custa consulta de sessão nem de usuário. Só a
linha pública sai; a privada (documento do RH, da O.S., nota) só pelas
views de sempre, que conferem a permissão. Cache de um ano
(`immutable`: o nome nunca troca de conteúdo), ETag = SHA-256, `?w=` com as
larguras da lista (WebP reduzido pelo Pillow), e a cópia no disco da
instância: a segunda vez que alguém pede a foto, o banco nem fica sabendo.

O ENDEREÇO É CONTA, NÃO CONSULTA. `url()` monta o endereço sem ir ao banco
nem à rede: uma página com cem fotos não faz cem consultas.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import mimetypes
import os
import posixpath
import secrets
import string
import tempfile
import threading
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible

from sistema_interno.utils import ErroDeFormulario

log = logging.getLogger("lazer.midia")

#: Todo nome guardado aqui começa assim (e só os daqui).
PREFIXO = "banco/"
#: O endereço público: /midia/banco/<caminho>.
ROTA = "/midia/"

#: As larguras que `?w=` aceita. Fora da lista, 404 (um robô não gera mil variantes).
LARGURAS = (160, 240, 320, 480, 720, 960, 1200, 1600)
#: A foto maior que isto (lado ou peso) entra como WebP de até LADO_MAXIMO px.
LADO_MAXIMO = 2400
PESO_MAXIMO = 700 * 1024
QUALIDADE = 86
QUALIDADE_DA_VARIANTE = 82
TIPOS_QUE_SE_REDUZEM = ("image/jpeg", "image/png", "image/webp")

#: O que pode abrir no navegador vindo do nosso endereço. O resto (um .html, um
#: .svg, um .js que alguém tenha enviado) sai como download, numa caixa de areia:
#: nada que chega por envio roda com os cookies do site.
SEGUROS_NA_TELA = (
    "image/jpeg", "image/png", "image/webp", "image/gif", "image/avif",
    "model/gltf-binary", "application/pdf", "text/plain", "application/json",
)
SEGUROS_PELO_COMECO = ("video/", "audio/", "font/")

CACHE_DE_UM_ANO = "public, max-age=31536000, immutable"
#: A cópia de reserva (a foto parecida do repositório) pode ser trocada pela
#: original quando ela voltar: um dia de cache, sem `immutable`.
CACHE_DA_RESERVA = "public, max-age=86400"


class ArmazenamentoIndisponivel(ErroDeFormulario):
    """O arquivo não foi guardado (o banco recusou ou caiu): vira janela de app, nunca 500."""

    # O status fica o de todo ErroDeFormulario (400): um 503 do painel é lido
    # pelo InternalResponseRecoveryMiddleware como "o servidor oscilou" e a
    # janela com o motivo daria lugar ao "tente de novo" genérico.
    def __init__(self, mensagem="", **kwargs):
        kwargs.setdefault("titulo", "Arquivo não guardado")
        super().__init__(
            mensagem or (
                "Não deu para guardar o arquivo agora: nada foi gravado. "
                "Confira a conexão e envie de novo em instantes."
            ),
            **kwargs,
        )


class CloudinaryForaDoAr(FileNotFoundError):
    """O Cloudinary (o legado) respondeu 401/403 ou "disabled": a conta está fora do ar."""


# ======================================================================
# NOMES E TIPOS
# ======================================================================
def e_do_banco(nome) -> bool:
    return str(nome or "").startswith(PREFIXO)


_LETRAS = string.ascii_lowercase + string.digits


def _sufixo():
    # seis letras e números, como o sufixo que o Cloudinary sorteava: a
    # reserva das fotos (ls-foto-reserva.js) já sabe tirá-lo do nome
    return "_" + "".join(secrets.choice(_LETRAS) for _ in range(6))


def nome_novo(nome, max_length=None):
    """O nome de um arquivo NOVO: banco/<pasta>/<nome>_<sorteio><extensão>.

    Sorteado sempre (não só quando já existe): conferir se o nome existe
    custaria uma ida ao banco a cada envio, e um nome nunca é reaproveitado
    -- é isso que deixa o cache de um ano ser seguro.
    """
    nome = str(nome or "arquivo").replace("\\", "/").lstrip("/")
    if nome.startswith(PREFIXO):
        nome = nome[len(PREFIXO):]
    pasta, base = posixpath.split(nome)
    raiz, extensao = posixpath.splitext(base)
    extensao = extensao.lower()
    raiz = raiz or "arquivo"
    # a foto que vira WebP troca .jpg/.png por .webp: um caractere a mais
    folga = 1 if extensao in (".jpg", ".png") else 0
    comeco = PREFIXO + (pasta + "/" if pasta else "")
    sufixo = _sufixo()
    if max_length:
        cabe = max_length - len(comeco) - len(sufixo) - len(extensao) - folga
        if cabe < 1:
            raise SuspiciousFileOperation(f'O nome "{nome}" não cabe em {max_length} caracteres.')
        raiz = raiz[:cabe]
    return f"{comeco}{raiz}{sufixo}{extensao}"


def nome_do_espelho(nome_antigo, max_length=None):
    """O nome no banco de um arquivo que veio de fora: banco/<nome de antes>.

    Se não couber na coluna, a base é encurtada e ganha seis letras do
    SHA-1 do nome de antes (o mesmo nome antigo dá sempre o mesmo nome novo).
    """
    nome_antigo = str(nome_antigo or "").lstrip("/")
    if nome_antigo.startswith(PREFIXO):
        return nome_antigo
    inteiro = PREFIXO + nome_antigo
    if not max_length or len(inteiro) <= max_length:
        return inteiro
    pasta, base = posixpath.split(nome_antigo)
    raiz, extensao = posixpath.splitext(base)
    if len(extensao) > 6:
        raiz, extensao = base, ""
    marca = "_" + hashlib.sha1(nome_antigo.encode("utf-8")).hexdigest()[:6]
    comeco = PREFIXO + (pasta + "/" if pasta else "")
    cabe = max_length - len(comeco) - len(marca) - len(extensao)
    if cabe < 1:
        comeco, cabe = PREFIXO, max_length - len(PREFIXO) - len(marca) - len(extensao)
    return f"{comeco}{raiz[:max(1, cabe)]}{marca}{extensao}"


def tipo_do_conteudo(dados: bytes, nome: str = "") -> str:
    """O tipo pelo começo do arquivo (a extensão mente; o nome do Cloudinary nem tem)."""
    cabeca = bytes(dados[:16])
    if cabeca.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if cabeca.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if cabeca[:4] == b"RIFF" and cabeca[8:12] == b"WEBP":
        return "image/webp"
    if cabeca[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if cabeca[4:12] in (b"ftypavif", b"ftypavis"):
        return "image/avif"
    if cabeca.startswith(b"%PDF"):
        return "application/pdf"
    if cabeca.startswith(b"glTF"):
        return "model/gltf-binary"
    adivinhado = mimetypes.guess_type(nome or "")[0]
    if adivinhado and not adivinhado.startswith("image/"):
        return adivinhado
    return "application/octet-stream"


def preparar_imagem(dados: bytes, tipo: str):
    """(bytes, tipo, mudou?) -- a foto grande vira WebP de até LADO_MAXIMO px.

    A foto pequena e leve fica como chegou. A transparência (PNG recortado)
    continua: o WebP guarda o canal alfa. A orientação do celular (EXIF) é
    aplicada antes, porque o WebP não a leva. Qualquer problema com a
    imagem: fica o original (quem confere a imagem é o formulário).
    """
    if tipo not in TIPOS_QUE_SE_REDUZEM:
        return dados, tipo, False
    try:
        from PIL import Image, ImageOps

        with Image.open(io.BytesIO(dados)) as imagem:
            if getattr(imagem, "is_animated", False) and getattr(imagem, "n_frames", 1) > 1:
                return dados, tipo, False
            largura, altura = imagem.size
            if max(largura, altura) <= LADO_MAXIMO and len(dados) <= PESO_MAXIMO:
                return dados, tipo, False
            pronta = ImageOps.exif_transpose(imagem)
            if max(pronta.size) > LADO_MAXIMO:
                pronta.thumbnail((LADO_MAXIMO, LADO_MAXIMO), Image.LANCZOS)
            alfa = pronta.mode in ("RGBA", "LA", "PA") or (pronta.mode == "P" and "transparency" in pronta.info)
            pronta = pronta.convert("RGBA" if alfa else "RGB")
            saida = io.BytesIO()
            pronta.save(saida, "WEBP", quality=QUALIDADE, method=4)
            novo = saida.getvalue()
    except Exception:  # noqa: BLE001 -- imagem estranha: guarda como veio
        log.info("midia: a imagem não foi reduzida (fica o original)", exc_info=True)
        return dados, tipo, False
    if len(novo) >= len(dados) and max(largura, altura) <= LADO_MAXIMO:
        return dados, tipo, False
    return novo, "image/webp", True


def preparar(nome: str, dados: bytes, *, reduzir=True):
    """(nome, bytes, tipo): o tipo pelo conteúdo e, na foto grande, o WebP (com .webp no nome)."""
    tipo = tipo_do_conteudo(dados, nome)
    if not reduzir:
        return nome, dados, tipo
    dados, tipo, mudou = preparar_imagem(dados, tipo)
    if mudou:
        raiz, extensao = posixpath.splitext(nome)
        if extensao.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            nome = raiz + ".webp"
    return nome, dados, tipo


def seguro_na_tela(tipo: str) -> bool:
    return tipo in SEGUROS_NA_TELA or tipo.startswith(SEGUROS_PELO_COMECO)


# ======================================================================
# O BANCO
# ======================================================================
def _modelo():
    from .models import ArquivoNoBanco

    return ArquivoNoBanco


def guardar(nome, dados, *, publico, tipo=None, origem="envio", exata=True):
    """Grava uma linha nova. IntegrityError (o nome já existe) sobe para quem chamou."""
    from django.db import transaction

    dados = bytes(dados)
    ArquivoNoBanco = _modelo()
    with transaction.atomic():
        ArquivoNoBanco.objects.create(
            nome=nome,
            conteudo=dados,
            tipo=(tipo or tipo_do_conteudo(dados, nome))[:100],
            tamanho=len(dados),
            sha256=hashlib.sha256(dados).hexdigest(),
            publico=bool(publico),
            origem=str(origem or "")[:24],
            exata=bool(exata),
        )
    return nome


def substituir(nome, dados, *, tipo=None, origem="cloudinary", exata=True):
    """Troca os bytes de uma linha (a cópia de reserva pela original). Apaga a cópia do disco."""
    dados = bytes(dados)
    feito = _modelo().objects.filter(nome=nome).update(
        conteudo=dados,
        tipo=(tipo or tipo_do_conteudo(dados, nome))[:100],
        tamanho=len(dados),
        sha256=hashlib.sha256(dados).hexdigest(),
        origem=str(origem or "")[:24],
        exata=bool(exata),
    )
    apagar_do_disco(nome)
    return bool(feito)


def ler(nome, *, so_publico=False):
    """(bytes, tipo, sha256, exata) ou None. Uma consulta, só as colunas que servem."""
    consulta = _modelo().objects.filter(nome=nome)
    if so_publico:
        consulta = consulta.filter(publico=True)
    linha = consulta.values_list("conteudo", "tipo", "sha256", "exata").first()
    if linha is None:
        return None
    conteudo, tipo, sha, exata = linha
    return bytes(conteudo), tipo, sha, exata


def apagar(nome):
    _modelo().objects.filter(nome=nome).delete()
    apagar_do_disco(nome)


# ======================================================================
# A CÓPIA NO DISCO DA INSTÂNCIA
# ======================================================================
# O disco do Render é efêmero: some a cada publicação. Serve de cache --
# a segunda vez que alguém pede a mesma foto, o banco não é consultado.
# Só o que é PÚBLICO vai para o disco (documento privado nunca).
_escrito = {"bytes": 0}
_trava_do_disco = threading.Lock()


def pasta_do_disco() -> Path:
    configurada = str(getattr(settings, "MIDIA_CACHE_DIR", "") or "").strip()
    return Path(configurada) if configurada else Path(tempfile.gettempdir()) / "ls-midia-banco"


def _limite_do_disco() -> int:
    try:
        return int(float(getattr(settings, "MIDIA_CACHE_MAX_MB", 1024))) * 1024 * 1024
    except (TypeError, ValueError):
        return 1024 * 1024 * 1024


def _caminhos(nome, largura=None):
    chave = hashlib.sha1(nome.encode("utf-8")).hexdigest()
    pasta = pasta_do_disco() / chave[:2]
    if largura:
        return pasta / f"{chave}-w{int(largura)}.webp", None
    return pasta / f"{chave}.bin", pasta / f"{chave}.json"


def _gravar_no_disco(caminho: Path, dados: bytes):
    if _escrito["bytes"] + len(dados) > _limite_do_disco():
        return False
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario = caminho.with_name(caminho.name + f".{os.getpid()}.{threading.get_ident()}.tmp")
        temporario.write_bytes(dados)
        os.replace(temporario, caminho)
    except OSError:
        log.warning("midia: não deu para guardar a cópia no disco", exc_info=True)
        return False
    with _trava_do_disco:
        _escrito["bytes"] += len(dados)
    return True


def _do_disco(nome):
    """(bytes do original, meta) do disco, ou (None, None)."""
    arquivo, meta = _caminhos(nome)
    try:
        dados_meta = json.loads(meta.read_text(encoding="utf-8"))
        return arquivo.read_bytes(), dados_meta
    except (OSError, ValueError):
        return None, None


def _meta_do_disco(nome):
    _arquivo, meta = _caminhos(nome)
    try:
        return json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _para_o_disco(nome, dados, meta):
    arquivo, caminho_meta = _caminhos(nome)
    if _gravar_no_disco(arquivo, dados):
        _gravar_no_disco(caminho_meta, json.dumps(meta).encode("utf-8"))


def apagar_do_disco(nome):
    arquivo, meta = _caminhos(nome)
    for caminho in (arquivo, meta, *(_caminhos(nome, largura)[0] for largura in LARGURAS)):
        try:
            caminho.unlink()
        except OSError:
            pass


# ======================================================================
# O ENDEREÇO
# ======================================================================
def base_do_endereco() -> str:
    return str(getattr(settings, "MIDIA_BANCO_URL_BASE", "") or "").strip().rstrip("/")


def url_publica(nome) -> str:
    """O endereço da linha pública. Conta de texto: nada de banco nem de rede."""
    return f"{base_do_endereco()}{ROTA}{quote(str(nome), safe='/')}"


def largura_permitida(largura) -> int:
    """A largura da lista que cobre `largura` (a menor que não é menor); a maior, se passar."""
    try:
        largura = int(largura)
    except (TypeError, ValueError):
        return LARGURAS[-1]
    for opcao in LARGURAS:
        if opcao >= largura:
            return opcao
    return LARGURAS[-1]


def e_endereco_do_banco(url) -> bool:
    return isinstance(url, str) and (ROTA + PREFIXO) in url


# ======================================================================
# O LEGADO (o Cloudinary)
# ======================================================================
PRAZO_DO_LEGADO = 25


def baixar_endereco(url, prazo=PRAZO_DO_LEGADO) -> bytes:
    """Os bytes do endereço do legado. 401/403/"disabled" -> CloudinaryForaDoAr; outro erro -> FileNotFoundError."""
    import requests

    resposta = requests.get(url, timeout=prazo, headers={"User-Agent": "lazersport-midia/1"})
    erro = (resposta.headers.get("x-cld-error") or "").lower()
    if resposta.status_code in (401, 403) or "disabled" in erro:
        raise CloudinaryForaDoAr(f"O Cloudinary recusou (HTTP {resposta.status_code}): {erro or 'sem detalhe'}")
    if resposta.status_code != 200:
        raise FileNotFoundError(f"O Cloudinary não entregou o arquivo (HTTP {resposta.status_code}).")
    return resposta.content


@deconstructible(path="core.arquivos_no_banco.MidiaNoBanco")
class MidiaNoBanco(Storage):
    """O armazenamento padrão do site: o que chega vai para o banco; o nome antigo é do Cloudinary.

    `legado` é o tipo do Cloudinary do nome antigo: "image" (as fotos) ou
    "raw" (o .glb dos objetos 3D).
    """

    #: o espelho (core/espelho_midia.py) copia os nomes antigos deste armazenamento
    espelha_no_banco = True
    guarda_publico = True

    def __init__(self, legado="image"):
        self.legado = "raw" if legado == "raw" else "image"

    # ---- o legado ----
    def _legado(self):
        from cloudinary_storage.storage import MediaCloudinaryStorage, RawMediaCloudinaryStorage

        return RawMediaCloudinaryStorage() if self.legado == "raw" else MediaCloudinaryStorage()

    def baixar_legado(self, nome) -> bytes:
        return baixar_endereco(self._legado().url(nome))

    # ---- o contrato do Storage ----
    def get_available_name(self, name, max_length=None):
        return nome_novo(name, max_length=max_length)

    def get_alternative_name(self, file_root, file_ext):
        return f"{file_root}{_sufixo()}{file_ext}"

    def _save(self, name, content):
        from django.db import DatabaseError, IntegrityError

        try:
            if hasattr(content, "seek"):
                content.seek(0)
            dados = content.read()
        except Exception as erro:  # noqa: BLE001 -- o envio que não se lê é recusado com janela
            raise ArmazenamentoIndisponivel("O arquivo enviado não pôde ser lido. Envie de novo.") from erro
        nome, dados, tipo = preparar(name, dados, reduzir=self.legado == "image")
        for tentativa in range(3):
            try:
                return guardar(nome, dados, publico=True, tipo=tipo)
            except IntegrityError:
                if tentativa == 2:
                    raise ArmazenamentoIndisponivel() from None
                raiz, extensao = posixpath.splitext(nome)
                nome = f"{raiz[:-7] if len(raiz) > 7 else raiz}{_sufixo()}{extensao}"
            except DatabaseError as erro:
                log.exception("midia: o banco não guardou %s", nome)
                raise ArmazenamentoIndisponivel() from erro
        raise ArmazenamentoIndisponivel()

    def _open(self, name, mode="rb"):
        if e_do_banco(name):
            linha = None
            dados, _meta = _do_disco(name)
            if dados is None:
                linha = ler(name)
                if linha is None:
                    raise FileNotFoundError(f"{name} não está no banco.")
                dados = linha[0]
            arquivo = ContentFile(dados, name=name)
            arquivo.mode = mode
            return arquivo
        try:
            dados = self.baixar_legado(name)
        except FileNotFoundError:
            raise
        except Exception as erro:  # noqa: BLE001 -- rede: para quem lê, o arquivo não está
            raise FileNotFoundError(f"O Cloudinary não respondeu: {erro.__class__.__name__}") from erro
        arquivo = ContentFile(dados, name=name)
        arquivo.mode = mode
        return arquivo

    def exists(self, name):
        if e_do_banco(name):
            return _modelo().objects.filter(nome=name).exists()
        return False  # o nome antigo: perguntar ao Cloudinary custaria uma ida à rede (e ele está fora)

    def size(self, name):
        if e_do_banco(name):
            tamanho = _modelo().objects.filter(nome=name).values_list("tamanho", flat=True).first()
            if tamanho is None:
                raise FileNotFoundError(name)
            return tamanho
        import requests

        try:
            resposta = requests.head(self._legado().url(name), timeout=10)
        except requests.RequestException:
            return None
        return int(resposta.headers.get("content-length") or 0) if resposta.status_code == 200 else None

    def delete(self, name):
        if not name:
            return
        if e_do_banco(name):
            apagar(name)
            return
        try:
            self._legado().delete(name)
        except Exception:  # noqa: BLE001 -- apagar no legado é melhor esforço: o log conta
            log.warning("midia: o Cloudinary não apagou %s", name)

    def url(self, name):
        if e_do_banco(name):
            return url_publica(name)
        return self._legado().url(name)

    def listdir(self, path):
        raise NotImplementedError("O banco não lista pastas.")


def armazenamento_raw():
    return MidiaNoBanco(legado="raw")


# ======================================================================
# A ENTREGA
# ======================================================================
def _nome_valido(caminho: str) -> bool:
    return (
        bool(caminho) and len(caminho) <= 500 and "\x00" not in caminho
        and ".." not in caminho.split("/") and not caminho.startswith("/")
    )


def _variante(dados: bytes, largura: int):
    """A foto em WebP com no máximo `largura` px de largura, ou None (não é foto que se reduz)."""
    try:
        from PIL import Image, ImageOps

        with Image.open(io.BytesIO(dados)) as imagem:
            if getattr(imagem, "is_animated", False) and getattr(imagem, "n_frames", 1) > 1:
                return None
            pronta = ImageOps.exif_transpose(imagem)
            if pronta.width > largura:
                pronta.thumbnail((largura, max(1, pronta.height * largura // max(1, pronta.width)) + 1), Image.LANCZOS)
            alfa = pronta.mode in ("RGBA", "LA", "PA") or (pronta.mode == "P" and "transparency" in pronta.info)
            pronta = pronta.convert("RGBA" if alfa else "RGB")
            saida = io.BytesIO()
            pronta.save(saida, "WEBP", quality=QUALIDADE_DA_VARIANTE, method=4)
            return saida.getvalue()
    except Exception:  # noqa: BLE001 -- não é imagem: sai o original
        return None


def _resposta_vazia(status, texto=""):
    from django.http import HttpResponse

    resposta = HttpResponse(texto, status=status, content_type="text/plain; charset=utf-8")
    resposta["Cache-Control"] = "no-store" if status >= 500 else "public, max-age=60"
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta


def servir(request, caminho):
    """GET/HEAD /midia/banco/<caminho>: só a linha pública, com cache longo e ETag.

    O banco que não responde é 503 curto (o navegador tenta de novo), nunca 500.
    """
    from django.db import DatabaseError

    try:
        return _servir(request, caminho)
    except DatabaseError:
        log.warning("midia: o banco não respondeu ao entregar %s", caminho, exc_info=True)
        resposta = _resposta_vazia(503, "Tente de novo em instantes.")
        resposta["Retry-After"] = "5"
        return resposta


def _servir(request, caminho):
    from django.http import FileResponse, HttpResponse

    if request.method not in ("GET", "HEAD"):
        resposta = _resposta_vazia(405, "Só leitura.")
        resposta["Allow"] = "GET, HEAD"
        return resposta
    caminho = str(caminho or "")
    nome = caminho if caminho.startswith(PREFIXO) else PREFIXO + caminho
    if not _nome_valido(nome[len(PREFIXO):]):
        return _resposta_vazia(404, "Arquivo não encontrado.")
    largura = None
    pedida = request.GET.get("w")
    if pedida is not None:
        if not pedida.isdigit() or int(pedida) not in LARGURAS:
            return _resposta_vazia(404, "Largura fora da lista.")
        largura = int(pedida)

    meta = _meta_do_disco(nome)
    dados = None
    if meta is None:
        linha = ler(nome, so_publico=True)
        if linha is None:
            return _resposta_vazia(404, "Arquivo não encontrado.")
        dados, tipo, sha, exata = linha
        meta = {"tipo": tipo, "sha256": sha, "exata": bool(exata)}
        _para_o_disco(nome, dados, meta)

    tipo = meta.get("tipo") or "application/octet-stream"
    etiqueta = meta.get("sha256", "")[:32] + (f"-w{largura}" if largura else "")
    etag = f'"{etiqueta}"'
    cache = CACHE_DE_UM_ANO if meta.get("exata", True) else CACHE_DA_RESERVA

    def cabecalhos(resposta):
        if not resposta.streaming and resposta.status_code == 200:
            # atendido antes do CommonMiddleware: o tamanho vai daqui (sem ele, o envio sai em pedaços)
            resposta["Content-Length"] = str(len(resposta.content))
        resposta["ETag"] = etag
        resposta["Cache-Control"] = cache
        resposta["X-Content-Type-Options"] = "nosniff"
        # as fotos aparecem no painel (interno.) e no site (www.); o canvas que
        # confere a transparência (ls-fotos.js) precisa poder ler os pixels
        resposta["Access-Control-Allow-Origin"] = "*"
        resposta["Cross-Origin-Resource-Policy"] = "cross-origin"
        if not seguro_na_tela(tipo):
            resposta["Content-Disposition"] = "attachment"
            resposta["Content-Security-Policy"] = "sandbox; default-src 'none'"
        return resposta

    pedidas = [e.strip() for e in (request.headers.get("If-None-Match") or "").split(",")]
    if etag in pedidas or f"W/{etag}" in pedidas:
        return cabecalhos(HttpResponse(status=304))

    if largura and tipo.startswith("image/") and tipo != "image/svg+xml":
        variante_no_disco, _ = _caminhos(nome, largura)
        if variante_no_disco.is_file():
            return cabecalhos(FileResponse(open(variante_no_disco, "rb"), content_type="image/webp"))
        if dados is None:
            dados, _meta = _do_disco(nome)
            if dados is None:
                linha = ler(nome, so_publico=True)
                if linha is None:
                    return _resposta_vazia(404, "Arquivo não encontrado.")
                dados = linha[0]
        reduzida = _variante(dados, largura)
        if reduzida is not None:
            _gravar_no_disco(variante_no_disco, reduzida)
            return cabecalhos(HttpResponse(reduzida, content_type="image/webp"))

    if dados is None:
        original, _meta = _caminhos(nome)
        if original.is_file():
            return cabecalhos(FileResponse(open(original, "rb"), content_type=tipo))
        linha = ler(nome, so_publico=True)
        if linha is None:
            return _resposta_vazia(404, "Arquivo não encontrado.")
        dados = linha[0]
    return cabecalhos(HttpResponse(dados, content_type=tipo))


def midia_no_banco(request, caminho):
    """A view (www. e interno.): o mesmo que o middleware, para quem chega pelo urlconf."""
    return servir(request, caminho)


class MidiaNoBancoMiddleware:
    """Atende /midia/banco/ antes da sessão, do login, do GZip e dos registros.

    Uma foto não precisa saber quem é a pessoa: passar pelo resto da pilha
    custaria, a quem está logado, a consulta da sessão e a do usuário POR
    FOTO (~170 ms cada no banco remoto), e o GZip gastaria CPU tentando
    comprimir um WebP.
    """

    INICIO = ROTA + PREFIXO

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(self.INICIO):
            return servir(request, request.path[len(ROTA):])
        return self.get_response(request)
