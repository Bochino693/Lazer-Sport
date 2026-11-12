"""As fotos sem fundo (branca ou transparente) ficam fora do site, sozinhas (LEIA-ME 72).

O cliente: "me diga sobre as imagens de fundo branco dos brinquedos, por que
ainda aparecem? elas devem ficar de fora dos carrosseis e cards, ficando
somente para outras finalidades." O que estes testes protegem:

  * o painel: a foto enviada sem fundo (a frente, os lados, a posição de um
    adesivo) vira "recorte para artes" sozinha, fica guardada e some do site;
    a capa sem fundo dá lugar à primeira foto com fundo;
  * a varredura (a 0185, só no Render, e o comando `fotos_sem_fundo`): marca
    as que ninguém marcou, rodar de novo não muda nada nem baixa de novo, a
    falha de rede fica para a próxima, a capa em cena não é tocada, nada é
    apagado, a volta devolve tudo, o --simular não muda nada;
  * o site: a galeria, os cards (home, brinquedos, categoria, loja, busca), o
    giro, a vitrine do topo e a Arena não mostram a foto sem fundo;
  * a reserva: o brinquedo sem NENHUMA foto com fundo mostra o que tem (o card
    não fica vazio) e o painel avisa "precisa de foto com fundo".
"""

import importlib
import json
import re
import tempfile
from decimal import Decimal
from io import BytesIO, StringIO
from unittest import mock

from django.apps import apps as registro
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from PIL import Image, ImageDraw

from . import conferir_fotos, fotos_dos_cards
from .models import Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, galeria_publica
from .views_arena import dados_publicos_da_arena

migracao_0184 = importlib.import_module("core.migrations.0184_conferencia_do_fundo")
migracao_0185 = importlib.import_module("core.migrations.0185_fotos_sem_fundo_fora_do_site")

INTERNO = {"HTTP_HOST": "interno.testserver"}
AJAX = {**INTERNO, "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


def _calado(*_a, **_k):
    return None


def _png(desenho="cena"):
    """Os bytes de uma foto: "cena" (com fundo: ruído), "branco" (fundo branco) ou "recorte" (transparente)."""
    if desenho == "cena":
        imagem = Image.merge("RGB", [Image.effect_noise((96, 72), 90) for _ in range(3)])
    elif desenho == "branco":
        imagem = Image.new("RGB", (96, 72), "white")
        ImageDraw.Draw(imagem).rectangle((24, 12, 70, 66), fill=(20, 60, 200))
    else:
        imagem = Image.new("RGBA", (96, 72), (0, 0, 0, 0))
        ImageDraw.Draw(imagem).rectangle((24, 12, 70, 66), fill=(20, 60, 200, 255))
    saida = BytesIO()
    imagem.save(saida, "PNG")
    return saida.getvalue()


def _envio(nome, desenho="cena"):
    return SimpleUploadedFile(nome, _png(desenho), content_type="image/png")


class _ComDisco(TestCase):
    """As fotos num disco temporário (os arquivos existem: a conferência de verdade lê cada um)."""

    def setUp(self):
        cache.clear()
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.disco = FileSystemStorage(location=pasta.name, base_url="/media/")
        for campo in (Brinquedos._meta.get_field("imagem_brinquedo"), ImagemBrinquedo._meta.get_field("imagem")):
            troca = mock.patch.object(campo, "storage", self.disco)
            troca.start()
            self.addCleanup(troca.stop)
        self.categoria = CategoriasBrinquedos.objects.create(nome_categoria="Jogos de Mesa", imagem_categoria="categorias/m.png")

    def _arquivo(self, nome, desenho):
        return self.disco.save(f"imagens_brinquedos/{nome}.png", BytesIO(_png(desenho)))

    def _produto(self, nome, fotos, capa=None):
        """O brinquedo com as fotos [(tipo, nome, desenho, papel)]; a capa é a primeira (ou `capa`)."""
        arquivos = [(tipo, self._arquivo(arquivo, desenho), papel) for tipo, arquivo, desenho, papel in fotos]
        brinquedo = Brinquedos.objects.create(
            nome_brinquedo=nome, descricao=f"{nome}.", avaliacao=Decimal("4.8"), voltz="220V",
            valor_brinquedo=Decimal("1000.00"), exibir_na_loja=True,
            imagem_brinquedo=capa or arquivos[0][1],
        )
        brinquedo.categorias_brinquedos.add(self.categoria)
        for ordem, (tipo, arquivo, papel) in enumerate(arquivos, start=1):
            ImagemBrinquedo.objects.create(brinquedo=brinquedo, tipo=tipo, ordem=ordem, imagem=arquivo, papel_na_capa=papel)
        return brinquedo


class VarreduraTests(_ComDisco):
    """A 0185 e o comando: a conferência de verdade (os arquivos no disco)."""

    def setUp(self):
        super().setUp()
        # a capa (a frente) é branca; o lado tem fundo; o recorte do remove.bg, sem posição; a capa em cena de outro
        self.branco = self._produto("Pebolim", [
            ("perfil", "pebolim-branco", "branco", ""),
            ("lado_direito", "pebolim-lado", "cena", ""),
            (None, "pebolim-removebg", "recorte", ""),
        ])
        self.cena = self._produto("Air Game Home", [
            ("perfil", "air-game-home-cena", "branco", "cena"),  # (a capa em cena nunca é tocada)
            ("verso", "air-game-home-verso", "cena", ""),
        ])
        self.so_branco = self._produto("Pula Pula", [("perfil", "pula-branco", "branco", ""), ("verso", "pula-verso-branco", "branco", "")])
        self.bf = self._produto("Basquete Kids", [("perfil", "basquete-kids-branco", "branco", "")])

    def _retrato(self):
        return (sorted(ImagemBrinquedo.objects.values_list("id", "tipo", "papel_na_capa", "fundo", "imagem")),
                sorted(Brinquedos.objects.values_list("id", "imagem_brinquedo", "capa_sem_fundo")))

    def test_marca_as_sem_fundo_troca_a_capa_e_nao_apaga_nada(self):
        n = ImagemBrinquedo.objects.count()
        resumo = conferir_fotos.marcar_sem_fundo(Brinquedos, ImagemBrinquedo, avisar=_calado)
        self.assertEqual(len(resumo["marcadas"]), 4)  # a frente e o recorte do Pebolim, as duas do Pula Pula
        self.assertGreaterEqual(ImagemBrinquedo.objects.count(), n)  # nada some
        frente = ImagemBrinquedo.objects.get(brinquedo=self.branco, tipo="perfil")
        self.assertEqual((frente.papel_na_capa, frente.fundo), ("recorte", "sem"))  # fica guardada, com a posição
        self.assertEqual(ImagemBrinquedo.objects.get(brinquedo=self.branco, tipo="lado_direito").fundo, "com")
        # a capa sem fundo deu lugar à foto com fundo; a de antes fica guardada
        self.branco.refresh_from_db()
        self.assertIn("pebolim-lado", self.branco.imagem_brinquedo.name)
        self.assertIn("pebolim-branco", self.branco.capa_sem_fundo)
        self.assertEqual(resumo["capas"], ["Pebolim"])
        # a capa em cena não foi tocada (nem conferida)
        cena = ImagemBrinquedo.objects.get(brinquedo=self.cena, tipo="perfil")
        self.assertEqual((cena.papel_na_capa, cena.fundo), ("cena", ""))
        # sem nenhuma foto com fundo: fica o que tem (e a lista avisa)
        self.so_branco.refresh_from_db()
        self.assertIn("pula-branco", self.so_branco.imagem_brinquedo.name)
        self.assertEqual(resumo["sem_foto_com_fundo"], ["Pula Pula"])
        # a da Black Friday ficou de fora
        self.assertEqual(resumo["black_friday"], ["Basquete Kids"])
        self.assertEqual(ImagemBrinquedo.objects.get(brinquedo=self.bf).fundo, "")

    def test_de_novo_nao_muda_nada_nem_baixa_de_novo(self):
        conferir_fotos.marcar_sem_fundo(Brinquedos, ImagemBrinquedo, avisar=_calado)
        antes = self._retrato()
        conferir = mock.Mock(side_effect=AssertionError("conferiu de novo"))
        resumo = conferir_fotos.marcar_sem_fundo(Brinquedos, ImagemBrinquedo, conferir=conferir, avisar=_calado)
        conferir.assert_not_called()
        self.assertEqual(resumo["conferidas"], 0)
        self.assertEqual(self._retrato(), antes)

    def test_a_falha_de_rede_fica_para_a_proxima(self):
        def conferir(imagem):
            if "pebolim-lado" in imagem.name:
                raise OSError("sem rede")
            return conferir_fotos.foto_sem_fundo(imagem)

        avisos = []
        resumo = conferir_fotos.marcar_sem_fundo(Brinquedos, ImagemBrinquedo, conferir=conferir, avisar=avisos.append)
        self.assertEqual(len(resumo["falhas"]), 1)
        self.assertTrue(any("não foi conferida agora" in a for a in avisos))
        self.assertEqual(ImagemBrinquedo.objects.get(brinquedo=self.branco, tipo="lado_direito").fundo, "")
        # a próxima confere a que faltou
        resumo = conferir_fotos.marcar_sem_fundo(Brinquedos, ImagemBrinquedo, avisar=_calado)
        self.assertEqual(resumo["conferidas"], 1)
        self.assertEqual(ImagemBrinquedo.objects.get(brinquedo=self.branco, tipo="lado_direito").fundo, "com")

    def test_a_volta_devolve_a_capa_e_as_fotos(self):
        antes = self._retrato()
        conferir_fotos.marcar_sem_fundo(Brinquedos, ImagemBrinquedo, avisar=_calado)
        migracao_0185.desmarcar(registro, None)
        fotos, capas = self._retrato()
        self.assertEqual(capas, antes[1])
        self.assertEqual([f for f in fotos if f[0] in {x[0] for x in antes[0]}], antes[0])

    def test_simular_nao_muda_nada_e_o_comando_lista(self):
        antes = self._retrato()
        saida = StringIO()
        call_command("fotos_sem_fundo", "--simular", stdout=saida)
        self.assertEqual(self._retrato(), antes)
        texto = saida.getvalue()
        self.assertIn("marcaria 4 como recorte para artes", texto)
        self.assertIn("pebolim-branco", texto)
        self.assertIn("PRECISAM DE FOTO COM FUNDO", texto)
        self.assertIn("Pula Pula", texto)
        self.assertIn("Black Friday (de fora", texto)
        # sem --simular, marca
        call_command("fotos_sem_fundo", stdout=StringIO())
        self.assertEqual(ImagemBrinquedo.objects.filter(papel_na_capa="recorte").count(), 4)

    def test_a_migracao_so_roda_no_render(self):
        self.assertEqual(migracao_0184.Migration.dependencies, [("core", "0183_posicoes_do_3d_dos_adesivos")])
        with self.settings(IS_RENDER=False):
            migracao_0185.marcar(registro, None)
        self.assertFalse(ImagemBrinquedo.objects.exclude(fundo="").exists())
        with self.settings(IS_RENDER=True), mock.patch("builtins.print"):
            migracao_0185.marcar(registro, None)
        self.assertEqual(ImagemBrinquedo.objects.filter(papel_na_capa="recorte").count(), 4)


class SiteTests(_ComDisco):
    """Nenhuma vitrine pública mostra a foto sem fundo (marcada sozinha); sem foto com fundo, mostra a que tem."""

    def setUp(self):
        super().setUp()
        self.com_capa_branca = self._produto("Pebolim", [
            ("perfil", "pebolim-branco", "branco", ""),
            ("lado_direito", "pebolim-lado", "cena", ""),
            ("verso", "pebolim-verso", "cena", ""),
        ])
        self.so_branco = self._produto("Pula Pula", [("perfil", "pula-branco", "branco", "")])
        conferir_fotos.marcar_sem_fundo(Brinquedos, ImagemBrinquedo, avisar=_calado)
        fotos_dos_cards.limpar_cache()
        cache.clear()

    def test_as_listas_e_o_giro_sem_a_foto_sem_fundo(self):
        paginas = {
            "home": reverse("home"),
            "brinquedos": reverse("brinquedos"),
            "categoria": reverse("categoria_detalhe", args=[self.categoria.pk]),
            "loja": reverse("loja"),
            "busca": reverse("search") + "?q=pebolim",
        }
        for nome, url in paginas.items():
            with self.subTest(nome):
                html = self.client.get(url).content.decode()
                self.assertIn(f"/brinquedo/{self.com_capa_branca.pk}/", html)
                self.assertNotIn("pebolim-branco", html)
        giro = fotos_dos_cards.do_card(self.com_capa_branca.pk)
        self.assertEqual([u.split("/")[-1].split(".")[0].split("_")[0] for u in giro], ["pebolim-lado", "pebolim-verso"])

    def test_a_pagina_a_vitrine_do_topo_e_a_arena(self):
        resposta = self.client.get(reverse("brinquedo_detalhe", args=[self.com_capa_branca.pk]))
        self.assertNotContains(resposta, "pebolim-branco")
        self.assertEqual([f.tipo for f in resposta.context["imagens_brinquedo"]], ["lado_direito", "verso"])
        from .views import vitrine_do_quadro

        vitrine = vitrine_do_quadro(Brinquedos.objects.all())
        self.assertFalse(any("pebolim-branco" in item["capa"] + item["miniatura"] for item in vitrine))
        arena = next(b for b in dados_publicos_da_arena()["brinquedos_arena"] if b["nome"] == "Pebolim")
        self.assertNotIn("pebolim-branco", json.dumps(arena))

    def test_sem_foto_com_fundo_mostra_o_que_tem_e_o_painel_avisa(self):
        # o card e a página não ficam vazios
        html = self.client.get(reverse("brinquedos")).content.decode()
        self.assertIn("pula-branco", html)
        resposta = self.client.get(reverse("brinquedo_detalhe", args=[self.so_branco.pk]))
        self.assertEqual(len(resposta.context["imagens_brinquedo"]), 1)
        self.assertEqual(len(galeria_publica(self.so_branco.imagens_brinquedo.all(), self.so_branco.adesivo_padrao_id)), 1)
        # o painel: o selo no card e o aviso no adesivo
        gestor = User.objects.create_superuser("fundo", "f@exemplo.com", "x")
        self.client.force_login(gestor)
        html = self.client.get("/site/brinquedos/", **INTERNO).content.decode()
        self.assertEqual(html.count("Precisa de foto com fundo"), 1)
        dados = json.loads(re.search(r'id="toysAdminData"[^>]*>(.*?)</script>', html, re.S).group(1))
        adesivos = {d["id"]: d["adesivos"] for d in dados}
        self.assertTrue(adesivos[self.so_branco.pk][0]["precisa_foto_com_fundo"])
        self.assertFalse(adesivos[self.com_capa_branca.pk][0]["precisa_foto_com_fundo"])
        self.assertEqual(len(adesivos[self.com_capa_branca.pk][0]["recortes"]), 1)


class PainelTests(_ComDisco):
    """O cadastro do painel: a foto sem fundo enviada vira recorte sozinha (a frente, os lados, a posição)."""

    URL = "/site/brinquedos/"

    def setUp(self):
        super().setUp()
        self.client.force_login(User.objects.create_superuser("cadastro", "c@exemplo.com", "x"))
        self.brinquedo = self._produto("Pebolim", [("perfil", "pebolim-cena", "cena", "")])

    def _salvar(self, **arquivos):
        dados = {"action": "save", "id": self.brinquedo.pk, "nome_brinquedo": "Pebolim", "descricao": "x", **arquivos}
        resposta = self.client.post(self.URL, dados, **AJAX)
        self.assertLess(resposta.status_code, 400, resposta.content[:300])
        return json.loads(resposta.content)

    def test_a_frente_sem_fundo_vira_recorte_e_a_capa_fica_com_fundo(self):
        dados = self._salvar(imagem_perfil=_envio("frente-branca.png", "branco"),
                             imagem_lado_direito=_envio("lado.png"))
        self.assertIn("recorte para artes", dados["msg"])
        frente = ImagemBrinquedo.objects.get(brinquedo=self.brinquedo, tipo="perfil")
        self.assertEqual((frente.papel_na_capa, frente.fundo), ("recorte", "sem"))
        self.assertIn("frente-branca", frente.imagem.name)  # guardada
        self.assertEqual(ImagemBrinquedo.objects.get(brinquedo=self.brinquedo, tipo="lado_direito").fundo, "com")
        self.brinquedo.refresh_from_db()
        self.assertIn("lado", self.brinquedo.imagem_brinquedo.name)  # a capa é a com fundo
        self.assertIn("frente-branca", self.brinquedo.capa_sem_fundo)
        self.assertIn("lado", self.brinquedo.imagem_catalogo.name)
        # salvar de novo (sem foto nova) não desfaz nada nem perde a sem fundo
        self._salvar()
        frente.refresh_from_db()
        self.assertEqual((frente.tipo, frente.papel_na_capa), ("perfil", "recorte"))
        self.assertIn("frente-branca", frente.imagem.name)
        # uma frente com fundo depois: ela é a capa; a sem fundo fica guardada, sem posição
        self._salvar(imagem_perfil=_envio("frente-nova.png"))
        self.brinquedo.refresh_from_db()
        self.assertIn("frente-nova", self.brinquedo.imagem_brinquedo.name)
        nova = ImagemBrinquedo.objects.get(brinquedo=self.brinquedo, tipo="perfil")
        self.assertEqual((nova.papel_na_capa, nova.fundo), ("", "com"))
        self.assertTrue(ImagemBrinquedo.objects.filter(brinquedo=self.brinquedo, tipo=None, papel_na_capa="recorte",
                                                       imagem__contains="frente-branca").exists())

    def test_o_lado_transparente_vira_recorte(self):
        dados = self._salvar(imagem_lado_esquerdo=_envio("lado-recorte.png", "recorte"))
        self.assertIn("recorte para artes", dados["msg"])
        lado = ImagemBrinquedo.objects.get(brinquedo=self.brinquedo, tipo="lado_esquerdo")
        self.assertEqual(lado.papel_na_capa, "recorte")
        self.assertEqual([f.tipo for f in self.brinquedo.imagens_ordenadas], ["perfil"])

    def test_a_posicao_do_adesivo_nao_troca_a_sem_fundo_por_cima(self):
        padrao = self.brinquedo.adesivo_padrao
        resposta = self.client.post(self.URL, {"action": "adesivo_posicao", "id": self.brinquedo.pk, "adesivo_id": padrao.pk,
                                               "tipo": "verso", "foto": _envio("verso-branco.png", "branco")}, **AJAX)
        self.assertIn("recorte para artes", json.loads(resposta.content)["msg"])
        ImagemBrinquedo.objects.filter(brinquedo=self.brinquedo, imagem__contains="verso-branco").update(tipo="verso")
        self.client.post(self.URL, {"action": "adesivo_posicao", "id": self.brinquedo.pk, "adesivo_id": padrao.pk,
                                    "tipo": "verso", "foto": _envio("verso-cena.png")}, **AJAX)
        branca = ImagemBrinquedo.objects.get(brinquedo=self.brinquedo, imagem__contains="verso-branco")
        self.assertEqual((branca.tipo, branca.papel_na_capa), (None, "recorte"))  # guardada, fora da posição
        verso = ImagemBrinquedo.objects.get(brinquedo=self.brinquedo, tipo="verso")
        self.assertIn("verso-cena", verso.imagem.name)
