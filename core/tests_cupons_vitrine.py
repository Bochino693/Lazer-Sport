from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from .models import Cupom, RecompensaCupom


class VitrineDeCuponsTests(TestCase):
    URL = "/estabelecimentos/"

    def test_mostra_cupom_publico_e_recompensa_do_app(self):
        Cupom.objects.create(
            codigo="PARCEIRO10",
            desconto_percentual=Decimal("10"),
            todos_usuarios=True,
            exibir_na_vitrine=True,
        )
        RecompensaCupom.objects.create(
            nome="Cupom de 15%",
            custo_pontos=250,
            desconto_percentual=Decimal("15"),
            exibir_na_vitrine_site=True,
        )

        resposta = self.client.get(self.URL)

        self.assertContains(resposta, "PARCEIRO10")
        self.assertContains(resposta, "Cupom de 15%")
        self.assertContains(resposta, "Resgate de pontos somente no app")

    def test_cupom_pessoal_so_aparece_para_seu_cliente(self):
        dono = User.objects.create_user("dono", password="senha-forte")
        outro = User.objects.create_user("outro", password="senha-forte")
        for usuario in (dono, outro):
            usuario.perfil.nome_completo = usuario.username.title()
            usuario.perfil.telefone = "(11)91234-5678"
            usuario.perfil.save(update_fields=["nome_completo", "telefone"])
        cupom = Cupom.objects.create(
            codigo="PESSOAL20",
            desconto_percentual=Decimal("20"),
            todos_usuarios=False,
            exibir_na_vitrine=False,
        )
        cupom.cliente.add(dono.perfil)

        self.client.force_login(outro)
        self.assertNotContains(self.client.get(self.URL), "PESSOAL20")

        self.client.force_login(dono)
        self.assertContains(self.client.get(self.URL), "PESSOAL20")

    def test_cupom_pessoal_nunca_vaza_na_vitrine_publica(self):
        dono = User.objects.create_user("cliente", password="senha-forte")
        cupom = Cupom.objects.create(
            codigo="SEGREDO30",
            desconto_percentual=Decimal("30"),
            todos_usuarios=False,
            exibir_na_vitrine=True,
        )
        cupom.cliente.add(dono.perfil)

        self.assertNotContains(self.client.get(self.URL), "SEGREDO30")
