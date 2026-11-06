"""A janela "Criar objeto 3D" do painel (/site/objetos-3d/) e o 3D na ficha do projeto.

O que se garante: a prévia sai das fotos, das fotos de um projeto ou de um
arquivo 3D sem gravar nada; gravar leva o .glb da prévia para um ou vários
brinquedos e para o projeto, com o produto parecido da loja (o paralelo);
os dados do projeto trazem as fotos com a vista provável e as sugestões da
loja; tirar o 3D do projeto exige a confirmação; e a ficha do projeto no
site ganha "Ver em 3D" e "Este projeto na loja".
"""
import io
import json
import shutil
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image, ImageDraw

from core.models import (
    Brinquedos,
    BrinquedosProjeto,
    ImagemProjetoBrinquedo,
    ObjetoTresD,
    ObjetoTresDProjeto,
    Projetos,
)
from core.objetos_3d import ler_glb
from core.tests_criar_3d import CUBO_OBJ

from .utils import PALAVRA_CONFIRMACAO_EXCLUSAO

HOST = "interno.testserver"


def png(caixa=(60, 40, 340, 260)):
    imagem = Image.new("RGB", (400, 300), (250, 250, 250))
    ImageDraw.Draw(imagem).rectangle(caixa, fill=(30, 120, 220))
    saida = io.BytesIO()
    imagem.save(saida, "PNG")
    return saida.getvalue()


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class BaseCriar(TestCase):
    def setUp(self):
        pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, pasta, ignore_errors=True)
        self.disco = FileSystemStorage(location=pasta, base_url="/media/")
        for modelo, campo in ((ObjetoTresD, "arquivo"), (ObjetoTresDProjeto, "arquivo"), (ImagemProjetoBrinquedo, "imagem")):
            trocar = mock.patch.object(modelo._meta.get_field(campo), "storage", self.disco)
            trocar.start()
            self.addCleanup(trocar.stop)
        self.super = User.objects.create_superuser("chefe", "chefe@example.com", "senha-segura")
        self.brinquedao = Brinquedos.objects.create(
            nome_brinquedo="Brinquedão Playground 3 Torres", descricao="Playground com tobogã e piscina de bolinhas",
            avaliacao=5, voltz="220V", altura_m=3.2, largura_m=6, profundidade_m=4,
        )
        self.pebolim = Brinquedos.objects.create(nome_brinquedo="Pebolim", descricao="mesa de pebolim", avaliacao=4, voltz="110V")
        self.projetado = BrinquedosProjeto.objects.create(nome_brinquedo_projeto="Playground do shopping", descricao="Parquinho com tobogã")
        self.projeto = Projetos.objects.create(
            titulo="Playground Indoor do Shopping",
            descricao="Playground com tobogã e piscina de bolinhas. Medidas: 6 x 4 x 3,2 m",
            brinquedo_projetado=self.projetado,
        )
        self.foto_frente = ImagemProjetoBrinquedo(brinquedo=self.projetado, legenda="Vista frontal")
        self.foto_frente.imagem.save("frente.png", ContentFile(png()), save=True)
        self.foto_lado = ImagemProjetoBrinquedo(brinquedo=self.projetado, legenda="Lateral direita")
        self.foto_lado.imagem.save("lado.png", ContentFile(png((150, 40, 250, 260))), save=True)

    def enviar(self, dados, user=None):
        self.client.force_login(user or self.super)
        return self.client.post("/site/objetos-3d/", dados, HTTP_HOST=HOST, HTTP_X_REQUESTED_WITH="XMLHttpRequest")


class PreviaTests(BaseCriar):
    def test_previa_pelas_fotos_nao_grava_nada(self):
        resposta = self.enviar({
            "action": "gerar", "origem": "fotos", "modo": "volume", "recortar": "on", "altura": "2,2",
            "foto_frente": SimpleUploadedFile("f.png", png(), content_type="image/png"),
        })
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Content-Type"], "model/gltf-binary")
        info = json.loads(resposta["X-Objeto3D-Info"])
        self.assertEqual(info["medidas"][0], 2.2)
        self.assertEqual(info["modo"], "volume")
        self.assertEqual(ler_glb(io.BytesIO(resposta.content))["medidas"][0], 2.2)
        self.assertFalse(ObjetoTresD.objects.exists())

    def test_previa_pelas_fotos_do_projeto(self):
        vistas = {str(self.foto_frente.pk): "frente", str(self.foto_lado.pk): "direita"}
        resposta = self.enviar({"action": "gerar", "origem": "projeto", "projeto": self.projetado.pk,
                                "vistas": json.dumps(vistas), "modo": "paineis", "recortar": "on", "altura": "3"})
        self.assertEqual(resposta.status_code, 200, resposta.content[:300])
        self.assertEqual(json.loads(resposta["X-Objeto3D-Info"])["vistas"], ["frente", "direita"])

    def test_duas_fotos_na_mesma_vista_e_recusado(self):
        vistas = {str(self.foto_frente.pk): "frente", str(self.foto_lado.pk): "frente"}
        resposta = self.enviar({"action": "gerar", "origem": "projeto", "projeto": self.projetado.pk, "vistas": json.dumps(vistas)})
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("Duas fotos", resposta.json()["msg"])

    def test_previa_de_um_arquivo_3d(self):
        resposta = self.enviar({"action": "gerar", "origem": "arquivo", "eixo": "auto", "unidade": "auto", "limpar": "on",
                                "arquivo3d": SimpleUploadedFile("cubo.obj", CUBO_OBJ)})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(json.loads(resposta["X-Objeto3D-Info"])["medidas"], [3.0, 2.0, 1.0])

    def test_formato_que_nao_abre_volta_o_caminho(self):
        resposta = self.enviar({"action": "gerar", "origem": "arquivo", "arquivo3d": SimpleUploadedFile("p.skp", b"x")})
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("COLLADA", resposta.json()["msg"])

    def test_so_o_superadministrador(self):
        comum = User.objects.create_user("comum", password="senha-segura", is_staff=True)
        resposta = self.enviar({"action": "gerar", "origem": "fotos"}, user=comum)
        self.assertNotEqual(resposta.status_code, 200)


class ProjetoDadosTests(BaseCriar):
    def test_fotos_com_a_vista_e_o_produto_parecido(self):
        resposta = self.enviar({"action": "projeto_dados", "projeto": self.projetado.pk})
        dados = resposta.json()
        self.assertEqual(dados["status"], "sucesso")
        self.assertEqual([f["vista"] for f in dados["fotos"]], ["frente", "direita"])
        self.assertEqual(dados["medidas"], {"largura": 6.0, "profundidade": 4.0, "altura": 3.2})
        self.assertEqual(dados["sugestoes"][0]["id"], self.brinquedao.pk)
        self.assertNotIn(self.pebolim.pk, [s["id"] for s in dados["sugestoes"]])

    def test_guardar_so_o_paralelo(self):
        resposta = self.enviar({"action": "projeto_paralelo", "projeto": self.projetado.pk, "produto": self.brinquedao.pk})
        self.assertEqual(resposta.json()["status"], "sucesso")
        objeto = ObjetoTresDProjeto.objects.get(projeto=self.projetado)
        self.assertEqual(objeto.produto, self.brinquedao)
        self.assertFalse(objeto.arquivo)


class GravarTests(BaseCriar):
    def glb(self):
        resposta = self.enviar({"action": "gerar", "origem": "arquivo", "arquivo3d": SimpleUploadedFile("cubo.obj", CUBO_OBJ)})
        return SimpleUploadedFile("objeto-3d.glb", resposta.content, content_type="model/gltf-binary")

    def test_grava_em_varios_brinquedos_e_no_projeto(self):
        resposta = self.enviar({
            "action": "gerado_salvar", "arquivo": self.glb(), "brinquedos": [self.brinquedao.pk, self.pebolim.pk],
            "projeto": self.projetado.pk, "produto": self.brinquedao.pk, "exibir_na_arena": "on",
            "origem": "arquivo", "modo": "arquivo",
        })
        self.assertEqual(resposta.json()["status"], "sucesso", resposta.content)
        for brinquedo in (self.brinquedao, self.pebolim):
            objeto = ObjetoTresD.objects.get(brinquedo=brinquedo)
            self.assertEqual(objeto.medidas, [3.0, 2.0, 1.0])
            self.assertTrue(self.disco.exists(objeto.arquivo.name))
        do_projeto = ObjetoTresDProjeto.objects.get(projeto=self.projetado)
        self.assertEqual(do_projeto.produto, self.brinquedao)
        self.assertEqual(do_projeto.modo, "arquivo")
        self.assertTrue(self.disco.exists(do_projeto.arquivo.name))

    def test_sem_destino_nao_grava(self):
        resposta = self.enviar({"action": "gerado_salvar", "arquivo": self.glb()})
        self.assertEqual(resposta.status_code, 400)

    def test_trocar_apaga_o_arquivo_antigo(self):
        self.enviar({"action": "gerado_salvar", "arquivo": self.glb(), "projeto": self.projetado.pk})
        antigo = ObjetoTresDProjeto.objects.get(projeto=self.projetado).arquivo.name
        self.enviar({"action": "gerado_salvar", "arquivo": self.glb(), "projeto": self.projetado.pk})
        novo = ObjetoTresDProjeto.objects.get(projeto=self.projetado).arquivo.name
        self.assertNotEqual(antigo, novo)
        self.assertFalse(self.disco.exists(antigo))

    def test_apagar_o_3d_do_projeto_pede_confirmacao_e_guarda_o_paralelo(self):
        self.enviar({"action": "gerado_salvar", "arquivo": self.glb(), "projeto": self.projetado.pk, "produto": self.brinquedao.pk})
        nome = ObjetoTresDProjeto.objects.get(projeto=self.projetado).arquivo.name
        sem = self.enviar({"action": "delete", "id": f"projeto3d-{self.projetado.pk}"})
        self.assertEqual(sem.status_code, 400)
        com = self.enviar({"action": "delete", "id": f"projeto3d-{self.projetado.pk}", "confirmacao_exclusao": PALAVRA_CONFIRMACAO_EXCLUSAO})
        self.assertEqual(com.json()["status"], "sucesso")
        objeto = ObjetoTresDProjeto.objects.get(projeto=self.projetado)
        self.assertFalse(objeto.arquivo)
        self.assertEqual(objeto.produto, self.brinquedao)
        self.assertFalse(self.disco.exists(nome))

    def test_tela_lista_o_projeto_com_3d(self):
        self.enviar({"action": "gerado_salvar", "arquivo": self.glb(), "projeto": self.projetado.pk})
        self.client.force_login(self.super)
        tela = self.client.get("/site/objetos-3d/", HTTP_HOST=HOST)
        self.assertContains(tela, 'id="modalCriar3d"')
        self.assertContains(tela, f'data-ver3d-projeto="{self.projetado.pk}"')


class FichaDoProjetoTests(BaseCriar):
    def test_ficha_ganha_ver_em_3d_e_o_produto_da_loja(self):
        objeto = ObjetoTresDProjeto(projeto=self.projetado, produto=self.brinquedao, modo="paineis")
        objeto.arquivo.save("projeto.glb", ContentFile(b"glb"), save=True)
        pagina = self.client.get("/projetos/", HTTP_HOST="testserver")
        self.assertContains(pagina, 'data-ficha-3d="/media/')
        self.assertContains(pagina, "ls-ficha-3d.js")
        self.assertContains(pagina, "Este projeto na loja")
        self.assertContains(pagina, f"/brinquedo/{self.brinquedao.pk}/")

    def test_ficha_sem_3d_segue_so_com_as_fotos(self):
        pagina = self.client.get("/projetos/", HTTP_HOST="testserver")
        self.assertNotContains(pagina, "data-ficha-3d=")
        self.assertNotContains(pagina, "Este projeto na loja")
