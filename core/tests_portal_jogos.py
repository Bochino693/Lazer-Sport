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


class ArteDoTopoTests(BasePortal):
    """A vitrine do alto: a arte larga de cada jogo da casa e a fila dos destaques."""

    def test_cada_jogo_da_casa_tem_a_arte_larga_e_ela_vai_na_vitrine(self):
        from . import portal_jogos

        for jogo in arena.JOGOS:
            with self.subTest(jogo=jogo["slug"]):
                self.assertIn(jogo["slug"], portal_jogos.TOPOS_DA_CASA)
        resposta = self.portal()
        html = resposta.content.decode()
        self.assertIn('class="pg-slide-topo"', html)
        self.assertIn("site/arena/capas/topo/", html)
        self.assertIn('class="pg-mini"', html)  # a fila dos destaques, no lugar dos pontinhos
        self.assertNotIn("{#", html)  # nenhum comentário do template vazando na página
        self.assertNotIn("{% comment", html)


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
    def abrir(self, slug):
        return self.client.post(reverse("jogos_abriu"), data=json.dumps({"jogo": slug}), content_type="application/json")

    def test_visitante_joga_uma_vez_cada_jogo_cadastrado(self):
        self.salvo()
        primeira = self.abrir("corrida-maluca").json()
        self.assertTrue(primeira["liberado"])
        self.assertTrue(primeira["ultima_gratis"])
        segunda = self.abrir("corrida-maluca").json()
        self.assertFalse(segunda["liberado"])
        self.assertIn(reverse("registrar"), segunda["cadastro"])
        self.assertIn("next=" + reverse("jogo", args=["corrida-maluca"]), segunda["cadastro"])
        # a partida conta uma vez (recarregar não infla o "Mais jogados")
        self.assertEqual(PartidasDoJogo.objects.get(slug="corrida-maluca").partidas, 1)

    def test_quem_tem_conta_joga_a_vontade(self):
        self.salvo()
        self.client.force_login(_cliente("bia", "bia@exemplo.com"))
        for _ in range(3):
            resposta = self.abrir("corrida-maluca").json()
            self.assertTrue(resposta["liberado"])
            self.assertFalse(resposta["ultima_gratis"])

    def test_o_jogo_da_casa_so_conta(self):
        slug = arena.JOGOS[0]["slug"]
        self.assertTrue(self.abrir(slug).json()["liberado"])
        self.assertTrue(self.abrir(slug).json()["liberado"])  # a regra da casa é do ranking.js
        self.assertEqual(PartidasDoJogo.objects.get(slug=slug).partidas, 1)

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
