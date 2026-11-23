"""Os avisos entre os processos do site (LEIA-ME-V10, seção 131)."""

import time
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError
from django.test import RequestFactory, TestCase, override_settings

from core import espelho_midia, fotos, sinais
from core.home_cache import HOME_CONTEXT_CACHE_KEY
from core.models import SinalDoSite


class EstadoLimpo(TestCase):
    """Cada teste começa como um processo que acabou de subir."""

    def setUp(self):
        self._antes = dict(sinais._estado)
        sinais._estado.update({"pid": None, "thread": None, "visto": {}, "inicio": time.time_ns(), "ultima": None})
        cache.clear()

    def tearDown(self):
        sinais._estado.clear()
        sinais._estado.update(self._antes)
        cache.clear()

    def outro_processo_avisa(self, chave=sinais.MIDIA):
        """O que o processo da restauração grava no banco."""
        with self.captureOnCommitCallbacks(execute=True):
            sinais.avisar(chave)
        return SinalDoSite.objects.get(chave=chave).versao


class AvisarTests(EstadoLimpo):
    def test_o_aviso_grava_uma_versao_nova_a_cada_vez(self):
        primeira = self.outro_processo_avisa()
        segunda = self.outro_processo_avisa()
        self.assertGreater(segunda, primeira)
        self.assertEqual(SinalDoSite.objects.filter(chave=sinais.MIDIA).count(), 1)

    def test_o_aviso_so_vale_depois_do_commit(self):
        with self.captureOnCommitCallbacks(execute=False) as pendentes:
            sinais.avisar(sinais.MIDIA)
        self.assertFalse(SinalDoSite.objects.exists())
        self.assertEqual(len(pendentes), 1)

    def test_banco_fora_do_ar_nao_derruba_quem_avisou(self):
        with mock.patch.object(SinalDoSite.objects, "filter", side_effect=DatabaseError("caiu")):
            self.assertIsNone(sinais._gravar(sinais.MIDIA))

    def test_limpar_caches_da_restauracao_avisa_os_outros_processos(self):
        with self.captureOnCommitCallbacks(execute=True):
            espelho_midia.limpar_caches()
        self.assertTrue(SinalDoSite.objects.filter(chave=sinais.MIDIA).exists())


class ConferirTests(EstadoLimpo):
    def test_a_tela_guardada_antes_da_troca_some_quando_outro_processo_avisa(self):
        # o processo que atende as visitas guardou a home com os endereços de antes
        cache.set(HOME_CONTEXT_CACHE_KEY, {"foto": "https://res.cloudinary.com/x/antiga"}, 1800)
        fotos._URLS["chave"] = "https://res.cloudinary.com/x/antiga"
        self.outro_processo_avisa()
        self.assertEqual(sinais.conferir(), [sinais.MIDIA])
        self.assertIsNone(cache.get(HOME_CONTEXT_CACHE_KEY))
        self.assertNotIn("chave", fotos._URLS)

    def test_aviso_de_antes_do_processo_subir_nao_limpa_de_novo(self):
        SinalDoSite.objects.create(chave=sinais.MIDIA, versao=sinais._estado["inicio"] - 10)
        cache.set(HOME_CONTEXT_CACHE_KEY, {"foto": "nova"}, 1800)
        self.assertEqual(sinais.conferir(), [])
        self.assertEqual(cache.get(HOME_CONTEXT_CACHE_KEY), {"foto": "nova"})

    def test_sem_mudanca_a_conferencia_seguinte_nao_limpa(self):
        self.outro_processo_avisa()
        self.assertEqual(sinais.conferir(), [sinais.MIDIA])
        cache.set(HOME_CONTEXT_CACHE_KEY, {"foto": "nova"}, 1800)
        self.assertEqual(sinais.conferir(), [])
        self.assertEqual(cache.get(HOME_CONTEXT_CACHE_KEY), {"foto": "nova"})
        # e o aviso seguinte limpa outra vez
        self.outro_processo_avisa()
        self.assertEqual(sinais.conferir(), [sinais.MIDIA])
        self.assertIsNone(cache.get(HOME_CONTEXT_CACHE_KEY))

    def test_chave_desconhecida_nao_quebra(self):
        SinalDoSite.objects.create(chave="outra-coisa", versao=time.time_ns() + 1)
        self.assertEqual(sinais.conferir(), ["outra-coisa"])

    def test_conferir_e_uma_consulta(self):
        self.outro_processo_avisa()
        with self.assertNumQueries(1):
            sinais.conferir()


class LinhaDeFundoTests(EstadoLimpo):
    def test_desligada_fora_do_render(self):
        self.assertEqual(settings.SINAIS_INTERVALO_S, 0)
        with mock.patch("core.sinais.threading.Thread") as thread:
            self.assertFalse(sinais.garantir_vigia())
        thread.assert_not_called()

    @override_settings(SINAIS_INTERVALO_S=60)
    def test_uma_linha_por_processo_e_outra_depois_do_fork(self):
        with mock.patch("core.sinais.threading.Thread") as thread:
            thread.return_value.is_alive.return_value = True
            self.assertTrue(sinais.garantir_vigia())
            self.assertFalse(sinais.garantir_vigia())
            self.assertEqual(thread.call_count, 1)
            self.assertEqual(thread.call_args.kwargs["args"], (60,))
            self.assertTrue(thread.call_args.kwargs["daemon"])
            # o worker que nasceu do fork liga a sua e não herda o que o pai leu
            sinais._estado["visto"] = {sinais.MIDIA: 123}
            with mock.patch("core.sinais.os.getpid", return_value=sinais._estado["pid"] + 1):
                self.assertTrue(sinais.garantir_vigia())
            self.assertEqual(thread.call_count, 2)
            self.assertEqual(sinais._estado["visto"], {})

    @override_settings(SINAIS_INTERVALO_S=60)
    def test_a_visita_liga_a_linha_de_fundo(self):
        resposta = object()
        middleware = sinais.SinaisMiddleware(lambda request: resposta)
        with mock.patch("core.sinais.threading.Thread") as thread:
            thread.return_value.is_alive.return_value = True
            self.assertIs(middleware(RequestFactory().get("/")), resposta)
            self.assertIs(middleware(RequestFactory().get("/brinquedos/")), resposta)
        self.assertEqual(thread.call_count, 1)

    def test_o_middleware_esta_ligado(self):
        self.assertIn("core.sinais.SinaisMiddleware", settings.MIDDLEWARE)


@override_settings(SINAIS_INTERVALO_S=60)
class CloudinaryForaTests(EstadoLimpo):
    """Seção 132: com o Cloudinary fora, o site não pede foto nenhuma a ele."""

    def setUp(self):
        super().setUp()
        from core.arquivos_no_banco import MidiaNoBanco

        self.storage = MidiaNoBanco()
        self.raw = MidiaNoBanco(legado="raw")

    def test_marcar_grava_so_quando_muda(self):
        self.assertTrue(sinais.marcar(sinais.CLOUDINARY, True))
        self.assertFalse(sinais.marcar(sinais.CLOUDINARY, True))
        self.assertGreater(sinais.valor(sinais.CLOUDINARY), 0)
        self.assertTrue(sinais.marcar(sinais.CLOUDINARY, False))
        self.assertEqual(SinalDoSite.objects.get(chave=sinais.CLOUDINARY).versao, 0)
        self.assertEqual(sinais.valor(sinais.CLOUDINARY), 0)

    def test_outro_processo_le_o_estado_e_recomeca_o_cache(self):
        SinalDoSite.objects.create(chave=sinais.CLOUDINARY, versao=time.time_ns() + 5)
        cache.set(HOME_CONTEXT_CACHE_KEY, {"foto": "https://res.cloudinary.com/x/antiga"}, 1800)
        self.assertEqual(sinais.conferir(), [sinais.CLOUDINARY])
        self.assertGreater(sinais.valor(sinais.CLOUDINARY), 0)
        self.assertIsNone(cache.get(HOME_CONTEXT_CACHE_KEY))

    def test_estado_antigo_vale_desde_a_primeira_leitura(self):
        # o processo novo não limpa nada, mas já sabe que o Cloudinary está fora
        SinalDoSite.objects.create(chave=sinais.CLOUDINARY, versao=sinais._estado["inicio"] - 10)
        self.assertEqual(sinais.conferir(), [])
        self.assertGreater(sinais.valor(sinais.CLOUDINARY), 0)

    def test_nome_antigo_com_o_cloudinary_fora_vira_o_quadro_daqui(self):
        from core.arquivos_no_banco import legado_fora_do_ar

        sinais.marcar(sinais.CLOUDINARY, True)
        self.assertTrue(legado_fora_do_ar())
        url = self.storage.url("logo_clientes/happymania_yn31so")
        self.assertTrue(url.endswith("site/foto-em-atualizacao.svg"), url)
        self.assertNotIn("cloudinary", url)
        # o que já está no banco segue normal; o raw (3D, documento) não vira foto
        self.assertIn("/midia/banco/", self.storage.url("banco/logo_clientes/x"))
        self.assertFalse(self.storage.disponivel("logo_clientes/happymania_yn31so"))
        self.assertTrue(self.storage.disponivel("banco/logo_clientes/x"))
        self.assertTrue(self.raw.disponivel("objetos/modelo_ab12cd.glb"))
        self.assertNotIn("foto-em-atualizacao", self.raw.url("objetos/modelo_ab12cd.glb"))

    def test_com_o_cloudinary_no_ar_o_nome_antigo_segue_para_ele(self):
        self.assertFalse(sinais.valor(sinais.CLOUDINARY))
        self.assertIn("cloudinary", self.storage.url("logo_clientes/happymania_yn31so"))
        self.assertTrue(self.storage.disponivel("logo_clientes/happymania_yn31so"))

    @override_settings(SINAIS_INTERVALO_S=0)
    def test_sem_a_linha_de_fundo_o_automatico_nao_vale(self):
        sinais.marcar(sinais.CLOUDINARY, True)
        self.assertIn("cloudinary", self.storage.url("logo_clientes/happymania_yn31so"))

    @override_settings(MIDIA_CLOUDINARY_FORA="1")
    def test_a_variavel_forca_fora(self):
        self.assertIn("foto-em-atualizacao", self.storage.url("projetos/001_vmp7th"))

    @override_settings(MIDIA_CLOUDINARY_FORA="0")
    def test_a_variavel_forca_no_ar(self):
        sinais.marcar(sinais.CLOUDINARY, True)
        self.assertIn("cloudinary", self.storage.url("projetos/001_vmp7th"))

    def test_o_filtro_tem_foto_conta_o_que_sai_de_algum_lugar(self):
        from django.template import Context, Template

        from core.models import Brinquedos

        b = Brinquedos(nome_brinquedo="x", descricao="x", avaliacao=5, voltz="220V",
                       imagem_brinquedo="imagens_brinquedos/BOLICHE_VIRTUAL_igkeus")
        modelo = Template("{% load fotos %}{% if b.imagem_brinquedo|tem_foto %}sim{% else %}nao{% endif %}")
        self.assertEqual(modelo.render(Context({"b": b})), "sim")
        sinais.marcar(sinais.CLOUDINARY, True)
        fotos._URLS.clear()
        self.assertEqual(modelo.render(Context({"b": b})), "nao")
        # o filtro foto entrega o quadro daqui, nunca o endereço que devolve 401
        foto = Template("{% load fotos %}{{ b.imagem_brinquedo|foto:480 }}").render(Context({"b": b}))
        self.assertIn("foto-em-atualizacao.svg", foto)
        b.imagem_brinquedo = "banco/imagens_brinquedos/x"
        self.assertEqual(modelo.render(Context({"b": b})), "sim")
        self.assertEqual(Template("{% load fotos %}{{ ''|tem_foto }}").render(Context()), "False")

    def test_o_espelho_marca_fora_e_marca_de_volta(self):
        from core import arquivos_no_banco as anb
        from core.models import Brinquedos

        Brinquedos.objects.create(nome_brinquedo="x", descricao="x", avaliacao=5, voltz="220V",
                                  imagem_brinquedo="imagens_brinquedos/antiga_ab12cd")
        with mock.patch.object(anb, "baixar_endereco", side_effect=anb.CloudinaryForaDoAr("disabled")):
            espelho_midia.espelhar()
        self.assertGreater(SinalDoSite.objects.get(chave=sinais.CLOUDINARY).versao, 0)
        with mock.patch.object(anb, "baixar_endereco", side_effect=FileNotFoundError("404")):
            espelho_midia.espelhar()
        self.assertEqual(SinalDoSite.objects.get(chave=sinais.CLOUDINARY).versao, 0)
