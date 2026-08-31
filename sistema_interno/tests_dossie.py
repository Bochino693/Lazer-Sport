"""O histórico do cliente num lugar só -- e a oferta para uma pessoa só.

DUAS PERGUNTAS QUE O SISTEMA TINHA E NÃO RESPONDIA.

A primeira: "o que já fizemos para este cliente?". Cliente, orçamento e
O.S. viviam em três telas que não se olhavam. Para responder era preciso
abrir Orçamentos, filtrar pelo nome, abrir Ordens de Serviço, filtrar de
novo e somar de cabeça -- na frente do cliente, no telefone.

A segunda: "quero mandar esta promoção para ESTA pessoa". A divulgação
nasceu em massa ("todos os buffets parceiros"), e a conversa comercial de
verdade é um a um. Sem isso, a saída era disparar para o segmento inteiro
ou copiar o texto na mão -- e texto copiado na mão não deixa registro
nenhum.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core.models import Brinquedos, CategoriasBrinquedos, Promocoes

from .models import (
    Cliente,
    EntregaCampanha,
    ItemOrcamento,
    ItemOrdemServico,
    Orcamento,
    OrdemServico,
)
from .permissoes import atribuir_funcoes


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class DossieDoClienteTests(TestCase):

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-dossie", password="x", email="g@example.com",
        )
        self.client.force_login(self.gestor)

        self.cliente = Cliente.objects.create(
            nome_cliente="Buffet Alegria",
            email="contato@buffet.com",
            telefone="(11) 99999-1111",
            canal_telefone=Cliente.CanalTelefone.WHATSAPP,
        )

    def dossie(self, cliente=None):
        return self.client.get(
            f"/clientes/{(cliente or self.cliente).pk}/dossie/",
            HTTP_HOST="interno.testserver",
        )

    def orcamento(self, status=Orcamento.Status.APROVADO, valor="450.00"):
        orcamento = Orcamento.objects.create(
            cliente=self.cliente, nome_cliente="Buffet Alegria", status=status,
        )
        ItemOrcamento.objects.create(
            orcamento=orcamento, descricao="Cama elástica",
            quantidade=1, valor_unitario=Decimal(valor),
        )
        return orcamento

    def test_junta_orcamentos_e_ordens_do_mesmo_cliente(self):
        self.orcamento()
        self.orcamento(status=Orcamento.Status.RASCUNHO, valor="120.00")
        ordem = OrdemServico.objects.create(
            cliente=self.cliente, nome_cliente="Buffet Alegria",
            equipamento="Tobogã",
        )
        ItemOrdemServico.objects.create(
            ordem=ordem, tipo=ItemOrdemServico.Tipo.SERVICO,
            descricao="Reparo", quantidade=1, valor_unitario=Decimal("300.00"),
        )

        dados = self.dossie().json()

        self.assertEqual(dados["resumo"]["orcamentos"], 2)
        self.assertEqual(dados["resumo"]["ordens"], 1)
        self.assertEqual(len(dados["orcamentos"]), 2)
        self.assertEqual(len(dados["ordens"]), 1)
        self.assertEqual(dados["ordens"][0]["equipamento"], "Tobogã")

    def test_o_total_soma_so_o_que_foi_aprovado(self):
        """Rascunho e recusado não entram: não é dinheiro que entrou."""
        self.orcamento(valor="450.00")
        self.orcamento(status=Orcamento.Status.RASCUNHO, valor="999.00")
        self.orcamento(status=Orcamento.Status.RECUSADO, valor="777.00")

        dados = self.dossie().json()

        self.assertEqual(dados["resumo"]["aprovados"], 1)
        self.assertEqual(dados["resumo"]["total_aprovado"], "450.00")

    def test_cada_linha_leva_o_caminho_da_previa(self):
        """A prévia é interna e abre rascunho -- é o que se quer conferir."""
        orcamento = self.orcamento(status=Orcamento.Status.RASCUNHO)

        dados = self.dossie().json()

        self.assertIn(
            f"/orcamentos/{orcamento.pk}/previa/",
            dados["orcamentos"][0]["previa"],
        )

    def test_diz_quais_canais_o_cadastro_realmente_tem(self):
        """Canal sem cadastro não pode vir marcado na tela.

        O envio falharia, e a pessoa só leria o motivo depois de tentar --
        com o cliente esperando na linha.
        """
        sem_canal = Cliente.objects.create(
            nome_cliente="Sem contato",
            telefone="(11) 98888-7777",
            canal_telefone=Cliente.CanalTelefone.NAO_CONFIRMADO,
        )

        completo = self.dossie().json()["cliente"]
        vazio = self.dossie(sem_canal).json()["cliente"]

        self.assertTrue(completo["email"])
        self.assertTrue(completo["whatsapp_confirmado"])
        self.assertFalse(vazio["email"])
        self.assertFalse(vazio["whatsapp_confirmado"])

    def test_o_ambulante_so_ve_a_propria_carteira_no_historico(self):
        """A carteira individual vale aqui como vale na lista.

        Sem isto, o histórico do cliente viraria a porta dos fundos para
        ver a proposta de um colega.
        """
        ambulante = User.objects.create_user(
            username="ambulante-x", password="x", email="a@example.com",
        )
        atribuir_funcoes(ambulante, ["ambulante"])

        minha = self.orcamento()
        minha.responsavel = ambulante
        minha.save(update_fields=["responsavel"])
        self.orcamento(valor="800.00")  # de outra pessoa

        self.client.force_login(ambulante)
        dados = self.dossie().json()

        ids = [o["id"] for o in dados["orcamentos"]]
        self.assertEqual(ids, [minha.pk])


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class OfertaParaUmClienteTests(TestCase):

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-oferta", password="x", email="g@example.com",
        )
        self.client.force_login(self.gestor)

        categoria = CategoriasBrinquedos.objects.create(nome_categoria="Infláveis")
        brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Cama elástica",
            imagem_brinquedo="imagens_brinquedos/x.jpg",
            descricao="3m", valor_brinquedo=Decimal("280.00"),
            avaliacao=Decimal("5.00"), voltz="110",
        )
        self.promocao = Promocoes.objects.create(
            descricao="Semana da criança",
            brinquedos=brinquedo,
            preco_promocao=Decimal("199.00"),
        )

        self.alvo = Cliente.objects.create(
            nome_cliente="Quem eu quero",
            email="alvo@example.com",
        )
        self.outro = Cliente.objects.create(
            nome_cliente="Quem eu não quero",
            email="outro@example.com",
        )

    def criar(self, **extras):
        dados = {
            "tipo": "promocao",
            "objeto": self.promocao.pk,
            "email": "1",
            "whatsapp": "0",
        }
        dados.update(extras)
        return self.client.post(
            "/site/campanhas/criar/", dados,
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_a_oferta_vai_para_um_cliente_so(self):
        resposta = self.criar(cliente=self.alvo.pk)

        self.assertEqual(resposta.status_code, 201)
        destinos = list(
            EntregaCampanha.objects.values_list("destino", flat=True)
        )
        self.assertEqual(destinos, ["alvo@example.com"])

    def test_sem_cliente_continua_valendo_para_o_segmento_inteiro(self):
        """O caminho antigo não pode ter mudado de comportamento."""
        resposta = self.criar()

        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(EntregaCampanha.objects.count(), 2)

    def test_cliente_sem_canal_recusa_com_uma_frase_que_ajuda(self):
        mudo = Cliente.objects.create(nome_cliente="Sem canal nenhum")

        resposta = self.criar(cliente=mudo.pk)

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("não tem e-mail nem WhatsApp", resposta.json()["msg"])
        self.assertFalse(EntregaCampanha.objects.exists())

    def test_o_envio_individual_entra_no_mesmo_historico_da_divulgacao(self):
        """Não é atalho por fora: é campanha de um destinatário só.

        Se fosse por fora, ninguém depois conseguiria auditar o que foi
        mandado, para quem e quando.
        """
        self.criar(cliente=self.alvo.pk)

        entrega = EntregaCampanha.objects.get()
        self.assertEqual(entrega.cliente, self.alvo)
        self.assertEqual(entrega.campanha.responsavel, self.gestor)
        self.assertEqual(entrega.status, EntregaCampanha.Status.PENDENTE)

    def test_a_lista_de_ofertas_so_traz_o_que_esta_ativo(self):
        desligada = Promocoes.objects.create(
            descricao="Promoção antiga",
            brinquedos=self.promocao.brinquedos,
            preco_promocao=Decimal("99.00"),
            ativo=False,
        )

        dados = self.client.get(
            "/site/campanhas/ofertas/", {"tipo": "promocao"},
            HTTP_HOST="interno.testserver",
        ).json()

        rotulos = [i["rotulo"] for i in dados["itens"]]
        self.assertIn("Semana da criança", rotulos)
        self.assertNotIn(desligada.descricao, rotulos)
