"""A barra do topo e as abas de baixo (LEIA-ME-V10, seção 140).

Os dois pontos que o dono mandou arrumar depois de vistos nos prints:

  * um nome de usuário muito comprido no botão da barra do topo espremia o
    título da tela (81 px em 1366, zero em 1024): o botão tem largura
    máxima e o nome encurta com reticências; o título tem largura mínima;
  * no celular, a aba de baixo que ficava sob o dedo ("Estoque") acendia
    numa tela que não é de nenhuma aba (o :hover preso do toque): a aba só
    acende quando é a tela dela.

A largura de cada peça em cada resolução foi medida no navegador; aqui fica
travado o que a faz estável (dados SINTÉTICOS).
"""

import re
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase

RAIZ = Path(__file__).resolve().parent
INTERNO = {"HTTP_HOST": "interno.testserver"}
NOME_COMPRIDO = ("Administrador Sintético", "de Teste da Fábrica")
MARCO = "A BARRA DO TOPO E AS ABAS DE BAIXO, SEM NADA ESPREMIDO NEM ACESO À TOA"


def _secao():
    css = (RAIZ / "static" / "interno" / "interno_modern.css").read_text(encoding="utf-8")
    return css, re.sub(r"/\*.*?\*/", "", css[css.index(MARCO):], flags=re.S)


class NomeCompridoNaBarraDoTopoTests(TestCase):
    def setUp(self):
        self.dono = User.objects.create_superuser("dono-barra", "d@exemplo.invalid", "senha-de-teste")
        self.dono.first_name, self.dono.last_name = NOME_COMPRIDO
        self.dono.save()
        self.client.force_login(self.dono)

    def test_o_botao_leva_o_nome_inteiro_no_balao(self):
        html = self.client.get("/equipe/avaliacoes/", **INTERNO).content.decode()
        inteiro = " ".join(NOME_COMPRIDO)
        self.assertRegex(
            html,
            rf'<a class="ls-user-pill[^"]*" href="[^"]+" title="{inteiro}" aria-label="Minha conta: {inteiro}">',
        )
        self.assertIn(f"<span>{inteiro}</span>", html)

    def test_sem_nome_o_botao_mostra_o_usuario(self):
        outro = User.objects.create_superuser("so-usuario-barra", "s@exemplo.invalid", "senha-de-teste")
        self.client.force_login(outro)
        html = self.client.get("/equipe/avaliacoes/", **INTERNO).content.decode()
        self.assertIn('title="so-usuario-barra"', html)

    def test_o_botao_tem_largura_maxima_e_reticencias(self):
        _, secao = _secao()
        self.assertRegex(secao, r"\.ls-user-pill\{[^}]*min-width:0[^}]*max-width:\d+px")
        self.assertRegex(
            secao, r"\.ls-user-pill span\{[^}]*overflow:hidden[^}]*text-overflow:ellipsis[^}]*white-space:nowrap",
        )

    def test_o_titulo_tem_largura_minima_e_os_atalhos_nao_encolhem(self):
        _, secao = _secao()
        self.assertRegex(secao, r"\.ls-topbar-copy\{flex:1 1 0;min-width:150px\}")
        self.assertRegex(secao, r"\.ls-atalhos\{flex:0 0 auto\}")
        # no tablet o botão do nome fica só com o ícone e o selo do ambiente sai
        self.assertRegex(secao, r"\.ls-topbar-side>\.ls-ambiente\{display:none\}")
        self.assertRegex(secao, r"\.ls-user-pill span\{display:none\}")

    def test_secao_nova_no_fim_e_so_com_as_variaveis_do_tema(self):
        css, secao = _secao()
        self.assertGreater(css.index(MARCO), css.index("LISTA OU CARDS, SEGUNDA PARTE — a barra de ações"))
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", secao), [])
        self.assertNotIn("rgb(", secao.replace("rgba(var(", ""))


class AbaDeBaixoSoAcendeNaTelaDelaTests(TestCase):
    def setUp(self):
        self.dono = User.objects.create_superuser("dono-abas", "a@exemplo.invalid", "senha-de-teste")
        self.client.force_login(self.dono)

    def acesas(self, caminho):
        html = self.client.get(caminho, **INTERNO).content.decode()
        barra = html[html.index('<nav class="ls-abas"'):]
        barra = barra[:barra.index("</nav>")]
        return re.findall(r'class="ls-aba ativa"[^>]*>\s*<i[^>]*></i><span>([^<]+)</span>', barra)

    def test_telas_que_nao_sao_de_nenhuma_aba_nao_acendem_nenhuma(self):
        for caminho in ("/equipe/avaliacoes/", "/equipe/", "/assinaturas/", "/orcamentos/dados-do-contrato/"):
            with self.subTest(tela=caminho):
                self.assertEqual(self.acesas(caminho), [])

    def test_a_tela_de_uma_aba_acende_so_a_dela(self):
        self.assertEqual(self.acesas("/orcamentos/"), ["Orçamentos"])
        self.assertEqual(self.acesas("/stock/"), ["Estoque"])

    def test_sem_mouse_a_aba_fora_da_tela_fica_na_cor_de_repouso(self):
        _, secao = _secao()
        self.assertRegex(
            secao,
            r"@media \(hover:none\)\{\s*\.ls-abas \.ls-aba:not\(\.ativa\):hover\{color:var\(--muted\)\}\s*\}",
        )
