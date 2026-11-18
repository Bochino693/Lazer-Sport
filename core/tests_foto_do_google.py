"""A foto do Google nas contas do painel (core.presenca.foto_da_conta).

O dono: "nos clientes, não podemos pegar a foto do Google e pôr ali, somente
em caso de não haver que fica sem?". Quem entrou com o Google mostra a foto;
quem não tem fica com as iniciais.
"""

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import User
from django.test import TestCase

from core.presenca import cartao_da_conta, foto_da_conta

FOTO = "https://lh3.googleusercontent.com/a/ACg8ocJteste=s96-c"


class FotoDaContaTests(TestCase):
    def setUp(self):
        self.com_google = User.objects.create_user("ana", "ana@example.com", "x", first_name="Ana", last_name="Lima")
        SocialAccount.objects.create(user=self.com_google, provider="google", uid="1", extra_data={"picture": FOTO})
        self.sem_foto = User.objects.create_user("bia", "bia@example.com", "x", first_name="Bia", last_name="Reis")

    def _com_prefetch(self, usuario):
        return User.objects.prefetch_related("socialaccount_set").get(pk=usuario.pk)

    def test_foto_do_google_maior_que_a_miniatura(self):
        self.assertEqual(
            foto_da_conta(self._com_prefetch(self.com_google)),
            "https://lh3.googleusercontent.com/a/ACg8ocJteste=s160-c",
        )

    def test_sem_conta_social_fica_sem_foto_e_com_iniciais(self):
        cartao = cartao_da_conta(self._com_prefetch(self.sem_foto))
        self.assertEqual(cartao["foto"], "")
        self.assertEqual(cartao["iniciais"], "BR")

    def test_sem_prefetch_nao_consulta_uma_por_pessoa(self):
        conta = User.objects.get(pk=self.com_google.pk)
        with self.assertNumQueries(0):
            self.assertEqual(foto_da_conta(conta), "")

    def test_foto_sem_https_e_ignorada(self):
        SocialAccount.objects.filter(user=self.com_google).update(extra_data={"picture": "http://x/y.jpg"})
        self.assertEqual(foto_da_conta(self._com_prefetch(self.com_google)), "")

    def test_lista_de_contas_mostra_a_foto_e_as_iniciais_por_baixo(self):
        admin = User.objects.create_superuser("chefe", "chefe@example.com", "x")
        self.client.force_login(admin)

        resposta = self.client.get("/site/contas-clientes/", HTTP_HOST="interno.testserver")
        if resposta.status_code in (301, 302):
            resposta = self.client.get(resposta["Location"], HTTP_HOST="interno.testserver")
        html = resposta.content.decode()
        self.assertIn("ACg8ocJteste=s160-c", html)
        self.assertIn('referrerpolicy="no-referrer"', html)
        self.assertIn("tem-foto", html)
