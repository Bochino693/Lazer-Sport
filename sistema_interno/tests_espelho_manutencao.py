"""O chamado de manutenção entra inteiro na Ordem de Serviço.

Quem abre uma O.S. a partir de um chamado já tem, no chamado, tudo que a
O.S. pergunta de novo: qual equipamento, o que o cliente relatou, para
onde ir, com quem falar. Redigitar isso é trabalho que o sistema deveria
poupar -- e é trabalho em que se erra: um número de rua trocado manda o
técnico para o lugar errado com o carro cheio.

O que estes testes protegem:

  1. O espelho existe no SERVIDOR, e não nos `data-` de uma <option>.
     Preso à opção, ele sumia junto com ela -- chamado concluído ou fora
     da janela carregada abria o formulário vazio, em silêncio.
  2. O chamado pedido pela URL SEMPRE está disponível para cópia, mesmo
     quando não caberia na fila normal.
  3. O endereço vai completo, com bairro e CEP. Meio endereço obriga
     alguém a abrir o chamado noutra aba, que era o que se queria evitar.
"""

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core.models import ClientePerfil, Manutencao

from .models import OrdemServico
from .views_ordens_servico import espelho_da_manutencao


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class EspelhoDoChamadoTests(TestCase):

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-espelho",
            password="senha-segura",
            email="gestor-espelho@example.com",
        )
        self.client.force_login(self.gestor)

        self.solicitante = User.objects.create_user(
            username="buffet.alegria",
            password="x",
            email="contato@alegria.com.br",
        )
        # O perfil nasce por sinal ao criar o usuário; aqui só se
        # completa o que o cadastro do site preencheria.
        self.perfil, _ = ClientePerfil.objects.get_or_create(
            user=self.solicitante,
        )
        self.perfil.nome_completo = "Maria Alegria"
        self.perfil.telefone = "11988887777"
        self.perfil.save()

    def criar_chamado(self, **extras):
        dados = dict(
            usuario=self.perfil,
            brinquedo_nao_listado=True,
            brinquedo_descricao_livre="Castelo inflável 5x5",
            descricao="Motor soprador falhando e rasgo lateral de 30 cm.",
            telefone_contato="11977776666",
            cep="03310-000",
            endereco="Rua Serra de Bragança",
            numero="1200",
            bairro="Tatuapé",
            cidade="São Paulo",
            estado="SP",
            status="P",
        )
        dados.update(extras)
        return Manutencao.objects.create(**dados)

    def abrir_tela(self, consulta=""):
        return self.client.get(
            f"/ordens-servico/{consulta}", HTTP_HOST="interno.testserver",
        )

    # ------------------------------------------------------------------
    # O conteúdo do espelho
    # ------------------------------------------------------------------
    def test_o_espelho_traz_tudo_que_a_os_perguntaria_de_novo(self):
        chamado = self.criar_chamado()

        espelho = espelho_da_manutencao(chamado)

        self.assertEqual(espelho["equipamento"], "Castelo inflável 5x5")
        self.assertEqual(espelho["defeito_relatado"], chamado.descricao)
        self.assertEqual(espelho["nome_cliente"], "Maria Alegria")
        # Quem abriu o chamado é o responsável no local até que se diga
        # outra coisa: é para ele que o técnico pergunta ao chegar.
        self.assertEqual(espelho["contato"], "Maria Alegria")
        self.assertEqual(espelho["whatsapp_cliente"], "11977776666")
        self.assertEqual(espelho["email_cliente"], "contato@alegria.com.br")
        self.assertEqual(espelho["codigo"], "MAN-%05d" % chamado.id)

    def test_o_endereco_vai_inteiro_com_bairro_e_cep(self):
        """Meio endereço obriga a abrir o chamado noutra aba."""
        espelho = espelho_da_manutencao(self.criar_chamado())

        endereco = espelho["endereco_servico"]
        for pedaco in ("Rua Serra de Bragança", "1200", "Tatuapé",
                       "São Paulo/SP", "03310-000"):
            self.assertIn(pedaco, endereco)

    def test_sem_telefone_no_chamado_usa_o_do_cadastro(self):
        """Um contato vazio é o mesmo que não ter copiado nada."""
        chamado = self.criar_chamado(telefone_contato="")

        self.assertEqual(
            espelho_da_manutencao(chamado)["whatsapp_cliente"], "11988887777",
        )

    # ------------------------------------------------------------------
    # O espelho chega à tela
    # ------------------------------------------------------------------
    def test_a_tela_entrega_o_espelho_de_cada_chamado(self):
        chamado = self.criar_chamado()

        contexto = self.abrir_tela().context["manutencoes_dados"]

        self.assertIn(str(chamado.id), contexto)
        self.assertEqual(
            contexto[str(chamado.id)]["equipamento"], "Castelo inflável 5x5",
        )

    def test_chamado_pedido_pela_url_existe_mesmo_ja_concluido(self):
        """Era aqui que a promessa de poupar digitação se perdia.

        A fila normal só carrega chamados em aberto. Um chamado concluído
        -- ou fora dos cem mais antigos -- não estava na lista, e o link
        que prometia trazer os dados abria o formulário em branco, sem
        avisar que não tinha trazido nada.
        """
        concluido = self.criar_chamado(status="C")

        resposta = self.abrir_tela(f"?novo=1&manutencao={concluido.id}")

        self.assertEqual(resposta.context["manutencao_pedida"], concluido.id)
        self.assertIn(str(concluido.id), resposta.context["manutencoes_dados"])
        self.assertIn(
            concluido.id, [m.id for m in resposta.context["manutencoes"]],
        )

    def test_chamado_inexistente_nao_derruba_a_tela(self):
        resposta = self.abrir_tela("?novo=1&manutencao=99999")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["manutencao_pedida"], 0)

    def test_chamado_que_ja_virou_os_avisa_antes_de_virar_outra(self):
        """Segunda visita é comum; segunda O.S. por engano, não."""
        chamado = self.criar_chamado()
        OrdemServico.objects.create(
            manutencao=chamado,
            equipamento="Castelo inflável 5x5",
            responsavel=self.gestor,
        )

        dados = self.abrir_tela().context["manutencoes_dados"]

        self.assertTrue(dados[str(chamado.id)]["ja_tem_os"])

    def test_o_espelho_e_lido_do_servidor_e_nao_do_data_da_opcao(self):
        """Preso à <option>, o espelho sumia junto com ela."""
        self.criar_chamado()

        corpo = self.abrir_tela().content.decode()

        self.assertIn('id="manutencoesDados"', corpo)
        self.assertIn("function espelharChamado(", corpo)
        # A cópia não pode voltar a depender dos atributos da opção.
        self.assertNotIn("op.dataset.equipamento", corpo)

    def test_a_tela_conta_o_que_copiou(self):
        """Copiar em silêncio tem o mesmo defeito de não copiar."""
        self.criar_chamado()

        corpo = self.abrir_tela().content.decode()

        self.assertIn('id="osEspelhoChamado"', corpo)
        self.assertIn("copiado para esta O.S.", corpo)

    def test_o_pedido_sai_da_url_depois_de_atendido(self):
        """`?novo=1` é uma ordem, não um endereço de tela.

        Deixá-lo na barra fazia a lista, ao ser rebuscada depois de
        gravar, reabrir uma O.S. nova e vazia por cima do que acabara de
        ser salvo.
        """
        corpo = self.abrir_tela("?novo=1").content.decode()

        self.assertIn('searchParams.delete("novo")', corpo)
        self.assertIn('searchParams.delete("manutencao")', corpo)
