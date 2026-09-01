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
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from core.models import Manutencao, Pedido

from . import avisos as mod
from .context_processors import fab_counts
from .permissoes import atribuir_funcoes
from .models import (
    AtividadeOrcamento,
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
            status=Orcamento.Status.AGUARDANDO_RESPOSTA,
            validade=self.hoje - timedelta(days=1),
        )
        Orcamento.objects.create(
            nome_cliente="Ainda dá",
            status=Orcamento.Status.AGUARDANDO_RESPOSTA,
            validade=self.hoje + timedelta(days=2),
        )

        chaves = self.chaves()
        self.assertIn("orcamentos_vencidos", chaves)
        self.assertIn("orcamentos_vencendo", chaves)

    def test_sino_soma_ocorrencias_e_nao_apenas_tipos(self):
        """Três vencidos são três atenções, mesmo ocupando uma linha."""
        for numero in range(3):
            Orcamento.objects.create(
                nome_cliente=f"Vencido {numero}",
                status=Orcamento.Status.AGUARDANDO_RESPOSTA,
                validade=self.hoje - timedelta(days=1),
            )

        from .context_processors import _apurar

        apurado = _apurar(self.gestor)
        self.assertEqual(apurado["total_avisos"], 3)
        self.assertEqual(apurado["avisos_urgentes"], 3)
        self.assertEqual(apurado["count_orcamentos"], 3)

    def test_numero_do_menu_conta_toda_proposta_nao_finalizada(self):
        """Validade distante ou ausente não pode esconder trabalho aberto."""
        estados_em_aberto = (
            Orcamento.Status.RASCUNHO,
            Orcamento.Status.AGUARDANDO_RESPOSTA,
            Orcamento.Status.EM_NEGOCIACAO,
        )
        for indice, status in enumerate(estados_em_aberto):
            Orcamento.objects.create(
                nome_cliente=f"Pendente {indice}",
                status=status,
                # Fora da janela de três dias de cobrança de validade.
                validade=(self.hoje + timedelta(days=30)) if indice else None,
            )

        for status in (
            Orcamento.Status.APROVADO,
            Orcamento.Status.RECUSADO,
            Orcamento.Status.EXPIRADO,
            Orcamento.Status.SUBSTITUIDO,
        ):
            Orcamento.objects.create(
                nome_cliente=f"Finalizado {status}", status=status,
            )

        from .context_processors import _apurar

        apurado = _apurar(self.gestor)
        aviso = next(
            item for item in apurado["avisos"]
            if item.chave == "orcamentos_em_aberto"
        )
        self.assertEqual(aviso.quantidade, 3)
        self.assertEqual(apurado["count_orcamentos"], 3)

    def test_numero_do_menu_conta_so_a_versao_atual(self):
        anterior = Orcamento.objects.create(
            nome_cliente="Cliente com duas versões",
            status=Orcamento.Status.SUBSTITUIDO,
        )
        Orcamento.objects.create(
            nome_cliente="Cliente com duas versões",
            status=Orcamento.Status.RASCUNHO,
            orcamento_anterior=anterior,
            versao=2,
        )

        from .context_processors import _apurar

        self.assertEqual(_apurar(self.gestor)["count_orcamentos"], 1)

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
            status=Orcamento.Status.AGUARDANDO_RESPOSTA,
            validade=self.hoje + timedelta(days=30),
        )
        self.assertNotIn("orcamentos_vencendo", self.chaves())

    def test_resposta_recente_do_cliente_vira_novidade(self):
        orcamento = Orcamento.objects.create(
            nome_cliente="Fulano",
            status=Orcamento.Status.AGUARDANDO_RESPOSTA,
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
            status=Orcamento.Status.AGUARDANDO_RESPOSTA,
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
            status=Orcamento.Status.AGUARDANDO_RESPOSTA,
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
            status=Orcamento.Status.AGUARDANDO_RESPOSTA,
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


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class EstadoAoVivoTests(TestCase):
    """As bolinhas e a situação da proposta se atualizam sem recarregar.

    O painel fica aberto o dia inteiro numa bancada, e a sessão dura o dia
    inteiro junto. Antes, um pedido novo ou um "aprovado" vindo do cliente
    só apareciam depois de sair e entrar de novo -- aviso que chega tarde
    é o mesmo que aviso que não chega.
    """

    URL = "/avisos/estado/"

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="chefe", password="x", email="c@example.com",
        )
        self.client.force_login(self.gestor)

    def pedir(self):
        return self.client.get(self.URL, HTTP_HOST="interno.testserver")

    def test_devolve_as_mesmas_contagens_que_a_tela_desenha(self):
        """Duas fontes para o mesmo número acabam divergindo.

        O HTML e a atualização saem os dois de `avisos.coletar`; este
        teste é o que impede alguém de dar um atalho em um dos dois.
        """
        Orcamento.objects.create(
            nome_cliente="Vencido",
            status=Orcamento.Status.AGUARDANDO_RESPOSTA,
            validade=timezone.localdate() - timedelta(days=2),
        )

        dados = self.pedir().json()
        do_contexto = fab_counts(self._pedido_falso())

        # str() antes de int(): o context processor devolve tudo
        # embrulhado em SimpleLazyObject, para a loja não pagar consulta
        # nenhuma quando o template não pede o valor.
        self.assertEqual(
            dados["contagens"]["count_orcamentos"],
            int(str(do_contexto["count_orcamentos"])),
        )
        self.assertEqual(dados["total"], int(str(do_contexto["total_avisos"])))

    def _pedido_falso(self):
        pedido = RequestFactory().get("/")
        pedido.user = self.gestor
        return pedido

    def test_a_assinatura_muda_quando_o_estado_muda(self):
        """É o que deixa a tela quieta enquanto não há novidade.

        Redesenhar a central a cada 30 segundos faria a lista piscar
        debaixo do dedo de quem está lendo.
        """
        primeira = self.pedir().json()["assinatura"]
        self.assertEqual(self.pedir().json()["assinatura"], primeira)

        Orcamento.objects.create(
            nome_cliente="Novo vencido",
            status=Orcamento.Status.AGUARDANDO_RESPOSTA,
            validade=timezone.localdate() - timedelta(days=1),
        )
        from .context_processors import invalidar_avisos
        invalidar_avisos(self.gestor)

        self.assertNotEqual(self.pedir().json()["assinatura"], primeira)

    def test_atividade_de_outro_usuario_entra_sem_recarregar_a_pagina(self):
        """O id do evento fura o cache curto mesmo entre workers distintos."""
        primeira = self.pedir().json()["assinatura"]
        colega = User.objects.create_superuser(
            username="colega", password="x", email="colega@example.com",
        )
        orcamento = Orcamento.objects.create(
            nome_cliente="Cliente novo",
            responsavel=colega,
        )
        AtividadeOrcamento.registrar(
            orcamento,
            colega,
            AtividadeOrcamento.Tipo.CRIADO,
        )

        dados = self.pedir().json()
        atividade = next(
            aviso for aviso in dados["avisos"]
            if aviso["chave"] == "orcamentos_atividade"
        )
        self.assertNotEqual(dados["assinatura"], primeira)
        self.assertEqual(atividade["quantidade"], 1)
        self.assertEqual(dados["contagens"]["count_orcamentos"], 1)
        self.assertIn("colega", atividade["detalhe"])

    def test_contador_usa_negociacoes_e_nao_versoes_ou_movimentacoes(self):
        """Thiago v1/v2 + Ana v1 + Marcelo v1/v2/v3 = três."""
        colega = User.objects.create_superuser(
            username="colega-versoes", password="x", email="v@example.com",
        )

        def cadeia(nome, quantidade):
            anterior = None
            for versao in range(1, quantidade + 1):
                if anterior:
                    anterior.status = Orcamento.Status.SUBSTITUIDO
                    anterior.save(update_fields=["status"])
                atual = Orcamento.objects.create(
                    nome_cliente=nome,
                    responsavel=colega,
                    orcamento_anterior=anterior,
                    versao=versao,
                )
                AtividadeOrcamento.registrar(
                    atual,
                    colega,
                    (
                        AtividadeOrcamento.Tipo.CRIADO
                        if versao == 1 else AtividadeOrcamento.Tipo.REFEITO
                    ),
                )
                anterior = atual
            # Duas alterações na versão atual continuam sendo uma proposta.
            AtividadeOrcamento.registrar(
                anterior, colega, AtividadeOrcamento.Tipo.ALTERADO,
            )

        cadeia("Thiago", 2)
        cadeia("Ana", 1)
        cadeia("Marcelo", 3)

        dados = self.pedir().json()
        atividade = next(
            aviso for aviso in dados["avisos"]
            if aviso["chave"] == "orcamentos_atividade"
        )
        self.assertEqual(atividade["quantidade"], 3)
        self.assertEqual(dados["contagens"]["count_orcamentos"], 3)
        self.assertEqual(dados["total"], 3)

    def test_mesmo_orcamento_com_dois_motivos_ocupa_uma_bolinha(self):
        colega = User.objects.create_superuser(
            username="colega-motivos", password="x", email="m@example.com",
        )
        orcamento = Orcamento.objects.create(
            nome_cliente="Vencido e alterado",
            responsavel=colega,
            status=Orcamento.Status.AGUARDANDO_RESPOSTA,
            validade=timezone.localdate() - timedelta(days=1),
        )
        AtividadeOrcamento.registrar(
            orcamento, colega, AtividadeOrcamento.Tipo.ALTERADO,
        )

        dados = self.pedir().json()
        self.assertEqual(dados["contagens"]["count_orcamentos"], 1)
        self.assertEqual(dados["total"], 1)
        self.assertTrue(any(
            aviso["chave"] == "orcamentos_vencidos"
            for aviso in dados["avisos"]
        ))
        self.assertTrue(any(
            aviso["chave"] == "orcamentos_atividade"
            for aviso in dados["avisos"]
        ))

    def test_abrir_o_sino_marca_so_as_atividades_como_lidas(self):
        colega = User.objects.create_superuser(
            username="colega2", password="x", email="colega2@example.com",
        )
        orcamento = Orcamento.objects.create(nome_cliente="Leitura")
        AtividadeOrcamento.registrar(
            orcamento,
            colega,
            AtividadeOrcamento.Tipo.ALTERADO,
        )
        self.assertTrue(any(
            aviso["chave"] == "orcamentos_atividade"
            for aviso in self.pedir().json()["avisos"]
        ))

        atividade_ate = self.pedir().json()["atividade_ate"]
        resposta = self.client.post(
            self.URL,
            {"acao": "ler_atividades", "atividade_ate": atividade_ate},
            HTTP_HOST="interno.testserver",
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(any(
            aviso["chave"] == "orcamentos_atividade"
            for aviso in self.pedir().json()["avisos"]
        ))

    def test_clique_no_sino_nao_apaga_evento_que_chegou_depois_do_pulso(self):
        colega = User.objects.create_superuser(
            username="colega-race", password="x", email="race@example.com",
        )
        primeiro = Orcamento.objects.create(nome_cliente="Primeiro")
        AtividadeOrcamento.registrar(
            primeiro, colega, AtividadeOrcamento.Tipo.CRIADO,
        )
        atividade_ate = self.pedir().json()["atividade_ate"]

        segundo = Orcamento.objects.create(nome_cliente="Chegou no clique")
        AtividadeOrcamento.registrar(
            segundo, colega, AtividadeOrcamento.Tipo.CRIADO,
        )
        resposta = self.client.post(
            self.URL,
            {"acao": "ler_atividades", "atividade_ate": atividade_ate},
            HTTP_HOST="interno.testserver",
        )

        self.assertEqual(resposta.status_code, 200)
        atividade = next(
            aviso for aviso in self.pedir().json()["avisos"]
            if aviso["chave"] == "orcamentos_atividade"
        )
        self.assertEqual(atividade["quantidade"], 1)
        self.assertIn("Chegou no clique", atividade["detalhe"])

    def test_o_proprio_usuario_nao_recebe_som_por_sua_acao(self):
        orcamento = Orcamento.objects.create(nome_cliente="Meu trabalho")
        AtividadeOrcamento.registrar(
            orcamento,
            self.gestor,
            AtividadeOrcamento.Tipo.CRIADO,
        )
        self.assertFalse(any(
            aviso["chave"] == "orcamentos_atividade"
            for aviso in self.pedir().json()["avisos"]
        ))

    def test_painel_consulta_rapido_e_tem_toque_de_tres_notas(self):
        from pathlib import Path

        painel = Path("sistema_interno/static/interno/painel.js").read_text(
            encoding="utf-8"
        )
        base = Path("sistema_interno/templates/base_inner.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("intervalo: 12000", painel)
        self.assertIn("659.25", painel)
        self.assertIn("783.99", painel)
        self.assertIn("987.77", painel)
        self.assertIn("lerAtividades", painel)
        self.assertIn("Painel.avisos.lerAtividades()", base)

    def test_sessao_caida_devolve_401_para_a_tela_parar_de_perguntar(self):
        """403 faria o JavaScript insistir contra uma tela de login."""
        self.client.logout()

        self.assertEqual(self.pedir().status_code, 401)

    def test_quem_nao_e_da_equipe_nao_le_o_estado_do_painel(self):
        cliente = User.objects.create_user(username="cliente", password="x")
        self.client.force_login(cliente)

        self.assertEqual(self.pedir().status_code, 403)

    def test_a_resposta_nao_pode_ser_guardada_por_ninguem(self):
        """É pessoal: o painel de um não pode ser servido a outro."""
        self.assertIn("no-store", self.pedir()["Cache-Control"])
