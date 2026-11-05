"""A tela de jogos do painel (/site/jogos/): só o superadministrador.

O que se garante: quem não é super não entra (nem vê o menu); o cadastro
pelo painel recusa o que a página pública não aguentaria (http, .html
binário, .apk que não é ZIP, arquivo grande); salvar, ligar/desligar e
excluir funcionam e o jogo salvo aparece no site; excluir exige a
palavra de confirmação e apaga os arquivos.
"""
import shutil
import tempfile
from io import BytesIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from core.models import JogoCadastrado

from .permissoes import atribuir_funcoes


def _png():
    from PIL import Image

    saida = BytesIO()
    Image.new("RGB", (8, 8), (255, 61, 242)).save(saida, format="PNG")
    return saida.getvalue()


PNG = _png()
HTML = b"<!doctype html><html><body><canvas></canvas><script>console.log('oi')</script></body></html>"
APK = b"PK\x03\x04" + b"\x00" * 60
HOST = "interno.testserver"


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class BaseTela(TestCase):
    def setUp(self):
        pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, pasta, ignore_errors=True)
        self.disco = FileSystemStorage(location=pasta, base_url="/media/")
        for campo in ("capa", "poster", "arquivo_html", "apk", "versao_pc"):
            trocar = mock.patch.object(JogoCadastrado._meta.get_field(campo), "storage", self.disco)
            trocar.start()
            self.addCleanup(trocar.stop)
        self.super = User.objects.create_superuser("chefe", "chefe@example.com", "senha-segura")
        self.criador = User.objects.create_user("criador", password="senha-segura", is_staff=True)
        atribuir_funcoes(self.criador, ["criacao", "gestao"])

    def dados(self, **extra):
        base = {
            "action": "salvar",
            "nome": "Corrida Maluca",
            "slug": "corrida-maluca",
            "chamada": "Desvie de tudo!",
            "cor": "#22d3ee",
            "ordem": "10",
            "ativo": "on",
            "proporcao": "paisagem",
            "endereco": "https://jogos.exemplo.com/corrida/index.html",
            "capa": SimpleUploadedFile("capa.png", PNG, content_type="image/png"),
        }
        base.update(extra)
        return base

    def enviar(self, dados, user=None):
        self.client.force_login(user or self.super)
        return self.client.post("/site/jogos/", dados, HTTP_HOST=HOST, HTTP_X_REQUESTED_WITH="XMLHttpRequest")


class PermissaoTests(BaseTela):
    def test_anonimo_vai_para_o_login(self):
        resposta = self.client.get("/site/jogos/", HTTP_HOST=HOST)
        self.assertRedirects(resposta, "/login/inner/", fetch_redirect_response=False)

    def test_criacao_e_gestao_nao_bastam(self):
        self.client.force_login(self.criador)
        resposta = self.client.get("/site/jogos/", HTTP_HOST=HOST)
        self.assertEqual(resposta.status_code, 302)
        self.assertNotIn("/site/jogos/", resposta.get("Location", ""))
        # nem gravar
        resposta = self.enviar(self.dados(), user=self.criador)
        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(JogoCadastrado.objects.exists())

    def test_menu_so_para_o_superadministrador(self):
        self.client.force_login(self.criador)
        self.assertNotContains(self.client.get("/", HTTP_HOST=HOST), "/site/jogos/")
        self.client.force_login(self.super)
        resposta = self.client.get("/site/jogos/", HTTP_HOST=HOST)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Jogos do simulador")
        self.assertContains(resposta, 'href="/site/jogos/"')


class CadastroTests(BaseTela):
    def test_salva_e_o_jogo_aparece_no_site(self):
        resposta = self.enviar(self.dados())
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(resposta.json()["status"], "sucesso")
        jogo = JogoCadastrado.objects.get(slug="corrida-maluca")
        self.assertTrue(jogo.ativo)
        self.assertEqual(jogo.endereco, "https://jogos.exemplo.com/corrida/index.html")

        pagina = self.client.get("/jogos/corrida-maluca/", HTTP_HOST="testserver")
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "Corrida Maluca")

        lista = self.client.get("/site/jogos/", HTTP_HOST=HOST)
        self.assertContains(lista, "Corrida Maluca")
        self.assertContains(lista, "Endereço hospedado")

    def test_http_e_recusado(self):
        resposta = self.enviar(self.dados(endereco="http://jogos.exemplo.com/x.html"))
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("https", resposta.json()["msg"])
        self.assertFalse(JogoCadastrado.objects.exists())

    def test_sem_endereco_e_sem_html_e_recusado(self):
        resposta = self.enviar(self.dados(endereco=""))
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(JogoCadastrado.objects.exists())

    def test_slug_de_jogo_do_simulador_e_recusado(self):
        from core import arena

        resposta = self.enviar(self.dados(slug=arena.JOGOS[0]["slug"]))
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("simulador", resposta.json()["msg"])

    def test_html_binario_e_recusado_e_html_de_verdade_passa(self):
        falso = SimpleUploadedFile("jogo.html", b"\x89PNG\x00\x00binario", content_type="text/html")
        resposta = self.enviar(self.dados(endereco="", arquivo_html=falso))
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("binário", resposta.json()["msg"])

        texto_sem_cara_de_pagina = SimpleUploadedFile("jogo.html", b"so um texto qualquer", content_type="text/html")
        resposta = self.enviar(self.dados(endereco="", arquivo_html=texto_sem_cara_de_pagina))
        self.assertEqual(resposta.status_code, 400)

        resposta = self.enviar(self.dados(endereco="", arquivo_html=SimpleUploadedFile("jogo.html", HTML, content_type="text/html")))
        self.assertEqual(resposta.status_code, 200, resposta.content)
        jogo = JogoCadastrado.objects.get()
        self.assertTrue(jogo.arquivo_html.name.endswith(".html"))
        self.assertTrue(jogo.url_para_jogar)

    def test_apk_que_nao_e_zip_e_recusado(self):
        resposta = self.enviar(self.dados(apk=SimpleUploadedFile("jogo.apk", b"MZ\x90\x00exe", content_type="application/octet-stream")))
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("APK", resposta.json()["msg"])

        resposta = self.enviar(self.dados(apk=SimpleUploadedFile("jogo.apk", APK, content_type="application/vnd.android.package-archive")))
        self.assertEqual(resposta.status_code, 200, resposta.content)
        jogo = JogoCadastrado.objects.get()
        self.assertTrue(jogo.apk)
        self.assertFalse(jogo.liberar_download)
        self.assertEqual(jogo.apk_url, "")  # guardado, mas não sai no site

    def test_arquivo_grande_e_recusado(self):
        from . import views_jogos

        with mock.patch.dict(views_jogos.LIMITES, {"capa": 10}):
            resposta = self.enviar(self.dados())
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("limite", resposta.json()["msg"])

    def test_editar_mantem_os_arquivos_quando_nao_envia_outros(self):
        self.enviar(self.dados())
        jogo = JogoCadastrado.objects.get()
        capa_antes = jogo.capa.name
        resposta = self.enviar({**self.dados(), "id": jogo.pk, "nome": "Corrida Maluca 2", "capa": ""})
        self.assertEqual(resposta.status_code, 200, resposta.content)
        jogo.refresh_from_db()
        self.assertEqual(jogo.nome, "Corrida Maluca 2")
        self.assertEqual(jogo.capa.name, capa_antes)

    def test_ligar_desligar(self):
        self.enviar(self.dados())
        jogo = JogoCadastrado.objects.get()
        resposta = self.enviar({"action": "alternar", "id": jogo.pk})
        self.assertEqual(resposta.json()["status"], "sucesso")
        jogo.refresh_from_db()
        self.assertFalse(jogo.ativo)
        self.assertEqual(self.client.get("/jogos/corrida-maluca/", HTTP_HOST="testserver").status_code, 404)

    def test_excluir_exige_a_palavra_e_apaga_os_arquivos(self):
        self.enviar(self.dados())
        jogo = JogoCadastrado.objects.get()
        nome_da_capa = jogo.capa.name
        self.assertTrue(self.disco.exists(nome_da_capa))

        resposta = self.enviar({"action": "delete", "id": jogo.pk, "confirmacao_exclusao": "sim"})
        self.assertEqual(resposta.status_code, 400)
        self.assertTrue(JogoCadastrado.objects.filter(pk=jogo.pk).exists())

        resposta = self.enviar({"action": "delete", "id": jogo.pk, "confirmacao_exclusao": "confirmar"})
        self.assertEqual(resposta.json()["status"], "sucesso")
        self.assertFalse(JogoCadastrado.objects.filter(pk=jogo.pk).exists())
        self.assertFalse(self.disco.exists(nome_da_capa))

    def test_acao_desconhecida_nao_faz_nada(self):
        resposta = self.enviar({"action": "apagar_tudo"})
        self.assertEqual(resposta.status_code, 400)


class JogosOficiaisNaTelaTests(BaseTela):
    def test_os_jogos_do_simulador_aparecem_com_o_material_e_sem_apk(self):
        from core import arena

        self.client.force_login(self.super)
        pagina = self.client.get("/site/jogos/", HTTP_HOST=HOST)
        for jogo in arena.JOGOS:
            self.assertContains(pagina, jogo["titulo"])
            self.assertContains(pagina, f"/jogos/{jogo['slug']}/")
        self.assertContains(pagina, "Jogos oficiais do simulador")
        self.assertContains(pagina, "Sem APK")
        self.assertContains(pagina, "Lazer &amp; Sport Games")   # o bloco do menu
        self.assertContains(pagina, 'style="--cor: %s"' % arena.JOGOS[0]["cor"])

    def test_a_busca_filtra_os_oficiais_tambem(self):
        self.client.force_login(self.super)
        pagina = self.client.get("/site/jogos/?q=strike", HTTP_HOST=HOST)
        self.assertContains(pagina, "Strike Kids")
        self.assertNotContains(pagina, "Dragon Bowling")


def _zip(nomes):
    import zipfile

    saida = BytesIO()
    with zipfile.ZipFile(saida, "w") as pacote:
        for nome in nomes:
            pacote.writestr(nome, b"x")
    return saida.getvalue()


EXE_GODOT = b"MZ\x90\x00" + b"\x00" * 200 + b"\x10\x00\x00\x00\x00\x00\x00\x00GDPC"


class VersaoParaComputadorTests(BaseTela):
    """O jogo que só tem a versão de PC: guardado, reconhecido, fora do site."""

    def test_exe_de_verdade_e_aceito_e_o_godot_reconhecido(self):
        exe = SimpleUploadedFile("corrida.exe", EXE_GODOT, content_type="application/octet-stream")
        resposta = self.enviar(self.dados(endereco="", versao_pc=exe))
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertIn("versão para computador", resposta.json()["msg"])
        jogo = JogoCadastrado.objects.get()
        self.assertTrue(jogo.versao_pc.name.endswith(".exe"))
        self.assertEqual(jogo.motor, "godot")
        self.assertTrue(jogo.so_versao_pc)

        lista = self.client.get("/site/jogos/", HTTP_HOST=HOST)
        self.assertContains(lista, "Só para computador")
        self.assertContains(lista, "Godot")
        self.assertContains(lista, "Ainda não joga no site")

    def test_o_jogo_so_de_pc_nao_aparece_no_site(self):
        self.enviar(self.dados(endereco="", versao_pc_link="https://drive.google.com/file/d/abc/view"))
        jogo = JogoCadastrado.objects.get()
        self.assertTrue(jogo.so_versao_pc)
        self.assertEqual(self.client.get("/jogos/corrida-maluca/", HTTP_HOST="testserver").status_code, 404)
        self.assertNotContains(self.client.get("/jogos/", HTTP_HOST="testserver"), "Corrida Maluca")
        # o arquivo de PC nunca vai para a página pública, nem quando o jogo ganha a versão de navegador
        self.enviar({**self.dados(), "id": jogo.pk, "capa": "", "versao_pc_link": jogo.versao_pc_link})
        pagina = self.client.get("/jogos/corrida-maluca/", HTTP_HOST="testserver")
        self.assertEqual(pagina.status_code, 200)
        self.assertNotContains(pagina, "drive.google.com")

    def test_zip_com_a_pasta_do_unity_e_aceito_e_reconhecido(self):
        pacote = SimpleUploadedFile("jogo.zip", _zip(["Jogo/Jogo.exe", "Jogo/UnityPlayer.dll", "Jogo/Jogo_Data/globalgamemanagers"]))
        resposta = self.enviar(self.dados(versao_pc=pacote))
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(JogoCadastrado.objects.get().motor, "unity")

    def test_recusa_exe_falso_zip_sem_exe_e_outros_tipos(self):
        casos = [
            SimpleUploadedFile("virus.exe", b"isto nao e um executavel"),
            SimpleUploadedFile("jogo.zip", _zip(["leia-me.txt", "imagem.png"])),
            SimpleUploadedFile("jogo.zip", b"PK\x03\x04 corrompido"),
            SimpleUploadedFile("jogo.rar", b"Rar!\x1a\x07"),
        ]
        for arquivo in casos:
            with self.subTest(arquivo=arquivo.name):
                resposta = self.enviar(self.dados(versao_pc=arquivo))
                self.assertEqual(resposta.status_code, 400, resposta.content)
                self.assertIn("Versão para computador", resposta.json()["msg"])
        self.assertFalse(JogoCadastrado.objects.exists())

    def test_build_grande_pede_o_link(self):
        exe = SimpleUploadedFile("grande.exe", EXE_GODOT)
        with override_settings(JOGOS_ARQUIVO_MAX_MB=0):
            from . import views_jogos

            with mock.patch.object(views_jogos, "_limite_de_arquivo_grande", return_value=10):
                resposta = self.enviar(self.dados(versao_pc=exe))
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("link", resposta.json()["msg"])

    def test_armazenamento_que_recusa_vira_aviso_e_nao_erro_500(self):
        from cloudinary.exceptions import Error as ErroDoCloudinary

        exe = SimpleUploadedFile("corrida.exe", EXE_GODOT)
        with mock.patch.object(self.disco, "save", side_effect=ErroDoCloudinary("File size too large")):
            resposta = self.enviar(self.dados(endereco="", versao_pc=exe))
        self.assertEqual(resposta.status_code, 400, resposta.content)
        self.assertIn("link", resposta.json()["msg"])
        self.assertFalse(JogoCadastrado.objects.exists())

    def test_sem_nada_para_jogar_nem_versao_pc_continua_recusado(self):
        resposta = self.enviar(self.dados(endereco=""))
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("versão para computador", resposta.json()["msg"])
