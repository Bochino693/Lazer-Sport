"""A central de avisos: o que aparece, para quem, e a que custo.

O custo tem teste próprio porque o context processor é global — roda em
toda página do site, e não só no painel. Uma regressão ali não quebra
nada visível: só deixa a loja mais lenta para quem está logado como
equipe, que é o tipo de problema que ninguém liga a este arquivo meses
depois.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.template import Context, Template
from django.test.utils import CaptureQueriesContext
from django.test import RequestFactory, TestCase
from django.utils import timezone

from core.models import Manutencao, Pedido

from . import avisos as mod
from .context_processors import fab_counts
from .permissoes import atribuir_funcoes
from .models import (
    Colaborador,
    EstoqueMaterial,
    Material,
    Orcamento,
    OrdemProducao,
    ProdutoInterno,
    TipoMaterial,
)


class ColetaDeAvisosTests(TestCase):

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor",
            password="x",
            email="g@example.com",
        )
        self.hoje = timezone.localdate()

    def chaves(self, user=None):
        return [a.chave for a in mod.coletar(user or self.gestor)]

    # ----------------------------------------------------- orçamentos
    def test_vencido_e_a_vencer_sao_avisos_diferentes(self):
        """Vencido é perda; a vencer ainda dá para salvar num telefonema."""
        Orcamento.objects.create(
            nome_cliente="Já era",
            status=Orcamento.Status.ENVIADO,
            validade=self.hoje - timedelta(days=1),
        )
        Orcamento.objects.create(
            nome_cliente="Ainda dá",
            status=Orcamento.Status.ENVIADO,
            validade=self.hoje + timedelta(days=2),
        )

        chaves = self.chaves()
        self.assertIn("orcamentos_vencidos", chaves)
        self.assertIn("orcamentos_vencendo", chaves)

    def test_orcamento_ja_respondido_nao_cobra_validade(self):
        Orcamento.objects.create(
            nome_cliente="Fechado",
            status=Orcamento.Status.APROVADO,
            validade=self.hoje - timedelta(days=5),
        )
        self.assertNotIn("orcamentos_vencidos", self.chaves())

    def test_validade_distante_nao_vira_aviso(self):
        Orcamento.objects.create(
            nome_cliente="Tem tempo",
            status=Orcamento.Status.ENVIADO,
            validade=self.hoje + timedelta(days=30),
        )
        self.assertNotIn("orcamentos_vencendo", self.chaves())

    def test_resposta_recente_do_cliente_vira_novidade(self):
        orcamento = Orcamento.objects.create(
            nome_cliente="Fulano",
            status=Orcamento.Status.ENVIADO,
        )
        orcamento.registrar_resposta(aprovado=True, nome="Fulano")

        self.assertIn("orcamentos_aprovados", self.chaves())

    def test_resposta_antiga_para_de_avisar(self):
        """Aviso é do que acabou de acontecer, não histórico."""
        orcamento = Orcamento.objects.create(
            nome_cliente="Fulano",
            status=Orcamento.Status.APROVADO,
        )
        Orcamento.objects.filter(pk=orcamento.pk).update(
            respondido_em=timezone.now() - timedelta(days=mod.DIAS_DE_NOVIDADE + 1)
        )

        self.assertNotIn("orcamentos_aprovados", self.chaves())

    # -------------------------------------------------------- estoque
    def test_material_no_minimo_entra_como_critico(self):
        """Mesma conta da propriedade `situacao`, feita no banco."""
        tipo = TipoMaterial.objects.create(descricao="Lona")
        material = Material.objects.create(
            nome_material="Lona 500",
            tipo_material=tipo,
        )
        EstoqueMaterial.objects.create(
            material=material,
            descricao_local="Galpão",
            quantidade=2,
            estoque_minimo=5,
            preco_fornecedor=Decimal("10.00"),
        )

        self.assertIn("estoque", self.chaves())

    def test_material_acima_do_minimo_nao_avisa(self):
        tipo = TipoMaterial.objects.create(descricao="Lona")
        material = Material.objects.create(
            nome_material="Lona 500",
            tipo_material=tipo,
        )
        EstoqueMaterial.objects.create(
            material=material,
            descricao_local="Galpão",
            quantidade=50,
            estoque_minimo=5,
            preco_fornecedor=Decimal("10.00"),
        )

        self.assertNotIn("estoque", self.chaves())

    def test_conta_do_banco_bate_com_a_propriedade_do_modelo(self):
        """A consulta e a propriedade não podem discordar sobre "crítico"."""
        tipo = TipoMaterial.objects.create(descricao="Lona")
        material = Material.objects.create(nome_material="Lona", tipo_material=tipo)

        for quantidade, minimo in ((0, 0), (5, 5), (6, 5), (1, 0), (4, 10)):
            EstoqueMaterial.objects.create(
                material=material,
                descricao_local=f"Local {quantidade}-{minimo}",
                quantidade=quantidade,
                estoque_minimo=minimo,
                preco_fornecedor=Decimal("1.00"),
            )

        pela_propriedade = sum(
            1 for e in EstoqueMaterial.objects.all()
            if e.situacao == EstoqueMaterial.CRITICO
        )
        pelo_banco = EstoqueMaterial.objects.criticos().count()

        self.assertEqual(pela_propriedade, pelo_banco)

    # ------------------------------------------------------- operação
    def test_pedido_e_manutencao_aparecem(self):
        Pedido.objects.create(status="pendente")
        Manutencao.objects.create(
            descricao="Rasgou a lona",
            status="P",
            usuario=self._perfil(),
        )

        chaves = self.chaves()
        self.assertIn("pedidos", chaves)
        self.assertIn("manutencoes", chaves)

    def _perfil(self):
        """O perfil já nasce junto com o User, por signal do core."""
        from core.models import ClientePerfil

        cliente = User.objects.create_user(username="cliente", password="x")
        perfil, _ = ClientePerfil.objects.get_or_create(user=cliente)
        return perfil

    # --------------------------------------------------------- ordem
    def test_pior_vem_primeiro(self):
        Orcamento.objects.create(
            nome_cliente="Vencido",
            status=Orcamento.Status.ENVIADO,
            validade=self.hoje - timedelta(days=1),
        )
        Pedido.objects.create(status="pendente")

        niveis = [a.nivel for a in mod.coletar(self.gestor)]
        self.assertEqual(niveis[0], "critico")
        self.assertEqual(niveis[-1], "info")

    # -------------------------------------------------------- alcance
    def test_montador_nao_recebe_aviso_comercial(self):
        """Avisar sobre tela que a pessoa não pode abrir é número piscando
        sem saída: as views comerciais já desviam quem não é gerência."""
        montador = User.objects.create_user(
            username="montador", password="x", is_staff=True,
        )
        atribuir_funcoes(montador, ["producao"])
        Orcamento.objects.create(
            nome_cliente="Vencido",
            status=Orcamento.Status.ENVIADO,
            validade=self.hoje - timedelta(days=1),
        )

        chaves = self.chaves(montador)
        self.assertNotIn("orcamentos_vencidos", chaves)
        self.assertNotIn("vendas", chaves)

    def test_equipe_de_producao_ve_a_fabrica_sem_ligar_montador_a_login(self):
        usuario_producao = User.objects.create_user(
            username="producao", password="x", is_staff=True,
        )
        atribuir_funcoes(usuario_producao, ["producao"])
        montador = Colaborador.objects.create(nome="Montador A")
        outro = Colaborador.objects.create(nome="Montador B")
        produto = ProdutoInterno.objects.create(nome="Máquina")

        OrdemProducao.objects.create(produto=produto, quantidade=1, colaborador=montador)
        OrdemProducao.objects.create(produto=produto, quantidade=1, colaborador=outro)

        producao = [a for a in mod.coletar(usuario_producao) if a.chave == "producao"]
        self.assertEqual(len(producao), 1)
        self.assertEqual(producao[0].quantidade, 2)

    def test_funcao_gestao_conta_como_gestor(self):
        from .permissoes import atribuir_funcoes

        usuario = User.objects.create_user(username="gerente", password="x")
        atribuir_funcoes(usuario, ["gestao"])

        self.assertTrue(mod.eh_gestor(usuario))

    def test_visitante_nao_recebe_nada(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertEqual(mod.coletar(AnonymousUser()), [])


class CustoDoContextProcessorTests(TestCase):
    """O context processor é global: roda na loja inteira, não só no painel."""

    def setUp(self):
        self.factory = RequestFactory()
        self.gestor = User.objects.create_superuser(
            username="gestor", password="x", email="g@example.com",
        )

    def pedido(self, usuario):
        req = self.factory.get("/")
        req.user = usuario
        return req

    def test_template_que_nao_usa_avisos_nao_consulta_nada(self):
        contexto = fab_counts(self.pedido(self.gestor))

        with self.assertNumQueries(0):
            Template("nada aqui").render(Context(contexto))

    def test_valores_sao_calculados_uma_vez_so(self):
        Orcamento.objects.create(
            nome_cliente="Vencido",
            status=Orcamento.Status.ENVIADO,
            validade=timezone.localdate() - timedelta(days=1),
        )
        contexto = fab_counts(self.pedido(self.gestor))

        modelo = Template(
            "{{ total_avisos }}{{ count_pedidos }}{{ count_vendas }}"
            "{% for a in avisos %}{{ a.titulo }}{% endfor %}"
        )

        # Quanto custa apurar uma vez. Medido, e não fixado numa
        # constante: um aviso novo muda o número, e o que este teste
        # protege não é o valor -- é a igualdade abaixo.
        with CaptureQueriesContext(connection) as medida:
            mod.coletar(self.gestor)
        de_uma_vez = len(medida)

        # Ler cinco chaves não pode custar cinco apurações.
        with self.assertNumQueries(de_uma_vez):
            saida = modelo.render(Context(contexto))

        # singular: é um só orçamento vencido no cenário
        self.assertIn("Orçamento vencido", saida)

    def test_visitante_nao_consulta(self):
        from django.contrib.auth.models import AnonymousUser

        with self.assertNumQueries(0):
            contexto = fab_counts(self.pedido(AnonymousUser()))
            Template("{{ total_avisos }}").render(Context(contexto))

    def test_comparacao_numerica_funciona_no_template(self):
        """As bolinhas do menu usam `{% if count_x > 0 %}`."""
        Pedido.objects.create(status="pendente")
        contexto = fab_counts(self.pedido(self.gestor))

        saida = Template(
            "{% if count_pedidos > 0 %}tem {{ count_pedidos }}{% else %}nada{% endif %}"
        ).render(Context(contexto))

        self.assertEqual(saida, "tem 1")

    def test_troca_de_tela_reaproveita_contadores_por_alguns_segundos(self):
        Pedido.objects.create(status="pendente")
        modelo = Template("{{ total_avisos }} {{ count_pedidos }}")

        primeiro = fab_counts(self.pedido(self.gestor))
        self.assertEqual(modelo.render(Context(primeiro)), "1 1")

        # Uma nova requisição logo depois representa o clique em outra tela.
        # Os mesmos nove COUNT não devem atravessar o Supabase outra vez.
        segundo = fab_counts(self.pedido(self.gestor))
        with self.assertNumQueries(0):
            self.assertEqual(modelo.render(Context(segundo)), "1 1")
