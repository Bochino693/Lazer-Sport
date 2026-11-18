"""As fases de todos os pedidos da loja, até a entrega (LEIA-ME-V10, seção 106).

O pedido do dono, depois de ver a linha do tempo dos orçamentos em Meus
pedidos: "em todos os pedidos devemos ter esse faseamento, para o cliente
conseguir ver tudo certinho até a entrega."

O que estes testes protegem:

  * AS DATAS DE CADA FASE: gravadas sozinhas pelo `Pedido.save()` quando a
    situação muda, por qualquer caminho (o checkout do Mercado Pago, o
    painel, a devolução ao carrinho, o `save()` do admin); a fase pulada
    ganha a mesma data; a volta de correção apaga a da frente; e gravar o
    pedido SEM mudar a situação não faz consulta nenhuma a mais;
  * AS FASES COMO O CLIENTE VÊ: feito, pagamento (Pix, boleto, cartão em
    análise), produção, envio (ou retirada) e entregue, em cada situação,
    com o cancelado parando em vermelho onde estava;
  * MEUS PEDIDOS: a linha do tempo em todos os pedidos, o rastreio e o
    "Rastrear" só para o dono, o endereço da fábrica na retirada;
  * O PAINEL: o "Saiu para entrega" pede a transportadora (chips, nunca
    lista suspensa), grava o código e o link junto com a situação, e o
    rastreio se corrige depois; a retirada vira "Pronto para retirada";
  * A MIGRAÇÃO 0210: os pedidos de antes ganham as datas que dá para saber.
"""

import datetime as dt
import json
import re
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.apps import apps
from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from core import fases_pedido
from core.models import Carrinho, ItemPedido, Pedido
from sistema_interno.permissoes import atribuir_funcoes

INTERNO = {"HTTP_HOST": "interno.testserver"}
AJAX = {"HTTP_HOST": "interno.testserver", "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}

#: Uma quarta-feira qualquer, às 10h de Brasília.
QUARTA = timezone.make_aware(dt.datetime(2026, 11, 18, 10, 0))
DIA = dt.timedelta(days=1)


def no_relogio(momento):
    """Para o relógio em `momento` (o `save()` lê `timezone.now()`)."""
    return mock.patch("django.utils.timezone.now", return_value=momento)


class Base(TestCase):

    def setUp(self):
        self.dono = User.objects.create_user("dono-fases", password="x")
        perfil = self.dono.perfil
        perfil.nome_completo = "Dona Fases"
        perfil.telefone = "(11) 98888-7777"
        perfil.save()

    def pedido(self, status="aguardando_pagamento", envio="retirada", forma="pix", dono=None, **campos):
        dono = dono or self.dono
        carrinho = Carrinho.objects.create(cliente=dono.perfil)
        pedido = Pedido.objects.create(
            cliente=dono.perfil, carrinho_origem=carrinho, status=status,
            tipo_envio=envio, forma_pagamento=forma,
            total_bruto=Decimal("4990.00"), total_liquido=Decimal("4990.00"),
            **campos,
        )
        ItemPedido.objects.create(
            pedido=pedido, nome_item="Air Game Kids", tipo_item="brinquedo",
            preco_unitario=Decimal("4990.00"), quantidade=1, subtotal=Decimal("4990.00"),
        )
        return Pedido.objects.get(pk=pedido.pk)

    def datas(self, pedido):
        pedido = Pedido.objects.get(pk=pedido.pk)
        return {campo: getattr(pedido, campo) for campo in Pedido.DATA_DA_SITUACAO.values()}


# ======================================================================
# 1. AS DATAS DE CADA FASE
# ======================================================================
class DatasDasFasesTests(Base):

    def test_cada_passo_grava_a_sua_data_e_mantem_as_de_antes(self):
        with no_relogio(QUARTA):
            pedido = self.pedido()
        self.assertEqual(set(self.datas(pedido).values()), {None})

        passos = [("pago", "pago_em"), ("em_preparacao", "preparacao_em"),
                  ("saiu_entrega", "enviado_em"), ("finalizado", "entregue_em")]
        for numero, (situacao, campo) in enumerate(passos, start=1):
            with self.subTest(situacao=situacao), no_relogio(QUARTA + numero * DIA):
                pedido = Pedido.objects.get(pk=pedido.pk)
                pedido.status = situacao
                pedido.save(update_fields=["status", "atualizado"])
                self.assertEqual(self.datas(pedido)[campo], QUARTA + numero * DIA)

        self.assertEqual(self.datas(pedido), {
            "pago_em": QUARTA + DIA, "preparacao_em": QUARTA + 2 * DIA,
            "enviado_em": QUARTA + 3 * DIA, "entregue_em": QUARTA + 4 * DIA,
            "cancelado_em": None,
        })

    def test_o_pagamento_aprovado_pelo_checkout_grava_o_pago_em(self):
        """O caminho de verdade do Mercado Pago (webhook e conferência)."""
        from core import checkout

        pedido = self.pedido()
        Pedido.objects.filter(pk=pedido.pk).update(mp_fingerprint="assinatura-x")
        pedido.refresh_from_db()
        pagamento = {
            "id": 7711, "status": "approved", "payment_type_id": "bank_transfer",
            "transaction_amount": float(pedido.total_final),
            "external_reference": checkout.referencia_do_pedido(pedido),
            "metadata": {"cart_fingerprint": "assinatura-x"},
        }
        with no_relogio(QUARTA), mock.patch("core.notificacoes.enviar_confirmacao_de_compra"), \
                self.captureOnCommitCallbacks(execute=True):
            checkout.confirmar_pagamento(pedido, pagamento)

        self.assertEqual(self.datas(pedido)["pago_em"], QUARTA)

    def test_quem_pula_uma_fase_nao_fica_com_fase_feita_sem_data(self):
        pedido = self.pedido(status="pago", envio="frete")
        antes = self.datas(pedido)["pago_em"]
        with no_relogio(QUARTA + 3 * DIA):
            pedido.mudar_situacao("saiu_entrega", envio={"transportadora_envio": "Jadlog"})

        datas = self.datas(pedido)
        self.assertEqual(datas["pago_em"], antes)
        self.assertEqual(datas["preparacao_em"], QUARTA + 3 * DIA)
        self.assertEqual(datas["enviado_em"], QUARTA + 3 * DIA)
        self.assertIsNone(datas["entregue_em"])
        # o próprio objeto já sai acertado (o painel lê dele)
        self.assertEqual(pedido.enviado_em, QUARTA + 3 * DIA)

    def test_o_pedido_que_nasce_entregue_tem_todas_as_datas(self):
        with no_relogio(QUARTA):
            pedido = self.pedido(status="finalizado")
        datas = self.datas(pedido)
        self.assertEqual(
            {datas["pago_em"], datas["preparacao_em"], datas["enviado_em"], datas["entregue_em"]},
            {QUARTA},
        )

    def test_a_volta_de_correcao_apaga_a_data_da_frente_e_nao_mexe_no_pagamento(self):
        with no_relogio(QUARTA):
            pedido = self.pedido(status="pago", envio="frete")
        with no_relogio(QUARTA + DIA):
            pedido.mudar_situacao("saiu_entrega", envio={"transportadora_envio": "Braspress"})
        with no_relogio(QUARTA + 2 * DIA):
            Pedido.objects.get(pk=pedido.pk).mudar_situacao("em_preparacao")
            Pedido.objects.get(pk=pedido.pk).mudar_situacao("pago")

        datas = self.datas(pedido)
        self.assertEqual(datas["pago_em"], QUARTA)  # o dia do pagamento não muda
        self.assertIsNone(datas["preparacao_em"])
        self.assertIsNone(datas["enviado_em"])

    def test_cancelar_grava_o_dia_e_nao_apaga_nada(self):
        with no_relogio(QUARTA):
            pedido = self.pedido(status="em_preparacao")
        with no_relogio(QUARTA + 2 * DIA):
            pedido.mudar_situacao("cancelado")

        datas = self.datas(pedido)
        self.assertEqual(datas["cancelado_em"], QUARTA + 2 * DIA)
        self.assertEqual(datas["pago_em"], QUARTA)
        self.assertEqual(datas["preparacao_em"], QUARTA)

    def test_devolver_ao_carrinho_grava_o_cancelamento(self):
        pedido = self.pedido()
        with no_relogio(QUARTA):
            pedido.devolver_ao_carrinho()
        self.assertEqual(self.datas(pedido)["cancelado_em"], QUARTA)
        self.assertIsNone(self.datas(pedido)["pago_em"])

    def test_o_save_inteiro_do_admin_tambem_grava(self):
        pedido = self.pedido(status="pago")
        pedido = Pedido.objects.get(pk=pedido.pk)
        pedido.status = "em_preparacao"
        with no_relogio(QUARTA):
            pedido.save()
        self.assertEqual(self.datas(pedido)["preparacao_em"], QUARTA)

    def test_gravar_sem_mudar_a_situacao_nao_consulta_nada_a_mais(self):
        pedido = Pedido.objects.get(pk=self.pedido(status="pago").pk)

        with self.assertNumQueries(1):
            pedido.impresso = True
            pedido.save(update_fields=["impresso"])
        with self.assertNumQueries(1):
            pedido.observacoes = "Embalar com plástico bolha"
            pedido.save()
        # e mudar a situação também é uma gravação só (a anterior veio do banco junto)
        with self.assertNumQueries(1):
            pedido.status = "em_preparacao"
            pedido.save(update_fields=["status"])
        self.assertIsNotNone(self.datas(pedido)["preparacao_em"])

    def test_o_pedido_lido_sem_a_situacao_pergunta_uma_vez(self):
        pedido = self.pedido(status="pago")
        parcial = Pedido.objects.only("id").get(pk=pedido.pk)
        parcial.status = "em_preparacao"
        with no_relogio(QUARTA):
            parcial.save(update_fields=["status"])
        self.assertEqual(self.datas(pedido)["preparacao_em"], QUARTA)

        # sem tocar na situação adiada, ela não é perguntada (o `save()` de
        # sempre ainda lê os totais adiados -- isso é de antes desta versão)
        outro = Pedido.objects.only("id", "impresso", "total_liquido", "valor_frete").get(pk=pedido.pk)
        with self.assertNumQueries(1):
            outro.impresso = True
            outro.save(update_fields=["impresso"])

    def test_reler_do_banco_acerta_a_situacao_de_comparacao(self):
        pedido = Pedido.objects.get(pk=self.pedido(status="pago").pk)
        with no_relogio(QUARTA):
            Pedido.objects.get(pk=pedido.pk).mudar_situacao("em_preparacao")
        pedido.refresh_from_db()
        with no_relogio(QUARTA + 5 * DIA):
            pedido.save()
        # nada mudou de situação depois de reler: a data continua a do passo
        self.assertEqual(self.datas(pedido)["preparacao_em"], QUARTA)


# ======================================================================
# 2. AS FASES COMO O CLIENTE VÊ
# ======================================================================
class FasesDoClienteTests(Base):

    def fases(self, pedido, agora=None):
        cartao = fases_pedido.acompanhamento_do_pedido(Pedido.objects.get(pk=pedido.pk), agora=agora)
        estados = {fase.chave: fase.estado for fase in cartao.fases}
        notas = {fase.chave: fase.nota for fase in cartao.fases}
        return cartao, estados, notas

    def test_aguardando_o_pix(self):
        with no_relogio(QUARTA):
            pedido = self.pedido(forma=None, mp_payment_id="123", mp_status="pending")
        cartao, estados, notas = self.fases(pedido)

        self.assertEqual(
            estados,
            {"feito": "feita", "pagamento": "atual", "producao": "futura", "envio": "futura", "entrega": "futura"},
        )
        self.assertEqual(notas["feito"], "18/11 às 10:00")
        self.assertEqual(notas["pagamento"], "Aguardando Pix")
        self.assertEqual(cartao.situacao_texto, "Aguardando pagamento")
        self.assertEqual(cartao.fase_atual.chave, "pagamento")

    def test_boleto_aberto_e_cartao_em_analise(self):
        boleto = self.pedido(
            forma=None, mp_payment_id="124", mp_status="pending",
            boleto_url="https://www.mercadopago.com.br/payments/124/ticket",
            boleto_vencimento=QUARTA + 3 * DIA,
        )
        self.assertEqual(self.fases(boleto, agora=QUARTA)[2]["pagamento"], "Boleto vence em 21/11")
        self.assertEqual(self.fases(boleto, agora=QUARTA + 4 * DIA)[2]["pagamento"], "Boleto venceu em 21/11")

        cartao = self.pedido(forma=None, mp_payment_id="125", mp_status="in_process")
        self.assertEqual(self.fases(cartao)[2]["pagamento"], "Cartão em análise")

    def test_pago_no_cartao_com_prazo_de_producao(self):
        with no_relogio(QUARTA):
            pedido = self.pedido(status="pago", forma="credito", parcelas=3, prazo_producao_dias=5)
        _, estados, notas = self.fases(pedido)

        self.assertEqual(estados["pagamento"], "feita")
        self.assertEqual(notas["pagamento"], "Pago em 18/11 · cartão 3x")
        self.assertEqual(estados["producao"], "atual")
        # 5 dias úteis depois da quarta 18/11, pulando o fim de semana e o 20/11
        self.assertEqual(notas["producao"], "Começou em 18/11 · previsão 26/11")

    def test_em_preparacao_sem_prazo(self):
        with no_relogio(QUARTA):
            pedido = self.pedido(status="em_preparacao")
        self.assertEqual(self.fases(pedido)[2]["producao"], "Em preparação desde 18/11")
        sem_dia = self.pedido(status="em_preparacao")
        Pedido.objects.filter(pk=sem_dia.pk).update(preparacao_em=None)
        self.assertEqual(self.fases(sem_dia)[2]["producao"], "Em preparação")

    def test_saiu_para_entrega_com_a_transportadora_e_o_codigo(self):
        with no_relogio(QUARTA):
            pedido = self.pedido(
                status="saiu_entrega", envio="frete", forma="boleto",
                transportadora_envio="Braspress", codigo_rastreio="BRP123",
                link_rastreio="https://www.braspress.com/rastreio/",
            )
        cartao, estados, notas = self.fases(pedido)

        self.assertEqual(estados["producao"], "feita")
        self.assertEqual(notas["producao"], "Pronta em 18/11")
        self.assertEqual(estados["envio"], "atual")
        self.assertEqual(notas["envio"], "Saiu em 18/11 · Braspress · código BRP123")
        self.assertEqual(notas["pagamento"], "Pago em 18/11 · boleto")
        self.assertEqual(cartao.envio["link"], "https://www.braspress.com/rastreio/")
        self.assertEqual(cartao.situacao_texto, "Saiu para entrega")
        self.assertFalse(cartao.retirada_pronta)

    def test_retirada_pronta_e_retirada(self):
        with no_relogio(QUARTA):
            pronto = self.pedido(status="saiu_entrega")
        cartao, estados, notas = self.fases(pronto)
        self.assertEqual([fase.nome for fase in cartao.fases][3:], ["Retirada", "Retirado"])
        self.assertEqual(estados["envio"], "atual")
        self.assertEqual(notas["envio"], "Pronto para retirada em 18/11")
        self.assertEqual(cartao.situacao_texto, "Pronto para retirada")
        self.assertTrue(cartao.retirada_pronta)
        self.assertIsNone(cartao.envio)

        with no_relogio(QUARTA):
            retirado = self.pedido(status="finalizado")
        cartao, estados, notas = self.fases(retirado)
        self.assertEqual(set(estados.values()), {"feita"})
        self.assertEqual(notas["entrega"], "Retirado em 18/11")
        self.assertEqual(cartao.situacao_texto, "Retirado")

    def test_entregue(self):
        with no_relogio(QUARTA):
            pedido = self.pedido(status="finalizado", envio="frete", transportadora_envio="Patrus")
        cartao, estados, notas = self.fases(pedido)
        self.assertEqual(set(estados.values()), {"feita"})
        self.assertIsNone(cartao.fase_atual)
        self.assertEqual(notas["entrega"], "Entregue em 18/11")
        self.assertEqual(cartao.situacao_texto, "Entregue")
        # toda fase feita tem o seu dia
        self.assertTrue(all(re.search(r"\d\d/\d\d", nota) for nota in notas.values()))

    def test_o_cancelado_para_onde_estava(self):
        with no_relogio(QUARTA):
            sem_pagar = self.pedido()
            sem_pagar.devolver_ao_carrinho()
        cartao, estados, notas = self.fases(sem_pagar)
        self.assertTrue(cartao.parou)
        self.assertEqual(
            estados,
            {"feito": "feita", "pagamento": "parada", "producao": "futura", "envio": "futura", "entrega": "futura"},
        )
        self.assertEqual(notas["pagamento"], "Cancelado em 18/11")

        with no_relogio(QUARTA):
            pago = self.pedido(status="pago")
        with no_relogio(QUARTA + DIA):
            pago.mudar_situacao("cancelado")
        _, estados, notas = self.fases(pago)
        self.assertEqual(estados["pagamento"], "feita")
        self.assertEqual(notas["pagamento"], "Pago em 18/11 · Pix")
        self.assertEqual(estados["producao"], "parada")
        self.assertEqual(notas["producao"], "Cancelado em 19/11")

        with no_relogio(QUARTA):
            saiu = self.pedido(status="saiu_entrega", envio="frete", transportadora_envio="Jadlog")
        with no_relogio(QUARTA + DIA):
            saiu.mudar_situacao("cancelado")
        _, estados, _ = self.fases(saiu)
        self.assertEqual((estados["envio"], estados["entrega"]), ("feita", "parada"))

    def test_icones_das_fases_estao_no_recorte_do_site(self):
        icones = set(
            (Path(__file__).resolve().parent / "static/vendor/fontawesome-site/icones.txt").read_text().split()
        )
        self.assertLessEqual(set(fases_pedido.ICONES_DAS_FASES.values()), icones)
        # e os do quadro do envio e da retirada (partials/pedido_fases.html)
        parcial = (Path(__file__).resolve().parent / "templates/partials/pedido_fases.html").read_text()
        usados = set(re.findall(r"fa-solid (fa-[a-z0-9-]+)", parcial))
        self.assertLessEqual(usados, icones)


# ======================================================================
# 3. MEUS PEDIDOS
# ======================================================================
class MeusPedidosTests(Base):

    def abrir(self, usuario):
        self.client.force_login(usuario)
        resposta = self.client.get("/meus-pedidos/")
        self.assertEqual(resposta.status_code, 200)
        return resposta.content.decode()

    def test_todo_pedido_tem_a_linha_do_tempo(self):
        for status in ("aguardando_pagamento", "pago", "em_preparacao", "saiu_entrega", "finalizado", "cancelado"):
            self.pedido(status=status)
        html = self.abrir(self.dono)

        self.assertEqual(html.count('class="oc-fases pd-fases'), 6)
        self.assertEqual(html.count('aria-current="step"') - 1, 4)  # 1 é a etapa do checkout; finalizado e cancelado não têm fase de agora
        self.assertIn('class="oc-fases pd-fases is-parou"', html)
        self.assertNotIn("pd-trilha", html)
        # o "aguardando" continua com as ações dele
        self.assertIn("Retomar pagamento", html)
        self.assertIn("Cancelar e voltar ao carrinho", html)

    def test_o_rastreio_aparece_so_para_o_dono(self):
        self.pedido(
            status="saiu_entrega", envio="frete", transportadora_envio="Braspress",
            codigo_rastreio="BRP998877", link_rastreio="https://www.braspress.com/rastreio/?c=BRP998877",
        )
        html = self.abrir(self.dono)
        self.assertIn('class="pd-envio"', html)
        self.assertIn('data-copiar="BRP998877"', html)
        self.assertIn('href="https://www.braspress.com/rastreio/?c=BRP998877"', html)
        self.assertIn("Rastrear", html)
        self.assertIn("Saiu em", html)

        outro = User.objects.create_user("outra-pessoa", password="x")
        perfil = outro.perfil
        perfil.telefone = "(11) 97777-6666"
        perfil.save()
        html = self.abrir(outro)
        self.assertNotIn("BRP998877", html)
        self.assertNotIn("Braspress", html)

    def test_sem_link_nao_tem_botao_rastrear(self):
        self.pedido(status="saiu_entrega", envio="frete", transportadora_envio="Jadlog", codigo_rastreio="JD1")
        html = self.abrir(self.dono)
        self.assertIn('data-copiar="JD1"', html)
        self.assertNotIn("pd-envio-rastrear", html)

    def test_pronto_para_retirada_mostra_a_fabrica(self):
        self.pedido(status="saiu_entrega")
        html = self.abrir(self.dono)
        self.assertIn("pd-envio--retirada", html)
        self.assertIn("Rua São Roque de Minas, 104", html)
        self.assertIn("Como chegar", html)
        self.assertIn("Pronto para retirada", html)

    def test_as_consultas_nao_crescem_com_os_pedidos(self):
        self.pedido(status="saiu_entrega", envio="frete", transportadora_envio="Braspress", codigo_rastreio="A1")
        self.abrir(self.dono)
        with CaptureQueriesContext(connection) as poucos:
            self.client.get("/meus-pedidos/")
        for status in ("pago", "finalizado", "cancelado", "saiu_entrega"):
            self.pedido(status=status, envio="frete", transportadora_envio="Jadlog")
        with CaptureQueriesContext(connection) as muitos:
            self.client.get("/meus-pedidos/")
        self.assertEqual(len(muitos), len(poucos))


# ======================================================================
# 4. O PAINEL: A TRANSPORTADORA E O RASTREIO
# ======================================================================
class PainelDoEnvioTests(Base):

    def setUp(self):
        super().setUp()
        self.financeiro = User.objects.create_user("fin-envio", password="x")
        atribuir_funcoes(self.financeiro, ["financeiro"])

    def andar(self, pedido, status, **campos):
        self.client.force_login(self.financeiro)
        return self.client.post(f"/pedidos/{pedido.pk}/andamento/", {"status": status, **campos}, **AJAX)

    def test_saiu_para_entrega_pede_a_transportadora(self):
        pedido = self.pedido(status="em_preparacao", envio="frete")

        resposta = self.andar(pedido, "saiu_entrega")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("transportadora", resposta.json()["msg"])
        self.assertEqual(Pedido.objects.get(pk=pedido.pk).status, "em_preparacao")

        with no_relogio(QUARTA):
            resposta = self.andar(
                pedido, "saiu_entrega", transportadora="  Braspress ",
                codigo_rastreio="BRP 4455", link_rastreio="www.braspress.com/rastreio",
            )
        self.assertEqual(resposta.status_code, 200, resposta.content)
        corpo = resposta.json()
        self.assertIn("Braspress", corpo["msg"])
        self.assertEqual(corpo["envio"]["codigo"], "BRP 4455")
        pedido = Pedido.objects.get(pk=pedido.pk)
        self.assertEqual(pedido.status, "saiu_entrega")
        self.assertEqual(pedido.transportadora_envio, "Braspress")
        self.assertEqual(pedido.link_rastreio, "https://www.braspress.com/rastreio")
        self.assertEqual(pedido.enviado_em, QUARTA)

    def test_link_que_nao_e_da_internet_e_recusado(self):
        pedido = self.pedido(status="em_preparacao", envio="frete")
        resposta = self.andar(pedido, "saiu_entrega", transportadora="Jadlog", link_rastreio="javascript:alert(1)")
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(Pedido.objects.get(pk=pedido.pk).status, "em_preparacao")

    def test_a_retirada_fica_pronta_sem_transportadora(self):
        pedido = self.pedido(status="em_preparacao")
        resposta = self.andar(pedido, "saiu_entrega")
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(resposta.json()["rotulo"], "Pronto para retirada")
        pedido = Pedido.objects.get(pk=pedido.pk)
        self.assertEqual(pedido.transportadora_envio, "")
        self.assertIsNotNone(pedido.enviado_em)

    def test_o_rastreio_se_completa_depois(self):
        pedido = self.pedido(status="saiu_entrega", envio="frete", transportadora_envio="Jadlog")
        self.client.force_login(self.financeiro)
        url = f"/pedidos/{pedido.pk}/envio/"

        resposta = self.client.post(url, {"transportadora": "Jadlog", "codigo_rastreio": "JD-777"}, **AJAX)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        pedido = Pedido.objects.get(pk=pedido.pk)
        self.assertEqual(pedido.codigo_rastreio, "JD-777")
        self.assertEqual(pedido.status, "saiu_entrega")

        # a retirada e o pedido que ainda não saiu não têm rastreio
        retirada = self.pedido(status="saiu_entrega")
        self.assertEqual(self.client.post(f"/pedidos/{retirada.pk}/envio/", {"transportadora": "X"}, **AJAX).status_code, 400)
        cedo = self.pedido(status="pago", envio="frete")
        self.assertEqual(self.client.post(f"/pedidos/{cedo.pk}/envio/", {"transportadora": "X"}, **AJAX).status_code, 400)

        # quem não é do Financeiro nem da Gestão não mexe
        producao = User.objects.create_user("fab-envio", password="x")
        atribuir_funcoes(producao, ["producao"])
        self.client.force_login(producao)
        self.assertEqual(self.client.post(url, {"transportadora": "Outra"}, **AJAX).status_code, 302)
        self.assertEqual(Pedido.objects.get(pk=pedido.pk).transportadora_envio, "Jadlog")

    def test_a_tela_tem_os_chips_das_transportadoras_e_nenhum_select(self):
        from sistema_interno.models import Transportadora

        Transportadora.objects.create(nome="Transportes Inativa", ativo=False)
        frete = self.pedido(status="em_preparacao", envio="frete")
        saiu = self.pedido(status="saiu_entrega", envio="frete", transportadora_envio="Braspress", codigo_rastreio="BR1")
        self.client.force_login(self.financeiro)

        html = self.client.get("/pedidos/inner/?filtro=todos", **INTERNO).content.decode()

        self.assertNotIn("<select", html)
        bloco = re.search(r'<script id="lsTransportadorasEnvio" type="application/json">(.*?)</script>', html, re.S)
        nomes = [t["nome"] for t in json.loads(bloco.group(1))]
        ativas = set(Transportadora.objects.ativas().values_list("nome", "nome_fantasia"))
        self.assertEqual(len(nomes), len(ativas))
        self.assertNotIn("Transportes Inativa", nomes)
        # o andamento leva o "pede_envio" no "Saiu para entrega" do frete
        opcoes = re.search(
            rf'data-andamento-url="/pedidos/{frete.pk}/andamento/"\s+data-andamento-opcoes="([^"]+)"', html,
        ).group(1).replace("&quot;", '"')
        saiu_entrega = [o for o in json.loads(opcoes) if o["valor"] == "saiu_entrega"][0]
        self.assertTrue(saiu_entrega["pede_envio"])
        # a linha de quem saiu mostra o rastreio e abre a folha de corrigir
        self.assertIn(f'data-envio-url="/pedidos/{saiu.pk}/envio/"', html)
        self.assertIn('data-envio-codigo="BR1"', html)

    def test_o_js_da_folha_usa_chips_e_a_pergunta_do_site(self):
        js = (Path(__file__).resolve().parent.parent / "sistema_interno/static/interno/producao-etiquetas.js").read_text()
        self.assertIn("function folhaDoEnvio", js)
        self.assertIn('radio.type = "radio"', js)
        self.assertNotIn("alert(", js)
        self.assertNotIn("confirm(", js.replace("LSAviso.confirmar(", ""))


# ======================================================================
# 5. A LEITURA DO ENVIO
# ======================================================================
class LerEnvioTests(TestCase):

    def test_o_que_a_tela_aceita(self):
        ler = fases_pedido.ler_envio
        self.assertEqual(
            ler({"transportadora": " Entrega   própria ", "codigo_rastreio": "", "link_rastreio": ""}),
            {"transportadora_envio": "Entrega própria", "codigo_rastreio": "", "link_rastreio": ""},
        )
        self.assertEqual(ler({"transportadora": "Correios", "link_rastreio": "rastreamento.correios.com.br"})["link_rastreio"],
                         "https://rastreamento.correios.com.br")
        for ruim in ({}, {"transportadora": "  "}, {"transportadora": "X" * 121},
                     {"transportadora": "Jadlog", "codigo_rastreio": "9" * 61},
                     {"transportadora": "Jadlog", "link_rastreio": "ftp://arquivo"},
                     {"transportadora": "Jadlog", "link_rastreio": "javascript:alert(1)"}):
            with self.subTest(ruim=ruim), self.assertRaises(ValueError):
                ler(ruim)


# ======================================================================
# 6. A MIGRAÇÃO 0210: AS DATAS DOS PEDIDOS DE ANTES
# ======================================================================
class MigracaoDasDatasTests(Base):

    def rodar(self):
        import_module("core.migrations.0210_datas_das_fases_dos_pedidos").preencher(
            apps, SimpleNamespace(connection=connection),
        )

    def antigo(self, status, **campos):
        """O pedido de antes desta versão: as datas vazias."""
        pedido = self.pedido(status=status)
        Pedido.objects.filter(pk=pedido.pk).update(
            pago_em=None, preparacao_em=None, enviado_em=None, entregue_em=None, cancelado_em=None,
            **campos,
        )
        return pedido

    def test_os_pedidos_de_antes_ganham_as_datas_que_da_para_saber(self):
        feito = QUARTA - 10 * DIA
        mexido = QUARTA - 2 * DIA
        pago = self.antigo("pago", criacao=feito, atualizado=mexido, producao_inicio=feito.date())
        boleto = self.antigo("em_preparacao", criacao=feito, atualizado=mexido, producao_inicio=(feito + 3 * DIA).date())
        saiu = self.antigo("saiu_entrega", criacao=feito, atualizado=mexido, producao_inicio=feito.date())
        entregue = self.antigo("finalizado", criacao=feito, atualizado=mexido, producao_inicio=feito.date())
        cancelado_pago = self.antigo("cancelado", criacao=feito, atualizado=mexido, mp_status="approved")
        cancelado = self.antigo("cancelado", criacao=feito, atualizado=mexido)
        esperando = self.antigo("aguardando_pagamento", criacao=feito, atualizado=mexido)

        self.rodar()

        self.assertEqual(self.datas(pago)["pago_em"], feito)
        # o boleto pago dias depois: o dia do pagamento, ao meio-dia
        self.assertEqual(
            timezone.localtime(self.datas(boleto)["pago_em"]),
            timezone.make_aware(dt.datetime.combine((feito + 3 * DIA).date(), dt.time(12))),
        )
        self.assertIsNone(self.datas(boleto)["preparacao_em"])
        self.assertEqual(self.datas(saiu)["enviado_em"], mexido)
        self.assertEqual(self.datas(entregue)["entregue_em"], mexido)
        self.assertEqual(self.datas(cancelado_pago)["pago_em"], feito)
        self.assertEqual(self.datas(cancelado_pago)["cancelado_em"], mexido)
        self.assertIsNone(self.datas(cancelado)["pago_em"])
        self.assertEqual(self.datas(cancelado)["cancelado_em"], mexido)
        self.assertEqual(set(self.datas(esperando).values()), {None})
        # o `atualizado` dos pedidos fica como estava
        self.assertEqual(Pedido.objects.get(pk=entregue.pk).atualizado, mexido)

    def test_rodar_de_novo_nao_muda_nada(self):
        pedido = self.antigo("finalizado", atualizado=QUARTA - DIA)
        self.rodar()
        primeira = self.datas(pedido)
        Pedido.objects.filter(pk=pedido.pk).update(atualizado=QUARTA)
        self.rodar()
        self.assertEqual(self.datas(pedido), primeira)

    def test_esquema_e_dados_em_arquivos_separados(self):
        esquema = import_module("core.migrations.0209_pedido_fases_e_rastreio").Migration
        self.assertEqual({type(op).__name__ for op in esquema.operations}, {"AddField"})
        self.assertEqual(esquema.dependencies, [("core", "0208_kits_iniciais")])
        dados = import_module("core.migrations.0210_datas_das_fases_dos_pedidos").Migration
        self.assertEqual([type(op).__name__ for op in dados.operations], ["RunPython"])
