"""Nenhuma tela pede um arquivo que não existe.

A tela de Indicadores pedia `static/js/Chart.min.js`, e esse arquivo nunca
esteve no repositório. O resultado não era um erro visível: era um 404 no
console, um `typeof Chart !== "undefined"` que não passava, e um retângulo
vazio embaixo do título "Vendas por período" -- sem nada dizendo por quê.

ESTE É O PIOR TIPO DE FALHA PARA ENCONTRAR OLHANDO. A página abre, responde
200, não quebra nada, e simplesmente não mostra o que deveria. Quem usa
supõe que não há dado. Por isso a varredura aqui é do repositório inteiro,
e não de uma tela: o defeito é da forma "alguém escreveu um caminho que
não existe", e ela reaparece a cada arquivo renomeado.
"""

import re
from pathlib import Path

from django.contrib.staticfiles import finders
from django.test import TestCase


RAIZ = Path(__file__).resolve().parent.parent

# `{% static 'algo' %}` e `{% static "algo" %}`, com ou sem espaços.
CHAMADA_ESTATICA = re.compile(r"""\{%\s*static\s+(['"])(?P<caminho>[^'"]+)\1""")


class ArquivosEstaticosExistemTests(TestCase):

    def templates(self):
        for pasta in ("core", "sistema_interno", "lazer"):
            yield from (RAIZ / pasta).rglob("*.html")

    def test_todo_static_do_projeto_aponta_para_um_arquivo_real(self):
        faltando = []

        for template in self.templates():
            texto = template.read_text(encoding="utf-8", errors="ignore")
            for achado in CHAMADA_ESTATICA.finditer(texto):
                caminho = achado.group("caminho")
                # Caminho montado em tempo de execução ({{ }} no meio) não
                # dá para conferir daqui, e conferir errado seria pior.
                if "{" in caminho or "%" in caminho:
                    continue
                if finders.find(caminho) is None:
                    faltando.append(
                        "%s → %s" % (template.relative_to(RAIZ), caminho)
                    )

        self.assertEqual(
            faltando, [],
            "Estas telas pedem arquivos que não existem. A página abre, "
            "responde 200 e não mostra o que deveria:\n  "
            + "\n  ".join(faltando),
        )

    def test_o_grafico_de_vendas_nao_depende_de_biblioteca_externa(self):
        """O painel roda na estrada, instalado como aplicativo."""
        painel = (
            RAIZ / "core" / "templates" / "gestao" / "dashboard.html"
        ).read_text(encoding="utf-8")

        # O nome ainda aparece no comentário que conta a história; o que
        # não pode voltar é a tag que pedia o arquivo.
        self.assertNotIn("{% static 'js/Chart.min.js' %}", painel)
        self.assertNotIn("cdn.jsdelivr", painel)
        self.assertNotIn("cdnjs.cloudflare", painel)
        # Ele desenha o próprio SVG, e some sem barulho quando não há dado.
        self.assertIn("dashboardSalesChart", painel)
        self.assertIn("lsVendasFundo", painel)
