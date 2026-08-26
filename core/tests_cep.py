"""Resolução de CEP usada pelo site e pelo aplicativo interno.

O campo que mais falta é o BAIRRO: o ViaCEP devolve vazio numa fatia
grande de CEPs, e é justamente o que quem monta uma entrega precisa. Por
isso a busca passa por mais de uma base, cada uma preenchendo só o que
ainda está em branco.

O que estes testes protegem:

  * o bairro que falta na primeira fonte é buscado nas seguintes;
  * uma fonte fora do ar não derruba o recurso -- a próxima assume;
  * quando tudo já veio na primeira, não se gasta consulta à toa;
  * CEP que não existe devolve None, e CEP de cidade inteira (sem bairro)
    devolve o resto em vez de fingir que não existe.
"""

from unittest.mock import patch

import requests
from django.test import SimpleTestCase

from .utils import buscar_dados_cep


VIACEP_COMPLETO = {
    "logradouro": "Avenida Paulista",
    "bairro": "Bela Vista",
    "localidade": "São Paulo",
    "uf": "SP",
}

VIACEP_SEM_BAIRRO = {
    "logradouro": "Avenida Brasil",
    "bairro": "",
    "localidade": "São Paulo",
    "uf": "SP",
}

BRASILAPI = {
    "street": "Avenida Brasil",
    "neighborhood": "Jardim América",
    "city": "São Paulo",
    "state": "SP",
}


class DadosCepTests(SimpleTestCase):

    def tearDown(self):
        buscar_dados_cep.cache_clear()

    @patch("core.utils._request_json")
    def test_resposta_completa_nao_gasta_segunda_consulta(self, requisitar):
        requisitar.side_effect = [VIACEP_COMPLETO]

        dados = buscar_dados_cep("01310-100")

        self.assertEqual(dados["bairro"], "Bela Vista")
        self.assertEqual(requisitar.call_count, 1)

    @patch("core.utils._request_json")
    def test_completa_bairro_ausente_com_a_fonte_alternativa(self, requisitar):
        requisitar.side_effect = [VIACEP_SEM_BAIRRO, BRASILAPI]

        dados = buscar_dados_cep("01430-001")

        self.assertEqual(dados["bairro"], "Jardim América")
        # A rua da primeira fonte não é sobrescrita pela segunda.
        self.assertEqual(dados["rua"], "Avenida Brasil")
        self.assertEqual(requisitar.call_count, 2)

    @patch("core.utils._request_json")
    def test_terceira_fonte_entra_quando_a_segunda_falha(self, requisitar):
        requisitar.side_effect = [
            VIACEP_SEM_BAIRRO,
            requests.RequestException("indisponível"),
            BRASILAPI,
        ]

        dados = buscar_dados_cep("01001-000")

        self.assertEqual(dados["bairro"], "Jardim América")
        self.assertEqual(requisitar.call_count, 3)

    @patch("core.utils._request_json")
    def test_viacep_fora_do_ar_nao_derruba_a_consulta(self, requisitar):
        """Antes, uma falha na primeira fonte devolvia None e a tela dizia
        que o CEP não existia -- para um CEP que existe."""
        requisitar.side_effect = [
            requests.RequestException("fora do ar"),
            BRASILAPI,
        ]

        dados = buscar_dados_cep("01001-001")

        self.assertEqual(dados["cidade"], "São Paulo")
        self.assertEqual(dados["bairro"], "Jardim América")

    @patch("core.utils._request_json")
    def test_cep_inexistente_devolve_none(self, requisitar):
        requisitar.side_effect = [
            {"erro": True},
            requests.RequestException("404"),
            requests.RequestException("404"),
        ]

        self.assertIsNone(buscar_dados_cep("99999-999"))

    @patch("core.utils._request_json")
    def test_cep_de_cidade_sem_bairro_ainda_serve(self, requisitar):
        """CEP geral de cidade não tem bairro em base nenhuma. A tela pede
        para conferir; o resto do endereço continua valendo."""
        sem_bairro = {
            "logradouro": "",
            "bairro": "",
            "localidade": "Cotia",
            "uf": "SP",
        }
        requisitar.side_effect = [
            sem_bairro,
            {"street": "", "neighborhood": "", "city": "Cotia", "state": "SP"},
            {"street": "", "neighborhood": "", "city": "Cotia", "state": "SP"},
        ]

        dados = buscar_dados_cep("06700-000")

        self.assertIsNotNone(dados)
        self.assertEqual(dados["cidade"], "Cotia")
        self.assertEqual(dados["bairro"], "")

    @patch("core.utils._request_json")
    def test_cep_invalido_nem_consulta(self, requisitar):
        self.assertIsNone(buscar_dados_cep("123"))
        requisitar.assert_not_called()
