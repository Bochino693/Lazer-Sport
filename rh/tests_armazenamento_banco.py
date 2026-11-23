"""O RH com os documentos no nosso banco (LEIA-ME-V10, seção 130).

O caso do dono: "não consigo gerar o ponto para os funcionários" -- o PDF
do cartão de ponto voltava "Não deu para salvar -- O servidor encontrou um
erro" porque o Cloudinary desativou a conta. Aqui o modo "banco" (o padrão
em produção): o cartão e o documento entram com o Cloudinary RECUSANDO
tudo, ficam numa linha privada (nunca em /midia/banco/), abrem só pela
view, e o nome antigo continua no legado. E se o próprio armazenamento
falhar, a resposta é a janela de app, nunca 500. Dados sintéticos.
"""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from unittest import mock

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.utils import timezone

from core import arquivos_no_banco as anb
from core import espelho_midia
from core.models import ArquivoNoBanco

from . import armazenamento
from .apoio_testes import cartao_ponto_pdf, criar_colaborador, criar_conta, funcionario_do_cartao, pdf_sintetico
from .models import CartaoPonto, DocumentoColaborador, ImportacaoPonto
from .tests_importacao_ponto import DIAS_DO_CARTAO

INTERNO = {"HTTP_HOST": "interno.testserver"}
AJAX = {**INTERNO, "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


def cloudinary_desativado(*args, **kwargs):
    raise Exception("cloud_name dgikjmki8 is disabled")


@override_settings(EMPRESA_CNPJ="54.486.908/0001-86", RH_ARMAZENAMENTO="banco")
class DocumentosNoBancoTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._pasta = tempfile.mkdtemp(prefix="rh-legado-")
        cls._override = override_settings(RH_ARQUIVOS_PRIVADOS_DIR=cls._pasta)
        cls._override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._override.disable()
        shutil.rmtree(cls._pasta, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.gestora = criar_conta("gestora-banco", "gestao")

    def setUp(self):
        self.client.force_login(self.gestora)
        relogio = mock.patch("django.utils.timezone.now",
                             return_value=datetime(2026, 11, 23, 10, 0, tzinfo=timezone.get_default_timezone()))
        relogio.start()
        self.addCleanup(relogio.stop)
        # o Cloudinary recusa TUDO, como em 23/11/2026: nada aqui pode depender dele
        for alvo in ("cloudinary.uploader.upload", "cloudinary.uploader.destroy"):
            trava = mock.patch(alvo, side_effect=cloudinary_desativado)
            trava.start()
            self.addCleanup(trava.stop)

    def enviar_cartao(self, dados):
        return self.client.post("/rh/ponto/cartoes/enviar/",
                                {"arquivos": SimpleUploadedFile("cartao.pdf", dados, content_type="application/pdf")},
                                **AJAX)

    def test_o_cartao_de_ponto_entra_com_o_cloudinary_desativado(self):
        pessoa = criar_colaborador(1)
        dados = cartao_ponto_pdf(funcionario_do_cartao(1, dias=DIAS_DO_CARTAO))
        resposta = self.enviar_cartao(dados)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(resposta.json()["status"], "sucesso")
        importacao = ImportacaoPonto.objects.get()
        self.assertTrue(importacao.arquivo.name.startswith("banco/rh/cartoes/"), importacao.arquivo.name)
        linha = ArquivoNoBanco.objects.get(nome=importacao.arquivo.name)
        self.assertFalse(linha.publico)
        self.assertEqual(bytes(linha.conteudo), dados)
        # o original abre só pela view, para a Gestão
        aberto = self.client.get(f"/rh/ponto/cartoes/{importacao.pk}/arquivo/", **INTERNO)
        self.assertEqual(aberto.status_code, 200)
        self.assertEqual(aberto.content, dados)
        self.assertIn("no-store", aberto["Cache-Control"])
        # nunca pela rota pública
        self.assertEqual(self.client.get("/midia/" + importacao.arquivo.name).status_code, 404)
        # e importar põe o PDF da pessoa na pasta dela -- também no banco
        cartao = CartaoPonto.objects.get()
        importado = self.client.post(f"/rh/ponto/cartoes/cartao/{cartao.pk}/importar/", {}, **AJAX)
        self.assertEqual(importado.status_code, 200, importado.content)
        documento = DocumentoColaborador.objects.get(colaborador=pessoa, tipo="cartao_ponto")
        self.assertTrue(documento.arquivo.name.startswith("banco/rh/"))
        self.assertFalse(ArquivoNoBanco.objects.get(nome=documento.arquivo.name).publico)

    def test_o_documento_entra_abre_e_sai(self):
        c = criar_colaborador(2)
        dados = pdf_sintetico("Conta de luz")
        resposta = self.client.post(
            f"/rh/colaboradores/{c.pk}/documentos/",
            {"tipo": "residencia", "emissao": timezone.localdate().isoformat(),
             "arquivo": SimpleUploadedFile("comprovante.pdf", dados)},
            **AJAX,
        )
        self.assertEqual(resposta.status_code, 200, resposta.content)
        doc = DocumentoColaborador.objects.get(colaborador=c)
        self.assertTrue(doc.arquivo.name.startswith("banco/rh/"))
        with self.assertRaises(armazenamento.ArquivoSemEnderecoPublico):
            doc.arquivo.url
        aberto = self.client.get(f"/rh/documentos/{doc.pk}/arquivo/", **INTERNO)
        self.assertEqual((aberto.status_code, aberto.content), (200, dados))
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/rh/documentos/{doc.pk}/remover/", **INTERNO)
        self.assertFalse(ArquivoNoBanco.objects.filter(nome=doc.arquivo.name).exists())

    def test_o_banco_que_falha_vira_janela_e_nao_500(self):
        c = criar_colaborador(3)
        with mock.patch.object(anb, "guardar", side_effect=DatabaseError("o banco caiu")):
            cartao = self.enviar_cartao(cartao_ponto_pdf(funcionario_do_cartao(3, dias=DIAS_DO_CARTAO)))
            documento = self.client.post(
                f"/rh/colaboradores/{c.pk}/documentos/",
                {"tipo": "residencia", "emissao": timezone.localdate().isoformat(),
                 "arquivo": SimpleUploadedFile("comprovante.pdf", pdf_sintetico())},
                **AJAX,
            )
        self.assertNotEqual(cartao.status_code, 500)
        self.assertEqual(cartao.json()["status"], "erro", cartao.json())
        self.assertEqual(cartao.json()["titulo"], "Arquivo não guardado")
        self.assertEqual(cartao.json()["campo"], "arquivos")
        self.assertFalse(ImportacaoPonto.objects.exists())
        self.assertEqual(documento.status_code, 400)
        self.assertEqual((documento.json()["titulo"], documento.json()["campo"]), ("Arquivo não guardado", "arquivo"))
        self.assertFalse(DocumentoColaborador.objects.exists())

    def test_o_cloudinary_forcado_que_recusa_tambem_vira_janela(self):
        with override_settings(RH_ARMAZENAMENTO="cloudinary"):
            resposta = self.enviar_cartao(cartao_ponto_pdf(funcionario_do_cartao(4, dias=DIAS_DO_CARTAO)))
        self.assertNotEqual(resposta.status_code, 500)
        self.assertEqual(resposta.json()["titulo"], "Arquivo não guardado")

    def test_o_nome_antigo_vai_para_o_legado(self):
        # no computador e nos testes o legado é a pasta local; em produção, o Cloudinary autenticado
        armazenamento._LocalPrivado().save("rh/aa/antigo.pdf", ContentFile(b"%PDF-1.4 antigo"))
        with armazenamento.armazenamento_privado.open("rh/aa/antigo.pdf") as arquivo:
            self.assertEqual(arquivo.read(), b"%PDF-1.4 antigo")
        with override_settings(ENVIRONMENT="production"):
            self.assertTrue(armazenamento.legado_e_cloudinary())
            self.assertIsInstance(armazenamento.armazenamento_privado._para("rh/aa/antigo.pdf"),
                                  armazenamento._CloudinaryPrivado)
            self.assertIsInstance(armazenamento.armazenamento_privado._para("banco/rh/aa/novo.pdf"),
                                  armazenamento._BancoPrivado)

    @override_settings(RH_ARMAZENAMENTO="")
    def test_o_padrao_de_producao_e_o_banco(self):
        with override_settings(ENVIRONMENT="production"):
            self.assertEqual(armazenamento.modo(), "banco")
        with override_settings(ENVIRONMENT="development"):
            self.assertEqual(armazenamento.modo(), "local")

    def test_o_cloudinary_autenticado_desativado_e_reconhecido(self):
        resposta = mock.Mock(status_code=401, headers={"x-cld-error": "cloud_name x is disabled"}, content=b"")
        with mock.patch("requests.get", return_value=resposta):
            with self.assertRaises(anb.CloudinaryForaDoAr):
                armazenamento._CloudinaryPrivado()._open("rh/aa/antigo.pdf")

    def test_o_espelho_traz_o_documento_antigo_como_privado(self):
        c = criar_colaborador(5)
        armazenamento._LocalPrivado().save("rh/bb/antigo.pdf", ContentFile(pdf_sintetico("antigo")))
        doc = DocumentoColaborador.objects.create(
            colaborador=c, tipo="residencia", nome_original="antigo.pdf", tipo_conteudo="application/pdf",
            tamanho=10, sha256="0" * 64, arquivo="rh/bb/antigo.pdf",
        )
        resultado = espelho_midia.espelhar()
        self.assertEqual(resultado["copiados"], 1)
        doc.refresh_from_db()
        self.assertEqual(doc.arquivo.name, "banco/rh/bb/antigo.pdf")
        self.assertFalse(ArquivoNoBanco.objects.get(nome="banco/rh/bb/antigo.pdf").publico)
