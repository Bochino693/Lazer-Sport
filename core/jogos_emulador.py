"""Jogos de console e de fliperama que rodam no site por emulador.

POR QUE EXISTE. Muito jogo não é um arquivo só. Um disco de PlayStation em
.cue/.bin é um ÍNDICE (o .cue, um texto) mais as FAIXAS (os .bin: a de
dados e, muitas vezes, uma por música -- "Track 01.bin", "Track 02.bin"...).
Um jogo de vários discos é um conjunto desses por disco. Cartucho (NES,
Game Boy...) costuma ser um arquivo só, mas alguns precisam de uma BIOS ao
lado. Este módulo recebe o CONJUNTO que a equipe enviou e responde:

* está completo? (cada arquivo que o .cue/.m3u/.ccd pede veio, com o nome
  conferido sem diferenciar maiúscula; o que falta sai pelo nome);
* que sistema é? (pelo cabeçalho dos arquivos -- a assinatura do
  PlayStation no setor 16 do disco, o "NES" no começo do cartucho... -- e,
  só quando não dá, pela extensão);
* o emulador deste site abre isso? (núcleo, extensões, BIOS obrigatória,
  licença do núcleo);
* como o emulador recebe: qual arquivo ele abre (o índice ou o jogo), com
  que nome cada um entra na pasta virtual dele, e o índice reescrito com
  os nomes certos (acento e maiúscula batem com o que foi enviado).

O EMULADOR. É o EmulatorJS 4.2.3 (GPL-3), hospedado no próprio site em
`core/static/vendor/emulatorjs/`, com os núcleos do RetroArch compilados
para o navegador. Cada arquivo é baixado e gravado na pasta virtual com o
nome que o índice pede; o .cue enxerga os .bin ao lado, como no computador.

A LICENÇA DOS NÚCLEOS. O site é de uma empresa. Três núcleos do EmulatorJS
proíbem uso comercial por escrito: o do Super Nintendo (Snes9x: "commercial
use includes ... using Snes9x as a promotion for your commercial product"),
o do Mega Drive/Sega CD (Genesis Plus GX: "may not be used in a commercial
product or activity") e o de fliperama (FinalBurn Neo: "you may not ... seek
to gain monetary profit"). Esses sistemas são RECONHECIDOS (o painel diz o
que é), mas ficam desligados. `JOGOS_EMULADORES_NAO_COMERCIAIS` liga cada um,
para quando houver permissão escrita dos autores; o núcleo deles não vem no
site e é baixado do CDN do EmulatorJS.

O QUE ESTE MÓDULO NÃO FAZ. Não decide de quem é o jogo: só entra no site o
que a empresa tem direito de publicar.
"""

from __future__ import annotations

import re
import unicodedata
import zipfile
from dataclasses import dataclass, field

MB = 1024 * 1024

#: Teto de arquivos num jogo (um disco com 30 faixas de música passa folgado).
MAX_ARQUIVOS = 99

#: Quanto do começo de cada arquivo basta para reconhecer o sistema (o setor
#: 16 de um CD em 2352 bytes termina perto de 40 KB; o cabeçalho do SNES, com
#: o cabeçalho de copiadora, em 66 KB).
CABECA = 128 * 1024

#: O fim do .zip (onde mora a lista dos arquivos dentro dele).
CAUDA = 64 * 1024

#: Índice é texto pequeno; o painel guarda e serve o conteúdo dele.
MAX_INDICE = 256 * 1024

#: Um CD tem no máximo uns 900 MB; acima disso é DVD (PS2...), que não roda aqui.
MAX_CD = 1000 * MB


@dataclass(frozen=True)
class Sistema:
    codigo: str  # o "EJS_core" do EmulatorJS
    nome: str
    nucleo: str
    licenca: str
    uso_comercial: bool
    extensoes: frozenset
    disco: bool = False
    bios: tuple = ()
    bios_obrigatoria: str = ""  # "" | "sempre" | "cd" (só quando é disco)
    nota: str = ""
    #: o formato da tela que o painel sugere (JogoCadastrado.PROPORCOES)
    formato: str = "classico"
    #: o "como jogar" que o painel sugere: os controles padrão do EmulatorJS
    #: (setas; Z, X, A, S = os botões; Q/E = L/R; Enter = Start; V = Select)
    comandos: str = ""


def _ext(*nomes):
    return frozenset(nomes)


SISTEMAS = {
    "psx": Sistema(
        "psx", "PlayStation (PS1)", "pcsx_rearmed", "GPL-2.0", True,
        _ext("cue", "bin", "img", "ccd", "sub", "mdf", "pbp", "toc", "cbn", "m3u"), disco=True,
        bios=("scph5500.bin", "scph5501.bin", "scph5502.bin", "scph1001.bin", "scph7001.bin", "scph101.bin"),
        nota="Roda sem BIOS (o núcleo imita a do console); alguns jogos pedem a BIOS original. "
             "Não abre .chd nem .iso: use .cue/.bin, .pbp (um arquivo só) ou .m3u para vários discos.",
        comandos="Setas movem · X = ✕ · Z = ○ · S = □ · A = △ · Q/E = L1/R1 · Enter = Start. No celular, o controle aparece na tela; um controle USB ou Bluetooth também serve.",
    ),
    "nes": Sistema(
        "nes", "NES / Famicom", "fceumm", "GPL-2.0", True, _ext("nes", "fds", "unf", "unif"),
        bios=("disksys.rom",), nota="O Famicom Disk System (.fds) precisa da BIOS disksys.rom.",
        comandos="Setas movem · Z = A · X = B · Enter = Start · V = Select. No celular, o controle aparece na tela; um controle USB ou Bluetooth também serve.",
    ),
    "gb": Sistema(
        "gb", "Game Boy / Game Boy Color", "gambatte", "GPL-2.0", True, _ext("gb", "gbc", "dmg"), formato="quadrado",
        comandos="Setas movem · Z = A · X = B · Enter = Start · V = Select. No celular, o controle aparece na tela; um controle USB ou Bluetooth também serve.",
    ),
    "gba": Sistema(
        "gba", "Game Boy Advance", "mgba", "MPL-2.0", True, _ext("gba"), bios=("gba_bios.bin",), formato="portatil",
        comandos="Setas movem · Z = A · X = B · Q/E = L/R · Enter = Start. No celular, o controle aparece na tela; um controle USB ou Bluetooth também serve.",
    ),
    "n64": Sistema(
        "n64", "Nintendo 64", "mupen64plus_next", "GPL-2.0", True, _ext("n64", "z64", "v64"),
        comandos="Setas = direcional · Z e X são os botões principais · Q/E = L/R · Enter = Start. No celular, o controle aparece na tela; um controle USB ou Bluetooth também serve.",
    ),
    "pce": Sistema(
        "pce", "PC Engine / TurboGrafx-16 (e o CD)", "mednafen_pce", "GPL-2.0", True,
        _ext("pce", "cue", "bin", "img", "ccd", "sub", "iso", "chd"), disco=True,
        bios=("syscard3.pce", "syscard2.pce", "syscard1.pce"), bios_obrigatoria="cd",
        nota="O cartucho (.pce) roda sozinho; o CD precisa da BIOS syscard3.pce.",
        comandos="Setas movem · Z = I · X = II · Enter = Run · V = Select. No celular, o controle aparece na tela; um controle USB ou Bluetooth também serve.",
    ),
    # --- reconhecidos, mas com núcleo de licença não comercial ---------------
    "snes": Sistema(
        "snes", "Super Nintendo", "snes9x", "não comercial (Snes9x)", False, _ext("sfc", "smc", "swc", "fig", "bs"),
    ),
    "segaMD": Sistema(
        "segaMD", "Mega Drive / Genesis", "genesis_plus_gx", "não comercial (Genesis Plus GX)", False,
        _ext("md", "gen", "smd", "bin", "mdx"),
    ),
    "segaMS": Sistema("segaMS", "Master System", "genesis_plus_gx", "não comercial (Genesis Plus GX)", False, _ext("sms")),
    "segaGG": Sistema("segaGG", "Game Gear", "genesis_plus_gx", "não comercial (Genesis Plus GX)", False, _ext("gg")),
    "segaCD": Sistema(
        "segaCD", "Sega CD / Mega CD", "genesis_plus_gx", "não comercial (Genesis Plus GX)", False,
        _ext("cue", "bin", "iso", "chd", "img", "m3u"), disco=True,
        bios=("bios_CD_U.bin", "bios_CD_E.bin", "bios_CD_J.bin"), bios_obrigatoria="sempre",
    ),
    "arcade": Sistema(
        "arcade", "Fliperama (FinalBurn Neo)", "fbneo", "não comercial (FinalBurn Neo)", False, _ext("zip", "7z"),
        nota="O .zip precisa ter o nome exato do jogo no FinalBurn Neo (ex.: sf2.zip).",
    ),
}

#: Reconhecidos só para avisar que não rodam no navegador (por enquanto).
NAO_SUPORTADOS = {
    "segaSaturn": "Sega Saturn",
    "3do": "3DO",
    "ps2": "PlayStation 2",
    "dreamcast": "Dreamcast",
}

INDICES = _ext("cue", "ccd", "toc", "m3u")
#: O que pode ser a faixa ou a imagem de um disco.
DE_DISCO = _ext("bin", "img", "iso", "sub", "mdf", "mds", "cbn", "chd", "pbp")
#: Cartucho, inclusive o de console que também tem CD (o .pce do PC Engine).
DE_CARTUCHO = (frozenset().union(*(s.extensoes for s in SISTEMAS.values() if not s.disco)) | _ext("pce")) - _ext("bin", "zip", "7z")
#: Imagem de disco que nunca é cartucho.
SO_DE_DISCO = _ext("iso", "chd", "pbp", "img", "cbn", "mdf")
PACOTES = _ext("zip", "7z")
#: Vem junto quando se seleciona a pasta inteira; fica de fora, com aviso.
IGNORADOS = _ext("txt", "nfo", "sfv", "md5", "sha1", "dat", "jpg", "jpeg", "png", "gif", "pdf", "url", "ini", "db", "htm", "html", "xml", "log")

BIOS_CONHECIDAS = {nome.lower(): codigo for codigo, sistema in SISTEMAS.items() for nome in sistema.bios}


def sistemas_ligados(settings=None):
    """Os códigos de sistema que este site deixa rodar.

    Os de licença livre sempre; os de licença não comercial só se listados
    em `JOGOS_EMULADORES_NAO_COMERCIAIS` (ex.: "snes,segaMD"), para quando a
    empresa tiver a permissão dos autores.
    """
    if settings is None:
        from django.conf import settings
    extras = {c.strip() for c in str(getattr(settings, "JOGOS_EMULADORES_NAO_COMERCIAIS", "") or "").split(",") if c.strip()}
    return [codigo for codigo, s in SISTEMAS.items() if s.uso_comercial or codigo in extras]


def escolhas_de_sistema():
    """(código, rótulo) para o campo `sistema` do jogo."""
    return [(codigo, s.nome) for codigo, s in SISTEMAS.items()]


# ---------------------------------------------------------------------------
# Leitura dos arquivos (local, remota ou só um trecho que o navegador mandou)
# ---------------------------------------------------------------------------


class ForaDoTrecho(Exception):
    """Pediram um pedaço do arquivo que não veio (só a cabeça foi enviada)."""


@dataclass
class Entrada:
    """Um arquivo do conjunto: o nome, o tamanho e como ler um pedaço dele.

    `ler(inicio, quantos)` devolve bytes. Pode ser o arquivo inteiro (o envio
    direto), uma leitura remota por faixa (o armazenamento de jogos grandes)
    ou só a cabeça e a cauda que o navegador mandou antes de enviar (aí um
    pedaço de fora levanta `ForaDoTrecho`).
    """

    nome: str
    tamanho: int
    ler: object
    origem: object = None  # o arquivo enviado, a chave remota... quem chama decide

    def pedaco(self, inicio, quantos):
        if inicio >= self.tamanho or quantos <= 0:
            return b""
        quantos = min(quantos, self.tamanho - inicio)
        return self.ler(inicio, quantos)

    @property
    def ext(self):
        return extensao(self.nome)


def entrada_de_arquivo(arquivo, nome=None):
    """Uma `Entrada` sobre um arquivo enviado (UploadedFile) ou qualquer arquivo aberto."""

    def ler(inicio, quantos):
        arquivo.seek(inicio)
        dados = arquivo.read(quantos)
        arquivo.seek(0)
        return dados

    tamanho = getattr(arquivo, "size", None)
    if tamanho is None:
        arquivo.seek(0, 2)
        tamanho = arquivo.tell()
        arquivo.seek(0)
    return Entrada(nome or arquivo.name, int(tamanho), ler, arquivo)


def entrada_de_trechos(nome, tamanho, cabeca=b"", cauda=b""):
    """Uma `Entrada` com só a cabeça e a cauda do arquivo (a conferência antes de enviar)."""
    cabeca = bytes(cabeca or b"")
    cauda = bytes(cauda or b"")
    tamanho = int(tamanho)
    inicio_cauda = tamanho - len(cauda)

    def ler(inicio, quantos):
        fim = inicio + quantos
        if fim <= len(cabeca):
            return cabeca[inicio:fim]
        if cauda and inicio >= inicio_cauda:
            return cauda[inicio - inicio_cauda: fim - inicio_cauda]
        raise ForaDoTrecho(nome)

    return Entrada(nome, tamanho, ler)


class _ArquivoPorTrechos:
    """Um arquivo "de mentira" sobre `Entrada.ler`, para o `zipfile` ler o .zip sem baixá-lo."""

    def __init__(self, entrada):
        self.entrada = entrada
        self.pos = 0

    def seekable(self):
        return True

    def seek(self, pos, de=0):
        base = {0: 0, 1: self.pos, 2: self.entrada.tamanho}[de]
        self.pos = max(0, base + pos)
        return self.pos

    def tell(self):
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.entrada.tamanho - self.pos
        dados = self.entrada.pedaco(self.pos, n)
        self.pos += len(dados)
        return dados


# ---------------------------------------------------------------------------
# Nomes
# ---------------------------------------------------------------------------


def extensao(nome):
    nome = nome.rsplit("/", 1)[-1]
    return nome.rsplit(".", 1)[-1].lower() if "." in nome else ""


def normalizar_nome(nome):
    """O nome como vai para a pasta virtual: só o nome (sem pasta), em NFC."""
    nome = unicodedata.normalize("NFC", (nome or "").replace("\\", "/").rsplit("/", 1)[-1]).strip()
    return nome


def chave_de_nome(nome):
    """Para comparar nomes como o Windows compara: sem diferenciar maiúscula."""
    return normalizar_nome(nome).casefold()


_NOME_RUIM = re.compile(r"[\x00-\x1f\x7f/\\:*?\"<>|#]")


def problema_no_nome(nome):
    if not nome or nome in (".", ".."):
        return "nome vazio"
    if len(nome) > 180:
        return "nome comprido demais (mais de 180 caracteres)"
    if _NOME_RUIM.search(nome):
        return "nome com caractere que não pode (/ \\ : * ? \" < > | # ou de controle): renomeie o arquivo (e a linha dele no .cue)"
    return ""


def _ordem_natural(nome):
    return [int(p) if p.isdigit() else p.casefold() for p in re.split(r"(\d+)", nome)]


# ---------------------------------------------------------------------------
# Índices: .cue, .ccd, .toc, .m3u
# ---------------------------------------------------------------------------


def decodificar_texto(dados):
    """O índice como texto: UTF-8 (com ou sem BOM) ou, se não for, o do Windows (cp1252)."""
    if b"\x00" in dados:
        raise ValueError("tem conteúdo binário (não é um índice de texto)")
    try:
        return dados.decode("utf-8-sig")
    except UnicodeDecodeError:
        return dados.decode("cp1252", errors="replace")


_FILE_CUE = re.compile(r'^(?P<antes>\s*FILE\s+)(?:"(?P<aspas>[^"]+)"|(?P<solto>\S+))(?P<depois>\s+\S+\s*)$', re.I)
_FILE_TOC = re.compile(r'^(?P<antes>\s*(?:FILE|DATAFILE|AUDIOFILE)\s+)"(?P<aspas>[^"]+)"(?P<depois>.*)$', re.I)
_TRACK = re.compile(r"^\s*TRACK\s+\d+\s+(\S+)", re.I)


@dataclass
class Indice:
    nome: str  # o nome do arquivo de índice
    tipo: str  # cue | ccd | toc | m3u
    linhas: list  # o texto, linha a linha
    pedidos: list  # [(linha, nome pedido)] -- o que ele manda abrir
    dados_primeiro: str = ""  # o nome pedido que tem a faixa de dados (para reconhecer o sistema)


def ler_indice(nome, texto):
    tipo = extensao(nome)
    linhas = texto.splitlines()
    pedidos = []
    dados_primeiro = ""
    if tipo == "cue":
        atual = None
        for i, linha in enumerate(linhas):
            m = _FILE_CUE.match(linha)
            if m:
                atual = m.group("aspas") or m.group("solto")
                pedidos.append((i, atual))
                continue
            t = _TRACK.match(linha)
            if t and atual and not dados_primeiro and t.group(1).upper().startswith(("MODE", "CDI")):
                dados_primeiro = atual
    elif tipo == "toc":
        for i, linha in enumerate(linhas):
            m = _FILE_TOC.match(linha)
            if m:
                pedidos.append((i, m.group("aspas")))
        dados_primeiro = pedidos[0][1] if pedidos else ""
    elif tipo == "m3u":
        for i, linha in enumerate(linhas):
            limpo = linha.strip()
            if limpo and not limpo.startswith("#"):
                pedidos.append((i, limpo))
    elif tipo == "ccd":
        # o CloneCD não escreve os nomes: são o .img e o .sub com o mesmo nome do .ccd
        base = nome.rsplit(".", 1)[0]
        pedidos = [(None, base + ".img"), (None, base + ".sub")]
        dados_primeiro = base + ".img"
    return Indice(nome, tipo, linhas, pedidos, dados_primeiro)


def reescrever_indice(indice, nomes):
    """O índice com cada nome pedido trocado pelo nome do arquivo que veio (o da pasta virtual).

    `nomes` mapeia o nome pedido (como está no índice) para o nome final.
    Uma pasta no caminho do índice ("CD1\\Track 01.bin") some: tudo fica lado
    a lado, como o emulador recebe.
    """
    if indice.tipo == "ccd":
        return "\n".join(indice.linhas) + "\n"
    linhas = list(indice.linhas)
    for i, pedido in indice.pedidos:
        if i is None or pedido not in nomes:
            continue
        if indice.tipo == "m3u":
            linhas[i] = nomes[pedido]
            continue
        regra = _FILE_CUE if indice.tipo == "cue" else _FILE_TOC
        m = regra.match(linhas[i])
        if m:
            linhas[i] = f'{m.group("antes")}"{nomes[pedido]}"{m.group("depois")}'
    return "\n".join(linhas) + "\n"


# ---------------------------------------------------------------------------
# Reconhecer o sistema pelo conteúdo
# ---------------------------------------------------------------------------

SYNC = b"\x00" + b"\xff" * 10 + b"\x00"


def _setor_de_dados(entrada, n):
    """Os 2048 bytes de dados do setor `n` de uma imagem de CD (2352 cru ou 2048)."""
    inicio = entrada.pedaco(0, 16)
    if inicio[:12] == SYNC:
        modo = inicio[15] if len(inicio) > 15 else 1
        desloc = 24 if modo == 2 else 16
        return entrada.pedaco(n * 2352 + desloc, 2048)
    return entrada.pedaco(n * 2048, 2048)


def sistema_do_cd(entrada):
    """O sistema de uma faixa de dados de CD, ou None. Pode levantar ForaDoTrecho."""
    if entrada.tamanho > MAX_CD:
        pvd = _setor_de_dados(entrada, 16)
        if pvd[1:6] == b"CD001" and pvd[8:19] == b"PLAYSTATION":
            return "ps2"
        return None
    zero = _setor_de_dados(entrada, 0)
    if zero.startswith(b"SEGADISCSYSTEM"):
        return "segaCD"
    if zero.startswith(b"SEGA SEGASATURN"):
        return "segaSaturn"
    if zero[:7] == b"\x01\x5a\x5a\x5a\x5a\x5a\x01":
        return "3do"
    pvd = _setor_de_dados(entrada, 16)
    if pvd[1:6] == b"CD001" and pvd[8:19] == b"PLAYSTATION":
        return "psx"
    if b"Sony Computer Entertainment" in _setor_de_dados(entrada, 4):
        return "psx"
    if b"PC Engine CD-ROM SYSTEM" in zero + _setor_de_dados(entrada, 1):
        return "pce"
    return None


_LOGO_GB = bytes.fromhex("CEED6666CC0D000B")
_LOGO_GBA = bytes.fromhex("24FFAE51699AA221")
_N64 = {bytes.fromhex("80371240"), bytes.fromhex("37804012"), bytes.fromhex("40123780")}


def _snes(entrada):
    copiadora = 512 if entrada.tamanho % 1024 == 512 else 0
    for base in (0x7FC0, 0xFFC0):
        cab = entrada.pedaco(copiadora + base, 32)
        if len(cab) == 32:
            soma = cab[0x1E] | cab[0x1F] << 8
            complemento = cab[0x1C] | cab[0x1D] << 8
            if soma ^ complemento == 0xFFFF and soma not in (0, 0xFFFF):
                return True
    return False


def sistema_do_cartucho(entrada):
    """O sistema de um cartucho pelo cabeçalho, ou None. Pode levantar ForaDoTrecho."""
    comeco = entrada.pedaco(0, 16)
    if comeco[:4] == b"NES\x1a":
        return "nes"
    if comeco[:4] == b"FDS\x1a" or comeco[1:15] == b"*NINTENDO-HVC*":
        return "nes"
    if comeco[:4] in _N64:
        return "n64"
    if entrada.pedaco(4, 8) == _LOGO_GBA and entrada.pedaco(0xB2, 1) == b"\x96":
        return "gba"
    if entrada.pedaco(0x104, 8) == _LOGO_GB:
        return "gb"
    if b"SEGA" in entrada.pedaco(0x100, 16):
        return "segaMD"
    for base in (0x7FF0, 0x3FF0, 0x1FF0):
        if entrada.pedaco(base, 8) == b"TMR SEGA":
            return "segaGG" if entrada.ext == "gg" else "segaMS"
    if entrada.ext in SISTEMAS["snes"].extensoes and _snes(entrada):
        return "snes"
    return None


#: Extensões que não dizem o sistema: .bin é cartucho de Mega Drive OU faixa de
#: CD; .zip/.7z é fliperama OU um jogo qualquer zipado.
AMBIGUAS = _ext("bin", "zip", "7z", "img", "iso")


def sistema_pela_extensao(ext):
    """O sistema quando a extensão só existe num deles (.nes, .gba, .pce...); senão None."""
    if not ext or ext in AMBIGUAS:
        return None
    candidatos = [c for c, s in SISTEMAS.items() if ext in s.extensoes]
    return candidatos[0] if len(candidatos) == 1 else None


def nomes_no_pacote(entrada):
    """Os nomes dentro de um .zip (sem baixá-lo inteiro), ou None se não deu para ler."""
    if entrada.ext != "zip":
        return None
    try:
        with zipfile.ZipFile(_ArquivoPorTrechos(entrada)) as pacote:
            return [n for n in pacote.namelist() if not n.endswith("/")]
    except (zipfile.BadZipFile, ForaDoTrecho, OSError, ValueError, EOFError):
        return None


# ---------------------------------------------------------------------------
# A análise do conjunto
# ---------------------------------------------------------------------------

PAPEIS = (
    ("jogo", "O arquivo que o emulador abre"),
    ("disco", "Disco (de um jogo de vários discos)"),
    ("faixa", "Faixa do disco"),
    ("bios", "BIOS"),
)


@dataclass
class Peca:
    entrada: Entrada
    nome: str  # o nome na pasta virtual do emulador
    papel: str
    disco: int | None = None
    conteudo: str | None = None  # o índice reescrito (só .cue/.ccd/.toc/.m3u)


@dataclass
class Analise:
    sistema: str | None = None
    detectado: str | None = None
    como: str = ""  # "cabeçalho" | "extensão" | "escolhido"
    principal: Peca | None = None
    pecas: list = field(default_factory=list)
    m3u_gerado: str = ""  # vários discos sem .m3u: o índice que o painel monta
    discos: int = 0
    erros: list = field(default_factory=list)
    avisos: list = field(default_factory=list)
    ignorados: list = field(default_factory=list)

    @property
    def ok(self):
        return not self.erros and self.principal is not None and bool(self.sistema)

    @property
    def tamanho_total(self):
        return sum(p.entrada.tamanho for p in self.pecas)

    def resumo(self):
        sistema = SISTEMAS.get(self.sistema)
        partes = [sistema.nome if sistema else "sistema não reconhecido"]
        if self.discos > 1:
            partes.append(f"{self.discos} discos")
        faixas = sum(1 for p in self.pecas if p.papel == "faixa")
        if faixas:
            partes.append(f"{faixas} faixa{'s' if faixas != 1 else ''}")
        if any(p.papel == "bios" for p in self.pecas):
            partes.append("com BIOS")
        partes.append(_mb(self.tamanho_total))
        return " · ".join(partes)

    def para_json(self):
        return {
            "ok": self.ok,
            "sistema": self.sistema or "",
            "detectado": self.detectado or "",
            "como": self.como,
            "resumo": self.resumo(),
            "principal": self.principal.nome if self.principal else "",
            "discos": self.discos,
            "arquivos": [
                {"nome": p.nome, "papel": p.papel, "disco": p.disco, "tamanho": p.entrada.tamanho, "enviado": p.entrada.nome}
                for p in self.pecas
            ],
            "erros": self.erros,
            "avisos": self.avisos,
            "ignorados": self.ignorados,
        }


def _mb(bytes_):
    if bytes_ < MB:
        return f"{max(1, round(bytes_ / 1024))} KB"
    return f"{bytes_ / MB:.0f} MB" if bytes_ >= 10 * MB else f"{bytes_ / MB:.1f} MB".replace(".", ",")


def analisar(entradas, sistema_escolhido="", ligados=None, limite_por_arquivo=None):
    """Confere o conjunto de arquivos de UM jogo e diz como o emulador vai recebê-lo.

    `entradas`: lista de `Entrada`. `sistema_escolhido`: o código escolhido
    no painel ("" = reconhecer sozinho). `ligados`: os sistemas que o site
    deixa rodar (padrão: `sistemas_ligados()`). `limite_por_arquivo`: o teto
    do armazenamento, em bytes (None = sem teto).
    """
    an = Analise()
    ligados = sistemas_ligados() if ligados is None else ligados

    if not entradas:
        an.erros.append("Nenhum arquivo enviado.")
        return an

    # 1. nomes: só o nome, sem repetir, sem caractere que quebra a pasta virtual
    vistos = {}
    uteis = []
    for entrada in entradas:
        entrada.nome = normalizar_nome(entrada.nome)
        problema = problema_no_nome(entrada.nome)
        if problema:
            an.erros.append(f"“{entrada.nome}”: {problema}.")
            continue
        chave = chave_de_nome(entrada.nome)
        if chave in vistos:
            an.erros.append(f"O arquivo “{entrada.nome}” veio duas vezes.")
            continue
        vistos[chave] = entrada
        ext = entrada.ext
        if chave in BIOS_CONHECIDAS or ext in INDICES or ext in DE_DISCO or ext in DE_CARTUCHO or ext in PACOTES:
            uteis.append(entrada)
        elif ext in IGNORADOS:
            an.ignorados.append(entrada.nome)
        else:
            an.erros.append(f"“{entrada.nome}”: formato .{ext or '?'} não é de jogo que o emulador abre.")
    if len(uteis) > MAX_ARQUIVOS:
        an.erros.append(f"São {len(uteis)} arquivos; o limite é {MAX_ARQUIVOS} por jogo.")
        return an
    por_chave = {chave_de_nome(e.nome): e for e in uteis}

    if limite_por_arquivo:
        for entrada in uteis:
            if entrada.tamanho > limite_por_arquivo:
                an.erros.append(
                    f"“{entrada.nome}” tem {_mb(entrada.tamanho)}; o armazenamento aceita até "
                    f"{_mb(limite_por_arquivo)} por arquivo."
                )

    # 2. a BIOS se separa pelo nome (scph5501.bin seria tomada por uma faixa)
    bios = [e for e in uteis if chave_de_nome(e.nome) in BIOS_CONHECIDAS]
    resto = [e for e in uteis if e not in bios]
    usados = set()

    def achar(pedido, quem):
        entrada = por_chave.get(chave_de_nome(pedido))
        if entrada is None:
            an.erros.append(f"“{quem}” pede “{normalizar_nome(pedido)}”, que não veio. Selecione esse arquivo junto.")
        return entrada

    indices = {}
    for entrada in resto:
        if entrada.ext in INDICES:
            try:
                if entrada.tamanho > MAX_INDICE:
                    raise ValueError("é grande demais para um índice")
                texto = decodificar_texto(entrada.pedaco(0, entrada.tamanho))
            except ForaDoTrecho:
                an.erros.append(f"“{entrada.nome}” não pôde ser lido.")
                continue
            except ValueError as exc:
                an.erros.append(f"“{entrada.nome}” {exc}.")
                continue
            indices[chave_de_nome(entrada.nome)] = (entrada, ler_indice(entrada.nome, texto))

    dados_para_reconhecer = []  # entradas de faixa de dados / jogo, na ordem de importância

    def montar_disco(entrada_indice, indice, papel, numero):
        """Confere um índice de disco (.cue/.ccd/.toc) e registra as faixas dele."""
        nomes = {}
        for _, pedido in indice.pedidos:
            if indice.tipo == "ccd" and extensao(pedido) == "sub" and chave_de_nome(pedido) not in por_chave:
                continue  # o .sub (subcanal) do CloneCD é opcional
            alvo = achar(pedido, entrada_indice.nome)
            if alvo is None:
                continue
            if chave_de_nome(alvo.nome) in indices:
                an.erros.append(f"“{entrada_indice.nome}” aponta para outro índice (“{alvo.nome}”).")
                continue
            nomes[pedido] = alvo.nome
            if chave_de_nome(alvo.nome) not in usados:
                usados.add(chave_de_nome(alvo.nome))
                an.pecas.append(Peca(alvo, alvo.nome, "faixa", numero))
            if indice.dados_primeiro and chave_de_nome(pedido) == chave_de_nome(indice.dados_primeiro):
                dados_para_reconhecer.insert(0, alvo)
        if indice.tipo in ("cue", "toc") and not indice.pedidos:
            an.erros.append(f"“{entrada_indice.nome}” não lista nenhuma faixa (nenhuma linha FILE).")
        usados.add(chave_de_nome(entrada_indice.nome))
        conteudo = reescrever_indice(indice, nomes)
        peca = Peca(entrada_indice, entrada_indice.nome, papel, numero, conteudo)
        an.pecas.append(peca)
        return peca

    m3us = [(e, i) for e, i in indices.values() if i.tipo == "m3u"]
    discos_idx = [(e, i) for e, i in indices.values() if i.tipo != "m3u"]
    imagens_unicas = [e for e in resto if e.ext in ("chd", "pbp", "iso", "mdf", "cbn")]

    if len(m3us) > 1:
        an.erros.append("Veio mais de um .m3u: envie um jogo por vez (um .m3u só).")
    elif m3us:
        entrada_m3u, indice_m3u = m3us[0]
        usados.add(chave_de_nome(entrada_m3u.nome))
        nomes = {}
        for numero, (_, pedido) in enumerate(indice_m3u.pedidos, start=1):
            alvo = achar(pedido, entrada_m3u.nome)
            if alvo is None:
                continue
            nomes[pedido] = alvo.nome
            chave = chave_de_nome(alvo.nome)
            if chave in indices:
                montar_disco(alvo, indices[chave][1], "disco", numero)
            elif chave not in usados:
                usados.add(chave)
                an.pecas.append(Peca(alvo, alvo.nome, "disco", numero))
                dados_para_reconhecer.append(alvo)
        if not indice_m3u.pedidos:
            an.erros.append(f"“{entrada_m3u.nome}” não lista nenhum disco.")
        an.discos = len(indice_m3u.pedidos)
        an.principal = Peca(entrada_m3u, entrada_m3u.nome, "jogo", None, reescrever_indice(indice_m3u, nomes))
        an.pecas.insert(0, an.principal)
    elif discos_idx:
        discos_idx.sort(key=lambda par: _ordem_natural(par[0].nome))
        if len(discos_idx) == 1:
            entrada, indice = discos_idx[0]
            an.principal = montar_disco(entrada, indice, "jogo", None)
            an.discos = 1
        else:
            # vários discos sem .m3u: o painel monta o índice dos discos
            for numero, (entrada, indice) in enumerate(discos_idx, start=1):
                montar_disco(entrada, indice, "disco", numero)
            an.discos = len(discos_idx)
            an.m3u_gerado = "\n".join(e.nome for e, _ in discos_idx) + "\n"
            dados_m3u = an.m3u_gerado.encode("utf-8")
            virtual = Entrada("jogo.m3u", len(dados_m3u), lambda i, n: dados_m3u[i:i + n])
            an.principal = Peca(virtual, "jogo.m3u", "jogo", None, an.m3u_gerado)
            an.pecas.insert(0, an.principal)
            an.avisos.append(
                f"São {an.discos} discos: o painel montou a lista dos discos (.m3u) na ordem dos nomes — "
                + ", ".join(e.nome for e, _ in discos_idx) + ". Troque de disco pelo menu do emulador."
            )
    elif imagens_unicas or [e for e in resto if e.ext in ("bin", "img")]:
        candidatos = imagens_unicas or [e for e in resto if e.ext in ("bin", "img")]
        if len(candidatos) == 1:
            unica = candidatos[0]
            usados.add(chave_de_nome(unica.nome))
            an.principal = Peca(unica, unica.nome, "jogo")
            an.pecas.append(an.principal)
            an.discos = 1
            dados_para_reconhecer.append(unica)
            if unica.ext == "mdf":
                par = por_chave.get(chave_de_nome(unica.nome.rsplit(".", 1)[0] + ".mds"))
                if par is not None:
                    usados.add(chave_de_nome(par.nome))
                    an.pecas.append(Peca(par, par.nome, "faixa", 1))
            if unica.ext in ("bin", "img"):
                an.avisos.append(
                    f"“{unica.nome}” veio sem o .cue. Se for um disco com música (faixas de áudio), "
                    "o som de CD só funciona com o .cue e todas as faixas."
                )
        else:
            an.erros.append(
                "Vieram vários arquivos de disco sem o índice (.cue). O .cue é que diz a ordem das faixas: "
                "selecione o .cue junto com todos os .bin."
            )
    else:
        jogos = [e for e in resto if e.ext in DE_CARTUCHO or e.ext in PACOTES]
        if len(jogos) == 1:
            usados.add(chave_de_nome(jogos[0].nome))
            an.principal = Peca(jogos[0], jogos[0].nome, "jogo")
            an.pecas.append(an.principal)
            dados_para_reconhecer.append(jogos[0])
        elif len(jogos) > 1:
            an.erros.append("Vieram vários jogos (" + ", ".join(e.nome for e in jogos) + "): envie um jogo por vez.")
        elif not an.erros:
            an.erros.append("Não veio o arquivo do jogo: só BIOS ou arquivos que não abrem sozinhos.")

    # 3. o que sobrou (veio, mas nenhum índice pede) fica de fora
    for entrada in resto:
        if chave_de_nome(entrada.nome) not in usados:
            an.ignorados.append(entrada.nome)
            an.avisos.append(f"“{entrada.nome}” não é pedido por nenhum índice: ficou de fora.")

    # 4. o sistema: pelo conteúdo; depois pela extensão; o escolhido no painel manda
    detectado, como = _reconhecer(an, dados_para_reconhecer)
    an.detectado = detectado
    if sistema_escolhido:
        an.sistema = sistema_escolhido
        an.como = "escolhido"
        if detectado and detectado != sistema_escolhido:
            an.avisos.append(
                f"Os arquivos parecem de {_nome_do_sistema(detectado)}, mas foi escolhido "
                f"{_nome_do_sistema(sistema_escolhido)}. Confira: no sistema errado o jogo não abre."
            )
    else:
        an.sistema = detectado if detectado in SISTEMAS else None
        an.como = como if an.sistema else ""
        if detectado in NAO_SUPORTADOS:
            an.erros.append(f"É um jogo de {NAO_SUPORTADOS[detectado]}, que ainda não roda no navegador.")
        elif not an.sistema and an.principal and not an.erros:
            an.erros.append("Não deu para reconhecer o sistema pelos arquivos: escolha na lista “Sistema”.")

    sistema = SISTEMAS.get(an.sistema)
    if sistema is not None and not sistema.disco:
        an.discos = 0
    if sistema is not None:
        if an.sistema not in ligados:
            an.erros.append(
                f"{sistema.nome}: o emulador disponível ({sistema.nucleo}) tem licença {sistema.licenca}, "
                "que não permite uso no site de uma empresa sem a permissão dos autores. Veja o LEIA-ME."
            )
        _conferir_extensoes(an, sistema)
        _conferir_bios(an, sistema, bios)
        if _nota_vale(sistema, an):
            an.avisos.append(sistema.nota)
    elif bios:
        for entrada in bios:
            an.pecas.append(Peca(entrada, entrada.nome, "bios"))

    return an


def _nota_vale(sistema, an):
    """A nota do sistema só quando diz respeito a este jogo (a do .fds não vale para um .nes)."""
    if not sistema.nota or an.principal is None:
        return False
    if sistema.codigo == "nes":
        return an.principal.entrada.ext == "fds"
    if sistema.codigo == "pce":
        return an.discos > 0
    return True


def _nome_do_sistema(codigo):
    if codigo in SISTEMAS:
        return SISTEMAS[codigo].nome
    return NAO_SUPORTADOS.get(codigo, codigo)


def _reconhecer(an, candidatos):
    """(código, como) pelo conteúdo da faixa de dados ou do jogo; senão pela extensão."""
    principal = an.principal.entrada if an.principal else None
    vistos = []
    for entrada in candidatos + ([principal] if principal else []):
        if entrada is None or entrada in vistos:
            continue
        vistos.append(entrada)
        try:
            if entrada.ext == "pbp" and entrada.pedaco(0, 4) == b"\x00PBP":
                return "psx", "cabeçalho"
            if entrada.ext == "chd":
                continue  # comprimido: o conteúdo não se lê sem descomprimir
            if entrada.ext in ("bin", "img", "iso", "mdf"):
                achado = sistema_do_cd(entrada)
                if achado:
                    return achado, "cabeçalho"
            if entrada.ext in DE_CARTUCHO or entrada.ext == "bin":
                achado = sistema_do_cartucho(entrada)
                if achado:
                    return achado, "cabeçalho"
            if entrada.ext in PACOTES:
                nomes = nomes_no_pacote(entrada)
                if nomes is not None:
                    exts = {extensao(n) for n in nomes}
                    if exts & (INDICES | SO_DE_DISCO):
                        continue  # um disco zipado: o sistema não se lê pela lista
                    dentro = {sistema_pela_extensao(e) for e in exts} - {None}
                    if len(dentro) == 1:
                        return dentro.pop(), "extensão"
                    if not dentro and len(nomes) > 1:
                        # vários .bin/.rom/.u1 sem índice: é o jeito de um jogo de fliperama
                        return "arcade", "extensão"
        except ForaDoTrecho:
            continue
    if principal is not None:
        por_ext = sistema_pela_extensao(principal.ext)
        if por_ext:
            return por_ext, "extensão"
    return None, ""


def _conferir_extensoes(an, sistema):
    if an.principal is None:
        return
    ext = an.principal.entrada.ext if an.principal.conteudo is None else extensao(an.principal.nome)
    if an.m3u_gerado:
        ext = "m3u"
    if ext and ext not in sistema.extensoes and ext not in PACOTES:
        aceitos = ", ".join("." + e for e in sorted(sistema.extensoes))
        an.erros.append(f"O emulador de {sistema.nome} não abre .{ext}. Ele aceita: {aceitos}.")
    if an.m3u_gerado and "m3u" not in sistema.extensoes:
        an.erros.append(f"O emulador de {sistema.nome} não troca de disco: envie um disco só.")


def _conferir_bios(an, sistema, bios):
    nomes_validos = {n.lower() for n in sistema.bios}
    for entrada in bios:
        if chave_de_nome(entrada.nome) in nomes_validos:
            an.pecas.append(Peca(entrada, _nome_oficial_da_bios(sistema, entrada.nome), "bios"))
        else:
            an.avisos.append(f"“{entrada.nome}” é BIOS de outro sistema: ficou de fora.")
            an.ignorados.append(entrada.nome)
    tem_bios = any(p.papel == "bios" for p in an.pecas)
    precisa = sistema.bios_obrigatoria == "sempre" or (sistema.bios_obrigatoria == "cd" and an.discos > 0)
    if precisa and not tem_bios:
        an.erros.append(
            f"{sistema.nome} precisa da BIOS do console para abrir: selecione junto um destes arquivos — "
            + ", ".join(sistema.bios) + "."
        )


def _nome_oficial_da_bios(sistema, nome):
    """A BIOS entra com o nome exato que o núcleo procura (a pasta virtual diferencia maiúscula)."""
    for oficial in sistema.bios:
        if oficial.lower() == chave_de_nome(nome):
            return oficial
    return nome
