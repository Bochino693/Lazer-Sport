"""A migração de dados contas/0002 (contas com o mesmo e-mail) e o índice da 0003.

Para montar o banco "de antes", com contas repetidas, os gatilhos antigos
(sistema_interno/0047) e os índices da 0003 são soltos e as contas são
gravadas por `update()`, que pula a guarda do pre_save. No TestCase isso
acontece dentro da transação do teste (o SQLite desfaz o DDL junto); no
teste da migração de verdade (TransactionTestCase), tudo é refeito no fim.
E-mails inventados.
"""

import importlib
from datetime import timedelta

from allauth.account.models import EmailAddress
from django.apps import apps
from django.contrib.auth.models import Group, User
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from sistema_interno.migrations._email_escopo import criar_gatilhos, soltar_gatilhos

from .models import OcorrenciaSeguranca

MIGRACAO = importlib.import_module("contas.migrations.0002_contas_com_email_repetido")
INDICES = ("contas_auth_user_email_unico", "contas_emailaddress_email_unico")


def soltar_travas():
    with connection.cursor() as cursor:
        soltar_gatilhos(cursor, connection.vendor)
        for indice in INDICES:
            cursor.execute(f"DROP INDEX IF EXISTS {indice}")


def conta(username, email, *, dias=0, **campos):
    """Conta gravada com o e-mail CRU, do jeito que o banco antigo aceitava."""
    usuario = User.objects.create_user(username, email=f"{username}@provisorio.example", **campos)
    User.objects.filter(pk=usuario.pk).update(
        email=email, date_joined=timezone.now() - timedelta(days=dias),
    )
    usuario.refresh_from_db()
    return usuario


def endereco(usuario, email, **campos):
    registro = EmailAddress.objects.create(user=usuario, email=f"{usuario.username}-{EmailAddress.objects.count()}@provisorio.example", **campos)
    EmailAddress.objects.filter(pk=registro.pk).update(email=email)
    return registro


class ResolverRepetidosTests(TestCase):
    def setUp(self):
        soltar_travas()

    def resolver(self):
        MIGRACAO.resolver(apps)

    def test_a_conta_da_equipe_fica_e_a_do_cliente_e_bloqueada(self):
        cliente = conta("cliente", "vendas@example.com", dias=300)
        EmailAddress.objects.filter(user=cliente).delete()
        endereco(cliente, "vendas@example.com", primary=True)
        comercial = conta("comercial", "Vendas@Example.com", dias=10, is_staff=True)

        self.resolver()

        cliente.refresh_from_db()
        comercial.refresh_from_db()
        self.assertFalse(cliente.is_active)
        self.assertEqual(cliente.email, "")
        self.assertFalse(EmailAddress.objects.filter(user=cliente).exists())
        self.assertTrue(comercial.is_active)
        self.assertEqual(comercial.email, "vendas@example.com")  # normalizado

        ocorrencia = OcorrenciaSeguranca.objects.get()
        self.assertEqual(ocorrencia.tipo, OcorrenciaSeguranca.Tipo.EMAIL_REPETIDO)
        self.assertEqual(ocorrencia.situacao, OcorrenciaSeguranca.Situacao.PENDENTE)
        self.assertEqual(ocorrencia.usuario, cliente)
        self.assertEqual(ocorrencia.conta_mantida, comercial)
        self.assertEqual(ocorrencia.email_original, "vendas@example.com")
        self.assertEqual(ocorrencia.origem, "migracao")

    def test_funcao_de_equipe_vale_como_conta_comercial(self):
        cliente = conta("cliente", "vendas@example.com", dias=300)
        vendedor = conta("vendedor", " VENDAS@example.com ", dias=1)
        vendedor.groups.add(Group.objects.get_or_create(name="Equipe · Vendas")[0])
        self.resolver()
        cliente.refresh_from_db()
        vendedor.refresh_from_db()
        self.assertFalse(cliente.is_active)
        self.assertTrue(vendedor.is_active)

    def test_entre_clientes_fica_quem_confirmou_o_email(self):
        antiga = conta("antiga", "maria@example.com", dias=300)
        confirmada = conta("confirmada", "Maria@example.com", dias=5)
        endereco(confirmada, "maria@example.com", verified=True, primary=True)
        self.resolver()
        antiga.refresh_from_db()
        confirmada.refresh_from_db()
        self.assertFalse(antiga.is_active)
        self.assertTrue(confirmada.is_active)

    def test_sem_confirmacao_fica_a_mais_antiga(self):
        antiga = conta("antiga", "joao@example.com", dias=300)
        nova = conta("nova", "JOAO@example.com", dias=5)
        self.resolver()
        antiga.refresh_from_db()
        nova.refresh_from_db()
        self.assertTrue(antiga.is_active)
        self.assertFalse(nova.is_active)
        self.assertEqual(OcorrenciaSeguranca.objects.get().usuario, nova)

    def test_variante_unicode_e_ponto_final_contam_como_repetidos(self):
        um = conta("um", "ana@example.com", dias=300)
        dois = conta("dois", "ａｎａ@example.com", dias=5)
        tres = conta("tres", "ana@example.com.", dias=2)
        self.resolver()
        for usuario, ativo in ((um, True), (dois, False), (tres, False)):
            usuario.refresh_from_db()
            self.assertEqual(usuario.is_active, ativo, usuario.username)
        self.assertEqual(OcorrenciaSeguranca.objects.count(), 2)

    def test_endereco_extra_do_allauth_com_o_email_comercial(self):
        comercial = conta("comercial", "vendas@example.com", dias=1, is_staff=True)
        cliente = conta("cliente", "cliente@example.com", dias=300)
        endereco(cliente, "VENDAS@example.com")
        self.resolver()
        cliente.refresh_from_db()
        self.assertFalse(cliente.is_active)
        self.assertEqual(cliente.email, "cliente@example.com")  # o principal não era o repetido
        self.assertFalse(EmailAddress.objects.filter(user=cliente, email__iexact="vendas@example.com").exists())
        ocorrencia = OcorrenciaSeguranca.objects.get()
        self.assertEqual(ocorrencia.conta_mantida, comercial)
        self.assertEqual(ocorrencia.email_original, "VENDAS@example.com")

    def test_normaliza_o_que_sobrou_e_junta_enderecos_da_mesma_conta(self):
        sozinha = conta("sozinha", "  Solo@Example.COM ")
        EmailAddress.objects.filter(user=sozinha).delete()
        endereco(sozinha, "Solo@Example.com", primary=True)
        endereco(sozinha, "solo@example.com", verified=True)
        self.resolver()
        sozinha.refresh_from_db()
        self.assertEqual(sozinha.email, "solo@example.com")
        enderecos = list(EmailAddress.objects.filter(user=sozinha))
        self.assertEqual(len(enderecos), 1)
        self.assertEqual(enderecos[0].email, "solo@example.com")
        self.assertTrue(enderecos[0].verified)
        self.assertTrue(enderecos[0].primary)
        self.assertFalse(OcorrenciaSeguranca.objects.exists())

    def test_rodar_de_novo_nao_muda_nada(self):
        conta("antiga", "joao@example.com", dias=300)
        conta("nova", "JOAO@example.com", dias=5)
        self.resolver()
        antes = list(User.objects.order_by("pk").values_list("pk", "email", "is_active"))
        self.resolver()
        self.assertEqual(list(User.objects.order_by("pk").values_list("pk", "email", "is_active")), antes)
        self.assertEqual(OcorrenciaSeguranca.objects.count(), 1)


class ComandoContasRepetidasTests(TestCase):
    def setUp(self):
        soltar_travas()

    def test_mostra_mascarado_e_so_resolve_com_aplicar(self):
        from io import StringIO

        from django.core.management import call_command

        conta("antiga", "joao@example.com", dias=300)
        nova = conta("nova", "JOAO@example.com", dias=5)
        saida = StringIO()
        call_command("contas_repetidas", stdout=saida)
        self.assertIn("j***@example.com", saida.getvalue())
        self.assertNotIn("joao@", saida.getvalue())
        nova.refresh_from_db()
        self.assertTrue(nova.is_active)

        call_command("contas_repetidas", "--aplicar", stdout=StringIO())
        nova.refresh_from_db()
        self.assertFalse(nova.is_active)
        saida = StringIO()
        call_command("contas_repetidas", stdout=saida)
        self.assertIn("Nenhum e-mail", saida.getvalue())


class MigracaoDeVerdadeTests(TransactionTestCase):
    """migrate contas 0001 -> 0003 num banco com contas repetidas."""

    def tearDown(self):
        MigrationExecutor(connection).migrate([("contas", "0003_email_unico_no_banco")])
        with connection.cursor() as cursor:
            soltar_gatilhos(cursor, connection.vendor)
            criar_gatilhos(cursor, connection.vendor)

    def _indices(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
            return {linha[0] for linha in cursor.fetchall()}

    def test_migrar_resolve_os_repetidos_e_poe_o_indice(self):
        MigrationExecutor(connection).migrate([("contas", "0001_ocorrencia_seguranca")])
        self.assertFalse(set(INDICES) & self._indices())
        soltar_travas()

        comercial = conta("comercial", "Vendas@Example.com", dias=10, is_superuser=True, is_staff=True)
        cliente = conta("cliente", "vendas@example.com ", dias=400)

        MigrationExecutor(connection).migrate([("contas", "0003_email_unico_no_banco")])

        self.assertLessEqual(set(INDICES), self._indices())
        comercial.refresh_from_db()
        cliente.refresh_from_db()
        self.assertEqual(comercial.email, "vendas@example.com")
        self.assertTrue(comercial.is_active)
        self.assertFalse(cliente.is_active)
        self.assertEqual(cliente.email, "")
        self.assertEqual(OcorrenciaSeguranca.objects.get().usuario_id, cliente.pk)

        # a volta da 0003 solta os índices
        MigrationExecutor(connection).migrate([("contas", "0002_contas_com_email_repetido")])
        self.assertFalse(set(INDICES) & self._indices())
