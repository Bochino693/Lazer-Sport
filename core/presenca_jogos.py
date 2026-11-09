"""QUEM ESTÁ NO LAZER & SPORT GAMES AGORA: gente online e quem joga cada jogo.

COMO A CONTA É FEITA. Cada aba do portal e de um jogo manda um "estou aqui"
a cada 30 s (site/paginas/presenca-jogos.js) com um número sorteado pelo
aparelho (guardado no localStorage), um número da aba e, quando está
jogando, o jogo. A aba que não bate há 75 s sai da conta; a que fecha manda
um "saí" e sai na hora. A conta é por APARELHO: duas abas do mesmo
navegador (o portal e o jogo aberto nele) são uma pessoa só.

O QUE NÃO SE GUARDA. Nem conta, nem nome, nem IP: o número sorteado não diz
quem é a pessoa, vive só na memória deste processo e some 75 s depois da
última batida. Nada disso vai para o banco.

POR QUE NA MEMÓRIA. Uma batida a cada 30 s por aba viraria uma gravação no
banco a cada poucos segundos com o portal cheio, para um dado que só vale
por um minuto. A conta fica num dicionário deste processo, com uma trava (o
gunicorn atende com várias threads).

O LIMITE. O site roda UM processo do gunicorn (gunicorn.conf.py,
WEB_WORKERS=1). Com mais de um, cada processo só conhece quem bateu nele e a
conta se divide entre eles (com dois, cada um mostra mais ou menos a
metade). Se um dia forem vários, o dicionário vai para um cache
compartilhado (Redis): o resumo que sai daqui não muda de forma.

CONTRA ABUSO. Só POST, corpo pequeno, número do aparelho e da aba com
formato certo, no máximo BATIDAS_POR_MINUTO por aparelho, no máximo
ABAS_POR_APARELHO abas por aparelho e um teto de aparelhos na memória.
Robôs (buscadores, robôs de IA, programas de cópia e quem caiu na armadilha
do escudo) não entram na conta.
"""

from __future__ import annotations

import re
import threading
import time

#: A aba que não bate há mais que isto sai da conta (a batida é a cada 30 s:
#: sobra folga para uma batida perdida no caminho).
VALIDADE = 75
#: De quanto em quanto tempo a página bate (o JavaScript usa o que vier na resposta).
INTERVALO = 30
#: O resumo (a conta de todo mundo) é refeito no máximo a cada tantos segundos.
RESUMO_SEGUNDOS = 2.0
#: Batidas aceitas por aparelho a cada minuto: uma aba bate 2 vezes; o portal
#: com um jogo aberto, mais a troca de jogo e o "saí", ficam bem abaixo disto.
BATIDAS_POR_MINUTO = 20
ABAS_POR_APARELHO = 6
#: Teto de aparelhos na memória (cada um ocupa poucas centenas de bytes) e de
#: aparelhos novos por minuto: quem inventa um número novo a cada batida para
#: inflar a conta esbarra aqui (gente de verdade chegando não passa perto).
MAXIMO_DE_APARELHOS = 20_000
NOVOS_POR_MINUTO = 600
#: Quem chega, sai ou troca de jogo vê a conta já com a mudança, mas o resumo
#: não é refeito mais que uma vez a cada tanto (uma enxurrada de batidas novas
#: não vira uma conta inteira por batida).
RESUMO_MINIMO = 0.25
#: O corpo de uma batida é um JSON de poucas dezenas de bytes.
CORPO_MAXIMO = 512

FORMATO_DO_APARELHO = re.compile(r"^[A-Za-z0-9_-]{16,40}$")
FORMATO_DA_ABA = re.compile(r"^[A-Za-z0-9_-]{6,24}$")
FORMATO_DO_JOGO = re.compile(r"^[a-z0-9-]{1,80}$")
#: Além das listas do escudo dos jogos: os nomes genéricos de robô.
ROBO_GENERICO = re.compile(r"bot\b|bot/|crawl|spider|slurp|preview|lighthouse|pagespeed|monitor|uptime", re.I)

_trava = threading.Lock()
#: aparelho -> {"abas": {aba: (visto, jogo)}, "janela": início do minuto, "batidas": n}
_aparelhos: dict[str, dict] = {}
_resumo = {"online": 0, "jogando": {}}
_resumo_feito = -RESUMO_SEGUNDOS
#: [início do minuto, aparelhos novos nele]
_novos = [0.0, 0]


def _agora() -> float:
    return time.monotonic()


def e_robo(request) -> bool:
    """Quem não é gente não entra na conta (as listas são as do escudo dos jogos)."""
    from . import escudo_jogos

    ua = (request.META.get("HTTP_USER_AGENT") or "")[:512]
    if not ua.strip():
        return True
    if escudo_jogos.e_robo_de_ia(ua) or escudo_jogos.e_ferramenta(ua) or escudo_jogos.e_buscador(ua):
        return True
    if ROBO_GENERICO.search(ua):
        return True
    try:
        return escudo_jogos.marcado(request)
    except Exception:  # cache fora do ar: na dúvida, conta
        return False


def _limpar(agora: float) -> None:
    """Tira as abas vencidas e refaz o resumo (chamado com a trava presa)."""
    global _resumo, _resumo_feito
    online = 0
    jogando: dict[str, int] = {}
    for aparelho in list(_aparelhos):
        abas = _aparelhos[aparelho]["abas"]
        for aba in [a for a, (visto, _) in abas.items() if agora - visto > VALIDADE]:
            del abas[aba]
        if not abas:
            del _aparelhos[aparelho]
            continue
        online += 1
        # o mesmo aparelho com o mesmo jogo em duas abas conta uma vez
        for jogo in {jogo for _, jogo in abas.values() if jogo}:
            jogando[jogo] = jogando.get(jogo, 0) + 1
    _resumo = {"online": online, "jogando": jogando}
    _resumo_feito = agora


def bater(aparelho: str, aba: str, jogo: str = "", saiu: bool = False) -> dict | None:
    """Uma batida ("estou aqui" ou "saí"). Devolve o resumo, ou None quando o aparelho passou do limite.

    Quem chama já conferiu o formato do aparelho, da aba e do jogo.
    """
    agora = _agora()
    with _trava:
        dados = _aparelhos.get(aparelho)
        if dados is None:
            if saiu:
                return {"online": _resumo["online"], "jogando": dict(_resumo["jogando"])}
            if agora - _novos[0] >= 60:
                _novos[0], _novos[1] = agora, 0
            if len(_aparelhos) >= MAXIMO_DE_APARELHOS:
                _limpar(agora)
            if len(_aparelhos) >= MAXIMO_DE_APARELHOS or _novos[1] >= NOVOS_POR_MINUTO:
                # cheio: a pessoa vê a conta, só não entra nela
                return {"online": _resumo["online"], "jogando": dict(_resumo["jogando"])}
            _novos[1] += 1
            dados = _aparelhos[aparelho] = {"abas": {}, "janela": agora, "batidas": 0}
        if agora - dados["janela"] >= 60:
            dados["janela"], dados["batidas"] = agora, 0
        dados["batidas"] += 1
        if dados["batidas"] > BATIDAS_POR_MINUTO:
            return None
        abas = dados["abas"]
        mudou = False
        if saiu:
            mudou = abas.pop(aba, None) is not None
        else:
            anterior = abas.get(aba)
            mudou = anterior is None or anterior[1] != jogo
            abas[aba] = (agora, jogo)
            if len(abas) > ABAS_POR_APARELHO:
                # aba demais no mesmo aparelho: sai a que bateu há mais tempo
                del abas[min(abas, key=lambda a: abas[a][0])]
        if not abas:
            del _aparelhos[aparelho]
        # quem chegou, saiu ou trocou de jogo vê a conta já com a mudança
        if agora - _resumo_feito >= (RESUMO_MINIMO if mudou else RESUMO_SEGUNDOS):
            _limpar(agora)
        return {"online": _resumo["online"], "jogando": dict(_resumo["jogando"])}


def resumo() -> dict:
    """A conta de agora (para a página já abrir com os números)."""
    agora = _agora()
    with _trava:
        if agora - _resumo_feito >= RESUMO_SEGUNDOS:
            _limpar(agora)
        return {"online": _resumo["online"], "jogando": dict(_resumo["jogando"])}


def esquecer() -> None:
    """Zera a conta (os testes)."""
    global _resumo, _resumo_feito
    with _trava:
        _aparelhos.clear()
        _resumo = {"online": 0, "jogando": {}}
        _resumo_feito = -RESUMO_SEGUNDOS
        _novos[0], _novos[1] = 0.0, 0
