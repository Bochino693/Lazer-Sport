"""O ponto: hora do servidor, ordem, cadeia, imutabilidade, ajuste e espelho."""

from datetime import date, datetime, time, timedelta
from unittest import mock

from django.db import connection, transaction
from django.db.utils import DatabaseError, IntegrityError
from django.test import TestCase
from django.utils import timezone

from . import ponto
from .apoio_testes import INTERNO, criar_colaborador, criar_conta
from .models import AjustePonto, MarcacaoPonto, RegistroImutavel, TipoMarcacao

FUSO = timezone.get_default_timezone()


def quando(dia, hora, minuto=0):
    return datetime.combine(dia, time(hora, minuto), tzinfo=FUSO)


def bater(colaborador, dia, hora, minuto=0, tipo=None, **extra):
    with mock.patch("rh.ponto.timezone.now", return_value=quando(dia, hora, minuto)):
        return ponto.registrar(colaborador, tipo, **extra)


# Uma segunda-feira sem feriado, no passado.
SEGUNDA = date(2026, 10, 5)


class BaterOPontoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.conta = criar_conta("montador", "producao")
        cls.c = criar_colaborador(1, usuario=cls.conta)

    def test_a_ordem_do_dia_e_conferida(self):
        m1 = bater(self.c, SEGUNDA, 8)
        self.assertEqual(m1.tipo, TipoMarcacao.ENTRADA)
        self.assertEqual(m1.nsr, 1)
        with self.assertRaises(ponto.ErroDePonto):
            bater(self.c, SEGUNDA, 9, tipo=TipoMarcacao.ENTRADA)
        with self.assertRaises(ponto.ErroDePonto):
            bater(self.c, SEGUNDA, 9, tipo=TipoMarcacao.VOLTA_INTERVALO)
        m2 = bater(self.c, SEGUNDA, 12)
        self.assertEqual(m2.tipo, TipoMarcacao.SAIDA_INTERVALO)
        m3 = bater(self.c, SEGUNDA, 13)
        self.assertEqual(m3.tipo, TipoMarcacao.VOLTA_INTERVALO)
        m4 = bater(self.c, SEGUNDA, 17, tipo=TipoMarcacao.SAIDA)
        self.assertEqual((m4.nsr, m4.hash_anterior), (4, m3.hash))

    def test_dois_toques_seguidos_viram_um(self):
        bater(self.c, SEGUNDA, 8, 0)
        with mock.patch("rh.ponto.timezone.now", return_value=quando(SEGUNDA, 8, 0) + timedelta(seconds=20)):
            with self.assertRaises(ponto.ErroDePonto):
                ponto.registrar(self.c)
        self.assertEqual(MarcacaoPonto.objects.filter(colaborador=self.c).count(), 1)

    def test_a_hora_e_do_servidor_mesmo_que_o_aparelho_mande_outra(self):
        self.client.force_login(self.conta)
        agora = timezone.now()
        resposta = self.client.post(
            "/rh/ponto/marcar/", {"tipo": "entrada", "momento": "2001-01-01T03:00", "hora": "03:00"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest", HTTP_USER_AGENT="Celular de teste", **INTERNO,
        )
        self.assertEqual(resposta.status_code, 200, resposta.content)
        corpo = resposta.json()
        m = MarcacaoPonto.objects.get(colaborador=self.c)
        self.assertLess(abs((m.momento - agora).total_seconds()), 30)
        self.assertEqual(m.ip, "127.0.0.1")
        self.assertEqual(m.navegador, "Celular de teste")
        self.assertEqual(corpo["codigo"], m.codigo)
        self.assertRegex(m.codigo, r"^[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}$")

    def test_localizacao_so_com_consentimento_e_valida(self):
        m = bater(self.c, SEGUNDA, 8, latitude="-23.55", longitude="-46.63", precisao="15")
        self.assertEqual(str(m.latitude), "-23.550000")
        self.assertEqual(m.precisao_m, 15)
        m2 = bater(self.c, SEGUNDA, 12, latitude="999", longitude="-46.63")
        self.assertIsNone(m2.latitude)
        self.client.force_login(self.conta)
        self.client.post("/rh/ponto/marcar/", {"lat": "-23.5", "lng": "-46.6"},
                         HTTP_X_REQUESTED_WITH="XMLHttpRequest", **INTERNO)
        ultima = MarcacaoPonto.objects.filter(colaborador=self.c).order_by("-nsr").first()
        self.assertIsNone(ultima.latitude)  # sem o "localizacao=1" do consentimento

    def test_quem_nao_esta_ativo_nao_bate(self):
        self.c.situacao = "ferias"
        self.c.save()
        with self.assertRaises(ponto.ErroDePonto):
            bater(self.c, SEGUNDA, 8)

    def test_sem_ficha_nao_bate(self):
        sem_ficha = criar_conta("vendedora", "vendas")
        self.client.force_login(sem_ficha)
        resposta = self.client.post("/rh/ponto/marcar/", HTTP_X_REQUESTED_WITH="XMLHttpRequest", **INTERNO)
        self.assertEqual(resposta.status_code, 403)

    def test_comprovante_so_do_dono_ou_da_gestao(self):
        m = bater(self.c, SEGUNDA, 8)
        self.client.force_login(self.conta)
        self.assertContains(self.client.get(f"/rh/ponto/comprovante/{m.pk}/", **INTERNO), m.codigo)
        outra = criar_conta("outra", "producao")
        criar_colaborador(2, usuario=outra)
        self.client.force_login(outra)
        self.assertEqual(self.client.get(f"/rh/ponto/comprovante/{m.pk}/", **INTERNO).status_code, 404)


class ImutavelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.c = criar_colaborador(3)

    def test_nao_se_edita_nem_se_apaga_pelo_modelo(self):
        m = bater(self.c, SEGUNDA, 8)
        m.tipo = TipoMarcacao.SAIDA
        with self.assertRaises(RegistroImutavel):
            m.save()
        with self.assertRaises(RegistroImutavel):
            m.delete()
        with self.assertRaises(RegistroImutavel):
            MarcacaoPonto.objects.filter(pk=m.pk).update(tipo="saida")
        with self.assertRaises(RegistroImutavel):
            MarcacaoPonto.objects.filter(pk=m.pk).delete()

    def test_nem_pelo_banco(self):
        m = bater(self.c, SEGUNDA, 8)
        for sql in (
            f"UPDATE rh_marcacaoponto SET tipo = 'saida' WHERE id = {m.pk}",
            f"DELETE FROM rh_marcacaoponto WHERE id = {m.pk}",
        ):
            with self.subTest(sql=sql.split()[0]):
                with self.assertRaises((DatabaseError, IntegrityError)):
                    with transaction.atomic(), connection.cursor() as cursor:
                        cursor.execute(sql)
        m.refresh_from_db()
        self.assertEqual(m.tipo, TipoMarcacao.ENTRADA)

    def test_a_cadeia_acusa_a_adulteracao(self):
        bater(self.c, SEGUNDA, 8)
        m2 = bater(self.c, SEGUNDA, 12)
        bater(self.c, SEGUNDA, 13)
        self.assertEqual(ponto.conferir_cadeia(self.c), [])
        if connection.vendor != "sqlite":
            self.skipTest("o teste desliga o gatilho do SQLite")
        with connection.cursor() as cursor:
            cursor.execute("DROP TRIGGER rh_marcacao_sem_update")
            cursor.execute(
                "UPDATE rh_marcacaoponto SET momento = %s WHERE id = %s",
                [quando(SEGUNDA, 11, 0).astimezone(timezone.get_current_timezone()).isoformat(), m2.pk],
            )
        problemas = ponto.conferir_cadeia(self.c)
        self.assertTrue(any("NSR 2" in p for p in problemas), problemas)


class AjusteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.conta = criar_conta("operador", "producao")
        cls.c = criar_colaborador(4, usuario=cls.conta)
        cls.gestora = criar_conta("gestora", "gestao")

    def pedir(self, **dados):
        self.client.force_login(self.conta)
        return self.client.post("/rh/ponto/ajustes/", dados, **INTERNO)

    def test_pedido_aprovado_entra_na_conta_e_o_original_continua(self):
        bater(self.c, SEGUNDA, 8)
        bater(self.c, SEGUNDA, 12)
        bater(self.c, SEGUNDA, 13)
        # esqueceu a saída
        self.pedir(tipo="incluir", data=SEGUNDA.isoformat(), hora="17:00", tipo_marcacao="saida",
                   justificativa="Esqueci de marcar a saída, saí às 17h.")
        ajuste = AjustePonto.objects.get(colaborador=self.c)
        self.assertEqual(ajuste.situacao, "pendente")
        dia = self._dia()
        self.assertTrue(dia.incompleto)
        self.assertEqual(dia.trabalhado, 4 * 60)  # só o que fechou

        self.client.force_login(self.gestora)
        self.client.post(f"/rh/ponto/ajustes/{ajuste.pk}/decidir/", {"decisao": "aprovar"}, **INTERNO)
        ajuste.refresh_from_db()
        self.assertEqual(ajuste.situacao, "aprovado")
        self.assertEqual(ajuste.decidido_por, self.gestora)
        dia = self._dia()
        self.assertFalse(dia.incompleto)
        self.assertEqual(dia.trabalhado, 8 * 60)
        self.assertEqual(MarcacaoPonto.objects.filter(colaborador=self.c).count(), 3)
        self.assertEqual(sum(1 for e in dia.eventos if e.origem == "ajuste"), 1)

    def test_desconsiderar_marcacao_errada(self):
        bater(self.c, SEGUNDA, 8)
        errada = bater(self.c, SEGUNDA, 8, 5, tipo=TipoMarcacao.SAIDA)  # tocou sem querer
        bater(self.c, SEGUNDA, 8, 10, tipo=TipoMarcacao.ENTRADA)
        bater(self.c, SEGUNDA, 17, tipo=TipoMarcacao.SAIDA)
        self.pedir(tipo="desconsiderar", data=SEGUNDA.isoformat(), marcacao=errada.pk,
                   justificativa="Toquei em saída sem querer logo depois de entrar.")
        ajuste = AjustePonto.objects.get(marcacao=errada)
        self.client.force_login(self.gestora)
        self.client.post(f"/rh/ponto/ajustes/{ajuste.pk}/decidir/", {"decisao": "aprovar"}, **INTERNO)
        dia = self._dia()
        self.assertTrue(any(e.desconsiderada for e in dia.eventos))
        self.assertTrue(dia.incompleto)  # entrada, entrada, saída: falta uma ponta

    def test_recusar_pede_motivo(self):
        self.pedir(tipo="abono", data=SEGUNDA.isoformat(), motivo_abono="atestado",
                   justificativa="Fui ao médico, atestado entregue.")
        ajuste = AjustePonto.objects.get(colaborador=self.c)
        self.client.force_login(self.gestora)
        self.client.post(f"/rh/ponto/ajustes/{ajuste.pk}/decidir/", {"decisao": "recusar"}, **INTERNO)
        ajuste.refresh_from_db()
        self.assertEqual(ajuste.situacao, "pendente")
        self.client.post(f"/rh/ponto/ajustes/{ajuste.pk}/decidir/",
                         {"decisao": "recusar", "resposta": "Atestado não chegou ao RH."}, **INTERNO)
        ajuste.refresh_from_db()
        self.assertEqual(ajuste.situacao, "recusado")
        with self.assertRaises(RegistroImutavel):
            ajuste.resposta = "mudei de ideia"
            ajuste.save()

    def test_ninguem_decide_o_proprio_ajuste(self):
        gestor_com_ficha = criar_conta("gestor-ficha", "gestao")
        ficha = criar_colaborador(5, usuario=gestor_com_ficha, setor="gestao")
        self.client.force_login(gestor_com_ficha)
        self.client.post("/rh/ponto/ajustes/", {"tipo": "abono", "data": SEGUNDA.isoformat(),
                                                 "motivo_abono": "folga", "justificativa": "Folga combinada."},
                         **INTERNO)
        ajuste = AjustePonto.objects.get(colaborador=ficha)
        self.client.post(f"/rh/ponto/ajustes/{ajuste.pk}/decidir/", {"decisao": "aprovar"}, **INTERNO)
        ajuste.refresh_from_db()
        self.assertEqual(ajuste.situacao, "pendente")

    def test_colaborador_nao_decide(self):
        self.pedir(tipo="abono", data=SEGUNDA.isoformat(), motivo_abono="folga", justificativa="Folga combinada.")
        ajuste = AjustePonto.objects.get(colaborador=self.c)
        self.client.force_login(self.conta)
        self.client.post(f"/rh/ponto/ajustes/{ajuste.pk}/decidir/", {"decisao": "aprovar"}, **INTERNO)
        ajuste.refresh_from_db()
        self.assertEqual(ajuste.situacao, "pendente")

    def test_justificativa_curta_e_dia_futuro_sao_recusados(self):
        self.pedir(tipo="incluir", data=SEGUNDA.isoformat(), hora="08:00", tipo_marcacao="entrada", justificativa="ok")
        amanha = timezone.localdate() + timedelta(days=1)
        self.pedir(tipo="incluir", data=amanha.isoformat(), hora="08:00", tipo_marcacao="entrada",
                   justificativa="Vou esquecer amanhã, já aviso.")
        self.assertFalse(AjustePonto.objects.exists())

    def _dia(self):
        return next(d for d in ponto.espelho(self.c, SEGUNDA.year, SEGUNDA.month).dias if d.data == SEGUNDA)


class EspelhoTests(TestCase):
    """Jornada 8h-17h com 1h de intervalo: 8 horas por dia, de segunda a sexta."""

    @classmethod
    def setUpTestData(cls):
        cls.c = criar_colaborador(6, data_admissao=date(2026, 9, 1))

    def dia(self, d):
        return next(x for x in ponto.espelho(self.c, d.year, d.month).dias if x.data == d)

    def jornada(self, d, entrada=(8, 0), saida_int=(12, 0), volta=(13, 0), saida=(17, 0)):
        bater(self.c, d, *entrada)
        bater(self.c, d, *saida_int)
        bater(self.c, d, *volta)
        bater(self.c, d, *saida)

    def test_dia_normal_fecha_em_zero(self):
        self.jornada(SEGUNDA)
        d = self.dia(SEGUNDA)
        self.assertEqual((d.trabalhado, d.intervalo, d.extra, d.debito, d.atraso), (480, 60, 0, 0, 0))

    def test_tolerancia_de_cinco_e_dez_minutos(self):
        self.jornada(SEGUNDA, entrada=(8, 4), saida=(17, 3))
        d = self.dia(SEGUNDA)
        self.assertEqual((d.atraso, d.extra, d.debito), (0, 0, 0))

    def test_atraso_e_debito(self):
        self.jornada(SEGUNDA, entrada=(8, 40))
        d = self.dia(SEGUNDA)
        self.assertEqual(d.atraso, 40)
        self.assertEqual(d.debito, 40)

    def test_hora_extra_pela_jornada_da_ficha(self):
        self.jornada(SEGUNDA, saida=(19, 30))
        d = self.dia(SEGUNDA)
        self.assertEqual(d.extra, 150)
        self.c.jornada_fim = time(18, 0)
        self.c.save()
        self.assertEqual(self.dia(SEGUNDA).extra, 90)

    def test_domingo_e_feriado_valem_100(self):
        domingo = date(2026, 10, 4)
        bater(self.c, domingo, 9)
        bater(self.c, domingo, 13, tipo=TipoMarcacao.SAIDA)
        d = self.dia(domingo)
        self.assertEqual((d.extra_100, d.extra, d.esperado), (240, 0, 0))
        feriado = date(2026, 10, 12)  # Nossa Senhora Aparecida (segunda)
        self.assertEqual(self.dia(feriado).feriado, "Nossa Senhora Aparecida")
        self.assertFalse(self.dia(feriado).falta)

    def test_falta_e_abono(self):
        terca = SEGUNDA + timedelta(days=1)
        d = self.dia(terca)
        self.assertTrue(d.falta)
        self.assertEqual(d.debito, 480)
        AjustePonto.objects.create(colaborador=self.c, tipo="abono", data=terca, motivo_abono="atestado",
                                   justificativa="Atestado médico de um dia.", situacao="aprovado")
        d = self.dia(terca)
        self.assertFalse(d.falta)
        self.assertEqual(d.debito, 0)

    def test_intervalo_curto_e_sinalizado(self):
        self.jornada(SEGUNDA, saida_int=(12, 0), volta=(12, 20), saida=(16, 20))
        self.assertTrue(self.dia(SEGUNDA).intervalo_curto)

    def test_totais_do_mes(self):
        self.jornada(SEGUNDA, saida=(18, 0))
        espelho = ponto.espelho(self.c, SEGUNDA.year, SEGUNDA.month)
        self.assertEqual(espelho.totais["extra"], "1h00")
        self.assertTrue(espelho.integro)
        # 22 dias úteis em out/2026 menos o feriado do dia 12 e a segunda trabalhada = 20 faltas
        self.assertEqual(espelho.totais["faltas"], 20)

    def test_antes_da_admissao_nao_e_falta(self):
        agosto = date(2026, 8, 3)
        self.assertFalse(self.dia(agosto).falta)

    def test_pdf_para_assinar(self):
        gestora = criar_conta("gestora-espelho", "gestao")
        self.jornada(SEGUNDA)
        self.client.force_login(gestora)
        resposta = self.client.get(f"/rh/ponto/espelho/{self.c.pk}/imprimir/?mes=2026-10", **INTERNO)
        self.assertContains(resposta, "Espelho de ponto · outubro de 2026")
        self.assertContains(resposta, "Não substitui um REP certificado")
        self.assertContains(resposta, "Colaborador — confere e concorda")

    def test_feriados_moveis(self):
        self.assertEqual(ponto.feriados_nacionais(2026)[date(2026, 4, 3)], "Sexta-feira Santa")
        self.assertIn(date(2027, 3, 26), ponto.feriados_nacionais(2027))
