"""As telas não podem fazer uma consulta por linha.

COMO ISTO APARECE NA PRÁTICA. Nunca como erro. A tela abre, mostra tudo
certo, e só fica lenta -- e vai ficando mais lenta conforme a operação
cresce, que é justamente quando ninguém tem tempo de investigar. Numa
página de 25 orçamentos eram 26 idas ao banco só para buscar o endereço
do cliente, uma por linha, sobre dados que o prefetch já tinha trazido.

AS DUAS ARMADILHAS ERAM SUTIS, e as duas têm a mesma cara: um método de
QuerySet que parece inofensivo e que, por baixo, monta uma consulta nova
e joga o cache do prefetch fora.

  * `.first()` vira ORDER BY + LIMIT 1 -- consulta nova.
  * `.select_related(...)` sobre um related manager já prefetchado --
    consulta nova, e ainda por cima repetindo o trabalho já feito.

Um teto de consultas é a única forma de isso não voltar sem ninguém ver:
quem reintroduzir um `.first()` numa propriedade de linha vai reprovar
aqui, e não seis meses depois, num servidor lento.
"""

import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from core.models import PecasReposicao

from .models import (
    Cliente,
    EnderecoCliente,
    EnvioOrdemServico,
    ItemOrcamento,
    ItemOrdemServico,
    Orcamento,
    OrdemServico,
)


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class ConsultasNaoCrescemComAsLinhasTests(TestCase):
    """O teste não é "quantas consultas", é "cresce com o número de linhas".

    Um teto fixo seria um número mágico: some com a tela ganhando um
    cartão novo e reprovaria por motivo errado. O que realmente distingue
    uma tela sã de uma tela doente é o COMPORTAMENTO -- consulta por
    conjunto não muda de quantidade quando chegam mais registros;
    consulta por linha, sim.

    Então cada teste abre a mesma tela duas vezes, com poucos e com
    muitos registros, e exige que a diferença seja perto de zero.
    """

    #: Alguma folga: a paginação e os agregados do topo mudam de plano
    #: quando há mais páginas, e isso pode custar uma consulta a mais.
    FOLGA = 2

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-perf", password="x", email="g@example.com",
        )
        self.client.force_login(self.gestor)

    def povoar(self, quantos, inicio=0):
        """Cada linha com cliente, endereço, item e envio.

        É onde a consulta por linha se esconde: relação que o template
        toca e a view achou que tinha trazido.
        """
        for i in range(inicio, inicio + quantos):
            cliente = Cliente.objects.create(
                nome_cliente=f"Cliente {i}", telefone=f"1199999{i:04d}",
            )
            EnderecoCliente.objects.create(
                cliente=cliente, endereco="Rua das Flores", numero=str(i),
                bairro="Centro", cidade="São Paulo", estado="SP",
            )
            orcamento = Orcamento.objects.create(
                cliente=cliente, nome_cliente=cliente.nome_cliente,
                status=Orcamento.Status.APROVADO,
            )
            ItemOrcamento.objects.create(
                orcamento=orcamento, descricao="Cama elástica",
                quantidade=1, valor_unitario=Decimal("300.00"),
            )
            ordem = OrdemServico.objects.create(
                cliente=cliente, nome_cliente=cliente.nome_cliente,
                equipamento="Tobogã",
            )
            ItemOrdemServico.objects.create(
                ordem=ordem, tipo=ItemOrdemServico.Tipo.SERVICO,
                descricao="Reparo", quantidade=1, valor_unitario=Decimal("120.00"),
            )
            EnvioOrdemServico.objects.create(
                ordem=ordem, canal=EnvioOrdemServico.Canal.EMAIL,
                destino="cliente@example.com", responsavel=self.gestor,
            )

    def consultas_em(self, rota):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as capturadas:
            resposta = self.client.get(rota, HTTP_HOST="interno.testserver")
        self.assertEqual(resposta.status_code, 200)
        return len(capturadas)

    def conferir(self, rota, dica):
        self.povoar(3)
        poucas = self.consultas_em(rota)

        self.povoar(22, inicio=3)          # completa a página de 25
        muitas = self.consultas_em(rota)

        self.assertLessEqual(
            muitas, poucas + self.FOLGA,
            f"{rota}: {poucas} consultas com 3 registros e {muitas} com 25. "
            f"A conta cresce com as linhas, e não deveria. {dica}",
        )

    def test_a_lista_de_orcamentos_nao_consulta_por_linha(self):
        self.conferir(
            "/orcamentos/",
            "Procure um `.first()` numa propriedade que o template toca: "
            "ele monta consulta nova e ignora o prefetch da view.",
        )

    def test_a_lista_de_ordens_de_servico_nao_consulta_por_linha(self):
        self.conferir(
            "/ordens-servico/",
            "O histórico de envios já vem por prefetch; repetir "
            "`select_related` sobre ele joga o cache fora.",
        )

    def test_a_lista_de_clientes_nao_consulta_por_linha(self):
        self.conferir("/clientes/", "Confira endereço, orçamentos e pendências.")

    def test_a_lista_de_pedidos_nao_consulta_por_linha(self):
        self.conferir("/pedidos/inner/", "Confira cliente e itens de cada pedido.")


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class EnderecoPrincipalUsaOPrefetchTests(TestCase):
    """A propriedade que estava custando uma consulta por linha.

    `first()` vira ORDER BY + LIMIT 1 -- consulta nova, mesmo com o
    prefetch pago. `all()[0]` usa o cache. A lista de endereços de um
    cliente tem uma ou duas linhas: indexar isso em memória é de graça.
    """

    def setUp(self):
        for i in range(10):
            cliente = Cliente.objects.create(nome_cliente=f"Cliente {i}")
            EnderecoCliente.objects.create(
                cliente=cliente, endereco="Rua A", cidade="São Paulo",
            )

    def test_com_prefetch_nao_custa_consulta_nenhuma(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        clientes = list(Cliente.objects.prefetch_related("enderecos"))

        with CaptureQueriesContext(connection) as consultas:
            enderecos = [c.endereco_principal for c in clientes]

        self.assertEqual(
            len(consultas), 0,
            "`endereco_principal` voltou a consultar: provavelmente trocaram "
            "`all()[0]` por `first()`.",
        )
        self.assertTrue(all(enderecos))

    def test_sem_prefetch_continua_funcionando(self):
        cliente = Cliente.objects.get(nome_cliente="Cliente 0")

        self.assertIsNotNone(cliente.endereco_principal)

    def test_cliente_sem_endereco_devolve_nada_em_vez_de_estourar(self):
        sozinho = Cliente.objects.create(nome_cliente="Sem endereço")

        self.assertIsNone(sozinho.endereco_principal)


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class GravacoesNaoConsultamCatalogoPorItemTests(TestCase):
    """Salvar vinte linhas não pode fazer vinte viagens ao banco remoto."""

    FOLGA = 2

    def setUp(self):
        self.gestor = User.objects.create_superuser(
            username="gestor-gravacao", password="x", email="save@example.com",
        )
        self.client.force_login(self.gestor)
        self.peca = PecasReposicao.objects.create(
            nome="Bucha de teste", descricao_peca="Reposição",
            preco_venda=Decimal("12.00"), ativo=False,
        )

    def medir(self, rota, dados):
        with CaptureQueriesContext(connection) as consultas:
            resposta = self.client.post(
                rota,
                dados,
                HTTP_HOST="interno.testserver",
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(resposta.status_code, 200, resposta.content)
        return len(consultas)

    def itens_orcamento(self, quantidade):
        return json.dumps([
            {
                "descricao": f"Bucha {indice}",
                "peca": str(self.peca.pk),
                "quantidade": "1",
                "valor_unitario": "12,00",
            }
            for indice in range(quantidade)
        ])

    def itens_os(self, quantidade):
        return json.dumps([
            {
                "tipo": "peca",
                "descricao": f"Bucha {indice}",
                "peca": str(self.peca.pk),
                "quantidade": "1",
                "valor_unitario": "12,00",
            }
            for indice in range(quantidade)
        ])

    def test_orcamento_resolve_catalogo_em_lote(self):
        uma = self.medir("/orcamentos/", {
            "action": "save", "nome_cliente": "Uma linha",
            "itens": self.itens_orcamento(1),
        })
        vinte = self.medir("/orcamentos/", {
            "action": "save", "nome_cliente": "Vinte linhas",
            "itens": self.itens_orcamento(20),
        })

        self.assertLessEqual(vinte, uma + self.FOLGA)

    def test_os_resolve_pecas_em_lote(self):
        base = {
            "action": "save", "tipo": "manutencao",
            "status": "rascunho", "prioridade": "normal",
        }
        uma = self.medir("/ordens-servico/", {
            **base, "equipamento": "Uma linha", "itens": self.itens_os(1),
        })
        vinte = self.medir("/ordens-servico/", {
            **base, "equipamento": "Vinte linhas", "itens": self.itens_os(20),
        })

        self.assertLessEqual(vinte, uma + self.FOLGA)
