"""Comentário {# ... #} do Django só vale numa linha.

Quebrado em várias linhas ele NÃO é comentário: o texto aparece na tela do
cliente (aconteceu no seletor Frete/Retirada do carrinho e no card da loja).
Comentário longo vai em {% comment %} ... {% endcomment %}.
"""

import re
from pathlib import Path

from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parent.parent
PASTAS = [RAIZ / "core" / "templates", RAIZ / "sistema_interno" / "templates"]


class ComentarioDeUmaLinhaTests(SimpleTestCase):
    def test_nenhum_comentario_curto_quebrado_em_linhas(self):
        quebrados = []
        for pasta in PASTAS:
            for arquivo in pasta.rglob("*.html"):
                texto = arquivo.read_text(encoding="utf-8")
                # {# que não fecha na mesma linha (e não é o "{#" de um seletor CSS)
                for numero, linha in enumerate(texto.splitlines(), 1):
                    for achado in re.finditer(r"\{#(?![A-Za-z_-])", linha):
                        if "#}" not in linha[achado.end():]:
                            quebrados.append(f"{arquivo.relative_to(RAIZ)}:{numero}")
        self.assertEqual(quebrados, [], "Use {% comment %} para comentário em várias linhas")
