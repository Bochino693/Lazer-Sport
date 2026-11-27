"""Com ou sem moedeiro: a regra, a configuração e a conta (LEIA-ME-V10, seção 143).

O dono: "os moedeiros nas máquinas, que não são brinquedões, arenas
esportivas nem esses brinquedões grandes, têm dois preços com moedeiro ou sem."

PRIMEIRA FATIA (dados SINTÉTICOS): o acréscimo único que a Gestão digita, a
regra de quem aceita (máquina sim; brinquedão, kit e quem a Gestão desligou,
não) e o preço calculado no servidor. Enquanto o acréscimo está vazio, a
opção não existe.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from core.models import Brinquedos, CategoriasBrinquedos

from . import moedeiro, montagem
from .models import DadosContrato
from .permissoes import atribuir_funcoes

AJAX = {"HTTP_HOST": "interno.testserver", "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
INTERNO = {"HTTP_HOST": "interno.testserver"}


def maquina(nome, preco="6990.00", **campos):
    return Brinquedos.objects.create(
        nome_brinquedo=nome, descricao="x", valor_brinquedo=Decimal(preco) if preco else None,
        avaliacao=5, voltz="220V", **campos,
    )


def definir_acrescimo(valor):
    dados = DadosContrato.atual()
    dados.acrescimo_moedeiro = Decimal(valor) if valor is not None else None
    dados.save()


class RegraDoMoedeiroTests(TestCase):
    def setUp(self):
        cache.clear()
        self.fliperama = maquina("Fliperama Sintético")
        self.brinquedao = maquina("Brinquedão Sintético Modelo 9", "85000.00")
        categoria = CategoriasBrinquedos.objects.create(nome_categoria="Brinquedão", imagem_categoria="c/b.png")
        self.brinquedao.categorias_brinquedos.add(categoria)
        montagem.configuracao().categorias_projeto.add(categoria)
        self.kit = maquina("Kit Eletrônico Sintético", "1200.00", eh_kit=True)
        cache.clear()

    def test_sem_o_acrescimo_a_opcao_nao_existe(self):
        for vazio in (None, "0", "0.00"):
            with self.subTest(acrescimo=vazio):
                definir_acrescimo(vazio)
                self.assertFalse(moedeiro.ativo())
                self.assertEqual(moedeiro.acrescimo(), Decimal("0.00"))
                self.assertFalse(moedeiro.oferece(self.fliperama))
                self.assertEqual(moedeiro.opcoes(self.fliperama), [])
                # pedir "com moedeiro" sem a opção devolve o preço do cadastro
                self.assertEqual(moedeiro.preco(self.fliperama, True), Decimal("6990.00"))

    def test_maquina_aceita_e_brinquedao_e_kit_nao(self):
        definir_acrescimo("350.00")
        self.assertTrue(moedeiro.aceita(self.fliperama))
        self.assertFalse(moedeiro.aceita(self.brinquedao))   # a categoria marcada nas regras da produção
        self.assertFalse(moedeiro.aceita(self.kit))
        self.assertFalse(moedeiro.aceita(None))
        self.assertFalse(moedeiro.aceita(maquina("Trampolim Sintético Gigante")))  # a palavra no nome

    def test_a_gestao_liga_e_desliga_por_maquina(self):
        definir_acrescimo("350.00")
        self.fliperama.moedeiro = "nao"
        self.brinquedao.moedeiro = "sim"
        self.assertFalse(moedeiro.oferece(self.fliperama))
        self.assertTrue(moedeiro.oferece(self.brinquedao))
        self.assertEqual(moedeiro.preco(self.fliperama, True), Decimal("6990.00"))
        self.assertEqual(moedeiro.preco(self.brinquedao, True), Decimal("85350.00"))

    def test_o_preco_com_moedeiro_e_o_do_cadastro_mais_o_acrescimo(self):
        definir_acrescimo("350.00")
        self.assertEqual(moedeiro.preco(self.fliperama), Decimal("6990.00"))        # o cadastro é o SEM moedeiro
        self.assertEqual(moedeiro.preco(self.fliperama, True), Decimal("7340.00"))
        self.assertEqual(
            [(o["rotulo"], o["com_moedeiro"], o["preco"]) for o in moedeiro.opcoes(self.fliperama)],
            [("Sem sistema de ficha", False, Decimal("6990.00")), ("Com sistema de ficha", True, Decimal("7340.00"))],
        )
        # quem não aceita nunca ganha o acréscimo, nem pedindo
        self.assertEqual(moedeiro.preco(self.brinquedao, True), Decimal("85000.00"))
        self.assertEqual(moedeiro.opcoes(self.brinquedao), [])
        self.assertIsNone(moedeiro.preco(maquina("Máquina Sem Preço Sintética", None), True))

    def test_o_cadastro_novo_nasce_pela_regra(self):
        self.assertEqual(Brinquedos._meta.get_field("moedeiro").default, "")
        self.assertEqual(self.fliperama.moedeiro, "")
        # o valor que o dono deu (a migração 0086, seção 148)
        self.assertEqual(DadosContrato.atual().acrescimo_moedeiro, Decimal("999.00"))


class TelaDoAcrescimoTests(TestCase):
    def setUp(self):
        cache.clear()
        self.gestora = User.objects.create_user("gestora-ficha", password="senha-de-teste")
        atribuir_funcoes(self.gestora, ("gestao",))
        self.vendedor = User.objects.create_user("vendedor-ficha", password="senha-de-teste")
        atribuir_funcoes(self.vendedor, ("vendas",))

    def salvar(self, usuario=None, **troca):
        self.client.force_login(usuario or self.gestora)
        dados = {
            "action": "salvar", "nome_fantasia": "Brinquedos Lazer & Sport",
            "razao_social": "Fábrica de Brinquedos Lazer & Sport Oficial – LTDA", "cnpj": "54.486.908/0001-86",
            "endereco_sede": "Rua São Roque de Minas, n. 104, Jardim Peri, São Paulo, Capital", "cidade": "São Paulo",
        }
        dados.update(troca)
        return self.client.post("/orcamentos/dados-do-contrato/", dados, **AJAX)

    def test_a_gestao_digita_o_acrescimo_em_reais(self):
        for digitado, esperado in (("350", "350.00"), ("350,00", "350.00"), ("1.250,50", "1250.50"), ("R$ 99,9", "99.90")):
            with self.subTest(digitado=digitado):
                self.assertEqual(self.salvar(acrescimo_moedeiro=digitado).status_code, 200)
                self.assertEqual(DadosContrato.atual().acrescimo_moedeiro, Decimal(esperado))
                self.assertTrue(moedeiro.ativo())

    def test_vazio_ou_zero_desliga_a_opcao(self):
        self.salvar(acrescimo_moedeiro="350,00")
        for digitado in ("", "0", "0,00"):
            with self.subTest(digitado=digitado):
                self.assertEqual(self.salvar(acrescimo_moedeiro=digitado).status_code, 200)
                self.assertIsNone(DadosContrato.atual().acrescimo_moedeiro)
                self.assertFalse(moedeiro.ativo())

    def test_valor_invalido_volta_com_o_campo_e_nao_grava(self):
        self.salvar(acrescimo_moedeiro="350,00")
        for digitado in ("abc", "-5", "1e9", "12,3,4"):
            with self.subTest(digitado=digitado):
                resposta = self.salvar(acrescimo_moedeiro=digitado)
                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.json().get("campo"), "acrescimo_moedeiro")
                self.assertEqual(DadosContrato.atual().acrescimo_moedeiro, Decimal("350.00"))

    def test_so_a_gestao_muda(self):
        resposta = self.salvar(self.vendedor, acrescimo_moedeiro="123,00")
        self.assertNotEqual(resposta.status_code, 200)
        self.assertEqual(DadosContrato.atual().acrescimo_moedeiro, Decimal("999.00"))

    def test_a_tela_mostra_o_campo_e_o_que_ele_faz(self):
        self.client.force_login(self.gestora)
        definir_acrescimo(None)
        html = self.client.get("/orcamentos/dados-do-contrato/", **INTERNO).content.decode()
        self.assertIn('name="acrescimo_moedeiro"', html)
        self.assertIn("Vazio: a opção “com sistema de ficha” não aparece em lugar nenhum.", html)
        # o nome que a pessoa lê é "Sistema de ficha" (seção 148), nunca "moedeiro"
        self.assertIn("Sistema de ficha", html)
        self.assertIn("operações, eventos e afins", html)
        visivel = html.replace('name="acrescimo_moedeiro"', "").replace("dcAjudaMoedeiro", "")
        onde = visivel.lower().find("moedeiro")
        self.assertEqual(onde, -1, visivel[max(onde - 120, 0):onde + 60])
        self.salvar(acrescimo_moedeiro="350,00")
        html = self.client.get("/orcamentos/dados-do-contrato/", **INTERNO).content.decode()
        self.assertIn('value="350,00"', html)
        self.assertIn("preço do cadastro + R$ 350,00", html)
        self.assertNotIn("<select", html)

    def test_as_migracoes_de_esquema_nao_tem_runpython(self):
        import importlib

        from django.db import migrations

        for caminho in ("core.migrations.0219_moedeiro_por_maquina",
                        "sistema_interno.migrations.0083_acrescimo_do_moedeiro"):
            operacoes = importlib.import_module(caminho).Migration.operations
            self.assertTrue(all(isinstance(o, migrations.AddField) for o in operacoes), caminho)
        dados = importlib.import_module("core.migrations.0218_fichas_que_sao_adesivos").Migration.operations
        self.assertTrue(all(isinstance(o, migrations.RunPython) for o in dados))


# ======================================================================
# O NOME, O VALOR E O LIGA/DESLIGA POR MÁQUINA (LEIA-ME-V10, seção 148)
# ======================================================================
class NomeEValorTests(TestCase):
    def test_a_marca_no_nome_do_item(self):
        com = moedeiro.nome_com_a_escolha
        self.assertEqual(com("Air Game Premium", True), "Air Game Premium — com sistema de ficha")
        self.assertEqual(com("Air Game Premium — com sistema de ficha", True), "Air Game Premium — com sistema de ficha")
        self.assertEqual(com("Air Game Premium — com sistema de ficha", False), "Air Game Premium")
        self.assertEqual(com("Air Game Premium — adesivo Candy", True), "Air Game Premium — adesivo Candy — com sistema de ficha")
        # quem encurta é o nome, nunca a marca
        longo = com("M" * 200, True, limite=180)
        self.assertEqual(len(longo), 180)
        self.assertTrue(longo.endswith(moedeiro.SUFIXO))
        self.assertTrue(moedeiro.tem_a_marca("Fliperama — COM SISTEMA DE FICHA"))
        self.assertFalse(moedeiro.tem_a_marca("Fliperama"))

    def test_a_migracao_do_valor_so_preenche_o_vazio_e_e_idempotente(self):
        import importlib

        from django.apps import apps
        from django.db import migrations

        modulo = importlib.import_module("sistema_interno.migrations.0086_acrescimo_do_sistema_de_ficha")
        self.assertTrue(all(isinstance(o, migrations.RunPython) for o in modulo.Migration.operations))
        textos = importlib.import_module("sistema_interno.migrations.0085_textos_do_sistema_de_ficha")
        self.assertTrue(all(isinstance(o, migrations.AlterField) for o in textos.Migration.operations))
        for antes, depois in ((None, "999.00"), ("0", "999.00"), ("999.00", "999.00"), ("1250.50", "1250.50")):
            with self.subTest(antes=antes):
                definir_acrescimo(antes)
                modulo.preencher(apps, None)
                modulo.preencher(apps, None)
                moedeiro.esquecer()
                self.assertEqual(DadosContrato.atual().acrescimo_moedeiro, Decimal(depois))
        # sem a linha de Dados do contrato, nada quebra e nada é criado
        DadosContrato.objects.all().delete()
        modulo.preencher(apps, None)
        self.assertFalse(DadosContrato.objects.exists())


class CadastroDaMaquinaTests(TestCase):
    """O liga/desliga por máquina na tela do cadastro do brinquedo."""

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_superuser("admin-ficha", "admin@exemplo.test", "senha-de-teste")
        self.client.force_login(self.admin)
        self.maquina = maquina("Fliperama Sintético", imagem_brinquedo="imagens_brinquedos/fliperama-sintetico.jpg")

    def salvar(self, **troca):
        dados = {
            "action": "save", "id": self.maquina.pk, "nome_brinquedo": "Fliperama Sintético", "descricao": "x",
            "valor_brinquedo": "6.990,00", "avaliacao": "5", "voltz": "220V",
        }
        dados.update(troca)
        return self.client.post("/site/brinquedos/", dados, **AJAX)

    def test_a_tela_tem_os_tres_chips_sem_select(self):
        html = self.client.get("/site/brinquedos/", **INTERNO).content.decode()
        for valor in ("", "sim", "nao"):
            self.assertIn(f'name="moedeiro" value="{valor}"', html)
        self.assertIn("Sistema de ficha", html)
        self.assertIn("do cadastro + R$ 999,00", html)
        trecho = html[html.index('id="toyFicha"'):html.index('id="toyFichaAjuda"')]
        self.assertNotIn("<select", trecho)

    def test_grava_a_palavra_da_gestao_e_volta_para_a_regra(self):
        for escolha in ("nao", "sim", ""):
            with self.subTest(escolha=escolha):
                resposta = self.salvar(moedeiro=escolha)
                self.assertEqual(resposta.status_code, 200, resposta.content[:300])
                self.maquina.refresh_from_db()
                self.assertEqual(self.maquina.moedeiro, escolha)
        self.maquina.moedeiro = "nao"
        self.maquina.save()
        self.assertFalse(moedeiro.oferece(self.maquina))

    def test_valor_inventado_e_recusado(self):
        resposta = self.salvar(moedeiro="talvez")
        self.assertNotEqual(resposta.status_code, 200)
        self.maquina.refresh_from_db()
        self.assertEqual(self.maquina.moedeiro, "")
