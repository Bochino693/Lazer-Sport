"""O APK de um jogo cadastrado: conferir que é um APK de verdade e reconhecer o que tem dentro.

O QUE O APK FAZ NO SITE. Ele é guardado e, se a equipe liberar, vira o
botão "Baixar o aplicativo" na página do jogo -- para instalar na máquina
Android. O navegador NÃO roda APK: não existe emulador de Android que rode
um jogo dentro de uma página. Por isso o APK nunca "vira" o jogo do site
sozinho.

O QUE DÁ PARA APROVEITAR. Muito jogo Android é, por dentro, uma página de
HTML5 empacotada (Cordova, Capacitor, Construct, Phaser...): a pasta
`assets/www/` ou `assets/public/` do APK é o jogo de navegador pronto. O
painel avisa quando encontra isso -- é o caminho mais curto até o site
(hospedar essa pasta e colar o endereço). Para os outros, o motor
reconhecido (Unity, Godot...) diz como exportar para a Web.

O QUE SE CONFERE. Todo APK é um ZIP com o `AndroidManifest.xml` na raiz.
Antes, bastava o arquivo começar com "PK" -- qualquer .zip renomeado para
.apk passava. Agora o ZIP é aberto (só a lista de arquivos, no fim dele) e
o manifesto tem de estar lá.
"""

from __future__ import annotations

import zipfile

MOTORES = {
    "unity": "Unity",
    "godot": "Godot",
    "unreal": "Unreal Engine",
    "gamemaker": "GameMaker",
    "cocos": "Cocos",
    "defold": "Defold",
    "flutter": "Flutter",
    "react-native": "React Native",
    "html5": "HTML5 empacotado (Cordova, Capacitor...)",
    "desconhecido": "Não reconhecido",
}

CAMINHO_PARA_O_SITE = {
    "html5": "Este APK tem o jogo em HTML5 dentro (a pasta {pasta}): hospede essa pasta e cole o endereço no "
             "cadastro — é o jogo de navegador pronto.",
    "unity": "Unity exporta para WebGL pelo editor (File > Build Settings > WebGL); o APK não vira versão de navegador.",
    "godot": "Godot exporta para Web pelo editor (Projeto > Exportar > Web); o APK não vira versão de navegador.",
    "gamemaker": "GameMaker exporta para HTML5 (ou GX.games) a partir do projeto.",
    "cocos": "Cocos Creator exporta para Web Mobile a partir do projeto.",
    "defold": "Defold exporta para HTML5 a partir do projeto (Project > Bundle > HTML5).",
    "flutter": "Flutter compila para Web a partir do projeto (flutter build web).",
    "unreal": "Unreal não exporta para navegador nas versões atuais.",
    "react-native": "React Native não roda no navegador sem reescrever partes do app.",
    "desconhecido": "O motor não foi reconhecido: a versão do site sai do projeto do jogo, não do APK.",
}

PASTAS_HTML5 = ("assets/www/index.html", "assets/public/index.html")


class ApkInvalido(ValueError):
    """O arquivo enviado como APK não é um APK."""


def conferir(arquivo):
    """Confere o APK enviado e devolve (motor, pasta_html5_ou_vazio)."""
    arquivo.seek(0)
    if arquivo.read(2) != b"PK":
        arquivo.seek(0)
        raise ApkInvalido("Esse arquivo não é um APK de verdade (um APK é um pacote ZIP).")
    arquivo.seek(0)
    try:
        with zipfile.ZipFile(arquivo) as pacote:
            nomes = pacote.namelist()
    except zipfile.BadZipFile as exc:
        raise ApkInvalido("O APK está corrompido ou incompleto (o pacote não abre).") from exc
    finally:
        arquivo.seek(0)
    if "AndroidManifest.xml" not in nomes:
        raise ApkInvalido("Esse pacote não é um APK: falta o AndroidManifest.xml (é um .zip com outro nome?).")
    return reconhecer(nomes)


def reconhecer(nomes):
    baixos = [n.lower() for n in nomes]

    def tem(*trechos):
        return any(any(t in n for t in trechos) for n in baixos)

    for pasta in PASTAS_HTML5:
        if pasta in baixos:
            return "html5", pasta.rsplit("/", 1)[0] + "/"
    if tem("libunity.so", "assets/bin/data/"):
        return "unity", ""
    if tem("libgodot_android.so") or any(n.startswith("assets/") and n.endswith(".pck") for n in baixos):
        return "godot", ""
    if tem("libue4.so", "libunreal.so"):
        return "unreal", ""
    if tem("libyoyo.so"):
        return "gamemaker", ""
    if tem("libcocos2djs.so", "libcocos.so", "libcocos2dcpp.so"):
        return "cocos", ""
    if tem("libdmengine.so"):
        return "defold", ""
    if tem("libflutter.so"):
        return "flutter", ""
    if tem("libreactnativejni.so", "index.android.bundle"):
        return "react-native", ""
    return "desconhecido", ""


def caminho_para_o_site(motor, pasta=""):
    return CAMINHO_PARA_O_SITE.get(motor or "desconhecido", CAMINHO_PARA_O_SITE["desconhecido"]).format(pasta=pasta or "assets/www/")
