"""O trabalho pela metade não se perde ao fechar a janela.

O DEFEITO. Montar um orçamento leva minutos: cliente, itens, desconto
combinado no telefone, observação de entrega. Um toque fora da janela
fechava tudo e não deixava nada para trás -- `form.reset()` na abertura
seguinte apagava o resto. No celular era pior: sair do painel por um
instante (a galeria, uma ligação) punha a aba em segundo plano, e a volta
encontrava a janela fechada e a gravação falhando contra uma instância
que tinha adormecido.

O QUE PASSOU A VALER:

  * as janelas de montagem não fecham mais por clique fora
    (`data-bs-backdrop="static"`);
  * fechar de verdade guarda o que estava dentro e põe um botão
    flutuante na lateral direita -- um por rascunho, então um orçamento
    e uma O.S. pendurados ao mesmo tempo são dois botões;
  * o botão devolve a janela inteira, inclusive a partir de outra tela;
  * gravar apaga o rascunho correspondente.

O comportamento vive no navegador, então a prova de verdade é a do DOM,
em `tests_js/rascunhos.cjs`. O que se confere daqui é o que o servidor
entrega: a folha, o módulo e os atributos de proteção nas janelas.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

RAIZ = Path(__file__).resolve().parent


class ProtecaoDasJanelasTests(TestCase):
    """O clique fora deixou de custar o trabalho de dez minutos."""

    #: Janelas onde se DIGITA. Uma janela de confirmação não entra aqui:
    #: ali o clique fora é a saída certa.
    JANELAS = {
        "/orcamentos/": (
            "modalOrcamento", "modalBrinquedoNovo", "modalPecaNova", "modalClienteNovo",
        ),
        "/ordens-servico/": ("modalOS",),
    }

    def setUp(self):
        cache.clear()
        self.gestor = User.objects.create_superuser("gestor-rascunho", "g@example.com", "x")
        self.client.force_login(self.gestor)

    def html(self, rota):
        resposta = self.client.get(rota, HTTP_HOST="interno.testserver")
        self.assertEqual(resposta.status_code, 200, rota)
        return resposta.content.decode()

    def test_as_janelas_de_montagem_nao_fecham_por_clique_fora(self):
        for rota, janelas in self.JANELAS.items():
            corpo = self.html(rota)
            for janela in janelas:
                self.assertIn(
                    'id="%s" tabindex="-1" data-bs-backdrop="static"' % janela,
                    corpo,
                    "%s: %s ainda fecha no clique fora e leva o que foi "
                    "digitado junto" % (rota, janela),
                )

    def test_a_camada_filha_da_os_tambem_para_de_fechar_no_clique_ao_lado(self):
        """As camadas da O.S. não são modais do Bootstrap: a regra é do script."""
        script = (RAIZ / "templates" / "ordens_servico_inner.html").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("if(evento.target===camada)fecharFilhoOS", script)

    def test_o_modulo_de_rascunhos_chega_em_toda_tela_do_painel(self):
        """O botão flutuante precisa existir DEPOIS de sair da tela que o criou."""
        for rota in ("/orcamentos/", "/ordens-servico/", "/clientes/", "/estoque/"):
            self.assertIn("interno/ls-rascunhos.js", self.html(rota), rota)

    def test_as_duas_telas_de_montagem_se_inscrevem_no_guardador(self):
        for rota, tipo in (("/orcamentos/", "orcamento"),
                           ("/ordens-servico/", "ordem_servico")):
            corpo = self.html(rota)
            self.assertIn("LSRascunhos.registrar", corpo, rota)
            self.assertIn('tipo:"%s"' % tipo, corpo.replace('tipo: "', 'tipo:"'), rota)

    def test_sair_da_conta_limpa_os_rascunhos_da_aba(self):
        """No tablet do galpão a aba é a mesma para todo mundo."""
        resposta = self.client.post("/logout/inner/", HTTP_HOST="interno.testserver", follow=True)
        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.content.decode()
        self.assertIn('indexOf("ls:rascunho:") === 0', corpo)
        self.assertIn("sessionStorage.removeItem", corpo)

    def test_a_folha_do_painel_desenha_os_botoes_flutuantes(self):
        css = (RAIZ / "static" / "interno" / "interno_modern.css").read_text(
            encoding="utf-8"
        )
        self.assertIn(".ls-rascunhos{", css)
        # Com uma janela aberta os botões sairiam por cima dela.
        self.assertIn("body.modal-open .ls-rascunhos{display:none!important}", css)


class GravacaoEsperaOServidorAcordarTests(TestCase):
    """A volta do segundo plano não pode custar a gravação.

    Aba escondida não gera pulso e o processo da hospedagem dorme. O POST
    que chega primeiro depois da volta é justamente o que carrega o
    trabalho inteiro -- e levava "não foi possível salvar" de uma
    instância que estava subindo. Agora, e SÓ quando há motivo (um
    aquecimento em andamento ou a rede parada há mais de dois minutos), a
    gravação espera o GET de aquecimento, que pode repetir à vontade. O
    POST continua saindo uma vez só.
    """

    def painel(self):
        return (RAIZ / "static" / "interno" / "painel.js").read_text(encoding="utf-8")

    def test_o_post_espera_o_aquecimento_quando_ha_motivo(self):
        texto = self.painel()
        self.assertIn("var precisaAcordar = Boolean(redeAcordando)", texto)
        self.assertIn("Date.now() - redeUltimoSucesso >= REDE_OCIOSA_MS", texto)

    def test_o_aquecimento_que_falha_nao_impede_a_gravacao(self):
        self.assertIn(
            'acordarServidor(false, true).catch(function () { return false; })',
            self.painel(),
        )

    def test_a_gravacao_avisa_quem_guarda_rascunho(self):
        self.assertIn('new CustomEvent("ls:gravado"', self.painel())

    def test_a_queda_de_rede_e_explicada_em_portugues(self):
        """"Failed to fetch" não diz o que houve nem o que fazer."""
        texto = self.painel()
        self.assertIn("A conexão caiu antes de o servidor responder", texto)
        self.assertIn("Nada foi perdido", texto)


class RascunhoNoNavegadorTests(TestCase):
    """O fluxo inteiro, num DOM de verdade.

    Opcional como as outras provas de DOM do painel: sem `jsdom`
    instalado a prova é pulada, e não falsamente aprovada.
    """

    def setUp(self):
        cache.clear()
        self.client.force_login(
            User.objects.create_superuser("gestor-dom", "dom@example.com", "x")
        )

    def test_fluxo_no_dom(self):
        # Uma proposta já gravada na lista: é dela que sai o botão
        # "editar" que o teste usa para provar que gravar uma proposta
        # não apaga o rascunho de OUTRA.
        from decimal import Decimal

        from .models import ItemOrcamento, Orcamento

        proposta = Orcamento.objects.create(nome_cliente="Cliente da lista")
        ItemOrcamento.objects.create(
            orcamento=proposta, descricao="Item da lista",
            quantidade=1, valor_unitario=Decimal("120.00"),
        )

        node = shutil.which("node")
        if not node or subprocess.run(
            [node, "-e", "require('jsdom')"], capture_output=True
        ).returncode:
            self.skipTest("Instale jsdom e configure NODE_PATH para testar o DOM")

        fixture = {}
        for caminho in ("/orcamentos/", "/ordens-servico/"):
            resposta = self.client.get(caminho, HTTP_HOST="interno.testserver")
            self.assertEqual(resposta.status_code, 200, caminho)
            fixture[caminho] = resposta.content.decode()

        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "fixture.json"
            arquivo.write_text(json.dumps(fixture))
            resultado = subprocess.run(
                [node, str(RAIZ / "tests_js" / "rascunhos.cjs"), str(arquivo)],
                capture_output=True, text=True, timeout=60,
            )
        self.assertEqual(
            resultado.returncode, 0, resultado.stdout + resultado.stderr
        )
