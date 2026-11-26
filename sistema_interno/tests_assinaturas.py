"""As assinaturas num lugar só, organizadas pelo objeto (LEIA-ME-V10, seção 137).

O pedido do dono: "e no sistema interno ter com facilidade e orientado com
os objetos as assinaturas, para fáceis impressões e etc."

O que estes testes protegem (dados SINTÉTICOS, nada de cliente real):

  * a tela mostra um card por documento, com o objeto (orçamento ou O.S.),
    o cliente, o papel, a situação, quem assinou e quando;
  * QUEM VÊ O QUÊ, também por URL direta: o Comercial vê as dos
    orçamentos (o Ambulante, só as da carteira dele); a Produção e o
    Financeiro, as das O.S.; a Criação do site não entra; e NENHUM botão
    de um card leva a uma tela que a própria pessoa não abre;
  * os chips (situação e objeto) e a busca por cliente, por quem assinou e
    pelo número;
  * o documento substituído não aparece; o suspenso diz por quê;
  * a página é múltipla de 12 e a paginação guarda os filtros;
  * o número de consultas não cresce com o número de cards;
  * o item no menu de cada função, uma vez só; o CSS só com as variáveis
    do tema; a tela sem <select>, sem alert e sem confirm.
"""

import re
from pathlib import Path

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from . import documento_assinatura as svc
from . import documento_servico as servico
from .menu import menu_do_usuario
from . import views_assinaturas
from .models import Cliente, DocumentoAssinatura, Orcamento, OrdemServico
from .permissoes import capacidades
from .tests_documento_assinatura import CPF_DO_CLIENTE, png_de_assinatura
from .tests_documento_os import BaseOS
from .views_assinaturas import AssinaturasInnerView

INTERNO = {"HTTP_HOST": "interno.testserver"}
URL = "/assinaturas/"
RAIZ = Path(__file__).resolve().parent


class BaseAssinaturas(BaseOS):
    """Um orçamento do vendedor, um do ambulante e duas O.S., com e sem assinatura."""

    def setUp(self):
        super().setUp()  # self.tecnico (Produção), self.ordem, self.cliente_cadastro
        self.vendedor = self.usuario("vendedor-as", "vendas")
        self.ambulante = self.usuario("ambulante-as", "ambulante")
        self.financeiro = self.usuario("financeiro-as", "financeiro")
        self.gestao = self.usuario("gestao-as", "gestao")
        self.criacao = self.usuario("criacao-as", "criacao")

        # orçamento do vendedor: contrato ASSINADO
        self.orc_assinado = self.criar_orcamento("Buffet Alegria Sintético", self.vendedor)
        self.doc_assinado = self.assinar_doc(
            svc.gerar(self.orc_assinado, self.vendedor), "Maria Exemplo da Silva",
        )
        # orçamento do ambulante: contrato AGUARDANDO
        self.orc_ambulante = self.criar_orcamento("Escola Modelo Fictícia", self.ambulante)
        self.doc_ambulante = svc.gerar(self.orc_ambulante, self.ambulante)
        # O.S. assinada e O.S. aguardando
        self.doc_os_aguardando = self.gerar(self.ordem)
        self.ordem_assinada = self.criar_ordem(nome_cliente="Clube Teste do Bairro")
        self.doc_os_assinado = self.assinar_doc(
            self.gerar(self.ordem_assinada), "Ana Inventada Pereira",
        )

    def criar_orcamento(self, nome, responsavel, **campos):
        from decimal import Decimal

        from .models import ItemOrcamento

        padrao = {
            "nome_cliente": nome,
            "whatsapp_cliente": "(11) 97777-6655",
            "status": Orcamento.Status.APROVADO,
            "forma_pagamento": "Pix",
            "forma_envio": "Entrega Lazer & Sport",
            "responsavel": responsavel,
        }
        padrao.update(campos)
        orcamento = Orcamento.objects.create(**padrao)
        ItemOrcamento.objects.create(
            orcamento=orcamento, descricao="Cama elástica 3 m",
            quantidade=1, valor_unitario=Decimal("1500.00"),
        )
        return orcamento

    @staticmethod
    def assinar_doc(documento, nome):
        svc.assinar(
            documento, nome=nome, cpf_cnpj=CPF_DO_CLIENTE,
            png=svc.png_da_assinatura(png_de_assinatura()),
            ip="200.150.10.20", navegador="Mozilla/5.0 (iPhone)",
        )
        documento.refresh_from_db()
        return documento

    def abrir(self, usuario, consulta=""):
        self.client.force_login(usuario)
        return self.client.get(URL + consulta, **INTERNO)

    def ids(self, resposta):
        return {c["documento"].pk for c in resposta.context["cartoes"]}


# ======================================================================
# A TELA
# ======================================================================
class TelaDasAssinaturasTests(BaseAssinaturas):
    def test_a_gestao_ve_tudo_organizado_pelo_objeto(self):
        resposta = self.abrir(self.gestao)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.ids(resposta), {
            self.doc_assinado.pk, self.doc_ambulante.pk,
            self.doc_os_aguardando.pk, self.doc_os_assinado.pk,
        })
        html = resposta.content.decode()
        # o objeto, com o caminho de volta para ele
        self.assertIn(f"Orçamento nº {self.orc_assinado.numero_documento}", html)
        self.assertIn(f"/orcamentos/?q={self.orc_assinado.pk}&amp;editar={self.orc_assinado.pk}", html)
        self.assertIn(f"O.S. {self.ordem_assinada.numero_documento}", html)
        self.assertIn(f"/ordens-servico/?q={self.ordem_assinada.numero_documento}", html)
        # o cliente, o papel, quem assinou
        self.assertIn("Buffet Alegria Sintético", html)
        self.assertIn("Contrato de compra e venda", html)
        self.assertIn("Ordem de serviço", html)
        self.assertIn("Maria Exemplo da Silva", html)
        self.assertIn("Ana Inventada Pereira", html)
        self.assertIn(timezone.localtime(self.doc_assinado.assinado_em).strftime("%d/%m/%Y"), html)

    def test_o_assinado_imprime_e_o_que_espera_abre_o_qr(self):
        resposta = self.abrir(self.gestao)
        cartoes = {c["documento"].pk: c for c in resposta.context["cartoes"]}
        assinado = cartoes[self.doc_assinado.pk]
        self.assertEqual(assinado["situacao"], "assinado")
        self.assertEqual(
            assinado["url_imprimir"],
            f"/orcamentos/{self.orc_assinado.pk}/documento/via/?documento={self.doc_assinado.pk}&imprimir=1",
        )
        esperando = cartoes[self.doc_os_aguardando.pk]
        self.assertEqual(esperando["situacao"], "aguardando")
        self.assertEqual(esperando["url_pagina"], f"/ordens-servico/{self.ordem.pk}/assinatura/")
        html = resposta.content.decode()
        self.assertIn("Imprimir ou PDF", html)
        self.assertIn("Abrir o QR e o link", html)
        # a via aberta pelo botão é a do documento do card, e imprime sozinha
        via = self.client.get(assinado["url_imprimir"], **INTERNO)
        self.assertEqual(via.status_code, 200)
        self.assertTrue(via.context["imprimir_ao_abrir"])
        self.assertEqual(via.context["documento"].pk, self.doc_assinado.pk)

    def test_o_cpf_do_assinante_e_o_traco_nao_vao_para_a_lista(self):
        html = self.abrir(self.gestao).content.decode()
        self.assertNotIn(CPF_DO_CLIENTE, html)
        self.assertNotIn(re.sub(r"\D", "", CPF_DO_CLIENTE), html)
        self.assertNotIn("data:image/png", html)

    def test_o_substituido_nao_aparece(self):
        antigo = self.doc_ambulante
        novo = svc.gerar(self.orc_ambulante, self.ambulante, motivo="teste")
        antigo.refresh_from_db()
        self.assertEqual(antigo.situacao, DocumentoAssinatura.Situacao.SUBSTITUIDO)
        ids = self.ids(self.abrir(self.gestao))
        self.assertIn(novo.pk, ids)
        self.assertNotIn(antigo.pk, ids)

    def test_o_suspenso_diz_por_que(self):
        Orcamento.objects.filter(pk=self.orc_ambulante.pk).update(status=Orcamento.Status.RECUSADO)
        OrdemServico.objects.filter(pk=self.ordem.pk).update(status=OrdemServico.Status.CANCELADA)
        resposta = self.abrir(self.gestao)
        cartoes = {c["documento"].pk: c for c in resposta.context["cartoes"]}
        self.assertEqual(cartoes[self.doc_ambulante.pk]["situacao"], "suspenso")
        self.assertEqual(cartoes[self.doc_os_aguardando.pk]["situacao"], "suspenso")
        html = resposta.content.decode()
        self.assertIn("O orçamento não está mais aprovado", html)
        self.assertIn("A O.S. foi cancelada ou refeita", html)

    def test_sem_documento_a_tela_explica(self):
        DocumentoAssinatura.objects.all().delete()
        resposta = self.abrir(self.gestao)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Nenhum documento de assinatura ainda.")


# ======================================================================
# QUEM VÊ O QUÊ
# ======================================================================
class PermissoesDasAssinaturasTests(BaseAssinaturas):
    def test_vendas_ve_so_as_dos_orcamentos(self):
        resposta = self.abrir(self.vendedor)
        self.assertEqual(self.ids(resposta), {self.doc_assinado.pk, self.doc_ambulante.pk})
        self.assertEqual(resposta.context["chips_objeto"], [])
        self.assertNotContains(resposta, "Ana Inventada Pereira")

    def test_o_ambulante_ve_so_a_propria_carteira(self):
        resposta = self.abrir(self.ambulante)
        self.assertEqual(self.ids(resposta), {self.doc_ambulante.pk})
        self.assertNotContains(resposta, "Buffet Alegria Sintético")
        self.assertNotContains(resposta, "Maria Exemplo da Silva")

    def test_o_ambulante_nao_alcanca_o_alheio_pela_busca_nem_pelo_filtro(self):
        for consulta in (
            "?q=Buffet", f"?q={self.orc_assinado.pk}", "?q=Maria", "?objeto=os",
            "?situacao=assinadas", f"?q={self.ordem.pk}",
        ):
            with self.subTest(consulta=consulta):
                ids = self.ids(self.abrir(self.ambulante, consulta))
                self.assertLessEqual(ids, {self.doc_ambulante.pk})

    def test_a_producao_ve_so_as_das_ordens_de_servico(self):
        for usuario in (self.tecnico,):
            with self.subTest(usuario=usuario.username):
                resposta = self.abrir(usuario)
                self.assertEqual(
                    self.ids(resposta), {self.doc_os_aguardando.pk, self.doc_os_assinado.pk},
                )
                self.assertNotContains(resposta, "Buffet Alegria Sintético")
                # o filtro de objeto forçado na URL não abre os orçamentos
                self.assertEqual(
                    self.ids(self.abrir(usuario, "?objeto=orcamentos")),
                    {self.doc_os_aguardando.pk, self.doc_os_assinado.pk},
                )

    def test_o_financeiro_ve_as_dos_orcamentos_e_das_os_so_para_ler(self):
        """O dono liberou (seção 138): o Financeiro lê e imprime tudo, sem QR."""
        resposta = self.abrir(self.financeiro)
        self.assertEqual(self.ids(resposta), self.ids(self.abrir(self.gestao)))
        self.assertContains(resposta, "Buffet Alegria Sintético")
        # a via do contrato do orçamento abre para ele; o cartão do QR, não
        via = f"/orcamentos/{self.orc_assinado.pk}/documento/via/?documento={self.doc_assinado.pk}"
        self.client.force_login(self.financeiro)
        self.assertEqual(self.client.get(via, **INTERNO).status_code, 200)
        self.assertContains(self.client.get(via, **INTERNO), "/assinaturas/")
        self.assertEqual(
            self.client.get(f"/orcamentos/{self.orc_assinado.pk}/documento/", **INTERNO).status_code, 403,
        )
        self.assertEqual(
            self.client.post(f"/orcamentos/{self.orc_assinado.pk}/documento/link/", **INTERNO).status_code, 403,
        )

    def test_o_financeiro_ve_o_papel_mas_nao_o_qr(self):
        resposta = self.abrir(self.financeiro)
        self.assertNotContains(resposta, "Abrir o QR e o link")
        self.assertContains(resposta, "Ver o documento")
        self.assertContains(resposta, "Imprimir ou PDF")
        # a O.S., que ele só lê, não abre na janela de editar
        self.assertNotRegex(resposta.content.decode(), r'ordens-servico/\?q=[^"]*editar=')
        # a Produção, que edita a O.S., tem o QR
        self.assertContains(self.abrir(self.tecnico), "Abrir o QR e o link")

    def test_a_criacao_do_site_nao_entra(self):
        resposta = self.abrir(self.criacao)
        self.assertEqual(resposta.status_code, 302)
        self.assertNotIn("assinaturas", resposta["Location"])

    def test_sem_login_vai_para_a_entrada_e_fora_do_painel_nao_existe(self):
        resposta = self.client.get(URL, **INTERNO)
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("login", resposta["Location"])
        self.client.force_login(self.gestao)
        # no site público a rota não existe: nada de lista de clientes por lá
        fora = self.client.get(URL)
        self.assertNotEqual(fora.status_code, 200)
        self.assertNotIn(b"Buffet Alegria", fora.content)

    def test_nenhum_botao_leva_a_uma_tela_que_a_pessoa_nao_abre(self):
        """O card não oferece o que a tela do objeto recusa (403, 404 ou volta)."""
        for usuario in (self.gestao, self.vendedor, self.ambulante, self.tecnico, self.financeiro):
            resposta = self.abrir(usuario)
            self.assertTrue(resposta.context["cartoes"], usuario.username)
            html = resposta.content.decode()
            grade = html[html.index('class="ls-as-grade"'):]
            grade = grade[:grade.index("</section>")]
            enderecos = {e.replace("&amp;", "&") for e in re.findall(r'href="([^"]+)"', grade)}
            self.assertTrue(enderecos)
            for endereco in sorted(enderecos):
                with self.subTest(usuario=usuario.username, endereco=endereco):
                    self.assertEqual(self.client.get(endereco, **INTERNO).status_code, 200)

    def test_as_capacidades_de_cada_funcao(self):
        esperado = {
            # função: (entra, orçamentos, O.S.)
            self.gestao: (True, True, True),
            self.vendedor: (True, True, False),
            self.ambulante: (True, True, False),
            self.tecnico: (True, False, True),
            self.financeiro: (True, True, True),
            self.criacao: (False, False, False),
        }
        for usuario, (entra, orcamentos, ordens) in esperado.items():
            with self.subTest(usuario=usuario.username):
                acesso = capacidades(usuario)
                self.assertEqual(
                    (acesso["assinaturas"], acesso["assinaturas_orcamentos"], acesso["assinaturas_os"]),
                    (entra, orcamentos, ordens),
                )


class TextoDoTopoPorFuncaoTests(BaseAssinaturas):
    """O texto do topo acompanha o que a pessoa pode fazer (seção 140)."""

    COM_QR = "ou abra o QR de quem ainda não assinou."
    SO_LE = "Imprima ou baixe o PDF assinado com um toque e acompanhe quem ainda não assinou."

    def test_quem_so_le_nao_e_convidado_a_abrir_o_qr(self):
        resposta = self.abrir(self.financeiro)
        self.assertFalse(resposta.context["pode_algum_qr"])
        self.assertContains(resposta, self.SO_LE)
        self.assertNotContains(resposta, "abra o QR")
        # e de fato não há botão de QR na tela dele
        self.assertNotContains(resposta, "data-as-qr")

    def test_quem_tem_o_qr_de_algum_objeto_continua_com_o_convite(self):
        for usuario in (self.gestao, self.vendedor, self.ambulante, self.tecnico):
            with self.subTest(usuario=usuario.username):
                resposta = self.abrir(usuario)
                self.assertTrue(resposta.context["pode_algum_qr"])
                self.assertContains(resposta, self.COM_QR)
                self.assertNotContains(resposta, "acompanhe quem ainda não assinou")


# ======================================================================
# CHIPS, BUSCA E PÁGINAS
# ======================================================================
class FiltrosDasAssinaturasTests(BaseAssinaturas):
    def test_chips_da_situacao_e_do_objeto(self):
        self.assertEqual(
            self.ids(self.abrir(self.gestao, "?situacao=assinadas")),
            {self.doc_assinado.pk, self.doc_os_assinado.pk},
        )
        self.assertEqual(
            self.ids(self.abrir(self.gestao, "?situacao=aguardando")),
            {self.doc_ambulante.pk, self.doc_os_aguardando.pk},
        )
        self.assertEqual(
            self.ids(self.abrir(self.gestao, "?objeto=os")),
            {self.doc_os_aguardando.pk, self.doc_os_assinado.pk},
        )
        self.assertEqual(
            self.ids(self.abrir(self.gestao, "?objeto=orcamentos&situacao=assinadas")),
            {self.doc_assinado.pk},
        )

    def test_os_numeros_dos_chips(self):
        resposta = self.abrir(self.gestao, "?objeto=os")
        situacao = {c["valor"]: c["quantos"] for c in resposta.context["chips_situacao"]}
        objeto = {c["valor"]: c["quantos"] for c in resposta.context["chips_objeto"]}
        self.assertEqual(situacao, {"todas": 2, "assinadas": 1, "aguardando": 1})
        self.assertEqual(objeto, {"todos": 4, "orcamentos": 2, "os": 2})
        ativo = [c["valor"] for c in resposta.context["chips_objeto"] if c["ativo"]]
        self.assertEqual(ativo, ["os"])

    def test_filtro_desconhecido_cai_no_padrao(self):
        resposta = self.abrir(self.gestao, "?situacao=xpto&objeto=%3Cscript%3E")
        self.assertEqual(resposta.context["situacao"], "todas")
        self.assertEqual(resposta.context["objeto"], "todos")
        self.assertEqual(len(resposta.context["cartoes"]), 4)

    def test_busca_por_cliente_por_quem_assinou_e_pelo_numero(self):
        self.assertEqual(self.ids(self.abrir(self.gestao, "?q=buffet")), {self.doc_assinado.pk})
        self.assertEqual(self.ids(self.abrir(self.gestao, "?q=Clube+Teste")), {self.doc_os_assinado.pk})
        self.assertEqual(self.ids(self.abrir(self.gestao, "?q=ana+inventada")), {self.doc_os_assinado.pk})
        # o número como está escrito no card
        self.assertIn(
            self.doc_os_assinado.pk,
            self.ids(self.abrir(self.gestao, f"?q={self.ordem_assinada.numero_documento}&objeto=os")),
        )
        self.assertEqual(
            self.ids(self.abrir(self.gestao, f"?q=%23{self.orc_ambulante.pk}&objeto=orcamentos")),
            {self.doc_ambulante.pk},
        )
        self.assertEqual(self.ids(self.abrir(self.gestao, "?q=nada+com+isso")), set())
        self.assertContains(self.abrir(self.gestao, "?q=nada+com+isso"), "Nenhuma assinatura com")

    def test_a_pagina_e_multipla_de_12_e_guarda_os_filtros(self):
        self.assertEqual(AssinaturasInnerView.POR_PAGINA % 12, 0)
        for numero in range(AssinaturasInnerView.POR_PAGINA + 1):
            svc.gerar(self.criar_orcamento(f"Cliente Sintético {numero:02d}", self.vendedor), self.vendedor)
        primeira = self.abrir(self.gestao, "?objeto=orcamentos&situacao=aguardando")
        self.assertEqual(len(primeira.context["cartoes"]), AssinaturasInnerView.POR_PAGINA)
        self.assertContains(primeira, "?situacao=aguardando&amp;objeto=orcamentos&amp;page=2")
        segunda = self.abrir(self.gestao, "?objeto=orcamentos&situacao=aguardando&page=2")
        self.assertEqual(len(segunda.context["cartoes"]), 2)  # 25 novos + o do ambulante
        self.assertFalse(self.ids(primeira) & self.ids(segunda))

    def test_as_consultas_nao_crescem_com_os_cards(self):
        self.client.force_login(self.gestao)
        self.client.get(URL, **INTERNO)  # aquece o cache das funções e do menu

        def consultas():
            with CaptureQueriesContext(connection) as contexto:
                resposta = self.client.get(URL, **INTERNO)
            self.assertEqual(resposta.status_code, 200)
            return len(contexto), len(resposta.context["cartoes"])

        antes, cards_antes = consultas()
        for numero in range(6):
            svc.gerar(self.criar_orcamento(f"Cliente Extra {numero}", self.vendedor), self.vendedor)
            self.assinar_doc(servico.gerar_da_ordem(
                self.criar_ordem(nome_cliente=f"O.S. Extra {numero}"), self.tecnico,
            ), "Fulana Sintética")
        depois, cards_depois = consultas()
        self.assertEqual(cards_depois, cards_antes + 12)
        self.assertLessEqual(depois, antes, "cada card a mais não pode custar uma ida ao banco")
        # a sessão, o usuário, os números dos chips e os cards
        self.assertLessEqual(depois, 4)


# ======================================================================
# O MENU E AS REGRAS DA CASA
# ======================================================================
class MenuERegrasDaCasaTests(BaseAssinaturas):
    def test_o_item_no_menu_de_cada_funcao_uma_vez_so(self):
        esperado = {
            self.gestao: [("gestao", "Comercial")],
            self.vendedor: [("vendas", "Comercial")],
            self.ambulante: [("ambulante", "Comercial")],
            self.tecnico: [("producao", "Operação")],
            self.financeiro: [("financeiro", "Operação")],
            self.criacao: [],
        }
        for usuario, onde in esperado.items():
            with self.subTest(usuario=usuario.username):
                achados = [
                    (grupo.codigo, bloco)
                    for grupo in menu_do_usuario(capacidades(usuario))
                    for bloco, itens in grupo.blocos
                    for item in itens if item.rota == "assinaturas_inner"
                ]
                self.assertEqual(achados, onde)

    def test_o_item_aparece_na_tela(self):
        resposta = self.abrir(self.vendedor)
        self.assertContains(resposta, 'href="/assinaturas/"')

    def test_css_so_com_as_variaveis_do_tema(self):
        css = (RAIZ / "static" / "interno" / "assinaturas.css").read_text(encoding="utf-8")
        sem_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", sem_comentarios), [])
        self.assertNotIn("rgb(", sem_comentarios.replace("rgba(var(", ""))
        # no máximo 4 cards por fileira
        colunas = [int(n) for n in re.findall(r"\.ls-as-grade\{[^}]*repeat\((\d+),", sem_comentarios)]
        self.assertEqual(max(colunas), 4)

    def test_a_tela_sem_select_alert_nem_confirm(self):
        modelo = (RAIZ / "templates" / "assinaturas_inner.html").read_text(encoding="utf-8")
        for proibido in ("<select", "alert(", "confirm(", "<script"):
            self.assertNotIn(proibido, modelo)
        self.assertIn('data-ls-tela="assinaturas"', modelo)


# ======================================================================
# PELA TELA CLIENTES (seção 144)
# ======================================================================
class AssinaturasPeloClienteTests(BaseAssinaturas):
    """O dono: "através da aba de clientes devemos poder acessar as assinaturas deles"."""

    def setUp(self):
        super().setUp()
        # o cadastro ligado ao orçamento assinado do vendedor e à O.S. que aguarda
        self.buffet = Cliente.objects.create(nome_cliente="Buffet Alegria Sintético", telefone="(11) 97777-6655")
        Orcamento.objects.filter(pk=self.orc_assinado.pk).update(cliente=self.buffet)
        OrdemServico.objects.filter(pk=self.ordem.pk).update(cliente=self.buffet)
        # o do ambulante, com o contrato que aguarda
        self.escola = Cliente.objects.create(nome_cliente="Escola Modelo Fictícia", telefone="(11) 96666-0000")
        Orcamento.objects.filter(pk=self.orc_ambulante.pk).update(cliente=self.escola)
        # um HOMÔNIMO sem vínculo nenhum: não pode herdar as assinaturas pelo nome
        self.homonimo = Cliente.objects.create(nome_cliente="Buffet Alegria Sintético", telefone="(11) 95555-0000")
        self.sem_nada = Cliente.objects.create(nome_cliente="Cliente Sem Documento Sintético")

    def clientes(self, usuario):
        self.client.force_login(usuario)
        return self.client.get("/clientes/", **INTERNO)

    def fichas(self, resposta):
        return {ficha["obj"].pk: ficha["assinaturas"] for ficha in resposta.context["fichas"]}

    # ---------------- a contagem, na lista de clientes ----------------
    def test_a_contagem_de_cada_cliente_pelo_vinculo_de_verdade(self):
        numeros = self.fichas(self.clientes(self.gestao))
        buffet = numeros[self.buffet.pk]
        self.assertEqual((buffet["assinadas"], buffet["aguardando"], buffet["total"]), (1, 1, 2))
        self.assertEqual(buffet["resumo"], "1 assinada · 1 aguardando")
        self.assertEqual(buffet["url"], f"/assinaturas/?cliente={self.buffet.pk}")
        self.assertEqual(numeros[self.escola.pk]["resumo"], "1 aguardando")
        self.assertIsNone(numeros[self.homonimo.pk])   # o mesmo nome, outro cadastro
        self.assertIsNone(numeros[self.sem_nada.pk])

    def test_o_atalho_aparece_na_linha_so_de_quem_tem_documento(self):
        html = self.clientes(self.gestao).content.decode()
        self.assertIn(f'data-cliente-assinaturas="{self.buffet.pk}"', html)
        self.assertIn(f'href="/assinaturas/?cliente={self.buffet.pk}"', html)
        self.assertIn("1 assinada · 1 aguardando", html)
        self.assertIn("Assinaturas (2)", html)
        self.assertNotIn(f'data-cliente-assinaturas="{self.homonimo.pk}"', html)
        self.assertNotIn(f'data-cliente-assinaturas="{self.sem_nada.pk}"', html)

    def test_cada_um_conta_so_o_que_pode_ver(self):
        # Vendas não vê as das O.S.: do buffet, só o contrato assinado
        vendas = self.fichas(self.clientes(self.vendedor))
        self.assertEqual(vendas[self.buffet.pk]["resumo"], "1 assinada")
        self.assertEqual(vendas[self.escola.pk]["resumo"], "1 aguardando")
        # o Ambulante, só a própria carteira
        ambulante = self.fichas(self.clientes(self.ambulante))
        self.assertIsNone(ambulante.get(self.buffet.pk))
        self.assertEqual(ambulante[self.escola.pk]["resumo"], "1 aguardando")
        # quem conta é a regra da tela Assinaturas
        self.assertEqual(
            views_assinaturas.contagem_por_cliente(self.tecnico, [self.buffet.pk, self.escola.pk]),
            {self.buffet.pk: {"assinadas": 0, "aguardando": 1}},   # a Produção: só a O.S.
        )
        self.assertEqual(views_assinaturas.contagem_por_cliente(self.criacao, [self.buffet.pk]), {})

    def test_a_contagem_e_uma_consulta_so_para_a_pagina(self):
        self.clientes(self.gestao)

        def consultas():
            with CaptureQueriesContext(connection) as contexto:
                self.assertEqual(self.client.get("/clientes/", **INTERNO).status_code, 200)
            return len(contexto)

        antes = consultas()
        for numero in range(6):
            cliente = Cliente.objects.create(nome_cliente=f"Cliente Extra Sintético {numero}")
            orcamento = self.criar_orcamento(cliente.nome_cliente, self.vendedor, cliente=cliente)
            svc.gerar(orcamento, self.vendedor)
        self.assertLessEqual(consultas(), antes, "cada cliente a mais não pode custar uma ida ao banco")
        todos = list(Cliente.objects.values_list("pk", flat=True))
        with CaptureQueriesContext(connection) as contexto:
            views_assinaturas.contagem_por_cliente(self.gestao, todos)
        contagens = [c["sql"] for c in contexto if "documentoassinatura" in c["sql"].lower()]
        self.assertEqual(len(contagens), 1)   # a contagem em si é UMA consulta, qualquer que seja a página

    # ---------------- a tela Assinaturas filtrada ----------------
    def test_o_filtro_mostra_so_as_do_cliente_com_o_chip_para_limpar(self):
        resposta = self.abrir(self.gestao, f"?cliente={self.buffet.pk}")
        self.assertEqual(self.ids(resposta), {self.doc_assinado.pk, self.doc_os_aguardando.pk})
        html = resposta.content.decode()
        self.assertIn("Cliente: Buffet Alegria Sintético", html)
        self.assertIn(f'data-as-cliente="{self.buffet.pk}"', html)
        self.assertIn(f'href="/clientes/?abrir={self.buffet.pk}"', html)          # a Gestão abre o cadastro
        self.assertRegex(html, r'class="ls-as-chip ativo ls-as-chip-cliente" href="/assinaturas/"')  # o ✕ volta a todas
        # os chips e a busca guardam o cliente
        self.assertIn(f"?situacao=assinadas&amp;cliente={self.buffet.pk}", html)
        self.assertIn(f'name="cliente" value="{self.buffet.pk}"', html)
        numeros = {c["valor"]: c["quantos"] for c in resposta.context["chips_situacao"]}
        self.assertEqual(numeros, {"todas": 2, "assinadas": 1, "aguardando": 1})

    def test_o_filtro_e_pelo_vinculo_e_nao_pelo_nome(self):
        self.assertEqual(self.ids(self.abrir(self.gestao, f"?cliente={self.homonimo.pk}")), set())
        self.assertEqual(self.ids(self.abrir(self.gestao, f"?cliente={self.sem_nada.pk}")), set())
        self.assertEqual(self.ids(self.abrir(self.gestao, "?cliente=abc")), self.ids(self.abrir(self.gestao)))
        self.assertEqual(self.ids(self.abrir(self.gestao, "?cliente=999999")), set())

    def test_o_filtro_nao_vaza_o_que_a_pessoa_nao_ve(self):
        # o Ambulante pede o cliente do vendedor: nada, nem o nome
        resposta = self.abrir(self.ambulante, f"?cliente={self.buffet.pk}")
        self.assertEqual(self.ids(resposta), set())
        self.assertNotContains(resposta, "Maria Exemplo da Silva")
        # a Produção vê só a O.S. dele; o Financeiro, o contrato e a O.S.
        self.assertEqual(self.ids(self.abrir(self.tecnico, f"?cliente={self.buffet.pk}")), {self.doc_os_aguardando.pk})
        self.assertEqual(
            self.ids(self.abrir(self.financeiro, f"?cliente={self.buffet.pk}")),
            {self.doc_assinado.pk, self.doc_os_aguardando.pk},
        )
        # quem não vê o cadastro e não tem documento dele não lê nem o nome
        resposta = self.abrir(self.tecnico, f"?cliente={self.escola.pk}")
        self.assertEqual(self.ids(resposta), set())
        self.assertNotContains(resposta, "Escola Modelo Fictícia")
        self.assertContains(resposta, "Um cliente")
        # e quem não vê Clientes não ganha o atalho para o cadastro
        self.assertNotContains(self.abrir(self.tecnico, f"?cliente={self.buffet.pk}"), "data-as-cadastro")
        # a Criação continua fora
        self.assertEqual(self.abrir(self.criacao, f"?cliente={self.buffet.pk}").status_code, 302)

    def test_do_card_volta_se_ao_cliente(self):
        html = self.abrir(self.gestao).content.decode()
        self.assertIn(f'href="/assinaturas/?cliente={self.buffet.pk}" data-as-do-cliente="{self.buffet.pk}"', html)
        # já filtrada, o card não repete o atalho
        self.assertNotIn("data-as-do-cliente", self.abrir(self.gestao, f"?cliente={self.buffet.pk}").content.decode())
