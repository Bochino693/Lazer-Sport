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

        self.assertIn('var pronto = conexao.ocioso()', painel)
        self.assertIn("? conexao.despertar()", painel)
        # E a repetição mora no despertar, não no envio.
        despertar = painel[painel.index("despertar: function ()"):]
        despertar = despertar[:despertar.index("Painel.conexao = conexao;")]
        self.assertIn("global.setTimeout(tentar, eu.esperas[passo++])", despertar)
        self.assertIn('method: "GET"', despertar)

    def test_desistir_de_acordar_nao_barra_a_acao(self):
        """Barrar transformaria uma espera em uma parede.

        Se nem depois de tudo o servidor respondeu, o envio sai assim
        mesmo: pode ser que só o endereço de acordar esteja indisponível.
        """
        painel = self.painel()
        despertar = painel[painel.index("despertar: function ()"):]
        despertar = despertar[:despertar.index("Painel.conexao = conexao;")]

        # Todos os caminhos resolvem; nenhum rejeita.
        self.assertIn("resolver(false)", despertar)
        self.assertNotIn("rejeitar", despertar)

    def test_a_espera_cresce_e_para_de_crescer(self):
        """Martelar um servidor que está subindo o faz subir mais devagar.

        E esperar para sempre é pior que falhar: o teto existe para a
        soma caber na paciência de quem está na tela.
        """
        painel = self.painel()
        self.assertIn("esperas: [800, 1800, 3500, 6000, 9000, 12000, 12000, 12000]", painel)

    def test_o_pulso_da_central_conta_como_contato(self):
        """Sem isto, um painel em uso acordaria à toa a cada envio."""
        self.assertIn(
            "conexao.registrar();\n        return resposta.json();", self.painel(),
        )

    def test_voltar_para_a_aba_acorda_antes_do_clique(self):
        """Assim a espera acontece enquanto a pessoa ainda lê a tela."""
        painel = self.painel()
        self.assertIn(
            'if (document.visibilityState === "visible" && conexao.ocioso()) {',
            painel,
        )

    def test_o_botao_diz_reconectando_e_nao_salvando(self):
        """"Salvando..." por trinta segundos parece travado, e quem está
        na tela clica de novo."""
        self.assertIn(
            'travar(true, Painel.conexao.ocioso() ? "Reconectando..." : null);',
            self.painel(),
        )
