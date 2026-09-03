"""Contratos de estrutura; não substituem inspeção visual em navegador."""
from pathlib import Path
from django.test import SimpleTestCase


class ColunasPainelTests(SimpleTestCase):
    raiz = Path(__file__).parent

    def test_clientes_tem_sete_colunas_sem_esconder_dados(self):
        html = (self.raiz / "templates/clientes_inner.html").read_text()
        self.assertEqual(html.count('<col class="ls-col-'), 7)
        self.assertEqual(html.count('scope="col"'), 7)
        self.assertIn('tabindex="0" role="region"', html)
        for campo in ('cliente.email', 'cliente.telefone', 'ficha.total_aprovado', 'ficha.orcamentos'):
            self.assertIn(campo, html)

    def test_perfis_independentes_para_tabelas_distintas(self):
        for arquivo, classes in {
            'pedidos_inner.html': ['ls-pedidos-table'],
            'vendas_inner.html': ['ls-vendas-table'],
            'material_inner.html': ['ls-materiais-table', 'ls-tipos-table', 'ls-fornecedores-table'],
        }.items():
            html = (self.raiz / 'templates' / arquivo).read_text()
            for classe in classes:
                self.assertIn(classe, html)

    def test_colunas_clientes_ocupam_exatamente_largura_disponivel(self):
        # Cada coluna recebe sua fração da largura após reservar 58px de ações.
        import re
        css = (self.raiz / 'static/interno/interno_modern.css').read_text()
        partes = re.findall(r'\.ls-clientes-table \.ls-col-\w+\{width:calc\((\d+)% - ([\d.]+)px\)', css)
        self.assertEqual(len(partes), 6)
        for largura in (900, 1024, 1280, 1520):
            total = sum(largura * float(p) / 100 - float(px) for p, px in partes) + 58
            self.assertAlmostEqual(total, largura)
        self.assertNotIn('td:nth-child(4){min-width:245px}', css)
        self.assertIn('.ls-clientes-table colgroup{display:none}', css)


class FichaDeListaTests(SimpleTestCase):
    """UMA FICHA SÓ PARA AS LISTAS DO PAINEL.

    No tablet e no celular as listas deixam de ser tabela e viram ficha.
    O estoque tinha a ficha DELE, escrita antes das outras: cada célula
    virava uma linha inteira, os números continuavam encostados na
    direita com meia tela vazia ao lado, e "Ações" ganhava uma faixa no
    rodapé só para um botão redondo. Um material ocupava 590px de altura;
    o mesmo material, na ficha compartilhada, ocupa 382px.

    Estes testes cobram o que fez a diferença -- e cada um deles nasceu de
    algo que estava errado na tela de alguém.
    """

    raiz = Path(__file__).parent

    def css(self):
        return (self.raiz / "static/interno/interno_modern.css").read_text()

    def test_o_estoque_usa_a_mesma_ficha_das_outras_listas(self):
        html = (self.raiz / "templates/estoque_inner.html").read_text()
        self.assertIn("ls-commercial-table", html)
        self.assertIn("ls-estoque-table", html)
        # E o empilhamento próprio dele não pode voltar: era ele que fazia
        # o rótulo e o valor ficarem na mesma linha, um por célula.
        self.assertNotIn('content:attr(data-rotulo) ": "', self.css())

    def test_a_ficha_nao_carrega_a_largura_minima_da_tabela(self):
        """`min-width:900px` numa tela de 760 arrasta a lista para o lado.

        A largura mínima existe para a TABELA não espremer sete colunas.
        Onde não há mais tabela, ela só produz rolagem lateral e metade de
        cada cliente fora da tela.
        """
        css = self.css()
        self.assertIn(".ls-commercial-table{min-width:0!important", css)

    def test_as_acoes_ficam_no_canto_e_nao_numa_faixa(self):
        """Quarenta pixels de botão não valem uma linha inteira da ficha."""
        css = self.css()
        # Nos dois tamanhos de tela em que a ficha existe.
        self.assertEqual(
            css.count(
                '.ls-commercial-table tbody td[data-rotulo="Ações"]{\n'
                '    position:absolute!important;'
            ),
            2,
        )
        # E a primeira célula reserva o lugar do botão -- só ela, e não o
        # card inteiro. Reservar no card come 15% da tela de um celular e
        # deixa uma faixa morta descendo pela direita da ficha inteira,
        # então o padding da ficha é simétrico:
        self.assertIn("margin:0 0 11px;padding:11px;display:grid", css)
        self.assertEqual(
            css.count('.ls-estoque-table tbody td[data-rotulo="Material"]{padding-right:46px!important}'),
            2,
        )

    def test_os_quatro_numeros_do_estoque_andam_de_dois_em_dois(self):
        """Empilhados, um material vira uma coluna de oito linhas."""
        css = self.css()
        for rotulo in ("Quantidade", "Mínimo", "Custo médio", "Valor em estoque"):
            self.assertIn(
                f'.ls-estoque-table tbody td[data-rotulo="{rotulo}"]', css
            )
        # Nome e situação, esses sim, mandam na largura.
        self.assertIn(
            '.ls-estoque-table tbody td[data-rotulo="Material"]{grid-column:1/-1}', css
        )

    def test_na_ficha_de_clientes_tudo_comeca_na_mesma_margem(self):
        """Centralizado ao lado de alinhado à direita não parece critério."""
        self.assertIn(
            '.ls-clientes-table tbody td[data-rotulo="Propostas"],\n'
            '  .ls-clientes-table tbody td[data-rotulo="Aprovado"]{text-align:left!important}',
            self.css(),
        )

    def test_acompanhamento_ocupa_a_ficha_inteira_do_orcamento(self):
        """Ele pegava duas das três colunas e sobrava a terceira vazia.

        A tarja da situação parava antes da borda direita, desalinhada de
        "Revisão dos blocos" logo abaixo, que sempre foi largura cheia.
        Duas caixas centradas em eixos diferentes, uma sobre a outra.
        """
        css = self.css()
        self.assertIn(
            '.ls-orcamentos-table tbody td[data-rotulo="Acompanhamento"]{grid-column:1/-1!important}',
            css,
        )
        self.assertNotIn(
            '.ls-orcamentos-table tbody td[data-rotulo="Acompanhamento"]{grid-column:1/3!important}',
            css,
        )
