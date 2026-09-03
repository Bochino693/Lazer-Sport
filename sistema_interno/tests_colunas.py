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
