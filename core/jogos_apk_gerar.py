"""GERAR O APK (ANDROID) DE UM JOGO, PELO PAINEL -- sem Android Studio, sem SDK.

Como os .bat dos jogos da casa fazem no computador, só que no servidor e num
clique: o painel monta um aplicativo Android de verdade, assinado, pronto para
instalar (e para pôr no site como "Baixar o aplicativo").

O QUE VAI DENTRO
  * O app (core/apk_casca/classes.dex, compilado de ferramentas/apk/src): uma tela
    só, em tela cheia e deitada, que serve o jogo de dentro do próprio APK -- abre
    sem internet. Ver Jogo.java.
  * O jogo, em assets/www/:
      - de console: o reprodutor do site (o mesmo jogo_emulador.html, com os botões
        na tela, os ícones das ações, o Ajustar controle, os Gráficos, o marca-passo
        que deixa o jogo liso), o EmulatorJS, o núcleo do console e os arquivos do
        jogo (a ROM, os discos, a BIOS);
      - de HTML5 (um .html só): o próprio arquivo.
  * O AndroidManifest.xml e o resources.arsc (o ícone), escritos aqui mesmo no
    formato binário do Android (sem o aapt2), e o ícone feito da capa do jogo.
  * As assinaturas v1 (JAR) e v2 (APK Signature Scheme), com a mesma chave sempre
    (ChaveDosApks): o Android só atualiza um app assinado pela mesma chave.

O QUE NÃO VAI: PSP e DOS (o núcleo de várias linhas precisa de um isolamento que
o WebView não dá) e jogo só por endereço (já é online).
"""

from __future__ import annotations

import base64
import hashlib
import io
import re
import struct
import tempfile
import time
import unicodedata
import zlib
from pathlib import Path

PASTA = Path(__file__).resolve().parent
CASCA_DEX = PASTA / "apk_casca" / "classes.dex"
ESTATICO = PASTA / "static"
ATIVIDADE = "br.com.lazersport.jogo.Jogo"
PACOTE_BASE = "br.com.lazersport.jogo"
SDK_MINIMO = 21          # Android 5
SDK_ALVO = 29            # a assinatura v1 + v2 vale em todo Android de hoje
ICONE_ID = 0x7F010000    # mipmap/icone (o resources.arsc daqui)
TEMA_TELA_CHEIA = 0x0103000A  # @android:style/Theme.NoTitleBar.Fullscreen
#: Os consoles que não vão para o APK (o núcleo de várias linhas).
SEM_APK = ("psp", "dos")
#: O maior jogo que o painel empacota (o APK é montado no servidor, na hora).
MAX_JOGO = 160 * 1024 * 1024


class ApkNaoDa(ValueError):
    """O jogo não pode virar APK (e o motivo, para a tela)."""


# ====================================================================== o pacote (o nome do app no Android)

def nome_do_pacote(slug):
    """'super-mario-teste' -> 'br.com.lazersport.jogo.super_mario_teste' (cada jogo é um app)."""
    limpo = unicodedata.normalize("NFD", slug or "jogo").encode("ascii", "ignore").decode().lower()
    limpo = re.sub(r"[^a-z0-9]+", "_", limpo).strip("_") or "jogo"
    if limpo[0].isdigit():
        limpo = "j" + limpo
    return f"{PACOTE_BASE}.{limpo[:60]}"


# ====================================================================== o XML binário do Android (AXML)

ANDROID_NS = "http://schemas.android.com/apk/res/android"
#: O número de cada atributo android:* que o manifesto usa (o do framework).
ATRIBUTOS = {
    "theme": 0x01010000, "label": 0x01010001, "icon": 0x01010002, "name": 0x01010003,
    "exported": 0x01010010, "launchMode": 0x0101001D, "screenOrientation": 0x0101001E,
    "configChanges": 0x0101001F, "minSdkVersion": 0x0101020C, "versionCode": 0x0101021B,
    "versionName": 0x0101021C, "targetSdkVersion": 0x01010270, "allowBackup": 0x01010280,
    "hardwareAccelerated": 0x010102D3,
}
TIPO_REFERENCIA, TIPO_TEXTO, TIPO_INTEIRO, TIPO_HEX, TIPO_SIM_NAO = 0x01, 0x03, 0x10, 0x11, 0x12


def _pool_de_textos(textos, utf8=False):
    """O ResStringPool (o bloco de textos do formato binário do Android)."""
    dados = bytearray()
    deslocamentos = []
    for t in textos:
        deslocamentos.append(len(dados))
        if utf8:
            b = t.encode("utf-8")
            for n in (len(t), len(b)):
                dados += bytes([n]) if n < 0x80 else bytes([0x80 | (n >> 8), n & 0xFF])
            dados += b + b"\x00"
        else:
            u = t.encode("utf-16-le")
            n = len(u) // 2
            dados += struct.pack("<H", n) if n < 0x8000 else struct.pack("<HH", 0x8000 | (n >> 16), n & 0xFFFF)
            dados += u + b"\x00\x00"
    while len(dados) % 4:
        dados += b"\x00"
    cabecalho = 28
    inicio = cabecalho + 4 * len(textos)
    corpo = b"".join(struct.pack("<I", d) for d in deslocamentos) + bytes(dados)
    return struct.pack("<HHIIIIII", 0x0001, cabecalho, cabecalho + len(corpo), len(textos), 0,
                       0x100 if utf8 else 0, inicio, 0) + corpo


class _Axml:
    """Monta o AndroidManifest.xml binário: elementos com atributos (android:* com o número certo)."""

    def __init__(self):
        self.eventos = []

    def abrir(self, nome, atributos):
        self.eventos.append(("abre", nome, atributos))

    def fechar(self, nome):
        self.eventos.append(("fecha", nome, None))

    def montar(self):
        # os nomes de atributo com número vêm primeiro no pool, na ordem do mapa de recursos
        usados = []
        for tipo, _nome, atributos in self.eventos:
            for (ns, chave, _valor) in atributos or ():
                if ns == "android" and chave not in usados:
                    usados.append(chave)
        usados.sort(key=lambda c: ATRIBUTOS[c])
        textos = list(usados)

        def idx(texto):
            if texto not in textos:
                textos.append(texto)
            return textos.index(texto)

        for t in ("android", ANDROID_NS):
            idx(t)
        corpo = bytearray()
        corpo += struct.pack("<HHIIIII", 0x0100, 16, 24, 1, 0xFFFFFFFF, idx("android"), idx(ANDROID_NS))
        for tipo, nome, atributos in self.eventos:
            if tipo == "abre":
                atrs = []
                for ns, chave, valor in atributos:
                    ns_idx = idx(ANDROID_NS) if ns == "android" else 0xFFFFFFFF
                    if isinstance(valor, bool):
                        bruto, tipo_v, dado = 0xFFFFFFFF, TIPO_SIM_NAO, 0xFFFFFFFF if valor else 0
                    elif isinstance(valor, tuple):  # (TIPO, número)
                        bruto, tipo_v, dado = 0xFFFFFFFF, valor[0], valor[1]
                    elif isinstance(valor, int):
                        bruto, tipo_v, dado = 0xFFFFFFFF, TIPO_INTEIRO, valor
                    else:
                        bruto = idx(str(valor))
                        tipo_v, dado = TIPO_TEXTO, bruto
                    atrs.append((ATRIBUTOS.get(chave, 0xFFFFFFFF) if ns == "android" else 0xFFFFFFFF,
                                 ns_idx, idx(chave), bruto, tipo_v, dado))
                # o Android procura os atributos em ordem de número
                atrs.sort(key=lambda a: a[0])
                pedaco = struct.pack("<IIHHHHHH", 0xFFFFFFFF, idx(nome), 20, 20, len(atrs), 0, 0, 0)
                for _num, ns_idx, nome_idx, bruto, tipo_v, dado in atrs:
                    pedaco += struct.pack("<IIIHBBI", ns_idx, nome_idx, bruto, 8, 0, tipo_v, dado & 0xFFFFFFFF)
                corpo += struct.pack("<HHIII", 0x0102, 16, 16 + len(pedaco), 1, 0xFFFFFFFF) + pedaco
            else:
                corpo += struct.pack("<HHIIIII", 0x0103, 16, 24, 1, 0xFFFFFFFF, 0xFFFFFFFF, idx(nome))
        corpo += struct.pack("<HHIIIII", 0x0101, 16, 24, 1, 0xFFFFFFFF, idx("android"), idx(ANDROID_NS))
        mapa = struct.pack("<HHI", 0x0180, 8, 8 + 4 * len(usados)) + b"".join(struct.pack("<I", ATRIBUTOS[c]) for c in usados)
        pool = _pool_de_textos(textos)
        tudo = pool + mapa + bytes(corpo)
        return struct.pack("<HHI", 0x0003, 8, 8 + len(tudo)) + tudo


def manifesto(pacote, titulo, versao_codigo, versao_nome, em_pe=False):
    x = _Axml()
    x.abrir("manifest", [("android", "versionCode", versao_codigo), ("android", "versionName", versao_nome),
                         (None, "package", pacote)])
    x.abrir("uses-sdk", [("android", "minSdkVersion", SDK_MINIMO), ("android", "targetSdkVersion", SDK_ALVO)])
    x.fechar("uses-sdk")
    x.abrir("uses-permission", [("android", "name", "android.permission.INTERNET")])
    x.fechar("uses-permission")
    x.abrir("application", [("android", "label", titulo), ("android", "icon", (TIPO_REFERENCIA, ICONE_ID)),
                            ("android", "allowBackup", True), ("android", "hardwareAccelerated", True)])
    # orientation|keyboardHidden|keyboard|screenSize|smallestScreenSize|screenLayout|uiMode|navigation
    x.abrir("activity", [("android", "name", ATIVIDADE), ("android", "label", titulo),
                         ("android", "theme", (TIPO_REFERENCIA, TEMA_TELA_CHEIA)), ("android", "exported", True),
                         ("android", "launchMode", 2), ("android", "screenOrientation", 7 if em_pe else 6),
                         ("android", "configChanges", (TIPO_HEX, 0xFF0)), ("android", "hardwareAccelerated", True)])
    x.abrir("intent-filter", [])
    x.abrir("action", [("android", "name", "android.intent.action.MAIN")])
    x.fechar("action")
    x.abrir("category", [("android", "name", "android.intent.category.LAUNCHER")])
    x.fechar("category")
    x.fechar("intent-filter")
    x.fechar("activity")
    x.fechar("application")
    x.fechar("manifest")
    return x.montar()


# ====================================================================== os recursos (resources.arsc): o ícone

CAMINHO_DO_ICONE = "res/mipmap-xxxhdpi-v4/icone.png"


def recursos(pacote):
    """Um resources.arsc com um recurso só: mipmap/icone (0x7f010000), na densidade xxxhdpi."""
    valores = _pool_de_textos([CAMINHO_DO_ICONE], utf8=True)
    tipos = _pool_de_textos(["mipmap"], utf8=True)
    chaves = _pool_de_textos(["icone"], utf8=True)
    especificacao = struct.pack("<HHIBBHI", 0x0202, 16, 16 + 4, 1, 0, 0, 1) + struct.pack("<I", 0)
    config = bytearray(64)
    struct.pack_into("<I", config, 0, 64)
    struct.pack_into("<H", config, 14, 640)  # densidade xxxhdpi
    struct.pack_into("<H", config, 24, 4)    # sdkVersion 4 (o -v4 do caminho)
    cabecalho_tipo = 20 + len(config)
    entrada = struct.pack("<HHI", 8, 0, 0) + struct.pack("<HBBI", 8, 0, TIPO_TEXTO, 0)
    deslocamentos = struct.pack("<I", 0)
    inicio = cabecalho_tipo + len(deslocamentos)
    tipo = struct.pack("<HHIBBHII", 0x0201, cabecalho_tipo, inicio + len(entrada), 1, 0, 0, 1, inicio) + bytes(config)
    tipo += deslocamentos + entrada
    nome = pacote.encode("utf-16-le")[:254].ljust(256, b"\x00")
    cabecalho_pacote = 288
    pos_tipos = cabecalho_pacote
    pos_chaves = pos_tipos + len(tipos)
    corpo_pacote = tipos + chaves + especificacao + tipo
    pacote_bloco = struct.pack("<HHII", 0x0200, cabecalho_pacote, cabecalho_pacote + len(corpo_pacote), 0x7F) + nome
    pacote_bloco += struct.pack("<IIIII", pos_tipos, 1, pos_chaves, 1, 0) + corpo_pacote
    corpo = valores + pacote_bloco
    return struct.pack("<HHII", 0x0002, 12, 12 + len(corpo), 1) + corpo


def icone_png(imagem_bytes=None, cor="#ff3d57"):
    """O ícone do app (192 x 192): a capa do jogo num quadrado de cantos redondos, ou a marca."""
    from PIL import Image, ImageDraw

    lado = 192
    try:
        origem = Image.open(io.BytesIO(imagem_bytes)).convert("RGBA") if imagem_bytes else None
    except Exception:
        origem = None
    if origem is None:
        origem = Image.open(ESTATICO / "images" / "icone" / "icone-192.png").convert("RGBA")
        return _png(origem.resize((lado, lado), Image.LANCZOS))
    fundo = Image.new("RGBA", (lado, lado), cor if re.match(r"^#[0-9a-fA-F]{6}$", cor or "") else "#ff3d57")
    escala = max(lado / origem.width, lado / origem.height)
    arte = origem.resize((max(1, round(origem.width * escala)), max(1, round(origem.height * escala))), Image.LANCZOS)
    fundo.alpha_composite(arte, ((lado - arte.width) // 2, (lado - arte.height) // 2))
    mascara = Image.new("L", (lado, lado), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, lado - 1, lado - 1), 38, fill=255)
    final = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    final.paste(fundo, (0, 0), mascara)
    return _png(final)


def _png(imagem):
    saida = io.BytesIO()
    imagem.save(saida, "PNG", optimize=True)
    return saida.getvalue()


# ====================================================================== o ZIP (alinhado, como o zipalign)

class _Zip:
    """Escreve o ZIP num arquivo: o que vai sem compressão fica alinhado em 4 bytes (o Android exige)."""

    def __init__(self, destino):
        self.f = destino
        self.entradas = []

    def adicionar(self, nome, dados, comprimir=True):
        nome_b = nome.encode("utf-8")
        crc = zlib.crc32(dados) & 0xFFFFFFFF
        if comprimir and len(dados) > 64:
            c = zlib.compressobj(6, zlib.DEFLATED, -15)
            gravado = c.compress(dados) + c.flush()
            metodo = 8
            if len(gravado) >= len(dados):
                gravado, metodo = dados, 0
        else:
            gravado, metodo = dados, 0
        pos = self.f.tell()
        extra = b""
        if metodo == 0:
            # o dado começa num múltiplo de 4 (o "zipalign")
            inicio_dado = pos + 30 + len(nome_b)
            falta = (4 - inicio_dado % 4) % 4
            extra = b"\x00" * falta
        flags = 0x0800  # nome em UTF-8
        self.f.write(struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, flags, metodo, 0, 0x21, crc, len(gravado), len(dados),
                                 len(nome_b), len(extra)) + nome_b + extra)
        self.f.write(gravado)
        self.entradas.append((nome_b, crc, len(gravado), len(dados), metodo, pos, flags))
        if self.f.tell() > 0xFFFFFFF0:
            raise ApkNaoDa("O APK passou de 4 GB.")

    def diretorio(self):
        """Grava o diretório central e o fim do ZIP; devolve (início do diretório, os bytes dele, o fim)."""
        inicio = self.f.tell()
        cd = bytearray()
        for nome_b, crc, comp, tam, metodo, pos, flags in self.entradas:
            cd += struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, flags, metodo, 0, 0x21, crc, comp, tam,
                              len(nome_b), 0, 0, 0, 0, 0, pos) + nome_b
        fim = struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, len(self.entradas), len(self.entradas), len(cd), inicio, 0)
        return inicio, bytes(cd), fim


# ====================================================================== as assinaturas (v1 JAR + v2)

def _linha_do_manifesto(texto):
    """As linhas do MANIFEST.MF têm no máximo 72 bytes (o resto continua com um espaço na frente)."""
    b = texto.encode("utf-8")
    partes = [b[:70]]
    b = b[70:]
    while b:
        partes.append(b" " + b[:69])
        b = b[69:]
    return b"\r\n".join(partes) + b"\r\n"


def _b64_sha256(dados):
    return base64.b64encode(hashlib.sha256(dados).digest())


def _assinatura_v1(arquivos, chave, certificado, com_v2=True):
    """META-INF/MANIFEST.MF, CERT.SF e CERT.RSA (a assinatura JAR, a que todo Android entende)."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.serialization import pkcs7

    manifesto_mf = bytearray(b"Manifest-Version: 1.0\r\nCreated-By: Lazer & Sport Games\r\n\r\n")
    secoes = []
    for nome, digest in arquivos:
        secao = _linha_do_manifesto("Name: " + nome) + b"SHA-256-Digest: " + digest + b"\r\n\r\n"
        manifesto_mf += secao
        secoes.append((nome, secao))
    sf = bytearray(b"Signature-Version: 1.0\r\nCreated-By: Lazer & Sport Games\r\n")
    sf += b"SHA-256-Digest-Manifest: " + _b64_sha256(bytes(manifesto_mf)) + b"\r\n"
    if com_v2:
        sf += b"X-Android-APK-Signed: 2\r\n"
    sf += b"\r\n"
    for nome, secao in secoes:
        sf += _linha_do_manifesto("Name: " + nome) + b"SHA-256-Digest: " + _b64_sha256(secao) + b"\r\n\r\n"
    rsa = (pkcs7.PKCS7SignatureBuilder().set_data(bytes(sf)).add_signer(certificado, chave, hashes.SHA256())
           .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.NoAttributes]))
    return [("META-INF/MANIFEST.MF", bytes(manifesto_mf)), ("META-INF/CERT.SF", bytes(sf)), ("META-INF/CERT.RSA", rsa)]


def _com_tamanho(dados):
    return struct.pack("<I", len(dados)) + dados


def _digest_em_pedacos(trechos):
    """O resumo do APK Signature Scheme v2: SHA-256 de cada pedaço de 1 MB, e o resumo dos resumos."""
    resumos = []
    for ler in trechos:
        for pedaco in ler():
            resumos.append(hashlib.sha256(b"\xa5" + struct.pack("<I", len(pedaco)) + pedaco).digest())
    return hashlib.sha256(b"\x5a" + struct.pack("<I", len(resumos)) + b"".join(resumos)).digest()


def _bloco_v2(resumo, chave, certificado):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    algoritmo = 0x0103  # RSASSA-PKCS1-v1_5 com SHA2-256
    digests = _com_tamanho(_com_tamanho(struct.pack("<I", algoritmo) + _com_tamanho(resumo)))
    certificados = _com_tamanho(_com_tamanho(certificado.public_bytes(serialization.Encoding.DER)))
    atributos = _com_tamanho(b"")
    dados_assinados = digests + certificados + atributos
    assinatura = chave.sign(dados_assinados, padding.PKCS1v15(), hashes.SHA256())
    assinaturas = _com_tamanho(_com_tamanho(struct.pack("<I", algoritmo) + _com_tamanho(assinatura)))
    publica = _com_tamanho(chave.public_key().public_bytes(serialization.Encoding.DER,
                                                           serialization.PublicFormat.SubjectPublicKeyInfo))
    assinante = _com_tamanho(_com_tamanho(dados_assinados) + assinaturas + publica)
    valor = _com_tamanho(assinante)
    par = struct.pack("<QI", 4 + len(valor), 0x7109871A) + valor
    tamanho = len(par) + 8 + 16
    return struct.pack("<Q", tamanho) + par + struct.pack("<Q", tamanho) + b"APK Sig Block 42"


def _ler_pedacos(arquivo, inicio, fim, tamanho=1024 * 1024):
    def gerar():
        arquivo.seek(inicio)
        restante = fim - inicio
        while restante > 0:
            pedaco = arquivo.read(min(tamanho, restante))
            if not pedaco:
                break
            restante -= len(pedaco)
            yield pedaco
    return gerar


def _bytes_em_pedacos(dados, tamanho=1024 * 1024):
    def gerar():
        for i in range(0, len(dados), tamanho):
            yield dados[i:i + tamanho]
    return gerar


def montar_apk(destino, arquivos, chave, certificado):
    """Grava o APK assinado em `destino` (arquivo binário). `arquivos`: [(nome, bytes, comprimir)]."""
    corpo = tempfile.TemporaryFile()
    try:
        z = _Zip(corpo)
        # a assinatura v1 primeiro (o MANIFEST.MF tem de ser o primeiro arquivo: é onde o Java e o
        # Android antigo procuram), e depois o resto
        resumos = [(nome, _b64_sha256(dados)) for nome, dados, _c in arquivos]
        for nome, dados in _assinatura_v1(resumos, chave, certificado):
            z.adicionar(nome, dados, True)
        for nome, dados, comprimir in arquivos:
            z.adicionar(nome, dados, comprimir)
        inicio_cd, cd, fim = z.diretorio()
        # v2: o resumo cobre as entradas, o diretório central e o fim (com o início do diretório
        # apontando para onde o bloco de assinatura vai entrar -- o mesmo lugar)
        resumo = _digest_em_pedacos([_ler_pedacos(corpo, 0, inicio_cd), _bytes_em_pedacos(cd), _bytes_em_pedacos(fim)])
        bloco = _bloco_v2(resumo, chave, certificado)
        corpo.seek(0)
        restante = inicio_cd
        while restante > 0:
            pedaco = corpo.read(min(4 * 1024 * 1024, restante))
            destino.write(pedaco)
            restante -= len(pedaco)
        destino.write(bloco)
        destino.write(cd)
        destino.write(fim[:16] + struct.pack("<I", inicio_cd + len(bloco)) + fim[20:])
    finally:
        corpo.close()


# ====================================================================== a chave (sempre a mesma)

def chave_e_certificado():
    """A chave RSA e o certificado que assinam todo APK do painel (criados na primeira vez)."""
    import datetime as dt

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    from .models import ChaveDosApks

    guardada = ChaveDosApks.objects.order_by("pk").first()
    if guardada is None:
        chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Lazer & Sport Games"),
                          x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Lazer & Sport"),
                          x509.NameAttribute(NameOID.COUNTRY_NAME, "BR")])
        certificado = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(chave.public_key())
                       .serial_number(x509.random_serial_number())
                       .not_valid_before(dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc))
                       .not_valid_after(dt.datetime(2074, 1, 1, tzinfo=dt.timezone.utc))
                       .sign(chave, hashes.SHA256()))
        guardada = ChaveDosApks.objects.create(
            chave_pem=chave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                          serialization.NoEncryption()).decode(),
            certificado_pem=certificado.public_bytes(serialization.Encoding.PEM).decode(),
        )
    chave = serialization.load_pem_private_key(guardada.chave_pem.encode(), password=None)
    certificado = x509.load_pem_x509_certificate(guardada.certificado_pem.encode())
    return chave, certificado


# ====================================================================== o jogo dentro do APK

#: O que o reprodutor usa do site (o resto da página vem no HTML).
ARQUIVOS_DO_REPRODUTOR = (
    "site/paginas/jogo-emulador.css", "site/paginas/jogo-emulador.js", "site/paginas/jogo-guardado.js",
    "site/paginas/jogo-passe.js", "site/paginas/jogo-progresso.js",
    "site/paginas/intro-jogos.css", "site/paginas/intro-jogos.js", "images/logoofi.png",
)
ARQUIVOS_DO_EMULADOR = (
    "loader.js", "emulator.min.js", "emulator.min.css", "version.json", "localization/pt-BR.json",
    "compression/extract7z.js", "compression/extractzip.js", "compression/libunrar.js", "compression/libunrar.wasm",
)
#: Os arquivos grandes que já vêm comprimidos: vão sem compressão (e alinhados)
JA_COMPRIMIDOS = (".data", ".zip", ".7z", ".png", ".webp", ".jpg", ".jpeg", ".wasm", ".chd", ".pbp", ".gz")


def _ler_estatico(caminho):
    return (ESTATICO / caminho).read_bytes()


def _baixar(url, timeout=60):
    import requests

    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.content


def _ler_arquivo_do_jogo(arquivo, request=None):
    """Os bytes de um arquivo do jogo: o índice (texto) ou as partes, baixadas na ordem, num bloco só."""
    if arquivo.e_indice:
        return arquivo.conteudo.encode("utf-8")
    bloco = bytearray()
    for url, _tamanho in arquivo.partes():
        bloco += _baixar(url if url.startswith("http") else _absoluto(request, url), 180)
    return bytes(bloco)


def conteudo_do_jogo(jogo, request=None, para="apk"):
    """[(caminho em assets/www/, bytes)] + a capa, para um jogo de console ou de HTML5.

    `para`: "apk" (o app do Android) ou "exe" (o programa do Windows, que serve a
    página isolada: aí o PSP e o DOS entram, com o núcleo de várias linhas).

    O painel roda no endereço interno, que tem as rotas dele: a página do jogo é montada
    com as rotas do site (as mesmas que o reprodutor usa no ar).
    """
    from django.urls import get_urlconf, set_urlconf

    anterior = get_urlconf()
    set_urlconf(None)
    try:
        return _conteudo_do_jogo(jogo, request, para)
    finally:
        set_urlconf(anterior)


def _conteudo_do_jogo(jogo, request=None, para="apk"):
    from django.template.loader import render_to_string

    from .jogos_emulador import SISTEMAS
    from .views_jogos import config_do_emulador

    if jogo.sistema:
        if jogo.sistema in SEM_APK and para == "apk":
            raise ApkNaoDa(f"{SISTEMAS[jogo.sistema].nome if jogo.sistema in SISTEMAS else jogo.sistema} não vai para APK: "
                           "o núcleo dele precisa de um isolamento que o app do Android não dá. Ele roda no site.")
        if jogo.sistema not in SISTEMAS:
            raise ApkNaoDa("O console deste jogo não foi reconhecido.")
        config = config_do_emulador(jogo)
        total = sum(a["tamanho"] for a in config["arquivos"])
        if total > MAX_JOGO:
            raise ApkNaoDa(f"O jogo tem {total // 1048576} MB: o painel empacota até {MAX_JOGO // 1048576} MB.")
        arquivos = []
        # os arquivos do jogo, cada um inteiro, em rom/
        por_nome = {a.nome: a for a in jogo.arquivos_emulador.all()}
        for item in config["arquivos"]:
            fonte = por_nome.get(item["nome"])
            if fonte is None:
                raise ApkNaoDa(f"Faltou o arquivo {item['nome']} do jogo.")
            dados = _ler_arquivo_do_jogo(fonte, request)
            if len(dados) != item["tamanho"]:
                raise ApkNaoDa(f"{item['nome']}: chegou com tamanho diferente ({len(dados)} de {item['tamanho']} bytes).")
            arquivos.append(("rom/" + item["nome"], dados))
            item["partes"] = ["/rom/" + _url_quote(item["nome"])]
            item["tamanhos"] = [item["tamanho"]]
        # o núcleo do console: o do site ou, quando ele não mora no site, o do pacote oficial
        sistema = SISTEMAS[jogo.sistema]
        dados_emu = "vendor/emulatorjs/data/"
        fins = ("-wasm.data", "-legacy-wasm.data")
        if para == "exe" and sistema.threads:
            # a página do .exe é isolada: o núcleo de várias linhas (PSP, DOS) funciona
            fins += ("-thread-wasm.data", "-thread-legacy-wasm.data")
        for fim in fins:
            nome = sistema.nucleo + fim
            local = ESTATICO / dados_emu / "cores" / nome
            if local.exists():
                arquivos.append(("static/" + dados_emu + "cores/" + nome, local.read_bytes()))
            elif config.get("nucleoExterno"):
                arquivos.append(("static/" + dados_emu + "cores/" + nome, _baixar(config["nucleoExterno"] + nome, 120)))
        relatorio = ESTATICO / dados_emu / "cores" / "reports" / (sistema.nucleo + ".json")
        if relatorio.exists():
            arquivos.append(("static/" + dados_emu + "cores/reports/" + relatorio.name, relatorio.read_bytes()))
        elif config.get("nucleoExterno"):
            try:
                arquivos.append(("static/" + dados_emu + "cores/reports/" + sistema.nucleo + ".json",
                                 _baixar(config["nucleoExterno"] + "reports/" + sistema.nucleo + ".json")))
            except Exception:
                pass
        for nome in ARQUIVOS_DO_EMULADOR:
            caminho = ESTATICO / dados_emu / nome
            if caminho.exists():
                arquivos.append(("static/" + dados_emu + nome, caminho.read_bytes()))
        for caminho in ARQUIVOS_DO_REPRODUTOR:
            arquivos.append(("static/" + caminho, _ler_estatico(caminho)))
        # a página: o reprodutor do site, com tudo apontando para dentro do APK
        config["nucleoExterno"] = ""
        config["dados"] = "/static/" + dados_emu
        config["voltar"] = ""
        config["apk"] = True
        capa = b""
        if jogo.poster_url:
            try:
                capa = _baixar(jogo.poster_url if jogo.poster_url.startswith("http") else _absoluto(request, jogo.poster_url))
                # a extensão certa (o app diz ao navegador o tipo pela extensão)
                ext = ("png" if capa[:8] == b"\x89PNG\r\n\x1a\n" else "webp" if capa[8:12] == b"WEBP"
                       else "gif" if capa[:3] == b"GIF" else "jpg")
                arquivos.append((f"capa.{ext}", capa))
                config["capa"] = f"/capa.{ext}"
            except Exception:
                config["capa"] = ""
        # sem a requisição: a página do reprodutor não usa nada da sessão (e o APK não leva cookie)
        html = render_to_string("jogo_emulador.html", {"jogo": jogo, "config": config})
        html = _so_caminhos(html)
        arquivos.insert(0, ("index.html", html.encode("utf-8")))
        return arquivos, capa
    if jogo.arquivo_html:
        campo = jogo.arquivo_html
        with campo.storage.open(campo.name, "rb") as f:
            html = f.read()
        capa = b""
        if jogo.capa_url:
            try:
                capa = _baixar(jogo.capa_url if jogo.capa_url.startswith("http") else _absoluto(request, jogo.capa_url))
            except Exception:
                capa = b""
        return [("index.html", html)], capa
    raise ApkNaoDa("Este jogo não tem um arquivo para empacotar (jogo só por endereço já roda online).")


def _url_quote(nome):
    from urllib.parse import quote

    return quote(nome)


def _absoluto(request, caminho):
    if request is not None:
        return request.build_absolute_uri(caminho)
    return caminho


def _so_caminhos(html):
    """Tira o domínio dos endereços do próprio site (o APK serve tudo pelo caminho)."""
    from django.conf import settings

    for dominio in getattr(settings, "ALLOWED_HOSTS", []) or []:
        if dominio and dominio not in ("*", "localhost") and not dominio.startswith("."):
            html = html.replace(f"https://{dominio}/", "/").replace(f"http://{dominio}/", "/")
    return html


def gerar_apk(jogo, destino, request=None):
    """Monta o APK do jogo em `destino` (arquivo binário aberto) e devolve o resumo."""
    if not CASCA_DEX.exists():
        raise ApkNaoDa("Falta o core/apk_casca/classes.dex (rode ferramentas/apk/montar_casca.sh).")
    conteudo, capa = conteudo_do_jogo(jogo, request)
    pacote = nome_do_pacote(jogo.slug)
    versao_codigo = max(1, int((time.time() - 1_700_000_000) // 60))  # sobe a cada minuto: a atualização instala por cima
    versao_nome = time.strftime("%Y.%m.%d.%H%M")
    em_pe = jogo.sistema == "nds" or getattr(jogo, "proporcao", "") == "retrato"
    arquivos = [
        ("AndroidManifest.xml", manifesto(pacote, jogo.nome[:60], versao_codigo, versao_nome, em_pe), True),
        ("classes.dex", CASCA_DEX.read_bytes(), True),
        ("resources.arsc", recursos(pacote), False),
        (CAMINHO_DO_ICONE, icone_png(capa, jogo.cor[:7] if jogo.cor else ""), False),
    ]
    for caminho, dados in conteudo:
        arquivos.append(("assets/www/" + caminho, dados, not caminho.lower().endswith(JA_COMPRIMIDOS)))
    chave, certificado = chave_e_certificado()
    montar_apk(destino, arquivos, chave, certificado)
    return {"pacote": pacote, "versao": versao_nome, "arquivos": len(arquivos)}
