"""O ESCUDO DOS JOGOS: os jogos são para quem joga, não para robôs.

O QUE ELE BARRA
  * ROBÔS DE IA (GPTBot, ClaudeBot, CCBot, PerplexityBot, Bytespider...): não
    entram em nada de /jogos/ nem nos arquivos dos jogos da casa. O robots.txt
    já pede isso a eles; quem não obedece leva 403 aqui.
  * PROGRAMAS DE CÓPIA (curl, wget, python-requests, Scrapy, navegador sem
    tela -- HeadlessChrome): não abrem o reprodutor, não pedem o passe e não
    baixam os arquivos dos jogos.
  * QUEM CAI NA ARMADILHA: a biblioteca tem um link escondido (/jogos/_acervo/)
    que pessoa nenhuma vê nem clica, e que o robots.txt proíbe. Quem entra nele
    é robô que lê o código da página atrás de arquivos: fica marcado por 6
    horas (pelo IP e pelo navegador juntos) e não abre jogo nenhum.

O PASSE (para os jogos de console)
  O endereço dos arquivos do jogo NÃO vai na página. O reprodutor pede um
  passe (/jogos/<jogo>/passe/) e, para ganhar, o navegador resolve uma "prova
  de trabalho": achar um número que, junto com o desafio assinado pelo site,
  dá um SHA-256 começando com N bits zero. Para quem joga, uma fração de
  segundo durante a abertura; para quem tenta abrir milhares de jogos, CPU
  cara -- e a dificuldade sobe sozinha para quem abre jogo demais em pouco
  tempo (e acima do limite, espera). O passe também recusa navegador
  controlado por programa (navigator.webdriver), pedido de outro site e
  desafio repetido.

O QUE ELE NÃO PROMETE
  O que o navegador de uma pessoa baixa, a pessoa consegue guardar: nenhum
  site impede isso. O escudo tira do caminho o robô e a cópia em massa, que é
  o que dá para impedir.

A loja e os buscadores (Google, Bing) não mudam: a biblioteca e as páginas
dos jogos continuam abertas para eles; só o reprodutor e o passe ficam de
fora (o reprodutor já não é indexado).
"""

import hashlib
import hmac
import json
import secrets
import time

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View

#: Robôs de IA (o nome que vai no User-Agent), em minúsculas.
ROBOS_DE_IA = (
    "gptbot", "chatgpt-user", "oai-searchbot", "claudebot", "claude-user", "claude-searchbot", "claude-web",
    "anthropic-ai", "ccbot", "perplexitybot", "perplexity-user", "bytespider", "amazonbot", "meta-externalagent",
    "meta-externalfetcher", "facebookbot", "diffbot", "imagesiftbot", "omgilibot", "omgili", "cohere-ai",
    "cohere-training-data-crawler", "youbot", "timpibot", "ai2bot", "duckassistbot", "mistralai-user",
    "google-cloudvertexbot", "googleother", "pangubot", "kangaroo bot", "img2dataset", "webzio",
    "iaskspider", "icc-crawler", "velenpublicwebcrawler", "brightbot", "crawlspace", "firecrawlagent",
    "novellum", "quillbot", "sidetrade", "tiktokspider", "factset_spyderbot", "aihitbot", "cotoyogi",
)
#: Os nomes do robots.txt (alguns só existem lá: Google-Extended e Applebot-Extended
#: dizem "não use para treinar IA", sem mexer na busca).
ROBOS_DE_IA_NO_ROBOTS = (
    "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "Claude-SearchBot", "Claude-Web",
    "anthropic-ai", "CCBot", "PerplexityBot", "Perplexity-User", "Bytespider", "Amazonbot", "meta-externalagent",
    "meta-externalfetcher", "FacebookBot", "Diffbot", "ImagesiftBot", "Omgilibot", "cohere-ai",
    "cohere-training-data-crawler", "YouBot", "Timpibot", "AI2Bot", "DuckAssistBot", "MistralAI-User",
    "Google-Extended", "Applebot-Extended", "Google-CloudVertexBot", "GoogleOther", "PanguBot",
    "img2dataset", "FirecrawlAgent", "TikTokSpider",
)
#: Programas que baixam páginas sem ser um navegador de verdade.
FERRAMENTAS = (
    "curl/", "wget/", "python-requests", "python-urllib", "python-httpx", "aiohttp", "httpx/", "scrapy",
    "go-http-client", "libwww-perl", "node-fetch", "axios/", "got (", "java/", "okhttp", "headlesschrome",
    "phantomjs", "puppeteer", "playwright", "selenium", "httrack", "wget ", "winhttp", "postmanruntime",
    "insomnia", "colly", "zgrab", "masscan", "nikto", "sqlmap",
)
#: Buscadores: não ficam marcados pela armadilha (eles respeitam o robots.txt; se
#: um passar por ela, foi engano, e a busca do site não pode pagar por isso).
BUSCADORES = ("googlebot", "bingbot", "duckduckbot", "yandexbot", "applebot", "baiduspider")

ARMADILHA = "/jogos/_acervo/"
#: Onde o escudo olha: o app dos jogos e os arquivos dos jogos da casa.
PREFIXOS = ("/jogos/", "/static/site/arena/jogos/")
TEMPO_DA_MARCA = 6 * 3600

#: O passe: bits zero do SHA-256 (16 = ~65 mil contas, uma fração de segundo no celular)
BITS = 16
VALIDADE = 15 * 60
JANELA = 10 * 60
#: Passes por IP a cada 10 minutos: a partir de cada degrau a conta fica mais difícil
#: (+2 bits = 4 vezes mais conta); acima do teto, espera.
DEGRAUS = ((10, 2), (25, 4), (40, 6))
TETO = 60

CABECALHO_NOAI = "noai, noimageai"


def _ua(request):
    return (request.META.get("HTTP_USER_AGENT") or "")[:512]


def e_robo_de_ia(ua):
    ua = (ua or "").lower()
    return any(nome in ua for nome in ROBOS_DE_IA)


def e_ferramenta(ua):
    ua = (ua or "").lower()
    return any(nome in ua for nome in FERRAMENTAS)


def e_buscador(ua):
    ua = (ua or "").lower()
    return any(nome in ua for nome in BUSCADORES)


def _ip(request):
    from .registro_cadastro import ip_da_requisicao

    return ip_da_requisicao(request)[0] or "sem-ip"


def _resumo(*partes):
    return hashlib.sha256("|".join(partes).encode("utf-8", "replace")).hexdigest()[:32]


def _impressao(request):
    """Quem está pedindo: o IP e o navegador juntos (num IP de operadora, pessoas e robôs se misturam)."""
    return _resumo(_ip(request), _ua(request))


def _chave():
    return hashlib.sha256(("escudo-dos-jogos|" + settings.SECRET_KEY).encode()).digest()


# ---------------------------------------------------------------- a marca da armadilha

def marcar(request, motivo="armadilha"):
    cache.set("escudo:robo:" + _impressao(request), motivo, TEMPO_DA_MARCA)


def marcado(request):
    return cache.get("escudo:robo:" + _impressao(request)) is not None


def _recusa(texto, status=403):
    resposta = HttpResponse(texto, status=status, content_type="text/plain; charset=utf-8")
    resposta["Cache-Control"] = "no-store"
    resposta["X-Robots-Tag"] = "noindex, nofollow, " + CABECALHO_NOAI
    return resposta


def _so_para_quem_joga(caminho):
    """O reprodutor, o passe, os arquivos e as partidas: o que só um navegador de verdade pede."""
    if caminho.startswith("/static/"):
        return True
    return (caminho.endswith("/passe/") or "/emulador/" in caminho or caminho.startswith(("/jogos/abriu/", "/jogos/partida/")))


class EscudoDosJogosMiddleware:
    """Robôs de IA, programas de cópia e quem caiu na armadilha ficam fora dos jogos.

    Vem antes do WhiteNoise: os arquivos dos jogos da casa (em /static/) também
    passam por aqui. O resto do site nem é olhado.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        caminho = request.path_info or "/"
        if not caminho.startswith(PREFIXOS):
            return self.get_response(request)
        ua = _ua(request)
        if e_robo_de_ia(ua):
            return _recusa("Os jogos da Lazer & Sport não estão abertos para robôs de IA.")
        if _so_para_quem_joga(caminho) and e_ferramenta(ua):
            return _recusa("Os jogos abrem no navegador, para quem joga.")
        if caminho != ARMADILHA and marcado(request):
            return _recusa("Acesso aos jogos suspenso por algumas horas: este acesso se comportou como um robô.")
        resposta = self.get_response(request)
        if caminho.startswith("/jogos/"):
            atual = resposta.get("X-Robots-Tag", "")
            if "noai" not in atual:
                resposta["X-Robots-Tag"] = (atual + ", " if atual else "") + CABECALHO_NOAI
        return resposta


class ArmadilhaView(View):
    """O link que só robô segue (escondido na biblioteca e proibido no robots.txt)."""

    def get(self, request):
        pre_carga = (request.META.get("HTTP_SEC_PURPOSE", "") + request.META.get("HTTP_PURPOSE", "")).lower()
        if "prefetch" not in pre_carga and not e_buscador(_ua(request)):
            marcar(request)
        resposta = HttpResponse("<!doctype html><title>Página não encontrada</title><p>Página não encontrada.</p>",
                                status=404, content_type="text/html; charset=utf-8")
        resposta["X-Robots-Tag"] = "noindex, nofollow"
        resposta["Cache-Control"] = "no-store"
        return resposta

    head = get
    post = get


# ---------------------------------------------------------------- o passe

def _contar(request):
    """Quantos passes este IP pediu nesta janela de 10 minutos (e conta mais um)."""
    chave = "escudo:passes:%s:%d" % (_resumo(_ip(request)), int(time.time() // JANELA))
    if cache.add(chave, 1, JANELA + 60):
        return 1
    try:
        return cache.incr(chave)
    except ValueError:
        cache.set(chave, 1, JANELA + 60)
        return 1


def _vezes(request):
    chave = "escudo:passes:%s:%d" % (_resumo(_ip(request)), int(time.time() // JANELA))
    return int(cache.get(chave) or 0)


def bits_para(request):
    vezes = _vezes(request)
    return BITS + max([mais for limite, mais in DEGRAUS if vezes >= limite], default=0)


def _assinar(slug, quando, sorteio, bits, ua):
    texto = f"{slug}|{quando}|{sorteio}|{bits}|{_resumo(ua)}"
    return hmac.new(_chave(), texto.encode(), hashlib.sha256).hexdigest()[:24]


def novo_desafio(request, slug):
    """O desafio que vai na página do reprodutor (e no 409 do passe): "quando.sorteio.bits.assinatura"."""
    quando = int(time.time())
    sorteio = secrets.token_hex(8)
    bits = bits_para(request)
    return {"desafio": f"{quando}.{sorteio}.{bits}.{_assinar(slug, quando, sorteio, bits, _ua(request))}", "bits": bits}


def zeros_do_comeco(sorteio, nonce):
    """Quantos bits zero abrem o SHA-256 de "sorteio:nonce" (até 32)."""
    primeiro = int.from_bytes(hashlib.sha256(f"{sorteio}:{nonce}".encode()).digest()[:4], "big")
    return 32 - primeiro.bit_length()


def conferir(request, slug, desafio, nonce):
    """'' quando o desafio é bom e a conta fecha; senão, o motivo."""
    try:
        quando, sorteio, bits, assinatura = str(desafio).split(".")
        quando, bits = int(quando), int(bits)
    except (TypeError, ValueError):
        return "desafio inválido"
    if not hmac.compare_digest(assinatura, _assinar(slug, quando, sorteio, bits, _ua(request))):
        return "desafio inválido"
    if not 0 <= time.time() - quando <= VALIDADE:
        return "desafio vencido"
    nonce = str(nonce)
    if not nonce.isdigit() or len(nonce) > 12:
        return "conta errada"
    if zeros_do_comeco(sorteio, nonce) < bits:
        return "conta errada"
    if not cache.add("escudo:usado:" + sorteio, 1, VALIDADE + 60):
        return "desafio já usado"
    return ""


def config_publica(config, request, slug):
    """O que a página do reprodutor leva: tudo, menos de onde baixar (isso vem com o passe)."""
    publica = dict(config)
    publica["arquivos"] = [{chave: valor for chave, valor in item.items() if chave != "partes"} for item in config["arquivos"]]
    from django.urls import reverse

    publica["passe"] = {"url": reverse("jogo_passe", args=[slug]), **novo_desafio(request, slug)}
    return publica


def _mesma_origem(request):
    site = request.META.get("HTTP_SEC_FETCH_SITE")
    if site and site not in ("same-origin", "none"):
        return False
    origem = request.META.get("HTTP_ORIGIN")
    if origem and origem != f"{request.scheme}://{request.get_host()}":
        return False
    return True


@method_decorator(csrf_exempt, name="dispatch")
class PasseDoJogoView(View):
    """POST {desafio, nonce, sinais}: a conta certa ganha a lista de onde baixar o jogo."""

    def post(self, request, slug):
        from .views_jogos import _jogo_no_emulador, config_do_emulador

        jogo = _jogo_no_emulador(slug, equipe=request.user.is_staff)
        if marcado(request):
            return self._erro("Acesso aos jogos suspenso por algumas horas.", 403)
        if not _mesma_origem(request):
            return self._erro("Pedido de fora do site.", 403)
        try:
            corpo = json.loads(request.body or b"{}")
        except ValueError:
            return self._erro("Pedido inválido.", 400)
        sinais = corpo.get("sinais") if isinstance(corpo.get("sinais"), dict) else {}
        if sinais.get("webdriver") is True:
            return self._erro("Este navegador está sendo controlado por um programa. Abra o jogo num navegador comum.", 403)
        if not corpo.get("desafio"):
            return self._novo(request, slug, "")
        if _vezes(request) >= TETO:
            resposta = self._erro("Muitos jogos abertos em pouco tempo. Espere alguns minutos e tente de novo.", 429)
            resposta["Retry-After"] = str(JANELA)
            return resposta
        motivo = conferir(request, slug, corpo.get("desafio"), corpo.get("nonce"))
        if motivo:
            return self._novo(request, slug, motivo)
        _contar(request)
        arquivos = [{"nome": a["nome"], "partes": a["partes"], "tamanhos": a["tamanhos"]} for a in config_do_emulador(jogo)["arquivos"]]
        resposta = JsonResponse({"arquivos": arquivos})
        resposta["Cache-Control"] = "no-store"
        resposta["X-Robots-Tag"] = "noindex, nofollow, " + CABECALHO_NOAI
        return resposta

    def _novo(self, request, slug, motivo):
        resposta = JsonResponse({"motivo": motivo, **novo_desafio(request, slug)}, status=409)
        resposta["Cache-Control"] = "no-store"
        return resposta

    @staticmethod
    def _erro(texto, status):
        resposta = JsonResponse({"erro": texto}, status=status)
        resposta["Cache-Control"] = "no-store"
        return resposta
