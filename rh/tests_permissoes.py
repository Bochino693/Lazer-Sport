"""Quem vê o quê no RH -- entrando nas telas com CADA função do painel.

O pedido: admin e Gestão veem e editam tudo; o Financeiro vê o necessário
para pagar (salário, banco/Pix) sem editar a ficha; Produção, Criação,
Vendas e Ambulante só o próprio (ponto, tarefas, ficha básica) e nunca o
salário dos outros. Documento alheio não abre, nem por URL digitada.
"""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .apoio_testes import (
    INTERNO,
    PastaPrivadaTemporaria,
    criar_colaborador,
    criar_conta,
    pdf_sintetico,
)
from .models import Colaborador, DocumentoColaborador, RegistroRH
from .servicos import guardar_documento
from .arquivos import conferir

TELAS_DA_EQUIPE = ("/rh/colaboradores/", "/rh/ponto/equipe/")
TELAS_DA_GESTAO = ("/rh/colaboradores/novo/", "/rh/documentos/")


class Base(PastaPrivadaTemporaria, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.super = criar_conta("dono", superusuario=True)
        cls.gestora = criar_conta("gestora", "gestao")
        cls.financeiro = criar_conta("financeiro", "financeiro")
        cls.contas = {
            codigo: criar_conta(f"conta-{codigo}", codigo)
            for codigo in ("producao", "criacao", "vendas", "ambulante")
        }
        cls.ana = criar_colaborador(1, usuario=cls.contas["producao"], salario="3456.78")
        cls.bruno = criar_colaborador(2, usuario=cls.contas["vendas"], setor="vendas", cargo="Vendedor",
                                      salario="9876.54")

    def setUp(self):
        super().setUp()
        self.doc_bruno = guardar_documento(
            self.bruno, conferir(SimpleUploadedFile("rg.pdf", pdf_sintetico("RG do Bruno"))),
            tipo="rg_cnh", usuario=self.gestora,
        )

    def abrir(self, conta, rota):
        self.client.force_login(conta)
        return self.client.get(rota, **INTERNO)


class MenuUmaEntradaTests(Base):
    """O RH no menu por função (LEIA-ME-V10, seção 114).

    Cada um acha o PRÓPRIO ponto uma vez só (Minha área); a equipe aparece
    na função de quem cuida dela: Gestão (RH completo) e Financeiro (as
    fichas e o ponto, para pagar). Quem não cuida da equipe não a vê.
    """

    def _menu(self, conta):
        html = self.abrir(conta, "/rh/ponto/").content.decode()
        menu = html[html.index('<nav class="ls-nav"'):]
        return menu[:menu.index("</nav>")]

    def test_o_proprio_ponto_uma_vez_e_a_equipe_so_para_quem_cuida(self):
        for conta in (self.super, self.gestora, self.financeiro, *self.contas.values()):
            with self.subTest(conta=conta.username):
                menu = self._menu(conta)
                self.assertEqual(menu.count('href="/rh/ponto/"'), 1)
                self.assertEqual(menu.count('data-funcao="pessoal"'), 1)
        self.assertEqual(self._menu(self.gestora).count('href="/rh/"'), 1)
        self.assertIn('href="/rh/colaboradores/"', self._menu(self.financeiro))
        self.assertNotIn('href="/rh/"', self._menu(self.financeiro))
        self.assertNotIn('href="/rh/colaboradores/"', self._menu(self.contas["criacao"]))

    def test_rotulo_do_menu_pela_funcao(self):
        self.assertContains(self.abrir(self.gestora, "/rh/"), "RH da equipe")
        self.assertContains(self.abrir(self.financeiro, "/rh/colaboradores/"), "Ponto da equipe")
        self.assertContains(self.abrir(self.contas["criacao"], "/rh/ponto/"), "Meu ponto")


class CadaFuncaoEntraNasTelasTests(Base):
    def test_super_e_gestao_abrem_tudo(self):
        for conta in (self.super, self.gestora):
            for rota in ("/rh/", *TELAS_DA_EQUIPE, *TELAS_DA_GESTAO, "/rh/tarefas/",
                         f"/rh/colaboradores/{self.ana.pk}/", f"/rh/colaboradores/{self.ana.pk}/editar/",
                         f"/rh/ponto/espelho/{self.ana.pk}/", f"/rh/colaboradores/{self.ana.pk}/termo/"):
                with self.subTest(conta=conta.username, rota=rota):
                    self.assertEqual(self.abrir(conta, rota).status_code, 200)

    def test_financeiro_ve_a_equipe_e_o_salario_mas_nao_edita(self):
        lista = self.abrir(self.financeiro, "/rh/colaboradores/")
        self.assertEqual(lista.status_code, 200)
        self.assertContains(lista, "3.456,78")
        ficha = self.abrir(self.financeiro, f"/rh/colaboradores/{self.ana.pk}/")
        self.assertContains(ficha, "3.456,78")
        self.assertNotContains(ficha, "/editar/")
        self.assertNotContains(ficha, 'id="documentos"')
        self.assertNotContains(ficha, "Contato Exemplo")  # endereço/contato não são de pagamento
        for rota in (f"/rh/colaboradores/{self.ana.pk}/editar/", "/rh/colaboradores/novo/", "/rh/documentos/"):
            with self.subTest(rota=rota):
                self.assertEqual(self.abrir(self.financeiro, rota).status_code, 302)
        self.assertEqual(self.abrir(self.financeiro, f"/rh/ponto/espelho/{self.ana.pk}/").status_code, 200)

    def test_financeiro_nao_abre_documento(self):
        resposta = self.abrir(self.financeiro, f"/rh/documentos/{self.doc_bruno.pk}/arquivo/")
        self.assertEqual(resposta.status_code, 404)

    def test_demais_funcoes_so_o_proprio(self):
        for codigo, conta in self.contas.items():
            with self.subTest(funcao=codigo):
                for rota in ("/rh/", *TELAS_DA_EQUIPE, *TELAS_DA_GESTAO):
                    resposta = self.abrir(conta, rota)
                    self.assertEqual(resposta.status_code, 302, rota)
                    self.assertFalse(resposta["Location"].startswith("/rh/colaboradores"), rota)
                self.assertEqual(self.abrir(conta, "/rh/ponto/").status_code, 200)
                self.assertEqual(self.abrir(conta, "/rh/tarefas/").status_code, 200)

    def test_colaborador_nao_ve_a_ficha_do_outro(self):
        conta = self.contas["producao"]  # é a Ana
        self.assertEqual(self.abrir(conta, f"/rh/colaboradores/{self.ana.pk}/").status_code, 200)
        for rota in (f"/rh/colaboradores/{self.bruno.pk}/", f"/rh/colaboradores/{self.bruno.pk}/imprimir/",
                     f"/rh/ponto/espelho/{self.bruno.pk}/", f"/rh/ponto/espelho/{self.bruno.pk}/imprimir/"):
            with self.subTest(rota=rota):
                self.assertEqual(self.abrir(conta, rota).status_code, 404)

    def test_colaborador_nunca_ve_salario(self):
        conta = self.contas["producao"]
        propria = self.abrir(conta, f"/rh/colaboradores/{self.ana.pk}/").content.decode()
        self.assertNotIn("3.456,78", propria)
        self.assertNotIn("9.876,54", propria)
        self.assertNotIn("Salário", propria)
        impressa = self.abrir(conta, f"/rh/colaboradores/{self.ana.pk}/imprimir/").content.decode()
        self.assertNotIn("3.456,78", impressa)

    def test_colaborador_nao_abre_documento_alheio_e_fica_registrado(self):
        conta = self.contas["producao"]
        resposta = self.abrir(conta, f"/rh/documentos/{self.doc_bruno.pk}/arquivo/")
        self.assertEqual(resposta.status_code, 404)
        self.assertNotIn(b"%PDF", resposta.content)
        self.assertTrue(RegistroRH.objects.filter(
            acao=RegistroRH.Acao.ACESSO_NEGADO, usuario=conta, colaborador=self.bruno,
        ).exists())

    def test_colaborador_abre_o_proprio_documento(self):
        doc = guardar_documento(
            self.ana, conferir(SimpleUploadedFile("cpf.pdf", pdf_sintetico("CPF da Ana"))), tipo="cpf",
        )
        resposta = self.abrir(self.contas["producao"], f"/rh/documentos/{doc.pk}/arquivo/")
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.content.startswith(b"%PDF"))
        self.assertTrue(RegistroRH.objects.filter(acao=RegistroRH.Acao.DOC_ABERTO, documento=doc).exists())

    def test_colaborador_nao_mexe_em_post_da_gestao(self):
        conta = self.contas["vendas"]
        self.client.force_login(conta)
        total = DocumentoColaborador.objects.count()
        resposta = self.client.post(
            f"/rh/documentos/{self.doc_bruno.pk}/remover/", **INTERNO,
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(DocumentoColaborador.objects.count(), total)
        resposta = self.client.post(f"/rh/colaboradores/{self.ana.pk}/termo/", {"action": "gerar"}, **INTERNO)
        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(self.ana.termos.exists())

    def test_quem_nao_e_da_equipe_nao_entra(self):
        cliente = criar_conta("cliente-da-loja")
        resposta = self.abrir(cliente, "/rh/ponto/")
        self.assertEqual(resposta.status_code, 302)
        self.client.logout()
        self.assertEqual(self.client.get("/rh/ponto/", **INTERNO).status_code, 302)

    def test_rh_fora_do_subdominio_nao_existe(self):
        self.client.force_login(self.gestora)
        self.assertNotEqual(self.client.get("/rh/").status_code, 200)

    def test_gestao_cria_e_edita_ficha(self):
        self.client.force_login(self.gestora)
        resposta = self.client.post(f"/rh/colaboradores/{self.ana.pk}/editar/", {
            **self._dados_da_ficha(self.ana), "cargo": "Montadora líder",
        }, **INTERNO)
        self.assertEqual(resposta.status_code, 302, getattr(resposta, "context", None) and resposta.context["form"].errors)
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.cargo, "Montadora líder")
        self.assertTrue(RegistroRH.objects.filter(acao=RegistroRH.Acao.FICHA_ALTERADA, colaborador=self.ana).exists())

    @staticmethod
    def _dados_da_ficha(c):
        return {
            "nome": c.nome, "cpf": c.cpf, "rg": c.rg, "data_nascimento": c.data_nascimento.isoformat(),
            "pis": c.pis, "cep": c.cep, "logradouro": c.logradouro, "numero": c.numero, "bairro": c.bairro,
            "cidade": c.cidade, "uf": c.uf, "telefone": c.telefone, "emergencia_nome": c.emergencia_nome,
            "emergencia_telefone": c.emergencia_telefone, "cargo": c.cargo, "setor": c.setor,
            "data_admissao": c.data_admissao.isoformat(), "vinculo": c.vinculo, "situacao": c.situacao,
            "jornada_inicio": "08:00", "jornada_fim": "17:00", "jornada_intervalo_min": "60",
            "jornada_dias": list(c.jornada_dias), "salario": "3.456,78",
        }


class ContaLigadaNaFichaTests(Base):
    def test_conta_do_painel_ligada_pelo_login(self):
        nova = criar_conta("montador-novo", "producao")
        self.client.force_login(self.gestora)
        dados = CadaFuncaoEntraNasTelasTests._dados_da_ficha(criar_colaborador(9))
        Colaborador.objects.filter(nome=dados["nome"]).delete()
        dados["conta_painel"] = "montador-novo"
        resposta = self.client.post("/rh/colaboradores/novo/", dados, **INTERNO)
        self.assertEqual(resposta.status_code, 302)
        ficha = Colaborador.objects.get(cpf=dados["cpf"])
        self.assertEqual(ficha.usuario, nova)
        # e entra na lista da produção (o nome das ordens de produção)
        self.assertIsNotNone(ficha.colaborador_producao)

    def test_conta_de_cliente_nao_liga(self):
        criar_conta("cliente-qualquer")
        self.client.force_login(self.gestora)
        dados = CadaFuncaoEntraNasTelasTests._dados_da_ficha(criar_colaborador(8))
        Colaborador.objects.filter(nome=dados["nome"]).delete()
        dados["conta_painel"] = "cliente-qualquer"
        resposta = self.client.post("/rh/colaboradores/novo/", dados, **INTERNO)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Nenhuma conta ativa da equipe")
