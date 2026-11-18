"""ENTRADA DE NOTA FISCAL NO ESTOQUE (LEIA-ME-V10, seção 115).

"Na entrada, devemos lançar uma nota com os materiais, auto criando se não
existir e registrando o estoque, dia de entrada e soma se houver juntos. O
financeiro dá entrada pela função."

O que estes testes seguram:

  * O LEITOR, a partir de um DANFE SINTÉTICO em texto (o leiaute padrão,
    com canhoto, chave de acesso, emitente, destinatário, impostos e o
    quadro de produtos em duas páginas) -- nenhum dado de nota real -- e do
    XML sintético da MESMA nota: as duas portas dão os mesmos campos e os
    mesmos itens. E um PDF de verdade, montado aqui com esse texto.
  * A LIGAÇÃO com os materiais (nome sem acento, parecido só com as mesmas
    medidas, cento vira unidades) e a SOMA dos itens repetidos.
  * O LANÇAMENTO pelas telas, como o Financeiro faz: fornecedor e materiais
    criados se faltarem, a entrada no estoque pelo caminho de sempre
    (MovimentoEstoque, com a data, a nota e quem lançou), a compra no
    Financeiro, e a mesma nota recusada na segunda vez.
  * QUEM: Financeiro e Gestão lançam; Produção vê as lançadas; Vendas não
    abre.
  * Os pontos do estoque que travavam a entrada (ver a seção 115).
"""

from __future__ import annotations

import shutil
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    ComprasMensais,
    EstoqueMaterial,
    Fornecedor,
    ItemFichaTecnica,
    ItemNotaEntrada,
    ItensCompra,
    Material,
    MovimentoEstoque,
    NotaEntrada,
    ProdutoInterno,
)
from .notas_entrada import leitura, ligacao
from .notas_entrada.armazenamento import ArquivoSemEnderecoPublico, armazenamento_das_notas
from .permissoes import atribuir_funcoes, capacidades
from .validacoes import cnpj_valido

INTERNO = {"HTTP_HOST": "interno.testserver"}


def rota(nome, *args):
    return reverse(nome, args=args, urlconf="sistema_interno.urls")

# ----------------------------------------------------------------------
# A NOTA SINTÉTICA (nenhum dado real)
# ----------------------------------------------------------------------
CNPJ_EMITENTE = "11222333000181"
CNPJ_EMITENTE_FORMATADO = "11.222.333/0001-81"
CNPJ_DESTINATARIO_FORMATADO = "11.444.777/0001-61"
NOME_EMITENTE = "FERRAGENS EXEMPLO COMERCIO LTDA"


def chave_sintetica(cnpj=CNPJ_EMITENTE, serie=1, numero=4321, codigo="12345678"):
    base = f"35" f"2611" f"{cnpj}" f"55" f"{serie:03d}" f"{numero:09d}" f"1" f"{codigo}"
    return base + str(leitura.digito_da_chave(base))


CHAVE = chave_sintetica()

#: (código, descrição, NCM, unidade, quantidade, unitário, total, complemento)
ITENS = [
    ("1001", "PARAFUSO CHIPBOARD 3,5 X 25", "73181200", "CE", "5,0000", "3,4000", "17,00", ""),
    ("2002", "LONA PVC AZUL 0,45 MM", "39219019", "M2", "10,0000", "25,0000", "250,00", ""),
    ("1001", "PARAFUSO CHIPBOARD 3,5 X 25", "73181200", "CE", "20,0000", "3,4000", "68,00", ""),
    ("3003", "COLA DE CONTATO 750 ML", "35069190", "UN", "3,0000", "45,5000", "136,50", "LOTE 77A"),
]
ITENS_PAGINA_2 = [
    ("4004", "FITA CREPE 48X50M", "48114110", "RL", "4,0000", "9,5000", "38,00", ""),
]
TOTAL = "509,50"


def _linha_item(codigo, descricao, ncm, unidade, quantidade, unitario, total):
    return (
        f"  {codigo:<8}{descricao:<44}{ncm:<10}{'000':<5}{'5102':<6}{unidade:<6}"
        f"{quantidade:>10}  {unitario:>10}  {total:>10}  {total:>10}  {'0,00':>8}  {'18,00':>6}"
    )


def _quadro_de_produtos(itens):
    linhas = [
        "DADOS DOS PRODUTOS / SERVIÇOS",
        "  CÓDIGO  DESCRIÇÃO DO PRODUTO / SERVIÇO              NCM/SH    CST  CFOP  UNID       QUANT       VALOR       VALOR    B. CÁLC.     VALOR   ALÍQ.",
        "  PRODUTO                                                                                         UNIT       TOTAL        ICMS      ICMS    ICMS",
    ]
    for codigo, descricao, ncm, unidade, quantidade, unitario, total, complemento in itens:
        linhas.append(_linha_item(codigo, descricao, ncm, unidade, quantidade, unitario, total))
        if complemento:
            linhas.append(f"          {complemento}")
        linhas.append("")
    return linhas


def paginas_do_danfe(chave=CHAVE, numero_impresso="000.004.321", serie_impressa="1", com_chave=True,
                     itens=None, itens_2=None, total=TOTAL):
    itens = ITENS if itens is None else itens
    itens_2 = ITENS_PAGINA_2 if itens_2 is None else itens_2
    chave_impressa = leitura.chave_formatada(chave) if com_chave else ""
    pagina_1 = [
        f"RECEBEMOS DE {NOME_EMITENTE} OS PRODUTOS E/OU SERVIÇOS CONSTANTES DA NOTA FISCAL ELETRÔNICA INDICADA AO",
        f"LADO. EMISSÃO: 10/11/2026 VALOR TOTAL: {total} DESTINATÁRIO: BRINQUEDOS DE TESTE LTDA - RUA DO TESTE, 1      NF-e",
        f"DATA DO RECEBIMENTO                 IDENTIFICAÇÃO E ASSINATURA DO RECEBEDOR                     Nº. {numero_impresso}",
        f"                                                                                              SÉRIE {serie_impressa}",
        "",
        "            IDENTIFICAÇÃO DO EMITENTE                         DANFE",
        "                                                       DOCUMENTO AUXILIAR",
        "  FERRAGENS EXEMPLO                                      DA NOTA FISCAL",
        "        COMERCIO LTDA                                    ELETRÔNICA                CHAVE DE ACESSO",
        f"                                                       0 - ENTRADA        1     {chave_impressa}",
        "     RUA DAS FERRAMENTAS, 100 - CENTRO                   1 - SAÍDA",
        "     01001-000 Sao Paulo - SP                          Nº. " + numero_impresso + "   Consulta de autenticidade no portal nacional da NF-e",
        "                                                       SÉRIE " + serie_impressa,
        "                                                       FOLHA 1/2",
        "NATUREZA DA OPERAÇÃO                                                       PROTOCOLO DE AUTORIZAÇÃO DE USO",
        "VENDA DE MERCADORIA",
        "",
        "INSCRIÇÃO ESTADUAL                 INSCRIÇÃO ESTADUAL DO SUBST. TRIBUT.                    CNPJ",
        f"      111111111111                                                               {CNPJ_EMITENTE_FORMATADO}",
        "",
        "DESTINATÁRIO / REMETENTE",
        "NOME / RAZÃO SOCIAL                                          CNPJ / CPF                 DATA DA EMISSÃO",
        f"BRINQUEDOS DE TESTE LTDA                                     {CNPJ_DESTINATARIO_FORMATADO}         10/11/2026",
        "",
        "ENDEREÇO                                   BAIRRO / DISTRITO           CEP          DATA DA SAÍDA",
        "RUA DO TESTE, 1                            CENTRO                      01001-001    10/11/2026",
        "",
        "CÁLCULO DO IMPOSTO",
        "BASE DE CÁLCULO DO ICMS        VALOR DO ICMS        BASE DE CÁLCULO DO ICMS S.T.     VALOR TOTAL DOS PRODUTOS",
        f"           509,50                    91,71                     0,00                          {total}",
        "",
        "VALOR DO FRETE      VALOR DO SEGURO     DESCONTO      OUTRAS DESP. ACESSÓRIAS    VALOR TOTAL DO IPI    VALOR TOTAL DA NOTA",
        f"      0,00               0,00            0,00                 0,00                    0,00               {total}",
        "",
    ] + _quadro_de_produtos(itens) + [
        "CÁLCULO DO ISSQN",
        "DADOS ADICIONAIS",
        "INFORMAÇÕES COMPLEMENTARES                                         RESERVADO AO FISCO",
        "VALOR APROXIMADO DOS TRIBUTOS R$ 91,71",
    ]
    pagina_2 = [
        "            IDENTIFICAÇÃO DO EMITENTE                         DANFE",
        f"                                                       0 - ENTRADA        1     {chave_impressa}",
        "                                                       FOLHA 2/2",
        "",
    ] + _quadro_de_produtos(itens_2)
    return [pagina_1, pagina_2]


def texto_do_danfe(**kwargs):
    return "\f".join("\n".join(pagina) for pagina in paginas_do_danfe(**kwargs))


def pdf_de_texto(paginas):
    """Um PDF de verdade, com o texto em Courier -- para o caminho do pypdf."""
    def escapar(linha):
        return linha.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode("cp1252")

    objetos, kids = [], []
    numero_fonte = 3 + 2 * len(paginas)
    for indice, linhas in enumerate(paginas):
        numero = 3 + 2 * indice
        conteudo = b"BT /F1 6 Tf 8 TL 10 1180 Td " + b" ".join(b"(" + escapar(l) + b") Tj T*" for l in linhas) + b" ET"
        objetos.append((numero, b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 900 1200] /Contents %d 0 R "
                                b"/Resources << /Font << /F1 %d 0 R >> >> >>" % (numero + 1, numero_fonte)))
        objetos.append((numero + 1, b"<< /Length %d >>\nstream\n" % len(conteudo) + conteudo + b"\nendstream"))
        kids.append(b"%d 0 R" % numero)
    objetos.append((1, b"<< /Type /Catalog /Pages 2 0 R >>"))
    objetos.append((2, b"<< /Type /Pages /Kids [" + b" ".join(kids) + b"] /Count %d >>" % len(paginas)))
    objetos.append((numero_fonte, b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>"))
    saida = BytesIO()
    saida.write(b"%PDF-1.4\n")
    posicoes = {}
    for numero, corpo in sorted(objetos):
        posicoes[numero] = saida.tell()
        saida.write(b"%d 0 obj\n" % numero + corpo + b"\nendobj\n")
    xref = saida.tell()
    total = max(posicoes) + 1
    saida.write(b"xref\n0 %d\n0000000000 65535 f \n" % total)
    for numero in range(1, total):
        saida.write(b"%010d 00000 n \n" % posicoes[numero])
    saida.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (total, xref))
    return saida.getvalue()


def _xml_numero(texto):
    return texto.replace(".", "").replace(",", ".")


def xml_da_nota(chave=CHAVE, numero=4321, serie=1, itens=None, cnpj=CNPJ_EMITENTE, total=TOTAL, prefixo=""):
    itens = (ITENS + ITENS_PAGINA_2) if itens is None else itens
    dets = []
    for indice, (codigo, descricao, ncm, unidade, quantidade, unitario, valor, complemento) in enumerate(itens, start=1):
        dets.append(
            f'<det nItem="{indice}"><prod><cProd>{codigo}</cProd><cEAN>SEM GTIN</cEAN><xProd>{descricao}</xProd>'
            f"<NCM>{ncm}</NCM><CFOP>5102</CFOP><uCom>{unidade}</uCom><qCom>{_xml_numero(quantidade)}</qCom>"
            f"<vUnCom>{_xml_numero(unitario)}000000</vUnCom><vProd>{_xml_numero(valor)}</vProd><indTot>1</indTot></prod>"
            f"<imposto><ICMS><ICMS00><orig>0</orig><CST>00</CST></ICMS00></ICMS></imposto>"
            + (f"<infAdProd>{complemento}</infAdProd>" if complemento else "")
            + "</det>"
        )
    return (
        prefixo + '<?xml version="1.0" encoding="UTF-8"?>'
        '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">'
        '<NFe xmlns="http://www.portalfiscal.inf.br/nfe">'
        f'<infNFe Id="NFe{chave}" versao="4.00">'
        f"<ide><cUF>35</cUF><natOp>VENDA DE MERCADORIA</natOp><mod>55</mod><serie>{serie}</serie><nNF>{numero}</nNF>"
        "<dhEmi>2026-11-10T09:30:00-03:00</dhEmi><tpNF>1</tpNF></ide>"
        f"<emit><CNPJ>{cnpj}</CNPJ><xNome>{NOME_EMITENTE}</xNome><IE>111111111111</IE></emit>"
        "<dest><CNPJ>11444777000161</CNPJ><xNome>BRINQUEDOS DE TESTE LTDA</xNome></dest>"
        + "".join(dets)
        + f"<total><ICMSTot><vProd>{_xml_numero(total)}</vProd><vNF>{_xml_numero(total)}</vNF></ICMSTot></total>"
        "</infNFe></NFe>"
        f"<protNFe versao=\"4.00\"><infProt><chNFe>{chave}</chNFe></infProt></protNFe>"
        "</nfeProc>"
    ).encode("utf-8")


# ======================================================================
# O LEITOR (sem banco)
# ======================================================================
class LeitorDoDanfeTests(SimpleTestCase):

    def test_os_numeros_sinteticos_sao_validos(self):
        self.assertTrue(cnpj_valido(CNPJ_EMITENTE))
        self.assertTrue(cnpj_valido(CNPJ_DESTINATARIO_FORMATADO))
        self.assertTrue(leitura.chave_valida(CHAVE))

    def test_le_cabecalho_e_itens_do_danfe(self):
        nota = leitura.conferir(leitura.ler_texto_danfe(texto_do_danfe()))

        self.assertEqual(nota.chave, CHAVE)
        self.assertEqual(nota.fornecedor_cnpj, CNPJ_EMITENTE)
        self.assertEqual(nota.fornecedor_nome, NOME_EMITENTE)
        self.assertEqual((nota.numero, nota.serie), ("4321", "1"))
        self.assertEqual(nota.emissao, date(2026, 11, 10))
        self.assertEqual(nota.valor_total, Decimal("509.50"))
        self.assertEqual(nota.valor_produtos, Decimal("509.50"))
        self.assertEqual(nota.avisos, [])

        self.assertEqual(len(nota.itens), 5, "quatro na folha 1 e um na folha 2")
        primeiro = nota.itens[0]
        self.assertEqual(primeiro.codigo, "1001")
        self.assertEqual(primeiro.descricao, "PARAFUSO CHIPBOARD 3,5 X 25")
        self.assertEqual(primeiro.unidade, "CE")
        self.assertEqual(primeiro.ncm, "73181200")
        self.assertEqual(primeiro.quantidade, Decimal("5"))
        self.assertEqual(primeiro.valor_unitario, Decimal("3.4"))
        self.assertEqual(primeiro.valor_total, Decimal("17.00"))
        # a linha de baixo, que não encosta no NCM, é o complemento do item
        self.assertEqual(nota.itens[3].descricao, "COLA DE CONTATO 750 ML")
        self.assertEqual(nota.itens[3].complemento, "LOTE 77A")
        self.assertEqual(nota.itens[4].codigo, "4004")
        self.assertEqual(nota.soma_dos_itens, Decimal("509.50"))

    def test_a_chave_tem_digito_verificador(self):
        errada = CHAVE[:-1] + str((int(CHAVE[-1]) + 1) % 10)
        self.assertFalse(leitura.chave_valida(errada))
        nota = leitura.ler_texto_danfe(texto_do_danfe(chave=errada))
        self.assertEqual(nota.chave, "")
        self.assertTrue(any("chave de acesso" in aviso for aviso in nota.avisos))

    def test_sem_chave_vale_o_numero_impresso_e_o_cnpj_do_emitente(self):
        nota = leitura.ler_texto_danfe(texto_do_danfe(com_chave=False))
        self.assertEqual(nota.chave, "")
        self.assertEqual((nota.numero, nota.serie), ("4321", "1"))
        # o primeiro CNPJ válido antes do destinatário -- e não o do destinatário
        self.assertEqual(nota.fornecedor_cnpj, CNPJ_EMITENTE)

    def test_numero_impresso_diferente_da_chave_vira_aviso_e_vale_a_chave(self):
        nota = leitura.ler_texto_danfe(texto_do_danfe(numero_impresso="000.004.329"))
        self.assertEqual(nota.numero, "4321")
        self.assertTrue(any("4329" in aviso for aviso in nota.avisos))

    def test_item_quebrado_em_linhas_no_texto_simples(self):
        """O texto sem layout põe código e descrição numa linha e os números na outra."""
        texto = "\n".join([
            "DADOS DOS PRODUTOS / SERVIÇOS",
            "CÓDIGO DESCRIÇÃO DO PRODUTO / SERVIÇO NCM/SH CST CFOP UNID QUANT VALOR",
            "1001 PARAFUSO CHIPBOARD 3,5 X 25 73181200 000 5102 CE 5,0000 3,4000 17,00 17,00 3,06 18,00",
            "3003 COLA DE CONTATO 750 ML",
            "LOTE 77A",
            "35069190 000 5102 UN 3,0000 45,5000 136,50 136,50 24,57 18,00",
            "4004 FITA CREPE 48X50M 48114110 000 5102 RL 4,0000 9,5000 38,00 38,00 6,84 18,00",
            "DADOS ADICIONAIS",
        ])
        nota = leitura.ler_texto_danfe(texto)
        self.assertEqual([i.codigo for i in nota.itens], ["1001", "3003", "4004"])
        self.assertEqual(nota.itens[1].descricao, "COLA DE CONTATO 750 ML")
        self.assertEqual(nota.itens[1].complemento, "LOTE 77A")
        self.assertEqual(nota.itens[1].valor_total, Decimal("136.50"))

    def test_outra_ordem_de_colunas_cai_na_regra_da_trinca(self):
        """Sem NCM/CST/CFOP no lugar de sempre: vale quantidade x unitário = total."""
        texto = "\n".join([
            "DADOS DO PRODUTO / SERVIÇO",
            "  COD      DESCRIÇÃO                         UN     QTD      V.UNIT     V.TOTAL",
            "  A-77     MOLA ESPIRAL 6 MM                 PC     12,0000  3,7000     44,40",
            "DADOS ADICIONAIS",
        ])
        nota = leitura.ler_texto_danfe(texto)
        self.assertEqual(len(nota.itens), 1)
        item = nota.itens[0]
        self.assertEqual((item.codigo, item.descricao, item.unidade), ("A-77", "MOLA ESPIRAL 6 MM", "PC"))
        self.assertEqual((item.quantidade, item.valor_total), (Decimal("12"), Decimal("44.40")))

    def test_conta_que_nao_fecha_vira_aviso(self):
        itens = [("1001", "PARAFUSO CHIPBOARD 3,5 X 25", "73181200", "CE", "5,0000", "3,4000", "19,00", "")]
        nota = leitura.conferir(leitura.ler_texto_danfe(texto_do_danfe(itens=itens, itens_2=[])))
        self.assertTrue(any("não dá o total" in aviso for aviso in nota.avisos))
        self.assertTrue(any("não bate com o total dos produtos" in aviso for aviso in nota.avisos))

    def test_o_xml_da_mesma_nota_da_os_mesmos_campos_e_itens(self):
        pdf = leitura.conferir(leitura.ler_texto_danfe(texto_do_danfe()))
        xml = leitura.ler("nota.xml", xml_da_nota())

        self.assertEqual(xml.formato, "xml")
        for campo in ("chave", "fornecedor_cnpj", "fornecedor_nome", "numero", "serie", "emissao",
                      "valor_total", "valor_produtos"):
            self.assertEqual(getattr(xml, campo), getattr(pdf, campo), campo)
        resumo = lambda nota: [  # noqa: E731
            (i.codigo, i.descricao, i.unidade, i.quantidade, i.valor_total, i.ncm, i.complemento)
            for i in nota.itens
        ]
        self.assertEqual(resumo(xml), resumo(pdf))
        self.assertEqual(xml.avisos, [])

    def test_o_pdf_de_verdade_passa_pelo_pypdf(self):
        nota = leitura.ler("nota.pdf", pdf_de_texto(paginas_do_danfe()))
        self.assertEqual(nota.formato, "pdf")
        self.assertEqual(nota.chave, CHAVE)
        self.assertEqual(len(nota.itens), 5)
        self.assertEqual(nota.soma_dos_itens, Decimal("509.50"))
        self.assertEqual(nota.fornecedor_nome, NOME_EMITENTE)

    def test_xml_com_doctype_ou_entidade_e_recusado(self):
        bomba = (
            b'<?xml version="1.0"?><!DOCTYPE lol [<!ENTITY a "aaaaaaaaaa">'
            b'<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]><nfeProc>&b;</nfeProc>'
        )
        with self.assertRaisesMessage(leitura.NotaRecusada, "DOCTYPE"):
            leitura.ler("nota.xml", bomba)
        externa = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x>&e;</x>'
        with self.assertRaises(leitura.NotaRecusada):
            leitura.ler("nota.xml", externa)

    def test_xml_com_bom_e_lido(self):
        nota = leitura.ler("nota.xml", b"\xef\xbb\xbf" + xml_da_nota())
        self.assertEqual(nota.numero, "4321")

    def test_xml_que_nao_e_nfe_e_recusado(self):
        with self.assertRaisesMessage(leitura.NotaRecusada, "não é de uma NF-e"):
            leitura.ler("nota.xml", b'<?xml version="1.0"?><pedido><item>1</item></pedido>')
        with self.assertRaisesMessage(leitura.NotaRecusada, "espaço de nomes"):
            leitura.ler("nota.xml", b'<?xml version="1.0"?><x xmlns="http://exemplo.test/x"><infNFe/></x>')

    def test_arquivo_que_nao_e_pdf_nem_xml_ou_com_extensao_trocada(self):
        with self.assertRaisesMessage(leitura.NotaRecusada, "não é PDF nem XML"):
            leitura.ler("nota.pdf", b"PK\x03\x04 um zip")
        with self.assertRaisesMessage(leitura.NotaRecusada, "o arquivo é XML"):
            leitura.ler("nota.pdf", xml_da_nota())
        with self.assertRaisesMessage(leitura.NotaRecusada, "vazio"):
            leitura.ler("nota.xml", b"")

    def test_pdf_sem_itens_pede_o_xml(self):
        with self.assertRaisesMessage(leitura.NotaRecusada, "envie o XML"):
            leitura.ler("nota.pdf", pdf_de_texto([["Um PDF qualquer, que nao e nota fiscal nenhuma, com texto."]]))


# ======================================================================
# A LIGAÇÃO COM OS MATERIAIS E A SOMA DOS REPETIDOS
# ======================================================================
class LigacaoTests(TestCase):

    def test_chave_de_nome_ignora_acento_caixa_e_pontuacao(self):
        self.assertEqual(
            ligacao.chave_de_nome("Parafuso  chipboard 3,5 x 25"),
            ligacao.chave_de_nome("PARAFUSO CHIPBOARD 3.5 X 25"),
        )
        self.assertEqual(ligacao.chave_de_nome("Cola de CONTATO, 750ml"), "cola de contato 750 ml")

    def test_liga_pelo_nome_sem_acento(self):
        material = Material.objects.create(nome_material="Lona PVC azul 0,45 mm", unidade="m2")
        achado, como, _ = ligacao.Catalogo().ligar("2002", "LONA PVC AZUL 0,45 MM")
        self.assertEqual((achado, como), (material, ItemNotaEntrada.Ligacao.NOME))

    def test_parecido_so_com_as_mesmas_medidas(self):
        material = Material.objects.create(nome_material="Parafuso chipboard 3,5 x 25 mm")
        catalogo = ligacao.Catalogo()
        achado, como, semelhanca = catalogo.ligar("", "PARAFUSO CHIP BOARD 3,5 X 25")
        self.assertEqual((achado, como), (material, ItemNotaEntrada.Ligacao.PARECIDO))
        self.assertGreaterEqual(semelhanca, 80)
        # 3,5 x 40 é outro parafuso, por mais parecido que o resto seja
        achado, como, _ = catalogo.ligar("", "PARAFUSO CHIPBOARD 3,5 X 40 MM")
        self.assertEqual((achado, como), (None, ItemNotaEntrada.Ligacao.NOVO))

    def test_cento_vira_unidades_e_pacote_avisa(self):
        unidade, quantidade, aviso = ligacao.unidade_do_estoque("CE", Decimal("5"))
        self.assertEqual((unidade, quantidade), ("un", 500))
        self.assertIn("cento", aviso)
        unidade, quantidade, aviso = ligacao.unidade_do_estoque("PT", Decimal("2"))
        self.assertEqual((unidade, quantidade), ("un", 2))
        self.assertIn("pacote", aviso)
        unidade, quantidade, aviso = ligacao.unidade_do_estoque("KG", Decimal("2.5"))
        self.assertEqual((unidade, quantidade), ("kg", 3))
        self.assertIn("inteiro", aviso)
        self.assertEqual(ligacao.unidade_do_estoque("M2", Decimal("10"))[:2], ("m2", 10))

    def test_itens_repetidos_viram_uma_linha_somada(self):
        nota = leitura.ler_texto_danfe(texto_do_danfe())
        linhas = ligacao.agrupar(nota.itens, ligacao.Catalogo(CNPJ_EMITENTE))

        self.assertEqual(len(linhas), 4, "5 linhas na nota, o parafuso em duas")
        parafuso = linhas[0]
        self.assertEqual(parafuso["linhas_nota"], "1, 3")
        self.assertEqual(parafuso["quantidade_nota"], Decimal("25"))
        self.assertEqual(parafuso["valor_total"], Decimal("85.00"))
        self.assertEqual((parafuso["unidade"], parafuso["quantidade"]), ("un", 2500))

    def test_repetidos_ligados_ao_mesmo_material_tambem_somam(self):
        material = Material.objects.create(nome_material="Fita crepe 48x50m", unidade="rl")
        itens = [
            leitura.ItemLido(1, "4004", "FITA CREPE 48X50M", "RL", Decimal("4"), Decimal("9.5"), Decimal("38.00")),
            leitura.ItemLido(2, "9999", "fita crepe 48 x 50 m", "RL", Decimal("1"), Decimal("9.5"), Decimal("9.50")),
        ]
        linhas = ligacao.agrupar(itens, ligacao.Catalogo())
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0]["material"], material)
        self.assertEqual((linhas[0]["quantidade"], linhas[0]["valor_total"]), (5, Decimal("47.50")))


# ======================================================================
# O LANÇAMENTO PELAS TELAS
# ======================================================================
class _BaseTelas(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._pasta = tempfile.mkdtemp(prefix="notas-teste-")
        cls._pasta_override = override_settings(NOTAS_ARQUIVOS_PRIVADOS_DIR=cls._pasta)
        cls._pasta_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._pasta_override.disable()
        shutil.rmtree(cls._pasta, ignore_errors=True)
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.usuarios = {}
        for codigo in ("financeiro", "gestao", "producao", "vendas"):
            user = User.objects.create_user(f"nota-{codigo}", f"nota-{codigo}@exemplo.test", "x", first_name=codigo.title())
            atribuir_funcoes(user, [codigo])
            cls.usuarios[codigo] = user
        cls.financeiro = cls.usuarios["financeiro"]

    def entrar(self, codigo="financeiro"):
        self.client.force_login(self.usuarios[codigo])

    def subir(self, conteudo=None, nome="nota.xml", follow=False):
        arquivo = SimpleUploadedFile(nome, conteudo if conteudo is not None else xml_da_nota())
        return self.client.post(rota("notas_entrada"), {"arquivo": arquivo}, follow=follow, **INTERNO)

    def nota_em_conferencia(self, **kwargs):
        resposta = self.subir(**kwargs)
        self.assertEqual(resposta.status_code, 302, resposta)
        return NotaEntrada.objects.latest("pk")

    def envio(self, nota, data_entrada=None, ajustes=None):
        """O POST da conferência como o navegador manda, sem mexer -- mais os ajustes."""
        dados = {"action": "lancar", "data_entrada": (data_entrada or timezone.localdate()).isoformat()}
        for item in nota.itens.all():
            prefixo = f"item-{item.pk}-"
            escolha = "fora" if item.ligacao == "fora" else (str(item.material_id) if item.material_id else "novo")
            dados.update({
                f"{prefixo}material": escolha,
                f"{prefixo}nome": item.nome_material,
                f"{prefixo}unidade": item.unidade,
                f"{prefixo}quantidade": str(item.quantidade),
                f"{prefixo}local": item.local,
            })
            for campo, valor in (ajustes or {}).get(item.ordem, {}).items():
                dados[f"{prefixo}{campo}"] = valor
        return dados

    def lancar(self, nota, follow=True, data_entrada=None, ajustes=None):
        return self.client.post(
            rota("nota_entrada", nota.pk), self.envio(nota, data_entrada, ajustes), follow=follow, **INTERNO,
        )

    @staticmethod
    def recados(resposta):
        return [str(m) for m in get_messages(resposta.wsgi_request)]


class LancamentoDaNotaTests(_BaseTelas):

    def test_financeiro_sobe_o_xml_confere_e_lanca(self):
        self.entrar("financeiro")
        resposta = self.subir()
        nota = NotaEntrada.objects.get()
        self.assertRedirects(resposta, rota("nota_entrada", nota.pk), fetch_redirect_response=False)
        self.assertEqual(nota.situacao, NotaEntrada.Situacao.CONFERENCIA)
        self.assertEqual(nota.formato, "xml")
        self.assertEqual(nota.chave_acesso, CHAVE)
        self.assertEqual(nota.itens.count(), 4, "o parafuso repetido já vem somado")

        tela = self.client.get(rota("nota_entrada", nota.pk), **INTERNO)
        self.assertEqual(tela.status_code, 200)
        html = tela.content.decode()
        self.assertIn("Fornecedor novo: será cadastrado", html)
        self.assertIn("Material novo — será criado", html)
        self.assertIn("linhas 1, 3 da nota, somadas", html)
        self.assertIn(f'value="{timezone.localdate().isoformat()}"', html, "a data de entrada vem com hoje")
        self.assertNotIn("<select", html)

        entrada = timezone.localdate() - timedelta(days=2)
        resposta = self.lancar(nota, data_entrada=entrada)
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(any("lançada" in recado for recado in self.recados(resposta)), self.recados(resposta))

        nota.refresh_from_db()
        self.assertEqual(nota.situacao, NotaEntrada.Situacao.LANCADA)
        self.assertEqual(nota.lancada_por, self.financeiro)
        self.assertEqual(nota.data_entrada, entrada)

        # o fornecedor foi criado pelo CNPJ
        fornecedor = Fornecedor.objects.get()
        self.assertEqual(fornecedor.nome, NOME_EMITENTE)
        self.assertEqual(fornecedor.cnpj, CNPJ_EMITENTE_FORMATADO)
        self.assertEqual(nota.fornecedor, fornecedor)

        # os quatro materiais foram criados, com a unidade do estoque
        self.assertEqual(Material.objects.count(), 4)
        parafuso = Material.objects.get(nome_material="PARAFUSO CHIPBOARD 3,5 X 25")
        self.assertEqual(parafuso.unidade, "un")
        self.assertEqual(Material.objects.get(nome_material="LONA PVC AZUL 0,45 MM").unidade, "m2")

        # a entrada no estoque, pelo caminho de sempre: o parafuso UMA vez, somado
        movimentos = MovimentoEstoque.objects.filter(nota_entrada=nota)
        self.assertEqual(movimentos.count(), 4)
        entrada_parafuso = movimentos.get(estoque__material=parafuso)
        self.assertEqual(entrada_parafuso.tipo, MovimentoEstoque.Tipo.ENTRADA)
        self.assertEqual(entrada_parafuso.quantidade, 2500)
        self.assertEqual(entrada_parafuso.valor_total, Decimal("85.00"), "o total exato, mesmo a R$ 0,034 cada")
        self.assertEqual(entrada_parafuso.data_compra, entrada)
        self.assertEqual(entrada_parafuso.documento, "NF-e 4321/1")
        self.assertEqual(entrada_parafuso.responsavel, self.financeiro)
        self.assertEqual(entrada_parafuso.fornecedor, fornecedor)
        local = entrada_parafuso.estoque
        self.assertEqual((local.quantidade, local.saldo_valor), (2500, Decimal("85.00")))
        self.assertEqual(local.nota_fiscal, "NF-e 4321/1")
        self.assertEqual(local.comprado_em, entrada)

        # a compra no Financeiro, no mês da entrada
        compra = nota.compra
        self.assertEqual(compra.valor, Decimal("509.50"))
        self.assertEqual(timezone.localtime(compra.criacao).date(), entrada)
        self.assertEqual(compra.itens.count(), 4)
        self.assertEqual(sum(i.subtotal for i in compra.itens.all()), Decimal("509.50"))

        # depois de lançada, a mesma tela mostra o que entrou
        tela = self.client.get(rota("nota_entrada", nota.pk), **INTERNO)
        self.assertContains(tela, "Lançada no estoque")
        self.assertContains(tela, "+2500 un")

    def test_o_pdf_e_o_xml_da_mesma_nota_dao_a_mesma_conferencia(self):
        self.entrar("financeiro")
        pdf = self.nota_em_conferencia(conteudo=pdf_de_texto(paginas_do_danfe()), nome="danfe.pdf")
        self.assertEqual(pdf.formato, "pdf")
        linhas_pdf = list(pdf.itens.values_list("codigo", "quantidade_nota", "valor_total", "quantidade", "unidade"))
        # o XML da mesma nota SUBSTITUI a leitura do PDF que ainda não foi lançada
        xml = self.nota_em_conferencia()
        self.assertFalse(NotaEntrada.objects.filter(pk=pdf.pk).exists())
        linhas_xml = list(xml.itens.values_list("codigo", "quantidade_nota", "valor_total", "quantidade", "unidade"))
        self.assertEqual(linhas_pdf, linhas_xml)

    def test_a_mesma_nota_nao_entra_duas_vezes(self):
        self.entrar("financeiro")
        self.lancar(self.nota_em_conferencia())
        self.assertEqual(MovimentoEstoque.objects.count(), 4)

        # de novo pelo XML (a chave), e pelo PDF da mesma nota
        for conteudo, nome in ((None, "nota.xml"), (pdf_de_texto(paginas_do_danfe()), "nota.pdf")):
            resposta = self.subir(conteudo=conteudo, nome=nome, follow=True)
            self.assertTrue(any("já foi lançada" in r for r in self.recados(resposta)), self.recados(resposta))
        self.assertEqual(NotaEntrada.objects.count(), 1)
        self.assertEqual(MovimentoEstoque.objects.count(), 4)

        # sem chave: CNPJ + número + série
        resposta = self.subir(conteudo=pdf_de_texto(paginas_do_danfe(com_chave=False)), nome="nota.pdf", follow=True)
        self.assertTrue(any("já foi lançada" in r for r in self.recados(resposta)))
        self.assertEqual(NotaEntrada.objects.count(), 1)

    def test_a_trava_do_banco_tambem_segura_a_nota_repetida(self):
        self.entrar("financeiro")
        primeira = self.nota_em_conferencia()
        self.lancar(primeira)
        segunda = NotaEntrada.objects.create(
            formato="xml", numero="4321", serie="1", fornecedor_cnpj=CNPJ_EMITENTE, chave_acesso=CHAVE,
        )
        resposta = self.client.post(
            rota("nota_entrada", segunda.pk), {"action": "lancar", "data_entrada": timezone.localdate().isoformat()},
            follow=True, **INTERNO,
        )
        self.assertTrue(any("já foi lançada" in r for r in self.recados(resposta)))
        segunda.refresh_from_db()
        self.assertEqual(segunda.situacao, NotaEntrada.Situacao.CONFERENCIA)

    def test_material_e_fornecedor_que_existem_sao_usados_e_o_saldo_soma(self):
        fornecedor = Fornecedor.objects.create(nome="Ferragens Exemplo", cnpj=CNPJ_EMITENTE)  # sem pontuação
        fita = Material.objects.create(nome_material="Fita crepe 48x50m", unidade="rl")
        local = EstoqueMaterial.objects.create(
            material=fita, descricao_local="Almoxarifado", quantidade=0, preco_fornecedor=Decimal("0"),
            saldo_valor=Decimal("0"),
        )
        MovimentoEstoque.registrar(local, "entrada", 10, valor_unitario=Decimal("9.00"))

        self.entrar("financeiro")
        nota = self.nota_em_conferencia()
        item_fita = nota.itens.get(codigo="4004")
        self.assertEqual((item_fita.material, item_fita.ligacao), (fita, ItemNotaEntrada.Ligacao.NOME))
        self.assertEqual(item_fita.local, "Almoxarifado")
        self.lancar(nota)

        self.assertEqual(Fornecedor.objects.count(), 1, "o CNPJ escrito sem pontuação é o mesmo fornecedor")
        local.refresh_from_db()
        self.assertEqual(local.quantidade, 14)
        self.assertEqual(EstoqueMaterial.objects.filter(material=fita).count(), 1)
        self.assertEqual(Material.objects.filter(nome_material__icontains="fita").count(), 1)
        nota.refresh_from_db()
        self.assertEqual(nota.fornecedor, fornecedor)

    def test_a_segunda_nota_do_fornecedor_ja_liga_pelo_codigo(self):
        self.entrar("financeiro")
        primeira = self.nota_em_conferencia()
        self.lancar(primeira, ajustes={2: {"nome": "Lona azul 0,45 (rolo de 50 m2)"}})
        lona = Material.objects.get(nome_material="Lona azul 0,45 (rolo de 50 m2)")

        outra = chave_sintetica(numero=4400, codigo="87654321")
        segunda = self.nota_em_conferencia(conteudo=xml_da_nota(chave=outra, numero=4400))
        item = segunda.itens.get(codigo="2002")
        self.assertEqual((item.material, item.ligacao), (lona, ItemNotaEntrada.Ligacao.CODIGO))

    def test_ajustes_da_conferencia_valem_no_lancamento(self):
        existente = Material.objects.create(nome_material="Cola branca", unidade="un")
        self.entrar("financeiro")
        nota = self.nota_em_conferencia()
        self.lancar(nota, ajustes={
            2: {"material": "fora"},                                   # lona: não entra no estoque
            3: {"material": str(existente.pk), "quantidade": "6"},     # cola: outro material, 6
            4: {"local": "Galpão B", "quantidade": "8", "unidade": "un"},  # fita: outro local e unidade
        })
        nota.refresh_from_db()
        self.assertEqual(nota.situacao, NotaEntrada.Situacao.LANCADA)
        self.assertFalse(Material.objects.filter(nome_material__icontains="lona").exists())
        self.assertEqual(EstoqueMaterial.objects.get(material=existente).quantidade, 6)
        fita = Material.objects.get(nome_material="FITA CREPE 48X50M")
        self.assertEqual(fita.unidade, "un")
        self.assertEqual(EstoqueMaterial.objects.get(material=fita).descricao_local, "Galpão B")
        # a linha fora do estoque continua na compra (foi paga)
        self.assertTrue(nota.compra.itens.filter(material__isnull=True, subtotal=Decimal("250.00")).exists())
        self.assertEqual(nota.compra.valor, Decimal("509.50"))
        self.assertEqual(MovimentoEstoque.objects.count(), 3)

    def test_duas_linhas_trocadas_para_o_mesmo_material_e_local_somam(self):
        destino = Material.objects.create(nome_material="Insumos diversos", unidade="un")
        self.entrar("financeiro")
        nota = self.nota_em_conferencia()
        self.lancar(nota, ajustes={
            3: {"material": str(destino.pk), "quantidade": "3", "local": "Almoxarifado"},
            4: {"material": str(destino.pk), "quantidade": "4", "local": "almoxarifado ", "unidade": "un"},
        })
        movimento = MovimentoEstoque.objects.get(estoque__material=destino)
        self.assertEqual(movimento.quantidade, 7)
        self.assertEqual(movimento.valor_total, Decimal("174.50"))

    def test_erro_no_lancamento_guarda_a_conferencia_e_nao_mexe_no_estoque(self):
        self.entrar("financeiro")
        nota = self.nota_em_conferencia()
        resposta = self.lancar(nota, ajustes={1: {"quantidade": "0"}, 2: {"local": "Prateleira 9"}})
        self.assertTrue(any("informe quantas unidades" in r for r in self.recados(resposta)), self.recados(resposta))
        nota.refresh_from_db()
        self.assertEqual(nota.situacao, NotaEntrada.Situacao.CONFERENCIA)
        self.assertEqual(nota.itens.get(ordem=2).local, "Prateleira 9", "o que a pessoa ajustou ficou guardado")
        self.assertFalse(MovimentoEstoque.objects.exists())
        self.assertFalse(Material.objects.exists())
        self.assertFalse(Fornecedor.objects.exists())
        self.assertFalse(ComprasMensais.objects.exists())

    def test_quantidade_ilegivel_nao_derruba_a_tela(self):
        self.entrar("financeiro")
        nota = self.nota_em_conferencia()
        resposta = self.lancar(nota, ajustes={1: {"quantidade": "dois"}})
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(any("número inteiro" in r for r in self.recados(resposta)))
        self.assertFalse(MovimentoEstoque.objects.exists())

    def test_material_com_saldo_nao_troca_de_unidade(self):
        lona = Material.objects.create(nome_material="Lona PVC azul 0,45 mm", unidade="m2")
        local = EstoqueMaterial.objects.create(material=lona, descricao_local="Galpão", quantidade=0,
                                               preco_fornecedor=Decimal("0"), saldo_valor=Decimal("0"))
        MovimentoEstoque.registrar(local, "entrada", 3, valor_unitario=Decimal("20"))
        self.entrar("financeiro")
        nota = self.nota_em_conferencia()
        resposta = self.lancar(nota, ajustes={2: {"unidade": "rl"}})
        self.assertTrue(any("converta a quantidade" in r for r in self.recados(resposta)), self.recados(resposta))
        lona.refresh_from_db()
        self.assertEqual(lona.unidade, "m2")

    def test_a_busca_da_lista_acha_pelo_material_numero_e_cnpj(self):
        self.entrar("financeiro")
        self.nota_em_conferencia()
        for termo in ("fita crepe", "4321", "11.222.333", "ferragens"):
            resposta = self.client.get(rota("notas_entrada"), {"q": termo}, **INTERNO)
            self.assertContains(resposta, "NF-e 4321/1", msg_prefix=termo)
            self.assertEqual([n.total_itens for n in resposta.context["notas"]], [4], termo)
        resposta = self.client.get(rota("notas_entrada"), {"q": "nada disso"}, **INTERNO)
        self.assertNotContains(resposta, "NF-e 4321/1")

    def test_material_sem_saldo_troca_de_unidade_na_conferencia(self):
        lona = Material.objects.create(nome_material="Lona PVC azul 0,45 mm", unidade="un")
        self.entrar("financeiro")
        nota = self.nota_em_conferencia()
        self.assertEqual(nota.itens.get(ordem=2).material, lona)
        self.lancar(nota, ajustes={2: {"unidade": "m2"}})
        lona.refresh_from_db()
        self.assertEqual(lona.unidade, "m2")
        self.assertEqual(nota.itens.get(ordem=2).unidade, "m2")

    def test_mesmo_material_em_unidades_diferentes_e_recusado(self):
        destino = Material.objects.create(nome_material="Insumos diversos", unidade="un")
        self.entrar("financeiro")
        nota = self.nota_em_conferencia()
        resposta = self.lancar(nota, ajustes={
            3: {"material": str(destino.pk), "unidade": "un"},
            4: {"material": str(destino.pk), "unidade": "cx"},
        })
        self.assertTrue(any("mesma unidade" in r for r in self.recados(resposta)), self.recados(resposta))
        self.assertFalse(MovimentoEstoque.objects.exists())

    def test_data_de_entrada_no_futuro_e_recusada(self):
        self.entrar("financeiro")
        nota = self.nota_em_conferencia()
        resposta = self.lancar(nota, data_entrada=timezone.localdate() + timedelta(days=1))
        self.assertTrue(any("depois de hoje" in r for r in self.recados(resposta)))
        self.assertFalse(MovimentoEstoque.objects.exists())

    def test_salvar_e_continuar_depois(self):
        self.entrar("financeiro")
        nota = self.nota_em_conferencia()
        dados = self.envio(nota, ajustes={1: {"local": "Gaveta 3"}})
        dados["action"] = "guardar"
        self.client.post(rota("nota_entrada", nota.pk), dados, **INTERNO)
        self.assertEqual(nota.itens.get(ordem=1).local, "Gaveta 3")
        self.assertFalse(MovimentoEstoque.objects.exists())

    def test_descartar_apaga_a_leitura_e_o_arquivo(self):
        self.entrar("financeiro")
        nota = self.nota_em_conferencia()
        caminho = armazenamento_das_notas.path(nota.arquivo.name)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(rota("nota_entrada", nota.pk), {"action": "descartar"}, **INTERNO)
        self.assertFalse(NotaEntrada.objects.exists())
        import os
        self.assertFalse(os.path.exists(caminho))

    def test_o_arquivo_fica_no_cofre_e_so_sai_pela_view(self):
        self.entrar("financeiro")
        nota = self.nota_em_conferencia()
        self.assertTrue(nota.arquivo.name.startswith("notas/"))
        self.assertLessEqual(len(nota.arquivo.name), 100)
        self.assertTrue(armazenamento_das_notas.path(nota.arquivo.name).startswith(self._pasta))
        with self.assertRaises(ArquivoSemEnderecoPublico):
            nota.arquivo.url  # noqa: B018
        resposta = self.client.get(rota("nota_entrada_arquivo", nota.pk), **INTERNO)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.content, xml_da_nota())
        self.assertIn("no-store", resposta["Cache-Control"])
        self.assertIn("attachment", resposta["Content-Disposition"])

        self.entrar("producao")  # em conferência, a Produção não vê
        self.assertEqual(self.client.get(rota("nota_entrada_arquivo", nota.pk), **INTERNO).status_code, 404)

    def test_pdf_com_script_e_recusado(self):
        self.entrar("financeiro")
        perigoso = pdf_de_texto(paginas_do_danfe()).replace(b"/Type /Catalog", b"/Type /Catalog /OpenAction << /S /JavaScript /JS (x) >>")
        resposta = self.subir(conteudo=perigoso, nome="nota.pdf", follow=True)
        self.assertTrue(any("script" in r for r in self.recados(resposta)))
        self.assertFalse(NotaEntrada.objects.exists())


class QuemLancaTests(_BaseTelas):

    def test_a_chave_da_capacidade_nas_funcoes(self):
        esperado = {
            "financeiro": (True, True), "gestao": (True, True),
            "producao": (False, True), "vendas": (False, False),
        }
        for codigo, (lanca, ve) in esperado.items():
            acesso = capacidades(self.usuarios[codigo])
            self.assertEqual((acesso["entrada_nota"], acesso["entrada_nota_ver"]), (lanca, ve), codigo)
        chefe = get_user_model().objects.create_superuser("nota-chefe", "c@exemplo.test", "x")
        self.assertTrue(capacidades(chefe)["entrada_nota"])

    def test_financeiro_e_gestao_veem_o_envio(self):
        for codigo in ("financeiro", "gestao"):
            self.entrar(codigo)
            resposta = self.client.get(rota("notas_entrada"), **INTERNO)
            self.assertEqual(resposta.status_code, 200, codigo)
            self.assertContains(resposta, 'id="formNotaArquivo"')
            self.assertNotContains(resposta, "<select")

    def test_gestao_tambem_lanca(self):
        self.entrar("gestao")
        nota = self.nota_em_conferencia()
        self.lancar(nota)
        nota.refresh_from_db()
        self.assertTrue(nota.lancada)

    def test_vendas_nao_abre_nem_lanca(self):
        self.entrar("vendas")
        self.assertEqual(self.client.get(rota("notas_entrada"), **INTERNO).status_code, 302)
        self.subir()
        self.assertFalse(NotaEntrada.objects.exists())

    def test_producao_ve_as_lancadas_sem_lancar(self):
        self.entrar("financeiro")
        lancada = self.nota_em_conferencia()
        self.lancar(lancada)
        outra = self.nota_em_conferencia(conteudo=xml_da_nota(chave=chave_sintetica(numero=9, codigo="11112222"), numero=9))

        self.entrar("producao")
        lista = self.client.get(rota("notas_entrada"), **INTERNO)
        self.assertEqual(lista.status_code, 200)
        self.assertNotContains(lista, 'id="formNotaArquivo"')
        self.assertContains(lista, "NF-e 4321/1")
        self.assertNotContains(lista, "NF-e 9/1")
        self.assertEqual(self.client.get(rota("nota_entrada", lancada.pk), **INTERNO).status_code, 200)
        self.assertEqual(self.client.get(rota("nota_entrada", outra.pk), **INTERNO).status_code, 404)
        self.client.post(rota("nota_entrada", outra.pk), self.envio(outra), **INTERNO)
        outra.refresh_from_db()
        self.assertFalse(outra.lancada)
        self.subir(conteudo=xml_da_nota(chave=chave_sintetica(numero=10, codigo="33334444"), numero=10))
        self.assertEqual(NotaEntrada.objects.count(), 2)

    def test_o_historico_do_estoque_leva_a_nota(self):
        self.entrar("financeiro")
        nota = self.nota_em_conferencia()
        self.lancar(nota)
        self.entrar("producao")
        resposta = self.client.get(rota("movimentacoes_inner"), **INTERNO)
        self.assertContains(resposta, rota("nota_entrada", nota.pk))
        self.assertContains(resposta, "NF-e 4321/1")


# ======================================================================
# OS PONTOS DO ESTOQUE QUE TRAVAVAM A ENTRADA
# ======================================================================
@override_settings(ALLOWED_HOSTS=["interno.testserver", "testserver"])
class EstoqueSemTravasTests(TestCase):

    def setUp(self):
        self.chefe = get_user_model().objects.create_superuser("estoque-chefe", "e@exemplo.test", "x")
        self.client.force_login(self.chefe)
        self.material = Material.objects.create(nome_material="Lona PVC", unidade="m2")

    def post(self, dados, url="/stock/"):
        return self.client.post(url, dados, HTTP_X_REQUESTED_WITH="XMLHttpRequest", **INTERNO)

    def test_cadastrar_de_novo_no_mesmo_local_soma_ao_saldo(self):
        primeiro = self.post({"action": "save", "material": self.material.pk, "descricao_local": "Galpão A",
                              "quantidade": "10", "preco_fornecedor": "20,00"})
        self.assertEqual(primeiro.json()["status"], "sucesso")
        segundo = self.post({"action": "save", "material": self.material.pk, "descricao_local": "galpão a ",
                             "quantidade": "5", "preco_fornecedor": "22,00", "nota_fiscal": "NF 77"})
        self.assertEqual(segundo.json()["status"], "sucesso", segundo.json())
        self.assertIn("somado", segundo.json()["msg"])
        local = EstoqueMaterial.objects.get()
        self.assertEqual(local.quantidade, 15)
        self.assertEqual(local.saldo_valor, Decimal("310.00"))
        self.assertEqual(local.nota_fiscal, "NF 77")

    def test_local_novo_sem_quantidade_nao_pede_preco(self):
        resposta = self.post({"action": "save", "material": self.material.pk, "descricao_local": "Galpão B"})
        self.assertEqual(resposta.json()["status"], "sucesso", resposta.json())
        resposta = self.post({"action": "save", "material": self.material.pk, "descricao_local": "Galpão C",
                              "quantidade": "3"})
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("valor pago", resposta.json()["msg"])

    def test_excluir_material_da_ficha_tecnica_explica_em_vez_de_500(self):
        produto = ProdutoInterno.objects.create(nome="Pula-pula 3 m")
        ItemFichaTecnica.objects.create(produto=produto, material=self.material, quantidade=Decimal("2"))
        resposta = self.post({"action": "delete_material", "id": self.material.pk}, url="/estoque/materiais/")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("ficha técnica", resposta.json()["msg"])
        self.assertTrue(Material.objects.filter(pk=self.material.pk).exists())

    def test_fornecedor_com_nome_repetido_explica(self):
        Fornecedor.objects.create(nome="Lonas do Brás")
        resposta = self.post({"action": "save_fornecedor", "nome": "lonas do brás", "ativo": "on"})
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("Já existe um fornecedor", resposta.json()["msg"])

    def test_a_entrada_atualiza_a_ultima_compra_do_local(self):
        fornecedor = Fornecedor.objects.create(nome="Lonas do Brás")
        local = EstoqueMaterial.objects.create(material=self.material, descricao_local="Galpão", quantidade=0,
                                               preco_fornecedor=Decimal("0"), saldo_valor=Decimal("0"),
                                               nota_fiscal="NF antiga", comprado_em=date(2025, 1, 2))
        MovimentoEstoque.registrar(local, "entrada", 4, valor_unitario=Decimal("10"), fornecedor=fornecedor,
                                   documento="NF 900", data_compra=date(2026, 11, 3))
        local.refresh_from_db()
        self.assertEqual((local.nota_fiscal, local.fornecedor, local.comprado_em), ("NF 900", fornecedor, date(2026, 11, 3)))

    def test_entrada_pelo_total_guarda_o_valor_exato(self):
        local = EstoqueMaterial.objects.create(material=self.material, descricao_local="Galpão", quantidade=0,
                                               preco_fornecedor=Decimal("0"), saldo_valor=Decimal("0"))
        movimento = MovimentoEstoque.registrar(local, "entrada", 500, valor_total=Decimal("17.00"))
        local.refresh_from_db()
        self.assertEqual(local.saldo_valor, Decimal("17.00"))
        self.assertEqual(movimento.valor_unitario, Decimal("0.03"))
        self.assertEqual(movimento.valor_total, Decimal("17.00"))
        self.assertFalse(ItensCompra.objects.exists())
