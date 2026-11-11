"""Os estados do mapa da home, coloridos pelo nível de pedidos de brinquedos.

O que estes testes protegem:

  * o estado vem certo de 'SP', 'sp', 'São Paulo' ou 'Sao Paulo', e o que
    não é estado não conta;
  * só conta quem tem alfinete: cada cliente do mapa vale as propostas
    aprovadas dele (pelo menos 1); proposta ou compra de quem não está no
    mapa não pinta nada (antes o Paraná saía colorido sem alfinete);
  * o estado (ou país) sai da coordenada do alfinete, não do texto do
    endereço; Fernando de Noronha é Pernambuco;
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


class RegiaoDoAlfineteTests(TestCase):
    """O estado (ou país) sai da COORDENADA do alfinete, não do texto."""

    def test_vale_onde_o_alfinete_esta(self):
        # endereço diz "SP", mas o ponto é Curitiba: quem pinta é o Paraná
        self.assertEqual(mapa_estados.regiao_do_ponto(-25.43, -49.27, "SP", ""), ("estado", "PR"))
        self.assertEqual(mapa_estados.regiao_do_ponto(-23.55, -46.63, "", ""), ("estado", "SP"))
        self.assertEqual(mapa_estados.regiao_do_ponto(-25.26, -57.58, "Central", "Paraguai"), ("pais", "PY"))
        self.assertEqual(mapa_estados.regiao_do_ponto(40.7, -74.0, "NY", "EUA"), ("pais", "US"))

    def test_ilhas_e_pontos_fora_da_malha(self):
        # Fernando de Noronha é Pernambuco (a malha de origem dizia RN)
        self.assertEqual(mapa_estados.regiao_do_ponto(-3.85, -32.42, "PE", ""), ("estado", "PE"))
        # no mar, longe de tudo: nada
        self.assertEqual(mapa_estados.regiao_do_ponto(-23.0, -40.0, "", ""), ("", ""))
        # sem coordenada: o endereço
        self.assertEqual(mapa_estados.regiao_do_ponto(None, None, "Bahia", ""), ("estado", "BA"))


class ContagemTests(TestCase):
    def cliente(self, nome):
        return Cliente.objects.create(nome_cliente=nome)

    def test_so_conta_quem_tem_alfinete(self):
        sp = self.cliente("Buffet SP")
        rj = self.cliente("Parque RJ")
        fora_do_mapa = self.cliente("Cliente do Paraná sem alfinete")
        EnderecoCliente.objects.create(cliente=fora_do_mapa, cidade="Curitiba", estado="PR")
        for _ in range(3):
            Orcamento.objects.create(cliente=sp, status=Orcamento.Status.APROVADO)
        # não aprovada não pesa
        Orcamento.objects.create(cliente=rj, status=Orcamento.Status.AGUARDANDO_RESPOSTA)
        # quem não está no mapa não pinta nada, nem a compra da loja
        Orcamento.objects.create(cliente=fora_do_mapa, status=Orcamento.Status.APROVADO)
        Pedido.objects.create(status="pago", estado="PR")

        contagem = mapa_estados.pedidos_por_estado(
            [(sp.pk, "estado", "SP"), (rj.pk, "estado", "RJ")]
        )

        # SP: as 3 aprovadas do cliente; RJ: está no mapa, conta 1; PR: nada
        self.assertEqual(contagem, {"SP": 3, "RJ": 1})

    def test_fora_do_brasil_conta_no_pais(self):
        py = self.cliente("Parque Asunción")
        Orcamento.objects.create(cliente=py, status=Orcamento.Status.APROVADO)
        Orcamento.objects.create(cliente=py, status=Orcamento.Status.APROVADO)

        dados = mapa_estados.dados_do_mapa([(py.pk, "pais", "PY")])

        self.assertEqual(dados["paises"], {"PY": 1})
        self.assertEqual(dados["niveis"], {})

    def test_pagina_recebe_so_o_nivel_nunca_o_numero(self):
        cliente = self.cliente("Buffet SP")
        for _ in range(7):
            Orcamento.objects.create(cliente=cliente, status=Orcamento.Status.APROVADO)

        dados = mapa_estados.dados_do_mapa([(cliente.pk, "estado", "SP")])

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

    def test_a_cor_e_o_cartao_seguem_o_alfinete(self):
        # O cadastro diz "SP", mas o alfinete está em Curitiba: o mapa pinta
        # o Paraná e o cartão do Paraná lista esse cliente. E um pedido de
        # quem não está no mapa (Bahia) não pinta a Bahia.
        cliente = Cliente.objects.create(
            nome_cliente="Responsável", nome_estabelecimento="Parque Curitiba",
            telefone="(41) 90000-0000", publicar_no_mapa=True,
        )
        EnderecoCliente.objects.create(
            cliente=cliente, endereco="Rua A", cidade="Curitiba", estado="SP",
            latitude="-25.4284", longitude="-49.2733",
        )
        escondido = Cliente.objects.create(nome_cliente="Sem mapa", telefone="(71) 90000-0000")
        EnderecoCliente.objects.create(cliente=escondido, endereco="Rua B", cidade="Salvador", estado="BA")
        Orcamento.objects.create(cliente=escondido, status=Orcamento.Status.APROVADO)

        resposta = self.client.get("/")
        estados = resposta.context["estados_mapa"]
        pontos = resposta.context["pontos_mapa"]

        self.assertEqual(estados["niveis"], {"PR": 1})
        curitiba = next(p for p in pontos if p.get("cidade") == "Curitiba")
        self.assertEqual(curitiba["uf"], "PR")
        self.assertEqual(curitiba["pais_id"], "")

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
