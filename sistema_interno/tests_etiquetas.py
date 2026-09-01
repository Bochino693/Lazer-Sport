"""A etiqueta de transporte sai do painel, e não da caneta.

As caixas saíam com "FRÁGIL" escrito a mão no papelão, quando saíam com
alguma coisa. Uma etiqueta escrita à mão não diz de quem é a carga, não
diz para onde vai, e some no meio da fita quando a caixa é reembalada --
e cama elástica, tobogã e inflável viajam em carga fracionada, onde quem
carrega nunca é quem vendeu.
"""

import json

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .models import Cliente


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class EtiquetasTests(TestCase):

    def setUp(self):
        self.equipe = User.objects.create_superuser(
            username="expedicao", password="x", email="e@example.com",
        )
        self.client.force_login(self.equipe)

    def tela(self):
        resposta = self.client.get("/etiquetas/", HTTP_HOST="interno.testserver")
        self.assertEqual(resposta.status_code, 200)
        return resposta.content.decode()

    def empresa(self, html=None):
        """A identidade viaja como JSON; `json_script` escapa o acento.

        Ler o dado, e não o HTML, é o que o navegador faz -- e é o que
        mantém o teste falando do conteúdo em vez da escapagem.
        """
        html = html if html is not None else self.tela()
        marca = '<script id="empresaEtiqueta" type="application/json">'
        inicio = html.index(marca) + len(marca)
        return json.loads(html[inicio:html.index("</script>", inicio)])

    def propostas(self, html=None):
        """As propostas aprovadas que viajaram para a tela, como dado."""
        html = html if html is not None else self.tela()
        marca = '<script id="opcoesPropostasEtiqueta" type="application/json">'
        inicio = html.index(marca) + len(marca)
        return json.loads(html[inicio:html.index("</script>", inicio)])

    def test_a_etiqueta_diz_de_onde_a_caixa_veio(self):
        """Se algo se perder, é para a empresa que ligam."""
        html = self.tela()
        empresa = self.empresa(html)

        self.assertEqual(empresa["nome"], "Fábrica de brinquedos Lazer Sport")
        self.assertEqual(empresa["telefone"], "(11) 96056-3135")
        self.assertEqual(empresa["cnpj"], "54.486.908/0001-86")
        self.assertIn("logoofi.png", html)

    def test_o_contato_impresso_e_o_mesmo_do_resto_da_casa(self):
        """Um contato só: mudou num lugar, muda na etiqueta junto."""
        with override_settings(EMPRESA_TELEFONE="(11) 90000-0000"):
            self.assertEqual(self.empresa()["telefone"], "(11) 90000-0000")

    def test_serve_cliente_cadastrado_e_nome_digitado_na_hora(self):
        """Exigir cadastro mandaria quem fecha a caixa abrir outra tela."""
        Cliente.objects.create(
            nome_cliente="Buffet Alegria", telefone="(11) 97777-6655",
        )

        html = self.tela()

        self.assertIn("Buffet Alegria", html)          # veio da lista
        self.assertIn('id="etiquetaNome"', html)       # e dá para digitar
        self.assertIn('id="etiquetaClienteBox"', html)

    def test_o_endereco_do_cadastro_viaja_junto_para_a_tela(self):
        cliente = Cliente.objects.create(
            nome_cliente="Buffet Alegria", telefone="(11) 97777-6655",
        )
        cliente.enderecos.create(
            endereco="Rua das Flores", numero="120", bairro="Centro",
            cidade="São Paulo", estado="SP", cep="01000-000",
        )

        self.assertIn("Rua das Flores", self.tela())

    def test_os_avisos_de_manuseio_sao_poucos_e_fragil_vem_marcado(self):
        """Etiqueta com sete selos não é lida: quem carrega olha um segundo."""
        html = self.tela()

        self.assertIn('data-aviso="fragil"', html)
        self.assertIn('data-aviso="nao_empilhar"', html)
        self.assertIn('data-aviso="este_lado"', html)
        # Frágil é o padrão -- é a razão de a tela existir.
        posicao = html.index('data-aviso="fragil"')
        self.assertIn("checked", html[posicao:posicao + 260])

    def test_um_volume_por_etiqueta_numerada(self):
        self.assertIn('id="etiquetaVolumes"', self.tela())

    def test_nada_e_gravado(self):
        """Etiqueta é papel: nasce da tela, vai para a impressora e acabou.

        Guardar o histórico de cada etiqueta impressa seria criar uma
        tabela que ninguém consulta para responder uma pergunta que
        ninguém faz.
        """
        from .views_etiquetas import EtiquetasInnerView

        self.assertFalse(hasattr(EtiquetasInnerView, "post"))
        resposta = self.client.post(
            "/etiquetas/", {"nome": "x"}, HTTP_HOST="interno.testserver",
        )
        self.assertEqual(resposta.status_code, 405)

    def test_a_impressao_tira_o_painel_da_frente(self):
        """Menu e formulário no papel gastariam meia folha por etiqueta."""
        from pathlib import Path

        folha = (
            Path(__file__).resolve().parent
            / "static" / "interno" / "interno_modern.css"
        ).read_text(encoding="utf-8")

        impressao = folha[folha.index("@media print"):]
        for fora in (".ls-sidebar", ".ls-topbar", ".ls-etiquetas-form"):
            with self.subTest(elemento=fora):
                self.assertIn(fora, impressao)
        # A faixa preta do aviso é o que se lê de longe, e impressora
        # descarta fundo por padrão.
        self.assertIn("print-color-adjust:exact", impressao)

    def papel(self):
        """As DECLARAÇÕES de CSS que descrevem a etiqueta impressa.

        Os comentários saem antes de devolver. Eles citam de propósito as
        cores que foram embora ("saía com âmbar", "#171310 que o olho lê
        como cinza"), e um teste que procurasse a cor no arquivo inteiro
        acusaria a explicação da correção como se fosse a falha.
        """
        import re
        from pathlib import Path

        folha = (
            Path(__file__).resolve().parent
            / "static" / "interno" / "interno_modern.css"
        ).read_text(encoding="utf-8")
        etiqueta = folha[folha.index("/* ------------------------------------------"
                                     "---------------- o papel"):]
        etiqueta = etiqueta[:etiqueta.index("@media print")]
        return re.sub(r"/\*.*?\*/", " ", etiqueta, flags=re.S)

    def test_o_papel_e_preto_no_branco_e_mais_nada(self):
        """Cor e marrom-quase-preto saem lavados na impressora do galpão.

        A etiqueta tinha faixa âmbar no topo e os rótulos miúdos em
        #171310 -- um marrom que o olho lê como cinza. Laser de galpão
        trabalha em meio-tom com toner no fim: cor vira chapado cinza e
        texto pequeno em marrom sai apagado, justamente nas linhas que
        dizem para onde a caixa vai.

        A única tinta agora é #000 sobre #fff.
        """
        etiqueta = self.papel()

        self.assertIn("border:4px solid #000", etiqueta)
        self.assertIn("background:#fff", etiqueta)
        # O único chapado preto é a faixa do aviso principal -- o que se
        # lê de longe. O topo é moldura, para o logotipo não sumir nela.
        self.assertIn("background:#000;color:#fff", etiqueta)

        for cor in ("#F2A93B", "#171310", "#4A423A", "#6B6055", "#B9AE9C"):
            with self.subTest(cor=cor):
                self.assertNotIn(cor, etiqueta)

    def test_o_miudo_do_papel_vence_o_cinza_global_do_painel(self):
        """A regra de cor da etiqueta perdia sem `!important`, e era isso.

        O painel pinta TODO texto miúdo do aplicativo de cinza quente
        com `.form-text,.small,small{color:...!important}`. Faz sentido
        lá: `small` no painel é sempre legenda sobre fundo escuro.

        Mas a etiqueta é branca, é papel, e mora dentro do painel. Ela
        herdava esse cinza no telefone da empresa, no CNPJ, no número do
        volume e nos rótulos do rodapé -- e as regras de cor da etiqueta,
        que diziam `#000` sem `!important`, perdiam para um `!important`
        escrito centenas de linhas acima. Não era disputa de ordem: cor
        sem `!important` contra cor com `!important` perde sempre, e o
        `#000` da etiqueta era decorativo.

        Este teste existe porque olhar o CSS da etiqueta não mostrava
        nada de errado: só o navegador mostrava.
        """
        from pathlib import Path

        folha = (
            Path(__file__).resolve().parent
            / "static" / "interno" / "interno_modern.css"
        ).read_text(encoding="utf-8")

        # A regra global continua lá -- é ela que torna o `!important`
        # da etiqueta obrigatório. Se um dia sair, este teste avisa que a
        # muleta pode sair junto.
        self.assertIn(".form-text,.small,small{color:#bcae9d!important}", folha)

        # E a etiqueta reivindica o preto de volta, com a mesma força.
        self.assertIn(
            ".ls-etiqueta small,\n.ls-etiqueta .form-text,\n"
            ".ls-etiqueta .small{color:#000!important}",
            folha,
        )

    def test_nenhuma_letra_do_papel_desce_abaixo_do_que_o_laser_imprime(self):
        """Abaixo de ~.6rem a impressora come a letra, e o rótulo some."""
        import re

        for tamanho in re.findall(r"font-size:\.(\d+)rem", self.papel()):
            with self.subTest(tamanho=tamanho):
                self.assertGreaterEqual(
                    int(tamanho.ljust(2, "0")), 62,
                    "corpo miúdo demais para sair legível da impressora",
                )

    def test_as_tres_origens_da_etiqueta(self):
        """Três situações reais do galpão, e cada uma começa de um lugar.

        A PROPOSTA APROVADA é de onde sai quase toda caixa: tudo o que a
        etiqueta precisa já foi digitado uma vez na venda, e redigitar
        com o caminhão esperando é a chance de errar o endereço -- erro
        que só aparece quando a carga volta.

        O CLIENTE resolve a troca em garantia e a peça que ele veio
        buscar. DO ZERO existe porque exigir cadastro antes de imprimir
        mandaria quem fecha a caixa abrir outra tela e voltar.
        """
        html = self.tela()

        self.assertIn('name="origem" value="proposta" checked', html)
        self.assertIn('name="origem" value="cliente"', html)
        self.assertIn('name="origem" value="zero"', html)
        # Cartão, e não `select`: num select fechado só uma das três
        # aparece, e quem não sabe das outras nunca abre a lista.
        self.assertIn("ls-cartoes-escolha", html)

    def test_a_proposta_aprovada_traz_a_etiqueta_pronta(self):
        """Endereço redigitado com o caminhão esperando é endereço errado."""
        from decimal import Decimal

        from .models import ItemOrcamento, Orcamento

        proposta = Orcamento.objects.create(
            nome_cliente="Buffet Alegria",
            whatsapp_cliente="(11) 99999-1111",
            status=Orcamento.Status.APROVADO,
        )
        ItemOrcamento.objects.create(
            orcamento=proposta, descricao="Cama elástica 3,05 m",
            quantidade=Decimal("1.00"), valor_unitario=Decimal("2500.00"),
        )
        ItemOrcamento.objects.create(
            orcamento=proposta, descricao="Piscina de bolinhas",
            quantidade=Decimal("1.00"), valor_unitario=Decimal("900.00"),
        )

        opcoes = self.propostas()
        self.assertEqual(len(opcoes), 1)
        escolhida = opcoes[0]
        self.assertEqual(escolhida["nome"], "Buffet Alegria")
        self.assertEqual(escolhida["contato"], "(11) 99999-1111")
        self.assertEqual(escolhida["referencia"], f"Proposta #{proposta.pk}")
        # O conteúdo é a lista, e não o primeiro item: quem abre a caixa
        # no destino confere contra o que está escrito.
        self.assertIn("Cama elástica 3,05 m", escolhida["conteudo"])
        self.assertIn("Piscina de bolinhas", escolhida["conteudo"])
        # Um volume por item é o palpite certo na maioria das cargas.
        self.assertEqual(escolhida["volumes"], 2)

    def test_a_versao_substituida_nao_vira_etiqueta(self):
        """Ela descreve a carga que foi trocada por outra."""
        from .models import Orcamento

        Orcamento.objects.create(
            nome_cliente="Proposta velha",
            status=Orcamento.Status.SUBSTITUIDO,
        )
        Orcamento.objects.create(
            nome_cliente="Rascunho",
            status=Orcamento.Status.RASCUNHO,
        )
        self.assertEqual(self.propostas(), [])

    def test_a_carga_e_opcional_e_parece_opcional(self):
        """Metade dos campos em branco ensina quem preenche a pular campo.

        Conteúdo, volume e referência só existem quando há pedido. Na
        caixa avulsa eles ficariam vazios -- e quem pula campo pula o
        endereço junto. Fechado, o essencial é o que se vê.
        """
        html = self.tela()

        self.assertIn('<details class="ls-completar-bloco ls-etiqueta-carga"', html)
        self.assertIn("opcional", html)
        # Sem `open`: nasce fechada. A proposta é que a abre, pelo JS,
        # depois de escrever conteúdo e volumes lá dentro.
        self.assertIn('id="etiquetaCarga"', html)
        self.assertNotIn('id="etiquetaCarga" open', html)

    def test_o_papel_segue_o_que_foi_preenchido(self):
        """Não há modo a escolher: campo em branco não imprime.

        A etiqueta sem conteúdo, sem volume e sem referência é a da caixa
        avulsa, e nela o endereço é o documento -- então sai grande.
        """
        html = self.tela()

        self.assertIn(
            'enxuta: !conteudo && !referencia && total === 1', html,
        )
        self.assertIn('dados.enxuta ? " enxuta" : ""', html)

    def test_a_tela_esta_no_menu(self):
        """Tela que não está no menu é tela que ninguém acha."""
        self.assertIn(
            'href="/etiquetas/"',
            self.client.get("/", HTTP_HOST="interno.testserver").content.decode(),
        )
