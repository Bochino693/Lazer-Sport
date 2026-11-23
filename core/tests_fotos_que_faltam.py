"""As fotos que só o Cloudinary tinha: as cópias certas e as reservas do site (LEIA-ME-V10, seção 133).

O Cloudinary desativou a conta e pede pagamento para devolver as fotos. O que
estes testes protegem:

  * AS REGRAS NOVAS DA RESTAURAÇÃO (core/restaurar_midia.py), cada uma só com
    certeza e só no campo dela: a capa e o adesivo Rosa do Boliche Virtual
    (as fotos no showroom feitas do recorte da foto Rosa; o Preto fica de
    fora), os seis tipos de estabelecimento (a foto do ambiente que mostra o
    lugar) e o recorte sem fundo das peças refeito da original guardada em
    site/reserva (também a de nome cortado em 48 letras) -- todas exata=False;
  * AS RESERVAS DO SITE com o Cloudinary fora: a faixa de clientes (o selo com
    o nome de casa, nunca o nome de uma pessoa; a faixa some sem ninguém), os
    projetos (a foto que falta sai da galeria; sem nenhuma, a capa desenhada),
    os combos (o mosaico das capas dos brinquedos), as peças (a primeira que
    sai; sem nenhuma, o cartão desenhado), as capas dos jogos (a capa de
    reserva do launcher), os estabelecimentos e a galeria do produto (a foto
    que falta sai). Nunca o quadro "Foto em atualização" onde há coisa melhor.
Tudo com imagens sintéticas.
"""

from __future__ import annotations

import io
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image, ImageDraw

from . import fotos, restaurar_midia
from .context_processors import escolher_clientes_da_faixa
from .models import (
    ArquivoNoBanco, Brinquedos, BrinquedosProjeto, CategoriasBrinquedos, Combos, Estabelecimentos, ImagemBrinquedo,
    ImagemPeca, ImagemProjetoBrinquedo, JogoCadastrado, PecasReposicao, Projetos, galeria_publica,
)

RAIZ = Path(__file__).resolve().parent.parent
SITE = Path(__file__).resolve().parent / "static" / "site"
FORA = {"MIDIA_CLOUDINARY_FORA": "1"}
STORAGES_DO_AR = {
    "default": {"BACKEND": "core.arquivos_no_banco.MidiaNoBanco"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


def foto(cor=(200, 60, 40), tamanho=(320, 240), formato="WEBP") -> bytes:
    saida = io.BytesIO()
    Image.new("RGB", tamanho, cor).save(saida, formato)
    return saida.getvalue()


def peca_no_branco() -> bytes:
    """A foto de catálogo de uma peça: um cabo escuro no fundo branco (o recorte tira o branco)."""
    imagem = Image.new("RGB", (400, 400), (255, 255, 255))
    d = ImageDraw.Draw(imagem)
    d.ellipse((80, 70, 320, 310), fill=(20, 20, 20))
    d.ellipse((140, 130, 260, 250), fill=(255, 255, 255))
    saida = io.BytesIO()
    imagem.save(saida, "PNG")
    return saida.getvalue()


def brinquedo(nome="Brinquedo", imagem=""):
    return Brinquedos.objects.create(nome_brinquedo=nome, descricao="x", avaliacao=Decimal("5.00"), voltz="220V",
                                     valor_brinquedo=Decimal("1000.00"), imagem_brinquedo=imagem)


BOLICHE = "imagens_brinquedos/BOLICHE_VIRTUAL_LAZER_SPORT_igkeus"
PRETO = "imagens_brinquedos/galeria/Boliche_Virtual_Preto_osn8q7"
ROSA = "imagens_brinquedos/galeria/Boliche_Virtual_Rosa_r17hzv"


# ======================================================================
# AS REGRAS NOVAS DA RESTAURAÇÃO
# ======================================================================
class RegrasDaSecao133Tests(TestCase):
    def setUp(self):
        self.raiz = Path(tempfile.mkdtemp(prefix="ls-fotos-133-"))
        self.addCleanup(shutil.rmtree, self.raiz, True)
        site = self.raiz / "core" / "static" / "site"
        for pasta in ("capas_catalogo", "categorias", "reserva"):
            (site / pasta).mkdir(parents=True)
        self.capa = foto((240, 40, 150))
        self.rosa = foto((250, 90, 170))
        (site / "capas_catalogo" / "boliche-virtual.webp").write_bytes(self.capa)
        (site / "capas_catalogo" / "boliche-virtual-rosa.webp").write_bytes(self.rosa)
        for nome in ("esportivos", "brinquedao", "jogos-de-mesa", "mecanicos", "simuladores", "famosos"):
            (site / "categorias" / f"{nome}.webp").write_bytes(foto((len(nome) * 9, 80, 160)))
        self.original = peca_no_branco()
        (site / "reserva" / "cabo_pc_2_d594iw.png").write_bytes(self.original)
        (site / "reserva" / "bonecos-pebolim-frente-ee78cafb65abff265417508856803055-1024-1024_nx4yyc.png").write_bytes(
            peca_no_branco())
        for nome, valor in {"BASE": self.raiz, "SITE": site, "RESERVA": site / "reserva", "MEDIA": self.raiz / "media",
                            "REPOSICAO": self.raiz / "nada", "RECORTAR": self.raiz / "nada.py"}.items():
            alvo = mock.patch.object(restaurar_midia, nome, valor)
            alvo.start()
            self.addCleanup(alvo.stop)

    def _nome(self, objeto, campo):
        objeto.refresh_from_db()
        return getattr(objeto, campo).name

    def test_o_boliche_ganha_a_capa_em_cena_e_o_rosa_o_preto_fica_de_fora(self):
        produto = brinquedo("Boliche Virtual", BOLICHE)
        perfil = ImagemBrinquedo.objects.create(brinquedo=produto, tipo="perfil", ordem=1, imagem=BOLICHE)
        preto = ImagemBrinquedo.objects.create(brinquedo=produto, tipo="lado_direito", ordem=2, imagem=PRETO)
        rosa = ImagemBrinquedo.objects.create(brinquedo=produto, tipo="lado_esquerdo", ordem=3, imagem=ROSA)
        resultado = restaurar_midia.restaurar_das_copias()

        self.assertEqual(self._nome(produto, "imagem_brinquedo"), "banco/" + BOLICHE)
        self.assertEqual(self._nome(perfil, "imagem"), "banco/" + BOLICHE)
        linha = ArquivoNoBanco.objects.get(nome="banco/" + BOLICHE)
        self.assertFalse(linha.exata)  # a original (o dono, ou o Cloudinary de volta) entra no lugar
        self.assertEqual(Image.open(io.BytesIO(bytes(linha.conteudo))).getpixel((5, 5)), Image.open(io.BytesIO(self.capa)).getpixel((5, 5)))
        self.assertEqual(self._nome(rosa, "imagem"), "banco/" + ROSA)
        self.assertFalse(ArquivoNoBanco.objects.get(nome="banco/" + ROSA).exata)
        # o adesivo Preto não tem foto nossa: continua faltando
        self.assertEqual(self._nome(preto, "imagem"), PRETO)
        self.assertEqual({i["nome"] for i in resultado.faltando}, {PRETO})

    def test_a_capa_do_boliche_so_vale_no_campo_de_produto(self):
        categoria = CategoriasBrinquedos.objects.create(nome_categoria="Boliche", imagem_categoria=BOLICHE)
        restaurar_midia.restaurar_das_copias()
        self.assertEqual(self._nome(categoria, "imagem_categoria"), BOLICHE)

    def test_os_tipos_de_estabelecimento_ganham_a_foto_do_ambiente(self):
        esperado = {
            "estabelecimentos/acad_rvluu1": "esportivos", "estabelecimentos/buffet_w4xhtf": "brinquedao",
            "estabelecimentos/condo_gsr5rb": "jogos-de-mesa", "estabelecimentos/parquees_d2dkwm": "mecanicos",
            "estabelecimentos/quios_lcst9n": "simuladores", "estabelecimentos/shopp_oyopn2": "famosos",
        }
        lugares = {nome: Estabelecimentos.objects.create(nome_estabelecimento=nome, imagem_estabelecimento=nome) for nome in esperado}
        outro = Estabelecimentos.objects.create(nome_estabelecimento="Outro", imagem_estabelecimento="estabelecimentos/outro_ab12cd")
        restaurar_midia.restaurar_das_copias()
        for nome, categoria in esperado.items():
            with self.subTest(nome):
                self.assertEqual(self._nome(lugares[nome], "imagem_estabelecimento"), "banco/" + nome)
                linha = ArquivoNoBanco.objects.get(nome="banco/" + nome)
                self.assertFalse(linha.exata)
                arquivo = restaurar_midia.SITE / "categorias" / f"{categoria}.webp"
                self.assertEqual(Image.open(io.BytesIO(bytes(linha.conteudo))).getpixel((5, 5)),
                                 Image.open(arquivo).convert("RGB").getpixel((5, 5)))
        # nome de fora da lista: só com a regra declarada
        self.assertEqual(self._nome(outro, "imagem_estabelecimento"), "estabelecimentos/outro_ab12cd")

    def test_o_recorte_sem_fundo_da_peca_e_refeito_da_original(self):
        peca = PecasReposicao.objects.create(nome="Cabo de Fonte", descricao_peca="x")
        recorte = "pecas_reposicao/cabo_pc_2_d594iw-sem-fundo_eergv3"
        imagem = ImagemPeca.objects.create(peca_reposicao=peca, imagem=recorte, imagem_original="pecas_reposicao/cabo_pc_2_d594iw")
        cortado = "pecas_reposicao/bonecos-pebolim-frente-ee78cafb65abff26541750885-sem-fundo_cpb2gy"
        bonecos = ImagemPeca.objects.create(peca_reposicao=peca, imagem=cortado, ordem=2)
        restaurar_midia.restaurar_das_copias()

        self.assertEqual(self._nome(imagem, "imagem"), "banco/" + recorte)
        linha = ArquivoNoBanco.objects.get(nome="banco/" + recorte)
        self.assertFalse(linha.exata)
        refeita = Image.open(io.BytesIO(bytes(linha.conteudo))).convert("RGBA")
        self.assertEqual(refeita.getpixel((0, 0))[3], 0)  # o branco saiu: o canto é transparente
        # a original volta exata, pelo nome (site/reserva)
        self.assertTrue(ArquivoNoBanco.objects.get(nome="banco/pecas_reposicao/cabo_pc_2_d594iw").exata)
        # a base da original cortada em 48 letras (o nome do recorte automático) também casa
        self.assertEqual(self._nome(bonecos, "imagem"), "banco/" + cortado)

    def test_o_recorte_automatico_so_vale_na_foto_da_peca(self):
        produto = brinquedo("Outro", "pecas_reposicao/cabo_pc_2_d594iw-sem-fundo_eergv3")
        restaurar_midia.restaurar_das_copias()
        self.assertEqual(self._nome(produto, "imagem_brinquedo"), "pecas_reposicao/cabo_pc_2_d594iw-sem-fundo_eergv3")


class SubstitutasDoRepositorioTests(SimpleTestCase):
    """As fotos que as regras declaram existem no repositório e são fotos num ambiente."""

    def test_cada_substituta_existe_e_e_foto_quadrada_ou_de_ambiente(self):
        for nome, (relativo, campos, rotulo) in restaurar_midia.SUBSTITUTAS.items():
            with self.subTest(nome):
                arquivo = SITE / relativo
                self.assertTrue(arquivo.is_file(), arquivo)
                self.assertTrue(rotulo)
                with Image.open(arquivo) as imagem:
                    self.assertEqual(imagem.format, "WEBP")
                    self.assertNotIn("A", imagem.getbands())  # foto opaca: nada de recorte solto
                    self.assertGreaterEqual(min(imagem.size), 1200)
        # o Preto do Boliche não tem foto nossa: nenhuma regra para ele
        self.assertNotIn(PRETO.lower(), restaurar_midia.SUBSTITUTAS)

    def test_as_duas_do_boliche_sao_diferentes(self):
        capa = (SITE / "capas_catalogo" / "boliche-virtual.webp").read_bytes()
        rosa = (SITE / "capas_catalogo" / "boliche-virtual-rosa.webp").read_bytes()
        self.assertNotEqual(capa, rosa)  # a galeria não repete a mesma foto

    def test_as_originais_das_pecas_estao_na_reserva(self):
        for base in ("cabo_pc_2_d594iw", "caixa_portatil_melhorada_3_a8juv6", "controle_xbox_gerxo6", "imagem_melhorada_1_sgokbi",
                     "bonecos-pebolim-frente-ee78cafb65abff265417508856803055-1024-1024_nx4yyc"):
            self.assertTrue((SITE / "reserva" / f"{base}.png").is_file(), base)


# ======================================================================
# AS RESERVAS DO SITE COM O CLOUDINARY FORA
# ======================================================================
class ComOCloudinaryFora(TestCase):
    def setUp(self):
        cache.clear()
        fotos._URLS.clear()
        self.addCleanup(fotos._URLS.clear)
        self.addCleanup(cache.clear)


@override_settings(**FORA)
class GaleriaEPecasTests(ComOCloudinaryFora):
    def test_a_galeria_do_produto_tira_a_foto_que_falta(self):
        produto = brinquedo("Boliche Virtual", "banco/imagens_brinquedos/capa.webp")
        ImagemBrinquedo.objects.create(brinquedo=produto, tipo="perfil", ordem=1, imagem="banco/imagens_brinquedos/capa.webp")
        ImagemBrinquedo.objects.create(brinquedo=produto, tipo="lado_direito", ordem=2, imagem=PRETO)
        galeria = galeria_publica(list(produto.imagens_brinquedo.all()), produto.adesivo_padrao_id)
        self.assertEqual([f.imagem.name for f in galeria], ["banco/imagens_brinquedos/capa.webp"])

    def test_sem_nenhuma_foto_no_ar_a_galeria_fica_como_esta(self):
        produto = brinquedo("Só no Cloudinary", BOLICHE)
        ImagemBrinquedo.objects.create(brinquedo=produto, tipo="perfil", ordem=1, imagem=BOLICHE)
        ImagemBrinquedo.objects.create(brinquedo=produto, tipo="lado_direito", ordem=2, imagem=PRETO)
        self.assertEqual(len(galeria_publica(list(produto.imagens_brinquedo.all()), produto.adesivo_padrao_id)), 2)

    def test_a_peca_usa_a_primeira_foto_que_sai(self):
        peca = PecasReposicao.objects.create(nome="Controle", descricao_peca="x", preco_venda=Decimal("10.00"))
        ImagemPeca.objects.create(peca_reposicao=peca, ordem=1, imagem="pecas_reposicao/controle_xbox_gerxo6-sem-fundo_bkghd2")
        segunda = ImagemPeca.objects.create(peca_reposicao=peca, ordem=2, imagem="banco/pecas_reposicao/controle.webp")
        peca = PecasReposicao.objects.prefetch_related("imagem_peca_reposicao").get(pk=peca.pk)
        self.assertEqual(peca.imagem_principal.pk, segunda.pk)
        self.assertEqual([i.pk for i in peca.imagens_ordenadas], [segunda.pk])

    def test_a_peca_sem_foto_vira_o_cartao_desenhado(self):
        peca = PecasReposicao.objects.create(nome="Caixa de Som Teste", descricao_peca="x", preco_venda=Decimal("10.00"))
        ImagemPeca.objects.create(peca_reposicao=peca, imagem="pecas_reposicao/imagem_melhorada_1_sgokbi-sem-fundo_pssyuv")
        for pagina in ("/pecas-reposicao/", f"/pecas/{peca.pk}/", "/loja/"):
            with self.subTest(pagina):
                resposta = self.client.get(pagina)
                self.assertEqual(resposta.status_code, 200)
                self.assertContains(resposta, "ls-capa-desenhada")
                self.assertContains(resposta, 'aria-label="Caixa de Som Teste')
                self.assertNotContains(resposta, "foto-em-atualizacao")
                self.assertNotContains(resposta, 'src=""')

    def test_o_jogo_sem_capa_no_ar_usa_a_capa_do_launcher(self):
        jogo = JogoCadastrado(nome="Jogo Teste", slug="jogo-teste", capa="jogos/capas/image_e6hpxm")
        self.assertEqual(jogo.capa_url, "")
        self.assertEqual(jogo.poster_url, "")
        jogo.capa = "banco/jogos/capas/capa.webp"
        self.assertIn("/midia/banco/jogos/capas/capa.webp", jogo.capa_url)


@override_settings(**FORA)
class ProjetosCombosEstabelecimentosTests(ComOCloudinaryFora):
    def setUp(self):
        super().setUp()
        self.sem_foto = BrinquedosProjeto.objects.create(nome_brinquedo_projeto="Espaço Kids", descricao="x")
        ImagemProjetoBrinquedo.objects.create(brinquedo=self.sem_foto, imagem="projetos/001_vmp7th")
        Projetos.objects.create(titulo="Espaço Kids do Shopping", descricao="Projeto.", brinquedo_projetado=self.sem_foto)
        self.misto = BrinquedosProjeto.objects.create(nome_brinquedo_projeto="Brinquedão", descricao="x")
        ImagemProjetoBrinquedo.objects.create(brinquedo=self.misto, imagem="projetos/01_uge882")
        self.boa = ImagemProjetoBrinquedo.objects.create(brinquedo=self.misto, imagem="banco/projetos/brinquedao.webp")
        Projetos.objects.create(titulo="Brinquedão do Buffet", descricao="Projeto.", brinquedo_projetado=self.misto)

    def test_a_foto_que_falta_sai_da_galeria_do_projeto(self):
        self.assertEqual([i.pk for i in self.misto.fotos_no_site], [self.boa.pk])
        self.assertEqual(self.sem_foto.fotos_no_site, [])

    def test_a_pagina_dos_projetos_desenha_a_capa_de_quem_nao_tem_foto(self):
        resposta = self.client.get("/projetos/")
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'aria-label="Espaço Kids do Shopping · Projeto sob medida"')
        self.assertContains(resposta, "/midia/banco/projetos/brinquedao.webp")
        self.assertNotContains(resposta, "foto-em-atualizacao")
        self.assertNotContains(resposta, "projetos/01_uge882")
        self.assertContains(resposta, "1 foto do projeto")

    def test_o_combo_sem_foto_vira_o_mosaico_dos_brinquedos(self):
        a = brinquedo("Air Game", "banco/imagens_brinquedos/air.webp")
        b = brinquedo("Pac Man", "banco/imagens_brinquedos/pac.webp")
        sem = brinquedo("Sem foto no ar", "imagens_brinquedos/antiga_ab12cd")
        combo = Combos.objects.create(descricao="Combo Arcade", imagem_combo="combos/WhatsApp_Image_2026-07-24_at_14.53.17_djegmh",
                                      valor_combo=Decimal("1500.00"))
        combo.brinquedos.set([a, b, sem])
        self.assertFalse(combo.tem_foto_propria)
        self.assertEqual([x.pk for x in combo.fotos_do_mosaico], [a.pk, b.pk])
        for pagina in ("/loja/", f"/combo/{combo.pk}"):
            with self.subTest(pagina):
                resposta = self.client.get(pagina)
                self.assertEqual(resposta.status_code, 200)
                self.assertContains(resposta, "ls-mosaico ls-mosaico--2")
                self.assertContains(resposta, "/midia/banco/imagens_brinquedos/air.webp")
                self.assertNotContains(resposta, "foto-em-atualizacao")

    def test_o_estabelecimento_sem_foto_ganha_a_capa_desenhada(self):
        Estabelecimentos.objects.create(nome_estabelecimento="Quiosques", imagem_estabelecimento="estabelecimentos/quios_lcst9n")
        resposta = self.client.get("/estabelecimentos/")
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'aria-label="Quiosques · Onde já tem Lazer &amp; Sport"')
        self.assertNotContains(resposta, "foto-em-atualizacao")


@override_settings(STORAGES=STORAGES_DO_AR, **FORA)
class FaixaDeClientesTests(ComOCloudinaryFora):
    def criar(self, nome, logo, documento="", estabelecimento=""):
        from sistema_interno.models import Cliente

        return Cliente.objects.create(nome_cliente=nome, documento=documento, nome_estabelecimento=estabelecimento, logo=logo)

    def test_sem_logo_o_selo_com_o_nome_da_casa_e_nunca_o_da_pessoa(self):
        self.criar("Ana Exemplo", "logo_clientes/104726_mfxth5", estabelecimento="Buffet Estrela Azul")
        self.criar("Parque Alegria Teste", "logo_clientes/LOGO_2_page-0001_pefbqq", documento="12345678000190")
        self.criar("Maria Exemplo", "logo_clientes/logo-happymania_yn31so", documento="12345678901")
        self.criar("Bruna Exemplo", "banco/logo_clientes/escola.png", estabelecimento="Escola Arco-Íris")
        resposta = self.client.get("/privacidade/")
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "ls-cliente-selo")
        self.assertContains(resposta, "Buffet Estrela Azul")
        self.assertContains(resposta, "Parque Alegria Teste")
        self.assertContains(resposta, "/midia/banco/logo_clientes/escola.png")
        # nome de pessoa nunca vai para o site
        for pessoa in ("Maria Exemplo", "Ana Exemplo", "Bruna Exemplo"):
            self.assertNotContains(resposta, pessoa)
        self.assertNotContains(resposta, "foto-em-atualizacao")

    def test_sem_ninguem_para_mostrar_a_faixa_some(self):
        self.criar("Maria Exemplo", "logo_clientes/logo-happymania_yn31so", documento="12345678901")
        resposta = self.client.get("/privacidade/")
        self.assertNotContains(resposta, "ls-clientes-strip")

    def test_a_escolha_para_em_seis_e_marca_o_logo(self):
        clientes = [self.criar(f"Buffet {n}", "logo_clientes/x_ab12cd") for n in range(8)]
        escolhidos = escolher_clientes_da_faixa(clientes)
        self.assertEqual(len(escolhidos), 6)
        self.assertTrue(all(c.logo_no_ar is False for c in escolhidos))
