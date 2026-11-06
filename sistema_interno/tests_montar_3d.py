"""Montar em 3D (/site/objetos-3d/montar/): a montagem peça por peça, como num CAD.

O que se garante: só o superadministrador entra; a montagem guarda as peças
conferidas (tipo conhecido, números dentro da faixa, cor válida) e o .glb
exportado; as medidas mais usadas viram atalhos (a biblioteca aprende pelo
uso); e as peças que se repetem num arquivo da fábrica aparecem para guardar
(a biblioteca aprende com os arquivos).
"""
import json
import shutil
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from core.models import MontagemTresD
from core.tests_objetos_3d import caixa, glb

from .utils import PALAVRA_CONFIRMACAO_EXCLUSAO
from .views_montar_3d import aprendido_das_montagens, limpar_pecas, mais_usadas

HOST = "interno.testserver"


def coluna(x, altura=3.5):
    return {"tipo": "coluna", "p": [x, 0, 0], "r": 0, "d": {"altura": altura, "diametro": 0.12}, "cor": "#2563EB"}


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class MontarTests(TestCase):
    def setUp(self):
        pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, pasta, ignore_errors=True)
        self.disco = FileSystemStorage(location=pasta, base_url="/media/")
        trocar = mock.patch.object(MontagemTresD._meta.get_field("arquivo"), "storage", self.disco)
        trocar.start()
        self.addCleanup(trocar.stop)
        self.super = User.objects.create_superuser("chefe", "chefe@example.com", "senha-segura")

    def enviar(self, dados, user=None):
        self.client.force_login(user or self.super)
        return self.client.post("/site/objetos-3d/montar/", dados, HTTP_HOST=HOST, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def test_so_o_superadministrador(self):
        comum = User.objects.create_user("comum", password="senha-segura", is_staff=True)
        self.client.force_login(comum)
        self.assertNotEqual(self.client.get("/site/objetos-3d/montar/", HTTP_HOST=HOST).status_code, 200)
        self.client.force_login(self.super)
        tela = self.client.get("/site/objetos-3d/montar/", HTTP_HOST=HOST)
        self.assertContains(tela, 'id="montar3d"')
        self.assertContains(tela, "GLTFExporter.js")

    def test_guardar_com_o_glb_e_reabrir(self):
        arquivo = SimpleUploadedFile("montagem.glb", glb(caixa([-1, 0, -1], [1, 3.5, 1])), content_type="model/gltf-binary")
        resposta = self.enviar({"action": "salvar", "nome": "Torre do shopping", "medidas": "[3.5, 2, 2]",
                                "pecas": json.dumps([coluna(0), coluna(1.5)]), "arquivo": arquivo})
        dados = resposta.json()
        self.assertEqual(dados["status"], "sucesso", dados)
        montagem = MontagemTresD.objects.get(pk=dados["id"])
        self.assertEqual(len(montagem.pecas), 2)
        self.assertEqual(montagem.pecas[0]["cor"], "#2563eb")
        self.assertEqual(montagem.medidas, [3.5, 2.0, 2.0])
        self.assertTrue(self.disco.exists(montagem.arquivo.name))
        self.client.force_login(self.super)
        tela = self.client.get(f"/site/objetos-3d/montar/?m={montagem.pk}", HTTP_HOST=HOST)
        self.assertContains(tela, "Torre do shopping")

    def test_sem_nome_ou_sem_pecas_nao_guarda(self):
        self.assertEqual(self.enviar({"action": "salvar", "nome": "", "pecas": json.dumps([coluna(0)])}).status_code, 400)
        self.assertEqual(self.enviar({"action": "salvar", "nome": "Vazia", "pecas": "[]"}).status_code, 400)

    def test_pecas_sao_conferidas(self):
        limpas = limpar_pecas(json.dumps([
            coluna(0),
            {"tipo": "foguete", "p": [0, 0, 0]},                         # tipo desconhecido: sai
            {"tipo": "coluna", "p": [9999, 0, 0], "d": {"altura": -4, "veneno": 3}},  # números presos na faixa
            {"tipo": "modulo", "ref": "abc"},                             # referência inválida: sai
            {"tipo": "modulo", "ref": 7, "p": [1, 0, 1], "s": 2},
            {"tipo": "plataforma", "cor": "javascript:alert(1)", "d": {"largura": 2}},
        ]))
        self.assertEqual([p["tipo"] for p in limpas], ["coluna", "coluna", "modulo", "plataforma"])
        self.assertEqual(limpas[1]["p"][0], 500)
        self.assertEqual(limpas[1]["d"], {"altura": 0.01})
        self.assertEqual(limpas[2], {"tipo": "modulo", "p": [1.0, 0.0, 1.0], "r": 0.0, "ref": 7, "s": 2.0})
        self.assertNotIn("cor", limpas[3])

    def test_pecas_novas_e_medidas_especiais(self):
        limpas = limpar_pecas(json.dumps([
            {"tipo": "toboga", "p": [0, 0, 0], "d": {"altura": 2.5, "raio": 1, "voltas": 99, "fechado": 7, "espelhado": "x"}},
            {"tipo": "rolos", "d": {"altura": 0.8, "largura": 0.95, "quantidade": 3.6}},
            {"tipo": "plataforma", "d": {"largura": 1.0}, "cor": "#FF0000", "cor2": "#00FF00"},
            {"tipo": "coluna", "d": {"altura": 3}, "cor2": "#00ff00"},              # coluna não tem segunda cor
            {"tipo": "rede", "d": {"largura": 1, "altura": 1}, "cor2": "url(x)"},    # cor inválida: sai
            {"tipo": "objeto", "ref": 4, "tema": "#22C55E"},
            {"tipo": "parede_curva", "d": {"largura": 2, "altura": 3}},
            {"tipo": "led", "d": {"comprimento": 1.05}},
        ]))
        self.assertEqual(limpas[0]["d"], {"altura": 2.5, "raio": 1.0, "voltas": 6.0, "fechado": 1, "espelhado": 0})
        self.assertEqual(limpas[1]["d"]["quantidade"], 4)
        self.assertEqual(limpas[2]["cor2"], "#00ff00")
        self.assertNotIn("cor2", limpas[3])
        self.assertNotIn("cor2", limpas[4])
        self.assertEqual(limpas[5]["tema"], "#22c55e")
        self.assertEqual([p["tipo"] for p in limpas[6:]], ["parede_curva", "led"])

    def test_o_projetista_aprende_o_modulo_e_os_pisos(self):
        def torre(x, largura=1.01, passo=0.9):
            return [{"tipo": "plataforma", "p": [x, n * passo - 0.05, 0], "d": {"largura": largura, "profundidade": largura, "espessura": 0.05}}
                    for n in (1, 2, 3)]
        self.assertEqual(aprendido_das_montagens(), {"vezes": 0})
        for nome in ("A", "B"):
            MontagemTresD.objects.create(nome=nome, pecas=torre(0) + torre(1.05))
        self.assertNotIn("modulo", aprendido_das_montagens())  # duas montagens ainda não ensinam
        MontagemTresD.objects.create(nome="C", pecas=torre(0, 1.21, 0.8))
        aprendido = aprendido_das_montagens()
        self.assertEqual(aprendido["vezes"], 3)
        self.assertEqual(aprendido["modulo"], 1.05)
        self.assertEqual(aprendido["nivel"], 0.9)
        self.client.force_login(self.super)
        tela = self.client.get("/site/objetos-3d/montar/", HTTP_HOST=HOST)
        self.assertContains(tela, '"modulo": 1.05')
        self.assertContains(tela, "montar3d-gerador.js")
        self.assertContains(tela, 'id="modalGerar"')

    def test_mais_usadas_aprende_pelo_uso(self):
        MontagemTresD.objects.create(nome="A", pecas=[coluna(0), coluna(1), coluna(2, 2.0)])
        MontagemTresD.objects.create(nome="B", pecas=[coluna(0)])
        atalhos = mais_usadas()
        self.assertEqual(atalhos[0]["tipo"], "coluna")
        self.assertEqual(atalhos[0]["d"]["altura"], 3.5)
        self.assertEqual(atalhos[0]["vezes"], 3)
        self.assertNotIn(2.0, [a["d"]["altura"] for a in atalhos])  # usada uma vez só: ainda não é atalho

    def test_aprender_as_pecas_que_se_repetem_num_3ds(self):
        # 4 colunas iguais (12 triângulos cada) e uma peça diferente
        vertices, faces = [], []
        def caixa_3ds(x0, z0, l, p, a):
            base = len(vertices)
            for dx in (0, l):
                for dy in (0, p):
                    for dz in (0, a):
                        vertices.append((x0 + dx, z0 + dy, dz))
            for f in ((0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)):
                faces.append(tuple(base + i for i in f))
        import struct
        def bloco(cid, corpo):
            return struct.pack("<HI", cid, 6 + len(corpo)) + corpo
        objetos = b""
        for i, (x, l, p, a) in enumerate([(0, 120, 120, 3500), (1500, 120, 120, 3500), (3000, 120, 120, 3500), (4500, 120, 120, 3500), (0, 1500, 1500, 60)]):
            vertices.clear(); faces.clear()
            caixa_3ds(x, 0, l, p, a)
            verts = struct.pack("<H", len(vertices)) + b"".join(struct.pack("<3f", *v) for v in vertices)
            fcs = struct.pack("<H", len(faces)) + b"".join(struct.pack("<4H", *f, 0) for f in faces)
            objetos += bloco(0x4000, f"obj{i}\0".encode() + bloco(0x4100, bloco(0x4110, verts) + bloco(0x4120, fcs)))
        dados_3ds = bloco(0x4D4D, bloco(0x3D3D, objetos))
        resposta = self.enviar({"action": "aprender", "arquivo3d": SimpleUploadedFile("fabrica.3ds", dados_3ds)})
        dados = resposta.json()
        self.assertEqual(dados["status"], "sucesso", dados)
        self.assertEqual(len(dados["pecas"]), 1)
        peca = dados["pecas"][0]
        self.assertEqual(peca["vezes"], 4)
        self.assertEqual(peca["categoria"], "torre")
        self.assertTrue(peca["nome"].startswith("Coluna 3,50"))
        self.assertEqual(peca["medidas"][0], 3.5)

    def test_aprender_pede_um_formato_com_pecas_separadas(self):
        resposta = self.enviar({"action": "aprender", "arquivo3d": SimpleUploadedFile("x.stl", b"solid x\nendsolid x\n")})
        self.assertEqual(resposta.status_code, 400)

    def test_apagar_pede_confirmacao(self):
        montagem = MontagemTresD.objects.create(nome="Apagar", pecas=[coluna(0)])
        self.assertEqual(self.enviar({"action": "apagar", "id": montagem.pk}).status_code, 400)
        resposta = self.enviar({"action": "apagar", "id": montagem.pk, "confirmacao_exclusao": PALAVRA_CONFIRMACAO_EXCLUSAO})
        self.assertEqual(resposta.json()["status"], "sucesso")
        self.assertFalse(MontagemTresD.objects.filter(pk=montagem.pk).exists())
