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
    #: o núcleo só roda com várias linhas de execução (PSP, DOS): a página do
    #: emulador abre sozinha (fora do quadro) e com o isolamento de origem
    threads: bool = False
    #: as mesmas extensões de outro sistema (C128, VIC-20... usam as do C64):
    #: só quando a equipe escolhe na lista "Sistema" do painel
    so_pela_lista: bool = False


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
    "nds": Sistema(
        "nds", "Nintendo DS", "melonds", "GPL-3.0", True, _ext("nds"),
        bios=("bios7.bin", "bios9.bin", "firmware.bin"), formato="retrato",
        nota="Roda sem BIOS na maior parte dos jogos; se algum pedir, junte bios7.bin, bios9.bin e firmware.bin.",
        comandos="Setas movem · Z = A · X = B · A = Y · S = X · Q/E = L/R · Enter = Start · V = Select. A tela de baixo responde ao toque (ou ao mouse). No celular, o controle aparece na tela.",
    ),
    "atari2600": Sistema(
        "atari2600", "Atari 2600", "stella2014", "GPL-2.0", True, _ext("a26"),
        comandos="Setas movem · Z = botão · Enter = Reset · V = Select. No celular, o controle aparece na tela; um controle USB ou Bluetooth também serve.",
    ),
    "atari7800": Sistema(
        "atari7800", "Atari 7800", "prosystem", "GPL-2.0", True, _ext("a78"),
        bios=("7800 BIOS (U).rom", "7800 BIOS (E).rom"),
        nota="A BIOS é opcional: sem ela, o jogo abre direto.",
        comandos="Setas movem · Z e X = os dois botões · Enter = Pause · V = Select. No celular, o controle aparece na tela.",
    ),
    "c64": Sistema(
        "c64", "Commodore 64", "vice_x64sc", "GPL-2.0", True, _ext("d64", "d71", "d81", "g64", "t64", "tap", "prg", "p00", "crt"),
        nota="Disquete (.d64), fita (.t64/.tap), programa (.prg) ou cartucho (.crt): o emulador carrega e roda sozinho.",
        comandos="Setas e Z = joystick · o teclado do computador é o teclado do C64. No celular, o controle aparece na tela.",
    ),
    "psp": Sistema(
        "psp", "PlayStation Portable (PSP)", "ppsspp", "GPL-2.0", True, _ext("iso", "cso", "pbp"), disco=True,
        threads=True, formato="paisagem",
        nota="Jogo de PSP grande? Envie em .cso (o .iso comprimido): fica com cerca de metade do tamanho e abre igual. "
             "O PSP é o console mais pesado do site: no computador roda bem; no celular, os jogos mais leves.",
        comandos="Setas = analógico · T F G H = direcional · X = ✕ · Z = ○ · S = □ · A = △ · Q/E = L/R · Enter = Start · V = Select. No celular, o controle aparece na tela.",
    ),
    "segaSaturn": Sistema(
        "segaSaturn", "Sega Saturn", "yabause", "GPL-2.0", True,
        _ext("cue", "bin", "img", "ccd", "sub", "iso", "mds", "chd", "m3u"), disco=True,
        bios=("saturn_bios.bin",),
        nota="Roda sem BIOS na maior parte dos jogos (o núcleo imita a do console); se algum pedir, junte saturn_bios.bin. "
             "É um console pesado: abre melhor no computador.",
        comandos="Setas movem · S = A · X = B · Z = C · A = X · Q = Y · E = Z · Tab/R = L/R · Enter = Start. No celular, o controle aparece na tela.",
    ),
    "vb": Sistema(
        "vb", "Virtual Boy (Nintendo)", "beetle_vb", "GPL-2.0", True, _ext("vb", "vboy"), formato="paisagem",
        comandos="Setas = direcional esquerdo · T F G H = direcional direito · Z = A · X = B · Q/E = L/R · Enter = Start · V = Select.",
    ),
    "ngp": Sistema(
        "ngp", "Neo Geo Pocket / Color", "mednafen_ngp", "GPL-2.0", True, _ext("ngp", "ngc"), formato="quadrado",
        comandos="Setas movem · X = A · Z = B · Enter = Option. No celular, o controle aparece na tela.",
    ),
    "ws": Sistema(
        "ws", "WonderSwan / Color", "mednafen_wswan", "GPL-2.0", True, _ext("ws", "wsc", "pc2"), formato="portatil",
        comandos="Setas = cruz X · R, Tab, Q, E = cruz Y (cima, baixo, esquerda, direita) · Z = A · X = B · Enter = Start.",
    ),
    "atari5200": Sistema(
        "atari5200", "Atari 5200", "a5200", "GPL-2.0", True, _ext("a52"), bios=("5200.rom",),
        nota="Se o jogo não abrir, junte a BIOS 5200.rom.",
        comandos="Setas movem · Z e X = os botões de disparo · Enter = Start. No celular, o controle aparece na tela.",
    ),
    "jaguar": Sistema(
        "jaguar", "Atari Jaguar", "virtualjaguar", "GPL-3.0", True, _ext("j64", "jag", "abs", "cof"),
        nota="O Jaguar é pesado para o navegador: alguns jogos ficam lentos, principalmente no celular.",
        comandos="Setas movem · Z = A · X = B · S = C · V = Pause · Enter = Option. No celular, o controle aparece na tela.",
    ),
    "coleco": Sistema(
        "coleco", "ColecoVision", "gearcoleco", "GPL-3.0", True, _ext("col", "cv"),
        bios=("colecovision.rom",), bios_obrigatoria="sempre",
        comandos="Setas movem · Z = botão esquerdo · X = botão direito · A, S, E, Q, R, Tab = teclas 1 a 6 · V = * · Enter = #.",
    ),
    "pcfx": Sistema(
        "pcfx", "PC-FX (NEC)", "mednafen_pcfx", "GPL-2.0", True, _ext("cue", "bin", "img", "ccd", "toc", "chd"), disco=True,
        bios=("pcfx.rom",), bios_obrigatoria="sempre", so_pela_lista=True,
        comandos="Setas movem · Z = I · X = II · A = III · S = IV · Q = V · E = VI · Enter = Run · V = Select.",
    ),
    "amiga": Sistema(
        "amiga", "Commodore Amiga", "puae", "GPL-2.0", True, _ext("adf", "adz", "dms", "fdi", "ipf", "hdf", "hdz", "lha"),
        bios=("kick34005.A500", "kick40063.A600", "kick40068.A1200"),
        nota="Roda sem a Kickstart original (o núcleo usa uma livre, a AROS); jogo que não abrir pede a Kickstart (kick34005.A500).",
        comandos="Setas e X = joystick e botão · o teclado e o mouse do computador são os do Amiga. No celular, o controle aparece na tela.",
    ),
    "dos": Sistema(
        "dos", "PC antigo (MS-DOS)", "dosbox_pure", "GPL-2.0", True, _ext("zip", "dosz", "exe", "com", "bat"),
        threads=True, formato="classico",
        nota="Envie a pasta do jogo zipada (.zip, com o .exe dentro) ou o .exe/.com sozinho; o DOSBox abre o programa. "
             "Só programas de MS-DOS: programa de Windows não roda no navegador.",
        comandos="O teclado e o mouse do computador são os do PC antigo. No celular, o controle da tela vira as setas e os botões; jogo que pede digitação precisa de um teclado Bluetooth.",
    ),
    "c128": Sistema(
        "c128", "Commodore 128", "vice_x128", "GPL-2.0", True, _ext("d64", "d71", "d81", "g64", "t64", "tap", "prg", "p00", "crt"),
        so_pela_lista=True,
        comandos="Setas e Z = joystick · o teclado do computador é o teclado do C128.",
    ),
    "vic20": Sistema(
        "vic20", "Commodore VIC-20", "vice_xvic", "GPL-2.0", True, _ext("d64", "t64", "tap", "prg", "p00", "crt", "20", "40", "60", "a0", "b0"),
        so_pela_lista=True,
        comandos="Setas e Z = joystick · o teclado do computador é o teclado do VIC-20.",
    ),
    "plus4": Sistema(
        "plus4", "Commodore Plus/4 e 16", "vice_xplus4", "GPL-2.0", True, _ext("d64", "t64", "tap", "prg", "p00", "crt"),
        so_pela_lista=True,
        comandos="Setas e Z = joystick · o teclado do computador é o teclado do Plus/4.",
    ),
    "pet": Sistema(
        "pet", "Commodore PET", "vice_xpet", "GPL-2.0", True, _ext("d64", "t64", "tap", "prg", "p00"),
        so_pela_lista=True,
        comandos="O teclado do computador é o teclado do PET.",
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
        nota="O .zip precisa ter o nome exato do jogo no FinalBurn Neo (ex.: sf2.zip) e ser da versão atual do FinalBurn "
             "Neo: um set de outra versão (feito para outro MAME) costuma não abrir, mesmo com o nome certo.",
        comandos="Setas movem · Z, X, A, S = botões 1 a 4 · V = ficha (moeda) · Enter = Start.",
    ),
    "mame": Sistema(
        "mame", "Fliperama (MAME 2003-Plus)", "mame2003_plus", "não comercial (MAME)", False, _ext("zip", "7z"),
        so_pela_lista=True,
        nota="Para o jogo que o FinalBurn Neo não tem: o .zip com o nome exato do jogo no MAME 2003-Plus (ex.: pacman.zip), "
             "no formato do MAME 0.78 -- set de MAME novo costuma não abrir.",
        comandos="Setas movem · Z, X, A, S = botões 1 a 4 · V = ficha (moeda) · Enter = Start.",
    ),
    "sega32x": Sistema(
        "sega32x", "Sega 32X", "picodrive", "não comercial (PicoDrive)", False, _ext("32x"),
        comandos="Setas movem · S = A · X = B · Z = C · Q = X · A = Y · E = Z · Enter = Start · V = Mode.",
    ),
    "lynx": Sistema(
        "lynx", "Atari Lynx", "handy", "não confirmada (o pacote do Handy não traz a licença)", False, _ext("lnx"),
        bios=("lynxboot.img",), bios_obrigatoria="sempre", formato="paisagem",
        comandos="Setas movem · Z = A · X = B · Q/E = Option 1 e 2 · Enter = Pause.",
    ),
    "3do": Sistema(
        "3do", "3DO", "opera", "não confirmada (o pacote do Opera não traz a licença)", False,
        _ext("cue", "bin", "iso", "chd", "img"), disco=True,
        bios=("panafz10.bin", "panafz1.bin", "goldstar.bin", "sanyotry.bin", "panafz10-norsa.bin"), bios_obrigatoria="sempre",
        comandos="Setas movem · S = A · X = B · Z = C · Q/E = L/R · Enter = Play (P) · V = Stop (X).",
    ),
}

#: Reconhecidos só para avisar que não rodam no navegador.
NAO_SUPORTADOS = {
    "pokemini": "Pokémon Mini",
    "ps2": "PlayStation 2",
    "dreamcast": "Dreamcast",
    "gamecube": "GameCube",
    "wii": "Wii",
    "switch": "Nintendo Switch",
    "3ds": "Nintendo 3DS",
    "windows": "Windows",
}

#: Por que não roda -- o painel mostra isto, para ninguém ficar tentando.
MOTIVO_NAO_SUPORTADO = {
    "pokemini": "o emulador do site (EmulatorJS) ainda não tem núcleo de Pokémon Mini; o PokeMini existe para "
                "computador e Android, mas não foi preparado para navegador.",
    "ps2": "não existe emulador de PlayStation 2 que rode no navegador, e um DVD (4 a 8 GB) não cabe na memória de uma aba. "
           "No celular, PS2 só roda em aplicativo instalado (Android com processador forte), nunca num site.",
    "dreamcast": "não existe emulador de Dreamcast que rode no navegador.",
    "gamecube": "não existe emulador de GameCube que rode no navegador (o Dolphin só roda instalado no computador ou no Android).",
    "wii": "não existe emulador de Wii que rode no navegador (o Dolphin só roda instalado no computador ou no Android).",
    "switch": "não existe emulador de Switch que rode no navegador, e os de computador exigem as chaves do console.",
    "3ds": "não existe emulador de 3DS que rode no navegador (o Azahar, que sucedeu o Citra, só roda instalado no computador "
           "ou no Android), e o .3ds tirado do cartucho costuma vir criptografado. Jogo de 3DS fica fora do site e do APK/.exe.",
    "windows": "é um programa de Windows (.exe) -- o navegador não roda programas de Windows, nem launchers como o TeknoParrot. "
               "Roda programa de MS-DOS (PC antigo). Jogo de Windows feito por vocês: exporte a versão Web no Godot ou no Unity "
               "e cadastre o link; o .exe pode ficar guardado em \"Versão para computador\".",
}

#: Extensões que já dizem o console que não roda (não precisam nem ser lidas).
EXTENSOES_NAO_SUPORTADAS = {
    "gcm": "gamecube", "gcz": "gamecube", "rvz": "gamecube", "wbfs": "wii", "wad": "wii",
    "nsp": "switch", "xci": "switch", "nsz": "switch", "3ds": "3ds", "cia": "3ds", "cci": "3ds", "cdi": "dreamcast",
    "gdi": "dreamcast", "dll": "windows", "msi": "windows", "lnk": "windows", "min": "pokemini",
}

#: O maior arquivo que um navegador consegue abrir: o jogo inteiro precisa caber
#: na memória da aba (e o emulador ainda faz uma cópia). Acima disso, nem no computador.
MAX_NO_NAVEGADOR = 2048 * MB
#: Daqui para cima, o celular costuma não ter memória para o jogo.
GRANDE_PARA_CELULAR = 700 * MB
#: Fliperama de placa (o que o FinalBurn e o MAME rodam) cabe em bem menos que isto;
#: um .zip maior é de fliperama baseado em PC (Pac-Man Battle Royale, Taito Type X,
#: Sega Lindbergh -- os do TeknoParrot), que precisa de Windows.
MAX_FLIPERAMA = 400 * MB

INDICES = _ext("cue", "ccd", "toc", "m3u")
#: O que pode ser a faixa ou a imagem de um disco.
DE_DISCO = _ext("bin", "img", "iso", "sub", "mdf", "mds", "cbn", "chd", "pbp", "cso")
#: Cartucho, inclusive o de console que também tem CD (o .pce do PC Engine).
DE_CARTUCHO = (frozenset().union(*(s.extensoes for s in SISTEMAS.values() if not s.disco)) | _ext("pce")) - _ext("bin", "zip", "7z")
#: Imagem de disco que nunca é cartucho.
SO_DE_DISCO = _ext("iso", "chd", "pbp", "img", "cbn", "mdf", "cso")
PACOTES = _ext("zip", "7z")
#: Vem junto quando se seleciona a pasta inteira; fica de fora, com aviso.
IGNORADOS = _ext("txt", "nfo", "sfv", "md5", "sha1", "dat", "jpg", "jpeg", "png", "gif", "pdf", "url", "ini", "db", "htm", "html", "xml", "log")

BIOS_CONHECIDAS = {nome.lower(): codigo for codigo, sistema in SISTEMAS.items() for nome in sistema.bios}
#: Todas as extensões que o painel sabe o que são (o resto, solto, costuma ser peça de fliperama).
CONHECIDAS = DE_CARTUCHO | DE_DISCO | INDICES | PACOTES | IGNORADOS


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


def sistemas_para(particular=False, settings=None):
    """Os sistemas que um jogo pode usar.

    O jogo PARTICULAR (só a equipe vê e joga; fora do portal e do Google) usa
    todos os reconhecidos -- inclusive os de licença não comercial, que
    permitem o uso que não é comercial. O jogo público segue
    `sistemas_ligados()`.
    """
    if particular:
        return list(SISTEMAS)
    return sistemas_ligados(settings)


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


_GAMECUBE = bytes.fromhex("C2339F3D")  # no byte 0x1C do disco
_WII = bytes.fromhex("5D1C9EA3")       # no byte 0x18


def _e_umd_de_psp(entrada, pvd):
    """O disco (UMD) de PSP: "PSP GAME" no descritor do volume, ou a pasta PSP_GAME na raiz."""
    if pvd[1:6] != b"CD001":
        return False
    if pvd[8:16] == b"PSP GAME":
        return True
    raiz = int.from_bytes(pvd[158:162], "little") if len(pvd) >= 162 else 0
    if 0 < raiz < 4096:
        try:
            return b"PSP_GAME" in entrada.pedaco(raiz * 2048, 2048)
        except ForaDoTrecho:
            return False
    return False


def sistema_do_cd(entrada):
    """O sistema de uma faixa de dados de CD, ou None. Pode levantar ForaDoTrecho."""
    comeco = entrada.pedaco(0, 32)
    if comeco[0x1C:0x20] == _GAMECUBE:
        return "gamecube"
    if comeco[0x18:0x1C] == _WII:
        return "wii"
    if entrada.tamanho > MAX_CD:
        pvd = _setor_de_dados(entrada, 16)
        if _e_umd_de_psp(entrada, pvd):
            return "psp"
        if pvd[1:6] == b"CD001" and pvd[8:19] == b"PLAYSTATION":
            return "ps2"
        return None
    if comeco[:12] != SYNC and _e_umd_de_psp(entrada, _setor_de_dados(entrada, 16)):
        return "psp"
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


def _categoria_do_pbp(entrada):
    """A CATEGORY do PARAM.SFO de um EBOOT.PBP ("ME" = PS1; "MG", "UG"... = PSP), ou ""."""
    cabeca = entrada.pedaco(0, 40)
    if cabeca[:4] != b"\x00PBP" or len(cabeca) < 40:
        return ""
    inicio = int.from_bytes(cabeca[8:12], "little")
    fim = int.from_bytes(cabeca[12:16], "little")
    if not (40 <= inicio < fim) or fim - inicio > 65536:
        return ""
    sfo = entrada.pedaco(inicio, fim - inicio)
    if sfo[:4] != b"\x00PSF" or len(sfo) < 20:
        return ""
    chaves = int.from_bytes(sfo[8:12], "little")
    valores = int.from_bytes(sfo[12:16], "little")
    for i in range(min(int.from_bytes(sfo[16:20], "little"), 64)):
        item = sfo[20 + i * 16: 36 + i * 16]
        if len(item) < 16:
            break
        desloc_chave = chaves + int.from_bytes(item[0:2], "little")
        chave = sfo[desloc_chave: sfo.find(b"\x00", desloc_chave)]
        if chave == b"CATEGORY":
            desloc = valores + int.from_bytes(item[12:16], "little")
            tamanho = int.from_bytes(item[4:8], "little")
            return sfo[desloc: desloc + tamanho].rstrip(b"\x00").decode("ascii", "replace")
    return ""


def sistema_do_pbp(entrada):
    """O EBOOT.PBP é do PS1 (PSone Classic, a categoria "ME") ou um jogo de PSP."""
    try:
        categoria = _categoria_do_pbp(entrada)
    except ForaDoTrecho:
        categoria = ""
    return "psp" if categoria and categoria != "ME" else "psx"


def exe_de_windows(dados):
    """O começo de um .exe é de Windows (PE) -- e não de MS-DOS (MZ puro)?"""
    if dados[:2] != b"MZ" or len(dados) < 0x40:
        return False
    novo = int.from_bytes(dados[0x3C:0x40], "little")
    if not 0x40 <= novo <= len(dados) - 4:
        return False
    # PE = Windows; NE = Windows 3.x. LE/LX são os extensores de DOS (DOS/4GW): rodam no DOSBox
    return dados[novo:novo + 4] == b"PE\x00\x00" or dados[novo:novo + 2] == b"NE"


# ---------------------------------------------------------------------------
# A ficha técnica do arquivo: o que o cabeçalho diz (para achar o problema)
# ---------------------------------------------------------------------------

def _texto_do_cabecalho(bruto):
    return bruto.decode("latin-1", "replace").replace("\x00", " ").strip()


def _ficha_snes(entrada):
    copiadora = 512 if entrada.tamanho % 1024 == 512 else 0
    melhor = None
    for base, mapa in ((0x7FC0, "LoROM"), (0xFFC0, "HiROM"), (0x40FFC0, "ExHiROM")):
        cab = entrada.pedaco(copiadora + base, 32)
        if len(cab) < 32:
            continue
        soma = cab[0x1E] | cab[0x1F] << 8
        complemento = cab[0x1C] | cab[0x1D] << 8
        certa = soma ^ complemento == 0xFFFF and soma not in (0, 0xFFFF)
        titulo = _texto_do_cabecalho(cab[:21])
        legivel = sum(32 <= c < 127 for c in cab[:21]) >= 15
        if certa or (legivel and melhor is None):
            melhor = (mapa, titulo, certa, cab)
            if certa:
                break
    if melhor is None:
        return ["Não achei o cabeçalho do Super Nintendo: o arquivo pode não ser uma ROM de SNES, ou estar corrompido."]
    mapa, titulo, certa, cab = melhor
    rapida = " FastROM" if cab[0x15] & 0x10 else ""
    tamanho = entrada.tamanho - copiadora
    linhas = [f"Super Nintendo · título interno “{titulo or 'sem título'}” · {mapa}{rapida} · {_mb(tamanho)}"]
    if copiadora:
        linhas.append("Tem o cabeçalho de copiadora de 512 bytes (.smc antigo): normal, o emulador ignora.")
    if tamanho % (128 * 1024):
        linhas.append("O tamanho não é múltiplo de 128 KB: a ROM pode estar cortada ou ter lixo no fim.")
    linhas.append("Soma de verificação certa: a ROM parece íntegra." if certa else
                  "A soma de verificação não bate: ROM modificada (hack, tradução) ou corrompida. Muitas abrem assim mesmo; "
                  "se esta não abrir, use uma cópia sem modificação.")
    return linhas


def _ficha_mega(entrada):
    if entrada.ext == "smd" or (b"SEGA" not in entrada.pedaco(0x100, 16) and entrada.tamanho % 16384 == 512):
        return ["Mega Drive no formato .smd (o de copiadora, intercalado): o emulador converte sozinho.",
                f"Tamanho: {_mb(entrada.tamanho - 512)}."]
    cab = entrada.pedaco(0x100, 0x100)
    if len(cab) < 0x100 or b"SEGA" not in cab[:16]:
        return ["Não achei o cabeçalho “SEGA” no lugar do Mega Drive (0x100): o arquivo pode ser de outro console ou estar corrompido."]
    console = _texto_do_cabecalho(cab[:16])
    titulo = _texto_do_cabecalho(cab[0x50:0x80]) or _texto_do_cabecalho(cab[0x20:0x50])
    regiao = _texto_do_cabecalho(cab[0xF0:0xF3])
    nomes = {"J": "Japão", "U": "EUA", "E": "Europa", "4": "EUA", "8": "Europa", "1": "Japão", "F": "todas"}
    regioes = ", ".join(dict.fromkeys(nomes[c] for c in regiao if c in nomes)) or regiao or "não informada"
    return [f"{console} · título “{titulo or 'sem título'}” · região: {regioes} · {_mb(entrada.tamanho)}"]


def _ficha_nes(entrada):
    cab = entrada.pedaco(0, 16)
    if cab[:4] != b"NES\x1a":
        return ["Sem o cabeçalho iNES (“NES” + 1A): o emulador não sabe o formato do cartucho -- use a ROM .nes com cabeçalho."]
    mapper = (cab[6] >> 4) | (cab[7] & 0xF0)
    formato = "NES 2.0" if cab[7] & 0x0C == 0x08 else "iNES"
    return [f"NES · {formato} · mapper {mapper} · {cab[4] * 16} KB de programa, {cab[5] * 8} KB de gráficos"]


def _ficha_gb(entrada):
    if entrada.pedaco(4, 8) == _LOGO_GBA:
        return [f"Game Boy Advance · título “{_texto_do_cabecalho(entrada.pedaco(0xA0, 12)) or 'sem título'}” · "
                f"código {_texto_do_cabecalho(entrada.pedaco(0xAC, 4))} · {_mb(entrada.tamanho)}"]
    cor = " Color" if entrada.pedaco(0x143, 1) in (b"\x80", b"\xc0") else ""
    return [f"Game Boy{cor} · título “{_texto_do_cabecalho(entrada.pedaco(0x134, 11)) or 'sem título'}” · {_mb(entrada.tamanho)}"]


def _ficha_n64(entrada):
    comeco = entrada.pedaco(0, 0x40)
    ordem = {bytes.fromhex("80371240"): ("z64", "big-endian, o formato padrão"),
             bytes.fromhex("37804012"): ("v64", "byte-swapped"),
             bytes.fromhex("40123780"): ("n64", "little-endian")}.get(comeco[:4], ("?", "desconhecida"))
    nome = comeco[0x20:0x34]
    if ordem[0] == "v64":
        nome = bytes(b for par in zip(nome[1::2], nome[0::2]) for b in par)
    elif ordem[0] == "n64":
        nome = bytes(b for i in range(0, len(nome), 4) for b in reversed(nome[i:i + 4]))
    return [f"Nintendo 64 · título “{_texto_do_cabecalho(nome) or 'sem título'}” · ordem dos bytes {ordem[0]} ({ordem[1]}) · "
            f"{_mb(entrada.tamanho)}. O emulador abre as três ordens."]


def ficha_do_arquivo(entrada, sistema):
    """O que o cabeçalho do arquivo diz (título interno, formato, integridade), em linhas para o painel."""
    try:
        if entrada.ext in PACOTES:
            nomes = nomes_no_pacote(entrada)
            if nomes:
                return [f"Pacote .{entrada.ext} com {len(nomes)} arquivo(s): " + ", ".join(nomes[:6]) + ("…" if len(nomes) > 6 else "")]
            return []
        if sistema == "snes":
            return _ficha_snes(entrada)
        if sistema in ("segaMD", "sega32x"):
            return _ficha_mega(entrada)
        if sistema == "nes" and entrada.ext != "fds":
            return _ficha_nes(entrada)
        if sistema in ("gb", "gba"):
            return _ficha_gb(entrada)
        if sistema == "n64":
            return _ficha_n64(entrada)
    except ForaDoTrecho:
        return []
    return []


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
    candidatos = [c for c, s in SISTEMAS.items() if ext in s.extensoes and not s.so_pela_lista]
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
    #: o que o cabeçalho do arquivo principal diz (título interno, formato, integridade)
    ficha: list = field(default_factory=list)

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
            "ficha": self.ficha,
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
    desconhecidos = []
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
        elif ext in EXTENSOES_NAO_SUPORTADAS:
            console = EXTENSOES_NAO_SUPORTADAS[ext]
            an.erros.append(f"“{entrada.nome}” é de {NAO_SUPORTADOS[console]}: {MOTIVO_NAO_SUPORTADO[console]}")
        else:
            desconhecidos.append(entrada.nome)
    if len(desconhecidos) >= 2 and not uteis:
        # pm1.ic2, pm2.6e, u1... soltos: são as peças (chips) de um jogo de fliperama
        an.erros.append(
            f"Vieram {len(desconhecidos)} arquivos soltos ({', '.join(desconhecidos[:4])}{'…' if len(desconhecidos) > 4 else ''}): "
            "parecem as peças (chips) de um jogo de fliperama. Arraste a PASTA do jogo -- o painel monta o .zip com o "
            "nome dela -- ou envie o .zip pronto com o nome exato do jogo (ex.: pacman.zip)."
        )
    else:
        for nome in desconhecidos:
            an.erros.append(f"“{nome}”: formato .{extensao(nome) or '?'} não é de jogo que o emulador abre.")
    if len(uteis) > MAX_ARQUIVOS:
        an.erros.append(f"São {len(uteis)} arquivos; o limite é {MAX_ARQUIVOS} por jogo.")
        return an
    por_chave = {chave_de_nome(e.nome): e for e in uteis}

    for entrada in uteis:
        if entrada.tamanho > MAX_NO_NAVEGADOR:
            an.erros.append(
                f"“{entrada.nome}” tem {_mb(entrada.tamanho)}: nenhum navegador abre um arquivo desse tamanho (o jogo "
                f"inteiro precisa caber na memória da aba; o teto é {_mb(MAX_NO_NAVEGADOR)}, e no celular bem menos). "
                "Jogo de DVD (PS2, GameCube, Wii) não roda em site."
            )
    if sum(e.tamanho for e in uteis) > GRANDE_PARA_CELULAR and not an.erros:
        an.avisos.append(
            f"Jogo grande ({_mb(sum(e.tamanho for e in uteis))}): no computador abre; no celular, só nos aparelhos com "
            "bastante memória. Jogo de PSP fica com cerca de metade do tamanho em .cso."
        )
    if limite_por_arquivo:
        for entrada in uteis:
            if entrada.tamanho > limite_por_arquivo and entrada.tamanho <= MAX_NO_NAVEGADOR:
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
    imagens_unicas = [e for e in resto if e.ext in ("chd", "pbp", "iso", "mdf", "cbn", "cso")]

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
            an.erros.append(
                f"É {'um programa' if detectado == 'windows' else 'um jogo'} de {NAO_SUPORTADOS[detectado]}, "
                f"que não roda no navegador: {MOTIVO_NAO_SUPORTADO.get(detectado, '')}".rstrip(": ")
            )
        elif not an.sistema and an.principal and not an.erros:
            an.erros.append("Não deu para reconhecer o sistema pelos arquivos: escolha na lista “Sistema”.")

    if an.principal is not None and an.principal.conteudo is None:
        an.ficha = ficha_do_arquivo(an.principal.entrada, an.sistema or an.detectado)
    sistema = SISTEMAS.get(an.sistema)
    if an.sistema in ("arcade", "mame") and an.principal is not None and an.principal.entrada.tamanho > MAX_FLIPERAMA:
        an.erros.append(
            f"“{an.principal.nome}” tem {_mb(an.principal.entrada.tamanho)}: fliperama desse tamanho não é de placa (os que o "
            "FinalBurn Neo e o MAME rodam ficam bem abaixo de 400 MB). É fliperama baseado em PC -- como o Pac-Man Battle "
            "Royale (pacmanbr), Taito Type X e Sega Lindbergh, os do TeknoParrot --, que roda num Windows de verdade, não no navegador."
        )
    if sistema is not None and not sistema.disco:
        an.discos = 0
    if sistema is not None:
        if an.sistema not in ligados:
            an.erros.append(
                f"{sistema.nome} ainda não roda no site: o único emulador de {sistema.nome} para navegador "
                f"({sistema.nucleo}) tem licença {sistema.licenca} e só pode ser usado no site de uma empresa "
                "com a permissão dos autores dele. Com a permissão, o dono do site liga no Render a variável "
                f"JOGOS_EMULADORES_NAO_COMERCIAIS={sistema.codigo} (LEIA-ME-V10.txt, seção 20). Para jogar sem "
                "publicar, marque o jogo como Particular (só a equipe vê): aí ele roda."
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
                return sistema_do_pbp(entrada), "cabeçalho"
            if entrada.ext == "cso" and entrada.pedaco(0, 4) in (b"CISO", b"ZISO"):
                return "psp", "cabeçalho"
            if entrada.ext == "chd":
                continue  # comprimido: o conteúdo não se lê sem descomprimir
            if entrada.ext == "exe":
                return ("windows" if exe_de_windows(entrada.pedaco(0, 4096)) else "dos"), "cabeçalho"
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
                    if exts & {"exe", "com", "bat"}:
                        # a pasta de um programa de PC zipada: de MS-DOS ou de Windows?
                        return ("windows" if _zip_de_windows(entrada, nomes) else "dos"), "extensão"
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


def _zip_de_windows(entrada, nomes):
    """Um .zip de programa de PC é de Windows: traz .dll, ou o .exe principal é de Windows."""
    if any(extensao(n) == "dll" for n in nomes):
        return True
    executaveis = sorted((n for n in nomes if extensao(n) == "exe"), key=lambda n: (n.count("/"), len(n)))
    if not executaveis:
        return False
    try:
        with zipfile.ZipFile(_ArquivoPorTrechos(entrada)) as pacote:
            with pacote.open(executaveis[0]) as arquivo:
                return exe_de_windows(arquivo.read(4096))
    except (zipfile.BadZipFile, ForaDoTrecho, OSError, ValueError, EOFError, RuntimeError, NotImplementedError):
        return False  # não deu para ler o .exe de dentro: fica como DOS (o DOSBox diz se não for)


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


# ---------------------------------------------------------------- comandos de cada console
#
# O MAPA DE TECLAS É O DO PRÓPRIO EMULADOR (EmulatorJS 4.2.3, defaultControllers):
# Z = A, X = B, A = X, S = Y, Q/E = L/R, Tab/R = L2/R2, Enter = Start, V = Select,
# setas = direcional. Cada console dá um nome próprio a cada botão (o ✕ do
# PlayStation é o "B" do emulador); a lista abaixo é o que a página mostra em
# "No computador", tecla por tecla. No celular o emulador desenha o controle por
# cima do jogo, com os mesmos nomes. Mudar uma tecla aqui sem mudar no emulador
# ensina errado: as duas coisas andam juntas.
#
# (ação, teclas no computador, onde fica no controle da tela do celular)
_DIRECIONAL = ("Mover", ("←", "↑", "→", "↓"), "o direcional, à esquerda")
_START = ("Start", ("Enter",), "START, embaixo")
_SELECT = ("Select", ("V",), "SELECT, embaixo")
CONTROLES = {
    "psx": (_DIRECIONAL, ("✕", ("X",), "✕, à direita"), ("○", ("Z",), "○, à direita"), ("□", ("S",), "□, à direita"),
            ("△", ("A",), "△, à direita"), ("L1 / R1", ("Q", "E"), "L1 e R1, em cima"), ("L2 / R2", ("Tab", "R"), "L2 e R2, em cima"),
            _START, _SELECT),
    "nes": (_DIRECIONAL, ("A", ("Z",), "A, à direita"), ("B", ("X",), "B, à direita"), _START, _SELECT),
    "gb": (_DIRECIONAL, ("A", ("Z",), "A, à direita"), ("B", ("X",), "B, à direita"), _START, _SELECT),
    "gba": (_DIRECIONAL, ("A", ("Z",), "A, à direita"), ("B", ("X",), "B, à direita"), ("L / R", ("Q", "E"), "L e R, em cima"), _START, _SELECT),
    "n64": (("Analógico", ("←", "↑", "→", "↓"), "o analógico, à esquerda"), ("A", ("X",), "A, à direita"), ("B", ("S",), "B, à direita"),
            ("Z (gatilho)", ("Tab",), "Z"), ("L / R", ("Q", "E"), "L e R, em cima"), ("Botões C", ("I", "J", "K", "L"), "os botões C"),
            ("Direcional (cruz)", ("T", "F", "G", "H"), "a cruz"), _START),
    "pce": (_DIRECIONAL, ("I", ("Z",), "I, à direita"), ("II", ("X",), "II, à direita"), ("Run", ("Enter",), "RUN, embaixo"), _SELECT),
    "nds": (_DIRECIONAL, ("A", ("Z",), "A"), ("B", ("X",), "B"), ("X", ("A",), "X"), ("Y", ("S",), "Y"), ("L / R", ("Q", "E"), "L e R, em cima"),
            ("Tela de baixo", ("Clique do mouse",), "toque direto na tela de baixo"), _START, _SELECT),
    "atari2600": (_DIRECIONAL, ("Disparo", ("X",), "o botão de disparo"), ("Reset (começar)", ("Enter",), "RESET"), ("Select", ("V",), "SELECT")),
    "atari7800": (_DIRECIONAL, ("Botão 1", ("X",), "botão 1"), ("Botão 2", ("Z",), "botão 2"), ("Pause", ("Enter",), "PAUSE"),
                  ("Reset", ("A",), "RESET"), ("Select", ("V",), "SELECT")),
    "c64": (("Teclado do C64", ("Teclado do computador",), "o teclado aparece no botão de teclado da barra"),
            ("Joystick", ("←", "↑", "→", "↓"), "o direcional, à esquerda"), ("Disparo", ("X",), "o botão de disparo")),
    "psp": (("Analógico", ("←", "↑", "→", "↓"), "o analógico, à esquerda"), ("✕", ("X",), "✕, à direita"), ("○", ("Z",), "○, à direita"),
            ("□", ("S",), "□, à direita"), ("△", ("A",), "△, à direita"), ("L / R", ("Q", "E"), "L e R, em cima"),
            ("Direcional (cruz)", ("T", "F", "G", "H"), "a cruz, à esquerda"), _START, _SELECT),
    "segaSaturn": (_DIRECIONAL, ("A", ("S",), "A"), ("B", ("X",), "B"), ("C", ("Z",), "C"), ("X", ("A",), "X"), ("Y", ("Q",), "Y"),
                   ("Z", ("E",), "Z"), ("L / R", ("Tab", "R"), "L e R, em cima"), _START),
    "vb": (("Direcional esquerdo", ("←", "↑", "→", "↓"), "o direcional da esquerda"), ("Direcional direito", ("T", "F", "G", "H"), "o direcional da direita"),
           ("A", ("Z",), "A"), ("B", ("X",), "B"), ("L / R", ("Q", "E"), "L e R, em cima"), _START, _SELECT),
    "ngp": (_DIRECIONAL, ("A", ("X",), "A"), ("B", ("Z",), "B"), ("Option", ("Enter",), "OPTION")),
    "ws": (("Cruz X", ("←", "↑", "→", "↓"), "a cruz da esquerda"), ("Cruz Y", ("R", "Tab", "Q", "E"), "a segunda cruz (cima, baixo, esquerda, direita)"),
           ("A", ("Z",), "A"), ("B", ("X",), "B"), _START),
    "atari5200": (_DIRECIONAL, ("Disparo", ("Z", "X"), "os botões de disparo"), _START),
    "jaguar": (_DIRECIONAL, ("A", ("Z",), "A"), ("B", ("X",), "B"), ("C", ("S",), "C"), ("Pause", ("V",), "PAUSE"), ("Option", ("Enter",), "OPTION")),
    "coleco": (_DIRECIONAL, ("Botão esquerdo", ("Z",), "botão esquerdo"), ("Botão direito", ("X",), "botão direito"),
               ("Teclas 1 a 6", ("A", "S", "E", "Q", "R", "Tab"), "o teclado numérico do controle"), ("* e #", ("V", "Enter"), "* e #")),
    "pcfx": (_DIRECIONAL, ("I e II", ("Z", "X"), "I e II"), ("III e IV", ("A", "S"), "III e IV"), ("V e VI", ("Q", "E"), "V e VI"),
             ("Run", ("Enter",), "RUN"), ("Select", ("V",), "SELECT")),
    "amiga": (("Joystick", ("←", "↑", "→", "↓"), "o direcional"), ("Botão do joystick", ("X",), "o botão"),
              ("Teclado e mouse do Amiga", ("Teclado do computador", "Mouse"), "o teclado aparece no botão de teclado da barra")),
    "dos": (("Teclado do PC antigo", ("Teclado do computador",), "o controle da tela manda as setas e os botões"),
            ("Mouse", ("Mouse",), "toque na tela"), ("Joystick", ("Controle USB ou Bluetooth",), "o controle da tela")),
    "c128": (("Teclado do C128", ("Teclado do computador",), "o teclado aparece no botão de teclado da barra"),
             ("Joystick", ("←", "↑", "→", "↓"), "o direcional"), ("Disparo", ("X",), "o botão de disparo")),
    "vic20": (("Teclado do VIC-20", ("Teclado do computador",), "o teclado aparece no botão de teclado da barra"),
              ("Joystick", ("←", "↑", "→", "↓"), "o direcional"), ("Disparo", ("X",), "o botão de disparo")),
    "plus4": (("Teclado do Plus/4", ("Teclado do computador",), "o teclado aparece no botão de teclado da barra"),
              ("Joystick", ("←", "↑", "→", "↓"), "o direcional"), ("Disparo", ("X",), "o botão de disparo")),
    "pet": (("Teclado do PET", ("Teclado do computador",), "o teclado aparece no botão de teclado da barra"),),
    "sega32x": (_DIRECIONAL, ("A", ("S",), "A"), ("B", ("X",), "B"), ("C", ("Z",), "C"), ("X", ("Q",), "X"), ("Y", ("A",), "Y"),
                ("Z", ("E",), "Z"), _START, ("Mode", ("V",), "MODE")),
    "lynx": (_DIRECIONAL, ("A", ("Z",), "A"), ("B", ("X",), "B"), ("Option 1 / 2", ("Q", "E"), "OPTION 1 e 2"), ("Pause", ("Enter",), "PAUSE")),
    "3do": (_DIRECIONAL, ("A", ("S",), "A"), ("B", ("X",), "B"), ("C", ("Z",), "C"), ("L / R", ("Q", "E"), "L e R, em cima"),
            ("Play (P)", ("Enter",), "P"), ("Stop (X)", ("V",), "X")),
    "segaMS": (_DIRECIONAL, ("Botão 1 (e Start)", ("X",), "botão 1"), ("Botão 2", ("Z",), "botão 2")),
    "segaGG": (_DIRECIONAL, ("Botão 1", ("X",), "botão 1"), ("Botão 2", ("Z",), "botão 2"), _START),
    "segaCD": (_DIRECIONAL, ("A", ("S",), "A"), ("B", ("X",), "B"), ("C", ("Z",), "C"), _START),
    "snes": (_DIRECIONAL, ("A", ("Z",), "A"), ("B", ("X",), "B"), ("X", ("A",), "X"), ("Y", ("S",), "Y"), ("L / R", ("Q", "E"), "L e R"), _START, _SELECT),
    "segaMD": (_DIRECIONAL, ("A", ("S",), "A"), ("B", ("X",), "B"), ("C", ("Z",), "C"), _START),
    "arcade": (_DIRECIONAL, ("Botões 1 a 4", ("X", "Z", "S", "A"), "os botões 1 a 4, à direita (5 e 6 ao lado)"), ("Ficha (moeda)", ("V",), "COIN"), ("Começar", ("Enter",), "START")),
}

#: O MAME 2003 Plus é fliperama também: os mesmos comandos.
CONTROLES["mame"] = CONTROLES["arcade"]

#: Vale para todo console: o que não muda de um para o outro.
DICAS_DE_CONTROLE = {
    "pc": "Um controle de videogame USB ou Bluetooth funciona na hora: é só ligar e apertar um botão. "
          "Salvar e carregar o jogo, o som e o filtro da imagem ficam em “Salvar e ajustes”, no alto.",
    "celular": "O controle aparece por cima do jogo, e você pode mudar o lugar e o tamanho de cada botão "
               "(Ajustar controle). Deite o celular e use a Tela cheia; um controle Bluetooth pareado também funciona.",
    "controle": "Ligue o controle de Xbox no computador ou no celular (cabo ou Bluetooth) e aperte qualquer botão: "
                "ele já vale. O de PlayStation e os genéricos funcionam igual, pela posição dos botões.",
}


#: O QUE CADA BOTÃO FAZ, em geral, em cada console (a convenção dos jogos dele). O
#: jogo pode dizer o dele no painel (JogoCadastrado.acoes: "B: Pular"): manda esse.
_FUNCAO_GERAL = {
    "Mover": "Andar e escolher no menu", "Analógico": "Andar e mirar", "Direcional (cruz)": "Menus e atalhos",
    "Start": "Pausar ou começar", "Select": "Opções e trocar", "L / R": "Botões de ombro: trocar, câmera, defender",
    "L1 / R1": "Ombros: trocar, defender, câmera", "L2 / R2": "Gatilhos: acelerar, mirar, especial",
    "Botões C": "Câmera e ações extras", "Z (gatilho)": "Gatilho: mirar e agachar",
    "Tela de baixo": "Tocar na tela de baixo do DS", "Joystick": "Andar e mirar", "Disparo": "Atirar e pular",
    "Teclado do PC antigo": "Digitar e os atalhos do jogo", "Mouse": "Apontar e clicar",
    "Teclado do C64": "Digitar (LOAD, RUN) e os atalhos do jogo", "Ficha (moeda)": "Pôr ficha (créditos)",
    "Começar": "Começar a partida", "Option": "Opções e começar", "Pause": "Pausar", "Reset": "Recomeçar",
    "Reset (começar)": "Começar a partida", "Run": "Pausar ou começar",
}
_FUNCAO_POR_CONSOLE = {
    "nes": {"A": "Pular e confirmar", "B": "Correr, atirar e voltar"},
    "snes": {"B": "Pular e confirmar (na maioria)", "Y": "Correr, pegar e atirar", "A": "Ação extra (pulo especial)", "X": "Menu e ação extra"},
    "gb": {"A": "Pular e confirmar", "B": "Correr, atirar e voltar"},
    "gba": {"A": "Pular e confirmar", "B": "Correr, atacar e voltar"},
    "n64": {"A": "Pular e confirmar", "B": "Atacar e voltar"},
    "psx": {"✕": "Confirmar e ação principal", "○": "Voltar e ação 2", "□": "Ação 3 (atacar, usar)", "△": "Menu e ação 4"},
    "psp": {"✕": "Confirmar e ação principal", "○": "Voltar e ação 2", "□": "Ação 3 (atacar, usar)", "△": "Menu e ação 4"},
    "segaMD": {"A": "Ação 1", "B": "Ação principal (pular)", "C": "Ação 3 (pular em muitos jogos)"},
    "segaCD": {"A": "Ação 1", "B": "Ação principal", "C": "Ação 3"},
    "sega32x": {"A": "Ação 1", "B": "Ação principal", "C": "Ação 3"},
    "segaMS": {"Botão 1 (e Start)": "Ação 1 e começar", "Botão 2": "Ação 2 (pular, atirar)"},
    "segaGG": {"Botão 1": "Ação 1", "Botão 2": "Ação 2 (pular, atirar)"},
    "nds": {"A": "Confirmar e ação principal", "B": "Voltar e pular"},
    "arcade": {"Botões 1 a 4": "Golpes, tiros e pulos (cada jogo é um)"},
    "mame": {"Botões 1 a 4": "Golpes, tiros e pulos (cada jogo é um)"},
}
#: Como a equipe escreve o botão no painel (e o nome dele aqui).
_APELIDOS_DE_BOTAO = {"X": "✕", "XIS": "✕", "O": "○", "BOLA": "○", "CIRCULO": "○", "QUADRADO": "□", "TRIANGULO": "△",
                      "START": "Start", "SELECT": "Select", "DIRECIONAL": "Mover", "SETAS": "Mover", "CRUZ": "Mover",
                      "ANALOGICO": "Analógico", "L": "L / R", "R": "L / R", "L1": "L1 / R1", "R1": "L1 / R1", "L2": "L2 / R2", "R2": "L2 / R2"}


def _chave_do_botao(texto):
    sem = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return sem.strip().upper()


def ler_acoes(texto, codigo):
    """O "o que cada botão faz" do painel ("B: Pular" por linha) -> {nome do botão aqui: ação}."""
    nomes = {_chave_do_botao(a): a for a, _, _ in CONTROLES.get(codigo, ())}
    acoes = {}
    for linha in (texto or "").splitlines():
        if ":" not in linha and "=" not in linha:
            continue
        botao, acao = re.split(r"[:=]", linha, maxsplit=1)
        chave = _chave_do_botao(botao)
        nome = nomes.get(chave)
        if nome is None:
            apelido = _APELIDOS_DE_BOTAO.get(chave)
            nome = apelido if apelido in nomes.values() else None
        if nome is None:  # "L" num console com "L / R": vale o par
            nome = next((n for k, n in nomes.items() if chave and chave in [p.strip() for p in k.split("/")]), None)
        if nome and acao.strip():
            acoes[nome] = acao.strip()[:60]
    return acoes


#: O ÍCONE DE CADA AÇÃO: o mesmo em todo jogo (o "Pular" do Mario e o do Sonic são o
#: mesmo bonequinho), para quem joga pegar a prática de um jogo para o outro. Vale a
#: primeira palavra que aparece no que o botão faz ("Pular e confirmar" -> pular).
#: Os desenhos ficam em templates/partials/icones_das_acoes.html.
ICONES_DAS_ACOES = (
    ("pular", ("pul", "salt")),
    ("atacar", ("atac", "golpe", "soco", "socar", "chut", "bater", "lut", "espad", "cort")),
    ("atirar", ("atir", "tiro", "dispar", "mira", "mirar")),
    ("correr", ("corr", "aceler", "turbo", "veloc", "nitro")),
    ("defender", ("defen", "bloq", "escud", "proteg")),
    ("especial", ("especial", "poder", "magia", "super")),
    ("pegar", ("peg", "usar", "agarr", "interag", "abrir", "segur")),
    ("confirmar", ("confirm", "aceit")),
    ("voltar", ("volt", "cancel")),
    ("pausar", ("paus", "comec", "inici", "menu")),
    ("trocar", ("troc", "mud", "altern")),
    ("opcoes", ("opc", "ajust")),
    ("camera", ("camer", "olh")),
    ("ficha", ("ficha", "moed", "credit")),
    ("frear", ("frei", "frea")),
    ("mover", ("andar", "mover", "anda ", "direc")),
    ("digitar", ("digit", "tecl")),
)


#: Os comandos de andar: o ícone é sempre o de mover.
_COMANDOS_DE_MOVER = {"Mover", "Analógico", "Direcional (cruz)", "Joystick", "Cruz X", "Cruz Y",
                      "Direcional esquerdo", "Direcional direito"}


def icone_da_funcao(texto):
    """O ícone do que o botão faz ("Pular e confirmar" -> "pular"); "" quando nenhum serve."""
    sem = "".join(c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn").lower()
    melhor, onde = "", len(sem) + 1
    for icone, palavras in ICONES_DAS_ACOES:
        for palavra in palavras:
            achou = sem.find(palavra)
            if achou != -1 and achou < onde:
                melhor, onde = icone, achou
    return melhor


def controles_do_sistema(codigo, acoes=None):
    """[{acao, funcao, teclas, celular, controle}]: o botão, o que ele faz e onde fica no
    teclado, na tela do celular e no controle de Xbox (ou qualquer controle USB/Bluetooth).

    `acoes`: o que cada botão faz NESTE jogo (ler_acoes); sem ela, o que costuma fazer no console.
    """
    acoes = acoes or {}
    gerais = _FUNCAO_POR_CONSOLE.get(codigo, {})
    return [
        {"acao": a, "funcao": funcao, "do_jogo": a in acoes,
         "icone": "mover" if a in _COMANDOS_DE_MOVER and a not in acoes else icone_da_funcao(funcao),
         "teclas": list(t), "celular": c, "controle": botoes_no_xbox(t, codigo)}
        for a, t, c in CONTROLES.get(codigo, ())
        for funcao in [acoes.get(a) or gerais.get(a) or _FUNCAO_GERAL.get(a, "")]
    ]


# ---------------------------------------------------------------- de onde vem o núcleo e a qualidade da imagem

#: A versão do EmulatorJS que mora em core/static/vendor/emulatorjs/ (a dos núcleos também).
EMULATORJS_VERSAO = "4.2.3"
#: O núcleo que NÃO mora no site (os de licença não comercial ou não confirmada) vem do
#: pacote oficial do EmulatorJS no npm, pelo jsDelivr -- o espelho público do npm, com CORS
#: e cache no mundo todo. Se ele falhar, o próprio emulador ainda tenta o CDN dele.
NUCLEO_NO_NPM = "https://cdn.jsdelivr.net/npm/@emulatorjs/core-{nucleo}@" + EMULATORJS_VERSAO + "/"

#: O filtro de imagem de cada console. O RetroArch do emulador estica a imagem "no grosso"
#: (vizinho mais próximo): numa tela que não é múltiplo exato do jogo, cada pixel sai de um
#: tamanho -- serrilhado, e parecendo que faltam pixels. Por isso nada vai sem filtro:
#:   sabr      (2D no computador)  contornos arredondados e nítidos, na tela toda;
#:   ls-nitido (2D no celular, Nítido e Leve)  os pixels do console, todos do mesmo tamanho,
#:             só a emenda suavizada -- uma leitura por pixel, leve para qualquer aparelho;
#:   ls-suave  (3D e computadores)  o bicúbico no dobro do jogo e depois o ls-nitido até a tela.
#: Os dois "ls-" são do site (definidos em jogo-emulador.js).
FILTRO_2D = "sabr"
FILTRO_3D = "ls-suave"
FILTRO_2D_CELULAR = "ls-nitido"
CONSOLES_3D = {"psx", "n64", "psp", "segaSaturn", "nds", "3do", "pcfx", "jaguar",
               "dos", "amiga", "c64", "c128", "vic20", "plus4", "pet"}
#: Mais resolução por dentro (no computador; o celular fica no padrão, que pesa menos).
RESOLUCAO_NO_COMPUTADOR = {
    "n64": {"mupen64plus-43screensize": "960x720"},
    "psp": {"ppsspp_internal_resolution": "960x544"},
}


def opcoes_no_computador(codigo):
    """O que muda no computador (placa de vídeo folgada): mais resolução por dentro e o SABR na arte 2D."""
    opcoes = dict(RESOLUCAO_NO_COMPUTADOR.get(codigo, {}))
    if codigo not in CONSOLES_3D:
        opcoes["shader"] = FILTRO_2D
    return opcoes


def origem_do_nucleo(codigo):
    """O endereço (pasta) do núcleo quando ele não mora no site; "" quando mora."""
    sistema = SISTEMAS.get(codigo)
    if sistema is None or sistema.uso_comercial:
        return ""
    return NUCLEO_NO_NPM.format(nucleo=sistema.nucleo)


def opcoes_do_emulador(codigo):
    """Os ajustes iniciais do emulador para o console (EJS_defaultOptions)."""
    sistema = SISTEMAS.get(codigo)
    # o filtro do celular; no computador, opcoes_no_computador troca pelo mais caprichado
    opcoes = {"shader": FILTRO_3D if codigo in CONSOLES_3D else FILTRO_2D_CELULAR}
    if codigo == "psx":
        opcoes["pcsx_rearmed_dithering"] = "disabled"  # o pontilhado do PS1 some: a imagem fica limpa
    # o núcleo certo (no Master System o emulador escolheria outro por conta própria); o
    # N64 fica de fora: no Safari do iPhone o emulador troca de núcleo de propósito
    if sistema is not None and codigo != "n64":
        opcoes["retroarch_core"] = sistema.nucleo
    return opcoes


#: Os consoles em que o analógico vai para as setas (e a cruz para T/F/G/H).
ANALOGICO_NAS_SETAS = ("n64", "psp")

# ---------------------------------------------------------------- o controle de Xbox (e qualquer controle USB/Bluetooth)
#
# O RetroArch fala "RetroPad": um controle de Super Nintendo com analógicos. Cada botão
# do console é um número dele (0 = B, 8 = A...). O EmulatorJS liga o teclado e o controle
# a esses números. No padrão dele, o controle vai PELO NOME (o A do Xbox no A do Super
# Nintendo): no PlayStation, o ✕ caía no B do Xbox, à direita. Aqui vai PELA POSIÇÃO,
# como o RetroArch faz: o botão de baixo do Xbox (A) é o botão de baixo do console (o B
# do Super Nintendo, o ✕ do PlayStation), o da esquerda (X) é o da esquerda, e assim vai.
# Xbox, PlayStation, 8BitDo e afins seguem o "controle padrão" do navegador: valem todos.

#: A tecla do computador -> o botão do RetroPad (o teclado padrão do EmulatorJS).
_TECLA_DO_RETROPAD = {"X": 0, "S": 1, "V": 2, "Enter": 3, "↑": 4, "↓": 5, "←": 6, "→": 7, "Z": 8, "A": 9,
                      "Q": 10, "E": 11, "Tab": 12, "R": 13}
#: N64 e PSP: as setas são o analógico e a cruz vai para T/F/G/H; I/J/K/L, o analógico da direita.
_TECLA_DO_RETROPAD_ANALOGICO = dict(_TECLA_DO_RETROPAD, **{"↑": 19, "↓": 18, "←": 17, "→": 16, "T": 4, "G": 5, "F": 6,
                                                           "H": 7, "I": 23, "K": 22, "J": 21, "L": 20})
#: O botão do RetroPad -> o nome no controle de Xbox.
_RETROPAD_NO_XBOX = {0: "A", 1: "X", 2: "Exibir", 3: "Menu", 4: "Direcional", 5: "Direcional", 6: "Direcional",
                     7: "Direcional", 8: "B", 9: "Y", 10: "LB", 11: "RB", 12: "LT", 13: "RT", 16: "Analógico esquerdo",
                     17: "Analógico esquerdo", 18: "Analógico esquerdo", 19: "Analógico esquerdo",
                     20: "Analógico direito", 21: "Analógico direito", 22: "Analógico direito", 23: "Analógico direito"}
#: O botão do RetroPad -> o botão do "controle padrão" do navegador (como o EmulatorJS escreve).
_RETROPAD_NO_CONTROLE = {0: "BUTTON_1", 1: "BUTTON_3", 2: "SELECT", 3: "START", 4: "DPAD_UP", 5: "DPAD_DOWN",
                         6: "DPAD_LEFT", 7: "DPAD_RIGHT", 8: "BUTTON_2", 9: "BUTTON_4", 10: "LEFT_TOP_SHOULDER",
                         11: "RIGHT_TOP_SHOULDER", 12: "LEFT_BOTTOM_SHOULDER", 13: "RIGHT_BOTTOM_SHOULDER",
                         16: "LEFT_STICK_X:+1", 17: "LEFT_STICK_X:-1", 18: "LEFT_STICK_Y:+1", 19: "LEFT_STICK_Y:-1",
                         20: "RIGHT_STICK_X:+1", 21: "RIGHT_STICK_X:-1", 22: "RIGHT_STICK_Y:+1", 23: "RIGHT_STICK_Y:-1"}


def botoes_no_xbox(teclas, codigo):
    """As teclas de um comando -> os botões do controle de Xbox (["A"], ["LB", "RB"], ["Direcional"])."""
    mapa = _TECLA_DO_RETROPAD_ANALOGICO if codigo in ANALOGICO_NAS_SETAS else _TECLA_DO_RETROPAD
    nomes = []
    for tecla in teclas:
        nome = _RETROPAD_NO_XBOX.get(mapa.get(tecla))
        if nome and nome not in nomes:
            nomes.append(nome)
    return nomes


def controles_do_emulador(codigo):
    """O teclado e o controle que o site entrega ao emulador (EJS_defaultControls).

    O teclado é o padrão do EmulatorJS (o que a página ensina, CONTROLES), com uma troca
    no N64 e no PSP: lá as setas são o ANALÓGICO e a cruz fica em T/F/G/H -- quase todo
    jogo deles anda pelo analógico. O controle (Xbox, PlayStation, USB, Bluetooth) vai
    pela posição dos botões (ver _RETROPAD_NO_CONTROLE).
    """
    teclado = {
        0: "x", 1: "s", 2: "v", 3: "enter", 4: "up arrow", 5: "down arrow", 6: "left arrow", 7: "right arrow",
        8: "z", 9: "a", 10: "q", 11: "e", 12: "tab", 13: "r",
        16: "h", 17: "f", 18: "g", 19: "t", 20: "l", 21: "j", 22: "k", 23: "i", 24: "1", 25: "2", 26: "3",
    }
    if codigo in ANALOGICO_NAS_SETAS:
        teclado.update({4: "t", 5: "g", 6: "f", 7: "h",
                        16: "right arrow", 17: "left arrow", 18: "down arrow", 19: "up arrow"})
    jogador = {str(i): ({"value": v, "value2": _RETROPAD_NO_CONTROLE[i]} if i in _RETROPAD_NO_CONTROLE else {"value": v})
               for i, v in teclado.items()}
    jogador.update({"14": {"value": "", "value2": "LEFT_STICK"}, "15": {"value": "", "value2": "RIGHT_STICK"},
                    "27": {}, "28": {}, "29": {}})
    return {"0": jogador, "1": {}, "2": {}, "3": {}}


# ---------------------------------------------------------------- o controle na tela do celular
#
# O EmulatorJS desenha um controle por cima do jogo (EJS_VirtualGamepadSettings). O dele
# vem com "Fast", "Slow" e "Rewind" no meio da tela, o PlayStation com Y/X/B/A de Xbox e
# o disparo do Atari sem nome. Aqui cada console tem o dele: o direcional à esquerda, os
# botões com os nomes do console à direita, os de ombro em cima e START/SELECT embaixo,
# no meio -- e só isso. O desenho (vidro escuro, cores do PlayStation) é do CSS do site.
# "acao" liga o botão ao comando de CONTROLES (o que ele faz no jogo vira legenda).
#
# Posições em px dentro das caixas do EmulatorJS: a da direita tem 150 x 150 (o CSS do
# site), botão de 56. (O EmulatorJS ignora o 0: o menor é 1.)
_DIAMANTE = ((47, 1), (1, 47), (93, 47), (47, 93))   # cima, esquerda, direita, baixo
_DOIS = ((6, 74), (88, 30))                          # embaixo à esquerda, em cima à direita
_SEIS = ((-40, 12), (28, 1), (96, 12), (-40, 82), (28, 71), (96, 82))  # duas fileiras de três
_TRES = ((-36, 80), (30, 58), (96, 36))


def _bt(texto, id_, valor, onde, acao="", x=None, y=None, direita=None):
    b = {"type": "button", "text": texto, "id": id_, "location": onde, "input_value": valor, "bold": True}
    if x is not None:
        b["left"] = x
    if direita is not None:
        b["right"] = direita
    if y is not None:
        b["top"] = y
    if acao:
        b["acao"] = acao
    return b


def _face(botoes, posicoes):
    """[(texto, id, valor, acao)] nas posições dadas, na caixa da direita."""
    return [_bt(t, i, v, "right", a, x, y) for (t, i, v, a), (x, y) in zip(botoes, posicoes)]


_CRUZ = {"type": "dpad", "id": "dpad", "location": "left", "left": "50%", "top": "50%",
         "joystickInput": False, "inputValues": [4, 5, 6, 7], "acao": "Mover"}
_ANALOGICO = {"type": "zone", "id": "stick", "location": "left", "left": "50%", "top": "50%",
              "joystickInput": True, "inputValues": [16, 17, 18, 19], "color": "#ffffff", "acao": "Analógico"}


def _ombros(par="L / R", l=("L", 10), r=("R", 11), y=-54):
    return [_bt(l[0], "l", l[1], "left", par, x=2, y=y), _bt(r[0], "r", r[1], "right", par, direita=2, y=y)]


def _meio(*botoes):
    """START, SELECT e afins, embaixo no meio (a caixa do meio tem 200 de largura no CSS do site)."""
    largura, espaco = 62, 6
    total = len(botoes) * largura + (len(botoes) - 1) * espaco
    inicio = (200 - total) // 2
    return [_bt(t, i, v, "center", a, x=max(1, inicio + n * (largura + espaco)), y=1)
            for n, (t, i, v, a) in enumerate(botoes)]


_START_SELECT = (("SELECT", "select", 2, "Select"), ("START", "start", 3, "Start"))
_PS = (("△", "triangulo", 9, "△"), ("□", "quadrado", 1, "□"), ("○", "bola", 8, "○"), ("✕", "xis", 0, "✕"))
_SNES = (("X", "x", 9, "X"), ("Y", "y", 1, "Y"), ("A", "a", 8, "A"), ("B", "b", 0, "B"))
_SEGA = (("X", "x", 10, ""), ("Y", "y", 9, ""), ("Z", "z", 11, ""), ("A", "a", 1, "A"), ("B", "b", 0, "B"), ("C", "c", 8, "C"))
_FLIPERAMA = (("3", "b3", 1, "Botões 1 a 4"), ("4", "b4", 9, "Botões 1 a 4"), ("5", "b5", 10, ""),
              ("1", "b1", 0, "Botões 1 a 4"), ("2", "b2", 8, "Botões 1 a 4"), ("6", "b6", 11, ""))

GAMEPAD_NA_TELA = {
    "nes": [_CRUZ, *_face((("B", "b", 0, "B"), ("A", "a", 8, "A")), _DOIS), *_meio(*_START_SELECT)],
    "gb": [_CRUZ, *_face((("B", "b", 0, "B"), ("A", "a", 8, "A")), _DOIS), *_meio(*_START_SELECT)],
    "gba": [_CRUZ, *_face((("B", "b", 0, "B"), ("A", "a", 8, "A")), _DOIS), *_ombros(), *_meio(*_START_SELECT)],
    "snes": [_CRUZ, *_face(_SNES, _DIAMANTE), *_ombros(), *_meio(*_START_SELECT)],
    "nds": [_CRUZ, *_face(_SNES, _DIAMANTE), *_ombros(), *_meio(*_START_SELECT)],
    "psx": [_CRUZ, *_face(_PS, _DIAMANTE), *_ombros("L1 / R1", ("L1", 10), ("R1", 11)),
            _bt("L2", "l2", 12, "left", "L2 / R2", x=2, y=-100), _bt("R2", "r2", 13, "right", "L2 / R2", direita=2, y=-100),
            *_meio(*_START_SELECT)],
    "psp": [_ANALOGICO, *_face(_PS, _DIAMANTE), *_ombros(), *_meio(*_START_SELECT)],
    "segaMD": [_CRUZ, *_face(_SEGA, _SEIS), *_meio(("MODE", "mode", 2, ""), ("START", "start", 3, "Start"))],
    "segaCD": [_CRUZ, *_face(_SEGA, _SEIS), *_meio(("MODE", "mode", 2, ""), ("START", "start", 3, "Start"))],
    "sega32x": [_CRUZ, *_face(_SEGA, _SEIS), *_meio(("MODE", "mode", 2, "Mode"), ("START", "start", 3, "Start"))],
    "segaSaturn": [_CRUZ, *_face((("X", "x", 9, "X"), ("Y", "y", 10, "Y"), ("Z", "z", 11, "Z"), ("A", "a", 1, "A"),
                                  ("B", "b", 0, "B"), ("C", "c", 8, "C")), _SEIS),
                   *_ombros(l=("L", 12), r=("R", 13)), *_meio(("START", "start", 3, "Start"))],
    "segaMS": [_CRUZ, *_face((("1", "b1", 0, "Botão 1 (e Start)"), ("2", "b2", 8, "Botão 2")), _DOIS)],
    "segaGG": [_CRUZ, *_face((("1", "b1", 0, "Botão 1"), ("2", "b2", 8, "Botão 2")), _DOIS), *_meio(("START", "start", 3, "Start"))],
    "arcade": [_CRUZ, *_face(_FLIPERAMA, _SEIS), *_meio(("FICHA", "ficha", 2, "Ficha (moeda)"), ("INICIAR", "start", 3, "Começar"))],
    "mame": [_CRUZ, *_face(_FLIPERAMA, _SEIS), *_meio(("FICHA", "ficha", 2, "Ficha (moeda)"), ("INICIAR", "start", 3, "Começar"))],
    "atari2600": [_CRUZ, _bt("FOGO", "fogo", 0, "right", "Disparo", x=44, y=44),
                  *_meio(("SELECT", "select", 2, "Select"), ("RESET", "reset", 3, "Reset (começar)"))],
    "atari5200": [_CRUZ, _bt("FOGO", "fogo", 0, "right", "Disparo", x=44, y=44), *_meio(("START", "start", 3, "Start"))],
    "atari7800": [_CRUZ, *_face((("1", "b1", 0, "Botão 1"), ("2", "b2", 8, "Botão 2")), _DOIS),
                  *_meio(("SELECT", "select", 2, "Select"), ("PAUSE", "pause", 3, "Pause"), ("RESET", "reset", 9, "Reset"))],
    "lynx": [_CRUZ, *_face((("B", "b", 0, "B"), ("A", "a", 8, "A")), _DOIS),
             *_meio(("OPT 1", "opt1", 10, "Option 1 / 2"), ("PAUSE", "pause", 3, "Pause"), ("OPT 2", "opt2", 11, "Option 1 / 2"))],
    "pce": [_CRUZ, *_face((("II", "ii", 0, "II"), ("I", "i", 8, "I")), _DOIS), *_meio(("SELECT", "select", 2, "Select"), ("RUN", "run", 3, "Run"))],
    "ngp": [_CRUZ, *_face((("A", "a", 0, "A"), ("B", "b", 8, "B")), _DOIS), *_meio(("OPTION", "option", 3, "Option"))],
    "jaguar": [_CRUZ, *_face((("A", "a", 8, "A"), ("B", "b", 0, "B"), ("C", "c", 1, "C")), _TRES),
               *_meio(("PAUSE", "pause", 2, "Pause"), ("OPTION", "option", 3, "Option"))],
    "3do": [_CRUZ, *_face((("A", "a", 1, "A"), ("B", "b", 0, "B"), ("C", "c", 8, "C")), _TRES), *_ombros(),
            *_meio(("X", "parar", 2, "Stop (X)"), ("P", "play", 3, "Play (P)"))],
}


def gamepad_na_tela(codigo, acoes=None):
    """(o controle da tela, {id do botão: {"icone", "texto"}}); (None, {}) = o do emulador.

    Cada botão leva o ícone do que ele faz (o do jogo, se a equipe disse; senão o costume
    do console) e, quando a equipe disse, o texto curto embaixo da letra.
    """
    desenho = GAMEPAD_NA_TELA.get(codigo)
    if not desenho:
        return None, {}
    funcoes = {c["acao"]: c for c in controles_do_sistema(codigo, acoes)}
    rotulos = {}
    for b in desenho:
        comando = funcoes.get(b.get("acao"))
        if b["type"] != "button" or not comando:
            continue
        rotulo = {"icone": comando["icone"], "texto": comando["funcao"] if comando["do_jogo"] else ""}
        if rotulo["icone"] or rotulo["texto"]:
            rotulos[b["id"]] = rotulo
    return [dict(b) for b in desenho], rotulos
