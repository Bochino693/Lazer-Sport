"""As fichas salvas como brinquedo que eram adesivos (a 0218; LEIA-ME-V10, seção 143).

O dono: "foi salvo uns brinquedos que na verdade eram para ser adesivos, air
game kids adesivo cand, balde e xícara também... apaga os objetos e adicione
como adesivo." O adesivo se chama "Candy" e não tem preço próprio.

O catálogo destes testes reproduz o que está no ar (os nomes, os preços e o
que o dono descreveu de cada ficha), com dados SINTÉTICOS:

  * "Air Game Kids cand" (R$ 5.680,00, 1 foto) -> o adesivo "Candy" do Air
    Game Kids, que continua com o preço e o adesivo padrão ("Astronautas");
  * "Multijogos 32"" (com as aspas de polegada; R$ 7.990,00, 1 foto, sem
    categoria) -> o adesivo "Candy" do Multi Jogos (R$ 9.990,00);
  * "Balde giratório" (sem foto, R$ 850.000,00) e "Balde Giratório Manual"
    (R$ 8.500,00, com as medidas e a foto) -> UM "Balde Giratório" a
    R$ 8.500,00, com a foto como adesivo "Candy";
  * as referências (orçamento, carrinho, favorito) vão para o que fica;
  * rodar de novo não muda nada; a ficha com OUTRO nome não é tocada, e
    nenhuma ficha de nome parecido é juntada por engano.
"""

import importlib
from decimal import Decimal

from django.apps import apps as registro
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from . import fotos_dos_cards, variantes
from .models import Brinquedos, Carrinho, CategoriasBrinquedos, Favorito, ImagemBrinquedo, ItemCarrinho, VarianteAdesivo

migracao = importlib.import_module("core.migrations.0218_fichas_que_sao_adesivos")


def _calado(*_a, **_k):
    return None


def produto(nome, preco, fotos=(), categoria=None, **campos):
    dados = {"descricao": f"{nome}.", "avaliacao": Decimal("4.9"), "voltz": "220V", "exibir_na_loja": True,
             "valor_brinquedo": Decimal(preco)}
    dados.update(campos)
    capa = f"imagens_brinquedos/{fotos[0]}" if fotos else ""
    brinquedo = Brinquedos.objects.create(nome_brinquedo=nome, imagem_brinquedo=capa, **dados)
    if categoria is not None:
        brinquedo.categorias_brinquedos.add(categoria)
    for ordem, arquivo in enumerate(fotos, start=1):
        ImagemBrinquedo.objects.create(brinquedo=brinquedo, tipo="perfil" if ordem == 1 else None, ordem=ordem,
                                       imagem=f"imagens_brinquedos/{arquivo}")
    return brinquedo


class _NoAr(TestCase):
    def setUp(self):
        cache.clear()
        mesa = CategoriasBrinquedos.objects.create(nome_categoria="Jogos de Mesa", imagem_categoria="categorias/m.png")
        self.mecanicos = CategoriasBrinquedos.objects.create(nome_categoria="Mecânicos", imagem_categoria="categorias/c.png")
        # os produtos que ficam
        self.agk = produto("Air Game Kids", "6990.00", ["air-game-kids-astronautas.webp"], mesa)
        padrao = variantes._padrao_do(self.agk, VarianteAdesivo, Brinquedos)
        VarianteAdesivo.objects.filter(pk=padrao.pk).update(nome="Astronautas", slug="astronautas")
        self.multi = produto("Multi Jogos", "9990.00", ["multi-jogos.webp"], mesa)
        # as fichas que eram adesivos
        self.agk_cand = produto("Air Game Kids cand", "5680.00", ["air-game-kids-candy.webp"], mesa)
        self.multi_32 = produto('Multijogos 32"', "7990.00", ["multijogos-32-candy.webp"])
        # o balde, em duas fichas
        self.balde = produto("Balde giratório", "850000.00", [], self.mecanicos)
        self.balde_manual = produto(
            "Balde Giratório Manual", "8500.00", ["balde-giratorio-candy.webp"], self.mecanicos,
            altura_m=Decimal("1.10"), largura_m=Decimal("1.50"), profundidade_m=Decimal("1.50"), voltz="Manual",
        )
        # vizinhos de nome parecido, que NÃO podem ser tocados
        self.agk_premium = produto("Air Game Premium", "14990.00", ["air-game-premium.webp"], mesa)
        self.multi_42 = produto('Multijogos 42"', "8990.00", ["multijogos-42.webp"])
        self.balde_eletrico = produto("Balde Giratório Elétrico", "12000.00", ["balde-eletrico.webp"], self.mecanicos)
        # as referências
        self.usuario = User.objects.create_user("cliente-candy", password="x")
        tipo = ContentType.objects.get_for_model(Brinquedos)
        self.carrinho = Carrinho.objects.create()
        self.linha_cand = ItemCarrinho.objects.create(carrinho=self.carrinho, content_type=tipo, object_id=self.agk_cand.pk, quantidade=1)
        self.linha_balde = ItemCarrinho.objects.create(carrinho=self.carrinho, content_type=tipo, object_id=self.balde.pk, quantidade=2)
        from sistema_interno.models import ItemOrcamento, Orcamento

        orcamento = Orcamento.objects.create(nome_cliente="Buffet Sintético")
        self.item_multi = ItemOrcamento.objects.create(orcamento=orcamento, descricao='Multijogos 32"', brinquedo=self.multi_32)
        self.item_balde = ItemOrcamento.objects.create(orcamento=orcamento, descricao="Balde giratório", brinquedo=self.balde)
        tipo_fav = Favorito._meta.get_field("tipo").choices[0][0]
        Favorito.objects.create(usuario=self.usuario, brinquedo=self.agk_cand, tipo=tipo_fav)
        cache.clear()

    def rodar(self):
        migracao.juntar(registro, None)
        fotos_dos_cards.limpar_cache()
        cache.clear()

    def retrato(self):
        return (
            sorted(Brinquedos.objects.values_list("id", "nome_brinquedo", "valor_brinquedo", "voltz")),
            sorted(VarianteAdesivo.objects.values_list("id", "brinquedo_id", "nome", "slug", "padrao", "id_antigo")),
            sorted(ImagemBrinquedo.objects.values_list("id", "brinquedo_id", "variante_id", "tipo", "imagem")),
            sorted(ItemCarrinho.objects.values_list("id", "object_id", "adesivo", "quantidade")),
        )


class FichasQueSaoAdesivosTests(_NoAr):
    def test_o_air_game_kids_cand_vira_o_adesivo_candy(self):
        ficha_id = self.agk_cand.pk
        self.rodar()
        self.assertFalse(Brinquedos.objects.filter(pk=ficha_id).exists())
        agk = Brinquedos.objects.get(pk=self.agk.pk)
        self.assertEqual((agk.nome_brinquedo, agk.valor_brinquedo), ("Air Game Kids", Decimal("6990.00")))  # o preço não muda
        adesivos = list(agk.variantes_adesivo.order_by("-padrao", "ordem").values_list("nome", "slug", "padrao"))
        self.assertEqual(adesivos, [("Astronautas", "astronautas", True), ("Candy", "candy", False)])
        candy = agk.variantes_adesivo.get(slug="candy")
        self.assertEqual(candy.id_antigo, ficha_id)
        self.assertEqual([f.imagem.name for f in candy.fotos.all()], ["imagens_brinquedos/air-game-kids-candy.webp"])
        # o carrinho e o favorito vieram, o carrinho com o adesivo
        linha = ItemCarrinho.objects.get(pk=self.linha_cand.pk)
        self.assertEqual((linha.object_id, linha.adesivo), (agk.pk, "Candy"))
        self.assertEqual(Favorito.objects.get(usuario=self.usuario).brinquedo_id, agk.pk)
        # o endereço antigo vai para o produto
        resposta = self.client.get(reverse("brinquedo_detalhe", args=[ficha_id]))
        self.assertEqual((resposta.status_code, resposta["Location"]), (301, f"/brinquedo/{agk.pk}/"))

    def test_o_multijogos_32_polegadas_vira_o_adesivo_candy_do_multi_jogos(self):
        ficha_id = self.multi_32.pk
        self.rodar()
        self.assertFalse(Brinquedos.objects.filter(pk=ficha_id).exists())
        multi = Brinquedos.objects.get(pk=self.multi.pk)
        self.assertEqual((multi.nome_brinquedo, multi.valor_brinquedo), ("Multi Jogos", Decimal("9990.00")))
        adesivos = list(multi.variantes_adesivo.order_by("-padrao", "ordem").values_list("nome", "slug", "padrao"))
        self.assertEqual(adesivos, [("Padrão", "padrao", True), ("Candy", "candy", False)])
        from sistema_interno.models import ItemOrcamento

        self.assertEqual(ItemOrcamento.objects.get(pk=self.item_multi.pk).brinquedo_id, multi.pk)

    def test_as_aspas_de_polegada_em_outras_grafias(self):
        for grafia in ("Multijogos 32”", "Multijogos 32''", 'multijogos  32"', "MULTIJOGOS 32"):
            with self.subTest(grafia=grafia):
                Brinquedos.objects.filter(pk=self.multi_32.pk).update(nome_brinquedo=grafia)
                self.assertIsNotNone(variantes._achar_uma_grafia(variantes.FICHAS_QUE_SAO_ADESIVOS[1][1], Brinquedos))

    def test_o_balde_vira_um_produto_so_a_8500(self):
        sai, fica = self.balde.pk, self.balde_manual.pk
        self.rodar()
        self.assertFalse(Brinquedos.objects.filter(pk=sai).exists())
        balde = Brinquedos.objects.get(pk=fica)
        self.assertEqual((balde.nome_brinquedo, balde.valor_brinquedo, balde.voltz), ("Balde Giratório", Decimal("8500.00"), "Manual"))
        self.assertEqual((balde.altura_m, balde.largura_m, balde.profundidade_m), (Decimal("1.10"), Decimal("1.50"), Decimal("1.50")))
        self.assertEqual(list(balde.categorias_brinquedos.values_list("nome_categoria", flat=True)), ["Mecânicos"])
        adesivos = list(balde.variantes_adesivo.values_list("nome", "slug", "padrao", "id_antigo"))
        self.assertEqual(adesivos, [("Candy", "candy", True, sai)])
        self.assertEqual([f.imagem.name for f in balde.variantes_adesivo.get().fotos.all()],
                         ["imagens_brinquedos/balde-giratorio-candy.webp"])
        # as referências da ficha apagada (o carrinho e o orçamento) apontam para a que ficou
        self.assertEqual(ItemCarrinho.objects.get(pk=self.linha_balde.pk).object_id, fica)
        from sistema_interno.models import ItemOrcamento

        self.assertEqual(ItemOrcamento.objects.get(pk=self.item_balde.pk).brinquedo_id, fica)
        resposta = self.client.get(reverse("brinquedo_detalhe", args=[sai]))
        self.assertEqual((resposta.status_code, resposta["Location"]), (301, f"/brinquedo/{fica}/"))
        self.assertEqual(Brinquedos.objects.filter(nome_brinquedo__icontains="balde").count(), 2)  # o Balde e o Elétrico

    def test_os_vizinhos_de_nome_parecido_nao_sao_tocados(self):
        antes = {b.pk: (b.nome_brinquedo, b.valor_brinquedo) for b in (self.agk_premium, self.multi_42, self.balde_eletrico)}
        fotos_antes = ImagemBrinquedo.objects.count()
        self.rodar()
        for pk, (nome, preco) in antes.items():
            vizinho = Brinquedos.objects.get(pk=pk)
            self.assertEqual((vizinho.nome_brinquedo, vizinho.valor_brinquedo), (nome, preco))
        self.assertEqual(ImagemBrinquedo.objects.count(), fotos_antes)  # nenhuma foto se perde
        self.assertEqual(Brinquedos.objects.count(), 6)                 # 9 fichas - 3 apagadas

    def test_rodar_de_novo_nao_muda_nada(self):
        self.rodar()
        primeiro = self.retrato()
        self.rodar()
        self.rodar()
        self.assertEqual(self.retrato(), primeiro)

    def test_com_outro_nome_no_ar_a_ficha_nao_e_tocada(self):
        Brinquedos.objects.filter(pk=self.agk_cand.pk).update(nome_brinquedo="Air Game Kids Docinho")
        Brinquedos.objects.filter(pk=self.balde_manual.pk).update(nome_brinquedo="Balde Manual")
        feito = variantes.juntar_as_fichas_que_sao_adesivos(registro, avisar=_calado)
        unido = variantes.unir_as_fichas_repetidas(registro, avisar=_calado)
        self.assertEqual(feito[0], ("Air Game Kids", "Air Game Kids cand", "ficha não encontrada (já juntada, ou com outro nome)"))
        self.assertEqual(feito[1][2], "juntada")
        self.assertEqual(unido, [("Balde Giratório", "ficha não encontrada")])
        self.assertTrue(Brinquedos.objects.filter(pk=self.agk_cand.pk).exists())
        balde = Brinquedos.objects.get(pk=self.balde.pk)
        self.assertEqual((balde.nome_brinquedo, balde.valor_brinquedo), ("Balde giratório", Decimal("850000.00")))

    def test_sem_o_produto_a_ficha_fica(self):
        Brinquedos.objects.filter(pk=self.multi.pk).delete()
        self.rodar()
        self.assertTrue(Brinquedos.objects.filter(pk=self.multi_32.pk).exists())

    def test_o_adesivo_nao_tem_preco_proprio(self):
        self.rodar()
        self.assertFalse(any(campo.name.startswith(("valor", "preco")) for campo in VarianteAdesivo._meta.fields))
        pagina = self.client.get(reverse("brinquedo_detalhe", args=[self.agk.pk]) + "?adesivo=candy")
        self.assertEqual(pagina.status_code, 200)
        self.assertEqual(pagina.context["imagens_brinquedo"][0].imagem.name, "imagens_brinquedos/air-game-kids-candy.webp")
        self.assertNotIn("5.680", pagina.content.decode())

    def test_a_migracao_e_so_de_dados_e_a_xicara_fica_para_depois(self):
        self.assertEqual(migracao.Migration.dependencies, [("core", "0217_sinal_do_site")])
        self.assertEqual(len(migracao.Migration.operations), 1)
        nomes = " ".join(str(par) for par in variantes.FICHAS_QUE_SAO_ADESIVOS + variantes.FICHAS_REPETIDAS).lower()
        self.assertNotIn("xícara", nomes)
        self.assertNotIn("xicara", nomes)
