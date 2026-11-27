"""Com ou sem sistema de ficha no site (LEIA-ME-V10, seção 150).

O dono: "o acréscimo (...) é 999 reais e deve se chamar sistema de ficha,
(...) para operações, eventos e afins". Na página do produto o cliente
escolhe com ou sem; o preço é sempre o do servidor.

O que estes testes protegem:

  * a página do produto mostra os dois chips e os DOIS preços (o sem e o
    com, calculados no servidor) só na máquina que oferece; brinquedão, kit,
    máquina desligada pela Gestão e o acréscimo vazio não mostram nada;
  * o carrinho grava a escolha e cobra o preço COM; com e sem são duas
    linhas; a escolha FORÇADA em quem não oferece entra SEM (e no preço do
    cadastro); se a Gestão desliga depois, a linha volta ao preço do
    cadastro e perde a marca;
  * o pedido leva a marca no nome do item e o preço COM; a devolução ao
    carrinho traz a escolha (e o adesivo) de volta;
  * a lista de montagem do pedido mostra a marca na variante; o contrato do
    pedido do site (seção 145) diz "com sistema de ficha";
  * promoção e combo NÃO têm a opção (o preço deles é fechado);
  * a migração é só de esquema.
"""

import importlib
from decimal import Decimal

from django.db import migrations
from django.urls import reverse

from core import checkout
from core.models import Brinquedos, CategoriasBrinquedos, ItemCarrinho, ItemPedido, VarianteAdesivo
from core.tests_carrinho_rapido import Base, _brinquedo, _cliente

XHR = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
MARCA = " — com sistema de ficha"


class BaseFichaSite(Base):
    def setUp(self):
        super().setUp()
        from sistema_interno import moedeiro, montagem

        moedeiro.esquecer()
        self.assertEqual(moedeiro.acrescimo(), Decimal("999.00"))
        self.brinquedao = _brinquedo("Brinquedão Sintético", "85000")
        categoria = CategoriasBrinquedos.objects.create(nome_categoria="Brinquedão", imagem_categoria="c/b.png")
        self.brinquedao.categorias_brinquedos.add(categoria)
        montagem.configuracao().categorias_projeto.add(categoria)
        from django.core.cache import cache

        cache.clear()
        self.usuario = _cliente("cliente-ficha")
        self.client.force_login(self.usuario)

    def adicionar(self, tipo, objeto, **dados):
        return self.client.post(reverse("adicionar_ao_carrinho", args=[tipo, objeto.pk]), dados, **XHR)

    def linhas(self):
        return list(ItemCarrinho.objects.filter(carrinho__cliente=self.usuario.perfil).order_by("id"))

    def desligar_o_acrescimo(self):
        from sistema_interno import moedeiro
        from sistema_interno.models import DadosContrato

        DadosContrato.objects.update(acrescimo_moedeiro=None)
        moedeiro.esquecer()


class PaginaDoProdutoTests(BaseFichaSite):
    def pagina(self, brinquedo, **consulta):
        return self.client.get(reverse("brinquedo_detalhe", args=[brinquedo.pk]), consulta)

    def test_a_maquina_mostra_os_chips_e_os_dois_precos(self):
        resposta = self.pagina(self.air)
        self.assertEqual(resposta.status_code, 200)
        ficha = resposta.context["ficha"]
        self.assertEqual((ficha["acrescimo"], ficha["preco_com"]), (Decimal("999.00"), Decimal("9989.00")))
        html = resposta.content.decode()
        self.assertIn('data-ficha-opcao="sem"', html)
        self.assertIn('data-ficha-opcao="com"', html)
        self.assertIn("Sem sistema de ficha", html)
        self.assertIn("Com sistema de ficha", html)
        self.assertIn("+ R$ 999,00", html)
        self.assertIn("operações, eventos e afins", html)
        self.assertIn("9.989,00", html)                      # o preço COM, do servidor
        self.assertIn('name="ficha" value="sem"', html)
        trecho = html[html.index("data-ficha "):html.index("produto-preco-nota")]
        self.assertNotIn("<select", trecho)
        self.assertNotIn("moedeiro", html.lower())

    def test_o_endereco_com_a_escolha_abre_no_com(self):
        html = self.pagina(self.air, ficha="com").content.decode()
        self.assertIn('name="ficha" value="com"', html)
        self.assertIn('data-ficha-preco="sem" hidden', html)

    def test_quem_nao_oferece_nao_mostra(self):
        kit = _brinquedo("Kit Eletrônico Sintético", "1200", eh_kit=True)
        desligada = _brinquedo("Máquina Desligada", "5000", moedeiro="nao")
        for brinquedo in (self.brinquedao, kit, desligada):
            with self.subTest(brinquedo=brinquedo.nome_brinquedo):
                resposta = self.pagina(brinquedo)
                self.assertEqual(resposta.status_code, 200)
                self.assertNotIn("ficha", resposta.context)
                self.assertNotContains(resposta, 'data-ficha-opcao="com"')
        self.desligar_o_acrescimo()
        self.assertNotContains(self.pagina(self.air), 'data-ficha-opcao="com"')

    def test_o_icone_esta_no_recorte_do_site(self):
        from pathlib import Path

        from django.conf import settings

        recorte = (Path(settings.BASE_DIR) / "core/static/vendor/fontawesome-site/icones.txt").read_text().split()
        self.assertIn("fa-coins", recorte)


class CarrinhoTests(BaseFichaSite):
    def test_grava_a_escolha_e_cobra_o_preco_com(self):
        self.assertEqual(self.adicionar("brinquedo", self.air, ficha="com", quantidade=2).status_code, 200)
        (linha,) = self.linhas()
        self.assertTrue(linha.com_ficha)
        self.assertEqual((linha.preco_unitario, linha.subtotal), (Decimal("9989.00"), Decimal("19978.00")))
        self.assertEqual(linha.nome_com_adesivo, "Air Game Kids" + MARCA)
        self.assertEqual(linha.carrinho.total_bruto, Decimal("19978.00"))
        carrinho = self.client.get(reverse("carrinho"))
        self.assertContains(carrinho, "Com sistema de ficha")
        self.assertContains(carrinho, "9.989,00")

    def test_a_pagina_manda_a_escolha_e_a_resposta_diz_o_preco_com(self):
        # o envio é por JS: o campo `ficha` tem de ir junto (faltou uma vez; só o navegador mostrou)
        from pathlib import Path

        from django.conf import settings

        base = Path(settings.BASE_DIR)
        self.assertIn('dados.set("ficha"', (base / "core/static/site/ls-carrinho-rapido.js").read_text())
        self.assertIn("ficha: campos.get('ficha')", (base / "core/templates/base.html").read_text())
        item = self.adicionar("brinquedo", self.air, ficha="com").json()["item"]
        self.assertEqual((item["com_ficha"], item["preco_unitario"]), (True, "9989.00"))
        self.assertNotIn("com_ficha", self.adicionar("brinquedo", self.air).json()["item"])

    def test_com_e_sem_sao_duas_linhas(self):
        self.adicionar("brinquedo", self.air, ficha="com")
        self.adicionar("brinquedo", self.air, ficha="sem")
        self.adicionar("brinquedo", self.air)
        self.adicionar("brinquedo", self.air, ficha="com")
        com, sem = self.linhas()
        self.assertEqual((com.com_ficha, com.quantidade, com.preco_unitario), (True, 2, Decimal("9989.00")))
        self.assertEqual((sem.com_ficha, sem.quantidade, sem.preco_unitario), (False, 2, Decimal("8990.00")))

    def test_a_escolha_forcada_em_quem_nao_oferece_entra_sem(self):
        desligada = _brinquedo("Máquina Desligada", "5000", moedeiro="nao")
        for objeto, preco in ((self.brinquedao, "85000.00"), (desligada, "5000.00")):
            self.adicionar("brinquedo", objeto, ficha="com")
        self.adicionar("promocao", self.promo, ficha="com")
        self.adicionar("combo", self.combo, ficha="com")
        self.adicionar("peca", self.peca, ficha="com")
        linhas = self.linhas()
        self.assertEqual(len(linhas), 5)
        for linha in linhas:
            self.assertFalse(linha.com_ficha, linha.nome_com_adesivo)
            self.assertNotIn("sistema de ficha", linha.nome_com_adesivo)
        self.assertEqual([l.preco_unitario for l in linhas],
                         [Decimal("85000"), Decimal("5000"), Decimal("4990"), Decimal("25900"), Decimal("89.90")])

    def test_marcado_no_banco_em_quem_nao_oferece_nao_soma(self):
        # a linha marcada à força (ou de antes de a Gestão desligar) não cobra nem diz
        self.adicionar("brinquedo", self.air, ficha="com")
        Brinquedos.objects.filter(pk=self.air.pk).update(moedeiro="nao")
        (linha,) = self.linhas()
        self.assertTrue(linha.com_ficha)
        self.assertFalse(linha.ficha_vale)
        self.assertEqual(linha.preco_unitario, Decimal("8990"))
        self.assertEqual(linha.nome_com_adesivo, "Air Game Kids")
        self.adicionar("promocao", self.promo)
        ItemCarrinho.objects.filter(carrinho__cliente=self.usuario.perfil).update(com_ficha=True)
        self.assertEqual([l.preco_unitario for l in self.linhas()], [Decimal("8990"), Decimal("4990")])

    def test_sem_o_acrescimo_ninguem_escolhe(self):
        self.desligar_o_acrescimo()
        self.adicionar("brinquedo", self.air, ficha="com")
        (linha,) = self.linhas()
        self.assertEqual((linha.com_ficha, linha.preco_unitario), (False, Decimal("8990")))

    def test_o_adesivo_e_a_ficha_no_mesmo_item(self):
        VarianteAdesivo.objects.create(brinquedo=self.air, nome="Candy", slug="candy", ativo=True)
        self.adicionar("brinquedo", self.air, ficha="com", adesivo="Candy")
        (linha,) = self.linhas()
        self.assertEqual(linha.nome_com_adesivo, "Air Game Kids — adesivo Candy" + MARCA)

    def test_a_migracao_e_so_de_esquema(self):
        modulo = importlib.import_module("core.migrations.0221_item_do_carrinho_com_sistema_de_ficha")
        self.assertTrue(all(isinstance(o, migrations.AddField) for o in modulo.Migration.operations))


class PedidoTests(BaseFichaSite):
    def reservar(self):
        carrinho = checkout.carrinho_do_cliente(self.usuario.perfil)
        resultado = checkout.reservar_pedido(carrinho, self.usuario)
        return resultado[0] if isinstance(resultado, tuple) else resultado

    def test_o_pedido_leva_a_marca_e_o_preco_com(self):
        self.adicionar("brinquedo", self.air, ficha="com")
        pedido = self.reservar()
        (item,) = ItemPedido.objects.filter(pedido=pedido)
        self.assertEqual((item.nome_item, item.preco_unitario, item.subtotal),
                         ("Air Game Kids" + MARCA, Decimal("9989.00"), Decimal("9989.00")))
        self.assertEqual(pedido.total_liquido, Decimal("9989.00"))
        # a lista de montagem: a marca na variante, para a fábrica
        from sistema_interno import montagem

        (linha,) = montagem.linhas_do_pedido(pedido)
        self.assertEqual((linha.nome, linha.variante), ("Air Game Kids", "com sistema de ficha"))

    def test_a_devolucao_ao_carrinho_traz_a_escolha_e_o_adesivo(self):
        VarianteAdesivo.objects.create(brinquedo=self.air, nome="Candy", slug="candy", ativo=True)
        self.adicionar("brinquedo", self.air, ficha="com", adesivo="Candy")
        pedido = self.reservar()
        self.assertEqual(ItemPedido.objects.get(pedido=pedido).nome_item, "Air Game Kids — adesivo Candy" + MARCA)
        ItemCarrinho.objects.filter(carrinho__cliente=self.usuario.perfil).delete()
        pedido.devolver_ao_carrinho()
        (linha,) = self.linhas()
        self.assertEqual((linha.adesivo, linha.com_ficha, linha.preco_unitario), ("Candy", True, Decimal("9989.00")))

    def test_o_contrato_do_pedido_diz_com_sistema_de_ficha(self):
        from sistema_interno import documento_pedido
        from sistema_interno.tests_documento_assinatura import CPF_DO_CLIENTE, preencher_dados_do_contrato

        preencher_dados_do_contrato()
        self.adicionar("brinquedo", self.air, ficha="com")
        pedido = self.reservar()
        type(pedido).objects.filter(pk=pedido.pk).update(status="pago")
        pedido.refresh_from_db()
        documento = documento_pedido.gerar_do_pedido(pedido, CPF_DO_CLIENTE, self.usuario)
        self.assertIn("com sistema de ficha", " ".join(i["descricao"] for i in documento.conteudo["itens"]))
        self.assertEqual(documento.conteudo["valores"]["total"], "9989.00")
