"""Toda tela do painel abre -- e nenhuma abre com erro.

É o teste mais chato de escrever e o que mais paga. Um `import` que some,
um campo renomeado, uma propriedade que virou consulta: nada disso aparece
na tela que se estava mexendo, e sim numa outra, semanas depois, quando
alguém do escritório clica no menu e leva um 500.

A varredura sai da própria lista de rotas (`sistema_interno.urls`). Isso
importa: rota nova entra no teste sozinha, sem ninguém lembrar de
adicioná-la aqui. Uma tela que não pode ser aberta por GET declara-se
abaixo, com o motivo escrito.
"""

import re
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from . import urls as rotas_internas
from .models import (
    Cliente,
    ItemOrcamento,
    Orcamento,
    OrdemProducao,
    OrdemServico,
    ProdutoInterno,
)


# Rotas que existem para receber POST ou parâmetro, e não para serem
# abertas. Cada uma diz por quê -- a lista não é lugar de esconder tela
# quebrada.
SO_POST = {
    "lembrar_cliente": "atalho da fila de urgências; envia lembrete",
    "categoria_new": "cria categoria a partir do modal",
    "tag_new": "cria tag a partir do modal",
    "banner_delete": "exclusão, nunca por link",
    "campanha_criar": "cria campanha",
    "campanha_whatsapp": "registra o disparo de WhatsApp",
    "atualizar_etapa_producao": "avança etapa da ordem",
    "logout_inner": "encerra a sessão",
}
EXIGEM_PARAMETRO = {
    "campanha_ofertas": "precisa do cliente escolhido",
    "campanha_preparar": "precisa da oferta escolhida",
    "consultar_cep_inner": "precisa do CEP",
}


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class TodasAsTelasAbremTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.chefe = User.objects.create_superuser(
            username="chefe-varredura", password="x", email="c@example.com",
        )
        cls.cliente_cadastrado = Cliente.objects.create(
            nome_cliente="Buffet Alegria", telefone="(11) 97777-6655",
        )
        cls.orcamento = Orcamento.objects.create(
            nome_cliente="Buffet Alegria", email_cliente="c@example.com",
            cliente=cls.cliente_cadastrado,
            validade=timezone.localdate() + timedelta(days=5),
            responsavel=cls.chefe,
        )
        ItemOrcamento.objects.create(
            orcamento=cls.orcamento, descricao="Cama elástica",
            quantidade=1, valor_unitario=Decimal("500.00"),
        )
        cls.ordem = OrdemServico.objects.create(
            nome_cliente="Buffet Alegria", cliente=cls.cliente_cadastrado,
            equipamento="Tobogã",
        )
        cls.producao = OrdemProducao.objects.create(
            produto=ProdutoInterno.objects.create(nome="Cama elástica 3m"),
            quantidade=1,
        )
        # Registrar pagamento é o que cria a venda -- é assim que ela
        # nasce no sistema, e é assim que a varredura deve encontrá-la.
        cls.venda = cls.orcamento.registrar_pagamento(Decimal("200.00"))

    def setUp(self):
        self.client.force_login(self.chefe)

    def valor_do_parametro(self, nome_rota, parametro):
        if parametro == "pk":
            return {
                "orcamento_previa_inner": self.orcamento.pk,
                "ordem_servico_previa_inner": self.ordem.pk,
                "dossie_cliente": self.cliente_cadastrado.pk,
                "producao_ordem_detalhe": self.producao.pk,
                "atualizar_etapa_producao": self.producao.pk,
                "venda_previa_inner": self.venda.pk,
            }.get(nome_rota, 1)
        if parametro.endswith("token"):
            return "00000000-0000-0000-0000-000000000000"
        return 1

    def caminho(self, rota):
        padrao = str(rota.pattern)
        return "/" + re.sub(
            r"<(?:\w+:)?(\w+)>",
            lambda achado: str(self.valor_do_parametro(rota.name, achado.group(1))),
            padrao,
        )

    def test_nenhuma_rota_do_painel_responde_com_erro(self):
        problemas = []

        for rota in rotas_internas.urlpatterns:
            nome = rota.name
            if nome in SO_POST:
                continue

            caminho = self.caminho(rota)
            try:
                resposta = self.client.get(caminho, HTTP_HOST="interno.testserver")
                codigo = resposta.status_code
            except Exception as erro:  # noqa: BLE001
                problemas.append(
                    "%s (%s): explodiu -- %s: %s"
                    % (nome, caminho, type(erro).__name__, erro)
                )
                continue

            # 400 é resposta correta de quem foi aberto sem o parâmetro que
            # a tela sempre manda; 404, de um token inventado.
            esperados = {200, 302}
            if nome in EXIGEM_PARAMETRO:
                esperados.add(400)
            if nome == "campanha_detalhe":
                esperados.add(404)

            if codigo not in esperados:
                problemas.append("%s (%s): HTTP %s" % (nome, caminho, codigo))

        self.assertEqual(
            problemas, [],
            "Estas telas do painel não abrem:\n  " + "\n  ".join(problemas),
        )

    def test_as_rotas_de_post_recusam_o_GET_em_vez_de_explodir(self):
        """405 é a resposta certa; 500 seria a errada."""
        for rota in rotas_internas.urlpatterns:
            if rota.name not in SO_POST:
                continue
            with self.subTest(rota=rota.name, motivo=SO_POST[rota.name]):
                resposta = self.client.get(
                    self.caminho(rota), HTTP_HOST="interno.testserver",
                )
                self.assertIn(resposta.status_code, (302, 400, 403, 404, 405))
