"""Quem está online agora e quando cada conta foi vista por último.

O QUE JÁ EXISTIA, E POR QUE NÃO SERVIA.
  * `User.last_login` só muda quando a pessoa digita a senha. Quem fica
    logado por semanas (o celular do cliente, o tablet do galpão) aparece
    como "entrou há 20 dias" estando com o site aberto agora.
  * A presença dos jogos (core/presenca_jogos.py) conta APARELHOS, sem
    conta nem nome, na memória do processo -- de propósito: diz "12 pessoas
    jogando", nunca quem.
  * As sessões guardam a validade, não o último uso.

O QUE ISTO FAZ. Toda requisição de uma conta logada (site, painel ou
aplicativo) é um sinal de vida. O `PresencaMiddleware` anota o sinal em
`PresencaUsuario` (o último) e em `AcessoDiario` (um por dia, para os
gráficos de ativos) -- mas NO MÁXIMO UMA VEZ POR MINUTO POR CONTA: o
primeiro sinal do minuto marca uma chave no cache e os seguintes morrem
ali, sem banco. A gravação vai pela mesma linha de fundo dos cliques
(core/cliques.py): a página não espera por ela.

"Online" é ter dado sinal nos últimos ONLINE_MINUTOS. O painel mostra o
resto como "Visto há 2 h", "Visto ontem às 14:32", "Nunca entrou".

QUEM, E NÃO SÓ QUANTOS (o AJUSTE da seção 76 do LEIA-ME-V10). O painel
dizia "1 online agora" sem dizer quem. `agora_mesmo()` devolve as PESSOAS:
quem está online (nome, papel -- Admin, Equipe ou Cliente --, onde está e
há quanto tempo), quem passou nas últimas 24 h e os contadores do topo. A
barra de cima de todo o painel pede só a EQUIPE; a tela Usuários (só o
superadministrador) pede as contas todas. Nome de cliente nunca sai na
resposta de quem não abre a tela Usuários.

Desligável por PRESENCA_DE_USUARIOS (desligado nos testes que não são
dele: uma gravação a mais mudaria a conta de consultas de toda a suíte).
"""

from __future__ import annotations

import datetime as dt
import logging

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

log = logging.getLogger("core.presenca")

#: Sinal mais novo que isto = online agora.
ONLINE_MINUTOS = 5
#: No máximo uma gravação por conta a cada tantos segundos.
INTERVALO_GRAVACAO = 60
PREFIXO_CACHE = "ls:presenca:"

#: "Vistos por último": quem passou neste tanto de horas e não está online.
RECENTES_HORAS = 24
#: Quantas pessoas cabem em cada lista (o total vai junto, à parte).
LIMITE_ONLINE = 60
LIMITE_RECENTES = 12
#: A resposta de `agora_mesmo` fica este tanto no cache: vinte tablets
#: abertos perguntando de 45 em 45 s não viram vinte rodadas no banco.
CACHE_AGORA = 10
#: De quanto em quanto tempo a tela pergunta de novo (segundos).
INTERVALO_DA_TELA = 45
#: Os grupos dos contadores, que também filtram a lista de Usuários.
GRUPOS = ("online", "hoje", "semana", "mes", "nunca")

ROTULO_DO_PAPEL = {"admin": "Admin", "equipe": "Equipe", "cliente": "Cliente"}
ROTULO_DE_ONDE = {"painel": "Painel", "site": "Site", "app": "Aplicativo"}
#: Quantas cores de avatar existem (a cor é estável: sai do número da conta).
CORES_DE_AVATAR = 5


def ligada():
    return bool(getattr(settings, "PRESENCA_DE_USUARIOS", True))


def onde_foi_visto(request):
    if getattr(request, "is_interno", False):
        return "painel"
    if (request.path or "").startswith("/api/"):
        return "app"
    return "site"


def marcar(usuario_id, onde="site", agora=None):
    """Anota o sinal de vida; devolve True quando este sinal vai ao banco.

    `cache.add` só grava se a chave não existe: é o freio. Num minuto com
    trinta requisições da mesma conta, só a primeira passa daqui.
    """
    if not usuario_id:
        return False
    if not cache.add(f"{PREFIXO_CACHE}{usuario_id}", 1, INTERVALO_GRAVACAO):
        return False
    from . import cliques

    cliques.depois(gravar, usuario_id, onde, agora or timezone.now())
    return True


def gravar(usuario_id, onde, agora):
    """O último sinal e o dia de acesso. Nunca levanta (presença não derruba página)."""
    from .models import AcessoDiario, PresencaUsuario

    try:
        with transaction.atomic():
            if not PresencaUsuario.objects.filter(usuario_id=usuario_id).update(visto_em=agora, onde=onde):
                PresencaUsuario.objects.create(usuario_id=usuario_id, visto_em=agora, onde=onde)
    except IntegrityError:
        # a conta foi apagada no meio do caminho, ou outro processo criou a linha
        pass
    except DatabaseError:
        log.warning("presenca: o sinal da conta %s não foi gravado", usuario_id, exc_info=True)
        return

    dia = timezone.localtime(agora).date()
    try:
        with transaction.atomic():
            if not AcessoDiario.objects.filter(usuario_id=usuario_id, dia=dia).update(ultimo=agora):
                AcessoDiario.objects.create(usuario_id=usuario_id, dia=dia, primeiro=agora, ultimo=agora)
    except IntegrityError:
        pass
    except DatabaseError:
        log.warning("presenca: o acesso do dia da conta %s não foi gravado", usuario_id, exc_info=True)


class PresencaMiddleware:
    """Depois da resposta: a conta logada deu sinal de vida.

    Fica depois do AuthenticationMiddleware. Lê `request.user` só quando a
    sessão já o carregou ou quando há cookie de sessão: o visitante anônimo
    da vitrine em cache não ganha consulta nenhuma por causa disto.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resposta = self.get_response(request)
        if not ligada():
            return resposta
        try:
            if not (
                settings.SESSION_COOKIE_NAME in request.COOKIES
                or request.META.get("HTTP_AUTHORIZATION")
                or hasattr(request, "_cached_user")
            ):
                return resposta  # anônimo sem sessão: nada a anotar, nenhuma consulta
            usuario = getattr(request, "user", None)
            if usuario is not None and getattr(usuario, "is_authenticated", False):
                marcar(usuario.pk, onde_foi_visto(request))
        except Exception:  # noqa: BLE001 -- sinal de vida nunca derruba a resposta
            log.warning("presenca: falhou ao anotar o sinal", exc_info=True)
        return resposta


# ----------------------------------------------------------------------
# Como o painel conta isso para as pessoas
# ----------------------------------------------------------------------

def _hora(valor):
    return timezone.localtime(valor).strftime("%H:%M")


def quando(momento, agora=None):
    """"agora", "há 12 min", "há 3 h", "ontem às 14:32", "em 03/11 às 09:10"."""
    agora = agora or timezone.now()
    local = timezone.localtime(momento)
    hoje = timezone.localtime(agora).date()
    passado = agora - momento
    if passado < dt.timedelta(minutes=1):
        return "agora"
    if passado < dt.timedelta(hours=1):
        return f"há {int(passado.total_seconds() // 60)} min"
    if local.date() == hoje:
        return f"há {int(passado.total_seconds() // 3600)} h"
    if local.date() == hoje - dt.timedelta(days=1):
        return f"ontem às {_hora(momento)}"
    if local.year == hoje.year:
        return f"em {local:%d/%m} às {_hora(momento)}"
    return f"em {local:%d/%m/%Y}"


def situacao(visto_em=None, last_login=None, agora=None):
    """{"online", "codigo", "texto", "quando"} para o selo da lista e o modal.

    `visto_em` é o sinal de vida (presença); `last_login` é o reserva para
    as contas que não aparecem desde que a presença passou a existir.
    """
    agora = agora or timezone.now()
    if visto_em and agora - visto_em <= dt.timedelta(minutes=ONLINE_MINUTOS):
        return {"online": True, "codigo": "online", "texto": "Online agora", "quando": visto_em.isoformat()}

    ultimo = max([v for v in (visto_em, last_login) if v], default=None)
    if ultimo is None:
        return {"online": False, "codigo": "nunca", "texto": "Nunca entrou", "quando": None}

    verbo = "Visto" if visto_em and ultimo == visto_em else "Entrou"
    passado = agora - ultimo
    trecho = quando(ultimo, agora)
    if trecho == "agora":  # o login deste minuto, de quem a presença ainda não anotou
        trecho = "há 1 min"
    codigo = "recente" if passado <= dt.timedelta(days=7) else "antigo"
    return {"online": False, "codigo": codigo, "texto": f"{verbo} {trecho}", "quando": ultimo.isoformat()}


def situacao_da_conta(usuario, agora=None):
    """A situação de um `User` (com `presenca` já carregada por select_related)."""
    try:
        presenca = usuario.presenca
    except Exception:  # noqa: BLE001 -- RelatedObjectDoesNotExist: nunca deu sinal
        presenca = None
    return situacao(getattr(presenca, "visto_em", None), usuario.last_login, agora)


def _marcos(agora):
    """Os começos de "hoje", "7 dias" e "30 dias" (meia-noite local)."""
    local = timezone.localtime(agora)
    meia_noite = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "hoje": meia_noite,
        "semana": meia_noite - dt.timedelta(days=6),
        "mes": meia_noite - dt.timedelta(days=29),
    }


def resumo(agora=None):
    """Os números do topo da tela Usuários, numa consulta só."""
    from django.contrib.auth.models import User
    from django.db.models import Count, Q

    agora = agora or timezone.now()
    marcos = _marcos(agora)

    def desde(momento):
        return Q(presenca__visto_em__gte=momento) | Q(last_login__gte=momento)

    numeros = User.objects.aggregate(
        online=Count("pk", filter=Q(presenca__visto_em__gte=agora - dt.timedelta(minutes=ONLINE_MINUTOS))),
        hoje=Count("pk", filter=desde(marcos["hoje"])),
        semana=Count("pk", filter=desde(marcos["semana"])),
        mes=Count("pk", filter=desde(marcos["mes"])),
        nunca=Count("pk", filter=Q(last_login__isnull=True, presenca__isnull=True)),
        total=Count("pk"),
    )
    return numeros


def grupos_da_conta(usuario, agora=None):
    """Em quais contadores a conta entra: a MESMA regra de `resumo()`.

    É o que a lista de Usuários escreve em cada linha (`data-presenca`),
    para o toque num contador filtrar a lista sem ir ao servidor. A conta
    vem com `presenca` já carregada (select_related).
    """
    agora = agora or timezone.now()
    try:
        visto_em = usuario.presenca.visto_em
    except Exception:  # noqa: BLE001 -- RelatedObjectDoesNotExist: nunca deu sinal
        visto_em = None
    ultimo = max([v for v in (visto_em, usuario.last_login) if v], default=None)
    if ultimo is None:
        return ["nunca"]
    grupos = []
    if visto_em and agora - visto_em <= dt.timedelta(minutes=ONLINE_MINUTOS):
        grupos.append("online")
    grupos += [nome for nome, marco in _marcos(agora).items() if ultimo >= marco]
    return grupos


# ----------------------------------------------------------------------
# Quem está online agora (e não só quantos)
# ----------------------------------------------------------------------

def tem_funcao_de_equipe(campo="pk"):
    """Exists(): a conta está em algum grupo de função do painel.

    `campo` é onde a consulta de fora guarda o número da conta ("pk" numa
    consulta de User; "usuario_id" numa de acessos).
    """
    from django.contrib.auth.models import User
    from django.db.models import Exists, OuterRef

    from sistema_interno.permissoes import NOMES_DOS_GRUPOS

    return Exists(
        User.groups.through.objects.filter(user_id=OuterRef(campo), group__name__in=NOMES_DOS_GRUPOS)
    )


def papel_da_conta(usuario, tem_funcao=None):
    """"admin", "equipe" ou "cliente".

    A regra de "quem é da casa" é a mesma do importador de orçamentos
    (sistema_interno/importacao_word/identificar.py): superusuário, staff
    ou quem tem função de equipe no painel. O resto é cliente do site.
    `tem_funcao` vem anotado na consulta (`tem_funcao_de_equipe`); sem
    ele, pergunta ao banco.
    """
    if usuario.is_superuser:
        return "admin"
    if usuario.is_staff:
        return "equipe"
    if tem_funcao is None:
        from sistema_interno.permissoes import faz_parte_da_equipe

        tem_funcao = faz_parte_da_equipe(usuario)
    return "equipe" if tem_funcao else "cliente"


def nome_da_conta(usuario):
    try:
        nome = (usuario.perfil.nome_completo or "").strip()
    except Exception:  # noqa: BLE001 -- conta sem perfil
        nome = ""
    return nome or usuario.get_full_name().strip() or usuario.username


def iniciais(nome):
    """"Heitor Costa" -> "HC"; "teste_orc" -> "TO"; "ana" -> "AN"."""
    partes = [p for p in str(nome or "").replace("_", " ").replace(".", " ").split() if p[:1].isalnum()]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


def cartao_da_conta(usuario, papel=None):
    """O que toda lista de pessoas do painel mostra: nome, iniciais, cor e papel."""
    nome = nome_da_conta(usuario)
    papel = papel or papel_da_conta(usuario, getattr(usuario, "_tem_funcao", None))
    return {
        "id": usuario.pk,
        "nome": nome,
        "usuario": usuario.username,
        "iniciais": iniciais(nome),
        "cor": usuario.pk % CORES_DE_AVATAR,
        "papel": papel,
        "papel_rotulo": ROTULO_DO_PAPEL[papel],
    }


def _pessoa(usuario, agora, visto_em=None, onde=None):
    try:
        presenca = usuario.presenca
    except Exception:  # noqa: BLE001 -- nunca deu sinal: só o último login
        presenca = None
    visto_em = visto_em or getattr(presenca, "visto_em", None)
    onde = onde or getattr(presenca, "onde", None)
    ultimo = max([v for v in (visto_em, usuario.last_login) if v], default=agora)
    online = bool(visto_em and agora - visto_em <= dt.timedelta(minutes=ONLINE_MINUTOS))
    # o lugar só vale quando o último sinal é o da presença (o login não diz onde)
    if not (visto_em and ultimo == visto_em):
        onde = None
    pessoa = cartao_da_conta(usuario)
    pessoa.update({
        "onde": onde,
        "onde_rotulo": ROTULO_DE_ONDE.get(onde),
        "online": online,
        "visto_em": ultimo.isoformat(),
        "quando": quando(ultimo, agora),
        "desde": None,
        "voce": False,
    })
    return pessoa


def _listas_de_agora(agora, contas):
    """As listas, sem o "você": é o pedaço que vai para o cache."""
    from django.contrib.auth.models import User
    from django.db.models import F, Q

    from .models import AcessoDiario

    corte_online = agora - dt.timedelta(minutes=ONLINE_MINUTOS)
    base = User.objects.select_related("perfil", "presenca").annotate(_tem_funcao=tem_funcao_de_equipe())
    if contas:
        corte = agora - dt.timedelta(hours=RECENTES_HORAS)
        consulta = base.filter(Q(presenca__visto_em__gte=corte) | Q(last_login__gte=corte))
    else:
        # só a equipe, e só quem está online: nenhum cliente entra nesta consulta
        consulta = base.filter(presenca__visto_em__gte=corte_online).filter(
            Q(is_superuser=True) | Q(is_staff=True) | Q(_tem_funcao=True)
        )
    consulta = consulta.order_by(F("presenca__visto_em").desc(nulls_last=True), "-last_login", "pk")
    pessoas = [_pessoa(usuario, agora) for usuario in consulta[: LIMITE_ONLINE * 4]]
    pessoas.sort(key=lambda p: dt.datetime.fromisoformat(p["visto_em"]), reverse=True)

    online = [p for p in pessoas if p["online"]]
    resposta = {
        "agora": timezone.localtime(agora).isoformat(),
        "online_minutos": ONLINE_MINUTOS,
        "intervalo": INTERVALO_DA_TELA,
        "equipe": [p for p in online if p["papel"] != "cliente"][:LIMITE_ONLINE],
    }
    visiveis = list(resposta["equipe"])
    if contas:
        recentes = [p for p in pessoas if not p["online"]]
        resposta.update({
            "online": online[:LIMITE_ONLINE],
            "recentes": recentes[:LIMITE_RECENTES],
            "recentes_total": len(recentes),
            "recentes_horas": RECENTES_HORAS,
            "numeros": resumo(agora),
        })
        visiveis = resposta["online"] + resposta["recentes"]

    # "desde": o primeiro sinal de hoje de cada pessoa que vai aparecer (uma consulta)
    ids = {p["id"] for p in visiveis}
    if ids:
        hoje = timezone.localtime(agora).date()
        primeiros = dict(
            AcessoDiario.objects.filter(usuario_id__in=ids, dia=hoje).values_list("usuario_id", "primeiro")
        )
        for pessoa in visiveis:
            primeiro = primeiros.get(pessoa["id"])
            if primeiro:
                pessoa["desde"] = _hora(primeiro)
    return resposta


def agora_mesmo(eu=None, contas=False, agora=None):
    """Quem está online agora -- e, com `contas`, quem passou hoje e os contadores.

    SEM `contas`: só a EQUIPE online (a pilha de avatares da barra de cima,
    que qualquer pessoa da equipe vê). COM `contas`: todas as contas online,
    as vistas nas últimas 24 h e os números do topo -- é o que a tela
    Usuários mostra, e quem chama confere a permissão dela.

    `eu` é quem está olhando: entra marcado "você" e SEMPRE entre os
    online -- está com o painel aberto, ainda que o sinal dele não tenha
    chegado ao banco (o primeiro do minuto vai pela linha de fundo).

    São no máximo três consultas, não importa o tamanho do histórico, e a
    resposta fica CACHE_AGORA segundos no cache (`agora` fixo, nos testes,
    não usa o cache).
    """
    import copy

    fixo = agora is not None
    agora = agora or timezone.now()
    chave = f"{PREFIXO_CACHE}agora:{'contas' if contas else 'equipe'}"
    resposta = None if fixo else cache.get(chave)
    if resposta is None:
        resposta = _listas_de_agora(agora, contas)
        if not fixo:
            cache.set(chave, resposta, CACHE_AGORA)
    resposta = copy.deepcopy(resposta)

    if eu is not None and getattr(eu, "is_authenticated", False):
        resposta["eu"] = eu.pk
        for nome in ("equipe", "online") if contas else ("equipe",):
            lista = resposta[nome]
            meu = next((p for p in lista if p["id"] == eu.pk), None)
            if meu is None:
                meu = _pessoa(eu, agora, visto_em=agora, onde="painel")
                if nome == "equipe" and meu["papel"] == "cliente":
                    continue
                lista.insert(0, meu)
            meu["voce"] = True
        if contas:
            resposta["recentes"] = [p for p in resposta["recentes"] if p["id"] != eu.pk]
    resposta["equipe_total"] = len(resposta["equipe"])
    if contas:
        resposta["numeros"]["online"] = max(resposta["numeros"]["online"], len(resposta["online"]))
    return resposta
