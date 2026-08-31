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

    def test_nao_ha_cinza_no_papel(self):
        """Etiqueta não é lida numa tela a 40 cm.

        É lida de pé, a um metro da caixa, na luz do galpão, e muitas
        vezes numa impressora no fim do toner. Todo cinza que parecia
        discreto no navegador desaparecia ali: a empresa, o rótulo
        "entregar a", o conteúdo e a referência sumiam, e sobrava uma
        etiqueta que só dizia "FRÁGIL".

        Hierarquia aqui se faz com tamanho e peso. Baixar o contraste do
        que é secundário é o que apaga a etiqueta inteira.
        """
        import re
        from pathlib import Path

        folha = (
            Path(__file__).resolve().parent
            / "static" / "interno" / "interno_modern.css"
        ).read_text(encoding="utf-8")

        inicio = folha.index("/* ---------------------------------------------------------- o papel")
        bloco = folha[inicio:folha.index("@media print", inicio)]
        # Fora os comentários: eles citam cores para contar a história.
        bloco = re.sub(r"/\*.*?\*/", "", bloco, flags=re.S)

        # Só a TINTA. O fundo da folha na tela (a mesa sob as etiquetas)
        # é escuro de propósito e não vai para o papel: a regra de
        # impressão o troca por branco.
        cinzas = []
        for cor in re.findall(r"color:\s*#([0-9A-Fa-f]{6})", bloco):
            r, v, a = (int(cor[i:i + 2], 16) for i in (0, 2, 4))
            proximo = max(r, v, a) - min(r, v, a) < 34
            meio = 90 < r < 215
            if proximo and meio:
                cinzas.append("#" + cor)

        self.assertEqual(
            cinzas, [],
            "Cinza médio no papel da etiqueta: " + ", ".join(cinzas),
        )

    def test_a_faixa_da_casa_identifica_a_caixa_de_longe(self):
        """Antes de ler qualquer palavra, se acha a caixa pela faixa."""
        from pathlib import Path

        folha = (
            Path(__file__).resolve().parent
            / "static" / "interno" / "interno_modern.css"
        ).read_text(encoding="utf-8")

        inicio = folha.index(".ls-etiqueta-topo{")
        faixa = folha[inicio:folha.index("}", inicio)]

        # O grafite do painel, cheio -- não uma variação clara dele.
        self.assertIn("#13100B", faixa)
        self.assertIn("color:#fff", faixa)

    def test_economizar_tinta_troca_o_preenchido_pelo_traco_e_so(self):
        """Economia de toner não vale uma etiqueta que ninguém lê."""
        from pathlib import Path

        folha = (
            Path(__file__).resolve().parent
            / "static" / "interno" / "interno_modern.css"
        ).read_text(encoding="utf-8")

        economia = [
            linha for linha in folha.splitlines()
            if ".ls-folha-etiquetas.sem-fundo" in linha
        ]
        self.assertTrue(economia, "o modo de economia de tinta sumiu")
        for linha in economia:
            with self.subTest(regra=linha.strip()[:60]):
                # Só preto e branco: nenhuma cor intermediária.
                for cor in ("#000", "#fff"):
                    pass
                self.assertNotIn("#bcae9d", linha)
                self.assertNotIn("var(--muted)", linha)

    def test_a_tela_esta_no_menu(self):
        """Tela que não está no menu é tela que ninguém acha."""
        self.assertIn(
            'href="/etiquetas/"',
            self.client.get("/", HTTP_HOST="interno.testserver").content.decode(),
        )
