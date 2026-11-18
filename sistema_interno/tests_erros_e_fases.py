"""Os erros 500 e as fases indefinidas achados na varredura (LEIA-ME-V10, seção 111).

O pedido do dono: "tenho erros 500 nos pedidos, visualização de assinatura e
etc, além de troca de fases indefinidas". A varredura percorreu todas as
rotas do painel com cada papel, cada transição oferecida pela interface e as
páginas do cliente, no SQLite E num PostgreSQL local (o banco do ar). O que
ela achou, e o que estes testes seguram:

  1. A RESPOSTA DO CLIENTE NA PROPOSTA (aprovar, pedir ajustes, recusar)
     estourava 500 no PostgreSQL: "FOR UPDATE cannot be applied to the
     nullable side of an outer join". O SQLite ignora a trava, então a
     suíte passava. O teste monta o SQL que o PostgreSQL receberia;
  2. A PROPOSTA ASSINADA OU PAGA VIRAVA "Recusada" pelo "Situação" do
     painel -- com a venda na receita e o termo assinado apontando para
     uma proposta recusada;
  3. O TOQUE NA CÉLULA "Acompanhamento" da lista abria a janela "Mudar
     situação" sem a situação de agora (a célula e o botão tinham o mesmo
     `data-situacao`), e a janela tinha uma lista suspensa;
  4. A FOLHA DO ANDAMENTO DO PEDIDO listava os passos sem dizer o sentido:
     "Pago" aparecia como se fosse a fase seguinte de um pedido em
     preparação.
"""

import re
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase

from core.models import Carrinho, ItemPedido, Pedido
from sistema_interno import documento_assinatura as svc
from sistema_interno.models import Cliente, ItemOrcamento, Orcamento
from sistema_interno.permissoes import atribuir_funcoes

INTERNO = {"HTTP_HOST": "interno.testserver"}
AJAX = {"HTTP_HOST": "interno.testserver", "HTTP_X_REQUESTED_WITH": "XMLHttpRequest",
        "HTTP_ACCEPT": "application/json"}


def sql_do_postgres(consulta):
    """O SQL que o PostgreSQL receberia -- sem precisar de um PostgreSQL.

    A suíte roda no SQLite, que ignora `select_for_update`. O compilador
    do backend do PostgreSQL monta a mesma consulta que iria ao ar.
    """
    from django.db.backends.postgresql.base import DatabaseWrapper

    ajustes = dict(connection.settings_dict)
    ajustes.update({"ENGINE": "django.db.backends.postgresql", "NAME": "sem-conexao"})
    postgres = DatabaseWrapper(ajustes, alias="postgres-sem-conexao")
    # a trava exige "dentro de uma transação": finge a conexão aberta
    postgres.connection = object()
    postgres.autocommit = False
    sql, _ = consulta.query.get_compiler(connection=postgres).as_sql()
    return sql


def trava_que_o_postgres_recusa(sql):
    """"FOR UPDATE" puro com LEFT OUTER JOIN: o PostgreSQL recusa (500 no ar)."""
    return "LEFT OUTER JOIN" in sql and re.search(r"FOR UPDATE(?! OF)", sql) is not None


def equipe(username, *funcoes):
    user = User.objects.create_user(username=username, password="x")
    atribuir_funcoes(user, funcoes)
    return user


def orcamento_aprovado(**campos):
    padrao = {
        "nome_cliente": "Buffet Fases", "whatsapp_cliente": "(11) 97777-6655",
        "status": Orcamento.Status.APROVADO, "forma_pagamento": "Pix",
    }
    padrao.update(campos)
    orcamento = Orcamento.objects.create(**padrao)
    ItemOrcamento.objects.create(
        orcamento=orcamento, descricao="Air Game Kids", quantidade=1, valor_unitario=Decimal("5000"),
    )
    return orcamento


# ======================================================================
# 1. A RESPOSTA DO CLIENTE NA PROPOSTA, NO POSTGRESQL
# ======================================================================
class TravaDaPropostaNoPostgresTests(TestCase):

    def test_o_detector_reconhece_a_trava_que_o_postgres_recusa(self):
        """O teste abaixo só vale se o detector pegar o caso de verdade."""
        ruim = Orcamento.objects.select_related("cliente").select_for_update()
        boa = Orcamento.objects.select_related("cliente").select_for_update(of=("self",))
        self.assertTrue(trava_que_o_postgres_recusa(sql_do_postgres(ruim)))
        self.assertFalse(trava_que_o_postgres_recusa(sql_do_postgres(boa)))

    def test_a_proposta_travada_para_a_resposta_so_trava_a_linha_dela(self):
        from core import views_orcamento

        orcamento = orcamento_aprovado(status=Orcamento.Status.AGUARDANDO_RESPOSTA)
        vistas = []
        original = views_orcamento.get_object_or_404

        def espiar(consulta, **filtros):
            vistas.append(consulta)
            return original(consulta, **filtros)

        with mock.patch.object(views_orcamento, "get_object_or_404", espiar):
            views_orcamento.carregar_orcamento_exibicao(token=orcamento.token, bloquear=True)

        sql = sql_do_postgres(vistas[0])
        self.assertIn("LEFT OUTER JOIN", sql)  # o cliente e o aceite podem faltar
        self.assertFalse(trava_que_o_postgres_recusa(sql), sql[-200:])
        self.assertIn('FOR UPDATE OF "sistema_interno_orcamento"', sql)

    def test_o_cliente_aprova_pela_pagina_da_proposta(self):
        orcamento = orcamento_aprovado(status=Orcamento.Status.AGUARDANDO_RESPOSTA)
        resposta = self.client.post(f"/orcamento/{orcamento.token}/", {
            "decisao": "aprovar", "nome": "Clara Fases",
            "documento_assinante": "529.982.247-25", "consentimento_aceite": "1",
        })
        self.assertEqual(resposta.status_code, 302)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, Orcamento.Status.APROVADO)


# ======================================================================
# 2. A PROPOSTA ASSINADA OU PAGA NÃO VIRA "RECUSADA"
# ======================================================================
class SituacaoTravadaTests(TestCase):

    def setUp(self):
        self.vendas = equipe("vendas-fases", "vendas")
        self.client.force_login(self.vendas)

    def mudar(self, orcamento, status):
        return self.client.post("/orcamentos/", {
            "action": "status", "id": orcamento.pk, "status": status, "motivo": "Desistiu",
        }, **AJAX)

    def assinar(self, orcamento):
        from sistema_interno.tests_documento_assinatura import png_de_assinatura

        documento = svc.gerar(orcamento, self.vendas)
        svc.assinar(
            documento, nome="Clara Fases", cpf_cnpj="52998224725",
            png=svc.png_da_assinatura(png_de_assinatura()), ip="10.0.0.1", navegador="teste",
        )

    def test_assinada_continua_aprovada(self):
        orcamento = orcamento_aprovado()
        self.assinar(orcamento)
        for status in ("recusado", "expirado", "em_negociacao"):
            with self.subTest(status=status):
                resposta = self.mudar(orcamento, status)
                self.assertEqual(resposta.status_code, 400)
                self.assertIn("já assinou o termo", resposta.json()["msg"])
                orcamento.refresh_from_db()
                self.assertEqual(orcamento.status, Orcamento.Status.APROVADO)

    def test_paga_nao_vira_recusada_com_a_venda_na_receita(self):
        orcamento = orcamento_aprovado()
        orcamento.registrar_pagamento(orcamento.total)
        venda_id = orcamento.venda_id
        resposta = self.mudar(orcamento, "recusado")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("zere o pagamento primeiro", resposta.json()["msg"])
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, Orcamento.Status.APROVADO)
        self.assertEqual(orcamento.venda_id, venda_id)

    def test_parcial_tambem_trava_e_zerar_o_pagamento_solta(self):
        orcamento = orcamento_aprovado()
        orcamento.registrar_pagamento(Decimal("100"))
        self.assertEqual(self.mudar(orcamento, "em_negociacao").status_code, 400)
        orcamento.registrar_pagamento(Decimal("0"))
        self.assertEqual(self.mudar(orcamento, "em_negociacao").status_code, 200)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, Orcamento.Status.EM_NEGOCIACAO)

    def test_com_pagamento_parcial_nao_ganha_outra_versao(self):
        """Refazer deixaria o dinheiro registrado numa proposta "substituída"."""
        orcamento = orcamento_aprovado()
        orcamento.registrar_pagamento(Decimal("100"))
        self.assertFalse(orcamento.pode_refazer)
        resposta = self.client.post("/orcamentos/", {"action": "refazer", "id": orcamento.pk}, **AJAX)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("pagamento registrado", resposta.json()["msg"])
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.status, Orcamento.Status.APROVADO)

    def test_aprovada_sem_assinatura_nem_pagamento_ainda_muda(self):
        orcamento = orcamento_aprovado()
        self.assertEqual(self.mudar(orcamento, "recusado").status_code, 200)

    def test_a_lista_nao_oferece_situacao_para_a_travada(self):
        livre = orcamento_aprovado(nome_cliente="Livre")
        paga = orcamento_aprovado(nome_cliente="Paga")
        paga.registrar_pagamento(paga.total)
        html = self.client.get("/orcamentos/?filtro=aprovados", **INTERNO).content.decode()
        self.assertIn(f'data-situacao="{livre.pk}"', html)
        self.assertNotIn(f'data-situacao="{paga.pk}"', html)


# ======================================================================
# 3. A JANELA "MUDAR SITUAÇÃO": SÓ PELO BOTÃO, E EM CHIPS
# ======================================================================
class JanelaDaSituacaoTests(TestCase):

    def setUp(self):
        self.client.force_login(equipe("vendas-janela", "vendas"))
        self.orcamento = orcamento_aprovado()
        self.html = self.client.get("/orcamentos/", **INTERNO).content.decode()

    def test_so_o_botao_tem_data_situacao(self):
        """A célula com o mesmo atributo abria a janela sem a situação de agora."""
        etiquetas = re.findall(r"<(\w+)[^>]*\sdata-situacao=\"", self.html)
        self.assertTrue(etiquetas)
        self.assertEqual(set(etiquetas), {"button"})
        self.assertIn(f'data-situacao-celula="{self.orcamento.pk}"', self.html)
        self.assertIn('Painel.aoClicar("button[data-situacao]"', self.html)

    def test_a_situacao_e_escolhida_em_chips(self):
        janela = self.html[self.html.index('id="formSituacao"'):]
        janela = janela[:janela.index("</form>")]
        self.assertNotIn("<select", janela)
        valores = re.findall(r'<input type="radio" name="status" value="(\w+)" required>', janela)
        self.assertEqual(sorted(valores), ["aprovado", "em_negociacao", "expirado", "recusado"])


# ======================================================================
# 4. O ANDAMENTO DO PEDIDO DIZ O SENTIDO DE CADA PASSO
# ======================================================================
class SentidoDoAndamentoTests(TestCase):

    def pedido(self, status, envio="retirada"):
        dono = User.objects.create_user(f"dono-{status}-{envio}", password="x")
        pedido = Pedido.objects.create(
            cliente=dono.perfil, carrinho_origem=Carrinho.objects.create(cliente=dono.perfil),
            status="aguardando_pagamento", tipo_envio=envio, total_liquido=Decimal("10"),
        )
        ItemPedido.objects.create(pedido=pedido, nome_item="Air Game Kids", tipo_item="brinquedos",
                                  preco_unitario=Decimal("10"), quantidade=1, subtotal=Decimal("10"))
        for passo in Pedido.ANDAMENTO[: Pedido.ANDAMENTO.index(status) + 1]:
            pedido.status = passo
            pedido.save()
        return Pedido.objects.get(pk=pedido.pk)

    def test_em_preparacao_na_retirada(self):
        from sistema_interno.views_funil import opcoes_de_andamento

        opcoes = opcoes_de_andamento(self.pedido("em_preparacao"))
        self.assertEqual(
            [(o["valor"], o["sentido"]) for o in opcoes],
            [("saiu_entrega", "proximo"), ("finalizado", "pular"), ("pago", "voltar"), ("cancelado", "cancelar")],
        )
        self.assertEqual(opcoes[0]["rotulo"], "Pronto para retirada")
        self.assertIn("Pula “Pronto para retirada”", opcoes[1]["dica"])
        self.assertEqual(opcoes[2]["rotulo"], "Voltar para “Pago”")

    def test_finalizado_so_volta_ou_cancela(self):
        from sistema_interno.views_funil import opcoes_de_andamento

        sentidos = {o["sentido"] for o in opcoes_de_andamento(self.pedido("finalizado", "frete"))}
        self.assertEqual(sentidos, {"voltar", "cancelar"})

    def test_toda_opcao_tem_sentido_rotulo_e_icone(self):
        from sistema_interno.views_funil import opcoes_de_andamento

        for envio in ("retirada", "frete"):
            for status in Pedido.ANDAMENTO:
                for opcao in opcoes_de_andamento(self.pedido(status, envio)):
                    with self.subTest(envio=envio, status=status, opcao=opcao["valor"]):
                        self.assertTrue(opcao["rotulo"] and opcao["icone"])
                        self.assertIn(opcao["sentido"], ("proximo", "pular", "voltar", "cancelar"))
                        self.assertNotEqual(opcao["valor"], status)
