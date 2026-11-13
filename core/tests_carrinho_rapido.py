"""O carrinho rápido: o botão do carrinho no topo e a folha de quantidade.

O pedido: "fora o carrinho deve ser visível, opção de quantidade, então
abra um modal para add quantidade e moderno aparecendo que há itens".

O que estes testes protegem:

  * a prévia da folha (`/carrinho/previa/<tipo>/<id>/`) responde pelas
    MESMAS regras do "adicionar" (`_item_vendavel`): brinquedo só à venda
    na loja, promoção só no ar e com preço, combo só ativo, peça só da
    vitrine e com preço -- e nunca o item de manutenção, cujo preço é
    custo interno;
  * o preço da prévia é o que o carrinho cobra (`ItemCarrinho.preco_unitario`);
  * o "adicionar" devolve, além do `total_itens` de sempre, o total do
    carrinho e o item, para o "pronto" da folha;
  * o topo mostra o botão do carrinho com `data-carrinho-total` para o
    cliente e para o visitante, e não para a equipe (que nem carrega a
    folha);
  * o base.html entrega todo "Adicionar" à folha, sem quebrar quem espera a
    Promise de sempre.
"""

import datetime
import re
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Brinquedos, Combos, ImagemPeca, ItemCarrinho, PecasReposicao, Promocoes

RAIZ = Path(__file__).resolve().parent
SITE = RAIZ / "static" / "site"
XHR = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
HOJE = timezone.localdate()


def _brinquedo(nome="Air Game Kids", valor="8990", **campos):
    dados = {
        "descricao": f"{nome}.", "avaliacao": Decimal("4.8"), "voltz": "220V",
        "valor_brinquedo": Decimal(valor) if valor else None, "exibir_na_loja": True,
        "imagem_brinquedo": "imagens_brinquedos/air-game.png",
    }
    dados.update(campos)
    return Brinquedos.objects.create(nome_brinquedo=nome, **dados)


def _cliente(usuario="cliente-carrinho"):
    user = User.objects.create_user(usuario, f"{usuario}@exemplo.com", "x", first_name="Marina")
    perfil = user.perfil
    perfil.telefone = "11999990000"  # sem telefone o site pede o cadastro antes
    perfil.save()
    return user


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.air = _brinquedo()
        self.promo = Promocoes.objects.create(
            descricao="Black Friday: Air Game Kids", brinquedos=self.air, preco_promocao=Decimal("4990"),
            ativo=True, valida_ate=HOJE + datetime.timedelta(days=3),
            imagem_promocao="promocoes/card.webp",
        )
        self.combo = Combos.objects.create(descricao="Combo Arena", valor_combo=Decimal("25900"),
                                           imagem_combo="combos/arena.webp")
        self.combo.brinquedos.add(self.air)
        self.peca = PecasReposicao.objects.create(nome="Maneta do Air Game", descricao_peca="Original.",
                                                  preco_venda=Decimal("89.90"))
        ImagemPeca.objects.create(peca_reposicao=self.peca, imagem="pecas_reposicao/maneta.webp", ordem=1)

    def tearDown(self):
        cache.clear()

    def previa(self, tipo, objeto_id, **extra):
        return self.client.get(reverse("previa_do_carrinho", args=[tipo, objeto_id]), **XHR, **extra)


class PreviaTests(Base):
    def test_brinquedo_a_venda(self):
        resposta = self.previa("brinquedo", self.air.pk)
        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertTrue(dados["sucesso"])
        self.assertFalse(dados["logado"])  # a prévia é pública; a folha pede para entrar
        item = dados["item"]
        self.assertEqual(item["nome"], "Air Game Kids")
        self.assertEqual(item["tipo"], "brinquedo")
        self.assertEqual(item["rotulo"], "Brinquedo")
        self.assertEqual(item["preco_unitario"], "8990.00")
        self.assertEqual(item["preco_unitario_formatado"], "R$ 8.990,00")
        # a foto do card da loja (mesma largura): o navegador já a tem
        self.assertIn("air-game", item["foto"])
        self.assertIn("w_720", item["foto"])
        self.assertIn("no-cache", resposta.get("Cache-Control", ""))

    def test_logado(self):
        self.client.force_login(_cliente())
        self.assertTrue(self.previa("brinquedo", self.air.pk).json()["logado"])

    def test_brinquedo_que_nao_esta_a_venda_e_404(self):
        so_orcamento = _brinquedo("Pista de boliche", exibir_na_loja=False)
        sem_preco = _brinquedo("Brinquedão", valor=None)
        preco_zero = _brinquedo("Brinde", valor="0")
        desligado = _brinquedo("Antigo", ativo=False)
        for brinquedo in (so_orcamento, sem_preco, preco_zero, desligado):
            with self.subTest(brinquedo=brinquedo.nome_brinquedo):
                resposta = self.previa("brinquedo", brinquedo.pk)
                self.assertEqual(resposta.status_code, 404)
                self.assertEqual(resposta.json()["erro"], "Este item não está à venda no momento.")
        self.assertEqual(self.previa("brinquedo", 999999).status_code, 404)

    def test_promocao_vale_o_preco_dela_e_some_quando_vence(self):
        dados = self.previa("promocao", self.promo.pk).json()
        self.assertEqual(dados["item"]["preco_unitario"], "4990.00")
        self.assertEqual(dados["item"]["rotulo"], "Promoção")
        self.assertIn("card", dados["item"]["foto"])

        vencida = Promocoes.objects.create(descricao="Vencida", brinquedos=self.air, preco_promocao=Decimal("100"),
                                           ativo=True, valida_ate=HOJE - datetime.timedelta(days=1))
        sem_preco = Promocoes.objects.create(descricao="Leve 4", brinquedos=self.air, preco_promocao=None,
                                             ativo=True, condicoes="Na compra de 3, leve 4")
        desligada = Promocoes.objects.create(descricao="Desligada", brinquedos=self.air,
                                             preco_promocao=Decimal("100"), ativo=False)
        for promocao in (vencida, sem_preco, desligada):
            with self.subTest(promocao=promocao.descricao):
                self.assertEqual(self.previa("promocao", promocao.pk).status_code, 404)

    def test_promocao_sem_foto_propria_usa_a_do_brinquedo(self):
        self.promo.imagem_promocao = None
        self.promo.save()
        self.assertIn("air-game", self.previa("promocao", self.promo.pk).json()["item"]["foto"])

    def test_combo(self):
        item = self.previa("combo", self.combo.pk).json()["item"]
        self.assertEqual((item["nome"], item["preco_unitario"]), ("Combo Arena", "25900.00"))
        self.combo.ativo = False
        self.combo.save()
        self.assertEqual(self.previa("combo", self.combo.pk).status_code, 404)

    def test_peca_da_vitrine_com_preco(self):
        item = self.previa("peca", self.peca.pk).json()["item"]
        self.assertEqual((item["nome"], item["preco_unitario"]), ("Maneta do Air Game", "89.90"))
        self.assertIn("maneta", item["foto"])

    def test_item_de_manutencao_nunca_mostra_o_preco(self):
        interno = PecasReposicao.objects.create(
            nome="Retentor 2019", descricao_peca="Custo interno.", preco_venda=Decimal("12.50"),
            uso=PecasReposicao.Uso.MANUTENCAO,
        )
        resposta = self.previa("peca", interno.pk)
        self.assertEqual(resposta.status_code, 404)
        self.assertNotIn("12.50", resposta.content.decode())
        self.assertNotIn("Retentor", resposta.content.decode())

    def test_peca_sob_consulta_e_desligada_sao_404(self):
        sob_consulta = PecasReposicao.objects.create(nome="Placa", descricao_peca="Consulte.")
        desligada = PecasReposicao.objects.create(nome="Velha", descricao_peca=".", preco_venda=Decimal("5"),
                                                  ativo=False)
        for peca in (sob_consulta, desligada):
            with self.subTest(peca=peca.nome):
                self.assertEqual(self.previa("peca", peca.pk).status_code, 404)

    def test_tipo_invalido_e_metodo(self):
        self.assertEqual(self.previa("cupom", 1).status_code, 400)
        resposta = self.client.post(reverse("previa_do_carrinho", args=["brinquedo", self.air.pk]))
        self.assertEqual(resposta.status_code, 405)

    def test_o_preco_e_o_que_o_carrinho_cobra(self):
        for tipo, objeto in (("brinquedo", self.air), ("promocao", self.promo),
                             ("combo", self.combo), ("peca", self.peca)):
            with self.subTest(tipo=tipo):
                esperado = Decimal(ItemCarrinho(item=objeto).preco_unitario).quantize(Decimal("0.01"))
                self.assertEqual(self.previa(tipo, objeto.pk).json()["item"]["preco_unitario"], f"{esperado:.2f}")

    def test_a_equipe_nao_compra(self):
        equipe = User.objects.create_user("gerente", "g@lazersport.com", "x", is_staff=True)
        self.client.force_login(equipe)
        resposta = self.previa("brinquedo", self.air.pk)
        self.assertEqual(resposta.status_code, 403)
        self.assertNotIn("item", resposta.json())


class AdicionarTests(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(_cliente())

    def adicionar(self, tipo, objeto_id, **dados):
        return self.client.post(reverse("adicionar_ao_carrinho", args=[tipo, objeto_id]), dados, **XHR)

    def test_a_resposta_traz_o_total_e_o_item_para_o_pronto(self):
        self.adicionar("brinquedo", self.air.pk, quantidade=2)
        resposta = self.adicionar("promocao", self.promo.pk, quantidade=1)
        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertTrue(dados["sucesso"])
        self.assertEqual(dados["total_itens"], 3)
        self.assertEqual(dados["quantidade"], 1)
        self.assertEqual(dados["total_carrinho"], "22970.00")  # 2 x 8.990 + 4.990
        self.assertEqual(dados["total_carrinho_formatado"], "R$ 22.970,00")
        self.assertEqual(dados["item"]["nome"], "Black Friday: Air Game Kids")
        self.assertEqual(dados["item"]["preco_unitario"], "4990.00")

    def test_sem_conta_pede_login(self):
        self.client.logout()
        resposta = self.adicionar("brinquedo", self.air.pk)
        self.assertEqual(resposta.status_code, 403)
        self.assertIn("login", resposta.json()["erro"])

    def test_as_regras_sao_as_da_previa(self):
        interno = PecasReposicao.objects.create(nome="Retentor", descricao_peca=".", preco_venda=Decimal("12.5"),
                                                uso=PecasReposicao.Uso.MANUTENCAO)
        sob_consulta = PecasReposicao.objects.create(nome="Placa", descricao_peca=".")
        self.combo.ativo = False
        self.combo.save()
        for tipo, objeto_id in (("peca", interno.pk), ("peca", sob_consulta.pk), ("combo", self.combo.pk)):
            with self.subTest(tipo=tipo, id=objeto_id):
                self.assertEqual(self.adicionar(tipo, objeto_id).status_code, 404)
        self.assertEqual(self.adicionar("cupom", 1).status_code, 400)
        self.assertFalse(ItemCarrinho.objects.exists())

    def test_peca_da_vitrine_entra(self):
        dados = self.adicionar("peca", self.peca.pk, quantidade=4).json()
        self.assertEqual(dados["total_itens"], 4)
        self.assertEqual(dados["total_carrinho"], "359.60")


class TopoTests(Base):
    URL = "/loja/"

    def botao(self, html):
        achado = re.search(r'<a class="ls-topo-carrinho"[^>]*>.*?</a>', html, flags=re.S)
        return achado.group(0) if achado else ""

    def test_cliente_ve_o_carrinho_com_o_numero(self):
        self.client.force_login(_cliente())
        self.client.post(reverse("adicionar_ao_carrinho", args=["brinquedo", self.air.pk]), {"quantidade": 3}, **XHR)
        html = self.client.get(self.URL).content.decode()
        botao = self.botao(html)
        self.assertTrue(botao, "o botão do carrinho não está no topo")
        self.assertIn(f'href="{reverse("carrinho")}#carrinho"', botao)
        self.assertRegex(botao, r'<b class="ls-topo-carrinho-selo" data-carrinho-total>3</b>')
        self.assertIn("site/ls-carrinho-rapido.js", html)
        self.assertIn("site/ls-carrinho-rapido.css", html)
        self.assertIn(f'data-url-login="{reverse("login")}"', html)

    def test_carrinho_vazio_esconde_o_selo(self):
        self.client.force_login(_cliente())
        botao = self.botao(self.client.get(self.URL).content.decode())
        self.assertIn('class="ls-topo-carrinho-selo vazio" data-carrinho-total>0</b>', botao)

    def test_visitante_tambem_ve(self):
        html = self.client.get(self.URL).content.decode()
        botao = self.botao(html)
        self.assertIn("data-carrinho-total", botao)
        self.assertIn("vazio", botao)
        self.assertIn("site/ls-carrinho-rapido.js", html)

    def test_equipe_nao_ve_nem_carrega_a_folha(self):
        equipe = User.objects.create_user("gerente", "g@lazersport.com", "x", is_staff=True)
        self.client.force_login(equipe)
        html = self.client.get(self.URL).content.decode()
        self.assertEqual(self.botao(html), "")
        self.assertNotIn("ls-topo-carrinho", html)
        # nenhum selo do carrinho em lugar nenhum (o seletor no script não conta)
        self.assertNotRegex(html, r"<[^>]*\sdata-carrinho-total[\s>]")
        self.assertNotIn("site/ls-carrinho-rapido.js", html)
        self.assertNotIn("site/ls-carrinho-rapido.css", html)

    def test_loja_so_oferece_adicionar_ao_que_tem_preco(self):
        PecasReposicao.objects.create(nome="Placa sob consulta", descricao_peca="Consulte.")
        html = self.client.get(self.URL).content.decode()
        cartao = html.split("Placa sob consulta", 1)[1].split("</article>", 1)[0]
        self.assertNotIn("adicionarItemLoja", cartao)
        self.assertIn("Consultar", cartao)
        self.assertIn(f"adicionarItemLoja(event, 'peca', {self.peca.pk}", html)


class JavaScriptTests(SimpleTestCase):
    """O desenho do fluxo, conferido no texto (o navegador fica com o Playwright)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.js = (SITE / "ls-carrinho-rapido.js").read_text(encoding="utf-8")
        cls.css = (SITE / "ls-carrinho-rapido.css").read_text(encoding="utf-8")
        cls.base = (RAIZ / "templates" / "base.html").read_text(encoding="utf-8")

    def test_a_folha(self):
        for parte in ("window.LSCarrinhoRapido = {", "showModal", '"aria-modal": "true"', 'role: "dialog"',
                      '"cancel"', "prenderFoco", "devolverFoco", "/carrinho/previa/", "/carrinho/adicionar/",
                      "cancelado: true", "login: true", "bloqueado: true", "LSCartLoading",
                      "atualizarBadgeCarrinho", "quantidade-input", "prefers-reduced-motion", "MAXIMO = 99",
                      "?next=", "MutationObserver", "carrinhoNaBarra", "minhaVez !== vez"):
            with self.subTest(parte=parte):
                self.assertIn(parte, self.js)

    def test_o_css_respeita_movimento_reduzido_e_os_alvos(self):
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css)
        self.assertIn("[data-carrinho-total].ls-cr-pulo", self.css)
        self.assertRegex(self.css, r"\.ls-cr-botao \{[^}]*min-height: 52px")
        self.assertRegex(self.css, r"\.ls-cr-fechar \{[^}]*width: 44px")

    def test_o_base_entrega_o_adicionar_a_folha(self):
        inicio = self.base.index("function adicionarAoCarrinho(")
        corpo = self.base[inicio:inicio + 1200]
        self.assertIn("window.LSCarrinhoRapido.adicionar(tipo, id, irParaCarrinho", corpo)
        # o envio do formulário da página do brinquedo leva a quantidade, o adesivo e o "Comprar agora"
        envio = self.base[self.base.index("document.addEventListener('submit'"):][:1800]
        self.assertIn("campos.get('quantidade')", envio)
        self.assertIn("campos.get('adesivo')", envio)
        self.assertIn("event.submitter.value === 'carrinho'", envio)
