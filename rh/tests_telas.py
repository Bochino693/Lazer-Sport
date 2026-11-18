"""As regras do painel nas telas do RH, e a pasta de documentos (checklist e vencimento).

  * nada de <select>: chips de rádio (ou campo de busca com sugestões);
  * CSS sem cor escrita à mão (só variáveis do tema, que existem nos três);
  * sem alert()/confirm() (a folha do LSAviso);
  * `{# #}` de uma linha só;
  * Lista e Cards nas listas (o seletor comum, padrão "lista");
  * a pasta mostra o que FALTA pelo vínculo, e o que vence em 30 dias.
"""

import re
from datetime import timedelta
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from . import servicos
from .apoio_testes import INTERNO, PastaPrivadaTemporaria, criar_colaborador, criar_conta, pdf_sintetico
from .arquivos import conferir

RAIZ = Path(__file__).resolve().parent
TEMPLATES = RAIZ / "templates" / "rh"
CSS_PAINEL = RAIZ / "static" / "rh" / "rh.css"
CSS_FOLHA = RAIZ / "static" / "rh" / "rh-folha.css"
TEMA = RAIZ.parent / "sistema_interno" / "static" / "interno" / "interno_modern.css"


def sem_comentarios(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def sem_root(css):
    return re.sub(r":root[^{]*\{[^}]*\}", "", css)


class RegrasDoPainelTests(SimpleTestCase):
    def modelos(self):
        return sorted(TEMPLATES.rglob("*.html"))

    def test_nenhum_select(self):
        for arquivo in self.modelos():
            with self.subTest(arquivo=arquivo.name):
                texto = re.sub(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}|\{#.*?#\}", "",
                               arquivo.read_text(encoding="utf-8"), flags=re.S)
                self.assertNotIn("<select", texto)

    def test_comentario_de_uma_linha_e_de_uma_linha(self):
        for arquivo in self.modelos():
            with self.subTest(arquivo=arquivo.name):
                for trecho in re.findall(r"\{#.*?#\}", arquivo.read_text(encoding="utf-8"), flags=re.S):
                    self.assertNotIn("\n", trecho)

    def test_css_do_painel_sem_cor_escrita_a_mao(self):
        css = sem_comentarios(CSS_PAINEL.read_text(encoding="utf-8"))
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", css), [])
        faixa = (TEMPLATES / "partes" / "faixa_termo.html").read_text(encoding="utf-8")
        estilo = faixa[faixa.index("<style>"):faixa.index("</style>")]
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", estilo), [])

    def test_a_folha_de_papel_so_tem_cor_no_root(self):
        css = sem_root(sem_comentarios(CSS_FOLHA.read_text(encoding="utf-8")))
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", css), [])

    def test_toda_variavel_usada_existe_nos_tres_temas(self):
        tema = sem_comentarios(TEMA.read_text(encoding="utf-8"))
        usados = set(re.findall(r"var\((--[a-z0-9-]+)", CSS_PAINEL.read_text(encoding="utf-8")))
        faixa = (TEMPLATES / "partes" / "faixa_termo.html").read_text(encoding="utf-8")
        usados |= set(re.findall(r"var\((--[a-z0-9-]+)", faixa))
        usados -= {"--lv-colunas", "--lv-areas"}
        for marca in (':root,\n:root[data-tema="lua"]{', ':root[data-tema="sol"]{', ':root[data-tema="eclipse"]{'):
            inicio = tema.index(marca)
            bloco = tema[inicio:tema.index("\n}", inicio)]
            definidos = set(re.findall(r"(--[a-z0-9-]+)\s*:", bloco))
            base = set(re.findall(r"(--[a-z0-9-]+)\s*:", tema))
            with self.subTest(tema=marca[:30]):
                # cor: definida no tema; medida/nome histórico: definida em algum lugar da folha
                self.assertEqual(sorted(v for v in usados if v not in definidos and v not in base), [])

    def test_sem_alert_nem_confirm(self):
        for arquivo in (RAIZ / "static" / "rh").glob("*.js"):
            with self.subTest(arquivo=arquivo.name):
                codigo = re.sub(r"/\*.*?\*/|//[^\n]*", "", arquivo.read_text(encoding="utf-8"), flags=re.S)
                self.assertIsNone(re.search(r"(?<![\w.])(alert|confirm)\s*\(", codigo))
                self.assertIsNone(re.search(r"window\.(alert|confirm)\s*\(", codigo))

    def test_script_de_tela_nao_espera_o_evento_da_pagina(self):
        self.assertNotIn("DOMContentLoaded", (RAIZ / "static" / "rh" / "rh.js").read_text(encoding="utf-8"))


class ListasECardsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from .models import Tarefa

        cls.gestora = criar_conta("gestora-telas", "gestao")
        Tarefa.objects.create(titulo="Conferir o estoque de MDF", colaborador=criar_colaborador(1))

    def test_lista_e_cards_nas_duas_listas(self):
        self.client.force_login(self.gestora)
        for rota, alvo, chave in (("/rh/colaboradores/", "rhColaboradores", "rh-colaboradores"),
                                  ("/rh/tarefas/", "rhTarefas", "rh-tarefas")):
            with self.subTest(rota=rota):
                html = self.client.get(rota, **INTERNO).content.decode()
                self.assertIn(f'data-visao-seletor data-visao-alvo="{alvo}" data-visao-chave="{chave}"', html)
                self.assertRegex(html, rf'id="{alvo}"[^>]*data-visao="lista"')
                self.assertIn("data-visao-item", html)
                miolo = html[html.index('<main class="ls-content">'):html.index('id="lsTelaScripts"')]
                self.assertNotIn("<select", miolo)

    def test_css_da_tela_se_declara(self):
        self.client.force_login(self.gestora)
        self.assertContains(self.client.get("/rh/", **INTERNO), 'data-ls-tela="rh"')


class PastaDeDocumentosTests(PastaPrivadaTemporaria, TestCase):
    def guardar(self, c, tipo, **campos):
        return servicos.guardar_documento(
            c, conferir(SimpleUploadedFile(f"{tipo}.pdf", pdf_sintetico(tipo))), tipo=tipo, **campos,
        )

    def test_checklist_pelo_vinculo(self):
        clt = criar_colaborador(1, vinculo="clt")
        pj = criar_colaborador(2, vinculo="pj", pis="")
        self.assertEqual(len(servicos.faltando(clt)), 7)
        self.assertEqual(len(servicos.faltando(pj)), 4)
        self.guardar(pj, "rg_cnh")
        self.guardar(pj, "cpf")
        estados = {linha["tipo"]: linha["estado"] for linha in servicos.checklist(pj)}
        self.assertEqual(estados["rg_cnh"], "ok")
        self.assertEqual(estados["residencia"], "falta")
        self.assertEqual(len(servicos.faltando(pj)), 2)

    def test_vencendo_em_30_dias_e_o_renovado_substitui(self):
        c = criar_colaborador(3)
        hoje = timezone.localdate()
        vencido = self.guardar(c, "aso", emissao=hoje - timedelta(days=380), validade=hoje - timedelta(days=15))
        self.assertEqual([d.pk for d in servicos.documentos_a_vencer()], [vencido.pk])
        self.assertEqual({l["tipo"]: l["estado"] for l in servicos.checklist(c)}["aso"], "vencido")
        novo = self.guardar(c, "aso", emissao=hoje, validade=hoje + timedelta(days=20))
        self.assertEqual([d.pk for d in servicos.documentos_a_vencer()], [novo.pk])
        self.assertEqual({l["tipo"]: l["estado"] for l in servicos.checklist(c)}["aso"], "vence")
        self.guardar(c, "aso", emissao=hoje, validade=hoje + timedelta(days=365))
        self.assertEqual(servicos.documentos_a_vencer(), [])

    def test_painel_do_rh_mostra_o_que_precisa(self):
        gestora = criar_conta("gestora-painel", "gestao")
        c = criar_colaborador(4)
        hoje = timezone.localdate()
        self.guardar(c, "aso", emissao=hoje, validade=hoje + timedelta(days=10))
        self.client.force_login(gestora)
        html = self.client.get("/rh/", **INTERNO).content.decode()
        self.assertIn("sem o termo de exclusividade assinado", html)
        self.assertIn("vence " + (hoje + timedelta(days=10)).strftime("%d/%m/%Y"), html)
        docs = self.client.get("/rh/documentos/", **INTERNO).content.decode()
        self.assertIn(c.nome, docs)
