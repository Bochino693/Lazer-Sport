"""Todo endereço de cliente ganha o seu ponto no mapa (LEIA-ME-V10, seção 121).

"Verifique na área interna, nos clientes, o 'no mapa, sem local', pois
tem endereço e deve estar no mapa tudo que tiver." O cadastro do painel só
ganhava ponto pela consulta rápida do CEP no navegador; o que ela não
achava ficava sem ponto para sempre. Agora uma fila por trás procura em
várias fontes, da mais precisa para a mais larga, e uma varredura acerta
os antigos.
"""

from decimal import Decimal
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings

from core import utils as geo
from . import localizacao
from .models import Cliente, EnderecoCliente

L = "sistema_interno.localizacao."


def _endereco(**campos):
    cliente = Cliente.objects.create(nome_cliente=campos.pop("nome", "Buffet Mapa"), publicar_no_mapa=True)
    padrao = dict(cep="", endereco="Rua das Flores", numero="10", cidade="Campinas", estado="SP")
    padrao.update(campos)
    return EnderecoCliente.objects.create(cliente=cliente, **padrao)


class ProcurarTests(TestCase):
    def test_o_ponto_do_cep_vem_primeiro(self):
        e = _endereco(cep="13010-000")
        with mock.patch(L + "_ponto_do_cep", return_value=(-22.9, -47.06)) as cep, \
                mock.patch(L + "_cep_e_numero") as nominatim:
            self.assertTrue(localizacao.localizar_um(e.pk))
        cep.assert_called_once()
        nominatim.assert_not_called()
        e.refresh_from_db()
        self.assertAlmostEqual(float(e.latitude), -22.9)
        self.assertEqual(e.precisao, "")
        self.assertTrue(e.cliente.no_mapa)

    def test_sem_o_ponto_do_cep_vale_cep_e_numero_com_a_precisao(self):
        e = _endereco(cep="13010-000")
        with mock.patch(L + "_ponto_do_cep", return_value=(None, None)), \
                mock.patch(L + "_cep_e_numero", return_value=(-22.91, -47.07, "exato")):
            self.assertTrue(localizacao.localizar_um(e.pk))
        e.refresh_from_db()
        self.assertEqual(e.precisao, EnderecoCliente.Precisao.EXATO)

    def test_sem_cep_procura_rua_e_cidade(self):
        """O endereço sem CEP era justamente o que nunca ganhava ponto."""
        e = _endereco(cep="")
        with mock.patch(L + "_ponto_do_cep") as cep, \
                mock.patch(L + "_rua_e_cidade", return_value=(-22.92, -47.08, "rua")) as rua:
            self.assertTrue(localizacao.localizar_um(e.pk))
        cep.assert_not_called()
        rua.assert_called_once_with("Rua das Flores", "10", "Campinas", "SP", "Brasil")
        e.refresh_from_db()
        self.assertEqual(e.precisao, EnderecoCliente.Precisao.RUA)

    def test_nada_achou_a_rua_cai_no_centro_da_cidade(self):
        e = _endereco(cep="13010-000")
        with mock.patch(L + "_ponto_do_cep", return_value=(None, None)), \
                mock.patch(L + "_cep_e_numero", return_value=(None, None, None)), \
                mock.patch(L + "_rua_e_cidade", return_value=(None, None, None)), \
                mock.patch(L + "_centro_da_cidade", return_value=(-22.95, -47.1)):
            self.assertTrue(localizacao.localizar_um(e.pk))
        e.refresh_from_db()
        self.assertEqual(e.precisao, EnderecoCliente.Precisao.CIDADE)

    def test_nenhuma_fonte_achou_nao_grava_nada(self):
        e = _endereco()
        with mock.patch(L + "_rua_e_cidade", return_value=(None, None, None)), \
                mock.patch(L + "_municipio", return_value=(None, None)), \
                mock.patch(L + "_centro_da_cidade", return_value=(None, None)):
            self.assertIs(localizacao.localizar_um(e.pk), False)
        e.refresh_from_db()
        self.assertIsNone(e.latitude)

    def test_nunca_sobrescreve_um_ponto_que_ja_existe(self):
        e = _endereco(latitude=Decimal("-23.5"), longitude=Decimal("-46.6"), precisao="manual")
        with mock.patch(L + "procurar") as procurar:
            self.assertIsNone(localizacao.localizar_um(e.pk))
        procurar.assert_not_called()

    def test_o_ajuste_a_mao_feito_durante_a_busca_vence(self):
        e = _endereco()

        def procurar(endereco):
            # enquanto a busca roda, alguém marca o ponto à mão
            EnderecoCliente.objects.filter(pk=endereco.pk).update(
                latitude=Decimal("-1"), longitude=Decimal("-2"), precisao="manual",
            )
            return -22.9, -47.0, "cidade"

        with mock.patch(L + "procurar", side_effect=procurar):
            self.assertIs(localizacao.localizar_um(e.pk), False)
        e.refresh_from_db()
        self.assertEqual(e.precisao, "manual")
        self.assertEqual(e.latitude, Decimal("-1"))


class TabelaDoIbgeTests(TestCase):
    """A rede de segurança: o centro da cidade sai da tabela que está no site, sem rede."""

    def test_sem_nenhuma_fonte_de_fora_a_cidade_ainda_ganha_ponto(self):
        e = _endereco(cep="", cidade="Campinas", estado="SP")
        with mock.patch(L + "_rua_e_cidade", return_value=(None, None, None)), \
                mock.patch(L + "_centro_da_cidade") as de_fora:
            self.assertTrue(localizacao.localizar_um(e.pk))
        de_fora.assert_not_called()
        e.refresh_from_db()
        self.assertEqual(e.precisao, EnderecoCliente.Precisao.CIDADE)
        self.assertAlmostEqual(float(e.latitude), -22.9053, places=3)

    def test_os_jeitos_de_escrever_a_cidade(self):
        sp = geo.centro_do_municipio("São Paulo", "SP")
        self.assertAlmostEqual(sp[0], -23.53, places=1)
        self.assertEqual(geo.centro_do_municipio("SAO PAULO - SP"), sp)
        self.assertEqual(geo.centro_do_municipio("São Paulo/SP"), sp)
        self.assertEqual(geo.centro_do_municipio("São Paulo", "São Paulo"), sp)
        self.assertIsNotNone(geo.centro_do_municipio("Rio de Janeiro", "Rio de Janeiro")[0])
        # nome repetido em vários estados: sem a UF, nada de chute
        self.assertEqual(geo.centro_do_municipio("Bom Jesus"), (None, None))
        self.assertIsNotNone(geo.centro_do_municipio("Bom Jesus", "PI")[0])
        self.assertEqual(geo.centro_do_municipio("Cidade Que Não Existe", "SP"), (None, None))

    def test_tudo_numa_linha_so(self):
        """O cadastro importado com o endereço inteiro na linha da rua."""
        e = _endereco(cep="", cidade="", estado="",
                      endereco="Rua das Flores, 10 - Centro, Campinas - SP, 13010-000")
        onde = localizacao._onde_procurar(e)
        self.assertEqual(onde["cep"], "13010-000")
        self.assertEqual((onde["cidade"], onde["estado"]), ("Campinas", "SP"))
        with mock.patch(L + "_ponto_do_cep", return_value=(None, None)), \
                mock.patch(L + "_cep_e_numero", return_value=(None, None, None)), \
                mock.patch(L + "_rua_e_cidade", return_value=(None, None, None)):
            self.assertTrue(localizacao.localizar_um(e.pk))

    def test_so_o_cep_a_cidade_vem_dele(self):
        e = _endereco(cep="13010-000", cidade="", estado="")
        with mock.patch(L + "_dados_do_cep", return_value={"cidade": "Campinas", "estado": "SP"}):
            onde = localizacao._onde_procurar(e)
        self.assertEqual((onde["cidade"], onde["estado"]), ("Campinas", "SP"))


class FilaTests(TestCase):
    def setUp(self):
        localizacao._fila.clear()
        localizacao._na_fila.clear()
        localizacao._falhou_em.clear()

    def test_salvar_sem_ponto_poe_na_fila_depois_do_commit(self):
        with mock.patch(L + "pedir") as pedir, self.captureOnCommitCallbacks(execute=True):
            e = _endereco()
        pedir.assert_called_once_with(e.pk)

    def test_salvar_com_ponto_nao_poe_na_fila(self):
        with mock.patch(L + "pedir") as pedir, self.captureOnCommitCallbacks(execute=True):
            _endereco(latitude=Decimal("-23"), longitude=Decimal("-46"))
        pedir.assert_not_called()

    def test_nos_testes_a_fila_fica_desligada(self):
        self.assertFalse(localizacao.ativo())
        self.assertFalse(localizacao.pedir(1))

    @override_settings(LOCALIZAR_ENDERECOS_NO_SITE=True)
    def test_a_varredura_poe_so_os_sem_ponto_e_pula_a_falha_recente(self):
        sem = _endereco(nome="Sem ponto")
        falhou = _endereco(nome="Falhou agora")
        _endereco(nome="Com ponto", latitude=Decimal("-23"), longitude=Decimal("-46"))
        localizacao._falhou_em[falhou.pk] = localizacao.time.monotonic()
        with mock.patch("core.sempre_pronto._comando_de_manutencao", return_value=False), \
                mock.patch(L + "_garantir_thread"):
            localizacao.varrer()
        self.assertEqual(list(localizacao._fila), [sem.pk])

    @override_settings(LOCALIZAR_ENDERECOS_NO_SITE=True)
    def test_endereco_que_mudou_volta_a_fila_mesmo_depois_de_falhar(self):
        e = _endereco()
        localizacao._falhou_em[e.pk] = localizacao.time.monotonic()
        with mock.patch("core.sempre_pronto._comando_de_manutencao", return_value=False), \
                mock.patch(L + "_garantir_thread"):
            localizacao.pedir(e.pk)
        self.assertEqual(list(localizacao._fila), [e.pk])
        self.assertNotIn(e.pk, localizacao._falhou_em)


class ComandoTests(TestCase):
    def test_o_comando_localiza_e_relata(self):
        achado = _endereco(nome="Buffet Achado")
        _endereco(nome="Buffet Perdido", cidade="Cidade Que Não Existe")

        def centro(cidade, estado, pais):
            return (-22.9, -47.0) if cidade == "Campinas" else (None, None)

        saida = StringIO()
        with mock.patch(L + "_rua_e_cidade", return_value=(None, None, None)), \
                mock.patch(L + "_centro_da_cidade", side_effect=centro):
            call_command("localizar_enderecos", stdout=saida)
        texto = saida.getvalue()
        self.assertIn("Buffet Achado", texto)
        self.assertIn("não achei", texto)
        self.assertIn("1 de 2", texto)
        achado.refresh_from_db()
        self.assertTrue(achado.tem_local)


class FontesTests(TestCase):
    def test_open_meteo_so_aceita_a_cidade_do_estado_certo(self):
        resposta = {"results": [
            {"name": "São José", "admin1": "Santa Catarina", "latitude": -27.6, "longitude": -48.6},
            {"name": "São José", "admin1": "Rio Grande do Norte", "latitude": -6.1, "longitude": -35.2},
        ]}
        with mock.patch.object(geo, "_request_json", return_value=resposta):
            self.assertEqual(geo.buscar_cidade_open_meteo("São José", "SC"), (-27.6, -48.6))
            self.assertEqual(geo.buscar_cidade_open_meteo("Sao Jose", "Rio Grande do Norte"), (-6.1, -35.2))
            self.assertEqual(geo.buscar_cidade_open_meteo("São José", "SP"), (None, None))

    def test_open_meteo_fora_do_ar_nao_quebra(self):
        with mock.patch.object(geo, "_request_json", side_effect=geo.requests.ConnectionError("fora")):
            self.assertEqual(geo.buscar_cidade_open_meteo("Campinas", "SP"), (None, None))

    def test_rua_sem_numero_mapeado_e_rua_e_nao_exato(self):
        ponto = [{"lat": "-22.9", "lon": "-47.0", "address": {"road": "Rua das Flores"}}]
        with mock.patch.object(geo, "_consultar_nominatim", return_value=ponto):
            self.assertEqual(geo.geocodificar_sem_cep("Rua das Flores", "10", "Campinas", "SP"),
                             (-22.9, -47.0, "rua"))

    def test_no_ritmo_cada_consulta_espera_a_vez(self):
        esperas = []
        with mock.patch.object(geo.time, "sleep", side_effect=esperas.append), \
                mock.patch.object(geo, "_request_json", return_value=[]):
            geo._ultima_nominatim[0] = 0.0
            with geo.no_ritmo_do_nominatim():
                geo._consultar_nominatim({"q": "a"})
                geo._consultar_nominatim({"q": "b"})
            fora = len(esperas)
            geo._consultar_nominatim({"q": "c"})  # fora do bloco: ninguém espera
        self.assertEqual(fora, 1)
        self.assertEqual(len(esperas), 1)
        self.assertGreater(esperas[0], 0.5)
