"""As validações da ficha e dos arquivos (dados sintéticos)."""

from datetime import date, time, timedelta
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from . import arquivos
from .apoio_testes import (
    INTERNO,
    PastaPrivadaTemporaria,
    cpf_sintetico,
    criar_colaborador,
    criar_conta,
    imagem_sintetica,
    pdf_sintetico,
    pis_sintetico,
)
from .armazenamento import ArquivoSemEnderecoPublico, armazenamento_privado, pasta_privada
from .forms import ColaboradorForm
from .models import DocumentoColaborador, RegistroRH
from .validadores import pis_valido


class DigitosTests(SimpleTestCase):
    def test_cpf_e_pis_gerados_sao_validos_e_o_digito_errado_nao(self):
        for n in range(1, 30):
            pis = pis_sintetico(n)
            self.assertEqual(len(cpf_sintetico(n)), 11)
            self.assertTrue(pis_valido(pis), pis)
            errado = pis[:-1] + str((int(pis[-1]) + 1) % 10)
            self.assertFalse(pis_valido(errado))
        self.assertFalse(pis_valido("11111111111"))
        self.assertFalse(pis_valido("123"))


class FichaTests(TestCase):
    def ficha(self, **campos):
        return criar_colaborador(campos.pop("n", 1), **campos)

    def erro_em(self, campo, **dados):
        with self.assertRaises(ValidationError) as ctx:
            self.ficha(**dados)
        self.assertIn(campo, ctx.exception.message_dict, ctx.exception.message_dict)

    def test_cpf_invalido(self):
        self.erro_em("cpf", cpf="12345678900")

    def test_cpf_unico(self):
        self.ficha(n=1)
        self.erro_em("cpf", n=2, cpf=cpf_sintetico(1))

    def test_pis_invalido_e_obrigatorio_na_clt(self):
        self.erro_em("pis", pis="12345678901")
        self.erro_em("pis", pis="", vinculo="clt")
        self.assertIsNone(self.ficha(n=3, pis="", vinculo="pj").pis)

    def test_cep_com_8_numeros(self):
        self.erro_em("cep", cep="0100100")

    def test_admissao_nao_pode_ser_no_futuro(self):
        self.erro_em("data_admissao", data_admissao=timezone.localdate() + timedelta(days=1))

    def test_maior_de_idade_para_clt_e_pj(self):
        admissao = date(2026, 1, 5)
        dezessete = date(admissao.year - 17, admissao.month, admissao.day)
        self.erro_em("data_nascimento", data_nascimento=dezessete, vinculo="clt")
        self.erro_em("data_nascimento", data_nascimento=dezessete, vinculo="pj", pis="")
        estagio = self.ficha(n=4, data_nascimento=dezessete, vinculo="estagio", pis="")
        self.assertEqual(estagio.vinculo, "estagio")

    def test_desligamento_coerente(self):
        self.erro_em("data_desligamento", situacao="desligado")
        self.erro_em("data_desligamento", situacao="desligado", data_desligamento=date(2025, 12, 1))
        self.erro_em("data_desligamento", situacao="ativo", data_desligamento=date(2026, 2, 1))
        ok = self.ficha(n=5, situacao="desligado", data_desligamento=date(2026, 2, 1))
        self.assertEqual(ok.situacao, "desligado")

    def test_contato_de_emergencia_e_outra_pessoa(self):
        self.erro_em("emergencia_telefone", telefone="11988887777", emergencia_telefone="11988887777")

    def test_jornada(self):
        self.erro_em("jornada_fim", jornada_inicio=time(17), jornada_fim=time(8))
        self.erro_em("jornada_intervalo_min", jornada_inicio=time(8), jornada_fim=time(17), jornada_intervalo_min=15)
        self.erro_em("jornada_fim", jornada_inicio=time(6), jornada_fim=time(19), jornada_intervalo_min=60)
        self.erro_em("jornada_dias", jornada_dias="")

    def test_pix_pelo_tipo(self):
        self.erro_em("pix_chave", pix_tipo="cpf", pix_chave="11111111111")
        self.erro_em("pix_chave", pix_tipo="email", pix_chave="sem-arroba")
        self.erro_em("pix_tipo", pix_chave="algo")
        ok = self.ficha(n=6, pix_tipo="telefone", pix_chave="(11) 97777-6655")
        self.assertEqual(ok.pix_chave, "11977776655")

    def test_formulario_aceita_mascaras_e_avisa_cpf_repetido(self):
        existente = self.ficha(n=7)
        dados = {
            "nome": "Nova Pessoa Teste", "cpf": "", "rg": "1", "data_nascimento": "1995-05-05",
            "pis": "", "cep": "01001-000", "logradouro": "Rua X", "numero": "1", "bairro": "B",
            "cidade": "C", "uf": "sp", "telefone": "(11) 91234-5678", "emergencia_nome": "Contato",
            "emergencia_telefone": "(11) 3333-4444", "cargo": "Auxiliar", "setor": "producao",
            "data_admissao": "2026-02-02", "vinculo": "pj", "situacao": "ativo",
            "jornada_inicio": "08:00", "jornada_fim": "17:00", "jornada_intervalo_min": "60",
            "jornada_dias": ["1", "2", "3", "4", "5"], "salario": "3.200,50",
        }
        cpf = cpf_sintetico(77)
        dados["cpf"] = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
        form = ColaboradorForm(dados)
        self.assertTrue(form.is_valid(), form.errors)
        salvo = form.save()
        self.assertEqual((salvo.cpf, salvo.cep, salvo.uf, str(salvo.salario)), (cpf, "01001000", "SP", "3200.50"))
        dados["cpf"] = existente.cpf
        form = ColaboradorForm(dados)
        self.assertFalse(form.is_valid())
        self.assertIn("Já existe uma ficha com este CPF.", form.errors["cpf"])


class ArquivoTests(SimpleTestCase):
    def enviar(self, nome, dados):
        return arquivos.conferir(SimpleUploadedFile(nome, dados))

    def test_pdf_jpg_png_webp_validos(self):
        self.assertEqual(self.enviar("rg.pdf", pdf_sintetico()).tipo_conteudo, "application/pdf")
        self.assertEqual(self.enviar("rg.jpg", imagem_sintetica("JPEG")).tipo_conteudo, "image/jpeg")
        self.assertEqual(self.enviar("rg.png", imagem_sintetica("PNG")).tipo_conteudo, "image/png")
        self.assertEqual(self.enviar("rg.webp", imagem_sintetica("WEBP")).tipo_conteudo, "image/webp")

    def test_confere_o_conteudo_e_nao_so_a_extensao(self):
        casos = {
            "executavel.pdf": b"MZ\x90\x00" + b"\x00" * 200,
            "pagina.jpg": b"<html><script>alert(1)</script></html>",
            "falso.pdf": b"%PDF-1.4\n isto nao e um pdf de verdade",
        }
        for nome, dados in casos.items():
            with self.subTest(nome=nome):
                with self.assertRaises(ValidationError):
                    self.enviar(nome, dados)

    def test_extensao_que_nao_bate_com_o_conteudo(self):
        with self.assertRaises(ValidationError) as ctx:
            self.enviar("comprovante.pdf", imagem_sintetica("PNG"))
        self.assertIn("PNG", str(ctx.exception))

    def test_ate_10_mb(self):
        grande = pdf_sintetico() + b"%" + b"0" * (10 * 1024 * 1024)
        with self.assertRaises(ValidationError):
            self.enviar("grande.pdf", grande)

    def test_pdf_com_javascript_e_recusado(self):
        perigoso = pdf_sintetico().replace(b"/Type /Catalog", b"/Type /Catalog /OpenAction << /S /JavaScript /JS (app.alert(1)) >>")
        with self.assertRaises(ValidationError):
            self.enviar("rg.pdf", perigoso)

    def test_imagem_corrompida(self):
        with self.assertRaises(ValidationError):
            self.enviar("foto.jpg", imagem_sintetica("JPEG")[:120])


class ArmazenamentoPrivadoTests(PastaPrivadaTemporaria, TestCase):
    def test_arquivo_fora_do_media_sem_url_e_servido_so_pela_view(self):
        gestora = criar_conta("gestora-docs", "gestao")
        c = criar_colaborador(11)
        self.client.force_login(gestora)
        resposta = self.client.post(
            f"/rh/colaboradores/{c.pk}/documentos/",
            {"tipo": "residencia", "emissao": timezone.localdate().isoformat(),
             "arquivo": SimpleUploadedFile("comprovante.pdf", pdf_sintetico("Conta de luz"))},
            **INTERNO,
        )
        self.assertEqual(resposta.status_code, 302)
        doc = DocumentoColaborador.objects.get(colaborador=c)
        caminho = Path(armazenamento_privado.path(doc.arquivo.name))
        self.assertTrue(caminho.exists())
        self.assertTrue(str(caminho).startswith(str(pasta_privada())))
        self.assertFalse(str(caminho).startswith(str(settings.MEDIA_ROOT)))
        self.assertNotIn(str(c.cpf), doc.arquivo.name)
        self.assertNotIn("Pessoa", doc.arquivo.name)
        with self.assertRaises(ArquivoSemEnderecoPublico):
            doc.arquivo.url
        ficha = self.client.get(f"/rh/colaboradores/{c.pk}/", **INTERNO).content.decode()
        self.assertNotIn(doc.arquivo.name, ficha)
        self.assertIn(f"/rh/documentos/{doc.pk}/arquivo/", ficha)

        aberto = self.client.get(f"/rh/documentos/{doc.pk}/arquivo/", **INTERNO)
        self.assertEqual(aberto.status_code, 200)
        self.assertIn("no-store", aberto["Cache-Control"])
        self.assertEqual(aberto["X-Content-Type-Options"], "nosniff")
        self.assertTrue(RegistroRH.objects.filter(acao="doc_aberto", documento=doc, usuario=gestora).exists())
        self.assertTrue(RegistroRH.objects.filter(acao="doc_enviado", documento=doc).exists())

        # O arquivo sai do armazenamento DEPOIS do commit (ver rh/sinais.py).
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f"/rh/documentos/{doc.pk}/remover/", **INTERNO)
        self.assertFalse(DocumentoColaborador.objects.filter(pk=doc.pk).exists())
        self.assertFalse(caminho.exists())
        self.assertTrue(RegistroRH.objects.filter(acao="doc_removido", colaborador=c).exists())

    def test_envio_recusado_nao_guarda_nada(self):
        gestora = criar_conta("gestora-docs2", "gestao")
        c = criar_colaborador(12)
        self.client.force_login(gestora)
        self.client.post(
            f"/rh/colaboradores/{c.pk}/documentos/",
            {"tipo": "aso", "arquivo": SimpleUploadedFile("aso.pdf", pdf_sintetico())},  # ASO sem validade
            **INTERNO,
        )
        self.assertFalse(DocumentoColaborador.objects.exists())
        self.assertFalse(any(Path(pasta_privada()).rglob("*.pdf")))
