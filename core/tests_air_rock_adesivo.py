"""O Air Rock é um adesivo do Air Game Premium, e o card gira por adesivo (LEIA-ME 72, a 0190).

O cliente: "vc não percebeu que o air game premium e o air game rock são o
mesmo, só é um adesivo? e que eles deveriam estar juntos, o carrossel não
deve ser por posição e sim por adesivos, entendeu? com uma transição suave e
legal." O que estes testes protegem:

  * a 0190 com o banco como está no ar (o Air Rock à parte, com a capa em cena
    do showroom, o recorte do cartaz e referências de verdade: carrinho,
    orçamento, favorito, lista de desejos, a promoção da Black Friday e uma
    com ele nos extras, combo, clique e as interações por hora): vira o adesivo
    "Air Rock" do Air Game Premium (o padrão vira "Premium"), nada se perde,
    a ficha some, o endereço antigo vai para o produto e rodar de novo não
    muda nada;
  * o card: uma foto por adesivo (a capa quadrada em cena do adesivo; sem
    ela, a primeira posição), o padrão primeiro, o nome de cada um; com um
    adesivo só, não gira; o site/ls-giro.js com a troca de lado e o nome.
"""

import importlib
import json
import re
from decimal import Decimal
from pathlib import Path

from django.apps import apps as registro
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import fotos_dos_cards, variantes
from .models import (
    BrinquedoClick,
    Brinquedos,
    Carrinho,
    CategoriasBrinquedos,
    Combos,
    Favorito,
    ImagemBrinquedo,
    InteracaoPorHora,
    ItemCarrinho,
    ListaDesejos,
    Promocoes,
    VarianteAdesivo,
    galeria_publica,
)

migracao_0190 = importlib.import_module("core.migrations.0190_air_rock_adesivo_do_air_game_premium")
SITE = Path(__file__).resolve().parent / "static" / "site"


def _calado(*_a, **_k):
    return None


def _produto(nome, categoria, fotos, **campos):
    """O produto com as fotos [(tipo, arquivo, papel)] (a primeira é a capa)."""
    dados = {"descricao": f"{nome}.", "avaliacao": Decimal("4.9"), "voltz": "220V", "exibir_na_loja": True}
    dados.update(campos)
    brinquedo = Brinquedos.objects.create(nome_brinquedo=nome, imagem_brinquedo=f"imagens_brinquedos/{fotos[0][1]}", **dados)
    brinquedo.categorias_brinquedos.add(categoria)
    for ordem, (tipo, arquivo, papel) in enumerate(fotos, start=1):
        ImagemBrinquedo.objects.create(brinquedo=brinquedo, tipo=tipo, ordem=ordem, papel_na_capa=papel,
                                       imagem=f"imagens_brinquedos/{arquivo}")
    return brinquedo


class _NoAr(TestCase):
    """O catálogo como está no ar: o Air Game Premium e o Air Rock à parte (com tudo o que aponta para ele)."""

    def setUp(self):
        cache.clear()
        self.categoria = CategoriasBrinquedos.objects.create(nome_categoria="Jogos de Mesa", imagem_categoria="categorias/m.png")
        self.premium = _produto("Air Game Premium", self.categoria, [
            ("perfil", "galeria/cena-air-game-premium-219129ff3c.webp", "cena"),
            ("lado_direito", "air-game-premium-lado.webp", ""),
        ], valor_brinquedo=Decimal("14990.00"))
        self.rock = _produto("Air Rock", self.categoria, [
            ("perfil", "galeria/cena-air-rock-5d2e1a0b3c.webp", "cena"),          # a capa em cena (a 0180)
            (None, "black-friday-2026-produto-air-rock-8cf5a03f_cbfpzb.webp", ""),  # o recorte do cartaz
            ("lado_direito", "air-rock-lado.webp", ""),
        ], exibir_na_loja=False)
        self.cartaz = "imagens_brinquedos/black-friday-2026-produto-air-rock-8cf5a03f_cbfpzb.webp"
        # as referências ao Air Rock
        self.usuario = User.objects.create_user("cliente-rock", password="x")
        tipo = ContentType.objects.get_for_model(Brinquedos)
        self.carrinho = Carrinho.objects.create()
        self.linha_rock = ItemCarrinho.objects.create(carrinho=self.carrinho, content_type=tipo, object_id=self.rock.pk, quantidade=2)
        self.linha_premium = ItemCarrinho.objects.create(carrinho=self.carrinho, content_type=tipo, object_id=self.premium.pk, quantidade=1)
        from sistema_interno.models import ItemOrcamento, Orcamento

        orcamento = Orcamento.objects.create(nome_cliente="Buffet do Rock")
        self.item_orcamento = ItemOrcamento.objects.create(orcamento=orcamento, descricao="Air Rock", brinquedo=self.rock)
        tipo_fav = Favorito._meta.get_field("tipo").choices[0][0]
        Favorito.objects.create(usuario=self.usuario, brinquedo=self.rock, tipo=tipo_fav)
        Favorito.objects.create(usuario=self.usuario, brinquedo=self.premium, tipo=tipo_fav)
        self.desejos = ListaDesejos.objects.create()
        self.desejos.brinquedos.add(self.rock)
        self.promo = Promocoes.objects.create(descricao="Black Friday: Air Rock", brinquedos=self.rock,
                                              preco_promocao=Decimal("12990.00"), preco_de=Decimal("14990.00"),
                                              arte_promocao="promocoes/black-friday-2026-arte-10-aa.webp")
        self.kit = Promocoes.objects.create(descricao="Kit Jogos", brinquedos=self.premium)
        self.kit.brinquedos_extras.add(self.rock)
        self.combo = Combos.objects.create(descricao="Combo Mesas", valor_combo=Decimal("100.00"))
        self.combo.brinquedos.add(self.rock)
        self.clique = BrinquedoClick.objects.create(brinquedo_clicado=self.rock)
        hora = timezone.now().replace(minute=0, second=0, microsecond=0)
        InteracaoPorHora.objects.create(evento="visita", alvo="brinquedo", objeto_id=self.rock.pk, hora=hora, quantidade=3)
        InteracaoPorHora.objects.create(evento="visita", alvo="brinquedo", objeto_id=self.premium.pk, hora=hora, quantidade=5)
        InteracaoPorHora.objects.create(evento="carrinho", alvo="brinquedo", objeto_id=self.rock.pk, hora=hora, quantidade=1)
        cache.clear()

    def juntar(self):
        variantes.juntar_os_achados_depois(registro, avisar=_calado)
        fotos_dos_cards.limpar_cache()
        cache.clear()


class JuntarTests(_NoAr):
    def _retrato(self):
        return (
            sorted(ImagemBrinquedo.objects.values_list("id", "brinquedo_id", "variante_id", "tipo", "papel_na_capa", "imagem")),
            sorted(VarianteAdesivo.objects.values_list("id", "brinquedo_id", "nome", "slug", "padrao", "id_antigo")),
            sorted(ItemCarrinho.objects.values_list("id", "object_id", "adesivo", "quantidade")),
            sorted(InteracaoPorHora.objects.values_list("evento", "objeto_id", "quantidade")),
            sorted(Brinquedos.objects.values_list("id", "nome_brinquedo")),
        )

    def test_um_objeto_com_os_dois_adesivos_e_nada_se_perde(self):
        rock_id, fotos_antes = self.rock.pk, ImagemBrinquedo.objects.count()
        self.juntar()
        primeiro = self._retrato()
        self.juntar()  # de novo: nada muda
        self.assertEqual(self._retrato(), primeiro)

        # um objeto só: a ficha sumiu; o Premium tem os dois adesivos (o padrão primeiro)
        self.assertFalse(Brinquedos.objects.filter(pk=rock_id).exists())
        self.assertEqual(ImagemBrinquedo.objects.count(), fotos_antes)
        premium = Brinquedos.objects.get(pk=self.premium.pk)
        self.assertEqual(premium.valor_brinquedo, Decimal("14990.00"))
        adesivos = list(premium.variantes_adesivo.order_by("-padrao", "ordem").values_list("nome", "slug", "padrao"))
        self.assertEqual(adesivos, [("Premium", "premium", True), ("Air Rock", "air-rock", False)])
        rock = premium.variantes_adesivo.get(slug="air-rock")
        self.assertEqual(rock.id_antigo, rock_id)
        # as fotos do Air Rock: a capa em cena, as posições e o recorte do cartaz (fora do site)
        self.assertEqual(sorted((f.tipo or "-", f.papel_na_capa) for f in rock.fotos.all()),
                         [("-", ""), ("lado_direito", ""), ("perfil", "cena")])
        publicas = [f.imagem.name for f in galeria_publica(premium.imagens_brinquedo.all(), adesivo_id=rock.pk)]
        self.assertNotIn(self.cartaz, publicas)
        self.assertEqual(len(publicas), 2)
        self.assertEqual([f.imagem.name for f in premium.imagens_ordenadas],
                         ["imagens_brinquedos/galeria/cena-air-game-premium-219129ff3c.webp",
                          "imagens_brinquedos/air-game-premium-lado.webp"])
        # TODAS as referências vieram para o Premium; o carrinho, com o adesivo
        linha = ItemCarrinho.objects.get(pk=self.linha_rock.pk)
        self.assertEqual((linha.object_id, linha.adesivo, linha.quantidade), (premium.pk, "Air Rock", 2))
        self.assertEqual(ItemCarrinho.objects.get(pk=self.linha_premium.pk).adesivo, "")
        from sistema_interno.models import ItemOrcamento

        self.assertEqual(ItemOrcamento.objects.get(pk=self.item_orcamento.pk).brinquedo_id, premium.pk)
        self.assertEqual(Favorito.objects.filter(usuario=self.usuario).count(), 1)  # o repetido virou um
        self.assertEqual(list(self.desejos.brinquedos.values_list("pk", flat=True)), [premium.pk])
        promo = Promocoes.objects.get(pk=self.promo.pk)
        self.assertEqual((promo.brinquedos_id, promo.descricao, promo.preco_promocao, promo.arte_promocao.name),
                         (premium.pk, "Black Friday: Air Rock", Decimal("12990.00"), "promocoes/black-friday-2026-arte-10-aa.webp"))
        self.assertEqual(list(Promocoes.objects.get(pk=self.kit.pk).brinquedos_extras.values_list("pk", flat=True)), [])
        self.assertEqual(list(Combos.objects.get(pk=self.combo.pk).brinquedos.values_list("pk", flat=True)), [premium.pk])
        self.assertEqual(BrinquedoClick.objects.get(pk=self.clique.pk).brinquedo_clicado_id, premium.pk)
        self.assertEqual(sorted(InteracaoPorHora.objects.values_list("evento", "objeto_id", "quantidade")),
                         [("carrinho", premium.pk, 1), ("visita", premium.pk, 8)])  # a mesma hora: somada
        # o endereço antigo vai para o produto
        resposta = self.client.get(reverse("brinquedo_detalhe", args=[rock_id]))
        self.assertEqual((resposta.status_code, resposta["Location"]), (301, f"/brinquedo/{premium.pk}/"))
        # a página do produto: o seletor com os dois adesivos; o Air Rock com a capa em cena dele
        pagina = self.client.get(reverse("brinquedo_detalhe", args=[premium.pk]) + "?adesivo=air-rock")
        self.assertEqual([i.imagem.name for i in pagina.context["imagens_brinquedo"]][0],
                         "imagens_brinquedos/galeria/cena-air-rock-5d2e1a0b3c.webp")
        self.assertNotIn("black-friday-2026-produto-air-rock", pagina.content.decode())

    def test_o_kit_com_o_premium_e_o_rock_nos_extras_fica_com_o_premium(self):
        self.kit.brinquedos_extras.add(Brinquedos.objects.create(nome_brinquedo="Pebolim", descricao="x", avaliacao=5, voltz="220V"))
        self.juntar()
        kit = Promocoes.objects.get(pk=self.kit.pk)
        self.assertEqual(kit.brinquedos_id, self.premium.pk)
        self.assertEqual([b.nome_brinquedo for b in kit.brinquedos_extras.all()], ["Pebolim"])

    def test_a_migracao(self):
        self.assertEqual(migracao_0190.Migration.dependencies, [("core", "0186_capas_quadradas_dos_adesivos")])
        migracao_0190.juntar(registro, None)
        self.assertFalse(Brinquedos.objects.filter(nome_brinquedo="Air Rock").exists())
        self.assertEqual(variantes.JUNTADOS_DEPOIS[0][0][0], "Air Game Premium")

    def test_sem_a_ficha_nada_acontece(self):
        Brinquedos.objects.filter(pk=self.rock.pk).delete()
        antes = self._retrato()
        self.juntar()
        self.assertEqual(self._retrato()[4], antes[4])
        self.assertEqual(Brinquedos.objects.get(pk=self.premium.pk).variantes_adesivo.count(), 1)


class CardPorAdesivoTests(_NoAr):
    """O card gira uma foto por adesivo: a capa quadrada em cena de cada um, o padrão primeiro, com o nome."""

    def _cards(self, url):
        html = self.client.get(url).content.decode()
        return html, [json.loads(m.replace("&quot;", '"')) for m in re.findall(r'data-fotos-card="([^"]*)"', html)]

    def test_o_card_do_premium_gira_os_dois_adesivos(self):
        self.juntar()
        for url in (reverse("brinquedos"), reverse("categoria_detalhe", args=[self.categoria.pk]), reverse("home")):
            with self.subTest(url):
                html, cards = self._cards(url)
                do_premium = next(c for c in cards if any("air-game-premium" in item["src"] for item in c))
                self.assertEqual([item["adesivo"] for item in do_premium], ["Premium", "Air Rock"])
                self.assertIn("cena-air-game-premium", do_premium[0]["src"])
                self.assertIn("cena-air-rock", do_premium[1]["src"])
                self.assertNotIn("black-friday-2026-produto-air-rock", html)

    def test_sem_a_capa_em_cena_a_primeira_posicao_e_um_adesivo_so_nao_gira(self):
        self.juntar()
        rock = VarianteAdesivo.objects.get(slug="air-rock")
        ImagemBrinquedo.objects.filter(variante=rock, papel_na_capa="cena").update(papel_na_capa="")
        ImagemBrinquedo.objects.filter(variante=rock, tipo="perfil").update(tipo=None)
        fotos_dos_cards.limpar_cache()
        cartoes = fotos_dos_cards.do_card(self.premium.pk)
        self.assertEqual([c["adesivo"] for c in cartoes], ["Premium", "Air Rock"])
        self.assertIn("air-rock-lado", cartoes[1]["src"])  # a primeira posição com fundo do adesivo
        # um adesivo só (com várias posições): não gira
        sozinho = _produto("Pebolim", self.categoria, [("perfil", "pebolim.png", ""), ("verso", "pebolim-verso.png", "")])
        fotos_dos_cards.limpar_cache()
        self.assertIsNone(fotos_dos_cards.do_card(sozinho.pk))
        _html, cards = self._cards(reverse("brinquedos"))
        self.assertFalse(any("pebolim" in item["src"] for c in cards for item in c))

    def test_o_script_troca_de_lado_com_o_nome_do_adesivo(self):
        js = (SITE / "ls-giro.js").read_text()
        self.assertIn('etiqueta.className = "card-giro-adesivo"', js)
        self.assertIn('foto.classList.add("card-giro-saindo")', js)
        self.assertIn("prefers-reduced-motion: reduce", js)
        self.assertIn("estado.puladas.add(indice)", js)  # a foto que ficaria com faixas continua pulada
        css = (SITE / "ls-tema.css").read_text()
        self.assertIn("translate: 5% 0;", css)
        self.assertIn(".card-giro-adesivo--trocando", css)
