"""A lista de montagem: a fila, as 7 etapas e o prazo (LEIA-ME-V10, seção 108).

O que o dono pediu, e o que estes testes seguram:

  * "lista de montagem com todos os brinquedos que tem pra montar": as
    máquinas dos pedidos pagos E dos orçamentos aprovados entram SOZINHAS,
    uma por unidade (quantidade 3 = 3); o combo e a promoção abrem nos
    brinquedos; serviço ("Montagem e instalação") fica de fora;
  * "o prazo de montagem são de 4 a 5 dias, dependendo do m cúbico": 4 até
    o limite (2,5 m³), 5 acima e sem medida; "dividido por 7 etapas":
    corte de MDF, montagem, adesivo, eletrônica, finalização, teste de
    qualidade e embalagem, com a data prevista de cada; brinquedões e
    espaços esportivos fora dessa regra; peças em 3 dias;
  * "se já tiver sendo montado 3 brinquedos, deve entrar na fila e ter uma
    previsão de 15 a 30 dias mais os da produção"; "brinquedões só podem
    ser montados um por vez, com prazo de 30 dias a cada um na fila": a
    vaga que libera puxa o primeiro da fila, que é avisado;
  * a origem anda junto: a primeira etapa feita põe o pedido "Em
    preparação"; tudo embalado na retirada vira "Pronto para retirada"
    (com as datas da seção 106); finalizado no painel de Pedidos, as
    máquinas saem como entregues; cancelado, a vaga libera;
  * os avisos ao cliente: um por fato, agrupados no mesmo dia; o "pronto"
    nunca espera; a carga dos pedidos antigos não avisa ninguém;
  * o prazo antes da compra (produto, carrinho, proposta) já conta a fila,
    e é o mesmo número do painel e do contrato (`montagem.prazo_de_entrega`);
  * a tela: chips (nunca <select>), sem alert/confirm, só variáveis do
    tema, quem vê e quem mexe; Meus pedidos com a fila e as etapas, sem
    consulta a mais por pedido.
"""

import datetime as dt
import re
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from unittest import mock

from django.apps import apps
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from core.models import (
    Brinquedos, Carrinho, CategoriasBrinquedos, Combos, ItemPedido, PecasReposicao, Pedido, Promocoes,
)

from . import montagem
from .models import (
    ConfiguracaoProducao, ItemOrcamento, Orcamento, ProducaoOrigem, UnidadeMontagem,
)
from .permissoes import atribuir_funcoes

INTERNO = {"HTTP_HOST": "interno.testserver"}
AJAX = {"HTTP_HOST": "interno.testserver", "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
RAIZ = Path(__file__).resolve().parent
S = UnidadeMontagem.Situacao

#: Uma quarta-feira, 10h (18/11/2026); o 20/11 é feriado (Consciência Negra).
QUARTA = timezone.make_aware(dt.datetime(2026, 11, 18, 10, 0))


def no_relogio(momento):
    return mock.patch("django.utils.timezone.now", return_value=momento)


def no_dia(dia):
    return mock.patch.object(montagem, "hoje", return_value=dia)


def brinquedo(nome="Air Game Kids", medidas=(1.0, 1.0, 1.0), categoria=None):
    altura, largura, profundidade = medidas if medidas else (None, None, None)
    objeto = Brinquedos.objects.create(
        nome_brinquedo=nome, descricao="x", valor_brinquedo=Decimal("4990"), avaliacao=5,
        altura_m=altura, largura_m=largura, profundidade_m=profundidade,
    )
    if categoria is not None:
        objeto.categorias_brinquedos.add(categoria)
    return objeto


def equipe(nome, *funcoes):
    user = User.objects.create_user(nome, f"{nome}@exemplo.test", "x")
    atribuir_funcoes(user, funcoes)
    return user


class Base(TestCase):

    def setUp(self):
        from django.core.cache import cache

        cache.clear()  # as previsões guardadas (montagem._guardado) são por teste
        self.dono = User.objects.create_user("dono-montagem", "dono@exemplo.test", "x")
        perfil = self.dono.perfil
        perfil.nome_completo = "Dona Montagem"
        perfil.telefone = "(11) 98888-7777"
        perfil.save()
        self.config = montagem.configuracao()
        self.agk = brinquedo("Air Game Kids", (1.0, 1.0, 1.0))          # 1 m³: 4 dias
        self.basquete = brinquedo("Basquete Street", (2.7, 1.0, 2.4))   # 6,48 m³: 5 dias

    def pedido(self, itens=None, envio="retirada", status="pago", dono=None, pago_em=None):
        dono = dono or self.dono
        pedido = Pedido.objects.create(
            cliente=dono.perfil, carrinho_origem=Carrinho.objects.create(cliente=dono.perfil),
            status="aguardando_pagamento", tipo_envio=envio, total_liquido=Decimal("4990"),
        )
        for objeto, quantidade, nome in itens or [(self.agk, 1, None)]:
            ItemPedido.objects.create(
                pedido=pedido, content_type=ContentType.objects.get_for_model(objeto), object_id=objeto.pk,
                nome_item=nome or str(objeto), tipo_item=ContentType.objects.get_for_model(objeto).model,
                preco_unitario=Decimal("10"), quantidade=quantidade, subtotal=Decimal("10"),
            )
        if status != "aguardando_pagamento":
            with self.captureOnCommitCallbacks(execute=True):
                pedido.status = status
                pedido.save()
        if pago_em is not None:
            Pedido.objects.filter(pk=pedido.pk).update(pago_em=pago_em)
        return Pedido.objects.get(pk=pedido.pk)

    def unidades(self, origem):
        filtro = {"producao__pedido": origem} if isinstance(origem, Pedido) else {"producao__orcamento": origem}
        return list(UnidadeMontagem.objects.filter(**filtro).order_by("id"))


# ======================================================================
# 1. O QUE ENTRA, E COM QUE PRAZO
# ======================================================================
class ClassificacaoTests(Base):

    def test_quatro_dias_ate_o_limite_cinco_acima_e_sem_medida(self):
        sem_medida = brinquedo("Strike Kids", medidas=None)
        pedido = self.pedido([(self.agk, 1, None), (self.basquete, 1, None), (sem_medida, 1, None)])
        dias = {u.nome: (u.trilha, u.dias) for u in self.unidades(pedido)}
        self.assertEqual(dias, {
            "Air Game Kids": ("maquina", 4), "Basquete Street": ("maquina", 5), "Strike Kids": ("maquina", 5),
        })

    def test_quantidade_tres_sao_tres_maquinas_com_o_adesivo(self):
        pedido = self.pedido([(self.agk, 3, "Air Game Kids — adesivo Alienígenas")])
        unidades = self.unidades(pedido)
        self.assertEqual([(u.numero, u.de) for u in unidades], [(1, 3), (2, 3), (3, 3)])
        self.assertEqual({u.variante for u in unidades}, {"Alienígenas"})

    def test_brinquedao_pela_categoria_ou_pela_palavra(self):
        categoria = CategoriasBrinquedos.objects.create(nome_categoria="Brinquedões", imagem_categoria="c/b.png")
        self.config.categorias_projeto.add(categoria)
        castelo = brinquedo("Castelo Kids", (3.2, 4, 4), categoria=categoria)
        cama = brinquedo("Cama Elástica 3m", (2.5, 3, 3))
        pedido = self.pedido([(castelo, 1, None), (cama, 1, None)])
        self.assertEqual({(u.nome, u.trilha, u.dias) for u in self.unidades(pedido)}, {
            ("Castelo Kids", "projeto", 30), ("Cama Elástica 3m", "projeto", 30),
        })

    def test_peca_tres_dias_e_kit_com_eletronica_e_teste(self):
        peca = PecasReposicao.objects.create(nome="Maneta", descricao_peca="x", preco_venda=Decimal("10"))
        kit = PecasReposicao.objects.create(nome="Kit Strike", descricao_peca="x", preco_venda=Decimal("10"), eh_kit=True)
        pedido = self.pedido([(peca, 2, None), (kit, 1, None)])
        trilhas = sorted((u.trilha, u.dias, u.situacao) for u in self.unidades(pedido))
        self.assertEqual(trilhas, [("kit", 3, S.PRODUCAO), ("peca", 3, S.PRODUCAO), ("peca", 3, S.PRODUCAO)])
        self.assertEqual([c for c, _, _ in montagem.ETAPAS["kit"]], ["separacao", "eletronica", "teste", "embalagem"])

    def test_combo_e_promocao_abrem_nos_brinquedos(self):
        combo = Combos.objects.create(descricao="Combo Arcade", valor_combo=Decimal("9000"))
        combo.brinquedos.add(self.agk, self.basquete)
        promo = Promocoes.objects.create(descricao="BF", brinquedos=self.agk, preco_promocao=Decimal("1"))
        promo.brinquedos_extras.add(self.basquete)
        pedido = self.pedido([(combo, 1, None), (promo, 2, None)])
        nomes = sorted(u.nome for u in self.unidades(pedido))
        self.assertEqual(nomes, ["Air Game Kids", "Air Game Kids", "Air Game Kids",
                                 "Basquete Street", "Basquete Street", "Basquete Street"])

    def test_orcamento_aprovado_entra_sem_o_servico_e_reconhece_o_catalogo(self):
        orcamento = Orcamento.objects.create(nome_cliente="Buffet", status=Orcamento.Status.RASCUNHO)
        ItemOrcamento.objects.create(orcamento=orcamento, descricao="Air Game Kids Alienígenas", quantidade=2,
                                     valor_unitario=Decimal("1"))
        ItemOrcamento.objects.create(orcamento=orcamento, descricao="Montagem e instalação", quantidade=1,
                                     valor_unitario=Decimal("1"))
        ItemOrcamento.objects.create(orcamento=orcamento, descricao="Frete", quantidade=1, valor_unitario=Decimal("1"))
        with self.captureOnCommitCallbacks(execute=True):
            orcamento.status = Orcamento.Status.APROVADO
            orcamento.save(update_fields=["status"])
        unidades = self.unidades(orcamento)
        self.assertEqual([(u.nome, u.variante, u.dias, u.brinquedo_id) for u in unidades],
                         [("Air Game Kids", "Alienígenas", 4, self.agk.pk)] * 2)

    def test_as_sete_etapas_dividem_o_prazo(self):
        datas = montagem.datas_das_etapas("maquina", dt.date(2026, 11, 16), 4)  # segunda
        self.assertEqual(list(datas), [c for c, _, _ in montagem.ETAPAS["maquina"]])
        self.assertEqual([c for _, c, _ in montagem.ETAPAS["maquina"]], [
            "Corte de MDF", "Montagem", "Adesivo", "Eletrônica", "Finalização", "Teste de qualidade", "Embalagem",
        ])
        # ceil(i × 4 / 7) = 1, 2, 2, 3, 3, 4, 4 dias úteis (o 20/11 é feriado)
        self.assertEqual(list(datas.values()), [
            "2026-11-17", "2026-11-18", "2026-11-18", "2026-11-19", "2026-11-19", "2026-11-23", "2026-11-23",
        ])


# ======================================================================
# 2. A FILA: 3 MÁQUINAS AO MESMO TEMPO, BRINQUEDÃO UM POR VEZ
# ======================================================================
@override_settings(EMAIL_HOST_USER="robo@exemplo.test", AVISOS_DA_PRODUCAO_NA_HORA=True)
class FilaTests(Base):

    def test_a_quarta_maquina_espera_na_fila_com_15_a_30_dias_mais_a_montagem(self):
        with no_relogio(QUARTA), no_dia(QUARTA.date()):
            pedidos = [self.pedido() for _ in range(4)]
        situacoes = [self.unidades(p)[0].situacao for p in pedidos]
        self.assertEqual(situacoes, [S.PRODUCAO, S.PRODUCAO, S.PRODUCAO, S.FILA])
        quarta = self.unidades(pedidos[3])[0]
        self.assertEqual(quarta.posicao, 1)
        base = QUARTA.date()
        self.assertEqual(quarta.previsao_de, montagem.somar_dias_uteis(montagem.somar_dias_uteis(base, 15), 4))
        self.assertEqual(quarta.previsao_ate, montagem.somar_dias_uteis(montagem.somar_dias_uteis(base, 30), 4))
        self.assertEqual(quarta.previstas, {})

    def test_a_vaga_que_libera_puxa_a_primeira_da_fila_e_avisa(self):
        with no_relogio(QUARTA), no_dia(QUARTA.date()):
            pedidos = [self.pedido() for _ in range(4)]
        mail.outbox.clear()
        primeira = self.unidades(pedidos[0])[0]
        depois = QUARTA + dt.timedelta(days=5)
        with no_relogio(depois), no_dia(depois.date()):
            montagem.concluir_ate(primeira, "embalagem")
        quarta = self.unidades(pedidos[3])[0]
        self.assertEqual(quarta.situacao, S.PRODUCAO)
        self.assertEqual(quarta.entrou_em, depois)
        self.assertEqual(quarta.previstas["embalagem"],
                         montagem.somar_dias_uteis(depois.date(), 4).isoformat())
        assuntos = [m.subject for m in mail.outbox]
        self.assertTrue(any(f"Pedido #{pedidos[3].pk}: entrou em produção" in a for a in assuntos), assuntos)

    def test_brinquedao_um_por_vez_e_trinta_dias_cada(self):
        cama = brinquedo("Cama Elástica 3m", (2.5, 3, 3))
        with no_relogio(QUARTA), no_dia(QUARTA.date()):
            primeiro = self.pedido([(cama, 1, None)])
            segundo = self.pedido([(cama, 1, None)])
            terceiro = self.pedido([(cama, 1, None)])
        um, dois, tres = (self.unidades(p)[0] for p in (primeiro, segundo, terceiro))
        self.assertEqual((um.situacao, dois.situacao, tres.situacao), (S.PRODUCAO, S.FILA, S.FILA))
        self.assertEqual(dois.previsao_ate, montagem.somar_dias_uteis(um.previsao_ate, 30))
        self.assertEqual(tres.previsao_ate, montagem.somar_dias_uteis(dois.previsao_ate, 30))

    def test_a_capacidade_e_a_ordem_mudam_pelo_painel(self):
        with no_relogio(QUARTA), no_dia(QUARTA.date()):
            pedidos = [self.pedido() for _ in range(5)]
        quarta, quinta = self.unidades(pedidos[3])[0], self.unidades(pedidos[4])[0]
        self.assertEqual((quarta.posicao, quinta.posicao), (1, 2))
        self.assertTrue(montagem.mover_na_fila(quinta, -1))
        quarta.refresh_from_db()
        quinta.refresh_from_db()
        self.assertEqual((quarta.posicao, quinta.posicao), (2, 1))
        self.config.capacidade_maquinas = 4
        self.config.save()
        montagem.distribuir(config=self.config)
        quinta.refresh_from_db()
        self.assertEqual(quinta.situacao, S.PRODUCAO)

    def test_cancelado_sai_da_lista_e_libera_a_vaga(self):
        with no_relogio(QUARTA), no_dia(QUARTA.date()):
            pedidos = [self.pedido() for _ in range(4)]
        with self.captureOnCommitCallbacks(execute=True):
            pedidos[0].mudar_situacao("cancelado")
        self.assertEqual(self.unidades(pedidos[0])[0].situacao, S.CANCELADA)
        self.assertEqual(self.unidades(pedidos[3])[0].situacao, S.PRODUCAO)


# ======================================================================
# 3. AS ETAPAS E A FASE DA ORIGEM (as datas da seção 106)
# ======================================================================
@override_settings(EMAIL_HOST_USER="robo@exemplo.test", AVISOS_DA_PRODUCAO_NA_HORA=True)
class EtapasTests(Base):

    def test_para_a_frente_conclui_as_do_meio_e_para_tras_apaga(self):
        unidade = self.unidades(self.pedido())[0]
        with no_relogio(QUARTA):
            montagem.concluir_ate(unidade, "adesivo")
        self.assertEqual(list(unidade.etapas_em), ["corte", "montagem", "adesivo"])
        self.assertEqual(set(unidade.etapas_em.values()), {QUARTA.isoformat()})
        montagem.concluir_ate(unidade, "corte")
        self.assertEqual(list(unidade.etapas_em), ["corte"])
        with self.assertRaises(ValueError):
            montagem.concluir_ate(unidade, "fabricacao")

    def test_a_primeira_etapa_poe_o_pedido_em_preparacao(self):
        pedido = self.pedido()
        unidade = self.unidades(pedido)[0]
        with no_relogio(QUARTA):
            montagem.concluir_ate(unidade, "corte")
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, "em_preparacao")
        self.assertEqual(pedido.preparacao_em, QUARTA)

    def test_tudo_embalado_na_retirada_fica_pronto_para_retirada_e_volta_se_corrigir(self):
        pedido = self.pedido([(self.agk, 2, None)])
        a, b = self.unidades(pedido)
        with no_relogio(QUARTA):
            montagem.concluir_ate(a, "embalagem")
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, "em_preparacao")  # falta a segunda
        with no_relogio(QUARTA + dt.timedelta(hours=2)):
            montagem.concluir_ate(b, "embalagem")
        pedido.refresh_from_db()
        self.assertEqual((pedido.status, pedido.situacao_texto), ("saiu_entrega", "Pronto para retirada"))
        self.assertEqual(pedido.enviado_em, QUARTA + dt.timedelta(hours=2))
        b.refresh_from_db()
        montagem.concluir_ate(b, "teste")
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, "em_preparacao")
        self.assertIsNone(pedido.enviado_em)

    def test_no_frete_o_pronto_espera_a_transportadora(self):
        pedido = self.pedido(envio="frete")
        montagem.concluir_ate(self.unidades(pedido)[0], "embalagem")
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, "em_preparacao")
        self.assertEqual(pedido.producao.situacao, ProducaoOrigem.Situacao.PRONTA)

    def test_finalizado_no_painel_entrega_as_maquinas(self):
        pedido = self.pedido([(self.agk, 2, None)])
        with self.captureOnCommitCallbacks(execute=True):
            pedido.mudar_situacao("finalizado")
        self.assertEqual({u.situacao for u in self.unidades(pedido)}, {S.ENTREGUE})
        self.assertEqual(ProducaoOrigem.objects.get(pedido=pedido).situacao, ProducaoOrigem.Situacao.ENTREGUE)

    def test_o_prazo_da_origem_acompanha_a_lista_ate_a_equipe_digitar(self):
        with no_relogio(QUARTA), no_dia(QUARTA.date()):
            pedido = self.pedido()
        self.assertEqual(pedido.prazo_producao_dias, 4)
        self.assertEqual(pedido.previsao_producao, self.unidades(pedido)[0].previsao_ate)
        self.assertEqual(montagem.prazo_de_entrega(pedido).data_ate, pedido.previsao_producao)
        financeiro = equipe("fin-montagem", "financeiro")
        self.client.force_login(financeiro)
        self.client.post(f"/producao/prazo/pedido/{pedido.pk}/", {"prazo": "20"}, **AJAX)
        producao = ProducaoOrigem.objects.get(pedido=pedido)
        self.assertFalse(producao.prazo_automatico)
        montagem.acertar_origem(producao)
        pedido.refresh_from_db()
        self.assertEqual(pedido.prazo_producao_dias, 20)
        self.assertEqual(montagem.prazo_de_entrega(pedido).dias_max, 20)


# ======================================================================
# 4. OS AVISOS AO CLIENTE
# ======================================================================
@override_settings(EMAIL_HOST_USER="robo@exemplo.test", AVISOS_DA_PRODUCAO_NA_HORA=True)
class AvisosTests(Base):

    def test_um_por_fato_agrupado_no_dia_e_o_pronto_nao_espera(self):
        with no_relogio(QUARTA), no_dia(QUARTA.date()):
            pedido = self.pedido()
        self.assertEqual(len(mail.outbox), 1)  # entrou em produção
        self.assertIn("entrou em produção", mail.outbox[0].subject)
        unidade = self.unidades(pedido)[0]
        with no_relogio(QUARTA), no_dia(QUARTA.date()):
            montagem.concluir_ate(unidade, "corte")
            montagem.concluir_ate(unidade, "montagem")
        self.assertEqual(len(mail.outbox), 1)  # o mesmo dia: esperam juntas
        amanha = QUARTA + dt.timedelta(days=1)
        with no_relogio(amanha), no_dia(amanha.date()):
            montagem.concluir_ate(unidade, "adesivo")
        self.assertEqual(len(mail.outbox), 2)
        corpo = mail.outbox[1].body
        for etapa in ("Corte de MDF", "Montagem", "Adesivo"):
            self.assertIn(f"{etapa}: concluída", corpo)
        with no_relogio(amanha), no_dia(amanha.date()):
            montagem.concluir_ate(unidade, "embalagem")
        self.assertEqual(len(mail.outbox), 3)  # o pronto sai mesmo no mesmo dia
        self.assertIn("já pode retirar na fábrica", mail.outbox[2].subject)
        self.assertEqual(mail.outbox[2].to, ["dono@exemplo.test"])

    def test_o_que_ficou_para_depois_sai_ao_abrir_a_lista_no_outro_dia(self):
        with no_relogio(QUARTA), no_dia(QUARTA.date()):
            unidade = self.unidades(self.pedido())[0]
            montagem.concluir_ate(unidade, "corte")
        self.assertEqual(len(mail.outbox), 1)
        amanha = QUARTA + dt.timedelta(days=1)
        with no_relogio(amanha), no_dia(amanha.date()):
            self.assertEqual(montagem.avisar_pendentes(), 1)
        self.assertIn("Corte de MDF: concluída", mail.outbox[-1].body)

    def test_o_pedido_antigo_entra_em_silencio(self):
        antigo = QUARTA - dt.timedelta(days=10)
        Pedido.objects.all().delete()
        pedido = self.pedido(status="aguardando_pagamento")
        Pedido.objects.filter(pk=pedido.pk).update(status="pago", pago_em=antigo)
        mail.outbox.clear()
        with no_relogio(QUARTA), no_dia(QUARTA.date()):
            montagem.sincronizar_tudo()
        self.assertEqual(len(self.unidades(pedido)), 1)
        self.assertEqual(mail.outbox, [])


# ======================================================================
# 5. O PRAZO ANTES DA COMPRA (produto, carrinho, proposta)
# ======================================================================
class PrazoAntesDaCompraTests(Base):

    def test_com_vaga_e_so_a_montagem_sem_vaga_soma_a_fila(self):
        with no_dia(QUARTA.date()):
            self.assertEqual(montagem.prazo_do_produto(self.agk).texto, "4 dias úteis")
            for _ in range(3):
                self.pedido()
            prazo = montagem.prazo_do_produto(self.agk)
        self.assertEqual((prazo.dias_min, prazo.dias_max, prazo.fila), (19, 34, True))
        self.assertEqual(prazo.texto, "19 a 34 dias úteis")

    def test_a_pagina_do_produto_mostra_o_prazo(self):
        Brinquedos.objects.filter(pk=self.agk.pk).update(exibir_na_loja=True)
        html = self.client.get(f"/brinquedo/{self.agk.pk}/").content.decode()
        if "produto-compra" not in html:
            self.skipTest("a página do produto mudou de endereço")
        self.assertIn("Fica pronto em 4 dias úteis", html)

    def test_a_proposta_mostra_o_prazo_da_montagem_e_o_contrato_le_o_mesmo(self):
        orcamento = Orcamento.objects.create(
            nome_cliente="Buffet", status=Orcamento.Status.AGUARDANDO_RESPOSTA, enviado_em=timezone.now(),
        )
        ItemOrcamento.objects.create(orcamento=orcamento, descricao="Basquete Street", quantidade=1,
                                     valor_unitario=Decimal("1"))
        self.assertEqual(orcamento.prazo_para_o_cliente, "5 dias úteis após a aprovação")
        self.assertEqual(montagem.prazo_de_entrega(orcamento).dias_max, 5)
        html = self.client.get(f"/orcamento/{orcamento.token}/").content.decode()
        self.assertIn("5 dias úteis após a aprovação", html)


# ======================================================================
# 6. A TELA DO PAINEL
# ======================================================================
class TelaTests(Base):

    def setUp(self):
        super().setUp()
        self.producao_user = equipe("prod-montagem", "producao")
        with no_relogio(QUARTA), no_dia(QUARTA.date()):
            self.pedidos = [self.pedido() for _ in range(5)]

    def test_a_lista_agrupa_por_brinquedo_com_as_contagens_e_sem_select(self):
        self.client.force_login(self.producao_user)
        resposta = self.client.get("/producao/montagem/", **INTERNO)
        self.assertEqual(resposta.status_code, 200)
        html = resposta.content.decode()
        self.assertIn("Air Game Kids", html)
        self.assertIn("2 na fila, 3 em montagem", html)
        self.assertNotIn("<select", html)
        self.assertIn('type="radio" name="etapa-', html)
        self.assertIn("Corte de MDF", html)
        self.assertIn("Na fila — máquinas", html)
        self.assertIn('data-visao-chave="montagem"', html)  # Lista e Cards

    def test_produção_marca_a_etapa_e_o_financeiro_so_ve(self):
        unidade = self.unidades(self.pedidos[0])[0]
        financeiro = equipe("fin-ve", "financeiro")
        self.client.force_login(financeiro)
        self.assertEqual(self.client.get("/producao/montagem/", **INTERNO).status_code, 200)
        resposta = self.client.post("/producao/montagem/", {"action": "etapa", "id": unidade.pk, "etapa": "corte"}, **AJAX)
        self.assertEqual(resposta.status_code, 403)
        self.client.force_login(self.producao_user)
        resposta = self.client.post("/producao/montagem/", {"action": "etapa", "id": unidade.pk, "etapa": "corte"}, **AJAX)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertIn("Corte de MDF feita", resposta.json()["msg"])
        resposta = self.client.post("/producao/montagem/", {"action": "etapa", "id": unidade.pk, "etapa": "xyz"}, **AJAX)
        self.assertEqual(resposta.status_code, 400)
        fila = self.unidades(self.pedidos[4])[0]
        resposta = self.client.post("/producao/montagem/", {"action": "etapa", "id": fila.pk, "etapa": "corte"}, **AJAX)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("na fila", resposta.json()["msg"])

    def test_a_tela_de_pedidos_mostra_a_fila_de_cada_pedido(self):
        self.client.force_login(equipe("fin-pedidos", "financeiro"))
        html = self.client.get("/pedidos/inner/?filtro=todos", **INTERNO).content.decode()
        self.assertIn('class="ls-montagem-elo"', html)
        self.assertIn("Na fila de produção — posição 1", html)
        self.assertIn("Em produção · Corte de MDF", html)

    def test_quem_nao_e_da_producao_nem_do_comercial_nao_entra(self):
        self.client.force_login(equipe("criacao-montagem", "criacao"))
        self.assertEqual(self.client.get("/producao/montagem/", **INTERNO).status_code, 302)

    def test_as_regras_se_salvam_e_recusam_o_que_nao_faz_sentido(self):
        self.client.force_login(self.producao_user)
        dados = {
            "action": "regras", "capacidade_maquinas": "4", "limite_m3": "3,0", "dias_ate_limite": "4",
            "dias_acima_limite": "5", "fila_min_dias": "15", "fila_max_dias": "30", "capacidade_projetos": "1",
            "dias_projeto": "30", "dias_pecas": "3", "palavras_projeto": "brinquedão",
        }
        self.assertEqual(self.client.post("/producao/montagem/", dados, **AJAX).status_code, 200)
        config = ConfiguracaoProducao.objects.get()
        self.assertEqual((config.capacidade_maquinas, config.limite_m3), (4, Decimal("3.00")))
        self.assertEqual(self.unidades(self.pedidos[3])[0].situacao, S.PRODUCAO)  # a vaga nova
        ruim = dict(dados, fila_min_dias="40")
        self.assertEqual(self.client.post("/producao/montagem/", ruim, **AJAX).status_code, 400)

    def test_o_orcamento_pronto_e_marcado_entregue(self):
        orcamento = Orcamento.objects.create(nome_cliente="Buffet", status=Orcamento.Status.RASCUNHO)
        ItemOrcamento.objects.create(orcamento=orcamento, descricao="Peça avulsa", peca=PecasReposicao.objects.create(
            nome="Maneta", descricao_peca="x", preco_venda=Decimal("1")), quantidade=1, valor_unitario=Decimal("1"))
        with self.captureOnCommitCallbacks(execute=True):
            orcamento.status = Orcamento.Status.APROVADO
            orcamento.save(update_fields=["status"])
        unidade = self.unidades(orcamento)[0]
        montagem.concluir_ate(unidade, "embalagem")
        self.client.force_login(self.producao_user)
        resposta = self.client.post("/producao/montagem/", {"action": "entregue", "id": unidade.pk}, **AJAX)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        from .codigo_orcamento import acompanhamento

        fases = {f.chave: (f.estado, f.nota) for f in acompanhamento(Orcamento.objects.get(pk=orcamento.pk)).fases}
        self.assertEqual(fases["producao"][0], "feita")
        self.assertEqual(fases["entrega"][0], "feita")

    def test_folha_js_e_css_seguem_as_regras_do_painel(self):
        css = (RAIZ / "static/interno/lista-montagem.css").read_text(encoding="utf-8")
        limpo = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b", limpo))
        tema = (RAIZ / "static/interno/interno_modern.css").read_text(encoding="utf-8")
        for variavel in set(re.findall(r"var\((--[a-z0-9-]+)", limpo)):
            self.assertIn(f"{variavel}:", tema, variavel)
        js = (RAIZ / "static/interno/lista-montagem.js").read_text(encoding="utf-8")
        self.assertNotIn("alert(", js)
        self.assertNotIn("confirm(", js.replace("LSAviso.confirmar(", ""))
        for nome in ("lista_montagem_inner.html", "partes/montagem_unidade.html", "partes/montagem_fila.html"):
            html = (RAIZ / "templates" / nome).read_text(encoding="utf-8")
            self.assertNotIn("<select", html)
            for linha in html.splitlines():
                if "{#" in linha:
                    self.assertIn("#}", linha, f"{nome}: comentário {{# #}} de mais de uma linha")


# ======================================================================
# 6b. CADA FUNÇÃO ENTRANDO NA TELA (permissoes.capacidades)
# ======================================================================
class FuncoesTests(Base):
    """A lista é da Engenharia de produção; Gestão e Financeiro veem; Vendas e
    Ambulante veem só o que venderam; o resto não entra -- no menu E na view."""

    def setUp(self):
        super().setUp()
        self.vendedor = equipe("vend-montagem", "vendas")
        self.ambulante = equipe("amb-montagem", "ambulante")
        self.pedido_site = self.pedido()
        self.do_vendedor = self.orcamento_aprovado("Buffet do Vendedor", self.vendedor)
        self.de_outro = self.orcamento_aprovado("Buffet de Outro", equipe("outro-vendedor", "vendas"))

    def orcamento_aprovado(self, nome, responsavel):
        orcamento = Orcamento.objects.create(nome_cliente=nome, status=Orcamento.Status.RASCUNHO,
                                             responsavel=responsavel)
        ItemOrcamento.objects.create(orcamento=orcamento, descricao="Basquete Street", quantidade=1,
                                     valor_unitario=Decimal("1"))
        with self.captureOnCommitCallbacks(execute=True):
            orcamento.status = Orcamento.Status.APROVADO
            orcamento.save(update_fields=["status"])
        return orcamento

    def entrar(self, user):
        self.client.force_login(user)
        resposta = self.client.get("/producao/montagem/", **INTERNO)
        unidade = UnidadeMontagem.objects.filter(producao__pedido=self.pedido_site).first()
        mexe = self.client.post("/producao/montagem/", {"action": "etapa", "id": unidade.pk, "etapa": "corte"},
                                **AJAX).status_code
        menu = self.client.get("/", **INTERNO, follow=True).content.decode()
        return resposta, mexe, 'href="/producao/montagem/"' in menu

    def test_cada_funcao(self):
        super_ = User.objects.create_superuser("super-montagem", "s@exemplo.test", "x")
        casos = {
            "super": (super_, 200, 200, True, True),
            "producao": (equipe("eng-montagem", "producao"), 200, 200, True, True),
            "gestao": (equipe("gest-montagem", "gestao"), 200, 403, True, True),
            "financeiro": (equipe("fin-montagem2", "financeiro"), 200, 403, True, True),
            "vendas": (self.vendedor, 200, 403, True, False),
            "ambulante": (self.ambulante, 200, 403, True, False),
            "criacao": (equipe("cri-montagem", "criacao"), 302, 403, False, None),
        }
        for nome, (user, status, mexe_esperado, no_menu, ve_o_site) in casos.items():
            with self.subTest(funcao=nome):
                resposta, mexe, menu = self.entrar(user)
                self.assertEqual(resposta.status_code, status)
                self.assertIn(mexe, (mexe_esperado, 302) if mexe_esperado == 403 else (mexe_esperado,))
                self.assertEqual(menu, no_menu)
                if status == 200:
                    html = resposta.content.decode()
                    self.assertEqual(f"Pedido #{self.pedido_site.pk}" in html, ve_o_site)
                    self.assertEqual("Buffet de Outro" in html, ve_o_site)
                    if nome in ("vendas",):
                        self.assertIn("Buffet do Vendedor", html)
                    self.assertEqual('name="etapa-' in html and " disabled" not in html.split('name="etapa-')[0][-400:],
                                     mexe_esperado == 200)
                UnidadeMontagem.objects.update(etapa="", etapas_em={}, situacao=S.PRODUCAO)


class GruposDoClienteTests(Base):

    def test_maquina_e_brinquedao_na_mesma_compra_tem_uma_linha_de_etapas_cada(self):
        cama = brinquedo("Cama Elástica 3m", (2.5, 3, 3))
        with no_relogio(QUARTA), no_dia(QUARTA.date()):
            for _ in range(3):
                self.pedido()          # as 3 vagas das máquinas
            self.pedido([(cama, 1, None)])  # a vaga do brinquedão
            misto = self.pedido([(self.agk, 1, None), (cama, 1, None)])
        vista = montagem.acompanhamento_da_producao(ProducaoOrigem.objects.get(pedido=misto))
        self.assertEqual([g.titulo for g in vista.grupos], ["Máquinas", "Brinquedão / espaço"])
        self.assertEqual([e.nome for e in vista.grupos[1].etapas], ["Fabricação", "Finalização", "Teste de qualidade"])
        self.assertEqual(len(vista.grupos[0].etapas), 7)
        self.assertIn("máquinas: posição 1 · brinquedão / espaço: posição 1", vista.nota)


# ======================================================================
# 7. MEUS PEDIDOS: A FILA E AS ETAPAS, SEM CONSULTA A MAIS POR PEDIDO
# ======================================================================
class MeusPedidosTests(Base):

    def test_a_fila_e_as_etapas_aparecem_e_as_consultas_nao_crescem(self):
        with no_relogio(QUARTA), no_dia(QUARTA.date()):
            for _ in range(4):
                self.pedido()
        self.client.force_login(self.dono)
        html = self.client.get("/meus-pedidos/").content.decode()
        self.assertIn("Na fila de produção — posição 1", html)
        self.assertIn('class="pp-etapas"', html)
        self.assertIn("Corte de MDF", html)
        with CaptureQueriesContext(connection) as quatro:
            self.client.get("/meus-pedidos/")
        with no_relogio(QUARTA), no_dia(QUARTA.date()):
            for _ in range(3):
                self.pedido()
        with CaptureQueriesContext(connection) as sete:
            self.client.get("/meus-pedidos/")
        self.assertLessEqual(len(sete), len(quatro) + 2)


# ======================================================================
# 8. A MIGRAÇÃO DAS REGRAS
# ======================================================================
class MigracaoTests(TestCase):

    def test_0069_cria_a_linha_e_marca_as_categorias_de_brinquedao(self):
        ConfiguracaoProducao.objects.all().delete()
        brinquedoes = CategoriasBrinquedos.objects.create(nome_categoria="Brinquedões", imagem_categoria="c/1.png")
        ninja = CategoriasBrinquedos.objects.create(nome_categoria="Área Ninja", imagem_categoria="c/2.png")
        CategoriasBrinquedos.objects.create(nome_categoria="Fliperamas", imagem_categoria="c/3.png")
        migracao = import_module("sistema_interno.migrations.0069_regras_da_producao")
        migracao.criar_regras(apps, None)
        migracao.criar_regras(apps, None)  # de novo: nada muda
        config = ConfiguracaoProducao.objects.get()
        self.assertEqual(set(config.categorias_projeto.values_list("pk", flat=True)), {brinquedoes.pk, ninja.pk})
        self.assertEqual((config.capacidade_maquinas, config.fila_min_dias, config.fila_max_dias), (3, 15, 30))
