"""O registro de cada cadastro: quem criou a conta, de onde e por qual caminho.

POR QUE EXISTE. Contas falsas chegam em lote, do mesmo lugar, com o mesmo
navegador. Sem saber de onde cada cadastro veio, não há como frear nem
como investigar depois. Aqui fica, para cada conta que nasce: o IP (e os
cabeçalhos crus de onde ele saiu), a região APROXIMADA tirada do IP
(cidade, estado e país -- nunca localização precisa, nada pedido ao
aparelho), o navegador, a data/hora e a origem (site, aplicativo, Google,
Apple, painel).

COMO É GRAVADO. Três caminhos criam conta: o formulário /registrar/, a
API do aplicativo e o Google/Apple (allauth). Em vez de três gravações,
uma só: o `post_save` do `User` (core/signals.py) chama `registrar`, que
lê a requisição atual guardada por `RequisicaoAtualMiddleware` num
contextvar. Sem requisição (comando, shell, teste sem cliente) não há o
que registrar, e nada é gravado.

NUNCA DERRUBA O CADASTRO. A gravação roda num savepoint e qualquer erro
dela é engolido e logado: um defeito aqui não pode impedir uma pessoa de
criar conta.

A REGIÃO VEM DEPOIS. A consulta ao serviço de geo-IP só acontece depois
do commit (transaction.on_commit), numa thread, com tempo-limite curto,
e pula IP privado. Desligada nos testes (GEOIP_ATIVO). O que ficou sem
região (serviço fora, limite do dia) o comando `preencher_regioes`
completa depois.

QUAL CABEÇALHO TRAZ O IP REAL. No Render, o proxy deles grava o IP do
cliente em X-Forwarded-For (o primeiro da lista). Com o Cloudflare na
frente (ver docs/CLOUDFLARE_INTERNO.md), o IP real vem em
CF-Connecting-IP e o X-Forwarded-For passa a ter o do Cloudflare no fim.
Por isso a ordem abaixo prefere CF-Connecting-IP quando existe, e
IP_REAL_CABECALHO força um cabeçalho específico. Na dúvida, a cadeia
inteira fica guardada em `cabecalhos_ip`.
"""

from __future__ import annotations

import contextvars
import ipaddress
import logging
import threading
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

log = logging.getLogger(__name__)

_requisicao = contextvars.ContextVar("requisicao_atual", default=None)

#: Onde procurar o IP do cliente, em ordem. O primeiro válido vence.
CABECALHOS_IP = (
    "HTTP_CF_CONNECTING_IP",
    "HTTP_TRUE_CLIENT_IP",
    "HTTP_X_REAL_IP",
    "HTTP_X_FORWARDED_FOR",
    "REMOTE_ADDR",
)


class RequisicaoAtualMiddleware:
    """Guarda a requisição em curso para quem não a recebe (o post_save)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        marca = _requisicao.set(request)
        try:
            return self.get_response(request)
        finally:
            _requisicao.reset(marca)


def requisicao_atual():
    return _requisicao.get()


# ----------------------------------------------------------------------
# De onde veio
# ----------------------------------------------------------------------

def _ip_valido(texto):
    texto = (texto or "").strip()
    if not texto:
        return None
    try:
        return str(ipaddress.ip_address(texto))
    except ValueError:
        return None


def ip_privado(ip) -> bool:
    try:
        endereco = ipaddress.ip_address(ip)
    except (TypeError, ValueError):
        return True
    return endereco.is_private or endereco.is_loopback or endereco.is_link_local or endereco.is_reserved or endereco.is_unspecified


def ip_da_requisicao(request):
    """(ip do cliente ou None, a cadeia crua dos cabeçalhos de IP)."""
    meta = getattr(request, "META", {}) or {}
    partes = []
    for chave in CABECALHOS_IP:
        valor = meta.get(chave)
        if valor:
            partes.append(f"{chave[5:] if chave.startswith('HTTP_') else chave}={str(valor)[:200]}")
    cadeia = " | ".join(partes)

    forcado = (getattr(settings, "IP_REAL_CABECALHO", "") or "").strip()
    ordem = (forcado,) + CABECALHOS_IP if forcado else CABECALHOS_IP
    for chave in ordem:
        valor = meta.get(chave)
        if not valor:
            continue
        # X-Forwarded-For: "cliente, proxy1, proxy2" -- o cliente é o primeiro
        ip = _ip_valido(str(valor).split(",", 1)[0])
        if ip:
            return ip, cadeia
    return None, cadeia


def origem_do_cadastro(request) -> str:
    """Pelo caminho da URL (e pelo host): site, app, google, apple, painel ou outro."""
    from .models import RegistroCadastro

    caminho = (getattr(request, "path", "") or "").lower()
    host = ""
    try:
        host = request.get_host().split(":", 1)[0].lower()
    except Exception:  # noqa: BLE001 -- host inválido: não importa aqui
        pass
    if getattr(request, "is_interno", False) or host.startswith("interno.") or caminho.startswith("/system/"):
        return RegistroCadastro.Origem.PAINEL
    if caminho.startswith("/api/"):
        return RegistroCadastro.Origem.APP
    if "/accounts/google" in caminho:
        return RegistroCadastro.Origem.GOOGLE
    if "/accounts/apple" in caminho:
        return RegistroCadastro.Origem.APPLE
    if caminho.startswith("/registrar") or caminho.startswith("/accounts/signup"):
        return RegistroCadastro.Origem.SITE
    return RegistroCadastro.Origem.OUTRO


# ----------------------------------------------------------------------
# Gravar
# ----------------------------------------------------------------------

def registrar(usuario, request=None):
    """Grava o registro do cadastro de `usuario`; nunca levanta exceção."""
    request = request or requisicao_atual()
    if request is None:
        return None
    try:
        from .models import RegistroCadastro

        ip, cadeia = ip_da_requisicao(request)
        with transaction.atomic():
            registro = RegistroCadastro.objects.create(
                usuario=usuario,
                username=(usuario.username or "")[:150],
                email=(usuario.email or "")[:254],
                ip=ip,
                cabecalhos_ip=cadeia[:2000],
                navegador=(request.META.get("HTTP_USER_AGENT") or "")[:512],
                origem=origem_do_cadastro(request),
            )
    except Exception:  # noqa: BLE001 -- o cadastro vale mais que o registro
        log.exception("O registro do cadastro de %s não foi gravado.", getattr(usuario, "username", "?"))
        return None

    if ip and not ip_privado(ip) and getattr(settings, "GEOIP_ATIVO", False):
        registro_id = registro.pk
        transaction.on_commit(lambda: _em_segundo_plano(registro_id))
    return registro


def _em_segundo_plano(registro_id):
    threading.Thread(target=preencher_regiao, args=(registro_id,), daemon=True, name=f"geoip-{registro_id}").start()


# ----------------------------------------------------------------------
# A região aproximada, pelo IP
# ----------------------------------------------------------------------

def consultar_regiao(ip):
    """{"cidade", "estado", "pais"} do IP, pelo serviço configurado; {} se não deu."""
    import requests

    url = (getattr(settings, "GEOIP_URL", "") or "").format(ip=ip)
    if not url:
        return {}
    try:
        resposta = requests.get(
            url,
            timeout=getattr(settings, "GEOIP_TIMEOUT", 3),
            headers={"User-Agent": "lazersport-site/1.0 (geo-ip aproximado para antifraude)"},
        )
        resposta.raise_for_status()
        dados = resposta.json()
    except Exception as erro:  # noqa: BLE001
        log.warning("geo-IP de %s não respondeu: %r", ip, erro)
        return {}
    if not isinstance(dados, dict) or dados.get("error") or dados.get("status") == "fail":
        return {}
    # ipapi.co: city/region/country_name; ip-api.com: city/regionName/country; ipinfo: city/region/country
    return {
        "cidade": str(dados.get("city") or "")[:100],
        "estado": str(dados.get("region") or dados.get("regionName") or dados.get("region_name") or "")[:100],
        "pais": str(dados.get("country_name") or dados.get("country") or "")[:100],
    }


def preencher_regiao(registro_id):
    """Consulta a região do registro e grava; roda fora da requisição."""
    from .models import RegistroCadastro

    try:
        registro = RegistroCadastro.objects.filter(pk=registro_id).only("ip").first()
        if registro is None or not registro.ip or ip_privado(registro.ip):
            return False
        regiao = consultar_regiao(registro.ip)
        if not regiao:
            return False
        RegistroCadastro.objects.filter(pk=registro_id).update(regiao_conferida=True, **regiao)
        return True
    except Exception:  # noqa: BLE001
        log.exception("A região do registro %s não foi preenchida.", registro_id)
        return False
    finally:
        # a thread tem a própria conexão: não pode ficar aberta
        if threading.current_thread() is not threading.main_thread():
            connection.close()


# ----------------------------------------------------------------------
# O freio: cadastros demais do mesmo IP
# ----------------------------------------------------------------------

def cadastros_recentes_do_ip(ip, horas=None) -> int:
    from .models import RegistroCadastro

    if not ip:
        return 0
    horas = horas if horas is not None else getattr(settings, "CADASTRO_JANELA_HORAS", 24)
    desde = timezone.now() - timedelta(hours=horas)
    return RegistroCadastro.objects.filter(ip=ip, criacao__gte=desde).count()


def limite_de_cadastros_estourado(request) -> bool:
    """Este IP já criou contas demais na janela? (IP privado nunca estoura.)"""
    limite = getattr(settings, "CADASTRO_LIMITE_POR_IP", 0)
    if not limite:
        return False
    ip, _ = ip_da_requisicao(request)
    if not ip or ip_privado(ip):
        return False
    try:
        return cadastros_recentes_do_ip(ip) >= limite
    except Exception:  # noqa: BLE001 -- sem a tabela (antes da migração), não freia
        log.exception("Não deu para contar os cadastros do IP %s.", ip)
        return False


MENSAGEM_LIMITE = (
    "Já foram criadas várias contas a partir da sua conexão nas últimas horas. "
    "Tente de novo mais tarde ou fale com a gente pelo WhatsApp."
)
