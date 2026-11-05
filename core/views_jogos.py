"""O simulador: a área dedicada às prévias dos jogos das máquinas.

Cada jogo tem o seu endereço (/jogos/<jogo>/) -- é o link para mandar a
alguém e o que o buscador lê -- e a página abre com ele em foco. Trocar
de jogo dentro da página não recarrega nada: o script troca o jogo e o
endereço juntos. Sem JavaScript, a página continua dizendo o que é cada
jogo e como se joga, e o seletor é uma lista de links.

Quem não entrou na conta joga uma partida de cada jogo; o fim de cada
partida chega em /jogos/partida/ e o ranking (do jogo e geral) sai de
/jogos/ranking/. As regras moram em `core/ranking.py`.
"""

import json

from django.db.models import Prefetch
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import View

from sistema_interno.templatetags.interno_extras import estatico

from . import arena, ranking
from .home_cache import get_cached_catalog_page
from .jogos_emulador import SISTEMAS, sistemas_ligados
from .models import ArquivoEmulador, Brinquedos, JogoCadastrado
from .views_arena import WHATSAPP


def jogos_cadastrados():
    """Os jogos que a equipe subiu pelo painel (ativos, com onde jogar), em ordem."""
    from .objetos_3d import tabela_pronta

    jogos = []
    if not tabela_pronta(JogoCadastrado):  # antes da migração, a lista sai sem eles
        return jogos
    lista = JogoCadastrado.objects.filter(ativo=True).order_by("ordem", "nome")
    if tabela_pronta(ArquivoEmulador):
        lista = lista.prefetch_related(Prefetch("arquivos_emulador", queryset=ArquivoEmulador.objects.only("id", "jogo_id", "papel")))
    else:
        # antes da migração dos jogos de console: só os que têm endereço ou .html,
        # sem tocar nas colunas novas
        lista = lista.exclude(endereco="", arquivo_html="").defer("sistema", "emulador_resumo")
    for jogo in lista:
        if not jogo.url_para_jogar:
            continue
        emulador = not (jogo.endereco or jogo.arquivo_html)
        jogos.append({
            "slug": jogo.slug,
            "titulo": jogo.nome,
            "chamada": jogo.chamada,
            "descricao": jogo.descricao,
            "comandos": jogo.comandos,
            "cor": jogo.cor,
            "capa": jogo.capa_url,
            "poster": jogo.poster_url,
            "jogar": jogo.url_para_jogar,
            "proporcao": jogo.proporcao,
            "apk": jogo.apk_url,
            "url": jogo.url,
            "externo": True,
            # a página do emulador é do próprio site (código nosso, sem .html
            # enviado): o quadro pode ter a mesma origem, para guardar o jogo salvo
            "emulador": emulador,
            "sistema": SISTEMAS[jogo.sistema].nome if emulador and jogo.sistema in SISTEMAS else "",
        })
    return jogos


def maquinas_dos_jogos():
    """Para cada jogo, a máquina do catálogo que é ele (pelo nome)."""
    maquinas = {}
    brinquedos = (
        Brinquedos.objects
        .filter(ativo=True)
        .only("id", "nome_brinquedo")
        .order_by("nome_brinquedo")
    )
    for brinquedo in brinquedos:
        slug = arena.jogo_da_maquina(brinquedo.nome_brinquedo)
        if not slug:
            continue
        maquinas.setdefault(slug, {
            "url": reverse("brinquedo_detalhe", args=[brinquedo.pk]) + "#bread",
            "nome": brinquedo.nome_brinquedo,
        })
    return maquinas


def _para_o_script(jogo):
    """O que o simulador precisa de um jogo, com os endereços já versionados."""
    controle = jogo["controle"]
    return {
        "slug": jogo["slug"],
        "titulo": jogo["titulo"],
        "maquina": jogo["maquina"],
        "chamada": jogo["chamada"],
        "descricao": jogo["descricao"],
        "comandos": jogo["comandos"],
        "cor": jogo["cor"],
        "capa": estatico(jogo["capa"]),
        "miniatura": estatico(jogo["miniatura"]),
        "poster": estatico(jogo["poster"]),
        "script": estatico(jogo["script"]),
        "variante": jogo.get("variante", ""),
        "url": jogo["url"],
        "maquinaUrl": jogo["maquina_url"],
        "maquinaNome": jogo["maquina_nome"],
        "gesto": controle["gesto"],
        "rotulo": controle["rotulo"],
        "icone": jogo["icone_gesto"],
        "passos": list(controle["passos"]),
        "naMaquina": controle["na_maquina"],
        "teclado": controle.get("teclado", ""),
        "botoes": [dict(b) for b in controle["botoes"]],
    }


def dados_do_simulador():
    """Os jogos da casa (com a máquina de cada um) e os cadastrados pelo painel.

    É igual para todo visitante, por isso vai para o cache público do
    catálogo (core/home_cache.py): muda quando um brinquedo ou um jogo
    cadastrado muda, pela versão do catálogo. O ranking e a posição de
    quem está olhando ficam de fora, resolvidos por requisição.
    """
    maquinas = maquinas_dos_jogos()
    jogos = []
    for jogo in arena.jogos_do_simulador(arena.JOGOS):
        maquina = maquinas.get(jogo["slug"])
        jogos.append({
            **jogo,
            "maquina_url": maquina["url"] if maquina else "",
            "maquina_nome": maquina["nome"] if maquina else "",
        })
    return {"jogos": jogos, "externos": jogos_cadastrados()}


@method_decorator(ensure_csrf_cookie, name="get")
class SimuladorView(View):
    def get(self, request, slug=None):
        dados = get_cached_catalog_page("jogos", (), dados_do_simulador)
        externos = dados["externos"]
        if slug is not None and slug not in arena.JOGOS_POR_SLUG:
            # um jogo que a equipe subiu pelo painel: a sua própria página
            cadastrado = next((j for j in externos if j["slug"] == slug), None)
            if cadastrado is None:
                raise Http404("Jogo não encontrado")
            return self.pagina_do_jogo_cadastrado(request, cadastrado, externos)

        jogos = dados["jogos"]
        atual = next((j for j in jogos if j["slug"] == slug), jogos[0])
        painel = ranking.painel(request, atual["slug"])
        voltar = atual["url"]
        salvos = ranking.salvos_agora(request)

        return render(request, "jogos.html", {
            "jogos": jogos,
            "jogos_externos": externos,
            "atual": atual,
            "jogo_escolhido": slug is not None,
            "jogos_script": [_para_o_script(j) for j in jogos],
            "whatsapp": WHATSAPP,
            "ranking": painel,
            "salvos": salvos,
            "jogador": {
                **painel,
                "partidaUrl": reverse("jogos_partida"),
                "rankingUrl": reverse("jogos_ranking"),
                "cadastroUrl": reverse("registrar"),
                "entrarUrl": reverse("login"),
                "voltar": voltar,
            },
        })

    def pagina_do_jogo_cadastrado(self, request, jogo, externos):
        """A página de um jogo que a equipe subiu: o jogo num quadro isolado."""
        return render(request, "jogo_cadastrado.html", {
            "jogo": jogo,
            "jogos": arena.jogos_do_simulador(arena.JOGOS),
            "jogos_externos": externos,
            "whatsapp": WHATSAPP,
        })


class PartidaJogoView(View):
    """O fim de uma partida: grava o recorde (ou a partida grátis do visitante)."""

    def post(self, request):
        try:
            dados = json.loads(request.body or b"{}")
        except ValueError:
            return JsonResponse({"erro": "corpo inválido"}, status=400)
        try:
            resposta = ranking.registrar_partida(request, dados.get("jogo"), dados.get("pontos"))
        except ranking.PartidaInvalida as erro:
            return JsonResponse({"erro": str(erro)}, status=400)
        return JsonResponse(resposta)


@method_decorator(never_cache, name="get")
class RankingJogosView(View):
    """Os dois rankings e a posição de quem está vendo (por isso sem cache)."""

    def get(self, request):
        jogo = request.GET.get("jogo") or ""
        if jogo not in arena.JOGOS_POR_SLUG:
            return JsonResponse({"erro": "jogo desconhecido"}, status=404)
        return JsonResponse(ranking.painel(request, jogo))


def _jogo_no_emulador(slug):
    """O jogo ativo que roda pelo emulador, com os arquivos, ou 404."""
    from .objetos_3d import tabela_pronta

    if not (tabela_pronta(JogoCadastrado) and tabela_pronta(ArquivoEmulador)):
        raise Http404("Jogo não encontrado.")
    jogo = get_object_or_404(
        JogoCadastrado.objects.prefetch_related(
            Prefetch("arquivos_emulador", queryset=ArquivoEmulador.objects.order_by("ordem", "id"))
        ),
        slug=slug, ativo=True,
    )
    if not jogo.emulador_pronto or jogo.sistema not in sistemas_ligados():
        raise Http404("Jogo não encontrado.")
    return jogo


def config_do_emulador(jogo):
    """O que o EmulatorJS recebe: o núcleo, o arquivo que ele abre e os que vão ao lado.

    Cada arquivo entra na pasta virtual com o `nome` guardado (o que o .cue
    pede), pela lista de arquivos externos -- o endereço no armazenamento
    pode ter outro nome. O índice (.cue/.m3u) sai do próprio site, já
    reescrito; o resto, do armazenamento.
    """
    arquivos = list(jogo.arquivos_emulador.all())
    principal = next(a for a in arquivos if a.papel == ArquivoEmulador.JOGO)
    if principal.e_indice:
        url_do_jogo = reverse("jogo_emulador_arquivo", args=[jogo.slug, principal.nome])
    else:
        # o "#/nome" não vai ao servidor: é para o emulador gravar com o nome certo
        url_do_jogo = f"{principal.url}#/{principal.nome}"
    externos = []
    for arquivo in arquivos:
        if arquivo is principal:
            continue
        externos.append({
            "caminho": "/" + arquivo.nome,
            "url": reverse("jogo_emulador_arquivo", args=[jogo.slug, arquivo.nome]) if arquivo.e_indice else arquivo.url,
            "tamanho": len(arquivo.conteudo.encode("utf-8")) if arquivo.e_indice else arquivo.tamanho,
            "nome": arquivo.nome,
        })
    return {
        "core": jogo.sistema,
        "jogo": url_do_jogo,
        # o quadro baixa estes antes (com progresso) e entrega os bytes ao emulador
        "externos": externos,
        "dados": static("vendor/emulatorjs/data/"),
        "nome": jogo.slug,
        "cor": jogo.cor[:7],
        "titulo": jogo.nome,
    }


@method_decorator(xframe_options_sameorigin, name="dispatch")
class JogoEmuladorView(View):
    """A página do emulador: o que o quadro da página do jogo abre.

    Página do próprio site, com o código do EmulatorJS e mais nada: nenhum
    .html enviado roda aqui (os arquivos são dados que o emulador lê). Abre
    só dentro do próprio site (o padrão do site é não deixar enquadrar).
    """

    def get(self, request, slug):
        jogo = _jogo_no_emulador(slug)
        resposta = render(request, "jogo_emulador.html", {"jogo": jogo, "config": config_do_emulador(jogo)})
        resposta["X-Robots-Tag"] = "noindex"
        return resposta


class ArquivoDoEmuladorView(View):
    """O índice (.cue, .m3u...) de um jogo do emulador, já com os nomes certos."""

    def get(self, request, slug, nome):
        jogo = _jogo_no_emulador(slug)
        arquivo = next((a for a in jogo.arquivos_emulador.all() if a.nome == nome and a.e_indice), None)
        if arquivo is None:
            raise Http404("Arquivo não encontrado.")
        resposta = HttpResponse(arquivo.conteudo.encode("utf-8"), content_type="text/plain; charset=utf-8")
        resposta["Cache-Control"] = "public, max-age=300"
        resposta["X-Robots-Tag"] = "noindex"
        return resposta

    head = get
