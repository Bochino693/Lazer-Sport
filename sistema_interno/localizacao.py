"""Todo endereço de cliente ganha o seu ponto no mapa (LEIA-ME-V10, seção 121).

O PEDIDO: "verifique na área interna, nos clientes, o 'no mapa, sem
local', pois tem endereço e deve estar no mapa tudo que tiver".

A CAUSA. O cadastro do painel só ganhava coordenada de UM lugar: a
consulta rápida do CEP que o navegador faz enquanto a pessoa digita
(BrasilAPI). Ela não traz o ponto de muitos CEPs, e o endereço sem CEP
(rua e cidade bastam para salvar) nunca tinha ponto nenhum. Ficava salvo
sem latitude, e NADA tentava de novo: a busca completa
(`EnderecoCliente.localizar`, CEP + número no Nominatim, depois o centro
da cidade) só rodava no botão "Recalcular" da gestão e no importador. O
selo "no mapa, sem local" ficava para sempre.

O QUE ESTE MÓDULO FAZ. Uma fila por processo, com uma thread só:

  * gravou um endereço sem ponto (painel, importador, gestão, /system/),
    ele entra na fila DEPOIS do commit (`pedir`) -- a gravação nunca
    espera serviço de fora, e o clique de salvar continua rápido;
  * de tempos em tempos (e logo depois de o site subir) uma varredura põe
    na fila todo endereço que ainda está sem ponto (`varrer`): é o que
    acerta os cadastros antigos sem ninguém precisar abrir um por um;
  * cada endereço passa pelas fontes em ordem, da mais precisa para a
    mais larga, e PARA na primeira que responde (`localizar_um`):
      1. o ponto do CEP (BrasilAPI);
      2. CEP + número no Nominatim (exato, rua, bairro ou cidade);
      3. sem CEP: rua + número + cidade no Nominatim;
      4. o centro da cidade (Nominatim, e o Open-Meteo quando ele falha).
    A precisão fica gravada ("Centro da cidade" é diferente de "Endereço
    exato"), como sempre foi.

O QUE NÃO FAZ. Não sobrescreve ponto nenhum: grava só se o endereço AINDA
está sem coordenada no instante da gravação (um ajuste à mão feito
enquanto a busca rodava vence). Não liga o "Aparece no mapa" de ninguém:
quem decide o que vai ao site continua sendo o cadastro. E respeita o
ritmo do serviço público (uma consulta por segundo, `no_ritmo_do_nominatim`).

Endereço que nenhuma fonte acha (cidade escrita errado, por exemplo) é
tentado de novo só depois de algumas horas, para a fila não martelar o
mesmo cadastro.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from collections import deque
from decimal import Decimal

from django.conf import settings
from django.db import connections, transaction

log = logging.getLogger(__name__)

#: Endereço que nenhuma fonte achou só volta à fila depois disto.
REPETIR_FALHA_S = 6 * 3600
#: De quanto em quanto tempo a varredura procura endereço sem ponto.
VARREDURA_S = 30 * 60
#: Espera antes da primeira varredura: o processo ainda está subindo.
PRIMEIRA_VARREDURA_S = 45
#: Uma varredura põe no máximo isto na fila (o resto fica para a próxima).
LOTE_DA_VARREDURA = 400

_trava = threading.Lock()
_fila: deque[int] = deque()
_na_fila: set[int] = set()
_falhou_em: dict[int, float] = {}
_acordar = threading.Event()
_thread: threading.Thread | None = None
_proxima_varredura = 0.0


# --------------------------------------------------------------- as fontes
# Funções finas, uma por fonte: são elas que os testes trocam. As de
# `core.utils` guardam a resposta por processo (lru_cache) -- inclusive a
# FALHA. Aqui se chama a função de verdade (`__wrapped__`): uma queda do
# serviço às 9h não pode deixar o cadastro sem ponto até o próximo deploy.

def _sem_cache(funcao):
    return getattr(funcao, "__wrapped__", funcao)


def _ponto_do_cep(cep):
    from core.utils import buscar_coordenadas_cep_rapido, cep_valido

    if not cep_valido(cep):
        return None, None
    return _sem_cache(buscar_coordenadas_cep_rapido)(cep)


def _cep_e_numero(cep, numero):
    from core.utils import cep_valido, geocodificar_endereco

    if not cep_valido(cep):
        return None, None, None
    return _sem_cache(geocodificar_endereco)(cep, numero or "")


def _rua_e_cidade(rua, numero, cidade, estado, pais):
    from core.utils import geocodificar_sem_cep

    return geocodificar_sem_cep(rua, numero, cidade, estado, pais)


def _centro_da_cidade(cidade, estado, pais):
    from core.utils import buscar_cidade_open_meteo, buscar_coordenadas_por_cidade

    latitude, longitude = _sem_cache(buscar_coordenadas_por_cidade)(cidade, estado or "", pais or "Brasil")
    if latitude is None or longitude is None:
        latitude, longitude = buscar_cidade_open_meteo(cidade, estado or "", pais or "Brasil")
    return latitude, longitude


def _dados_do_cep(cep):
    from core.utils import buscar_dados_cep, cep_valido

    if not cep_valido(cep):
        return None
    return _sem_cache(buscar_dados_cep)(cep)


def _municipio(cidade, estado):
    from core.utils import centro_do_municipio

    return centro_do_municipio(cidade, estado)


_RE_CEP = re.compile(r"\b(\d{5})-?(\d{3})\b")


def _onde_procurar(endereco) -> dict:
    """CEP, rua, número, cidade, UF e país do cadastro, completando o que der.

    O cadastro importado às vezes guarda tudo numa linha só ("Rua X, 10 -
    Centro, Campinas - SP, 13010-000"), ou a UF grudada na cidade, ou o
    estado por extenso. Nada disto é regravado no cadastro (só o ponto):
    é só para a busca ter por onde começar.
    """
    from core.utils import separar_cidade_uf

    texto = " ".join(p for p in (endereco.endereco, endereco.complemento, endereco.bairro) if p)
    cep = endereco.cep or ""
    if not cep:
        casou = _RE_CEP.search(texto)
        cep = f"{casou.group(1)}-{casou.group(2)}" if casou else ""
    cidade, estado = separar_cidade_uf(endereco.cidade, endereco.estado)
    if not cidade:
        # "..., Campinas - SP" no fim da linha da rua
        pedacos = [p.strip() for p in re.split(r",", _RE_CEP.sub("", texto)) if p.strip()]
        for pedaco in reversed(pedacos):
            achada, uf = separar_cidade_uf(pedaco, estado)
            if uf and achada and achada != pedaco:
                cidade, estado = achada, uf
                break
    if (not cidade or not estado) and cep:
        dados = _dados_do_cep(cep) or {}
        cidade = cidade or dados.get("cidade", "")
        estado = estado or dados.get("estado", "")
    return {
        "cep": cep, "rua": endereco.endereco or "", "numero": endereco.numero or "",
        "cidade": cidade, "estado": estado, "pais": endereco.pais or "Brasil",
    }


def procurar(endereco) -> tuple:
    """(latitude, longitude, precisão) do endereço, ou (None, None, "").

    Não grava nada: só pergunta às fontes, na ordem da mais precisa para
    a mais larga, e para na primeira que responde. O centro da cidade sai
    primeiro da tabela do IBGE que está no próprio site (sem rede, nunca
    falha para cidade brasileira escrita certo); as buscas de fora ficam
    para o resto (cidade fora do Brasil, nome que a tabela não conhece).
    """
    from core.utils import no_ritmo_do_nominatim

    from .models import EnderecoCliente

    precisao = EnderecoCliente.Precisao
    onde = _onde_procurar(endereco)
    with no_ritmo_do_nominatim():
        if onde["cep"]:
            latitude, longitude = _ponto_do_cep(onde["cep"])
            if latitude is not None and longitude is not None:
                # o ponto do CEP: a precisão não é conhecida (é o do CEP)
                return latitude, longitude, ""
            latitude, longitude, nivel = _cep_e_numero(onde["cep"], onde["numero"])
            if latitude is not None and longitude is not None:
                return latitude, longitude, nivel or ""
        if onde["rua"] and onde["cidade"]:
            latitude, longitude, nivel = _rua_e_cidade(
                onde["rua"], onde["numero"], onde["cidade"], onde["estado"], onde["pais"],
            )
            if latitude is not None and longitude is not None:
                return latitude, longitude, nivel or precisao.RUA
        if onde["cidade"]:
            latitude, longitude = _municipio(onde["cidade"], onde["estado"])
            if latitude is not None and longitude is not None:
                return latitude, longitude, precisao.CIDADE
            latitude, longitude = _centro_da_cidade(onde["cidade"], onde["estado"], onde["pais"])
            if latitude is not None and longitude is not None:
                return latitude, longitude, precisao.CIDADE
    return None, None, ""


def localizar_um(endereco_id) -> bool | None:
    """Procura e grava o ponto de um endereço. True achou, False não achou, None nada a fazer."""
    from .models import EnderecoCliente

    endereco = (
        EnderecoCliente.objects
        .only("pk", "cep", "endereco", "numero", "complemento", "bairro", "cidade", "estado", "pais",
              "latitude", "longitude")
        .filter(pk=endereco_id)
        .first()
    )
    if endereco is None or endereco.tem_local:
        return None

    latitude, longitude, precisao = procurar(endereco)
    if latitude is None or longitude is None:
        return False

    # Só grava se ainda está sem ponto: um ajuste à mão feito enquanto a
    # busca rodava vence. `update` não dispara o post_save (nada de laço).
    gravados = EnderecoCliente.objects.filter(pk=endereco.pk, latitude__isnull=True).update(
        latitude=Decimal(str(round(float(latitude), 7))),
        longitude=Decimal(str(round(float(longitude), 7))),
        precisao=precisao or "",
    )
    if gravados:
        try:
            from core.home_cache import invalidate_home_cache

            invalidate_home_cache()
        except Exception:  # noqa: BLE001 -- o mapa se acerta no próximo ciclo do cache
            log.exception("localizacao: não deu para avisar o cache da home")
    return bool(gravados)


def pendentes():
    """Os endereços que ainda não têm ponto (o CEP e a cidade podem estar dentro da linha da rua)."""
    from .models import EnderecoCliente

    return EnderecoCliente.objects.filter(latitude__isnull=True).order_by("id")


# ------------------------------------------------------------------ a fila
def ativo() -> bool:
    if not getattr(settings, "LOCALIZAR_ENDERECOS_NO_SITE", True):
        return False
    import sys

    from core.sempre_pronto import _comando_de_manutencao

    # o comando `localizar_enderecos` faz o mesmo trabalho na frente de quem o rodou
    return not _comando_de_manutencao() and sys.argv[1:2] != ["localizar_enderecos"]


def pedir(*ids, forcar=True) -> bool:
    """Põe endereços na fila. Com `forcar`, ignora a falha recente (o endereço mudou)."""
    if not ativo():
        return False
    with _trava:
        for endereco_id in ids:
            if not endereco_id:
                continue
            if forcar:
                _falhou_em.pop(endereco_id, None)
            elif time.monotonic() - _falhou_em.get(endereco_id, -REPETIR_FALHA_S) < REPETIR_FALHA_S:
                continue
            if endereco_id not in _na_fila:
                _na_fila.add(endereco_id)
                _fila.append(endereco_id)
    _garantir_thread()
    _acordar.set()
    return True


def varrer() -> int:
    """Põe na fila os endereços sem ponto (os que falharam há pouco ficam de fora)."""
    ids = list(pendentes().values_list("pk", flat=True)[:LOTE_DA_VARREDURA])
    if ids:
        pedir(*ids, forcar=False)
    return len(ids)


def _fechar_conexoes():
    try:
        connections.close_all()
    except Exception:  # noqa: BLE001
        pass


def _proximo():
    with _trava:
        if not _fila:
            return None
        endereco_id = _fila.popleft()
        _na_fila.discard(endereco_id)
        return endereco_id


def _laco():
    global _proxima_varredura

    _proxima_varredura = time.monotonic() + PRIMEIRA_VARREDURA_S
    while True:
        try:
            if time.monotonic() >= _proxima_varredura:
                _proxima_varredura = time.monotonic() + VARREDURA_S
                try:
                    quantos = varrer()
                    if quantos:
                        log.info("localizacao: %s endereço(s) sem ponto na fila", quantos)
                finally:
                    _fechar_conexoes()

            endereco_id = _proximo()
            if endereco_id is None:
                _acordar.clear()
                _acordar.wait(timeout=max(1.0, _proxima_varredura - time.monotonic()))
                continue
            try:
                achou = localizar_um(endereco_id)
                if achou is False:
                    with _trava:
                        _falhou_em[endereco_id] = time.monotonic()
                    log.warning("localizacao: endereço %s sem ponto em nenhuma fonte", endereco_id)
            except Exception:  # noqa: BLE001 -- um cadastro ruim nunca para a fila
                log.exception("localizacao: falhou ao localizar o endereço %s", endereco_id)
                with _trava:
                    _falhou_em[endereco_id] = time.monotonic()
            finally:
                _fechar_conexoes()
        except Exception:  # noqa: BLE001 -- a thread não morre
            log.exception("localizacao: a volta da fila falhou")
            time.sleep(5)


def _garantir_thread():
    global _thread
    with _trava:
        if _thread is not None and _thread.is_alive():
            return
        _thread = threading.Thread(target=_laco, name="localizar-enderecos", daemon=True)
        _thread.start()


def ligar() -> bool:
    """A fila e a varredura, uma vez por processo do site."""
    if not ativo():
        return False
    _garantir_thread()
    return True


def _depois_de_gravar(sender, instance, created=False, raw=False, **kwargs):
    if raw or instance.latitude is not None:
        return
    endereco_id = instance.pk
    transaction.on_commit(lambda: pedir(endereco_id))


def ligar_ouvinte():
    from django.db.models.signals import post_save

    from .models import EnderecoCliente

    post_save.connect(_depois_de_gravar, sender=EnderecoCliente,
                      dispatch_uid="sistema_interno.localizacao.depois_de_gravar")
