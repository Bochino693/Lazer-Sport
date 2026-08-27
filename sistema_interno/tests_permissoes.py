from importlib import import_module

from django.apps import apps
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .models import Colaborador, Gerente
from .permissoes import GESTAO, atribuir_funcoes, capacidades


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class FuncoesDaEquipeTests(TestCase):
    def usuario(self, username, *funcoes):
        user = User.objects.create_user(username=username, password="senha-segura")
        atribuir_funcoes(user, funcoes)
        return user

    def abrir(self, rota, user, **extras):
        self.client.force_login(user)
        return self.client.get(rota, HTTP_HOST="interno.testserver", **extras)

    def test_funcoes_sao_aditivas_sem_subclasse_de_usuario(self):
        user = self.usuario("hibrido", "vendas", "gestao")
        acesso = capacidades(user)

        self.assertTrue(acesso["vendas"])
        self.assertTrue(acesso["gestao"])
        self.assertTrue(acesso["orcamentos"])
        self.assertTrue(acesso["financeiro"])
        self.assertFalse(acesso["producao"])

    def test_criador_trabalha_no_site_mas_nao_abre_financeiro(self):
        criador = self.usuario("criador", "criacao")

        catalogo = self.abrir("/site/brinquedos/", criador)
        financeiro = self.abrir("/financeiro/", criador)

        self.assertEqual(catalogo.status_code, 200)
        self.assertContains(catalogo, "Gestão interna")
        self.assertNotContains(catalogo, "adm-sidebar")
        self.assertRedirects(
            financeiro,
            "/site/brinquedos/",
            fetch_redirect_response=False,
        )

    def test_vendedor_abre_cliente_e_orcamento_sem_ver_financeiro(self):
        vendedor = self.usuario("vendedor", "vendas")
        acesso = capacidades(vendedor)

        self.assertEqual(self.abrir("/clientes/", vendedor).status_code, 200)
        self.assertEqual(self.abrir("/orcamentos/", vendedor).status_code, 200)
        self.assertFalse(acesso["excluir_clientes"])
        self.assertTrue(acesso["excluir_orcamentos"])
        self.assertFalse(acesso["excluir_orcamentos_alheios"])
        self.assertRedirects(
            self.abrir("/financeiro/", vendedor),
            "/orcamentos/",
            fetch_redirect_response=False,
        )

    def test_colaborador_da_montagem_nao_e_usuario(self):
        producao = self.usuario("engenheira", "producao")
        self.client.force_login(producao)
        resposta = self.client.post(
            "/producao/ordens/",
            {"action": "colaborador_save", "nome_colaborador": "Carlos Montagem"},
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(Colaborador.objects.filter(nome="Carlos Montagem").exists())
        self.assertFalse(User.objects.filter(username="Carlos Montagem").exists())


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver", "lazersport.com.br"])
class DelegacaoETransicaoTests(TestCase):
    def setUp(self):
        self.super = User.objects.create_superuser(
            username="super",
            password="senha-segura",
            email="super@example.com",
        )

    def test_super_delega_varias_funcoes_na_mesma_conta(self):
        self.client.force_login(self.super)
        resposta = self.client.post(
            "/equipe/",
            {
                "action": "save",
                "username": "ana",
                "first_name": "Ana",
                "email": "ana@example.com",
                "password": "senha-segura",
                "is_active": "on",
                "funcoes": ["producao", "vendas"],
            },
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(resposta.status_code, 200)
        ana = User.objects.get(username="ana")
        self.assertTrue(capacidades(ana)["producao"])
        self.assertTrue(capacidades(ana)["vendas"])

    def test_contas_de_clientes_sao_exclusivas_do_super(self):
        gestor = User.objects.create_user(
            username="gestor",
            password="senha-segura",
        )
        atribuir_funcoes(gestor, ["gestao"])
        self.client.force_login(gestor)

        resposta = self.client.get(
            "/site/contas-clientes/",
            HTTP_HOST="interno.testserver",
        )

        self.assertRedirects(resposta, "/", fetch_redirect_response=False)

    def test_migracao_preserva_gerente_antigo_sem_is_staff(self):
        legado = User.objects.create_user(
            username="gerente-legado",
            password="senha-segura",
            is_staff=False,
        )
        Gerente.objects.create(user=legado, nome="Gerente legado", ativo=True)
        migracao = import_module("sistema_interno.migrations.0018_funcoes_equipe")

        migracao.criar_funcoes_e_migrar_equipe(apps, None)

        legado.refresh_from_db()
        self.assertTrue(legado.is_staff)
        self.assertTrue(legado.groups.filter(name=GESTAO).exists())

    def test_painel_adm_antigo_redireciona_para_o_interno(self):
        resposta = self.client.get(
            "/adm/brinquedos/",
            HTTP_HOST="lazersport.com.br",
        )

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(
            resposta["Location"],
            "https://interno.lazersport.com.br/site/brinquedos/",
        )
