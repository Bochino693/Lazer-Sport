"""Os critérios de ordem da fila de montagem (LEIA-ME-V10, seção 142).

O pedido do dono: "na listagem de montagem, você pode pôr filtros para ter a
lista e visualizar qual melhor se enquadra, por metros cúbicos (...), um que
seria a média de todos, outro para soltar compras menores, soltar compras
maiores, soltar pedidos maiores e pedidos menores (...), default é a mediana."

O que estes testes protegem (dados SINTÉTICOS):

  * cada critério põe a fila na ordem esperada e escreve o número que usou;
  * a posição de 0 a 100, com empate dividindo a posição;
  * a média e a mediana das posições (com quantidade par e ímpar), e a
    diferença entre elas quando um critério foge da curva;
  * empate desempata pela fila oficial, sempre igual;
  * quem não tem o dado vai para o fim, marcado, e sai da conta do resumo;
  * a tela: o padrão é a mediana, o critério vai na URL, os chips guardam
    os outros filtros, as setas só aparecem na fila oficial, ABRIR A TELA
    NÃO GRAVA NADA e o número de consultas não cresce com a fila.
"""

from datetime import date, datetime, timedelta, timezone as tz
from decimal import Decimal
from pathlib import Path
from statistics import median
from types import SimpleNamespace

from django.db import connection
from django.test import SimpleTestCase
from django.test.utils import CaptureQueriesContext

from . import ordem_montagem as om
from .models import ItemOrcamento, Orcamento, UnidadeMontagem
from .tests_lista_montagem import AJAX, INTERNO, QUARTA, Base, brinquedo, equipe, no_dia, no_relogio

HOJE = date(2026, 11, 25)
AGORA = datetime(2026, 11, 25, 12, 0, tzinfo=tz.utc)
RAIZ = Path(__file__).resolve().parent


def maquina(pk, *, m3=1.0, compra=1000, pedido=None, espera=1, prazo=10, dias=4, posicao=None):
    """Uma máquina da fila, de mentira: só o que os critérios leem."""
    producao_id = pedido if pedido is not None else 1000 + pk
    return SimpleNamespace(
        pk=pk, producao_id=producao_id,
        producao=SimpleNamespace(pedido_id=None, orcamento=SimpleNamespace(total=Decimal(compra) if compra else None)),
        brinquedo_id=1 if m3 else None, brinquedo=SimpleNamespace(metros_cubicos=m3),
        chegada=AGORA - timedelta(days=espera),
        previsao_ate=(HOJE + timedelta(days=prazo)) if prazo is not None else None,
        dias=dias, posicao=posicao if posicao is not None else pk,
    )


def ordem(unidades, chave):
    ordenadas, resumo = om.ordenar(unidades, chave, hoje=HOJE, agora=AGORA)
    return [u.pk for u in ordenadas], ordenadas, resumo


# ======================================================================
# AS CONTAS
# ======================================================================
class PosicoesTests(SimpleTestCase):
    def test_de_0_a_100_do_que_sai_primeiro_ao_ultimo(self):
        self.assertEqual(om.posicoes({"a": 1, "b": 2, "c": 3}, False), {"a": 0.0, "b": 50.0, "c": 100.0})
        self.assertEqual(om.posicoes({"a": 1, "b": 2, "c": 3}, True), {"c": 0.0, "b": 50.0, "a": 100.0})

    def test_empate_divide_a_posicao(self):
        self.assertEqual(om.posicoes({"a": 5, "b": 5, "c": 9}, False), {"a": 25.0, "b": 25.0, "c": 100.0})
        self.assertEqual(om.posicoes({"a": 7, "b": 7}, False), {"a": 50.0, "b": 50.0})

    def test_sem_o_dado_fica_de_fora_e_um_so_e_zero(self):
        self.assertEqual(om.posicoes({"a": None, "b": 3, "c": 1}, False), {"c": 0.0, "b": 100.0})
        self.assertEqual(om.posicoes({"a": 4, "b": None}, False), {"a": 0.0})
        self.assertEqual(om.posicoes({"a": None}, False), {})


class NotasTests(SimpleTestCase):
    def test_media_e_mediana_com_quantidade_par_e_impar(self):
        # as seis medidas dos COMPONENTES: quantidade PAR de posições
        self.assertEqual(len(om.COMPONENTES), 6)
        fila = [maquina(1, m3=1, compra=9000, pedido=1, espera=30, prazo=5, dias=4),
                maquina(2, m3=2, compra=5000, pedido=2, espera=20, prazo=10, dias=4),
                maquina(3, m3=6, compra=1000, pedido=3, espera=1, prazo=40, dias=5)]
        medidas = om.medir(fila, hoje=HOJE, agora=AGORA)
        # a 1 sai primeiro em quase tudo; a 3, por último; a 2, no meio. A montagem da 1 empata com a
        # da 2 (posição 25 cada) e o tamanho do pedido empata nas três (1 máquina cada: posição 50).
        # posições (espera, prazo, montagem, m³, pedido, compra):
        #   1 -> 0, 0, 25, 0, 50, 0      2 -> 50, 50, 25, 50, 50, 50      3 -> 100, 100, 100, 100, 50, 100
        self.assertEqual(om.notas(medidas, median), {1: 0.0, 2: 50.0, 3: 100.0})
        media = om.notas(medidas, om._media)
        self.assertAlmostEqual(media[1], (0 + 0 + 25 + 0 + 50 + 0) / 6)
        self.assertAlmostEqual(media[2], (50 + 50 + 25 + 50 + 50 + 50) / 6)
        self.assertAlmostEqual(media[3], (100 + 100 + 100 + 100 + 50 + 100) / 6)
        # sem a medida do m³ a conta fica com CINCO posições (ímpar): a do meio
        sem_m3 = [maquina(1, m3=None, compra=9000, pedido=1, espera=30, prazo=5, dias=4),
                  maquina(2, m3=None, compra=5000, pedido=2, espera=20, prazo=10, dias=5),
                  maquina(3, m3=None, compra=1000, pedido=3, espera=1, prazo=40, dias=6)]
        self.assertEqual(om.notas(om.medir(sem_m3, hoje=HOJE, agora=AGORA), median), {1: 0.0, 2: 50.0, 3: 100.0})

    def test_um_criterio_fora_da_curva_puxa_a_media_e_nao_a_mediana(self):
        """A 1 sai primeiro em cinco medidas e por último em uma (o m³ gigante)."""
        fila = [maquina(1, m3=40, compra=9000, pedido=1, espera=30, prazo=5, dias=3),
                maquina(2, m3=2, compra=5000, pedido=2, espera=20, prazo=10, dias=4),
                maquina(3, m3=1, compra=1000, pedido=3, espera=1, prazo=40, dias=5)]
        medidas = om.medir(fila, hoje=HOJE, agora=AGORA)
        mediana, media = om.notas(medidas, median), om.notas(medidas, om._media)
        self.assertEqual(mediana[1], 0.0)             # a maioria dos critérios manda sair primeiro
        # posições da 1: espera 0, prazo 0, montagem 0, m³ 100, pedido 50 (empate), compra 0
        self.assertAlmostEqual(media[1], 150 / 6)      # a média sente o m³
        self.assertEqual(ordem(fila, "mediana")[0], [1, 2, 3])

    def test_sem_nenhum_dado_nao_tem_nota(self):
        vazia = SimpleNamespace(
            pk=9, producao_id=9, producao=SimpleNamespace(pedido_id=None, orcamento=SimpleNamespace(total=None)),
            brinquedo_id=None, brinquedo=None, chegada=None, previsao_ate=None, dias=None, posicao=1,
        )
        medidas = om.medir([vazia], hoje=HOJE, agora=AGORA)
        medidas[9]["pedido"] = None
        self.assertEqual(om.notas(medidas, median), {9: None})


# ======================================================================
# CADA CRITÉRIO
# ======================================================================
class CadaCriterioTests(SimpleTestCase):
    def fila(self):
        return [
            # pk  m³    compra  pedido(máquinas)  espera  prazo  montagem
            maquina(1, m3=2.0, compra=5000, pedido=10, espera=10, prazo=20, dias=4),
            maquina(2, m3=6.5, compra=18000, pedido=20, espera=3, prazo=35, dias=5),
            maquina(3, m3=1.0, compra=900, pedido=30, espera=30, prazo=-2, dias=3),
            maquina(4, m3=2.0, compra=5000, pedido=10, espera=10, prazo=20, dias=4),  # do mesmo pedido da 1
            maquina(5, m3=None, compra=7000, pedido=50, espera=6, prazo=None, dias=5),  # sem medida e sem previsão
        ]

    def test_a_ordem_de_cada_um(self):
        esperado = {
            "fila": [1, 2, 3, 4, 5],
            "m3_menor": [3, 1, 4, 2, 5],          # a 5 não tem medida: no fim
            "m3_maior": [2, 1, 4, 3, 5],
            "compra_menor": [3, 1, 4, 5, 2],
            "compra_maior": [2, 5, 1, 4, 3],
            "pedido_menor": [2, 3, 5, 1, 4],      # 1 máquina no pedido antes das 2 do pedido 10
            "pedido_maior": [1, 4, 2, 3, 5],
            "espera": [3, 1, 4, 5, 2],
            "prazo": [3, 1, 4, 2, 5],             # a 5 não tem previsão: no fim
            "trabalho": [3, 1, 4, 2, 5],
            "valor_m3": [2, 1, 4, 3, 5],          # 18000/6,5 = 2769; 5000/4 = 1250; 900/1 = 900
        }
        for chave, pks in esperado.items():
            with self.subTest(criterio=chave):
                self.assertEqual(ordem(self.fila(), chave)[0], pks)

    def test_o_numero_que_o_criterio_usou(self):
        casos = {
            "m3_menor": (3, "1,00 m³"), "compra_maior": (2, "R$ 18.000,00"),
            "pedido_maior": (1, "2 máquinas no pedido"), "pedido_menor": (2, "1 máquina no pedido"),
            "espera": (3, "30 dias esperando"), "prazo": (3, "prazo vencido há 2 dias"),
            "trabalho": (3, "3 dias úteis de montagem"), "valor_m3": (2, "R$ 2.769,23 por m³"),
        }
        for chave, (pk, texto) in casos.items():
            with self.subTest(criterio=chave):
                _, ordenadas, _ = ordem(self.fila(), chave)
                primeira = ordenadas[0]
                self.assertEqual((primeira.pk, primeira.criterio_texto, primeira.criterio_ordem), (pk, texto, 1))
                self.assertFalse(primeira.criterio_sem_dado)

    def test_quem_nao_tem_o_dado_vai_para_o_fim_marcado(self):
        _, ordenadas, resumo = ordem(self.fila(), "m3_menor")
        ultima = ordenadas[-1]
        self.assertEqual((ultima.pk, ultima.criterio_sem_dado, ultima.criterio_texto), (5, True, "sem medida no cadastro"))
        self.assertEqual((resumo.total, resumo.com_dado, resumo.sem_dado), (5, 4, 1))
        _, ordenadas, resumo = ordem(self.fila(), "prazo")
        self.assertEqual((ordenadas[-1].pk, ordenadas[-1].criterio_texto), (5, "sem este dado"))
        self.assertEqual(resumo.sem_dado, 1)

    def test_o_resumo_traz_a_media_e_a_mediana(self):
        _, _, resumo = ordem(self.fila(), "compra_menor")   # 900, 5000, 5000, 7000, 18000 (ímpar)
        self.assertEqual((resumo.media, resumo.mediana), ("R$ 7.180,00", "R$ 5.000,00"))
        _, _, resumo = ordem(self.fila(), "m3_menor")       # 1, 2, 2, 6,5 (par): a mediana é o meio dos dois do meio
        self.assertEqual((resumo.media, resumo.mediana, resumo.soma), ("2,88 m³", "2,00 m³", "11,50 m³"))
        _, _, resumo = ordem(self.fila(), "espera")
        self.assertEqual((resumo.media, resumo.mediana), ("11,8 dias", "10,0 dias"))
        _, _, resumo = ordem(self.fila(), "mediana")
        self.assertEqual(resumo.medida, "nota de 0 a 100 (menor sai primeiro)")
        self.assertTrue(resumo.media and resumo.mediana)

    def test_empate_desempata_pela_fila_oficial_sempre_igual(self):
        iguais = [maquina(pk, posicao=posicao) for pk, posicao in ((1, 3), (2, 1), (3, 2))]
        for chave in om.POR_CHAVE:
            with self.subTest(criterio=chave):
                self.assertEqual(ordem(iguais, chave)[0], [2, 3, 1])
                self.assertEqual(ordem(list(reversed(iguais)), chave)[0], [2, 3, 1])

    def test_criterio_desconhecido_cai_na_mediana(self):
        self.assertEqual(om.PADRAO, "mediana")
        for chave in ("", None, "xpto", "<script>"):
            self.assertEqual(om.criterio(chave).chave, "mediana")
        self.assertEqual(om.CRITERIOS[0].chave, "mediana")  # é o primeiro chip

    def test_ordenar_nao_muda_a_posicao_oficial(self):
        fila = self.fila()
        for chave in om.POR_CHAVE:
            ordem(fila, chave)
        self.assertEqual([u.posicao for u in fila], [1, 2, 3, 4, 5])

    def test_a_mediana_e_a_media_como_notas(self):
        pks, ordenadas, _ = ordem(self.fila(), "mediana")
        self.assertEqual(pks[0], 3)   # a mais antiga, de prazo vencido, a menor e a mais rápida
        self.assertTrue(ordenadas[0].criterio_texto.startswith("nota "))
        self.assertIn("30 dias esperando", ordenadas[0].criterio_detalhe)
        self.assertEqual(ordem(self.fila(), "media")[0][0], 3)


# ======================================================================
# A TELA
# ======================================================================
class TelaComCriteriosTests(Base):
    def setUp(self):
        super().setUp()
        self.producao_user = equipe("prod-ordem", "producao")
        self.fliperama = brinquedo("Fliperama Sintético", (1.8, 0.7, 0.8))
        with no_relogio(QUARTA), no_dia(QUARTA.date()):
            self.pedidos = [self.pedido() for _ in range(3)]            # enchem as 3 vagas
            self.na_fila = [
                self.orcamento("Cliente A", self.basquete, 1, 18000),
                self.orcamento("Cliente B", self.fliperama, 2, 6500),
                self.orcamento("Cliente C", self.agk, 1, 4990),
            ]
        self.client.force_login(self.producao_user)

    def orcamento(self, nome, objeto, quantidade, valor):
        orcamento = Orcamento.objects.create(nome_cliente=nome, status=Orcamento.Status.RASCUNHO)
        ItemOrcamento.objects.create(
            orcamento=orcamento, brinquedo=objeto, descricao=objeto.nome_brinquedo,
            quantidade=quantidade, valor_unitario=Decimal(valor),
        )
        with self.captureOnCommitCallbacks(execute=True):
            orcamento.status = Orcamento.Status.APROVADO
            orcamento.save(update_fields=["status"])
        return orcamento

    def abrir(self, consulta=""):
        return self.client.get("/producao/montagem/" + consulta, **INTERNO)

    def nomes(self, resposta):
        return [u.nome for u in resposta.context["fila_maquinas"]]

    def test_o_padrao_e_a_mediana_e_o_criterio_vai_na_url(self):
        resposta = self.abrir()
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["criterio"].chave, "mediana")
        self.assertFalse(resposta.context["fila_oficial"])
        html = resposta.content.decode()
        self.assertIn("Ordenar a fila por", html)
        self.assertRegex(html, r'class="lm-chip is-ativo"[^>]*data-montagem-ordem="mediana"')
        for chave in om.POR_CHAVE:
            self.assertIn(f'data-montagem-ordem="{chave}"', html)
        self.assertIn("data-montagem-resumo", html)
        self.assertIn("nota ", html)
        self.assertNotIn("<select", html)
        self.assertEqual(self.abrir("?ordem=xpto").context["criterio"].chave, "mediana")

    def test_cada_criterio_reordena_a_fila(self):
        self.assertEqual(self.nomes(self.abrir("?ordem=fila"))[0], "Basquete Street")
        self.assertEqual(self.nomes(self.abrir("?ordem=m3_menor"))[0], "Air Game Kids")
        self.assertEqual(self.nomes(self.abrir("?ordem=m3_maior"))[0], "Basquete Street")
        self.assertEqual(self.nomes(self.abrir("?ordem=compra_menor"))[0], "Air Game Kids")
        self.assertEqual(self.nomes(self.abrir("?ordem=compra_maior"))[0], "Basquete Street")
        self.assertEqual(self.nomes(self.abrir("?ordem=pedido_maior"))[0], "Fliperama Sintético")
        html = self.abrir("?ordem=compra_maior").content.decode()
        self.assertIn("R$ 18.000,00", html)
        self.assertIn("fila oficial: 1º", html)
        self.assertIn("2 máquinas no pedido", self.abrir("?ordem=pedido_maior").content.decode())

    def test_as_setas_so_na_fila_oficial(self):
        self.assertNotIn("data-montagem-fila=", self.abrir().content.decode())
        self.assertNotIn("data-montagem-fila=", self.abrir("?ordem=compra_maior").content.decode())
        self.assertIn('data-montagem-fila="subir"', self.abrir("?ordem=fila").content.decode())
        # e a seta continua mudando a ordem GRAVADA
        segunda = UnidadeMontagem.objects.filter(situacao="fila").order_by("posicao")[1]
        resposta = self.client.post("/producao/montagem/", {"action": "fila", "id": segunda.pk, "direcao": "subir"}, **AJAX)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        segunda.refresh_from_db()
        self.assertEqual(segunda.posicao, 1)

    def test_trocar_o_criterio_nao_grava_nada(self):
        self.abrir("?ordem=fila")  # a tela acerta a fila e as previsões do dia ao abrir (seção 112)
        campos = ("pk", "posicao", "situacao", "previsao_de", "previsao_ate", "etapa", "entrou_em", "chegada")
        antes = list(UnidadeMontagem.objects.order_by("pk").values_list(*campos))
        for chave in om.POR_CHAVE:
            self.assertEqual(self.abrir(f"?ordem={chave}").status_code, 200)
        self.assertEqual(list(UnidadeMontagem.objects.order_by("pk").values_list(*campos)), antes)

    def test_os_chips_guardam_os_outros_filtros_e_vice_versa(self):
        html = self.abrir("?filtro=fila&linha=maquina&ordem=espera").content.decode()
        self.assertIn('href="?filtro=fila&amp;linha=maquina&amp;ordem=compra_maior"', html)
        self.assertIn('href="?filtro=fila&amp;linha=maquina"', html)                 # o chip da mediana (o padrão)
        self.assertIn('href="?filtro=producao&amp;linha=maquina&amp;ordem=espera"', html)  # o chip da situação
        self.assertIn('href="?filtro=fila&amp;ordem=espera"', html)                  # o chip "Todas" da linha

    def test_as_consultas_nao_crescem_com_a_fila(self):
        self.abrir()

        def consultas():
            with CaptureQueriesContext(connection) as contexto:
                self.assertEqual(self.abrir("?ordem=compra_maior").status_code, 200)
            return len(contexto)

        antes = consultas()
        with no_relogio(QUARTA), no_dia(QUARTA.date()):
            for numero in range(4):
                self.orcamento(f"Cliente Extra {numero}", self.fliperama, 1, 7000 + numero)
        self.abrir()  # a primeira visita põe os novos na lista
        self.assertLessEqual(consultas(), antes + 1, "cada máquina a mais na fila não pode custar uma ida ao banco")

    def test_quem_so_ve_nao_mexe(self):
        financeiro = equipe("fin-ordem", "financeiro")
        self.client.force_login(financeiro)
        resposta = self.abrir("?ordem=fila")
        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn("data-montagem-fila=", resposta.content.decode())  # vê a fila oficial, sem as setas

    def test_css_so_com_as_variaveis_do_tema(self):
        import re

        css = (RAIZ / "static" / "interno" / "lista-montagem.css").read_text(encoding="utf-8")
        secao = css[css.index("OS CRITÉRIOS DE ORDEM DA FILA"):]
        secao = re.sub(r"/\*.*?\*/", "", secao, flags=re.S)
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", secao), [])
