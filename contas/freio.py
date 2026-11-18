"""O freio do login: senhas erradas demais pausam o acesso por um tempo.

VALE EM TODA PORTA. O login do site (/login/), o do painel (interno.), o do
/system/ (admin), o do aplicativo (/api/v1/auth/login/) e o do allauth
(/accounts/login/). As telas da casa chamam `autenticar()`, que confere o
freio, autentica, conta o erro e devolve a mensagem certa; o que chega por
fora (o allauth, um authenticate() qualquer) é contado pelo sinal
`user_login_failed` e barrado pelo `backends.FreioDeLoginBackend`, o
primeiro da lista AUTHENTICATION_BACKENDS.

DUAS CONTAGENS, cada uma na sua janela (LOGIN_FREIO_JANELA_MIN):

  * por CONTA: LOGIN_FREIO_POR_CONTA erros (5) pausam aquela conta por
    LOGIN_FREIO_BLOQUEIO_MIN minutos (15), de qualquer IP -- é o que para
    quem tenta adivinhar a senha de alguém. O login digitado é trocado pela
    conta (usuário ou e-mail, tanto faz); login que não existe conta do
    mesmo jeito, então a resposta não diz se a conta existe;
  * por IP: LOGIN_FREIO_POR_IP erros (20), em contas quaisquer, pausam o
    IP -- é o que para quem testa uma senha em muitas contas. IP privado
    (o próprio servidor, a rede interna) não entra: atrás dele estaria todo
    mundo.

O acerto zera a contagem da conta, não a do IP (senão um acerto de vez em
quando, numa conta do próprio atacante, liberaria o chute nas outras).
Cada pausa que começa vira uma OcorrenciaSeguranca, e a tela "Segurança
das contas" pode liberar antes da hora.

ONDE MORA A CONTAGEM: no cache do Django (hoje o LocMemCache, memória do
processo). Com mais de um worker sem cache compartilhado, cada worker conta
a sua parte -- o freio continua valendo, só que com o limite multiplicado
pelo número de workers. O IP vem de `core.registro_cadastro.ip_da_requisicao`
(o mesmo do freio de cadastros): com proxy na frente, confira
IP_REAL_CABECALHO.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.core.cache import cache
from django.utils import timezone

from .emails import normalizar_email

log = logging.getLogger(__name__)

PREFIXO = "contas:login"


def _numero(nome, padrao):
    try:
        return max(1, int(getattr(settings, nome, padrao)))
    except (TypeError, ValueError):
        return padrao


def ativo() -> bool:
    return bool(getattr(settings, "LOGIN_FREIO_ATIVO", True))


def limite_por_conta() -> int:
    return _numero("LOGIN_FREIO_POR_CONTA", 5)


def limite_por_ip() -> int:
    return _numero("LOGIN_FREIO_POR_IP", 20)


def janela() -> int:
    return _numero("LOGIN_FREIO_JANELA_MIN", 15) * 60


def duracao_do_bloqueio() -> int:
    return _numero("LOGIN_FREIO_BLOQUEIO_MIN", 15) * 60


def _resumo(texto) -> str:
    return hashlib.sha256(str(texto).encode("utf-8")).hexdigest()[:24]


# ----------------------------------------------------------------------
# Quem é o login digitado
# ----------------------------------------------------------------------
def conta_do_login(login):
    """A conta do usuário OU e-mail digitado (o usuário vence, como no ModelBackend)."""
    login = (login or "").strip()
    if not login:
        return None
    User = get_user_model()
    conta = User.objects.filter(username=login).first()
    if conta is None and "@" in login:
        from .emails import conta_do_email

        conta = conta_do_email(login)
    if conta is None:
        conta = User.objects.filter(username__iexact=login).first()
    return conta


def _origem(request) -> str:
    caminho = (getattr(request, "path", "") or "").lower()
    if getattr(request, "is_interno", False):
        return "painel"
    if caminho.startswith("/system/"):
        return "admin"
    if caminho.startswith("/api/"):
        return "api"
    if caminho.startswith("/accounts/"):
        return "allauth"
    return "site"


def _ip(request):
    from core.registro_cadastro import ip_da_requisicao, ip_privado

    if request is None:
        return None, False
    ip, _ = ip_da_requisicao(request)
    return ip, bool(ip) and not ip_privado(ip)


def _conta_lembrada(request, login):
    """conta_do_login, uma vez por requisição (o freio pergunta mais de uma vez)."""
    if request is None:
        return conta_do_login(login)
    lembradas = request.__dict__.setdefault("_contas_freio_contas", {})
    chave = (login or "").strip()
    if chave not in lembradas:
        lembradas[chave] = conta_do_login(chave)
    return lembradas[chave]


def _alvos(request, login):
    """[(chave, limite, conta)]: a da conta (ou do login) e, com IP público, a do IP."""
    conta = _conta_lembrada(request, login)
    if conta is not None:
        alvo = f"conta:{conta.pk}"
    else:
        alvo = "login:" + _resumo(normalizar_email(login) if "@" in (login or "") else (login or "").strip().lower())
    alvos = [(alvo, limite_por_conta(), conta)]
    ip, publico = _ip(request)
    if publico:
        alvos.append((f"ip:{_resumo(ip)}", limite_por_ip(), None))
    return alvos, conta, ip


# ----------------------------------------------------------------------
# Ler, contar, liberar
# ----------------------------------------------------------------------
def _fim_do_bloqueio(alvo) -> float:
    try:
        return float(cache.get(f"{PREFIXO}:bloqueio:{alvo}") or 0)
    except Exception:  # noqa: BLE001 -- cache fora do ar não tranca ninguém
        return 0.0


#: Existe enquanto houver alguma pausa no ar: sem ela, ninguém está pausado
#: e a conferência não precisa nem descobrir de quem é o login (zero consultas).
MARCA_DE_PAUSA = f"{PREFIXO}:alguma-pausa"


def segundos_de_bloqueio(request, login) -> int:
    """Quanto falta para poder tentar de novo (0 = pode agora)."""
    if not ativo():
        return 0
    try:
        if not cache.get(MARCA_DE_PAUSA):
            return 0
    except Exception:  # noqa: BLE001
        return 0
    alvos, _, _ = _alvos(request, login)
    agora = time.time()
    resta = max((_fim_do_bloqueio(alvo) - agora for alvo, _, _ in alvos), default=0)
    return max(0, int(resta + 0.999))


def registrar_falha(request, login, *, origem="") -> int:
    """Mais um erro na conta e no IP. Devolve os segundos de pausa, se começou uma."""
    if not ativo():
        return 0
    alvos, conta, ip = _alvos(request, login)
    agora = time.time()
    pausa = 0
    for alvo, limite, conta_do_alvo in alvos:
        if _fim_do_bloqueio(alvo) > agora:
            continue  # já pausado: não estende nem registra de novo
        chave = f"{PREFIXO}:falhas:{alvo}"
        try:
            if cache.add(chave, 1, janela()):
                erros = 1
            else:
                erros = cache.incr(chave)
        except ValueError:  # a chave venceu entre o add e o incr
            cache.set(chave, 1, janela())
            erros = 1
        except Exception:  # noqa: BLE001
            log.exception("Freio de login sem cache")
            return 0
        if erros >= limite:
            fim = agora + duracao_do_bloqueio()
            cache.set(f"{PREFIXO}:bloqueio:{alvo}", fim, duracao_do_bloqueio())
            cache.set(MARCA_DE_PAUSA, fim, duracao_do_bloqueio())
            cache.delete(chave)
            pausa = max(pausa, duracao_do_bloqueio())
            _registrar_ocorrencia(
                alvo=alvo, conta=conta_do_alvo, login=login, ip=ip,
                origem=origem or _origem(request), erros=erros,
            )
    return pausa


def registrar_acerto(request, login):
    """O acerto zera a contagem da CONTA (a do IP continua)."""
    if not ativo():
        return
    alvos, _, _ = _alvos(request, login)
    try:
        cache.delete(f"{PREFIXO}:falhas:{alvos[0][0]}")
    except Exception:  # noqa: BLE001
        pass


def liberar(*, conta=None, ip=None, login=None):
    """Tira a pausa (a tela "Segurança das contas" usa)."""
    alvos = []
    if conta is not None:
        alvos.append(f"conta:{getattr(conta, 'pk', conta)}")
    if ip:
        alvos.append(f"ip:{_resumo(ip)}")
    if login:
        alvos.append("login:" + _resumo(normalizar_email(login) if "@" in login else login.strip().lower()))
    for alvo in alvos:
        cache.delete_many([f"{PREFIXO}:bloqueio:{alvo}", f"{PREFIXO}:falhas:{alvo}"])


def _registrar_ocorrencia(*, alvo, conta, login, ip, origem, erros):
    from .models import OcorrenciaSeguranca

    pelo_ip = alvo.startswith("ip:")
    minutos = duracao_do_bloqueio() // 60
    if pelo_ip:
        motivo = f"{erros} senhas erradas a partir deste IP em {janela() // 60} min: o IP ficou pausado por {minutos} min."
    else:
        motivo = f"{erros} senhas erradas para este login em {janela() // 60} min: o acesso ficou pausado por {minutos} min."
    try:
        OcorrenciaSeguranca.objects.create(
            tipo=OcorrenciaSeguranca.Tipo.LOGIN_BLOQUEADO,
            usuario=conta,
            username=(getattr(conta, "username", "") or "")[:150],
            login_tentado=(login or "")[:254],
            ip=ip,
            origem=origem[:20],
            motivo=motivo,
        )
    except Exception:  # noqa: BLE001 -- o freio vale mesmo sem o registro
        log.exception("A ocorrência do login bloqueado não foi gravada.")


# ----------------------------------------------------------------------
# A porta das telas da casa
# ----------------------------------------------------------------------
def mensagem_de_bloqueio(segundos) -> str:
    minutos = max(1, (int(segundos) + 59) // 60)
    volta = timezone.localtime(timezone.now() + timedelta(seconds=int(segundos)))
    return (
        "Muitas tentativas de entrar com senha errada. Por segurança, o acesso "
        f"ficou pausado por {minutos} minuto{'s' if minutos != 1 else ''} "
        f"(até {volta:%H:%M}). Se esqueceu a senha, use “Esqueci minha senha”."
    )


@dataclass
class Tentativa:
    usuario: object = None
    bloqueio: int = 0

    @property
    def bloqueada(self) -> bool:
        return self.bloqueio > 0

    @property
    def mensagem(self) -> str:
        return mensagem_de_bloqueio(self.bloqueio) if self.bloqueada else ""


def username_para(login, request=None) -> str:
    """O usuário a autenticar: o digitado ou, se for e-mail, o da conta dele."""
    login = (login or "").strip()
    conta = _conta_lembrada(request, login)
    return conta.get_username() if conta is not None else login


def autenticar(request, login, senha, *, origem="") -> Tentativa:
    """Confere o freio, autentica e conta: a porta das telas de login da casa.

    Volta `Tentativa(usuario)` no acerto; `Tentativa(None)` no erro; e
    `Tentativa(None, bloqueio=segundos)` quando o acesso está pausado (ou
    acabou de ser, com este erro) -- `tentativa.mensagem` diz até quando.
    """
    if request is not None:
        request._contas_freio_tratado = True
    login = (login or "").strip()
    espera = segundos_de_bloqueio(request, login)
    if espera:
        return Tentativa(None, espera)
    usuario = None
    if login and senha:
        usuario = authenticate(request, username=username_para(login, request), password=senha)
    if usuario is None:
        return Tentativa(None, registrar_falha(request, login, origem=origem))
    registrar_acerto(request, login)
    return Tentativa(usuario)


# ----------------------------------------------------------------------
# O que chega por fora das telas da casa
# ----------------------------------------------------------------------
def _ao_falhar(sender, credentials=None, request=None, **kwargs):
    if request is None or getattr(request, "_contas_freio_tratado", False):
        return
    credentials = credentials or {}
    login = credentials.get("username") or credentials.get("email") or credentials.get("login") or ""
    if not isinstance(login, str) or not login:
        return
    try:
        registrar_falha(request, login)
    except Exception:  # noqa: BLE001
        log.exception("Freio de login: erro ao contar a falha")


def ligar_sinais():
    from django.contrib.auth.signals import user_login_failed

    user_login_failed.connect(_ao_falhar, dispatch_uid="contas.freio.falha")
