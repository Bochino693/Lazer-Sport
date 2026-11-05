"""O cache público das telas do catálogo (core/home_cache.py).

O que estes testes protegem:

  * a segunda visita a uma tela do catálogo quase não consulta o banco --
    é o que faz uma instância pequena atender muita gente;
  * uma edição no cadastro aparece na visita seguinte, sem esperar TTL;
  * cada combinação de filtro, ordem e página tem a sua cópia;
  * o que é de UM visitante (lista de desejos, conta) nunca aparece para
    outro, e o estado dos favoritos continua certo com o cache ligado;
  * busca livre e página inventada não ocupam o cache.

Medido em docs/TESTE_DE_CARGA.md, seção "Depois do cache".
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .favoritos import COOKIE_DISPOSITIVO
from .home_cache import (
    CATALOG_PAGE_CACHE_PREFIX,
    chave_de_tela,
    dados_da_pagina,
    pagina_de_cache,
    versao_do_catalogo,
)
from .models import (
    BrinquedoClick,
    Brinquedos,
    CategoriaClick,
    CategoriasBrinquedos,
    ImagemBrinquedo,
    PecasReposicao,
)


def _chaves_de(tela):
    """As chaves de uma tela no LocMemCache (só para o teste olhar dentro)."""
    guardadas = getattr(cache, "_cache", {})
    marca = f"{CATALOG_PAGE_CACHE_PREFIX}:{tela}:"
    return [chave for chave in list(guardadas) if marca in chave]


class CacheDoCatalogoBase(TestCase):
    def setUp(self):
        cache.clear()
        self.categoria = CategoriasBrinquedos.objects.create(nome_categoria="Infláveis")
        self.loja = Brinquedos.objects.create(
            nome_brinquedo="Air Game Hockey",
            descricao="Mesa de air game",
            avaliacao=Decimal("4.80"),
            valor_brinquedo=Decimal("9800.00"),
            exibir_na_loja=True,
            voltz="220V",
        )
        self.orcamento = Brinquedos.objects.create(
            nome_brinquedo="Brinquedão Castelo",
            descricao="Estrutura de três andares",
            avaliacao=Decimal("5.00"),
            voltz="110V",
        )
        self.loja.categorias_brinquedos.add(self.categoria)
        self.orcamento.categorias_brinquedos.add(self.categoria)
        self.peca = PecasReposicao.objects.create(
            nome="Maneta do air game",
            descricao_peca="Maneta original",
            preco_venda=Decimal("120.00"),
        )
        self.url_categoria = reverse("categoria_detalhe", args=[self.categoria.pk])
        self.url_brinquedo = reverse("brinquedo_detalhe", args=[self.loja.pk])
        self.url_peca = reverse("reposicao_detalhe", args=[self.peca.pk])

    def tearDown(self):
        cache.clear()

    def consultas(self, url, **extra):
        with CaptureQueriesContext(connection) as capturadas:
            resposta = self.client.get(url, **extra)
        self.assertEqual(resposta.status_code, 200, url)
        return resposta, len(capturadas)

    def guardar_desejo(self, brinquedo=None):
        return self.client.post(
            reverse("alternar_favorito"),
            data={"tipo": "desejo", "produto": "brinquedo", "id": (brinquedo or self.loja).pk},
            content_type="application/json",
        )


class PoucasConsultasTests(CacheDoCatalogoBase):
    """A segunda visita anônima sai do cache."""

    def test_segunda_visita_anonima_quase_nao_consulta(self):
        # o contador de cliques da ficha e da categoria é a única consulta
        # que sobra: ele é por visita, de propósito
        telas = [
            (reverse("brinquedos"), 0),
            (self.url_categoria, 1),
            (self.url_brinquedo, 1),
            (reverse("pecas_reposicao"), 0),
            (self.url_peca, 0),
            (reverse("jogos"), 0),
        ]
        for url, maximo in telas:
            self.client.get(url)  # aquece
            resposta, consultas = self.consultas(url)
            self.assertLessEqual(consultas, maximo, f"{url}: {consultas} consultas na segunda visita")

    def test_filtros_do_catalogo_tambem_saem_do_cache(self):
        url = reverse("brinquedos") + "?disponibilidade=loja&ordenar=az&categoria=%d" % self.categoria.pk
        self.client.get(url)
        resposta, consultas = self.consultas(url)
        self.assertEqual(consultas, 0)
        self.assertContains(resposta, "Air Game Hockey")
        self.assertNotContains(resposta, "Brinquedão Castelo")

    def test_visitante_novo_nao_ganha_cookie_so_por_olhar(self):
        """A chave do aparelho nasce na primeira marcação, não na primeira olhada."""
        for url in (reverse("brinquedos"), self.url_brinquedo, reverse("pecas_reposicao"), self.url_peca):
            resposta = self.client.get(url)
            self.assertEqual(resposta.status_code, 200)
            self.assertNotIn(COOKIE_DISPOSITIVO, resposta.cookies, url)

    def test_o_clique_continua_sendo_contado_a_cada_visita(self):
        self.client.get(self.url_brinquedo)
        self.client.get(self.url_brinquedo)
        self.client.get(self.url_categoria)
        self.client.get(self.url_categoria)
        self.client.get(self.url_categoria)
        self.assertEqual(BrinquedoClick.objects.count(), 1)
        self.assertEqual(BrinquedoClick.objects.get().quantidade_click, 2)
        self.assertEqual(CategoriaClick.objects.count(), 1)
        self.assertEqual(CategoriaClick.objects.get().quantidade_click, 3)
        self.assertEqual(CategoriaClick.objects.get().nome_categoria, "Infláveis")


class InvalidacaoTests(CacheDoCatalogoBase):
    """Mudou o cadastro, a próxima visita já mostra."""

    def aquecer(self):
        for url in (reverse("brinquedos"), self.url_categoria, self.url_brinquedo, reverse("jogos")):
            self.assertEqual(self.client.get(url).status_code, 200)

    def test_editar_o_nome_aparece_na_visita_seguinte(self):
        self.aquecer()
        self.loja.nome_brinquedo = "Air Game Hockey Pro"
        self.loja.save()
        self.assertContains(self.client.get(reverse("brinquedos")), "Air Game Hockey Pro")
        self.assertContains(self.client.get(self.url_categoria), "Air Game Hockey Pro")
        self.assertContains(self.client.get(self.url_brinquedo), "Air Game Hockey Pro")

    def test_desativar_some_na_visita_seguinte(self):
        self.aquecer()
        self.orcamento.ativo = False
        self.orcamento.save()
        self.assertNotContains(self.client.get(reverse("brinquedos")), "Brinquedão Castelo")
        self.assertNotContains(self.client.get(self.url_categoria), "Brinquedão Castelo")
        self.assertEqual(
            self.client.get(reverse("brinquedo_detalhe", args=[self.orcamento.pk])).status_code,
            404,
        )

    def test_brinquedo_novo_entra_na_visita_seguinte(self):
        self.aquecer()
        novo = Brinquedos.objects.create(
            nome_brinquedo="Boliche Strike Kids", descricao="x", avaliacao=Decimal("5.00"),
        )
        novo.categorias_brinquedos.add(self.categoria)
        self.assertContains(self.client.get(reverse("brinquedos")), "Boliche Strike Kids")
        self.assertContains(self.client.get(self.url_categoria), "Boliche Strike Kids")

    def test_foto_categoria_e_peca_tambem_trocam_a_versao(self):
        antes = versao_do_catalogo()
        ImagemBrinquedo.objects.create(brinquedo=self.loja, imagem="brinquedos/x.jpg", tipo="perfil")
        depois_da_foto = versao_do_catalogo()
        self.assertNotEqual(antes, depois_da_foto)

        self.categoria.nome_categoria = "Infláveis gigantes"
        self.categoria.save()
        depois_da_categoria = versao_do_catalogo()
        self.assertNotEqual(depois_da_foto, depois_da_categoria)

        self.peca.nome = "Maneta nova"
        self.peca.save()
        self.assertNotEqual(depois_da_categoria, versao_do_catalogo())

    def test_a_versao_nao_muda_sozinha(self):
        """Sem edição, a versão é a mesma entre visitas (senão o cache nunca acerta)."""
        antes = versao_do_catalogo()
        self.client.get(reverse("brinquedos"))
        self.client.get(self.url_brinquedo)
        self.assertEqual(antes, versao_do_catalogo())


class ChavesDiferentesTests(CacheDoCatalogoBase):
    """Cada combinação de filtro, ordem e página tem a sua cópia."""

    def test_filtros_diferentes_nao_compartilham_cache(self):
        base = reverse("brinquedos")
        loja = self.client.get(base + "?disponibilidade=loja")
        self.assertContains(loja, "Air Game Hockey")
        self.assertNotContains(loja, "Brinquedão Castelo")

        orcamento = self.client.get(base + "?disponibilidade=orcamento")
        self.assertContains(orcamento, "Brinquedão Castelo")
        self.assertNotContains(orcamento, "Air Game Hockey")

        todos = self.client.get(base)
        self.assertContains(todos, "Air Game Hockey")
        self.assertContains(todos, "Brinquedão Castelo")

        az = self.client.get(base + "?ordenar=az").content.decode()
        za = self.client.get(base + "?ordenar=za").content.decode()
        self.assertLess(az.index("Air Game Hockey"), az.index("Brinquedão Castelo"))
        self.assertGreater(za.index("Air Game Hockey"), za.index("Brinquedão Castelo"))

    def test_categoria_com_filtro_de_disponibilidade(self):
        so_loja = self.client.get(self.url_categoria + "?disp=loja")
        self.assertContains(so_loja, "Air Game Hockey")
        self.assertNotContains(so_loja, "Brinquedão Castelo")
        so_consulta = self.client.get(self.url_categoria + "?disp=consulta")
        self.assertContains(so_consulta, "Brinquedão Castelo")
        self.assertNotContains(so_consulta, "Air Game Hockey")

    def test_a_chave_leva_a_versao_e_as_partes(self):
        a = chave_de_tela("brinquedos", "", "", "todos", "az", "1")
        b = chave_de_tela("brinquedos", "", "", "todos", "za", "1")
        self.assertNotEqual(a, b)
        self.assertEqual(a, chave_de_tela("brinquedos", "", "", "todos", "az", "1"))
        self.loja.save()  # versão nova
        self.assertNotEqual(a, chave_de_tela("brinquedos", "", "", "todos", "az", "1"))

    def test_busca_livre_e_faixa_de_preco_ficam_fora_do_cache(self):
        self.client.get(reverse("brinquedos"))
        guardadas = len(_chaves_de("brinquedos"))
        self.assertEqual(guardadas, 1)
        for sufixo in (
            "?q=hockey", "?preco_min=100", "?preco_max=100000",
            "?categoria=999999", "?voltagem=inventada",  # valores que não existem
        ):
            resposta = self.client.get(reverse("brinquedos") + sufixo)
            self.assertEqual(resposta.status_code, 200, sufixo)
        self.assertEqual(len(_chaves_de("brinquedos")), guardadas)

        # categoria e voltagem que existem ganham a sua cópia
        self.client.get(reverse("brinquedos") + f"?categoria={self.categoria.pk}")
        self.client.get(reverse("brinquedos") + "?voltagem=220v")
        self.assertEqual(len(_chaves_de("brinquedos")), guardadas + 2)

    def test_pagina_inventada_nao_ocupa_o_cache(self):
        self.client.get(reverse("brinquedos"))
        self.client.get(self.url_categoria)
        guardadas_lista = len(_chaves_de("brinquedos"))
        guardadas_categoria = len(_chaves_de("categoria"))
        for sufixo in ("?page=999", "?page=abc", "?page=0"):
            self.assertEqual(self.client.get(reverse("brinquedos") + sufixo).status_code, 200)
            self.assertEqual(self.client.get(self.url_categoria + sufixo).status_code, 200)
        self.assertEqual(len(_chaves_de("brinquedos")), guardadas_lista)
        self.assertEqual(len(_chaves_de("categoria")), guardadas_categoria)

    def test_pagina_do_paginador_sobrevive_ao_cache(self):
        from django.core.paginator import Paginator

        original = Paginator(list(range(30)), 12).page(2)
        refeita = pagina_de_cache(dados_da_pagina(original))
        self.assertEqual(list(refeita.object_list), list(range(12, 24)))
        self.assertEqual(refeita.number, 2)
        self.assertEqual(refeita.paginator.num_pages, 3)
        self.assertTrue(refeita.has_next())
        self.assertTrue(refeita.has_previous())
        self.assertEqual(refeita.start_index(), 13)
        self.assertEqual(refeita.end_index(), 24)
        self.assertEqual(list(refeita.paginator.page_range), [1, 2, 3])

        vazia = pagina_de_cache(dados_da_pagina(Paginator([], 12).page(1)))
        self.assertEqual(list(vazia.object_list), [])
        self.assertEqual(vazia.paginator.num_pages, 1)


class NadaVazaEntreVisitantesTests(CacheDoCatalogoBase):
    """O cache guarda só o que é de todo mundo."""

    def setUp(self):
        super().setUp()
        self.ana = self.cliente("ana", "Ana")
        self.bia = self.cliente("bia", "Bia")

    @staticmethod
    def cliente(nome, primeiro_nome):
        usuario = User.objects.create_user(nome, f"{nome}@exemplo.com", "Senha#12345", first_name=primeiro_nome)
        # Sem telefone o middleware manda completar o perfil e nenhuma
        # rota do site responde.
        perfil = usuario.perfil
        perfil.telefone = "(11)91234-5678"
        perfil.save(update_fields=["telefone"])
        return usuario

    def test_lista_de_desejos_de_uma_pessoa_nao_aparece_para_outra(self):
        self.client.force_login(self.ana)
        self.assertEqual(self.guardar_desejo().status_code, 200)

        de_ana = self.client.get(reverse("brinquedos"))
        self.assertIn(self.loja.pk, de_ana.context["fav_desejados"])
        self.assertContains(de_ana, 'aria-pressed="true"')
        self.assertContains(de_ana, "Olá, Ana")

        self.client.logout()
        self.client.force_login(self.bia)
        de_bia = self.client.get(reverse("brinquedos"))
        self.assertNotIn(self.loja.pk, de_bia.context["fav_desejados"])
        self.assertNotContains(de_bia, 'aria-pressed="true"')
        self.assertContains(de_bia, "Olá, Bia")
        self.assertNotContains(de_bia, "Olá, Ana")

        self.client.logout()
        anonimo = self.client.get(reverse("brinquedos"))
        self.assertEqual(set(anonimo.context["fav_desejados"]), set())
        self.assertNotContains(anonimo, 'aria-pressed="true"')
        self.assertNotContains(anonimo, "Olá, Ana")
        self.assertNotContains(anonimo, "Olá, Bia")

    def test_a_ficha_traz_o_estado_de_quem_olha(self):
        self.client.force_login(self.ana)
        self.guardar_desejo()
        de_ana = self.client.get(self.url_brinquedo)
        self.assertTrue(de_ana.context["favorito"]["desejado"])

        self.client.logout()
        self.client.force_login(self.bia)
        de_bia = self.client.get(self.url_brinquedo)
        self.assertFalse(de_bia.context["favorito"]["desejado"])
        self.assertFalse(de_bia.context["favorito"]["curtido"])

        self.client.logout()
        anonimo = self.client.get(self.url_brinquedo)
        self.assertFalse(anonimo.context["favorito"]["desejado"])

    def test_aparelhos_diferentes_nao_compartilham_marcacao(self):
        self.client.cookies[COOKIE_DISPOSITIVO] = "a" * 32
        self.guardar_desejo()
        self.assertIn(self.loja.pk, self.client.get(reverse("brinquedos")).context["fav_desejados"])

        self.client.cookies[COOKIE_DISPOSITIVO] = "b" * 32
        self.assertNotIn(self.loja.pk, self.client.get(reverse("brinquedos")).context["fav_desejados"])

    def test_usuario_logado_tambem_aproveita_o_cache(self):
        """O que é público é o mesmo para todos: logar não refaz o catálogo."""
        self.client.get(reverse("brinquedos"))
        self.client.force_login(self.ana)
        self.client.get(reverse("brinquedos"))  # aquece sessão e cabeçalho
        with CaptureQueriesContext(connection) as capturadas:
            resposta = self.client.get(reverse("brinquedos"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Olá, Ana")
        # O que sobra é só da pessoa (sessão, usuário, perfil, carrinho,
        # selos do cabeçalho, as marcações dela); o catálogo não é relido.
        tabelas_do_catalogo = (
            "core_brinquedos", "core_categoriasbrinquedos", "core_imagembrinquedo", "core_tagsbrinquedos",
        )
        do_catalogo = [
            q["sql"] for q in capturadas.captured_queries
            if any(tabela in q["sql"] for tabela in tabelas_do_catalogo)
        ]
        self.assertEqual(do_catalogo, [])
        self.assertLessEqual(len(capturadas), 10, f"{len(capturadas)} consultas para quem está logado")
