"""A ficha "Air Game Premium com Sistema de Ficheiro" vira a opção do Air Game Premium (a 0222;
LEIA-ME-V10, seção 151). Dados SINTÉTICOS.

O que estes testes protegem:

  * a ficha some e o Air Game Premium fica, com o preço dele e oferecendo a opção;
  * o preço COM passa a ser Air Game Premium + o acréscimo (a regra do acréscimo fixo vence os
    R$ 14.990,00 da ficha), e o log diz o preço antigo, o novo e a diferença;
  * o item de orçamento passa para a máquina, marcado e com o nome dela + a marca, sem mudar o
    valor combinado; o item de carrinho passa marcado (e soma com a linha igual, sem se misturar
    com a linha SEM); o item de pedido passa sem mudar o nome nem o preço vendidos; o favorito
    passa; o endereço antigo redireciona;
  * rodar de novo não muda nada; sem a ficha, sem a máquina, ou com a máquina marcada "não
    oferece", nada é apagado; a ficha de nome parecido não é tocada;
  * a migração é só de dados.
"""

import importlib
from decimal import Decimal

from django.apps import apps as registro
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import migrations
from django.test import TestCase
from django.urls import reverse

from . import variantes
from .models import Brinquedos, Carrinho, Favorito, ItemCarrinho, ItemPedido, Pedido, VarianteAdesivo
from .tests_fichas_que_sao_adesivos import produto

migracao = importlib.import_module("core.migrations.0222_ficha_com_sistema_de_ficha")
FICHA = "Air Game Premium com Sistema de Ficheiro"
MARCA = " — com sistema de ficha"


class _NoAr(TestCase):
    def setUp(self):
        from sistema_interno import moedeiro
        from sistema_interno.models import ItemOrcamento, Orcamento

        cache.clear()
        moedeiro.esquecer()
        self.premium = produto("Air Game Premium", "13500.00", ["air-game-premium.webp"])
        self.ficha = produto(FICHA, "14990.00", ["air-game-premium-ficheiro.webp"])
        self.vizinho = produto("Air Game Premium Plus com Sistema de Ficheiro", "19990.00", ["plus.webp"])
        self.ficha_id = self.ficha.pk
        self.usuario = User.objects.create_user("cliente-premium", password="x")
        self.tipo = ContentType.objects.get_for_model(Brinquedos)
        self.carrinho = Carrinho.objects.create(cliente=self.usuario.perfil)
        self.linha = ItemCarrinho.objects.create(carrinho=self.carrinho, content_type=self.tipo,
                                                 object_id=self.ficha.pk, quantidade=1)
        self.linha_sem = ItemCarrinho.objects.create(carrinho=self.carrinho, content_type=self.tipo,
                                                     object_id=self.premium.pk, quantidade=3)
        orcamento = Orcamento.objects.create(nome_cliente="Buffet Sintético")
        self.item = ItemOrcamento.objects.create(orcamento=orcamento, descricao=FICHA, brinquedo=self.ficha,
                                                 quantidade=2, valor_unitario=Decimal("14000.00"))
        self.item_escrito = ItemOrcamento.objects.create(orcamento=orcamento, descricao="Premium do evento, com ficheiro",
                                                         brinquedo=self.ficha, valor_unitario=Decimal("14990.00"))
        self.pedido = Pedido.objects.create(cliente=self.usuario.perfil, carrinho_origem=self.carrinho,
                                            status="pago", total_liquido=Decimal("14990.00"))
        self.item_pedido = ItemPedido.objects.create(
            pedido=self.pedido, content_type=self.tipo, object_id=self.ficha.pk, nome_item=FICHA,
            tipo_item="brinquedos", preco_unitario=Decimal("14990.00"), quantidade=1, subtotal=Decimal("14990.00"),
        )
        tipo_fav = Favorito._meta.get_field("tipo").choices[0][0]
        Favorito.objects.create(usuario=self.usuario, brinquedo=self.ficha, tipo=tipo_fav)
        cache.clear()

    def rodar(self):
        avisos = []
        feito = variantes.unir_as_fichas_com_sistema_de_ficha(registro, None, avisar=avisos.append)
        cache.clear()
        return feito, " ".join(avisos)


class FichaDoPremiumTests(_NoAr):
    def test_a_ficha_some_e_a_maquina_fica_com_a_opcao_e_o_preco_novo(self):
        from sistema_interno import moedeiro

        feito, log = self.rodar()
        self.assertEqual(feito, [("Air Game Premium", FICHA, "unida", Decimal("14990.00"), Decimal("14499.00"))])
        self.assertFalse(Brinquedos.objects.filter(pk=self.ficha_id).exists())
        self.premium.refresh_from_db()
        self.assertEqual((self.premium.nome_brinquedo, self.premium.valor_brinquedo, self.premium.moedeiro),
                         ("Air Game Premium", Decimal("13500.00"), "sim"))
        self.assertTrue(moedeiro.oferece(self.premium))
        self.assertEqual(moedeiro.preco(self.premium, True), Decimal("14499.00"))
        # o log do deploy: o preço antigo, o novo e a diferença
        for trecho in ("PREÇO ANTIGO da ficha: R$ 14.990,00", "PREÇO NOVO com sistema de ficha: R$ 14.499,00",
                       "R$ 13.500,00 + acréscimo R$ 999,00", "Diferença: R$ -491,00", "air-game-premium-ficheiro.webp"):
            self.assertIn(trecho, log)
        # a vizinha de nome parecido não foi tocada
        self.assertTrue(Brinquedos.objects.filter(pk=self.vizinho.pk, valor_brinquedo=Decimal("19990.00")).exists())

    def test_as_referencias_passam_para_a_maquina_com_a_opcao_marcada(self):
        self.rodar()
        # o orçamento: a máquina, marcado, o nome dela com a marca; o valor combinado fica
        self.item.refresh_from_db()
        self.assertEqual((self.item.brinquedo_id, self.item.com_moedeiro, self.item.descricao, self.item.valor_unitario),
                         (self.premium.pk, True, "Air Game Premium" + MARCA, Decimal("14000.00")))
        self.item_escrito.refresh_from_db()
        self.assertEqual((self.item_escrito.brinquedo_id, self.item_escrito.com_moedeiro, self.item_escrito.descricao),
                         (self.premium.pk, True, "Premium do evento, com ficheiro" + MARCA))
        # o carrinho: a linha da ficha vira a máquina COM; a linha SEM continua separada
        self.linha.refresh_from_db()
        self.linha_sem.refresh_from_db()
        self.assertEqual((self.linha.object_id, self.linha.com_ficha, self.linha.quantidade), (self.premium.pk, True, 1))
        self.assertEqual((self.linha_sem.com_ficha, self.linha_sem.quantidade), (False, 3))
        self.assertEqual(ItemCarrinho.objects.get(pk=self.linha.pk).preco_unitario, Decimal("14499.00"))
        self.assertEqual(ItemCarrinho.objects.get(pk=self.linha.pk).nome_com_adesivo, "Air Game Premium" + MARCA)
        # o pedido: aponta para a máquina; o nome e o preço vendidos não mudam
        self.item_pedido.refresh_from_db()
        self.assertEqual((self.item_pedido.object_id, self.item_pedido.nome_item, self.item_pedido.preco_unitario),
                         (self.premium.pk, FICHA, Decimal("14990.00")))
        self.assertEqual(Favorito.objects.get(usuario=self.usuario).brinquedo_id, self.premium.pk)
        # o endereço antigo vai para a máquina
        self.assertEqual(variantes.redirecionamento(self.ficha_id), self.premium.pk)
        resposta = self.client.get(reverse("brinquedo_detalhe", args=[self.ficha_id]))
        self.assertEqual(resposta.status_code, 301)
        self.assertTrue(resposta["Location"].endswith(reverse("brinquedo_detalhe", args=[self.premium.pk])))

    def test_a_linha_igual_do_carrinho_soma(self):
        ja_com = ItemCarrinho.objects.create(carrinho=self.carrinho, content_type=self.tipo,
                                             object_id=self.premium.pk, quantidade=2, com_ficha=True)
        self.rodar()
        ja_com.refresh_from_db()
        self.assertEqual(ja_com.quantidade, 3)
        self.assertFalse(ItemCarrinho.objects.filter(pk=self.linha.pk).exists())
        self.assertEqual(ItemCarrinho.objects.filter(carrinho=self.carrinho).count(), 2)

    def test_rodar_de_novo_nao_muda_nada(self):
        self.rodar()

        def retrato():
            from sistema_interno.models import ItemOrcamento

            return (
                sorted(Brinquedos.objects.values_list("id", "nome_brinquedo", "valor_brinquedo", "moedeiro")),
                sorted(VarianteAdesivo.objects.values_list("id", "brinquedo_id", "id_antigo")),
                sorted(ItemCarrinho.objects.values_list("id", "object_id", "com_ficha", "quantidade")),
                sorted(ItemOrcamento.objects.values_list("id", "brinquedo_id", "com_moedeiro", "descricao")),
            )

        antes = retrato()
        feito, log = self.rodar()
        self.assertEqual(retrato(), antes)
        self.assertIn("ficha não encontrada", feito[0][2])
        migracao.unir(registro, None)
        self.assertEqual(retrato(), antes)

    def test_sem_a_ficha_ou_sem_a_maquina_nada_e_apagado(self):
        Brinquedos.objects.filter(pk=self.premium.pk).update(nome_brinquedo="Air Game Premium 2")
        feito, _ = self.rodar()
        self.assertEqual(feito[0][2], "máquina não encontrada")
        self.assertTrue(Brinquedos.objects.filter(pk=self.ficha_id).exists())

    def test_a_maquina_marcada_como_nao_oferece_nao_e_mexida(self):
        Brinquedos.objects.filter(pk=self.premium.pk).update(moedeiro="nao")
        feito, log = self.rodar()
        self.assertIn("não oferece", feito[0][2])
        self.assertTrue(Brinquedos.objects.filter(pk=self.ficha_id).exists())
        self.item.refresh_from_db()
        self.assertEqual(self.item.brinquedo_id, self.ficha_id)

    def test_a_migracao_e_so_de_dados(self):
        self.assertTrue(all(isinstance(o, migrations.RunPython) for o in migracao.Migration.operations))
        self.assertIn(("sistema_interno", "0087_item_do_orcamento_com_sistema_de_ficha"), migracao.Migration.dependencies)
