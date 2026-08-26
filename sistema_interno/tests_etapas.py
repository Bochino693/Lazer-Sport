"""Gerar o manual de produção sem escrever tudo do zero.

O que estes testes protegem:

  * o roteiro padrão entra com um toque e respeita o tipo do produto;
  * gerar de novo não duplica nem sobrescreve o que a fábrica ajustou;
  * dá para criar o produto de dentro do manual, ligado ao brinquedo do
    site, já com as etapas;
  * copiar o manual de um produto parecido não traz as fotos dele --
    imagem de outro produto engana quem está montando.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core.models import Brinquedos

from . import etapas_padrao
from .models import GuiaEtapaProducao, ProdutoInterno


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class RoteiroPadraoTests(TestCase):

    URL = "/producao/guias/"

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor",
            password="senha-segura",
            email="gestor@example.com",
        )
        self.client.force_login(self.gestor)

        self.produto = ProdutoInterno.objects.create(
            nome="Cama elástica 3m",
            categoria=ProdutoInterno.Categoria.BRINQUEDO,
        )

    def post(self, dados):
        return self.client.post(
            self.URL,
            dados,
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    # ------------------------------------------------------- geração
    def test_gera_o_roteiro_da_fabrica(self):
        resposta = self.post({
            "action": "gerar_padrao",
            "produto": self.produto.id,
        })

        self.assertEqual(resposta.status_code, 200)
        etapas = list(self.produto.guias_producao.order_by("ordem"))
        self.assertEqual(len(etapas), 7)
        self.assertEqual(etapas[0].titulo, "Separar material e conferir a ficha")
        self.assertEqual(etapas[-1].titulo, "Limpeza, identificação e embalagem")

        # A ordem é sequencial: é ela que guia o colaborador na execução.
        self.assertEqual(
            [e.ordem for e in etapas],
            list(range(1, len(etapas) + 1)),
        )

    def test_cada_etapa_nasce_com_instrucao_e_criterio(self):
        """Etapa sem texto seria só um título para o colaborador ler."""
        self.post({"action": "gerar_padrao", "produto": self.produto.id})

        for etapa in self.produto.guias_producao.all():
            self.assertTrue(etapa.instrucoes.strip())
            self.assertTrue(etapa.criterio_conclusao.strip())
            self.assertTrue(etapa.tempo_estimado_min)

    def test_maquina_ganha_etapa_eletrica_que_brinquedo_nao_tem(self):
        maquina = ProdutoInterno.objects.create(
            nome="Fliperama",
            categoria=ProdutoInterno.Categoria.MAQUINA,
        )

        etapas_padrao.gerar(maquina)
        etapas_padrao.gerar(self.produto)

        titulos_maquina = set(
            maquina.guias_producao.values_list("titulo", flat=True)
        )
        titulos_brinquedo = set(
            self.produto.guias_producao.values_list("titulo", flat=True)
        )

        self.assertIn("Instalação elétrica", titulos_maquina)
        self.assertNotIn("Instalação elétrica", titulos_brinquedo)

    def test_gerar_duas_vezes_nao_duplica(self):
        self.post({"action": "gerar_padrao", "produto": self.produto.id})
        antes = self.produto.guias_producao.count()

        resposta = self.post({
            "action": "gerar_padrao",
            "produto": self.produto.id,
        })

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(self.produto.guias_producao.count(), antes)

    def test_texto_ajustado_pela_fabrica_nao_e_sobrescrito(self):
        etapas_padrao.gerar(self.produto)
        etapa = self.produto.guias_producao.order_by("ordem").first()
        etapa.instrucoes = "Do jeito que a gente faz aqui."
        etapa.save(update_fields=["instrucoes"])

        etapas_padrao.gerar(self.produto)

        etapa.refresh_from_db()
        self.assertEqual(etapa.instrucoes, "Do jeito que a gente faz aqui.")

    def test_etapa_faltante_e_completada_sem_repetir_a_ordem(self):
        etapas_padrao.gerar(self.produto)
        self.produto.guias_producao.filter(
            titulo="Acabamento",
        ).delete()

        criadas = etapas_padrao.gerar(self.produto)

        self.assertEqual(criadas, 1)
        ordens = list(
            self.produto.guias_producao.order_by("ordem").values_list(
                "ordem", flat=True,
            )
        )
        self.assertEqual(len(ordens), len(set(ordens)))

    # -------------------------------------------------------- produto
    def test_cria_produto_a_partir_do_brinquedo_do_site(self):
        brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Piscina de bolinhas",
            descricao="Piscina 3x3",
            avaliacao=Decimal("5.00"),
            voltz="110",
        )

        resposta = self.post({
            "action": "produto_novo",
            "nome": "Piscina de bolinhas",
            "categoria": ProdutoInterno.Categoria.BRINQUEDO,
            "brinquedo": brinquedo.id,
            "gerar_etapas": "1",
        })

        self.assertEqual(resposta.status_code, 200)
        novo = ProdutoInterno.objects.get(nome="Piscina de bolinhas")
        self.assertEqual(novo.brinquedo, brinquedo)
        self.assertEqual(novo.guias_producao.count(), 7)

    def test_produto_novo_sem_gerar_etapas_nasce_vazio(self):
        self.post({
            "action": "produto_novo",
            "nome": "Carrinho bate-bate",
            "categoria": ProdutoInterno.Categoria.MAQUINA,
        })

        novo = ProdutoInterno.objects.get(nome="Carrinho bate-bate")
        self.assertEqual(novo.guias_producao.count(), 0)

    def test_nome_repetido_de_produto_e_barrado(self):
        resposta = self.post({
            "action": "produto_novo",
            "nome": "cama elástica 3m",
        })

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(ProdutoInterno.objects.count(), 1)

    # --------------------------------------------------------- cópia
    def test_copia_manual_de_produto_parecido(self):
        etapas_padrao.gerar(self.produto)
        destino = ProdutoInterno.objects.create(
            nome="Cama elástica 4m",
            categoria=ProdutoInterno.Categoria.BRINQUEDO,
        )

        resposta = self.post({
            "action": "copiar_etapas",
            "produto": destino.id,
            "origem": self.produto.id,
        })

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            destino.guias_producao.count(),
            self.produto.guias_producao.count(),
        )

    def test_copiar_para_o_mesmo_produto_nao_faz_nada(self):
        etapas_padrao.gerar(self.produto)

        resposta = self.post({
            "action": "copiar_etapas",
            "produto": self.produto.id,
            "origem": self.produto.id,
        })

        self.assertEqual(resposta.status_code, 400)

    def test_etapa_desativada_nao_e_copiada(self):
        etapas_padrao.gerar(self.produto)
        GuiaEtapaProducao.objects.filter(
            produto=self.produto,
            titulo="Acabamento",
        ).update(ativo=False)

        destino = ProdutoInterno.objects.create(nome="Outro brinquedo")
        copiadas = etapas_padrao.copiar(self.produto, destino)

        self.assertEqual(copiadas, self.produto.guias_producao.count() - 1)
        self.assertFalse(
            destino.guias_producao.filter(titulo="Acabamento").exists()
        )

    # ----------------------------------------------------------- tela
    def test_tela_convida_a_gerar_quando_nao_ha_manual(self):
        resposta = self.client.get(
            self.URL,
            {"produto": self.produto.id},
            HTTP_HOST="interno.testserver",
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["roteiro_previsto"], 7)
        self.assertContains(resposta, "Gerar as 7 etapas do roteiro padrão")
