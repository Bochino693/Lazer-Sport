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
from django.test import SimpleTestCase, TestCase


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
        from core.apoio_de_teste import script_da_pagina

        # O JavaScript da tela saiu do HTML -- era peso repetido a cada
        # abertura. A regra é a mesma: o gráfico continua sendo desenhado
        # aqui dentro, sem pedir biblioteca a ninguém.
        painel = script_da_pagina("gestao/dashboard.html")

        # O nome ainda aparece no comentário que conta a história; o que
        # não pode voltar é a tag que pedia o arquivo.
        self.assertNotIn("{% static 'js/Chart.min.js' %}", painel)
        self.assertNotIn("cdn.jsdelivr", painel)
        self.assertNotIn("cdnjs.cloudflare", painel)
        # Ele desenha o próprio SVG, e some sem barulho quando não há dado.
        self.assertIn("dashboardSalesChart", painel)
        self.assertIn("lsVendasFundo", painel)


class VersaoDoEstaticoTests(SimpleTestCase):
    """A versão do CSS sai do arquivo, e não da memória de quem edita.

    O QUE ACONTECEU. A folha do painel era pedida como
    `{% static 'interno/interno_modern.css' %}?v=35` -- um número
    digitado à mão. Uma rodada inteira de correções de cor foi para
    produção com o `v=35` intacto, e durante 24 horas (o `max-age` do
    WhiteNoise) todo navegador que já tinha aberto o painel continuou
    usando a folha velha.

    O sintoma é cruel: o HTML é sempre novo, porque página não se
    cacheia; só o CSS fica para trás. A tela mostra a marcação nova com
    o estilo antigo, e a leitura é "a correção não funcionou" -- quando
    ela nunca chegou. Foi exatamente o que aconteceu com o cinza da
    etiqueta, duas vezes.
    """

    def test_nenhum_estatico_do_painel_carrega_versao_digitada_a_mao(self):
        import re

        base = (
            Path(__file__).resolve().parent
            / "templates" / "base_inner.html"
        ).read_text(encoding="utf-8")

        restos = re.findall(r"\{%\s*static[^%]*%\}\?v=\d+", base)
        self.assertEqual(
            restos, [],
            "versão digitada à mão: mude o arquivo e esqueça o número, e a "
            "correção não chega ao navegador por 24 horas",
        )

    def test_a_versao_muda_quando_o_arquivo_muda(self):
        """É isso que faz o navegador buscar de novo."""
        from sistema_interno.templatetags.interno_extras import estatico

        endereco = estatico("interno/interno_modern.css")
        self.assertIn("?v=", endereco)

        versao = endereco.split("?v=")[1]
        self.assertTrue(versao, "sem versão, o cache velho vence")
        # A mesma folha responde a mesma versão: o navegador só rebusca
        # quando o conteúdo muda de verdade.
        self.assertEqual(endereco, estatico("interno/interno_modern.css"))
        # E arquivos diferentes têm versões diferentes.
        self.assertNotEqual(
            versao, estatico("interno/painel.js").split("?v=")[1],
        )

    def test_estatico_que_nao_existe_nao_derruba_a_pagina(self):
        """Sem versão o navegador ainda carrega; sem página, ninguém trabalha."""
        from sistema_interno.templatetags.interno_extras import estatico

        self.assertNotIn("?v=", estatico("interno/nao-existe-mesmo.css"))
