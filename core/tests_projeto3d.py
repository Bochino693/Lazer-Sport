"""Monte seu espaço (na Arena 3D, /arena/#monte-seu-espaco) e os pedidos no painel.

O que se garante: a página abre com o catálogo e as regras (e sem
JavaScript, com a lista); o pedido é conferido (o contato, as medidas, só o
que o catálogo tem) e gravado; robô cai na armadilha sem gravar; o mesmo
endereço não manda mais de 5 por hora; a equipe comercial vê a lista e a
ficha com o 3D refeito da escolha, muda a situação e o sino avisa do novo.
O arrumador (o JavaScript que põe tudo na planta) é conferido pelo node,
com o catálogo de verdade.
"""

import io
import json
import shutil
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from core import projeto3d
from core.models import Brinquedos, ClientePerfil, FotoDoEspaco, PedidoProjeto3D
from sistema_interno.permissoes import PRODUCAO, VENDAS

RAIZ = Path(__file__).resolve().parent
HOST = "interno.testserver"


def _escolha(**extra):
    return {
        "principal": {"tipo": "area", "area": "esportivo"},
        "areas": ["baby"],
        "itens": [],
        "estilo": "neon",
        "cor": "#22c55e",
        "semente": 7,
        **extra,
    }


def _pedido(**extra):
    corpo = {
        "contato": {"nome": "Marina Souza", "whatsapp": "(11) 98888-7777", "email": "marina@example.com", "cidade": "Campinas"},
        "espaco": {"largura": "20", "comprimento": "15,5", "pe_direito": 4},
        "escolha": _escolha(),
        "resumo": {"coube": [{"nome": "Espaço esportivo kids", "qtd": "1"}], "ficou_de_fora": [], "numeros": {"ocupacao": 61}},
    }
    corpo.update(extra)
    return corpo


class PaginaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.basquete = Brinquedos.objects.create(
            nome_brinquedo="Basquete Street", descricao="Máquina de basquete", valor_brinquedo=Decimal("9000"), avaliacao=5,
            altura_m=Decimal("2.7"), largura_m=Decimal("1.0"), profundidade_m=Decimal("2.4"),
        )

    def test_a_pagina_abre_com_o_catalogo_e_as_regras(self):
        resposta = self.client.get("/arena/")
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'id="p3dDados"')
        self.assertContains(resposta, "site/projeto3d/arrumador.js")
        self.assertContains(resposta, "interno/montar3d-gerador.js")
        dados = resposta.context["projeto_dados"]
        self.assertEqual(set(dados["areas"]), set(projeto3d.AREAS))
        basquete = next(i for i in dados["itens"] if i["nome"] == "Basquete Street")
        self.assertEqual(basquete["tipo"], "maquina")
        self.assertTrue(basquete["parede"])
        self.assertEqual(basquete["medidas"], [2.7, 1.0, 2.4])
        self.assertEqual(basquete["uso"], {"frente": 1.0})
        # os brinquedos grandes do site (o brinquedão, o espaço pronto) vêm com a faixa de segurança
        grandes = [i for i in dados["itens"] if i["tipo"] == "grande"]
        self.assertTrue(grandes)
        self.assertTrue(all(i["uso"] == {"todos": 1.0} and not i["parede"] for i in grandes))
        self.assertTrue(any(i["area"] == "esportivo" for i in grandes))
        # sem JavaScript: a lista com as medidas e o WhatsApp
        self.assertContains(resposta, "As áreas que a fábrica monta sob medida")
        self.assertContains(resposta, "Basquete Street</b> — 1,00 × 2,40 m")

    def test_um_trampolim_so_nao_e_o_trampolim_park(self):
        # o park é o sob medida (com os portes); a cama elástica e o trampolim de enterrada são brinquedos grandes
        dados = projeto3d.catalogo()
        enterrada = next(i for i in dados["itens"] if i["nome"] == "Trampolim de Enterrada")
        self.assertEqual((enterrada["tipo"], enterrada["area"]), ("grande", ""))
        self.assertIn("trampolim-enterrada.glb", enterrada["modelo"])
        park = dados["areas"]["trampolim"]
        self.assertEqual([p["chave"] for p in park["portes"]], ["compacto", "medio", "grande"])
        self.assertIn("parede_inclinada", park["portes"][2]["componentes"])
        self.assertIn("trampolim_park", dados["areas"]["esportivo"]["portes"][1]["componentes"])
        self.assertEqual(dados["componentes"]["espuma"], "Piscina de espuma")

    def test_o_endereco_antigo_leva_para_a_arena(self):
        resposta = self.client.get("/monte-seu-projeto/")
        self.assertEqual((resposta.status_code, resposta["Location"]), (301, "/arena/#monte-seu-espaco"))
        self.assertContains(self.client.get("/arena/"), 'href="/arena/#monte-seu-espaco"')


class ValidarPedidoTests(TestCase):
    def setUp(self):
        self.catalogo = {"itens": [{"id": "5", "nome": "Lazer Shot"}, {"id": "modelo-brinquedao-ninja", "nome": "Brinquedão Ninja"}]}

    def test_pedido_certo(self):
        campos = projeto3d.validar_pedido(_pedido(escolha=_escolha(itens=[{"id": "5", "qtd": 3}, {"id": "999", "qtd": 1}, {"id": "5", "qtd": "x"}])), self.catalogo)
        self.assertEqual(campos["whatsapp"], "11988887777")
        self.assertEqual(campos["comprimento"], Decimal("15.50"))
        self.assertEqual(campos["principal"], "Espaço esportivo kids (sob medida)")
        # só o que o catálogo tem
        self.assertEqual(campos["escolhas"]["itens"], [{"id": "5", "qtd": 3}])
        self.assertEqual(campos["escolhas"]["areas"], ["baby"])
        self.assertEqual(campos["estilo"], "neon")
        self.assertEqual(campos["semente"], 7)

    def test_guarda_o_porte_e_o_que_o_cliente_tirou(self):
        escolha = _escolha(opcoes={
            "trampolim": {"porte": "grande", "sem": ["queimada", "camas", "inventado"]},
            "baby": {"porte": "gigante"},
            "brinquedao": {"porte": "grande"},
            "lixo": "x",
        })
        campos = projeto3d.validar_pedido(_pedido(escolha=escolha), self.catalogo)
        self.assertEqual(campos["escolhas"]["opcoes"], {
            "trampolim": {"porte": "grande", "sem": ["queimada"]},  # as camas não saem; o inventado some
            "baby": {"porte": "auto", "sem": []},
        })

    def test_o_principal_pode_ser_um_modelo_pronto(self):
        campos = projeto3d.validar_pedido(_pedido(escolha=_escolha(principal={"tipo": "item", "id": "modelo-brinquedao-ninja"})), self.catalogo)
        self.assertEqual(campos["principal"], "Brinquedão Ninja")

    def test_o_que_o_cliente_tem_de_corrigir(self):
        casos = (
            ({"contato": {"nome": "M", "whatsapp": "11988887777"}}, "nome"),
            ({"contato": {"nome": "Marina", "whatsapp": "1234"}}, "WhatsApp"),
            ({"contato": {"nome": "Marina", "whatsapp": "11988887777", "email": "marina@"}}, "e-mail"),
            ({"espaco": {"largura": "0,5", "comprimento": "10"}}, "largura"),
            ({"espaco": {"largura": "20", "comprimento": "abc"}}, "comprimento"),
            ({"escolha": {"principal": None, "areas": [], "itens": []}}, "Escolha"),
        )
        for extra, palavra in casos:
            with self.subTest(palavra):
                with self.assertRaisesRegex(projeto3d.PedidoInvalido, palavra):
                    projeto3d.validar_pedido(_pedido(**extra), self.catalogo)

    def test_resumo_so_com_texto_curto(self):
        campos = projeto3d.validar_pedido(_pedido(resumo={
            "coube": [{"nome": "<b>x</b>" * 100, "qtd": "2", "lixo": "y"}],
            "numeros": {"ocupacao": 61, "hack": "z"},
            "espaco_para_tudo": {"largura": 22.5, "comprimento": "x"},
        }), self.catalogo)
        self.assertEqual(len(campos["resumo"]["coube"][0]["nome"]), 200)
        self.assertNotIn("lixo", campos["resumo"]["coube"][0])
        self.assertEqual(campos["resumo"]["numeros"], {"ocupacao": 61.0})
        self.assertEqual(campos["resumo"]["espaco_para_tudo"], {"largura": 22.5})


class PedirTests(TestCase):
    URL = "/monte-seu-projeto/pedir/"

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def mandar(self, corpo, cliente=None):
        return (cliente or self.client).post(self.URL, json.dumps(corpo), content_type="application/json")

    def test_grava_o_pedido_e_devolve_o_whatsapp(self):
        resposta = self.mandar(_pedido())
        self.assertEqual(resposta.status_code, 200, resposta.content)
        dados = resposta.json()
        self.assertEqual(dados["status"], "sucesso")
        pedido = PedidoProjeto3D.objects.get(pk=dados["numero"])
        self.assertEqual((pedido.nome, pedido.status, pedido.cor), ("Marina Souza", "novo", "#22c55e"))
        self.assertEqual(pedido.escolhas["principal"], {"tipo": "area", "area": "esportivo"})
        self.assertIn("wa.me/", dados["whatsapp"])
        self.assertIn("Pedido%20n%C2%BA%20" + str(pedido.pk), dados["whatsapp"])

    def test_robo_cai_na_armadilha_e_nada_e_gravado(self):
        resposta = self.mandar(_pedido(site="https://spam.example"))
        self.assertEqual(resposta.json()["status"], "sucesso")
        self.assertFalse(PedidoProjeto3D.objects.exists())

    def test_cinco_por_hora_do_mesmo_endereco(self):
        for _ in range(5):
            self.assertEqual(self.mandar(_pedido()).status_code, 200)
        self.assertEqual(self.mandar(_pedido()).status_code, 429)
        self.assertEqual(PedidoProjeto3D.objects.count(), 5)

    def test_corpo_errado_ou_grande_demais(self):
        self.assertEqual(self.client.post(self.URL, "não é json", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post(self.URL, "[1, 2]", content_type="application/json").status_code, 400)
        grande = _pedido(resumo={"coube": [{"nome": "x" * 1000}] * 100})
        self.assertEqual(self.mandar(grande).status_code, 413)
        resposta = self.mandar(_pedido(contato={"nome": "Marina", "whatsapp": "1"}))
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("WhatsApp", resposta.json()["mensagem"])
        self.assertFalse(PedidoProjeto3D.objects.exists())

    def test_pede_o_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        self.assertEqual(self.mandar(_pedido(), cliente).status_code, 403)
        cliente.get("/arena/")
        resposta = cliente.post(self.URL, json.dumps(_pedido()), content_type="application/json",
                                HTTP_X_CSRFTOKEN=cliente.cookies["csrftoken"].value)
        self.assertEqual(resposta.status_code, 200)

    def test_a_conta_logada_fica_no_pedido(self):
        conta = User.objects.create_user("marina", password="senha-segura")
        # o site pede o telefone de quem tem conta antes de tudo (TelefoneObrigatorioMiddleware)
        ClientePerfil.objects.update_or_create(user=conta, defaults={"telefone": "11988887777"})
        self.client.force_login(conta)
        numero = self.mandar(_pedido()).json()["numero"]
        self.assertEqual(PedidoProjeto3D.objects.get(pk=numero).usuario, conta)


def _jpeg(tamanho=(320, 240), cor=(30, 120, 200), com_lugar=False):
    """Uma foto JPEG de mentira; com_lugar grava no EXIF o GPS e o aparelho (o que não pode ficar guardado)."""
    from PIL import Image

    imagem = Image.new("RGB", tamanho, cor)
    saida = io.BytesIO()
    if com_lugar:
        exif = Image.Exif()
        exif[0x010F] = "Fabricante do Celular"  # Make
        exif[0x8825] = {1: "S", 2: (23.0, 33.0, 1.0)}  # GPSInfo
        imagem.save(saida, "JPEG", exif=exif.tobytes())
    else:
        imagem.save(saida, "JPEG")
    return saida.getvalue()


CANTOS = {"pontos": [[0.26, 0.45], [0.74, 0.45], [0.97, 0.96], [0.03, 0.96]], "giro": 1, "frente": False}


class FotosDoEspacoTests(TestCase):
    """O "Veja no seu espaço": as fotos do lugar (e o projeto montado nelas) vêm com o pedido."""

    URL = "/monte-seu-projeto/pedir/"

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, pasta, True)
        ajuste = override_settings(MEDIA_ROOT=pasta)
        ajuste.enable()
        self.addCleanup(ajuste.disable)

    def mandar(self, **arquivos):
        from django.core.files.uploadedfile import SimpleUploadedFile

        campos = {"dados": json.dumps(_pedido())}
        for nome, valor in arquivos.items():
            campos[nome] = SimpleUploadedFile(f"{nome}.jpg", valor, content_type="image/jpeg") if isinstance(valor, bytes) else valor
        return self.client.post(self.URL, campos)

    def test_a_foto_e_a_montagem_ficam_no_pedido(self):
        from PIL import Image

        resposta = self.mandar(foto_0=_jpeg(com_lugar=True), cantos_0=json.dumps(CANTOS), montagem_0=_jpeg(cor=(200, 60, 30)))
        self.assertEqual(resposta.status_code, 200, resposta.content)
        dados = resposta.json()
        self.assertEqual((dados["status"], dados["fotos"]), ("sucesso", 1))
        self.assertIn("foto%20do%20espa%C3%A7o", dados["whatsapp"])
        pedido = PedidoProjeto3D.objects.get(pk=dados["numero"])
        self.assertEqual(pedido.resumo["fotos"], 1)
        self.assertEqual(pedido.resumo["coube"][0]["nome"], "Espaço esportivo kids")
        foto, montagem = pedido.fotos.order_by("id")
        self.assertEqual((foto.tipo, montagem.tipo), ("foto", "montagem"))
        self.assertEqual(foto.cantos, CANTOS)
        self.assertEqual(montagem.cantos, {})
        # regravada: JPEG, sem o lugar nem o aparelho que estavam no EXIF
        with Image.open(foto.imagem.path) as guardada:
            self.assertEqual(guardada.format, "JPEG")
            self.assertEqual(dict(guardada.getexif()), {})

    def test_a_foto_grande_fica_menor(self):
        from PIL import Image

        resposta = self.mandar(foto_0=_jpeg(tamanho=(2400, 1800)))
        self.assertEqual(resposta.json()["fotos"], 1)
        with Image.open(FotoDoEspaco.objects.get().imagem.path) as guardada:
            self.assertEqual(max(guardada.size), 1600)

    def test_o_que_nao_e_imagem_volta_e_nada_e_gravado(self):
        resposta = self.mandar(foto_0=b"isto nao e uma foto")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("JPG", resposta.json()["mensagem"])
        self.assertFalse(PedidoProjeto3D.objects.exists())
        self.assertFalse(FotoDoEspaco.objects.exists())

    def test_no_maximo_tres_fotos_e_cantos_conferidos(self):
        arquivos = {f"foto_{n}": _jpeg() for n in range(5)}
        arquivos["cantos_0"] = json.dumps({"pontos": [[0, 0], [1, 0]], "giro": 9})
        arquivos["cantos_1"] = json.dumps({"pontos": [[0, 0], [1, 0], [1, 1], [99, 1]]})
        arquivos["cantos_2"] = json.dumps({"pontos": [[0, 0], [1, 0], [1, 1], [0, 1]], "giro": 9, "frente": True})
        resposta = self.mandar(**arquivos)
        self.assertEqual(resposta.json()["fotos"], 3)
        cantos = [f.cantos for f in FotoDoEspaco.objects.order_by("id")]
        self.assertEqual(cantos[:2], [{}, {}])
        self.assertEqual(cantos[2], {"pontos": [[0, 0], [1, 0], [1, 1], [0, 1]], "giro": 0, "frente": True})

    def test_sem_a_tabela_das_fotos_o_pedido_entra_assim_mesmo(self):
        from unittest import mock

        from core import objetos_3d

        real = objetos_3d.tabela_pronta
        with mock.patch.object(objetos_3d, "tabela_pronta", side_effect=lambda *a: False if a and a[0] is FotoDoEspaco else real(*a)):
            resposta = self.mandar(foto_0=_jpeg())
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()["fotos"], 0)
        self.assertTrue(PedidoProjeto3D.objects.exists())

    def test_os_dados_em_partes_tambem_tem_teto(self):
        campos = {"dados": json.dumps(_pedido(resumo={"coube": [{"nome": "x" * 1000}] * 100}))}
        self.assertEqual(self.client.post(self.URL, campos).status_code, 413)
        self.assertEqual(self.client.post(self.URL, {"dados": "não é json"}).status_code, 400)


@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class PainelTests(TestCase):
    def setUp(self):
        cache.clear()
        self.vendas = User.objects.create_user("vendedora", password="senha-segura", is_staff=True)
        self.vendas.groups.add(Group.objects.get_or_create(name=VENDAS)[0])
        self.pedido = PedidoProjeto3D.objects.create(
            nome="Marina Souza", whatsapp="11988887777", largura=Decimal("20"), comprimento=Decimal("15"),
            pe_direito=Decimal("4"), principal="Espaço esportivo kids (sob medida)", estilo="neon", cor="#22c55e",
            semente=7, escolhas=_escolha(), resumo={"coube": [{"nome": "Área baby", "qtd": "1"}],
                                                   "ficou_de_fora": [{"nome": "Touro", "motivo": "alto demais"}]},
        )

    def test_a_lista_e_a_ficha_com_o_3d(self):
        self.client.force_login(self.vendas)
        lista = self.client.get("/site/projetos-3d/", HTTP_HOST=HOST)
        self.assertEqual(lista.status_code, 200)
        self.assertContains(lista, "Marina Souza")
        self.assertContains(lista, "20 × 15 m, pé-direito 4 m")
        ficha = self.client.get(f"/site/projetos-3d/{self.pedido.pk}/", HTTP_HOST=HOST)
        self.assertEqual(ficha.status_code, 200)
        self.assertContains(ficha, 'data-modo="painel"')
        self.assertContains(ficha, 'id="p3dEstado"')
        self.assertContains(ficha, "wa.me/5511988887777")
        self.assertContains(ficha, "Touro</strong>: alto demais")
        self.assertNotContains(ficha, "data-pedir")
        estado = ficha.context["projeto_estado"]
        self.assertEqual(estado["espaco"], {"largura": 20.0, "comprimento": 15.0, "pe_direito": 4.0})
        self.assertEqual((estado["semente"], estado["estilo"]), (7, "neon"))

    def test_a_ficha_mostra_as_fotos_do_espaco(self):
        from django.core.files.base import ContentFile

        pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, pasta, True)
        with override_settings(MEDIA_ROOT=pasta):
            foto = FotoDoEspaco(pedido=self.pedido, tipo="foto", cantos=CANTOS)
            foto.imagem.save("espaco-1.jpg", ContentFile(_jpeg()), save=True)
            montagem = FotoDoEspaco(pedido=self.pedido, tipo="montagem")
            montagem.imagem.save("projeto-na-foto-1.jpg", ContentFile(_jpeg()), save=True)
            self.client.force_login(self.vendas)
            ficha = self.client.get(f"/site/projetos-3d/{self.pedido.pk}/", HTTP_HOST=HOST)
        self.assertContains(ficha, "O espaço do cliente (1 foto)")
        self.assertContains(ficha, montagem.imagem.url)
        self.assertContains(ficha, 'id="p3dFotosDados"')
        self.assertContains(ficha, 'id="p3dFotosPasso"')
        self.assertEqual(ficha.context["projeto_fotos"], [{"url": foto.imagem.url, "cantos": CANTOS}])
        self.assertEqual(ficha.context["fotos"][0]["montagem"], montagem)

    def test_muda_a_situacao_e_anota(self):
        self.client.force_login(self.vendas)
        self.client.post(f"/site/projetos-3d/{self.pedido.pk}/", {"status": "conversa", "anotacao": "Ligar sexta"}, HTTP_HOST=HOST)
        self.pedido.refresh_from_db()
        self.assertEqual((self.pedido.status, self.pedido.anotacao), ("conversa", "Ligar sexta"))

    def test_so_a_equipe_comercial(self):
        producao = User.objects.create_user("producao", password="senha-segura", is_staff=True)
        producao.groups.add(Group.objects.get_or_create(name=PRODUCAO)[0])
        self.client.force_login(producao)
        self.assertNotEqual(self.client.get("/site/projetos-3d/", HTTP_HOST=HOST).status_code, 200)

    def test_o_sino_avisa_do_projeto_novo(self):
        from sistema_interno.avisos import coletar

        self.assertIn("projetos_3d", [a.chave for a in coletar(self.vendas)])
        self.pedido.status = "conversa"
        self.pedido.save()
        self.assertNotIn("projetos_3d", [a.chave for a in coletar(self.vendas)])


class FotoNodeTests(TestCase):
    """A conta da câmera da foto (JavaScript): core/tests_js/foto3d.mjs."""

    def test_a_camera_da_foto_confere(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Sem node para rodar o JavaScript da foto")
        resultado = subprocess.run([node, str(RAIZ / "tests_js" / "foto3d.mjs")], capture_output=True, text=True, timeout=120)
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)


class ArrumadorTests(TestCase):
    """O arrumador (JavaScript) com o catálogo de verdade: core/tests_js/arrumador.mjs."""

    def test_o_arrumador_confere(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Sem node para rodar o JavaScript do arrumador")
        Brinquedos.objects.create(nome_brinquedo="Fliperama Retrô", descricao="x", valor_brinquedo=Decimal("1"), avaliacao=5,
                                  altura_m=Decimal("1.7"), largura_m=Decimal("0.7"), profundidade_m=Decimal("0.8"))
        Brinquedos.objects.create(nome_brinquedo="Air Game Hockey", descricao="x", valor_brinquedo=Decimal("1"), avaliacao=5,
                                  altura_m=Decimal("1.0"), largura_m=Decimal("1.1"), profundidade_m=Decimal("2.1"))
        Brinquedos.objects.create(nome_brinquedo="Lazer Shot", descricao="x", valor_brinquedo=Decimal("1"), avaliacao=5,
                                  altura_m=Decimal("1.7"), largura_m=Decimal("0.7"), profundidade_m=Decimal("0.8"))
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "catalogo.json"
            arquivo.write_text(json.dumps(projeto3d.catalogo()))
            resultado = subprocess.run([node, str(RAIZ / "tests_js" / "arrumador.mjs"), str(arquivo)],
                                       capture_output=True, text=True, timeout=120)
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
