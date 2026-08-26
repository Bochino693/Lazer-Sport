"""A aba de clientes do painel interno.

O painel responde no subdomínio interno, então todo teste aqui usa
HTTP_HOST="interno.testserver" — sem isso o SubdomainURLMiddleware não
liga `is_interno` e a view devolve um desvio, que é o mesmo que o usuário
veria.

O que estes testes protegem:

  * o buffet e o cliente comum moram na mesma lista, com papéis
    diferentes — e o vínculo entre os dois é o que responde "quais
    clientes vieram por este parceiro";
  * cadastro sem forma de contato não entra: é linha morta que só suja a
    busca;
  * nome repetido é barrado, porque duplicata parte o histórico do
    cliente em dois;
  * cliente com proposta no histórico não é apagado por engano;
  * dá para cadastrar cliente de dentro do orçamento, com a mesma regra.
"""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core.models import Clientes as ClienteMapa

from .models import Cliente, EnderecoCliente, Orcamento
from .permissoes import atribuir_funcoes


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class ClientesInternoTests(TestCase):

    URL = "/clientes/"

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor",
            password="senha-segura",
            email="gestor@example.com",
        )
        self.client.force_login(self.gestor)

        self.buffet = Cliente.objects.create(
            nome_cliente="Buffet Alegria",
            tipo=Cliente.Tipo.BUFFET,
            telefone="(11) 3333-4444",
        )

    def abrir(self, **filtros):
        return self.client.get(
            self.URL,
            filtros,
            HTTP_HOST="interno.testserver",
        )

    def post(self, dados):
        return self.client.post(
            self.URL,
            dados,
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    # ------------------------------------------------------------ tela
    def test_tela_abre_e_lista_o_cadastro(self):
        resposta = self.abrir()

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Buffet Alegria")
        self.assertEqual(resposta.context["total_buffets"], 1)

    def test_colaborador_sem_gerencia_nao_entra(self):
        self.client.logout()
        montador = User.objects.create_user(
            username="montador",
            password="senha-segura",
            is_staff=True,
        )
        atribuir_funcoes(montador, ["producao"])
        self.client.login(username="montador", password="senha-segura")

        resposta = self.abrir()

        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/producao/", resposta["Location"])

    # -------------------------------------------------------- cadastro
    def test_cadastra_cliente_ligado_ao_buffet(self):
        resposta = self.post({
            "action": "save",
            "nome_cliente": "Marina Souza",
            "tipo": Cliente.Tipo.PESSOA,
            "telefone": "(11) 99999-8888",
            "parceiro": self.buffet.id,
        })

        self.assertEqual(resposta.status_code, 200)
        cliente = Cliente.objects.get(nome_cliente="Marina Souza")
        self.assertEqual(cliente.parceiro, self.buffet)
        self.assertEqual(list(self.buffet.clientes_atendidos.all()), [cliente])

    def test_buffet_nao_vem_por_outro_buffet(self):
        """Parceiro de parceiro cria um vínculo que nenhuma tela desenha."""
        self.post({
            "action": "save",
            "nome_cliente": "Buffet Estrela",
            "tipo": Cliente.Tipo.BUFFET,
            "telefone": "(11) 2222-1111",
            "parceiro": self.buffet.id,
        })

        novo = Cliente.objects.get(nome_cliente="Buffet Estrela")
        self.assertIsNone(novo.parceiro)

    def test_cadastro_sem_contato_e_recusado(self):
        resposta = self.post({
            "action": "save",
            "nome_cliente": "Cliente fantasma",
            "tipo": Cliente.Tipo.PESSOA,
        })

        self.assertEqual(resposta.status_code, 400)
        self.assertIn("contato", resposta.json()["msg"])
        self.assertFalse(
            Cliente.objects.filter(nome_cliente="Cliente fantasma").exists()
        )

    def test_telefone_incompleto_e_recusado(self):
        resposta = self.post({
            "action": "save",
            "nome_cliente": "Telefone curto",
            "telefone": "99999",
        })

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(Cliente.objects.count(), 1)

    def test_nome_repetido_e_barrado(self):
        resposta = self.post({
            "action": "save",
            "nome_cliente": "buffet alegria",
            "telefone": "(11) 98888-7777",
        })

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(Cliente.objects.count(), 1)

    def test_telefone_com_mascara_cabe_no_cadastro(self):
        """O campo tinha 14 caracteres e um celular com máscara tem 15."""
        self.post({
            "action": "save",
            "nome_cliente": "Celular completo",
            "telefone": "(11) 99999-8888",
        })

        cliente = Cliente.objects.get(nome_cliente="Celular completo")
        self.assertEqual(cliente.telefone, "(11) 99999-8888")

    def test_endereco_entra_junto_do_cadastro(self):
        self.post({
            "action": "save",
            "nome_cliente": "Com endereço",
            "telefone": "(11) 99999-0000",
            "cep": "02909-000",
            "endereco": "Rua das Palmeiras",
            "numero": "120",
            "bairro": "Centro",
            "cidade": "São Paulo",
            "estado": "SP",
        })

        cliente = Cliente.objects.get(nome_cliente="Com endereço")
        endereco = cliente.endereco_principal
        self.assertEqual(endereco.cidade, "São Paulo")

    @patch("sistema_interno.clientes.buscar_dados_cep", return_value=None)
    def test_endereco_pela_metade_avisa_em_vez_de_salvar_torto(self, _buscar):
        resposta = self.post({
            "action": "save",
            "nome_cliente": "Endereço solto",
            "telefone": "(11) 99999-0000",
            "cep": "02909-000",
        })

        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(
            Cliente.objects.filter(nome_cliente="Endereço solto").exists()
        )

    @patch(
        "sistema_interno.clientes.buscar_coordenadas_cep_rapido",
        return_value=(-23.55052, -46.633308),
    )
    @patch("sistema_interno.clientes.buscar_dados_cep")
    def test_consulta_cep_preenche_o_formulario(self, buscar, _coordenadas):
        buscar.return_value = {
            "cep": "02909000",
            "rua": "Rua das Palmeiras",
            "bairro": "Centro",
            "cidade": "São Paulo",
            "estado": "SP",
        }

        resposta = self.client.get(
            "/clientes/consultar-cep/",
            {"cep": "02909-000"},
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["endereco"]["cidade"], "São Paulo")
        self.assertEqual(resposta.json()["endereco"]["bairro"], "Centro")
        self.assertEqual(resposta.json()["endereco"]["latitude"], -23.55052)

    @patch("sistema_interno.clientes.buscar_dados_cep")
    def test_bairro_vazio_e_completado_no_servidor_ao_salvar(self, buscar):
        """Rua/cidade preenchidas pelo navegador não podem impedir o bairro."""
        buscar.return_value = {
            "cep": "02909000",
            "rua": "Rua das Palmeiras",
            "bairro": "Jardim Pery",
            "cidade": "São Paulo",
            "estado": "SP",
        }

        resposta = self.post({
            "action": "save",
            "nome_cliente": "Cliente com bairro",
            "telefone": "(11) 99999-0000",
            "cep": "02909-000",
            "endereco": "Rua das Palmeiras",
            "bairro": "",
            "cidade": "São Paulo",
            "estado": "SP",
        })

        self.assertEqual(resposta.status_code, 200)
        endereco = Cliente.objects.get(
            nome_cliente="Cliente com bairro"
        ).endereco_principal
        self.assertEqual(endereco.bairro, "Jardim Pery")

    def test_endereco_alterado_nao_conserva_coordenada_antiga(self):
        cliente = Cliente.objects.create(
            nome_cliente="Cliente que mudou",
            telefone="(11) 99999-0000",
        )
        EnderecoCliente.objects.create(
            cliente=cliente,
            cep="01001-000",
            endereco="Praça da Sé",
            numero="1",
            bairro="Sé",
            cidade="São Paulo",
            estado="SP",
            latitude="-23.550520",
            longitude="-46.633308",
        )

        resposta = self.post({
            "action": "save",
            "id": cliente.pk,
            "nome_cliente": cliente.nome_cliente,
            "telefone": cliente.telefone,
            "tipo": Cliente.Tipo.PESSOA,
            "cep": "20040-020",
            "endereco": "Rua da Assembleia",
            "numero": "10",
            "bairro": "Centro",
            "cidade": "Rio de Janeiro",
            "estado": "RJ",
            "latitude": "",
            "longitude": "",
        })

        self.assertEqual(resposta.status_code, 200)
        endereco = cliente.enderecos.get()
        self.assertIsNone(endereco.latitude)
        self.assertIsNone(endereco.longitude)

    @patch(
        "core.models.geocodificar_endereco",
        return_value=(-23.550520, -46.633308, "rua"),
    )
    def test_orcamento_aprovado_publica_cliente_no_mapa(self, _geocodificar):
        cliente = Cliente.objects.create(
            nome_cliente="Escola Horizonte",
            tipo=Cliente.Tipo.EMPRESA,
            telefone="(11) 95555-1111",
        )
        EnderecoCliente.objects.create(
            cliente=cliente,
            cep="01001-000",
            endereco="Praça da Sé",
            numero="10",
            bairro="Sé",
            cidade="São Paulo",
            estado="SP",
        )

        resposta = self.client.post(
            "/orcamentos/",
            {
                "action": "save",
                "cliente": cliente.id,
                "status": Orcamento.Status.APROVADO,
                "itens": (
                    '[{"descricao":"Locação","quantidade":"1",'
                    '"valor_unitario":"300,00"}]'
                ),
            },
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(resposta.status_code, 200)
        cliente.refresh_from_db()
        self.assertIsNotNone(cliente.cliente_mapa_id)
        mapa = cliente.cliente_mapa
        self.assertEqual(mapa.descricao_cliente, "Escola Horizonte")
        self.assertEqual(mapa.cidade, "São Paulo")
        self.assertTrue(mapa.exibir_no_mapa)
        self.assertEqual(ClienteMapa.objects.count(), 1)

    def test_pode_associar_cliente_que_ja_estava_no_mapa(self):
        mapa = ClienteMapa.objects.create(
            descricao_cliente="Cliente antigo",
            cidade="Osasco",
            estado="SP",
            latitude=Decimal("-23.5320"),
            longitude=Decimal("-46.7910"),
        )

        resposta = self.post({
            "action": "save",
            "nome_cliente": "Cliente antigo",
            "telefone": "(11) 94444-2222",
            "cliente_mapa": mapa.id,
        })

        self.assertEqual(resposta.status_code, 200)
        interno = Cliente.objects.get(nome_cliente="Cliente antigo")
        self.assertEqual(interno.cliente_mapa, mapa)

    def test_buffet_aprovado_nao_duplica_o_parceiro_como_cliente_do_mapa(self):
        EnderecoCliente.objects.create(
            cliente=self.buffet,
            cep="01001-000",
            endereco="Praça da Sé",
            numero="30",
            bairro="Sé",
            cidade="São Paulo",
            estado="SP",
        )

        resposta = self.client.post(
            "/orcamentos/",
            {
                "action": "save",
                "cliente": self.buffet.id,
                "status": Orcamento.Status.APROVADO,
                "itens": (
                    '[{"descricao":"Locação","quantidade":"1",'
                    '"valor_unitario":"300,00"}]'
                ),
            },
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(ClienteMapa.objects.count(), 0)

    def test_edicao_nao_reclama_do_proprio_nome(self):
        resposta = self.post({
            "action": "save",
            "id": self.buffet.id,
            "nome_cliente": "Buffet Alegria",
            "tipo": Cliente.Tipo.BUFFET,
            "telefone": "(11) 3333-0000",
        })

        self.assertEqual(resposta.status_code, 200)
        self.buffet.refresh_from_db()
        self.assertEqual(self.buffet.telefone, "(11) 3333-0000")

    # -------------------------------------------------------- exclusão
    def test_cliente_com_proposta_nao_e_apagado(self):
        Orcamento.objects.create(
            cliente=self.buffet,
            nome_cliente="Buffet Alegria",
        )

        resposta = self.post({"action": "delete", "id": self.buffet.id})

        self.assertEqual(resposta.status_code, 400)
        self.assertTrue(Cliente.objects.filter(pk=self.buffet.pk).exists())

    def test_buffet_com_clientes_nao_e_apagado(self):
        Cliente.objects.create(
            nome_cliente="Atendido",
            telefone="(11) 91111-2222",
            parceiro=self.buffet,
        )

        resposta = self.post({"action": "delete", "id": self.buffet.id})

        self.assertEqual(resposta.status_code, 400)
        self.assertTrue(Cliente.objects.filter(pk=self.buffet.pk).exists())

    def test_cliente_sem_historico_e_apagado(self):
        solto = Cliente.objects.create(
            nome_cliente="Cadastro errado",
            telefone="(11) 91234-5678",
        )

        resposta = self.post({"action": "delete", "id": solto.id})

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Cliente.objects.filter(pk=solto.pk).exists())

    # ---------------------------------------------------------- busca
    def test_busca_encontra_pelo_telefone_sem_mascara(self):
        Cliente.objects.create(
            nome_cliente="Pedro Lima",
            telefone="(11) 97777-6655",
        )

        resposta = self.abrir(q="977776655")

        nomes = [f["obj"].nome_cliente for f in resposta.context["fichas"]]
        self.assertEqual(nomes, ["Pedro Lima"])

    def test_filtro_por_buffet_mostra_quem_veio_por_ele(self):
        Cliente.objects.create(
            nome_cliente="Cliente do parceiro",
            telefone="(11) 95555-4444",
            parceiro=self.buffet,
        )
        Cliente.objects.create(
            nome_cliente="Cliente direto",
            telefone="(11) 94444-3333",
        )

        resposta = self.abrir(parceiro=self.buffet.id)

        nomes = [f["obj"].nome_cliente for f in resposta.context["fichas"]]
        self.assertEqual(nomes, ["Cliente do parceiro"])

    def test_ficha_soma_o_que_o_cliente_ja_fechou(self):
        from .models import ItemOrcamento

        aprovado = Orcamento.objects.create(
            cliente=self.buffet,
            status=Orcamento.Status.APROVADO,
        )
        ItemOrcamento.objects.create(
            orcamento=aprovado,
            descricao="Cama elástica",
            quantidade=2,
            valor_unitario=Decimal("300.00"),
        )
        Orcamento.objects.create(
            cliente=self.buffet,
            status=Orcamento.Status.ENVIADO,
        )

        resposta = self.abrir()
        ficha = resposta.context["fichas"][0]

        self.assertEqual(ficha["orcamentos"], 2)
        self.assertEqual(ficha["aprovados"], 1)
        self.assertEqual(ficha["abertos"], 1)
        self.assertEqual(ficha["total_aprovado"], Decimal("600.00"))


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class ClienteDentroDoOrcamentoTests(TestCase):
    """O cadastro rápido não pode nascer com regra mais frouxa."""

    URL = "/orcamentos/"

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor",
            password="senha-segura",
            email="gestor@example.com",
        )
        self.client.force_login(self.gestor)

    def post(self, dados):
        return self.client.post(
            self.URL,
            dados,
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_cadastra_cliente_sem_sair_do_orcamento(self):
        resposta = self.post({
            "action": "cliente_novo",
            "nome_cliente": "Festa da Ana",
            "telefone": "(11) 96666-5555",
        })

        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertEqual(dados["status"], "sucesso")
        self.assertEqual(dados["cliente"]["rotulo"], "Festa da Ana")
        self.assertTrue(
            Cliente.objects.filter(nome_cliente="Festa da Ana").exists()
        )

    def test_cadastro_rapido_tambem_exige_contato(self):
        resposta = self.post({
            "action": "cliente_novo",
            "nome_cliente": "Sem telefone",
        })

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(Cliente.objects.count(), 0)

    @patch("sistema_interno.clientes.buscar_dados_cep")
    def test_cadastro_rapido_guarda_endereco_pelo_cep(self, buscar):
        buscar.return_value = {
            "cep": "01001000",
            "rua": "Praça da Sé",
            "bairro": "Sé",
            "cidade": "São Paulo",
            "estado": "SP",
        }
        resposta = self.post({
            "action": "cliente_novo",
            "nome_cliente": "Cliente do orçamento",
            "telefone": "(11) 96666-1111",
            "cep": "01001-000",
            "numero": "40",
        })

        self.assertEqual(resposta.status_code, 200)
        endereco = Cliente.objects.get(
            nome_cliente="Cliente do orçamento"
        ).endereco_principal
        self.assertEqual(endereco.endereco, "Praça da Sé")
        self.assertEqual(endereco.cidade, "São Paulo")
        dados = resposta.json()["cliente"]
        self.assertEqual(dados["whatsapp"], "(11) 96666-1111")
        self.assertEqual(dados["endereco"]["bairro"], "Sé")


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class MenuInternoTests(TestCase):
    """O menu não pode oferecer caminho que a view devolve como desvio."""

    def test_gestor_ve_o_atalho_de_clientes(self):
        gestor = User.objects.create_superuser(
            username="gestor",
            password="senha-segura",
            email="gestor@example.com",
        )
        self.client.force_login(gestor)

        resposta = self.client.get("/", HTTP_HOST="interno.testserver")

        self.assertContains(resposta, 'href="/clientes/"')

    def test_colaborador_nao_ve_o_atalho(self):
        montador = User.objects.create_user(
            username="montador",
            password="senha-segura",
            is_staff=True,
        )
        atribuir_funcoes(montador, ["producao"])
        self.client.login(username="montador", password="senha-segura")

        resposta = self.client.get(
            "/producao/",
            HTTP_HOST="interno.testserver",
        )

        self.assertNotContains(resposta, 'href="/clientes/"')
