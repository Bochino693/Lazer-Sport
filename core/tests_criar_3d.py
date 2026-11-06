"""Criar objetos 3D sem programa de 3D: o .glb escrito aqui, a conversão dos
formatos dos programas de projeto, as fotos que viram objeto e o paralelo com
a loja (core/glb_montar.py, core/conversor_3d.py, core/modelo_fotos.py,
core/produtos_parecidos.py).

O que se garante: o .glb sai válido e na medida (lido pelo mesmo leitor do
cadastro); cada formato chega de pé, no chão, na unidade certa; as peças
soltas longe do conjunto saem; as fotos são recortadas do fundo e casadas
com as medidas; e o projeto acha o produto parecido pelo nome, pela
descrição e pelas medidas.
"""

import io
import struct
import zipfile

from django.test import SimpleTestCase
from PIL import Image, ImageDraw

from . import conversor_3d, glb_montar, modelo_fotos, produtos_parecidos
from .objetos_3d import ler_glb


def lido(glb):
    return ler_glb(io.BytesIO(glb))


def foto(largura=400, altura=300, caixa=(100, 60, 300, 260), cor=(230, 40, 60), fundo=(250, 250, 250)):
    """Uma foto de fundo liso com um "brinquedo" (retângulo) no meio, em PNG."""
    imagem = Image.new("RGB", (largura, altura), fundo)
    ImageDraw.Draw(imagem).rectangle(caixa, fill=cor)
    saida = io.BytesIO()
    imagem.save(saida, "PNG")
    return saida.getvalue()


CUBO_OBJ = b"""mtllib cubo.mtl
v 0 0 0
v 200 0 0
v 200 300 0
v 0 300 0
v 0 0 100
v 200 0 100
v 200 300 100
v 0 300 100
vt 0 0
vt 1 0
vt 1 1
vt 0 1
usemtl pintura
f 1/1 2/2 3/3 4/4
f 5/1 6/2 7/3 8/4
f 1/1 5/2 8/3 4/4
f 2/1 6/2 7/3 3/4
f 4/1 3/2 7/3 8/4
f 1/1 2/2 6/3 5/4
"""


def stl_binario(triangulos):
    dados = bytearray(b"\0" * 80) + struct.pack("<I", len(triangulos))
    for a, b, c in triangulos:
        dados += struct.pack("<12fH", 0, 0, 0, *a, *b, *c, 0)
    return bytes(dados)


def tres_ds(vertices, faces):
    """Um .3ds mínimo: MAIN > EDIT > OBJECT > TRIMESH (vértices e faces)."""
    def bloco(cid, corpo):
        return struct.pack("<HI", cid, 6 + len(corpo)) + corpo

    verts = struct.pack("<H", len(vertices)) + b"".join(struct.pack("<3f", *v) for v in vertices)
    fcs = struct.pack("<H", len(faces)) + b"".join(struct.pack("<4H", a, b, c, 0) for a, b, c in faces)
    malha = bloco(0x4100, bloco(0x4110, verts) + bloco(0x4120, fcs))
    return bloco(0x4D4D, bloco(0x3D3D, bloco(0x4000, b"caixa\0" + malha)))


DAE = b"""<?xml version="1.0" encoding="utf-8"?>
<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">
  <asset><unit meter="0.0254" name="inch"/><up_axis>Z_UP</up_axis></asset>
  <library_effects><effect id="ef"><profile_COMMON><technique sid="c"><lambert>
    <diffuse><color>0.9 0.2 0.1 1</color></diffuse></lambert></technique></profile_COMMON></effect></library_effects>
  <library_materials><material id="vermelho"><instance_effect url="#ef"/></material></library_materials>
  <library_geometries><geometry id="g"><mesh>
    <source id="p"><float_array id="pa" count="12">0 0 0 100 0 0 100 0 50 0 0 50</float_array>
      <technique_common><accessor source="#pa" count="4" stride="3"/></technique_common></source>
    <vertices id="v"><input semantic="POSITION" source="#p"/></vertices>
    <polylist material="m" count="1"><input semantic="VERTEX" source="#v" offset="0"/><vcount>4</vcount><p>0 1 2 3</p></polylist>
  </mesh></geometry></library_geometries>
  <library_visual_scenes><visual_scene id="cena"><node id="n">
    <translate>10 20 0</translate>
    <instance_geometry url="#g"><bind_material><technique_common><instance_material symbol="m" target="#vermelho"/></technique_common></bind_material></instance_geometry>
  </node></visual_scene></library_visual_scenes>
  <scene><instance_visual_scene url="#cena"/></scene>
</COLLADA>
"""


class GlbTests(SimpleTestCase):
    def test_cena_escreve_um_glb_que_o_cadastro_le(self):
        cena = glb_montar.Cena()
        parte = glb_montar.soldar([
            (((0, 0, 0), (2, 0, 0), (2, 3, 0)), None),
            (((0, 0, 0), (2, 3, 0), (0, 3, 0)), None),
            (((0, 0, 0), (0, 3, 0), (0, 3, -1)), None),
        ])
        parte["material"] = cena.material("x", (1, 0, 0, 1))
        cena.no("o", cena.malha("o", [parte]))
        glb = cena.glb()
        self.assertEqual(lido(glb)["medidas"], [3.0, 2.0, 1.0])
        gltf, _binario = glb_montar.ler_glb(glb)
        self.assertIn("KHR_mesh_quantization", gltf["extensionsRequired"])

    def test_soldar_mantem_quina_viva_e_junta_o_mesmo_ponto(self):
        # dois triângulos no mesmo plano dividem os cantos (4 vértices); o terceiro,
        # em quina de 90°, ganha os seus (3): a dobra não é alisada
        parte = glb_montar.soldar([
            (((0, 0, 0), (1, 0, 0), (1, 1, 0)), None),
            (((0, 0, 0), (1, 1, 0), (0, 1, 0)), None),
            (((0, 0, 0), (0, 1, 0), (0, 1, -1)), None),
        ])
        self.assertEqual(len(parte["indices"]), 9)
        self.assertEqual(len(parte["posicoes"]) // 3, 7)

    def test_parte_grande_e_dividida_em_indices_de_16_bits(self):
        indices = list(range(70002))
        parte = {"posicoes": [0.0] * (70002 * 3), "normais": [0.0] * (70002 * 3), "uvs": None, "indices": indices}
        pedacos = glb_montar._partir(parte)
        self.assertGreater(len(pedacos), 1)
        self.assertTrue(all(len(p["posicoes"]) // 3 <= 65535 for p in pedacos))
        self.assertEqual(sum(len(p["indices"]) for p in pedacos), 70002)

    def test_encaixe_poe_em_pe_no_chao_e_na_medida(self):
        # caixa de 2000 x 1000 x 3000 em mm, Z para cima: altura 3 m depois do giro
        matriz, info = glb_montar.encaixe(([0, 0, 0], [2000, 1000, 3000]), eixo_z=True)
        self.assertEqual(info["medidas"], [3.0, 2.0, 1.0])
        self.assertIn("mm", info["unidade"])
        baixo = glb_montar.aplicar(matriz, (0, 0, 0))
        self.assertAlmostEqual(baixo[1], 0.0)
        _matriz, info = glb_montar.encaixe(([0, 0, 0], [2, 3, 1]), medidas={"altura": 6})
        self.assertEqual(info["medidas"], [6.0, 4.0, 2.0])


class ConversorTests(SimpleTestCase):
    def test_obj_com_mtl_e_textura_no_zip(self):
        textura = io.BytesIO()
        Image.new("RGB", (8, 8), (10, 200, 30)).save(textura, "JPEG")
        pacote = io.BytesIO()
        with zipfile.ZipFile(pacote, "w") as z:
            z.writestr("modelo/cubo.obj", CUBO_OBJ)
            z.writestr("modelo/cubo.mtl", b"newmtl pintura\nKd 1 1 1\nmap_Kd C:\\\\Projetos\\\\VERDE.JPG\n")
            z.writestr("modelo/texturas/verde.jpg", textura.getvalue())
        glb, info = conversor_3d.converter("cubo.zip", pacote.getvalue())
        # 300 de altura: centímetros (adivinhados) -> 3 m
        self.assertEqual(info["medidas"], [3.0, 2.0, 1.0])
        self.assertEqual(info["fotos"], 1)
        self.assertEqual(lido(glb)["medidas"], [3.0, 2.0, 1.0])

    def test_obj_sozinho_sem_o_mtl(self):
        _glb, info = conversor_3d.converter("cubo.obj", CUBO_OBJ, unidade="mm")
        self.assertEqual(info["medidas"], [0.3, 0.2, 0.1])

    def test_stl_binario_e_texto(self):
        tri = [((0, 0, 0), (1, 0, 0), (0, 1, 2)), ((1, 0, 0), (1, 1, 0), (0, 1, 2))]
        _glb, info = conversor_3d.converter("peca.stl", stl_binario(tri))
        self.assertEqual(info["medidas"], [2.0, 1.0, 1.0])  # Z para cima no STL
        texto = b"solid x\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 2\nendloop\nendfacet\nendsolid x\n"
        _glb, info = conversor_3d.converter("peca.stl", texto)
        self.assertEqual(info["medidas"][0], 2.0)

    def test_3ds(self):
        vertices = [(0, 0, 0), (4000, 0, 0), (4000, 2000, 0), (0, 2000, 0), (0, 0, 3000)]
        glb, info = conversor_3d.converter("brinquedo.3ds", tres_ds(vertices, [(0, 1, 2), (0, 2, 3), (0, 1, 4)]))
        self.assertEqual(info["medidas"], [3.0, 4.0, 2.0])
        self.assertEqual(info["formato"], "3ds")
        self.assertEqual(lido(glb)["medidas"], [3.0, 4.0, 2.0])

    def test_dae_do_sketchup_em_polegadas_e_z_para_cima(self):
        glb, info = conversor_3d.converter("modelo.dae", DAE)
        # 100 x 50 polegadas, de pé (Z para cima): 2,54 m de largura e 1,27 m de altura
        self.assertEqual(info["medidas"][0], 1.27)
        self.assertEqual(info["medidas"][1], 2.54)
        self.assertIn("pol", info["unidade"])
        gltf, _ = glb_montar.ler_glb(glb)
        self.assertEqual(gltf["materials"][0]["pbrMetallicRoughness"]["baseColorFactor"][:3], [0.9, 0.2, 0.1])

    def test_kmz_e_o_dae_zipado(self):
        pacote = io.BytesIO()
        with zipfile.ZipFile(pacote, "w") as z:
            z.writestr("doc.kml", b"<kml/>")
            z.writestr("models/modelo.dae", DAE)
        _glb, info = conversor_3d.converter("modelo.kmz", pacote.getvalue())
        self.assertEqual(info["formato"], "dae")

    def test_dae_com_entidades_e_recusado(self):
        with self.assertRaises(conversor_3d.ErroDeConversao):
            conversor_3d.converter("x.dae", b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><COLLADA/>')

    def test_glb_pronto_so_se_encaixa(self):
        cena = glb_montar.Cena()
        parte = glb_montar.soldar([(((5, 5, 5), (7, 5, 5), (7, 8, 6)), None)])
        parte["material"] = cena.material("x")
        cena.no("o", cena.malha("o", [parte], quantizar=False))
        glb, info = conversor_3d.converter("pronto.glb", cena.glb(), medidas={"altura": 1.5})
        self.assertEqual(info["medidas"][0], 1.5)
        gltf, _ = glb_montar.ler_glb(glb)
        menor, _maior = glb_montar.caixa_do_gltf(gltf)
        self.assertAlmostEqual(menor[1], 0.0, places=5)

    def test_formatos_que_nao_abrem_dizem_como_exportar(self):
        with self.assertRaisesMessage(conversor_3d.ErroDeConversao, "SketchUp"):
            conversor_3d.converter("projeto.skp", b"xx")
        with self.assertRaisesMessage(conversor_3d.ErroDeConversao, "Blender"):
            conversor_3d.converter("modelo.fbx", b"xx")

    def test_pecas_soltas_longe_do_conjunto_saem(self):
        modelo = conversor_3d.Modelo()
        for i in range(200):
            x = (i % 20) * 0.1
            modelo.triangulo("a", ((x, 0, 0), (x + 0.1, 0, 0), (x, 1, 0)))
        modelo.triangulo("a", ((90, 0, 0), (91, 0, 0), (90, 1, 0)))  # uma cota a 90 m
        self.assertEqual(modelo.tirar_soltas(), 1)
        self.assertLess(modelo.caixa()[1][0], 3)


class FotosTests(SimpleTestCase):
    def test_recorte_tira_o_fundo_e_enquadra_o_objeto(self):
        recortada, aviso = modelo_fotos.recortar(modelo_fotos.abrir_foto(foto()))
        self.assertEqual(aviso, "")
        self.assertAlmostEqual(recortada.width / recortada.height, 1.0, delta=0.06)
        self.assertEqual(recortada.getpixel((recortada.width // 2, recortada.height // 2))[3], 255)

    def test_paineis_e_volume_na_medida(self):
        fotos = {"frente": foto(caixa=(50, 50, 350, 250)), "direita": foto(caixa=(150, 50, 250, 250))}
        for modo in modelo_fotos.MODOS:
            glb, info = modelo_fotos.gerar(fotos, {"altura": "2,0"}, modo)
            self.assertEqual(info["medidas"][0], 2.0)
            # a frente tem 3:2 -> 3 m de largura; o lado 1:2 -> 1 m de profundidade
            self.assertAlmostEqual(info["medidas"][1], 3.0, delta=0.1)
            self.assertAlmostEqual(info["medidas"][2], 1.0, delta=0.1)
            self.assertEqual(lido(glb)["medidas"][0], 2.0)

    def test_so_a_frente_vira_um_painel_recortado(self):
        glb, info = modelo_fotos.gerar({"frente": foto()}, {}, "paineis")
        self.assertTrue(any("2 m de altura" in a for a in info["avisos"]))
        self.assertTrue(any("painel recortado" in a for a in info["avisos"]))
        self.assertLess(lido(glb)["medidas"][2], 0.05)

    def test_sem_a_frente_nao_monta(self):
        with self.assertRaises(modelo_fotos.ErroDasFotos):
            modelo_fotos.gerar({"direita": foto()}, {}, "volume")

    def test_foto_que_nao_abre(self):
        with self.assertRaises(modelo_fotos.ErroDasFotos):
            modelo_fotos.gerar({"frente": b"nao e imagem"}, {}, "paineis")


class ParecidosTests(SimpleTestCase):
    def test_medidas_escritas_na_descricao(self):
        self.assertEqual(produtos_parecidos.medidas_no_texto("Área de 6,00 x 4,00 x 3,20 m"),
                         {"largura": 6.0, "profundidade": 4.0, "altura": 3.2})
        self.assertEqual(produtos_parecidos.medidas_no_texto("ocupa 600 x 400 cm, altura: 3,5 m"),
                         {"largura": 6.0, "profundidade": 4.0, "altura": 3.5})
        self.assertEqual(produtos_parecidos.medidas_no_texto("sem medida nenhuma"), {})

    def test_sinonimos_e_plural(self):
        self.assertEqual(produtos_parecidos.palavras("Parquinho com Tobogãs e Camas Elásticas"),
                         ["playground", "toboga", "cama", "trampolim"])

    def test_acha_o_produto_mais_parecido(self):
        class Categoria:
            def __init__(self, nome):
                self.nome_categoria = nome

        class Lista(list):
            def all(self):
                return self

        class Produto:
            def __init__(self, pk, nome, descricao, categorias=(), medidas=(None, None, None)):
                self.pk, self.nome_brinquedo, self.descricao = pk, nome, descricao
                self.categorias_brinquedos = Lista(Categoria(c) for c in categorias)
                self.altura_m, self.largura_m, self.profundidade_m = medidas

        catalogo = [
            Produto(1, "Brinquedão Playground 3 Torres", "Playground com tobogã e piscina de bolinhas", ["Brinquedão"], (3.2, 6, 4)),
            Produto(2, "Pebolim Profissional", "Mesa de pebolim", ["Jogos de mesa"]),
            Produto(3, "Cama Elástica 3 m", "Trampolim redondo com rede", ["Trampolim"]),
        ]
        achados = produtos_parecidos.parecidos(
            "Playground Indoor do Shopping", "Parquinho com tobogã, piscina de bolinhas. 6 x 4 x 3,2 m", catalogo)
        self.assertEqual(achados[0]["brinquedo"].pk, 1)
        self.assertIn("medidas parecidas", achados[0]["motivos"])
        self.assertNotIn(2, [a["brinquedo"].pk for a in achados])
