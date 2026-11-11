"""Os estados do mapa da home, coloridos pelo nível de pedidos de brinquedos.

O que estes testes protegem:

  * o estado vem certo de 'SP', 'sp', 'São Paulo' ou 'Sao Paulo', e o que
    não é estado não conta;
  * contam a proposta aprovada (no estado do primeiro endereço do cliente),
    o pedido pago da loja e o cliente do mapa sem proposta aprovada; não
    contam a proposta não aprovada nem o pedido cancelado ou esperando
    pagamento; o cliente do mapa com proposta aprovada não conta duas vezes;
  * a página recebe só o NÍVEL de cada estado e o rótulo da faixa, nunca o
    número de pedidos;
  * a home leva os dados dos estados, a malha e a logo de fundo para o mapa,
    e o botão "Pedidos por estado"; um erro na contagem não derruba a home;
  * a malha dos estados tem as 27 UFs e é leve.
"""

import json
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from core import mapa_estados
from core.models import Pedido
from sistema_interno.models import Cliente, EnderecoCliente, Orcamento


class UfTests(TestCase):
    def test_reconhece_sigla_e_nome_com_ou_sem_acento(self):
        for valor in ("SP", "sp", " São Paulo ", "Sao Paulo", "SÃO PAULO"):
            self.assertEqual(mapa_estados.uf_de(valor), "SP", valor)
        self.assertEqual(mapa_estados.uf_de("Rio Grande do Sul"), "RS")
        self.assertEqual(mapa_estados.uf_de("Distrito Federal"), "DF")

    def test_o_que_nao_e_estado_nao_conta(self):
        for valor in ("", None, "XX", "Buenos Aires", "Brasil"):
            self.assertEqual(mapa_estados.uf_de(valor), "", valor)

    def test_faixas(self):
        self.assertEqual(
            [mapa_estados.nivel_de(n) for n in (0, 1, 2, 3, 5, 6, 10, 11, 20, 21, 500)],
            [0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5],
        )


class ContagemTests(TestCase):
    def cliente(self, nome, estado):
        cliente = Cliente.objects.create(nome_cliente=nome)
        EnderecoCliente.objects.create(cliente=cliente, cidade="Cidade", estado=estado)
        return cliente

    def test_conta_aprovadas_loja_e_clientes_do_mapa(self):
        sp = self.cliente("Buffet SP", "São Paulo")
        rj = self.cliente("Parque RJ", "RJ")
        ba = self.cliente("Shopping BA", "ba")
        for _ in range(3):
            Orcamento.objects.create(cliente=sp, status=Orcamento.Status.APROVADO)
        Orcamento.objects.create(cliente=rj, status=Orcamento.Status.APROVADO)
        # não contam: proposta não aprovada
        Orcamento.objects.create(cliente=ba, status=Orcamento.Status.AGUARDANDO_RESPOSTA)
        Orcamento.objects.create(cliente=ba, status=Orcamento.Status.RECUSADO)
        # loja: pago conta, cancelado e esperando pagamento não
        Pedido.objects.create(status="pago", estado="MG")
        Pedido.objects.create(status="finalizado", estado="mg")
        Pedido.objects.create(status="cancelado", estado="MG")
        Pedido.objects.create(status="aguardando_pagamento", estado="MG")

        contagem = mapa_estados.pedidos_por_estado(
            # SP já tem aprovada (não conta de novo); BA está no mapa sem aprovada
            [(sp.pk, "SP"), (ba.pk, "Bahia")]
        )

        self.assertEqual(contagem, {"SP": 3, "RJ": 1, "MG": 2, "BA": 1})

    def test_fora_do_brasil_conta_no_pais(self):
        py = Cliente.objects.create(nome_cliente="Parque Asunción")
        EnderecoCliente.objects.create(cliente=py, cidade="Asunción", estado="Central", pais="Paraguai")
        us = Cliente.objects.create(nome_cliente="Mall Miami")
        EnderecoCliente.objects.create(cliente=us, cidade="Miami", estado="FL", pais="EUA")
        Orcamento.objects.create(cliente=py, status=Orcamento.Status.APROVADO)
        Orcamento.objects.create(cliente=py, status=Orcamento.Status.APROVADO)

        dados = mapa_estados.dados_do_mapa([(us.pk, "FL", "EUA"), (py.pk, "Central", "Paraguai")])

        self.assertEqual(dados["paises"], {"paraguai": 1, "estados unidos": 1})
        # "FL" não vira estado brasileiro, nem "Central"
        self.assertEqual(dados["niveis"], {})
        self.assertEqual(mapa_estados.pais_de("Brasil"), "")
        self.assertEqual(mapa_estados.pais_de("Paraguay"), "paraguay")

    def test_pagina_recebe_so_o_nivel_nunca_o_numero(self):
        cliente = self.cliente("Buffet SP", "SP")
        for _ in range(7):
            Orcamento.objects.create(cliente=cliente, status=Orcamento.Status.APROVADO)

        dados = mapa_estados.dados_do_mapa()

        self.assertEqual(dados["niveis"], {"SP": 3})
        self.assertEqual(dados["faixas"][2], {"nivel": 3, "rotulo": "6 a 10 pedidos"})
        self.assertEqual(dados["faixas"][-1]["rotulo"], "21 ou mais pedidos")
        self.assertNotIn("7", json.dumps(dados["niveis"]))


class HomeComEstadosTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_home_leva_estados_malha_e_logo_de_fundo(self):
        resposta = self.client.get("/")

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'id="dados-estados-onde"')
        self.assertContains(resposta, "site/dados/estados-br.json")
        self.assertContains(resposta, "site/dados/paises.json")
        self.assertContains(resposta, "images/logoofi-512.webp")
        self.assertContains(resposta, 'data-onde-camada="estados"')

    def test_erro_na_contagem_nao_derruba_a_home(self):
        with mock.patch.object(mapa_estados, "_contar", side_effect=RuntimeError("banco fora")):
            resposta = self.client.get("/")

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'id="dados-estados-onde"')
        # sem faixas, sem botão da camada
        self.assertNotContains(resposta, 'data-onde-camada="estados"')


class MalhaDosEstadosTests(TestCase):
    DADOS = Path(__file__).resolve().parent / "static" / "site" / "dados"

    def test_27_estados_e_leve(self):
        arquivo = self.DADOS / "estados-br.json"
        geo = json.loads(arquivo.read_text(encoding="utf-8"))

        self.assertEqual(sorted(f["id"] for f in geo["features"]), sorted(mapa_estados.UFS))
        self.assertLess(arquivo.stat().st_size, 150_000)

    def test_paises_sem_o_brasil_com_nome_em_portugues(self):
        arquivo = self.DADOS / "paises.json"
        geo = json.loads(arquivo.read_text(encoding="utf-8"))
        por_id = {f["id"]: f for f in geo["features"]}

        # o Brasil vai pelos estados: nenhum país "Brasil" por cima deles
        self.assertNotIn("BR", por_id)
        self.assertEqual(por_id["PY"]["properties"]["nome"], "Paraguai")
        self.assertEqual(por_id["US"]["properties"]["nome"], "Estados Unidos")
        self.assertIn("Paraguay", por_id["PY"]["properties"]["apelidos"])
        self.assertGreater(len(por_id), 150)
        self.assertLess(arquivo.stat().st_size, 250_000)
