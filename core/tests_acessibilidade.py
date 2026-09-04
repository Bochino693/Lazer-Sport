"""O site também precisa funcionar para quem não usa mouse nem enxerga.

Estes testes olham o HTML como um leitor de tela olha: existe um jeito de
pular o menu? cada imagem se descreve? cada campo tem nome? São regras
objetivas, e por isso dá para cobrá-las aqui em vez de descobrir na
reclamação de alguém.
"""

import re
from pathlib import Path

from django.test import TestCase


TEMPLATES = Path(__file__).resolve().parent / "templates"


class ImagensSeDescrevemTests(TestCase):
    """Toda imagem diz o que é -- ou diz que não é nada.

    Sem `alt`, o leitor de tela lê o nome do arquivo: "WhatsApp Image
    2025-11-20 at 14.05.13 jpeg". Com `alt=""`, ele pula a imagem, que é
    o certo para enfeite. O que não pode é o atributo faltar.
    """

    def test_nenhuma_imagem_do_site_fica_sem_alt(self):
        faltando = []

        for template in sorted(TEMPLATES.rglob("*.html")):
            texto = template.read_text(encoding="utf-8")
            for achado in re.finditer(r"<img\b[^>]*>", texto, re.S):
                if "alt=" in achado.group(0):
                    continue
                linha = texto[: achado.start()].count("\n") + 1
                faltando.append(f"{template.name}:{linha}")

        self.assertEqual(faltando, [], f"<img> sem alt: {faltando}")


class AtalhoDoTecladoTests(TestCase):
    """Dá para pular o menu e cair no conteúdo.

    São catorze itens de menu, mais busca e carrinho, antes do texto da
    página -- em toda página. Quem navega por teclado passava por tudo
    isso a cada abertura.
    """

    def setUp(self):
        self.base = (TEMPLATES / "base.html").read_text(encoding="utf-8")

    def test_o_atalho_e_o_primeiro_ponto_de_tabulacao(self):
        corpo = self.base.split("<body>", 1)[1]
        atalho = corpo.index('href="#conteudo"')
        primeiro_link = corpo.index("<a ")

        self.assertLessEqual(atalho - 40, primeiro_link)

    def test_o_atalho_tem_destino(self):
        self.assertIn('<main id="conteudo"', self.base)

    def test_o_atalho_aparece_ao_receber_foco(self):
        css = (
            Path(__file__).resolve().parent / "static" / "site" / "ls-base.css"
        ).read_text(encoding="utf-8")

        self.assertIn(".ls-pular-para-conteudo", css)
        self.assertIn(".ls-pular-para-conteudo:focus", css)


class CamposComNomeTests(TestCase):
    """Rótulo solto não é rótulo.

    No checkout, os rótulos eram `<label>CEP</label>` -- texto na tela,
    invisível para o leitor de tela, que anunciava "caixa de texto" em
    campo de endereço, telefone e CEP.
    """

    def test_os_campos_do_endereco_de_entrega_estao_ligados_ao_rotulo(self):
        texto = (TEMPLATES / "payment_finally.html").read_text(encoding="utf-8")

        soltos = re.findall(r"<label>(?!\s*</label>)([^<]{1,40})</label>", texto)

        self.assertEqual(soltos, [], f"rótulos sem `for`: {soltos}")

    def test_a_busca_do_site_tem_nome(self):
        texto = (TEMPLATES / "base.html").read_text(encoding="utf-8")

        self.assertIn('for="ls-busca-do-site"', texto)
        self.assertIn('id="ls-busca-do-site"', texto)

    def test_o_campo_de_cupom_tem_nome(self):
        texto = (TEMPLATES / "carrinho.html").read_text(encoding="utf-8")

        self.assertIn('for="cupomCodigo"', texto)
