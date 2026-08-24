import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib import admin
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.test import (
    RequestFactory,
    SimpleTestCase,
    TestCase,
    TransactionTestCase,
    override_settings,
)
from django.urls import reverse

from .catalog_images import (
    adicionar_imagens_atuais_como_primeira,
    numerar_imagens_existentes_das_pecas,
)
from .home_cache import (
    CATALOG_METADATA_CACHE_KEY,
    HOME_CONTEXT_CACHE_KEY,
    HOME_FRAGMENT_NAME,
    get_cached_catalog_metadata,
    get_cached_home_context,
)
from .models import (
    Brinquedos,
    CategoriasBrinquedos,
    ImagemBrinquedo,
    ImagemPeca,
    PecasReposicao,
)
from .views import gerar_pix, processar_cartao, verificar_pagamento


def carrinho_mock(total="100.00", payment_id=None):
    carrinho = MagicMock()
    carrinho.id = 7
    carrinho.total_final = Decimal(total)
    carrinho.mp_payment_id = payment_id
    carrinho.itens.exists.return_value = True
    return carrinho


def pedido_mock(total="100.00", payment_id=None, pedido_id=31):
    pedido = MagicMock()
    pedido.id = pedido_id
    pedido.total_final = Decimal(total)
    pedido.mp_fingerprint = "fingerprint-do-pedido"
    pedido.mp_payment_id = payment_id
    pedido.status = "aguardando_pagamento"
    return pedido


def usuario_mock():
    return SimpleNamespace(
        is_authenticated=True,
        email="comprador@example.com",
    )


@override_settings(
    MP_ACCESS_TOKEN="TEST-ACCESS-TOKEN",
    ALLOWED_HOSTS=["testserver"],
)
class MercadoPagoPixTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("core.views.mercadopago.SDK")
    @patch("core.views.checkout.expirar_reserva")
    @patch("core.views.checkout.reservar_pedido")
    @patch("core.views.checkout.pedido_reservado_do_carrinho")
    @patch("core.views._carrinho_pagamento_do_usuario")
    def test_erro_do_gateway_nao_vira_key_error(
        self,
        buscar_carrinho,
        buscar_reserva,
        reservar_pedido,
        expirar_reserva,
        sdk_class,
    ):
        carrinho = carrinho_mock()
        pedido = pedido_mock()
        buscar_carrinho.return_value = carrinho
        buscar_reserva.return_value = None
        reservar_pedido.return_value = (pedido, True)
        sdk_class.return_value.payment.return_value.create.return_value = {
            "status": 400,
            "response": {
                "message": "Bad request",
                "cause": [{"description": "payer.email inválido"}],
            },
        }
        request = self.factory.get("/api/gerar-pix/?carrinho_id=7")
        request.user = usuario_mock()

        response = gerar_pix(request)
        body = json.loads(response.content)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(body["erro"], "Não foi possível gerar o Pix.")
        self.assertIn("payer.email", body["detalhe"])
        expirar_reserva.assert_called_once_with(
            pedido,
            "cobrança recusada pelo provedor",
        )

    @patch("core.views.mercadopago.SDK")
    @patch("core.views.Carrinho.objects.filter")
    @patch("core.views.checkout.reservar_pedido")
    @patch("core.views.checkout.pedido_reservado_do_carrinho")
    @patch("core.views._carrinho_pagamento_do_usuario")
    def test_pix_valido_salva_payment_id_e_retorna_qr_code(
        self,
        buscar_carrinho,
        buscar_reserva,
        reservar_pedido,
        filtrar_carrinhos,
        sdk_class,
    ):
        carrinho = carrinho_mock()
        pedido = pedido_mock()
        buscar_carrinho.return_value = carrinho
        buscar_reserva.return_value = None
        reservar_pedido.return_value = (pedido, True)
        sdk_class.return_value.payment.return_value.create.return_value = {
            "status": 201,
            "response": {
                "id": 123456,
                "status": "pending",
                "transaction_amount": 100.00,
                "point_of_interaction": {
                    "transaction_data": {
                        "qr_code_base64": "BASE64",
                        "qr_code": "PIX-COPIA-COLA",
                        "ticket_url": "https://example.test/pix",
                    }
                },
            },
        }
        request = self.factory.get("/api/gerar-pix/?carrinho_id=7")
        request.user = usuario_mock()

        response = gerar_pix(request)
        body = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["payment_id"], 123456)
        self.assertEqual(body["pedido_id"], 31)
        self.assertEqual(body["qr_code"], "BASE64")
        self.assertEqual(pedido.mp_payment_id, "123456")
        pedido.save.assert_called_once_with(
            update_fields=["mp_payment_id", "mp_status", "atualizado"]
        )
        filtrar_carrinhos.return_value.update.assert_called_once_with(
            mp_payment_id="123456"
        )


@override_settings(
    MP_ACCESS_TOKEN="TEST-ACCESS-TOKEN",
    ALLOWED_HOSTS=["testserver"],
)
class VerificarPagamentoPedidoTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("core.views.Pedido.objects.filter")
    @patch("core.views._carrinho_pagamento_do_usuario")
    def test_sem_pedido_id_nao_reaproveita_pagamento_antigo(
        self,
        buscar_carrinho,
        filtrar_pedidos,
    ):
        buscar_carrinho.return_value = carrinho_mock()
        request = self.factory.get("/verificar-pagamento/?carrinho_id=7")
        request.user = usuario_mock()

        response = verificar_pagamento(request)
        body = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(body["pago"])
        self.assertEqual(body["status"], "waiting_payment")
        filtrar_pedidos.assert_not_called()

    @patch("core.views.Pedido.objects.filter")
    @patch("core.views._carrinho_pagamento_do_usuario")
    def test_confirma_somente_o_pedido_id_informado(
        self,
        buscar_carrinho,
        filtrar_pedidos,
    ):
        carrinho = carrinho_mock()
        pedido = SimpleNamespace(id=42, status="pago")
        buscar_carrinho.return_value = carrinho
        filtrar_pedidos.return_value.first.return_value = pedido
        request = self.factory.get(
            "/verificar-pagamento/?carrinho_id=7&pedido_id=42"
        )
        request.user = usuario_mock()

        response = verificar_pagamento(request)
        body = json.loads(response.content)

        self.assertTrue(body["pago"])
        self.assertEqual(body["pedido_id"], 42)
        filtrar_pedidos.assert_called_once_with(
            pk=42,
            carrinho_origem=carrinho,
            cliente__user=request.user,
        )


@override_settings(
    MP_ACCESS_TOKEN="TEST-ACCESS-TOKEN",
    ALLOWED_HOSTS=["testserver"],
)
class MercadoPagoCardTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("core.views.checkout.pedido_reservado_do_carrinho")
    @patch("core.views._carrinho_pagamento_do_usuario")
    def test_abaixo_de_20_mil_rejeita_mais_de_12_parcelas(
        self,
        buscar_carrinho,
        buscar_reserva,
    ):
        buscar_carrinho.return_value = carrinho_mock("19999.99")
        buscar_reserva.return_value = pedido_mock("19999.99")
        request = self.factory.post(
            "/processar_cartao/",
            data=json.dumps({
                "carrinho_id": 7,
                "token": "token",
                "payment_method_id": "visa",
                "installments": 13,
                "payer": {"email": "comprador@example.com"},
            }),
            content_type="application/json",
        )
        request.user = usuario_mock()

        response = processar_cartao(request)
        body = json.loads(response.content)

        self.assertEqual(response.status_code, 400)
        self.assertIn("12 parcelas", body["mensagem"])

    @patch("core.views.mercadopago.SDK")
    @patch("core.views.checkout.confirmar_pagamento")
    @patch("core.views.Carrinho.objects.filter")
    @patch("core.views.checkout.pedido_reservado_do_carrinho")
    @patch("core.views._carrinho_pagamento_do_usuario")
    def test_acima_de_20_mil_aceita_18_parcelas(
        self,
        buscar_carrinho,
        buscar_reserva,
        filtrar_carrinhos,
        confirmar_pagamento,
        sdk_class,
    ):
        carrinho = carrinho_mock("20000.01")
        pedido = pedido_mock("20000.01")
        buscar_carrinho.return_value = carrinho
        buscar_reserva.return_value = pedido
        confirmar_pagamento.return_value = (pedido, True)
        sdk_class.return_value.payment.return_value.create.return_value = {
            "status": 201,
            "response": {
                "id": 987654,
                "status": "approved",
                "status_detail": "accredited",
                "transaction_amount": 20000.01,
            },
        }
        request = self.factory.post(
            "/processar_cartao/",
            data=json.dumps({
                "carrinho_id": 7,
                "token": "card-token",
                "payment_method_id": "visa",
                "issuer_id": "123",
                "installments": 18,
                "payer": {
                    "email": "comprador@example.com",
                    "identification": {
                        "type": "CPF",
                        "number": "19119119100",
                    },
                },
            }),
            content_type="application/json",
        )
        request.user = usuario_mock()

        response = processar_cartao(request)
        body = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["aprovado"])
        self.assertEqual(body["pedido_id"], 31)
        self.assertEqual(pedido.mp_payment_id, "987654")
        filtrar_carrinhos.return_value.update.assert_called_once_with(
            mp_payment_id="987654"
        )


class CatalogImageMigrationTests(TestCase):
    def test_imagem_antiga_vira_foto_um_sem_duplicar(self):
        brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Brinquedo de teste",
            imagem_brinquedo="imagens_brinquedos/original.jpg",
            descricao="Descrição",
            avaliacao=Decimal("5.00"),
            voltz="220V",
        )

        self.assertEqual(adicionar_imagens_atuais_como_primeira(), 1)
        self.assertEqual(adicionar_imagens_atuais_como_primeira(), 0)

        imagem = ImagemBrinquedo.objects.get(brinquedo=brinquedo)
        self.assertEqual(imagem.ordem, 1)
        self.assertEqual(
            imagem.imagem.name,
            "imagens_brinquedos/original.jpg",
        )
        self.assertEqual(brinquedo.imagem_catalogo.name, imagem.imagem.name)

    def test_peca_prioriza_frente_e_numera_as_demais(self):
        peca = PecasReposicao.objects.create(
            nome="Peça de teste",
            descricao_peca="Descrição",
        )
        detalhe = ImagemPeca.objects.create(
            peca_reposicao=peca,
            imagem="pecas_reposicao/detalhe.jpg",
            posicao=ImagemPeca.PosicaoImagem.DETALHE,
            ordem=1,
        )
        frente = ImagemPeca.objects.create(
            peca_reposicao=peca,
            imagem="pecas_reposicao/frente.jpg",
            posicao=ImagemPeca.PosicaoImagem.FRENTE,
            ordem=2,
        )

        self.assertEqual(numerar_imagens_existentes_das_pecas(), 2)

        detalhe.refresh_from_db()
        frente.refresh_from_db()
        self.assertEqual(frente.ordem, 1)
        self.assertEqual(detalhe.ordem, 2)
        self.assertEqual(peca.imagem_principal.pk, frente.pk)

    def test_telas_de_detalhe_exibem_galerias(self):
        brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Brinquedo galeria",
            imagem_brinquedo="imagens_brinquedos/principal.jpg",
            descricao="Descrição completa do brinquedo",
            avaliacao=Decimal("4.50"),
            voltz="220V",
        )
        for ordem in (1, 2):
            ImagemBrinquedo.objects.create(
                brinquedo=brinquedo,
                imagem=f"imagens_brinquedos/foto-{ordem}.jpg",
                ordem=ordem,
            )

        resposta_brinquedo = self.client.get(
            reverse("brinquedo_detalhe", args=[brinquedo.id])
        )
        self.assertEqual(resposta_brinquedo.status_code, 200)
        self.assertContains(resposta_brinquedo, 'data-galeria-indice="1"')
        self.assertContains(resposta_brinquedo, "1 / 2")
        self.assertContains(resposta_brinquedo, "produto-breadcrumb ls-breadcrumb")
        self.assertContains(resposta_brinquedo, 'id="bread"')
        self.assertContains(resposta_brinquedo, "#ffe36b")
        self.assertContains(resposta_brinquedo, 'href="#produto-informacoes"')
        self.assertContains(
            resposta_brinquedo,
            '<main class="content-section content-section--full">',
        )

        peca = PecasReposicao.objects.create(
            nome="Peça galeria",
            descricao_peca="Descrição completa da peça",
            preco_venda=Decimal("129.90"),
        )
        for ordem, posicao in (
            (1, ImagemPeca.PosicaoImagem.FRENTE),
            (2, ImagemPeca.PosicaoImagem.DETALHE),
        ):
            ImagemPeca.objects.create(
                peca_reposicao=peca,
                imagem=f"pecas_reposicao/foto-{ordem}.jpg",
                ordem=ordem,
                posicao=posicao,
            )

        resposta_peca = self.client.get(
            reverse("reposicao_detalhe", args=[peca.id])
        )
        self.assertEqual(resposta_peca.status_code, 200)
        self.assertContains(resposta_peca, 'data-foto-indice="1"')
        self.assertContains(resposta_peca, "Código LS-P")
        self.assertContains(resposta_peca, "peca-breadcrumb ls-breadcrumb")
        self.assertContains(resposta_peca, 'id="breadcrumb"')
        self.assertContains(resposta_peca, "#ffc928")
        self.assertContains(resposta_peca, 'href="#peca-informacoes"')
        self.assertContains(
            resposta_peca,
            '<main class="content-section content-section--full">',
        )

        resposta_catalogo_pecas = self.client.get(reverse("pecas_reposicao"))
        self.assertEqual(resposta_catalogo_pecas.status_code, 200)
        self.assertContains(resposta_catalogo_pecas, "breadcrumb ls-breadcrumb")
        self.assertContains(resposta_catalogo_pecas, "data-scroll-reveal")


class CatalogGalleryAdminTests(SimpleTestCase):
    def test_novos_modelos_de_imagem_aparecem_no_admin(self):
        self.assertIn(ImagemBrinquedo, admin.site._registry)
        self.assertIn(ImagemPeca, admin.site._registry)

    def test_editor_individual_protege_a_posicao_ja_salva(self):
        admin_brinquedo = admin.site._registry[ImagemBrinquedo]
        admin_peca = admin.site._registry[ImagemPeca]
        foto_brinquedo = ImagemBrinquedo(pk=10, ordem=2)
        foto_peca = ImagemPeca(pk=20, ordem=3)

        self.assertIn(
            "ordem",
            admin_brinquedo.get_readonly_fields(None, foto_brinquedo),
        )
        self.assertIn(
            "ordem",
            admin_peca.get_readonly_fields(None, foto_peca),
        )
        self.assertNotIn("ordem", admin_brinquedo.get_readonly_fields(None))
        self.assertNotIn("ordem", admin_peca.get_readonly_fields(None))


@override_settings(HOME_CACHE_TTL=600)
class HomePublicCacheTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_builder_roda_uma_vez_enquanto_cache_estiver_valido(self):
        builder = MagicMock(return_value={"brinquedos_count": 7})

        primeiro = get_cached_home_context(builder)
        segundo = get_cached_home_context(builder)

        self.assertEqual(primeiro, segundo)
        self.assertEqual(builder.call_count, 1)

        # Quem recebe o contexto pode acrescentar dados sem sujar o cache.
        primeiro["temporario"] = True
        self.assertNotIn("temporario", get_cached_home_context(builder))


@override_settings(CATALOG_CACHE_TTL=600)
class CatalogMetadataCacheTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_metadados_publicos_sao_montados_uma_vez(self):
        builder = MagicMock(return_value={"total_catalogo": 12})

        primeiro = get_cached_catalog_metadata(builder)
        segundo = get_cached_catalog_metadata(builder)

        self.assertEqual(primeiro, segundo)
        self.assertEqual(builder.call_count, 1)


@override_settings(HOME_CACHE_TTL=600)
class HomeCacheInvalidationTests(TransactionTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _preencher_cache(self):
        cache.set(HOME_CONTEXT_CACHE_KEY, {"antigo": True}, 600)
        cache.set(
            make_template_fragment_key(HOME_FRAGMENT_NAME),
            "html antigo",
            600,
        )
        cache.set(CATALOG_METADATA_CACHE_KEY, {"antigo": True}, 600)

    def test_save_no_catalogo_invalida_dados_e_html_da_home(self):
        self._preencher_cache()

        Brinquedos.objects.create(
            nome_brinquedo="Novo brinquedo",
            descricao="Descrição",
            avaliacao=Decimal("5.00"),
            voltz="220V",
        )

        self.assertIsNone(cache.get(HOME_CONTEXT_CACHE_KEY))
        self.assertIsNone(
            cache.get(make_template_fragment_key(HOME_FRAGMENT_NAME))
        )
        self.assertIsNone(cache.get(CATALOG_METADATA_CACHE_KEY))

    def test_alteracao_many_to_many_tambem_invalida_home(self):
        brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Brinquedo categorizado",
            descricao="Descrição",
            avaliacao=Decimal("4.50"),
            voltz="220V",
        )
        categoria = CategoriasBrinquedos.objects.create(
            nome_categoria="Interativos",
        )
        self._preencher_cache()

        brinquedo.categorias_brinquedos.add(categoria)

        self.assertIsNone(cache.get(HOME_CONTEXT_CACHE_KEY))
        self.assertIsNone(
            cache.get(make_template_fragment_key(HOME_FRAGMENT_NAME))
        )

    def test_segunda_visita_anonima_nao_repete_consultas_da_home(self):
        primeira = self.client.get(reverse("home"))
        self.assertEqual(primeira.status_code, 200)

        with self.assertNumQueries(0):
            segunda = self.client.get(reverse("home"))

        self.assertEqual(segunda.status_code, 200)


class CatalogFilterUXTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_catalogo_usa_seletores_modernos_sem_dropdown_nativo(self):
        resposta = self.client.get(reverse("brinquedos"))

        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, '<select id="catalogo-categoria"')
        self.assertNotContains(resposta, '<select id="catalogo-ordenar"')
        self.assertContains(resposta, 'data-mobile-filter-toggle')
        self.assertContains(resposta, 'class="catalogo-choice"', count=4)
        self.assertContains(resposta, 'type="radio" name="categoria"')
        self.assertContains(resposta, 'type="radio" name="disponibilidade"')
        self.assertContains(resposta, 'type="radio" name="voltagem"')
        self.assertContains(resposta, 'type="radio" name="ordenar"')
        self.assertContains(resposta, "catalogo-breadcrumb ls-breadcrumb")

    def test_filtros_continuam_enviando_parametros_ao_backend(self):
        categoria = CategoriasBrinquedos.objects.create(
            nome_categoria="Interativos",
        )
        brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Jogo interativo",
            descricao="Brinquedo para teste dos filtros",
            avaliacao=Decimal("4.80"),
            voltz="220V",
        )
        brinquedo.categorias_brinquedos.add(categoria)

        resposta = self.client.get(
            reverse("brinquedos"),
            {
                "categoria": categoria.id,
                "voltagem": "220V",
                "disponibilidade": "todos",
                "ordenar": "az",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Jogo interativo")
        self.assertContains(
            resposta,
            f'name="categoria" value="{categoria.id}" checked',
        )

    def test_faixa_comeca_no_menor_preco_real_disponivel_na_loja(self):
        Brinquedos.objects.create(
            nome_brinquedo="Somente orçamento barato",
            descricao="Não deve definir o limite da loja",
            valor_brinquedo=Decimal("10.00"),
            avaliacao=Decimal("4.00"),
            exibir_na_loja=False,
            voltz="220V",
        )
        Brinquedos.objects.create(
            nome_brinquedo="Primeiro preço válido",
            descricao="Menor preço disponível",
            valor_brinquedo=Decimal("1234.50"),
            avaliacao=Decimal("4.50"),
            exibir_na_loja=True,
            voltz="220V",
        )
        Brinquedos.objects.create(
            nome_brinquedo="Maior preço válido",
            descricao="Maior preço disponível",
            valor_brinquedo=Decimal("9876.54"),
            avaliacao=Decimal("4.80"),
            exibir_na_loja=True,
            voltz="220V",
        )

        resposta = self.client.get(reverse("brinquedos"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Menor encontrado")
        self.assertContains(resposta, "R$ 1.234,50")
        self.assertContains(resposta, "R$ 9.876,54")
        self.assertContains(resposta, 'min="1234.50"')
        self.assertContains(resposta, 'max="9876.54"')

    def test_preco_digitado_volta_formatado_no_padrao_brasileiro(self):
        Brinquedos.objects.create(
            nome_brinquedo="Brinquedo disponível",
            descricao="Produto vendido na loja",
            valor_brinquedo=Decimal("1999.90"),
            avaliacao=Decimal("4.70"),
            exibir_na_loja=True,
            voltz="220V",
        )

        resposta = self.client.get(
            reverse("brinquedos"),
            {"preco_min": "R$ 1.234,50"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'value="1.234,50"')
        