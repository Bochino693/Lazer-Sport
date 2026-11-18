"""A regra do e-mail das contas, a guarda do pre_save e o índice do banco.

Os e-mails daqui são inventados (example.com e o domínio da casa).
"""

from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group, User
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, override_settings

from sistema_interno.migrations._email_escopo import soltar_gatilhos

from .emails import (
    EmailEmUso,
    EmailIndisponivel,
    contas_com_email,
    e_reservado,
    normalizar_email,
    sincronizar_enderecos,
    trocar_email,
    validar_email_de_conta,
)


class NormalizarTests(TestCase):
    def test_caixa_espacos_e_ponto_final(self):
        self.assertEqual(normalizar_email("  Vendas@Exemplo.COM.BR. "), "vendas@exemplo.com.br")

    def test_variantes_unicode_viram_o_mesmo_endereco(self):
        # letras de largura total, espaço invisível no domínio, espaço inseparável
        self.assertEqual(normalizar_email("ｖｅｎｄａｓ@exemplo.com"), "vendas@exemplo.com")
        self.assertEqual(normalizar_email("vendas@exem​plo.com"), "vendas@exemplo.com")
        self.assertEqual(normalizar_email(" vendas@exemplo.com "), "vendas@exemplo.com")

    def test_vazio(self):
        self.assertEqual(normalizar_email(None), "")
        self.assertEqual(normalizar_email("   "), "")


class ValidarTests(TestCase):
    def setUp(self):
        self.comercial = User.objects.create_user("comercial", email="vendas@example.com", password="x")

    def test_recusa_o_mesmo_email_com_caixa_ou_variante_diferente(self):
        for variante in ("VENDAS@example.com", " vendas@EXAMPLE.com ", "ｖｅｎｄａｓ@example.com", "vendas@example.com."):
            with self.subTest(variante=variante), self.assertRaises(EmailIndisponivel) as erro:
                validar_email_de_conta(variante)
            self.assertEqual(erro.exception.code, "em_uso")

    def test_recusa_o_endereco_extra_do_allauth_de_outra_conta(self):
        EmailAddress.objects.create(user=self.comercial, email="extra@example.com")
        with self.assertRaises(EmailIndisponivel):
            validar_email_de_conta("Extra@Example.com")
        self.assertEqual(contas_com_email("EXTRA@example.com"), {self.comercial.pk})

    def test_a_propria_conta_pode_manter_o_endereco(self):
        self.assertEqual(validar_email_de_conta("Vendas@Example.com", usuario=self.comercial), "vendas@example.com")

    def test_endereco_da_empresa_so_pela_equipe(self):
        self.assertTrue(e_reservado("qualquer@lazersport.com.br"))
        self.assertTrue(e_reservado("contato@LazerSport.com"))
        with self.assertRaises(EmailIndisponivel) as erro:
            validar_email_de_conta("pessoa@lazersport.com.br")
        self.assertEqual(erro.exception.code, "reservado")
        self.assertEqual(validar_email_de_conta("pessoa@lazersport.com.br", pela_equipe=True), "pessoa@lazersport.com.br")
        equipe = User.objects.create_user("da-equipe", password="x")
        equipe.groups.add(Group.objects.get_or_create(name="Equipe · Vendas")[0])
        self.assertEqual(validar_email_de_conta("pessoa@lazersport.com.br", usuario=equipe), "pessoa@lazersport.com.br")

    @override_settings(CONTAS_EMAILS_RESERVADOS=["Financeiro <caixa@exemplo-empresa.com>"], CONTAS_DOMINIOS_RESERVADOS=[])
    def test_lista_de_reservados_do_settings(self):
        self.assertTrue(e_reservado("caixa@exemplo-empresa.com"))
        self.assertFalse(e_reservado("pessoa@lazersport.com.br"))

    def test_invalido(self):
        with self.assertRaises(EmailIndisponivel) as erro:
            validar_email_de_conta("nao-e-email")
        self.assertEqual(erro.exception.code, "invalido")


class GuardaTests(TestCase):
    """Nenhum caminho grava, nem pelo ORM direto, o e-mail de outra conta."""

    def setUp(self):
        self.comercial = User.objects.create_user("comercial", email="vendas@example.com", password="x")

    def test_conta_nova_com_o_mesmo_email_em_outra_caixa_e_recusada(self):
        for variante in ("VENDAS@example.com", "ｖｅｎｄａｓ@example.com", "vendas@example.com."):
            with self.subTest(variante=variante):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    User.objects.create_user(f"intruso-{len(variante)}", email=variante)
        self.assertEqual(User.objects.filter(email__iexact="vendas@example.com").count(), 1)

    def test_trocar_para_o_email_de_outra_conta_e_recusado(self):
        cliente = User.objects.create_user("cliente", email="cliente@example.com")
        cliente.email = "Vendas@Example.com"
        with self.assertRaises(EmailEmUso), transaction.atomic():
            cliente.save()

    def test_endereco_do_allauth_de_outra_conta_e_recusado(self):
        cliente = User.objects.create_user("cliente", email="cliente@example.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            EmailAddress.objects.create(user=cliente, email="VENDAS@example.com")

    def test_grava_normalizado(self):
        conta = User.objects.create_user("nova", email="  Nova.Pessoa@Example.COM ")
        conta.refresh_from_db()
        self.assertEqual(conta.email, "nova.pessoa@example.com")

    def test_salvar_sem_trocar_o_email_nao_consulta_nada_a_mais(self):
        self.comercial.refresh_from_db()
        with self.assertNumQueries(1):
            self.comercial.first_name = "Comercial"
            self.comercial.save()
        lida = User.objects.get(pk=self.comercial.pk)
        with self.assertNumQueries(1):
            lida.save(update_fields=["last_login"])


class EnderecosDoAllauthTests(TestCase):
    def test_trocar_email_leva_o_principal_e_solta_o_antigo_nao_confirmado(self):
        conta = User.objects.create_user("pessoa", email="antigo@example.com")
        sincronizar_enderecos(conta)
        EmailAddress.objects.create(user=conta, email="confirmado@example.com", verified=True)

        trocar_email(conta, "Novo@Example.com")

        enderecos = {e.email: e for e in EmailAddress.objects.filter(user=conta)}
        self.assertEqual(set(enderecos), {"novo@example.com", "confirmado@example.com"})
        self.assertTrue(enderecos["novo@example.com"].primary)
        self.assertFalse(enderecos["confirmado@example.com"].primary)
        # o antigo, não confirmado, ficou livre para outra pessoa
        self.assertEqual(validar_email_de_conta("antigo@example.com"), "antigo@example.com")

    def test_trocar_para_email_de_outra_conta_nao_grava_nada(self):
        User.objects.create_user("dono", email="dono@example.com")
        conta = User.objects.create_user("pessoa", email="pessoa@example.com")
        with self.assertRaises(EmailIndisponivel):
            trocar_email(conta, "DONO@example.com")
        conta.refresh_from_db()
        self.assertEqual(conta.email, "pessoa@example.com")


class IndiceDoBancoTests(TestCase):
    """O índice da migração contas/0003, sem a guarda e sem os gatilhos.

    Os gatilhos antigos (sistema_interno/0047) são soltos DENTRO da
    transação do teste: o SQLite desfaz o DDL junto no fim.
    """

    def _indices(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
            return {linha[0] for linha in cursor.fetchall()}

    def test_os_dois_indices_existem(self):
        self.assertLessEqual(
            {"contas_auth_user_email_unico", "contas_emailaddress_email_unico"}, self._indices(),
        )

    def test_o_banco_recusa_o_mesmo_email_em_outra_caixa(self):
        with connection.cursor() as cursor:
            soltar_gatilhos(cursor, connection.vendor)
        User.objects.create_user("um", email="mesmo@example.com")
        dois = User.objects.create_user("dois", email="dois@example.com")
        with self.assertRaises(IntegrityError) as erro, transaction.atomic():
            # update() pula a guarda do pre_save: quem recusa é o índice
            User.objects.filter(pk=dois.pk).update(email="MESMO@example.com")
        self.assertIn("contas_auth_user_email_unico", str(erro.exception))

    def test_varias_contas_sem_email_continuam_valendo(self):
        User.objects.create_user("sem-1", email="")
        User.objects.create_user("sem-2", email="")
        self.assertEqual(User.objects.filter(email="").count(), 2)

    def test_o_banco_recusa_o_mesmo_endereco_do_allauth_em_duas_contas(self):
        with connection.cursor() as cursor:
            soltar_gatilhos(cursor, connection.vendor)
        um = User.objects.create_user("um", email="um@example.com")
        dois = User.objects.create_user("dois", email="dois@example.com")
        EmailAddress.objects.create(user=um, email="extra@example.com")
        outro = EmailAddress.objects.create(user=dois, email="outro@example.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            EmailAddress.objects.filter(pk=outro.pk).update(email="EXTRA@example.com")
