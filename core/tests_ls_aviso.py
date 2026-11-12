"""Os avisos de aplicativo: toast, folha e o fim do alert()/confirm().

O PEDIDO: "este tipo de mensagem deve virar um modal moderno que aparece
estilo app para avisar, eu falei que quero estilo app em tudo" -- sobre a
caixa do Bootstrap "A importação de “...docx” foi descartada." no alto de
uma tela do painel.

O que se cobra aqui (o painel tem os seus em sistema_interno/tests_ls_aviso.py):

  * os recados do Django saem como DADOS (core/ls_aviso.py): nível, título,
    ícone, e o `extra_tags` escolhe a apresentação -- "modal", "fixo",
    "titulo:...", "icone:...", "acao:<url>|<rótulo>";
  * o título de quem não deu um sai do verbo ("excluído" vira "Excluído",
    com a lixeira), e o erro de campo que falta é "Confira";
  * nenhuma base (site, painel, gestão) desenha mais o recado como caixa
    de alerta -- e nenhuma tela o desenha de novo por conta própria, fora a
    de manutenção do site, que tem a janela de sucesso dela;
  * nenhum alert()/confirm() do navegador sobra no JavaScript do painel, da
    gestão e do site (o `prompt()` de "copie o link" continua: ver
    ARQUIVOS_DE_JS);
  * o CSS do aviso só usa variável de tema, e cada variável tem dono: o
    tema escuro do site (ls-tema.css) e o sol/lua/eclipse do painel;
  * os ícones do servidor são os que o JavaScript sabe desenhar.
"""

import re
from pathlib import Path

from django.contrib import messages
from django.contrib.messages.storage.base import Message
from django.contrib.messages.storage.fallback import FallbackStorage
from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from . import ls_aviso

RAIZ = Path(__file__).resolve().parent.parent
SITE = RAIZ / "core" / "static" / "site"
JS = SITE / "ls-aviso.js"
CSS = SITE / "ls-aviso.css"
TEMA_SITE = SITE / "ls-tema.css"
TEMA_PAINEL = RAIZ / "sistema_interno" / "static" / "interno" / "interno_modern.css"
TEMPLATES_CORE = RAIZ / "core" / "templates"
TEMPLATES_PAINEL = RAIZ / "sistema_interno" / "templates"
ESTATICOS_PAINEL = RAIZ / "sistema_interno" / "static" / "interno"


def recado(nivel, texto, extra_tags=""):
    return Message(nivel, texto, extra_tags=extra_tags)


def sem_comentarios_js(texto):
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.S)
    texto = re.sub(r"^\s*//.*$", "", texto, flags=re.M)
    texto = re.sub(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", "", texto, flags=re.S)
    texto = re.sub(r"\{#.*?#\}", "", texto)
    return re.sub(r"<!--.*?-->", "", texto, flags=re.S)


class MarcasDoExtraTagsTests(SimpleTestCase):
    """A convenção do `extra_tags` (documentada em core/ls_aviso.py)."""

    def test_modal_fixo_titulo_icone_e_acao(self):
        marcas = ls_aviso.ler_marcas(
            "modal; fixo; titulo:Importação descartada; icone:arquivo-x; "
            "acao:/orcamentos/importar/?para=cliente|Importar outro"
        )
        self.assertTrue(marcas["modal"])
        self.assertTrue(marcas["fixo"])
        self.assertEqual(marcas["titulo"], "Importação descartada")
        self.assertEqual(marcas["icone"], "arquivo-x")
        self.assertEqual(marcas["acao"], {"url": "/orcamentos/importar/?para=cliente", "rotulo": "Importar outro"})

    def test_marcas_sem_valor_podem_vir_so_com_espaco(self):
        marcas = ls_aviso.ler_marcas("modal fixo")
        self.assertTrue(marcas["modal"] and marcas["fixo"])

    def test_o_que_nao_e_marca_e_ignorado(self):
        marcas = ls_aviso.ler_marcas("destaque; icone:foguete; acao:/so-url/")
        self.assertEqual(
            marcas, {"modal": False, "fixo": False, "titulo": "", "icone": "", "acao": None},
        )

    def test_avisar_escreve_a_convencao(self):
        pedido = RequestFactory().get("/")
        pedido.session = {}
        pedido._messages = FallbackStorage(pedido)
        ls_aviso.avisar(pedido, "Texto.", nivel=messages.ERROR, titulo="Título", icone="email",
                        modal=True, acao=("/x/", "Ver"))
        guardado = list(pedido._messages)[0]
        self.assertEqual((guardado.level, guardado.message), (messages.ERROR, "Texto."))
        lido = ls_aviso.ler_marcas(guardado.extra_tags)
        self.assertEqual((lido["modal"], lido["titulo"], lido["icone"]), (True, "Título", "email"))
        self.assertEqual(lido["acao"], {"url": "/x/", "rotulo": "Ver"})


class TituloEIconeTests(SimpleTestCase):

    def aviso(self, nivel, texto, extra_tags=""):
        return ls_aviso.aviso_do_recado(recado(nivel, texto, extra_tags))

    def test_os_niveis_do_django_no_nome_do_aviso(self):
        self.assertEqual(self.aviso(messages.SUCCESS, "Ok.")["nivel"], "sucesso")
        self.assertEqual(self.aviso(messages.INFO, "Ok.")["nivel"], "info")
        self.assertEqual(self.aviso(messages.WARNING, "Ok.")["nivel"], "alerta")
        self.assertEqual(self.aviso(messages.ERROR, "Ok.")["nivel"], "erro")

    def test_o_erro_fica_ate_fechar(self):
        self.assertTrue(self.aviso(messages.ERROR, "Falhou.")["fixo"])
        self.assertFalse(self.aviso(messages.SUCCESS, "Salvo.")["fixo"])

    def test_os_recados_de_sempre_ganham_titulo_e_icone(self):
        casos = {
            "Cliente “Buffet Alegria” excluído.": ("Excluído", "lixeira"),
            "Promoção excluída com sucesso.": ("Excluída", "lixeira"),
            "Banner removido com sucesso.": ("Removido", "lixeira"),
            "Promoção criada com sucesso.": ("Criada", "sucesso"),
            "Usuário atualizado.": ("Atualizado", "salvo"),
            "Categoria salva.": ("Salva", "salvo"),
            "“Buffet Alegria” salvo.": ("Salvo", "salvo"),
            "E-mail de teste enviado para a@b.com.": ("E-mail enviado", "email"),
            "A importação de “x.docx” foi descartada.": ("Importação descartada", "arquivo-x"),
            "Campanha cancelada. Nenhuma entrega pendente será processada.": ("Cancelada", "sucesso"),
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                aviso = self.aviso(messages.SUCCESS, texto)
                self.assertEqual((aviso["titulo"], aviso["icone"]), esperado)
                self.assertEqual(aviso["texto"], texto)

    def test_o_erro_nao_vira_sucesso_pelo_verbo(self):
        aviso = self.aviso(messages.ERROR, "Esta manutenção não pode ser cancelada.")
        self.assertEqual((aviso["titulo"], aviso["icone"]), ("Não foi possível", "erro"))

    def test_campo_que_falta_e_confira(self):
        aviso = self.aviso(messages.ERROR, "Informe o título da promoção.")
        self.assertEqual((aviso["titulo"], aviso["icone"]), ("Confira", "alerta"))

    def test_o_titulo_dado_pela_view_ganha(self):
        aviso = self.aviso(messages.ERROR, "Usuário, e-mail ou senha incorretos.",
                           "titulo:Não foi possível entrar")
        self.assertEqual(aviso["titulo"], "Não foi possível entrar")

    def test_sem_verbo_conhecido_fica_o_do_nivel(self):
        self.assertEqual(self.aviso(messages.INFO, "Bom dia.")["titulo"], "Aviso")
        self.assertEqual(self.aviso(messages.WARNING, "Cuidado com o prazo.")["titulo"], "Atenção")


class CartoesDoServidorTests(SimpleTestCase):
    """`{% avisos_do_app %}`: os recados como dados, e legíveis sem JS."""

    def desenhar(self, recados, **extra):
        return Template("{% load ls_aviso %}{% avisos_do_app recuperado=r %}").render(
            Context({"messages": recados, "r": extra.get("recuperado", "")}),
        )

    def test_sem_recado_nao_desenha_nada(self):
        self.assertEqual(self.desenhar([]).strip(), "")

    def test_cada_recado_vira_um_cartao_com_os_dados(self):
        html = self.desenhar([
            recado(messages.SUCCESS, "Categoria salva."),
            recado(messages.ERROR, "O servidor recusou.", "modal; titulo:O e-mail não saiu; icone:email"),
            recado(messages.INFO, "Pronto <b>já</b>.", "acao:/orcamentos/importar/|Importar outro"),
        ])
        self.assertRegex(html, r'data-ls-recados="[0-9a-f]{16}"')
        self.assertEqual(html.count("data-ls-recado\n") + html.count("data-ls-recado "), 3)
        self.assertIn('data-nivel="sucesso" data-titulo="Salva" data-icone="salvo"', html)
        # o erro: folha, fixo, e lido na hora pelo leitor de tela
        bloco_erro = html[html.index('data-nivel="erro"') - 120:html.index("O servidor recusou.")]
        self.assertIn("data-modal", bloco_erro)
        self.assertIn("data-fixo", bloco_erro)
        self.assertIn('role="alert"', bloco_erro)
        self.assertIn('data-titulo="O e-mail não saiu" data-icone="email"', html)
        # a ação: no dado e no link de quem está sem JavaScript
        self.assertIn('data-acao-url="/orcamentos/importar/" data-acao-rotulo="Importar outro"', html)
        self.assertIn('<a class="ls-recado-acao" href="/orcamentos/importar/">Importar outro</a>', html)
        # o texto é escapado
        self.assertIn("Pronto &lt;b&gt;já&lt;/b&gt;.", html)

    def test_o_endereco_antigo_do_painel(self):
        html = self.desenhar([], recuperado="pagina")
        self.assertIn('data-titulo="Endereço antigo"', html)
        self.assertIn("Você voltou com segurança para o painel.", html)

    def test_cada_resposta_tem_a_sua_chave(self):
        um = re.search(r'data-ls-recados="(\w+)"', self.desenhar([recado(messages.INFO, "a")])).group(1)
        outro = re.search(r'data-ls-recados="(\w+)"', self.desenhar([recado(messages.INFO, "a")])).group(1)
        self.assertNotEqual(um, outro)


class NenhumaCaixaDeAlertaTests(SimpleTestCase):
    """O recado não é mais desenhado como caixa, em base nenhuma."""

    def test_as_bases_usam_os_avisos_de_aplicativo(self):
        painel = (TEMPLATES_PAINEL / "base_inner.html").read_text(encoding="utf-8")
        site = (TEMPLATES_CORE / "base.html").read_text(encoding="utf-8")
        for nome, html in (("base_inner.html", painel), ("base.html", site)):
            with self.subTest(base=nome):
                self.assertIn("{% avisos_do_app", html)
                self.assertIn("site/ls-aviso.js", html)
                self.assertIn("site/ls-aviso.css", html)
                self.assertIn('classList.add("ls-recados-js")', html)
                self.assertNotIn("{% for message in messages %}", html)
        self.assertNotIn("alert alert-", painel)
        self.assertNotIn("alert-info", painel)
        self.assertIn("{% avisos_do_app recuperado=request.GET.recuperado %}", painel)

    def test_nenhuma_tela_desenha_os_recados_de_novo(self):
        """Fora a manutenção do site, que tem a janela de sucesso dela (e
        tira o toast pelo bloco `avisos_do_app`), ninguém percorre
        `messages`: senão o mesmo recado aparece duas vezes."""
        percorre = re.compile(r"\{%\s*(?:for \w+ in messages|if messages)\b")
        achados = []
        for raiz in (TEMPLATES_CORE, TEMPLATES_PAINEL):
            for arquivo in sorted(raiz.rglob("*.html")):
                if arquivo.name == "manutencao.html" and arquivo.parent == TEMPLATES_CORE:
                    continue
                if percorre.search(arquivo.read_text(encoding="utf-8")):
                    achados.append(str(arquivo.relative_to(RAIZ)))
        self.assertEqual(achados, [])
        manutencao = (TEMPLATES_CORE / "manutencao.html").read_text(encoding="utf-8")
        self.assertIn("{% block avisos_do_app %}{% endblock %}", manutencao)


#: Onde o alert()/confirm() do navegador não pode voltar. O `prompt()` fica
#: de fora de propósito: é o "copie o link" de quando a área de
#: transferência é negada (jogos_inner.html, gestao-manutencao_adm.js) e a
#: pergunta da pasta dos arquivos de console -- pedem um texto, e não um
#: "sim ou não". Não há lista de exceções: nenhum alert()/confirm() sobrou.
def arquivos_com_js():
    for arquivo in sorted(ESTATICOS_PAINEL.glob("*.js")):
        yield arquivo
    for arquivo in sorted(SITE.rglob("*.js")):
        if ".min." in arquivo.name:
            continue
        yield arquivo
    for raiz in (TEMPLATES_PAINEL, TEMPLATES_CORE):
        yield from sorted(raiz.rglob("*.html"))


class SemCaixaDoNavegadorTests(SimpleTestCase):

    CAIXA = re.compile(r"(?<![\w.$])(?:window\s*\.\s*)?(alert|confirm)\s*\(")

    def test_nenhum_alert_nem_confirm_no_painel_na_gestao_e_no_site(self):
        achados = []
        for arquivo in arquivos_com_js():
            texto = sem_comentarios_js(arquivo.read_text(encoding="utf-8"))
            for numero, linha in enumerate(texto.splitlines(), 1):
                if self.CAIXA.search(linha):
                    achados.append(f"{arquivo.relative_to(RAIZ)}:{numero}: {linha.strip()[:90]}")
        self.assertEqual(
            achados, [],
            "Use LSAviso.toast(...) / await LSAviso.confirmar(...) (core/static/site/ls-aviso.js) "
            "ou data-ls-confirmar no formulário.",
        )

    def test_a_gestao_esta_mesmo_na_lista(self):
        nomes = {arquivo.name for arquivo in arquivos_com_js()}
        for esperado in ("gestao-brinquedos_adm.js", "gestao-manutencao_adm.js", "gestao-promocoes_adm.js",
                         "painel.js", "banner_adm.html", "saidas_estoque.html", "guias_producao.html"):
            self.assertIn(esperado, nomes)

    def test_as_confirmacoes_viraram_folha(self):
        saidas = (TEMPLATES_PAINEL / "saidas_estoque.html").read_text(encoding="utf-8")
        self.assertIn('data-ls-confirmar-botao="Excluir" data-ls-perigo', saidas)
        gestao = (TEMPLATES_CORE / "gestao" / "manutencao_adm.html").read_text(encoding="utf-8")
        self.assertIn('data-ls-confirmar-titulo="Cancelar a manutenção {{ m.protocolo }}?"', gestao)
        self.assertNotIn("data-confirm=", gestao)
        brinquedos = (SITE / "paginas" / "gestao-brinquedos_adm.js").read_text(encoding="utf-8")
        self.assertIn("await LSAviso.confirmar", brinquedos)

    def test_o_aviso_do_painel_e_o_mostrarToast_do_site_sao_o_toast(self):
        painel = (ESTATICOS_PAINEL / "painel.js").read_text(encoding="utf-8")
        self.assertIn("global.LSAviso.toast(", painel)
        site = (TEMPLATES_CORE / "base.html").read_text(encoding="utf-8")
        inicio = site.index("function mostrarToast(")
        self.assertIn("window.LSAviso.toast(", site[inicio:inicio + 900])


class OJavaScriptDoAvisoTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.js = JS.read_text(encoding="utf-8")

    def test_a_api(self):
        for parte in ("window.LSAviso = {", "toast: toast", "modal: modal", "confirmar: confirmar",
                      "lerDoServidor: lerDoServidor", '"ls:tela"', "data-ls-confirmar",
                      'role", "alert"', 'aria-live", "polite"', 'aria-live", "assertive"',
                      "showModal", 'popover", "manual"', "prefers-reduced-motion", "pointerenter",
                      "visibilitychange", "sessionStorage"):
            with self.subTest(parte=parte):
                self.assertIn(parte, self.js)

    def test_os_icones_do_servidor_sao_os_do_javascript(self):
        bloco = self.js[self.js.index("var ICONES = {"):self.js.index("};", self.js.index("var ICONES = {"))]
        nomes = set(re.findall(r'^\s*"?([\w-]+)"?\s*:', bloco, flags=re.M))
        self.assertEqual(ls_aviso.ICONES, nomes - {"fechar"})

    def test_sem_dependencia(self):
        """Nem Bootstrap, nem jQuery, nem fonte de ícones: roda igual no site e no painel."""
        codigo = sem_comentarios_js(self.js)
        self.assertNotIn("bootstrap", codigo.lower())
        self.assertNotRegex(codigo, r"\bjQuery\b|\$\(|\bbi-|fa-solid")


def tokens_do_bloco(css, seletor_inicial):
    inicio = css.index(seletor_inicial)
    corpo = css[css.index("{", inicio) + 1:css.index("}", inicio)]
    return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", corpo))


class CssSoComVariavelDeTemaTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.css = re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.S)

    def test_nenhuma_cor_escrita_a_mao(self):
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", self.css), [])
        self.assertEqual(re.findall(r"rgba?\(\s*\d", self.css), [])
        self.assertEqual(re.findall(r"\bhsla?\(", self.css), [])
        self.assertEqual(
            re.findall(r":\s*(?:white|black|red|green|blue|gray|grey)\b", self.css), [],
        )

    def test_o_site_usa_o_tema_escuro_do_site(self):
        site = tokens_do_bloco(self.css, ".ls-recados-pilha,\n.ls-recado-folha,\n.ls-recados-servidor {")
        tema = re.sub(r"/\*.*?\*/", "", TEMA_SITE.read_text(encoding="utf-8"), flags=re.S)
        raiz = tema[tema.index(":root {"):tema.index("}", tema.index(":root {"))]
        definidos = set(re.findall(r"(--[\w-]+)\s*:", raiz))
        usados = {v for valor in site.values() for v in re.findall(r"var\((--[\w-]+)\)", valor)}
        self.assertTrue(usados)
        self.assertLessEqual(usados, definidos, f"sem dono no ls-tema.css: {sorted(usados - definidos)}")

    def test_o_painel_usa_o_sol_a_lua_e_o_eclipse(self):
        painel = tokens_do_bloco(self.css, ".ls-body .ls-recados-pilha,")
        self.assertEqual(set(painel), set(tokens_do_bloco(
            self.css, ".ls-recados-pilha,\n.ls-recado-folha,\n.ls-recados-servidor {")),
            "o painel e o site definem as mesmas --recado-*")
        tema = re.sub(r"/\*.*?\*/", "", TEMA_PAINEL.read_text(encoding="utf-8"), flags=re.S)
        lua = set(re.findall(r"(--[a-z0-9-]+)\s*:", tema[tema.index(':root,\n:root[data-tema="lua"]{'):]
                             .split("\n}", 1)[0]))
        usados = {v for valor in painel.values() for v in re.findall(r"var\((--[\w-]+)\)", valor)}
        self.assertLessEqual(usados, lua, f"sem dono no tema do painel: {sorted(usados - lua)}")
        for tema_nome in ("sol", "eclipse"):
            marca = f':root[data-tema="{tema_nome}"]{{'
            bloco = set(re.findall(r"(--[a-z0-9-]+)\s*:", tema[tema.index(marca):].split("\n}", 1)[0]))
            de_cor = {v for v in usados if v not in {"--topbar-h", "--shadow"}}
            with self.subTest(tema=tema_nome):
                self.assertLessEqual(de_cor, bloco | {"--shadow"}, sorted(de_cor - bloco))

    def test_toda_variavel_usada_no_desenho_tem_dono(self):
        definidos = set(re.findall(r"(--recado-[\w-]+)\s*:", self.css))
        usados = set(re.findall(r"var\((--recado-[\w-]+)\)", self.css))
        self.assertLessEqual(usados, definidos, sorted(usados - definidos))

    def test_celular_seguro_e_movimento_reduzido(self):
        self.assertIn("env(safe-area-inset-top", self.css)
        self.assertIn("env(safe-area-inset-bottom", self.css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css)
        self.assertIn("@media (max-width: 640px)", self.css)


@override_settings(ALLOWED_HOSTS=["www.lazersport.com.br", "testserver"])
class ToastNoSiteTests(TestCase):

    def test_o_erro_do_login_vira_toast(self):
        resposta = self.client.post("/login/", {"username": "ninguem", "password": "errada"})
        self.assertEqual(resposta.status_code, 200)
        html = resposta.content.decode()
        self.assertIn('data-nivel="erro" data-titulo="Não foi possível entrar"', html)
        self.assertIn("Usuário, e-mail ou senha incorretos.", html)
        self.assertNotIn('class="ls-msg', html)
        self.assertEqual(html.count("Usuário, e-mail ou senha incorretos."), 1)
