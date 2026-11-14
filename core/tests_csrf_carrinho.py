"""Black Friday: logado, nada entrava no carrinho (core/views_seguranca.py).

O navegador guardava dois cookies csrftoken -- o velho primeiro. O JS lia
o primeiro, o Django lê o último: o token não batia, o servidor respondia
403 em HTML e a folha só dizia "Não foi possível adicionar este item".
Aqui a checagem de CSRF fica LIGADA (enforce_csrf_checks), como no ar.
"""

import re
from decimal import Decimal

from django.contrib.auth.models import User
from django.middleware.csrf import _get_new_csrf_string, _mask_cipher_secret
from django.test import Client, TestCase
from django.urls import reverse

from .models import Brinquedos, Carrinho


class CarrinhoComCsrfLigadoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("bia", "bia@exemplo.com", "Senha#12345")
        perfil = self.user.perfil
        perfil.telefone = "(11)91234-5678"
        perfil.save(update_fields=["telefone"])
        self.perfil = perfil
        self.brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Air Game Kids", descricao="x", avaliacao=Decimal("5"),
            valor_brinquedo=Decimal("4990.00"), exibir_na_loja=True,
        )
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.url = reverse("adicionar_ao_carrinho", args=["brinquedo", self.brinquedo.pk])

    def _segredo_atual(self):
        # Abre uma página: o Django cria o segredo e manda o cookie.
        self.client.get(reverse("token_csrf"))
        return self.client.cookies["csrftoken"].value

    def _postar(self, token, cookie_cru=None):
        extra = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest", "HTTP_X_CSRFTOKEN": token}
        if cookie_cru is not None:
            extra["HTTP_COOKIE"] = cookie_cru
        return self.client.post(self.url, {"quantidade": "1"}, **extra)

    def test_token_errado_responde_json_que_explica(self):
        self._segredo_atual()
        r = self._postar("x" * 64)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r["Content-Type"], "application/json")
        dados = r.json()
        self.assertEqual(dados["codigo"], "csrf")
        self.assertIn("Atualize a página", dados["erro"])

    def test_token_novo_do_endpoint_poe_no_carrinho(self):
        r = self.client.get(reverse("token_csrf"), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(r.status_code, 200)
        self.assertIn("no-cache", r.get("Cache-Control", ""))
        r = self._postar(r.json()["token"])
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertTrue(r.json()["sucesso"])
        self.assertEqual(Carrinho.objects.get(cliente=self.perfil).itens.count(), 1)

    def test_dois_cookies_o_velho_primeiro_como_no_navegador(self):
        """O caso do ar: o token do cookie velho falha; o da página entra."""
        atual = self._segredo_atual()
        velho = _get_new_csrf_string()
        sessao = self.client.cookies["sessionid"].value
        cru = f"csrftoken={velho}; sessionid={sessao}; csrftoken={atual}"

        # o que o JS antigo mandava: o primeiro cookie
        r = self._postar(velho, cookie_cru=cru)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["codigo"], "csrf")

        # o que o JS novo manda: o token impresso na página (segredo atual)
        r = self._postar(_mask_cipher_secret(atual), cookie_cru=cru)
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertTrue(r.json()["sucesso"])

    def test_pagina_entrega_o_token_e_a_segunda_chance(self):
        html = self.client.get(reverse("home")).content.decode()
        self.assertIn('meta name="csrf-token"', html)
        self.assertIn("window.LSCsrf", html)
        self.assertIn("/seguranca/token/", html)
        # o cookie velho é apagado só quando há dois
        self.assertIn('d.cookie = "csrftoken=; Max-Age=0; path=/"', html)
        self.assertTrue(re.search(r"cookies\.length > 1", html))

    def test_tela_comum_sem_fetch_continua_com_a_pagina_padrao(self):
        self._segredo_atual()
        r = self.client.post(reverse("carrinho"), {"x": "1"})
        self.assertEqual(r.status_code, 403)
        self.assertIn("text/html", r["Content-Type"])

    def test_scripts_usam_o_token_da_pagina_e_tentam_de_novo(self):
        from pathlib import Path
        from django.conf import settings
        base = Path(settings.BASE_DIR) / "core" / "static" / "site"
        rapido = (base / "ls-carrinho-rapido.js").read_text(encoding="utf-8")
        self.assertIn("window.LSCsrf.token()", rapido)
        self.assertIn("lsc.renovar().then(uma", rapido)
        for nome in ("ls-favoritos.js", "ls-app-avisos.js", "ls-confirmacao.js"):
            self.assertIn("window.LSCsrf", (base / nome).read_text(encoding="utf-8"), nome)
