from django.contrib.auth.models import User
from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings

from .models import (
    ExecucaoEtapaProducao,
    EstoqueMaterial,
    GuiaEtapaProducao,
    HistoricoProducao,
    ItemFichaTecnica,
    Material,
    OrdemProducao,
    ProdutoInterno,
)
from .views_gestao import OrdemProducaoDetalheView


class FluxoGuiadoProducaoTests(TestCase):
    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor",
            password="senha-segura",
            email="gestor@example.com",
        )
        self.colaborador = User.objects.create_user(
            username="operador",
            password="senha-segura",
            is_staff=True,
        )
        self.outro_colaborador = User.objects.create_user(
            username="outro-operador",
            password="senha-segura",
            is_staff=True,
        )
        self.produto = ProdutoInterno.objects.create(nome="Máquina de teste")
        self.guia_1 = GuiaEtapaProducao.objects.create(
            produto=self.produto,
            ordem=1,
            titulo="Preparar peças",
            instrucoes="Separe e confira todas as peças.",
        )
        self.guia_2 = GuiaEtapaProducao.objects.create(
            produto=self.produto,
            ordem=2,
            titulo="Montar estrutura",
            instrucoes="Monte a estrutura conforme as imagens.",
        )
        self.ordem = OrdemProducao.objects.create(
            produto=self.produto,
            quantidade=1,
            colaborador=self.colaborador,
        )
        self.ordem.preparar_etapas()
        self.etapa_1, self.etapa_2 = list(
            self.ordem.etapas_execucao.order_by("guia_etapa__ordem")
        )

    def test_nao_permite_pular_etapa(self):
        with self.assertRaisesMessage(ValueError, "Conclua a etapa atual"):
            ExecucaoEtapaProducao.registrar_acao(
                self.etapa_2.pk,
                "iniciar",
                self.colaborador,
            )

    def test_registra_andamento_sequencial_e_historico(self):
        ExecucaoEtapaProducao.registrar_acao(
            self.etapa_1.pk,
            "iniciar",
            self.colaborador,
        )
        ExecucaoEtapaProducao.registrar_acao(
            self.etapa_1.pk,
            "concluir",
            self.colaborador,
            "Peças conferidas.",
        )

        self.etapa_1.refresh_from_db()
        self.ordem.refresh_from_db()
        self.assertEqual(
            self.etapa_1.status,
            ExecucaoEtapaProducao.Status.CONCLUIDA,
        )
        self.assertEqual(self.ordem.status, OrdemProducao.Status.EM_PRODUCAO)
        self.assertEqual(
            HistoricoProducao.objects.filter(ordem_producao=self.ordem).count(),
            2,
        )

        ExecucaoEtapaProducao.registrar_acao(
            self.etapa_2.pk,
            "iniciar",
            self.colaborador,
        )
        self.etapa_2.refresh_from_db()
        self.assertEqual(
            self.etapa_2.status,
            ExecucaoEtapaProducao.Status.EM_ANDAMENTO,
        )

    def test_bloqueio_exige_explicacao(self):
        with self.assertRaisesMessage(ValueError, "Explique a dúvida"):
            ExecucaoEtapaProducao.registrar_acao(
                self.etapa_1.pk,
                "bloquear",
                self.colaborador,
            )

        ExecucaoEtapaProducao.registrar_acao(
            self.etapa_1.pk,
            "bloquear",
            self.colaborador,
            "A peça recebida não corresponde ao guia.",
        )
        self.ordem.refresh_from_db()
        self.assertEqual(self.ordem.status, OrdemProducao.Status.BLOQUEADA)

    def test_ultima_etapa_conclui_ordem_e_baixa_estoque(self):
        material = Material.objects.create(nome_material="Parafuso de teste")
        estoque = EstoqueMaterial.objects.create(
            descricao_local="Prateleira A",
            material=material,
            quantidade=1,
            preco_fornecedor="2.00",
        )
        ItemFichaTecnica.objects.create(
            produto=self.produto,
            material=material,
            quantidade="1.000",
        )

        for etapa in (self.etapa_1, self.etapa_2):
            ExecucaoEtapaProducao.registrar_acao(
                etapa.pk,
                "iniciar",
                self.colaborador,
            )
            ExecucaoEtapaProducao.registrar_acao(
                etapa.pk,
                "concluir",
                self.colaborador,
            )

        self.ordem.refresh_from_db()
        estoque.refresh_from_db()
        self.assertEqual(self.ordem.status, OrdemProducao.Status.CONCLUIDA)
        self.assertTrue(self.ordem.baixa_aplicada)
        self.assertEqual(estoque.quantidade, 0)

    def test_colaborador_nao_abre_ordem_de_outra_pessoa(self):
        request = RequestFactory().get(f"/producao/ordens/{self.ordem.pk}/")
        request.user = self.outro_colaborador
        request.is_interno = True

        with self.assertRaises(Http404):
            OrdemProducaoDetalheView.as_view()(request, pk=self.ordem.pk)

    @override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
    def test_telas_do_colaborador_renderizam_os_guias(self):
        self.client.force_login(self.colaborador)

        lista = self.client.get(
            "/producao/",
            HTTP_HOST="interno.testserver",
        )
        detalhe = self.client.get(
            f"/producao/ordens/{self.ordem.pk}/",
            HTTP_HOST="interno.testserver",
        )

        self.assertEqual(lista.status_code, 200)
        self.assertContains(lista, "Máquina de teste")
        self.assertEqual(detalhe.status_code, 200)
        self.assertContains(detalhe, "Separe e confira todas as peças.")

    @override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
    def test_colaborador_nao_acessa_editor_de_guias(self):
        self.client.force_login(self.colaborador)
        resposta = self.client.get(
            "/producao/guias/",
            HTTP_HOST="interno.testserver",
        )
        self.assertRedirects(
            resposta,
            "/producao/",
            fetch_redirect_response=False,
        )

    @override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
    def test_telas_de_gestao_de_producao_renderizam(self):
        self.client.force_login(self.gestor)
        guias = self.client.get(
            f"/producao/guias/?produto={self.produto.pk}",
            HTTP_HOST="interno.testserver",
        )
        ordens = self.client.get(
            "/producao/ordens/",
            HTTP_HOST="interno.testserver",
        )

        self.assertEqual(guias.status_code, 200)
        self.assertContains(guias, "Preparar peças")
        self.assertEqual(ordens.status_code, 200)
        self.assertContains(ordens, "operador")
