"""As análises gráficas e as fichas das telas de gestão (LEIA-ME-V10, seção 76).

O que estes testes protegem:
  * as janelas e os baldes de cada período, com data fixa (Hoje por hora,
    Semana e Mês por dia, 3 meses e Semestre por semana, Ano por mês, e o
    período de dias escolhido);
  * a comparação com o período ANTERIOR de mesmo tamanho, até o mesmo ponto;
  * "sem dados ainda" no lugar de zero inventado;
  * a permissão do endereço JSON é a da tela; cada tipo responde;
  * a ficha (modal de detalhes) de cada tipo, sem consulta por item do histórico;
  * a presença: "Online agora", "Visto há 2 h", e o middleware que NÃO grava
    a cada requisição;
  * o painel está nas telas, e o componente não usa <select>.

E, do AJUSTE da seção 76 (no fim do arquivo):
  * QUEM está online: o nome, o papel (Admin, Equipe, Cliente), onde está, há
    quanto tempo e quem é "você"; a barra de cima só recebe a equipe (nome de
    cliente não sai do servidor para quem não abre a tela Usuários); a
    permissão e a conta de consultas do /presenca/agora/;
  * o painel sem parede de caixas vazias: a métrica sem número vai marcada
    `vazia`, com o motivo, e a `principal` é a que tem dado; nenhum gráfico
    que "não existe" (colunas para pessoas distintas, as pessoas do dia em
    Hoje); as frases do período; a fonte que falha vira uma linha calma;
  * a lista de Usuários de 18 em 18, com os contadores de presença filtrando
    no servidor, os filtros viajando no paginador e nenhuma consulta por linha;
  * a ficha da conta, que abre pelo que importa: compras, presença, o que quer.
"""

import datetime as dt
import re
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from sistema_interno.models import Cliente, ItemOrcamento, Orcamento
from sistema_interno.permissoes import CRIACAO, FINANCEIRO, VENDAS

from . import analises, cliques, interacoes, presenca
from .analises_tipos import tipo as tipo_por_codigo
from .analises_tipos import tipos
from .detalhes import reais
from .models import (
    AcessoDiario,
    BrinquedoClick,
    Brinquedos,
    Combos,
    Cupom,
    Eventos,
    Favorito,
    InteracaoPorHora,
    ItemPedido,
    JogadaRegistrada,
    JogoCadastrado,
    PecasReposicao,
    Pedido,
    PresencaUsuario,
    Projetos,
    Promocoes,
)
from .tests_desempenho import CatalogoDeTeste

INTERNO = {"HTTP_HOST": "interno.testserver"}
FUSO = timezone.get_current_timezone()


def local(ano, mes, dia, hora=0, minuto=0):
    return timezone.make_aware(dt.datetime(ano, mes, dia, hora, minuto), FUSO)


#: quarta-feira, 11/11/2026, 15h30 no fuso do site
AGORA = local(2026, 11, 11, 15, 30)


def ingenuo(valor):
    return timezone.localtime(valor, FUSO).replace(tzinfo=None)


class JanelasEBaldesTests(TestCase):
    def test_hoje_vai_de_meia_noite_ate_agora_hora_a_hora(self):
        j = analises.janela("hoje", agora=AGORA)
        self.assertEqual((j.unidade, j.dias), ("hora", 1))
        self.assertEqual(j.inicio, local(2026, 11, 11))
        self.assertEqual(j.fim, AGORA)
        # o anterior é ontem ATÉ A MESMA HORA, não o dia inteiro de ontem
        self.assertEqual(j.anterior_inicio, local(2026, 11, 10))
        self.assertEqual(j.anterior_fim, local(2026, 11, 10, 15, 30))
        baldes = j.baldes()
        self.assertEqual(len(baldes), 24)
        self.assertEqual(baldes[0], dt.datetime(2026, 11, 11, 0))
        self.assertEqual(baldes[-1], dt.datetime(2026, 11, 11, 23))

    def test_semana_e_mes_por_dia(self):
        semana = analises.janela("semana", agora=AGORA)
        self.assertEqual(semana.inicio, local(2026, 11, 5))
        self.assertEqual(semana.anterior_inicio, local(2026, 10, 29))
        self.assertEqual(semana.unidade, "dia")
        self.assertEqual(len(semana.baldes()), 7)
        self.assertEqual(semana.baldes()[-1], dt.datetime(2026, 11, 11))

        mes = analises.janela("mes", agora=AGORA)
        self.assertEqual(mes.inicio, local(2026, 10, 13))
        self.assertEqual(mes.anterior_inicio, local(2026, 9, 13))
        self.assertEqual(len(mes.baldes()), 30)

    def test_tres_meses_e_semestre_por_semana_comecando_na_segunda(self):
        trimestre = analises.janela("trimestre", agora=AGORA)
        self.assertEqual(trimestre.dias, 90)
        self.assertEqual(trimestre.inicio, local(2026, 8, 14))
        baldes = trimestre.baldes()
        self.assertEqual(baldes[0], dt.datetime(2026, 8, 10))  # a segunda da semana de 14/08
        self.assertEqual(baldes[-1], dt.datetime(2026, 11, 9))  # a semana de hoje
        self.assertTrue(all(b.weekday() == 0 for b in baldes))
        self.assertEqual(len(baldes), 14)

        semestre = analises.janela("semestre", agora=AGORA)
        self.assertEqual(semestre.dias, 180)
        self.assertEqual(semestre.inicio, local(2026, 5, 16))
        self.assertEqual(semestre.unidade, "semana")
        self.assertEqual(semestre.baldes()[0], dt.datetime(2026, 5, 11))
        self.assertEqual(len(semestre.baldes()), 27)

    def test_ano_por_mes(self):
        ano = analises.janela("ano", agora=AGORA)
        self.assertEqual(ano.inicio, local(2025, 11, 12))
        self.assertEqual(ano.anterior_inicio, local(2024, 11, 12))
        baldes = ano.baldes()
        self.assertEqual(len(baldes), 13)
        self.assertEqual(baldes[0], dt.datetime(2025, 11, 1))
        self.assertEqual(baldes[-1], dt.datetime(2026, 11, 1))
        rotulos = [analises.rotulo_do_balde(b, "mes")[0] for b in baldes[:2]]
        self.assertEqual(rotulos, ["nov/25", "dez/25"])

    def test_dias_escolhidos(self):
        j = analises.janela("dias", agora=AGORA, de="2026-10-01", ate="2026-10-10")
        self.assertEqual((j.unidade, j.dias), ("dia", 10))
        self.assertEqual(j.inicio, local(2026, 10, 1))
        self.assertEqual(j.fim, local(2026, 10, 11))  # dia inteiro: até a meia-noite seguinte
        self.assertEqual(j.anterior_inicio, local(2026, 9, 21))
        self.assertEqual(j.anterior_fim, local(2026, 10, 1))  # colado no começo, sem vão
        self.assertEqual(len(j.baldes()), 10)
        # datas invertidas são desviradas; um dia só vira hora a hora; muitos dias, mês a mês
        self.assertEqual(analises.janela("dias", agora=AGORA, de="2026-10-10", ate="2026-10-01").dias, 10)
        self.assertEqual(analises.janela("dias", agora=AGORA, de="2026-11-03", ate="2026-11-03").unidade, "hora")
        self.assertEqual(analises.janela("dias", agora=AGORA, de="2026-01-01", ate="2026-08-30").unidade, "mes")
        # até hoje: o fim é agora, não a meia-noite de amanhã
        self.assertEqual(analises.janela("dias", agora=AGORA, de="2026-11-01", ate="2026-11-30").fim, AGORA)

    def test_periodos_invalidos(self):
        for codigo, extra in (
            ("semanal", {}),
            ("dias", {}),
            ("dias", {"de": "2026-12-01", "ate": "2026-12-05"}),
            ("dias", {"de": "2020-01-01", "ate": "2026-01-01"}),
            ("dias", {"de": "ontem", "ate": "hoje"}),
        ):
            with self.subTest(codigo=codigo, extra=extra), self.assertRaises(analises.PeriodoInvalido):
                analises.janela(codigo, agora=AGORA, **extra)


class VariacaoTests(CatalogoDeTeste, TestCase):
    def setUp(self):
        self.preparar_catalogo()
        self.povoar(2)
        Favorito.objects.all().delete()
        self.brinquedo, self.outro = Brinquedos.objects.order_by("id")[:2]

    def curtida(self, quando, brinquedo=None, tipo="curtida"):
        fav = Favorito.objects.create(
            tipo=tipo, brinquedo=brinquedo or self.brinquedo, dispositivo=f"{Favorito.objects.count():032d}",
        )
        Favorito.objects.filter(pk=fav.pk).update(criacao=quando)

    def metrica(self, dados, codigo):
        return next(m for m in dados["metricas"] if m["codigo"] == codigo)

    def calcular(self, periodo, **extra):
        return analises.calcular(tipo_por_codigo("brinquedo"), analises.janela(periodo, agora=AGORA), usar_cache=False, **extra)

    def test_semana_contra_a_semana_anterior(self):
        for dia in (5, 9, 11):
            self.curtida(local(2026, 11, dia, 10))
        for dia in (30, 31):
            self.curtida(local(2026, 10, dia, 10))
        self.curtida(local(2026, 10, 20, 10))  # fora das duas janelas
        curtidas = self.metrica(self.calcular("semana"), "curtidas")
        self.assertEqual((curtidas["total"], curtidas["anterior"]), (3, 2))
        self.assertEqual((curtidas["variacao"], curtidas["direcao"]), (50.0, "sobe"))
        self.assertEqual(curtidas["serie"], [1, 0, 0, 0, 1, 0, 1])
        # o anterior cai no MESMO dia da janela, recuado: 30/10 é o segundo dia (06/11)
        self.assertEqual(curtidas["serie_anterior"], [0, 1, 1, 0, 0, 0, 0])
        # dia da semana: 05/11 quinta, 09/11 segunda, 11/11 quarta
        self.assertEqual(curtidas["semana"], [1, 0, 1, 1, 0, 0, 0])
        self.assertFalse(curtidas["sem_dados"])

    def test_hoje_compara_com_ontem_ate_a_mesma_hora(self):
        self.curtida(local(2026, 11, 11, 10))
        self.curtida(local(2026, 11, 11, 14, 59))
        self.curtida(local(2026, 11, 10, 9))
        self.curtida(local(2026, 11, 10, 18))  # depois das 15h30 de ontem: não entra
        dados = self.calcular("hoje")
        curtidas = self.metrica(dados, "curtidas")
        self.assertEqual((curtidas["total"], curtidas["anterior"]), (2, 1))
        self.assertEqual(curtidas["direcao"], "sobe")
        self.assertEqual(curtidas["serie"][10], 1)
        self.assertEqual(curtidas["serie"][14], 1)
        self.assertIsNone(curtidas["serie"][16])  # as 16h ainda não chegaram
        self.assertTrue(dados["rotulos"][16]["futuro"])
        self.assertIsNone(curtidas["semana"])  # em Hoje não há dia da semana

    def test_queda_novo_e_estavel(self):
        self.curtida(local(2026, 10, 31, 10))
        self.curtida(local(2026, 11, 1, 10))
        self.curtida(local(2026, 11, 8, 10))
        curtidas = self.metrica(self.calcular("semana"), "curtidas")
        self.assertEqual((curtidas["variacao"], curtidas["direcao"]), (-50.0, "desce"))

        self.curtida(local(2026, 11, 9, 10), tipo="desejo")
        desejos = self.metrica(self.calcular("semana"), "desejos")
        self.assertEqual((desejos["total"], desejos["anterior"], desejos["direcao"]), (1, 0, "novo"))
        self.assertIsNone(desejos["variacao"])

    def test_ano_soma_cada_mes_e_poe_o_ano_anterior_no_mes_certo(self):
        self.curtida(local(2026, 3, 15, 10))
        self.curtida(local(2026, 3, 20, 10))
        self.curtida(local(2025, 3, 15, 10))
        curtidas = self.metrica(self.calcular("ano"), "curtidas")
        # março/2026 é o quinto balde (nov/25, dez, jan, fev, mar)
        self.assertEqual(curtidas["serie"][4], 2)
        self.assertEqual(curtidas["serie_anterior"][4], 1)
        self.assertEqual(sum(curtidas["serie"]), curtidas["total"])

    def test_sem_dados_nao_vira_zero(self):
        dados = self.calcular("mes")
        self.assertTrue(self.metrica(dados, "orcamentos")["sem_dados"])
        self.assertTrue(self.metrica(dados, "visitas")["sem_dados"])  # o registro por hora ainda não começou
        self.curtida(local(2026, 1, 5, 10))  # só fora da janela
        self.assertFalse(self.metrica(self.calcular("mes"), "curtidas")["sem_dados"])

    def test_visitas_registradas_depois_do_inicio_do_anterior_nao_comparam(self):
        interacoes.somar("visita", "brinquedo", self.brinquedo.pk, 7, hora=local(2026, 11, 10, 14))
        visitas = self.metrica(self.calcular("semana"), "visitas")
        self.assertEqual(visitas["total"], 7)
        self.assertEqual(visitas["direcao"], "sem_base")
        self.assertIsNone(visitas["variacao"])
        self.assertEqual(visitas["desde"], "2026-11-10")

    def test_ranking_e_objeto(self):
        for _ in range(3):
            self.curtida(local(2026, 11, 10, 10), brinquedo=self.outro)
        self.curtida(local(2026, 11, 10, 11))
        geral = self.metrica(self.calcular("semana"), "curtidas")
        self.assertEqual([(r["id"], r["valor"]) for r in geral["ranking"]], [(self.outro.pk, 3), (self.brinquedo.pk, 1)])
        self.assertEqual(geral["ranking"][0]["nome"], self.outro.nome_brinquedo)
        so_um = self.metrica(self.calcular("semana", objeto_id=self.brinquedo.pk), "curtidas")
        self.assertEqual(so_um["total"], 1)
        self.assertEqual(so_um["ranking"], [])

    def test_pedidos_receita_e_ticket(self):
        pago = Pedido.objects.create(status="pago", total_liquido=Decimal("300"))
        cancelado = Pedido.objects.create(status="cancelado", total_liquido=Decimal("900"))
        Pedido.objects.filter(pk__in=[pago.pk, cancelado.pk]).update(criacao=local(2026, 11, 10, 10))
        ItemPedido.objects.create(pedido=pago, tipo_item="brinquedo", object_id=self.brinquedo.pk, nome_item="x",
                                  preco_unitario=150, quantidade=2, subtotal=300)
        ItemPedido.objects.create(pedido=cancelado, tipo_item="brinquedo", object_id=self.brinquedo.pk, nome_item="x",
                                  preco_unitario=900, quantidade=1, subtotal=900)
        brinquedo = self.calcular("semana")
        self.assertEqual(self.metrica(brinquedo, "pedidos")["total"], 1)
        self.assertEqual(self.metrica(brinquedo, "receita")["total"], 300.0)
        loja = analises.calcular(tipo_por_codigo("pedido"), analises.janela("semana", agora=AGORA), usar_cache=False)
        self.assertEqual(self.metrica(loja, "criados")["total"], 2)
        self.assertEqual(self.metrica(loja, "pagos")["total"], 1)
        self.assertEqual(self.metrica(loja, "cancelados")["total"], 1)
        self.assertEqual(self.metrica(loja, "ticket")["total"], 300.0)
        itens = self.metrica(loja, "itens")
        self.assertEqual(itens["ranking"][0]["tipo"], "brinquedo")

    def test_ativos_conta_pessoas_distintas(self):
        conta = User.objects.create_user("ana")
        outra = User.objects.create_user("bia")
        for usuario, dia in ((conta, 9), (conta, 10), (outra, 10)):
            AcessoDiario.objects.create(usuario=usuario, dia=dt.date(2026, 11, dia),
                                        primeiro=local(2026, 11, dia, 9), ultimo=local(2026, 11, dia, 10))
        AcessoDiario.objects.create(usuario=conta, dia=dt.date(2026, 11, 1), primeiro=local(2026, 11, 1), ultimo=local(2026, 11, 1))
        dados = analises.calcular(tipo_por_codigo("usuario"), analises.janela("semana", agora=AGORA), usar_cache=False)
        ativos = self.metrica(dados, "ativos")
        self.assertEqual((ativos["total"], ativos["anterior"]), (2, 1))  # a mesma conta em dois dias é uma
        self.assertEqual(ativos["serie"][-3:], [1, 2, 0])
        self.assertIsNone(ativos["serie_anterior"])


class JogadasTests(CatalogoDeTeste, TestCase):
    """O portal de jogos (JogadaRegistrada, LEIA-ME 77): jogadas, pessoas e o ranking por jogo."""

    def setUp(self):
        self.preparar_catalogo()
        self.povoar(1)
        self.cadastrado = JogoCadastrado.objects.get()
        self.ana = User.objects.create_user("ana")
        self.bia = User.objects.create_user("bia", is_staff=True)

    def jogada(self, jogo, quando, usuario=None, visitante="", equipe=False, origem="pagina"):
        JogadaRegistrada.objects.create(jogo=jogo, usuario=usuario, visitante=visitante, equipe=equipe, origem=origem, quando=quando)

    def test_jogadas_pessoas_e_ranking(self):
        ontem = local(2026, 11, 10, 20)
        self.jogada("strike-kids", ontem, self.ana)
        self.jogada("strike-kids", ontem, self.ana)
        self.jogada("strike-kids", ontem, self.bia, equipe=True)
        self.jogada(self.cadastrado.slug, ontem, visitante="v1")
        self.jogada(self.cadastrado.slug, ontem, visitante="v2")
        self.jogada("strike-kids", local(2026, 11, 1, 20), self.ana)  # semana anterior
        dados = analises.calcular(tipo_por_codigo("jogo"), analises.janela("semana", agora=AGORA), usar_cache=False)
        m = {x["codigo"]: x for x in dados["metricas"]}
        self.assertEqual((m["jogadas"]["total"], m["jogadas"]["anterior"]), (5, 1))
        self.assertEqual(m["com_conta"]["total"], 2)
        self.assertEqual(m["visitantes"]["total"], 2)
        self.assertEqual(m["equipe"]["total"], 1)
        ranking = [(r["nome"], r["valor"], r["id"]) for r in m["jogadas"]["ranking"]]
        self.assertEqual(ranking, [("Strike Kids", 3, None), (self.cadastrado.nome, 2, self.cadastrado.pk)])
        so_um = analises.calcular(tipo_por_codigo("jogo"), analises.janela("semana", agora=AGORA), objeto_id=self.cadastrado.pk, usar_cache=False)
        self.assertEqual({x["codigo"]: x["total"] for x in so_um["metricas"]}["jogadas"], 2)

    def test_jogadas_da_conta_no_grafico_e_na_atividade(self):
        User.objects.filter(pk=self.ana.pk).update(date_joined=timezone.now() - dt.timedelta(days=2))
        self.jogada("strike-kids", timezone.now() - dt.timedelta(hours=1), self.ana, origem="casa")
        conta = analises.calcular(tipo_por_codigo("usuario"), analises.janela("semana"), objeto_id=self.ana.pk, usar_cache=False)
        self.assertEqual({x["codigo"]: x["total"] for x in conta["metricas"]}["jogadas"], 1)
        chefe = User.objects.create_superuser("chefe", "c@exemplo.com", "x")
        self.client.force_login(chefe)
        ficha = self.client.get(f"/detalhes/usuario/{self.ana.pk}/", **INTERNO).json()
        primeira = ficha["atividade"]["itens"][0]
        self.assertEqual((primeira["titulo"], primeira["texto"]), ("Jogou Strike Kids", "jogo da casa"))
        jogo = self.client.get(f"/detalhes/jogo/{self.cadastrado.pk}/", **INTERNO).json()
        self.assertEqual(jogo["titulo"], self.cadastrado.nome)


class EquipeMixin:
    def conta(self, nome, *funcoes, super_=False):
        if super_:
            return User.objects.create_superuser(nome, f"{nome}@exemplo.com", "x")
        usuario = User.objects.create_user(nome, f"{nome}@exemplo.com", "x")
        for funcao in funcoes:
            usuario.groups.add(Group.objects.get_or_create(name=funcao)[0])
        return usuario


class EnderecoJsonTests(EquipeMixin, CatalogoDeTeste, TestCase):
    def setUp(self):
        self.preparar_catalogo()
        self.povoar(2)
        self.brinquedo = Brinquedos.objects.order_by("id").first()

    def pedir(self, usuario, tipo, **parametros):
        self.client.logout()
        if usuario:
            self.client.force_login(usuario)
        return self.client.get(f"/analises/{tipo}/", parametros, **INTERNO)

    def test_permissao_e_a_da_tela(self):
        criacao = self.conta("criacao", CRIACAO)
        vendas = self.conta("vendas", VENDAS)
        financeiro = self.conta("fin", FINANCEIRO)
        chefe = self.conta("chefe", super_=True)
        cliente = User.objects.create_user("cliente")
        self.assertEqual(self.pedir(None, "brinquedo").status_code, 401)
        self.assertEqual(self.pedir(cliente, "brinquedo").status_code, 403)
        casos = [
            (criacao, "brinquedo", 200), (criacao, "promocao", 200), (criacao, "cupom", 200),
            (criacao, "cliente", 403), (criacao, "usuario", 403), (criacao, "pedido", 403),
            (vendas, "brinquedo", 403), (vendas, "cliente", 200), (vendas, "pedido", 403),
            (financeiro, "pedido", 200), (financeiro, "cupom", 403),
            (chefe, "usuario", 200), (chefe, "pedido", 200), (chefe, "cliente", 200),
            (criacao, "jogo", 403), (chefe, "jogo", 200),
        ]
        for usuario, tipo, esperado in casos:
            with self.subTest(usuario=usuario.username, tipo=tipo):
                resposta = self.pedir(usuario, tipo)
                self.assertEqual(resposta.status_code, esperado)
                self.assertEqual(resposta["Content-Type"], "application/json")

    def test_fora_do_painel_nao_existe(self):
        # no site público o endereço nem existe (a conta da equipe, lá, é mandada de volta ao painel)
        for rota in ("/analises/brinquedo/", f"/detalhes/brinquedo/{self.brinquedo.pk}/"):
            resposta = self.client.get(rota)
            self.assertIn(resposta.status_code, (301, 302, 404), rota)
            self.assertNotEqual(resposta.get("Content-Type"), "application/json", rota)

    def test_cada_tipo_responde_em_cada_periodo(self):
        self.client.force_login(self.conta("chefe", super_=True))
        objetos = {
            "brinquedo": self.brinquedo.pk, "combo": Combos.objects.first().pk, "promocao": Promocoes.objects.first().pk,
            "peca": PecasReposicao.objects.first().pk, "evento": Eventos.objects.first().pk, "projeto": Projetos.objects.first().pk,
            "jogo": JogoCadastrado.objects.first().pk,
        }
        for codigo in tipos():
            for periodo in ("hoje", "semana", "mes", "trimestre", "semestre", "ano"):
                with self.subTest(tipo=codigo, periodo=periodo):
                    resposta = self.client.get(f"/analises/{codigo}/", {"periodo": periodo}, **INTERNO)
                    self.assertEqual(resposta.status_code, 200, resposta.content[:200])
                    dados = resposta.json()
                    self.assertEqual(dados["periodo"]["codigo"], periodo)
                    self.assertTrue(dados["metricas"])
                    self.assertEqual(len(dados["rotulos"]), len(dados["metricas"][0]["serie"] or dados["rotulos"]))
            if codigo in objetos:
                resposta = self.client.get(f"/analises/{codigo}/", {"periodo": "mes", "id": objetos[codigo]}, **INTERNO)
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(resposta.json()["objeto"]["id"], objetos[codigo])

    def test_parametros_ruins(self):
        self.client.force_login(self.conta("chefe", super_=True))
        self.assertEqual(self.client.get("/analises/brinquedo/", {"periodo": "x"}, **INTERNO).status_code, 400)
        self.assertEqual(self.client.get("/analises/brinquedo/", {"id": "abc"}, **INTERNO).status_code, 400)
        self.assertEqual(self.client.get("/analises/brinquedo/", {"id": "999999"}, **INTERNO).status_code, 404)
        self.assertEqual(self.client.get("/analises/pedido/", {"id": "1"}, **INTERNO).status_code, 400)
        self.assertEqual(self.client.get("/analises/nada/", **INTERNO).status_code, 404)
        resposta = self.client.get("/analises/brinquedo/", {"periodo": "dias", "de": "2026-01-01", "ate": "2026-01-31"}, **INTERNO)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["periodo"]["unidade"], "dia")

    def test_poucas_consultas_e_cache(self):
        self.client.force_login(self.conta("chefe", super_=True))
        cache.clear()
        with CaptureQueriesContext(connection) as primeira:
            self.client.get("/analises/brinquedo/", {"periodo": "ano"}, **INTERNO)
        # 5 fontes x (série + semana + ranking) + nomes + cobertura + sessão. Os pontos de
        # retorno só existem dentro de uma transação (aqui, a do teste): no site não vão ao banco.
        consultas = [q["sql"] for q in primeira.captured_queries if "SAVEPOINT" not in q["sql"]]
        self.assertLess(len(consultas), 26, [sql[:80] for sql in consultas])
        with CaptureQueriesContext(connection) as segunda:
            self.client.get("/analises/brinquedo/", {"periodo": "ano"}, **INTERNO)
        self.assertLess(len(segunda), 6)  # só sessão e conta: o resto veio do cache


class FichaTests(EquipeMixin, CatalogoDeTeste, TestCase):
    def setUp(self):
        self.preparar_catalogo()
        self.povoar(2)
        self.chefe = self.conta("chefe", super_=True)
        self.brinquedo = Brinquedos.objects.order_by("id").first()
        cliente = Cliente.objects.create(nome_cliente="Buffet Alegria", telefone="(11) 98888-7777")
        self.cliente = cliente
        self.pedidos(3)
        Cupom.objects.create(codigo="BF10", desconto_percentual=Decimal("10"))

    def pedidos(self, quantos):
        for i in range(quantos):
            pedido = Pedido.objects.create(status="pago", total_liquido=Decimal("100"), cupom_codigo="BF10")
            ItemPedido.objects.create(pedido=pedido, tipo_item="brinquedo", object_id=self.brinquedo.pk, nome_item="x",
                                      preco_unitario=100, quantidade=1, subtotal=100)
            orcamento = Orcamento.objects.create(cliente=self.cliente, status="aprovado", respondido_em=timezone.now())
            ItemOrcamento.objects.create(orcamento=orcamento, descricao="x", brinquedo=self.brinquedo, valor_unitario=500)

    def ficha(self, tipo, pk, usuario=None, sufixo=""):
        self.client.force_login(usuario or self.chefe)
        return self.client.get(f"/detalhes/{tipo}/{pk}/{sufixo}", **INTERNO)

    def ids(self):
        return {
            "brinquedo": self.brinquedo.pk, "peca": PecasReposicao.objects.first().pk,
            "promocao": Promocoes.objects.first().pk, "combo": Combos.objects.first().pk,
            "cupom": Cupom.objects.first().pk, "evento": Eventos.objects.first().pk,
            "projeto": Projetos.objects.first().pk, "cliente": self.cliente.pk,
            "pedido": Pedido.objects.first().pk, "usuario": self.chefe.pk,
            "jogo": JogoCadastrado.objects.first().pk,
        }

    def test_os_graficos_de_cada_objeto_abrem_em_todo_periodo(self):
        """O "O servidor respondeu 500" da aba Gráficos da ficha do usuário no "Hoje": os
        dias com acesso só têm o DIA, e a conta tentava parti-los por hora. Aqui cada tipo
        com gráfico abre, com o objeto, em TODOS os períodos (era só o "mês")."""
        from . import views_analises
        from .models import AcessoDiario

        agora = timezone.now()
        for dias in (0, 1):
            AcessoDiario.objects.create(
                usuario=self.chefe, dia=timezone.localdate() - dt.timedelta(days=dias),
                primeiro=agora - dt.timedelta(days=dias), ultimo=agora - dt.timedelta(days=dias),
            )
        self.client.force_login(self.chefe)
        periodos = [{"periodo": p} for p in ("hoje", "semana", "mes", "trimestre", "semestre", "ano")]
        periodos.append({"periodo": "dias", "de": "2026-01-01", "ate": "2026-01-31"})
        for codigo, pk in self.ids().items():
            if not tipo_por_codigo(codigo).tem_objeto:
                continue
            for parametros in periodos:
                with self.subTest(tipo=codigo, **parametros):
                    cache.clear()
                    resposta = self.client.get(f"/analises/{codigo}/", {**parametros, "id": pk}, **INTERNO)
                    self.assertEqual(resposta.status_code, 200, resposta.content[:300])
                    dados = resposta.json()
                    self.assertEqual(dados["objeto"]["id"], pk)
                    self.assertFalse([m["codigo"] for m in dados["metricas"] if m.get("indisponivel")])
        # o usuário no "Hoje": os dias com acesso valem pelo total (1 hoje, 1 ontem), sem hora a hora
        cache.clear()
        hoje = self.client.get("/analises/usuario/", {"periodo": "hoje", "id": self.chefe.pk}, **INTERNO).json()
        acessos = next(m for m in hoje["metricas"] if m["serie"] is None)
        self.assertEqual(acessos["motivo_sem_serie"], "por_dia")
        self.assertEqual((acessos["total"], acessos["anterior"]), (1, 1))
        self.assertFalse(acessos["sem_dados"])
        self.assertTrue(any(m["serie"] is not None for m in hoje["metricas"]))  # as outras têm a série por hora
        self.assertNotIn("500", views_analises.FALHA_INESPERADA)

    def test_uma_fonte_com_defeito_nao_derruba_o_painel(self):
        """"você não pode me gerar uma coisa gerando erros": a fonte que falhar vai para o
        log e sai como indisponível; as outras continuam; nada fica em cache; e, se o
        inesperado for geral, a tela recebe uma frase de gente (não a página de erro)."""
        from unittest import mock

        from . import views_analises

        self.client.force_login(self.chefe)
        cache.clear()
        de_verdade = analises._acumular_aditiva

        def quebrada(fonte, *resto):
            if fonte.chave == "favoritos":
                raise RuntimeError("a consulta desta fonte falhou")
            return de_verdade(fonte, *resto)

        with mock.patch.object(analises, "_acumular_aditiva", quebrada), self.assertLogs("core.analises", "ERROR") as registro:
            resposta = self.client.get("/analises/usuario/", {"periodo": "mes", "id": self.chefe.pk}, **INTERNO)
        self.assertEqual(resposta.status_code, 200)
        metricas = resposta.json()["metricas"]
        fora = [m for m in metricas if m.get("indisponivel")]
        self.assertEqual(len(fora), 1)
        self.assertTrue(fora[0]["sem_dados"])
        self.assertTrue(any(not m.get("indisponivel") for m in metricas))
        self.assertIn("favoritos", registro.output[0])
        # não ficou em cache: a consulta seguinte, sã, vem inteira
        depois = self.client.get("/analises/usuario/", {"periodo": "mes", "id": self.chefe.pk}, **INTERNO).json()
        self.assertFalse([m for m in depois["metricas"] if m.get("indisponivel")])

        cache.clear()
        with mock.patch.object(analises, "calcular", side_effect=RuntimeError("geral")), \
                self.assertLogs("core.views_analises", "ERROR"):
            geral = self.client.get("/analises/usuario/", {"periodo": "mes"}, **INTERNO)
        self.assertEqual(geral.status_code, 500)
        self.assertEqual(geral.json()["erro"], views_analises.FALHA_INESPERADA)
        with mock.patch("core.detalhes.montar", side_effect=RuntimeError("geral")), \
                self.assertLogs("core.views_analises", "ERROR"):
            ficha = self.client.get(f"/detalhes/usuario/{self.chefe.pk}/", **INTERNO)
        self.assertEqual(ficha.status_code, 500)
        self.assertEqual(ficha.json()["erro"], views_analises.FALHA_INESPERADA)

    def test_cada_tipo_tem_ficha_com_resumo_e_atividade(self):
        for tipo, pk in self.ids().items():
            with self.subTest(tipo=tipo):
                resposta = self.ficha(tipo, pk)
                self.assertEqual(resposta.status_code, 200, resposta.content[:300])
                ficha = resposta.json()
                self.assertTrue(ficha["titulo"])
                self.assertTrue(ficha["secoes"])
                self.assertIn("itens", ficha["atividade"])
                self.assertEqual(ficha["tipo"], tipo)
                self.assertEqual(ficha["tem_graficos"], tipo != "pedido")
        self.assertEqual(self.ficha("brinquedo", 999999).status_code, 404)

    def test_campos_que_importam(self):
        brinquedo = self.ficha("brinquedo", self.brinquedo.pk).json()
        secoes = {s["titulo"]: s for s in brinquedo["secoes"]}
        rotulos = {c["rotulo"] for c in secoes["Ficha"]["campos"]}
        self.assertTrue({"Preço", "Medidas (A × L × P)", "Voltagem"} <= rotulos)
        self.assertIn("Fliperamas", secoes["Categorias e tags"]["etiquetas"])
        self.assertTrue(secoes["Fotos"]["fotos"])
        self.assertIn("Objeto 3D", secoes)
        self.assertTrue(secoes["Promoções com ele"]["lista"])
        titulos = [e["titulo"] for e in brinquedo["atividade"]["itens"]]
        self.assertTrue(any(t.startswith("Pedido nº") for t in titulos))
        self.assertTrue(any(t.startswith("Orçamento nº") for t in titulos))

        conta = self.ficha("usuario", self.chefe.pk).json()
        campos = {c["rotulo"]: c["valor"] for s in conta["secoes"] for c in s.get("campos", [])}
        for rotulo in ("E-mail", "Telefone", "Perfil", "Criada em", "Último login com senha", "Visto por último"):
            self.assertIn(rotulo, campos)
        self.assertEqual(campos["Perfil"], "Superadministrador")
        # sem sinal de vida gravado, vale o último login (o force_login acabou de marcar)
        self.assertTrue(conta["presenca"]["texto"].startswith("Entrou há"))
        nunca = User.objects.create_user("nunca")
        self.assertEqual(self.ficha("usuario", nunca.pk).json()["presenca"]["codigo"], "nunca")

    def test_nome_do_cliente_so_para_o_comercial(self):
        criacao = self.conta("criacao", CRIACAO)
        textos = [e["titulo"] for e in self.ficha("brinquedo", self.brinquedo.pk, criacao).json()["atividade"]["itens"]]
        self.assertFalse(any("Buffet Alegria" in t for t in textos))
        textos = [e["titulo"] for e in self.ficha("brinquedo", self.brinquedo.pk).json()["atividade"]["itens"]]
        self.assertTrue(any("Buffet Alegria" in t for t in textos))

    def test_permissao_da_ficha(self):
        criacao = self.conta("criacao", CRIACAO)
        self.assertEqual(self.ficha("brinquedo", self.brinquedo.pk, criacao).status_code, 200)
        self.assertEqual(self.ficha("usuario", self.chefe.pk, criacao).status_code, 403)
        self.assertEqual(self.ficha("cliente", self.cliente.pk, criacao).status_code, 403)
        self.assertEqual(self.ficha("pedido", Pedido.objects.first().pk, criacao).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(f"/detalhes/brinquedo/{self.brinquedo.pk}/", **INTERNO).status_code, 401)

    def test_atividade_paginada(self):
        self.pedidos(14)  # 17 pedidos e 17 orçamentos com o brinquedo
        primeira = self.ficha("brinquedo", self.brinquedo.pk).json()["atividade"]
        self.assertEqual((len(primeira["itens"]), primeira["tem_mais"]), (12, True))
        segunda = self.ficha("brinquedo", self.brinquedo.pk, sufixo="atividade/?pagina=2").json()
        self.assertEqual(segunda["pagina"], 2)
        self.assertEqual(len(segunda["itens"]), 12)
        momentos = [i["momento"] for i in primeira["itens"] + segunda["itens"]]
        self.assertEqual(momentos, sorted(momentos, reverse=True))

    def test_consultas_nao_crescem_com_o_historico(self):
        def contar(tipo, pk):
            self.client.force_login(self.chefe)
            with CaptureQueriesContext(connection) as consultas:
                self.assertEqual(self.client.get(f"/detalhes/{tipo}/{pk}/", **INTERNO).status_code, 200)
            return len(consultas)

        antes = {tipo: contar(tipo, pk) for tipo, pk in self.ids().items()}
        self.pedidos(10)
        depois = {tipo: contar(tipo, pk) for tipo, pk in self.ids().items()}
        for tipo in antes:
            with self.subTest(tipo=tipo):
                self.assertLessEqual(depois[tipo], antes[tipo] + 1, f"{tipo}: {antes[tipo]} -> {depois[tipo]}")
                self.assertLess(depois[tipo], 32)


class PresencaTests(EquipeMixin, TestCase):
    def test_textos_da_situacao(self):
        casos = [
            (AGORA - dt.timedelta(minutes=2), None, "Online agora"),
            (AGORA - dt.timedelta(minutes=12), None, "Visto há 12 min"),
            (AGORA - dt.timedelta(hours=3), None, "Visto há 3 h"),
            (local(2026, 11, 10, 14, 32), None, "Visto ontem às 14:32"),
            (local(2026, 11, 3, 9, 10), None, "Visto em 03/11 às 09:10"),
            (local(2025, 11, 3, 9, 10), None, "Visto em 03/11/2025"),
            (None, local(2026, 11, 9, 8, 5), "Entrou em 09/11 às 08:05"),
            (None, None, "Nunca entrou"),
        ]
        for visto, login, esperado in casos:
            with self.subTest(esperado=esperado):
                self.assertEqual(presenca.situacao(visto, login, agora=AGORA)["texto"], esperado)
        self.assertTrue(presenca.situacao(AGORA - dt.timedelta(minutes=4), None, agora=AGORA)["online"])
        self.assertFalse(presenca.situacao(AGORA - dt.timedelta(minutes=6), None, agora=AGORA)["online"])

    @override_settings(PRESENCA_DE_USUARIOS=True)
    def test_middleware_grava_no_maximo_uma_vez_por_minuto(self):
        cache.clear()
        conta = self.conta("ana", CRIACAO)
        self.client.force_login(conta)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.get("/minha-conta/", **INTERNO)
        primeiro = PresencaUsuario.objects.get(usuario=conta)
        self.assertEqual(primeiro.onde, "painel")
        self.assertEqual(AcessoDiario.objects.filter(usuario=conta).count(), 1)
        with CaptureQueriesContext(connection) as consultas, self.captureOnCommitCallbacks(execute=True) as pendentes:
            for _ in range(3):
                self.client.get("/minha-conta/", **INTERNO)
        self.assertEqual(pendentes, [], "o freio do cache deixou passar gravação")
        gravacoes = [q["sql"] for q in consultas.captured_queries if "core_presencausuario" in q["sql"] or "core_acessodiario" in q["sql"]]
        self.assertEqual(gravacoes, [], "o freio do cache deixou passar gravação")
        self.assertEqual(PresencaUsuario.objects.get(usuario=conta).visto_em, primeiro.visto_em)
        # passado o minuto (a chave do cache vence), grava de novo -- na mesma linha do dia
        cache.delete(f"{presenca.PREFIXO_CACHE}{conta.pk}")
        with self.captureOnCommitCallbacks(execute=True):
            self.client.get("/minha-conta/", **INTERNO)
        self.assertGreater(PresencaUsuario.objects.get(usuario=conta).visto_em, primeiro.visto_em)
        self.assertEqual(AcessoDiario.objects.filter(usuario=conta).count(), 1)

    @override_settings(PRESENCA_DE_USUARIOS=True)
    def test_visitante_anonimo_nao_ganha_consulta(self):
        cache.clear()
        with self.captureOnCommitCallbacks(execute=True) as pendentes:
            self.client.get("/privacidade/")
        self.assertEqual(pendentes, [])
        self.assertFalse(PresencaUsuario.objects.exists())

    def test_desligado_nos_testes_por_padrao(self):
        conta = self.conta("bia", CRIACAO)
        self.client.force_login(conta)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.get("/minha-conta/", **INTERNO)
        self.assertFalse(PresencaUsuario.objects.exists())

    def test_resumo_e_selo_na_lista(self):
        agora = timezone.now()
        chefe = self.conta("chefe", super_=True)
        online = User.objects.create_user("online")
        ontem = User.objects.create_user("ontem")
        User.objects.create_user("nunca")
        PresencaUsuario.objects.create(usuario=online, visto_em=agora - dt.timedelta(minutes=1))
        PresencaUsuario.objects.create(usuario=ontem, visto_em=agora - dt.timedelta(days=1, hours=1))
        numeros = presenca.resumo(agora)
        self.assertEqual(numeros["online"], 1)
        self.assertEqual(numeros["semana"], 2)
        self.assertEqual(numeros["nunca"], 2)  # o chefe (sem login nos testes) e "nunca"
        self.client.force_login(chefe)
        with CaptureQueriesContext(connection) as consultas:
            resposta = self.client.get("/site/contas-clientes/", **INTERNO)
        html = resposta.content.decode()
        self.assertIn("Online agora", html)
        self.assertIn("Nunca entrou", html)
        self.assertFalse([q for q in consultas.captured_queries if 'FROM "core_presencausuario"' in q["sql"]],
                         "o selo consultou a presença conta por conta")
        # os contadores do topo saíram da resposta das análises (que fica 2 min no cache): agora
        # vêm, com as pessoas, do /presenca/agora/, que a tela pergunta de novo a cada 45 s
        self.assertNotIn("destaques", analises.calcular(tipo_por_codigo("usuario"), analises.janela("mes"), usar_cache=False))
        cache.clear()
        agora_mesmo = self.client.get("/presenca/agora/", {"contas": 1}, **INTERNO).json()
        self.assertEqual({p["usuario"] for p in agora_mesmo["online"]}, {"online", "chefe"})  # quem olha está online
        self.assertEqual(agora_mesmo["numeros"]["nunca"], 1)  # o chefe acabou de entrar (force_login)


class InteracoesTests(CatalogoDeTeste, TestCase):
    def setUp(self):
        self.preparar_catalogo()
        self.povoar(1)
        self.brinquedo = Brinquedos.objects.get()

    def test_visita_vai_para_a_hora_certa(self):
        # fora da linha de fundo, a hora vai ao banco depois do commit (core/cliques.depois)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.get(f"/brinquedo/{self.brinquedo.pk}/")
            self.client.get(f"/brinquedo/{self.brinquedo.pk}/")
        linha = InteracaoPorHora.objects.get(evento="visita", alvo="brinquedo")
        self.assertEqual((linha.objeto_id, linha.quantidade), (self.brinquedo.pk, 2))
        self.assertEqual(linha.hora, interacoes.inicio_da_hora())
        peca = PecasReposicao.objects.get()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.get(f"/pecas/{peca.pk}/")
        self.assertEqual(InteracaoPorHora.objects.get(alvo="peca").quantidade, 1)

    def test_fila_de_fundo_separa_as_horas(self):
        from unittest import mock

        with override_settings(CLIQUES_EM_SEGUNDO_PLANO=True), mock.patch("core.cliques._garantir_linha"):
            with mock.patch("core.interacoes.inicio_da_hora", return_value=local(2026, 11, 11, 13)):
                cliques.registrar(BrinquedoClick, {"brinquedo_clicado_id": self.brinquedo.pk})
            with mock.patch("core.interacoes.inicio_da_hora", return_value=local(2026, 11, 11, 14)):
                cliques.registrar(BrinquedoClick, {"brinquedo_clicado_id": self.brinquedo.pk})
                cliques.registrar(BrinquedoClick, {"brinquedo_clicado_id": self.brinquedo.pk})
            self.assertEqual(cliques.gravar_pendentes(), 3)
        horas = dict(InteracaoPorHora.objects.values_list("hora", "quantidade"))
        self.assertEqual(horas, {local(2026, 11, 11, 13): 1, local(2026, 11, 11, 14): 2})

    def test_carrinho_do_site_e_do_aplicativo(self):
        conta = User.objects.create_user("compra", password="x")
        conta.perfil.telefone = "(11)91234-5678"
        conta.perfil.save()
        self.client.force_login(conta)
        self.brinquedo.exibir_na_loja = True
        self.brinquedo.save()
        with self.captureOnCommitCallbacks(execute=True):
            resposta = self.client.post(f"/carrinho/adicionar/brinquedo/{self.brinquedo.pk}/", {"quantidade": 2})
        self.assertEqual(resposta.status_code, 200, resposta.content[:200])
        self.assertEqual(InteracaoPorHora.objects.get(evento="carrinho").quantidade, 2)

        from rest_framework.test import APIClient

        api = APIClient()
        api.force_authenticate(conta)
        envio = {"itens": [{"tipo": "brinquedo", "item_id": self.brinquedo.pk, "quantidade": 3}]}
        with self.captureOnCommitCallbacks(execute=True):
            api.post("/api/v1/carrinho/sincronizar/", envio, format="json")
        with self.captureOnCommitCallbacks(execute=True):
            api.post("/api/v1/carrinho/sincronizar/", envio, format="json")  # reenviar não é pôr de novo
        app = InteracaoPorHora.objects.get(evento="carrinho", origem="app")
        self.assertEqual(app.quantidade, 1)  # tinha 2 (do site), passou a 3: acrescentou 1


class TelasTests(EquipeMixin, CatalogoDeTeste, TestCase):
    TELAS = {
        "/site/brinquedos/": "brinquedo",
        "/site/promocoes/": "promocao",
        "/site/combos/": "combo",
        "/site/cupons/": "cupom",
        "/site/eventos/": "evento",
        "/site/projetos/": "projeto",
        "/site/pecas/": "peca",
        "/site/clientes-mapa/": "cliente",
        "/site/contas-clientes/": "usuario",
        "/pedidos/inner/?filtro=todos": "pedido",
        "/site/jogos/": "jogo",
    }

    def setUp(self):
        self.preparar_catalogo()
        self.povoar(1)
        Cupom.objects.create(codigo="BF10", desconto_percentual=Decimal("10"))
        Cliente.objects.create(nome_cliente="Buffet", telefone="(11) 98888-7777", publicar_no_mapa=True)
        Pedido.objects.create(status="pago", total_liquido=Decimal("10"))
        self.client.force_login(self.conta("chefe", super_=True))

    def test_o_painel_e_a_ficha_estao_em_cada_tela(self):
        for rota, tipo in self.TELAS.items():
            with self.subTest(rota=rota):
                resposta = self.client.get(rota, **INTERNO)
                self.assertEqual(resposta.status_code, 200)
                html = resposta.content.decode()
                self.assertIn(f'data-lsa-painel data-lsa-tipo="{tipo}"', html)
                self.assertIn("data-lsa-ficha", html)
                self.assertIn("gestao-analises.js", html)
                if tipo != "cliente":  # o mapa só lista quem tem endereço publicado
                    self.assertIn(f'data-detalhe-tipo="{tipo}"', html)

    def test_o_componente_nao_tem_select(self):
        from django.contrib.auth.models import AnonymousUser

        request = RequestFactory().get("/", HTTP_HOST="interno.testserver")
        request.urlconf = "sistema_interno.urls"
        request.is_interno = True
        request.user = AnonymousUser()
        from django.urls import set_urlconf

        set_urlconf("sistema_interno.urls")
        try:
            html = render_to_string("gestao/includes/analises.html", {"tipo": "brinquedo"}, request=request)
        finally:
            set_urlconf(None)
        self.assertNotIn("<select", html)
        self.assertIn('type="radio"', html)
        for periodo in ("hoje", "semana", "mes", "trimestre", "semestre", "ano", "dias"):
            self.assertIn(f'value="{periodo}"', html)
        raiz = Path(__file__).resolve().parent / "static" / "site" / "paginas"
        js = (raiz / "gestao-analises.js").read_text(encoding="utf-8")
        css = (raiz / "gestao-analises.css").read_text(encoding="utf-8")
        self.assertNotIn('"select"', js)
        self.assertNotIn(".innerHTML", js)  # texto do banco entra por textContent
        # nada de cor escrita à mão: tudo pelas variáveis de tema
        import re

        self.assertFalse(re.findall(r"#[0-9a-fA-F]{3,8}\b", css), "cor fixa no CSS das análises")
        self.assertNotIn("http", js.replace("http://www.w3.org/2000/svg", ""))


class SementeTests(CatalogoDeTeste, TestCase):
    def test_semear_e_apagar_sem_tocar_no_resto(self):
        self.preparar_catalogo()
        self.povoar(1)
        antes = {
            "brinquedos": Brinquedos.objects.count(), "favoritos": Favorito.objects.count(),
            "contas": User.objects.count(), "pedidos": Pedido.objects.count(),
        }
        call_command("semear_analises", "--mesmo-assim", stdout=open("/dev/null", "w"))
        self.assertTrue(InteracaoPorHora.objects.filter(origem="exemplo").exists())
        self.assertGreater(Pedido.objects.count(), antes["pedidos"])
        dados = analises.calcular(tipo_por_codigo("brinquedo"), analises.janela("ano"), usar_cache=False)
        self.assertGreater(next(m for m in dados["metricas"] if m["codigo"] == "visitas")["total"], 0)
        call_command("semear_analises", "--apagar", "--mesmo-assim", stdout=open("/dev/null", "w"))
        depois = {
            "brinquedos": Brinquedos.objects.count(), "favoritos": Favorito.objects.count(),
            "contas": User.objects.count(), "pedidos": Pedido.objects.count(),
        }
        self.assertEqual(antes, depois)
        self.assertFalse(InteracaoPorHora.objects.exists())


# ======================================================================
# O AJUSTE DA SEÇÃO 76: QUEM ESTÁ ONLINE, O PAINEL EM ESTILO APP, A LISTA
# DE USUÁRIOS DE 18 EM 18 E A FICHA DA CONTA QUE ABRE PELO QUE IMPORTA
# ======================================================================

RAIZ_DO_PROJETO = Path(__file__).resolve().parent.parent
ESTATICOS_DO_PAINEL = RAIZ_DO_PROJETO / "sistema_interno" / "static" / "interno"
PAGINAS = Path(__file__).resolve().parent / "static" / "site" / "paginas"


class QuemEstaOnlineTests(EquipeMixin, TestCase):
    """"vc deve mostrar qual usuário está logado": quem, o papel, onde e há quanto tempo."""

    def setUp(self):
        cache.clear()
        self.agora = timezone.now()
        self.chefe = self.conta("chefe", super_=True)
        self.marina = self.conta("marina", VENDAS)                      # equipe pela função, sem is_staff
        self.caio = User.objects.create_user("caio", is_staff=True)     # equipe pelo staff
        self.quesia = User.objects.create_user("quesia")                # cliente do site
        self.quesia.perfil.nome_completo = "Quésia Souza"
        self.quesia.perfil.save()
        self.ontem = User.objects.create_user("ontem")
        User.objects.create_user("nunca")

    def presente(self, usuario, minutos, onde="site"):
        visto = self.agora - dt.timedelta(minutes=minutos)
        PresencaUsuario.objects.update_or_create(usuario=usuario, defaults={"visto_em": visto, "onde": onde})
        return visto

    def pedir(self, usuario, **parametros):
        self.client.logout()
        if usuario:
            self.client.force_login(usuario)
        cache.clear()
        return self.client.get("/presenca/agora/", parametros, **INTERNO)

    def test_a_faixa_diz_quem_o_papel_onde_e_quem_e_voce(self):
        self.presente(self.marina, 1, "painel")
        self.presente(self.caio, 3, "site")
        self.presente(self.quesia, 2, "app")
        self.presente(self.ontem, 60 * 20, "site")
        manha = timezone.localtime(self.agora).replace(hour=0, minute=7, second=0, microsecond=0)
        AcessoDiario.objects.create(usuario=self.marina, dia=manha.date(), primeiro=manha, ultimo=self.agora)

        resposta = self.pedir(self.chefe, contas=1)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Cache-Control"], "private, no-store")
        dados = resposta.json()
        online = {p["usuario"]: p for p in dados["online"]}
        self.assertEqual(set(online), {"chefe", "marina", "caio", "quesia"})
        # quem está olhando: sempre online, marcado "você", no painel -- mesmo sem sinal gravado
        self.assertEqual(
            (online["chefe"]["voce"], online["chefe"]["papel_rotulo"], online["chefe"]["onde_rotulo"]),
            (True, "Admin", "Painel"),
        )
        self.assertEqual(dados["eu"], self.chefe.pk)
        self.assertEqual(
            (online["marina"]["papel"], online["marina"]["papel_rotulo"], online["marina"]["onde_rotulo"], online["marina"]["quando"]),
            ("equipe", "Equipe", "Painel", "há 1 min"),
        )
        self.assertEqual(online["marina"]["desde"], "00:07")  # o primeiro sinal de hoje
        self.assertEqual((online["caio"]["papel"], online["caio"]["onde_rotulo"]), ("equipe", "Site"))
        self.assertEqual(
            (online["quesia"]["papel_rotulo"], online["quesia"]["nome"], online["quesia"]["iniciais"], online["quesia"]["onde_rotulo"]),
            ("Cliente", "Quésia Souza", "QS", "Aplicativo"),
        )
        self.assertFalse(online["quesia"]["voce"])
        self.assertEqual(online["quesia"]["cor"], self.quesia.pk % presenca.CORES_DE_AVATAR)  # a cor é da conta
        # vistos por último: quem passou nas últimas 24 h e não está online, com a hora
        self.assertEqual([p["usuario"] for p in dados["recentes"]], ["ontem"])
        self.assertTrue(dados["recentes"][0]["quando"].startswith(("ontem às", "há 20 h")), dados["recentes"][0]["quando"])
        self.assertFalse(dados["recentes"][0]["online"])
        # os contadores: os mesmos da lista
        self.assertEqual(dados["numeros"]["online"], 4)
        self.assertEqual(dados["numeros"]["total"], User.objects.count())
        self.assertEqual(dados["numeros"]["nunca"], 1)
        self.assertEqual(dados["intervalo"], 45)
        # a equipe é um recorte dos online: nenhum cliente
        self.assertEqual({p["usuario"] for p in dados["equipe"]}, {"chefe", "marina", "caio"})

    def test_a_barra_de_cima_so_recebe_a_equipe(self):
        self.presente(self.caio, 2, "painel")
        self.presente(self.quesia, 1, "site")
        resposta = self.pedir(self.marina)
        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertEqual([p["usuario"] for p in dados["equipe"]], ["marina", "caio"])  # quem olha vem primeiro
        self.assertTrue(dados["equipe"][0]["voce"])
        self.assertEqual(dados["equipe_total"], 2)
        for chave in ("online", "recentes", "numeros"):
            self.assertNotIn(chave, dados)
        # nome de cliente não sai do servidor para quem não abre a tela Usuários
        self.assertNotIn("quesia", resposta.content.decode().lower())
        self.assertNotIn("Quésia", resposta.content.decode())

    def test_a_permissao_e_a_da_tela(self):
        self.assertEqual(self.pedir(None).status_code, 401)
        self.assertEqual(self.pedir(self.quesia).status_code, 403)           # cliente não vê nem a equipe
        self.assertEqual(self.pedir(self.marina).status_code, 200)           # a equipe vê a equipe
        self.assertEqual(self.pedir(self.marina, contas=1).status_code, 403)  # as contas: só quem abre Usuários
        self.assertEqual(self.pedir(self.caio).status_code, 403)             # staff sem função não entra no painel
        self.assertEqual(self.pedir(self.chefe, contas=1).status_code, 200)
        # fora do painel o endereço não existe
        self.client.force_login(self.chefe)
        fora = self.client.get("/presenca/agora/")
        self.assertIn(fora.status_code, (301, 302, 404))
        self.assertNotEqual(fora.get("Content-Type"), "application/json")

    def test_as_consultas_nao_crescem_com_o_historico(self):
        def contar():
            self.client.force_login(self.chefe)
            cache.clear()
            with CaptureQueriesContext(connection) as consultas:
                self.assertEqual(self.client.get("/presenca/agora/", {"contas": 1}, **INTERNO).status_code, 200)
            return len(consultas)

        self.presente(self.marina, 1, "painel")
        antes = contar()
        for i in range(30):
            conta = User.objects.create_user(f"movimento{i}")
            self.presente(conta, i % 9, "site")
            for dia in range(1, 9):
                quando = self.agora - dt.timedelta(days=dia)
                AcessoDiario.objects.create(usuario=conta, dia=timezone.localtime(quando).date(), primeiro=quando, ultimo=quando)
        depois = contar()
        self.assertEqual(antes, depois)
        self.assertLess(depois, 10)
        # dez segundos de cache: a segunda pergunta não refaz as listas
        self.client.force_login(self.chefe)
        self.client.get("/presenca/agora/", {"contas": 1}, **INTERNO)
        with CaptureQueriesContext(connection) as consultas:
            self.client.get("/presenca/agora/", {"contas": 1}, **INTERNO)
        self.assertFalse([q["sql"] for q in consultas.captured_queries if "core_acessodiario" in q["sql"]])

    def test_o_que_falhar_vira_frase_e_nao_pagina_de_erro(self):
        from unittest import mock

        from . import views_analises

        self.client.force_login(self.chefe)
        with mock.patch.object(presenca, "agora_mesmo", side_effect=RuntimeError("banco fora")), \
                self.assertLogs("core.views_analises", "ERROR"):
            resposta = self.client.get("/presenca/agora/", **INTERNO)
        self.assertEqual(resposta.status_code, 500)
        self.assertEqual(resposta.json()["erro"], views_analises.FALHA_INESPERADA)

    def test_os_grupos_da_linha_sao_os_dos_contadores(self):
        self.presente(self.marina, 0)
        self.presente(self.ontem, 60 * 24 * 3)
        velho = User.objects.create_user("velho")
        self.presente(velho, 60 * 24 * 40)
        numeros = presenca.resumo(self.agora)
        contas = User.objects.select_related("presenca")
        for grupo in presenca.GRUPOS:
            with self.subTest(grupo=grupo):
                pelo_filtro = set(User.objects.filter(presenca.filtro_do_grupo(grupo, self.agora)).values_list("username", flat=True))
                pela_linha = {c.username for c in contas if grupo in presenca.grupos_da_conta(c, self.agora)}
                self.assertEqual(pelo_filtro, pela_linha)
                self.assertEqual(numeros[grupo], len(pelo_filtro))
        self.assertEqual(presenca.grupos_da_conta(self.marina, self.agora), ["online", "hoje", "semana", "mes"])
        self.assertEqual(presenca.grupos_da_conta(velho, self.agora), [])
        self.assertEqual(presenca.iniciais("Heitor Costa"), "HC")
        self.assertEqual(presenca.iniciais("teste_orc"), "TO")
        self.assertEqual(presenca.iniciais("ana"), "AN")


class PainelCoerenteTests(EquipeMixin, CatalogoDeTeste, TestCase):
    """Sem parede de caixas vazias, sem gráfico pedindo desculpa, com as frases que fecham."""

    def setUp(self):
        self.preparar_catalogo()
        self.povoar(1)
        self.brinquedo = Brinquedos.objects.order_by("id").first()
        self.ana = User.objects.create_user("ana")
        self.bia = self.conta("bia", VENDAS)
        # as contas do teste nascem "agora" (o relógio da máquina): aqui, numa data fixa, fora de toda janela
        User.objects.update(date_joined=local(2026, 1, 5, 10))

    def metrica(self, dados, codigo):
        return next(m for m in dados["metricas"] if m["codigo"] == codigo)

    def calcular(self, tipo, periodo, **extra):
        janela = analises.janela(periodo, agora=AGORA, de=extra.pop("de", None), ate=extra.pop("ate", None))
        return analises.calcular(tipo_por_codigo(tipo), janela, usar_cache=False, **extra)

    def acesso(self, usuario, dia, das=9, ate=10):
        return AcessoDiario.objects.create(
            usuario=usuario, dia=dt.date(2026, 11, dia), primeiro=local(2026, 11, dia, das), ultimo=local(2026, 11, dia, ate, 28),
        )

    def test_a_metrica_sem_numero_dobra_e_a_principal_e_a_que_tem_dado(self):
        self.acesso(self.ana, 10)
        self.acesso(self.bia, 9)
        dados = self.calcular("usuario", "semana")
        # ninguém se cadastrou na janela nem na anterior (as contas são de janeiro): vazia, com o motivo
        cadastros = self.metrica(dados, "cadastros")
        self.assertEqual((cadastros["vazia"], cadastros["sem_dados"]), (True, False))
        self.assertEqual(cadastros["motivo"], "Sem movimento neste período nem no anterior.")
        pedidos = self.metrica(dados, "pedidos")
        self.assertEqual((pedidos["vazia"], pedidos["sem_dados"], pedidos["motivo"]), (True, True, "Nenhum registro até hoje."))
        ativos = self.metrica(dados, "ativos")
        self.assertEqual((ativos["vazia"], ativos["motivo"], ativos["total"]), (False, "", 2))
        # "cadastros" é a principal do tipo, mas está vazia: o gráfico abre na primeira que tem dado
        self.assertEqual(tipo_por_codigo("usuario").principal, "cadastros")
        self.assertEqual(dados["principal"], "ativos")
        # o tom do ícone sai da ordem das métricas, nunca do valor (e não usa verde, vermelho nem o laranja)
        self.assertTrue(all(m["tom"] in analises.TONS for m in dados["metricas"]))
        self.assertFalse({"acento", "green", "red"} & set(analises.TONS))
        # a queda de verdade (zero agora, algo antes) continua com cartão: não é "vazia"
        antes = self.calcular("usuario", "hoje")
        self.assertFalse(self.metrica(antes, "ativos")["vazia"])  # 0 hoje, 1 ontem
        self.assertEqual(self.metrica(antes, "ativos")["direcao"], "desce")

    def test_o_registro_que_comecou_depois_diz_desde_quando(self):
        interacoes.somar("visita", "brinquedo", self.brinquedo.pk, 7, hora=local(2026, 11, 10, 14))
        dados = self.calcular("brinquedo", "dias", de="2026-11-01", ate="2026-11-03")
        visitas = self.metrica(dados, "visitas")
        self.assertTrue(visitas["vazia"])
        self.assertEqual(visitas["motivo"], "Registrado desde 10/11/2026: nada neste período.")

    def test_contas_ativas_nunca_pede_um_grafico_que_nao_existe(self):
        self.acesso(self.ana, 11, das=8, ate=15)
        self.acesso(self.bia, 11, das=9, ate=9)
        self.acesso(self.ana, 10)
        self.acesso(self.ana, 9)
        # Hoje: o acesso só guarda o dia. No lugar de colunas por hora, as PESSOAS do dia
        hoje = self.metrica(self.calcular("usuario", "hoje"), "ativos")
        self.assertIsNone(hoje["serie"])
        self.assertEqual(hoje["pessoas"]["total"], 2)
        ana, bia = hoje["pessoas"]["itens"]  # do último sinal para trás
        self.assertEqual((ana["nome"], ana["de"], ana["ate"], ana["inicio"], ana["fim"]), ("ana", "08:00", "15:28", 480, 928))
        self.assertEqual((bia["papel_rotulo"], bia["de"], bia["ate"]), ("Equipe", "09:00", "09:28"))
        self.assertFalse(hoje["pessoas"]["da_conta"])
        self.assertEqual(hoje["ranking"], [])            # "dias com acesso" num dia só não é ranking
        self.assertFalse(hoje["tem_ranking"])
        # Semana: uma coluna por dia (pessoas distintas não se ligam com uma linha) e o ranking "Mais ativos"
        dados = self.calcular("usuario", "semana")
        semana = self.metrica(dados, "ativos")
        self.assertEqual((semana["forma"], semana["distinta"]), ("colunas", True))
        self.assertEqual(semana["serie"][-3:], [1, 1, 2])
        self.assertIsNone(semana["pessoas"])
        self.assertEqual(dados["ranking_titulo"], "Mais ativos")
        self.assertEqual(semana["ranking_unidade"], ["dia com acesso", "dias com acesso"])
        primeiro, segundo = semana["ranking"]
        self.assertEqual((primeiro["nome"], primeiro["valor"]), ("ana", 3))  # dias com acesso de cada conta
        self.assertEqual((segundo["nome"], segundo["valor"]), ("bia", 1))
        self.assertEqual(primeiro["avatar"], {"iniciais": "AN", "cor": self.ana.pk % presenca.CORES_DE_AVATAR})
        self.assertTrue(primeiro["detalhe"].startswith(("Visto", "Entrou", "Nunca", "Online")))
        self.assertEqual(self.metrica(self.calcular("brinquedo", "semana"), "curtidas")["forma"], "linha")

    def test_pessoas_distintas_por_hora_quando_a_fonte_guarda_a_hora(self):
        for hora, usuario in ((9, self.ana), (9, self.bia), (9, self.ana), (14, self.ana)):
            jogada = JogadaRegistrada.objects.create(jogo="corrida", usuario=usuario)
            JogadaRegistrada.objects.filter(pk=jogada.pk).update(quando=local(2026, 11, 11, hora, 5))
        com_conta = self.metrica(self.calcular("jogo", "hoje"), "com_conta")
        self.assertEqual(com_conta["total"], 2)
        self.assertEqual((com_conta["serie"][9], com_conta["serie"][14], com_conta["serie"][10]), (2, 1, 0))
        self.assertIsNone(com_conta["serie"][20])  # a hora que ainda não chegou
        self.assertEqual(com_conta["forma"], "colunas")

    def test_os_cadastros_recentes_entram_no_lugar_do_ranking(self):
        User.objects.filter(pk=self.ana.pk).update(date_joined=local(2026, 11, 10, 9, 30))
        User.objects.filter(pk=self.bia.pk).update(date_joined=local(2026, 11, 11, 8, 5))
        cadastros = self.metrica(self.calcular("usuario", "semana"), "cadastros")
        self.assertEqual(cadastros["total"], 2)
        lista = cadastros["lista"]
        self.assertEqual(lista["titulo"], "Cadastros mais recentes")
        self.assertEqual([(i["nome"], i["detalhe"], i["quando"]) for i in lista["itens"]],
                         [("bia", "Equipe", "11/11, 08:05"), ("ana", "Cliente", "10/11, 09:30")])
        self.assertEqual(lista["itens"][0]["tipo"], "usuario")

    def test_as_frases_do_periodo(self):
        hoje = analises.janela("hoje", agora=AGORA).textos()
        self.assertEqual(hoje, {
            "titulo": "Hoje, 11/11, até 15:30", "comparacao": "comparado com ontem até a mesma hora", "anterior_curto": "ontem",
        })
        mes = analises.janela("mes", agora=AGORA).textos()
        self.assertEqual(mes["titulo"], "Últimos 30 dias (13/10 a 11/11)")
        self.assertEqual(mes["comparacao"], "comparado com os 30 dias anteriores (13/09 a 12/10)")
        self.assertEqual(mes["anterior_curto"], "antes")
        ano = analises.janela("ano", agora=AGORA).textos()
        self.assertEqual(ano["titulo"], "Últimos 365 dias (12/11/2025 a 11/11/2026)")  # o ano aparece quando muda
        dias = analises.janela("dias", agora=AGORA, de="2026-10-01", ate="2026-10-10").textos()
        self.assertEqual(dias["titulo"], "De 01/10 a 10/10 (10 dias)")
        self.assertEqual(dias["comparacao"], "comparado com os 10 dias anteriores (21/09 a 30/09)")
        um_dia = analises.janela("dias", agora=AGORA, de="2026-11-03", ate="2026-11-03").textos()
        self.assertEqual((um_dia["titulo"], um_dia["anterior_curto"]), ("Dia 03/11", "dia anterior"))
        dados = self.calcular("usuario", "mes")
        self.assertEqual(dados["periodo"]["descricao"], mes["titulo"] + " · " + mes["comparacao"])
        self.assertEqual((dados["periodo"]["titulo"], dados["periodo"]["anterior_curto"]), (mes["titulo"], "antes"))
        # nada de jargão nos avisos nem nas dicas que a tela mostra
        for tipo in tipos().values():
            for texto in list(tipo.avisos) + [m.ajuda for m in tipo.metricas]:
                with self.subTest(texto=texto[:40]):
                    self.assertNotRegex(texto, r"LEIA-ME|seção \d|core/|\.py")

    def test_a_fonte_que_falha_vira_uma_linha_calma(self):
        from unittest import mock

        de_verdade = analises._acumular_aditiva

        def quebrada(fonte, *resto):
            if fonte.chave == "favoritos":
                raise RuntimeError("a consulta desta fonte falhou")
            return de_verdade(fonte, *resto)

        self.acesso(self.ana, 10)
        with mock.patch.object(analises, "_acumular_aditiva", quebrada), self.assertLogs("core.analises", "ERROR"):
            dados = self.calcular("usuario", "semana")
        favoritos = self.metrica(dados, "favoritos")
        self.assertEqual((favoritos["indisponivel"], favoritos["vazia"]), (True, True))
        self.assertTrue(favoritos["motivo"].startswith("Não deu para carregar agora"))
        self.assertEqual(dados["principal"], "ativos")  # o gráfico abre numa métrica que veio

    def test_a_tela_nao_tem_mais_as_frases_do_desenho_antigo(self):
        js = (PAGINAS / "gestao-analises.js").read_text(encoding="utf-8")
        css = (PAGINAS / "gestao-analises.css").read_text(encoding="utf-8")
        for frase in ("hora a hora não existe", '"sem dados ainda"', '"estável"', '"sem base anterior"', "Ninguém pontuou"):
            with self.subTest(frase=frase):
                self.assertNotIn(frase, js)
        for frase in ("Ainda sem registro neste período: ", "Não deu para carregar agora: ", "Quem esteve ativo hoje",
                      "Sem movimento no período", "Ver os números em tabela", "lsa-esqueleto"):
            with self.subTest(frase=frase):
                self.assertIn(frase, js)
        # os recados são o toast de aplicativo (LSAviso): a atualização que falhou, a métrica que não
        # carregou e a faixa "Agora" sem rede avisam sem tirar nada da tela -- e sem alert() nem confirm()
        self.assertIn("window.LSAviso.toast({", js)
        for titulo in ("Os números não atualizaram", "Alguns números não carregaram", "Sem conexão com o servidor"):
            with self.subTest(titulo=titulo):
                self.assertIn(titulo, js)
        self.assertNotRegex(js, r"\b(alert|confirm)\(")
        self.assertNotIn("Failed to fetch", js)
        # a tabela continua (o gêmeo acessível de todo gráfico), para a série e para as pessoas do dia
        self.assertIn("Analise.prototype.tabela = ", js)
        self.assertIn("Analise.prototype.tabelaDePessoas = ", js)
        # movimento reduzido respeitado, a régua de períodos gruda, a grade é do contêiner
        self.assertIn("@media (prefers-reduced-motion:reduce)", css)
        self.assertRegex(css, r"\.lsa-barra\{\s*position:sticky")
        self.assertIn("@container lsa (min-width:1040px)", css)
        self.assertIn("scroll-snap-type:x mandatory", css)
        # o laranja não entra transparente em fundo (vira marrom sobre o ameixa): só em contorno de foco
        fundos = re.findall(r"background:[^;}]*rgba\(var\(--lsa-t-acento-rgb\)[^;}]*", css)
        self.assertEqual(fundos, [])


class ListaDeUsuariosTests(EquipeMixin, TestCase):
    """18 por página, com os filtros de presença no servidor e a mesma pessoa em todo lugar."""

    def setUp(self):
        cache.clear()
        self.agora = timezone.now()
        self.chefe = self.conta("chefe", super_=True)
        self.contas = [User.objects.create_user(f"conta{i:02d}", email=f"conta{i:02d}@exemplo.com") for i in range(40)]
        self.client.force_login(self.chefe)

    def abrir(self, **parametros):
        return self.client.get("/site/contas-clientes/", parametros, **INTERNO)

    def linhas(self, resposta):
        return re.findall(r'<tr data-visao-item data-detalhe-tipo="usuario" data-detalhe-id="(\d+)"', resposta.content.decode())

    def test_dezoito_por_pagina(self):
        primeira = self.abrir()
        html = primeira.content.decode()
        self.assertEqual(len(self.linhas(primeira)), 18)
        self.assertEqual(primeira.context["pagina"].paginator.count, 41)
        self.assertEqual(primeira.context["pagina"].paginator.num_pages, 3)
        self.assertIn("Exibindo <strong>1–18</strong> de", html)
        self.assertIn('<nav class="ls-pager" aria-label="Páginas da lista de contas">', html)
        self.assertIn("<strong>1–18</strong> de 41", html)
        self.assertIn('href="?page=2#usrContas"', html)        # a tela chega na lista, não no topo
        self.assertIn('aria-current="page"', html)
        self.assertIn('id="usrContas" data-lsa-ancora', html)
        self.assertNotIn('rel="prev"', html)                   # na primeira, o "Anterior" fica parado
        segunda = self.abrir(page=2)
        self.assertEqual(len(self.linhas(segunda)), 18)
        self.assertIn("<strong>19–36</strong> de 41", segunda.content.decode())
        self.assertFalse(set(self.linhas(primeira)) & set(self.linhas(segunda)))
        terceira = self.abrir(page=3)
        self.assertEqual(len(self.linhas(terceira)), 5)
        self.assertNotIn('rel="next"', terceira.content.decode())
        # a página que não existe cai na última; texto no lugar do número, na primeira
        self.assertEqual(self.abrir(page=99).context["pagina"].number, 3)
        self.assertEqual(self.abrir(page="abc").context["pagina"].number, 1)
        # as três páginas, juntas, são todas as contas, cada uma uma vez
        todas = self.linhas(primeira) + self.linhas(segunda) + self.linhas(terceira)
        self.assertEqual(sorted(map(int, todas)), sorted(User.objects.values_list("pk", flat=True)))

    def test_os_filtros_viajam_no_paginador(self):
        resposta = self.abrir(q="conta", tipo="clientes", page=2)
        self.assertEqual(resposta.context["pagina"].number, 2)
        self.assertEqual(resposta.context["pagina"].paginator.count, 40)
        html = resposta.content.decode()
        self.assertIn('href="?q=conta&amp;tipo=clientes&amp;page=1#usrContas"', html)
        self.assertIn('href="?q=conta&amp;tipo=clientes&amp;page=3#usrContas"', html)
        self.assertIn("Exibindo <strong>19–36</strong> de", html)
        # a busca que não acha nada: o estado vazio de sempre, sem paginador
        vazio = self.abrir(q="ninguém com este nome").content.decode()
        self.assertIn("Nenhum usuário encontrado", vazio)
        self.assertNotIn('class="ls-pager"', vazio)

    def test_o_contador_filtra_no_servidor_e_segue_pelas_paginas(self):
        for i, conta in enumerate(self.contas[:20]):
            PresencaUsuario.objects.create(usuario=conta, visto_em=self.agora - dt.timedelta(seconds=10 + i), onde="site")
        PresencaUsuario.objects.create(usuario=self.contas[25], visto_em=self.agora - dt.timedelta(days=3), onde="app")
        resposta = self.abrir(presenca="online")
        html = resposta.content.decode()
        self.assertEqual(resposta.context["pagina"].paginator.count, 20)
        self.assertEqual(len(self.linhas(resposta)), 18)
        self.assertIn('data-lsa-filtro-aviso="online"', html)
        self.assertIn("<strong>20 contas</strong> online agora", html)
        self.assertIn('href="?presenca=online&amp;page=2#usrContas"', html)
        self.assertIn('<a class="lsa-filtro-limpar" href="?#usrContas">Mostrar todas</a>', html)
        self.assertIn('<input type="hidden" name="presenca" value="online">', html)  # a busca não perde o filtro
        self.assertEqual(len(self.linhas(self.abrir(presenca="online", page=2))), 2)
        # cada linha diz em que contadores entra (o ponto verde do avatar sai daí) e o selo salta aos olhos
        self.assertIn('data-presenca="online hoje semana mes"', html)
        self.assertIn('class="lsa-presenca is-online" data-lsa-selo', html)
        # cada contador mostra exatamente as contas que conta
        numeros = presenca.resumo()
        for grupo in presenca.GRUPOS:
            with self.subTest(grupo=grupo):
                self.assertEqual(self.abrir(presenca=grupo).context["pagina"].paginator.count, numeros[grupo])
        semana = self.abrir(presenca="semana").content.decode()
        self.assertIn(f"<strong>{numeros['semana']} contas</strong> ativas nos últimos 7 dias", semana)
        nunca = self.abrir(presenca="nunca", q="conta39").content.decode()
        self.assertIn("<strong>1 conta</strong> que nunca entrou na busca", nunca)
        self.assertIn('href="?q=conta39#usrContas">Mostrar todas</a>', nunca)
        # o que não é contador é ignorado
        self.assertEqual(self.abrir(presenca="qualquer").context["pagina"].paginator.count, 41)
        self.assertNotIn("data-lsa-filtro-aviso", self.abrir(presenca="qualquer").content.decode())

    def test_nenhuma_consulta_por_linha(self):
        def contar(**parametros):
            with CaptureQueriesContext(connection) as consultas:
                self.assertEqual(self.abrir(**parametros).status_code, 200)
            return consultas

        self.abrir()  # aquece o que é da sessão
        cheia = contar()
        curta = contar(page=3)  # 5 linhas no lugar de 18
        self.assertEqual(len(cheia), len(curta), [q["sql"][:90] for q in cheia.captured_queries])
        self.assertFalse([q for q in cheia.captured_queries if 'FROM "core_presencausuario"' in q["sql"]])
        self.assertFalse([q for q in cheia.captured_queries if 'FROM "auth_group"' in q["sql"]],
                         "o papel de cada linha foi perguntado conta por conta")

    def test_a_linha_usa_as_iniciais_a_cor_e_o_papel_da_faixa(self):
        marina = self.conta("marina", VENDAS)
        marina.perfil.nome_completo = "Marina Albuquerque"
        marina.perfil.save()
        html = self.abrir(q="marina").content.decode()
        self.assertIn(f'<span class="usr-avatar lsa-avatar is-c{marina.pk % presenca.CORES_DE_AVATAR}" aria-hidden="true">MA</span>', html)
        self.assertIn('<span class="usr-chip is-staff">Equipe</span>', html)  # equipe pela função, sem is_staff
        self.assertIn('<span class="usr-chip is-super">Admin</span>', self.abrir(q="chefe").content.decode())
        self.assertIn('<span class="usr-chip is-client">Cliente</span>', self.abrir(q="conta00").content.decode())

    def test_a_faixa_agora_so_na_tela_de_usuarios_e_a_pilha_em_todo_o_painel(self):
        html = self.abrir().content.decode()
        self.assertIn("data-lsa-agora", html)
        self.assertIn('aria-label="Quem está online agora"', html)
        # a pilha da equipe: vazia e escondida no HTML (nenhuma consulta a mais); quem a enche é o ls-presenca.js
        self.assertIn('<div class="ls-equipe" id="lsEquipe" hidden>', html)
        self.assertIn('data-presenca="/presenca/agora/"', html)
        self.assertIn("interno/ls-presenca.js", html)
        outra = self.client.get("/minha-conta/", **INTERNO).content.decode()
        self.assertIn('id="lsEquipe"', outra)
        self.assertIn("interno/ls-presenca.js", outra)
        self.assertNotIn("data-lsa-agora", outra)
        relogio = (ESTATICOS_DO_PAINEL / "ls-presenca.js").read_text(encoding="utf-8")
        self.assertIn("var INTERVALO = 45000;", relogio)
        self.assertIn('document.visibilityState === "visible"', relogio)   # aba escondida não pergunta
        self.assertNotIn(".innerHTML", relogio)                           # nome de gente entra como texto
        self.assertIn("?contas=1", relogio)


class FichaDaContaTests(EquipeMixin, CatalogoDeTeste, TestCase):
    """"eu quero dados realmente interessantes e que precisamos de fato": a conta abre pelo que importa."""

    def setUp(self):
        self.preparar_catalogo()
        self.povoar(1)
        self.chefe = self.conta("chefe", super_=True)
        self.brinquedo = Brinquedos.objects.order_by("id").first()
        self.compradora = User.objects.create_user("elisa", email="elisa@exemplo.com")
        self.compradora.perfil.nome_completo = "Elisa Souza"
        self.compradora.perfil.save()
        for valor, quantidade in ((300, 2), (500, 1)):
            pedido = Pedido.objects.create(status="pago", total_liquido=Decimal(valor), cliente=self.compradora.perfil)
            ItemPedido.objects.create(pedido=pedido, tipo_item="brinquedo", object_id=self.brinquedo.pk, nome_item="Fliperama",
                                      preco_unitario=Decimal(valor) / quantidade, quantidade=quantidade, subtotal=valor)
        Pedido.objects.create(status="aguardando_pagamento", total_liquido=Decimal("90"), cliente=self.compradora.perfil)
        Favorito.objects.create(tipo="desejo", brinquedo=self.brinquedo, usuario=self.compradora)
        self.client.force_login(self.chefe)

    def ficha(self, pk):
        resposta = self.client.get(f"/detalhes/usuario/{pk}/", **INTERNO)
        self.assertEqual(resposta.status_code, 200, resposta.content[:300])
        return resposta.json()

    def test_a_ficha_abre_pelas_compras_e_pela_presenca(self):
        agora = timezone.now()
        hoje = timezone.localtime(agora)
        entrou = hoje.replace(hour=0, minute=3, second=0, microsecond=0)
        AcessoDiario.objects.create(usuario=self.compradora, dia=hoje.date(), primeiro=entrou, ultimo=agora)
        PresencaUsuario.objects.create(usuario=self.compradora, visto_em=agora, onde="app")
        ficha = self.ficha(self.compradora.pk)
        titulos = [s["titulo"] for s in ficha["secoes"]]
        self.assertEqual(titulos[:3], ["Compras na loja", "Presença", "O que comprou"])
        self.assertIn("O que quer", titulos)
        self.assertIn("Curtiu e pôs na lista de desejos", titulos)
        self.assertEqual(titulos[-1], "Conta")                 # o cadastro vem por último
        self.assertNotIn("Jogos", titulos)                     # não joga: a seção não aparece
        self.assertNotIn("Funções na equipe", titulos)         # é cliente
        self.assertNotIn("Carrinho agora", titulos)            # carrinho vazio
        secoes = {s["titulo"]: s for s in ficha["secoes"]}
        compras = {c["rotulo"]: c["valor"] for c in secoes["Compras na loja"]["campos"]}
        self.assertEqual(compras["Pedidos pagos"], "2")
        self.assertEqual(compras["Total gasto"], reais(800))
        self.assertEqual(compras["Ticket médio"], reais(400))
        self.assertRegex(compras["Último pedido pago"], r"^nº \d+ · \d\d/\d\d/\d{4} · " + re.escape(reais(500)) + "$")
        self.assertEqual(compras["Aguardando pagamento"], "1 pedido")
        comprou = secoes["O que comprou"]["lista"]
        self.assertEqual((comprou[0]["titulo"], comprou[0]["texto"]), ("Fliperama", f"3 unidades · {reais(800)}"))
        self.assertEqual(comprou[0]["detalhe"], {"tipo": "brinquedo", "id": self.brinquedo.pk})
        presenca_da_conta = {c["rotulo"]: c["valor"] for c in secoes["Presença"]["campos"]}
        self.assertEqual(presenca_da_conta["Visto por último"], "Online agora · no aplicativo")
        if agora - entrou > dt.timedelta(minutes=1):
            self.assertEqual(presenca_da_conta["Hoje"], f"entrou às 00:03 · último sinal às {hoje:%H:%M}")
        else:  # o teste rodou no primeiro minuto do dia
            self.assertTrue(presenca_da_conta["Hoje"].startswith("um sinal só"))
        self.assertEqual(presenca_da_conta["Dias com acesso (30 dias)"], "1 de 30")
        quer = {c["rotulo"]: c["valor"] for c in secoes["O que quer"]["campos"]}
        self.assertEqual((quer["Lista de desejos"], quer["No carrinho agora"]), ("1", "vazio"))
        self.assertEqual(secoes["Curtiu e pôs na lista de desejos"]["lista"][0]["titulo"], self.brinquedo.nome_brinquedo)
        self.assertIn(f"Comprou 2 vezes · {reais(800)}", [s["texto"] for s in ficha["selos"]])
        self.assertEqual(ficha["avatar"], {"iniciais": "ES", "cor": self.compradora.pk % presenca.CORES_DE_AVATAR})

    def test_quem_nunca_comprou_nao_ganha_caixa_vazia(self):
        visita = User.objects.create_user("visita")
        ficha = self.ficha(visita.pk)
        titulos = [s["titulo"] for s in ficha["secoes"]]
        self.assertEqual(titulos, ["Compras na loja", "Presença", "Conta"])
        self.assertTrue(all(len(s) > 2 for s in ficha["secoes"]))  # nenhuma seção só com o título
        compras = {c["rotulo"]: c["valor"] for c in ficha["secoes"][0]["campos"]}
        self.assertEqual(compras, {"Pedidos pagos": "Nenhum ainda"})
        presenca_da_conta = {c["rotulo"]: c["valor"] for c in ficha["secoes"][1]["campos"]}
        self.assertEqual((presenca_da_conta["Hoje"], presenca_da_conta["Dias com acesso (30 dias)"]), ("ainda não apareceu", "0 de 30"))
        self.assertFalse([s for s in ficha["selos"] if s["texto"].startswith("Comprou")])
        equipe = self.ficha(self.chefe.pk)
        self.assertIn("Funções na equipe", [s["titulo"] for s in equipe["secoes"]])

    def test_os_graficos_da_conta_no_hoje_mostram_o_dia_dela(self):
        agora = timezone.now()
        hoje = timezone.localtime(agora)
        entrou = hoje.replace(hour=0, minute=3, second=0, microsecond=0)
        AcessoDiario.objects.create(usuario=self.compradora, dia=hoje.date(), primeiro=entrou, ultimo=agora)
        cache.clear()
        dados = self.client.get("/analises/usuario/", {"periodo": "hoje", "id": self.compradora.pk}, **INTERNO).json()
        acessos = next(m for m in dados["metricas"] if m["codigo"] == "acessos")
        self.assertIsNone(acessos["serie"])
        self.assertEqual((acessos["total"], acessos["vazia"]), (1, False))
        self.assertTrue(acessos["pessoas"]["da_conta"])
        self.assertEqual([(p["id"], p["de"]) for p in acessos["pessoas"]["itens"]], [(self.compradora.pk, "00:03")])
        # nos outros períodos, uma coluna por dia: em cada dia, apareceu ou não
        cache.clear()
        mes = self.client.get("/analises/usuario/", {"periodo": "mes", "id": self.compradora.pk}, **INTERNO).json()
        acessos = next(m for m in mes["metricas"] if m["codigo"] == "acessos")
        self.assertEqual((acessos["forma"], acessos["serie"][-1]), ("colunas", 1))
        self.assertEqual(acessos["titulos"]["dia"], "Em que dias apareceu")
        self.assertIsNone(acessos["pessoas"])
