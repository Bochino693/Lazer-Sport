"""A tela de objetos 3D do painel (/site/objetos-3d/): só o superadministrador.

O que se garante: a lista mostra cada brinquedo com (ou sem) o seu objeto,
o jogo da máquina e a sugestão do objeto que vem com o site; subir um .glb
lê as cores e as medidas e grava tudo de uma vez (se o banco falhar, o
arquivo não fica órfão); ligar um objeto do site só aceita os que existem;
tirar exige a palavra de confirmação, apaga o enviado e só desliga o do
site, que pode ser religado.
"""
import shutil
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from core.models import Brinquedos, ObjetoTresD
from core.tests_objetos_3d import caixa, glb

from .permissoes import atribuir_funcoes

HOST = "interno.testserver"


def glb_colorido():
    dados = caixa([-0.5, 0, -1], [0.5, 2, 1])
    dados["extensions"] = {"KHR_materials_variants": {"variants": [{"name": "Azul"}, {"name": "Rosa"}]}}
    return SimpleUploadedFile("maquina.glb", glb(dados), content_type="model/gltf-binary")


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class BaseTela(TestCase):
    def setUp(self):
        pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, pasta, ignore_errors=True)
        self.disco = FileSystemStorage(location=pasta, base_url="/media/")
        trocar = mock.patch.object(ObjetoTresD._meta.get_field("arquivo"), "storage", self.disco)
        trocar.start()
        self.addCleanup(trocar.stop)
        self.super = User.objects.create_superuser("chefe", "chefe@example.com", "senha-segura")
        self.criador = User.objects.create_user("criador", password="senha-segura", is_staff=True)
        atribuir_funcoes(self.criador, ["criacao", "gestao"])
        self.strike = Brinquedos.objects.create(nome_brinquedo="Strike Kids", descricao="boliche", avaliacao=5, voltz="220V")
        self.pembolim = Brinquedos.objects.create(nome_brinquedo="Pembolim", descricao="mesa", avaliacao=4, voltz="110V")

    def enviar(self, dados, user=None):
        self.client.force_login(user or self.super)
        return self.client.post("/site/objetos-3d/", dados, HTTP_HOST=HOST, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def abrir(self, user=None):
        self.client.force_login(user or self.super)
        return self.client.get("/site/objetos-3d/", HTTP_HOST=HOST)


class PermissaoTests(BaseTela):
    def test_so_o_superadministrador(self):
        self.assertRedirects(self.client.get("/site/objetos-3d/", HTTP_HOST=HOST), "/login/inner/", fetch_redirect_response=False)
        self.assertEqual(self.abrir(self.criador).status_code, 302)
        self.assertEqual(self.enviar({"action": "salvar", "brinquedo": self.strike.pk}, user=self.criador).status_code, 302)
        self.assertFalse(ObjetoTresD.objects.exists())
        self.client.force_login(self.criador)
        self.assertNotContains(self.client.get("/", HTTP_HOST=HOST), "/site/objetos-3d/")

    def test_lista_mostra_brinquedo_jogo_e_sugestao(self):
        resposta = self.abrir()
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Strike Kids")
        self.assertContains(resposta, "/jogos/strike-kids/")          # a prévia do jogo da máquina
        self.assertContains(resposta, "site/arena/modelos/strike-kids.glb")  # o objeto do site, sugerido
        self.assertContains(resposta, "Pembolim")
        self.assertContains(resposta, 'href="/site/objetos-3d/"')


class CadastroTests(BaseTela):
    def test_sobe_o_glb_le_cores_e_medidas_e_fica_no_ar(self):
        resposta = self.enviar({"action": "salvar", "brinquedo": self.pembolim.pk, "arquivo": glb_colorido(), "exibir_na_arena": "on"})
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertIn("Azul, Rosa", resposta.json()["msg"])
        objeto = ObjetoTresD.objects.get(brinquedo=self.pembolim)
        self.assertEqual(objeto.cores, ["Azul", "Rosa"])
        self.assertEqual(objeto.medidas, [2.0, 1.0, 2.0])
        self.assertTrue(objeto.ativo and objeto.exibir_na_arena)
        self.assertTrue(self.disco.exists(objeto.arquivo.name))

        pagina = self.abrir()
        self.assertContains(pagina, "Azul")
        self.assertContains(pagina, "Ver em 3D")
        # a página pública do brinquedo mostra o botão do 3D
        publica = self.client.get(f"/brinquedo/{self.pembolim.pk}/", HTTP_HOST="testserver")
        self.assertContains(publica, "data-visor3d")

    def test_arquivo_que_nao_e_glb_e_recusado(self):
        resposta = self.enviar({"action": "salvar", "brinquedo": self.pembolim.pk, "arquivo": SimpleUploadedFile("m.txt", b"nada", content_type="text/plain")})
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(ObjetoTresD.objects.exists())

    def test_liga_um_objeto_do_site_e_recusa_caminho_inventado(self):
        resposta = self.enviar({"action": "salvar", "brinquedo": self.strike.pk, "arquivo_estatico": "site/arena/modelos/strike-kids.glb"})
        self.assertEqual(resposta.status_code, 200, resposta.content)
        objeto = ObjetoTresD.objects.get(brinquedo=self.strike)
        self.assertEqual(objeto.arquivo_estatico, "site/arena/modelos/strike-kids.glb")
        self.assertEqual(objeto.codigo, "strike-kids")
        self.assertEqual(objeto.medidas, [2.07, 0.74, 1.91])

        resposta = self.enviar({"action": "salvar", "brinquedo": self.pembolim.pk, "arquivo_estatico": "site/arena/modelos/../../x.glb"})
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(ObjetoTresD.objects.filter(brinquedo=self.pembolim).exists())

    def test_os_dois_ao_mesmo_tempo_ou_nenhum_e_erro(self):
        resposta = self.enviar({"action": "salvar", "brinquedo": self.pembolim.pk, "arquivo": glb_colorido(), "arquivo_estatico": "site/arena/modelos/strike-kids.glb"})
        self.assertEqual(resposta.status_code, 400)
        resposta = self.enviar({"action": "salvar", "brinquedo": self.pembolim.pk})
        self.assertEqual(resposta.status_code, 400)

    def test_se_o_banco_falhar_o_arquivo_nao_fica_orfao(self):
        with mock.patch.object(ObjetoTresD, "save", side_effect=RuntimeError("banco caiu")):
            with self.assertRaises(RuntimeError):
                self.enviar({"action": "salvar", "brinquedo": self.pembolim.pk, "arquivo": glb_colorido()})
        self.assertFalse(ObjetoTresD.objects.exists())
        self.assertEqual(self.disco.listdir("")[1] if self.disco.exists("") else [], [])
        pasta = self.disco.exists("objetos_3d") and self.disco.listdir("objetos_3d")[1]
        self.assertFalse(pasta)

    def test_trocar_apaga_o_arquivo_antigo(self):
        self.enviar({"action": "salvar", "brinquedo": self.pembolim.pk, "arquivo": glb_colorido()})
        antigo = ObjetoTresD.objects.get(brinquedo=self.pembolim).arquivo.name
        self.enviar({"action": "salvar", "brinquedo": self.pembolim.pk, "arquivo": glb_colorido()})
        objeto = ObjetoTresD.objects.get(brinquedo=self.pembolim)
        self.assertNotEqual(objeto.arquivo.name, antigo)
        self.assertFalse(self.disco.exists(antigo))
        self.assertTrue(self.disco.exists(objeto.arquivo.name))

    def test_arena_liga_e_desliga(self):
        self.enviar({"action": "salvar", "brinquedo": self.pembolim.pk, "arquivo": glb_colorido(), "exibir_na_arena": "on"})
        self.enviar({"action": "alternar_arena", "brinquedo": self.pembolim.pk})
        self.assertFalse(ObjetoTresD.objects.get(brinquedo=self.pembolim).exibir_na_arena)
        self.enviar({"action": "alternar_arena", "brinquedo": self.pembolim.pk})
        self.assertTrue(ObjetoTresD.objects.get(brinquedo=self.pembolim).exibir_na_arena)

    def test_tirar_exige_a_palavra_apaga_o_enviado_e_so_desliga_o_do_site(self):
        self.enviar({"action": "salvar", "brinquedo": self.pembolim.pk, "arquivo": glb_colorido()})
        nome = ObjetoTresD.objects.get(brinquedo=self.pembolim).arquivo.name
        resposta = self.enviar({"action": "delete", "id": self.pembolim.pk, "confirmacao_exclusao": "nao"})
        self.assertEqual(resposta.status_code, 400)
        self.assertTrue(ObjetoTresD.objects.filter(brinquedo=self.pembolim).exists())
        resposta = self.enviar({"action": "delete", "id": self.pembolim.pk, "confirmacao_exclusao": "CONFIRMAR"})
        self.assertEqual(resposta.json()["status"], "sucesso")
        self.assertFalse(ObjetoTresD.objects.filter(brinquedo=self.pembolim).exists())
        self.assertFalse(self.disco.exists(nome))

        self.enviar({"action": "salvar", "brinquedo": self.strike.pk, "arquivo_estatico": "site/arena/modelos/strike-kids.glb"})
        self.enviar({"action": "delete", "id": self.strike.pk, "confirmacao_exclusao": "confirmar"})
        objeto = ObjetoTresD.objects.get(brinquedo=self.strike)
        self.assertFalse(objeto.ativo)
        self.assertContains(self.abrir(), "Religar")
        self.enviar({"action": "religar", "brinquedo": self.strike.pk})
        self.assertTrue(ObjetoTresD.objects.get(brinquedo=self.strike).ativo)


class LaboratorioTests(BaseTela):
    """A biblioteca de peças para montar brinquedões (ModuloTresD)."""

    def setUp(self):
        super().setUp()
        from core.models import ModuloTresD

        trocar = mock.patch.object(ModuloTresD._meta.get_field("arquivo"), "storage", self.disco)
        trocar.start()
        self.addCleanup(trocar.stop)

    def test_guarda_uma_peca_com_cores_e_medidas_e_mostra_na_tela(self):
        from core.models import ModuloTresD

        resposta = self.enviar({"action": "modulo_salvar", "nome": "Torre 2 andares", "categoria": "torre", "descricao": "Aço e tela", "arquivo": glb_colorido()})
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertIn("Torre 2 andares", resposta.json()["msg"])
        peca = ModuloTresD.objects.get()
        self.assertEqual((peca.categoria, peca.cores, peca.medidas), ("torre", ["Azul", "Rosa"], [2.0, 1.0, 2.0]))
        self.assertTrue(self.disco.exists(peca.arquivo.name))
        pagina = self.abrir()
        self.assertContains(pagina, "Torre 2 andares")
        self.assertContains(pagina, "Laboratório")
        self.assertContains(pagina, 'data-ver3d-modulo="%d"' % peca.pk)

    def test_recusa_sem_nome_categoria_errada_ou_arquivo_ruim(self):
        from core.models import ModuloTresD

        self.assertEqual(self.enviar({"action": "modulo_salvar", "nome": "", "categoria": "torre", "arquivo": glb_colorido()}).status_code, 400)
        self.assertEqual(self.enviar({"action": "modulo_salvar", "nome": "X", "categoria": "nave", "arquivo": glb_colorido()}).status_code, 400)
        self.assertEqual(self.enviar({"action": "modulo_salvar", "nome": "X", "categoria": "torre", "arquivo": SimpleUploadedFile("x.txt", b"nada")}).status_code, 400)
        self.assertEqual(self.enviar({"action": "modulo_salvar", "nome": "X", "categoria": "torre"}).status_code, 400)
        self.assertFalse(ModuloTresD.objects.exists())

    def test_apagar_exige_a_palavra_e_tira_o_arquivo(self):
        from core.models import ModuloTresD

        self.enviar({"action": "modulo_salvar", "nome": "Rede", "categoria": "rede", "arquivo": glb_colorido()})
        peca = ModuloTresD.objects.get()
        nome = peca.arquivo.name
        self.assertEqual(self.enviar({"action": "delete", "id": f"modulo-{peca.pk}", "confirmacao_exclusao": "nao"}).status_code, 400)
        self.assertTrue(ModuloTresD.objects.filter(pk=peca.pk).exists())
        resposta = self.enviar({"action": "delete", "id": f"modulo-{peca.pk}", "confirmacao_exclusao": "confirmar"})
        self.assertEqual(resposta.json()["status"], "sucesso")
        self.assertFalse(ModuloTresD.objects.exists())
        self.assertFalse(self.disco.exists(nome))

    def test_so_o_superadministrador(self):
        from core.models import ModuloTresD

        self.assertEqual(self.enviar({"action": "modulo_salvar", "nome": "X", "categoria": "torre", "arquivo": glb_colorido()}, user=self.criador).status_code, 302)
        self.assertFalse(ModuloTresD.objects.exists())
