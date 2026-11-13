"""O cartão do cliente (modo Cards da tela de Clientes) e a barra de ações.

Os pedidos: "no modo card, centralize o conteúdo e se houver logo no
cliente, mostre a logo, tudo moderno e bem otimizado" e "nos cards, melhore
as ações deixando estilo app, como um botão no card elegante e com bons
ícones e texto".

O que se cobra aqui:

  * o rosto do cartão: a logo do cliente quando ele tem -- reduzida pelo
    caminho das fotos do site, preguiçosa e com largura e altura -- e, sem
    logo, as iniciais sobre uma cor que é sempre a mesma para aquele nome;
  * o contato como atalhos de tocar (WhatsApp, ligar, e-mail), sem WhatsApp
    no telefone marcado "sem WhatsApp";
  * a marcação do cartão centrado: as partes (`data-v`), o que é só do
    cartão (`data-visao-so="cards"`) e a lista, que continua como era;
  * BEM OTIMIZADO: o cartão não custa consulta nenhuma a mais por cliente;
  * a barra de ações no pé do cartão e a folha do "Mais" (o comportamento,
    em tests_js/cartao_acoes.cjs);
  * as outras listas não mudam: as regras novas só valem para o contêiner
    que as pede, e continuam só com as cores do tema.
"""

import re
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from . import cartao_cliente
from .models import Cliente, EnderecoCliente, ItemOrcamento, Orcamento

INTERNO = {"HTTP_HOST": "interno.testserver"}
RAIZ = Path(__file__).resolve().parent
CSS = RAIZ / "static" / "interno" / "interno_modern.css"
JS = RAIZ / "static" / "interno" / "ls-listas.js"
MODELOS = RAIZ / "templates"

PERFIL = '[data-visao-cartao="perfil"]'
BARRA = '[data-visao-acoes="barra"]'


def sem_comentarios(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def segunda_parte():
    """O bloco novo da folha: do cartão de perfil e da barra de ações."""
    css = CSS.read_text(encoding="utf-8")
    # o título do bloco (a primeira parte só o cita, mais acima)
    titulo = css.index("LISTA OU CARDS, SEGUNDA PARTE —")
    return sem_comentarios(css[css.rindex("/*", 0, titulo):])


def linha_do(html, cliente):
    """O <tr> de um cliente (é ele que vira o cartão)."""
    inicio = html.index(f'<tr data-registro="{cliente.pk}"')
    return html[inicio:html.index("</tr>", inicio)]


class RostoDoCartaoTests(SimpleTestCase):
    """As contas que não tocam no banco: iniciais, cor, atalhos."""

    def test_iniciais_sao_as_duas_primeiras_palavras_que_contam(self):
        casos = {
            "Buffet Alegria Festas e Eventos": "BA",
            "Marina de Souza": "MS",
            "joão": "J",
            "Academia Corpo & Movimento": "AC",
            "  Élida   dos Santos ": "ÉS",
            "3 Irmãos Festas": "3I",
            "& Cia": "C",
            "": "?",
            None: "?",
        }
        for nome, esperado in casos.items():
            with self.subTest(nome=nome):
                self.assertEqual(cartao_cliente.iniciais(nome), esperado)

    def test_a_cor_e_sempre_a_mesma_para_o_mesmo_nome(self):
        """Nada de `hash()`: ele muda a cada processo, e o cliente trocaria de cor."""
        tom = cartao_cliente.tom_do_nome("Buffet Alegria")
        self.assertEqual(tom, 2)  # valor fixo: não depende do processo
        self.assertEqual(cartao_cliente.tom_do_nome("  BUFFET   alegria "), tom)
        self.assertEqual(cartao_cliente.tom_do_nome("Buffét Alegria"), tom)
        tons = {cartao_cliente.tom_do_nome(f"Cliente {i}") for i in range(200)}
        self.assertEqual(tons, set(range(1, cartao_cliente.TONS + 1)))

    def test_cada_tom_tem_a_sua_cor_do_tema(self):
        css = segunda_parte()
        for tom in range(2, cartao_cliente.TONS + 1):
            with self.subTest(tom=tom):
                self.assertRegex(css, rf'\.ls-perfil-avatar\[data-tom="{tom}"\]\{{--tom-rgb:var\(--[a-z]+-rgb\)')

    def test_atalhos_de_contato(self):
        def cliente(**campos):
            return Cliente(nome_cliente="Teste", **campos)

        completo = cartao_cliente.atalhos_de_contato(
            cliente(telefone="(11) 97777-6655", email="ana@exemplo.com", canal_telefone="whatsapp")
        )
        self.assertEqual(completo, {
            "whatsapp": "https://wa.me/5511977776655",
            "ligar": "tel:+5511977776655",
            "email": "mailto:ana@exemplo.com",
        })
        # telefone que o cadastro diz não ter WhatsApp: liga, mas não abre conversa
        fixo = cartao_cliente.atalhos_de_contato(cliente(telefone="(11) 3333-4444", canal_telefone="telefone"))
        self.assertEqual(fixo["whatsapp"], "")
        self.assertEqual(fixo["ligar"], "tel:+551133334444")
        # número que já veio com o 55 não ganha outro
        internacional = cartao_cliente.atalhos_de_contato(cliente(telefone="+55 11 97777-6655"))
        self.assertEqual(internacional["whatsapp"], "https://wa.me/5511977776655")
        # sem DDD não há endereço internacional: só dá para ligar
        curto = cartao_cliente.atalhos_de_contato(cliente(telefone="3333-4444"))
        self.assertEqual((curto["whatsapp"], curto["ligar"]), ("", "tel:33334444"))
        vazio = cartao_cliente.atalhos_de_contato(cliente())
        self.assertEqual(vazio, {"whatsapp": "", "ligar": "", "email": ""})

    def test_a_logo_passa_pelo_redutor_das_fotos_do_site(self):
        """No Cloudinary a URL já pede a versão pequena; nunca o original."""
        original = "https://res.cloudinary.com/conta/image/upload/v1/logo_clientes/alegria.png"
        cliente = Cliente(nome_cliente="Buffet Alegria", logo="logo_clientes/alegria.png")
        with patch("core.fotos.url_da_imagem", return_value=original) as url:
            reduzida = cartao_cliente.logo_reduzida(cliente)
        url.assert_called_once_with(cliente.logo)
        self.assertEqual(
            reduzida,
            "https://res.cloudinary.com/conta/image/upload/c_limit,w_176,f_auto,q_auto/v1/logo_clientes/alegria.png",
        )
        self.assertEqual(cartao_cliente.LARGURA_DA_LOGO, 176)
        self.assertEqual(cartao_cliente.logo_reduzida(Cliente(nome_cliente="Sem logo")), "")


class Base(TestCase):
    URL = "/clientes/"

    @classmethod
    def setUpTestData(cls):
        cls.gestor = User.objects.create_superuser("cartoes", "cartoes@exemplo.com", "x")
        cls.buffet = Cliente.objects.create(
            nome_cliente="Buffet Alegria Festas", tipo=Cliente.Tipo.BUFFET,
            telefone="(11) 3333-4444", email="contato@alegria.com.br",
            canal_telefone=Cliente.CanalTelefone.WHATSAPP,
            nome_estabelecimento="Buffet Alegria", logo="logo_clientes/alegria.png",
        )
        EnderecoCliente.objects.create(
            cliente=cls.buffet, endereco="Avenida Paulista", numero="1578", bairro="Bela Vista",
            cidade="São Paulo", estado="SP", cep="01310-100",
        )
        aprovado = Orcamento.objects.create(cliente=cls.buffet, status=Orcamento.Status.APROVADO)
        ItemOrcamento.objects.create(
            orcamento=aprovado, descricao="Cama elástica", quantidade=2, valor_unitario=Decimal("300.00"),
        )
        Orcamento.objects.create(cliente=cls.buffet, status=Orcamento.Status.AGUARDANDO_RESPOSTA)
        cls.marina = Cliente.objects.create(
            nome_cliente="Marina Souza", telefone="(19) 99876-5432", parceiro=cls.buffet,
        )
        cls.joao = Cliente.objects.create(nome_cliente="João")

    def setUp(self):
        cache.clear()
        self.client.force_login(self.gestor)

    def abrir(self, rota=None):
        resposta = self.client.get(rota or self.URL, **INTERNO)
        self.assertEqual(resposta.status_code, 200)
        return resposta.content.decode()


class CartaoDoClienteTests(Base):
    def test_cliente_com_logo_mostra_a_logo(self):
        linha = linha_do(self.abrir(), self.buffet)
        avatar = linha[linha.index('class="ls-perfil-avatar"'):linha.index('class="material-nome"')]
        self.assertIn('data-v="avatar" data-visao-so="cards"', avatar)
        imagem = re.search(r"<img [^>]*>", avatar)
        self.assertIsNotNone(imagem, "cliente com logo sem <img> no cartão")
        imagem = imagem.group(0)
        self.assertIn("logo_clientes/alegria.png", imagem)
        self.assertIn('alt="Logo de Buffet Alegria"', imagem)
        # preguiçosa e com as medidas: o cartão não pula quando ela chega,
        # e na lista (onde o rosto fica escondido) ela nem é baixada
        for atributo in ('loading="lazy"', 'decoding="async"', 'width="84"', 'height="84"'):
            self.assertIn(atributo, imagem)
        # as iniciais ficam por baixo, para a imagem que não carregar
        self.assertIn('<span class="ls-perfil-iniciais" aria-hidden="true">BA</span>', avatar)

    def test_cliente_sem_logo_mostra_as_iniciais_na_cor_do_nome(self):
        html = self.abrir()
        for cliente, iniciais in ((self.marina, "MS"), (self.joao, "J")):
            with self.subTest(cliente=cliente.nome_cliente):
                linha = linha_do(html, cliente)
                avatar = linha[linha.index('class="ls-perfil-avatar"'):linha.index('class="material-nome"')]
                self.assertNotIn("<img", avatar)
                self.assertIn(f'data-tom="{cartao_cliente.tom_do_nome(cliente.nome_cliente)}"', avatar)
                self.assertIn(f'aria-hidden="true">{iniciais}</span>', avatar)

    def test_a_ficha_leva_a_logo_reduzida_e_o_avatar(self):
        resposta = self.client.get(self.URL, **INTERNO)
        fichas = {f["obj"].pk: f for f in resposta.context["fichas"]}
        self.assertTrue(fichas[self.buffet.pk]["logo"].endswith("logo_clientes/alegria.png"))
        self.assertEqual(fichas[self.marina.pk]["logo"], "")
        self.assertEqual(fichas[self.marina.pk]["avatar"]["iniciais"], "MS")

    def test_o_conteiner_pede_o_cartao_de_perfil_e_a_barra_de_acoes(self):
        html = self.abrir()
        self.assertRegex(
            html,
            r'id="clientesLista" data-visao="lista" data-visao-cartao="perfil" data-visao-acoes="barra"',
        )

    def test_as_celulas_sao_as_partes_do_cartao(self):
        linha = linha_do(self.abrir(), self.buffet)
        for rotulo, parte in (("Cliente", "rosto"), ("Contato", "contato"), ("Vínculo", "elo"),
                              ("Onde fica", "local"), ("Propostas", "numeros"), ("Aprovado", "total")):
            with self.subTest(parte=parte):
                self.assertIn(f'<td data-rotulo="{rotulo}" data-v="{parte}"', linha)
        # as ações continuam na célula de sempre (é dela que sai a barra)
        self.assertIn('<td data-rotulo="Ações" class="ls-actions ls-commercial-actions text-end">', linha)
        self.assertIn('data-visao-nome="Buffet Alegria Festas"', linha)

    def test_os_selos_servem_a_lista_e_ao_cartao(self):
        """Na lista são uma frase com "·"; no cartão o "·" some e viram pílulas."""
        marina = linha_do(self.abrir(), self.marina)
        selos = marina[marina.index("ls-perfil-selos"):marina.index("</td>")]
        self.assertIn('<span class="ls-perfil-selo">Residencial</span>', selos)
        buffet = linha_do(self.abrir(), self.buffet)
        self.assertIn('<span class="ls-status info">Buffet parceiro</span>', buffet)
        css = segunda_parte()
        self.assertRegex(css, re.escape(PERFIL) + r" \.ls-perfil-ponto\{display:none\}")

    def test_o_contato_do_cartao_e_de_tocar(self):
        html = self.abrir()
        buffet = linha_do(html, self.buffet)
        contato = buffet[buffet.index('data-v="contato"'):buffet.index('data-v="elo"')]
        self.assertIn('<div class="ls-perfil-contato" data-visao-so="cards">', contato)
        self.assertIn('class="ls-perfil-atalho whatsapp" href="https://wa.me/551133334444" target="_blank" rel="noopener"', contato)
        self.assertIn('class="ls-perfil-atalho ligar" href="tel:+551133334444"', contato)
        self.assertIn('class="ls-perfil-atalho email" href="mailto:contato@alegria.com.br"', contato)
        for nome in ("<span>WhatsApp</span>", "<span>Ligar</span>", "<span>E-mail</span>"):
            self.assertIn(nome, contato)
        self.assertIn('aria-label="Chamar Buffet Alegria Festas no WhatsApp"', contato)
        # o que a lista mostrava continua lá, marcado como só da lista
        self.assertIn('<a class="ls-link" data-visao-so="lista" href="https://wa.me/55', contato)
        # sem e-mail não há atalho de e-mail
        marina = linha_do(html, self.marina)
        self.assertNotIn("ls-perfil-atalho email", marina)
        # sem contato nenhum: o aviso, e nenhum atalho
        joao = linha_do(html, self.joao)
        self.assertIn('<span class="ls-status warning">Sem contato</span>', joao)
        self.assertNotIn("ls-perfil-atalho", joao)

    def test_telefone_sem_whatsapp_nao_ganha_atalho_de_whatsapp(self):
        Cliente.objects.filter(pk=self.marina.pk).update(canal_telefone=Cliente.CanalTelefone.TELEFONE)
        marina = linha_do(self.abrir(), self.marina)
        self.assertNotIn("ls-perfil-atalho whatsapp", marina)
        self.assertIn('class="ls-perfil-atalho ligar" href="tel:+5519998765432"', marina)

    def test_quem_veio_direto_nao_ocupa_lugar_no_cartao(self):
        html = self.abrir()
        self.assertIn('<td data-rotulo="Vínculo" data-v="elo" data-visao-so="lista">', linha_do(html, self.joao))
        self.assertIn('<td data-rotulo="Vínculo" data-v="elo">', linha_do(html, self.marina))
        self.assertIn('<td data-rotulo="Vínculo" data-v="elo">', linha_do(html, self.buffet))
        css = segunda_parte()
        self.assertRegex(css, re.escape(PERFIL) + r' \.ls-visao-tabela tbody td\[data-visao-so="lista"\]\{display:none!important\}')

    def test_os_numeros_viram_quadradinhos_e_o_aprovado_fecha_a_conta(self):
        html = self.abrir()
        buffet = linha_do(html, self.buffet)
        numeros = buffet[buffet.index('class="ls-perfil-numeros"'):buffet.index('data-v="total"')]
        self.assertEqual(
            re.findall(r"<strong>(\d+)</strong><small>([^<]+)</small>", numeros),
            [("2", "Propostas"), ("1", "Em aberto"), ("1", "Fechada")],
        )
        self.assertIn('<td data-rotulo="Aprovado" data-v="total" class="text-end">', buffet)
        self.assertIn("R$ 600,00", buffet)
        # quem não fechou nada: o mesmo lugar, sem o verde
        self.assertIn('<td data-rotulo="Aprovado" data-v="total" class="text-end" data-zerado>', linha_do(html, self.joao))

    def test_as_acoes_mais_usadas_vao_para_a_barra(self):
        buffet = linha_do(self.abrir(), self.buffet)
        self.assertRegex(buffet, r'data-nova-proposta="\d+"\s+data-acao-cartao="Proposta" data-acao-ordem="1"')
        self.assertRegex(buffet, r'data-dossie="\d+"\s+data-nome="[^"]+"\s+data-acao-cartao="Histórico" data-acao-ordem="2"')
        self.assertRegex(buffet, r'data-editar="\d+"[^>]*data-acao-cartao="Editar" data-acao-ordem="3"')
        # excluir nunca vai para a barra: fica no "Mais"
        excluir = buffet[buffet.index("data-excluir="):]
        self.assertNotIn("data-acao-cartao", excluir[:excluir.index(">")])

    def test_nova_proposta_sai_do_cliente(self):
        """O link leva à janela de proposta com este cliente já escolhido."""
        buffet = linha_do(self.abrir(), self.buffet)
        self.assertIn(f'href="/orcamentos/?novo=1&amp;cliente={self.buffet.pk}"', buffet)
        self.assertIn('aria-label="Nova proposta para Buffet Alegria Festas"', buffet)
        self.assertIn('<i class="bi bi-file-earmark-plus"></i><span class="ls-action-label">Nova proposta</span>', buffet)

        resposta = self.client.get(f"/orcamentos/?novo=1&cliente={self.buffet.pk}", **INTERNO)
        self.assertEqual(resposta.status_code, 200)
        ficha = resposta.context["cliente_inicial"]
        self.assertEqual(ficha["valor"], str(self.buffet.pk))
        self.assertEqual(ficha["rotulo"], "Buffet Alegria Festas")
        self.assertEqual(ficha["email"], "contato@alegria.com.br")
        html = resposta.content.decode()
        self.assertIn('<script id="orcamentoClienteInicial" type="application/json">', html)
        # e é a tela que o aplica, depois de abrir a proposta nova
        self.assertIn('document.getElementById("orcamentoClienteInicial")', html)
        self.assertIn("aplicarClienteNoOrcamento(clienteInicial, true);", html)

    def test_proposta_nova_sem_cliente_ou_com_cliente_que_nao_existe_abre_como_sempre(self):
        for rota in ("/orcamentos/", "/orcamentos/?novo=1", "/orcamentos/?novo=1&cliente=999999",
                     "/orcamentos/?novo=1&cliente=abc", "/orcamentos/?novo=1&cliente="):
            with self.subTest(rota=rota):
                resposta = self.client.get(rota, **INTERNO)
                self.assertEqual(resposta.status_code, 200)
                self.assertIsNone(resposta.context["cliente_inicial"])
                self.assertNotIn('id="orcamentoClienteInicial"', resposta.content.decode())

    def test_vendedor_ve_proposta_historico_e_editar_e_nao_ve_excluir(self):
        """Excluir cliente é da Gestão: para o vendedor a barra não tem "Mais"."""
        from .permissoes import atribuir_funcoes

        vendedor = User.objects.create_user("vendedor-cartoes", password="x", is_staff=True)
        atribuir_funcoes(vendedor, ["vendas"])
        self.client.force_login(vendedor)
        linha = linha_do(self.abrir(), self.buffet)
        for marca in ('data-acao-cartao="Proposta"', 'data-acao-cartao="Histórico"', 'data-acao-cartao="Editar"'):
            self.assertIn(marca, linha)
        self.assertNotIn("data-excluir=", linha)

    def test_quem_so_ve_o_financeiro_da_proposta_nao_recebe_cliente_inicial(self):
        """O Financeiro abre Orçamentos, mas quem cria proposta é o Comercial."""
        from .permissoes import atribuir_funcoes

        financeiro = User.objects.create_user("financeiro-cartoes", password="x", is_staff=True)
        atribuir_funcoes(financeiro, ["financeiro"])
        self.client.force_login(financeiro)
        resposta = self.client.get(f"/orcamentos/?novo=1&cliente={self.buffet.pk}", **INTERNO)
        self.assertEqual(resposta.status_code, 200)
        self.assertIsNone(resposta.context["cliente_inicial"])

    def test_a_lista_continua_com_o_que_tinha(self):
        """O cartão não tirou nada da linha: a lista mostra o mesmo de antes."""
        html = self.abrir()
        buffet = linha_do(html, self.buffet)
        for trecho in (
            '<span class="material-nome">Buffet Alegria Festas</span>',
            '<i class="bi bi-whatsapp me-1"></i>(11) 3333-4444',
            '<span class="material-sub d-block" data-visao-so="lista">contato@alegria.com.br</span>',
            '<strong class="ls-address-line">Avenida Paulista, 1578</strong>',
            "1 em aberto · 1 fechada",
            '<span class="ls-money">R$ 600,00</span>',
        ):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, buffet)
        # e o servidor continua mandando a lista: o cartão é escolha do aparelho
        self.assertNotIn('data-visao="cards"', html)


class BemOtimizadoTests(Base):
    """O cartão não pode custar uma ida ao banco por cliente."""

    def consultas(self):
        cache.clear()
        with CaptureQueriesContext(connection) as capturadas:
            resposta = self.client.get(self.URL, **INTERNO)
        self.assertEqual(resposta.status_code, 200)
        return len(capturadas), resposta

    def test_mais_clientes_nao_fazem_mais_consultas(self):
        poucos, _ = self.consultas()
        for i in range(12):
            cliente = Cliente.objects.create(
                nome_cliente=f"Cliente de teste {i:02d}",
                tipo=Cliente.Tipo.COMERCIAL if i % 2 else Cliente.Tipo.RESIDENCIAL,
                telefone=f"(11) 9{i:04d}-0000", email=f"cliente{i}@exemplo.com",
                logo=f"logo_clientes/{i}.png" if i % 3 else "",
                parceiro=self.buffet if i % 4 == 0 else None,
                publicar_no_mapa=bool(i % 2),
            )
            EnderecoCliente.objects.create(
                cliente=cliente, endereco="Rua A", numero=str(i), cidade="Campinas", estado="SP",
                latitude=Decimal("-22.9"), longitude=Decimal("-47.06"),
            )
            orcamento = Orcamento.objects.create(cliente=cliente, status=Orcamento.Status.APROVADO)
            ItemOrcamento.objects.create(
                orcamento=orcamento, descricao="Brinquedo", quantidade=1, valor_unitario=Decimal("100.00"),
            )
        muitos, resposta = self.consultas()
        self.assertEqual(len(resposta.context["fichas"]), 15)
        self.assertEqual(
            muitos, poucos,
            f"A lista fez {poucos} consultas com 3 clientes e {muitos} com 15: "
            "alguma coisa do cartão está indo ao banco por cliente.",
        )

    def test_montar_o_cartao_nao_vai_ao_banco(self):
        clientes = list(Cliente.objects.all())
        with CaptureQueriesContext(connection) as capturadas:
            for cliente in clientes:
                cartao_cliente.logo_reduzida(cliente)
                cartao_cliente.avatar(cliente)
                cartao_cliente.atalhos_de_contato(cliente)
        self.assertEqual(len(capturadas), 0)

    def test_sem_sombra_larga_nem_filtro_no_cartao(self):
        """Nada que o navegador repinte a cada rolagem: borda de 1px no lugar."""
        css = segunda_parte()
        inicio = css.index("grid-template-columns:repeat(auto-fill")
        perfil = css[inicio:]
        self.assertNotIn("filter:", perfil)
        self.assertNotIn("backdrop-filter", perfil)
        self.assertEqual(re.findall(r"box-shadow:(?!none)[^;}]*", perfil), [])
        self.assertRegex(css, re.escape(PERFIL) + r" \.ls-visao-tabela tbody tr:not\(\[hidden\]\)\{[^}]*box-shadow:none!important")


class GradeDoCartaoTests(SimpleTestCase):
    def test_uma_coluna_no_celular_e_no_maximo_quatro_no_pc(self):
        grade = re.search(re.escape(PERFIL) + r" \.ls-visao-tabela tbody\{([^}]*)\}", segunda_parte())
        self.assertIsNotNone(grade, "falta a grade do cartão de perfil")
        # nunca menos de 248px por cartão (uma coluna no celular, duas no
        # tablet) e nunca menos de um quarto da largura (no máximo quatro)
        self.assertIn(
            "grid-template-columns:repeat(auto-fill,minmax(max(min(100%,248px),calc((100% - 48px) / 4)),1fr));",
            grade.group(1),
        )
        # e no celular é um por linha, como nas outras listas
        self.assertRegex(
            segunda_parte(),
            r"@media \(max-width:640px\)\{\s*" + re.escape(".ls-content .ls-visao-alvo[data-visao=\"cards\"]" + PERFIL)
            + r" \.ls-visao-tabela tbody\{grid-template-columns:minmax\(0,1fr\)",
        )

    def test_o_conteudo_e_centrado_e_os_numeros_encostam_no_pe(self):
        css = segunda_parte()
        celula = re.search(re.escape(PERFIL) + r" \.ls-visao-tabela tbody td\{([^}]*)\}", css).group(1)
        self.assertIn("text-align:center!important", celula)
        self.assertIn("border:0!important", celula)
        # sem o rótulo da coluna em cima de cada célula
        self.assertRegex(css, r"tbody td::before,\s*" + re.escape(".ls-content .ls-visao-alvo[data-visao=\"cards\"]" + PERFIL)
                         + r" \.ls-visao-tabela tbody td:not\(:first-child\)\[data-rotulo\]::before\{\s*content:none!important")
        numeros = re.search(re.escape(PERFIL) + r' \.ls-visao-tabela tbody td\[data-v="numeros"\]\{([^}]*)\}', css).group(1)
        self.assertIn("margin-top:auto!important", numeros)

    def test_a_placa_da_logo_e_neutra_e_igual_nos_tres_temas(self):
        css = CSS.read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"--logo-placa:#C2BECA;", css)), 3)
        self.assertRegex(segunda_parte(), r"\.ls-perfil-avatar img\{[^}]*object-fit:contain;[^}]*background:var\(--logo-placa\)")

    def test_alvos_de_toque(self):
        css = segunda_parte()
        self.assertRegex(css, r":is\(\.ls-cartao-acao,\.ls-action-fab-trigger\)\{\s*flex:1 1 auto;[^}]*min-height:48px!important")
        self.assertRegex(css, r"\.ls-perfil-atalho\{[^}]*min-height:48px")
        self.assertRegex(css, r"\.ls-perfil-atalho i\{\s*width:46px;height:46px")
        self.assertRegex(css, r'\.ls-action-fab-menu\[data-folha="1"\] > button\{\s*min-height:46px!important')


class AsOutrasListasNaoMudamTests(Base):
    """A segunda parte só vale para o contêiner que a pede."""

    def test_toda_regra_nova_e_de_quem_pediu(self):
        css = segunda_parte()
        css = re.sub(r"@media[^{]*\{", "", css)
        # cada seletor da lista, sem partir as vírgulas de dentro de :is(...)
        seletores = [
            s.strip() for bloco in re.findall(r"([^{}]+)\{", css)
            for s in re.split(r",(?![^()]*\))", bloco)
        ]
        self.assertGreater(len(seletores), 80)
        permitidos = (PERFIL, BARRA, '[data-folha="1"]', ".ls-perfil-", ".ls-cartao-", ".ls-folha-")
        soltos = [s for s in seletores if s and not any(marca in s for marca in permitidos)]
        self.assertEqual(soltos, [], "Regra do cartão de perfil ou da barra que pega outras listas")

    def test_a_primeira_parte_ficou_como_estava(self):
        """As regras comuns da tabela que vira cartões não foram tocadas."""
        css = CSS.read_text(encoding="utf-8")
        comum = css[css.index("/* ---- tabela que vira CARDS ---- */"):css.index("/* ---- tablet: a lista perde as colunas de apoio ---- */")]
        self.assertNotIn("perfil", comum)
        self.assertNotIn("barra", comum)
        self.assertIn(
            '.ls-content .ls-visao-alvo[data-visao="cards"] .ls-visao-tabela tbody{\n'
            "  display:grid!important;grid-template-columns:repeat(auto-fill,minmax(min(100%,290px),1fr));",
            comum,
        )
        self.assertIn("content:attr(data-rotulo);display:block;margin:0 0 4px;", comum)

    def test_so_clientes_tem_o_cartao_de_perfil(self):
        for rota in ("/orcamentos/", "/ordens-servico/", "/pedidos/inner/", "/site/contas-clientes/",
                     "/site/clientes-mapa/", "/site/brinquedos/"):
            with self.subTest(rota=rota):
                html = self.abrir(rota)
                self.assertNotIn("data-visao-cartao", html)
                self.assertNotIn("ls-perfil-avatar", html)

    def test_a_barra_de_acoes_so_onde_foi_pedida(self):
        """Orçamentos e O.S. pediram a barra; as telas de gestão ficam como estavam."""
        for rota, alvo in (("/orcamentos/", "orcamentosLista"), ("/ordens-servico/", "ordensLista")):
            with self.subTest(rota=rota):
                self.assertRegex(self.abrir(rota), rf'id="{alvo}" data-visao="lista" data-visao-acoes="barra"')
        for rota in ("/pedidos/inner/", "/site/contas-clientes/", "/site/clientes-mapa/", "/site/brinquedos/"):
            with self.subTest(rota=rota):
                self.assertNotIn("data-visao-acoes", self.abrir(rota))

    def test_orcamentos_e_os_marcam_as_acoes_da_barra(self):
        orcamentos = (MODELOS / "partes" / "orcamentos_lista.html").read_text(encoding="utf-8")
        self.assertIn('target="_blank" rel="noopener" data-acao-cartao="Prévia" data-acao-ordem="1"', orcamentos)
        self.assertIn('data-editar="{{ orcamento.id }}" data-acao-cartao data-acao-ordem="2"\n', orcamentos)
        # no orçamento pago o documento para assinar vem à frente do "Enviar":
        # a barra leva três, e é ele o próximo passo
        self.assertIn(
            "data-acao-cartao=\"{% if orcamento.documento_assinatura.situacao == 'assinado' %}Assinado"
            "{% elif orcamento.documento_assinatura %}Assinatura{% else %}Documento{% endif %}\" data-acao-ordem=\"3\"",
            orcamentos,
        )
        self.assertIn(
            'data-acao-cartao="{% if orcamento.enviado_em %}Link{% else %}Enviar{% endif %}" data-acao-ordem="4"',
            orcamentos,
        )
        ordens = (MODELOS / "partes" / "os_lista.html").read_text(encoding="utf-8")
        for marca in ('data-acao-cartao="Imprimir"', 'data-editar-os="{{ ordem.id }}" data-acao-cartao', 'data-acao-cartao="Enviar"'):
            self.assertIn(marca, ordens)
        # o que apaga nunca é marcado para a barra
        for modelo in (orcamentos, ordens):
            for botao in re.findall(r"<button[^>]*btn-outline-danger[^>]*>", modelo, re.S):
                self.assertNotIn("data-acao-cartao", botao)


class BarraDeAcoesTests(SimpleTestCase):
    """A barra do pé do cartão e a folha do "Mais" (ls-listas.js)."""

    def test_os_atalhos_acionam_a_acao_de_verdade_e_nada_e_clonado(self):
        js = JS.read_text(encoding="utf-8")
        self.assertIn("if (!acao.disabled) acao.click();", js)
        self.assertNotIn("cloneNode", js)
        # a barra só é montada quando a lista entra em cards
        trecho = js[js.index("function prepararAcoes"):js.index("document.addEventListener(\"error\"")]
        self.assertIn('if (!alvo || alvo.getAttribute("data-visao-acoes") !== "barra") return;', trecho)
        self.assertIn("if (emCards) {", trecho)
        self.assertIn("window.Painel.organizarAcoesTabelas(alvo)", trecho)

    def test_o_que_apaga_fica_na_folha_separado_e_vermelho(self):
        js = JS.read_text(encoding="utf-8")
        self.assertIn('var PERIGOSA = ".btn-outline-danger,[data-excluir],[data-excluir-os],[data-acao-perigosa]";', js)
        self.assertIn('divisor.className = "ls-folha-divisor";', js)
        self.assertIn('item.no.classList.add("ls-folha-perigo");', js)
        css = segunda_parte()
        # pela ordem do CSS: o menu não é reescrito, e na lista continua como era
        self.assertRegex(css, r'\.ls-action-fab-menu\[data-folha="1"\] \.ls-folha-divisor\{display:block;order:1;height:1px')
        self.assertIn('.ls-action-fab-menu[data-folha="1"] > .ls-folha-perigo{order:2}', css)
        self.assertRegex(css, r'\[data-folha="1"\] :is\(\.btn-outline-danger,\[data-excluir\],\[data-excluir-os\],\[data-acao-perigosa\]\) i\{\s*color:var\(--red-texto\)!important')

    def test_no_celular_a_folha_sobe_do_pe_da_tela(self):
        css = segunda_parte()
        celular = css[css.index("@media (max-width:760px){"):]
        celular = celular[:celular.index("\n}\n")]
        self.assertIn("bottom:0!important", celular)
        self.assertIn("border-radius:22px 22px 0 0", celular)
        # acima das abas do pé do painel (z-index 1100), com o véu logo abaixo
        self.assertIn("z-index:1120", celular)
        veu = re.search(r"\.ls-folha-veu\{([^}]*)\}", celular).group(1)
        self.assertIn("position:fixed;inset:0;z-index:1119", veu)
        # some devagar: o toque que fechou a folha ainda cai nele, e não no cartão de baixo
        self.assertIn("visibility 0s linear .35s", veu)

    def test_o_veu_e_um_elemento_e_some_com_janela_aberta(self):
        """Fixo acima do modal: ou some com `body.modal-open`, ou não recebe toque."""
        css = segunda_parte()
        self.assertIn("body.modal-open .ls-folha-veu{display:none!important}", css)
        self.assertIn(".ls-folha-veu{display:none}", css)
        self.assertNotIn("body:has(", css)
        js = JS.read_text(encoding="utf-8")
        self.assertIn('veu.className = "ls-folha-veu";', js)
        self.assertIn('vigia.observe(menu, { attributes: true, attributeFilter: ["class"] });', js)

    def test_a_barra_nao_inventa_confirmacao(self):
        """Quem pergunta é a própria ação (a janela de exclusão, o
        `data-ls-confirmar` do ls-aviso.js): o botão da barra só a aciona.
        E o link que pede confirmação não vira link de verdade na barra,
        para o botão do meio não pular a pergunta."""
        js = JS.read_text(encoding="utf-8")
        self.assertNotIn("confirm(", js)
        self.assertIn('!acao.hasAttribute("data-ls-confirmar")', js)
        self.assertIn("!acao.matches(PERIGOSA) && acao.getAttribute(\"href\")", js)

    def test_a_folha_anda_pelo_teclado(self):
        js = JS.read_text(encoding="utf-8")
        for tecla in ("ArrowDown", "ArrowUp", "Home", "End", "Tab"):
            self.assertIn(f'"{tecla}"', js)
        self.assertIn("itens[0].focus({ preventScroll: true });", js)
        self.assertIn('gatilho.setAttribute("aria-haspopup", "menu");', js)

    def test_comportamento_no_dom(self):
        node = shutil.which("node")
        if not node or subprocess.run([node, "-e", "require('jsdom')"], capture_output=True).returncode:
            self.skipTest("jsdom não está disponível em NODE_PATH")
        resultado = subprocess.run(
            [node, str(RAIZ / "tests_js" / "cartao_acoes.cjs")],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
