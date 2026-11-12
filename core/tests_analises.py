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
"""

import datetime as dt
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
        # 5 fontes x (série + semana + ranking) + nomes + cobertura + sessão
        self.assertLess(len(primeira), 26, [q["sql"][:80] for q in primeira.captured_queries])
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
        destaques = analises.calcular(tipo_por_codigo("usuario"), analises.janela("mes"), usar_cache=False)["destaques"]
        self.assertEqual({d["codigo"]: d["valor"] for d in destaques}["online"], 1)


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
