"""O portal Lazer & Sport Games (/jogos/): vitrine, busca, anúncios, partida grátis.

O que se garante:
* os jogos da casa e os "feitos pela Lazer & Sport" ficam juntos, separados
  dos de console e dos HTML5; o destaque vai para o carrossel do topo;
* a busca (?q=) responde sem JavaScript, sem acento e por pedaços do nome,
  e a página traz o índice que a busca na hora usa;
* o anúncio entra no ar só ativo e dentro das datas, e o clique é contado;
* o toque em Jogar conta a partida (uma vez a cada meia hora) e o visitante
  sem conta joga uma vez cada jogo cadastrado; quem tem conta, à vontade;
* o painel interno grava a categoria e as marcas do portal.
"""
import datetime as dt
import json
import shutil
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from . import arena, portal_jogos
from .models import AnuncioJogos, JogoCadastrado, PartidasDoJogo
from .tests_jogos_cadastrados import PNG, BaseJogos
from .tests_ranking import _cliente


class BasePortal(BaseJogos):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)
        pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, pasta, ignore_errors=True)
        trocar = mock.patch.object(AnuncioJogos._meta.get_field("imagem"), "storage",
                                   FileSystemStorage(location=pasta, base_url="/media/"))
        trocar.start()
        self.addCleanup(trocar.stop)

    def anuncio(self, **dados):
        base = {"titulo": "Festa na Lazer", "texto": "Alugue as máquinas", "link": "https://exemplo.com/festa",
                "local": AnuncioJogos.TOPO,
                "imagem": SimpleUploadedFile("anuncio.png", PNG, content_type="image/png")}
        base.update(dados)
        return AnuncioJogos.objects.create(**base)

    def portal(self, **parametros):
        resposta = self.client.get(reverse("jogos"), parametros)
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "jogos_portal.html")
        return resposta

    @staticmethod
    def estante(resposta, chave):
        """Os jogos de uma estante, na vista das estantes (a página sem filtro)."""
        return [j["slug"] for e in resposta.context["estantes"] if e["chave"] == chave for j in e["jogos"]]

    def lista(self, **parametros):
        """Os jogos da lista pedida (?estante=, ?genero=, ?ordem=, ?q=)."""
        return [j["slug"] for j in self.portal(**parametros).context["lista"]]


class VitrineTests(BasePortal):
    def test_os_da_casa_e_os_feitos_por_nos_ficam_numa_estante_separada(self):
        self.salvo()  # Corrida Maluca: um HTML5 de fora
        self.salvo(nome="Pinball da Lazer", slug="pinball-da-lazer", feito_pela_lazer=True)
        resposta = self.portal()
        nossos = self.estante(resposta, "nosso")
        for jogo in arena.JOGOS:
            self.assertIn(jogo["slug"], nossos)
        self.assertIn("pinball-da-lazer", nossos)
        self.assertNotIn("corrida-maluca", nossos)
        self.assertEqual(self.estante(resposta, "html"), ["corrida-maluca"])
        self.assertContains(resposta, 'data-estante="nosso"')
        self.assertContains(resposta, "Feitos pela Lazer &amp; Sport")
        self.assertContains(resposta, '<span class="bj-sigla">L&amp;S</span>')
        self.assertContains(resposta, '<span class="bj-sigla">HTML5</span>')

    def test_o_destaque_vai_para_o_carrossel_do_topo(self):
        self.salvo(destaque=True)
        resposta = self.portal()
        self.assertEqual(resposta.context["destaques"][0]["slug"], "corrida-maluca")
        self.assertContains(resposta, "data-portal-hero")

    def test_colecoes_novidades_e_mais_jogados(self):
        self.salvo()
        self.assertIn("corrida-maluca", self.lista(estante="novidades"))
        self.assertEqual(self.lista(estante="mais-jogados"), [])  # ninguém jogou ainda
        PartidasDoJogo.objects.create(slug="corrida-maluca", partidas=7)
        PartidasDoJogo.objects.create(slug=arena.JOGOS[0]["slug"], partidas=3)
        portal_jogos.esquecer_vivo()
        self.assertEqual(self.lista(estante="mais-jogados"), ["corrida-maluca", arena.JOGOS[0]["slug"]])
        self.assertContains(self.portal(), "7 partidas")
        com_ranking = self.lista(estante="ranking")
        self.assertEqual(sorted(com_ranking), sorted(j["slug"] for j in arena.JOGOS))

    def test_estante_genero_e_ordem_pelo_endereco(self):
        self.salvo(categoria="corrida")
        self.salvo(nome="Abelha Veloz", slug="abelha-veloz", categoria="corrida")
        self.salvo(nome="Xadrez Rápido", slug="xadrez-rapido", categoria="puzzle")
        self.assertEqual(self.lista(estante="html", ordem="az"), ["abelha-veloz", "corrida-maluca", "xadrez-rapido"])
        self.assertEqual(self.lista(genero="Corrida", ordem="az"), ["abelha-veloz", "corrida-maluca"])
        self.assertEqual(self.lista(estante="html", genero="Quebra-cabeça"), ["xadrez-rapido"])
        resposta = self.portal(estante="html")
        self.assertContains(resposta, "Jogos HTML5")
        self.assertContains(resposta, "3 jogos")
        self.assertContains(resposta, "data-portal-hero hidden")  # com filtro, a biblioteca sobe
        self.assertIsNone(self.portal(estante="nao-existe").context["lista"])  # estante errada: a biblioteca inteira

    def test_estante_grande_mostra_ver_todos(self):
        for i in range(portal_jogos.POR_ESTANTE + 1):
            self.salvo(nome=f"Jogo {i:02d}", slug=f"jogo-{i:02d}")
        resposta = self.portal()
        html = next(e for e in resposta.context["estantes"] if e["chave"] == "html")
        self.assertEqual(len(html["jogos"]), portal_jogos.POR_ESTANTE)
        self.assertEqual(html["total"], portal_jogos.POR_ESTANTE + 1)
        self.assertContains(resposta, 'class="bj-estante-todos" href="?estante=html#biblioteca"')
        self.assertEqual(len(self.lista(estante="html")), portal_jogos.POR_ESTANTE + 1)

    def test_os_generos_e_o_indice_da_biblioteca_vem_na_pagina(self):
        self.salvo(categoria="corrida")
        resposta = self.portal()
        self.assertIn({"nome": "Corrida", "total": 1}, resposta.context["generos"])
        self.assertContains(resposta, 'data-bj-genero="Corrida"')
        self.assertContains(resposta, 'href="?estante=html#biblioteca"')
        indice = resposta.context["indice_busca"]
        corrida = next(j for j in indice if j["slug"] == "corrida-maluca")
        self.assertEqual(corrida["tipo"], "html")
        self.assertEqual(corrida["estante"], "html")
        self.assertEqual(corrida["sigla"], "HTML5")
        self.assertEqual(corrida["como"], "Arraste para desviar.")
        self.assertIn("corrida maluca", corrida["busca"])
        casa = next(j for j in indice if j["slug"] == "super-boxing")
        self.assertIn("Espaço", casa["dicas"]["pc"])
        self.assertContains(resposta, 'id="portal-jogos"')
        self.assertContains(resposta, 'id="portal-biblioteca"')
        self.assertContains(resposta, "data-bj-ficha")
        self.assertContains(resposta, "portal-jogos.js")

    def test_visitante_ve_o_convite_e_quem_entrou_ve_o_proprio_nome(self):
        resposta = self.portal()
        self.assertContains(resposta, "Criar conta grátis")
        self.assertIsNone(resposta.context["eu"])
        self.client.force_login(_cliente("ana", "ana@exemplo.com", first_name="Ana"))
        resposta = self.portal()
        self.assertIsNotNone(resposta.context["eu"])
        self.assertNotContains(resposta, "pg-convite")

    def test_o_ranking_e_os_dados_estruturados(self):
        resposta = self.portal()
        self.assertContains(resposta, "Ranking Lazer &amp; Sport Games")
        self.assertContains(resposta, '"@type": "CollectionPage"')


class GaleriaTests(BasePortal):
    """Os cartões da biblioteca: a capa ou a arte de reserva, os selos, o Jogar por cima e a barra de ferramentas."""

    def test_cada_cartao_leva_a_ficha_e_tem_o_jogar_por_cima_da_capa(self):
        self.salvo()
        resposta = self.portal()
        url = reverse("jogo", args=["corrida-maluca"])
        # o cartão inteiro abre a ficha (sem JavaScript, a página do jogo)...
        self.assertContains(resposta, f'<a class="bj-capa-link" href="{url}" data-bj-jogo="corrida-maluca">')
        # ...e o Jogar abre o jogo direto, dentro do app, com o nome do jogo para o leitor de tela
        self.assertContains(resposta, f'<a class="bj-capa-jogar" href="{url}" data-app-jogo="corrida-maluca" aria-label="Jogar Corrida Maluca">')
        # nas estantes, a grade que vira fila no celular
        self.assertContains(resposta, 'class="bj-grade bj-grade--fila"')
        self.assertContains(resposta, 'class="bj-capa-img"')
        self.assertNotContains(resposta, 'class="bj-capa-reserva"')  # todos têm capa

    def test_jogo_sem_capa_ganha_a_arte_de_reserva(self):
        self.salvo()
        JogoCadastrado.objects.filter(slug="corrida-maluca").update(capa="")
        resposta = self.portal()
        corrida = next(c for c in resposta.context["todos"] if c["slug"] == "corrida-maluca")
        self.assertEqual(corrida["capa"], "")
        self.assertEqual(corrida["icone"], "fa-html5")
        # nunca um quadrado vazio: o ícone do console e o nome, sobre a cor do jogo
        self.assertContains(resposta, '<span class="bj-capa-reserva" aria-hidden="true"><i class="fa-brands fa-html5"></i><b>Corrida Maluca</b></span>',
                            count=1, html=False)
        self.assertContains(resposta, "data-bj-ficha-reserva")  # e a ficha também tem a dela

    def test_o_recorde_aparece_no_selo_de_ranking(self):
        from .models import RecordeJogo

        ana = _cliente("ana", "ana@exemplo.com", first_name="Ana", last_name="Souza")
        RecordeJogo.objects.create(usuario=ana, jogo="hit-music", pontos=9000, partidas=1)
        resposta = self.portal()
        hit = next(c for c in resposta.context["todos"] if c["slug"] == "hit-music")
        self.assertEqual(hit["campeao"], {"nome": "Ana S.", "pontos": 9000})
        self.assertContains(resposta, 'title="Com ranking · recorde de Ana S.: 9.000 pts"')
        self.assertContains(resposta, '<span class="bj-oculto">Recorde:</span> 9.000')
        # quem ainda não tem recorde fica só com o troféu (e o nome dele para o leitor de tela)
        self.assertContains(resposta, '<span class="bj-oculto">Com ranking</span>')

    def test_o_genero_tambem_fica_na_barra_de_ferramentas(self):
        self.salvo(categoria="corrida")
        resposta = self.portal(genero="Corrida")
        self.assertContains(resposta, "data-bj-genero-escolha")
        self.assertContains(resposta, '<option value="Corrida" selected>Corrida (1)</option>')
        # o gênero vai uma vez só no formulário (a escolha), não também num campo escondido
        self.assertNotContains(resposta, 'type="hidden" name="genero"')
        self.assertEqual([j["slug"] for j in resposta.context["lista"]], ["corrida-maluca"])


class LauncherAppTests(BasePortal):
    """O launcher é um app: sem o cabeçalho do site, com o carrossel, instalável e sem internet."""

    def test_o_launcher_abre_como_app_com_o_carrossel(self):
        html = self.portal().content.decode()
        self.assertIn("ls-modo-app", html)  # sem o cabeçalho e o rodapé do site
        self.assertIn("data-app-abertura", html)  # o carregamento com a marca
        self.assertIn('class="pg-slide-arte"', html)  # o carrossel de sempre (a capa que flutua)
        self.assertIn("data-portal-pontos", html)
        self.assertIn('data-app-jogo="', html)  # o Jogar abre o jogo dentro do app
        self.assertIn("data-app-tela-cheia", html)
        self.assertIn(reverse("jogos_app_manifesto"), html)
        self.assertNotIn("{#", html)  # nenhum comentário do template vazando na página
        self.assertNotIn("{% comment", html)

    def test_o_service_worker_e_o_manifesto(self):
        sw = self.client.get(reverse("jogos_app_sw"))
        self.assertEqual(sw.status_code, 200)
        self.assertIn("javascript", sw["Content-Type"])
        self.assertEqual(sw["Service-Worker-Allowed"], reverse("jogos"))
        corpo = sw.content.decode()
        self.assertIn('"/jogos/"', corpo)  # a biblioteca guardada desde a primeira visita
        self.assertIn("site/paginas/jogo-emulador.js", corpo)
        self.assertNotIn("__VERSAO__", corpo)
        manifesto = self.client.get(reverse("jogos_app_manifesto")).json()
        self.assertEqual(manifesto["scope"], reverse("jogos"))
        self.assertEqual(manifesto["display"], "fullscreen")
        self.assertTrue(any(i["sizes"] == "512x512" for i in manifesto["icons"]))

    def test_a_pagina_de_um_jogo_dentro_do_app_vem_sem_o_site(self):
        normal = self.client.get(reverse("jogo", args=["super-boxing"])).content.decode()
        no_app = self.client.get(reverse("jogo", args=["super-boxing"]), {"app": "1"}).content.decode()
        self.assertNotIn('class=" ls-modo-app"', normal)
        self.assertIn("ls-modo-app", no_app)

    def test_cada_jogo_da_casa_tem_a_arte_larga(self):
        from . import portal_jogos

        for jogo in arena.JOGOS:
            with self.subTest(jogo=jogo["slug"]):
                self.assertIn(jogo["slug"], portal_jogos.TOPOS_DA_CASA)


class BuscaTests(BasePortal):
    def test_a_busca_responde_sem_javascript_e_sem_acento(self):
        self.salvo()
        resposta = self.portal(q="corrida")
        self.assertEqual([j["slug"] for j in resposta.context["resultados"]], ["corrida-maluca"])
        self.assertContains(resposta, "Resultados para “corrida”")
        # os destaques saem do caminho enquanto há busca
        self.assertContains(resposta, "data-portal-hero hidden")
        musica = self.portal(q="MÚSICA")
        self.assertIn("hit-music", [j["slug"] for j in musica.context["resultados"]])

    def test_todas_as_palavras_precisam_bater(self):
        self.salvo()
        self.assertEqual(self.portal(q="corrida maluca").context["resultados"][0]["slug"], "corrida-maluca")
        self.assertEqual(self.portal(q="corrida xadrez").context["resultados"], [])

    def test_nada_achado_avisa(self):
        resposta = self.portal(q="zzzz")
        self.assertContains(resposta, "Nenhum jogo encontrado aqui ainda")


class AnunciosTests(BasePortal):
    def test_o_anuncio_ativo_aparece_e_o_clique_e_contado(self):
        anuncio = self.anuncio()
        resposta = self.portal()
        self.assertContains(resposta, "Festa na Lazer")
        clique = reverse("anuncio_jogos", args=[anuncio.pk])
        self.assertContains(resposta, f'href="{clique}"')
        self.assertContains(resposta, 'rel="sponsored noopener"')
        ida = self.client.get(clique)
        self.assertEqual(ida.status_code, 302)
        self.assertEqual(ida["Location"], "https://exemplo.com/festa")
        anuncio.refresh_from_db()
        self.assertEqual(anuncio.cliques, 1)

    def test_fora_das_datas_ou_inativo_nao_aparece(self):
        hoje = timezone.localdate()
        self.anuncio(titulo="Ainda nao", inicio=hoje + dt.timedelta(days=2))
        self.anuncio(titulo="Ja passou", fim=hoje - dt.timedelta(days=1))
        inativo = self.anuncio(titulo="Desligado", ativo=False)
        resposta = self.portal()
        for titulo in ("Ainda nao", "Ja passou", "Desligado"):
            self.assertNotContains(resposta, titulo)
        self.assertEqual(self.client.get(reverse("anuncio_jogos", args=[inativo.pk])).status_code, 404)

    def test_salvar_no_system_poe_no_ar_na_hora(self):
        self.portal()  # aquece o cache curto, ainda sem anúncio
        self.anuncio(titulo="Novidade quente", local=AnuncioJogos.MEIO)
        self.assertContains(self.portal(), "Novidade quente")

    def test_o_anuncio_da_pagina_do_jogo(self):
        self.salvo()
        self.anuncio(titulo="Na página do jogo", local=AnuncioJogos.JOGO)
        pagina = self.client.get(reverse("jogo", args=["corrida-maluca"]))
        self.assertContains(pagina, "Na página do jogo")
        self.assertNotContains(self.portal(), "Na página do jogo")


@override_settings(ALLOWED_HOSTS=["*"])
class PartidaGratisTests(BasePortal):
    def abrir(self, slug, gastar=False):
        corpo = {"jogo": slug, "gastar": True} if gastar else {"jogo": slug}
        return self.client.post(reverse("jogos_abriu"), data=json.dumps(corpo), content_type="application/json")

    def test_visitante_tem_duas_jogadas_no_total(self):
        """Morreu uma, morreu duas: a terceira pede o cadastro (o mesmo jogo duas vezes)."""
        self.salvo()
        primeira = self.abrir("corrida-maluca", gastar=True).json()
        self.assertTrue(primeira["liberado"])
        self.assertEqual(primeira["restantes"], 1)
        self.assertFalse(primeira["ultima_gratis"])
        self.assertEqual(primeira["segundos"], 5 * 60)  # jogo HTML/console: até 5 minutos
        segunda = self.abrir("corrida-maluca", gastar=True).json()
        self.assertTrue(segunda["liberado"])
        self.assertEqual(segunda["restantes"], 0)
        self.assertTrue(segunda["ultima_gratis"])
        terceira = self.abrir("corrida-maluca", gastar=True).json()
        self.assertFalse(terceira["liberado"])
        self.assertIn(reverse("registrar"), terceira["cadastro"])
        self.assertIn("next=" + reverse("jogo", args=["corrida-maluca"]), terceira["cadastro"])
        # a partida conta uma vez (recarregar não infla o "Mais jogados")
        self.assertEqual(PartidasDoJogo.objects.get(slug="corrida-maluca").partidas, 1)

    def test_dois_jogos_diferentes_uma_vez_cada_tambem_esgotam(self):
        self.salvo()
        casa = arena.JOGOS[0]["slug"]
        partida = self.abrir(casa, gastar=True).json()
        self.assertTrue(partida["liberado"])
        self.assertIsNone(partida["segundos"])  # o da casa acaba no fim da partida, sem relógio
        self.assertTrue(self.abrir("corrida-maluca", gastar=True).json()["liberado"])
        # acabou para TODOS os jogos, os da casa também
        self.assertFalse(self.abrir(casa, gastar=True).json()["liberado"])
        self.assertFalse(self.abrir("corrida-maluca").json()["liberado"])

    def test_perguntar_nao_gasta(self):
        """O launcher e a página do jogo de console só perguntam: quem gasta é o Jogar do emulador."""
        self.salvo()
        for _ in range(3):
            resposta = self.abrir("corrida-maluca").json()
            self.assertTrue(resposta["liberado"])
            self.assertEqual(resposta["restantes"], 2)
            self.assertIsNone(resposta["segundos"])

    def test_quem_tem_conta_joga_a_vontade(self):
        self.salvo()
        self.client.force_login(_cliente("bia", "bia@exemplo.com"))
        for _ in range(4):
            resposta = self.abrir("corrida-maluca", gastar=True).json()
            self.assertTrue(resposta["liberado"])
            self.assertFalse(resposta["ultima_gratis"])
            self.assertNotIn("segundos", resposta)

    def test_o_jogo_da_casa_traz_as_jogadas_da_sessao(self):
        slug = arena.JOGOS[0]["slug"]
        self.abrir(slug, gastar=True)
        pagina = self.client.get(reverse("jogo", args=[slug]))
        self.assertEqual(pagina.context["jogador"]["gratis"], {"limite": 2, "usadas": 1, "segundos": 300})
        self.client.force_login(_cliente("rui", "rui@exemplo.com"))
        self.assertIsNone(self.client.get(reverse("jogo", args=[slug])).context["jogador"]["gratis"])

    def test_depois_de_meia_hora_conta_de_novo(self):
        slug = arena.JOGOS[0]["slug"]
        agora = 1_000_000.0
        with mock.patch("core.views_jogos.time.time", return_value=agora):
            self.abrir(slug)
        with mock.patch("core.views_jogos.time.time", return_value=agora + 31 * 60):
            self.abrir(slug)
        self.assertEqual(PartidasDoJogo.objects.get(slug=slug).partidas, 2)

    def test_jogo_desconhecido_e_corpo_quebrado(self):
        self.assertEqual(self.abrir("nao-existe").status_code, 404)
        resposta = self.client.post(reverse("jogos_abriu"), data="{", content_type="application/json")
        self.assertEqual(resposta.status_code, 400)

    def test_sem_o_token_csrf_e_recusado(self):
        from django.test import Client

        cliente = Client(enforce_csrf_checks=True)
        resposta = cliente.post(reverse("jogos_abriu"), data=json.dumps({"jogo": arena.JOGOS[0]["slug"]}),
                                content_type="application/json")
        self.assertEqual(resposta.status_code, 403)

    def test_a_pagina_do_jogo_traz_o_convite_so_para_visitante(self):
        self.salvo()
        url = reverse("jogo", args=["corrida-maluca"])
        pagina = self.client.get(url)
        self.assertContains(pagina, "data-jogo-portao")
        self.assertContains(pagina, f'data-jogo-abriu="{reverse("jogos_abriu")}"')
        self.assertContains(pagina, "Crie sua conta grátis e jogue à vontade")
        self.client.force_login(_cliente("cris", "cris@exemplo.com"))
        self.assertNotContains(self.client.get(url), "data-jogo-portao")

    def test_o_simulador_conta_as_partidas_da_casa(self):
        resposta = self.client.get(reverse("jogo", args=[arena.JOGOS[0]["slug"]]))
        self.assertContains(resposta, f'"abriuUrl": "{reverse("jogos_abriu")}"')


class PaginaDoJogoTests(BasePortal):
    def test_jogos_parecidos_vem_primeiro_os_da_mesma_categoria(self):
        self.salvo(categoria="corrida")
        self.salvo(nome="Kart Turbo", slug="kart-turbo", categoria="corrida")
        self.salvo(nome="Xadrez Rápido", slug="xadrez-rapido", categoria="puzzle")
        pagina = self.client.get(reverse("jogo", args=["corrida-maluca"]))
        parecidos = [j["slug"] for j in pagina.context["parecidos"]]
        self.assertEqual(parecidos[0], "kart-turbo")
        self.assertNotIn("corrida-maluca", parecidos)
        self.assertContains(pagina, "Quem joga Corrida Maluca também joga")
        self.assertContains(pagina, "Ver todos os jogos")

    def test_nenhum_comentario_do_template_vaza_na_pagina(self):
        self.salvo()
        for url in (reverse("jogos"), reverse("jogo", args=["corrida-maluca"]), reverse("jogo", args=["super-boxing"])):
            html = self.client.get(url).content.decode()
            self.assertNotIn("{#", html, url)
            self.assertNotIn("{%", html, url)

    def test_jogo_html_mostra_o_como_jogar_da_equipe(self):
        self.salvo()
        pagina = self.client.get(reverse("jogo", args=["corrida-maluca"]))
        self.assertContains(pagina, "Como jogar")
        self.assertContains(pagina, "Arraste para desviar.")
        self.assertNotContains(pagina, "jc-teclas")  # sem console, sem tabela de teclas

    def test_a_ficha_do_simulador_explica_computador_e_celular(self):
        for jogo in arena.JOGOS:
            controle = arena.CONTROLES[jogo["slug"]]
            self.assertTrue(controle.get("pc"), jogo["slug"])
            self.assertTrue(controle.get("celular"), jogo["slug"])
        resposta = self.client.get(reverse("jogo", args=["super-boxing"]))
        self.assertContains(resposta, "data-sim-no-pc")
        self.assertContains(resposta, "aperte Espaço")
        self.assertContains(resposta, "botão SOCAR!")


@override_settings(ALLOWED_HOSTS=["*"])
class PainelTests(BasePortal):
    def test_o_admin_tem_os_anuncios_e_os_campos_do_portal(self):
        admin = User.objects.create_superuser("chefe", "chefe@exemplo.com", "x")
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("admin:core_anunciojogos_add")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:core_partidasdojogo_changelist")).status_code, 200)
        jogo = self.salvo()
        pagina = self.client.get(reverse("admin:core_jogocadastrado_change", args=[jogo.pk]))
        self.assertContains(pagina, 'name="feito_pela_lazer"')
        self.assertContains(pagina, 'name="destaque"')
        self.assertContains(pagina, 'name="categoria"')

    def test_o_formulario_aceita_console_nao_comercial_so_no_particular(self):
        from sistema_interno.views_jogos import JogoForm

        jogo = self.salvo()
        dados = {campo: getattr(jogo, campo) for campo in ("nome", "slug", "chamada", "descricao", "comandos", "cor",
                                                            "ordem", "endereco", "proporcao")}
        dados.update({"ativo": "on", "sistema": "snes"})
        publico = JogoForm(dados, instance=jogo)
        self.assertFalse(publico.is_valid())
        self.assertIn("Particular", " ".join(publico.errors["sistema"]))
        dados["particular"] = "on"
        particular = JogoForm(dados, instance=jogo)
        self.assertTrue(particular.is_valid(), particular.errors)
        particular.save()
        jogo.refresh_from_db()
        self.assertTrue(jogo.particular)

    def test_o_formulario_do_painel_grava_as_marcas_do_portal(self):
        from sistema_interno.views_jogos import JogoForm

        jogo = self.salvo()
        dados = {campo: getattr(jogo, campo) for campo in ("nome", "slug", "chamada", "descricao", "comandos", "cor",
                                                            "ordem", "endereco", "proporcao")}
        dados.update({"ativo": "on", "categoria": "corrida", "feito_pela_lazer": "on", "destaque": "on", "sistema": ""})
        form = JogoForm(dados, instance=jogo)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        jogo.refresh_from_db()
        self.assertEqual(jogo.categoria, "corrida")
        self.assertTrue(jogo.feito_pela_lazer)
        self.assertTrue(jogo.destaque)


class LauncherAoVivoTests(BasePortal):
    """O topo do launcher: a arte de cada destaque e os números de agora.

    * os jogos da casa têm a cena do jogo (capas/topo/: a larga e a quase quadrada); o primeiro
      destaque baixa já e os outros esperam a vez (data-src); os cadastrados ganham o mural da capa;
    * gente online, "jogando agora", "Em alta agora" e quem jogou valendo ranking hoje saem de dados
      de verdade e somem quando não há nada para mostrar.
    """

    def setUp(self):
        super().setUp()
        import itertools

        from . import presenca_jogos

        presenca_jogos.esquecer()
        self.addCleanup(presenca_jogos.esquecer)
        # o relógio da conta anda um segundo a cada leitura (a conta é refeita a cada batida)
        relogio = itertools.count(10_000.0, 1.0)
        trocar = mock.patch.object(presenca_jogos, "_agora", lambda: next(relogio))
        trocar.start()
        self.addCleanup(trocar.stop)

    def test_todo_jogo_da_casa_tem_as_duas_artes_do_destaque(self):
        from pathlib import Path

        pasta = Path(portal_jogos.__file__).resolve().parent / "static" / "site" / "arena" / "capas" / "topo"
        for jogo in arena.JOGOS:
            with self.subTest(jogo=jogo["slug"]):
                self.assertIn(jogo["slug"], portal_jogos.TOPOS_DA_CASA)
                self.assertIn(jogo["slug"], portal_jogos.TOPOS_ESTREITOS)
                for nome in (f"{jogo['slug']}.webp", f"{jogo['slug']}-estreito.webp"):
                    arquivo = pasta / nome
                    # leve: nenhuma arte do destaque passa de 160 KB
                    self.assertLess(arquivo.stat().st_size, 160 * 1024, nome)

    def test_o_destaque_usa_a_cena_e_so_o_primeiro_baixa_ja(self):
        resposta = self.portal()
        html = resposta.content.decode()
        destaques = resposta.context["destaques"]
        self.assertTrue(all(d["tipo"] == "nosso" for d in destaques))
        primeiro, segundo = destaques[0]["slug"], destaques[1]["slug"]
        self.assertIn(f'src="/static/site/arena/capas/topo/{primeiro}.webp?v=', html)
        self.assertIn(f'srcset="/static/site/arena/capas/topo/{primeiro}-estreito.webp?v=', html)
        self.assertIn(f'data-src="/static/site/arena/capas/topo/{segundo}.webp?v=', html)
        self.assertIn(f'data-srcset="/static/site/arena/capas/topo/{segundo}-estreito.webp?v=', html)
        # o fundo desfocado (o "borrão marrom") saiu
        self.assertNotIn("pg-slide-fundo", html)
        self.assertEqual(html.count("pg-slide--cena"), len(destaques))

    def test_o_cadastrado_em_destaque_ganha_o_mural_da_capa(self):
        jogo = self.salvo(destaque=True)
        resposta = self.portal()
        self.assertEqual(resposta.context["destaques"][0]["slug"], "corrida-maluca")
        self.assertContains(resposta, f'data-pg-mural="{jogo.capa.url}"')

    def test_os_jogos_da_casa_se_revezam_no_destaque_dia_a_dia(self):
        hoje = timezone.localdate()
        primeiros = set()
        for dias in range(len(arena.JOGOS)):
            with mock.patch.object(portal_jogos.timezone, "localdate", return_value=hoje + dt.timedelta(days=dias)):
                destaques = portal_jogos.montar({"jogos": arena.jogos_do_simulador(arena.JOGOS), "externos": []})["destaques"]
            self.assertEqual(len(destaques), portal_jogos.DESTAQUES)
            primeiros.add(destaques[0]["slug"])
        # em tantos dias quantos são os jogos, cada um abriu o carrossel uma vez
        self.assertEqual(primeiros, {j["slug"] for j in arena.JOGOS})

    def test_ninguem_online_nada_aparece(self):
        resposta = self.portal()
        self.assertContains(resposta, 'data-pg-online title="Pessoas com o Lazer &amp; Sport Games aberto agora" hidden')
        self.assertNotContains(resposta, 'class="bj-vivo"')
        self.assertIsNone(resposta.context["em_alta"])
        self.assertNotContains(resposta, "0 jogando")

    def test_gente_jogando_aparece_no_selo_no_destaque_e_nas_capas(self):
        from . import presenca_jogos

        slug = arena.JOGOS[2]["slug"]
        for i in range(3):
            presenca_jogos.bater(f"aparelho-de-teste-{i:03d}", "aba001", slug if i < 2 else "")
        resposta = self.portal()
        self.assertEqual(resposta.context["presenca"]["online"], 3)
        self.assertContains(resposta, '<b data-pg-online-n>3</b>')
        self.assertNotContains(resposta, 'data-pg-online title="Pessoas com o Lazer &amp; Sport Games aberto agora" hidden')
        self.assertEqual(resposta.context["em_alta"]["slug"], slug)
        self.assertContains(resposta, "2 jogando</small>")
        self.assertContains(resposta, '<span class="bj-vivo"><i class="pg-vivo-ponto" aria-hidden="true"></i>2 jogando</span>')
        self.assertEqual(next(j for j in resposta.context["indice_busca"] if j["slug"] == slug)["jogando"], 2)

    def test_o_pulso_traz_as_partidas_e_quem_jogou_hoje_valendo_ranking(self):
        from .models import RecordeJogo

        PartidasDoJogo.objects.create(slug=arena.JOGOS[0]["slug"], partidas=1200)
        PartidasDoJogo.objects.create(slug=arena.JOGOS[1]["slug"], partidas=34)
        ana = _cliente("ana@exemplo.com", "ana@exemplo.com", first_name="Ana")
        rui = _cliente("rui@exemplo.com", "rui@exemplo.com", first_name="Rui")
        RecordeJogo.objects.create(usuario=ana, jogo=arena.JOGOS[0]["slug"], pontos=90, partidas=2)
        RecordeJogo.objects.create(usuario=ana, jogo=arena.JOGOS[1]["slug"], pontos=40, partidas=1)
        antigo = RecordeJogo.objects.create(usuario=rui, jogo=arena.JOGOS[0]["slug"], pontos=50, partidas=1)
        RecordeJogo.objects.filter(pk=antigo.pk).update(atualizado_em=timezone.now() - dt.timedelta(days=3))
        portal_jogos.esquecer_vivo()
        resposta = self.portal()
        self.assertEqual(resposta.context["partidas_total"], 1234)
        self.assertContains(resposta, "<b>1.234</b> <span>partidas jogadas</span>", html=False)
        self.assertEqual(resposta.context["jogadores_hoje"], 1)
        self.assertContains(resposta, "<b>1</b> <span>jogador no ranking hoje</span>")
        self.assertEqual(resposta.context["lider"]["nome"], "Ana")

    def test_com_busca_o_pulso_sai_junto_com_o_destaque(self):
        self.assertContains(self.portal(q="boliche"), 'data-pg-pulso aria-label="Agora no Lazer &amp; Sport Games" hidden')


class EstantesPorConsoleTests(BasePortal):
    """ "Não foi criada uma categoria de Game Boy automaticamente": cada console que tem jogo
    ganha a estante dele, sozinha; console sem jogo não aparece; a família vira só filtro."""

    @staticmethod
    def externo(slug, codigo, nome_do_sistema, **extra):
        return {"slug": slug, "titulo": slug.replace("-", " ").title(), "url": f"/jogos/{slug}/", "emulador": True,
                "codigo_sistema": codigo, "sistema": nome_do_sistema, **extra}

    def montar(self, *externos, **filtros):
        return portal_jogos.montar({"jogos": [], "externos": list(externos)}, **filtros)

    def test_cada_console_com_jogo_ganha_a_sua_estante(self):
        dados = self.montar(
            self.externo("pokemon-firered", "gba", "Game Boy Advance"),
            self.externo("super-mario-advance-4", "gba", "Game Boy Advance"),
            self.externo("super-mario-64", "n64", "Nintendo 64"),
            self.externo("crash-bandicoot", "psx", "PlayStation (PS1)"),
            self.externo("metal-slug", "mame", "Fliperama (MAME 2003-Plus)"),
        )
        estantes = {e["chave"]: (e["nome"], [j["slug"] for j in e["jogos"]]) for e in dados["estantes"]}
        self.assertEqual(estantes["gba"], ("Game Boy Advance", ["pokemon-firered", "super-mario-advance-4"]))
        self.assertEqual(estantes["n64"], ("Nintendo 64", ["super-mario-64"]))
        self.assertEqual(estantes["psx"][1], ["crash-bandicoot"])
        self.assertEqual(estantes["arcade"], ("Fliperama", ["metal-slug"]))  # MAME e FinalBurn: a mesma estante
        # sem a fila da família misturando tudo, e sem estante vazia
        self.assertNotIn("nintendo", estantes)
        self.assertNotIn("gb", estantes)
        self.assertNotIn("snes", estantes)
        # a ordem da página: da casa, PlayStation, Nintendo (N64 antes do GBA), Fliperama
        ordem = [chave for chave in estantes if chave in ("psx", "n64", "gba", "arcade")]
        self.assertEqual(ordem, ["psx", "n64", "gba", "arcade"])
        # a ficha do jogo diz "Mais de Game Boy Advance"
        cartao = next(c for c in dados["todos"] if c["slug"] == "pokemon-firered")
        self.assertEqual(cartao["estante"], "gba")
        self.assertEqual(cartao["tema"], portal_jogos.TEMA["gba"]["cor"])

    def test_a_estante_do_console_e_a_familia_filtram(self):
        jogos = (self.externo("pokemon-firered", "gba", "Game Boy Advance"),
                 self.externo("super-mario-64", "n64", "Nintendo 64"),
                 self.externo("crash-bandicoot", "psx", "PlayStation (PS1)"))
        so_gba = self.montar(*jogos, estante="gba")
        self.assertEqual([c["slug"] for c in so_gba["lista"]], ["pokemon-firered"])
        self.assertEqual(so_gba["lista_titulo"], "Game Boy Advance")
        da_nintendo = self.montar(*jogos, estante="nintendo", ordem="az")
        self.assertEqual([c["slug"] for c in da_nintendo["lista"]], ["pokemon-firered", "super-mario-64"])

    def test_console_sem_estante_propria_vai_para_outros_consoles(self):
        dados = self.montar(self.externo("jogo-novo", "console-que-nao-existe", "Console Novo"))
        estantes = {e["chave"]: [j["slug"] for j in e["jogos"]] for e in dados["estantes"]}
        self.assertEqual(estantes["outros"], ["jogo-novo"])

    def test_todo_console_do_emulador_tem_estante(self):
        from .jogos_emulador import SISTEMAS
        sem_estante = sorted(codigo for codigo in SISTEMAS if codigo not in portal_jogos.ESTANTE_DO_SISTEMA)
        self.assertEqual(sem_estante, [])
        # e os ícones existem no recorte do Font Awesome do site
        from pathlib import Path
        icones = set((Path(portal_jogos.__file__).resolve().parent / "static/vendor/fontawesome-site/icones.txt")
                     .read_text().split())
        self.assertLessEqual({t["icone"] for t in portal_jogos.TEMA.values()}, icones)

    def test_a_pagina_mostra_o_atalho_da_estante_do_console(self):
        original = portal_jogos.cartoes

        def com_gba(dados):
            return original({**dados, "externos": [*dados["externos"],
                                                   self.externo("pokemon-firered", "gba", "Game Boy Advance")]})
        with mock.patch("core.portal_jogos.cartoes", side_effect=com_gba):
            resposta = self.portal()
        self.assertContains(resposta, 'href="?estante=gba#biblioteca"')
        self.assertContains(resposta, "Game Boy Advance")
        bib = resposta.context["dados_da_biblioteca"]
        self.assertIn("gba", [e["chave"] for e in bib["estantes"]])
        self.assertIn("nintendo", [t["chave"] for t in bib["temas"]])
