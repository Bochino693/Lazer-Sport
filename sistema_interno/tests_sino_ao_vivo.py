"""O aviso de um usuário chegando na tela do outro, sem recarregar nada.

O CASO QUE ESTE ARQUIVO EXISTE PARA NÃO REPETIR.

Duas contas de gestão abertas ao mesmo tempo. Uma cadastra um cliente
faltando dados. Na outra, que não fez nada, o número do sino não mudava.
Não demorava: não mudava mesmo, até o cache curto vencer -- e o cache era
`LocMemCache`, memória de UM processo, com prazo de 45 segundos. No
servidor há vários workers, cada um com a sua fotografia, então:

  * quem gravou via na hora (a gravação limpava a chave DELE, no worker
    que atendeu);
  * todos os outros -- que são exatamente quem precisa ser avisado --
    ficavam com o número velho por até 45 segundos, e mais o intervalo da
    sondagem em cima disso;
  * e como cada worker tinha o seu prazo, dois pedidos seguidos do mesmo
    navegador podiam trazer números diferentes: era isso que fazia o sino
    marcar 22, depois 19, e voltar para 22 ao ser aberto.

A CORREÇÃO foi trocar o que decide se o guardado ainda vale. Não é mais o
relógio: é um resumo do banco (`pulso.py`), que é o único lugar que todos
os workers enxergam igual, e que muda para TODO MUNDO no instante em que
qualquer pessoa grava qualquer coisa.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from core.models import Manutencao, ClientePerfil

from . import pulso
from .models import Cliente, EstoqueMaterial, Material, Orcamento, OrdemServico


class SinoEntreContasTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_superuser("ana", "ana@example.com", "x")
        self.bruno = User.objects.create_superuser("bruno", "bruno@example.com", "x")
        self.de_bruno = self.client_class()
        self.de_bruno.force_login(self.bruno)

    def bruno_ve(self):
        """O que o painel do Bruno mostraria no próximo pulso da tela."""
        return self.de_bruno.get(
            "/avisos/estado/", HTTP_HOST="interno.testserver",
        ).json()

    # ---------------------------------------------------------------
    def test_cliente_incompleto_de_uma_conta_aparece_na_outra(self):
        """O caso relatado, do jeito que aconteceu."""
        self.assertEqual(self.bruno_ve()["total"], 0)

        Cliente.objects.create(nome_cliente="Festa da Marta", telefone="11999990000")

        depois = self.bruno_ve()
        self.assertEqual(depois["total"], 1)
        self.assertEqual(
            depois["contagens"]["count_clientes_incompletos"], 1,
        )
        self.assertIn(
            "clientes_incompletos",
            {aviso["chave"] for aviso in depois["avisos"]},
        )

    def test_vale_para_toda_fonte_que_o_sino_conta(self):
        """Um aviso novo que dependa de outra tabela precisa entrar em FONTES.

        Sem isso ele nasce mudo para quem não fez a ação -- que é
        exatamente o defeito que estamos consertando, só que numa tela
        diferente e daqui a seis meses.
        """
        perfil, _ = ClientePerfil.objects.get_or_create(user=self.ana)
        material = Material.objects.create(nome_material="Lona PVC")

        casos = {
            "clientes_incompletos": lambda: Cliente.objects.create(
                nome_cliente="Sem documento", telefone="11988887777",
            ),
            "orcamentos_em_aberto": lambda: Orcamento.objects.create(
                nome_cliente="Proposta nova",
                status=Orcamento.Status.AGUARDANDO_RESPOSTA,
            ),
            "ordens_servico": lambda: OrdemServico.objects.create(
                nome_cliente="Chamado", equipamento="Brinquedo",
                status=OrdemServico.Status.ABERTA,
            ),
            "manutencoes": lambda: Manutencao.objects.create(
                usuario=perfil, descricao="Assistência", status="P",
            ),
            "estoque": lambda: EstoqueMaterial.objects.create(
                material=material, quantidade=0, estoque_minimo=5,
                preco_fornecedor=Decimal("10.00"), descricao_local="Prateleira A",
            ),
        }

        vistos = set()
        for chave, criar in casos.items():
            criar()
            vistos = {aviso["chave"] for aviso in self.bruno_ve()["avisos"]}
            self.assertIn(
                chave, vistos,
                f"'{chave}' não chegou ao painel de quem não fez a ação",
            )

    def test_o_numero_nao_anda_para_tras_entre_duas_leituras(self):
        """Dois workers, duas fotografias: era o 22 -> 19 -> 22 do relato.

        Aqui os dois pedidos saem do mesmo processo, então o que se cobra
        é a causa: leituras seguidas, sem nada acontecer no meio, têm de
        devolver o mesmo número e a mesma assinatura.
        """
        Cliente.objects.create(nome_cliente="Cliente A", telefone="11900000001")
        Cliente.objects.create(nome_cliente="Cliente B", telefone="11900000002")

        leituras = [self.bruno_ve() for _ in range(4)]
        totais = {leitura["total"] for leitura in leituras}
        assinaturas = {leitura["assinatura"] for leitura in leituras}
        self.assertEqual(len(totais), 1, f"o número oscilou: {totais}")
        self.assertEqual(len(assinaturas), 1)

    def test_um_pulso_parado_nao_recalcula_a_central(self):
        """O preço de tudo isso: enquanto nada muda, uma consulta curta."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        Cliente.objects.create(nome_cliente="Cliente", telefone="11900000003")
        self.bruno_ve()  # esquenta

        with CaptureQueriesContext(connection) as medida:
            self.bruno_ve()
        # Sessão, usuário e as duas leituras do sino (pulso e último
        # evento). A central inteira -- uma dúzia de consultas -- não é
        # refeita enquanto o banco disser que nada mudou.
        self.assertLessEqual(
            len(medida), 6,
            f"pulso parado ficou caro: {[c['sql'][:60] for c in medida.captured_queries]}",
        )


class PulsoTests(TestCase):
    """O resumo em si, sem passar pela tela."""

    def fresco(self):
        cache.delete(pulso.CHAVE)
        return pulso.agora()

    def test_muda_quando_nasce_altera_e_some(self):
        vazio = self.fresco()

        cliente = Cliente.objects.create(nome_cliente="Novo", telefone="11900000004")
        nasceu = self.fresco()
        self.assertNotEqual(nasceu, vazio, "criar tem de mudar o pulso")

        cliente.nome_cliente = "Novo nome"
        cliente.save()
        alterou = self.fresco()
        self.assertNotEqual(alterou, nasceu, "alterar tem de mudar o pulso")

        cliente.delete()
        # Apagar devolve a contagem ao que era, mas não a data: o resumo
        # leva as duas justamente para o caso de uma delas não bastar.
        self.assertNotEqual(self.fresco(), alterou, "apagar tem de mudar o pulso")

    def test_uma_viagem_ao_banco_para_todas_as_tabelas(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        cache.delete(pulso.CHAVE)
        with CaptureQueriesContext(connection) as medida:
            pulso.agora()
        self.assertEqual(len(medida), 1, "o pulso não pode virar nove consultas")

    def test_a_leitura_seguinte_nao_toca_o_banco(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        cache.delete(pulso.CHAVE)
        pulso.agora()
        with CaptureQueriesContext(connection) as medida:
            pulso.agora()
        self.assertEqual(len(medida), 0)

    def test_gravar_derruba_o_resumo_deste_processo(self):
        """Quem acabou de salvar não espera o prazo de ninguém."""
        cache.delete(pulso.CHAVE)
        pulso.agora()
        self.assertIsNotNone(cache.get(pulso.CHAVE))

        Cliente.objects.create(nome_cliente="Recém-salvo", telefone="11900000005")
        self.assertIsNone(
            cache.get(pulso.CHAVE),
            "o sinal de gravação tem de jogar o resumo fora na hora",
        )

    def test_banco_fora_do_ar_nao_derruba_o_painel(self):
        from unittest.mock import patch

        from django.db import DatabaseError

        cache.delete(pulso.CHAVE)
        with patch.object(pulso, "_ler_do_banco", side_effect=DatabaseError("boom")):
            self.assertEqual(pulso.agora(), "")
