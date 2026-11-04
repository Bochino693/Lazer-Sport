"""O objeto 3D (.glb) no cadastro do brinquedo: o Strike Kids é o primeiro.

O que estes testes protegem:

  * o .glb se lê sem abrir o 3D: as cores (variações de material) e as
    medidas de verdade, inclusive no arquivo comprimido (posições
    quantizadas e nós com escala); o que não é .glb é recusado;
  * a migração e o comando ligam os objetos do site ao brinquedo do
    catálogo (pelo nome, sem duplicar) e só cadastram um brinquedo novo
    no Render;
  * a Arena 3D usa o objeto do cadastro (endereço, medidas e código), e o
    "não mostrar na arena" tira;
  * a página do brinquedo ganha o visor 3D só quando há objeto;
  * o painel aceita o .glb, guarda cores e medidas e tira o objeto;
  * antes da migração da tabela (o código novo no ar, o banco ainda não),
    a Arena, a página do brinquedo e o painel abrem sem o 3D, sem erro 500.
"""

import importlib
import json
import struct
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from . import arena
from .cadastro_modelos import achar_no_catalogo, ligar_objeto_3d
from .models import Brinquedos, ObjetoTresD
from . import objetos_3d
from .objetos_3d import ler_glb, ler_glb_do_site, validar_glb

migracao = importlib.import_module("core.migrations.0116_objetos_3d_do_site")


def glb(dados):
    """Um .glb de mentira: só o cabeçalho e o JSON (o que o site lê)."""
    bloco = json.dumps(dados).encode()
    bloco += b" " * (-len(bloco) % 4)
    return struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(bloco)) + struct.pack("<II", len(bloco), 0x4E4F534A) + bloco


def caixa(menor, maior, **acessor):
    return {
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "accessors": [{"min": menor, "max": maior, "componentType": 5126, "type": "VEC3", **acessor}],
    }


class LeituraDoGlbTests(TestCase):
    def test_cores_e_medidas(self):
        dados = caixa([-0.5, 0, -1], [0.5, 2, 1])
        dados["extensions"] = {"KHR_materials_variants": {"variants": [{"name": "Azul"}, {"name": "Rosa"}, {}]}}
        lido = ler_glb(SimpleUploadedFile("m.glb", glb(dados)))
        self.assertEqual(lido["cores"], ["Azul", "Rosa", "Cor 3"])
        # [altura, largura, profundidade]
        self.assertEqual(lido["medidas"], [2.0, 1.0, 2.0])

    def test_no_com_escala_giro_e_filhos(self):
        dados = caixa([0, 0, 0], [1, 1, 1])
        # o pai dobra o tamanho; o filho (a malha) gira 90° em y
        dados["nodes"] = [
            {"scale": [2, 2, 2], "children": [1]},
            {"mesh": 0, "rotation": [0, 0.7071068, 0, 0.7071068], "translation": [3, 0, 0]},
        ]
        self.assertEqual(ler_glb(SimpleUploadedFile("m.glb", glb(dados)))["medidas"], [2.0, 2.0, 2.0])

    def test_posicoes_quantizadas(self):
        # o gltfpack grava as posições em inteiros e põe a escala no nó
        dados = caixa([0, 0, 0], [65535, 32767, 65535], componentType=5123, normalized=True)
        dados["nodes"][0]["scale"] = [4, 3, 2]
        dados["accessors"][0]["componentType"] = 5123
        self.assertEqual(ler_glb(SimpleUploadedFile("m.glb", glb(dados)))["medidas"], [1.5, 4.0, 2.0])

    def test_os_objetos_do_site_tem_as_medidas_de_verdade(self):
        self.assertEqual(ler_glb_do_site("site/arena/modelos/strike-kids.glb")["medidas"], [2.07, 0.74, 1.91])
        for modelo in arena.MODELOS_3D:
            self.assertEqual(ler_glb_do_site(modelo["arquivo"])["medidas"], list(modelo["medidas"]), modelo["id"])
        self.assertEqual(ler_glb_do_site("site/nao-existe.glb"), {"cores": [], "medidas": []})

    def test_recusa_o_que_nao_e_glb(self):
        with self.assertRaises(ValidationError):
            validar_glb(SimpleUploadedFile("foto.png", b"\x89PNG" + b"0" * 40))
        with self.assertRaises(ValidationError):
            validar_glb(SimpleUploadedFile("falso.glb", b"0" * 40))
        with self.assertRaises(ValidationError):
            validar_glb(SimpleUploadedFile("curto.glb", b"glTF"))
        grande = SimpleUploadedFile("grande.glb", glb(caixa([0, 0, 0], [1, 1, 1])))
        grande.size = 11 * 1024 * 1024
        with self.assertRaises(ValidationError):
            validar_glb(grande)


class LigacaoTests(TestCase):
    def test_acha_pelo_nome_e_liga_sem_duplicar(self):
        Brinquedos.objects.create(nome_brinquedo="Air Game", descricao="x", avaliacao=5)
        boliche = Brinquedos.objects.create(nome_brinquedo="Boliche Kids (Strike)", descricao="x", avaliacao=5)
        self.assertEqual(achar_no_catalogo("strike-kids", Brinquedos), boliche)
        ligar_objeto_3d("strike-kids", boliche, ObjetoTresD)
        ligar_objeto_3d("strike-kids", boliche, ObjetoTresD)
        objeto = ObjetoTresD.objects.get()
        self.assertEqual((objeto.brinquedo, objeto.codigo), (boliche, "strike-kids"))
        self.assertEqual(objeto.medidas, [2.07, 0.74, 1.91])
        self.assertIn("site/arena/modelos/strike-kids.glb", objeto.url)
        self.assertTrue(finders.find(objeto.arquivo_estatico))

    def test_migracao_liga_o_que_ja_esta_no_catalogo_e_nao_cria_fora_do_render(self):
        from django.apps import apps

        strike = Brinquedos.objects.create(nome_brinquedo="Strike Kids Boliche", descricao="x", avaliacao=5)
        migracao.Migration.operations[0].code(apps, None)
        self.assertEqual(strike.objeto_3d.codigo, "strike-kids")
        # os que não estão no catálogo não são cadastrados fora do Render
        self.assertEqual(Brinquedos.objects.count(), 1)
        self.assertEqual(ObjetoTresD.objects.count(), 1)


class NaArenaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.strike = Brinquedos.objects.create(
            nome_brinquedo="Strike Kids Boliche", descricao="x", avaliacao=5, voltz="220v",
            altura_m=2, largura_m=1, profundidade_m=3.5,
        )

    def maquina(self):
        maquinas = self.client.get(reverse("arena")).context["arena_dados"]["maquinas"]
        return next(m for m in maquinas if m["nome"] == "Strike Kids Boliche")

    def test_sem_objeto_e_volume_das_fotos(self):
        self.assertEqual(self.maquina()["modelo"], "")

    def test_com_objeto_vai_o_glb_nas_medidas_dele(self):
        ligar_objeto_3d("strike-kids", self.strike, ObjetoTresD)
        dados = self.maquina()
        self.assertIn("site/arena/modelos/strike-kids.glb", dados["modelo"])
        self.assertEqual(dados["modelo_id"], "strike-kids")
        self.assertEqual(dados["medidas_modelo"], [2.07, 0.74, 1.91])
        self.assertContains(self.client.get(reverse("arena")), "site/arena/cores3d.js")

    def test_fora_da_arena_quando_pedido(self):
        objeto = ligar_objeto_3d("strike-kids", self.strike, ObjetoTresD)
        objeto.exibir_na_arena = False
        objeto.save()
        self.assertEqual(self.maquina()["modelo"], "")

    def test_codigo_do_espaco_continua_no_reino(self):
        espaco = Brinquedos.objects.create(nome_brinquedo="Espaço Esportivo Modelo 1", descricao="x", avaliacao=5)
        ligar_objeto_3d("espaco-esportivo-modelo-1", espaco, ObjetoTresD)
        maquinas = self.client.get(reverse("arena")).context["arena_dados"]["maquinas"]
        dados = next(m for m in maquinas if m["nome"] == "Espaço Esportivo Modelo 1")
        self.assertEqual((dados["grupo"], dados["reino"]), ("esportivos", True))
        self.assertEqual({j["slug"] for j in dados["jogos_no_espaco"]}, {"swish-arena", "gol-flash-arena"})


class PaginaDoBrinquedoTests(TestCase):
    def setUp(self):
        self.strike = Brinquedos.objects.create(nome_brinquedo="Strike Kids Boliche", descricao="x", avaliacao=5)
        self.url = reverse("brinquedo_detalhe", args=[self.strike.pk])

    def test_visor_so_com_objeto(self):
        resposta = self.client.get(self.url)
        self.assertNotContains(resposta, "data-visor3d")
        self.assertNotContains(resposta, "visor3d.js")
        ligar_objeto_3d("strike-kids", self.strike, ObjetoTresD)
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "data-visor3d-abrir")
        self.assertContains(resposta, "site/arena/visor3d.js")
        self.assertContains(resposta, "site/arena/modelos/strike-kids.glb")

    def test_objeto_desligado_nao_aparece(self):
        objeto = ligar_objeto_3d("strike-kids", self.strike, ObjetoTresD)
        objeto.ativo = False
        objeto.save()
        self.assertNotContains(self.client.get(self.url), "data-visor3d")


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class PainelTests(TestCase):
    def setUp(self):
        admin = User.objects.create_superuser(username="gestor", email="gestor@exemplo.com", password="senha-forte-123")
        self.client.force_login(admin)
        self.url = reverse("brinquedos_admin", urlconf="sistema_interno.urls")
        self.brinquedo = Brinquedos.objects.create(
            nome_brinquedo="Máquina Nova", descricao="x", avaliacao=5, imagem_brinquedo="brinquedos/capa.webp",
        )
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        disco = mock.patch.object(ObjetoTresD._meta.get_field("arquivo"), "storage", FileSystemStorage(location=self.pasta.name))
        disco.start()
        self.addCleanup(disco.stop)

    def salvar(self, **extra):
        dados = {"action": "save", "id": self.brinquedo.pk, "nome_brinquedo": "Máquina Nova", "descricao": "x", **extra}
        return self.client.post(self.url, dados, HTTP_HOST="interno.testserver", HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def test_envia_o_glb_e_guarda_cores_e_medidas(self):
        dados = caixa([0, 0, 0], [0.8, 1.9, 1.2])
        dados["extensions"] = {"KHR_materials_variants": {"variants": [{"name": "Verde"}, {"name": "Azul"}]}}
        resposta = self.salvar(objeto_3d=SimpleUploadedFile("maquina.glb", glb(dados), "model/gltf-binary"))
        self.assertLess(resposta.status_code, 400, resposta.content[:300])
        objeto = ObjetoTresD.objects.get(brinquedo=self.brinquedo)
        self.assertEqual(objeto.cores, ["Verde", "Azul"])
        self.assertEqual(objeto.medidas, [1.9, 0.8, 1.2])
        self.assertTrue(objeto.arquivo.name.endswith(".glb"))
        # e o modal mostra o objeto
        lista = self.client.get(self.url, HTTP_HOST="interno.testserver")
        self.assertContains(lista, "maquina")
        # tirar o objeto apaga o arquivo enviado
        self.salvar(remover_objeto_3d="on")
        self.assertFalse(ObjetoTresD.objects.filter(brinquedo=self.brinquedo).exists())

    def test_recusa_arquivo_que_nao_e_glb(self):
        resposta = self.salvar(objeto_3d=SimpleUploadedFile("maquina.glb", b"nao sou um glb" * 4))
        self.assertIn("Objeto 3D", resposta.content.decode())
        self.assertFalse(ObjetoTresD.objects.exists())

    def test_tirar_o_objeto_do_site_so_desliga(self):
        ligar_objeto_3d("strike-kids", self.brinquedo, ObjetoTresD)
        self.salvar(remover_objeto_3d="on")
        objeto = ObjetoTresD.objects.get(brinquedo=self.brinquedo)
        self.assertFalse(objeto.ativo)


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class AntesDaMigracaoTests(TestCase):
    """Sem a tabela dos objetos 3D, nenhuma tela a consulta (e nada cai)."""

    def setUp(self):
        cache.clear()
        self.strike = Brinquedos.objects.create(
            nome_brinquedo="Strike Kids Boliche", descricao="x", avaliacao=5,
            imagem_brinquedo="brinquedos/capa.webp",
        )
        ligar_objeto_3d("strike-kids", self.strike, ObjetoTresD)
        sem_tabela = mock.patch.object(objetos_3d, "tabela_pronta", return_value=False)
        sem_tabela.start()
        self.addCleanup(sem_tabela.stop)

    def sem_consultar_a_tabela(self, *args, **kwargs):
        with CaptureQueriesContext(connection) as consultas:
            resposta = self.client.get(*args, **kwargs)
        self.assertEqual(resposta.status_code, 200)
        tabela = ObjetoTresD._meta.db_table
        self.assertFalse([q["sql"] for q in consultas if tabela in q["sql"]])
        return resposta

    def test_arena_e_pagina_abrem_sem_o_3d(self):
        resposta = self.sem_consultar_a_tabela(reverse("arena"))
        dados = next(m for m in resposta.context["arena_dados"]["maquinas"] if m["nome"] == "Strike Kids Boliche")
        self.assertEqual(dados["modelo"], "")
        resposta = self.sem_consultar_a_tabela(reverse("brinquedo_detalhe", args=[self.strike.pk]))
        self.assertNotContains(resposta, "data-visor3d")

    def test_painel_abre_e_salva_sem_o_3d(self):
        admin = User.objects.create_superuser(username="gestor", email="gestor@exemplo.com", password="senha-forte-123")
        self.client.force_login(admin)
        url = reverse("brinquedos_admin", urlconf="sistema_interno.urls")
        self.sem_consultar_a_tabela(url, HTTP_HOST="interno.testserver")
        dados = {"action": "save", "id": self.strike.pk, "nome_brinquedo": "Strike Kids Boliche", "descricao": "y"}
        resposta = self.client.post(url, dados, HTTP_HOST="interno.testserver", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertIn("sucesso", resposta.content.decode())
        # enviar um .glb antes da migração avisa o que fazer (e não cai)
        dados["objeto_3d"] = SimpleUploadedFile("m.glb", glb(caixa([0, 0, 0], [1, 1, 1])))
        resposta = self.client.post(url, dados, HTTP_HOST="interno.testserver", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertIn("migrate", resposta.content.decode())


class TabelaProntaTests(TestCase):
    def test_acha_a_tabela_criada_pela_migracao(self):
        objetos_3d._tabela.update(pronta=False, conferida=0.0)
        self.assertTrue(objetos_3d.tabela_pronta())
        self.assertEqual(objetos_3d.prefetch_do_objeto(), ("objeto_3d",))
