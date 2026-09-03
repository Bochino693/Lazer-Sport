"""Onde as janelas do painel ficam, e se elas existem de verdade.

ESTE ARQUIVO NASCEU DE DOIS DEFEITOS QUE 890 PROVAS NÃO PEGARAM, porque
nenhuma delas abria uma janela e olhava onde ela tinha ido parar.

1. A CONFIRMAÇÃO DE EXCLUSÃO NO CANTO INFERIOR ESQUERDO.

   No tablet as janelas viravam folha colada na base -- largura cheia,
   topo arredondado, o gesto do aplicativo de telefone. Só que a
   confirmação de exclusão tem largura máxima própria (520px), e essa
   regra ganhava da folha. Sobrava uma folha de 520px com `margin:0`,
   grudada no canto inferior esquerdo de uma tela de 800, com 280 pixels
   de vazio à direita.

2. QUATRO JANELAS DA TELA DE O.S. QUE NÃO ABRIAM DE JEITO NENHUM.

   Faltava um `</div>` no meio do formulário da O.S. O navegador então
   fechava `#modalOS` só no fim do bloco -- e Enviar, Pagamento, Refazer
   e Excluir, que vêm depois no arquivo, viravam FILHOS de uma janela
   fechada. Filho de elemento com `display:none` não aparece: clicar em
   "Excluir" numa O.S. não mostrava nada. Nenhum teste percebeu, porque
   HTML mal fechado não levanta erro: o navegador conserta do jeito dele.

QUEM PEGA CADA UM. O `</div>` faltando aparece na contagem: a tela termina
com uma `<div>` em aberto, e é esse o teste que falha quando se tira a
correção -- conferido. O outro, janela dentro de janela, pega o caso em
que alguém escreve um modal dentro do outro de propósito, que também
nunca funciona. São defeitos parecidos com causas diferentes, e cada um
precisa do seu.
"""

from html.parser import HTMLParser

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase


#: Telas do painel que têm janela. Uma tela nova com modal entra aqui.
TELAS = (
    "/clientes/",
    "/estoque/",
    "/estoque/materiais/",
    "/orcamentos/",
    "/ordens-servico/",
    "/producao/ordens/",
    "/producao/guias/",
    "/producao/produtos/",
    "/equipe/",
)


class _Aninhamento(HTMLParser):
    """Segue a pilha de `<div>` e anota toda janela dentro de janela."""

    VAZIAS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pilha = []
        self.modais_abertos = []
        self.aninhados = []
        self.divs_abertas = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.VAZIAS:
            return
        atributos = dict(attrs)
        classes = (atributos.get("class") or "").split()
        e_modal = "modal" in classes
        if tag == "div":
            self.divs_abertas += 1
        if e_modal:
            nome = atributos.get("id") or "(sem id)"
            if self.modais_abertos:
                self.aninhados.append((nome, self.modais_abertos[-1]))
            self.modais_abertos.append(nome)
        self.pilha.append((tag, e_modal))

    def handle_endtag(self, tag):
        if tag in self.VAZIAS:
            return
        for i in range(len(self.pilha) - 1, -1, -1):
            if self.pilha[i][0] == tag:
                for _, era_modal in self.pilha[i:]:
                    if era_modal and self.modais_abertos:
                        self.modais_abertos.pop()
                if tag == "div":
                    self.divs_abertas -= 1
                del self.pilha[i:]
                return


class JanelasDoPainelTests(TestCase):

    def setUp(self):
        cache.clear()
        self.gestor = User.objects.create_superuser("gestor", "g@example.com", "x")
        self.client.force_login(self.gestor)

    def html(self, rota):
        resposta = self.client.get(rota, HTTP_HOST="interno.testserver")
        self.assertEqual(resposta.status_code, 200, rota)
        return resposta.content.decode()

    def test_nenhuma_janela_mora_dentro_de_outra(self):
        """Janela dentro de janela nunca abre: a de fora está escondida.

        Filho de elemento com `display:none` não é desenhado. Foi esse o
        efeito, na tela de Ordens de Serviço, de um `</div>` faltando
        cinquenta linhas acima -- embora quem pegue AQUELE caso seja o
        teste de contagem abaixo. Este aqui cobre o modal escrito dentro
        do outro, que dá no mesmo e é mais fácil de fazer sem perceber.
        """
        for rota in TELAS:
            leitor = _Aninhamento()
            leitor.feed(self.html(rota))
            self.assertEqual(
                leitor.aninhados, [],
                f"em {rota}, janela dentro de janela: "
                + ", ".join(f"{d} dentro de {f}" for d, f in leitor.aninhados),
            )

    def test_as_telas_fecham_as_divs_que_abrem(self):
        """A causa, e não só o sintoma.

        HTML mal fechado não levanta erro: o navegador conserta do jeito
        dele, e o jeito dele foi pôr quatro janelas dentro de uma quinta.
        """
        for rota in TELAS:
            leitor = _Aninhamento()
            leitor.feed(self.html(rota))
            self.assertEqual(
                leitor.divs_abertas, 0,
                f"{rota} termina com {leitor.divs_abertas} <div> em aberto",
            )


class PosicaoDasJanelasTests(TestCase):
    """As regras de posição, lidas onde elas moram.

    O navegador é quem diz a verdade sobre layout, e a conferência visual
    foi feita lá -- 120 aberturas de janela, em 390, 800 e 1400 pixels.
    O que se trava aqui é a decisão: no celular, folha na base; no tablet,
    janela centrada. Foi misturar as duas que pôs a confirmação de
    exclusão no canto.
    """

    def css(self):
        from pathlib import Path

        return (
            Path(__file__).parent / "static/interno/interno_modern.css"
        ).read_text(encoding="utf-8")

    def test_no_celular_a_folha_vence_a_largura_maxima_da_janela(self):
        """Sem `!important`, os 520px da exclusão desalinham a folha."""
        self.assertIn("width:100%;max-width:none!important", self.css())

    def test_no_tablet_a_janela_e_centrada(self):
        css = self.css()
        self.assertIn("@media (min-width:601px) and (max-width:900px){", css)
        # `margin:auto` nos quatro lados é o que centra dentro do flex.
        self.assertIn("margin:auto!important;padding:0!important", css)

    def test_a_folha_colada_na_base_nao_alcanca_o_tablet(self):
        """Era o `max-width:900px` que trazia a folha para a tela de 800."""
        css = self.css()
        self.assertNotIn(
            "@media (max-width:900px){\n  .modal-dialog{margin:0;align-items:flex-end",
            css,
        )
        self.assertIn(
            "@media (max-width:600px){\n  .modal-dialog{margin:0;align-items:flex-end",
            css,
        )
