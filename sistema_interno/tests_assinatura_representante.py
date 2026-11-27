"""A assinatura do representante da empresa nos documentos assinados (LEIA-ME-V10, seção 152).

O dono: "sempre que o cliente assinar, embutir esta assinatura no lado nosso
da Lazer & Sport, com o nome (...) e da fábrica, inclusive ponha em todos os
docs já gerados."

TUDO AQUI É SINTÉTICO: a "foto" é um rabisco desenhado em código sobre um
papel acinzentado com sombra. A assinatura de verdade nunca entra no
repositório.

O que estes testes protegem:

  * o tratamento: o papel some (transparente), o traço fica, a margem é
    recortada, o tamanho tem teto, a saída é sempre um PNG novo -- com
    JPEG, PNG e WebP, com sombra e com o PNG já transparente;
  * o arquivo é dado não confiável: SVG, PDF, GIF, lixo, vazio, pequeno
    demais, grande demais, papel em branco e foto escura são recusados, com
    o campo, e nada é gravado;
  * só a Gestão e o superusuário veem a tela, pedem a prévia, salvam e
    removem; a prévia não grava;
  * a assinatura aparece SÓ no documento que o cliente já assinou (via do
    painel, página pública do assinado, impressão) -- contrato, termo
    antigo, ordem de serviço e contrato do pedido do site --, com os nomes
    e a frase honesta; o que espera assinatura fica como era;
  * os documentos JÁ ASSINADOS antes do cadastro ganham a assinatura, e o
    retrato e os dois hashes não mudam;
  * sem assinatura cadastrada (ou depois de remover) tudo sai como antes;
  * a imagem não aparece em tela que não é o documento, nem tem endereço.
"""

import importlib
import io
import random

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import migrations
from django.test import TestCase

from . import assinatura_representante as ar
from . import documento_assinatura as svc
from .models import AssinaturaRepresentante, DadosContrato, DocumentoAssinatura
from .permissoes import atribuir_funcoes
from .tests_documento_assinatura import BaseDocumento, conteudo_do_termo_antigo
from .utils import ErroDeFormulario

AJAX = {"HTTP_HOST": "interno.testserver", "HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
INTERNO = {"HTTP_HOST": "interno.testserver"}
TELA = "/orcamentos/dados-do-contrato/"
MARCA = "data:image/png;base64,"
#: a frase como sai no HTML (o "&" escapado)
NOTA = ar.NOTA.replace("&", "&amp;")


def foto_sintetica(formato="JPEG", tamanho=(1200, 700), traco=True, papel=(214, 219, 222), tinta=(38, 44, 150)):
    """Um rabisco a "caneta azul" num papel acinzentado, com sombra e grão -- desenhado em código."""
    from PIL import Image, ImageDraw

    largura, altura = tamanho
    imagem = Image.new("RGB", tamanho, papel)
    desenho = ImageDraw.Draw(imagem)
    # a sombra: o papel escurece para baixo e para a direita
    for y in range(0, altura, 4):
        sombra = round(34 * y / altura)
        desenho.rectangle([0, y, largura, y + 4], fill=tuple(max(c - sombra, 0) for c in papel))
    sorteio = random.Random(152)
    for _ in range(900):                       # o grão do papel
        x, y = sorteio.randrange(largura), sorteio.randrange(altura)
        r, g, b = imagem.getpixel((x, y))
        desenho.point((x, y), fill=(max(r - 9, 0), max(g - 9, 0), max(b - 9, 0)))
    if traco:
        pontos = [(260, 420), (380, 250), (470, 430), (600, 230), (720, 410), (860, 260), (950, 380)]
        desenho.line(pontos, fill=tinta, width=7, joint="curve")
        desenho.arc([230, 200, 980, 470], 170, 380, fill=tinta, width=5)
    saida = io.BytesIO()
    imagem.save(saida, format=formato, **({"quality": 88} if formato in ("JPEG", "WEBP") else {}))
    return saida.getvalue()


def enviada(dados=None, nome="assinatura.jpg", tipo="image/jpeg"):
    return SimpleUploadedFile(nome, dados if dados is not None else foto_sintetica(), content_type=tipo)


def aberta(png):
    from PIL import Image

    imagem = Image.open(io.BytesIO(png))
    imagem.load()
    return imagem


class TratamentoTests(TestCase):
    def test_o_papel_some_o_traco_fica_e_a_margem_e_recortada(self):
        original = foto_sintetica()
        png, largura, altura = ar.tratar(original)
        self.assertNotEqual(png[:16], original[:16])
        imagem = aberta(png)
        self.assertEqual((imagem.format, imagem.mode, imagem.size), ("PNG", "RGBA", (largura, altura)))
        self.assertLessEqual(largura, ar.SAIDA_MAXIMA[0])
        self.assertLessEqual(altura, ar.SAIDA_MAXIMA[1])
        self.assertLessEqual(len(png), ar.TETO_DO_PNG)
        alfa = imagem.getchannel("A")
        # os cantos são papel: transparentes; o traço é opaco; a maior parte da imagem é papel
        for canto in ((0, 0), (largura - 1, 0), (0, altura - 1), (largura - 1, altura - 1)):
            self.assertEqual(alfa.getpixel(canto), 0)
        histograma = alfa.histogram()
        self.assertGreater(sum(histograma[200:]), 400)
        self.assertGreater(histograma[0], largura * altura * 0.75)
        # recortada: o traço encosta nas bordas (o rabisco ocupava ~60% da foto)
        caixa = alfa.point([255 if v >= 48 else 0 for v in range(256)]).getbbox()
        self.assertLess(caixa[0], largura * 0.06)
        self.assertGreater(caixa[2], largura * 0.94)
        # a cor é a da caneta (azul), uma só
        cores = {imagem.getpixel((x, y))[:3] for x in range(0, largura, 7) for y in range(0, altura, 7)}
        self.assertEqual(len(cores), 1)
        r, g, b = cores.pop()
        self.assertGreater(b, r + 40)

    def test_aceita_jpeg_png_e_webp_e_o_png_ja_transparente(self):
        from PIL import Image

        for formato in ("JPEG", "PNG", "WEBP"):
            with self.subTest(formato=formato):
                _png, largura, altura = ar.tratar(foto_sintetica(formato))
                self.assertGreater(largura, 300)
                self.assertGreater(altura, 60)
        # o PNG já recortado (fundo transparente): a transparência vira papel
        base = aberta(ar.tratar(foto_sintetica())[0])
        solto = Image.new("RGBA", (base.width + 200, base.height + 200), (0, 0, 0, 0))
        solto.alpha_composite(base, (100, 100))
        memoria = io.BytesIO()
        solto.save(memoria, format="PNG")
        png, largura, _altura = ar.tratar(memoria.getvalue())
        self.assertGreater(sum(aberta(png).getchannel("A").histogram()[200:]), 300)

    def test_o_que_nao_e_foto_de_assinatura_e_recusado(self):
        from PIL import Image

        gif = io.BytesIO()
        Image.new("P", (400, 200), 0).save(gif, format="GIF")
        pequena = io.BytesIO()
        Image.new("RGB", (60, 30), "white").save(pequena, format="PNG")
        recusados = {
            "vazio": b"",
            "lixo": b"isto nao e uma imagem" * 20,
            "svg": b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="400" height="200"><script>alert(1)</script></svg>',
            "pdf": b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
            "html": b"<html><body><img src=x onerror=alert(1)></body></html>",
            "gif": gif.getvalue(),
            "pequena": pequena.getvalue(),
            "papel em branco": foto_sintetica(traco=False),
            "foto escura": foto_sintetica(papel=(28, 28, 30), tinta=(250, 250, 250)),
            "jpeg cortado": foto_sintetica()[:900],
        }
        for nome, dados in recusados.items():
            with self.subTest(arquivo=nome):
                with self.assertRaises(ErroDeFormulario) as erro:
                    ar.tratar(dados)
                self.assertEqual(getattr(erro.exception, "campo", ""), "assinatura_arquivo")

    def test_os_tetos_de_tamanho(self):
        from unittest import mock

        with mock.patch.object(ar, "TETO_DO_ENVIO", 1000):
            with self.assertRaises(ErroDeFormulario):
                ar.tratar(foto_sintetica())
        with mock.patch.object(ar, "TETO_DE_PIXELS", 10_000):
            with self.assertRaises(ErroDeFormulario):
                ar.tratar(foto_sintetica())
        # a foto enorme é reduzida, e a saída continua dentro do teto
        png, largura, altura = ar.tratar(foto_sintetica(tamanho=(3600, 2100)))
        self.assertLessEqual((largura, altura), ar.SAIDA_MAXIMA)

    def test_a_migracao_e_so_de_esquema(self):
        modulo = importlib.import_module("sistema_interno.migrations.0088_assinatura_do_representante")
        self.assertTrue(all(isinstance(o, migrations.CreateModel) for o in modulo.Migration.operations))


class TelaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.gestora = User.objects.create_user("gestora-rubrica", password="senha-de-teste")
        atribuir_funcoes(self.gestora, ("gestao",))
        self.admin = User.objects.create_superuser("admin-rubrica", "a@exemplo.test", "senha-de-teste")

    def mandar(self, acao, usuario=None, arquivo=True, **extra):
        if usuario is not False:
            self.client.force_login(usuario or self.gestora)
        dados = {"action": acao, **extra}
        if arquivo:
            dados["assinatura_arquivo"] = arquivo if arquivo is not True else enviada()
        return self.client.post(TELA, dados, **AJAX)

    def test_a_previa_devolve_o_traco_e_nao_grava(self):
        resposta = self.mandar("assinatura_previa")
        self.assertEqual(resposta.status_code, 200, resposta.content[:300])
        corpo = resposta.json()
        self.assertTrue(corpo["imagem"].startswith(MARCA))
        self.assertFalse(AssinaturaRepresentante.objects.exists())
        self.assertEqual(ar.imagem_atual(), "")

    def test_salvar_trocar_e_remover(self):
        resposta = self.mandar("assinatura_salvar")
        self.assertEqual(resposta.status_code, 200, resposta.content[:300])
        linha = AssinaturaRepresentante.objects.get()
        self.assertEqual(linha.enviada_por, self.gestora)
        self.assertEqual(bytes(linha.png)[:8], bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]))
        self.assertEqual(len(linha.sha256), 64)
        self.assertEqual(ar.imagem_atual(), ar.data_url(linha.png))
        # trocar: continua uma linha só, com o traço novo
        outra = foto_sintetica(tinta=(20, 20, 24))
        self.assertEqual(self.mandar("assinatura_salvar", self.admin, enviada(outra)).status_code, 200)
        nova = AssinaturaRepresentante.objects.get()
        self.assertNotEqual(nova.sha256, linha.sha256)
        self.assertEqual(ar.imagem_atual(), ar.data_url(nova.png))
        # remover
        self.assertEqual(self.mandar("assinatura_remover", arquivo=False).status_code, 200)
        self.assertFalse(AssinaturaRepresentante.objects.exists())
        self.assertEqual(ar.imagem_atual(), "")

    def test_arquivo_invalido_volta_com_o_campo_e_nada_e_gravado(self):
        self.mandar("assinatura_salvar")
        antes = AssinaturaRepresentante.objects.get().sha256
        for nome, dados, tipo in (
            ("x.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script>1</script></svg>', "image/svg+xml"),
            ("x.jpg", b"<html>", "image/jpeg"),           # o nome e o tipo declarados não enganam
            ("x.png", b"%PDF-1.4", "image/png"),
        ):
            with self.subTest(arquivo=nome):
                resposta = self.mandar("assinatura_salvar", arquivo=enviada(dados, nome, tipo))
                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.json().get("campo"), "assinatura_arquivo")
        sem = self.mandar("assinatura_salvar", arquivo=False)
        self.assertEqual(sem.status_code, 400)
        self.assertEqual(AssinaturaRepresentante.objects.get().sha256, antes)

    def test_so_a_gestao_e_o_superusuario(self):
        for nome, funcao in (("ven", "vendas"), ("fin", "financeiro"), ("pro", "producao"), ("amb", "ambulante")):
            usuario = User.objects.create_user(f"rubrica-{nome}", password="x")
            atribuir_funcoes(usuario, (funcao,))
            for acao in ("assinatura_previa", "assinatura_salvar", "assinatura_remover"):
                with self.subTest(funcao=funcao, acao=acao):
                    self.assertNotEqual(self.mandar(acao, usuario).status_code, 200)
            self.assertNotEqual(self.client.get(TELA, **INTERNO).status_code, 200)
        self.client.logout()
        self.assertNotEqual(self.mandar("assinatura_salvar", usuario=False).status_code, 200)
        self.assertFalse(AssinaturaRepresentante.objects.exists())

    def test_a_tela_avisa_que_falta_e_mostra_a_cadastrada(self):
        self.client.force_login(self.gestora)
        html = self.client.get(TELA, **INTERNO).content.decode()
        self.assertIn("Ainda não há assinatura cadastrada", html)
        self.assertIn('data-tem="0"', html)
        self.assertIn('accept="image/jpeg,image/png,image/webp"', html)
        self.assertNotIn(MARCA, html)
        self.mandar("assinatura_salvar")
        html = self.client.get(TELA, **INTERNO).content.decode()
        self.assertIn('data-tem="1"', html)
        self.assertIn(ar.imagem_atual(), html)
        self.assertIn(NOTA, html)
        self.assertNotIn("<select", html)


class NosDocumentosTests(BaseDocumento):
    def setUp(self):
        super().setUp()
        self.gestao = self.usuario("gestora-doc", "gestao")

    def cadastrar(self):
        return ar.salvar(foto_sintetica(), self.gestao)

    def paginas(self, documento):
        """A cópia que o cliente vê e a via do painel (a tela e a impressão)."""
        self.client.force_login(self.vendedor)
        return {
            "publica": self.client.get(f"/assinado/{documento.codigo_publico}/").content.decode(),
            "via": self.client.get(f"/orcamentos/{self.orcamento.pk}/documento/via/", **INTERNO).content.decode(),
            "impressao": self.client.get(f"/orcamentos/{self.orcamento.pk}/documento/via/?imprimir=1", **INTERNO).content.decode(),
        }

    def test_so_depois_de_o_cliente_assinar(self):
        imagem = ar.data_url(self.cadastrar().png)
        documento = self.gerar()
        token = self.link(documento)
        esperando = self.client.get(f"/assinar/{token}/").content.decode()
        self.assertNotIn(imagem, esperando)
        self.assertNotIn(NOTA, esperando)
        self.client.force_login(self.vendedor)
        self.assertNotIn(imagem, self.client.get(f"/orcamentos/{self.orcamento.pk}/documento/via/", **INTERNO).content.decode())
        self.assertEqual(self.assinar(token).status_code, 200)
        documento.refresh_from_db()
        for nome, html in self.paginas(documento).items():
            with self.subTest(pagina=nome):
                self.assertIn(imagem, html)
                self.assertIn(NOTA, html)
                self.assertIn("ct-assina-empresa", html)
                self.assertIn("Assinatura da empresa", html)             # a linha no registro
                self.assertIn("não é uma assinatura eletrônica feita neste ato", html)

    def test_os_ja_assinados_ganham_e_o_retrato_e_os_hashes_nao_mudam(self):
        documento = self.gerar()
        self.assertEqual(self.assinar(self.link(documento)).status_code, 200)
        documento.refresh_from_db()
        antes = (documento.conteudo, documento.hash_conteudo, documento.hash_assinado,
                 bytes(documento.assinatura_png), documento.assinado_em, documento.atualizado)
        for html in self.paginas(documento).values():        # sem cadastro: como sempre
            self.assertNotIn(NOTA, html)
            self.assertNotIn("Assinatura da empresa", html)
        imagem = ar.data_url(self.cadastrar().png)
        for nome, html in self.paginas(documento).items():   # cadastrou depois: o antigo ganha
            with self.subTest(pagina=nome):
                self.assertIn(imagem, html)
                self.assertIn(NOTA, html)
        documento = DocumentoAssinatura.objects.get(pk=documento.pk)
        depois = (documento.conteudo, documento.hash_conteudo, documento.hash_assinado,
                  bytes(documento.assinatura_png), documento.assinado_em, documento.atualizado)
        self.assertEqual(depois, antes)
        self.assertEqual(svc.hash_do_retrato(documento.conteudo), documento.hash_conteudo)
        # removeu: volta a sair como antes, na hora
        ar.remover()
        for html in self.paginas(documento).values():
            self.assertNotIn(imagem, html)
            self.assertNotIn(NOTA, html)

    def test_os_nomes_sao_os_do_retrato_e_o_antigo_usa_os_de_agora(self):
        self.cadastrar()
        documento = self.gerar()
        self.assinar(self.link(documento))
        documento.refresh_from_db()
        nome_no_retrato = documento.conteudo["vendedor"]["representante_nome"]
        self.assertTrue(nome_no_retrato)
        # os dados mudam depois: o documento continua com o nome que ele guardou
        dados = DadosContrato.atual()
        dados.representante_nome = "Outro Representante Sintético"
        dados.save()
        html = self.paginas(documento)["publica"]
        self.assertIn(f'alt="Assinatura de {nome_no_retrato}"', html)
        self.assertNotIn("Outro Representante Sintético", html)

    def test_o_termo_antigo_tambem_ganha(self):
        imagem = ar.data_url(self.cadastrar().png)
        documento = self.gerar()
        self.assinar(self.link(documento))
        documento.refresh_from_db()
        # um TERMO de antes do contrato, já assinado (o retrato dele não tem o vendedor)
        antigo = conteudo_do_termo_antigo(documento, "2026-11")
        DocumentoAssinatura.objects.filter(pk=documento.pk).update(
            conteudo=antigo, hash_conteudo=svc.hash_do_retrato(antigo), hash_assinado=svc.hash_do_retrato(antigo),
        )
        html = self.client.get(f"/assinado/{documento.codigo_publico}/").content.decode()
        self.assertIn("folha-assinatura-empresa", html)
        self.assertIn(imagem, html)
        self.assertIn(NOTA, html)
        self.assertIn(DadosContrato.atual().representante_nome, html)

    def test_a_imagem_nao_aparece_fora_do_documento(self):
        imagem = ar.data_url(self.cadastrar().png)
        documento = self.gerar()
        self.assinar(self.link(documento))
        self.client.force_login(self.vendedor)
        for rota in ("/orcamentos/", "/assinaturas/inner/", f"/orcamentos/{self.orcamento.pk}/documento/"):
            with self.subTest(rota=rota):
                resposta = self.client.get(rota, **INTERNO)
                self.assertNotIn(imagem, resposta.content.decode())
        self.assertNotIn(imagem, self.client.get(self.orcamento.caminho_publico).content.decode())
        # o vendedor não abre a tela onde ela é cadastrada
        self.assertNotEqual(self.client.get(TELA, **INTERNO).status_code, 200)

    def test_documento_que_espera_nao_consulta_a_imagem(self):
        self.cadastrar()
        self.assertEqual(ar.para_o_documento(self.gerar()), "")
        self.assertEqual(ar.para_o_documento(None), "")


from .tests_documento_assinatura import CPF_DO_CLIENTE  # noqa: E402
from .tests_documento_os import BaseOS  # noqa: E402
from .tests_documento_pedido import BasePedido  # noqa: E402


class NaOrdemDeServicoTests(BaseOS):
    def test_a_ordem_de_servico_assinada_ganha_do_lado_da_contratada(self):
        from . import documento_servico

        imagem = ar.data_url(ar.salvar(foto_sintetica()).png)
        documento = documento_servico.gerar_da_ordem(self.ordem, self.tecnico)
        self.assertNotIn(imagem, self.client.get(f"/assinar/{svc.emitir_link(documento)[0]}/").content.decode())
        svc.assinar(documento, nome="Cliente Sintético", cpf_cnpj="52998224725", png=b"\x89PNG", ip="127.0.0.1", navegador="t")
        documento.save()
        html = self.client.get(f"/assinado/{documento.codigo_publico}/").content.decode()
        self.assertIn(imagem, html)
        self.assertIn("ct-assina-empresa", html)
        self.assertIn("CONTRATADA", html)
        self.assertIn(NOTA, html)


class NoContratoDoPedidoTests(BasePedido):
    def test_o_contrato_do_pedido_do_site_assinado_ganha(self):
        from . import documento_pedido

        imagem = ar.data_url(ar.salvar(foto_sintetica()).png)
        documento = documento_pedido.gerar_do_pedido(self.pedido_maquina, CPF_DO_CLIENTE, self.dono)
        svc.assinar(documento, nome="Cliente Sintético", cpf_cnpj="52998224725", png=b"\x89PNG", ip="127.0.0.1", navegador="t")
        documento.save()
        html = self.client.get(f"/assinado/{documento.codigo_publico}/").content.decode()
        self.assertIn(imagem, html)
        self.assertIn(NOTA, html)
