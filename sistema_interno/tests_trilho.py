"""O menu fechado é uma coluna de ícones -- e nada além disso.

O DEFEITO, DITO COMO A FÁBRICA VIU

"No meu drawer de navegação, posso usar rolagem para a direita quando ele
está fechado; isso não deveria acontecer, somente ficar os ícones ali."

Estava certo. Medido no navegador, com o menu fechado: 83px de largura
visível para 283px de área rolável. Duzentos pixels de vazio que o dedo
alcançava e que não tinham nada dentro.

A CAUSA, QUE NÃO ESTAVA ONDE PARECIA

`.ls-nav` tinha `overflow-y:auto` e mais nada. Só que o CSS não permite
um eixo em `auto` e o outro em `visible`: ele PROMOVE o outro a `auto`,
calado. A partir daí, qualquer filho que passasse da borda virava barra
de rolagem.

E havia um: o balãozinho com o nome do ícone, um `::after` nascendo em
`left:calc(100% + 10px)` -- dez pixels DEPOIS da borda direita do menu.
Ele criava a rolagem, e como a caixa que rola também corta, ele mesmo era
cortado. Ou seja: o nome nunca apareceu para ninguém. O que a fábrica
recebeu desse desenho foi só o efeito colateral dele.

O CONSERTO SÃO DUAS PEÇAS

  1. `overflow-x:clip` no menu. `clip` corta sem criar barra -- é o único
     valor que diz "não transborda, e também não rola".
  2. O balão sai de dentro da caixa que rola e vira UM elemento preso à
     janela, escrito por `ls-trilho.js`. Fora de qualquer scroller, não
     há o que cortar.
"""

from pathlib import Path

from django.test import TestCase

RAIZ = Path(__file__).resolve().parent


class MenuFechadoNaoRolaTests(TestCase):
    def css(self):
        return (
            RAIZ / "static" / "interno" / "interno_modern.css"
        ).read_text(encoding="utf-8")

    def script(self):
        return (
            RAIZ / "static" / "interno" / "ls-trilho.js"
        ).read_text(encoding="utf-8")

    def test_o_eixo_horizontal_esta_escrito_e_nao_deduzido(self):
        """Deduzido, o navegador deduz `auto` -- que é barra de rolagem."""
        self.assertIn(
            ".ls-nav{flex:1;overflow-y:auto;overflow-x:clip;padding:20px 14px 18px}",
            self.css(),
        )

    def test_o_nome_do_icone_nao_nasce_mais_dentro_do_que_rola(self):
        css = self.css()
        # O `::after` que criava a rolagem não existe mais.
        self.assertNotIn(".ls-nav-item::after{", css)
        self.assertNotIn("content:attr(data-titulo)", css)
        # No lugar dele, um elemento preso à janela.
        self.assertIn(".ls-dica-trilho{", css)
        self.assertIn("position:fixed", css[css.index(".ls-dica-trilho{"):][:400])

    def test_o_balao_so_aparece_com_o_menu_fechado(self):
        """Com a lateral aberta o nome já está escrito ao lado do ícone."""
        codigo = self.script()
        self.assertIn('lateral.classList.contains("expandida")', codigo)
        self.assertIn("global.innerWidth < LARGURA_DO_TRILHO", codigo)

    def test_a_posicao_medida_nao_pode_envelhecer_na_tela(self):
        """Rolar ou redimensionar move o ícone; o balão não acompanha."""
        codigo = self.script()
        for gatilho in ('"resize", esconder', '"scroll", esconder'):
            self.assertIn(gatilho, codigo)

    def test_o_balao_nao_repete_o_que_o_leitor_de_tela_ja_diz(self):
        self.assertIn('dica.setAttribute("aria-hidden", "true")', self.script())

    def test_o_toque_nao_abre_balao(self):
        """No toque ele apareceria por cima da tela que já está trocando."""
        self.assertIn('if (evento.pointerType === "touch") return;', self.script())


class OMenuFechadoContinuaLegivelSemVerTests(TestCase):
    """Com o nome escondido por `display:none`, ele some da árvore de
    acessibilidade -- e o item vira um link sem nome nenhum para quem
    usa leitor de tela. O `aria-label` é o que devolve esse nome."""

    def test_todo_item_do_menu_tem_nome_para_quem_nao_ve_o_icone(self):
        import re

        gabarito = (
            RAIZ / "templates" / "base_inner.html"
        ).read_text(encoding="utf-8")

        itens = re.findall(r'<a data-titulo="([^"]+)"([^>]*)>', gabarito)
        self.assertTrue(itens, "o menu perdeu os itens")
        for titulo, resto in itens:
            with self.subTest(item=titulo):
                self.assertIn(f'aria-label="{titulo}"', resto)
