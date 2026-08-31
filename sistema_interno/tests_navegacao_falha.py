"""Clique em item de menu sempre leva a algum lugar.

A navegação suave é um ATALHO por cima do clique num link: em vez de
recarregar a página, ela busca a tela e troca só o miolo. Quando o atalho
funciona, é imperceptível. A pergunta que importa é a outra: e quando não
funciona?

A resposta era um painel -- "A conexão oscilou · tentar novamente" --, e
ele parecia cuidadoso mas era um beco sem saída. A tela pedida não vinha,
a anterior ficava, e quem clicou tinha de clicar de novo. Do lado de quem
usa, isso não é "a conexão oscilou": é a troca de tela falhando.

Três caminhos falhavam, todos verificados no navegador antes desta
correção: rede caindo, servidor devolvendo 500 e -- o pior -- resposta
demorando mais que o prazo, caso em que não aparecia nem o painel. O
clique simplesmente não fazia nada, por doze segundos, duas vezes.

Agora todo caminho de falha entrega ao navegador, que sabe esperar melhor
e tem tela própria para dizer que não deu. Os testes daqui guardam esse
contrato lendo o módulo: não há como abrir o navegador dentro da suíte,
mas dá para provar que nenhum caminho volta a terminar em painel.
"""

from pathlib import Path

from django.test import TestCase


MODULO = (
    Path(__file__).resolve().parent
    / "static" / "interno" / "ls-soft-navigation.js"
)


class NavegacaoSuaveNuncaFicaParadaTests(TestCase):

    def setUp(self):
        self.fonte = MODULO.read_text(encoding="utf-8")

    def test_nenhum_caminho_de_falha_termina_num_painel(self):
        """O painel era o beco sem saída; some com ele o azul do /adm."""
        self.assertNotIn("mostrarFalha", self.fonte)
        self.assertNotIn("ls-nav-recovery", self.fonte)
        self.assertNotIn("data-retry", self.fonte)

        folha = (
            MODULO.parent / "interno_modern.css"
        ).read_text(encoding="utf-8")
        self.assertNotIn(".ls-nav-recovery{", folha)

    def test_falhar_significa_entregar_ao_navegador(self):
        """Falha da busca e falha da troca vão para o mesmo lugar."""
        self.assertIn("function entregarAoNavegador", self.fonte)
        # Uma vez na busca, uma na espera da folha, uma no erro dela, e as
        # do desenho: nenhum ramo pode ficar sem saída.
        self.assertGreaterEqual(self.fonte.count("entregarAoNavegador("), 5)

    def test_nao_se_repete_o_que_uma_segunda_tentativa_nao_resolve(self):
        """Rede ruim repetida é a pessoa esperando duas vezes por nada."""
        trecho = self.fonte[self.fonte.index("}).catch(function (erro) {"):]
        trecho = trecho[:trecho.index("}).finally(")]

        # Só código de "estou ocupado" merece segunda tentativa.
        self.assertIn("erro.status && podeTentarNovamente(erro.status)", trecho)

    def test_o_prazo_de_espera_cabe_na_paciencia_de_quem_clicou(self):
        """Doze segundos parados eram a versão do usuário de "falhou"."""
        linha = next(
            l for l in self.fonte.splitlines() if "var TIMEOUT_REDE" in l
        )
        prazo = int(linha.split("=")[1].strip().rstrip(";"))
        self.assertLessEqual(prazo, 6000)

    def test_a_sequencia_da_navegacao_acompanha_a_troca_inteira(self):
        """A conferência era só depois do fetch, e a troca não acaba ali.

        Depois da resposta ainda vem a espera pela folha de estilo da tela
        nova. Duas telas pedidas em seguida entravam as duas nessa espera,
        e quem terminasse por último desenhava -- que podia ser a
        primeira. O clique mais recente perdia para o antigo.
        """
        self.assertIn(
            "function trocarDocumento(html, url, modoHistorico, minhaNavegacao)",
            self.fonte,
        )
        # Inclusive no caminho do cache, que nem conferia.
        self.assertIn(
            'trocarDocumento(cache, alvo, modoHistorico || "push", minhaNavegacao)',
            self.fonte,
        )
        self.assertIn("minhaNavegacao !== navegacao) return;", self.fonte)

    def test_a_transicao_e_enfeite_e_o_desenho_nao_e(self):
        """Transição abortada não pode levar o desenho junto.

        `startViewTransition` devolve na hora e chama o callback depois.
        Entre uma coisa e outra o navegador pode desistir -- outra
        transição começou, a aba foi para o fundo. Se a desistência
        levasse o callback, a tela nova nunca era desenhada.
        """
        self.assertIn("updateCallbackDone", self.fonte)
        self.assertIn("garantirDesenho", self.fonte)
        # A rede final, para o navegador que não oferece as promessas.
        self.assertIn("window.setTimeout(garantirDesenho", self.fonte)
