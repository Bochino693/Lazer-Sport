"""O painel rápido: tetos de idas ao banco nas ações e nas telas (LEIA-ME-V10, seção 120).

POR QUE TETOS. Em produção o banco fica em outra região: cada consulta é
uma viagem de ~170 ms (medido em 11/2026). Uma gravação que fazia 25
consultas e uma tela que fazia 40 eram ~11 s de espera. O que esta seção
cortou (o sino em poucas consultas, as contagens juntas, as listas da janela
no cache do catálogo, a faixa do termo e as funções guardadas, a lista de
técnicos sem uma consulta por conta...) volta sem aviso se ninguém cobrar
-- nada quebra, a tela só fica lenta de novo. Por isso cada teste aqui é um
TETO: quem acrescentar uma consulta a um destes caminhos vai reprovar aqui
e decidir, de olhos abertos, se ela vale 170 ms em cada clique.

Os números contam como o PostgreSQL conta: SAVEPOINT e RELEASE são idas
(cada `atomic()` aninhado são duas), e o BEGIN do SQLite aparece na
captura (no PostgreSQL ele e o COMMIT também são idas). Além de contar,
cada otimização tem aqui o teste de que a RESPOSTA é a mesma de antes.
"""

import json
import os
import select
import socket
import time
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.db import connection
from django.db.models import Count
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from core.models import Brinquedos, Pedido, Venda

from . import avisos
from .models import (
    AvaliacaoBlocoOrcamento,
    Cliente,
    EnderecoCliente,
    EstoqueMaterial,
    ItemOrcamento,
    ItemOrdemServico,
    Material,
    Orcamento,
    OrdemProducao,
    OrdemServico,
    ProdutoInterno,
)
from .permissoes import atribuir_funcoes, nomes_das_funcoes

INTERNO = {"HTTP_HOST": "interno.testserver"}
AJAX = {"HTTP_HOST": "interno.testserver", "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
LISTA = {**AJAX, "HTTP_X_LS_FRAGMENTO": "lista"}


def idas(capturadas):
    """Viagens ao banco como no PostgreSQL: o BEGIN do SQLite conta também o COMMIT."""
    total = 0
    for consulta in capturadas.captured_queries:
        sql = consulta["sql"].strip().upper()
        total += 2 if sql == "BEGIN" else 1
    return total


def povoar(quantos=12, dono=None):
    brinquedo = Brinquedos.objects.create(
        nome_brinquedo="Cama elástica", imagem_brinquedo="imagens_brinquedos/cama.jpg",
        descricao="Cama", valor_brinquedo=Decimal("280.00"), avaliacao=Decimal("5.00"), voltz="110",
    )
    situacoes = [
        Orcamento.Status.AGUARDANDO_RESPOSTA, Orcamento.Status.EM_NEGOCIACAO, Orcamento.Status.APROVADO,
        Orcamento.Status.RECUSADO, Orcamento.Status.RASCUNHO,
    ]
    hoje = timezone.localdate()
    for i in range(quantos):
        cliente = Cliente.objects.create(nome_cliente=f"Cliente {i}", telefone=f"1198888{i:04d}")
        EnderecoCliente.objects.create(cliente=cliente, endereco="Rua A", numero=str(i), cidade="São Paulo")
        orcamento = Orcamento.objects.create(
            cliente=cliente, nome_cliente=cliente.nome_cliente, status=situacoes[i % 5],
            validade=hoje + timedelta(days=(i % 7) - 2), responsavel=dono,
            respondido_em=timezone.now() - timedelta(days=i % 9) if i % 5 in (2, 3) else None,
        )
        ItemOrcamento.objects.create(
            orcamento=orcamento, descricao="Cama", brinquedo=brinquedo, quantidade=1,
            valor_unitario=Decimal("300.00"),
        )
        os_ = OrdemServico.objects.create(cliente=cliente, nome_cliente=cliente.nome_cliente, equipamento="Tobogã")
        ItemOrdemServico.objects.create(
            ordem=os_, tipo=ItemOrdemServico.Tipo.SERVICO, descricao="Reparo", quantidade=1,
            valor_unitario=Decimal("120.00"),
        )
    material = Material.objects.create(nome_material="Lona")
    EstoqueMaterial.objects.create(material=material, descricao_local="Galpão", quantidade=1, estoque_minimo=5,
                                   preco_fornecedor=Decimal("1.00"))
    OrdemProducao.objects.create(produto=ProdutoInterno.objects.create(nome="Máquina"), quantidade=1)
    return brinquedo


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.dono = User.objects.create_superuser("dono", "dono@exemplo.invalid", "x")
        self.gestora = User.objects.create_user("gestora", "gestora@exemplo.invalid", "x")
        atribuir_funcoes(self.gestora, ["gestao", "producao", "financeiro", "vendas"])
        self.brinquedo = povoar(dono=self.dono)
        self.client.force_login(self.dono)

    def medir(self, metodo, rota, dados=None, **cabecalhos):
        cabecalhos = cabecalhos or INTERNO
        with CaptureQueriesContext(connection) as capturadas:
            resposta = getattr(self.client, metodo)(rota, dados or {}, **cabecalhos)
        self.assertLess(resposta.status_code, 400, resposta.content[:300])
        return resposta, idas(capturadas), capturadas

    def teto(self, rota, maximo, metodo="get", dados=None, **cabecalhos):
        resposta, n, capturadas = self.medir(metodo, rota, dados, **cabecalhos)
        self.assertLessEqual(
            n, maximo,
            f"{metodo.upper()} {rota}: {n} idas ao banco (teto {maximo}, ~170 ms cada no ar). "
            "Veja LEIA-ME-V10 §120 antes de subir o teto.\n"
            + "\n".join(q["sql"][:160] for q in capturadas.captured_queries),
        )
        return resposta


# ======================================================================
# O SINO
# ======================================================================
class SinoTests(Base):
    def test_o_sino_depois_de_uma_gravacao_cabe_no_teto(self):
        """Eram 26 consultas (~4,4 s) a cada número novo; agora cabem em 11."""
        cache.clear()
        self.teto("/avisos/estado/", 11, **AJAX)

    def test_o_sino_que_nada_mudou_custa_tres(self):
        """Sessão, conta e o pulso: a versão das movimentações vem carimbada pelo pulso,
        e o 304 não lê a memória do sino (ela só viaja no corpo)."""
        etag = self.client.get("/avisos/estado/", **AJAX)["ETag"]
        cache.delete("interno:pulso:v1")  # o pulso vence (1 s) entre um toque e outro
        resposta = self.teto("/avisos/estado/", 3, HTTP_IF_NONE_MATCH=etag, **AJAX)
        self.assertEqual(resposta.status_code, 304)

    def test_o_corpo_ainda_leva_a_memoria_do_sino(self):
        avisos.guardar_avisos_vistos(self.dono, {"estoque": 1})
        corpo = self.client.get("/avisos/estado/", **AJAX).json()
        self.assertEqual(corpo["vistos"], {"estoque": 1})

    def test_o_sino_nao_cresce_com_os_cadastros(self):
        cache.clear()
        _, poucos, _ = self.medir("get", "/avisos/estado/", **AJAX)
        povoar(30, dono=self.dono)
        cache.clear()
        _, muitos, _ = self.medir("get", "/avisos/estado/", **AJAX)
        self.assertLessEqual(muitos, poucos)

    def test_guardar_o_que_o_sino_mostrou_custa_poucas_idas(self):
        """Era um update_or_create por aviso (~4 idas cada); agora poucas, para qualquer quantidade."""
        mapa = {f"aviso_{i}": i + 1 for i in range(8)}
        self.teto("/avisos/estado/", 9, metodo="post",
                  dados={"acao": "avisos_vistos", "vistos": json.dumps(mapa)}, **AJAX)
        mapa = {f"aviso_{i}": i + 2 for i in range(6)}  # muda seis, tira dois
        self.teto("/avisos/estado/", 9, metodo="post",
                  dados={"acao": "avisos_vistos", "vistos": json.dumps(mapa)}, **AJAX)
        self.assertEqual(avisos.avisos_ja_vistos(self.dono), mapa)


class SinoContaOMesmoTests(Base):
    """As consultas juntaram; os números da central tinham de continuar os mesmos."""

    def test_contar_juntos_da_o_mesmo_que_cada_count(self):
        Pedido.objects.create(status="pago")
        Venda.objects.create(confirmado=False) if hasattr(Venda, "confirmado") else None
        consultas = avisos.consultas_das_contagens(avisos.capacidades(self.dono))
        juntos = avisos.contar_juntos(consultas)
        for nome, consulta in consultas.items():
            with self.subTest(nome=nome):
                self.assertEqual(juntos[nome], consulta.values("pk").distinct().count())
        # e as partes dos clientes incompletos batem com o agregado de antes
        sem_contato, sem_documento, sem_endereco = avisos.partes_incompletas()
        antes = Cliente.objects.filter(ativo=True).aggregate(
            total=Count("pk", filter=avisos.filtro_incompletos(), distinct=True),
            endereco=Count("pk", filter=sem_endereco, distinct=True),
        )
        self.assertEqual(juntos["clientes_total"], antes["total"])
        self.assertEqual(juntos["clientes_endereco"], antes["endereco"])

    def test_as_versoes_de_cada_aviso_sao_as_da_consulta_dele(self):
        """`versoes_dos_avisos` (uma consulta) == `consulta_do_aviso` (a regra), aviso por aviso."""
        # uma negociação refeita: a versão 2 aponta para a 1
        v1 = Orcamento.objects.filter(status=Orcamento.Status.AGUARDANDO_RESPOSTA).first()
        v2 = Orcamento.objects.create(nome_cliente="v2", status=Orcamento.Status.EM_NEGOCIACAO,
                                      orcamento_anterior=v1, validade=timezone.localdate())
        Orcamento.objects.filter(pk=v1.pk).update(status=Orcamento.Status.SUBSTITUIDO)
        hoje, agora = timezone.localdate(), timezone.now()
        for usuario in (self.dono, self.gestora):
            versoes = avisos.versoes_dos_avisos(usuario, hoje, agora)
            for chave in avisos.CHAVES_COMERCIAIS:
                with self.subTest(usuario=usuario.username, chave=chave):
                    esperado = set(avisos.consulta_do_aviso(usuario, chave, hoje, agora).values_list("pk", flat=True))
                    self.assertEqual(set(versoes.por_chave[chave]), esperado)
        mapa = avisos.mapa_de_negociacoes({v2.pk}, pais_conhecidos=versoes.pais)
        self.assertEqual(mapa, avisos.mapa_de_negociacoes({v2.pk}))
        self.assertEqual(mapa[v2.pk], v1.pk)

    def test_a_central_inteira_e_a_mesma_por_qualquer_caminho(self):
        """`coletar` (o caminho junto) == cada função sozinha (o caminho de antes)."""
        for usuario in (self.dono, self.gestora):
            juntos = {a.chave: (a.quantidade, a.detalhe, a.orcamentos) for a in avisos.coletar(usuario)}
            acesso = avisos.capacidades(usuario)
            hoje = timezone.localdate()
            sozinhos = (
                avisos._atividades_orcamento(usuario) + avisos._orcamentos(usuario, hoje)
                + avisos._respostas_de_cliente(usuario, timezone.now()) + avisos._clientes_incompletos()
                + avisos._projetos_3d() + avisos._operacao(acesso) + avisos._estoque()
                + avisos._producao(usuario, True)
            )
            sozinhos = {a.chave: (a.quantidade, a.detalhe, a.orcamentos) for a in sozinhos}
            with self.subTest(usuario=usuario.username):
                self.assertEqual(juntos, sozinhos)


# ======================================================================
# AS TELAS
# ======================================================================
class TelasTests(Base):
    def test_inicio(self):
        """Os nove números do topo numa ida (eram nove COUNT): 23 -> 12 consultas.

        A primeira abertura também monta a central de avisos, a faixa do termo
        e o resumo de pessoas do menu (que ficam no cache); a segunda, não.
        """
        self.teto("/", 21)
        resposta = self.teto("/", 12)
        self.assertEqual(resposta.context["total_orcamentos_abertos"],
                         Orcamento.objects.filter(status__in=Orcamento.EM_ABERTO).count())
        self.assertEqual(resposta.context["total_ordens_servico_abertas"],
                         OrdemServico.objects.filter(status__in=OrdemServico.ABERTAS).count())
        self.assertEqual(resposta.context["total_criticos"], EstoqueMaterial.objects.criticos().count())

    def test_orcamentos_inteira_e_so_a_lista(self):
        self.client.get("/orcamentos/", **INTERNO)  # o cache do catálogo (as listas da janela) enche
        self.teto("/orcamentos/", 15)
        self.teto("/orcamentos/", 13, **LISTA)

    def test_o_total_do_paginador_e_o_do_resumo(self):
        resposta = self.client.get("/orcamentos/", **INTERNO)
        self.assertEqual(resposta.context["page_obj"].paginator.count,
                         Orcamento.objects.exclude(status=Orcamento.Status.SUBSTITUIDO).count())

    def test_ordens_de_servico_nao_paga_por_conta_da_loja(self):
        """A lista de técnicos perguntava as funções de CADA conta ativa -- inclusive dos clientes da loja."""
        _, antes, _ = self.medir("get", "/ordens-servico/")
        User.objects.bulk_create([User(username=f"loja{i}", is_active=True) for i in range(25)])
        resposta, depois, _ = self.medir("get", "/ordens-servico/")
        self.assertLessEqual(depois, antes)
        self.assertLessEqual(depois, 24)
        tecnicos = {u.username for u in resposta.context["tecnicos"]}
        self.assertEqual(tecnicos, {"dono", "gestora"})

    def test_a_regua_do_orcamento(self):
        orcamento = Orcamento.objects.filter(status=Orcamento.Status.APROVADO).first()
        self.teto(f"/orcamentos/{orcamento.pk}/etapas/", 6, **AJAX)

    def test_a_faixa_do_termo_sai_do_cache_e_volta_quando_o_rh_muda(self):
        from rh.apoio_testes import criar_colaborador

        criar_colaborador(1)
        primeira = self.client.get("/estoque/", **INTERNO)
        self.assertContains(primeira, "1 colaborador sem o termo")
        with CaptureQueriesContext(connection) as capturadas:
            self.client.get("/estoque/", **INTERNO)
        self.assertFalse(any("rh_colaborador" in q["sql"] for q in capturadas.captured_queries),
                         "A faixa do termo voltou a consultar o RH em toda tela.")
        criar_colaborador(2)  # uma ficha nova troca a versão: a próxima tela conta de novo
        self.assertContains(self.client.get("/estoque/", **INTERNO), "2 colaboradores sem o termo")


# ======================================================================
# AS AÇÕES
# ======================================================================
class AcoesTests(Base):
    def itens(self, n):
        return json.dumps([
            {"descricao": f"Item {j}", "brinquedo": str(self.brinquedo.pk), "quantidade": "1",
             "valor_unitario": "300,00"}
            for j in range(n)
        ])

    def test_orcamento_novo_editar_e_situacao(self):
        cliente = Cliente.objects.first()
        resposta = self.teto("/orcamentos/", 14, metodo="post", dados={
            "action": "save", "cliente": str(cliente.pk), "nome_cliente": cliente.nome_cliente,
            "contato": "11999990000", "itens": self.itens(3),
        }, **AJAX)
        pk = resposta.json()["id"]
        Orcamento.objects.filter(pk=pk).update(status=Orcamento.Status.RASCUNHO)
        orcamento = Orcamento.objects.get(pk=pk)
        self.teto("/orcamentos/", 18, metodo="post", dados={
            "action": "save", "id": str(pk), "revisao": orcamento.atualizado.isoformat(),
            "cliente": str(cliente.pk), "nome_cliente": cliente.nome_cliente, "contato": "11999990000",
            "itens": self.itens(4),
        }, **AJAX)
        # o bloco reaberto: a mesma linha, de volta a pendente
        blocos = AvaliacaoBlocoOrcamento.objects.filter(orcamento_id=pk)
        self.assertEqual(blocos.count(), 2)
        self.assertTrue(all(b.status == AvaliacaoBlocoOrcamento.Status.PENDENTE for b in blocos))
        self.teto("/orcamentos/", 12, metodo="post",
                  dados={"action": "status", "id": str(pk), "status": "em_negociacao"}, **AJAX)

    def test_reabrir_bloco_sem_update_or_create(self):
        """O bloco avaliado volta a pendente, sem avaliador -- num UPDATE só."""
        from .views_gestao import OrcamentosInnerView

        orcamento = Orcamento.objects.first()
        AvaliacaoBlocoOrcamento.objects.create(
            orcamento=orcamento, bloco=AvaliacaoBlocoOrcamento.Bloco.COMERCIAL,
            status=AvaliacaoBlocoOrcamento.Status.APROVADO, avaliador=self.dono,
            avaliado_em=timezone.now(), observacao="ok",
        )
        with CaptureQueriesContext(connection) as capturadas:
            OrcamentosInnerView._reabrir_bloco(orcamento, AvaliacaoBlocoOrcamento.Bloco.COMERCIAL)
        self.assertEqual(len(capturadas), 1)
        bloco = AvaliacaoBlocoOrcamento.objects.get(orcamento=orcamento, bloco=AvaliacaoBlocoOrcamento.Bloco.COMERCIAL)
        self.assertEqual((bloco.status, bloco.avaliador_id, bloco.avaliado_em, bloco.observacao),
                         (AvaliacaoBlocoOrcamento.Status.PENDENTE, None, None, ""))
        # sem a linha, cria (o caminho de antes)
        OrcamentosInnerView._reabrir_bloco(orcamento, AvaliacaoBlocoOrcamento.Bloco.FINANCEIRO)
        self.assertTrue(AvaliacaoBlocoOrcamento.objects.filter(
            orcamento=orcamento, bloco=AvaliacaoBlocoOrcamento.Bloco.FINANCEIRO).exists())

    def test_excluir_sem_ponto_de_salvamento_inutil(self):
        rascunho = Orcamento.objects.create(nome_cliente="Rascunho", responsavel=self.dono)
        _, n, capturadas = self.medir("post", "/orcamentos/", {
            "action": "delete", "id": str(rascunho.pk), "confirmacao_exclusao": "CONFIRMAR",
        }, **AJAX)
        # Dois: a transação da view (que dentro do TestCase vira SAVEPOINT; no
        # ar é o BEGIN) e a do `Orcamento.delete`, que precisa do dela -- o
        # `remover` pega a ProtectedError e continua. O de `remover` saiu.
        savepoints = [q for q in capturadas.captured_queries if q["sql"].upper().startswith("SAVEPOINT")]
        self.assertLessEqual(len(savepoints), 2, "exclusoes.remover voltou a abrir um SAVEPOINT à toa")
        self.assertFalse(Orcamento.objects.filter(pk=rascunho.pk).exists())

    def test_cliente_salvar_responde_com_o_mesmo(self):
        resposta = self.teto("/clientes/", 18, metodo="post", dados={
            "action": "save", "nome_cliente": "Cliente medido", "telefone": "11988887777",
            "canal_telefone": "whatsapp", "tipo": "residencial", "email": "medido@exemplo.invalid",
            "endereco": "Rua A", "numero": "1", "cidade": "São Paulo", "estado": "SP",
        }, **AJAX)
        corpo = resposta.json()
        cliente = Cliente.objects.get(pk=corpo["id"])
        self.assertEqual(corpo["cliente"]["rotulo"], "Cliente medido")
        self.assertEqual(corpo["cliente"]["endereco"]["rua"], "Rua A")
        self.assertEqual(corpo["mapa_publicado"], cliente.no_mapa)

    def test_salvar_acesso_le_os_grupos_uma_vez(self):
        vendedor = User.objects.create_user("vendedor", "vendedor@exemplo.invalid", "x")
        atribuir_funcoes(vendedor, ["vendas"])
        _, _, capturadas = self.medir("post", "/equipe/", {
            "action": "save", "id": str(vendedor.pk), "username": "vendedor",
            "email": "vendedor@exemplo.invalid", "first_name": "Vendedor", "is_active": "on",
            "funcoes": ["vendas", "ambulante"],
        }, **AJAX)
        leituras = [q for q in capturadas.captured_queries if q["sql"].startswith('SELECT "auth_group"')]
        self.assertLessEqual(len(leituras), 1)
        vendedor = User.objects.get(pk=vendedor.pk)
        self.assertEqual(nomes_das_funcoes(vendedor), {"Equipe · Vendas", "Equipe · Vendedor ambulante"})


# ======================================================================
# AS FUNÇÕES GUARDADAS: mais rápido, e a mesma regra
# ======================================================================
class FuncoesGuardadasTests(TestCase):
    def setUp(self):
        cache.clear()
        self.pessoa = User.objects.create_user("pessoa", "pessoa@exemplo.invalid", "x")
        atribuir_funcoes(self.pessoa, ["vendas"])
        self.client.force_login(self.pessoa)

    def grupos_lidos(self, rota="/orcamentos/"):
        with CaptureQueriesContext(connection) as capturadas:
            resposta = self.client.get(rota, **INTERNO)
        return resposta, [q for q in capturadas.captured_queries if '"auth_group"' in q["sql"]]

    def test_a_segunda_requisicao_nao_pergunta_os_grupos(self):
        self.grupos_lidos()
        _, lidos = self.grupos_lidos()
        self.assertEqual(lidos, [])

    def test_tirar_a_funcao_vale_na_proxima_requisicao(self):
        resposta, _ = self.grupos_lidos()
        self.assertEqual(resposta.status_code, 200)
        atribuir_funcoes(User.objects.get(pk=self.pessoa.pk), ["producao"])
        resposta, _ = self.grupos_lidos()
        self.assertEqual(resposta.status_code, 302, "a função retirada continuou valendo")

    def test_pelo_system_tambem(self):
        """Tirar o grupo por fora da tela de acessos (o /system/, o shell) também vale na hora."""
        self.grupos_lidos()
        Group.objects.get(name="Equipe · Vendas").user_set.remove(self.pessoa)
        resposta, _ = self.grupos_lidos()
        self.assertEqual(resposta.status_code, 302)

    @mock.patch.dict(os.environ, {"WEB_WORKERS": "2"})
    def test_com_dois_workers_sem_cache_compartilhado_nao_guarda(self):
        self.grupos_lidos()
        _, lidos = self.grupos_lidos()
        self.assertTrue(lidos, "com LocMemCache e dois workers a função não pode ficar guardada")


# ======================================================================
# A PROPOSTA SÓ REFAZ A VITRINE QUANDO MEXE NO MAPA
# ======================================================================
class VitrineTests(TestCase):
    def test_editar_item_nao_apaga_o_cache_publico_e_mudar_a_situacao_apaga(self):
        from core.home_cache import ADMIN_CATALOG_VERSION_KEY, versao_do_catalogo

        orcamento = Orcamento.objects.create(nome_cliente="X", status=Orcamento.Status.RASCUNHO)
        orcamento = Orcamento.objects.get(pk=orcamento.pk)
        antes = versao_do_catalogo()
        orcamento.observacoes = "só o texto"
        orcamento.save()
        self.assertEqual(cache.get(ADMIN_CATALOG_VERSION_KEY), antes)
        orcamento.status = Orcamento.Status.AGUARDANDO_RESPOSTA
        orcamento.save()
        self.assertIsNone(cache.get(ADMIN_CATALOG_VERSION_KEY), "a situação mudou e a vitrine não foi refeita")


# ======================================================================
# A SINCRONIA DE ORÇAMENTO DEPOIS DO COMMIT
# ======================================================================
class SincroniaDaMontagemTests(TestCase):
    def test_proposta_fora_da_lista_custa_uma_consulta(self):
        from . import montagem

        orcamento = Orcamento.objects.create(nome_cliente="X", status=Orcamento.Status.EM_NEGOCIACAO)
        with CaptureQueriesContext(connection) as capturadas:
            self.assertIsNone(montagem.sincronizar_orcamento(orcamento.pk))
        self.assertEqual(len(capturadas), 1)


# ======================================================================
# A CONFERÊNCIA DA CONEXÃO (lazer/banco_postgres)
# ======================================================================
class _Info:
    transaction_status = 0


class _ConexaoFalsa:
    """O mínimo do psycopg que a conferência olha, sobre um socket de verdade."""

    def __init__(self, sock):
        self.sock = sock
        self.closed = 0
        self.info = _Info()

    def fileno(self):
        return self.sock.fileno()


@override_settings(DB_CONEXAO_RECENTE_S=30)
class ConferenciaDaConexaoTests(TestCase):
    def setUp(self):
        from lazer.banco_postgres.base import DatabaseWrapper

        self.lado_app, self.lado_banco = socket.socketpair()
        self.addCleanup(self.lado_app.close)
        self.addCleanup(self.lado_banco.close)
        ajustes = dict(connection.settings_dict)
        ajustes.update({"ENGINE": "lazer.banco_postgres", "NAME": "sem-conexao", "CONN_HEALTH_CHECKS": True})
        self.banco = DatabaseWrapper(ajustes)
        self.banco.connection = _ConexaoFalsa(self.lado_app)
        self.banco.health_check_enabled = True
        self.banco.health_check_done = False
        self.conferencias = 0

        def is_usable():
            self.conferencias += 1
            return True

        self.banco.is_usable = is_usable

    def test_usada_agora_e_quieta_dispensa_o_select_1(self):
        self.banco._ls_ultimo_uso = time.monotonic()
        self.banco.close_if_health_check_failed()
        self.assertEqual(self.conferencias, 0)
        self.assertTrue(self.banco.health_check_done)

    def test_o_servidor_fechou_a_conexao_confere(self):
        self.banco._ls_ultimo_uso = time.monotonic()
        self.lado_banco.close()  # o FIN chega: o socket fica legível
        self.banco.close_if_health_check_failed()
        self.assertEqual(self.conferencias, 1)

    def test_chegou_qualquer_coisa_confere(self):
        self.banco._ls_ultimo_uso = time.monotonic()
        self.lado_banco.sendall(b"E")  # a mensagem FATAL de encerramento, por exemplo
        self.banco.close_if_health_check_failed()
        self.assertEqual(self.conferencias, 1)

    def test_parada_mais_que_a_janela_confere(self):
        self.banco._ls_ultimo_uso = time.monotonic() - 31
        self.banco.close_if_health_check_failed()
        self.assertEqual(self.conferencias, 1)

    def test_em_transacao_ou_desconhecida_confere(self):
        self.banco._ls_ultimo_uso = time.monotonic()
        self.banco.connection.info.transaction_status = 2
        self.banco.close_if_health_check_failed()
        self.assertEqual(self.conferencias, 1)

    @override_settings(DB_CONEXAO_RECENTE_S=0)
    def test_janela_zero_e_o_comportamento_antigo(self):
        self.banco._ls_ultimo_uso = time.monotonic()
        self.banco.close_if_health_check_failed()
        self.assertEqual(self.conferencias, 1)

    def test_o_settings_usa_o_backend_no_postgresql(self):
        from pathlib import Path

        texto = (Path(__file__).resolve().parent.parent / "lazer" / "settings.py").read_text(encoding="utf-8")
        self.assertIn('DATABASES["default"]["ENGINE"] = "lazer.banco_postgres"', texto)
        self.assertIn('_CONN_MAX_AGE_PADRAO = "600"', texto)
        self.assertTrue(hasattr(select, "poll") or hasattr(select, "select"))


# ======================================================================
# O NAVEGADOR: a lista não é pedida duas vezes depois de gravar
# ======================================================================
class NavegadorTests(TestCase):
    def ler(self, nome):
        from pathlib import Path

        return (Path(__file__).resolve().parent / "static" / "interno" / nome).read_text(encoding="utf-8")

    def test_a_sincronia_espera_a_tela_que_a_gravacao_ja_pediu(self):
        painel, navegacao, sincronia = self.ler("painel.js"), self.ler("ls-soft-navigation.js"), self.ler("ls-sincronia.js")
        self.assertIn('new CustomEvent("ls:atualizacao-a-caminho")', painel)
        self.assertIn('new CustomEvent("ls:atualizada")', navegacao)
        self.assertIn('"ls:atualizacao-a-caminho"', sincronia)
        self.assertIn('"ls:atualizada"', sincronia)

    def test_a_etapa_da_producao_trava_o_botao_e_nao_recarrega_a_pagina(self):
        from pathlib import Path

        html = (Path(__file__).resolve().parent / "templates" / "producao_ordem_detalhe.html").read_text(encoding="utf-8")
        self.assertIn("LSTela.pronto", html)
        self.assertIn('form.dataset.enviando === "1"', html)
        self.assertIn("LSAtualizarTela", html)
        self.assertNotIn("alert(", html)
        self.assertNotIn("confirm(", html)
