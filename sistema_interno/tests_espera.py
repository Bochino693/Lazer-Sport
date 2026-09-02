"""Esperar não pode virar erro, e voltar depois tem de ser rápido.

O QUE ACONTECIA. A hospedagem desliga a instância depois de alguns
minutos sem nenhuma requisição. O painel tem um pulso -- a central de
avisos pergunta de 30 em 30 segundos --, mas ele só bate com a ABA
VISÍVEL. Painel aberto numa aba de fundo, ou com a tela bloqueada, é
painel sem pulso: a instância dorme.

Aí a pessoa volta, clica em "Salvar", e é esse clique que paga a conta de
acordar processo web e conexão de banco. São dezenas de segundos.
Passando de 90, o gunicorn mata o worker e o que volta é 502.
"""

from pathlib import Path

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings

RAIZ = Path(__file__).resolve().parent


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class DespertarTests(TestCase):

    def test_pronto_acorda_processo_e_banco(self):
        """Acordar só o processo trocaria espera longa por espera média.

        O primeiro clique de quem volta ao painel vai consultar o banco, e
        abrir conexão nova com o Supabase custa segundos. Por isso este
        endereço toca o banco, ao contrário do `healthz`.
        """
        with self.assertNumQueries(1):
            resposta = self.client.get("/pronto/", HTTP_HOST="testserver")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {"ok": True, "banco": True})

    def test_pronto_responde_sem_login(self):
        """Ele é chamado justamente quando a sessão pode ter caído."""
        resposta = self.client.get("/pronto/", HTTP_HOST="testserver")
        self.assertEqual(resposta.status_code, 200)

    def test_o_healthz_da_hospedagem_continua_sem_tocar_no_banco(self):
        """Se ele dependesse do banco, uma oscilação derrubaria o processo.

        E um processo derrubado não volta mais rápido por isso -- volta
        mais devagar, porque precisa subir tudo de novo.
        """
        with self.assertNumQueries(0):
            resposta = self.client.get("/healthz/", HTTP_HOST="testserver")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.content, b"ok")

    def test_a_equipe_logada_tambem_alcanca(self):
        User.objects.create_superuser("espera", "e@e.com", "x")
        self.client.login(username="espera", password="x")
        self.assertEqual(
            self.client.get("/pronto/", HTTP_HOST="testserver").status_code, 200,
        )


class AcordarAntesDeAgirTests(SimpleTestCase):
    """O POST espera o servidor acordar, em vez de falhar contra ele."""

    @staticmethod
    def painel():
        return (RAIZ / "static" / "interno" / "painel.js").read_text(encoding="utf-8")

    def test_o_post_nunca_e_repetido_as_cegas(self):
        """Ele pode ter chegado e sido gravado; só a resposta se perdeu.

        Repetir criaria a segunda proposta, o segundo pagamento. Quem
        repete é o GET de acordar, que é seguro repetir.
        """
        painel = self.painel()

        self.assertIn("POST único", painel)
        self.assertIn("Painel.rede.post(destino", painel)

        pulso = painel[painel.index("function pulsoDoServidor("):]
        pulso = pulso[:pulso.index("function acordarServidor(")]
        self.assertIn('method: "GET"', pulso)
        # A repetição carrega junto quem tem direito de falar na tela:
        # aquecimento por precaução é mudo, gravação anuncia.
        self.assertIn("pulsoDoServidor(tentativa + 1, anunciar)", pulso)

    def test_acorda_o_banco_e_nao_so_o_processo(self):
        """Acordar só o processo troca uma espera longa por uma média.

        O primeiro clique de quem volta ao painel vai consultar o banco,
        e abrir conexão nova com o Supabase custa segundos.
        """
        self.assertIn('fetch("/pronto/?painel=1"', self.painel())

    def test_get_recente_elimina_despertar_redundante_antes_do_post(self):
        painel = self.painel()
        navegacao = (
            RAIZ / "static" / "interno" / "ls-soft-navigation.js"
        ).read_text(encoding="utf-8")

        self.assertIn("marcarSucesso: function ()", painel)
        self.assertIn("Painel.rede.marcarSucesso();", painel)
        self.assertIn("window.Painel.rede.marcarSucesso();", navegacao)

    def test_a_espera_cabe_numa_partida_a_frio(self):
        """Eram ~2 segundos: o bastante para uma oscilação de rede, e
        muito pouco para o caso que motivou tudo isto.

        Uma instância suspensa leva de vinte a sessenta segundos para
        voltar. Desistindo aos dois, o painel decidia que o servidor não
        vinha justamente enquanto ele estava subindo.
        """
        painel = self.painel()

        # UMA SONDAGEM CURTA, DEPOIS UMA ESPERA LONGA.
        #
        # A duração total já cabia numa partida a frio; o formato é que
        # não. Sete tentativas curtas contra uma instância que está
        # subindo são sete `abort`, e cada um joga fora o pedido que já
        # estava na fila -- a resposta que vinha no segundo 40 nunca
        # chegava. Uma sondagem de 6s separa "rede lenta" de "servidor
        # fora"; a espera de 50s cobre a volta inteira num pedido só.
        self.assertIn("var PRAZOS_DO_PULSO = [6000, 50000];", painel)
        self.assertGreaterEqual(max(6000, 50000), 40000)

    def test_desistir_de_acordar_nao_barra_a_gravacao(self):
        """O POST é único e independente do GET de aquecimento."""
        painel = self.painel()
        post = painel[painel.index("post: function (destino, opcoes)"):]
        post = post[:post.index("/* Mantém a instância pronta")]

        self.assertNotIn("acordarServidor(", post)
        self.assertEqual(post.count("fetch(destino, opcoes)"), 1)
        self.assertNotIn("Nada foi enviado", post)

    def test_a_espera_avisa_em_vez_de_ficar_muda(self):
        """Quarenta segundos de tela parada parecem sistema travado.

        A duração da espera não era o defeito -- ela cobre uma partida a
        frio de propósito. O defeito era o silêncio: quem estava olhando
        não tinha como distinguir "o servidor está voltando" de "isto
        aqui não funciona mais", e tocava de novo, pondo outra requisição
        na fila de um servidor que já estava lento.
        """
        painel = self.painel()

        self.assertIn("Painel.aoEsperarRede = function", painel)
        self.assertIn('avisarEspera("acordando", tentativa)', painel)
        self.assertIn('textoOcupado = "Servidor acordando…"', painel)

    def test_gravar_mostra_o_ciclo_inteiro_e_confirma_no_fim(self):
        """Salvar e depois rebuscar a lista é UMA espera, para quem olha.

        A janela fechava assim que o POST voltava e a atualização
        acontecia em silêncio: a tela antiga continuava na frente, com os
        dados antigos. Parecia que nada tinha sido salvo -- e no celular,
        onde a barra de 3px do topo some no recorte da tela, não havia
        nenhum outro sinal.
        """
        painel = self.painel()
        navegacao = (
            RAIZ / "static" / "interno" / "ls-soft-navigation.js"
        ).read_text(encoding="utf-8")

        self.assertIn("Painel.ocupado = function", painel)
        self.assertIn("Painel.pronto = function", painel)
        self.assertIn("Painel.aviso = function", painel)
        self.assertIn('textoOcupado = "Atualizando a lista…"', painel)

        # A tarja só sai quando a lista nova chega -- e para isso a
        # navegação precisa devolver promessa.
        self.assertIn("atualizacao.then(encerrar, encerrar)", painel)
        self.assertIn("return navegar(window.location.href", navegacao)
        self.assertIn("return buscar(alvo, false, soAsPartes).then(", navegacao)

    def test_o_pulso_so_bate_com_a_aba_visivel(self):
        """Aba escondida não gera tráfego; ao voltar, acorda na hora."""
        painel = self.painel()
        self.assertIn('if (document.visibilityState === "visible") acordarServidor(true)', painel)
        self.assertIn('document.addEventListener("visibilitychange"', painel)
