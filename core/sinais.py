"""AVISOS ENTRE OS PROCESSOS DO SITE (LEIA-ME-V10, seção 131).

O QUE ACONTECEU. Na publicação da seção 130 a restauração das fotos rodou
sozinha no servidor: as 79 fotos com cópia certa no repositório foram para
o banco e os cadastros passaram a apontar para elas. A página do produto, a
página 2 do catálogo e as buscas saíram certas. Mas a home e a primeira
página do catálogo continuaram com os endereços antigos do Cloudinary (o
ícone de foto quebrada que a reserva da seção 128 tapa): elas estavam no
cache, e o cache (`LocMemCache`) mora na memória de CADA processo. A
restauração limpou o cache do processo em que rodou; o processo que
atendia as visitas guardou a tela de antes até o fim do prazo.

O SINAL. Quem troca o que as telas mostram sem passar pelos signals (a
restauração, a importação do ZIP, o espelho, um comando no terminal) chama
`avisar()`: uma linha em `SinalDoSite` ganha uma versão nova (o relógio em
nanossegundos), gravada só depois do commit. Cada processo do site tem uma
linha de fundo (`garantir_vigia`, ligada pela primeira visita, dentro do
próprio processo -- também com `--preload` e com mais de um worker) que lê
as versões a cada `SINAIS_INTERVALO_S` segundos (60 no Render; desligado no
computador e nos testes) e, se uma mudou, faz a limpeza daquela chave neste
processo. Uma consulta por minuto por processo, fora do caminho da visita.

A primeira leitura de um processo conta como mudança só a versão gravada
DEPOIS que ele subiu: o processo novo já começa com o cache vazio. E quem
avisou também limpa de novo quando a linha de fundo vê a versão: a tela que
alguém montou no meio da troca não sobrevive.
"""

from __future__ import annotations

import logging
import os
import threading
import time

from django.conf import settings

log = logging.getLogger("lazer.sinais")

#: As fotos e os arquivos do site mudaram (seção 130): as telas guardadas recomeçam.
MIDIA = "midia"
#: O Cloudinary (o legado) está fora do ar: versão > 0 é o instante em que o
#: espelho viu a conta desativada; 0, que voltou (seção 132). Com ele fora, o
#: site não pede foto nenhuma a ele (core.arquivos_no_banco.legado_fora_do_ar).
CLOUDINARY = "cloudinary-fora"

_trava = threading.Lock()
_estado = {
    "pid": None,  # o processo que tem a linha de fundo (depois de um fork, a do pai não vale)
    "thread": None,
    "visto": {},  # chave -> última versão lida por este processo
    "inicio": time.time_ns(),
    "ultima": None,
}


def intervalo() -> int:
    try:
        return max(0, int(getattr(settings, "SINAIS_INTERVALO_S", 0) or 0))
    except (TypeError, ValueError):
        return 0


def _limpar_midia():
    from . import espelho_midia

    espelho_midia.limpar_caches_locais()


#: O que cada chave limpa NESTE processo.
LIMPEZAS = {MIDIA: _limpar_midia, CLOUDINARY: _limpar_midia}


def _gravar(chave, versao=None):
    from django.db import DatabaseError, IntegrityError, transaction

    from .models import SinalDoSite

    versao = time.time_ns() if versao is None else int(versao)
    try:
        if not SinalDoSite.objects.filter(chave=chave).update(versao=versao):
            try:
                with transaction.atomic():
                    SinalDoSite.objects.create(chave=chave, versao=versao)
            except IntegrityError:  # outro processo criou no mesmo instante
                SinalDoSite.objects.filter(chave=chave).update(versao=versao)
    except DatabaseError:
        # o aviso nunca derruba quem avisou: os outros processos ficam com o prazo do cache
        log.warning("sinais: não deu para gravar %s", chave, exc_info=True)
        return None
    return versao


def avisar(chave=MIDIA):
    """Os outros processos devem recomeçar o que guardam para `chave` (gravado depois do commit)."""
    from django.db import transaction

    transaction.on_commit(lambda: _gravar(chave))


def marcar(chave, ligado):
    """Um estado (não um evento): grava só quando muda. True se mudou.

    Ligado guarda o instante; desligado, 0. Os processos que leem a versão
    nova limpam o cache (as telas trocam de foto) e passam a responder
    `valor(chave)` com o estado novo.
    """
    from .models import SinalDoSite

    atual = SinalDoSite.objects.filter(chave=chave).values_list("versao", flat=True).first()
    if bool(atual) == bool(ligado):
        return False
    versao = time.time_ns() if ligado else 0
    if _gravar(chave, versao) is None:
        return False
    with _trava:
        _estado["visto"][chave] = versao
    return True


def valor(chave):
    """A última versão que este processo leu de `chave` (0 se nunca leu)."""
    return _estado["visto"].get(chave) or 0


def conferir():
    """Uma leitura: as chaves cuja versão mudou desde a última vez, já limpas neste processo."""
    from .models import SinalDoSite

    versoes = dict(SinalDoSite.objects.values_list("chave", "versao"))
    mudaram = []
    with _trava:
        vistos = _estado["visto"]
        for chave, versao in versoes.items():
            anterior = vistos.get(chave)
            if anterior is None:
                mudou = versao > _estado["inicio"]
            else:
                mudou = versao != anterior
            vistos[chave] = versao
            if mudou:
                mudaram.append(chave)
        _estado["ultima"] = time.time()
    for chave in mudaram:
        limpeza = LIMPEZAS.get(chave)
        if limpeza is None:
            continue
        try:
            limpeza()
            log.info("sinais: %s mudou, o cache deste processo recomeçou", chave)
        except Exception:  # noqa: BLE001 -- uma limpeza com problema não para as outras
            log.warning("sinais: a limpeza de %s falhou", chave, exc_info=True)
    return mudaram


def _laco(espera):
    from django.db import close_old_connections, connection

    primeira = True
    while True:
        # a primeira leitura sai logo: o estado do Cloudinary vale desde a primeira tela
        if not primeira:
            time.sleep(espera)
        primeira = False
        try:
            close_old_connections()
            conferir()
        except Exception:  # noqa: BLE001 -- a linha de fundo nunca derruba o site
            log.warning("sinais: a conferência falhou", exc_info=True)
        finally:
            # uma consulta por minuto não segura conexão parada no pooler
            connection.close()


def garantir_vigia() -> bool:
    """Liga a linha de fundo deste processo (uma por processo). True se ligou agora."""
    espera = intervalo()
    if not espera:
        return False
    pid = os.getpid()
    if _estado["pid"] == pid and _estado["thread"] is not None and _estado["thread"].is_alive():
        return False
    with _trava:
        if _estado["pid"] == pid and _estado["thread"] is not None and _estado["thread"].is_alive():
            return False
        if _estado["pid"] != pid:
            # processo novo (fork): o que o pai leu não vale para o cache daqui
            _estado["visto"] = {}
            _estado["inicio"] = time.time_ns()
        thread = threading.Thread(target=_laco, args=(espera,), name="sinais-do-site", daemon=True)
        _estado["pid"], _estado["thread"] = pid, thread
        thread.start()
    return True


class SinaisMiddleware:
    """Liga a linha de fundo na primeira visita de cada processo (custa uma comparação depois)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if _estado["pid"] != os.getpid() or _estado["thread"] is None:
            try:
                garantir_vigia()
            except Exception:  # noqa: BLE001
                log.warning("sinais: não deu para ligar a linha de fundo", exc_info=True)
        return self.get_response(request)
