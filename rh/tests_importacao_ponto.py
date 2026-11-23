"""O cartão de ponto do relógio (PDF): ler, casar, preencher, importar e comparar.

LEIA-ME-V10, seção 125. Só dados SINTÉTICOS: os PDFs são montados aqui
(rh/apoio_testes.cartao_ponto_pdf) com o desenho do cartão do relógio --
o cabeçalho, o quadro do horário, a tabela com os totais esparsos nas
mesmas colunas, a linha TOTAIS e as alterações -- e nomes, CPFs e PIS
inventados.
"""

from __future__ import annotations

import io
import json
from datetime import date, datetime, time
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from . import cartao_ponto, importacao_ponto, ponto
from .apoio_testes import (
    INTERNO,
    PastaPrivadaTemporaria,
    cartao_ponto_pdf,
    cpf_sintetico,
    criar_colaborador,
    criar_conta,
    funcionario_do_cartao,
    pdf_sintetico,
    pis_sintetico,
)
from .models import (
    AjustePonto,
    CartaoPonto,
    Colaborador,
    DocumentoColaborador,
    ImportacaoPonto,
    MarcacaoPonto,
    RegistroImutavel,
    TipoDocumento,
    TipoMarcacao,
)

#: O mês do cartão: outubro de 2026 (12/10 é feriado nacional, uma segunda).
DIAS_DO_CARTAO = {
    date(2026, 10, 1): ["08:31", "12:00", "13:05", "18:00"],     # 36 min a menos: o relógio desconta 10
    date(2026, 10, 2): ["08:19", "12:10", "13:15", "17:00"],     # sexta, jornada de 8 h (24 min a menos)
    date(2026, 10, 5): "Falta",
    date(2026, 10, 6): ["08:05", "12:00", "12:50", "22:40"],     # jornada longa, noturno, intervalo curto
    date(2026, 10, 9): ["08:10", "12:05", "13:00", "Falta"],     # sem a última saída
    date(2026, 10, 12): "Feriado",
    date(2026, 10, 14): ["08:20 (I)", "12:00", "17:55 (M)", "Falta"],  # com as marcas do relógio
    date(2026, 10, 15): ["08:05", "12:00", "13:00", "17:57"],    # 8 min a menos: dentro da tolerância
}


#: A jornada do cartão, como a ficha a guarda (segunda a quinta 9 h, sexta 8 h).
SEMANA_DO_CARTAO = {
    "1": [["08:00", "12:00"], ["13:00", "18:00"]], "2": [["08:00", "12:00"], ["13:00", "18:00"]],
    "3": [["08:00", "12:00"], ["13:00", "18:00"]], "4": [["08:00", "12:00"], ["13:00", "18:00"]],
    "5": [["08:00", "12:00"], ["13:00", "17:00"]],
}


def ficha(n=1, **campos):
    """A ficha com a mesma jornada do relógio (o caso de quem já usa o cartão)."""
    campos.setdefault("jornada_semana", SEMANA_DO_CARTAO)
    return criar_colaborador(n, **campos)


def pdf_do_mes(n=1, **campos):
    dados = {"dias": DIAS_DO_CARTAO, "alteracoes": ["Feriado em 12/10/2026"]}
    dados.update(campos)
    return cartao_ponto_pdf(funcionario_do_cartao(n, **dados))


def arquivo(dados, nome="cartao.pdf"):
    return SimpleUploadedFile(nome, dados, content_type="application/pdf")


def pdf_so_imagem() -> bytes:
    """Um PDF sem texto nenhum (como um cartão escaneado): só uma imagem."""
    import zlib

    pixels = zlib.compress(bytes([200, 200, 200]) * 64 * 64)
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /XObject << /Im0 5 0 R >> >> >>",
        None,
        b"<< /Type /XObject /Subtype /Image /Width 64 /Height 64 /ColorSpace /DeviceRGB /BitsPerComponent 8 "
        b"/Filter /FlateDecode /Length " + str(len(pixels)).encode() + b" >>\nstream\n" + pixels + b"\nendstream",
    ]
    fluxo = b"q 500 0 0 700 40 60 cm /Im0 Do Q"
    objetos[3] = b"<< /Length " + str(len(fluxo)).encode() + b" >>\nstream\n" + fluxo + b"\nendstream"
    saida = io.BytesIO()
    saida.write(b"%PDF-1.4\n")
    posicoes = []
    for numero, corpo in enumerate(objetos, start=1):
        posicoes.append(saida.tell())
        saida.write(f"{numero} 0 obj\n".encode() + corpo + b"\nendobj\n")
    xref = saida.tell()
    saida.write(f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode())
    for posicao in posicoes:
        saida.write(f"{posicao:010d} 00000 n \n".encode())
    saida.write(f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return saida.getvalue()


# ======================================================================
# A LEITURA DO PDF (sem banco)
# ======================================================================
class LeituraTests(SimpleTestCase):
    def test_um_funcionario_cabecalho_periodo_e_horario(self):
        leitura = cartao_ponto.ler(pdf_do_mes(1))
        self.assertEqual((leitura.paginas, len(leitura.cartoes)), (1, 1))
        c = leitura.cartoes[0]
        self.assertEqual(c.nome, "PESSOA TESTE 1 SILVA")
        self.assertEqual(c.cpf, cpf_sintetico(1))
        self.assertEqual(c.pis, pis_sintetico(1))
        self.assertEqual(c.empresa_cnpj, "54486908000186")
        self.assertEqual(c.admissao, date(2026, 1, 5))
        self.assertEqual((c.inicio, c.fim), (date(2026, 10, 1), date(2026, 10, 31)))
        self.assertEqual(c.emitido_em, datetime(2026, 11, 18, 16, 45))
        self.assertEqual(len(c.dias), 31)
        self.assertEqual(c.horario[1], [(time(8), time(12)), (time(13), time(18))])
        self.assertEqual(c.horario[5], [(time(8), time(12)), (time(13), time(17))])
        self.assertEqual((c.horario[6], c.horario[7]), ([], []))
        self.assertEqual(c.alteracoes, ["Feriado em 12/10/2026"])
        self.assertEqual(c.feriados, [date(2026, 10, 12)])
        self.assertEqual(c.avisos, [])

    def test_colunas_esparsas_pela_posicao(self):
        c = cartao_ponto.ler(pdf_do_mes(1)).cartoes[0]
        dia = {d.data: d for d in c.dias}
        # 06/10: normais, noturno e as extras -- nenhuma coluna trocada de lugar
        self.assertEqual(dia[date(2026, 10, 6)].totais, {
            "normais": 540, "noturno": 40, "extra_50d": 235, "extra_50n": 40,
            "extra_diurna": 235, "extra_noturna": 40,
        })
        # 01/10: só normais e falta e atraso (o resto da linha vazio)
        self.assertEqual(dia[date(2026, 10, 1)].totais, {"normais": 504, "falta_atraso": 26})
        self.assertEqual(c.soma_dos_dias(), c.totais)

    def test_falta_folga_feriado_e_marcacao_faltando(self):
        c = cartao_ponto.ler(pdf_do_mes(1)).cartoes[0]
        dia = {d.data: d for d in c.dias}
        self.assertEqual(dia[date(2026, 10, 5)].ocorrencia, "falta")
        self.assertEqual(dia[date(2026, 10, 5)].totais, {"dia_falta": 1, "falta_atraso": 540})
        self.assertEqual(dia[date(2026, 10, 3)].ocorrencia, "folga")
        self.assertEqual(dia[date(2026, 10, 12)].ocorrencia, "feriado")
        sem_saida = dia[date(2026, 10, 9)]
        self.assertEqual(sem_saida.ocorrencia, "")
        self.assertEqual([m.hora for m in sem_saida.horas], [time(8, 10), time(12, 5), time(13, 0)])
        self.assertEqual(sem_saida.marcas_faltando, 1)
        self.assertEqual(sem_saida.marcas[-1].palavra, "falta")

    def test_as_marcas_do_relogio_ficam_com_a_hora(self):
        c = cartao_ponto.ler(pdf_do_mes(1)).cartoes[0]
        dia = next(d for d in c.dias if d.data == date(2026, 10, 14))
        self.assertEqual([(m.hora, m.marcador) for m in dia.horas],
                         [(time(8, 20), "I"), (time(12, 0), ""), (time(17, 55), "M")])

    def test_varios_funcionarios_e_paginas(self):
        dados = cartao_ponto_pdf(funcionario_do_cartao(1, dias=DIAS_DO_CARTAO), funcionario_do_cartao(2), linhas_por_pagina=20)
        leitura = cartao_ponto.ler(dados)
        self.assertEqual(leitura.paginas, 4)
        self.assertEqual([c.cpf for c in leitura.cartoes], [cpf_sintetico(1), cpf_sintetico(2)])
        self.assertEqual([c.paginas for c in leitura.cartoes], [[1, 2], [3, 4]])
        self.assertTrue(all(len(c.dias) == 31 for c in leitura.cartoes))
        self.assertTrue(all(c.soma_dos_dias() == c.totais for c in leitura.cartoes))

    def test_o_texto_em_layout_da_o_mesmo(self):
        leitor = cartao_ponto._pdf(pdf_do_mes(1))
        por_posicao = cartao_ponto._ler_pagina(leitor.pages[0], 1)
        por_layout = cartao_ponto._ler_pagina(leitor.pages[0], 1, por_layout=True)
        self.assertEqual([c[1] for c in por_posicao.colunas], [c[1] for c in por_layout.colunas])
        self.assertEqual([d.para_json() for d in por_posicao.dias], [d.para_json() for d in por_layout.dias])
        self.assertEqual(por_posicao.totais, por_layout.totais)

    def test_totais_que_nao_batem_viram_aviso(self):
        dados = cartao_ponto_pdf(funcionario_do_cartao(1, dias=DIAS_DO_CARTAO), totais_errados={"normais": 1})
        c = cartao_ponto.ler(dados).cartoes[0]
        self.assertTrue(any("TOTAIS" in a for a in c.avisos))

    def test_pdf_escaneado_e_pdf_que_nao_e_cartao(self):
        with self.assertRaises(cartao_ponto.CartaoIlegivel) as erro:
            cartao_ponto.ler(pdf_so_imagem())
        self.assertEqual(erro.exception.titulo, "PDF sem texto")
        with self.assertRaises(cartao_ponto.CartaoIlegivel) as erro:
            cartao_ponto.ler(pdf_sintetico("Uma carta qualquer, sem tabela de ponto."))
        self.assertIn("Não achei um cartão de ponto", str(erro.exception))


# ======================================================================
# A IMPORTAÇÃO
# ======================================================================
@override_settings(EMPRESA_CNPJ="54.486.908/0001-86")
class Base(PastaPrivadaTemporaria, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.gestora = criar_conta("gestora-cartao", "gestao")
        cls.financeiro = criar_conta("financeiro-cartao", "financeiro")
        cls.montador = criar_conta("montador-cartao", "producao")

    def setUp(self):
        self.client.force_login(self.gestora)
        self.agora = mock.patch("django.utils.timezone.now",
                                return_value=datetime(2026, 11, 23, 10, 0, tzinfo=timezone.get_default_timezone()))
        self.agora.start()
        self.addCleanup(self.agora.stop)

    def enviar(self, dados, nome="cartao.pdf", **extra):
        return self.client.post("/rh/ponto/cartoes/enviar/", {"arquivos": arquivo(dados, nome), **extra},
                                HTTP_X_REQUESTED_WITH="XMLHttpRequest", **INTERNO)

    def importar(self, cartao, **dados):
        return self.client.post(f"/rh/ponto/cartoes/cartao/{cartao.pk}/importar/", dados,
                                HTTP_X_REQUESTED_WITH="XMLHttpRequest", **INTERNO)


class CasarETrazerTests(Base):
    def test_acha_pelo_cpf_e_abre_a_conferencia(self):
        pessoa = criar_colaborador(1)
        resposta = self.enviar(pdf_do_mes(1))
        self.assertEqual(resposta.status_code, 200, resposta.content)
        corpo = resposta.json()
        self.assertEqual(corpo["status"], "sucesso")
        cartao = CartaoPonto.objects.get()
        self.assertEqual((cartao.colaborador, cartao.casado_por, cartao.situacao), (pessoa, "cpf", "pendente"))
        self.assertIn(f"/rh/ponto/cartoes/?ids={cartao.importacao_id}", corpo["ir"])
        tela = self.client.get(corpo["ir"], **INTERNO)
        self.assertContains(tela, pessoa.nome)
        self.assertContains(tela, "Ficha achada pelo")
        self.assertContains(tela, "Importar para o ponto")
        self.assertNotContains(tela, "<select")

    def test_acha_pelo_pis_quando_o_cpf_nao_bate(self):
        pessoa = criar_colaborador(3)
        self.enviar(pdf_do_mes(33, pis=pis_sintetico(3)))
        cartao = CartaoPonto.objects.get()
        self.assertEqual((cartao.colaborador, cartao.casado_por), (pessoa, "pis"))
        plano = importacao_ponto.plano_da_ficha(pessoa, cartao)
        self.assertEqual([linha["campo"] for linha in plano if linha["acao"] == "divergente"][:2], ["nome", "cpf"])

    def test_nunca_pelo_nome(self):
        criar_colaborador(4, nome="Pessoa Teste 1 Silva")
        self.enviar(pdf_do_mes(1))
        self.assertIsNone(CartaoPonto.objects.get().colaborador)

    def test_pis_igual_ao_cpf_nao_conta_nem_preenche(self):
        pessoa = criar_colaborador(5, pis=None, vinculo="pj")
        self.enviar(pdf_do_mes(5, pis=cpf_sintetico(5)))
        cartao = CartaoPonto.objects.get()
        self.assertEqual(cartao.casado_por, "cpf")
        plano = {linha["campo"]: linha for linha in importacao_ponto.plano_da_ficha(pessoa, cartao)}
        self.assertEqual(plano["pis"]["acao"], "ignorado")
        self.importar(cartao)
        pessoa.refresh_from_db()
        self.assertIsNone(pessoa.pis)

    def test_o_mesmo_arquivo_nao_entra_duas_vezes(self):
        criar_colaborador(1)
        dados = pdf_do_mes(1)
        self.enviar(dados)
        segunda = self.enviar(dados).json()
        self.assertEqual(ImportacaoPonto.objects.count(), 1)
        self.assertEqual(segunda["janela"]["titulo"], "Já recebido")
        self.assertIn("já recebido", " ".join(segunda["janela"]["lista"]))

    def test_arquivo_que_nao_e_cartao_vira_janela_com_o_campo(self):
        resposta = self.enviar(pdf_so_imagem())
        self.assertEqual(resposta.status_code, 400)
        corpo = resposta.json()
        self.assertEqual((corpo["titulo"], corpo["campo"]), ("PDF sem texto", "arquivos"))
        resposta = self.client.post("/rh/ponto/cartoes/enviar/", {}, HTTP_X_REQUESTED_WITH="XMLHttpRequest", **INTERNO)
        self.assertEqual(resposta.json()["titulo"], "Nenhum arquivo")
        self.assertFalse(ImportacaoPonto.objects.exists())

    def test_cnpj_de_outra_empresa_so_entra_com_o_mesmo_assim(self):
        criar_colaborador(1)
        self.client.post("/rh/ponto/cartoes/enviar/",
                         {"arquivos": arquivo(cartao_ponto_pdf(funcionario_do_cartao(1), cnpj="11222333000181"))},
                         HTTP_X_REQUESTED_WITH="XMLHttpRequest", **INTERNO)
        importacao = ImportacaoPonto.objects.get()
        self.assertFalse(importacao.cnpj_confere)
        cartao = importacao.cartoes.get()
        resposta = self.importar(cartao)
        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(resposta.json()["acao"]["chave"], "forcar_cnpj")
        self.assertFalse(MarcacaoPonto.objects.exists())
        self.assertEqual(self.importar(cartao, forcar_cnpj="1").status_code, 200)
        cartao.refresh_from_db()
        self.assertTrue(cartao.resultado["cnpj_forcado"])


class ImportarTests(Base):
    def test_lanca_as_marcacoes_com_a_origem_e_a_cadeia(self):
        pessoa = ficha(1)
        self.enviar(pdf_do_mes(1))
        cartao = CartaoPonto.objects.get()
        resposta = self.importar(cartao)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(resposta.json()["janela"]["titulo"], "Cartão importado")
        marcas = list(MarcacaoPonto.objects.filter(colaborador=pessoa).order_by("nsr"))
        lido = cartao_ponto.ler(pdf_do_mes(1)).cartoes[0]
        self.assertEqual(len(marcas), sum(len(d.horas) for d in lido.dias))
        self.assertTrue(all(m.origem == "rep" and m.cartao_id == cartao.pk for m in marcas))
        self.assertEqual([m.nsr for m in marcas], list(range(1, len(marcas) + 1)))
        self.assertEqual(ponto.conferir_cadeia(pessoa), [])
        dia14 = [m for m in marcas if m.data == date(2026, 10, 14)]
        self.assertEqual([(m.marcador, m.tipo) for m in dia14],
                         [("I", TipoMarcacao.ENTRADA), (None, TipoMarcacao.SAIDA_INTERVALO), ("M", TipoMarcacao.VOLTA_INTERVALO)])
        self.assertIn("(I) Incluído", dia14[0].origem_rotulo)
        cartao.refresh_from_db()
        self.assertTrue(cartao.importado)
        self.assertEqual(cartao.resultado["criadas"], len(marcas))

    def test_o_espelho_fica_coerente_com_o_cartao(self):
        pessoa = ficha(1)
        self.enviar(pdf_do_mes(1))
        cartao = CartaoPonto.objects.get()
        self.importar(cartao)
        pessoa.refresh_from_db()
        e = ponto.espelho_periodo(pessoa, date(2026, 10, 1), date(2026, 10, 31))
        dia = {d.data: d for d in e.dias}
        self.assertTrue(dia[date(2026, 10, 5)].falta)                  # Falta: o espelho conta sozinho
        self.assertEqual(dia[date(2026, 10, 12)].feriado, "Nossa Senhora Aparecida")
        self.assertTrue(dia[date(2026, 10, 9)].incompleto)             # sem a última saída
        self.assertEqual(dia[date(2026, 10, 9)].falta_texto, "sem a volta do intervalo e a saída"
                         if dia[date(2026, 10, 9)].efetivos[-1].tipo == TipoMarcacao.SAIDA_INTERVALO else "sem a saída")
        self.assertTrue(dia[date(2026, 10, 6)].jornada_longa)
        self.assertEqual(dia[date(2026, 10, 6)].noturno, 40)
        self.assertEqual(dia[date(2026, 10, 2)].esperado, 8 * 60)      # a sexta do relógio: 8 h
        self.assertEqual(dia[date(2026, 10, 1)].esperado, 9 * 60)
        chaves = {a["chave"] for a in e.alertas}
        self.assertTrue({"incompleto", "falta", "longa", "atraso"} <= chaves)

    def test_a_comparacao_explica_a_tolerancia(self):
        ficha(1)
        self.enviar(pdf_do_mes(1))
        cartao = CartaoPonto.objects.get()
        self.importar(cartao)
        cartao.refresh_from_db()
        r = importacao_ponto.comparar(cartao)
        linhas = {linha["chave"]: linha for linha in r["linhas"]}
        for chave in ("normais", "noturno", "dia_falta"):
            self.assertTrue(linhas[chave]["confere"], linhas[chave])
        # 01/10 (36 min) e 02/10 (24 min): o relógio desconta 10 de cada; 06/10: 10 a menos de extra
        self.assertEqual(linhas["falta_atraso"]["diferenca_minutos"], 20)
        self.assertEqual(linhas["extras"]["diferenca_minutos"], 10)
        self.assertEqual([m["chave"] for m in r["motivos"]], ["tolerancia"])
        self.assertTrue(r["so_regra"])
        self.assertEqual(sorted(d["data"] for d in r["dias"]),
                         [date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 6)])

    def test_preenche_o_vazio_e_nao_mexe_no_preenchido_sem_escolha(self):
        pessoa = criar_colaborador(6, pis=None, vinculo="pj", data_admissao=date(2026, 2, 2),
                                   jornada_inicio=time(8), jornada_fim=time(18), jornada_intervalo_min=60)
        self.enviar(pdf_do_mes(6, matricula="1234", pis=pis_sintetico(6)))
        cartao = CartaoPonto.objects.get()
        plano = {linha["campo"]: linha for linha in importacao_ponto.plano_da_ficha(pessoa, cartao)}
        self.assertEqual(plano["pis"]["acao"], "preencher")
        self.assertEqual(plano["matricula"]["acao"], "preencher")
        self.assertEqual(plano["data_admissao"]["acao"], "divergente")
        self.assertEqual(plano["jornada_semana"]["acao"], "divergente")   # a sexta do relógio é diferente
        self.importar(cartao)
        pessoa.refresh_from_db()
        self.assertEqual((pessoa.pis, pessoa.matricula), (pis_sintetico(6), "1234"))
        self.assertEqual(pessoa.data_admissao, date(2026, 2, 2))
        self.assertEqual(pessoa.jornada_semana, {})
        cartao.refresh_from_db()
        self.assertEqual(sorted(cartao.resultado["mantidos"]), ["Admissão", "Jornada"])

    def test_a_escolha_usar_o_do_cartao(self):
        pessoa = criar_colaborador(7, data_admissao=date(2026, 2, 2))
        self.enviar(pdf_do_mes(7))
        cartao = CartaoPonto.objects.get()
        self.importar(cartao, escolha_data_admissao="cartao", escolha_jornada_semana="cartao")
        pessoa.refresh_from_db()
        self.assertEqual(pessoa.data_admissao, date(2026, 1, 5))
        self.assertEqual(pessoa.jornada_semana["5"], [["08:00", "12:00"], ["13:00", "17:00"]])
        self.assertEqual((pessoa.jornada_inicio, pessoa.jornada_fim, pessoa.jornada_intervalo_min, pessoa.jornada_dias),
                         (time(8), time(18), 60, "12345"))
        self.assertEqual(pessoa.horas_semanais, "44h")

    def test_reimportar_nao_duplica_nem_de_outro_arquivo(self):
        pessoa = ficha(1)
        self.enviar(pdf_do_mes(1))
        primeiro = CartaoPonto.objects.get()
        self.importar(primeiro)
        total = MarcacaoPonto.objects.filter(colaborador=pessoa).count()
        de_novo = self.importar(primeiro)
        self.assertEqual((de_novo.status_code, de_novo.json()["titulo"]), (409, "Já importado"))
        # o mesmo período, emitido de novo (outro arquivo), com uma batida incluída no relógio
        dias = dict(DIAS_DO_CARTAO)
        dias[date(2026, 10, 9)] = ["08:10", "12:05", "13:00", "17:00 (I)"]
        self.enviar(cartao_ponto_pdf(funcionario_do_cartao(1, dias=dias), emitido=datetime(2026, 11, 20, 9, 0)))
        segundo = CartaoPonto.objects.exclude(pk=primeiro.pk).get()
        self.importar(segundo)
        segundo.refresh_from_db()
        self.assertEqual(segundo.resultado["criadas"], 1)
        self.assertEqual(segundo.resultado["ja_estavam"], total)
        self.assertEqual(MarcacaoPonto.objects.filter(colaborador=pessoa).count(), total + 1)
        self.assertEqual(ponto.conferir_cadeia(pessoa), [])

    def test_dia_com_marcacao_do_painel_vira_pedido_de_ajuste(self):
        pessoa = ficha(1)
        fuso = timezone.get_default_timezone()
        with mock.patch("rh.ponto.timezone.now", return_value=datetime(2026, 10, 7, 8, 5, tzinfo=fuso)):
            do_painel = ponto.registrar(pessoa)
        dias = dict(DIAS_DO_CARTAO)
        dias[date(2026, 10, 7)] = ["08:20", "12:00", "13:00", "18:00"]
        self.enviar(cartao_ponto_pdf(funcionario_do_cartao(1, dias=dias)))
        cartao = CartaoPonto.objects.get()
        self.importar(cartao)
        cartao.refresh_from_db()
        do_dia = MarcacaoPonto.objects.filter(colaborador=pessoa, data=date(2026, 10, 7))
        self.assertEqual(list(do_dia), [do_painel])                      # o dia do painel não foi tocado
        pedidos = AjustePonto.objects.filter(colaborador=pessoa, data=date(2026, 10, 7))
        self.assertEqual(pedidos.count(), 4)
        self.assertTrue(all(a.situacao == "pendente" and a.tipo == "incluir" for a in pedidos))
        self.assertIn("relógio", pedidos.first().justificativa)
        self.assertEqual(cartao.resultado["pedidos_de_ajuste"], 4)
        self.assertEqual(cartao.resultado["conflitos"][0]["data"], "2026-10-07")
        r = importacao_ponto.comparar(cartao)
        self.assertIn("painel", [m["chave"] for m in r["motivos"]])

    def test_folga_num_dia_de_jornada_e_feriado_local_viram_abono(self):
        pessoa = ficha(1)
        dias = dict(DIAS_DO_CARTAO)
        dias[date(2026, 10, 16)] = "Folga"
        dias[date(2026, 10, 20)] = "Feriado"
        self.enviar(cartao_ponto_pdf(funcionario_do_cartao(1, dias=dias)))
        self.importar(CartaoPonto.objects.get())
        abonos = {a.data: a for a in AjustePonto.objects.filter(colaborador=pessoa, tipo="abono")}
        self.assertEqual(sorted(abonos), [date(2026, 10, 16), date(2026, 10, 20)])  # 12/10 é nacional: nada
        self.assertEqual(abonos[date(2026, 10, 16)].motivo_abono, "folga")
        self.assertEqual(abonos[date(2026, 10, 20)].motivo_abono, "feriado")
        self.assertTrue(all(a.situacao == "aprovado" and a.decidido_por == self.gestora for a in abonos.values()))
        e = ponto.espelho_periodo(pessoa, date(2026, 10, 1), date(2026, 10, 31))
        self.assertFalse(next(d for d in e.dias if d.data == date(2026, 10, 16)).falta)

    def test_dia_antes_da_admissao_nao_recebe_marcacao(self):
        pessoa = criar_colaborador(1, data_admissao=date(2026, 10, 10))
        self.enviar(pdf_do_mes(1))
        cartao = CartaoPonto.objects.get()
        self.importar(cartao)
        self.assertFalse(MarcacaoPonto.objects.filter(colaborador=pessoa, data__lt=date(2026, 10, 10)).exists())
        cartao.refresh_from_db()
        self.assertTrue(cartao.resultado["pulados"])

    def test_imutavel_depois_de_importar(self):
        criar_colaborador(1)
        self.enviar(pdf_do_mes(1))
        self.importar(CartaoPonto.objects.get())
        marca = MarcacaoPonto.objects.first()
        with self.assertRaises(RegistroImutavel):
            marca.save()
        with self.assertRaises(RegistroImutavel):
            marca.delete()
        with self.assertRaises(RegistroImutavel):
            MarcacaoPonto.objects.filter(pk=marca.pk).update(tipo="saida")
        # o gatilho do banco (migração 0002) continua de pé depois da 0004
        from django.db import DatabaseError, transaction

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("UPDATE rh_marcacaoponto SET marcador = 'X' WHERE id = %s", [marca.pk])
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM rh_marcacaoponto WHERE id = %s", [marca.pk])
        # e o PDF que deu origem às marcações não sai da pasta
        cartao = CartaoPonto.objects.get()
        resposta = self.client.post(f"/rh/documentos/{cartao.documento_id}/remover/",
                                    HTTP_X_REQUESTED_WITH="XMLHttpRequest", **INTERNO)
        self.assertEqual(resposta.status_code, 409)
        self.assertTrue(DocumentoColaborador.objects.filter(pk=cartao.documento_id).exists())

    def test_o_pdf_vai_para_a_pasta_so_com_as_paginas_da_pessoa(self):
        from pypdf import PdfReader

        pessoa = criar_colaborador(1)
        criar_colaborador(2)
        dados = cartao_ponto_pdf(funcionario_do_cartao(1, dias=DIAS_DO_CARTAO),
                                 funcionario_do_cartao(2, nome="OUTRA PESSOA TESTE"), linhas_por_pagina=20)
        self.enviar(dados)
        cartao = CartaoPonto.objects.get(colaborador=pessoa)
        self.importar(cartao)
        cartao.refresh_from_db()
        documento = cartao.documento
        self.assertEqual((documento.colaborador, documento.tipo), (pessoa, TipoDocumento.CARTAO_PONTO))
        with documento.arquivo.open("rb") as f:
            leitor = PdfReader(io.BytesIO(f.read()))
        self.assertEqual(len(leitor.pages), 2)
        texto = " ".join(p.extract_text() for p in leitor.pages)
        self.assertIn("PESSOA TESTE 1 SILVA", texto)
        self.assertNotIn("OUTRA PESSOA", texto)
        # e só abre pela view, para quem pode (o próprio colaborador vê o dele)
        self.assertEqual(self.client.get(f"/rh/documentos/{documento.pk}/arquivo/", **INTERNO).status_code, 200)

    def test_importar_todos_os_prontos(self):
        criar_colaborador(1)
        criar_colaborador(2)
        self.enviar(cartao_ponto_pdf(funcionario_do_cartao(1), funcionario_do_cartao(2)))
        importacao = ImportacaoPonto.objects.get()
        resposta = self.client.post(f"/rh/ponto/cartoes/{importacao.pk}/importar-todos/",
                                    HTTP_X_REQUESTED_WITH="XMLHttpRequest", **INTERNO)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertEqual(importacao.cartoes.filter(situacao="importado").count(), 2)

    def test_descartar_so_o_que_nao_entrou(self):
        criar_colaborador(1)
        self.enviar(pdf_do_mes(1))
        importacao = ImportacaoPonto.objects.get()
        nome = importacao.arquivo.name
        armazenamento = importacao.arquivo.storage
        with self.captureOnCommitCallbacks(execute=True):
            resposta = self.client.post(f"/rh/ponto/cartoes/{importacao.pk}/descartar/",
                                        HTTP_X_REQUESTED_WITH="XMLHttpRequest", **INTERNO)
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(ImportacaoPonto.objects.exists())
        self.assertFalse(armazenamento._real().exists(nome))
        self.enviar(pdf_do_mes(1))
        importacao = ImportacaoPonto.objects.get()
        self.importar(importacao.cartoes.get())
        resposta = self.client.post(f"/rh/ponto/cartoes/{importacao.pk}/descartar/",
                                    HTTP_X_REQUESTED_WITH="XMLHttpRequest", **INTERNO)
        self.assertEqual(resposta.status_code, 409)


class CadastrarPeloCartaoTests(Base):
    def dados_do_cadastro(self, cartao, **mais):
        prefixo = f"c{cartao.pk}-"
        dados = {
            "nome": "Pessoa Teste 9 Silva", "data_nascimento": "1990-05-04", "rg": "123456789",
            "pis": pis_sintetico(9), "cargo": "Montador", "setor": "producao", "vinculo": "clt",
            "data_admissao": "2026-01-05", "telefone": "11999990009", "cep": "01001-000",
            "logradouro": "Rua Inventada", "numero": "9", "bairro": "Bairro Exemplo", "cidade": "Cidade Exemplo",
            "uf": "SP", "emergencia_nome": "Contato Exemplo", "emergencia_telefone": "11988880009",
        }
        dados.update(mais)
        return {prefixo + k: v for k, v in dados.items()}

    def test_sem_ficha_cadastra_com_o_cartao_e_importa(self):
        self.enviar(pdf_do_mes(9))
        cartao = CartaoPonto.objects.get()
        self.assertIsNone(cartao.colaborador)
        tela = self.client.get(f"/rh/ponto/cartoes/?ids={cartao.importacao_id}", **INTERNO)
        self.assertContains(tela, "Cadastrar colaborador")
        self.assertContains(tela, "Pessoa Teste 9 Silva")   # o nome do cartão, sem o maiúsculo do relógio
        resposta = self.client.post(f"/rh/ponto/cartoes/cartao/{cartao.pk}/cadastrar/", self.dados_do_cadastro(cartao),
                                    HTTP_X_REQUESTED_WITH="XMLHttpRequest", **INTERNO)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        pessoa = Colaborador.objects.get(cpf=cpf_sintetico(9))
        self.assertEqual(pessoa.jornada_semana["5"], [["08:00", "12:00"], ["13:00", "17:00"]])
        cartao.refresh_from_db()
        self.assertEqual((cartao.colaborador, cartao.situacao), (pessoa, "importado"))
        self.assertTrue(MarcacaoPonto.objects.filter(colaborador=pessoa).exists())
        self.assertEqual(resposta.json()["janela"]["titulo"], "Ficha criada e cartão importado")

    def test_jornada_do_relogio_fora_da_regra_nao_entra_mas_o_cadastro_sai(self):
        longa = {1: ("07:00", "12:00", "13:00", "19:00"), 3: ("07:00", "12:00", "13:00", "19:00")}  # 11 h no dia
        self.enviar(cartao_ponto_pdf(funcionario_do_cartao(9, semana=longa)))
        cartao = CartaoPonto.objects.get()
        resposta = self.client.post(f"/rh/ponto/cartoes/cartao/{cartao.pk}/cadastrar/", self.dados_do_cadastro(cartao),
                                    HTTP_X_REQUESTED_WITH="XMLHttpRequest", **INTERNO)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        pessoa = Colaborador.objects.get(cpf=cpf_sintetico(9))
        self.assertEqual(pessoa.jornada_semana, {})
        self.assertIn("não entrou", resposta.json()["janela"]["lista"][0])
        outra = criar_colaborador(8)
        self.enviar(cartao_ponto_pdf(funcionario_do_cartao(8, semana=longa), emitido=datetime(2026, 11, 21, 8, 0)))
        plano = {linha["campo"]: linha for linha in
                 importacao_ponto.plano_da_ficha(outra, CartaoPonto.objects.get(colaborador=outra))}
        self.assertEqual(plano["jornada_semana"]["acao"], "ignorado")

    def test_o_que_falta_volta_com_o_campo_aceso(self):
        self.enviar(pdf_do_mes(9))
        cartao = CartaoPonto.objects.get()
        resposta = self.client.post(f"/rh/ponto/cartoes/cartao/{cartao.pk}/cadastrar/",
                                    self.dados_do_cadastro(cartao, cargo=""),
                                    HTTP_X_REQUESTED_WITH="XMLHttpRequest", **INTERNO)
        self.assertEqual(resposta.status_code, 400)
        corpo = resposta.json()
        self.assertEqual((corpo["titulo"], corpo["campo"]), ("Complete a ficha", f"c{cartao.pk}-cargo"))
        self.assertFalse(Colaborador.objects.exists())


class PermissaoTests(Base):
    def test_so_a_gestao_envia_importa_e_abre(self):
        criar_colaborador(1)
        self.enviar(pdf_do_mes(1))
        importacao = ImportacaoPonto.objects.get()
        cartao = importacao.cartoes.get()
        for conta in (self.financeiro, self.montador):
            self.client.force_login(conta)
            with self.subTest(conta=conta.username):
                for rota in (f"/rh/ponto/cartoes/cartao/{cartao.pk}/importar/",
                             f"/rh/ponto/cartoes/cartao/{cartao.pk}/cadastrar/",
                             f"/rh/ponto/cartoes/{importacao.pk}/importar-todos/",
                             f"/rh/ponto/cartoes/{importacao.pk}/descartar/"):
                    self.assertEqual(self.client.post(rota, **INTERNO).status_code, 302, rota)
                resposta = self.client.post("/rh/ponto/cartoes/enviar/", {"arquivos": arquivo(pdf_do_mes(2))}, **INTERNO)
                self.assertEqual(resposta.status_code, 302)
                self.assertEqual(self.client.get("/rh/ponto/cartoes/", **INTERNO).status_code, 302)
                self.assertEqual(self.client.get(f"/rh/ponto/cartoes/{importacao.pk}/arquivo/", **INTERNO).status_code, 302)
        self.assertEqual(ImportacaoPonto.objects.count(), 1)
        self.assertFalse(MarcacaoPonto.objects.exists())
        cartao.refresh_from_db()
        self.assertTrue(cartao.pendente)

    def test_o_colaborador_ve_so_o_proprio_acompanhamento(self):
        dono = criar_colaborador(1, usuario=self.montador)
        outro = criar_colaborador(2)
        self.enviar(cartao_ponto_pdf(funcionario_do_cartao(1), funcionario_do_cartao(2)))
        importacao = ImportacaoPonto.objects.get()
        self.client.post(f"/rh/ponto/cartoes/{importacao.pk}/importar-todos/", HTTP_X_REQUESTED_WITH="XMLHttpRequest", **INTERNO)
        self.client.force_login(self.montador)
        proprio = self.client.get(f"/rh/ponto/espelho/{dono.pk}/?de=2026-10-01&ate=2026-10-31", **INTERNO)
        self.assertEqual(proprio.status_code, 200)
        self.assertContains(proprio, "Cartão do relógio")
        self.assertEqual(self.client.get(f"/rh/ponto/espelho/{outro.pk}/", **INTERNO).status_code, 404)
        self.assertEqual(self.client.get("/rh/ponto/equipe/", **INTERNO).status_code, 302)


class TelasETetoDeConsultasTests(Base):
    def importar_para(self, *numeros):
        for n in numeros:
            ficha(n)
        self.enviar(cartao_ponto_pdf(*(funcionario_do_cartao(n, dias=DIAS_DO_CARTAO) for n in numeros)))
        importacao = ImportacaoPonto.objects.order_by("-id").first()
        self.client.post(f"/rh/ponto/cartoes/{importacao.pk}/importar-todos/", HTTP_X_REQUESTED_WITH="XMLHttpRequest", **INTERNO)

    def consultas(self, rota):
        with CaptureQueriesContext(connection) as contexto:
            resposta = self.client.get(rota, **INTERNO)
        self.assertEqual(resposta.status_code, 200, rota)
        return len(contexto.captured_queries), resposta

    def test_o_ponto_da_equipe_nao_cresce_com_a_equipe(self):
        self.importar_para(1, 2)
        poucos, resposta = self.consultas("/rh/ponto/equipe/?de=2026-10-01&ate=2026-10-31")
        self.assertContains(resposta, 'id="rhPontoEquipe"')
        self.assertContains(resposta, "rh-fita")
        self.assertContains(resposta, "Marcação faltando")
        self.importar_para(3, 4, 5, 6)
        muitos, _ = self.consultas("/rh/ponto/equipe/?de=2026-10-01&ate=2026-10-31")
        self.assertEqual(poucos, muitos)
        self.assertLessEqual(muitos, 22)

    def test_inicio_mostra_o_que_o_ponto_pede(self):
        self.importar_para(1)
        quantas, resposta = self.consultas("/rh/")
        self.assertContains(resposta, "Ponto: o que pede atenção")
        self.assertContains(resposta, "com marcação faltando")
        self.assertContains(resposta, "Pessoa Teste 1 Silva")
        self.assertLessEqual(quantas, 40)

    def test_acompanhamento_e_conferencia_com_teto(self):
        self.importar_para(1)
        pessoa = Colaborador.objects.get(cpf=cpf_sintetico(1))
        quantas, resposta = self.consultas(f"/rh/ponto/espelho/{pessoa.pk}/?de=2026-10-01&ate=2026-10-31")
        self.assertContains(resposta, "Linha do tempo")
        self.assertContains(resposta, "Tolerância de 10 min")
        self.assertContains(resposta, "rh-trilho--trabalho")
        self.assertLessEqual(quantas, 16)
        importacao = ImportacaoPonto.objects.get()
        quantas, resposta = self.consultas(f"/rh/ponto/cartoes/?ids={importacao.pk}")
        self.assertContains(resposta, "Cartão do relógio × sistema")
        self.assertContains(resposta, "Só diferença de regra")
        self.assertLessEqual(quantas, 16)

    def test_importar_um_mes_nao_faz_uma_consulta_por_dia(self):
        criar_colaborador(1)
        self.enviar(pdf_do_mes(1))
        cartao = CartaoPonto.objects.get()
        with CaptureQueriesContext(connection) as contexto:
            self.importar(cartao)
        self.assertLessEqual(len(contexto.captured_queries), 30)


class JornadaDaFichaTests(Base):
    def test_a_ficha_salva_a_jornada_dia_a_dia(self):
        from .forms import ColaboradorForm

        pessoa = criar_colaborador(1)
        dados = {campo: valor for campo, valor in ColaboradorForm(instance=pessoa).initial.items() if valor is not None}
        dados.update({
            "cpf": pessoa.cpf, "pis": pessoa.pis, "cep": pessoa.cep, "telefone": pessoa.telefone,
            "emergencia_telefone": pessoa.emergencia_telefone, "salario": "2.500,00",
            "data_nascimento": "1990-01-01", "data_admissao": "2026-01-05",
            "jornada_inicio": "08:00", "jornada_fim": "17:00", "jornada_intervalo_min": "60",
            "jornada_dias": list("12345"), "jornada_por_dia": "on",
        })
        for dia in "1234":
            dados.update({f"js_{dia}_0": "08:00", f"js_{dia}_1": "12:00", f"js_{dia}_2": "13:00", f"js_{dia}_3": "18:00"})
        dados.update({"js_5_0": "08:00", "js_5_1": "12:00", "js_5_2": "13:00", "js_5_3": "17:00"})
        dados.pop("especialidades", None)
        form = ColaboradorForm(dados, instance=pessoa)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        pessoa.refresh_from_db()
        self.assertEqual(pessoa.minutos_previstos(date(2026, 10, 2)), 480)
        self.assertEqual(pessoa.minutos_previstos(date(2026, 10, 1)), 540)
        self.assertEqual(pessoa.jornada_dias, "12345")
        dados["js_3_1"] = "07:00"   # saída antes da entrada na quarta
        form = ColaboradorForm(dados, instance=pessoa)
        self.assertFalse(form.is_valid())
        self.assertIn("Qua", " ".join(form.errors.get("jornada_semana", [])))
