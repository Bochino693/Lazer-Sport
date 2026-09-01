"""Por onde a conversa do WhatsApp abre, e por quê.

ERA UMA APOSTA, E ELA FALHAVA EM SILÊNCIO. No computador o painel chamava
o esquema `whatsapp://`, contando com o aplicativo instalado. O problema
está na natureza desse esquema: se o aplicativo NÃO existe, o navegador
não avisa nada -- não dá erro, não abre janela, não acontece nada. Quem
clicava ficava olhando a tela esperando uma conversa que nunca ia abrir.

E a aposta é ruim justamente na máquina onde mais importa: no computador
da empresa quem atende já está com o WhatsApp Web logado na aba ao lado.
"""

import re
from pathlib import Path

from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parent


class CaminhoDoWhatsappTests(SimpleTestCase):

    @staticmethod
    def painel():
        return (RAIZ / "static" / "interno" / "painel.js").read_text(encoding="utf-8")

    def test_o_computador_abre_o_whatsapp_web_daquele_navegador(self):
        """E não `wa.me`, que no computador ainda pergunta antes.

        `wa.me` mostra uma página intermediária oferecendo o aplicativo --
        mais um clique entre quem atende e o cliente. `web.whatsapp.com/
        send` cai direto na conversa da sessão já aberta.
        """
        painel = self.painel()

        self.assertIn("https://web.whatsapp.com/send?phone=", painel)
        # E é ele que o caminho padrão do computador usa.
        self.assertIn("var alvo = this.navegador(telefone, mensagem);", painel)

    def test_o_aplicativo_instalado_virou_escolha_e_nao_padrao(self):
        """Ele só é chamado quando alguém disse que o tem."""
        painel = self.painel()

        self.assertIn(
            'if (preferenciaDoComputador() === "aplicativo") {', painel,
        )
        # O esquema continua existindo -- só deixou de ser o palpite.
        self.assertIn('"whatsapp://send?phone="', painel)

    def test_a_escolha_e_do_computador_e_sobrevive_a_falta_de_armazenamento(self):
        """Preferência de conforto não pode derrubar um envio.

        `localStorage` lança em janela anônima e com cookies bloqueados.
        Qualquer falha volta ao padrão em vez de estourar no meio do
        clique que manda a proposta ao cliente.
        """
        painel = self.painel()

        self.assertIn('var CHAVE_PREFERENCIA = "ls:whatsapp:computador";', painel)
        trecho = painel[painel.index("function preferenciaDoComputador()"):]
        trecho = trecho[:trecho.index("Painel.whatsapp = {")]
        self.assertEqual(trecho.count("try {"), 2)
        self.assertIn('return "web";', trecho)

    def test_o_celular_nao_mudou(self):
        """`wa.me` já leva ao aplicativo, e é o caminho que o WhatsApp indica."""
        painel = self.painel()
        trecho = painel[painel.index("if (noCelular()) {"):]
        trecho = trecho[:trecho.index("NO COMPUTADOR")]
        self.assertIn("window.open(web,", trecho)

    def test_as_duas_telas_oferecem_a_troca(self):
        """A proposta e a O.S. mandam pelo mesmo caminho, então perguntam igual."""
        for nome, campo in (
            ("orcamentos_inner.html", "whatsapp_por"),
            ("ordens_servico_inner.html", "whatsapp_por_os"),
        ):
            with self.subTest(tela=nome):
                tela = (RAIZ / "templates" / nome).read_text(encoding="utf-8")
                self.assertIn('name="%s" value="web" checked' % campo, tela)
                self.assertIn('name="%s" value="aplicativo"' % campo, tela)
                # E só no computador: no celular não há escolha a fazer.
                self.assertIn("Painel.whatsapp.noCelular()", tela)

    def test_nenhuma_tela_promete_mais_o_aplicativo_como_padrao(self):
        """O texto que explicava a aposta antiga não pode ficar para trás."""
        for nome in ("orcamentos_inner.html", "ordens_servico_inner.html"):
            with self.subTest(tela=nome):
                tela = (RAIZ / "templates" / nome).read_text(encoding="utf-8")
                sem_comentario = re.sub(
                    r"{% comment %}.*?{% endcomment %}", "", tela, flags=re.S,
                )
                self.assertNotIn(
                    "quem abre é o APLICATIVO INSTALADO", sem_comentario,
                )
