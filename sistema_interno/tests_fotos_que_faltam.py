"""A tela "Fotos que faltam" do painel (LEIA-ME-V10, seção 133).

O Cloudinary pede pagamento para devolver as fotos; o dono as envia de novo,
uma por card. Protege: a tela só do superadministrador; um card por FOTO (o
que ela é e onde aparece), por tipo, os públicos primeiro e o privado só na
contagem; o "Enviar foto" (grava no banco, exata, e troca o nome em TODO campo
que a usava; o número desce); o arquivo que não é foto, em janela, sem mexer
em nada; a foto que já voltou; a original no lugar da provisória; o casar dos
arquivos soltos pelo nome (o public id, o nome com o sufixo e o nome de antes
de subir; o ambíguo vai para o dono escolher); a consulta única que dá o mesmo
que o espelho; e as regras da casa (sem <select>, sem alert/confirm, sem cor
em hex). Tudo com imagens sintéticas.
"""

from __future__ import annotations

import io
import re
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from PIL import Image

from core import espelho_midia
from core.arquivos_no_banco import guardar
from core.models import ArquivoNoBanco, Brinquedos, Combos, ImagemBrinquedo, ImagemPeca, PecasReposicao

from . import fotos_que_faltam
from .models import Cliente

INTERNO = {"HTTP_HOST": "interno.testserver"}
AJAX = {**INTERNO, "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
ESTATICO = Path(__file__).resolve().parent / "static" / "interno"
STORAGES_DO_AR = {
    "default": {"BACKEND": "core.arquivos_no_banco.MidiaNoBanco"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
BOLICHE = "imagens_brinquedos/BOLICHE_VIRTUAL_LAZER_SPORT_igkeus"
PRETO = "imagens_brinquedos/galeria/Boliche_Virtual_Preto_osn8q7"
COMBO = "combos/WhatsApp_Image_2026-07-24_at_14.53.17_djegmh"


def foto(cor=(30, 90, 200), formato="JPEG") -> bytes:
    saida = io.BytesIO()
    Image.new("RGB", (300, 200), cor).save(saida, formato)
    return saida.getvalue()


@override_settings(STORAGES=STORAGES_DO_AR, MIDIA_BANCO_URL_BASE="", SITE_URL="https://www.exemplo.invalid")
class FotosQueFaltamTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._cache = tempfile.mkdtemp(prefix="ls-fq-cache-")
        cls._override = override_settings(MIDIA_CACHE_DIR=cls._cache)
        cls._override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._override.disable()
        shutil.rmtree(cls._cache, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.dono = Usuario.objects.create_superuser("dono-fq", "d@exemplo.invalid", "x")
        cls.gestora = Usuario.objects.create_user("gestora-fq", "g@exemplo.invalid", "x")
        from .permissoes import atribuir_funcoes

        atribuir_funcoes(cls.gestora, ["gestao"])

    def setUp(self):
        self.boliche = Brinquedos.objects.create(nome_brinquedo="Boliche Virtual", descricao="x", avaliacao=Decimal("5"),
                                                 voltz="220V", imagem_brinquedo=BOLICHE)
        self.perfil = ImagemBrinquedo.objects.create(brinquedo=self.boliche, tipo="perfil", ordem=1, imagem=BOLICHE)
        self.preto = ImagemBrinquedo.objects.create(brinquedo=self.boliche, tipo="lado_direito", ordem=2, imagem=PRETO)
        self.combo = Combos.objects.create(descricao="Combo Arcade Teste", imagem_combo=COMBO, valor_combo=Decimal("10"))
        self.cliente = Cliente.objects.create(nome_cliente="Ana Exemplo", nome_estabelecimento="Buffet Estrela Azul",
                                              logo="logo_clientes/104726_mfxth5")
        peca = PecasReposicao.objects.create(nome="Maneta", descricao_peca="x")
        self.peca = ImagemPeca.objects.create(peca_reposicao=peca, imagem="pecas_reposicao/MANETA_zcqczy")
        self.client.force_login(self.dono)

    def enviar(self, nome, dados=None, arquivo="foto.jpg"):
        return self.client.post("/restaurar-fotos/", {
            "acao": "enviar", "nome": nome,
            "arquivo": SimpleUploadedFile(arquivo, foto() if dados is None else dados, content_type="image/jpeg"),
        }, **AJAX)

    # ------------------------------------------------------------------
    def test_so_o_superadministrador(self):
        self.client.force_login(self.gestora)
        self.assertEqual(self.client.get("/restaurar-fotos/", **INTERNO).status_code, 302)
        self.assertEqual(self.enviar(PRETO).status_code, 302)
        self.preto.refresh_from_db()
        self.assertEqual(self.preto.imagem.name, PRETO)

    def test_um_card_por_foto_o_que_e_e_onde_aparece(self):
        tela = self.client.get("/restaurar-fotos/", **INTERNO)
        self.assertEqual(tela.status_code, 200)
        self.assertContains(tela, "Fotos que faltam")
        self.assertContains(tela, "pede pagamento")
        self.assertContains(tela, "nunca mais depende do Cloudinary")
        self.assertNotContains(tela, "<select")
        html = tela.content.decode()
        # uma foto, um card (a capa do Boliche serve a dois campos e é UM card)
        self.assertEqual(html.count("data-fq-card"), 5)
        self.assertEqual(html.count(f'data-nome="{BOLICHE}"'), 1)
        self.assertContains(tela, "e mais 1 cadastro com a mesma foto")
        # o que é: o produto e qual foto, o cliente (pelo nome da casa), o combo, a peça
        self.assertContains(tela, "Lado direito")
        self.assertContains(tela, "Buffet Estrela Azul")
        self.assertContains(tela, "Combo Arcade Teste")
        self.assertContains(tela, "Fotos das peças")
        # onde aparece, com o endereço do site
        self.assertContains(tela, f"https://www.exemplo.invalid/brinquedo/{self.boliche.pk}/")
        self.assertContains(tela, f"https://www.exemplo.invalid/combo/{self.combo.pk}/")
        # os públicos na ordem do site: produtos antes dos clientes, antes dos combos
        self.assertLess(html.index('id="fqGrupo-produtos"'), html.index('id="fqGrupo-clientes"'))
        self.assertLess(html.index('id="fqGrupo-clientes"'), html.index('id="fqGrupo-combos"'))

    def test_enviar_foto_grava_no_banco_e_troca_em_todo_campo(self):
        antes = len(fotos_que_faltam.pendentes(somente_publicos=True))
        resposta = self.enviar(BOLICHE)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        corpo = resposta.json()
        self.assertEqual(corpo["status"], "sucesso")
        self.assertEqual(corpo["para"], "banco/" + BOLICHE)
        self.assertIn("/midia/banco/" + BOLICHE, corpo["url"])
        self.assertEqual(corpo["faltam"], antes - 1)
        for objeto, campo in ((self.boliche, "imagem_brinquedo"), (self.perfil, "imagem")):
            objeto.refresh_from_db()
            self.assertEqual(getattr(objeto, campo).name, "banco/" + BOLICHE)
        linha = ArquivoNoBanco.objects.get(nome="banco/" + BOLICHE)
        self.assertTrue(linha.exata)
        self.assertEqual(linha.origem, "envio")
        self.assertTrue(linha.publico)
        # o logo do cliente (o campo sem armazenamento próprio) também
        self.assertEqual(self.enviar("logo_clientes/104726_mfxth5", foto(formato="PNG"), "logo.png").status_code, 200)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.logo.name, "banco/logo_clientes/104726_mfxth5")

    def test_o_arquivo_que_nao_e_foto_vira_janela_e_nada_muda(self):
        resposta = self.enviar(COMBO, b"isto nao e uma foto", "texto.png")
        self.assertEqual(resposta.status_code, 400)
        corpo = resposta.json()
        self.assertEqual(corpo["titulo"], "Este arquivo não serve")
        self.assertEqual(corpo["campo"], "arquivo")
        self.combo.refresh_from_db()
        self.assertEqual(self.combo.imagem_combo.name, COMBO)
        self.assertFalse(ArquivoNoBanco.objects.exists())
        sem = self.client.post("/restaurar-fotos/", {"acao": "enviar", "nome": COMBO}, **AJAX)
        self.assertEqual((sem.status_code, sem.json()["campo"]), (400, "arquivo"))

    def test_a_foto_que_ja_voltou(self):
        self.assertEqual(self.enviar(PRETO).status_code, 200)
        de_novo = self.enviar(PRETO)
        self.assertEqual(de_novo.status_code, 200)
        self.assertEqual(de_novo.json()["status"], "ja")
        self.assertEqual(self.enviar("imagens_brinquedos/ninguem_usa_ab12cd").json()["status"], "ja")

    def test_a_original_entra_no_lugar_da_provisoria(self):
        guardar("banco/" + COMBO, foto((200, 200, 0)), publico=True, tipo="image/jpeg", origem="copia_local", exata=False)
        Combos.objects.filter(pk=self.combo.pk).update(imagem_combo="banco/" + COMBO)
        tela = self.client.get("/restaurar-fotos/", **INTERNO)
        self.assertContains(tela, "Com foto provisória")
        self.assertContains(tela, "Enviar a original")
        resposta = self.enviar("banco/" + COMBO)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(resposta.json()["houve"], "trocado")
        self.assertIn("&v=", resposta.json()["url"])  # o card do painel pede a foto nova
        self.assertTrue(ArquivoNoBanco.objects.get(nome="banco/" + COMBO).exata)

    def test_casar_os_arquivos_soltos_pelo_nome(self):
        projetos = [Brinquedos.objects.create(nome_brinquedo=f"P{n}", descricao="x", avaliacao=Decimal("5"), voltz="",
                                              imagem_brinquedo=f"imagens_brinquedos/001_{sufixo}")
                    for n, sufixo in enumerate(("vmp7th", "x3chb1"))]
        self.assertEqual(len(projetos), 2)
        resposta = self.client.post("/restaurar-fotos/", {"acao": "casar", "arquivos": [
            "Boliche_Virtual_Preto.jpg",                           # o nome de antes de subir
            "WhatsApp Image 2026-07-24 at 14.53.17.jpeg",          # com espaços, como saiu do celular
            "MANETA_zcqczy.png",                                   # o nome com o sufixo do Cloudinary
            "001.jpg",                                             # dois cards com o mesmo nome
            "IMG_9999.jpg",                                        # nenhum
        ]}, **AJAX)
        self.assertEqual(resposta.status_code, 200)
        resultado = {item["arquivo"]: item for item in resposta.json()["resultado"]}
        self.assertEqual(resultado["Boliche_Virtual_Preto.jpg"]["nome"], PRETO)
        self.assertEqual(resultado["WhatsApp Image 2026-07-24 at 14.53.17.jpeg"]["nome"], COMBO)
        self.assertEqual(resultado["MANETA_zcqczy.png"]["nome"], "pecas_reposicao/MANETA_zcqczy")
        self.assertIsNone(resultado["001.jpg"]["nome"])
        self.assertEqual(set(resultado["001.jpg"]["candidatos"]),
                         {"imagens_brinquedos/001_vmp7th", "imagens_brinquedos/001_x3chb1"})
        self.assertIsNone(resultado["IMG_9999.jpg"]["nome"])
        self.assertEqual(resultado["IMG_9999.jpg"]["candidatos"], [])

    def test_a_consulta_unica_da_o_mesmo_que_o_espelho(self):
        espelho = espelho_midia.referencias()
        with CaptureQueriesContext(connection) as consultas:
            unica = fotos_que_faltam.pendentes()
        self.assertEqual(len(consultas), 1)
        self.assertEqual(set(unica), set(espelho))
        for nome, grupo in espelho.items():
            self.assertEqual({(r.rotulo, tuple(sorted(r.pks))) for r in grupo},
                             {(r.rotulo, tuple(sorted(r.pks))) for r in unica[nome]})

    @override_settings(RH_ARMAZENAMENTO="banco")
    def test_o_privado_fica_so_na_contagem(self):
        from rh.apoio_testes import criar_colaborador
        from rh.models import DocumentoColaborador

        colaborador = criar_colaborador(1)
        DocumentoColaborador.objects.create(colaborador=colaborador, tipo=DocumentoColaborador._meta.get_field("tipo").choices[0][0],
                                            arquivo="rh/documentos/antigo_ab12cd.pdf", tipo_conteudo="application/pdf",
                                            tamanho=10, sha256="0" * 64)
        dados = fotos_que_faltam.montar()
        nomes = [card["nome"] for grupo in dados["grupos"] for card in grupo["cards"]]
        self.assertNotIn("rh/documentos/antigo_ab12cd.pdf", nomes)
        self.assertEqual(dados["privados_total"], 1)
        self.assertEqual(dados["privados"][0]["titulo"], "Documentos do RH")
        # e não se envia documento privado por esta tela
        self.assertEqual(self.enviar("rh/documentos/antigo_ab12cd.pdf").json()["status"], "ja")

    def test_regras_da_casa_na_tela(self):
        js = (ESTATICO / "fotos-que-faltam.js").read_text(encoding="utf-8")
        codigo = re.sub(r"/\*.*?\*/", "", js, flags=re.S)  # (o comentário do topo cita o que é proibido)
        self.assertNotRegex(codigo, r"\balert\(|\bconfirm\(")
        self.assertIn("LSAviso", js)
        css = (ESTATICO / "restaurar-fotos.css").read_text(encoding="utf-8")
        secao = css[css.index("FOTOS QUE FALTAM (LEIA-ME-V10, seção 133)"):]
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b", secao))
        self.assertIn("repeat(4,minmax(0,1fr))", secao)  # no máximo 4 por fileira
        self.assertEqual(fotos_que_faltam.POR_VEZ % 12, 0)
