"""Lista · Cards em todas as listas do painel, e as tabelas sem palavra quebrada.

O pedido: "os dois modelos, tabela e cards, em todas as listas; padrão vem
lista, mas podendo mudar para o card". O que se cobra aqui:

  * o seletor ("Lista" / "Cards") está em cada tela de lista -- as de
    gestão do site e as principais do painel (Orçamentos, Clientes, O.S.,
    Pedidos) -- apontando para o contêiner certo;
  * o padrão é a LISTA: o contêiner sai do servidor com `data-visao="lista"`
    e o rádio "lista" marcado;
  * o seletor são rádios dentro de <label>, sem nenhum <select> novo;
  * o mesmo item serve aos dois modos (`data-visao-item` e as partes com
    `data-v`), e o que é do cadastro de Brinquedos (adesivos) continua lá;
  * a escolha é lembrada no aparelho e reaplicada quando a tela chega pela
    navegação suave: o módulo é carregado uma vez, fora do bloco de scripts
    de cada tela, e entra no `Painel.montarTela`;
  * o cabeçalho das tabelas nunca quebra palavra, anda alinhado com a sua
    coluna (`data-coluna`) e o título longo é abreviado com o nome inteiro
    na dica.
"""

import re
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from sistema_interno.models import Cliente, EnderecoCliente

from .models import Brinquedos, Cupom, Eventos, Projetos, Promocoes

INTERNO = {"HTTP_HOST": "interno.testserver"}
RAIZ = Path(__file__).resolve().parent.parent
INTERNO_CSS = RAIZ / "sistema_interno" / "static" / "interno" / "interno_modern.css"

#: tela -> (rota, id do contêiner, chave guardada no aparelho)
TELAS = {
    "brinquedos": ("/site/brinquedos/", "bqLista", "brinquedos"),
    "promocoes": ("/site/promocoes/", "prLista", "promocoes"),
    "combos": ("/site/combos/", "comboLista", "combos"),
    "cupons": ("/site/cupons/", "cupLista", "cupons"),
    "pecas": ("/site/pecas/", "pecasLista", "pecas"),
    "projetos": ("/site/projetos/", "projetoLista", "projetos"),
    "eventos": ("/site/eventos/", "eventoLista", "eventos"),
    "banners": ("/site/banners/", "bannerLista", "banners"),
    "usuarios": ("/site/contas-clientes/", "usrLista", "usuarios"),
    "clientes-mapa": ("/site/clientes-mapa/", "clientsLista", "clientes-mapa"),
    "orcamentos": ("/orcamentos/", "orcamentosLista", "orcamentos"),
    "clientes": ("/clientes/", "clientesLista", "clientes"),
    "ordens-servico": ("/ordens-servico/", "ordensLista", "ordens-servico"),
    "pedidos": ("/pedidos/inner/", "pedidosLista", "pedidos"),
}


def sem_comentarios(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.gestor = User.objects.create_superuser("listas", "listas@exemplo.com", "x")
        cls.brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Air Game Hockey", descricao="Mesa", avaliacao=Decimal("4.8"),
            voltz="220V", valor_brinquedo=Decimal("9800.00"), exibir_na_loja=True,
            imagem_brinquedo="brinquedos/air.png",
        )
        Promocoes.objects.create(
            descricao="Air Game em oferta", brinquedos=cls.brinquedo,
            preco_promocao=Decimal("8900.00"), ativo=True,
        )
        Cupom.objects.create(codigo="BEMVINDO10", desconto_percentual=Decimal("10"), quantidade_uso=5)
        Eventos.objects.create(titulo="Festa Junina", descricao="Três dias de brinquedos")
        Projetos.objects.create(titulo="Espaço Kids", descricao="Brinquedão e escalada")
        cliente = Cliente.objects.create(nome_cliente="Marina Souza", nome_estabelecimento="Buffet Alegria")
        EnderecoCliente.objects.create(cliente=cliente, endereco="Rua das Flores, 100", cidade="Campinas", estado="SP")

    def setUp(self):
        cache.clear()
        self.client.force_login(self.gestor)

    def abrir(self, rota):
        resposta = self.client.get(rota, **INTERNO)
        self.assertEqual(resposta.status_code, 200, rota)
        return resposta.content.decode()


class SeletorEmTodaListaTests(Base):
    def test_cada_lista_tem_o_seletor_apontando_para_o_conteiner(self):
        for nome, (rota, alvo, chave) in TELAS.items():
            with self.subTest(tela=nome):
                html = self.abrir(rota)
                self.assertRegex(
                    html,
                    rf'data-visao-seletor data-visao-alvo="{alvo}" data-visao-chave="{chave}"',
                )
                self.assertRegex(html, rf'id="{alvo}"[^>]*data-visao="lista"')
                self.assertIn('class="ls-visao-opcao"', html)

    def test_o_padrao_e_a_lista(self):
        for nome, (rota, alvo, chave) in TELAS.items():
            with self.subTest(tela=nome):
                html = self.abrir(rota)
                seletor = html[html.index("data-visao-seletor"):]
                seletor = seletor[:seletor.index("</div>")]
                self.assertRegex(seletor, r'value="lista" checked')
                self.assertNotRegex(seletor, r'value="cards" checked')
                self.assertNotIn('data-visao="cards"', html)

    def test_o_seletor_sao_radios_e_nenhum_select_novo(self):
        parcial = (RAIZ / "sistema_interno" / "templates" / "includes" / "lista_ou_cards.html").read_text(encoding="utf-8")
        parcial = re.sub(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", "", parcial, flags=re.S)
        self.assertNotIn("<select", parcial)
        self.assertNotIn("<button", parcial)
        self.assertEqual(parcial.count('type="radio"'), 2)
        # Brinquedos não tinha <select> nenhum e continua sem; nas outras, a
        # lista (do seletor até o fim do contêiner) também não ganhou nenhum.
        html = self.abrir("/site/brinquedos/")
        miolo = html[html.index('<main class="ls-content">'):html.index('id="lsTelaScripts"')]
        self.assertNotIn("<select", miolo)
        for nome, (rota, alvo, chave) in TELAS.items():
            with self.subTest(tela=nome):
                html = self.abrir(rota)
                lista = html[html.index("data-visao-seletor"):]
                # até a primeira janela (cadastro, exclusão), que não é a lista
                fim = re.search(r'<dialog|role="dialog"|aria-modal="true"|-modal"|class="modal|</main>|id="lsTelaScripts"', lista)
                self.assertNotIn("<select", lista[:fim.start()] if fim else lista)

    def test_o_seletor_fica_fora_dos_formularios(self):
        """Dentro de um <form> de busca, a escolha iria junto na URL."""
        for nome, (rota, alvo, chave) in TELAS.items():
            with self.subTest(tela=nome):
                html = self.abrir(rota)
                antes = html[:html.index("data-visao-seletor")]
                self.assertEqual(antes.count("<form"), antes.count("</form>"))


class UmItemDuasApresentacoesTests(Base):
    def test_os_cartoes_marcam_as_partes_para_a_linha(self):
        casos = {
            "/site/brinquedos/": ['data-v="foto"', 'data-v="titulo"', 'data-v="valor"', 'data-v="acoes"', 'data-v="selos"'],
            "/site/promocoes/": ['data-v="foto"', 'data-v="titulo"', 'data-v="valor"', 'data-v="estado"', 'data-v="acoes"'],
            "/site/cupons/": ['data-v="titulo"', 'data-v="valor"', 'data-v="estado"', 'data-v="acoes"'],
            "/site/eventos/": ['data-v="foto"', 'data-v="titulo"', 'data-v="acoes"'],
            "/site/projetos/": ['data-v="titulo"', 'data-v="acoes"'],
        }
        for rota, partes in casos.items():
            with self.subTest(rota=rota):
                html = self.abrir(rota)
                self.assertIn("data-visao-item", html)
                for parte in partes:
                    self.assertIn(parte, html)
                # o cabeçalho das colunas só aparece na lista
                self.assertIn('class="ls-visao-cabeca" data-visao-so="lista"', html)

    def test_as_tabelas_viram_cartoes_pela_mesma_marcacao(self):
        for rota, tabela in (("/site/contas-clientes/", "usr-table"), ("/site/clientes-mapa/", "clients-table"),
                             ("/orcamentos/", "ls-orcamentos-table"), ("/clientes/", "ls-clientes-table"),
                             ("/ordens-servico/", "ls-os-tabela"), ("/pedidos/inner/", "ls-pedidos-table")):
            with self.subTest(rota=rota):
                html = self.abrir(rota)
                self.assertRegex(html, rf'<table class="[^"]*{tabela}[^"]*ls-visao-tabela')

    def test_o_cartao_de_brinquedo_guarda_o_lugar_dos_adesivos(self):
        """A frente dos adesivos pôs o selo e a seção no cadastro."""
        html = self.abrir("/site/brinquedos/")
        self.assertIn('data-adesivos', html)
        self.assertIn('class="bq-selos bq-selos--fim" data-v="selos"', html)
        modelo = (RAIZ / "core" / "templates" / "gestao" / "brinquedos_adm.html").read_text(encoding="utf-8")
        self.assertIn("bq-selo--adesivos", modelo)


class EscolhaLembradaTests(Base):
    def test_o_modulo_e_carregado_uma_vez_fora_dos_scripts_da_tela(self):
        html = self.abrir("/site/brinquedos/")
        script = html.index("interno/ls-listas")
        self.assertLess(script, html.index('id="lsTelaScripts"'))
        self.assertEqual(html.count("interno/ls-listas"), 1)

    def test_a_escolha_fica_no_aparelho_com_try_catch(self):
        js = (RAIZ / "sistema_interno" / "static" / "interno" / "ls-listas.js").read_text(encoding="utf-8")
        self.assertIn('"ls-visao:"', js)
        self.assertEqual(js.count("window.localStorage"), 2)
        self.assertEqual(len(re.findall(r"try \{\s*(?:return )?window\.localStorage", js)), 2)
        self.assertIn('addEventListener("ls:tela"', js)

    def test_a_lista_trocada_sem_recarregar_recebe_a_escolha(self):
        painel = (RAIZ / "sistema_interno" / "static" / "interno" / "painel.js").read_text(encoding="utf-8")
        trecho = painel[painel.index("Painel.montarTela = function"):]
        trecho = trecho[:trecho.index("};")]
        self.assertIn("global.LSVisao.montar(alvo)", trecho)


class TabelasSemPalavraQuebradaTests(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.css = sem_comentarios(INTERNO_CSS.read_text(encoding="utf-8"))

    def test_cabecalho_de_tabela_nunca_quebra(self):
        regra = re.search(r"\.ls-content table th\{([^}]*)\}", self.css)
        self.assertIsNotNone(regra)
        for propriedade in ("white-space:nowrap!important", "hyphens:none!important",
                            "overflow-wrap:normal!important", "word-break:keep-all!important"):
            self.assertIn(propriedade, regra.group(1))

    def test_o_cabecalho_anda_com_a_coluna(self):
        html = self.abrir("/orcamentos/")
        cabecalho = html[html.index("<thead>"):html.index("</thead>")]
        for coluna in ("ID", "Cliente", "Origem", "Proposta", "Pagamento", "Acompanhamento", "Ações"):
            self.assertIn(f'data-coluna="{coluna}"', cabecalho)
        # o título comprido vai abreviado, com o nome inteiro na dica
        self.assertIn('title="Revisão dos blocos" aria-label="Revisão dos blocos">Revisão</th>', cabecalho)
        # e as colunas de número e de ações alinham à direita, com o título junto
        self.assertIn('th[data-coluna="Total"]', self.css)
        self.assertRegex(self.css, r':is\(th\[data-coluna="Ações"\],th\[data-coluna="Ação"\]\),\s*'
                                   r'\.ls-content \.ls-commercial-table td:is\(\.ls-actions,\.ls-commercial-actions\)\{\s*'
                                   r'width:1%!important;min-width:0!important;white-space:nowrap!important;text-align:right!important;')

    def test_todas_as_tabelas_do_painel_tem_o_nome_da_coluna_no_cabecalho(self):
        for rota in ("/orcamentos/", "/clientes/", "/ordens-servico/", "/pedidos/inner/", "/stock/"):
            with self.subTest(rota=rota):
                html = self.abrir(rota)
                if "ls-commercial-table" not in html:
                    continue
                cabecalho = html[html.index("<thead>"):html.index("</thead>")]
                self.assertEqual(len(re.findall(r"<th[\s>]", cabecalho)), cabecalho.count("data-coluna="))

    def test_orcamentos_e_os_sem_larguras_fixas_de_porcentagem(self):
        """As oito porcentagens fixas quebravam "AÇÕES" e espremiam o cliente."""
        self.assertIn(".ls-content .ls-orcamentos-table{table-layout:auto!important}", self.css)
        self.assertIn(".ls-content .ls-os-tabela{table-layout:auto!important}", self.css)

    def test_em_tela_media_a_origem_vira_linha_do_cliente(self):
        html = self.abrir("/orcamentos/")
        self.assertIn('class="ls-linha-apoio material-sub"', (RAIZ / "sistema_interno" / "templates" / "partes"
                                                               / "orcamentos_lista.html").read_text(encoding="utf-8"))
        self.assertRegex(self.css, r'@media \(min-width:1200px\) and \(max-width:1599px\)\{\s*'
                                   r'\.ls-content \.ls-orcamentos-table :is\(th\[data-coluna="Origem"\],td\[data-rotulo="Origem"\]\)\{display:none\}')
        self.assertTrue(html)


class CoresDaListaTests(TestCase):
    def test_o_bloco_da_lista_so_usa_o_tema(self):
        css = sem_comentarios(INTERNO_CSS.read_text(encoding="utf-8"))
        bloco = css[css.index(".ls-visao{"):]
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", bloco), [])
        trios = {t for t in re.findall(r"rgba?\(\s*(\d+\s*,\s*\d+\s*,\s*\d+)", bloco)}
        self.assertEqual(trios, set())
