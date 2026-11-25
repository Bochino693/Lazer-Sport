"""As tabelas das avaliações com formato estável (LEIA-ME-V10, seção 139).

O pedido do dono: "as tabelas estão mal formatadas no campo das
avaliações, você deve deixar em qualquer resolução do mesmo tamanho para
nunca quebrar."

O que estes testes protegem (dados SINTÉTICOS):

  * a tela "Avaliação dos setores" abre mesmo quando o avaliador de um
    registro antigo foi removido da equipe (dava erro 500);
  * a tabela do histórico tem colunas de largura fixa (colgroup +
    table-layout:fixed) e o parecer comprido vai inteiro para o balão e
    encurta dentro da célula, em vez de alargar a coluna;
  * o card do setor mostra o parecer sem estourar o card;
  * os selos da "Revisão dos blocos", na lista de orçamentos, não partem
    palavra e têm coluna de largura fixa;
  * as regras da casa: CSS só com as variáveis do tema, folha da tela com
    `data-ls-tela`, sem <select>, alert nem confirm.

A aparência em cada largura (390, 768, 1024, 1366 e 1920 px) foi conferida
no navegador; aqui fica travado o que a faz estável.
"""

import re
from datetime import date
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase

from .models import AvaliacaoSetor

INTERNO = {"HTTP_HOST": "interno.testserver"}
URL = "/equipe/avaliacoes/"
RAIZ = Path(__file__).resolve().parent
PARECER_LONGO = (
    "Equipe entregou as ordens no prazo, mas o retrabalho na costura das lonas subiu; "
    "revisar o gabarito de corte, treinar os dois novos integrantes e acompanhar "
    "semanalmente o indicador de refugo até voltar ao patamar do trimestre anterior."
)
PALAVRA_SEM_ESPACO = "Atendimento_rapido_porem_sem_registro_no_sistema_em_varias_propostas_verificar"


def _sem_comentarios(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


class TelaDaAvaliacaoDosSetoresTests(TestCase):
    def setUp(self):
        self.dono = User.objects.create_superuser("dono-av", "dono-av@exemplo.invalid", "senha-de-teste")
        self.dono.first_name, self.dono.last_name = "Administrador Sintético", "de Teste"
        self.dono.save()
        self.client.force_login(self.dono)

    def abrir(self, periodo="2026-11"):
        return self.client.get(URL, {"periodo": periodo}, **INTERNO)

    def test_abre_quando_o_avaliador_foi_removido(self):
        """O avaliador é SET_NULL: sem ele a tela dava erro 500."""
        AvaliacaoSetor.objects.create(
            setor="vendas", periodo=date(2026, 10, 1), nota=3, observacao="Bom mês.", avaliador=None,
        )
        resposta = self.abrir()
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Conta removida")

    def test_o_historico_mostra_o_nome_do_avaliador_ou_o_usuario(self):
        sem_nome = User.objects.create_superuser("so-usuario-av", "s@exemplo.invalid", "senha-de-teste")
        AvaliacaoSetor.objects.create(setor="vendas", periodo=date(2026, 10, 1), nota=3, avaliador=self.dono)
        AvaliacaoSetor.objects.create(setor="gestao", periodo=date(2026, 10, 1), nota=4, avaliador=sem_nome)
        html = self.abrir().content.decode()
        self.assertIn('title="Administrador Sintético de Teste"', html)
        self.assertIn('title="so-usuario-av"', html)

    def test_a_tabela_tem_colunas_fixas_e_o_parecer_inteiro_no_balao(self):
        AvaliacaoSetor.objects.create(
            setor="producao", periodo=date(2026, 10, 1), nota=2, observacao=PARECER_LONGO, avaliador=self.dono,
        )
        AvaliacaoSetor.objects.create(
            setor="vendas", periodo=date(2026, 10, 1), nota=5, observacao="", avaliador=self.dono,
        )
        html = self.abrir().content.decode()
        self.assertIn('class="ls-table ls-av-tabela"', html)
        # uma <col> por coluna, na ordem do cabeçalho
        self.assertEqual(
            re.findall(r'<col class="ls-av-col-(\w+)">', html),
            ["periodo", "setor", "nota", "parecer", "avaliador"],
        )
        self.assertEqual(html.count("<th scope=\"col\">"), 5)
        # o parecer não é cortado no servidor: vai inteiro, e é o CSS que encurta
        self.assertIn(f'<span class="ls-av-duas-linhas" title="{PARECER_LONGO}">{PARECER_LONGO}</span>', html)
        self.assertIn("Sem parecer", html)
        # a tabela não precisa mais de rolagem lateral por dentro
        historico = html[html.index("ls-av-historico"):]
        self.assertNotIn("table-responsive", historico[:historico.index("</section>")])

    def test_o_card_do_setor_nao_estoura_com_palavra_sem_espaco(self):
        AvaliacaoSetor.objects.create(
            setor="vendas", periodo=date(2026, 11, 1), nota=4, observacao=PALAVRA_SEM_ESPACO, avaliador=self.dono,
        )
        html = self.abrir().content.decode()
        self.assertIn(f'<p class="ls-sector-comment" title="{PALAVRA_SEM_ESPACO}">', html)
        self.assertIn('class="ls-sector-score" aria-label="Nota 4 de 5"><b>4</b><small>/5</small>', html)
        # o setor sem nota também tem o círculo: os cards ficam iguais
        self.assertIn('class="ls-sector-score vazio"', html)
        css = _sem_comentarios((RAIZ / "static" / "interno" / "avaliacao-setores.css").read_text(encoding="utf-8"))
        regra = re.search(r"\.ls-sector-comment\{([^}]*)\}", css).group(1)
        self.assertIn("overflow-wrap:anywhere", regra)
        self.assertIn("-webkit-line-clamp:4", regra)
        self.assertIn("overflow:hidden", regra)

    def test_salvar_continua_funcionando(self):
        resposta = self.client.post(
            URL,
            {"action": "save", "setor": "financeiro", "periodo": "2026-11", "nota": "4", "observacao": PARECER_LONGO},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest", **INTERNO,
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(AvaliacaoSetor.objects.get(setor="financeiro").observacao, PARECER_LONGO)
        self.assertContains(self.abrir(), "Revisar avaliação")


class FolhasDeEstiloDasAvaliacoesTests(TestCase):
    def setUp(self):
        self.css = _sem_comentarios(
            (RAIZ / "static" / "interno" / "avaliacao-setores.css").read_text(encoding="utf-8")
        )
        self.modelo = (RAIZ / "templates" / "avaliacao_setores.html").read_text(encoding="utf-8")
        self.painel = (RAIZ / "static" / "interno" / "interno_modern.css").read_text(encoding="utf-8")

    def test_tabela_de_layout_fixo_com_largura_em_cada_coluna(self):
        self.assertRegex(self.css, r"\.ls-av-historico \.ls-av-tabela\{[^}]*table-layout:fixed")
        for coluna in ("periodo", "setor", "nota", "parecer", "avaliador"):
            with self.subTest(coluna=coluna):
                self.assertRegex(self.css, rf"\.ls-av-col-{coluna}\{{width:[^}}]+\}}")
        # todas as linhas da mesma altura; texto comprido encurta na célula
        self.assertRegex(self.css, r"\.ls-av-historico \.ls-av-tabela tbody td\{height:\d+px")
        self.assertRegex(self.css, r"\.ls-av-corta\{[^}]*text-overflow:ellipsis[^}]*white-space:nowrap")
        self.assertRegex(self.css, r"\.ls-av-duas-linhas\{[^}]*overflow-wrap:anywhere[^}]*-webkit-line-clamp:2")

    def test_no_celular_cada_linha_vira_um_cartao(self):
        celular = self.css[self.css.index("@media (max-width:700px)"):]
        self.assertIn("display:grid", celular)
        self.assertIn('grid-template-areas:"periodo setor nota" "parecer parecer nota" "avaliador avaliador avaliador"', celular)
        self.assertIn("thead{display:none}", celular)

    def test_css_so_com_as_variaveis_do_tema(self):
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", self.css), [])
        self.assertNotIn("rgb(", self.css.replace("rgba(var(", ""))

    def test_a_tela_segue_as_regras_da_casa(self):
        self.assertIn('data-ls-tela="avaliacao-setores"', self.modelo)
        for proibido in ("<select", "alert(", "confirm(", "truncatechars"):
            self.assertNotIn(proibido, self.modelo)
        # comentário {# #} só numa linha
        for linha in self.modelo.splitlines():
            self.assertEqual(linha.count("{#"), linha.count("#}"), linha)

    def test_os_selos_da_revisao_dos_blocos_nao_partem_palavra(self):
        marco = "A REVISÃO DOS BLOCOS NA LISTA DE ORÇAMENTOS, SEM PALAVRA PARTIDA"
        self.assertIn(marco, self.painel)
        # seção nova no fim, depois da "LISTA OU CARDS, SEGUNDA PARTE"
        self.assertGreater(
            self.painel.index(marco),
            self.painel.index("LISTA OU CARDS, SEGUNDA PARTE — a barra de ações"),
        )
        secao = _sem_comentarios(self.painel[self.painel.index(marco):])
        self.assertRegex(
            secao,
            r"\.ls-review-label,\s*\.ls-review-item strong\{[^}]*text-overflow:ellipsis[^}]*white-space:nowrap[^}]*overflow-wrap:normal",
        )
        self.assertRegex(secao, r'th\[data-coluna="Revisão dos blocos"\][^{]*\{\s*width:148px!important')
        self.assertIn("@media (min-width:1200px)", secao)
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", secao), [])
