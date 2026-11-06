"""GERAR O PROGRAMA DE WINDOWS (.exe) DE UM JOGO, PELO PAINEL -- sem compilar nada.

O irmão do APK (core/jogos_apk_gerar.py), para o computador: um .exe só, que se
abre com dois cliques e roda o jogo sem internet, numa janela de app (o Edge que
todo Windows 10/11 tem, ou o Chrome), sem barra de navegador.

COMO É FEITO. A casca (core/exe_casca/jogo-windows.exe, compilada de
ferramentas/exe/ em Go) já está pronta; o painel só junta:

    [ a casca ][ um .zip com o jogo ][ onde o .zip começa: 8 bytes ][ "LSJOGOV1" ]

O .zip leva o mesmo conteúdo do APK (`conteudo_do_jogo(..., para="exe")`): o
reprodutor do site, o EmulatorJS, o núcleo do console e os arquivos do jogo, e o
`lsjogo.json` (o nome e o endereço do jogo). Os arquivos grandes e os que já vêm
comprimidos vão sem compressão: a casca lê direto do .exe, em pedaços.

O QUE O .EXE FAZ (ferramentas/exe/main.go): serve o jogo só para o próprio
computador (127.0.0.1, numa porta fixa por jogo -- o jogo salvo fica guardado
entre uma vez e outra) e com o isolamento que o núcleo de várias linhas pede: o
PSP e o DOS, que ficam de fora do APK, rodam no .exe.

LIMITES. O mesmo teto do APK (o jogo é montado no servidor, na hora). O Windows
avisa ("o Windows protegeu o computador") no primeiro clique em todo programa
sem assinatura digital paga: "Mais informações" > "Executar assim mesmo".
"""

from __future__ import annotations

import json
import shutil
import struct
import tempfile
import time
import zipfile
from pathlib import Path

from .jogos_apk_gerar import JA_COMPRIMIDOS, MAX_JOGO, ApkNaoDa, conteudo_do_jogo

PASTA = Path(__file__).resolve().parent
CASCA_EXE = PASTA / "exe_casca" / "jogo-windows.exe"
MARCA = b"LSJOGOV1"
#: Acima disto o arquivo vai sem compressão (a casca lê em pedaços, sem abrir tudo na memória).
SEM_COMPRESSAO_ACIMA = 2 * 1024 * 1024


def montar_exe(destino, conteudo, nome, slug, casca=None):
    """Escreve o .exe em `destino` (arquivo binário aberto): a casca, o .zip e a marca."""
    casca = Path(casca or CASCA_EXE)
    with tempfile.TemporaryFile() as pacote:
        with zipfile.ZipFile(pacote, "w") as z:
            data = time.localtime()[:6]
            info = zipfile.ZipInfo("lsjogo.json", date_time=data)
            z.writestr(info, json.dumps({"nome": nome, "slug": slug}, ensure_ascii=False), compress_type=zipfile.ZIP_DEFLATED)
            for caminho, dados in conteudo:
                info = zipfile.ZipInfo(caminho, date_time=data)
                guardado = len(dados) > SEM_COMPRESSAO_ACIMA or caminho.lower().endswith(JA_COMPRIMIDOS)
                z.writestr(info, dados, compress_type=zipfile.ZIP_STORED if guardado else zipfile.ZIP_DEFLATED)
        with open(casca, "rb") as f:
            shutil.copyfileobj(f, destino)
        inicio = destino.tell()
        pacote.seek(0)
        shutil.copyfileobj(pacote, destino)
        destino.write(struct.pack("<Q", inicio) + MARCA)


def gerar_exe(jogo, destino, request=None):
    """Monta o .exe do jogo em `destino` e devolve o resumo (ApkNaoDa com o motivo, se não der)."""
    if not CASCA_EXE.exists():
        raise ApkNaoDa("Falta o core/exe_casca/jogo-windows.exe (rode ferramentas/exe/montar_casca.sh).")
    conteudo, _capa = conteudo_do_jogo(jogo, request, para="exe")
    total = sum(len(dados) for _caminho, dados in conteudo)
    if total > MAX_JOGO + 64 * 1024 * 1024:
        raise ApkNaoDa(f"O jogo tem {total // 1048576} MB: o painel monta até {MAX_JOGO // 1048576} MB.")
    montar_exe(destino, conteudo, jogo.nome, jogo.slug)
    return {"arquivos": len(conteudo), "versao": time.strftime("%Y.%m.%d.%H%M")}


def aviso_de_licenca(jogo):
    """O aviso da licença do núcleo, quando ela não deixa vender (o painel mostra junto do botão)."""
    from .jogos_emulador import SISTEMAS

    sistema = SISTEMAS.get(jogo.sistema or "")
    if sistema is None or sistema.uso_comercial:
        return ""
    return (f"O núcleo do {sistema.nome} tem licença {sistema.licenca}: o .exe e o APK servem para uso "
            "particular -- não vendam nem distribuam. E só jogos de que a empresa tem os direitos.")
