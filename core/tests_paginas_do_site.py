"""As grades paginadas do site fecham a fileira (LEIA-ME-V10, seções 121 e 129).

"Veja que cabe mais dois elementos e vc paginou... faça tudo ficar em
conformidade." A grade das peças tem 4, 3, 2 ou 1 coluna conforme a tela, e
a de eventos/projetos 3, 2 ou 1: só um múltiplo de 12 fecha a última
fileira de uma página que continua em todas elas.
"""

import re
from pathlib import Path

from django.test import SimpleTestCase

HOME_JS = Path(__file__).resolve().parent / "static" / "site" / "paginas" / "home.js"


class GradesDaHomeFechamAFileiraTests(SimpleTestCase):
    def test_todo_tamanho_de_pagina_da_home_e_multiplo_de_12(self):
        texto = HOME_JS.read_text(encoding="utf-8")
        tamanhos = [int(n) for n in re.findall(r"porPagina\s*[=:]\s*(\d+)", texto)]
        self.assertGreaterEqual(len(tamanhos), 4, tamanhos)
        for tamanho in tamanhos:
            self.assertEqual(tamanho % 12, 0, f"porPagina = {tamanho} deixa fileira pela metade")
