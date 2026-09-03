# core/context_processors.py
#
# Refatoração de performance
# ==========================
# Problema original: os processors globais (categorias_globais,
# estabelecimentos_globais, clientes_rodape) rodavam em TODA request,
# inclusive de visitante anônimo e de bot. Como o base.html usa os três,
# cada pageview do site batia no Supabase 3x só pra montar header e rodapé.
#
# Duas mudanças aqui:
#
# 1) CACHE. Esses três dados mudam raramente (categoria, estabelecimento,
#    logo de cliente). Ficam em cache por 10 min. Um bot varrendo 5.000
#    URLs passa a gerar ~3 queries no total em vez de ~15.000.
#
# 2) LAZY. Os processors de usuário logado (carrinho, pedidos, manutenção,
#    alertas de admin) agora devolvem SimpleLazyObject: a query só dispara
#    se o template realmente imprimir a variável. Antes, .count() e
#    .exists() executavam sempre, mesmo em página que não mostra o badge.
#
# Também juntei queries duplicadas:
#   - manutencao_notificacao fazia 2 counts -> agora 1 query com aggregate
#   - pedidos_ativos_context fazia .exists() + .count() -> agora 1 count
#
# IMPORTANTE: pra invalidar o cache depois de mexer em categoria/
# estabelecimento/cliente no admin, chame limpar_cache_global() no save()
# do model (ou espere os 10 min).

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.templatetags.static import static
from django.urls import reverse
from django.utils.functional import SimpleLazyObject

from .models import (
    Carrinho,
    CategoriasBrinquedos,
    Estabelecimentos,
    Manutencao,
    Pedido,
)

# 10 minutos. Aumente à vontade se o conteúdo do header/rodapé é estável.
TTL_GLOBAL = 60 * 10

CHAVE_CATEGORIAS = "ctx:categorias_header:v1"
CHAVE_ESTABELECIMENTOS = "ctx:estabelecimentos_globais:v1"
CHAVE_CLIENTES_RODAPE = "ctx:clientes_rodape:v1"

_CATEGORIAS_OCULTAS = (
    "competitivos",
    "kids",
    "famosos",
    "espaço esportivo kids",
    "espaço kids play",
)


def limpar_cache_global():
    """Chame isto no save()/delete() de CategoriasBrinquedos,
    Estabelecimentos e clientes pra o header/rodapé atualizar na hora."""
    cache.delete_many([
        CHAVE_CATEGORIAS,
        CHAVE_ESTABELECIMENTOS,
        CHAVE_CLIENTES_RODAPE,
    ])


# ============================================================
# GLOBAIS (todo visitante) -- servidos do cache
# ============================================================

def categorias_globais(request):
    def _buscar():
        dados = cache.get(CHAVE_CATEGORIAS)
        if dados is None:
            filtro = Q()
            for termo in _CATEGORIAS_OCULTAS:
                filtro |= Q(nome_categoria__icontains=termo)

            # list() força a avaliação: o cache precisa guardar os
            # objetos, não o QuerySet preguiçoso.
            dados = list(
                CategoriasBrinquedos.objects
                .exclude(filtro)
                .only("id", "nome_categoria", "imagem_categoria")
                .order_by("nome_categoria")
            )
            cache.set(CHAVE_CATEGORIAS, dados, TTL_GLOBAL)
        return dados

    return {"categorias_header": SimpleLazyObject(_buscar)}


def estabelecimentos_globais(request):
    def _buscar():
        dados = cache.get(CHAVE_ESTABELECIMENTOS)
        if dados is None:
            dados = list(Estabelecimentos.objects.all())
            cache.set(CHAVE_ESTABELECIMENTOS, dados, TTL_GLOBAL)
        return dados

    return {"estabelecimentos_globais": SimpleLazyObject(_buscar)}


def clientes_rodape(request):
    """Seis primeiros clientes ativos com logo, para o base.html.

    Sai do cadastro do painel, como o mapa: quem entra na faixa do rodapé
    é o mesmo cliente que a fábrica atende, e não uma lista à parte que
    alguém precisava lembrar de manter.
    """
    def _buscar():
        from sistema_interno.models import Cliente

        dados = cache.get(CHAVE_CLIENTES_RODAPE)
        if dados is None:
            dados = list(
                Cliente.objects
                .filter(ativo=True)
                .exclude(logo__isnull=True)
                .exclude(logo="")
                .only("id", "nome_cliente", "logo", "criacao")
                .order_by("-criacao", "-id")[:6]
            )
            cache.set(CHAVE_CLIENTES_RODAPE, dados, TTL_GLOBAL)
        return dados

    return {"clientes_rodape": SimpleLazyObject(_buscar)}


# ============================================================
# POR USUÁRIO -- lazy, só consulta se o template usar
# ============================================================

def manutencao_notificacao(request):
    # Alertas pessoais do cliente não pertencem ao painel da fábrica.
    if getattr(request, "is_interno", False) or not request.user.is_authenticated:
        return {}

    vazio = {
        "manutencao_pendente": 0,
        "manutencao_andamento": 0,
        "manutencao_abertas": 0,
        "tem_manutencao": False,
    }

    def _contar():
        perfil = getattr(request.user, "perfil", None)
        if not perfil:
            return vazio

        # Uma query só, em vez de dois .count() separados.
        agg = Manutencao.objects.filter(usuario=perfil).aggregate(
            pendentes=Count("id", filter=Q(status="P")),
            andamento=Count("id", filter=Q(status="A")),
        )
        pendentes = agg["pendentes"] or 0
        andamento = agg["andamento"] or 0
        total = pendentes + andamento

        return {
            "manutencao_pendente": pendentes,
            "manutencao_andamento": andamento,
            "manutencao_abertas": total,
            "tem_manutencao": total > 0,
        }

    dados = SimpleLazyObject(_contar)
    return {chave: SimpleLazyObject(lambda c=chave: dados[c]) for chave in vazio}


def equipe_context(request):
    """Diz ao site se quem está olhando trabalha aqui.

    O site usa isto para duas coisas opostas e complementares: esconder o
    que é do cliente (carrinho, lista de desejos, pedidos -- ver
    `LojaSomenteDeClienteMiddleware`, que é quem de fato barra) e mostrar
    o caminho de volta para o painel. Um sem o outro deixaria a pessoa
    numa loja onde nada funciona e sem porta de saída.
    """
    from .middleware import e_da_equipe
    from .views_redirects import _origem_interna

    if getattr(request, "is_interno", False):
        return {}

    usuario = getattr(request, "user", None)
    return {
        "usuario_da_equipe": SimpleLazyObject(lambda: e_da_equipe(usuario)),
        # O painel mora em outro subdomínio, então `{% url %}` não o
        # alcança: o endereço é montado a partir do host da vez, que é a
        # mesma conta que os redirecionamentos antigos já faziam.
        "ls_url_painel": SimpleLazyObject(lambda: _origem_interna(request) + "/"),
    }


def carrinho_context(request):
    if not request.user.is_authenticated:
        return {
            "carrinho_total_itens": 0,
            "mostrar_float_carrinho": False,
        }

    def _total():
        perfil = getattr(request.user, "perfil", None)
        if not perfil:
            return 0

        carrinho = (
            Carrinho.objects
            .filter(cliente=perfil)
            .only("id")
            .first()
        )
        if not carrinho:
            return 0

        return carrinho.itens.aggregate(
            total=Sum("quantidade")
        )["total"] or 0

    total = SimpleLazyObject(_total)

    return {
        "carrinho_total_itens": total,
        "mostrar_float_carrinho": SimpleLazyObject(lambda: total > 0),
    }


def pedidos_ativos_context(request):
    if not request.user.is_authenticated:
        return {}

    def _contar():
        perfil = getattr(request.user, "perfil", None)
        if not perfil:
            return 0

        # Antes: .exists() + .count() = 2 queries. Agora 1.
        return (
            Pedido.objects
            .filter(cliente=perfil)
            .exclude(status__in=["cancelado", "finalizado"])
            .count()
        )

    total = SimpleLazyObject(_contar)

    return {
        "tem_pedidos_ativos": SimpleLazyObject(lambda: total > 0),
        "total_pedidos_ativos": total,
    }


def admin_alertas_context(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return {}

    def _pedidos():
        return Pedido.objects.filter(
            status__in=[
                "criado",
                "aguardando_pagamento",
                "pago",
                "em_preparacao",
            ]
        ).count()

    def _manutencoes():
        return Manutencao.objects.filter(status__in=["P", "A"]).count()

    pedidos = SimpleLazyObject(_pedidos)
    manutencoes = SimpleLazyObject(_manutencoes)

    return {
        "pedidos_alerta": pedidos,
        "tem_pedidos_alerta": SimpleLazyObject(lambda: pedidos > 0),
        "manutencoes_alerta": manutencoes,
        "tem_manutencoes_alerta": SimpleLazyObject(lambda: manutencoes > 0),
    }

# ============================================================
# APP ANDROID -- sem banco, só configuração
# ============================================================

# Onde o APK é procurado quando nenhuma URL é configurada: basta commitar
# o arquivo em core/static/app/ para o download passar a existir, sem CDN
# nem variável de ambiente.
#
# É static, e não media, de propósito. Em produção o Django só serve
# /media/ com DEBUG ligado, e os uploads reais vão para o Cloudinary --
# um APK solto em MEDIA_ROOT daria 404 no site publicado. O WhiteNoise
# serve /static/ em produção, e o arquivo viaja junto com o repositório.
APK_NO_STATIC = "app/lazer-sport.apk"
CHAVE_APK_LOCAL = "app:apk-estatico:v1"


def _apk_publicado_no_static():
    """URL do APK versionado em static/, ou vazio se não houver arquivo.

    O resultado fica em cache: sem isso seria uma varredura dos diretórios
    de estáticos em toda página do site, inclusive nas de quem nem vai
    chegar a ver o rodapé.
    """
    url = cache.get(CHAVE_APK_LOCAL)
    if url is not None:
        return url

    try:
        existe = finders.find(APK_NO_STATIC) is not None
    except Exception:  # noqa: BLE001 - rodapé nunca derruba a página
        existe = False

    url = static(APK_NO_STATIC) if existe else ""
    cache.set(CHAVE_APK_LOCAL, url, 300)
    return url


def app_android(request):
    """Alimenta a caixa de download do app no rodapé.

    Não toca no banco. A escolha de o que mostrar — baixar, "em breve para
    iPhone" ou "abra no Android" — é feita no navegador, e não aqui: a
    vitrine do site é cacheada, e decidir por User-Agent no servidor
    guardaria a versão de um aparelho e serviria para todos os outros.
    """
    play = getattr(settings, "APP_ANDROID_PLAY_URL", "")
    apk = getattr(settings, "APP_ANDROID_APK_URL", "") or _apk_publicado_no_static()

    return {
        "app_android_play_url": play,
        "app_android_apk_url": apk,
        "app_android_versao": getattr(settings, "APP_ANDROID_VERSAO", ""),
        "app_android_disponivel": bool(play or apk),
    }


# ============================================================
# AVISO DE PAGAMENTO APROVADO -- só URLs, sem banco
# ============================================================

def confirmacao_pagamento(request):
    """Entrega ao JS os endereços dos endpoints de confirmação.

    Não consulta nada: quem pergunta se existe pedido pendente de aviso é o
    próprio JS, uma vez por página, para não somar uma query a cada
    pageview de quem não comprou nada.
    """
    # O subdomínio interno usa outro URLconf e não possui endpoints de
    # checkout. Tentar resolvê-los ali derrubaria qualquer tela da fábrica.
    if getattr(request, "is_interno", False) or not request.user.is_authenticated:
        return {}

    return {
        "ls_confirmacao_urls": {
            "consulta": reverse("confirmacoes_pendentes"),
            "baixa": reverse("marcar_confirmacao_vista"),
        }
    }


def favoritos_context(request):
    """Contador da lista de desejos no cabeçalho.

    Visitante sem cookie ainda não marcou nada -- e nesse caso não vale
    gastar consulta nem criar chave de dispositivo só para exibir zero.
    """
    from .favoritos import COOKIE_DISPOSITIVO, meus_favoritos
    from .models import Favorito

    logado = request.user.is_authenticated
    tem_cookie = bool(request.COOKIES.get(COOKIE_DISPOSITIVO))

    if not logado and not tem_cookie:
        return {"total_lista_desejos": 0, "tem_lista_desejos": False}

    def _contar():
        return meus_favoritos(request, Favorito.Tipo.DESEJO).count()

    total = SimpleLazyObject(_contar)

    return {
        "total_lista_desejos": total,
        "tem_lista_desejos": SimpleLazyObject(lambda: total > 0),
    }
