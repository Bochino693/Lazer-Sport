"""O filtro troca a lista, e não a tela inteira.

O QUE ESTES TESTES PROTEGEM

Um clique num cartão de filtro baixava a tela inteira: 380 KB medidos na
tela de Ordens de Serviço com 600 registros, dos quais 207 eram trecho
idêntico ao que já estava aberto -- a lista de clientes do autocompletar,
o script da tela, os modais. Baixado, analisado e jogado fora, a cada
toque.

Agora o navegador pede `X-LS-Fragmento: lista` e recebe só os quatro
trechos que mudam. O que se protege aqui é o contrato dessa troca, que
tem duas metades igualmente frágeis:

  * O SERVIDOR devolve as partes marcadas, e SÓ elas -- sem cabeçalho,
    sem menu, sem modal. E, com o pedido reduzido, também deixa de
    PRODUZIR o que não vai mandar.

  * O NAVEGADOR troca tudo ou não troca nada. Meia troca deixaria a
    tabela de um filtro sob os cartões de outro.
"""

from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase

from .models import Cliente, Orcamento, OrdemServico

RAIZ = Path(__file__).resolve().parent


class PartesDaListaTests(TestCase):
    """O servidor devolve o pedaço quando o pedaço é pedido."""

    @classmethod
    def setUpTestData(cls):
        cls.gestor = User.objects.create_superuser(
            username="gestor-partes",
            password="senha-segura",
            email="gestor-partes@example.com",
        )
        cls.cliente = Cliente.objects.create(nome_cliente="Buffet do Teste")
        cls.orcamento = Orcamento.objects.create(
            nome_cliente="Buffet do Teste",
            cliente=cls.cliente,
            status=Orcamento.Status.RASCUNHO,
        )
        cls.ordem = OrdemServico.objects.create(
            nome_cliente="Buffet do Teste",
            cliente=cls.cliente,
            equipamento="Piscina de bolinhas",
        )

    def setUp(self):
        self.client.force_login(self.gestor)

    def pedaco(self, caminho):
        return self.client.get(
            caminho, HTTP_HOST="interno.testserver",
            HTTP_X_LS_FRAGMENTO="lista",
        )

    def inteira(self, caminho):
        return self.client.get(caminho, HTTP_HOST="interno.testserver")

    # ------------------------------------------------------------------

    def test_o_pedaco_traz_as_partes_e_dispensa_a_moldura(self):
        for caminho in ("/orcamentos/", "/ordens-servico/"):
            with self.subTest(tela=caminho):
                corpo = self.pedaco(caminho).content.decode()

                # As quatro partes que o filtro troca.
                for parte in ("cartoes", "dinheiro", "lista", "dados"):
                    self.assertIn(f'data-ls-parte="{parte}"', corpo)

                # E nada da moldura: ela já está na tela de quem pediu.
                self.assertNotIn("<html", corpo)
                self.assertNotIn("ls-sidebar", corpo)
                self.assertNotIn('class="modal', corpo)

    def test_a_tela_inteira_continua_inteira(self):
        """O mesmo endereço, sem o cabeçalho, devolve a página de sempre."""
        for caminho, marca in (
            ("/orcamentos/", "modalOrcamento"),
            ("/ordens-servico/", "modalOS"),
        ):
            with self.subTest(tela=caminho):
                corpo = self.inteira(caminho).content.decode()
                self.assertIn("<html", corpo)
                self.assertIn("ls-sidebar", corpo)
                self.assertIn(marca, corpo)
                # As partes existem nas duas respostas -- é o mesmo
                # `{% include %}`, e é isso que impede as duas versões
                # da tabela de divergirem.
                self.assertIn('data-ls-parte="lista"', corpo)

    def test_a_mesma_url_com_duas_respostas_avisa_os_caches(self):
        """Sem `Vary`, um cache serviria o pedaço a quem pediu a tela."""
        for caminho in ("/orcamentos/", "/ordens-servico/"):
            with self.subTest(tela=caminho):
                for resposta in (self.inteira(caminho), self.pedaco(caminho)):
                    self.assertIn("X-LS-Fragmento", resposta["Vary"])

    def test_o_pedaco_nao_carrega_o_que_so_o_formulario_usa(self):
        """Baixar menos é metade; a outra é não produzir o que não vai."""
        corpo = self.pedaco("/ordens-servico/").content.decode()
        # A lista de clientes do autocompletar era o maior trecho da
        # resposta (84 KB medidos com 300 clientes) e não muda com o
        # filtro.
        self.assertNotIn("clientesOSDados", corpo)
        self.assertNotIn("manutencoesDados", corpo)

        corpo = self.pedaco("/orcamentos/").content.decode()
        self.assertNotIn("modalOrcamento", corpo)

    def test_o_pedaco_pesa_menos_que_a_tela(self):
        for caminho in ("/orcamentos/", "/ordens-servico/"):
            with self.subTest(tela=caminho):
                self.assertLess(
                    len(self.pedaco(caminho).content),
                    len(self.inteira(caminho).content),
                )

    def test_o_filtro_escolhido_chega_ao_pedaco(self):
        """O pedaço é da consulta pedida, não da consulta padrão."""
        corpo = self.pedaco("/orcamentos/?filtro=rascunhos").content.decode()
        self.assertIn('href="?filtro=rascunhos"', corpo)
        # O cartão escolhido chega aceso: quem troca os trechos não
        # precisa adivinhar qual acender.
        self.assertIn("active", corpo)


class ContratoDaTrocaPorPartesTests(TestCase):
    """A metade do navegador."""

    def navegacao(self):
        return (
            RAIZ / "static" / "interno" / "ls-soft-navigation.js"
        ).read_text(encoding="utf-8")

    def test_o_pedido_reduzido_sai_com_o_cabecalho_combinado(self):
        codigo = self.navegacao()
        self.assertIn('cabecalhos["X-LS-Fragmento"] = "lista"', codigo)
        # E o servidor confirma o que mandou: uma resposta de login
        # ignora o cabeçalho e devolve a página inteira.
        self.assertIn(
            'var veioPedaco = resposta.headers.get("X-LS-Fragmento") === "lista";',
            codigo,
        )

    def test_ou_troca_tudo_ou_nao_troca_nada(self):
        """Meia troca é pior do que a espera que se quer evitar."""
        codigo = self.navegacao()
        trecho = codigo[codigo.index("function trocarPartes("):]
        trecho = trecho[:trecho.index("\n  }\n")]
        # Trecho sem correspondente na tela derruba a troca inteira...
        self.assertIn("if (!aqui) return false;", trecho)
        # ...e isso acontece ANTES de qualquer substituição.
        self.assertLess(
            trecho.index("if (!aqui) return false;"),
            trecho.index("replaceWith"),
        )

    def test_quem_desiste_do_pedaco_pede_a_tela_inteira(self):
        codigo = self.navegacao()
        self.assertIn("removerChave(chave(urlFinal, true));", codigo)
        self.assertIn("return buscar(alvo, false, false).then(", codigo)

    def test_a_tela_e_o_pedaco_moram_em_gavetas_diferentes(self):
        """Guardados juntos, um clique no menu serviria o pedaço."""
        codigo = self.navegacao()
        self.assertIn('return PREFIXO + (pedaco ? "parte:" : "") + url.href;', codigo)

    def test_a_antecipacao_pede_no_formato_em_que_vai_usar(self):
        """Antecipar inteira e usar pedaço pagaria a rede duas vezes."""
        codigo = self.navegacao()
        trecho = codigo[codigo.index("function anteciparTela("):]
        trecho = trecho[:trecho.index("\n  }\n")]
        self.assertIn("var pedaco = ehTrocaDeLista(url);", trecho)
        self.assertIn("buscar(url, true, pedaco)", trecho)

    def test_depois_de_gravar_a_tela_vem_inteira(self):
        """Gravar muda coisas que não estão nos trechos."""
        codigo = self.navegacao()
        self.assertIn(
            'navegar(window.location.href, "replace", { inteira: true })', codigo,
        )
        self.assertIn("!(opcoes && opcoes.inteira) && ehTrocaDeLista(alvo)", codigo)

    def test_a_montagem_alcanca_so_o_que_chegou(self):
        """`montarTela(document)` passaria de novo pelos modais."""
        import re

        codigo = self.navegacao()
        trecho = codigo[codigo.index("function trocarPartes("):]
        trecho = trecho[:trecho.index("\n  }\n")]
        # Sem os comentários: eles explicam justamente o que NÃO se faz.
        trecho = re.sub(r"/\*.*?\*/", "", trecho, flags=re.S)
        self.assertIn("window.Painel.montarTela(novo);", trecho)
        self.assertNotIn("montarTela(document)", trecho)


class DadosDaLinhaNaoEnvelhecemTests(TestCase):
    """Abrir a terceira linha não pode trazer a terceira linha de antes.

    O JSON das linhas viaja dentro do pedaço, então ele é SUBSTITUÍDO a
    cada filtro. Uma variável lida uma vez, no início do script da tela,
    guardaria as linhas do filtro anterior para sempre.
    """

    def gabarito(self, nome):
        return (RAIZ / "templates" / nome).read_text(encoding="utf-8")

    def test_a_leitura_e_presa_ao_no_e_nao_ao_conteudo(self):
        for nome, funcao, no in (
            ("ordens_servico_inner.html", "ordensAtuais", "ordensServicoDados"),
            ("orcamentos_inner.html", "orcamentosAtuais", "orcamentosDados"),
        ):
            with self.subTest(tela=nome):
                texto = self.gabarito(nome)
                self.assertIn(f"function {funcao}()", texto)
                self.assertIn(f'document.getElementById("{no}")', texto)
                # Trocado o trecho, o elemento é outro e o JSON é lido
                # de novo -- sem evento e sem nada para lembrar de chamar.
                self.assertIn("if (no !== _noDe", texto)

    def test_ninguem_le_o_json_uma_vez_so(self):
        """A variável antiga não pode ter sobrado em canto nenhum."""
        self.assertNotIn(
            'var ordens = JSON.parse(document.getElementById("ordensServicoDados")',
            self.gabarito("ordens_servico_inner.html"),
        )
        self.assertNotIn(
            "var orcamentos = JSON.parse(",
            self.gabarito("orcamentos_inner.html"),
        )
