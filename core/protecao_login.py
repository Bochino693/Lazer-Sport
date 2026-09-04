"""Freio de tentativas de senha.

O PROBLEMA. Todas as portas de entrada do sistema -- o login do site, o
login do painel, o /system/ do Django e a rota do aplicativo -- aceitavam
tentativas sem limite. Uma lista de senhas comuns rodando a noite inteira
não encontrava nada no caminho: nem espera, nem aviso, nem registro.
Senha boa resolve uma conta; o freio resolve todas.

COMO FUNCIONA. Toda falha de autenticação -- venha de onde vier, porque
quem avisa é o sinal ``user_login_failed`` do próprio Django -- soma um
ponto em dois contadores guardados no cache:

  * ``identidade + origem``: este computador tentando ESTA conta. É o
    contador que trava o ataque de força bruta, que por definição repete
    a mesma conta da mesma máquina;
  * ``origem``: este computador tentando QUALQUER conta. Pega a varredura
    que troca de usuário a cada tentativa.

Estourado o limite, as rotas de login recusam o POST por alguns minutos
(``ProtecaoDeLoginMiddleware``), com 429 e ``Retry-After``. Login que dá
certo apaga os contadores daquela identidade.

POR QUE NÃO TRAVAR A CONTA. Travar por identidade sozinha entrega uma
arma: qualquer um erraria a senha do gerente de propósito e o deixaria de
fora. Por isso o contador que bloqueia é o do PAR identidade+origem, e o
bloqueio se desfaz sozinho em minutos -- o suficiente para inviabilizar
milhares de tentativas, longe do suficiente para ser usado como sabotagem.

O QUE ESTE FREIO NÃO É. O cache padrão do projeto é de memória do
processo (``LocMemCache``), então cada worker conta o seu. Com quatro
workers, o limite real é até quatro vezes o configurado -- ainda três
ordens de grandeza abaixo do que uma força bruta precisa, mas é bom saber
que é assim. Com Redis configurado no cache, a contagem passa a ser única
sem mudar uma linha daqui.
"""

from __future__ import annotations

import hashlib

from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver


#: Janela de contagem, em segundos. Também é quanto dura o bloqueio.
JANELA = 600

#: Tentativas erradas desta origem contra a MESMA conta.
LIMITE_POR_CONTA = 10

#: Tentativas erradas desta origem contra QUALQUER conta.
LIMITE_POR_ORIGEM = 30

#: Caminhos que recebem senha. O middleware só olha POST para estes.
CAMINHOS_DE_LOGIN = (
    "/login/",            # site
    "/login/inner/",      # painel interno (subdomínio interno.)
    "/system/login/",     # administração do Django
    "/accounts/login/",   # allauth
    "/api/v1/auth/login/",
    "/api/v1/auth/registro/",
)


def origem_do_pedido(request) -> str:
    """De qual máquina veio o pedido, do jeito mais honesto possível.

    Atrás do proxy da hospedagem, ``REMOTE_ADDR`` é sempre o proxy -- e
    contar por ele juntaria o Brasil inteiro num balde só. O primeiro
    endereço do ``X-Forwarded-For`` é o do cliente; ele é falsificável,
    mas falsificá-lo só troca o próprio balde de quem tenta, e o contador
    por conta continua valendo.
    """
    encaminhado = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")
    primeiro = encaminhado[0].strip()
    return primeiro or (request.META.get("REMOTE_ADDR") or "desconhecido")


def _chave(*partes) -> str:
    crua = "|".join(str(parte or "") for parte in partes).lower()
    return "login-falhas:" + hashlib.sha256(crua.encode("utf-8")).hexdigest()[:32]


def _somar(chave: str) -> int:
    """Soma um ponto sem perder a validade da janela."""
    try:
        if cache.add(chave, 1, JANELA):
            return 1
        return cache.incr(chave)
    except ValueError:
        # A linha expirou entre o `add` e o `incr`. Recomeça a janela.
        cache.set(chave, 1, JANELA)
        return 1


def _contar(chave: str) -> int:
    return int(cache.get(chave) or 0)


def registrar_falha(request, identidade: str) -> None:
    origem = origem_do_pedido(request)
    _somar(_chave("conta", identidade, origem))
    _somar(_chave("origem", origem))


def limpar(request, identidade: str) -> None:
    """Acertou a senha: esta origem volta ao zero para esta conta."""
    origem = origem_do_pedido(request)
    cache.delete(_chave("conta", identidade, origem))


def espera_restante(request, identidade: str = "") -> int:
    """Segundos que faltam de castigo, ou 0 quando o caminho está livre.

    Devolve a janela cheia por simplicidade: o cache não conta quanto
    falta para expirar, e prometer menos do que o freio cumpre seria pior
    do que dizer o prazo inteiro.
    """
    if not getattr(settings, "PROTECAO_LOGIN_ATIVA", True):
        return 0

    origem = origem_do_pedido(request)

    if _contar(_chave("origem", origem)) >= LIMITE_POR_ORIGEM:
        return JANELA

    if identidade and _contar(
        _chave("conta", identidade, origem)
    ) >= LIMITE_POR_CONTA:
        return JANELA

    return 0


def bloqueado(request, identidade: str = "") -> bool:
    return espera_restante(request, identidade) > 0


# ----------------------------------------------------------------------
# Quem avisa é o Django, e por isso vale para TODA porta de entrada:
# o login do site, o do painel, o /system/, o allauth e a API do app.
# ----------------------------------------------------------------------
@receiver(user_login_failed)
def _anotar_falha(sender, credentials=None, request=None, **kwargs):
    if request is None:
        return
    credenciais = credentials or {}
    identidade = (
        credenciais.get("username")
        or credenciais.get("email")
        or credenciais.get("login")
        or ""
    )
    registrar_falha(request, str(identidade)[:150])


@receiver(user_logged_in)
def _limpar_ao_entrar(sender, request=None, user=None, **kwargs):
    if request is None or user is None:
        return
    limpar(request, user.get_username())
    if user.email:
        limpar(request, user.email)
