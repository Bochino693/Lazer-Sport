"""Os avisos de aplicativo no painel: o recado que virou toast (ou folha).

O PEDIDO, sobre a caixa do Bootstrap "A importação de “CONTRATO OPEN SPICE
SUSHI LOUNGE LTDA.docx” foi descartada." no alto da tela: "este tipo de
mensagem deve virar um modal moderno que aparece estilo app para avisar".

Aqui, com as telas de verdade: o descarte da importação (título amigável,
o arquivo no texto, o botão "Importar outro"), o "voltou para o painel" do
endereço antigo, a exclusão por formulário comum que antes voltava calada,
e o erro de servidor que pede atenção (folha). O sistema em si -- a
convenção do `extra_tags`, o JavaScript e o CSS -- está em
core/tests_ls_aviso.py.
"""

import re
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .models import EstoqueMaterial, Material, MovimentoEstoque
from .permissoes import atribuir_funcoes
from .tests_importacao_word import HOST, _ComUsuario, docx_com_tabela

ARQUIVO = "CONTRATO OPEN SPICE SUSHI LOUNGE LTDA.docx"


def cartoes(html):
    """Os cartões de recado da página, como o ls-aviso.js os lê."""
    bloco = re.search(r'<div class="ls-recados-servidor".*?\n</div>', html, flags=re.S)
    if not bloco:
        return []
    achados = []
    for cartao in re.finditer(r"<div class=\"ls-recado-cartao(.*?)</div>", bloco.group(0), flags=re.S):
        texto = cartao.group(1)
        achados.append({
            "nivel": re.search(r'data-nivel="([^"]*)"', texto).group(1),
            "titulo": re.search(r'data-titulo="([^"]*)"', texto).group(1),
            "icone": re.search(r'data-icone="([^"]*)"', texto).group(1),
            "texto": re.search(r'class="ls-recado-texto">(.*?)</span>', texto, flags=re.S).group(1),
            "modal": "data-modal" in texto,
            "acao": re.findall(r'data-acao-url="([^"]*)" data-acao-rotulo="([^"]*)"', texto),
        })
    return achados


class DescarteDaImportacaoTests(_ComUsuario):

    def descartar(self, para=""):
        url = self.importar(docx_com_tabela(), nome=ARQUIVO, para=para)
        resposta = self.client.post(url, {"action": "descartar"}, **HOST)
        return resposta, self.client.get(resposta["Location"], **HOST)

    def test_o_descarte_vira_toast_com_titulo_e_o_arquivo(self):
        resposta, tela = self.descartar()
        self.assertEqual(resposta["Location"], "/orcamentos/")
        html = tela.content.decode()
        self.assertEqual(cartoes(html), [{
            "nivel": "sucesso",
            "titulo": "Importação descartada",
            "icone": "arquivo-x",
            "texto": "“CONTRATO OPEN SPICE SUSHI LOUNGE LTDA.docx” foi descartado. Nada foi cadastrado.",
            "modal": False,
            "acao": [("/orcamentos/importar/", "Importar outro")],
        }])
        # e nada da caixa de antes, no alto da tela (as caixas de erro dos
        # formulários das janelas continuam: são outra coisa)
        self.assertNotIn("foi descartada.", html)
        topo = html[html.index('<main class="ls-content">'):][:1500]
        self.assertNotIn('class="alert', topo)

    def test_da_aba_clientes_a_acao_volta_para_a_importacao_de_clientes(self):
        resposta, tela = self.descartar(para="cliente")
        self.assertEqual(resposta["Location"], "/clientes/")
        self.assertEqual(cartoes(tela.content.decode())[0]["acao"],
                         [("/orcamentos/importar/?para=cliente", "Importar outro")])

    def test_o_aviso_aparece_uma_vez_so(self):
        _, tela = self.descartar()
        self.assertEqual(len(cartoes(tela.content.decode())), 1)
        de_novo = self.client.get("/orcamentos/", **HOST)
        self.assertEqual(cartoes(de_novo.content.decode()), [])

    def test_a_importacao_expirada_tambem(self):
        resposta = self.client.get("/orcamentos/importar/naoexiste123/", **HOST)
        tela = self.client.get(resposta["Location"], **HOST)
        achado = cartoes(tela.content.decode())
        self.assertEqual([(c["titulo"], c["icone"]) for c in achado], [("Importação expirada", "arquivo")])


class PainelSemCaixaDeAlertaTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.chefe = User.objects.create_superuser("chefe", "chefe@exemplo.com", "senha")

    def setUp(self):
        self.client.force_login(self.chefe)

    def test_o_endereco_antigo_e_um_toast(self):
        html = self.client.get("/orcamentos/?recuperado=pagina", **HOST).content.decode()
        self.assertEqual([(c["nivel"], c["titulo"]) for c in cartoes(html)], [("info", "Endereço antigo")])
        self.assertNotIn("alert alert-info", html)

    def test_a_exclusao_por_formulario_comum_agora_avisa(self):
        """Antes voltava calada para a lista: "não aconteceu nada" parecia "deu certo"."""
        material = Material.objects.create(nome_material="Parafuso M8")
        estoque = EstoqueMaterial.objects.create(
            material=material, descricao_local="Prateleira A3", quantidade=0,
            preco_fornecedor=Decimal("0.50"),
        )
        movimento = MovimentoEstoque.registrar(
            estoque, MovimentoEstoque.Tipo.ENTRADA, 10, valor_unitario=Decimal("0.45"),
        )
        tela_antes = self.client.get("/estoque/movimentacoes/", **HOST).content.decode()
        self.assertIn('data-ls-confirmar-titulo="Excluir esta movimentação?"', tela_antes)
        self.assertNotIn("return confirm(", tela_antes)

        resposta = self.client.post("/estoque/movimentacoes/", {
            "action": "delete_movimento", "movimento_id": movimento.pk,
            "confirmacao_exclusao": "CONFIRMAR",
        }, **HOST)
        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(MovimentoEstoque.objects.filter(pk=movimento.pk).exists())
        achado = cartoes(self.client.get(resposta["Location"], **HOST).content.decode())
        self.assertEqual([(c["nivel"], c["titulo"], c["icone"]) for c in achado],
                         [("sucesso", "Excluída", "lixeira")])

    def test_o_erro_por_formulario_comum_tambem(self):
        """Quem não pode excluir volta para a lista com o motivo, e não calado."""
        producao = User.objects.create_user("producao", "p@exemplo.com", "senha")
        atribuir_funcoes(producao, ["producao"])
        self.client.force_login(producao)
        resposta = self.client.post("/estoque/movimentacoes/", {
            "action": "delete_movimento", "movimento_id": 1, "confirmacao_exclusao": "CONFIRMAR",
        }, **HOST)
        self.assertEqual(resposta.status_code, 302)
        achado = cartoes(self.client.get(resposta["Location"], **HOST).content.decode())
        self.assertEqual([(c["nivel"], c["texto"]) for c in achado],
                         [("erro", "Somente o superusuário pode excluir movimentações.")])

    # O SMTP de verdade, sem a credencial: o caso da hospedagem nova. (O
    # runner de testes troca o EMAIL_BACKEND pelo de memória; aqui volta.)
    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST_USER="", EMAIL_HOST_PASSWORD="",
    )
    def test_o_erro_que_para_o_envio_e_folha(self):
        resposta = self.client.post("/minha-conta/", {"action": "testar_email"}, **HOST)
        achado = cartoes(self.client.get(resposta["Location"], **HOST).content.decode())
        self.assertEqual(len(achado), 1)
        self.assertEqual((achado[0]["nivel"], achado[0]["titulo"], achado[0]["modal"]),
                         ("erro", "E-mail não configurado", True))
        self.assertIn("EMAIL_HOST_USER", achado[0]["texto"])
