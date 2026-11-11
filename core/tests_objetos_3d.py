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
from io import StringIO
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
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from . import arena
from .cadastro_modelos import CADASTROS, achar_no_catalogo, ligar_objeto_3d
from .models import Brinquedos, ObjetoTresD
from . import objetos_3d
from .objetos_3d import ler_glb, ler_glb_do_site, validar_glb

migracao = importlib.import_module("core.migrations.0116_objetos_3d_do_site")
migracao_strike = importlib.import_module("core.migrations.0117_strike_kids_no_catalogo")


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
        boliche = Brinquedos.objects.create(nome_brinquedo="Boliche Strike Kids Premium", descricao="x", avaliacao=5)
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


class CadastroDoStrikeKidsTests(TestCase):
    """A 0117 cadastra o Strike Kids no banco de verdade (PostgreSQL), fora do Render também."""

    def rodar(self, vendor):
        from django.apps import apps

        editor = mock.Mock()
        editor.connection.vendor = vendor
        migracao_strike.Migration.operations[0].code(apps, editor)

    def test_no_sqlite_dos_testes_nao_cadastra(self):
        self.rodar("sqlite")
        self.assertFalse(Brinquedos.objects.exists())

    def test_no_postgresql_cadastra_com_fotos_e_objeto(self):
        from .models import CategoriasBrinquedos

        CategoriasBrinquedos.objects.create(nome_categoria="Eletrônicos", imagem_categoria="categorias/e.png")
        with tempfile.TemporaryDirectory() as pasta:
            disco = FileSystemStorage(location=pasta)
            from .models import ImagemBrinquedo

            with mock.patch.object(ImagemBrinquedo._meta.get_field("imagem"), "storage", disco), \
                    mock.patch.object(Brinquedos._meta.get_field("imagem_brinquedo"), "storage", disco), \
                    mock.patch("builtins.print"):
                self.rodar("postgresql")
                self.rodar("postgresql")  # de novo: não duplica
        strike = Brinquedos.objects.get()
        self.assertEqual(strike.nome_brinquedo, "Strike Kids")
        self.assertEqual(strike.imagens_brinquedo.count(), len(CADASTROS["strike-kids"]["fotos"]))
        self.assertEqual(strike.objeto_3d.codigo, "strike-kids")
        self.assertEqual(strike.objeto_3d.medidas, [2.07, 0.74, 1.91])

    def test_a_0119_tira_os_objetos_desenhados_e_deixa_os_enviados(self):
        from django.apps import apps

        lazer = Brinquedos.objects.create(nome_brinquedo="Lazer Shot", descricao="x", avaliacao=5)
        boliche = Brinquedos.objects.create(nome_brinquedo="Boliche Virtual", descricao="x", avaliacao=5)
        ObjetoTresD.objects.create(brinquedo=lazer, codigo="lazer-shot", arquivo_estatico="site/arena/modelos/lazer-shot.glb")
        enviado = ObjetoTresD.objects.create(brinquedo=boliche, codigo="boliche-virtual", arquivo="objetos_3d/dragon.glb")
        importlib.import_module("core.migrations.0119_tira_objetos_3d_desenhados").tirar(apps, None)
        self.assertEqual(list(ObjetoTresD.objects.all()), [enviado])

    def test_ja_no_catalogo_so_liga(self):
        boliche = Brinquedos.objects.create(nome_brinquedo="Strike Kids Premium", descricao="x", avaliacao=5)
        self.rodar("postgresql")
        self.assertEqual(Brinquedos.objects.count(), 1)
        self.assertEqual(boliche.objeto_3d.codigo, "strike-kids")


class StrikeKidsBrinquedoNovoTests(TestCase):
    """A 0120: o Strike Kids no catálogo, com a foto 2D sem fundo e o objeto 3D."""

    def setUp(self):
        from .models import CategoriasBrinquedos, ImagemBrinquedo

        CategoriasBrinquedos.objects.create(nome_categoria="Eletrônicos", imagem_categoria="categorias/e.png")
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        disco = FileSystemStorage(location=self.pasta.name)
        for patch in (
            mock.patch.object(ImagemBrinquedo._meta.get_field("imagem"), "storage", disco),
            mock.patch.object(Brinquedos._meta.get_field("imagem_brinquedo"), "storage", disco),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def rodar(self, vendor="postgresql"):
        from django.apps import apps

        from .cadastro_modelos import strike_kids_no_catalogo

        editor = mock.Mock()
        editor.connection.vendor = vendor
        return strike_kids_no_catalogo(apps, editor, avisar=lambda *a: None)

    def test_cadastra_com_a_foto_sem_fundo_e_o_3d(self):
        self.rodar()
        self.rodar()  # de novo: não duplica
        strike = Brinquedos.objects.get()
        self.assertEqual(strike.nome_brinquedo, "Strike Kids")
        fotos = list(strike.imagens_brinquedo.order_by("ordem"))
        # a capa (a cena na game zone, a da 0153: o card e a primeira da galeria), a foto
        # sem fundo de antes (sem tipo), os lados que a Arena usa; depois mais ângulos e as cores
        self.assertEqual([f.tipo for f in fotos[:5]], ["perfil", None, "lado_direito", "lado_esquerdo", "verso"])
        self.assertEqual(len(fotos), 13)
        self.assertEqual(sum(1 for f in fotos if "cor_" in f.imagem.name), 5)
        self.assertIn("strike-kids-capa", fotos[0].imagem.name)
        self.assertIn("strike-kids-foto", fotos[1].imagem.name)
        self.assertIn("strike-kids-capa", strike.imagem_brinquedo.name)
        self.assertEqual(strike.objeto_3d.codigo, "strike-kids")
        self.assertIn("câmera", strike.descricao)
        self.assertIn("5 sensores", strike.descricao)

    def test_o_que_o_site_cadastrou_antes_vira_strike_kids_com_as_fotos_novas(self):
        antigo = Brinquedos.objects.create(
            nome_brinquedo="Strike Kids Boliche", descricao="x", avaliacao=5,
            imagem_brinquedo="imagens_brinquedos/strike-kids-frente.webp",
        )
        self.rodar()
        antigo.refresh_from_db()
        self.assertEqual(Brinquedos.objects.count(), 1)
        self.assertEqual(antigo.nome_brinquedo, "Strike Kids")
        self.assertIn("strike-kids-capa", antigo.imagem_brinquedo.name)
        self.assertEqual(antigo.imagens_brinquedo.count(), 13)

    def test_o_do_painel_fica_como_esta_e_ganha_o_3d(self):
        meu = Brinquedos.objects.create(
            nome_brinquedo="Strike Kids Turbo", descricao="minha", avaliacao=5, imagem_brinquedo="imagens_brinquedos/minha.webp",
        )
        self.rodar()
        meu.refresh_from_db()
        self.assertEqual((meu.nome_brinquedo, meu.descricao, meu.imagem_brinquedo.name), ("Strike Kids Turbo", "minha", "imagens_brinquedos/minha.webp"))
        self.assertEqual(meu.objeto_3d.codigo, "strike-kids")
        self.assertEqual(Brinquedos.objects.count(), 1)

    def test_nos_testes_sqlite_nao_faz_nada(self):
        self.assertIsNone(self.rodar("sqlite"))
        self.assertFalse(Brinquedos.objects.exists())

    def test_desativado_nao_conta(self):
        # o do painel, desativado: fica escondido, e o novo é cadastrado
        escondido = Brinquedos.objects.create(nome_brinquedo="Strike Kids Turbo", descricao="x", avaliacao=5, ativo=False)
        self.rodar()
        novo = Brinquedos.objects.get(ativo=True)
        self.assertEqual(novo.nome_brinquedo, "Strike Kids")
        self.assertEqual(novo.objeto_3d.codigo, "strike-kids")
        escondido.refresh_from_db()
        self.assertFalse(escondido.ativo)

    def test_o_strike_kids_desativado_volta(self):
        antigo = Brinquedos.objects.create(nome_brinquedo="Strike Kids", descricao="x", avaliacao=5, ativo=False)
        self.rodar()
        antigo.refresh_from_db()
        self.assertTrue(antigo.ativo)
        self.assertEqual(Brinquedos.objects.count(), 1)
        self.assertEqual(antigo.imagens_brinquedo.count(), 13)
        self.assertEqual(antigo.objeto_3d.codigo, "strike-kids")

    def test_o_que_subiu_com_4_fotos_ganha_as_novas(self):
        # o Strike Kids que o site cadastrou com as 4 fotos de antes
        self.rodar()
        strike = Brinquedos.objects.get()
        for foto in strike.imagens_brinquedo.order_by("ordem")[4:]:
            foto.delete()
        self.assertEqual(strike.imagens_brinquedo.count(), 4)
        self.rodar()
        self.assertEqual(strike.imagens_brinquedo.count(), 13)
        self.assertEqual(Brinquedos.objects.count(), 1)

    def test_o_comando_conta_o_que_fez(self):
        saida = StringIO()
        call_command("cadastrar_modelo_3d", "strike-kids", stdout=saida)
        texto = saida.getvalue()
        self.assertIn("Strike Kids no banco: nenhum", texto)
        self.assertIn("Criado: Strike Kids", texto)
        self.assertIn("Strike Kids pronto", texto)
        saida = StringIO()
        call_command("cadastrar_modelo_3d", "strike-kids", stdout=saida)  # de novo: só confere
        self.assertIn("(id", saida.getvalue())
        self.assertEqual(Brinquedos.objects.count(), 1)

    def test_a_foto_sem_fundo_tem_fundo_transparente(self):
        # a foto do produto (a capa da Arena, core/arena.py); a capa do card é a cena (capa.webp)
        from PIL import Image

        foto = Image.open(finders.find("site/arena/modelos/strike-kids/foto.webp"))
        self.assertEqual(foto.mode, "RGBA")
        self.assertEqual(foto.getpixel((2, 2))[3], 0)  # o canto: sem fundo


class MigrarAoSubirTests(TestCase):
    """O gunicorn aplica as migrações que faltarem ao subir (no Render)."""

    def carregar(self):
        import importlib.util
        from pathlib import Path

        caminho = Path(__file__).resolve().parent.parent / "gunicorn.conf.py"
        spec = importlib.util.spec_from_file_location("gunicorn_conf_teste", caminho)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo

    def test_no_render_migra_e_fora_dele_nao(self):
        conf = self.carregar()
        servidor = mock.Mock()
        with mock.patch("django.core.management.call_command") as migrar:
            with mock.patch.dict("os.environ", {"RENDER": "true", "AUTO_MIGRATE": ""}):
                conf.on_starting(servidor)
            migrar.assert_called_once_with("migrate", interactive=False, verbosity=1)
            migrar.reset_mock()
            with mock.patch.dict("os.environ", {"RENDER": "true", "AUTO_MIGRATE": "0"}):
                conf.on_starting(servidor)
            with mock.patch.dict("os.environ", {"RENDER": "", "AUTO_MIGRATE": ""}):
                conf.on_starting(servidor)
            migrar.assert_not_called()

    def test_depois_de_migrar_confere_o_strike_kids(self):
        conf = self.carregar()
        servidor = mock.Mock()
        with mock.patch("django.core.management.call_command"), \
                mock.patch("core.cadastro_modelos.garantir_strike_kids") as garantir, \
                mock.patch.dict("os.environ", {"RENDER": "true", "AUTO_MIGRATE": ""}):
            conf.on_starting(servidor)
        garantir.assert_called_once()
        # e uma falha nele também não derruba o site
        with mock.patch("django.core.management.call_command"), \
                mock.patch("core.cadastro_modelos.garantir_strike_kids", side_effect=OSError("cloudinary fora")), \
                mock.patch.dict("os.environ", {"RENDER": "true", "AUTO_MIGRATE": ""}):
            conf.on_starting(servidor)
        self.assertIn("cloudinary fora", servidor.log.error.call_args[0][0])

    def test_falha_na_migracao_nao_derruba_o_site(self):
        conf = self.carregar()
        servidor = mock.Mock()
        with mock.patch("django.core.management.call_command", side_effect=RuntimeError("banco fora")), \
                mock.patch.dict("os.environ", {"RENDER": "true", "AUTO_MIGRATE": ""}):
            conf.on_starting(servidor)  # não levanta
        self.assertIn("banco fora", servidor.log.error.call_args[0][0])


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

    def fora_da_roda(self, nome):
        """Sem objeto 3D: fora da roda (e da lista), mas na galeria de fotos."""
        contexto = self.client.get(reverse("arena")).context
        self.assertNotIn(nome, [m["nome"] for m in contexto["arena_dados"]["maquinas"]])
        self.assertEqual(next(b for b in contexto["brinquedos_arena"] if b["nome"] == nome)["modelo"], "")

    def test_sem_cadastro_vale_o_objeto_do_site_pelo_nome(self):
        # o Strike Kids do catálogo tem o .glb do site mesmo antes da ligação
        dados = self.maquina()
        self.assertIn("site/arena/modelos/strike-kids.glb", dados["modelo"])
        self.assertEqual((dados["grupo"], dados["jogo"]), ("jogos", "strike-kids"))
        # e um brinquedo sem objeto nenhum fica fora da roda (só nas fotos)
        Brinquedos.objects.create(nome_brinquedo="Air Game Hockey", descricao="x", avaliacao=5)
        self.fora_da_roda("Air Game Hockey")

    def test_aparece_na_arena_antes_do_catalogo(self):
        self.strike.delete()
        maquinas = self.client.get(reverse("arena")).context["arena_dados"]["maquinas"]
        dados = next(m for m in maquinas if m["nome"] == "Strike Kids")
        self.assertEqual(dados["id"], "modelo-strike-kids")
        self.assertIn("strike-kids.glb", dados["modelo"])
        self.assertEqual((dados["grupo"], dados["jogo"]), ("jogos", "strike-kids"))
        self.assertIn("strike-kids/foto.webp", dados["capa"])

    def test_tirado_no_painel_nao_volta_pelo_nome(self):
        objeto = ligar_objeto_3d("strike-kids", self.strike, ObjetoTresD)
        objeto.ativo = False
        objeto.save()
        self.fora_da_roda("Strike Kids Boliche")

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
        self.fora_da_roda("Strike Kids Boliche")

    def test_codigo_do_espaco_continua_no_reino(self):
        espaco = Brinquedos.objects.create(nome_brinquedo="Espaço Esportivo Modelo 1", descricao="x", avaliacao=5)
        ligar_objeto_3d("espaco-esportivo-modelo-1", espaco, ObjetoTresD)
        maquinas = self.client.get(reverse("arena")).context["arena_dados"]["maquinas"]
        dados = next(m for m in maquinas if m["nome"] == "Espaço Esportivo Modelo 1")
        self.assertEqual((dados["grupo"], dados["reino"]), ("esportivos", True))
        self.assertEqual({j["slug"] for j in dados["jogos_no_espaco"]}, {"swish-arena", "gol-flash-arena"})

    def test_objeto_do_site_sem_codigo_vale_pelo_arquivo(self):
        # ligado sem o "Código na Arena", o .glb do Espaço continua sendo o
        # Espaço: com as crianças (as animações), o passeio e o reino dele --
        # mesmo num brinquedo de outro nome, e sem repetir o do site
        gol = Brinquedos.objects.create(nome_brinquedo="Gol Flash Arena", descricao="x", avaliacao=5)
        ObjetoTresD.objects.create(brinquedo=gol, arquivo_estatico="site/arena/modelos/espaco-esportivo-modelo-1.glb")
        maquinas = self.client.get(reverse("arena")).context["arena_dados"]["maquinas"]
        dados = next(m for m in maquinas if m["nome"] == "Gol Flash Arena")
        self.assertEqual(dados["modelo_id"], "espaco-esportivo-modelo-1")
        self.assertEqual((dados["grupo"], dados["reino"], dados["medidas_modelo"]), ("esportivos", True, [3.9, 39.0, 23.0]))
        self.assertEqual(sum(m["modelo_id"] == "espaco-esportivo-modelo-1" for m in maquinas), 1)
        # um .glb enviado (sem código) segue como objeto do cadastro, sem as animações
        # (gravado com save(), como o painel faz: a Arena sai do cache do
        # catálogo, e é o signal do save() que avisa que o cadastro mudou)
        objeto = ObjetoTresD.objects.get(brinquedo=gol)
        objeto.arquivo_estatico, objeto.arquivo = "", "objetos_3d/gol.glb"
        objeto.save()
        maquinas = self.client.get(reverse("arena")).context["arena_dados"]["maquinas"]
        dados = next(m for m in maquinas if m["nome"] == "Gol Flash Arena")
        self.assertTrue(dados["modelo_id"].startswith("objeto-"))


class PaginaDoBrinquedoTests(TestCase):
    def setUp(self):
        self.strike = Brinquedos.objects.create(nome_brinquedo="Strike Kids Boliche", descricao="x", avaliacao=5)
        self.url = reverse("brinquedo_detalhe", args=[self.strike.pk])

    def test_visor_so_com_objeto(self):
        outro = Brinquedos.objects.create(nome_brinquedo="Air Game Hockey", descricao="x", avaliacao=5)
        resposta = self.client.get(reverse("brinquedo_detalhe", args=[outro.pk]))
        self.assertNotContains(resposta, "data-visor3d")
        self.assertNotContains(resposta, "visor3d.js")
        ligar_objeto_3d("strike-kids", self.strike, ObjetoTresD)
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "data-visor3d-abrir")
        self.assertContains(resposta, "site/arena/visor3d.js")
        self.assertContains(resposta, "site/arena/modelos/strike-kids.glb")

    def test_visor_pelo_nome_antes_da_ligacao(self):
        self.assertContains(self.client.get(self.url), "site/arena/modelos/strike-kids.glb")

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
        # as telas do painel importam a `tabela_pronta` quando carregam: carregadas
        # aqui pela primeira vez, guardariam o dublê para os testes seguintes
        import sistema_interno.urls  # noqa: F401

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

    def test_arena_e_pagina_abrem_sem_o_cadastro_do_3d(self):
        # sem a tabela, o Strike Kids ainda tem o .glb do site, ligado pelo nome
        resposta = self.sem_consultar_a_tabela(reverse("arena"))
        dados = next(m for m in resposta.context["arena_dados"]["maquinas"] if m["nome"] == "Strike Kids Boliche")
        self.assertIn("strike-kids.glb", dados["modelo"])
        resposta = self.sem_consultar_a_tabela(reverse("brinquedo_detalhe", args=[self.strike.pk]))
        self.assertContains(resposta, "strike-kids.glb")
        # e uma máquina sem objeto nenhum segue sem o visor
        outro = Brinquedos.objects.create(nome_brinquedo="Air Game Hockey", descricao="x", avaliacao=5)
        resposta = self.sem_consultar_a_tabela(reverse("brinquedo_detalhe", args=[outro.pk]))
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
        objetos_3d._tabelas.clear()
        self.assertTrue(objetos_3d.tabela_pronta())
        self.assertEqual(objetos_3d.prefetch_do_objeto(), ("objeto_3d",))
