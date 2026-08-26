"""Resolução de CEP usada pelo site e pelo aplicativo interno."""

from unittest.mock import patch

import requests
from django.test import SimpleTestCase

from .utils import buscar_dados_cep


class DadosCepTests(SimpleTestCase):
    def tearDown(self):
        buscar_dados_cep.cache_clear()

    @patch("core.utils._request_json")
    def test_completa_bairro_ausente_com_a_fonte_alternativa(self, requisitar):
        requisitar.side_effect = [
            {
                "logradouro": "Avenida Brasil",
                "bairro": "",
                "localidade": "São Paulo",
                "uf": "SP",
            },
            {
                "street": "Avenida Brasil",
                "neighborhood": "Jardim América",
                "city": "São Paulo",
                "state": "SP",
            },
        ]

        dados = buscar_dados_cep("01430-001")

        self.assertEqual(dados["bairro"], "Jardim América")
        self.assertEqual(requisitar.call_count, 2)

    @patch("core.utils._request_json")
    def test_falha_da_fonte_alternativa_preserva_viacep(self, requisitar):
        requisitar.side_effect = [
            {
                "logradouro": "Praça da Sé",
                "bairro": "",
                "localidade": "São Paulo",
                "uf": "SP",
            },
            requests.RequestException("indisponível"),
        ]

        dados = buscar_dados_cep("01001-000")

        self.assertEqual(dados["rua"], "Praça da Sé")
        self.assertEqual(dados["cidade"], "São Paulo")
