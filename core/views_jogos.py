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

import hashlib
import json
import logging
import time

from django.conf import settings
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

from . import arena, paginas_tema, ranking
from .home_cache import get_cached_catalog_page
from .jogos_emulador import SISTEMAS, controles_do_emulador, controles_do_sistema, DICAS_DE_CONTROLE, sistemas_para
from .models import ArquivoEmulador, Brinquedos, JogoCadastrado
from .views_arena import WHATSAPP

log_jogos = logging.getLogger(__name__)


def jogos_cadastrados(particulares=False, slug=None):
    """Os jogos que a equipe subiu pelo painel (ativos, com onde jogar), em ordem.

    Por padrão, só os públicos (o catálogo, que vai para o cache de todo mundo).
    `particulares=True` traz os particulares -- só para a equipe, por requisição.
    """
    from .objetos_3d import tabela_pronta

    jogos = []
    if not tabela_pronta(JogoCadastrado):  # antes da migração, a lista sai sem eles
        return jogos
    lista = JogoCadastrado.objects.filter(ativo=True, particular=particulares).order_by("ordem", "nome")
    if slug is not None:
        lista = lista.filter(slug=slug)
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
            "codigo_sistema": jogo.sistema if emulador else "",
            # PSP e DOS: o núcleo precisa de várias linhas de execução, e o navegador
            # só libera isso numa página isolada -- o jogo abre na tela inteira, fora do quadro
            "tela_propria": bool(emulador and jogo.sistema in SISTEMAS and SISTEMAS[jogo.sistema].threads),
            "particular": jogo.particular,
            "categoria": jogo.get_categoria_display() if jogo.categoria else "",
            "feito_pela_lazer": jogo.feito_pela_lazer,
            "destaque": jogo.destaque,
            "criado": jogo.criacao.isoformat() if jogo.criacao else "",
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


def _tema_do_jogo(slug):
    """A página da máquina daquele jogo (boliche, basquete...), para o link da ficha."""
    tema = paginas_tema.busca_do_jogo(slug).get("tema")
    if tema not in paginas_tema.TEMAS:
        return None
    return {"url": reverse("pagina_tema", args=[tema]), "h1": paginas_tema.TEMAS[tema]["h1"]}


def _dados_do_jogo(jogo, busca):
    """O jogo para o Google: um VideoGame gratuito, que roda no navegador."""
    site = str(getattr(settings, "SITE_URL", "") or "https://www.lazersport.com.br").rstrip("/")
    dados = {
        "@context": "https://schema.org",
        "@type": "VideoGame",
        "name": jogo["titulo"],
        "url": site + jogo["url"],
        "description": busca.get("descricao") or jogo["descricao"],
        "image": site + estatico(jogo["capa"]),
        "genre": jogo["maquina"],
        "inLanguage": "pt-BR",
        "gamePlatform": ["Navegador", "Celular", "Computador"],
        "playMode": "SinglePlayer",
        "isAccessibleForFree": True,
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "BRL"},
        "publisher": {"@id": "https://www.lazersport.com.br/#empresa"},
    }
    return json.dumps(dados, ensure_ascii=False).replace("</", "<\\/")


def _para_o_script(jogo):
    """O que o simulador precisa de um jogo, com os endereços já versionados."""
    controle = jogo["controle"]
    busca = paginas_tema.busca_do_jogo(jogo["slug"])
    tema = _tema_do_jogo(jogo["slug"])
    return {
        "tituloBusca": busca.get("titulo", ""),
        "fraseBusca": busca.get("frase", ""),
        "temaUrl": tema["url"] if tema else "",
        "temaNome": tema["h1"] if tema else "",
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
        "noPc": controle.get("pc", ""),
        "noCelular": controle.get("celular", ""),
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
            if cadastrado is None and request.user.is_staff:
                # o particular: fora do catálogo (e do cache de todo mundo); só a equipe abre
                cadastrado = next(iter(jogos_cadastrados(particulares=True, slug=slug)), None)
            if cadastrado is None:
                raise Http404("Jogo não encontrado")
            resposta = self.pagina_do_jogo_cadastrado(request, cadastrado, dados)
            if cadastrado.get("particular"):
                resposta["X-Robots-Tag"] = "noindex, nofollow"
                resposta["Cache-Control"] = "private, no-store"
            return resposta

        jogos = dados["jogos"]
        atual = next((j for j in jogos if j["slug"] == slug), jogos[0])
        painel = ranking.painel(request, atual["slug"])
        voltar = atual["url"]
        salvos = ranking.salvos_agora(request)

        busca = paginas_tema.busca_do_jogo(atual["slug"])
        return render(request, "jogos.html", {
            "jogos": jogos,
            "jogos_externos": externos,
            "atual": atual,
            "busca": busca,
            "tema_do_jogo": _tema_do_jogo(atual["slug"]),
            "dados_do_jogo_ld": _dados_do_jogo(atual, busca),
            "jogo_escolhido": slug is not None,
            "jogos_script": [_para_o_script(j) for j in jogos],
            "whatsapp": WHATSAPP,
            "ranking": painel,
            "salvos": salvos,
            "jogador": {
                **painel,
                "partidaUrl": reverse("jogos_partida"),
                "abriuUrl": reverse("jogos_abriu"),
                "rankingUrl": reverse("jogos_ranking"),
                "cadastroUrl": reverse("registrar"),
                "entrarUrl": reverse("login"),
                "voltar": voltar,
            },
        })

    def pagina_do_jogo_cadastrado(self, request, jogo, dados):
        """A página de um jogo que a equipe subiu: o jogo num quadro isolado."""
        from . import portal_jogos

        preparo = None
        if jogo.get("emulador"):
            try:
                modelo = _jogo_no_emulador(jogo["slug"], equipe=request.user.is_staff)
            except Http404:
                modelo = None
            if modelo is not None:
                config = config_do_emulador(modelo)
                sistema = SISTEMAS.get(modelo.sistema)
                preparo = {
                    "config": {"jogo": config["jogo"], "arquivos": config["arquivos"]},
                    "dados": config["dados"],
                    # só o núcleo que mora no site (os de licença livre); os outros vêm do CDN do emulador
                    "nucleo": sistema.nucleo if sistema and sistema.uso_comercial else "",
                    # o núcleo de várias linhas tem outro nome de arquivo (ppsspp-thread-wasm.data)
                    "threads": bool(sistema and sistema.threads),
                    # o PSP abre também os arquivos de apoio do PPSSPP (fontes, tabelas)
                    "extras": ["cores/ppsspp-assets.zip"] if sistema and sistema.nucleo == "ppsspp" else [],
                }
        codigo = jogo.get("codigo_sistema") or ""
        return render(request, "jogo_cadastrado.html", {
            "preparo": preparo,
            "jogo": jogo,
            "jogos": arena.jogos_do_simulador(arena.JOGOS),
            "parecidos": portal_jogos.parecidos(dados, jogo["slug"]),
            # "Como jogar": tecla por tecla no computador, botão por botão no celular
            "controles": controles_do_sistema(codigo) if codigo else [],
            "dicas_de_controle": DICAS_DE_CONTROLE,
            "anuncio": portal_jogos.anuncio_da_pagina_do_jogo(),
            "abriu_url": reverse("jogos_abriu"),
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


def _jogo_no_emulador(slug, equipe=False):
    """O jogo ativo que roda pelo emulador, com os arquivos, ou 404 (o particular, só para a equipe)."""
    from .objetos_3d import tabela_pronta

    if not (tabela_pronta(JogoCadastrado) and tabela_pronta(ArquivoEmulador)):
        raise Http404("Jogo não encontrado.")
    jogo = get_object_or_404(
        JogoCadastrado.objects.prefetch_related(
            Prefetch("arquivos_emulador", queryset=ArquivoEmulador.objects.order_by("ordem", "id"))
        ),
        slug=slug, ativo=True,
    )
    if jogo.particular and not equipe:
        raise Http404("Jogo não encontrado.")
    if not jogo.emulador_pronto or jogo.sistema not in sistemas_para(jogo.particular):
        raise Http404("Jogo não encontrado.")
    return jogo


def _nome_do_dos(nome):
    """O nome no padrão do MS-DOS (8 letras, ponto, 3 letras): "Meu Jogo 2.exe" -> "MEUJOGO2.EXE"."""
    import re

    base, _, ext = nome.rpartition(".") if "." in nome else (nome, "", "")
    base = re.sub(r"[^A-Za-z0-9_]", "", base).upper()[:8] or "JOGO"
    ext = re.sub(r"[^A-Za-z0-9]", "", ext).upper()[:3]
    return f"{base}.{ext}" if ext else base


def config_do_emulador(jogo):
    """O que o quadro do emulador recebe: o núcleo e TODOS os arquivos, cada um com o nome exato.

    O quadro baixa cada arquivo (juntando os pedaços, quando ele foi
    guardado em pedaços) e entrega os bytes ao EmulatorJS: o principal (o
    .cue, o .m3u, a ROM) como o jogo, os outros na pasta virtual, com o
    nome que o índice pede. O índice sai do próprio site, já reescrito.
    """
    arquivos = []
    principal = None
    for arquivo in jogo.arquivos_emulador.all():
        if arquivo.e_indice:
            # a versão no endereço: o índice sai sempre do mesmo lugar, e o jogo
            # guardado no aparelho (jogo-guardado.js) não pode abrir o índice velho
            texto = arquivo.conteudo.encode("utf-8")
            versao = hashlib.sha1(texto).hexdigest()[:12]
            partes = [(reverse("jogo_emulador_arquivo", args=[jogo.slug, arquivo.nome]) + f"?v={versao}", len(texto))]
        else:
            partes = arquivo.partes()
        item = {
            "caminho": "/" + arquivo.nome,
            "nome": arquivo.nome,
            "partes": [url for url, _ in partes],
            "tamanhos": [tamanho for _, tamanho in partes],
            "tamanho": sum(tamanho for _, tamanho in partes),
            "principal": arquivo.papel == ArquivoEmulador.JOGO,
        }
        if item["principal"]:
            principal = item
        arquivos.append(item)
    extensao = principal["nome"].rsplit(".", 1)[-1].lower() if principal and "." in principal["nome"] else ""
    # o jogo salvo é guardado pelo nome do jogo no emulador: o do site (único);
    # no fliperama, o nome do .zip é o do jogo e precisa ficar como está
    nome = principal["nome"] if jogo.sistema == "arcade" and principal else f"{jogo.slug}.{extensao}" if extensao else jogo.slug
    if jogo.sistema == "dos" and principal:
        # o MS-DOS só abre nome 8.3 (JOGO.EXE): "dos-teste.com" seria "Illegal command"
        nome = _nome_do_dos(principal["nome"])
    return {
        "core": jogo.sistema,
        # o jogo guardado no aparelho é separado por jogo (para liberar espaço do mais antigo)
        "jogo": jogo.slug,
        "arquivos": arquivos,
        "nome": nome,
        "dados": static("vendor/emulatorjs/data/"),
        "cor": jogo.cor[:7],
        "titulo": jogo.nome,
        # ajustes de teclado do site (N64 e PSP com o analógico nas setas); None = o padrão do emulador
        "controles": controles_do_emulador(jogo.sistema),
        # PSP e DOS: o núcleo de várias linhas (EJS_threads), na página isolada
        "threads": bool(jogo.sistema in SISTEMAS and SISTEMAS[jogo.sistema].threads),
        # aberta na tela inteira (sem o quadro), a página do emulador mostra o caminho de volta
        "voltar": reverse("jogo", args=[jogo.slug]),
    }


@method_decorator(xframe_options_sameorigin, name="dispatch")
class JogoEmuladorView(View):
    """A página do emulador: o que o quadro da página do jogo abre.

    Página do próprio site, com o código do EmulatorJS e mais nada: nenhum
    .html enviado roda aqui (os arquivos são dados que o emulador lê). Abre
    só dentro do próprio site (o padrão do site é não deixar enquadrar).
    """

    def get(self, request, slug):
        jogo = _jogo_no_emulador(slug, equipe=request.user.is_staff)
        config = config_do_emulador(jogo)
        resposta = render(request, "jogo_emulador.html", {"jogo": jogo, "config": config})
        resposta["X-Robots-Tag"] = "noindex"
        if config["threads"]:
            # ISOLAMENTO DE ORIGEM: sem estes dois cabeçalhos o navegador não libera
            # a memória compartilhada (SharedArrayBuffer) que o PSP e o DOS usam.
            # A página só carrega coisas do próprio site e os arquivos do jogo, que
            # vêm por CORS (Cloudinary/balde) -- nada aqui quebra com eles.
            resposta["Cross-Origin-Opener-Policy"] = "same-origin"
            resposta["Cross-Origin-Embedder-Policy"] = "require-corp"
        return resposta


class ArquivoDoEmuladorView(View):
    """O índice (.cue, .m3u...) de um jogo do emulador, já com os nomes certos."""

    def get(self, request, slug, nome):
        jogo = _jogo_no_emulador(slug, equipe=request.user.is_staff)
        arquivo = next((a for a in jogo.arquivos_emulador.all() if a.nome == nome and a.e_indice), None)
        if arquivo is None:
            raise Http404("Arquivo não encontrado.")
        resposta = HttpResponse(arquivo.conteudo.encode("utf-8"), content_type="text/plain; charset=utf-8")
        resposta["Cache-Control"] = "private, max-age=300" if jogo.particular else "public, max-age=300"
        resposta["X-Robots-Tag"] = "noindex"
        return resposta

    head = get


# ---------------------------------------------------------------- o portal (/jogos/)

SESSAO_ABERTOS = "jogos_abertos"
SESSAO_GRATIS = "jogos_gratis_usados"
#: Uma partida contada por visitante e jogo a cada meia hora (recarregar não infla o "Mais jogados").
INTERVALO_DE_CONTAGEM = 30 * 60


class PortalJogosView(View):
    """Lazer & Sport Games: a vitrine com busca, destaques, faixas, ranking e anúncios."""

    def get(self, request):
        from . import portal_jogos

        dados = get_cached_catalog_page("jogos", (), dados_do_simulador)
        pedido = request.GET
        contexto = portal_jogos.montar(
            dados,
            busca=(pedido.get("q") or "")[:80],
            estante=(pedido.get("estante") or "")[:20],
            genero=(pedido.get("genero") or "")[:40],
            ordem=(pedido.get("ordem") or "")[:12],
        )
        contexto["ranking_portal"] = portal_jogos.ranking_do_portal()
        contexto["eu"] = None
        if request.user.is_authenticated:
            contexto["eu"] = {"nome": ranking.nome_publico(request.user), "geral": ranking.posicao_geral(request.user)}
        # o campeão de cada jogo da casa vai na ficha do jogo, na biblioteca
        campeoes = {c["slug"]: {"nome": c["nome"], "pontos": c["pontos"]} for c in contexto["ranking_portal"]["campeoes"]}
        contexto["indice_busca"] = [
            {
                **{chave: c[chave] for chave in ("slug", "titulo", "url", "capa", "poster", "cor", "plataforma", "sigla",
                                                 "categoria", "tipo", "familias", "estante", "tema", "busca", "ranking",
                                                 "destaque", "partidas", "novidade", "chamada", "como", "sistema", "dicas")},
                "descricao": c["descricao"][:420],
                "criado": c["criado"][:10],
                "ordem": c["_ordem"],
                "campeao": campeoes.get(c["slug"]),
            }
            for c in contexto["todos"]
        ]
        # o que o JavaScript precisa para montar as estantes e as coleções sem o servidor
        contexto["dados_da_biblioteca"] = {
            "estantes": [dict(portal_jogos.TEMA[chave]) for chave, *_ in portal_jogos.ESTANTES],
            "colecoes": [{k: v for k, v in c.items() if k != "total"} for c in contexto["colecoes"]],
            "porEstante": portal_jogos.POR_ESTANTE,
            "novidadeDias": portal_jogos.NOVIDADE_DIAS,
            # o como jogar de cada console que está na biblioteca: tecla por tecla e botão por botão
            "controles": {codigo: controles_do_sistema(codigo) for codigo in sorted({c["sistema"] for c in contexto["todos"] if c["sistema"]})},
            "dicas": DICAS_DE_CONTROLE,
        }
        site = str(getattr(settings, "SITE_URL", "") or "https://www.lazersport.com.br").rstrip("/")
        contexto["dados_estruturados"] = json.dumps({
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": "Lazer & Sport Games",
            "url": site + reverse("jogos"),
            "mainEntity": {"@type": "ItemList", "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": c["titulo"], "url": site + c["url"]}
                for i, c in enumerate(contexto["todos"][:50])
            ]},
        }, ensure_ascii=False).replace("</", "<\\/")
        return render(request, "jogos_portal.html", contexto)


def _contar_partida(slug):
    from django.db import DatabaseError
    from django.db.models import F

    from .models import PartidasDoJogo

    try:
        linha, criada = PartidasDoJogo.objects.get_or_create(slug=slug, defaults={"partidas": 1})
        if not criada:
            PartidasDoJogo.objects.filter(pk=linha.pk).update(partidas=F("partidas") + 1)
    except DatabaseError:
        log_jogos.warning("Portal: não deu para contar a partida de %s", slug)


class AbriuJogoView(View):
    """O toque em Jogar: conta a partida e diz se o visitante pode jogar.

    Quem não entrou na conta joga UMA vez cada jogo cadastrado (a mesma regra
    dos jogos da casa, que o ranking.js já aplica); da segunda vez, a página
    convida a criar a conta. Falha de rede ou de banco nunca trava o jogo.
    """

    def post(self, request):
        try:
            slug = str(json.loads(request.body or b"{}").get("jogo") or "")[:80]
        except ValueError:
            return JsonResponse({"erro": "corpo inválido"}, status=400)
        da_casa = slug in arena.JOGOS_POR_SLUG
        cadastrado = None
        if not da_casa:
            dados = get_cached_catalog_page("jogos", (), dados_do_simulador)
            cadastrado = next((j for j in dados["externos"] if j["slug"] == slug), None)
            if cadastrado is None:
                return JsonResponse({"erro": "jogo desconhecido"}, status=404)
        visitante = not request.user.is_authenticated
        gratis = list(request.session.get(SESSAO_GRATIS, []))
        if cadastrado is not None and visitante and slug in gratis:
            url = cadastrado["url"]
            return JsonResponse({
                "liberado": False,
                "cadastro": reverse("registrar") + "?next=" + url,
                "entrar": reverse("login") + "?next=" + url,
            })
        agora = time.time()
        abertos = dict(request.session.get(SESSAO_ABERTOS, {}))
        if agora - float(abertos.get(slug, 0)) > INTERVALO_DE_CONTAGEM:
            _contar_partida(slug)
            abertos[slug] = agora
            request.session[SESSAO_ABERTOS] = abertos
        if cadastrado is not None and visitante:
            gratis.append(slug)
            request.session[SESSAO_GRATIS] = gratis
        return JsonResponse({"liberado": True, "ultima_gratis": cadastrado is not None and visitante})


class AnuncioJogosView(View):
    """O clique num anúncio do portal: conta e leva ao destino."""

    def get(self, request, pk):
        from django.db.models import F
        from django.shortcuts import redirect

        from .models import AnuncioJogos

        anuncio = get_object_or_404(AnuncioJogos, pk=pk, ativo=True)
        if not anuncio.link:
            raise Http404
        AnuncioJogos.objects.filter(pk=pk).update(cliques=F("cliques") + 1)
        return redirect(anuncio.link)
