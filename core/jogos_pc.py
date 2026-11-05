"""A versão para computador (Windows) dos jogos: conferir o arquivo e reconhecer o motor.

O navegador não roda .exe. A versão para computador entra no cadastro do
jogo como FONTE: é dela que se tiram as artes, os sons e a lógica para a
versão que roda no site (o "porte", como os jogos do simulador). Por isso
ela é guardada e NUNCA servida ao público.

O que se aceita:
* um .exe de verdade (começa com "MZ", o cabeçalho de todo executável do
  Windows) -- serve para jogo de arquivo único, como o Godot com o .pck
  embutido;
* um .zip com a pasta do jogo (o .exe e o que vai ao lado: o .pck do
  Godot, a pasta _Data do Unity, as DLLs...) -- é o jeito certo para quase
  todo jogo, que não é um arquivo só.

O motor (Godot, Unity, Unreal, GameMaker, RPG Maker, Electron/NW.js) é
reconhecido pelos nomes dos arquivos dentro do .zip, ou por marcas
conhecidas dentro do .exe. Sabendo o motor, o painel diz o caminho mais
curto até o site: Godot e Unity exportam para Web direto do editor.
"""

from __future__ import annotations

import zipfile

MOTORES = {
    "godot": "Godot",
    "unity": "Unity",
    "unreal": "Unreal Engine",
    "gamemaker": "GameMaker",
    "rpgmaker": "RPG Maker",
    "electron": "Electron / NW.js",
    "dos": "DOS (MS-DOS)",
    "desconhecido": "Não reconhecido",
}

#: O que dizer, por motor, sobre levar o jogo para o navegador.
CAMINHO_PARA_O_SITE = {
    "godot": "Godot exporta para Web pelo editor (Projeto > Exportar > Web). Com o projeto em mãos, a versão do site sai direto; só com o .exe, as artes e os scripts podem ser recuperados do .pck para portar.",
    "unity": "Unity exporta para WebGL (File > Build Settings > WebGL). Com o projeto, a versão do site sai direto; só com o build, ele serve de referência para portar.",
    "unreal": "Unreal não exporta para navegador nas versões atuais: o caminho é portar o jogo para o site.",
    "gamemaker": "GameMaker exporta para HTML5 (ou GX.games) a partir do projeto; só com o build, ele serve de referência para portar.",
    "rpgmaker": "RPG Maker MV/MZ já é feito em HTML: a pasta www do jogo roda no navegador quase sem mudanças.",
    "electron": "Jogo em Electron/NW.js já é HTML por dentro: dá para tirar a versão de navegador da pasta do app.",
    "dos": "É um programa de DOS (não de Windows): esse tipo roda no navegador pelo DOSBox, um emulador. O site "
           "ainda não liga o DOSBox — ele pede uma configuração a mais no servidor (isolamento de origem, para threads).",
    "desconhecido": "O motor não foi reconhecido: o build serve de referência para portar o jogo para o site.",
}


def _motor_pelos_nomes(nomes):
    baixos = [n.replace("\\", "/").lower() for n in nomes]
    tem = lambda *trechos: any(any(t in n for t in trechos) for n in baixos)  # noqa: E731
    if tem(".pck", "godot"):
        return "godot"
    if tem("unityplayer.dll", "_data/managed/", "_data/globalgamemanagers", "_data/il2cpp_data"):
        return "unity"
    if tem(".pak", "engine/binaries/", "/binaries/win64/"):
        return "unreal"
    if tem("data.win", "options.ini") and tem(".exe"):
        return "gamemaker"
    if tem("www/js/rpg_core.js", "js/rmmz_core.js", "game.rgss", ".rgssad", ".rgss3a"):
        return "rpgmaker"
    if tem("resources/app.asar", "package.nw", "nw.dll", "resources.pak"):
        return "electron"
    return "desconhecido"


def e_programa_de_dos(cabeca):
    """Um .exe de DOS não tem o cabeçalho "PE" que todo programa do Windows tem."""
    if cabeca[:2] != b"MZ" or len(cabeca) < 0x40:
        return False
    deslocamento = int.from_bytes(cabeca[0x3C:0x40], "little")
    return not (0 < deslocamento <= len(cabeca) - 4 and cabeca[deslocamento:deslocamento + 4] == b"PE\x00\x00")


def _motor_pelo_exe(arquivo):
    """Marcas conhecidas no começo e no fim do .exe (sem ler o arquivo inteiro)."""
    arquivo.seek(0)
    inicio = arquivo.read(8 * 1024 * 1024)
    try:
        arquivo.seek(-16, 2)
        fim = arquivo.read(16)
    except (OSError, ValueError):
        fim = b""
    arquivo.seek(0)
    # o Godot com o .pck embutido termina com a marca "GDPC"
    if fim.endswith(b"GDPC") or b"GDPC" in fim or b"Godot Engine" in inicio:
        return "godot"
    if b"UnityPlayer" in inicio:
        return "unity"
    if b"UnrealEngine" in inicio or b"Unreal Engine" in inicio:
        return "unreal"
    if b"YoYo Games" in inicio or b"GameMaker" in inicio:
        return "gamemaker"
    # nenhuma marca de motor e sem o cabeçalho "PE" do Windows: é um programa de DOS
    if e_programa_de_dos(inicio[:4096]):
        return "dos"
    return "desconhecido"


class ArquivoInvalido(ValueError):
    """A versão para computador enviada não é um .exe nem um .zip de jogo."""


def conferir(arquivo):
    """Confere o arquivo enviado e devolve o motor reconhecido (código de MOTORES)."""
    nome = (arquivo.name or "").lower()
    arquivo.seek(0)
    cabeca = arquivo.read(4)
    arquivo.seek(0)
    if nome.endswith(".exe"):
        if cabeca[:2] != b"MZ":
            raise ArquivoInvalido("Esse arquivo não é um executável do Windows de verdade.")
        return _motor_pelo_exe(arquivo)
    if nome.endswith(".zip"):
        if cabeca[:2] != b"PK":
            raise ArquivoInvalido("Esse arquivo não é um .zip de verdade.")
        try:
            with zipfile.ZipFile(arquivo) as pacote:
                nomes = pacote.namelist()
                executaveis = [n for n in nomes if n.lower().endswith(".exe")]
                cabeca_do_exe = b""
                if executaveis:
                    with pacote.open(executaveis[0]) as exe:
                        cabeca_do_exe = exe.read(4096)
        except zipfile.BadZipFile as exc:
            raise ArquivoInvalido("O .zip está corrompido ou incompleto.") from exc
        finally:
            arquivo.seek(0)
        if not executaveis:
            raise ArquivoInvalido("O .zip não tem nenhum .exe dentro: zipe a pasta inteira do jogo, com o executável.")
        motor = _motor_pelos_nomes(nomes)
        if motor == "desconhecido" and e_programa_de_dos(cabeca_do_exe):
            return "dos"
        return motor
    raise ArquivoInvalido("Envie o .exe do jogo ou um .zip com a pasta do jogo.")
