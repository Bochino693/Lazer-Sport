"""A tela vencida no cache sai na hora e se remonta em segundo plano (LEIA-ME-V10, seção 132)."""

from unittest import mock

from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.test import SimpleTestCase, override_settings

from core import aquecer, home_cache


@override_settings(HOME_CACHE_TTL=600, CATALOG_CACHE_TTL=600)
class RenovacaoTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_monta_uma_vez_e_depois_sai_do_cache(self):
        builder = mock.Mock(return_value={"n": 1})
        self.assertEqual(home_cache.com_renovacao("k", builder, 600), {"n": 1})
        self.assertEqual(home_cache.com_renovacao("k", builder, 600), {"n": 1})
        self.assertEqual(builder.call_count, 1)

    def test_vencido_sai_o_de_antes_e_se_remonta(self):
        builder = mock.Mock(side_effect=[{"n": 1}, {"n": 2}])
        home_cache.com_renovacao("k", builder, 600)
        agora = home_cache.time.time()
        with mock.patch.object(home_cache.time, "time", return_value=agora + 601):
            # quem chega leva a versão de antes, na hora
            self.assertEqual(home_cache.com_renovacao("k", builder, 600), {"n": 1})
        self.assertEqual(builder.call_count, 2)
        # a remontagem (aqui na mesma linha) já trocou o valor
        self.assertEqual(home_cache.com_renovacao("k", builder, 600), {"n": 2})

    def test_remontagem_que_falha_mantem_o_de_antes(self):
        builder = mock.Mock(side_effect=[{"n": 1}, RuntimeError("banco caiu")])
        home_cache.com_renovacao("k", builder, 600)
        agora = home_cache.time.time()
        with mock.patch.object(home_cache.time, "time", return_value=agora + 601), self.assertLogs("core.home_cache", "WARNING"):
            self.assertEqual(home_cache.com_renovacao("k", builder, 600), {"n": 1})
        self.assertEqual(cache.get("k")["_valor"], {"n": 1})
        self.assertIsNone(cache.get("k:renovando"))

    def test_uma_remontagem_por_vez(self):
        builder = mock.Mock(return_value={"n": 1})
        home_cache.com_renovacao("k", builder, 600)
        cache.add("k:renovando", 1, 3600)  # outra linha já está remontando
        agora = home_cache.time.time()
        with mock.patch.object(home_cache.time, "time", return_value=agora + 601):
            home_cache.com_renovacao("k", builder, 600)
        self.assertEqual(builder.call_count, 1)

    def test_valor_no_formato_antigo_conta_como_vazio(self):
        cache.set("k", {"antigo": True}, 600)
        self.assertEqual(home_cache.com_renovacao("k", lambda: {"novo": True}, 600), {"novo": True})

    def test_pagina_descartavel_nao_fica(self):
        self.assertEqual(home_cache.com_renovacao("k", lambda: {"x": 1, "_descartavel": True}, 600), {"x": 1})
        self.assertIsNone(cache.get("k"))

    def test_o_valor_guardado_vive_mais_que_o_prazo(self):
        home_cache.com_renovacao("k", lambda: {"n": 1}, 600)
        self.assertGreater(cache._expire_info[cache.make_and_validate_key("k")] - home_cache.time.time(), 600 * 5)

    def test_home_remontada_tira_o_html_e_pede_o_aquecimento_da_home(self):
        cache.set(make_template_fragment_key(home_cache.HOME_FRAGMENT_NAME), "html antigo", 600)
        builder = mock.Mock(side_effect=[{"n": 1}, {"n": 2}])
        home_cache.get_cached_home_context(builder)
        agora = home_cache.time.time()
        with mock.patch.object(aquecer, "agendar") as agendar, \
                mock.patch.object(home_cache.time, "time", return_value=agora + 601):
            self.assertEqual(home_cache.get_cached_home_context(builder), {"n": 1})
        self.assertIsNone(cache.get(make_template_fragment_key(home_cache.HOME_FRAGMENT_NAME)))
        agendar.assert_called_once()
        self.assertEqual(agendar.call_args.kwargs["paginas"], ("/",))
        self.assertEqual(home_cache.get_cached_home_context(builder), {"n": 2})

    def test_pagina_do_catalogo_tambem_se_remonta(self):
        builder = mock.Mock(side_effect=[{"itens": [1]}, {"itens": [1, 2]}])
        home_cache.get_cached_catalog_page("lista", ("a",), builder)
        agora = home_cache.time.time()
        with mock.patch.object(home_cache.time, "time", return_value=agora + 601):
            self.assertEqual(home_cache.get_cached_catalog_page("lista", ("a",), builder), {"itens": [1]})
        self.assertEqual(home_cache.get_cached_catalog_page("lista", ("a",), builder), {"itens": [1, 2]})


@override_settings(AQUECER_CACHE=True)
class AquecimentoSomaTelasTests(SimpleTestCase):
    def test_aquecer_so_a_home_nao_cancela_o_aquecimento_completo(self):
        with mock.patch.object(aquecer.threading, "Timer") as timer, mock.patch.object(aquecer, "aquecer") as rodar:
            aquecer.agendar(motivo="catálogo mudou")
            aquecer.agendar(atraso=0.5, motivo="home remontada", paginas=("/",))
            disparo = timer.call_args.kwargs.get("kwargs") or timer.call_args.args[2]
            aquecer._disparar(**disparo)
        rodar.assert_called_once()
        self.assertEqual(list(rodar.call_args.args[1]), list(aquecer.PAGINAS))
        self.assertEqual(aquecer._pendentes, set())
