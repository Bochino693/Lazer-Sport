"""Jogos que a equipe sobe pelo painel (JogoCadastrado).

O que se garante: o cadastro recusa o que quebraria a página (slug de um
jogo do simulador, nenhum lugar para jogar, http, cor que não é cor,
arquivo errado); o jogo ativo aparece em /jogos/ e ganha /jogos/<slug>/;
ele roda num quadro isolado que só nasce ao tocar em Jogar; e o APK só
fica à vista quando a equipe libera.
"""
import shutil
from io import BytesIO
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from . import arena
from .models import JogoCadastrado

def _png():
    """Um PNG de verdade (o formulário do painel confere a imagem com o Pillow)."""
    from PIL import Image

    saida = BytesIO()
    Image.new("RGB", (8, 8), (34, 211, 238)).save(saida, format="PNG")
    return saida.getvalue()


PNG = _png()


class BaseJogos(TestCase):
    def setUp(self):
        pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, pasta, ignore_errors=True)
        disco = FileSystemStorage(location=pasta, base_url="/media/")
        for campo in ("capa", "poster", "arquivo_html", "apk"):
            trocar = mock.patch.object(JogoCadastrado._meta.get_field(campo), "storage", disco)
            trocar.start()
            self.addCleanup(trocar.stop)

    def novo(self, **dados):
        base = {
            "nome": "Corrida Maluca",
            "slug": "corrida-maluca",
            "chamada": "Desvie de tudo!",
            "comandos": "Arraste para desviar.",
            "cor": "#22d3ee",
            "endereco": "https://jogos.exemplo.com/corrida/index.html",
            "capa": SimpleUploadedFile("capa.png", PNG, content_type="image/png"),
        }
        base.update(dados)
        return JogoCadastrado(**base)

    def salvo(self, **dados):
        jogo = self.novo(**dados)
        jogo.full_clean()
        jogo.save()
        return jogo


class ValidacaoDoCadastro(BaseJogos):
    def test_um_jogo_completo_passa(self):
        self.novo().full_clean()

    def test_o_slug_de_um_jogo_do_simulador_e_recusado(self):
        slug = arena.JOGOS[0]["slug"]
        with self.assertRaises(ValidationError) as erro:
            self.novo(slug=slug).full_clean()
        self.assertIn("slug", erro.exception.message_dict)

    def test_sem_endereco_e_sem_arquivo_e_recusado(self):
        with self.assertRaises(ValidationError):
            self.novo(endereco="").full_clean()

    def test_endereco_em_http_e_recusado(self):
        with self.assertRaises(ValidationError) as erro:
            self.novo(endereco="http://jogos.exemplo.com/corrida/").full_clean()
        self.assertIn("endereco", erro.exception.message_dict)

    def test_a_cor_precisa_ser_hexadecimal(self):
        for ruim in ("red", "#12345", "#fff; background:url(x)", "#ggg"):
            with self.subTest(cor=ruim), self.assertRaises(ValidationError) as erro:
                self.novo(cor=ruim).full_clean()
            self.assertIn("cor", erro.exception.message_dict)
        for boa in ("#fff", "#22d3ee", "#22d3eecc"):
            with self.subTest(cor=boa):
                self.novo(cor=boa).full_clean()

    def test_o_arquivo_do_jogo_precisa_ser_html(self):
        arquivo = SimpleUploadedFile("jogo.js", b"alert(1)", content_type="text/javascript")
        with self.assertRaises(ValidationError) as erro:
            self.novo(endereco="", arquivo_html=arquivo).full_clean()
        self.assertIn("arquivo_html", erro.exception.message_dict)

    def test_um_html_unico_basta_para_jogar(self):
        arquivo = SimpleUploadedFile("jogo.html", b"<!doctype html><canvas></canvas>", content_type="text/html")
        jogo = self.salvo(endereco="", arquivo_html=arquivo)
        self.assertTrue(jogo.url_para_jogar.endswith(".html"))

    def test_o_download_precisa_ser_apk(self):
        arquivo = SimpleUploadedFile("jogo.exe", b"MZ", content_type="application/octet-stream")
        with self.assertRaises(ValidationError) as erro:
            self.novo(apk=arquivo).full_clean()
        self.assertIn("apk", erro.exception.message_dict)


class NoSite(BaseJogos):
    def test_o_jogo_ativo_aparece_no_simulador(self):
        self.salvo()
        resposta = self.client.get(reverse("jogos"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "bj-capa")
        self.assertContains(resposta, reverse("jogo", args=["corrida-maluca"]))
        self.assertContains(resposta, "Corrida Maluca")

    def test_o_jogo_inativo_fica_fora(self):
        self.salvo(ativo=False)
        self.assertNotContains(self.client.get(reverse("jogos")), "Corrida Maluca")
        self.assertEqual(self.client.get(reverse("jogo", args=["corrida-maluca"])).status_code, 404)

    def test_a_pagina_do_jogo_abre_com_a_capa_e_o_quadro_so_ao_jogar(self):
        self.salvo()
        resposta = self.client.get(reverse("jogo", args=["corrida-maluca"]))
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "jogo_cadastrado.html")
        html = resposta.content.decode()
        self.assertIn("data-jogo-jogar", html)
        self.assertIn('data-jogo-src="https://jogos.exemplo.com/corrida/index.html"', html)
        self.assertIn("jc-palco--paisagem", html)
        self.assertIn("--cor-jogo: #22d3ee", html)
        # o jogo não baixa antes do toque: nada de iframe já na página
        self.assertNotIn("<iframe", html)
        self.assertIn("jogo-cadastrado.js", html)
        # a abertura "LAZER & SPORT GAMES apresenta", com a cor do jogo
        self.assertIn("intro-jogos.js", html)
        self.assertIn('data-jogo-cor="#22d3ee"', html)

    def test_um_slug_desconhecido_continua_404(self):
        self.assertEqual(self.client.get(reverse("jogo", args=["nao-existe"])).status_code, 404)

    def test_os_jogos_do_simulador_seguem_no_ar(self):
        self.salvo()
        slug = arena.JOGOS[0]["slug"]
        self.assertEqual(self.client.get(reverse("jogo", args=[slug])).status_code, 200)

    def test_o_apk_so_aparece_quando_liberado(self):
        apk = SimpleUploadedFile("corrida.apk", b"PK\x03\x04", content_type="application/vnd.android.package-archive")
        jogo = self.salvo(apk=apk)
        url = reverse("jogo", args=["corrida-maluca"])
        self.assertEqual(jogo.apk_url, "")
        self.assertNotContains(self.client.get(url), "Baixar o aplicativo")

        jogo.liberar_download = True
        jogo.save()
        resposta = self.client.get(url)
        self.assertContains(resposta, "Baixar o aplicativo")
        self.assertContains(resposta, jogo.apk.url)

    def test_sem_a_tabela_o_simulador_abre_sem_os_jogos_cadastrados(self):
        self.salvo()
        with mock.patch("core.objetos_3d.tabela_pronta", return_value=False):
            resposta = self.client.get(reverse("jogos"))
        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, "Corrida Maluca")


@override_settings(ALLOWED_HOSTS=["*"])
class NoPainel(BaseJogos):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser("chefe", "chefe@exemplo.com", "senha-forte-123")
        self.client.force_login(self.admin)

    def test_a_lista_e_o_formulario_abrem(self):
        self.salvo()
        lista = self.client.get(reverse("admin:core_jogocadastrado_changelist"))
        self.assertEqual(lista.status_code, 200)
        self.assertContains(lista, "Corrida Maluca")
        novo = self.client.get(reverse("admin:core_jogocadastrado_add"))
        self.assertEqual(novo.status_code, 200)
        self.assertContains(novo, "Foto de capa")
        self.assertContains(novo, "Os arquivos do jogo")

    def test_subir_um_jogo_pelo_painel(self):
        resposta = self.client.post(reverse("admin:core_jogocadastrado_add"), {
            "nome": "Pula Pula",
            "slug": "pula-pula",
            "chamada": "",
            "descricao": "",
            "comandos": "Toque para pular.",
            "cor": "#ff3df2",
            "ordem": "100",
            "ativo": "on",
            "capa": SimpleUploadedFile("capa.png", PNG, content_type="image/png"),
            "endereco": "https://jogos.exemplo.com/pula/",
            "proporcao": JogoCadastrado.RETRATO,
        })
        self.assertEqual(resposta.status_code, 302, getattr(resposta, "context", None) and resposta.context["adminform"].form.errors)
        jogo = JogoCadastrado.objects.get(slug="pula-pula")
        self.assertEqual(jogo.proporcao, JogoCadastrado.RETRATO)
        pagina = self.client.get(reverse("jogo", args=["pula-pula"]))
        self.assertContains(pagina, "jc-palco--retrato")


@override_settings(ALLOWED_HOSTS=["*"], SITE_URL="https://www.lazersport.com.br")
class ConsoleNoSystemTests(BaseJogos):
    """No /system/ a tela do jogo mostra a seção do console e leva ao envio, no painel."""

    def setUp(self):
        super().setUp()
        self.client.force_login(User.objects.create_superuser("chefe", "chefe@exemplo.com", "senha-forte-123"))

    def test_a_tela_do_jogo_tem_a_secao_do_console_e_o_botao_para_anexar(self):
        jogo = self.salvo()
        pagina = self.client.get(reverse("admin:core_jogocadastrado_change", args=[jogo.pk]))
        self.assertContains(pagina, "Jogo de console ou fliperama")
        self.assertContains(pagina, "Anexar os arquivos do jogo")
        self.assertContains(pagina, f"https://interno.lazersport.com.br/site/jogos/?editar={jogo.pk}")
        novo = self.client.get(reverse("admin:core_jogocadastrado_add"))
        self.assertContains(novo, "https://interno.lazersport.com.br/site/jogos/?novo=1")
