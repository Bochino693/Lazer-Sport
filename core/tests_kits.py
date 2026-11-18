"""O kit eletrônico: um produto, junto com as máquinas (LEIA-ME seções 105 e 107).

O dono pediu o kit ("os componentes eletrônicos sem a máquina para troca ou
semi instalação [...] para o cara instalar toda parte elétrica na máquina caso
ele só tenha a máquina") e, ao ver a vitrine à parte: "vc criou outra sub
section e nem sei se outro objeto, mas eles devem estar junto com os
produtos". O kit é um `Brinquedos` com `eh_kit`.

O que estes testes protegem:

  * o kit aparece COM os produtos -- a grade da home, /brinquedos/, a loja, a
    categoria "Kits eletrônicos" e a da máquina, a busca, o sitemap --, no
    mesmo card, com o selo "Kit" e a linha "N itens: ..."; não aparece entre
    as peças, na Arena 3D nem como a máquina de um jogo;
  * a página é a do produto, com "O que vem no kit" (a foto ou o ícone de
    cada item, a quantidade, a peça avulsa) e "Para a máquina X"; a página
    da máquina chama para o kit;
  * sem preço: "Sob consulta" e o WhatsApp, nunca R$ 0,00, e o carrinho
    recusa; com preço, carrinho e boleto como todo produto;
  * os endereços antigos (/kits/, /kits/<n>/, /pecas/<n>/) levam ao lugar novo;
  * a migração 0212, com os modelos históricos: a peça-kit vira produto
    (a mesma foto, os itens, as curtidas, as categorias), a peça sai (ou
    fica desligada, se um pedido aponta para ela), e rodar de novo não
    duplica nada;
  * o painel (Brinquedos) salva a marca, a máquina (chips de rádio, sem
    <select>) e os itens, na ordem da tela; a tela de Peças não tem mais o kit;
  * o comando `kits_eletronicos` e o menu.
"""

import importlib
import json
import re
import tempfile
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from PIL import Image

from . import kits
from .models import (
    Brinquedos,
    Carrinho,
    CategoriasBrinquedos,
    ComponenteKit,
    Favorito,
    ImagemBrinquedo,
    ImagemPeca,
    ItemCarrinho,
    ItemPedido,
    PecasReposicao,
    Pedido,
)

XHR = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
INTERNO = "interno.testserver"

migracao_0212 = importlib.import_module("core.migrations.0212_kits_viram_produtos")
ANTES = ("core", "0211_kit_vira_produto_inicio")
CONVERTE = ("core", "0212_kits_viram_produtos")


def _maquina(nome, **campos):
    dados = {
        "descricao": f"{nome}.", "avaliacao": Decimal("4.8"), "voltz": "220V",
        "imagem_brinquedo": f"imagens_brinquedos/{nome.lower().replace(' ', '-')}.webp",
    }
    dados.update(campos)
    return Brinquedos.objects.create(nome_brinquedo=nome, **dados)


def _cliente(usuario="cliente-kit"):
    user = User.objects.create_user(usuario, f"{usuario}@exemplo.com", "Senha#12345", first_name="Bia")
    perfil = user.perfil
    perfil.telefone = "(11)91234-5678"  # sem telefone o site pede o cadastro antes
    perfil.save(update_fields=["telefone"])
    return user


def _foto(nome="frente.png"):
    arquivo = BytesIO()
    Image.new("RGB", (4, 4), "navy").save(arquivo, "PNG")
    return SimpleUploadedFile(nome, arquivo.getvalue(), content_type="image/png")


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.cat_boliche = CategoriasBrinquedos.objects.create(
            nome_categoria="Boliche Virtual", imagem_categoria="categorias/boliche.webp")
        self.cat_kits = CategoriasBrinquedos.objects.create(
            nome_categoria="Kits eletrônicos", imagem_categoria="pecas_reposicao/kit-boliche-virtual-ab12")
        self.boliche = _maquina("Boliche Virtual")
        self.boliche.categorias_brinquedos.add(self.cat_boliche)
        self.cabo = PecasReposicao.objects.create(
            nome="Cabo HDMI", descricao_peca="Cabo HDMI de 1,5 m.", preco_venda=Decimal("29.90"),
        )
        self.motor = PecasReposicao.objects.create(
            nome="Motor 1/4 CV", descricao_peca="Motor do carrossel.", preco_venda=Decimal("450"),
        )
        self.kit = _maquina(
            "Kit Boliche Virtual", descricao="A parte eletrônica completa do Boliche Virtual.",
            imagem_brinquedo="pecas_reposicao/kit-boliche-virtual-ab12", exibir_na_loja=True,
            eh_kit=True, maquina=self.boliche, id_kit_antigo=24,
        )
        self.kit.categorias_brinquedos.add(self.cat_kits, self.cat_boliche)
        for ordem, (nome, detalhe, peca) in enumerate((
            ("Placa Zero Delay", "", None),
            ("TV Box", "Com o jogo Dragon Bowling", None),
            ("Cabo HDMI", "", self.cabo),
            ("Barra com 5 sensores", "Leem cada jogada da bola na pista", None),
        ), start=1):
            ComponenteKit.objects.create(kit=self.kit, nome=nome, detalhe=detalhe, ordem=ordem, peca=peca)

    def tearDown(self):
        cache.clear()

    def html(self, url, **params):
        resposta = self.client.get(url, params)
        self.assertEqual(resposta.status_code, 200, url)
        return resposta.content.decode()


class JuntoComOsProdutosTests(Base):
    RESUMO = "4 itens: Placa Zero Delay, TV Box, Cabo HDMI…"

    def test_na_grade_da_home_com_o_selo_e_os_itens(self):
        home = self.html(reverse("home"))
        grade = home[home.index('id="grid-cards"'):]
        grade = grade[:grade.index('id="paginacao-wrapper"')]
        self.assertIn("Kit Boliche Virtual", grade)
        self.assertIn('class="ls-kit-selo"', grade)
        self.assertIn(self.RESUMO, grade)
        self.assertIn(f'href="{reverse("brinquedo_detalhe", args=[self.kit.pk])}#bread"', grade)
        # o card do kit sem preço diz "Sob consulta" (na loja, mas sem valor)
        card = grade[grade.index(f'data-id="{self.kit.pk}"'):]
        card = card[:card.index("</article>")]
        self.assertIn("Sob consulta", card)
        self.assertNotIn("À venda", card)
        # a vitrine à parte e a faixa da home não existem mais
        self.assertNotIn('id="kits-section"', home)
        self.assertNotIn("home-kits.css", home)
        # o quadro inicial (as máquinas em 3D) é só de máquinas
        self.assertFalse(any(item.get("nome") == "Kit Boliche Virtual"
                             for item in self.client.get(reverse("home")).context["vitrine_quadro"]))

    def test_no_catalogo_na_loja_e_nas_categorias(self):
        catalogo = self.html(reverse("brinquedos"))
        self.assertIn("Kit Boliche Virtual", catalogo)
        self.assertIn('class="ls-kit-selo"', catalogo)
        self.assertIn(self.RESUMO, catalogo)
        self.assertIn("Para a máquina Boliche Virtual", catalogo)
        self.assertIn("Kit sob consulta", catalogo)

        loja = self.html(reverse("loja"))
        self.assertIn("Kit Boliche Virtual", loja)
        self.assertIn('class="loja-card-tipo kit"', loja)
        self.assertIn("Para Boliche Virtual", loja)
        self.assertNotIn('data-tipo="kit"', loja)  # sem filtro à parte: vem com as máquinas
        self.assertNotIn(f"adicionarItemLoja(event, 'brinquedo', {self.kit.pk}", loja)  # sem preço

        kits_html = self.html(reverse("categoria_detalhe", args=[self.cat_kits.pk]))
        self.assertIn("Kit Boliche Virtual", kits_html)
        self.assertIn('class="ls-kit-selo"', kits_html)
        self.assertIn("A parte eletrônica completa de cada máquina", kits_html)  # o texto da categoria dos kits
        self.assertIn("Kit Boliche Virtual", self.html(reverse("categoria_detalhe", args=[self.cat_boliche.pk])))
        # "À venda" é só com preço: o kit sem preço fica no filtro do orçamento
        self.assertNotIn("Kit Boliche Virtual",
                         self.html(reverse("categoria_detalhe", args=[self.cat_kits.pk]), disp="loja"))
        self.assertIn("Kit Boliche Virtual",
                      self.html(reverse("categoria_detalhe", args=[self.cat_kits.pk]), disp="consulta"))

    def test_fora_das_pecas(self):
        pecas = self.html(reverse("pecas_reposicao"))
        self.assertIn("Motor 1/4 CV", pecas)
        self.assertNotIn("Kit Boliche Virtual", pecas)

    def test_a_busca_acha_pelo_nome_pela_maquina_e_pelos_itens(self):
        for termo in ("kit boliche", "tv box"):
            with self.subTest(termo=termo):
                busca = self.html(reverse("search"), q=termo)
                self.assertIn("Kit Boliche Virtual", busca)
                self.assertIn("Kit eletrônico", busca)
                self.assertIn(reverse("brinquedo_detalhe", args=[self.kit.pk]), busca)

    def test_fora_da_arena_e_dos_jogos(self):
        from .views_arena import brinquedos_da_arena
        from .views_jogos import maquinas_dos_jogos

        self.assertNotIn(self.kit, list(brinquedos_da_arena()))
        strike = _maquina("Strike Kids")
        _maquina("Kit Strike Kids", eh_kit=True, maquina=strike)
        self.assertEqual(maquinas_dos_jogos()["strike-kids"]["nome"], "Strike Kids")

    def test_kit_desligado_nao_aparece(self):
        self.kit.ativo = False
        self.kit.save()
        cache.clear()
        self.assertNotIn("Kit Boliche Virtual", self.html(reverse("home")))
        self.assertEqual(self.client.get(reverse("brinquedo_detalhe", args=[self.kit.pk])).status_code, 404)


class PaginaDoKitTests(Base):
    def test_o_que_vem_no_kit_e_a_maquina(self):
        html = self.html(reverse("brinquedo_detalhe", args=[self.kit.pk]))
        self.assertIn("O que vem no kit", html)
        for nome in ("Placa Zero Delay", "TV Box", "Cabo HDMI", "Barra com 5 sensores"):
            self.assertIn(nome, html)
        self.assertIn("Com o jogo Dragon Bowling", html)
        self.assertIn("fa-solid fa-tv", html)
        self.assertIn("fa-solid fa-wave-square", html)
        self.assertIn('<span class="kit-item-qtd" title="Quantidade">1×</span>', html)
        # o item que também é vendido sozinho leva à peça, com a foto (a nossa, da biblioteca)
        self.assertIn(f'href="{reverse("reposicao_detalhe", args=[self.cabo.pk])}#breadcrumb"', html)
        self.assertIn("Também vendido sozinho", html)
        self.assertIn('class="kit-item kit-item--foto"', html)
        self.assertIn("site/kits/itens/cabo-hdmi.webp", html)
        # a máquina, com o link; o caminho passa pela categoria dos kits
        self.assertIn("Para a máquina Boliche Virtual", html)
        self.assertIn(f'href="{reverse("brinquedo_detalhe", args=[self.boliche.pk])}#bread"', html)
        self.assertIn(f'href="{reverse("categoria_detalhe", args=[self.cat_kits.pk])}"', html)
        self.assertIn("Sobre este kit", html)
        self.assertIn('class="ls-kit-selo"', html)
        # a foto do kit; o 3D (e os recursos) da máquina não são dele
        self.assertIn("kit-boliche-virtual-ab12", html)
        self.assertNotIn("data-visor3d", html)
        self.assertNotIn("Contém câmera", html)

    def test_a_foto_do_item_vem_da_peca_ligada_antes_da_biblioteca(self):
        item = ComponenteKit.objects.get(kit=self.kit, nome="Cabo HDMI")
        self.assertIn("site/kits/itens/cabo-hdmi.webp", kits.foto_do_componente(item))
        ImagemPeca.objects.create(peca_reposicao=self.cabo, imagem="pecas_reposicao/cabo-hdmi-xy.webp", ordem=1)
        item = ComponenteKit.objects.select_related("peca").get(pk=item.pk)
        self.assertIn("cabo-hdmi-xy", kits.foto_do_componente(item))

    def test_a_biblioteca_so_tem_foto_do_que_existe(self):
        self.assertTrue(kits.foto_da_biblioteca("Cabo HDMI").endswith("site/kits/itens/cabo-hdmi.webp"))
        self.assertEqual(kits.foto_da_biblioteca("Item sem nome conhecido"), "")

    def test_a_pagina_da_maquina_chama_o_kit(self):
        html = self.html(reverse("brinquedo_detalhe", args=[self.boliche.pk]))
        self.assertIn("Já tem a máquina?", html)
        self.assertIn("Kit eletrônico completo", html)
        self.assertIn(f'href="{reverse("brinquedo_detalhe", args=[self.kit.pk])}#bread"', html)
        self.assertIn("Sob consulta", html[html.index('class="produto-kit"'):])
        # a página do kit não chama para ela mesma
        self.assertNotIn("Já tem a máquina?", self.html(reverse("brinquedo_detalhe", args=[self.kit.pk])))


class SemPrecoTests(Base):
    def test_sob_consulta_e_nunca_zero(self):
        pagina = self.html(reverse("brinquedo_detalhe", args=[self.kit.pk]))
        self.assertIn("Valor sob consulta", pagina)
        self.assertIn("O valor do kit sai no orçamento", pagina)
        self.assertIn("Solicitar orçamento no WhatsApp", pagina)
        self.assertNotIn('id="form-adicionar-carrinho"', pagina)
        self.assertNotIn('"offers"', pagina)  # sem preço não há oferta para o Google
        for url in (reverse("brinquedo_detalhe", args=[self.kit.pk]), reverse("home"), reverse("loja"),
                    reverse("brinquedos")):
            with self.subTest(url=url):
                self.assertNotIn("R$ 0,00", self.html(url))

    def test_o_carrinho_recusa_o_kit_sem_preco(self):
        self.assertEqual(
            self.client.get(reverse("previa_do_carrinho", args=["brinquedo", self.kit.pk]), **XHR).status_code, 404)
        self.client.force_login(_cliente())
        resposta = self.client.post(reverse("adicionar_ao_carrinho", args=["brinquedo", self.kit.pk]),
                                    {"quantidade": 1}, **XHR)
        self.assertEqual(resposta.status_code, 404)
        self.assertFalse(ItemCarrinho.objects.exists())


@override_settings(MP_ACCESS_TOKEN="TEST-ACCESS-TOKEN")
class ComPrecoTests(Base):
    def setUp(self):
        super().setUp()
        self.kit.valor_brinquedo = Decimal("1890.00")
        self.kit.save()

    def test_a_pagina_tem_o_carrinho(self):
        html = self.html(reverse("brinquedo_detalhe", args=[self.kit.pk]))
        self.assertIn('id="form-adicionar-carrinho"', html)
        self.assertIn(reverse("adicionar_ao_carrinho", args=["brinquedo", self.kit.pk]), html)
        self.assertIn("1.890,00", html)
        self.assertNotIn("Valor sob consulta", html)
        # na home, "À venda"; na página da máquina, o preço no chamado do kit
        self.assertIn("1.890,00", self.html(reverse("brinquedo_detalhe", args=[self.boliche.pk])))

    def test_a_previa_diz_que_e_kit(self):
        item = self.client.get(reverse("previa_do_carrinho", args=["brinquedo", self.kit.pk]), **XHR).json()["item"]
        self.assertEqual(item["rotulo"], "Kit eletrônico")
        self.assertEqual(item["preco_unitario"], "1890.00")

    @mock.patch("core.notificacoes.enviar_boleto")
    @mock.patch("core.views.mercadopago.SDK")
    def test_vai_ao_carrinho_e_passa_no_checkout_como_produto(self, sdk_class, _email):
        self.client.force_login(_cliente())
        dados = self.client.post(reverse("adicionar_ao_carrinho", args=["brinquedo", self.kit.pk]),
                                 {"quantidade": 2}, **XHR).json()
        self.assertTrue(dados["sucesso"])
        self.assertEqual(dados["total_carrinho"], "3780.00")
        linha = ItemCarrinho.objects.get()
        self.assertEqual(linha.content_type, ContentType.objects.get_for_model(Brinquedos))

        # o carrinho mostra o kit como kit, com o link da página dele
        carrinho_html = self.html(reverse("carrinho"))
        self.assertIn("Kit eletrônico", carrinho_html)
        self.assertIn(reverse("brinquedo_detalhe", args=[self.kit.pk]), carrinho_html)

        carrinho = Carrinho.objects.get(pk=linha.carrinho_id)
        carrinho.tipo_envio = "retirada"
        carrinho.save()
        criar = sdk_class.return_value.payment.return_value.create
        criar.return_value = {
            "status": 201,
            "response": {
                "id": 777, "status": "pending", "payment_type_id": "ticket", "transaction_amount": 3780.0,
                "date_of_expiration": "2026-11-21T23:59:59.000-03:00",
                "transaction_details": {
                    "external_resource_url": "https://www.mercadopago.com.br/payments/777/ticket",
                    "digitable_line": "23793381286008200000000000000000000000000000000",
                },
            },
        }
        resposta = self.client.post(
            reverse("gerar_boleto"),
            data=json.dumps({
                "nome": "Bia Souza", "documento": "529.982.247-25", "cep": "01310-100", "rua": "Av. Paulista",
                "numero": "1000", "bairro": "Bela Vista", "cidade": "São Paulo", "uf": "SP",
                "carrinho_id": carrinho.pk,
            }),
            content_type="application/json", **XHR,
        )
        self.assertEqual(resposta.status_code, 200, resposta.content[:300])
        self.assertEqual(criar.call_args[0][0]["transaction_amount"], 3780.0)
        pedido = Pedido.objects.get(pk=resposta.json()["pedido_id"])
        item = ItemPedido.objects.get(pedido=pedido)
        self.assertEqual((item.object_id, item.quantidade), (self.kit.pk, 2))
        self.assertEqual(item.content_type.model, "brinquedos")
        self.assertEqual(item.nome_item, "Kit Boliche Virtual")


class EnderecosAntigosTests(Base):
    def test_kits_leva_a_categoria(self):
        resposta = self.client.get("/kits/")
        self.assertRedirects(resposta, reverse("categoria_detalhe", args=[self.cat_kits.pk]), status_code=301,
                             fetch_redirect_response=False)
        self.cat_kits.delete()
        self.assertRedirects(self.client.get("/kits/"), reverse("brinquedos"), status_code=301,
                             fetch_redirect_response=False)

    def test_o_numero_do_kit_antigo_leva_ao_produto(self):
        destino = reverse("brinquedo_detalhe", args=[self.kit.pk])
        for antigo in ("/kits/24/", "/pecas/24/"):
            with self.subTest(antigo=antigo):
                self.assertRedirects(self.client.get(antigo), destino, status_code=301,
                                     fetch_redirect_response=False)
        # o número de uma peça avulsa leva à peça, como antes; o que não existe, 404
        self.assertRedirects(self.client.get(f"/kits/{self.motor.pk}/"),
                             reverse("reposicao_detalhe", args=[self.motor.pk]), status_code=301,
                             fetch_redirect_response=False)
        self.assertEqual(self.client.get("/kits/999999/").status_code, 404)
        self.assertEqual(self.client.get("/pecas/999999/").status_code, 404)


class SitemapEMenuTests(Base):
    def test_sitemap_tem_o_kit_como_produto_e_a_categoria(self):
        xml = self.html("/sitemap.xml")
        self.assertIn(f"<loc>https://www.lazersport.com.br/brinquedo/{self.kit.pk}/</loc>", xml)
        self.assertIn(f"<loc>https://www.lazersport.com.br/categoria/{self.cat_kits.pk}/</loc>", xml)
        self.assertNotIn("/kits/", xml)
        self.assertIn(f"/pecas/{self.motor.pk}/</loc>", xml)

    def test_o_menu_leva_a_categoria_dos_kits(self):
        url = reverse("categoria_detalhe", args=[self.cat_kits.pk])
        html = self.html(reverse("pecas_reposicao"))
        topo = html[html.index('id="topo-servicos"'):]
        topo = topo[:topo.index("</div>")]
        self.assertIn(f'href="{url}"', topo)
        self.assertIn("Kits eletrônicos", topo)
        celular = html[html.index('class="ls-mobile-nav-list"'):]
        celular = celular[:celular.index("</div>")]
        self.assertIn(f'href="{url}"', celular)

    def test_sem_kit_no_ar_o_atalho_sai(self):
        self.kit.ativo = False
        self.kit.save()
        cache.clear()
        html = self.html(reverse("pecas_reposicao"))
        topo = html[html.index('id="topo-servicos"'):]
        self.assertNotIn("Kits eletrônicos", topo[:topo.index("</div>")])

    def test_o_icone_do_item(self):
        casos = {
            "TV Box": "fa-tv", "Barra com 5 sensores de precisão": "fa-wave-square", "Câmera": "fa-camera",
            "Webcam": "fa-camera", "Arma personalizada": "fa-crosshairs", "Placa Zero Delay": "fa-microchip",
            "Chicote": "fa-network-wired", "Cabo HDMI": "fa-plug", "Fonte": "fa-bolt", "Manual": "fa-puzzle-piece",
        }
        for nome, icone in casos.items():
            with self.subTest(nome=nome):
                self.assertEqual(kits.icone_do_componente(nome), icone)


@override_settings(ALLOWED_HOSTS=[INTERNO, "testserver"])
class PainelTests(Base):
    def setUp(self):
        super().setUp()
        self.strike = _maquina("Strike Kids")
        self.admin = User.objects.create_superuser("gestor", "gestor@lazersport.com.br", "senha-forte-123")
        self.client.force_login(self.admin)
        self.url = reverse("brinquedos_admin", urlconf="sistema_interno.urls")
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        disco = FileSystemStorage(location=pasta.name)
        for campo in (Brinquedos._meta.get_field("imagem_brinquedo"), ImagemBrinquedo._meta.get_field("imagem")):
            troca = mock.patch.object(campo, "storage", disco)
            troca.start()
            self.addCleanup(troca.stop)

    def salvar(self, **dados):
        base = {
            "action": "save", "resposta": "json", "nome_brinquedo": "Kit Strike Kids",
            "descricao": "A eletrônica do Strike Kids.", "avaliacao": "4,8", "voltz": "220V",
        }
        base.update(dados)
        return self.client.post(self.url, base, HTTP_HOST=INTERNO, **XHR)

    def tela(self, **params):
        resposta = self.client.get(self.url, params, HTTP_HOST=INTERNO)
        self.assertEqual(resposta.status_code, 200)
        return resposta.content.decode()

    def test_a_tela_tem_o_editor_do_kit_sem_select(self):
        html = self.tela()
        editor = html[html.index("data-kit>"):html.index("data-kit-json>")]
        self.assertNotIn("<select", editor)
        self.assertIn('id="toyKit" name="eh_kit"', editor)
        self.assertIn('type="radio" name="maquina" value="%d"' % self.strike.pk, editor)
        self.assertIn("data-kit-busca", editor)
        # um kit não é máquina de outro kit
        self.assertNotIn('name="maquina" value="%d"' % self.kit.pk, editor)
        # o selo "Kit" e a máquina na lista; o filtro do tipo
        self.assertIn("bq-selo--kit", html)
        self.assertIn("Para Boliche Virtual · 4 itens", html)
        self.assertIn("Kits eletrônicos</span> <b>1</b>", html)
        dados = json.loads(re.search(r'<script id="toysAdminData" type="application/json">(.*?)</script>', html,
                                     flags=re.S).group(1))
        kit = next(b for b in dados if b["id"] == self.kit.pk)
        self.assertTrue(kit["eh_kit"])
        self.assertEqual(kit["maquina_id"], self.boliche.pk)
        self.assertEqual([c["nome"] for c in kit["componentes"]][:2], ["Placa Zero Delay", "TV Box"])
        self.assertEqual(kit["componentes"][2]["peca"], self.cabo.pk)
        self.assertIn('id="toysAdminPecas"', html)

    def test_salva_o_kit_novo_com_a_maquina_e_os_itens(self):
        itens = [
            {"nome": "TV Box", "detalhe": "Com o jogo Strike Kids", "quantidade": "1", "peca": ""},
            {"nome": "Cabo HDMI", "detalhe": "", "quantidade": "2", "peca": str(self.cabo.pk)},
            {"nome": "", "detalhe": "", "quantidade": "1", "peca": ""},  # linha em branco não vira item
            {"nome": "Câmera", "detalhe": "", "quantidade": "1", "peca": ""},
        ]
        resposta = self.salvar(imagem_perfil=_foto(), eh_kit="1", maquina=str(self.strike.pk),
                               exibir_na_loja="on", categorias_brinquedos=[self.cat_kits.pk],
                               componentes_json=json.dumps(itens))
        self.assertEqual(resposta.status_code, 200, resposta.content)
        kit = Brinquedos.objects.get(pk=resposta.json()["id"])
        self.assertTrue(kit.eh_kit)
        self.assertEqual(kit.maquina, self.strike)
        self.assertIsNone(kit.valor_brinquedo)
        self.assertEqual(
            [(c.ordem, c.nome, c.quantidade, c.peca_id) for c in kit.componentes_kit.all()],
            [(1, "TV Box", 1, None), (2, "Cabo HDMI", 2, self.cabo.pk), (3, "Câmera", 1, None)],
        )
        self.assertEqual(kit.componentes_kit.first().detalhe, "Com o jogo Strike Kids")
        # e já está no site, junto com as máquinas
        cache.clear()
        self.assertIn("Kit Strike Kids", self.html(reverse("categoria_detalhe", args=[self.cat_kits.pk])))

    def test_editar_reordena_e_troca_a_maquina(self):
        itens = [{"nome": c.nome, "detalhe": c.detalhe, "quantidade": c.quantidade, "peca": c.peca_id or ""}
                 for c in self.kit.componentes_kit.all()]
        itens.reverse()
        resposta = self.salvar(id=self.kit.pk, nome_brinquedo="Kit Boliche Virtual", eh_kit="1",
                               maquina=str(self.strike.pk), valor_brinquedo="1.890,00", exibir_na_loja="on",
                               componentes_json=json.dumps(itens))
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.kit.refresh_from_db()
        self.assertEqual(self.kit.maquina, self.strike)
        self.assertEqual(self.kit.valor_brinquedo, Decimal("1890.00"))
        self.assertEqual([c.nome for c in self.kit.componentes_kit.all()],
                         ["Barra com 5 sensores", "Cabo HDMI", "TV Box", "Placa Zero Delay"])

    def test_sem_a_marca_a_maquina_sai_e_os_itens_ficam(self):
        # a chave desligada não manda a lista: os itens ficam guardados
        resposta = self.salvar(id=self.kit.pk, nome_brinquedo="Kit Boliche Virtual", maquina=str(self.boliche.pk))
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.kit.refresh_from_db()
        self.assertFalse(self.kit.eh_kit)
        self.assertIsNone(self.kit.maquina)
        self.assertEqual(self.kit.componentes_kit.count(), 4)

    def test_erros_do_kit_voltam_com_a_frase_e_nada_muda(self):
        casos = (
            ({"componentes_json": "[]"}, "pelo menos um item"),
            ({"componentes_json": json.dumps([{"nome": "TV Box", "quantidade": "0"}])}, "de 1 a 99"),
            ({"componentes_json": json.dumps([{"nome": "TV Box", "peca": "999999"}])}, "não existe mais"),
            ({"componentes_json": json.dumps([{"nome": "", "detalhe": "sem nome"}])}, "nome do item"),
            ({"componentes_json": "isto não é json"}, "incompleta"),
            ({"maquina": "999999", "componentes_json": json.dumps([{"nome": "TV Box"}])}, "não existe mais"),
            # um kit não é a máquina de outro kit, nem dele mesmo
            ({"maquina": str(self.kit.pk), "componentes_json": json.dumps([{"nome": "TV Box"}])}, "não existe mais"),
        )
        for dados, frase in casos:
            with self.subTest(frase=frase, dados=dados):
                resposta = self.salvar(id=self.kit.pk, nome_brinquedo="Kit Mudado", eh_kit="1", **dados)
                self.assertEqual(resposta.status_code, 400)
                self.assertIn(frase, resposta.json()["msg"])
        self.kit.refresh_from_db()
        self.assertEqual((self.kit.nome_brinquedo, self.kit.maquina), ("Kit Boliche Virtual", self.boliche))
        self.assertEqual(self.kit.componentes_kit.count(), 4)

    def test_filtro_dos_kits_e_das_maquinas(self):
        so_kits = self.tela(tipo="kits")
        self.assertIn("Kit Boliche Virtual</h3>", so_kits)
        self.assertNotIn("Strike Kids</h3>", so_kits)
        maquinas = self.tela(tipo="maquinas")
        self.assertNotIn("Kit Boliche Virtual</h3>", maquinas)
        self.assertIn("Strike Kids</h3>", maquinas)

    def test_a_tela_de_pecas_nao_tem_mais_o_kit(self):
        html = self.client.get(reverse("pecas_admin", urlconf="sistema_interno.urls"), HTTP_HOST=INTERNO)
        self.assertEqual(html.status_code, 200)
        html = html.content.decode()
        self.assertNotIn("kitEditor", html)
        self.assertNotIn('name="eh_kit"', html)
        self.assertNotIn("Kit Boliche Virtual", html)


class ComandoTests(TestCase):
    """`python manage.py kits_eletronicos`: os kits iniciais, como produtos."""

    def setUp(self):
        cache.clear()
        self.boliche = _maquina("Boliche Virtual")
        # "Strike Kids Boliche" vem antes e não pode ser confundido com o Strike Kids
        self.parecido = _maquina("Strike Kids Boliche")
        self.strike = _maquina("Strike Kids", avaliacao=Decimal("4.9"), voltz="Bivolt")
        self.cabo = PecasReposicao.objects.create(nome="Cabo HDMI", descricao_peca="Cabo.",
                                                  preco_venda=Decimal("29.90"))

    def test_cria_os_tres_kits_como_produtos_e_nao_duplica(self):
        call_command("kits_eletronicos", stdout=StringIO())
        kits_criados = Brinquedos.objects.filter(eh_kit=True).order_by("nome_brinquedo")
        self.assertEqual([k.nome_brinquedo for k in kits_criados],
                         ["Kit Boliche Virtual", "Kit Lazer Shot", "Kit Strike Kids"])
        strike = Brinquedos.objects.get(nome_brinquedo="Kit Strike Kids")
        self.assertEqual((strike.maquina, strike.voltz, strike.avaliacao), (self.strike, "Bivolt", Decimal("4.90")))
        self.assertIsNone(strike.valor_brinquedo)
        self.assertTrue(strike.exibir_na_loja and strike.adesivo_padrao_id)
        self.assertIn("Kits eletrônicos", [c.nome_categoria for c in strike.categorias_brinquedos.all()])
        self.assertEqual(strike.componentes_kit.count(), 7)
        self.assertEqual(strike.componentes_kit.get(nome="Cabo HDMI").peca, self.cabo)
        self.assertIsNone(Brinquedos.objects.get(nome_brinquedo="Kit Lazer Shot").maquina)  # sem a máquina
        # rodar de novo não duplica nem mexe no que o dono mudou
        strike.valor_brinquedo = Decimal("990")
        strike.save()
        resultado = kits.criar_kits_iniciais(avisar=lambda *_: None)
        self.assertEqual((resultado["criados"], len(resultado["existentes"])), ([], 3))
        self.assertEqual(Brinquedos.objects.filter(eh_kit=True).count(), 3)
        self.assertEqual(ComponenteKit.objects.count(), 21)
        self.assertEqual(CategoriasBrinquedos.objects.filter(nome_categoria="Kits eletrônicos").count(), 1)
        strike.refresh_from_db()
        self.assertEqual(strike.valor_brinquedo, Decimal("990.00"))

    def test_banco_sem_maquina_nenhuma_nao_ganha_kit(self):
        Brinquedos.objects.all().delete()
        self.assertEqual(kits.criar_kits_iniciais(avisar=lambda *_: None)["criados"], [])
        self.assertFalse(Brinquedos.objects.exists())

    def test_a_foto_sobe_com_nome_curto_so_no_kit_sem_foto(self):
        from django.core.files.storage import InMemoryStorage

        kits.criar_kits_iniciais(avisar=lambda *_: None)
        memoria = InMemoryStorage()
        with mock.patch.object(Brinquedos._meta.get_field("imagem_brinquedo"), "storage", memoria):
            resultado = kits.subir_fotos(avisar=lambda *_: None)
            de_novo = kits.subir_fotos(avisar=lambda *_: None)
        todos = ["Kit Boliche Virtual", "Kit Strike Kids", "Kit Lazer Shot"]
        self.assertEqual(resultado["subidas"], todos)
        self.assertEqual(de_novo["ja_tinham"], todos)
        for nome, chave in zip(todos, ("kit-boliche-virtual", "kit-strike-kids", "kit-lazer-shot")):
            kit = Brinquedos.objects.get(nome_brinquedo=nome)
            self.assertTrue(kit.imagem_brinquedo.name.startswith(f"imagens_brinquedos/{chave}-"))
            self.assertLessEqual(len(kit.imagem_brinquedo.name), 60)
            frente = kit.imagens_brinquedo.get(tipo="perfil")
            self.assertEqual((frente.imagem.name, frente.fundo), (kit.imagem_brinquedo.name, "com"))

    def test_as_artes_sao_nossas_e_quadradas(self):
        """O dono: "essa image é de outro site". Só as nossas artes, 1200 x 1200."""
        pasta = Path(kits.arquivo_da_foto("x")).parent
        self.assertEqual(
            sorted(p.name for p in pasta.glob("*.webp")),
            ["kit-boliche-virtual.webp", "kit-lazer-shot.webp", "kit-strike-kids.webp"],
        )
        for arte in pasta.glob("*.webp"):
            with Image.open(arte) as imagem:
                self.assertEqual(imagem.size, (1200, 1200), arte.name)
        for nome, _maquina, _chave, descricao, itens in kits.KITS_INICIAIS:
            texto = descricao + " ".join(f"{a} {b}" for a, b, _ in itens)
            self.assertNotIn("Bichinhos", texto, nome)


class MigracaoDosKitsTests(TransactionTestCase):
    """A 0212 com o banco como estava em produção: as peças-kit, com foto, itens, curtidas e um pedido."""

    FOTO = "pecas_reposicao/kit-strike-kids-a1b2c3d4e5_x9y8z7"

    def _apps(self, executor, no):
        folhas = [n for n in executor.loader.graph.leaf_nodes() if n[0] != "core"] + [no]
        return executor.loader.project_state(folhas).apps

    def _ate(self, no):
        executor = MigrationExecutor(connection)
        executor.migrate([no])
        executor.loader.build_graph()
        return self._apps(executor, no)

    def _ate_o_fim(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def tearDown(self):
        self._ate_o_fim()
        cache.clear()
        super().tearDown()

    def test_a_peca_kit_vira_produto(self):
        apps = self._ate(ANTES)
        B = apps.get_model("core", "Brinquedos")
        Cat = apps.get_model("core", "CategoriasBrinquedos")
        Peca = apps.get_model("core", "PecasReposicao")
        Img = apps.get_model("core", "ImagemPeca")
        Comp = apps.get_model("core", "ComponenteKit")
        Fav = apps.get_model("core", "Favorito")
        Pedido_ = apps.get_model("core", "Pedido")
        ItemPedido_ = apps.get_model("core", "ItemPedido")
        CT = apps.get_model("contenttypes", "ContentType")
        U = apps.get_model("auth", "User")

        eletronicos = Cat.objects.create(nome_categoria="Eletrônicos", imagem_categoria="categorias/eletronicos.webp")
        strike = B.objects.create(nome_brinquedo="Strike Kids", descricao="x", avaliacao=Decimal("4.9"),
                                  voltz="220V", imagem_brinquedo="imagens_brinquedos/strike.webp")
        strike.categorias_brinquedos.add(eletronicos)
        cabo = Peca.objects.create(nome="Cabo HDMI", descricao_peca="Cabo.", preco_venda=Decimal("29.90"))
        kit = Peca.objects.create(nome="Kit Strike Kids", descricao_peca="A eletrônica do Strike Kids.",
                                  eh_kit=True, maquina=strike, ajuste_curtidas=3, parcelas_sem_juros=10)
        Img.objects.create(peca_reposicao=kit, imagem=self.FOTO, recorte_de=self.FOTO, ordem=1)
        for ordem, (nome, peca) in enumerate((("TV Box", None), ("Cabo HDMI", cabo), ("Fonte", None)), start=1):
            Comp.objects.create(kit=kit, nome=nome, ordem=ordem, peca=peca)
        usuario = U.objects.create(username="curtiu-o-kit")
        Fav.objects.create(usuario=usuario, peca=kit, tipo="curtida")
        # o segundo kit tem um pedido antigo: a peça fica, desligada
        lazer = Peca.objects.create(nome="Kit Lazer Shot", descricao_peca="A eletrônica do Lazer Shot.",
                                    eh_kit=True, preco_venda=Decimal("1500.00"))
        Comp.objects.create(kit=lazer, nome="Arma personalizada", ordem=1)
        pedido = Pedido_.objects.create()
        ItemPedido_.objects.create(
            pedido=pedido, content_type=CT.objects.get(app_label="core", model="pecasreposicao"),
            object_id=lazer.pk, nome_item="Kit Lazer Shot", tipo_item="pecas", preco_unitario=Decimal("1500.00"),
            quantidade=1, subtotal=Decimal("1500.00"))
        # o item solto, de uma peça que deixou de ser kit
        Comp.objects.create(kit=cabo, nome="Sobra", ordem=1)
        numeros = (kit.pk, lazer.pk, cabo.pk)

        # a 0212, e de novo (nada duplica), e a 0213
        apps212 = self._ate(CONVERTE)
        avisos = []
        migracao_0212.converter(apps212, None, avisar=avisos.append)
        self.assertEqual(apps212.get_model("core", "Brinquedos").objects.filter(eh_kit=True).count(), 2)
        self._ate_o_fim()

        produto = Brinquedos.objects.get(nome_brinquedo="Kit Strike Kids")
        self.assertTrue(produto.eh_kit and produto.ativo and produto.exibir_na_loja)
        self.assertEqual((produto.maquina_id, produto.id_kit_antigo), (strike.pk, numeros[0]))
        self.assertEqual((produto.voltz, produto.avaliacao, produto.parcelas_sem_juros, produto.ajuste_curtidas),
                         ("220V", Decimal("4.90"), 10, 3))
        self.assertIsNone(produto.valor_brinquedo)
        # a MESMA foto do Cloudinary: a capa e a frente da galeria, no adesivo padrão
        self.assertEqual(produto.imagem_brinquedo.name, self.FOTO)
        frente = ImagemBrinquedo.objects.get(brinquedo=produto)
        self.assertEqual((frente.imagem.name, frente.tipo, frente.fundo, frente.variante_id),
                         (self.FOTO, "perfil", "com", produto.adesivo_padrao_id))
        # as categorias: a dos kits (criada, com a foto do kit de capa) e a da máquina
        categorias = {c.nome_categoria: c for c in produto.categorias_brinquedos.all()}
        self.assertEqual(set(categorias), {"Kits eletrônicos", "Eletrônicos"})
        self.assertEqual(categorias["Kits eletrônicos"].imagem_categoria.name, self.FOTO)
        # os itens, na ordem, com a peça avulsa
        self.assertEqual([(c.nome, c.peca_id) for c in produto.componentes_kit.all()],
                         [("TV Box", None), ("Cabo HDMI", cabo.pk), ("Fonte", None)])
        # a curtida passou para o produto; a peça sem referência saiu
        self.assertEqual(Favorito.objects.get().brinquedo, produto)
        self.assertFalse(PecasReposicao.objects.filter(pk=numeros[0]).exists())
        # o kit com pedido: o produto nasce (com o preço) e a peça fica, desligada
        outro = Brinquedos.objects.get(nome_brinquedo="Kit Lazer Shot")
        self.assertEqual((outro.valor_brinquedo, outro.maquina, outro.id_kit_antigo),
                         (Decimal("1500.00"), None, numeros[1]))
        self.assertFalse(PecasReposicao.objects.get(pk=numeros[1]).ativo)
        self.assertEqual(ItemPedido.objects.get().object_id, numeros[1])
        # o item solto saiu; a peça avulsa continua
        self.assertFalse(ComponenteKit.objects.filter(nome="Sobra").exists())
        self.assertTrue(PecasReposicao.objects.get(pk=numeros[2]).ativo)
        self.assertEqual(Brinquedos.objects.filter(eh_kit=True).count(), 2)
        # os endereços antigos levam ao produto
        self.assertRedirects(self.client.get(f"/kits/{numeros[0]}/"), reverse("brinquedo_detalhe", args=[produto.pk]),
                             status_code=301, fetch_redirect_response=False)
        self.assertRedirects(self.client.get(f"/pecas/{numeros[1]}/"), reverse("brinquedo_detalhe", args=[outro.pk]),
                             status_code=301, fetch_redirect_response=False)

    def test_banco_sem_kit_nao_muda_nada(self):
        apps = self._ate(CONVERTE)
        self.assertEqual(migracao_0212.converter(apps, None, avisar=lambda *_: None), [])
        self.assertFalse(apps.get_model("core", "CategoriasBrinquedos").objects.exists())


class CapasNovasDosKitsTests(Base):
    """A migração 0214: a arte nova (TV em pé com a tela do jogo) vira a capa do kit."""

    def migracao(self):
        return importlib.import_module("core.migrations.0214_capas_novas_dos_kits")

    def test_fora_do_render_nada_sobe(self):
        from django.apps import apps as django_apps

        resultado = self.migracao().trocar(django_apps, avisar=lambda *_: None)
        self.assertTrue(resultado.get("fora_do_render"))
        self.kit.refresh_from_db()
        self.assertEqual(self.kit.imagem_brinquedo.name, "pecas_reposicao/kit-boliche-virtual-ab12")

    def test_troca_a_capa_a_frente_e_a_categoria_uma_vez_so(self):
        from django.apps import apps as django_apps
        from django.core.files.storage import InMemoryStorage

        from .models import ImagemBrinquedo

        mig = self.migracao()
        campo = ImagemBrinquedo._meta.get_field("imagem")
        with mock.patch.object(campo, "storage", InMemoryStorage()):
            primeira = mig.trocar(django_apps, avisar=lambda *_: None, forcar=True)
            segunda = mig.trocar(django_apps, avisar=lambda *_: None, forcar=True)
        self.assertEqual(primeira["trocados"], ["Kit Boliche Virtual"])
        self.assertEqual(segunda["ja_estavam"], ["Kit Boliche Virtual"])
        self.kit.refresh_from_db()
        capa = self.kit.imagem_brinquedo.name
        marca = mig._assinatura(mig.PASTA / "kit-boliche-virtual.webp")
        self.assertIn(marca, capa)
        self.assertLessEqual(len(capa), 100)
        frente = ImagemBrinquedo.objects.get(brinquedo=self.kit, tipo="perfil")
        self.assertEqual(frente.imagem.name, capa)
        self.assertEqual(frente.fundo, "com")
        self.cat_kits.refresh_from_db()
        self.assertEqual(self.cat_kits.imagem_categoria.name, capa)

    def test_a_arte_deixa_o_topo_e_o_pe_livres_para_os_selos_do_card(self):
        """Nada de texto sob o selo "KIT", os botões e o "Sob consulta" do card (LEIA-ME 107)."""
        for chave in ("kit-boliche-virtual", "kit-strike-kids", "kit-lazer-shot"):
            with Image.open(Path(kits.arquivo_da_foto(chave))) as arte:
                arte = arte.convert("L").resize((1200, 1200))
                # o canto do "Sob consulta" (pé, à esquerda): só o fundo escuro, sem letra clara
                faixa = arte.crop((0, 1032, 672, 1164))
                self.assertLess(max(faixa.getdata()), 150, chave)
