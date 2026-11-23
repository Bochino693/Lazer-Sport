"""Os arquivos no nosso banco (LEIA-ME-V10, seção 130).

O Cloudinary desativou a conta: toda foto que só existia lá sumiu e todo
envio voltava 500. Aqui: o armazenamento no banco (público e privado), o
nome antigo que continua no Cloudinary, a foto grande que vira WebP, a
entrega (/midia/banco/: cabeçalhos, ETag/304, larguras, 404, o privado que
nunca sai), o espelho com o Cloudinary fora do ar e de volta, a restauração
pelas cópias do repositório e a exportação do Cloudinary (o ZIP) pela tela
do dono. Tudo com imagens sintéticas.
"""

from __future__ import annotations

import io
import shutil
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.db import DatabaseError, connection
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from PIL import Image

from . import arquivos_no_banco as anb
from . import espelho_midia, restaurar_midia
from .fotos import reduzir_imagem, url_da_imagem
from .models import ArquivoNoBanco, Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, ImagemPeca, PecasReposicao

INTERNO = {"HTTP_HOST": "interno.testserver"}
AJAX = {**INTERNO, "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


def foto(formato="PNG", tamanho=(320, 240), cor=(200, 60, 40), alfa=False, ruido=False) -> bytes:
    if ruido:
        imagem = Image.merge("RGB", [Image.effect_noise(tamanho, 90) for _ in range(3)])
    else:
        imagem = Image.new("RGBA" if alfa else "RGB", tamanho, (*cor, 120) if alfa else cor)
    saida = io.BytesIO()
    imagem.save(saida, formato, **({"quality": 95} if formato == "JPEG" else {}))
    return saida.getvalue()


def brinquedo(nome="Air Game Teste", imagem=""):
    return Brinquedos.objects.create(nome_brinquedo=nome, descricao="x", avaliacao=5, voltz="220V",
                                     imagem_brinquedo=imagem)


class CacheTemporario:
    """Cada classe usa uma pasta própria para a cópia das fotos no disco."""

    @classmethod
    def setUpClass(cls):
        cls._pasta_cache = tempfile.mkdtemp(prefix="ls-midia-teste-")
        cls._override_cache = override_settings(MIDIA_CACHE_DIR=cls._pasta_cache, MIDIA_BANCO_URL_BASE="")
        cls._override_cache.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._override_cache.disable()
        shutil.rmtree(cls._pasta_cache, ignore_errors=True)


# ======================================================================
# NOMES E TIPOS
# ======================================================================
class NomesETiposTests(SimpleTestCase):
    def test_nome_novo_comeca_com_banco_e_e_sorteado(self):
        um = anb.nome_novo("imagens_brinquedos/foto.jpg", max_length=100)
        outro = anb.nome_novo("imagens_brinquedos/foto.jpg", max_length=100)
        self.assertTrue(um.startswith("banco/imagens_brinquedos/foto_"))
        self.assertTrue(um.endswith(".jpg"))
        self.assertNotEqual(um, outro)
        self.assertRegex(um, r"_[a-z0-9]{6}\.jpg$")

    def test_nome_novo_cabe_na_coluna_com_folga_para_o_webp(self):
        nome = anb.nome_novo("imagens_brinquedos/" + "x" * 200 + ".png", max_length=100)
        self.assertLessEqual(len(nome) + 1, 100)

    def test_nome_do_espelho_e_o_de_antes_com_banco_na_frente(self):
        self.assertEqual(anb.nome_do_espelho("pecas_reposicao/cabo_ci5liw", 100), "banco/pecas_reposicao/cabo_ci5liw")
        longo = "imagens_brinquedos/galeria/" + "a" * 90
        curto = anb.nome_do_espelho(longo, 100)
        self.assertLessEqual(len(curto), 100)
        self.assertTrue(curto.startswith("banco/imagens_brinquedos/galeria/aaa"))
        self.assertEqual(curto, anb.nome_do_espelho(longo, 100))  # o mesmo nome antigo, o mesmo nome novo

    def test_tipo_pelo_conteudo(self):
        self.assertEqual(anb.tipo_do_conteudo(foto("PNG")), "image/png")
        self.assertEqual(anb.tipo_do_conteudo(foto("JPEG")), "image/jpeg")
        self.assertEqual(anb.tipo_do_conteudo(foto("WEBP")), "image/webp")
        self.assertEqual(anb.tipo_do_conteudo(b"%PDF-1.4 ..."), "application/pdf")
        self.assertEqual(anb.tipo_do_conteudo(b"glTF\x02\x00\x00\x00"), "model/gltf-binary")
        self.assertEqual(anb.tipo_do_conteudo(b"<html>", "x.html"), "text/html")

    def test_reduzir_imagem_pede_a_largura_da_lista(self):
        url = "/midia/banco/imagens_brinquedos/foto_ab12cd.webp"
        # a forma que o Cloudflare guarda na borda (seção 132)
        self.assertEqual(reduzir_imagem(url, 768), url + ".w960.webp")
        self.assertEqual(reduzir_imagem(url, 160), url + ".w160.webp")
        self.assertEqual(reduzir_imagem(url, 5000), url + ".w1600.webp")
        self.assertEqual(reduzir_imagem(url + ".w480.webp", 160), url + ".w480.webp")
        # o endereço antigo com ?w= continua como veio
        self.assertEqual(reduzir_imagem(url + "?w=480", 160), url + "?w=480")
        sem_extensao = "https://www.lazersport.com.br/midia/banco/categorias/area-ninja-97fe6ad9c5_q7l6oi"
        self.assertEqual(reduzir_imagem(sem_extensao, 480), sem_extensao + ".w480.webp")
        nuvem = "https://res.cloudinary.com/conta/image/upload/v1/imagens_brinquedos/foto"
        self.assertIn("/upload/c_limit,w_768,f_auto,q_auto/", reduzir_imagem(nuvem, 768))


class ReducaoDaFotoTests(SimpleTestCase):
    def test_foto_grande_vira_webp_de_ate_2400(self):
        grande = foto("JPEG", (3000, 2000), ruido=True)
        dados, tipo, mudou = anb.preparar_imagem(grande, "image/jpeg")
        self.assertTrue(mudou)
        self.assertEqual(tipo, "image/webp")
        with Image.open(io.BytesIO(dados)) as imagem:
            self.assertEqual(imagem.format, "WEBP")
            self.assertEqual(max(imagem.size), 2400)
        self.assertLess(len(dados), len(grande))

    def test_foto_pequena_e_leve_fica_como_veio(self):
        pequena = foto("PNG", (300, 200))
        self.assertEqual(anb.preparar_imagem(pequena, "image/png"), (pequena, "image/png", False))

    def test_png_recortado_continua_transparente(self):
        recorte = foto("PNG", (2600, 1200), alfa=True)
        dados, tipo, mudou = anb.preparar_imagem(recorte, "image/png")
        self.assertTrue(mudou)
        with Image.open(io.BytesIO(dados)) as imagem:
            self.assertIn(imagem.mode, ("RGBA", "LA"))

    def test_o_que_nao_e_foto_nao_e_mexido(self):
        self.assertEqual(anb.preparar_imagem(b"%PDF-1.4", "application/pdf"), (b"%PDF-1.4", "application/pdf", False))


# ======================================================================
# O ARMAZENAMENTO PÚBLICO
# ======================================================================
class MidiaNoBancoTests(CacheTemporario, TestCase):
    def setUp(self):
        self.storage = anb.MidiaNoBanco()

    def test_salvar_abrir_endereco_e_apagar(self):
        dados = foto("PNG")
        nome = self.storage.save("imagens_brinquedos/foto.png", ContentFile(dados), max_length=100)
        self.assertTrue(nome.startswith("banco/imagens_brinquedos/foto_"))
        linha = ArquivoNoBanco.objects.get(nome=nome)
        self.assertTrue(linha.publico)
        self.assertEqual((linha.tipo, linha.tamanho, linha.origem), ("image/png", len(dados), "envio"))
        self.assertEqual(len(linha.sha256), 64)
        with self.storage.open(nome) as arquivo:
            self.assertEqual(arquivo.read(), dados)
        self.assertTrue(self.storage.exists(nome))
        self.assertEqual(self.storage.size(nome), len(dados))
        self.assertEqual(self.storage.url(nome), f"/midia/{nome}")
        self.storage.delete(nome)
        self.assertFalse(ArquivoNoBanco.objects.filter(nome=nome).exists())
        self.assertFalse(self.storage.exists(nome))

    @override_settings(MIDIA_BANCO_URL_BASE="https://www.exemplo.invalid")
    def test_endereco_absoluto_em_producao_para_o_email(self):
        self.assertEqual(self.storage.url("banco/a/b_ab12cd.webp"), "https://www.exemplo.invalid/midia/banco/a/b_ab12cd.webp")

    def test_endereco_e_conta_nao_consulta(self):
        with self.assertNumQueries(0):
            for i in range(50):
                self.storage.url(f"banco/imagens_brinquedos/foto{i}_ab12cd.webp")
                self.storage.url(f"imagens_brinquedos/antiga{i}_ab12cd")

    def test_nome_antigo_continua_no_cloudinary(self):
        url = self.storage.url("imagens_brinquedos/galeria/cena-air-game-home-10bb33e058_ik4fg5")
        self.assertIn("res.cloudinary.com", url)
        self.assertIn("/image/upload/", url)
        self.assertIn("/raw/upload/", anb.MidiaNoBanco(legado="raw").url("objetos_3d/x_ab12cd.glb"))

    def test_nome_antigo_com_o_cloudinary_fora_do_ar_e_arquivo_que_nao_esta(self):
        resposta = mock.Mock(status_code=401, headers={"x-cld-error": "cloud_name dgikjmki8 is disabled"}, content=b"")
        with mock.patch("requests.get", return_value=resposta):
            with self.assertRaises(anb.CloudinaryForaDoAr):
                self.storage.open("imagens_brinquedos/antiga_ab12cd")
            with self.assertRaises(FileNotFoundError):  # quem trata OSError trata este também
                self.storage.open("imagens_brinquedos/antiga_ab12cd")
        self.assertFalse(self.storage.exists("imagens_brinquedos/antiga_ab12cd"))

    def test_apagar_o_antigo_com_o_cloudinary_fora_nao_derruba(self):
        with mock.patch("cloudinary.uploader.destroy", side_effect=Exception("disabled")):
            self.storage.delete("imagens_brinquedos/antiga_ab12cd")  # não levanta

    def test_foto_grande_entra_como_webp_com_o_nome_em_webp(self):
        nome = self.storage.save("imagens_brinquedos/grande.jpg", ContentFile(foto("JPEG", (3000, 1800), ruido=True)),
                                 max_length=100)
        self.assertTrue(nome.endswith(".webp"), nome)
        self.assertLessEqual(len(nome), 100)
        self.assertEqual(ArquivoNoBanco.objects.get(nome=nome).tipo, "image/webp")

    def test_glb_nao_e_reduzido(self):
        glb = b"glTF\x02\x00\x00\x00" + b"\x00" * 900_000
        nome = anb.MidiaNoBanco(legado="raw").save("objetos_3d/modelo.glb", ContentFile(glb), max_length=100)
        self.assertTrue(nome.endswith(".glb"))
        self.assertEqual(ArquivoNoBanco.objects.get(nome=nome).tamanho, len(glb))

    def test_banco_fora_do_ar_vira_erro_de_formulario(self):
        with mock.patch.object(anb, "guardar", side_effect=DatabaseError("caiu")):
            with self.assertRaises(anb.ArmazenamentoIndisponivel) as erro:
                self.storage.save("imagens_brinquedos/foto.png", ContentFile(foto()), max_length=100)
        self.assertEqual(erro.exception.titulo, "Arquivo não guardado")

    def test_campo_de_imagem_do_produto_guarda_no_banco(self):
        b = brinquedo()
        foto_do_produto = ImagemBrinquedo(brinquedo=b, tipo="perfil", ordem=1)
        foto_do_produto.imagem.save("air.png", ContentFile(foto()), save=True)
        foto_do_produto.refresh_from_db()
        self.assertTrue(foto_do_produto.imagem.name.startswith("banco/imagens_brinquedos/"))
        self.assertTrue(url_da_imagem(foto_do_produto.imagem).startswith("/midia/banco/imagens_brinquedos/"))


# ======================================================================
# A ENTREGA
# ======================================================================
class EntregaTests(CacheTemporario, TestCase):
    def setUp(self):
        self.dados = foto("PNG", (800, 600))
        self.nome = anb.guardar("banco/imagens_brinquedos/foto_ab12cd.png", self.dados, publico=True)
        anb.apagar_do_disco(self.nome)

    def test_entrega_com_cache_de_um_ano_e_etag(self):
        resposta = self.client.get("/midia/" + self.nome)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(b"".join(resposta.streaming_content) if resposta.streaming else resposta.content, self.dados)
        self.assertEqual(resposta["Content-Type"], "image/png")
        self.assertEqual(resposta["Cache-Control"], "public, max-age=31536000, immutable")
        sha = ArquivoNoBanco.objects.get(nome=self.nome).sha256
        self.assertEqual(resposta["ETag"], f'"{sha[:32]}"')
        self.assertEqual(resposta["X-Content-Type-Options"], "nosniff")
        self.assertEqual(resposta["Access-Control-Allow-Origin"], "*")
        self.assertNotIn("Set-Cookie", resposta)

    def test_304_com_a_mesma_etag(self):
        etag = self.client.get("/midia/" + self.nome)["ETag"]
        resposta = self.client.get("/midia/" + self.nome, HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(resposta.status_code, 304)
        self.assertEqual(resposta["ETag"], etag)

    def test_segunda_vez_sai_do_disco_sem_consulta(self):
        with self.assertNumQueries(1):
            self.client.get("/midia/" + self.nome)
        with self.assertNumQueries(0):
            resposta = self.client.get("/midia/" + self.nome)
        self.assertEqual(resposta.status_code, 200)

    def test_logado_nao_paga_sessao_nem_usuario_por_foto(self):
        conta = get_user_model().objects.create_user("equipe-foto", "e@exemplo.invalid", "x", is_staff=True)
        self.client.force_login(conta)
        self.client.get("/midia/" + self.nome)
        with CaptureQueriesContext(connection) as consultas:
            self.client.get("/midia/" + self.nome, **INTERNO)
        self.assertEqual(len(consultas), 0, [c["sql"] for c in consultas])

    def test_largura_da_lista_devolve_webp_reduzido(self):
        resposta = self.client.get("/midia/" + self.nome + "?w=480")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Content-Type"], "image/webp")
        corpo = b"".join(resposta.streaming_content) if resposta.streaming else resposta.content
        with Image.open(io.BytesIO(corpo)) as imagem:
            self.assertEqual(imagem.width, 480)
        self.assertTrue(resposta["ETag"].endswith('-w480"'))
        de_novo = self.client.get("/midia/" + self.nome + "?w=480")  # agora do disco
        self.assertEqual(de_novo["Content-Type"], "image/webp")

    def test_a_forma_que_o_cloudflare_guarda_entrega_a_mesma_foto(self):
        antiga = self.client.get("/midia/" + self.nome + "?w=480")
        nova = self.client.get("/midia/" + self.nome + ".w480.webp")
        self.assertEqual(nova.status_code, 200)
        self.assertEqual(nova["Content-Type"], "image/webp")
        self.assertEqual(nova["ETag"], antiga["ETag"])
        self.assertIn("immutable", nova["Cache-Control"])
        self.assertNotIn("Set-Cookie", nova)  # o Cloudflare não guarda resposta com cookie
        corpo = b"".join(nova.streaming_content) if nova.streaming else nova.content
        with Image.open(io.BytesIO(corpo)) as imagem:
            self.assertEqual(imagem.width, 480)
        self.assertEqual(self.client.get("/midia/" + self.nome + ".w333.webp").status_code, 404)
        self.assertEqual(self.client.get("/midia/" + self.nome + ".w480.webp", **INTERNO).status_code, 200)

    def test_aquecer_disco_traz_as_publicas_e_deixa_as_privadas(self):
        anb.apagar_do_disco(self.nome)
        privado = anb.guardar("banco/rh/ab/abcdef.pdf", b"%PDF-1.4 documento", publico=False)
        self.assertEqual(anb.aquecer_disco(), 1)
        self.assertIsNotNone(anb._meta_do_disco(self.nome))
        self.assertIsNone(anb._meta_do_disco(privado))
        # depois, a entrega não consulta o banco
        with CaptureQueriesContext(connection) as consultas:
            self.assertEqual(self.client.get("/midia/" + self.nome + ".w480.webp").status_code, 200)
        self.assertEqual(len(consultas), 0)
        self.assertEqual(anb.aquecer_disco(), 0)  # já está tudo no disco

    def test_fila_cheia_vira_503_curto_e_nao_500(self):
        anb.apagar_do_disco(self.nome)
        with mock.patch.object(anb, "_vez") as vez:
            vez.acquire.return_value = False
            resposta = self.client.get("/midia/" + self.nome + ".w480.webp")
        self.assertEqual(resposta.status_code, 503)
        self.assertEqual(resposta["Retry-After"], "2")
        self.assertEqual(resposta["Cache-Control"], "no-store")

    def test_largura_fora_da_lista_e_404(self):
        self.assertEqual(self.client.get("/midia/" + self.nome + "?w=333").status_code, 404)
        self.assertEqual(self.client.get("/midia/" + self.nome + "?w=abc").status_code, 404)

    def test_nome_que_nao_existe_e_404(self):
        self.assertEqual(self.client.get("/midia/banco/imagens_brinquedos/nao_existe.png").status_code, 404)
        self.assertEqual(self.client.get("/midia/banco/../core/settings.py").status_code, 404)

    def test_privado_nunca_sai(self):
        privado = anb.guardar("banco/rh/ab/abcdef.pdf", b"%PDF-1.4 documento", publico=False)
        self.assertEqual(self.client.get("/midia/" + privado).status_code, 404)
        self.assertEqual(self.client.get("/midia/" + privado, **INTERNO).status_code, 404)

    def test_tambem_no_endereco_interno(self):
        self.assertEqual(self.client.get("/midia/" + self.nome, **INTERNO).status_code, 200)

    def test_banco_fora_do_ar_e_503_curto(self):
        anb.apagar_do_disco(self.nome)
        with mock.patch.object(anb, "ler", side_effect=DatabaseError("caiu")):
            resposta = self.client.get("/midia/" + self.nome)
        self.assertEqual((resposta.status_code, resposta["Retry-After"]), (503, "5"))

    def test_so_leitura(self):
        self.assertEqual(self.client.post("/midia/" + self.nome).status_code, 405)

    def test_conteudo_ativo_sai_como_download_na_caixa_de_areia(self):
        html = anb.guardar("banco/jogo/pagina_ab12cd.html", b"<script>alert(1)</script>", publico=True,
                           tipo="text/html")
        resposta = self.client.get("/midia/" + html)
        self.assertEqual(resposta["Content-Disposition"], "attachment")
        self.assertIn("sandbox", resposta["Content-Security-Policy"])

    def test_copia_de_reserva_tem_cache_curto(self):
        reserva = anb.guardar("banco/imagens_brinquedos/reserva_ab12cd", foto(), publico=True, exata=False)
        self.assertEqual(self.client.get("/midia/" + reserva)["Cache-Control"], "public, max-age=86400")

    def test_a_view_do_urlconf_faz_o_mesmo(self):
        pedido = RequestFactory().get("/midia/" + self.nome)
        resposta = anb.midia_no_banco(pedido, self.nome[len("banco/"):])
        self.assertEqual(resposta.status_code, 200)


# ======================================================================
# O ESPELHO
# ======================================================================
class EspelhoTests(CacheTemporario, TestCase):
    def setUp(self):
        self.b = brinquedo(imagem="imagens_brinquedos/antiga_ab12cd")
        self.foto = ImagemBrinquedo.objects.create(brinquedo=self.b, tipo="perfil", ordem=1,
                                                   imagem="imagens_brinquedos/antiga_ab12cd")

    def test_com_o_cloudinary_de_volta_copia_e_reponta(self):
        dados = foto("JPEG")
        with mock.patch.object(anb, "baixar_endereco", return_value=dados) as baixar:
            saida = io.StringIO()
            call_command("espelhar_midia", stdout=saida)
        self.assertEqual(baixar.call_count, 1)  # o mesmo nome em dois campos: um download
        novo = "banco/imagens_brinquedos/antiga_ab12cd"
        self.b.refresh_from_db()
        self.foto.refresh_from_db()
        self.assertEqual((self.b.imagem_brinquedo.name, self.foto.imagem.name), (novo, novo))
        linha = ArquivoNoBanco.objects.get(nome=novo)
        self.assertEqual((linha.origem, linha.exata, linha.publico), ("cloudinary", True, True))
        self.assertIn("Copiados do Cloudinary: 1", saida.getvalue())
        self.assertEqual(espelho_midia.referencias(), {})

    def test_com_o_cloudinary_desativado_nao_muda_nada_e_avisa(self):
        with mock.patch.object(anb, "baixar_endereco", side_effect=anb.CloudinaryForaDoAr("disabled")):
            resultado = espelho_midia.espelhar()
            saida = io.StringIO()
            call_command("espelhar_midia", stdout=saida)
        self.assertTrue(resultado["fora_do_ar"])
        self.assertEqual(resultado["copiados"], 0)
        self.b.refresh_from_db()
        self.assertEqual(self.b.imagem_brinquedo.name, "imagens_brinquedos/antiga_ab12cd")
        self.assertFalse(ArquivoNoBanco.objects.exists())
        self.assertIn("fora do ar", saida.getvalue())

    def test_baixar_endereco_reconhece_o_disabled(self):
        recusado = mock.Mock(status_code=401, headers={"x-cld-error": "cloud_name x is disabled"}, content=b"")
        with mock.patch("requests.get", return_value=recusado):
            with self.assertRaises(anb.CloudinaryForaDoAr):
                anb.baixar_endereco("https://res.cloudinary.com/x/image/upload/v1/a")
        sumiu = mock.Mock(status_code=404, headers={}, content=b"")
        with mock.patch("requests.get", return_value=sumiu):
            with self.assertRaises(FileNotFoundError) as erro:
                anb.baixar_endereco("https://res.cloudinary.com/x/image/upload/v1/a")
        self.assertNotIsInstance(erro.exception, anb.CloudinaryForaDoAr)

    def test_o_que_o_cloudinary_nao_tem_fica_na_lista(self):
        with mock.patch.object(anb, "baixar_endereco", side_effect=FileNotFoundError("404")):
            resultado = espelho_midia.espelhar()
        self.assertEqual(resultado["faltando"], ["imagens_brinquedos/antiga_ab12cd"])

    def test_a_reserva_da_lugar_a_original(self):
        reserva = foto("PNG", cor=(10, 10, 10))
        espelho_midia.gravar_conteudo("imagens_brinquedos/antiga_ab12cd",
                                      espelho_midia.referencias()["imagens_brinquedos/antiga_ab12cd"],
                                      reserva, origem="copia_local", exata=False)
        original = foto("PNG", cor=(250, 10, 10))
        with mock.patch.object(anb, "baixar_endereco", return_value=original):
            resultado = espelho_midia.espelhar()
        self.assertEqual(resultado["trocados"], 1)
        linha = ArquivoNoBanco.objects.get(nome="banco/imagens_brinquedos/antiga_ab12cd")
        self.assertEqual((bytes(linha.conteudo), linha.exata, linha.origem), (original, True, "cloudinary"))

    def test_quem_trocou_a_foto_no_meio_tempo_ganha(self):
        grupo = espelho_midia.referencias()["imagens_brinquedos/antiga_ab12cd"]
        ImagemBrinquedo.objects.filter(pk=self.foto.pk).update(imagem="banco/imagens_brinquedos/nova_zz99zz.png")
        espelho_midia.gravar_conteudo("imagens_brinquedos/antiga_ab12cd", grupo, foto(), origem="cloudinary")
        self.foto.refresh_from_db()
        self.assertEqual(self.foto.imagem.name, "banco/imagens_brinquedos/nova_zz99zz.png")

    def test_orfaos_so_o_que_ninguem_usa_e_com_mais_de_um_dia(self):
        from datetime import timedelta

        from django.utils import timezone

        usado = anb.guardar("banco/imagens_brinquedos/usada_ab12cd.png", foto(), publico=True)
        ImagemBrinquedo.objects.filter(pk=self.foto.pk).update(imagem=usado)
        anb.guardar("banco/imagens_brinquedos/trocada_ab12cd.png", foto(), publico=True)
        anb.guardar("banco/imagens_brinquedos/agora_ab12cd.png", foto(), publico=True)
        ArquivoNoBanco.objects.exclude(nome__contains="agora").update(criado_em=timezone.now() - timedelta(days=2))
        self.assertEqual([n for n, _t in espelho_midia.orfaos()], ["banco/imagens_brinquedos/trocada_ab12cd.png"])
        saida = io.StringIO()
        call_command("restaurar_midia", "--orfaos", "--apagar", stdout=saida)
        self.assertIn("Apagados: 1", saida.getvalue())
        self.assertTrue(ArquivoNoBanco.objects.filter(nome=usado).exists())
        self.assertTrue(ArquivoNoBanco.objects.filter(nome__contains="agora").exists())

    def test_a_linha_de_fundo_nao_liga_nos_testes(self):
        self.assertFalse(espelho_midia.ativo())
        with override_settings(MIDIA_ESPELHO_AUTOMATICO=True, IS_RENDER=True):
            self.assertFalse(espelho_midia.ativo())  # manage.py test é comando

    def test_peca_acompanha_o_nome_conferido_pelo_recorte(self):
        peca = PecasReposicao.objects.create(nome="Cabo", descricao_peca="x")
        imagem = ImagemPeca.objects.create(peca_reposicao=peca, imagem="pecas_reposicao/cabo_ci5liw",
                                           recorte_de="pecas_reposicao/cabo_ci5liw")
        with mock.patch.object(anb, "baixar_endereco", return_value=foto()):
            espelho_midia.espelhar()
        imagem.refresh_from_db()
        self.assertEqual((imagem.imagem.name, imagem.recorte_de),
                         ("banco/pecas_reposicao/cabo_ci5liw", "banco/pecas_reposicao/cabo_ci5liw"))


# ======================================================================
# A RESTAURAÇÃO PELAS CÓPIAS DO REPOSITÓRIO
# ======================================================================
class CopiasDoRepositorioTests(CacheTemporario, TestCase):
    def setUp(self):
        self.raiz = Path(tempfile.mkdtemp(prefix="ls-restaurar-"))
        self.addCleanup(shutil.rmtree, self.raiz, True)
        site = self.raiz / "core" / "static" / "site"
        for pasta in ("capas_catalogo", "categorias", "reserva", "kits"):
            (site / pasta).mkdir(parents=True)
        (self.raiz / "media" / "imagens_brinquedos").mkdir(parents=True)
        self.capa = foto("WEBP", cor=(10, 120, 200))
        (site / "capas_catalogo" / "air-game-home.webp").write_bytes(self.capa)
        (site / "categorias" / "jogos-de-mesa.webp").write_bytes(foto("WEBP", cor=(90, 90, 20)))
        (site / "reserva" / "cabo-hdmi_ci5liw.png").write_bytes(foto("PNG", cor=(1, 2, 3)))
        (self.raiz / "media" / "imagens_brinquedos" / "produto1.PNG").write_bytes(foto("PNG", cor=(4, 5, 6)))
        for nome, valor in {"BASE": self.raiz, "SITE": site, "RESERVA": site / "reserva",
                            "MEDIA": self.raiz / "media", "REPOSICAO": self.raiz / "nada",
                            "RECORTAR": self.raiz / "nada.py"}.items():
            alvo = mock.patch.object(restaurar_midia, nome, valor)
            alvo.start()
            self.addCleanup(alvo.stop)
        import hashlib

        self.assinatura = hashlib.sha1(self.capa).hexdigest()[:10]

    def test_cada_regra_so_com_certeza(self):
        exata = brinquedo("Air Game Home", imagem=f"imagens_brinquedos/galeria/cena-air-game-home-{self.assinatura}_ik4fg5")
        nova_versao = brinquedo("Air Game Home 2", imagem="imagens_brinquedos/galeria/cena-air-game-home-0123456789_ab12cd")
        categoria_no_produto = brinquedo("Mesa", imagem="imagens_brinquedos/jogos-de-mesa-0123456789_ab12cd")
        categoria = CategoriasBrinquedos.objects.create(nome_categoria="Jogos de mesa",
                                                        imagem_categoria="categorias/jogos-de-mesa-0123456789_zz11zz")
        peca = PecasReposicao.objects.create(nome="Cabo HDMI", descricao_peca="x")
        foto_peca = ImagemPeca.objects.create(peca_reposicao=peca, imagem="pecas_reposicao/cabo-hdmi_ci5liw")
        antiga = brinquedo("Antigo", imagem="imagens_brinquedos/produto1_ab12cd")
        sem_copia = brinquedo("Sem cópia", imagem="imagens_brinquedos/foto-de-celular_qq22qq")
        parecido = brinquedo("Parecido", imagem="imagens_brinquedos/galeria/cena-air-game-home-premium-0123456789_ab12cd")

        resultado = restaurar_midia.restaurar_das_copias()

        def nome(objeto):
            objeto.refresh_from_db()
            campo = objeto.imagem_categoria if isinstance(objeto, CategoriasBrinquedos) else (
                objeto.imagem if isinstance(objeto, ImagemPeca) else objeto.imagem_brinquedo)
            return campo.name

        self.assertEqual(nome(exata), f"banco/imagens_brinquedos/galeria/cena-air-game-home-{self.assinatura}_ik4fg5")
        linha = ArquivoNoBanco.objects.get(nome=nome(exata))
        self.assertTrue(linha.exata)
        self.assertEqual(bytes(linha.conteudo), self.capa)
        self.assertTrue(nome(nova_versao).startswith("banco/"))
        self.assertFalse(ArquivoNoBanco.objects.get(nome=nome(nova_versao)).exata)
        self.assertTrue(nome(categoria).startswith("banco/"))
        self.assertTrue(nome(foto_peca).startswith("banco/"))
        self.assertTrue(ArquivoNoBanco.objects.get(nome=nome(foto_peca)).exata)
        self.assertTrue(nome(antiga).startswith("banco/"))
        # a foto da categoria NUNCA vira foto de produto; o nome que só "contém" a chave, também não
        self.assertEqual(nome(categoria_no_produto), "imagens_brinquedos/jogos-de-mesa-0123456789_ab12cd")
        self.assertEqual(nome(parecido), "imagens_brinquedos/galeria/cena-air-game-home-premium-0123456789_ab12cd")
        self.assertEqual(nome(sem_copia), "imagens_brinquedos/foto-de-celular_qq22qq")
        faltando = {item["nome"] for item in resultado.faltando}
        self.assertEqual(faltando, {"imagens_brinquedos/jogos-de-mesa-0123456789_ab12cd",
                                    "imagens_brinquedos/galeria/cena-air-game-home-premium-0123456789_ab12cd",
                                    "imagens_brinquedos/foto-de-celular_qq22qq"})
        # rodar de novo não muda nada
        self.assertEqual(restaurar_midia.restaurar_das_copias().restaurados, [])

    def test_simular_nao_grava(self):
        brinquedo("Antigo", imagem="imagens_brinquedos/produto1_ab12cd")
        resultado = restaurar_midia.restaurar_das_copias(simular=True)
        self.assertEqual(len(resultado.restaurados), 1)
        self.assertFalse(ArquivoNoBanco.objects.exists())

    def test_relatorio_do_que_falta(self):
        sem = brinquedo("Sem cópia", imagem="imagens_brinquedos/foto-de-celular_qq22qq")
        saida = io.StringIO()
        call_command("restaurar_midia", "--relatorio", stdout=saida)
        texto = saida.getvalue()
        self.assertIn("core.Brinquedos", texto)
        self.assertIn(f"#{sem.pk}", texto)
        self.assertIn("imagens_brinquedos/foto-de-celular_qq22qq", texto)


class RecortesDasPecasTests(CacheTemporario, TestCase):
    def test_o_recorte_registrado_volta_so_na_foto_da_peca(self):
        raiz = Path(tempfile.mkdtemp(prefix="ls-recortes-"))
        self.addCleanup(shutil.rmtree, raiz, True)
        (raiz / "reposicao").mkdir()
        (raiz / "reposicao" / "mini-caixa.webp").write_bytes(foto("WEBP", alfa=True))
        (raiz / "recortar.py").write_text(
            'PECAS = {"mini-caixa": (8, "Mini Caixa", "pecas_reposicao/caixa_portatil_2_mrd6in", 0.07, "escuro")}\n',
            encoding="utf-8",
        )
        for nome, valor in {"BASE": raiz, "SITE": raiz / "site", "RESERVA": raiz / "site" / "reserva",
                            "MEDIA": raiz / "media", "REPOSICAO": raiz / "reposicao",
                            "RECORTAR": raiz / "recortar.py"}.items():
            alvo = mock.patch.object(restaurar_midia, nome, valor)
            alvo.start()
            self.addCleanup(alvo.stop)
        peca = PecasReposicao.objects.create(nome="Mini Caixa", descricao_peca="x")
        imagem = ImagemPeca.objects.create(peca_reposicao=peca, imagem="pecas_reposicao/caixa_portatil_2_mrd6in")
        produto = brinquedo("Outro", imagem="pecas_reposicao/caixa_portatil_2_mrd6in-x")
        restaurar_midia.restaurar_das_copias()
        imagem.refresh_from_db()
        produto.refresh_from_db()
        self.assertTrue(imagem.imagem.name.startswith("banco/"))
        self.assertFalse(ArquivoNoBanco.objects.get(nome=imagem.imagem.name).exata)
        self.assertFalse(produto.imagem_brinquedo.name.startswith("banco/"))


# ======================================================================
# A EXPORTAÇÃO DO CLOUDINARY (ZIP)
# ======================================================================
def zip_com(entradas) -> bytes:
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as arquivo:
        for nome, dados in entradas.items():
            arquivo.writestr(nome, dados)
    return saida.getvalue()


class ExportacaoDoCloudinaryTests(CacheTemporario, TestCase):
    def setUp(self):
        self.b = brinquedo(imagem="imagens_brinquedos/galeria/cena-x-0123456789_ik4fg5")
        self.foto_b = ImagemBrinquedo.objects.create(brinquedo=self.b, tipo="perfil", ordem=1,
                                                     imagem="imagens_brinquedos/galeria/cena-x-0123456789_ik4fg5")
        peca = PecasReposicao.objects.create(nome="Maneta", descricao_peca="x")
        self.peca = ImagemPeca.objects.create(peca_reposicao=peca, imagem="pecas_reposicao/MANETA_zcqczy")
        self.pasta = Path(tempfile.mkdtemp(prefix="ls-zip-"))
        self.addCleanup(shutil.rmtree, self.pasta, True)

    def gravar_zip(self, entradas):
        caminho = self.pasta / "export.zip"
        caminho.write_bytes(zip_com(entradas))
        return caminho

    def test_cada_arquivo_volta_pelo_public_id(self):
        caminho = self.gravar_zip({
            "imagens_brinquedos/galeria/cena-x-0123456789_ik4fg5.webp": foto("WEBP"),
            "MANETA_zcqczy.png": foto("PNG"),  # a exportação "achatada" (sem a pasta)
            "imagens_brinquedos/ninguem-usa_aa11bb.jpg": foto("JPEG"),
            "imagens_brinquedos/texto_cc22dd.png": b"isto nao e uma foto",
            "__MACOSX/._lixo": b"x",
        })
        self.gravar_ref_texto = ImagemBrinquedo.objects.create(brinquedo=self.b, tipo="verso", ordem=2,
                                                               imagem="imagens_brinquedos/texto_cc22dd")
        resultado, proximo, total = restaurar_midia.importar_zip(caminho)
        self.assertIsNone(proximo)
        self.assertEqual(total, 4)
        self.b.refresh_from_db()
        self.foto_b.refresh_from_db()
        self.peca.refresh_from_db()
        self.assertEqual(self.b.imagem_brinquedo.name, "banco/imagens_brinquedos/galeria/cena-x-0123456789_ik4fg5")
        self.assertEqual(self.foto_b.imagem.name, self.b.imagem_brinquedo.name)
        self.assertEqual(self.peca.imagem.name, "banco/pecas_reposicao/MANETA_zcqczy")
        self.assertEqual(ArquivoNoBanco.objects.get(nome=self.peca.imagem.name).origem, "zip")
        self.assertEqual(resultado.nao_referenciados, ["imagens_brinquedos/ninguem-usa_aa11bb.jpg"])
        self.assertEqual([r["nome"] for r in resultado.recusados], ["imagens_brinquedos/texto_cc22dd.png"])
        self.assertEqual(len(resultado.restaurados), 2)

    def test_o_zip_em_partes_continua_de_onde_parou(self):
        caminho = self.gravar_zip({
            "imagens_brinquedos/galeria/cena-x-0123456789_ik4fg5.webp": foto("WEBP"),
            "pecas_reposicao/MANETA_zcqczy.png": foto("PNG"),
        })
        mapa = restaurar_midia.Mapa()
        relogio = mock.Mock()
        relogio.monotonic.side_effect = [0, 1000]
        with mock.patch.object(restaurar_midia, "time", relogio):
            resultado, proximo, total = restaurar_midia.importar_zip(caminho, prazo=5, mapa=mapa)
        self.assertEqual((proximo, total), (1, 2))
        resultado, proximo, _total = restaurar_midia.importar_zip(caminho, inicio=proximo, mapa=mapa, resultado=resultado)
        self.assertIsNone(proximo)
        self.assertEqual(len(resultado.restaurados), 2)

    def test_a_exportacao_troca_a_copia_de_reserva(self):
        grupo = espelho_midia.referencias()["pecas_reposicao/MANETA_zcqczy"]
        espelho_midia.gravar_conteudo("pecas_reposicao/MANETA_zcqczy", grupo, foto("PNG", cor=(1, 1, 1)),
                                      origem="copia_local", exata=False)
        original = foto("PNG", cor=(255, 0, 0))
        resultado, _p, _t = restaurar_midia.importar_zip(self.gravar_zip({"pecas_reposicao/MANETA_zcqczy.png": original}))
        self.assertEqual(len(resultado.restaurados), 1)
        linha = ArquivoNoBanco.objects.get(nome="banco/pecas_reposicao/MANETA_zcqczy")
        self.assertEqual((bytes(linha.conteudo), linha.exata), (original, True))
        de_novo, _p, _t = restaurar_midia.importar_zip(self.gravar_zip({"pecas_reposicao/MANETA_zcqczy.png": original}))
        self.assertEqual((de_novo.restaurados, de_novo.ja), ([], ["banco/pecas_reposicao/MANETA_zcqczy"]))

    def test_comando_com_o_zip(self):
        caminho = self.gravar_zip({"pecas_reposicao/MANETA_zcqczy.png": foto("PNG")})
        saida = io.StringIO()
        call_command("restaurar_midia", "--zip", str(caminho), stdout=saida)
        self.assertIn("Restaurados: 1", saida.getvalue())


@override_settings(MIDIA_BANCO_URL_BASE="")
class TelaRestaurarFotosTests(CacheTemporario, TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.dono = Usuario.objects.create_superuser("dono-fotos", "d@exemplo.invalid", "x")
        cls.gestora = Usuario.objects.create_user("gestora-fotos", "g@exemplo.invalid", "x")
        from sistema_interno.permissoes import atribuir_funcoes

        atribuir_funcoes(cls.gestora, ["gestao"])

    def setUp(self):
        peca = PecasReposicao.objects.create(nome="Maneta", descricao_peca="x")
        self.peca = ImagemPeca.objects.create(peca_reposicao=peca, imagem="pecas_reposicao/MANETA_zcqczy")

    def post(self, **dados):
        return self.client.post("/restaurar-fotos/", dados, **AJAX)

    def test_so_o_superadministrador(self):
        self.client.force_login(self.gestora)
        self.assertEqual(self.client.get("/restaurar-fotos/", **INTERNO).status_code, 302)
        resposta = self.post(acao="comecar", nome="x.zip", tamanho="10")
        self.assertEqual(resposta.status_code, 302)

    def test_a_tela_mostra_o_que_falta_sem_select(self):
        self.client.force_login(self.dono)
        tela = self.client.get("/restaurar-fotos/", **INTERNO)
        self.assertEqual(tela.status_code, 200)
        self.assertContains(tela, "Restaurar fotos")
        self.assertContains(tela, "Fotos das peças")
        self.assertContains(tela, "pecas_reposicao/MANETA_zcqczy")
        self.assertNotContains(tela, "<select")
        dados = self.client.get("/restaurar-fotos/?formato=json", **INTERNO).json()
        self.assertEqual(dados["faltando_nomes"], 1)

    def test_envio_em_pedacos_e_processamento(self):
        self.client.force_login(self.dono)
        conteudo = zip_com({"pecas_reposicao/MANETA_zcqczy.png": foto("PNG"), "outro_aa11bb.png": foto("PNG")})
        envio = self.post(acao="comecar", nome="export.zip", tamanho=str(len(conteudo))).json()["envio"]
        meio = len(conteudo) // 2
        from django.core.files.uploadedfile import SimpleUploadedFile

        primeiro = self.client.post("/restaurar-fotos/", {"acao": "pedaco", "envio": envio, "posicao": "0",
                                                          "pedaco": SimpleUploadedFile("p", conteudo[:meio])}, **AJAX)
        self.assertEqual(primeiro.json()["recebido"], meio)
        fora = self.client.post("/restaurar-fotos/", {"acao": "pedaco", "envio": envio, "posicao": "0",
                                                      "pedaco": SimpleUploadedFile("p", conteudo[:meio])}, **AJAX)
        self.assertEqual((fora.status_code, fora.json()["recebido"]), (409, meio))
        self.client.post("/restaurar-fotos/", {"acao": "pedaco", "envio": envio, "posicao": str(meio),
                                               "pedaco": SimpleUploadedFile("p", conteudo[meio:])}, **AJAX)
        resposta = self.post(acao="processar", envio=envio)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        corpo = resposta.json()
        self.assertIsNone(corpo["proximo"])
        self.assertEqual(corpo["resumo"]["restaurados"], 1)
        self.assertEqual(corpo["nao_referenciados"], ["outro_aa11bb.png"])
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.imagem.name, "banco/pecas_reposicao/MANETA_zcqczy")
        self.assertEqual(self.post(acao="processar", envio=envio).status_code, 410)  # a pasta do envio saiu

    def test_arquivo_grande_demais_vira_janela(self):
        self.client.force_login(self.dono)
        resposta = self.post(acao="comecar", nome="enorme.zip", tamanho=str(600 * 1024 * 1024))
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.json()["titulo"], "Arquivo grande demais")
        self.assertEqual(resposta.json()["campo"], "arquivos")

    def test_zip_quebrado_vira_janela(self):
        self.client.force_login(self.dono)
        ruim = b"PK\x03\x04" + b"\x00" * 64
        envio = self.post(acao="comecar", nome="ruim.zip", tamanho=str(len(ruim))).json()["envio"]
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.post("/restaurar-fotos/", {"acao": "pedaco", "envio": envio, "posicao": "0",
                                               "pedaco": SimpleUploadedFile("p", ruim)}, **AJAX)
        resposta = self.post(acao="processar", envio=envio)
        self.assertIn(resposta.status_code, (200, 400))
        self.assertNotEqual(resposta.status_code, 500)

    def test_foto_solta(self):
        self.client.force_login(self.dono)
        dados = foto("PNG")
        envio = self.post(acao="comecar", nome="MANETA_zcqczy.png", tamanho=str(len(dados))).json()["envio"]
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.post("/restaurar-fotos/", {"acao": "pedaco", "envio": envio, "posicao": "0",
                                               "pedaco": SimpleUploadedFile("p", dados)}, **AJAX)
        corpo = self.post(acao="processar", envio=envio).json()
        self.assertEqual(corpo["resumo"]["restaurados"], 1)

    def test_no_menu_da_administracao(self):
        self.client.force_login(self.dono)
        tela = self.client.get("/restaurar-fotos/", **INTERNO)
        self.assertContains(tela, 'href="/restaurar-fotos/"')


# ======================================================================
# O ERRO DO ARMAZENAMENTO NUNCA É 500
# ======================================================================
class ErroDoArmazenamentoTests(SimpleTestCase):
    def test_o_middleware_devolve_a_janela(self):
        from .middleware import InternalResponseRecoveryMiddleware

        pedido = RequestFactory().post("/qualquer/", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        pedido.is_interno = True
        resposta = InternalResponseRecoveryMiddleware(lambda r: None).process_exception(
            pedido, anb.ArmazenamentoIndisponivel())
        self.assertEqual(resposta.status_code, 400)
        import json

        corpo = json.loads(resposta.content)
        self.assertEqual((corpo["status"], corpo["titulo"]), ("erro", "Arquivo não guardado"))

    def test_a_referencia_vai_no_texto_do_500(self):
        from sistema_interno.resiliencia import erro_interno
        import json

        pedido = RequestFactory().post("/x/", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        pedido.ls_request_id = "ref123abc"
        corpo = json.loads(erro_interno(pedido).content)
        self.assertIn("ref123abc", corpo["msg"])
        pedido_sem = RequestFactory().post("/x/", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertNotIn("referência", json.loads(erro_interno(pedido_sem).content)["msg"])
