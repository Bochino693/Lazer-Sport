from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth.models import User
from django.db import connection
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings

from .codigos_materiais import padronizar_codigos
from .models import EstoqueMaterial, Fornecedor, HistoricoCodigoMaterial, Material, MovimentoEstoque, TipoMaterial


class PadronizacaoTests(TestCase):
    def test_simulacao_aplicacao_e_idempotencia(self):
        tipo = TipoMaterial.objects.create(descricao="Arduino")
        antigo = Material.objects.create(nome_material="Nano", tipo_material=tipo, codigo_interno="0001")
        correto = Material.objects.create(nome_material="Uno", tipo_material=tipo)
        local = EstoqueMaterial.objects.create(material=antigo, descricao_local="A", quantidade=2, preco_fornecedor=10)
        previa = padronizar_codigos()
        self.assertEqual(len(previa), 1)
        antigo.refresh_from_db()
        self.assertEqual(antigo.codigo_interno, "0001")
        self.assertFalse(HistoricoCodigoMaterial.objects.exists())
        self.assertEqual(padronizar_codigos(aplicar=True), previa)
        antigo.refresh_from_db()
        self.assertEqual(antigo.codigo_interno, "ard-0002")
        self.assertEqual(local.material_id, antigo.pk)
        self.assertEqual(correto.codigo_interno, "ard-0001")
        self.assertEqual(HistoricoCodigoMaterial.objects.get().anterior, "0001")
        self.assertEqual(padronizar_codigos(aplicar=True), [])
        proximo = Material.objects.create(nome_material="Mega", tipo_material=tipo)
        self.assertEqual(proximo.codigo_interno, "ard-0003")

    def test_corrige_duplicados_e_reclassificados(self):
        tipo = TipoMaterial.objects.create(descricao="Arduino")
        a = Material.objects.create(nome_material="A", tipo_material=tipo, codigo_interno="ard-0001")
        b = Material.objects.create(nome_material="B", tipo_material=tipo, codigo_interno="ard-0001")
        c = Material.objects.create(nome_material="C", tipo_material=tipo, codigo_interno="mot-0001")
        padronizar_codigos(aplicar=True)
        for item in (a, b, c):
            item.refresh_from_db()
        self.assertEqual(len({a.codigo_interno, b.codigo_interno, c.codigo_interno}), 3)
        self.assertTrue(c.codigo_interno.startswith("ard-"))


class CustosEstoqueTests(TestCase):
    def setUp(self):
        self.material = Material.objects.create(nome_material="Arduino")
        self.estoque = EstoqueMaterial.objects.create(material=self.material, descricao_local="A", quantidade=0, preco_fornecedor=0)

    def compra(self, quantidade, preco, **extras):
        return MovimentoEstoque.registrar(self.estoque, "entrada", quantidade, valor_unitario=Decimal(preco), **extras)

    def test_duas_compras_precos_diferentes_e_saida(self):
        fornecedor = Fornecedor.objects.create(nome="Fornecedor A")
        primeira = self.compra(10, "10", fornecedor=fornecedor, documento="NF-1")
        segunda = self.compra(10, "20", documento="NF-2")
        self.estoque.refresh_from_db()
        self.assertEqual(self.estoque.valor_total, Decimal("300"))
        self.assertEqual(self.estoque.preco_fornecedor, Decimal("15"))
        saida = MovimentoEstoque.registrar(self.estoque, "saida", 4, valor_unitario=999)
        self.estoque.refresh_from_db()
        self.assertEqual(saida.valor_total, Decimal("60"))
        self.assertEqual(self.estoque.valor_total, Decimal("240"))
        primeira.refresh_from_db()
        self.assertEqual(primeira.valor_total, Decimal("100"))
        self.assertEqual(segunda.valor_total, Decimal("200"))
        fornecedor.nome = "Nome alterado"
        fornecedor.save()
        self.assertEqual(primeira.fornecedor_nome, "Fornecedor A")

    def test_arredondamento_nao_perde_centavos_e_ajuste_zero(self):
        self.compra(1, "1")
        self.compra(2, "0")
        for _ in range(3):
            MovimentoEstoque.registrar(self.estoque, "saida", 1)
        self.estoque.refresh_from_db()
        self.assertEqual(self.estoque.valor_total, Decimal("0"))
        self.assertEqual(sum(-m.variacao_valor for m in self.estoque.movimentos.filter(tipo="saida")), Decimal("1"))
        self.compra(3, "5")
        ajuste = MovimentoEstoque.registrar(self.estoque, "ajuste", 0, motivo="Inventário físico")
        self.assertEqual(ajuste.variacao_valor, Decimal("-15"))
        self.estoque.refresh_from_db()
        self.assertEqual((self.estoque.quantidade, self.estoque.valor_total), (0, Decimal("0")))

    def test_validacao_nao_altera_saldo(self):
        for tipo, quantidade, extras in [
            ("entrada", 1, {}), ("entrada", 1, {"valor_unitario": -1}),
            ("saida", 1, {}), ("ajuste", 1, {}), ("invalido", 1, {}),
        ]:
            with self.subTest(tipo=tipo, extras=extras):
                with self.assertRaises(ValueError):
                    MovimentoEstoque.registrar(self.estoque, tipo, quantidade, **extras)
        self.estoque.refresh_from_db()
        self.assertEqual(self.estoque.quantidade, 0)
        self.assertFalse(self.estoque.movimentos.exists())

    def test_historico_protegido_e_saldo_legado_identificado(self):
        self.compra(2, "10")
        with self.assertRaises(ProtectedError):
            self.estoque.delete()
        with self.assertRaises(ProtectedError):
            self.material.delete()
        migracao = import_module("sistema_interno.migrations.0052_saldos_iniciais_custos")
        migracao.preencher(apps, SimpleNamespace(connection=connection))
        self.estoque.refresh_from_db()
        self.assertTrue(self.estoque.custo_estimado)
        movimento = MovimentoEstoque.registrar(self.estoque, "saida", 2)
        self.assertTrue(movimento.custo_estimado)
        self.estoque.refresh_from_db()
        self.assertFalse(self.estoque.custo_estimado)


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class FluxoCustosTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser("gestor-custos", "gestor@example.com", "x"))
        self.tipo = TipoMaterial.objects.create(descricao="Arduino")
        self.material = Material.objects.create(nome_material="Nano", tipo_material=self.tipo, codigo_interno="antigo-nano")
        self.estoque = EstoqueMaterial.objects.create(material=self.material, descricao_local="A", quantidade=0, preco_fornecedor=0)

    def post(self, url, dados):
        return self.client.post(url, dados, HTTP_HOST="interno.testserver", HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def test_previa_confirmacao_busca_legada_e_material_sem_investido(self):
        url = "/estoque/materiais/"
        self.assertEqual(self.post(url, {"action": "prever_codigos"}).status_code, 200)
        self.assertEqual(self.post(url, {"action": "padronizar_codigos"}).status_code, 400)
        self.assertEqual(self.post(url, {"action": "padronizar_codigos", "confirmacao": "PADRONIZAR"}).status_code, 200)
        resposta = self.client.get(url, {"q": "antigo-nano"}, HTTP_HOST="interno.testserver")
        self.assertEqual(len(resposta.context["materiais"]), 1)
        self.assertNotContains(resposta, '<th class="text-end">Investido</th>')

    def test_edicao_nao_reprecifica_e_exclusao_nao_apaga_compras(self):
        MovimentoEstoque.registrar(self.estoque, "entrada", 10, valor_unitario=10)
        resposta = self.post("/stock/", {"action": "save", "id": self.estoque.pk, "material": self.material.pk, "descricao_local": "A", "preco_fornecedor": "999,00"})
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.estoque.refresh_from_db()
        self.assertEqual(self.estoque.valor_total, Decimal("100"))
        self.assertEqual(self.estoque.preco_fornecedor, Decimal("10"))
        resposta = self.post("/stock/", {"action": "delete", "id": self.estoque.pk})
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(self.estoque.movimentos.count(), 1)

    def test_resumo_usa_todos_os_registros_e_nao_so_400(self):
        MovimentoEstoque.objects.bulk_create([
            MovimentoEstoque(estoque=self.estoque, tipo="entrada", quantidade=1, valor_unitario=2)
            for _ in range(405)
        ])
        resposta = self.client.get("/estoque/movimentacoes/", HTTP_HOST="interno.testserver")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["valor_comprado"], Decimal("810"))
        self.assertEqual(resposta.context["total_movimentos"], 405)
        self.assertEqual(len(resposta.context["movimentos"]), 50)
        ultima = self.client.get("/estoque/movimentacoes/", {"page": "9"}, HTTP_HOST="interno.testserver")
        self.assertEqual(len(ultima.context["movimentos"]), 5)
        self.assertEqual(ultima.context["valor_comprado"], Decimal("810"))
