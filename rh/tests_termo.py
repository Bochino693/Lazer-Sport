"""O termo de exclusividade: texto, assinatura, trilha, PDF, faixa e versão."""

import io
from datetime import date
from unittest import mock

from django.test import TestCase

from . import termo as svc
from .apoio_testes import (
    INTERNO,
    PastaPrivadaTemporaria,
    assinatura_sintetica,
    criar_colaborador,
    criar_conta,
)
from .models import DocumentoColaborador, MarcacaoPonto, RegistroRH, TermoExclusividade
from .validadores import formatar_cpf


def dados_da_assinatura(colaborador, **extra):
    return {
        "nome": colaborador.nome, "cpf": formatar_cpf(colaborador.cpf), "concordo": "1",
        "assinatura": assinatura_sintetica(), **extra,
    }


class TextoDoTermoTests(TestCase):
    def test_o_texto_sai_com_os_dados_da_ficha_e_da_empresa(self):
        c = criar_colaborador(1, cargo="Montador de brinquedos", data_admissao=date(2026, 3, 2))
        termo = svc.gerar(c)
        texto = termo.conteudo["texto"]
        self.assertIn(c.nome, texto["abertura"])
        self.assertIn(formatar_cpf(c.cpf), texto["abertura"])
        self.assertIn("contratado(a) por", texto["abertura"])
        self.assertIn("na função de Montador de brinquedos, desde 02/03/2026", texto["abertura"])
        self.assertIn("CNPJ", texto["abertura"])
        self.assertEqual(len(texto["itens"]), 4)
        self.assertIn("art. 482", texto["itens"][3])
        self.assertIn("máquinas de entretenimento", texto["itens"][0])
        self.assertRegex(texto["local_data"], r"^.+, \d{1,2} de [a-zç]+ de \d{4}\.$")
        self.assertEqual(termo.hash_conteudo, svc.hash_do_retrato(termo.conteudo))
        self.assertEqual(termo.situacao, "enviado")

    def test_pj_e_temporario_trocam_a_qualificacao_e_a_referencia_a_clt(self):
        for n, vinculo in ((2, "pj"), (3, "temporario")):
            with self.subTest(vinculo=vinculo):
                c = criar_colaborador(n, vinculo=vinculo, **({"pis": ""} if vinculo == "pj" else {}))
                texto = svc.gerar(c).conteudo["texto"]
                self.assertIn("prestador(a) de serviços", texto["abertura"])
                self.assertNotIn("contratado(a)", texto["abertura"])
                self.assertIn("rescisão do contrato de prestação de serviços", texto["itens"][3])
                self.assertNotIn("CLT", texto["itens"][3])

    def test_gerar_duas_vezes_nao_duplica(self):
        c = criar_colaborador(4)
        self.assertEqual(svc.gerar(c).pk, svc.gerar(c).pk)
        self.assertEqual(c.termos.count(), 1)

    def test_ficha_mudou_substitui_o_que_esperava(self):
        c = criar_colaborador(5)
        primeiro = svc.gerar(c)
        c.cargo = "Líder de montagem"
        c.save()
        segundo = svc.gerar(c)
        primeiro.refresh_from_db()
        self.assertNotEqual(primeiro.pk, segundo.pk)
        self.assertEqual(primeiro.situacao, "substituido")


class AssinarNoPainelTests(PastaPrivadaTemporaria, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.conta = criar_conta("colab-termo", "producao")
        cls.c = criar_colaborador(1, usuario=cls.conta)
        cls.conta2 = criar_conta("colab-termo-2", "vendas")
        cls.c2 = criar_colaborador(2, usuario=cls.conta2, setor="vendas")

    def test_assina_o_proprio_grava_trilha_e_pdf(self):
        self.client.force_login(self.conta)
        tela = self.client.get("/rh/termo/", **INTERNO)
        self.assertContains(tela, "revisão do advogado")
        termo = self.c.termos.get()
        resposta = self.client.post("/rh/termo/", dados_da_assinatura(self.c, termo=termo.pk),
                                    HTTP_ACCEPT="application/json", HTTP_USER_AGENT="Celular de teste", **INTERNO)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        termo.refresh_from_db()
        self.assertEqual(termo.situacao, "assinado")
        self.assertEqual(termo.canal, "painel")
        self.assertEqual(termo.assinatura_ip, "127.0.0.1")
        self.assertEqual(termo.assinatura_navegador, "Celular de teste")
        self.assertEqual(termo.hash_assinado, termo.hash_conteudo)
        self.assertIsNotNone(termo.assinado_em)
        # o PDF assinado foi para a pasta, no armazenamento privado
        doc = termo.documento
        self.assertEqual((doc.tipo, doc.colaborador), ("termo", self.c))
        with doc.arquivo.open("rb") as arquivo:
            dados = arquivo.read()
        from pypdf import PdfReader

        texto = "".join(p.extract_text() for p in PdfReader(io.BytesIO(dados)).pages)
        self.assertIn("TERMO DE EXCLUSIVIDADE E CONFIDENCIALIDADE", texto)
        self.assertIn(self.c.nome, texto)
        self.assertIn(termo.hash_assinado, texto.replace("\n", ""))
        self.assertTrue(RegistroRH.objects.filter(colaborador=self.c, documento=doc).exists())
        self.assertEqual(svc.situacao_de(self.c), "assinado")
        # assinado, não muda mais
        with self.assertRaises(Exception):
            termo.assinante_nome = "Outro"
            termo.save()

    def test_cpf_tem_de_ser_o_da_ficha(self):
        self.client.force_login(self.conta)
        self.client.get("/rh/termo/", **INTERNO)
        termo = self.c.termos.get()
        resposta = self.client.post("/rh/termo/", dados_da_assinatura(self.c, termo=termo.pk, cpf=formatar_cpf(self.c2.cpf)),
                                    HTTP_ACCEPT="application/json", **INTERNO)
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.json()["campo"], "documento")
        termo.refresh_from_db()
        self.assertEqual(termo.situacao, "enviado")

    def test_quadro_em_branco_e_sem_concordo_nao_assinam(self):
        self.client.force_login(self.conta)
        self.client.get("/rh/termo/", **INTERNO)
        termo = self.c.termos.get()
        for extra, campo in (({"assinatura": ""}, "assinatura"), ({"concordo": ""}, "concordo"), ({"nome": "Ana"}, "nome")):
            with self.subTest(campo=campo):
                resposta = self.client.post("/rh/termo/", dados_da_assinatura(self.c, termo=termo.pk, **extra),
                                            HTTP_ACCEPT="application/json", **INTERNO)
                self.assertEqual(resposta.json()["campo"], campo)
        self.assertFalse(DocumentoColaborador.objects.exists())

    def test_so_assina_o_proprio(self):
        termo_do_outro = svc.gerar(self.c2)
        self.client.force_login(self.conta)
        self.client.get("/rh/termo/", **INTERNO)
        resposta = self.client.post("/rh/termo/", dados_da_assinatura(self.c2, termo=termo_do_outro.pk),
                                    HTTP_ACCEPT="application/json", **INTERNO)
        self.assertEqual(resposta.status_code, 400)
        termo_do_outro.refresh_from_db()
        self.assertEqual(termo_do_outro.situacao, "enviado")
        self.assertEqual(self.client.get(f"/rh/termo/{termo_do_outro.pk}/via/", **INTERNO).status_code, 404)

    def test_o_ponto_continua_com_o_termo_pendente(self):
        self.client.force_login(self.conta)
        resposta = self.client.post("/rh/ponto/marcar/", HTTP_X_REQUESTED_WITH="XMLHttpRequest", **INTERNO)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(MarcacaoPonto.objects.filter(colaborador=self.c).count(), 1)


class AssinarPeloLinkTests(PastaPrivadaTemporaria, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.gestora = criar_conta("gestora-termo", "gestao")
        cls.c = criar_colaborador(1)

    def link(self):
        self.client.force_login(self.gestora)
        self.client.post(f"/rh/colaboradores/{self.c.pk}/termo/", {"action": "gerar"}, **INTERNO)
        corpo = self.client.post(f"/rh/colaboradores/{self.c.pk}/termo/", {"action": "link"}, **INTERNO).json()
        self.assertEqual(corpo["status"], "sucesso")
        self.assertIn("<svg", corpo["qr"])
        self.client.logout()
        return corpo["link"].split("testserver", 1)[1]

    def test_assina_pelo_link_sem_login(self):
        caminho = self.link()
        pagina = self.client.get(caminho, **INTERNO)
        self.assertEqual(pagina.status_code, 200)
        self.assertEqual(pagina["Cache-Control"], "no-store")
        self.assertContains(pagina, "TERMO DE EXCLUSIVIDADE")
        self.assertNotContains(pagina, self.c.cpf)  # o CPF não aparece inteiro
        resposta = self.client.post(caminho, dados_da_assinatura(self.c), HTTP_ACCEPT="application/json", **INTERNO)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        termo = self.c.termos.get()
        self.assertEqual((termo.situacao, termo.canal), ("assinado", "link"))
        self.assertIsNotNone(termo.documento_id)
        # o link vira o comprovante
        self.assertContains(self.client.get(caminho, **INTERNO), "Termo assinado")

    def test_link_vencido_ou_inventado(self):
        caminho = self.link()
        with mock.patch("rh.termo.VALIDADE_DO_LINK", -1):
            resposta = self.client.post(caminho, dados_da_assinatura(self.c), HTTP_ACCEPT="application/json", **INTERNO)
        self.assertEqual(resposta.status_code, 410)
        self.assertEqual(self.client.get("/rh/termo/assinar/1.abc.def.ghi/", **INTERNO).status_code, 404)
        self.assertEqual(self.c.termos.get().situacao, "enviado")


class FaixaEVersaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.gestora = criar_conta("gestora-faixa", "gestao")
        cls.conta = criar_conta("colab-faixa", "criacao")
        cls.c = criar_colaborador(1, usuario=cls.conta, setor="criacao", cargo="Designer")
        cls.outra = criar_colaborador(2)
        cls.vendedor = criar_conta("vendedor-sem-ficha", "vendas")

    def assinar_direto(self, colaborador):
        termo = svc.gerar(colaborador)
        termo.situacao = TermoExclusividade.Estado.ASSINADO
        termo.assinado_em = termo.gerado_em
        termo.save()
        return termo

    def faixa(self, conta, rota="/orcamentos/"):
        self.client.force_login(conta)
        html = self.client.get(rota, **INTERNO).content.decode()
        return html

    def test_faixa_da_gestao_em_qualquer_tela_e_some_quando_todos_assinam(self):
        for rota in ("/orcamentos/", "/clientes/", "/rh/"):
            with self.subTest(rota=rota):
                html = self.faixa(self.gestora, rota)
                self.assertIn('data-rh-faixa="gestao"', html)
                self.assertIn("2 colaboradores sem o termo de exclusividade assinado", html)
                self.assertIn("/rh/colaboradores/?termo=pendente", html)
        self.assinar_todos()
        self.assertNotIn("data-rh-faixa", self.faixa(self.gestora))

    def assinar_todos(self):
        self.assinar_direto(self.c)
        self.assinar_direto(self.outra)

    def test_faixa_do_proprio_colaborador(self):
        html = self.faixa(self.conta, "/site/brinquedos/")
        self.assertIn('data-rh-faixa="proprio"', html)
        self.assertIn("Assine o termo de exclusividade", html)
        self.assertIn('href="/rh/termo/"', html)
        self.assinar_direto(self.c)
        self.assertNotIn("data-rh-faixa", self.faixa(self.conta, "/site/brinquedos/"))

    def test_quem_nao_tem_ficha_nao_ve_faixa(self):
        self.assertNotIn("data-rh-faixa", self.faixa(self.vendedor))

    def test_desligado_nao_conta(self):
        self.outra.situacao = "desligado"
        self.outra.data_desligamento = self.outra.data_admissao
        self.outra.save()
        self.assertIn("1 colaborador sem o termo", self.faixa(self.gestora))

    def test_nova_versao_do_texto_pede_nova_assinatura(self):
        self.assinar_todos()
        self.assertEqual(svc.pendentes().count(), 0)
        with mock.patch("rh.termo.VERSAO_DO_TERMO", "2027-01"):
            self.assertEqual(svc.pendentes().count(), 2)
            self.assertEqual(svc.situacao_de(self.c), "pendente")
            novo = svc.gerar(self.c)
            self.assertEqual(novo.versao, "2027-01")
            self.assertIn('data-rh-faixa="proprio"', self.faixa(self.conta, "/site/brinquedos/"))

    def test_enviar_para_todos(self):
        self.client.force_login(self.gestora)
        self.client.post("/rh/termo/enviar-todos/", **INTERNO)
        self.assertEqual(TermoExclusividade.objects.filter(situacao="enviado").count(), 2)
        self.assertEqual(svc.situacao_de(self.c), "enviado")
