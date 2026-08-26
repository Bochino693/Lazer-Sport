from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .models import Gerente
from .permissoes import atribuir_funcoes


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class MinhaContaTests(TestCase):
    URL = "/minha-conta/"

    def setUp(self):
        self.user = User.objects.create_user(
            username="thiago",
            password="senha-antiga",
            is_staff=True,
        )
        atribuir_funcoes(self.user, ["gestao"])
        self.gerente = Gerente.objects.create(user=self.user, nome="Thiago")
        self.client.force_login(self.user)

    def test_atualiza_nome_email_e_telefone(self):
        resposta = self.client.post(self.URL, {
            "first_name": "Thiago",
            "last_name": "Bochino",
            "email": "thiago@example.com",
            "telefone": "(11) 99999-0000",
        }, HTTP_HOST="interno.testserver")

        self.assertRedirects(
            resposta, self.URL,
            fetch_redirect_response=False,
        )
        self.user.refresh_from_db()
        self.gerente.refresh_from_db()
        self.assertEqual(self.user.get_full_name(), "Thiago Bochino")
        self.assertEqual(self.user.email, "thiago@example.com")
        self.assertEqual(self.gerente.nome, "Thiago Bochino")
        self.assertEqual(self.gerente.telefone, "(11) 99999-0000")

    def test_troca_senha_sem_encerrar_sessao(self):
        resposta = self.client.post(self.URL, {
            "first_name": "Thiago",
            "email": "thiago@example.com",
            "senha_atual": "senha-antiga",
            "senha_nova": "senha-nova-segura",
            "senha_confirmacao": "senha-nova-segura",
        }, HTTP_HOST="interno.testserver")

        self.assertEqual(resposta.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("senha-nova-segura"))
        pagina = self.client.get(self.URL, HTTP_HOST="interno.testserver")
        self.assertEqual(pagina.status_code, 200)
