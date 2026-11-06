"""Gerar o programa de Windows (.exe) de um jogo pelo painel (core/jogos_exe_gerar.py).

O que se garante: o .exe é a casca + o .zip do jogo + a marca no fim (a casca
acha o .zip pelo próprio arquivo); leva o mesmo conteúdo do APK; o PSP e o DOS,
que não vão para o APK, entram no .exe (com o núcleo de várias linhas); os
arquivos grandes vão sem compressão (lidos em pedaços); e o painel baixa ou
guarda o .exe como a versão para computador.
"""

import io
import struct
import zipfile
from unittest import mock

from django.contrib.auth.models import User
from django.test import RequestFactory

from . import jogos_exe_gerar
from .models import JogoCadastrado
from .tests_jogos_apk_gerar import HOST, BaseApk


def abrir_exe(dados):
    """(casca, zip) de um .exe gerado: o que a casca em Go faz ao abrir."""
    assert dados[-8:] == jogos_exe_gerar.MARCA
    inicio = struct.unpack("<Q", dados[-16:-8])[0]
    return dados[:inicio], zipfile.ZipFile(io.BytesIO(dados[inicio:-16]))


class GerarExeTests(BaseApk):
    def exe(self, jogo=None):
        saida = io.BytesIO()
        jogos_exe_gerar.gerar_exe(jogo or JogoCadastrado.objects.get(pk=self.jogo.pk), saida,
                                  request=RequestFactory().get("/", HTTP_HOST="testserver"))
        return saida.getvalue()

    def test_o_exe_e_a_casca_mais_o_jogo(self):
        casca, pacote = abrir_exe(self.exe())
        self.assertEqual(casca, jogos_exe_gerar.CASCA_EXE.read_bytes())
        self.assertTrue(casca.startswith(b"MZ"))  # um executável do Windows
        nomes = pacote.namelist()
        self.assertIn("lsjogo.json", nomes)
        self.assertIn("index.html", nomes)
        self.assertTrue(any(n.startswith("rom/") for n in nomes))
        self.assertIn('"slug": "disco-teste"', pacote.read("lsjogo.json").decode())

    def test_psp_e_dos_entram_no_exe(self):
        JogoCadastrado.objects.filter(pk=self.jogo.pk).update(sistema="psp")
        _casca, pacote = abrir_exe(self.exe())
        # o APK recusa o PSP; o .exe aceita (a página dele é isolada)
        self.assertIn("index.html", pacote.namelist())
        self.assertIn("EJS_threads", pacote.read("static/site/paginas/jogo-emulador.js").decode())

    def test_arquivo_grande_vai_sem_compressao(self):
        saida = io.BytesIO()
        grande = bytes(range(256)) * (jogos_exe_gerar.SEM_COMPRESSAO_ACIMA // 256 + 10)
        jogos_exe_gerar.montar_exe(saida, [("index.html", b"<html></html>"), ("rom/jogo.bin", grande),
                                           ("capa.png", b"\x89PNG....")], "Jogo", "jogo")
        _casca, pacote = abrir_exe(saida.getvalue())
        tipos = {i.filename: i.compress_type for i in pacote.infolist()}
        self.assertEqual(tipos["rom/jogo.bin"], zipfile.ZIP_STORED)
        self.assertEqual(tipos["capa.png"], zipfile.ZIP_STORED)
        self.assertEqual(tipos["index.html"], zipfile.ZIP_DEFLATED)
        self.assertEqual(pacote.read("rom/jogo.bin"), grande)

    def test_aviso_da_licenca_nao_comercial(self):
        self.assertEqual(jogos_exe_gerar.aviso_de_licenca(JogoCadastrado(sistema="psx")), "")
        self.assertIn("uso particular", jogos_exe_gerar.aviso_de_licenca(JogoCadastrado(sistema="snes")))


class PainelExeTests(BaseApk):
    def setUp(self):
        super().setUp()
        self.chefe = User.objects.create_superuser("chefe", "chefe@example.com", "senha-segura")
        self.url = f"/site/jogos/{self.jogo.pk}/exe/"
        trocar = mock.patch.object(JogoCadastrado._meta.get_field("versao_pc"), "storage", self.disco)
        trocar.start()
        self.addCleanup(trocar.stop)

    def test_o_superadministrador_baixa_o_exe(self):
        self.client.force_login(self.chefe)
        resposta = self.client.get(self.url, HTTP_HOST=HOST)
        self.assertEqual(resposta.status_code, 200, getattr(resposta, "content", b"")[:300])
        self.assertIn('filename="disco-teste.exe"', resposta["Content-Disposition"])
        conteudo = b"".join(resposta.streaming_content)
        _casca, pacote = abrir_exe(conteudo)
        self.assertIn("index.html", pacote.namelist())
        self.assertEqual(int(resposta["X-Tamanho-Arquivo"]), len(conteudo))

    def test_guardar_como_versao_para_computador(self):
        self.client.force_login(self.chefe)
        resposta = self.client.post(self.url, HTTP_HOST=HOST)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertTrue(resposta.json()["ok"])
        self.assertTrue(JogoCadastrado.objects.get(pk=self.jogo.pk).versao_pc.name.endswith(".exe"))

    def test_quem_nao_e_superadministrador_nao_gera(self):
        outro = User.objects.create_user("criador", password="senha-segura", is_staff=True)
        self.client.force_login(outro)
        self.assertNotEqual(self.client.get(self.url, HTTP_HOST=HOST).status_code, 200)
