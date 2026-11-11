"""As telas públicas não podem voltar a ficar lentas sem ninguém ver.

O QUE ESTAVA LENTO (LEIA-ME-V10, seção 63). Com o banco no Supabase, cada
consulta é uma viagem pela rede -- no ar, de 0,15 a 0,25 s cada. A Arena
fazia dez consultas por visita e não tinha cache; a Loja, treze; o combo e
a promoção, cinco; a home, para se montar, 102 (uma por brinquedo, só para
ler o ajuste de curtidas); o portal de jogos, onze a cada minuto, uma por
jogo para achar o campeão. E o contador de cliques fazia a ficha do
brinquedo, que já saía do cache, esperar o banco do mesmo jeito.

O QUE ESTES TESTES PROTEGEM:

  * a MONTAGEM de cada tela -- a primeira visita depois de uma edição --
    não faz uma consulta por item: com 3 ou com 23 brinquedos, o mesmo
    número de consultas (padrão de sistema_interno/tests_desempenho.py);
  * a SEGUNDA visita de quem chega sem conta não vai ao banco, nem pelo
    contador de cliques (que vai para a linha de fundo, core/cliques.py);
  * o painel edita, a próxima visita já mostra -- o cache novo segue a
    versão do catálogo que os signals apagam;
  * as contas que mudaram de lugar (o campeão de cada jogo, os selos do
    cabeçalho, a galeria da ficha) dão os mesmos números de antes.
"""

from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from . import cliques, ranking
from .home_cache import invalidate_public_catalog_caches
from .models import (
    BrinquedoClick,
    Brinquedos,
    BrinquedosProjeto,
    Carrinho,
    CategoriaClick,
    CategoriaPeca,
    CategoriasBrinquedos,
    ComboClick,
    Combos,
    ComponenteBrinquedo,
    Estabelecimentos,
    Eventos,
    Favorito,
    ImagemBrinquedo,
    ImagemEvento,
    ImagemPeca,
    ImagemProjetoBrinquedo,
    ItemCarrinho,
    JogoCadastrado,
    Manutencao,
    ObjetoTresD,
    PecasReposicao,
    Pedido,
    Projetos,
    PromocaoClick,
    Promocoes,
    RecordeJogo,
    TagsBrinquedos,
)

TIPOS_DE_FOTO = ("perfil", "lado_direito", "verso", "lado_esquerdo")
INTERNO = {"HTTP_HOST": "interno.testserver"}


class CatalogoDeTeste:
    """Um catálogo com tudo o que as telas desenham: fotos, categorias, tags, 3D, combos, peças."""

    def preparar_catalogo(self):
        cache.clear()
        self.categoria = CategoriasBrinquedos.objects.create(nome_categoria="Fliperamas", imagem_categoria="categorias/f.jpg")
        self.tag = TagsBrinquedos.objects.create(nome_tags="arcade")
        self.categoria_peca = CategoriaPeca.objects.create(nome_categoria_peca="Botões")
        self.parceiro = Estabelecimentos.objects.create(nome_estabelecimento="Shopping Norte")

    def povoar(self, quantos, inicio=0):
        """`quantos` brinquedos com galeria, cada um com o seu combo, promoção, peça, evento, projeto e jogo."""
        for i in range(inicio, inicio + quantos):
            brinquedo = Brinquedos.objects.create(
                nome_brinquedo=f"Fliperama Retrô {i}", descricao="Gabinete com 2 mil jogos",
                imagem_brinquedo=f"brinquedos/b{i}.jpg", avaliacao=Decimal("4.50"),
                valor_brinquedo=Decimal("5000") + i, exibir_na_loja=True, voltz="220V",
                altura_m=Decimal("1.80"), largura_m=Decimal("0.80"), profundidade_m=Decimal("0.90"),
            )
            brinquedo.categorias_brinquedos.add(self.categoria)
            brinquedo.tags.add(self.tag)
            brinquedo.estabelecimentos.add(self.parceiro)
            for ordem, tipo in enumerate(TIPOS_DE_FOTO, start=1):
                ImagemBrinquedo.objects.create(
                    brinquedo=brinquedo, imagem=f"brinquedos/galeria/b{i}-{tipo}.jpg", tipo=tipo, ordem=ordem,
                )
            ObjetoTresD.objects.create(
                brinquedo=brinquedo, arquivo_estatico="site/arena/modelos/strike-kids.glb", medidas=[1.8, 0.8, 0.9],
            )
            Favorito.objects.create(tipo=Favorito.Tipo.CURTIDA, brinquedo=brinquedo, dispositivo=f"{i:032d}")

            combo = Combos.objects.create(descricao=f"Combo {i}", valor_combo=Decimal("9000"), imagem_combo=f"combos/c{i}.jpg")
            combo.brinquedos.add(brinquedo)
            Promocoes.objects.create(
                descricao=f"Promoção {i}", brinquedos=brinquedo, preco_promocao=Decimal("4000"),
                imagem_promocao=f"promocoes/p{i}.jpg",
            )
            peca = PecasReposicao.objects.create(nome=f"Botão {i}", descricao_peca="Botão arcade", preco_venda=Decimal("30"))
            peca.categoria_peca.add(self.categoria_peca)
            ImagemPeca.objects.create(peca_reposicao=peca, imagem=f"pecas/p{i}.jpg", ordem=1)

            evento = Eventos.objects.create(titulo=f"Festa {i}", descricao="x")
            evento.brinquedos.add(brinquedo)
            ImagemEvento.objects.create(evento=evento, imagem=f"eventos/e{i}.jpg")
            projetado = BrinquedosProjeto.objects.create(nome_brinquedo_projeto=f"Projeto {i}", descricao="x")
            ImagemProjetoBrinquedo.objects.create(brinquedo=projetado, imagem=f"projetos/pr{i}.jpg")
            Projetos.objects.create(titulo=f"Projeto {i}", descricao="x", brinquedo_projetado=projetado)

            JogoCadastrado.objects.create(
                nome=f"Jogo {i}", slug=f"jogo-{i}", capa=f"jogos/capas/j{i}.jpg", endereco="https://exemplo.com/jogo/",
            )


class MontagemNaoCresceComOsItensTests(CatalogoDeTeste, TestCase):
    """A primeira visita depois de uma edição monta a tela: a conta não pode crescer com o catálogo.

    É o caminho que o visitante paga sempre que alguém mexe no cadastro (o
    cache inteiro morre junto com a versão do catálogo). Uma consulta por
    item ali não aparece em teste nenhum de tela -- a página abre certa --,
    só no relógio de quem chega depois de uma edição.
    """

    #: Os agregados e os prefetch saltam quando a lista está vazia; a folga cobre isso.
    FOLGA = 2

    def setUp(self):
        self.preparar_catalogo()

    def montagem(self, rota):
        """As consultas da tela com o cache do catálogo vazio (a primeira visita depois de uma edição)."""
        invalidate_public_catalog_caches()
        self.client.cookies.clear()
        with CaptureQueriesContext(connection) as capturadas:
            resposta = self.client.get(rota)
        self.assertEqual(resposta.status_code, 200, rota)
        return len(capturadas)

    def conferir(self, *rotas):
        self.povoar(3)
        poucas = {}
        for rota in rotas:
            self.montagem(rota)  # a primeira de todas também enche os caches por tempo (ranking, painel)
            poucas[rota] = self.montagem(rota)
        self.povoar(20, inicio=3)
        for rota in rotas:
            muitas = self.montagem(rota)
            self.assertLessEqual(
                muitas, poucas[rota] + self.FOLGA,
                f"{rota}: {poucas[rota]} consultas com 3 brinquedos e {muitas} com 23 -- a montagem consulta por item.",
            )

    def test_home(self):
        # eram 102 com 61 brinquedos: o ajuste de curtidas fora do `only()`
        self.conferir(reverse("home"))

    def test_arena(self):
        self.conferir(reverse("arena"))

    def test_loja(self):
        self.conferir(reverse("loja"))

    def test_catalogo(self):
        self.conferir(reverse("brinquedos"))

    def test_categoria(self):
        self.conferir(reverse("categoria_detalhe", args=[self.categoria.pk]))

    def test_portal_de_jogos(self):
        self.conferir(reverse("jogos"))

    def test_pecas(self):
        self.conferir(reverse("pecas_reposicao"))

    def test_eventos_e_projetos(self):
        self.conferir(reverse("eventos"), reverse("projetos"))

    def test_parceiros(self):
        # o total de brinquedos de cada parceiro era um COUNT por cartão (dois, com o plural)
        for i in range(8):
            Estabelecimentos.objects.create(nome_estabelecimento=f"Parceiro {i}")
        self.conferir(reverse("estabelecimentos"))


class FichasNaoCrescemComOQueTrazemTests(CatalogoDeTeste, TestCase):
    """A ficha do brinquedo e a do combo: a galeria, a composição e os brinquedos do combo vêm por conjunto."""

    def setUp(self):
        self.preparar_catalogo()
        self.povoar(12)
        self.brinquedos = list(Brinquedos.objects.order_by("id"))

    def montagem(self, rota):
        invalidate_public_catalog_caches()
        with CaptureQueriesContext(connection) as capturadas:
            resposta = self.client.get(rota)
        self.assertEqual(resposta.status_code, 200, rota)
        return len(capturadas)

    def test_ficha_com_um_ou_com_dez_componentes(self):
        conjunto, um, outro = self.brinquedos[0], self.brinquedos[1], self.brinquedos[2]
        ComponenteBrinquedo.objects.create(conjunto=conjunto, item=um)
        ComponenteBrinquedo.objects.create(conjunto=outro, item=conjunto)
        poucas = self.montagem(reverse("brinquedo_detalhe", args=[conjunto.pk]))
        for ordem, item in enumerate(self.brinquedos[3:12], start=1):
            ComponenteBrinquedo.objects.create(conjunto=conjunto, item=item, ordem=ordem)
        muitas = self.montagem(reverse("brinquedo_detalhe", args=[conjunto.pk]))
        self.assertLessEqual(muitas, poucas)

    def test_a_composicao_continua_nas_duas_direcoes_e_em_ordem(self):
        espaco, gol, swish = self.brinquedos[0], self.brinquedos[1], self.brinquedos[2]
        ComponenteBrinquedo.objects.create(conjunto=espaco, item=swish, quantidade=2, ordem=2)
        ComponenteBrinquedo.objects.create(conjunto=espaco, item=gol, quantidade=3, ordem=1)
        ficha = self.client.get(reverse("brinquedo_detalhe", args=[espaco.pk])).context
        self.assertEqual([(c["nome"], c["quantidade"]) for c in ficha["componentes"]], [(gol.nome_brinquedo, 3), (swish.nome_brinquedo, 2)])
        self.assertEqual(ficha["faz_parte_de"], [])
        do_gol = self.client.get(reverse("brinquedo_detalhe", args=[gol.pk])).context
        self.assertEqual([c["nome"] for c in do_gol["faz_parte_de"]], [espaco.nome_brinquedo])
        self.assertEqual(do_gol["componentes"], [])

    def test_combo_com_um_ou_com_dez_brinquedos(self):
        combo = Combos.objects.create(descricao="Combo grande", valor_combo=Decimal("1000"))
        combo.brinquedos.add(self.brinquedos[0])
        poucas = self.montagem(reverse("combo", args=[combo.pk]))
        combo.brinquedos.add(*self.brinquedos[1:11])
        muitas = self.montagem(reverse("combo", args=[combo.pk]))
        self.assertLessEqual(muitas, poucas)

    def test_a_galeria_da_ficha_sai_do_prefetch_com_a_mesma_regra(self):
        brinquedo = self.brinquedos[0]
        ImagemBrinquedo.objects.filter(brinquedo=brinquedo, tipo="verso").update(tipo=None)
        pela_consulta = [foto.pk for foto in Brinquedos.objects.get(pk=brinquedo.pk).imagens_ordenadas]
        com_prefetch = Brinquedos.objects.prefetch_related("imagens_brinquedo").get(pk=brinquedo.pk)
        with CaptureQueriesContext(connection) as capturadas:
            pelo_prefetch = [foto.pk for foto in com_prefetch.imagens_ordenadas]
        self.assertEqual(len(capturadas), 0)
        self.assertEqual(pelo_prefetch, pela_consulta)
        self.assertEqual(len(pelo_prefetch), 3)


@override_settings(CLIQUES_EM_SEGUNDO_PLANO=True)
class SegundaVisitaSemBancoTests(CatalogoDeTeste, TestCase):
    """Quem chega sem conta e sem cookie (como o curl, como o Google) não espera o banco na segunda visita.

    No ar, com o banco pela rede, cada consulta custava 0,15-0,25 s; a página
    que não consulta nada não paga nem a conferência da conexão.
    """

    def setUp(self):
        self.preparar_catalogo()
        self.povoar(4)
        self.brinquedo = Brinquedos.objects.order_by("id").first()
        self.combo = Combos.objects.order_by("id").first()
        self.promocao = Promocoes.objects.order_by("id").first()
        # a linha de fundo não sobe no teste: a fila é gravada à mão, abaixo
        parar = mock.patch("core.cliques._garantir_linha")
        parar.start()
        self.addCleanup(parar.stop)
        self.addCleanup(cliques.gravar_pendentes)

    def visita(self, rota):
        self.client.cookies.clear()
        with CaptureQueriesContext(connection) as capturadas:
            resposta = self.client.get(rota)
        self.assertEqual(resposta.status_code, 200, rota)
        return capturadas

    def test_as_telas_principais_saem_inteiras_do_cache(self):
        rotas = [
            reverse("home"), reverse("arena"), reverse("loja"), reverse("brinquedos"),
            reverse("categoria_detalhe", args=[self.categoria.pk]),
            reverse("brinquedo_detalhe", args=[self.brinquedo.pk]),
            reverse("combo", args=[self.combo.pk]), reverse("promocao", args=[self.promocao.pk]),
            reverse("jogos"), reverse("eventos"), reverse("projetos"), reverse("pecas_reposicao"),
        ]
        for rota in rotas:
            self.visita(rota)  # monta e guarda
        for rota in rotas:
            consultas = self.visita(rota)
            self.assertEqual(
                len(consultas), 0,
                f"{rota}: a segunda visita foi ao banco -- {[q['sql'][:90] for q in consultas.captured_queries]}",
            )

    def test_o_clique_continua_contado_por_visita(self):
        for _ in range(3):
            self.visita(reverse("brinquedo_detalhe", args=[self.brinquedo.pk]))
            self.visita(reverse("categoria_detalhe", args=[self.categoria.pk]))
            self.visita(reverse("combo", args=[self.combo.pk]))
            self.visita(reverse("promocao", args=[self.promocao.pk]))
        self.assertEqual(BrinquedoClick.objects.count(), 0, "o clique tinha de esperar a linha de fundo")
        self.assertEqual(cliques.gravar_pendentes(), 12)
        self.assertEqual(BrinquedoClick.objects.get().quantidade_click, 3)
        categoria = CategoriaClick.objects.get()
        self.assertEqual((categoria.quantidade_click, categoria.nome_categoria), (3, "Fliperamas"))
        combo = ComboClick.objects.get()
        self.assertEqual((combo.quantidade_click, combo.descricao_combo, combo.valor_combo), (3, "Combo 0", Decimal("9000")))
        self.assertEqual(PromocaoClick.objects.get().quantidade_click, 3)

        # a linha existente é somada, e não duplicada
        self.visita(reverse("brinquedo_detalhe", args=[self.brinquedo.pk]))
        self.assertEqual(cliques.gravar_pendentes(), 1)
        self.assertEqual(BrinquedoClick.objects.get().quantidade_click, 4)

    def test_a_loja_nao_da_cookie_de_aparelho_a_quem_so_olhou(self):
        resposta = self.client.get(reverse("loja"))
        self.assertNotIn("ls_dispositivo", resposta.cookies)


class CliquesNaHoraForaDaProducaoTests(CatalogoDeTeste, TestCase):
    """Sem a linha de fundo (testes, computador), o UPDATE acontece dentro da visita, como antes."""

    def setUp(self):
        self.preparar_catalogo()
        self.povoar(1)

    def test_grava_na_hora(self):
        combo = Combos.objects.get()
        self.client.get(reverse("combo", args=[combo.pk]))
        self.client.get(reverse("combo", args=[combo.pk]))
        self.assertEqual(ComboClick.objects.get().quantidade_click, 2)
        self.assertEqual(cliques.gravar_pendentes(), 0)


class CachePublicoAcompanhaOPainelTests(CatalogoDeTeste, TestCase):
    """O painel grava, a próxima visita já mostra: as telas novas no cache seguem a versão do catálogo."""

    def setUp(self):
        self.preparar_catalogo()
        self.povoar(2)
        self.equipe = User.objects.create_superuser("criacao", "criacao@exemplo.com", "x")
        self.brinquedos = list(Brinquedos.objects.order_by("id"))

    def no_painel(self, rota, dados):
        self.client.force_login(self.equipe)
        resposta = self.client.post(rota, dados, **INTERNO)
        self.assertIn(resposta.status_code, (200, 302), resposta.content[:300])
        self.client.logout()

    def test_combo_editado_no_painel(self):
        combo = Combos.objects.order_by("id").first()
        url = reverse("combo", args=[combo.pk])
        self.assertContains(self.client.get(url), "Combo 0")
        self.assertContains(self.client.get(reverse("loja")), "Combo 0")
        self.no_painel("/site/combos/", {
            "acao": "editar", "combo_id": combo.pk, "descricao": "Combo de Natal",
            "brinquedos": [b.pk for b in self.brinquedos], "valor_combo": "8.500,00", "ativo": "on",
        })
        pagina = self.client.get(url)
        self.assertContains(pagina, "Combo de Natal")
        self.assertEqual(pagina.context["combo"].total_original, sum(b.valor_brinquedo for b in self.brinquedos))
        self.assertContains(self.client.get(reverse("loja")), "Combo de Natal")

    def test_promocao_editada_no_painel(self):
        promocao = Promocoes.objects.order_by("id").first()
        url = reverse("promocao", args=[promocao.pk])
        self.assertContains(self.client.get(url), "Promoção 0")
        self.no_painel("/site/promocoes/", {
            "acao": "editar", "promocao_id": promocao.pk, "descricao": "Queima de estoque",
            "brinquedos": self.brinquedos[1].pk, "preco_promocao": "3.900,00", "ativo": "on",
        })
        pagina = self.client.get(url)
        self.assertContains(pagina, "Queima de estoque")
        self.assertContains(pagina, self.brinquedos[1].nome_brinquedo)
        self.assertContains(self.client.get(reverse("loja")), "Queima de estoque")

    def test_combo_desligado_some_da_loja(self):
        combo = Combos.objects.order_by("id").first()
        self.assertContains(self.client.get(reverse("loja")), "Combo 0")
        self.no_painel("/site/combos/", {
            "acao": "editar", "combo_id": combo.pk, "descricao": "Combo 0",
            "brinquedos": [self.brinquedos[0].pk], "valor_combo": "9.000,00",
        })
        self.assertNotContains(self.client.get(reverse("loja")), "Combo 0")

    def test_arena_acompanha_o_cadastro(self):
        maquinas = lambda: {m["nome"] for m in self.client.get(reverse("arena")).context["arena_dados"]["maquinas"]}  # noqa: E731
        self.assertIn("Fliperama Retrô 0", maquinas())
        brinquedo = self.brinquedos[0]
        brinquedo.nome_brinquedo = "Fliperama Turbo"
        brinquedo.save()
        self.assertIn("Fliperama Turbo", maquinas())
        objeto = brinquedo.objeto_3d
        objeto.exibir_na_arena = False
        objeto.save()
        self.assertNotIn("Fliperama Turbo", maquinas())
        # o "Monte seu espaço" vem do mesmo cache e acompanha junto
        itens = {i["nome"] for i in self.client.get(reverse("arena")).context["projeto_dados"]["itens"]}
        self.assertIn("Fliperama Turbo", itens)

    def test_eventos_e_projetos_acompanham_o_cadastro(self):
        self.assertContains(self.client.get(reverse("eventos")), "Festa 0")
        evento = Eventos.objects.get(titulo="Festa 0")
        evento.titulo = "Aniversário do Pedro"
        evento.save()
        self.assertContains(self.client.get(reverse("eventos")), "Aniversário do Pedro")
        Projetos.objects.create(
            titulo="Parque do clube", descricao="x",
            brinquedo_projetado=BrinquedosProjeto.objects.create(nome_brinquedo_projeto="Parque", descricao="x"),
        )
        self.assertContains(self.client.get(reverse("projetos")), "Parque do clube")

    def test_loja_do_visitante_identificado_marca_o_que_ele_guardou(self):
        self.client.cookies["ls_dispositivo"] = "a" * 32
        brinquedo = self.brinquedos[0]
        Favorito.objects.create(tipo=Favorito.Tipo.DESEJO, brinquedo=brinquedo, dispositivo="a" * 32)
        itens = {(i["tipo"], i["id"]): i for i in self.client.get(reverse("loja")).context["itens_loja"]}
        self.assertTrue(itens[("brinquedo", brinquedo.pk)]["fav_desejado"])
        self.assertFalse(itens[("brinquedo", self.brinquedos[1].pk)]["fav_desejado"])
        # outro aparelho, a mesma loja do cache, sem as marcas do primeiro
        self.client.cookies["ls_dispositivo"] = "b" * 32
        itens = self.client.get(reverse("loja")).context["itens_loja"]
        self.assertFalse(any(i.get("fav_desejado") for i in itens))


class CampeoesDosJogosTests(TestCase):
    """O campeão de cada jogo sai da leitura do ranking geral -- e é o mesmo de antes."""

    def setUp(self):
        cache.clear()
        self.pessoas = [User.objects.create_user(f"j{i}", f"j{i}@exemplo.com", "x", first_name=f"Pessoa{i}", last_name="Silva") for i in range(4)]

    def test_o_campeao_e_o_primeiro_do_ranking_do_jogo(self):
        RecordeJogo.objects.create(usuario=self.pessoas[0], jogo="strike-kids", pontos=200, partidas=1)
        RecordeJogo.objects.create(usuario=self.pessoas[1], jogo="strike-kids", pontos=280, partidas=1)
        RecordeJogo.objects.create(usuario=self.pessoas[2], jogo="hit-music", pontos=9100, partidas=1)
        RecordeJogo.objects.create(usuario=self.pessoas[3], jogo="hit-music", pontos=0, partidas=1)
        campeoes = ranking.campeoes()
        for slug in ("strike-kids", "hit-music"):
            cache.clear()
            self.assertEqual(campeoes[slug], ranking.ranking_do_jogo(slug, 1)[0], slug)
        self.assertNotIn("dragon-bowling", campeoes)

    def test_o_portal_acha_todos_os_campeoes_numa_leitura(self):
        from . import arena

        for i, jogo in enumerate(arena.JOGOS):
            RecordeJogo.objects.create(usuario=self.pessoas[i % 4], jogo=jogo["slug"], pontos=100 + i, partidas=1)
        from . import portal_jogos

        cache.clear()
        portal_jogos.vivo()  # o "quem jogou hoje" é de outro cache, de dois minutos
        with CaptureQueriesContext(connection) as capturadas:
            portal = self.client.get(reverse("jogos")).context["ranking_portal"]
        do_recorde = [q for q in capturadas.captured_queries if "core_recordejogo" in q["sql"]]
        self.assertEqual(len(do_recorde), 1, [q["sql"][:80] for q in do_recorde])
        self.assertEqual(len(portal["campeoes"]), len(arena.JOGOS))

    def test_recorde_novo_troca_o_campeao_na_hora(self):
        RecordeJogo.objects.create(usuario=self.pessoas[0], jogo="lazer-shot", pontos=500, partidas=1)
        self.assertEqual(ranking.campeoes()["lazer-shot"]["usuario"], self.pessoas[0].pk)
        ranking._gravar(self.pessoas[1], "lazer-shot", 900)
        self.assertEqual(ranking.campeoes()["lazer-shot"]["usuario"], self.pessoas[1].pk)

    def test_o_ranking_do_jogo_nao_fica_cortado_no_campeao(self):
        # pedir só o primeiro guardava a lista de UM, e a página do jogo
        # mostrava o ranking com uma linha por até um minuto
        for i, pessoa in enumerate(self.pessoas):
            RecordeJogo.objects.create(usuario=pessoa, jogo="super-boxing", pontos=100 * (i + 1), partidas=1)
        self.assertEqual(len(ranking.ranking_do_jogo("super-boxing", 1)), 1)
        self.assertEqual([r["pontos"] for r in ranking.ranking_do_jogo("super-boxing")], [400, 300, 200, 100])


class SelosDoCabecalhoTests(TestCase):
    """Carrinho, manutenções, lista de desejos e pedidos de quem está logado: um SELECT, os mesmos números."""

    def setUp(self):
        cache.clear()
        self.pessoa = User.objects.create_user("ana", "ana@exemplo.com", "Senha#12345", first_name="Ana")
        self.perfil = self.pessoa.perfil
        self.perfil.telefone = "(11)91234-5678"
        self.perfil.save(update_fields=["telefone"])
        brinquedo = Brinquedos.objects.create(nome_brinquedo="Air Game", descricao="x", avaliacao=Decimal("5"))
        outro = Brinquedos.objects.create(nome_brinquedo="Pebolim", descricao="x", avaliacao=Decimal("5"))
        tipo = ContentType.objects.get_for_model(Brinquedos)
        primeiro = Carrinho.objects.create(cliente=self.perfil)
        segundo = Carrinho.objects.create(cliente=self.perfil)
        ItemCarrinho.objects.create(carrinho=primeiro, content_type=tipo, object_id=brinquedo.pk, quantidade=2)
        ItemCarrinho.objects.create(carrinho=primeiro, content_type=tipo, object_id=outro.pk, quantidade=3)
        ItemCarrinho.objects.create(carrinho=segundo, content_type=tipo, object_id=brinquedo.pk, quantidade=9)
        for status in ("P", "P", "A", "C"):
            Manutencao.objects.create(usuario=self.perfil, status=status, descricao="x", telefone_contato="11")
        Favorito.objects.create(tipo=Favorito.Tipo.DESEJO, brinquedo=brinquedo, usuario=self.pessoa)
        Favorito.objects.create(tipo=Favorito.Tipo.DESEJO, brinquedo=outro, usuario=self.pessoa)
        Favorito.objects.create(tipo=Favorito.Tipo.CURTIDA, brinquedo=outro, usuario=self.pessoa)
        for status in ("pago", "em_preparacao", "cancelado", "finalizado"):
            Pedido.objects.create(cliente=self.perfil, status=status)
        self.client.force_login(self.pessoa)

    def test_os_numeros_sao_os_de_antes_numa_consulta(self):
        self.client.get(reverse("brinquedos"))  # aquece o catálogo e o cabeçalho
        with CaptureQueriesContext(connection) as capturadas:
            resposta = self.client.get(reverse("brinquedos"))
        contexto = resposta.context
        # o PRIMEIRO carrinho (2 + 3), não o segundo
        self.assertEqual(contexto["carrinho_total_itens"], 5)
        self.assertEqual(
            (contexto["manutencao_pendente"], contexto["manutencao_andamento"], contexto["manutencao_abertas"]), (2, 1, 3),
        )
        self.assertEqual(contexto["total_lista_desejos"], 2)
        self.assertEqual(contexto["total_pedidos_ativos"], 2)
        # (a consulta das marcas do catálogo -- o que a Ana guardou, para
        # pintar as estrelas dos cartões -- é da página, e fica de fora)
        dos_selos = [
            q["sql"] for q in capturadas.captured_queries
            if any(t in q["sql"] for t in ("core_carrinho", "core_manutencao", "core_pedido"))
            or ('COUNT(' in q["sql"] and '"core_favorito"' in q["sql"])
        ]
        self.assertEqual(len(dos_selos), 1, dos_selos)

    def test_sem_nada_tudo_zero(self):
        vazia = User.objects.create_user("bia", "bia@exemplo.com", "Senha#12345")
        vazia.perfil.telefone = "(11)91234-0000"
        vazia.perfil.save(update_fields=["telefone"])
        self.client.force_login(vazia)
        contexto = self.client.get(reverse("brinquedos")).context
        self.assertEqual(
            [contexto[c] for c in ("carrinho_total_itens", "manutencao_abertas", "total_lista_desejos", "total_pedidos_ativos")],
            [0, 0, 0, 0],
        )
        self.assertFalse(contexto["tem_manutencao"])
        self.assertFalse(contexto["tem_pedidos_ativos"])


class MemoriaDoProcessoTests(TestCase):
    """O que passou a ser guardado na memória do processo dá a mesma resposta de antes."""

    def test_a_url_do_cloudinary_guardada_e_a_mesma(self):
        from .fotos import url_da_imagem

        brinquedo = Brinquedos(nome_brinquedo="x", descricao="x", avaliacao=1, imagem_brinquedo="brinquedos/foto.jpg")
        self.assertEqual(url_da_imagem(brinquedo.imagem_brinquedo), brinquedo.imagem_brinquedo.url)
        self.assertEqual(url_da_imagem(brinquedo.imagem_brinquedo), brinquedo.imagem_brinquedo.url)
        self.assertEqual(url_da_imagem(None), "")
        self.assertEqual(url_da_imagem("https://exemplo.com/a.jpg"), "https://exemplo.com/a.jpg")

    def test_o_glb_do_site_e_lido_uma_vez_e_cada_um_recebe_a_sua_copia(self):
        from . import objetos_3d

        caminho = "site/arena/modelos/strike-kids.glb"
        primeira = objetos_3d.ler_glb_do_site(caminho)
        self.assertEqual(len(primeira["medidas"]), 3)
        primeira["medidas"].append("estragado")
        with mock.patch("builtins.open", side_effect=AssertionError("leu o disco de novo")):
            segunda = objetos_3d.ler_glb_do_site(caminho)
        self.assertEqual(len(segunda["medidas"]), 3)

    def test_as_regras_da_arena_continuam_as_mesmas(self):
        from . import arena

        self.assertEqual(arena._normalizar("Pebolim-Eletrônico"), "pebolim eletronico")
        self.assertEqual(arena._normalizar(None), "")
        self.assertTrue(arena._contem("basquete kids", "basquete"))
        self.assertFalse(arena._contem("white", "hit"))
        self.assertEqual(arena.modelo_3d("Trampolim de Enterrada"), "cama_elastica")
        self.assertEqual(arena.modelo_3d("Uiii", ["Eletrônicos"]), "fliperama")
        self.assertEqual(arena.jogo_da_maquina("Dragon Bowling Rosa"), "dragon-bowling")
