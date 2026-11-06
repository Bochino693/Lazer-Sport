"""Gerar o APK (Android) de um jogo pelo painel (core/jogos_apk_gerar.py)."""

import base64
import hashlib
import io
import shutil
import struct
import tempfile
import zipfile
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.test import TestCase

from . import jogos_apk_gerar as gerar

from .models import ArquivoEmulador, ChaveDosApks, JogoCadastrado
from .tests_jogos_emulador import AUDIO, CUE, E, FAIXA_PSX, analisar

HOST = "interno.testserver"


class BaseApk(TestCase):
    def setUp(self):
        pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, pasta, ignore_errors=True)
        self.disco = FileSystemStorage(location=pasta, base_url="/media/")
        for modelo, campo in ((JogoCadastrado, "capa"), (JogoCadastrado, "apk"), (ArquivoEmulador, "arquivo")):
            trocar = mock.patch.object(modelo._meta.get_field(campo), "storage", self.disco)
            trocar.start()
            self.addCleanup(trocar.stop)
        # os arquivos do jogo "baixados" do armazenamento (aqui, a pasta de teste)
        disco = self.disco

        def baixar(url, timeout=60):
            nome = url.split("/media/", 1)[1]
            with disco.open(nome, "rb") as f:
                return f.read()

        trocar = mock.patch.object(gerar, "_baixar", side_effect=baixar)
        trocar.start()
        self.addCleanup(trocar.stop)
        self.jogo = JogoCadastrado.objects.create(nome="Disco Teste", slug="disco-teste", sistema="psx", cor="#22d3ee")
        an = analisar(E("Jogo (Disc 1).cue", CUE), E("Track 01.bin", FAIXA_PSX), E("Track 02.bin", AUDIO))
        for ordem, peca in enumerate(an.pecas):
            registro = ArquivoEmulador(jogo=self.jogo, nome=peca.nome, papel=peca.papel, tamanho=peca.entrada.tamanho,
                                       lote="abc", ordem=ordem)
            if peca.conteudo is not None:
                registro.conteudo = peca.conteudo
            else:
                registro.arquivo.save("guardado_" + peca.nome, ContentFile(peca.entrada.pedaco(0, peca.entrada.tamanho)), save=False)
            registro.save()

    def apk(self, jogo=None):
        saida = io.BytesIO()
        from django.test import RequestFactory

        gerar.gerar_apk(jogo or JogoCadastrado.objects.get(pk=self.jogo.pk), saida,
                        request=RequestFactory().get("/", HTTP_HOST="testserver"))
        return saida.getvalue()


class GerarApkTests(BaseApk):
    def test_o_apk_tem_o_app_o_jogo_e_as_assinaturas(self):
        bruto = self.apk()
        pacote = zipfile.ZipFile(io.BytesIO(bruto))
        self.assertIsNone(pacote.testzip())
        nomes = pacote.namelist()
        # a assinatura v1 primeiro (onde o Java e o Android antigo procuram)
        self.assertEqual(nomes[:3], ["META-INF/MANIFEST.MF", "META-INF/CERT.SF", "META-INF/CERT.RSA"])
        for nome in ("AndroidManifest.xml", "classes.dex", "resources.arsc", gerar.CAMINHO_DO_ICONE,
                     "assets/www/index.html", "assets/www/rom/Jogo (Disc 1).cue", "assets/www/rom/Track 01.bin",
                     "assets/www/static/vendor/emulatorjs/data/loader.js",
                     "assets/www/static/vendor/emulatorjs/data/cores/pcsx_rearmed-wasm.data",
                     "assets/www/static/site/paginas/jogo-emulador.js"):
            with self.subTest(arquivo=nome):
                self.assertIn(nome, nomes)
        # a página do jogo aponta para dentro do APK
        html = pacote.read("assets/www/index.html").decode()
        self.assertIn('"apk": true', html)
        self.assertIn('"/rom/Track%2001.bin"', html)
        self.assertIn('"nucleoExterno": ""', html)
        # o MANIFEST.MF tem o resumo certo de cada arquivo
        mf = pacote.read("META-INF/MANIFEST.MF").decode()
        resumo = base64.b64encode(hashlib.sha256(pacote.read("assets/www/rom/Track 01.bin")).digest()).decode()
        self.assertIn(resumo, mf)
        self.assertIn("X-Android-APK-Signed: 2", pacote.read("META-INF/CERT.SF").decode())
        # o bloco da assinatura v2 fica logo antes do diretório central, como o Android procura
        fim = bruto.rindex(b"PK\x05\x06")
        inicio_cd = struct.unpack("<I", bruto[fim + 16:fim + 20])[0]
        self.assertEqual(bruto[inicio_cd - 16:inicio_cd], b"APK Sig Block 42")
        # o que vai sem compressão fica alinhado em 4 bytes (o zipalign)
        for info in pacote.infolist():
            if info.compress_type == zipfile.ZIP_STORED:
                with self.subTest(alinhado=info.filename):
                    # o tamanho do nome e do "extra" do cabeçalho local (o enchimento do alinhamento mora ali)
                    n, x = struct.unpack("<HH", bruto[info.header_offset + 26:info.header_offset + 30])
                    inicio = info.header_offset + 30 + n + x
                    self.assertEqual(inicio % 4, 0)

    def test_o_manifesto_e_os_recursos_saem_no_formato_do_android(self):
        bruto = self.apk()
        pacote = zipfile.ZipFile(io.BytesIO(bruto))
        manifesto = pacote.read("AndroidManifest.xml")
        self.assertEqual(struct.unpack("<HH", manifesto[:4]), (0x0003, 8))  # XML binário
        self.assertIn("br.com.lazersport.jogo.disco_teste".encode("utf-16-le"), manifesto)
        self.assertIn(gerar.ATIVIDADE.encode("utf-16-le"), manifesto)
        self.assertIn(struct.pack("<I", gerar.ICONE_ID), manifesto)
        recursos = pacote.read("resources.arsc")
        self.assertEqual(struct.unpack("<HH", recursos[:4]), (0x0002, 12))
        self.assertIn(gerar.CAMINHO_DO_ICONE.encode(), recursos)
        # o ícone é um PNG de 192 x 192
        icone = pacote.read(gerar.CAMINHO_DO_ICONE)
        self.assertEqual(icone[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", icone[16:24]), (192, 192))

    def test_a_chave_e_sempre_a_mesma(self):
        primeiro = zipfile.ZipFile(io.BytesIO(self.apk())).read("META-INF/CERT.RSA")
        segundo = zipfile.ZipFile(io.BytesIO(self.apk())).read("META-INF/CERT.RSA")
        self.assertEqual(ChaveDosApks.objects.count(), 1)
        # o certificado (o que o Android compara para atualizar) é o mesmo nas duas
        from cryptography.hazmat.primitives.serialization import pkcs7

        self.assertEqual(pkcs7.load_der_pkcs7_certificates(primeiro), pkcs7.load_der_pkcs7_certificates(segundo))

    def test_psp_e_dos_nao_viram_apk(self):
        JogoCadastrado.objects.filter(pk=self.jogo.pk).update(sistema="psp")
        with self.assertRaises(gerar.ApkNaoDa):
            self.apk()

    def test_o_nome_do_pacote(self):
        self.assertEqual(gerar.nome_do_pacote("super-mario-teste"), "br.com.lazersport.jogo.super_mario_teste")
        self.assertEqual(gerar.nome_do_pacote("1942"), "br.com.lazersport.jogo.j1942")
        self.assertEqual(gerar.nome_do_pacote("Ação Total!"), "br.com.lazersport.jogo.acao_total")


class PainelApkTests(BaseApk):
    def setUp(self):
        super().setUp()
        self.chefe = User.objects.create_superuser("chefe", "chefe@example.com", "senha-segura")
        self.url = f"/site/jogos/{self.jogo.pk}/apk/"

    def test_o_superadministrador_baixa_o_apk(self):
        self.client.force_login(self.chefe)
        resposta = self.client.get(self.url, HTTP_HOST=HOST)
        self.assertEqual(resposta.status_code, 200, getattr(resposta, "content", b"")[:300])
        self.assertEqual(resposta["Content-Type"], "application/vnd.android.package-archive")
        self.assertIn('filename="disco-teste.apk"', resposta["Content-Disposition"])
        conteudo = b"".join(resposta.streaming_content)
        self.assertIn("AndroidManifest.xml", zipfile.ZipFile(io.BytesIO(conteudo)).namelist())

    def test_publicar_poe_o_botao_baixar_o_aplicativo(self):
        self.client.force_login(self.chefe)
        resposta = self.client.post(self.url, {"publicar": "1"}, HTTP_HOST=HOST)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertTrue(resposta.json()["ok"])
        jogo = JogoCadastrado.objects.get(pk=self.jogo.pk)
        self.assertTrue(jogo.apk.name.endswith(".apk"))
        self.assertTrue(jogo.liberar_download)

    def test_quem_nao_e_superadministrador_nao_gera(self):
        outro = User.objects.create_user("criador", password="senha-segura", is_staff=True)
        self.client.force_login(outro)
        self.assertNotEqual(self.client.get(self.url, HTTP_HOST=HOST).status_code, 200)

    def test_o_motivo_aparece_quando_nao_da(self):
        JogoCadastrado.objects.filter(pk=self.jogo.pk).update(sistema="dos")
        self.client.force_login(self.chefe)
        resposta = self.client.get(self.url, HTTP_HOST=HOST)
        self.assertEqual(resposta.status_code, 422)
        self.assertIn("não vai para APK", resposta.content.decode())
