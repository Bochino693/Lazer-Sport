"""O kit eletrônico (LEIA-ME seção 105).

O dono: "precisamos agora também do chamado kit, ele deve ter espaço entre os
demais produtos [...] os componentes eletrônicos sem a máquina para troca ou
semi instalação [...] para o cara instalar toda parte elétrica na máquina caso
ele só tenha a máquina".

O que estes testes protegem:

  * o kit é uma peça marcada: fica FORA de /pecas-reposicao/ (e da seção de
    peças da home) e DENTRO de /kits/, da faixa da home, da loja e da busca;
  * a página do kit lista os itens (ícone e quantidade, o item ligado à peça
    avulsa leva a ela) e a máquina; /pecas/<kit>/ leva a /kits/<kit>/;
  * sem preço: "Sob consulta" e o WhatsApp, nunca R$ 0,00, e o carrinho
    recusa; com preço, vai ao carrinho como peça e passa no checkout;
  * a página da máquina chama para o kit dela;
  * a migração de dados é idempotente, liga as máquinas pelo nome inteiro e
    o Cabo HDMI à peça, e não sobe foto fora do Render; a arte do kit não é
    estragada pelo recorte automático das peças;
  * o painel salva a marca, a máquina (chips de rádio, sem <select>) e os
    itens, na ordem da tela;
  * o sitemap e o menu.
"""

import json
import re
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.apps import apps as django_apps
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from . import kits
from .models import (
    Brinquedos,
    Carrinho,
    ComponenteKit,
    ImagemPeca,
    ItemCarrinho,
    ItemPedido,
    PecasReposicao,
    Pedido,
)

XHR = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
INTERNO = "interno.testserver"


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


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.boliche = _maquina("Boliche Virtual")
        self.cabo = PecasReposicao.objects.create(
            nome="Cabo HDMI", descricao_peca="Cabo HDMI de 1,5 m.", preco_venda=Decimal("29.90"),
        )
        self.motor = PecasReposicao.objects.create(
            nome="Motor 1/4 CV", descricao_peca="Motor do carrossel.", preco_venda=Decimal("450"),
        )
        self.kit = PecasReposicao.objects.create(
            nome="Kit Boliche Virtual", descricao_peca="A parte eletrônica completa do Boliche Virtual.",
            eh_kit=True, maquina=self.boliche,
        )
        for ordem, (nome, detalhe, peca) in enumerate((
            ("Placa Zero Delay", "", None),
            ("TV Box", "Com o jogo Dragon Bowling", None),
            ("Cabo HDMI", "", self.cabo),
            ("Barra com 5 sensores", "Leem cada jogada da bola na pista", None),
        ), start=1):
            ComponenteKit.objects.create(kit=self.kit, nome=nome, detalhe=detalhe, ordem=ordem, peca=peca)

    def tearDown(self):
        cache.clear()


class VitrineTests(Base):
    def test_kit_fora_das_pecas_e_dentro_de_kits(self):
        pecas = self.client.get(reverse("pecas_reposicao")).content.decode()
        self.assertIn("Motor 1/4 CV", pecas)
        self.assertNotIn("Kit Boliche Virtual", pecas)

        resposta = self.client.get(reverse("kits"))
        self.assertEqual(resposta.status_code, 200)
        html = resposta.content.decode()
        self.assertIn("Kit Boliche Virtual", html)
        self.assertNotIn("Motor 1/4 CV", html)
        self.assertIn("Monte sua própria", html)
        # o card do kit: o selo, a máquina e a lista curta
        self.assertIn("pc-selo--kit", html)
        self.assertIn("Para Boliche Virtual", html)
        self.assertIn("4 itens: Placa Zero Delay, TV Box, Cabo HDMI…", html)
        self.assertIn(f'href="{reverse("kit_detalhe", args=[self.kit.pk])}#breadcrumb"', html)

    def test_kit_desligado_ou_de_manutencao_nao_aparece(self):
        self.kit.ativo = False
        self.kit.save()
        self.assertNotIn("Kit Boliche Virtual", self.client.get(reverse("kits")).content.decode())
        self.assertEqual(self.client.get(reverse("kit_detalhe", args=[self.kit.pk])).status_code, 404)

    def test_pagina_do_kit_lista_os_itens_e_a_maquina(self):
        resposta = self.client.get(reverse("kit_detalhe", args=[self.kit.pk]))
        self.assertEqual(resposta.status_code, 200)
        html = resposta.content.decode()
        self.assertIn("O que vem no kit", html)
        for nome in ("Placa Zero Delay", "TV Box", "Cabo HDMI", "Barra com 5 sensores"):
            self.assertIn(nome, html)
        self.assertIn("Com o jogo Dragon Bowling", html)
        self.assertIn("fa-solid fa-tv", html)
        self.assertIn("fa-solid fa-wave-square", html)
        self.assertIn('<span class="kit-item-qtd" title="Quantidade">1×</span>', html)
        # o item que também é vendido sozinho leva à peça
        self.assertIn(f'href="{reverse("reposicao_detalhe", args=[self.cabo.pk])}#breadcrumb"', html)
        self.assertIn("Também vendido sozinho", html)
        # a máquina, com o link
        self.assertIn("Para a máquina Boliche Virtual", html)
        self.assertIn(f'href="{reverse("brinquedo_detalhe", args=[self.boliche.pk])}#bread"', html)
        # o caminho volta para os kits
        self.assertIn(f'href="{reverse("kits")}"', html)
        # sem foto própria, a foto da máquina com a faixa do kit (nunca quadro vazio)
        self.assertIn("boliche-virtual", html)
        self.assertIn("peca-faixa-kit", html)
        self.assertNotIn("Imagem em atualização", html)
        # o item com foto mostra a foto (o Cabo HDMI: a nossa); o sem foto, o ícone
        self.assertIn('class="kit-item kit-item--foto"', html)
        self.assertIn("site/kits/itens/cabo-hdmi.webp", html)

    def test_a_foto_do_item_vem_da_peca_ligada_antes_da_biblioteca(self):
        item = ComponenteKit.objects.get(kit=self.kit, nome="Cabo HDMI")
        self.assertIn("site/kits/itens/cabo-hdmi.webp", kits.foto_do_componente(item))
        ImagemPeca.objects.create(peca_reposicao=self.cabo, imagem="pecas_reposicao/cabo-hdmi-xy.webp", ordem=1)
        item = ComponenteKit.objects.select_related("peca").get(pk=item.pk)
        self.assertIn("cabo-hdmi-xy", kits.foto_do_componente(item))

    def test_a_biblioteca_so_tem_foto_do_que_existe(self):
        self.assertTrue(kits.foto_da_biblioteca("Cabo HDMI").endswith("site/kits/itens/cabo-hdmi.webp"))
        # sem arquivo na biblioteca: "" (a página mostra o ícone)
        self.assertEqual(kits.foto_da_biblioteca("Placa Zero Delay"), "")
        self.assertEqual(kits.foto_da_biblioteca("Item sem nome conhecido"), "")

    def test_endereco_de_peca_leva_ao_kit_e_o_contrario(self):
        resposta = self.client.get(reverse("reposicao_detalhe", args=[self.kit.pk]))
        self.assertRedirects(resposta, reverse("kit_detalhe", args=[self.kit.pk]), status_code=301,
                             fetch_redirect_response=False)
        resposta = self.client.get(reverse("kit_detalhe", args=[self.motor.pk]))
        self.assertRedirects(resposta, reverse("reposicao_detalhe", args=[self.motor.pk]), status_code=301,
                             fetch_redirect_response=False)

    def test_kit_com_foto_propria_nao_mostra_a_maquina(self):
        ImagemPeca.objects.create(peca_reposicao=self.kit, imagem="pecas_reposicao/kit-boliche-virtual-ab12.webp",
                                  ordem=1)
        html = self.client.get(reverse("kit_detalhe", args=[self.kit.pk])).content.decode()
        self.assertIn("kit-boliche-virtual-ab12", html)
        self.assertNotIn("peca-faixa-kit", html)

    def test_home_loja_busca_e_pagina_da_maquina(self):
        home = self.client.get(reverse("home")).content.decode()
        self.assertIn('id="kits-section"', home)
        self.assertIn("monte sua própria máquina", home)
        secao_pecas = home[home.index('id="pecas-section"'):] if 'id="pecas-section"' in home else ""
        self.assertNotIn("Kit Boliche Virtual", secao_pecas[:secao_pecas.find("</section>")])

        loja = self.client.get(reverse("loja")).content.decode()
        self.assertIn('data-tipo="kit"', loja)
        self.assertIn("Kits eletrônicos", loja)

        busca = self.client.get(reverse("search"), {"q": "kit boliche"}).content.decode()
        self.assertIn("Kit Boliche Virtual", busca)
        self.assertIn(reverse("kit_detalhe", args=[self.kit.pk]), busca)
        # e pelos itens
        self.assertIn("Kit Boliche Virtual", self.client.get(reverse("search"), {"q": "tv box"}).content.decode())

        maquina = self.client.get(reverse("brinquedo_detalhe", args=[self.boliche.pk])).content.decode()
        self.assertIn("Já tem a máquina?", maquina)
        self.assertIn("Kit eletrônico completo", maquina)
        self.assertIn(f'href="{reverse("kit_detalhe", args=[self.kit.pk])}#breadcrumb"', maquina)

    def test_sem_kit_a_home_nao_tem_a_faixa_nem_o_menu(self):
        self.kit.delete()
        cache.clear()
        home = self.client.get(reverse("home")).content.decode()
        self.assertNotIn('id="kits-section"', home)
        self.assertNotIn(f'href="{reverse("kits")}#breadcrumb"', home)
        self.assertNotIn("site/paginas/home-kits.css", home)


class SemPrecoTests(Base):
    def test_sob_consulta_e_nunca_zero(self):
        for url in (reverse("kits"), reverse("kit_detalhe", args=[self.kit.pk]), reverse("home")):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertIn("Sob consulta", html)
                self.assertNotIn("R$ 0,00", html)
        pagina = self.client.get(reverse("kit_detalhe", args=[self.kit.pk])).content.decode()
        self.assertIn("Valor sob consulta", pagina)
        self.assertIn("Pedir orçamento no WhatsApp", pagina)
        self.assertNotIn('id="adicionar-peca"', pagina)
        self.assertNotIn('"offers"', pagina)  # sem preço não há oferta para o Google

    def test_o_carrinho_recusa_o_kit_sem_preco(self):
        self.assertEqual(self.client.get(reverse("previa_do_carrinho", args=["peca", self.kit.pk]), **XHR).status_code,
                         404)
        self.client.force_login(_cliente())
        resposta = self.client.post(reverse("adicionar_ao_carrinho", args=["peca", self.kit.pk]), {"quantidade": 1},
                                    **XHR)
        self.assertEqual(resposta.status_code, 404)
        self.assertFalse(ItemCarrinho.objects.exists())


@override_settings(MP_ACCESS_TOKEN="TEST-ACCESS-TOKEN")
class ComPrecoTests(Base):
    def setUp(self):
        super().setUp()
        self.kit.preco_venda = Decimal("1890.00")
        self.kit.save()

    def test_a_pagina_tem_o_carrinho(self):
        html = self.client.get(reverse("kit_detalhe", args=[self.kit.pk])).content.decode()
        self.assertIn('id="adicionar-peca"', html)
        self.assertIn("adicionarAoCarrinho('peca', %d" % self.kit.pk, html)
        self.assertIn("1.890,00", html)
        self.assertNotIn("Valor sob consulta", html)

    def test_a_previa_diz_que_e_kit(self):
        item = self.client.get(reverse("previa_do_carrinho", args=["peca", self.kit.pk]), **XHR).json()["item"]
        self.assertEqual(item["rotulo"], "Kit eletrônico")
        self.assertEqual(item["preco_unitario"], "1890.00")

    @mock.patch("core.notificacoes.enviar_boleto")
    @mock.patch("core.views.mercadopago.SDK")
    def test_vai_ao_carrinho_e_passa_no_checkout_como_peca(self, sdk_class, _email):
        self.client.force_login(_cliente())
        dados = self.client.post(reverse("adicionar_ao_carrinho", args=["peca", self.kit.pk]), {"quantidade": 2},
                                 **XHR).json()
        self.assertTrue(dados["sucesso"])
        self.assertEqual(dados["total_carrinho"], "3780.00")
        linha = ItemCarrinho.objects.get()
        self.assertEqual(linha.content_type, ContentType.objects.get_for_model(PecasReposicao))

        # o carrinho mostra o kit como kit, com o link da página dele
        carrinho_html = self.client.get(reverse("carrinho")).content.decode()
        self.assertIn("Kit eletrônico", carrinho_html)
        self.assertIn(reverse("kit_detalhe", args=[self.kit.pk]), carrinho_html)

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
        self.assertEqual((item.tipo_item, item.object_id, item.quantidade), ("pecasreposicao", self.kit.pk, 2))
        self.assertEqual(item.nome_item, "Kit Boliche Virtual")


class MigracaoDeDadosTests(TestCase):
    """A 0208 (core/kits.py, `semear`), rodada de novo sobre o banco do teste."""

    def setUp(self):
        cache.clear()
        self.boliche = _maquina("Boliche Virtual")
        # "Strike Kids Boliche" vem antes e não pode ser confundido com o Strike Kids
        self.parecido = _maquina("Strike Kids Boliche")
        self.strike = _maquina("Strike Kids")
        self.cabo = PecasReposicao.objects.create(nome="Cabo HDMI", descricao_peca="Cabo.",
                                                  preco_venda=Decimal("29.90"))

    def semear(self, **settings):
        with override_settings(**settings), mock.patch.object(kits, "subir_fotos") as subir:
            resultado = kits.semear(django_apps, None, avisar=lambda *_: None)
        return resultado, subir

    def test_cria_os_tres_kits_sem_preco_e_ligados_pelo_nome(self):
        resultado, subir = self.semear(IS_RENDER=False)
        self.assertEqual(sorted(resultado["criados"]), ["Kit Boliche Virtual", "Kit Lazer Shot", "Kit Strike Kids"])
        subir.assert_not_called()  # fora do Render nada sobe
        self.assertFalse(ImagemPeca.objects.filter(peca_reposicao__eh_kit=True).exists())

        boliche = PecasReposicao.objects.get(nome="Kit Boliche Virtual")
        strike = PecasReposicao.objects.get(nome="Kit Strike Kids")
        lazer = PecasReposicao.objects.get(nome="Kit Lazer Shot")
        self.assertEqual((boliche.maquina, strike.maquina, lazer.maquina), (self.boliche, self.strike, None))
        for kit in (boliche, strike, lazer):
            with self.subTest(kit=kit.nome):
                self.assertTrue(kit.eh_kit and kit.ativo)
                self.assertEqual(kit.uso, PecasReposicao.Uso.LOJA)
                self.assertIsNone(kit.preco_venda)
                self.assertEqual(kit.componentes_kit.count(), 7)
                cabo = kit.componentes_kit.get(nome="Cabo HDMI")
                self.assertEqual(cabo.peca, self.cabo)
        self.assertEqual(
            [c.nome for c in boliche.componentes_kit.all()],
            ["Placa Zero Delay", "TV Box", "Chicote", "Cabo HDMI", "Fonte", "Webcam", "Barra com 5 sensores"],
        )
        self.assertEqual(
            [c.nome for c in lazer.componentes_kit.all()][:3], ["Arma personalizada", "TV Box", "Câmera"],
        )

    def test_rodar_de_novo_nao_duplica_nem_mexe_no_que_o_dono_mudou(self):
        self.semear(IS_RENDER=False)
        kit = PecasReposicao.objects.get(nome="Kit Strike Kids")
        kit.preco_venda = Decimal("990")
        kit.save()
        resultado, _ = self.semear(IS_RENDER=False)
        self.assertEqual(resultado["criados"], [])
        self.assertEqual(len(resultado["existentes"]), 3)
        self.assertEqual(PecasReposicao.objects.filter(eh_kit=True).count(), 3)
        self.assertEqual(ComponenteKit.objects.count(), 21)
        kit.refresh_from_db()
        self.assertEqual(kit.preco_venda, Decimal("990.00"))

    def test_no_render_a_foto_sobe(self):
        _, subir = self.semear(IS_RENDER=True)
        subir.assert_called_once()

    def test_banco_sem_maquina_nenhuma_nao_ganha_kit(self):
        Brinquedos.objects.all().delete()
        resultado, _ = self.semear(IS_RENDER=False)
        self.assertTrue(resultado.get("catalogo_vazio"))
        self.assertFalse(PecasReposicao.objects.filter(eh_kit=True).exists())

    def test_a_foto_sobe_com_nome_curto_e_ja_conferida_pelo_recorte(self):
        from django.core.files.storage import InMemoryStorage

        self.semear(IS_RENDER=False)
        campo = ImagemPeca._meta.get_field("imagem")
        with mock.patch.object(campo, "storage", InMemoryStorage()):
            resultado = kits.subir_fotos(PecasReposicao, ImagemPeca, avisar=lambda *_: None)
            again = kits.subir_fotos(PecasReposicao, ImagemPeca, avisar=lambda *_: None)
        todos = ["Kit Boliche Virtual", "Kit Strike Kids", "Kit Lazer Shot"]
        self.assertEqual(resultado["subidas"], todos)
        self.assertEqual(again["ja_tinham"], todos)
        for nome, chave in zip(todos, ("kit-boliche-virtual", "kit-strike-kids", "kit-lazer-shot")):
            foto = ImagemPeca.objects.get(peca_reposicao__nome=nome)
            self.assertTrue(foto.imagem.name.startswith(f"pecas_reposicao/{chave}-"))
            self.assertLessEqual(len(foto.imagem.name), 60)
            self.assertEqual(foto.recorte_de, foto.imagem.name)  # o recorte automático não confere de novo
        self.assertEqual(ImagemPeca.objects.filter(peca_reposicao__eh_kit=True).count(), 3)

    def test_a_arte_do_kit_tem_fundo_de_verdade_e_o_recorte_a_deixa_como_esta(self):
        from . import recorte_peca

        for chave in ("kit-boliche-virtual", "kit-strike-kids", "kit-lazer-shot"):
            arte = Path(kits.arquivo_da_foto(chave))
            self.assertTrue(arte.exists(), chave)
            self.assertIsNone(recorte_peca.recortar(arte.read_bytes()), chave)

    def test_as_artes_sao_nossas_e_quadradas(self):
        """O dono: "essa image é de outro site". Só as nossas artes, 1200 x 1200."""
        from PIL import Image

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


@override_settings(ALLOWED_HOSTS=[INTERNO, "testserver"])
class PainelTests(Base):
    def setUp(self):
        super().setUp()
        self.strike = _maquina("Strike Kids")
        self.admin = User.objects.create_superuser("gestor", "gestor@lazersport.com.br", "senha-forte-123")
        self.client.force_login(self.admin)
        self.url = reverse("pecas_admin", urlconf="sistema_interno.urls")

    def salvar(self, **dados):
        base = {
            "action": "save", "resposta": "json", "nome": "Kit Strike Kids",
            "descricao_peca": "A eletrônica do Strike Kids.", "ativo": "1",
        }
        base.update(dados)
        return self.client.post(self.url, base, HTTP_HOST=INTERNO)

    def test_a_tela_tem_o_editor_do_kit_sem_select(self):
        html = self.client.get(self.url, HTTP_HOST=INTERNO).content.decode()
        self.assertIn('id="kitEditor"', html)
        editor = html[html.index('id="kitEditor"'):html.index('id="kitComponentesJson"')]
        self.assertNotIn("<select", editor)
        self.assertIn('type="radio" name="maquina" value="%d"' % self.strike.pk, editor)
        self.assertIn('id="buscarMaquinaKit"', editor)
        # o selo "Kit" na lista, e a máquina e os itens nos dados do cadastro
        self.assertIn("peca-selo-kit", html)
        dados = json.loads(re.search(r'<script id="pecas-dados" type="application/json">(.*?)</script>', html,
                                     flags=re.S).group(1))
        kit = next(p for p in dados if p["id"] == self.kit.pk)
        self.assertTrue(kit["eh_kit"])
        self.assertEqual(kit["maquina_id"], self.boliche.pk)
        self.assertEqual([c["nome"] for c in kit["componentes"]][:2], ["Placa Zero Delay", "TV Box"])
        self.assertEqual(kit["componentes"][2]["peca"], self.cabo.pk)

    def test_salva_o_kit_novo_com_a_maquina_e_os_itens(self):
        itens = [
            {"nome": "TV Box", "detalhe": "Com o jogo Strike Kids", "quantidade": "1", "peca": ""},
            {"nome": "Cabo HDMI", "detalhe": "", "quantidade": "2", "peca": str(self.cabo.pk)},
            {"nome": "", "detalhe": "", "quantidade": "1", "peca": ""},  # linha em branco não vira item
            {"nome": "Câmera", "detalhe": "", "quantidade": "1", "peca": ""},
        ]
        resposta = self.salvar(eh_kit="1", maquina=str(self.strike.pk), componentes_json=json.dumps(itens))
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(resposta.json()["status"], "sucesso")
        kit = PecasReposicao.objects.get(pk=resposta.json()["id"])
        self.assertTrue(kit.eh_kit)
        self.assertEqual(kit.maquina, self.strike)
        self.assertIsNone(kit.preco_venda)
        self.assertEqual(
            [(c.ordem, c.nome, c.quantidade, c.peca_id) for c in kit.componentes_kit.all()],
            [(1, "TV Box", 1, None), (2, "Cabo HDMI", 2, self.cabo.pk), (3, "Câmera", 1, None)],
        )
        self.assertEqual(kit.componentes_kit.first().detalhe, "Com o jogo Strike Kids")

    def test_editar_reordena_e_troca_a_maquina(self):
        itens = [{"nome": c.nome, "detalhe": c.detalhe, "quantidade": c.quantidade, "peca": c.peca_id or ""}
                 for c in self.kit.componentes_kit.all()]
        itens.reverse()
        self.salvar(id=self.kit.pk, nome="Kit Boliche Virtual", eh_kit="1", maquina=str(self.strike.pk),
                    preco_venda="1.890,00", componentes_json=json.dumps(itens))
        self.kit.refresh_from_db()
        self.assertEqual(self.kit.maquina, self.strike)
        self.assertEqual(self.kit.preco_venda, Decimal("1890.00"))
        self.assertEqual([c.nome for c in self.kit.componentes_kit.all()],
                         ["Barra com 5 sensores", "Cabo HDMI", "TV Box", "Placa Zero Delay"])

    def test_sem_a_lista_os_itens_ficam_e_sem_a_marca_a_maquina_sai(self):
        # o formulário que não manda a lista (só a chave desligada) não apaga os itens
        self.salvar(id=self.kit.pk, nome="Kit Boliche Virtual", maquina=str(self.boliche.pk))
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
        )
        for dados, frase in casos:
            with self.subTest(frase=frase):
                resposta = self.salvar(eh_kit="1", **dados)
                self.assertEqual(resposta.status_code, 400)
                self.assertIn(frase, resposta.json()["msg"])
        self.assertFalse(PecasReposicao.objects.filter(nome="Kit Strike Kids").exists())

    def test_filtro_dos_kits(self):
        html = self.client.get(self.url, {"situacao": "kits"}, HTTP_HOST=INTERNO).content.decode()
        self.assertIn("Kit Boliche Virtual", html)
        self.assertNotIn("Motor 1/4 CV</h3>", html)


class SitemapEMenuTests(Base):
    def test_sitemap_tem_a_vitrine_e_cada_kit(self):
        xml = self.client.get("/sitemap.xml").content.decode()
        self.assertIn("<loc>https://www.lazersport.com.br/kits/</loc>", xml)
        self.assertIn(f"<loc>https://www.lazersport.com.br/kits/{self.kit.pk}/</loc>", xml)
        # o kit não aparece como peça
        self.assertNotIn(f"/pecas/{self.kit.pk}/</loc>", xml)
        self.assertIn(f"/pecas/{self.motor.pk}/</loc>", xml)

    def test_sitemap_sem_kit_nao_leva_a_vitrine_vazia(self):
        self.kit.delete()
        cache.clear()
        self.assertNotIn("/kits/</loc>", self.client.get("/sitemap.xml").content.decode())

    def test_menu_do_computador_e_do_celular(self):
        html = self.client.get(reverse("pecas_reposicao")).content.decode()
        topo = html[html.index('id="topo-servicos"'):]
        topo = topo[:topo.index("</div>")]
        self.assertIn(f'href="{reverse("kits")}#breadcrumb"', topo)
        self.assertIn("Kits eletrônicos", topo)
        celular = html[html.index('class="ls-mobile-nav-list"'):]
        celular = celular[:celular.index("</div>")]
        self.assertIn(f'href="{reverse("kits")}#breadcrumb"', celular)

    def test_o_icone_do_item(self):
        casos = {
            "TV Box": "fa-tv", "Barra com 5 sensores de precisão": "fa-wave-square", "Câmera": "fa-camera",
            "Webcam": "fa-camera", "Arma personalizada": "fa-crosshairs", "Placa Zero Delay": "fa-microchip",
            "Chicote": "fa-network-wired", "Cabo HDMI": "fa-plug", "Fonte": "fa-bolt", "Manual": "fa-puzzle-piece",
        }
        for nome, icone in casos.items():
            with self.subTest(nome=nome):
                self.assertEqual(kits.icone_do_componente(nome), icone)
