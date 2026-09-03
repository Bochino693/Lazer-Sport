"""A memória do sino: o que ele já anunciou para cada pessoa.

O sino balançava quando um aviso crescia com o painel ABERTO. Quem
fechava o sistema com dez pendências e voltava no dia seguinte com onze
não via nada -- a aba nova começava do zero e engolia justamente a
movimentação que aconteceu enquanto a pessoa não estava.

Estes testes cobram a peça de servidor que resolve isso: uma memória por
CONTA, guardada no banco, do que já foi anunciado. É ela que atravessa
o logout, o F5, o fim de semana e a troca de computador.
"""

import json

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from . import avisos as mod
from .models import AtividadeOrcamento, EstadoNotificacao, Orcamento


class MemoriaDoSinoTests(TestCase):
    """As funções, sem passar pela tela."""

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_superuser("ana", "ana@example.com", "x")
        self.bruno = User.objects.create_superuser("bruno", "bruno@example.com", "x")

    def test_conta_nova_nao_lembra_de_nada(self):
        self.assertEqual(mod.avisos_ja_vistos(self.ana), {})

    def test_o_que_foi_guardado_volta_igual(self):
        mod.guardar_avisos_vistos(self.ana, {"orcamentos_atividade": 10, "estoque_critico": 3})
        self.assertEqual(
            mod.avisos_ja_vistos(self.ana),
            {"orcamentos_atividade": 10, "estoque_critico": 3},
        )

    def test_a_memoria_e_de_cada_um(self):
        """Dois no mesmo tablet não herdam o sino um do outro."""
        mod.guardar_avisos_vistos(self.ana, {"orcamentos_atividade": 10})
        self.assertEqual(mod.avisos_ja_vistos(self.bruno), {})

    def test_aviso_resolvido_sai_da_memoria(self):
        """Senão o mesmo problema, ao voltar com o número antigo, entraria calado."""
        mod.guardar_avisos_vistos(self.ana, {"estoque_critico": 4})
        mod.guardar_avisos_vistos(self.ana, {"orcamentos_atividade": 1})
        self.assertEqual(mod.avisos_ja_vistos(self.ana), {"orcamentos_atividade": 1})

    def test_zero_nao_vira_linha(self):
        mod.guardar_avisos_vistos(self.ana, {"estoque_critico": 0})
        self.assertEqual(mod.avisos_ja_vistos(self.ana), {})

    def test_a_leitura_de_atividades_continua_intacta(self):
        """As duas memórias moram na mesma tabela e não podem se atropelar."""
        mod.guardar_avisos_vistos(self.ana, {"orcamentos_atividade": 10})
        EstadoNotificacao.objects.update_or_create(
            usuario=self.ana,
            chave=mod.CHAVE_ATIVIDADE_LIDA,
            defaults={"quantidade": 77},
        )
        mod.guardar_avisos_vistos(self.ana, {"orcamentos_atividade": 11})
        self.assertTrue(
            EstadoNotificacao.objects.filter(
                usuario=self.ana, chave=mod.CHAVE_ATIVIDADE_LIDA, quantidade=77
            ).exists()
        )

    def test_lixo_enviado_pelo_navegador_nao_entra(self):
        mod.guardar_avisos_vistos(self.ana, {
            "": 5,
            "boa": "muitos",
            "negativa": -3,
            "valida": 2,
        })
        self.assertEqual(mod.avisos_ja_vistos(self.ana), {"valida": 2})

    def test_um_post_forjado_nao_enche_a_tabela(self):
        mod.guardar_avisos_vistos(
            self.ana, {f"inventada{n}": 1 for n in range(200)}
        )
        self.assertLessEqual(
            EstadoNotificacao.objects.filter(
                usuario=self.ana, chave__startswith=mod.PREFIXO_VISTO
            ).count(),
            mod.MAXIMO_DE_VISTOS,
        )


class SinoNaTelaTests(TestCase):
    """O sino existe no HTML -- e não só no JavaScript que fala com ele.

    ESTE TESTE NASCEU DE UM ESTRAGO. Uma edição no grupo de botões do
    topo levou junto o bloco inteiro da central de avisos: o painel subiu
    sem sino nenhum. Nada quebrou, nada deu erro -- `painel.js` procura o
    botão, não acha, e desiste em silêncio, que é exatamente o que ele
    deve fazer nas telas onde o sino não existe. O aviso simplesmente
    deixou de ser dado, e a suíte inteira continuou verde.

    Por isso a lista abaixo é de ganchos, e não de aparência: cada um é
    um ponto em que o JavaScript encosta no HTML. Se algum sumir de novo,
    é aqui que aparece.
    """

    #: id/atributo -> o que deixa de funcionar sem ele.
    GANCHOS = {
        'id="avisosBotao"': "o sino em si: sem ele não há clique nem animação",
        'data-selo="total"': "o número de pendências no canto do sino",
        'id="avisosPainel"': "a lista que abre ao clicar",
        'id="avisosLista"': "onde os avisos são desenhados",
        'data-selo="urgentes-texto"': "o contador de urgentes no topo da lista",
        "data-avisos=": "o endereço que o painel consulta, montado com {% url %}",
    }

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_superuser("ana", "ana@example.com", "x")
        self.client.force_login(self.ana)

    def test_a_casca_do_painel_tem_o_sino_inteiro(self):
        html = self.client.get(
            "/", HTTP_HOST="interno.testserver"
        ).content.decode()
        for gancho, para_que_serve in self.GANCHOS.items():
            self.assertIn(gancho, html, f"Sumiu do painel: {para_que_serve}")

    def test_o_sino_aparece_nas_telas_de_trabalho_tambem(self):
        """Não adianta o sino existir só na home: o dia é passado nas listas."""
        for rota in ("/orcamentos/", "/clientes/", "/estoque/"):
            html = self.client.get(
                rota, HTTP_HOST="interno.testserver"
            ).content.decode()
            self.assertIn('id="avisosBotao"', html, f"Sem sino em {rota}")


class SinoPeloEndpointTests(TestCase):
    """O caminho inteiro, do jeito que o painel usa."""

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_superuser("ana", "ana@example.com", "x")
        self.client.force_login(self.ana)

    def estado(self):
        return self.client.get("/avisos/estado/", HTTP_HOST="interno.testserver").json()

    def confirmar(self, mapa):
        return self.client.post(
            "/avisos/estado/",
            {"acao": "avisos_vistos", "vistos": json.dumps(mapa)},
            HTTP_HOST="interno.testserver",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_o_estado_carrega_o_que_o_sino_ja_anunciou(self):
        self.assertEqual(self.estado()["vistos"], {})
        self.assertEqual(self.confirmar({"orcamentos_atividade": 10}).status_code, 200)
        self.assertEqual(self.estado()["vistos"], {"orcamentos_atividade": 10})

    def test_a_memoria_fica_fora_da_assinatura(self):
        """Confirmar o que foi mostrado não pode custar uma resposta inteira.

        A assinatura é o que decide se a tela redesenha. Se `vistos`
        entrasse nela, cada aviso anunciado geraria um segundo tráfego
        completo para todo mundo, sem uma única contagem diferente
        dentro dele.
        """
        antes = self.estado()
        self.confirmar({"orcamentos_atividade": 10})
        depois = self.estado()
        self.assertEqual(antes["assinatura"], depois["assinatura"])
        self.assertNotEqual(antes["vistos"], depois["vistos"])

    def test_acao_desconhecida_continua_recusada(self):
        resposta = self.client.post(
            "/avisos/estado/",
            {"acao": "apagar_tudo"},
            HTTP_HOST="interno.testserver",
        )
        self.assertEqual(resposta.status_code, 400)

    def test_de_fora_da_equipe_ninguem_grava_memoria(self):
        self.client.force_login(User.objects.create_user("visitante"))
        self.assertEqual(self.confirmar({"orcamentos_atividade": 9}).status_code, 403)

    def test_o_colega_mexe_e_o_sino_de_quem_estava_fora_cresce(self):
        """O caso inteiro, com duas contas de verdade.

        Ana sai do sistema com uma movimentação anunciada. Bruno mexe em
        outro orçamento. Ana volta: o número subiu ACIMA do que o sino já
        lhe mostrou -- e é essa diferença, e só ela, que faz o painel
        balançar o sino na chegada.
        """
        bruno = User.objects.create_superuser("bruno", "bruno@example.com", "x")

        primeiro = Orcamento.objects.create(nome_cliente="Escola Girassol")
        AtividadeOrcamento.registrar(
            primeiro, bruno, AtividadeOrcamento.Tipo.CRIADO,
        )
        # Ana viu esse: o painel dela confirmou o que mostrou.
        cache.clear()
        antes = self.estado()
        vistos = {
            aviso["chave"]: aviso["quantidade"] for aviso in antes["avisos"]
        }
        self.assertEqual(vistos.get("orcamentos_atividade"), 1)
        self.confirmar(vistos)

        # Ana sai. Bruno atribui mais uma movimentação.
        segundo = Orcamento.objects.create(nome_cliente="Creche Pintassilgo")
        AtividadeOrcamento.registrar(
            segundo, bruno, AtividadeOrcamento.Tipo.CRIADO,
        )

        # Ana volta.
        cache.clear()
        depois = self.estado()
        atual = {
            aviso["chave"]: aviso["quantidade"] for aviso in depois["avisos"]
        }
        self.assertEqual(atual["orcamentos_atividade"], 2)
        self.assertEqual(depois["vistos"]["orcamentos_atividade"], 1)
        self.assertGreater(
            atual["orcamentos_atividade"],
            depois["vistos"]["orcamentos_atividade"],
            "é esta diferença que o painel usa para balançar o sino na chegada",
        )

    def test_o_que_a_propria_pessoa_faz_nao_toca_o_sino_dela(self):
        orcamento = Orcamento.objects.create(nome_cliente="Escola Girassol")
        AtividadeOrcamento.registrar(
            orcamento, self.ana, AtividadeOrcamento.Tipo.CRIADO,
        )
        cache.clear()
        chaves = {aviso["chave"] for aviso in self.estado()["avisos"]}
        self.assertNotIn("orcamentos_atividade", chaves)

    def test_o_sino_do_navegador_roda_no_dom(self):
        import shutil
        import subprocess
        from pathlib import Path

        node = shutil.which("node")
        if not node or subprocess.run(
            [node, "-e", "require('jsdom')"], capture_output=True
        ).returncode:
            self.skipTest("jsdom não está disponível em NODE_PATH")
        resultado = subprocess.run(
            [node, str(Path(__file__).parent / "tests_js" / "sino.cjs")],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
