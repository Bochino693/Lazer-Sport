"""A descrição de projetos e eventos organizada para a ficha (core/ficha_texto.py)."""

from django.test import SimpleTestCase, TestCase
from django.template import Context, Template

from .ficha_texto import estruturar, resumo

COLADO = ("Playground indoor compacto projetado para crianças, ideal para espaços kids que precisam otimizar área. "
          "Com estrutura modular, o brinquedo incentiva a coordenação. Principais atrações 🧗 Área com obstáculos "
          "suspensos para estimular coordenação 🟡 Elementos rotativos e cilindros interativos Características "
          "Estrutura tubular resistente Revestimento acolchoado e seguro Design compacto ideal para ambientes menores "
          "Indicado para buffets infantis, brinquedotecas, escolas e áreas kids 💡 Este playground cria um ambiente "
          "lúdico e interativo, permitindo que várias crianças explorem o espaço enquanto desenvolvem habilidades motoras.")


class EstruturarTests(SimpleTestCase):
    def test_texto_colado_numa_linha_so_vira_secoes(self):
        f = estruturar(COLADO)
        self.assertEqual(len(f["lead"]), 1)
        self.assertIn("ideal para espaços kids", f["lead"][0])  # "ideal para" no meio da frase não é título
        titulos = [s["titulo"] for s in f["secoes"]]
        self.assertEqual(titulos, ["Principais atrações", "Características", "Indicado para"])
        self.assertEqual(f["secoes"][0]["itens"], ["Área com obstáculos suspensos para estimular coordenação",
                                                   "Elementos rotativos e cilindros interativos"])
        self.assertEqual(f["secoes"][1]["itens"], ["Estrutura tubular resistente", "Revestimento acolchoado e seguro",
                                                   "Design compacto ideal para ambientes menores"])
        self.assertTrue(f["secoes"][2]["etiquetas"])
        self.assertEqual(f["secoes"][2]["itens"], ["buffets infantis", "brinquedotecas", "escolas", "áreas kids"])
        self.assertEqual(len(f["fecho"]), 1)
        self.assertTrue(f["fecho"][0].startswith("Este playground"))

    def test_com_quebras_de_linha_e_marcadores(self):
        f = estruturar("Uma festa grande.\n\nDestaques:\n- Boliche com ranking\n- Fliperamas\nIdeal para: aniversários e formaturas")
        self.assertEqual(f["lead"], ["Uma festa grande."])
        self.assertEqual(f["secoes"][0]["itens"], ["Boliche com ranking", "Fliperamas"])
        self.assertEqual(f["secoes"][1]["itens"], ["aniversários", "formaturas"])

    def test_os_emojis_saem_do_texto(self):
        f = estruturar("Atrações\n🎳 Boliche\n🕹️ Fliperama")
        self.assertEqual(f["secoes"][0]["itens"], ["Boliche", "Fliperama"])

    def test_texto_simples_e_vazio(self):
        self.assertEqual(estruturar("Só uma frase."), {"lead": ["Só uma frase."], "secoes": [], "fecho": []})
        self.assertEqual(estruturar(""), {"lead": [], "secoes": [], "fecho": []})
        self.assertEqual(estruturar(None)["lead"], [])

    def test_resumo_do_cartao_sem_emoji(self):
        r = resumo(COLADO, 60)
        self.assertTrue(r.endswith("…"))
        self.assertNotIn("🧗", resumo(COLADO, 600))


class FichaNaPaginaTests(TestCase):
    def test_a_ficha_renderiza_o_texto_organizado(self):
        html = Template('{% include "partials/ficha_galeria.html" with janela="galeria-projeto-1" titulo="P" texto=t fotos=f selo="Projeto sob medida" mensagem="oi" %}').render(Context({"t": COLADO, "f": []}))
        self.assertIn('class="ls-galeria ls-ficha ls-ficha--projeto"', html)
        self.assertIn("Principais atrações", html)
        self.assertIn('class="ls-ficha-etiquetas"', html)
        self.assertIn("Buffets infantis", html)  # a etiqueta começa com maiúscula
        self.assertNotIn("🧗", html)
        self.assertIn("wa.me/5511960563135?text=oi", html)
        self.assertIn("As fotos deste projeto chegam em breve", html)
