"""Importação de orçamento do Word: leitura, conferência, criação e permissões.

OS .docx SÃO MONTADOS AQUI MESMO, com o XML mínimo do Word dentro de um
zip. Nenhum arquivo binário entra no repositório, e cada documento diz no
próprio teste o que tem dentro -- inclusive o erro que está ali de
propósito (o total que não bate, o produto que não existe).

A IA NUNCA É CHAMADA DE VERDADE. Onde ela entra, o cliente do SDK é
trocado por um falso (`ClienteFalso`) que devolve a leitura que o teste
escreveu, e que guarda os argumentos de cada chamada para conferir modelo,
esforço, fallback e esquema.
"""

from __future__ import annotations

import base64
import io
import json
import os
import zipfile
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock
from xml.sax.saxutils import escape

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from core.models import Brinquedos, PecasReposicao

from .importacao_word import catalogo, conferencia, deterministica as det, formulario, ia, leitor, mapa
from .models import (
    AtividadeOrcamento,
    AvaliacaoBlocoOrcamento,
    Cliente,
    EnderecoCliente,
    ItemOrcamento,
    Orcamento,
    ProdutoInterno,
)
from . import views_importacao
from .permissoes import atribuir_funcoes

HOST = {"HTTP_HOST": "interno.testserver"}
URL_IMPORTAR = "/orcamentos/importar/"


# ======================================================================
# O .docx FEITO À MÃO
# ======================================================================
W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
MC = 'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"'


def corrida(texto, *, oculto=False, apagado=False):
    if apagado:
        return f'<w:del><w:r><w:delText xml:space="preserve">{escape(texto)}</w:delText></w:r></w:del>'
    propriedades = "<w:rPr><w:vanish/></w:rPr>" if oculto else ""
    pedacos = "<w:br/>".join(f'<w:t xml:space="preserve">{escape(p)}</w:t>' for p in texto.split("\n"))
    return f"<w:r>{propriedades}{pedacos}</w:r>"


def par(*corridas):
    """Parágrafo; texto solto vira corrida. "\\n" é a quebra Shift+Enter."""
    corpo = "".join(c if c.startswith("<") else corrida(c) for c in corridas)
    return f"<w:p><w:pPr><w:tabs><w:tab w:val=\"left\" w:pos=\"720\"/></w:tabs></w:pPr>{corpo}</w:p>"


def celula(conteudo, *, vao=1):
    propriedades = f'<w:tcPr><w:gridSpan w:val="{vao}"/></w:tcPr>' if vao > 1 else ""
    if not conteudo.startswith("<"):
        conteudo = par(conteudo)
    return f"<w:tc>{propriedades}{conteudo}</w:tc>"


def tabela(*linhas):
    xml = "<w:tbl>"
    for linha in linhas:
        xml += "<w:tr>"
        for item in linha:
            xml += celula(item[0], vao=item[1]) if isinstance(item, tuple) else celula(item)
        xml += "</w:tr>"
    return xml + "</w:tbl>"


def caixa_de_texto(texto):
    """Uma caixa de texto como o Word grava: DrawingML com cópia em VML."""
    interno = f"<w:txbxContent>{par(texto)}</w:txbxContent>"
    return (
        f"<w:p><w:r><mc:AlternateContent {MC}>"
        f"<mc:Choice Requires=\"wps\"><w:drawing>{interno}</w:drawing></mc:Choice>"
        f"<mc:Fallback><w:pict>{interno}</w:pict></mc:Fallback>"
        "</mc:AlternateContent></w:r></w:p>"
    )


def montar_docx(corpo, *, cabecalho="", rodape="", cabecalhos_extras=0):
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as arquivo:
        arquivo.writestr("[Content_Types].xml", (
            '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/'
            'package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
            'officedocument.wordprocessingml.document.main+xml"/></Types>'
        ))
        arquivo.writestr("word/document.xml", (
            f'<?xml version="1.0" encoding="UTF-8"?><w:document {W} {MC}><w:body>{corpo}'
            "<w:sectPr/></w:body></w:document>"
        ))
        if cabecalho:
            for numero in range(1, 2 + cabecalhos_extras):
                arquivo.writestr(f"word/header{numero}.xml",
                                 f'<?xml version="1.0" encoding="UTF-8"?><w:hdr {W}>{cabecalho}</w:hdr>')
        if rodape:
            arquivo.writestr("word/footer1.xml",
                             f'<?xml version="1.0" encoding="UTF-8"?><w:ftr {W}>{rodape}</w:ftr>')
    return memoria.getvalue()


def montar_pdf_imagem():
    """O PDF digitalizado: página sem texto nenhum (só a "foto")."""
    return montar_pdf(linhas=())


#: O que a tela NUNCA mostra a quem importa. "A chave da IA não está
#: configurada" é assunto de quem cuida do servidor (fica no log); na tela,
#: a pessoa só lia que faltava "uma tal variável que eu desconheço".
JARGAO = ("ANTHROPIC_API_KEY", "ANTHROPIC", "chave", "variável", "IA desligada", "IA indisponível")


def texto_visivel(resposta) -> str:
    """O HTML da resposta sem <script> e sem comentários: o que se lê na tela."""
    import re as _re

    html = resposta.content.decode()
    html = _re.sub(r"(?is)<script\b.*?</script>", " ", html)
    html = _re.sub(r"(?s)<!--.*?-->", " ", html)
    return html


def montar_pdf(linhas=("Orcamento 2026/041", "Cliente: Buffet Alegria Ltda", "Total: R$ 1.919,00")):
    """Um PDF de verdade, pequeno: uma página com texto em Helvetica.

    Feito à mão (cabeçalho, objetos, tabela xref e %%EOF) para o teste não
    depender de biblioteca nem de arquivo guardado. O conteúdo vai para a
    IA falsa; o que se testa aqui é o caminho, a forma do pedido e as
    recusas.
    """
    texto = "BT /F1 12 Tf 72 760 Td 16 TL " + " ".join(
        "(" + linha.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ") '" for linha in linhas
    ) + " ET"
    objetos = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(texto)} >>\nstream\n{texto}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    saida = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    posicoes = []
    for numero, objeto in enumerate(objetos, start=1):
        posicoes.append(len(saida))
        saida += f"{numero} 0 obj\n{objeto}\nendobj\n".encode("latin-1")
    inicio_xref = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for posicao in posicoes:
        saida += f"{posicao:010d} 00000 n \n".encode()
    saida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n%%EOF\n".encode()
    return saida


CABECALHO_DA_EMPRESA = par("Lazer & Sport Brinquedos — CNPJ 54.486.908/0001-86 — (11) 96056-3135")
RODAPE_DA_EMPRESA = par("contato@lazersport.com · www.lazersport.com.br")


def _data_br(dias):
    return (timezone.localdate() + timedelta(days=dias)).strftime("%d/%m/%Y")


# --------------------------------------------- os cinco documentos de exemplo
def docx_com_tabela():
    """O caso comum: dados do cliente em parágrafos e itens numa tabela."""
    return montar_docx(
        par("ORÇAMENTO Nº 2026/041")
        + par(f"Data: {_data_br(-2)}")
        + par("Cliente: Buffet Alegria Ltda\nCNPJ: 11.222.333/0001-81")
        + par("Contato: Marina Souza")
        + par("Telefone: (11) 98765-4321 · E-mail: Contato@BuffetAlegria.com.br")
        + tabela(
            ["Descrição", "Qtd", "Valor unitário", "Total"],
            ["Cama elástica 3m com rede", "2", "R$ 280,00", "R$ 560,00"],
            ["Pula pula", "1", "R$ 1.234", "R$ 1.234,00"],
            ["Mola de reposição", "10 un", "12,50", "125,00"],
            [("Total", 3), "R$ 1.919,00"],
        )
        + par("Frete: grátis")
        + par("Validade da proposta: 15 dias")
        + par("Forma de pagamento: PIX")
        + par("Forma de envio: entrega Lazer & Sport")
        + par("Prazo de entrega: 20 dias úteis"),
        cabecalho=CABECALHO_DA_EMPRESA, rodape=RODAPE_DA_EMPRESA, cabecalhos_extras=2,
    )


def docx_com_paragrafos():
    """Sem tabela: os itens escritos em linhas corridas."""
    return montar_docx(
        par("Proposta para: Escola Pequeno Príncipe")
        + par("A/C: Sr. João Lima")
        + par("E-mail: joao@pequenoprincipe.com.br")
        + par("Itens:")
        + par("- 2x Cama elástica 3 m — R$ 280,00 cada — total R$ 560,00")
        + par("- 1x Piscina de bolinhas ........ R$ 450,00")
        + par("Total: R$ 1.010,00")
        + par(f"Validade: até {_data_br(20)}")
        + par("Pagamento: 50% na entrada e 50% na entrega"),
    )


def docx_com_frete_e_desconto():
    """Subtotal, frete e desconto na mesma linha, e o total depois."""
    return montar_docx(
        par("Cliente: Marina Souza")
        + par("CPF: 529.982.247-25")
        + par("WhatsApp: (11) 97777-6655")
        + tabela(
            ["Item", "Descrição", "Qtd.", "Preço unit.", "Total"],
            ["1", "Air Game Kids", "1", "R$ 1.200,00", "R$ 1.200,00"],
        )
        + par("Subtotal R$ 1.200,00 | Frete R$ 150,00 | Desconto R$ 100,00")
        + par("Valor total: R$ 1.250,00")
        + par(f"Validade: {_data_br(10)}")
        + par("Condições de pagamento: cartão de crédito em até 3x"),
    )


def docx_com_total_errado():
    """O total do Word não é a soma das linhas -- de propósito."""
    return montar_docx(
        par("Cliente: Buffet Alegria Ltda")
        + par("E-mail: contato@buffetalegria.com.br")
        + tabela(
            ["Produto", "Quantidade", "Unitário", "Total"],
            ["Cama elástica 3 m", "2", "R$ 280,00", "R$ 560,00"],
            ["Pula-pula", "1", "R$ 1.234,00", "R$ 1.234,00"],
        )
        + par("Total geral: R$ 1.850,00")
        + par("Validade: 10 dias")
        + par("Pagamento: Pix"),
    )


def docx_com_produto_inexistente():
    """Um item que o catálogo não tem."""
    return montar_docx(
        par("Cliente: Condomínio Jardim das Flores")
        + par("E-mail: sindico@jardimdasflores.com.br")
        + tabela(
            ["Descrição", "Qtd", "Valor unitário", "Total"],
            ["Tobogã gigante inflável 8 m", "1", "R$ 3.500,00", "R$ 3.500,00"],
        )
        + par("Total: R$ 3.500,00"),
    )


def docx_com_valor_negociado():
    """A soma das linhas dá R$ 10.200,00; a venda fechou em R$ 9.800,00."""
    return montar_docx(
        par("Cliente: Buffet Alegria Ltda")
        + par("E-mail: contato@buffetalegria.com.br")
        + tabela(
            ["Descrição", "Qtd", "Valor unitário", "Total"],
            ["Brinquedão Modelo 3", "1", "R$ 9.000,00", "R$ 9.000,00"],
            ["Air Game Kids", "1", "R$ 1.200,00", "R$ 1.200,00"],
        )
        + par("Valor total negociado: R$ 9.800,00")
        + par("Validade: 10 dias")
        + par("Pagamento: Pix")
        + par("Frete: grátis"),
    )


def criar_catalogo():
    brinquedos = {
        nome: Brinquedos.objects.create(
            nome_brinquedo=nome, descricao=f"{nome} do catálogo", valor_brinquedo=valor,
            avaliacao=Decimal("5.00"), voltz="110",
        )
        for nome, valor in (
            ("Cama elástica 3 m", Decimal("280.00")),
            ("Cama elástica 4 m", Decimal("350.00")),
            ("Pula-pula", Decimal("1234.00")),
            ("Piscina de bolinhas", Decimal("450.00")),
            ("Air Game Kids", Decimal("1200.00")),
            ("Brinquedão Modelo 3", Decimal("9000.00")),
            ("Brinquedão Modelo 5", Decimal("12000.00")),
        )
    }
    peca = PecasReposicao.objects.create(
        nome="Mola de reposição", descricao_peca="Mola galvanizada", preco_venda=Decimal("12.50"),
    )
    produto = ProdutoInterno.objects.create(nome="Máquina de algodão doce", preco_venda=Decimal("2500.00"))
    return brinquedos, peca, produto


def linhas_de(conteudo):
    return leitor.ler_docx(conteudo, "teste.docx")


def proposta_de(conteudo, *, dados_ia=None, escolhas=None):
    leitura = {"arquivo": "teste.docx", "linhas": linhas_de(conteudo),
               "ia": {"usada": dados_ia is not None, "modelo": "claude-opus-5-5", "dados": dados_ia},
               "escolhas": escolhas or {}}
    return conferencia.montar_proposta(leitura)


def alertas_por_id(proposta):
    return {alerta["id"]: alerta for alerta in proposta["alertas"]}


# ======================================================================
# 1. LEITURA DO .docx
# ======================================================================
class LeitorDocxTests(SimpleTestCase):

    def test_paragrafos_e_tabelas_saem_na_ordem_com_id(self):
        linhas = linhas_de(docx_com_tabela())
        ids = [linha["id"] for linha in linhas]

        self.assertEqual(ids[0], "CAB-P1")
        self.assertLess(ids.index("P6"), ids.index("T1L1C1"))
        self.assertLess(ids.index("T1L5C4"), ids.index("P7"))
        self.assertEqual(ids[-1], "ROD-P1")
        textos = {linha["id"]: linha["texto"] for linha in linhas}
        self.assertEqual(textos["T1L2C1"], "Cama elástica 3m com rede")
        self.assertEqual(textos["T1L3C3"], "R$ 1.234")

    def test_quebra_de_linha_dentro_do_paragrafo_vira_duas_linhas(self):
        textos = {linha["id"]: linha["texto"] for linha in linhas_de(docx_com_tabela())}
        self.assertEqual(textos["P3"], "Cliente: Buffet Alegria Ltda")
        self.assertEqual(textos["P4"], "CNPJ: 11.222.333/0001-81")

    def test_celula_mesclada_ocupa_a_coluna_onde_comeca(self):
        """"Total" ocupa 3 colunas: o valor ao lado é a coluna 4, a do total."""
        textos = {linha["id"]: linha["texto"] for linha in linhas_de(docx_com_tabela())}
        self.assertEqual(textos["T1L5C1"], "Total")
        self.assertEqual(textos["T1L5C4"], "R$ 1.919,00")

    def test_cabecalhos_iguais_entram_uma_vez_so(self):
        linhas = linhas_de(docx_com_tabela())
        self.assertEqual([l["id"] for l in linhas if l["parte"] == "cabecalho"], ["CAB-P1"])

    def test_texto_oculto_e_texto_apagado_nao_entram(self):
        conteudo = montar_docx(
            par("Preço: ", corrida("R$ 999,00", oculto=True), corrida("R$ 100,00", apagado=True), "R$ 80,00")
        )
        self.assertEqual([l["texto"] for l in linhas_de(conteudo)], ["Preço: R$ 80,00"])

    def test_caixa_de_texto_entra_uma_vez_depois_do_paragrafo(self):
        conteudo = montar_docx(par("Antes") + caixa_de_texto("Frete: R$ 50,00") + par("Depois"))
        linhas = linhas_de(conteudo)
        self.assertEqual(
            [(l["id"], l["texto"]) for l in linhas],
            [("P1", "Antes"), ("CX-P1", "Frete: R$ 50,00"), ("P2", "Depois")],
        )

    def test_tabela_dentro_de_celula_vira_tabela_propria(self):
        interna = tabela(["Descrição", "Valor"], ["Pula-pula", "R$ 300,00"])
        conteudo = montar_docx(f"<w:tbl><w:tr>{celula('Diagramação')}<w:tc>{interna}</w:tc></w:tr></w:tbl>")
        ids = [l["id"] for l in linhas_de(conteudo)]
        self.assertIn("T1L1C1", ids)
        self.assertIn("T2L2C2", ids)

    def test_texto_numerado_mostra_a_linha_da_tabela_numa_linha_so(self):
        texto = leitor.texto_numerado(linhas_de(docx_com_tabela()))
        self.assertIn(
            "[T1L2C1] Cama elástica 3m com rede | [T1L2C2] 2 | [T1L2C3] R$ 280,00 | [T1L2C4] R$ 560,00",
            texto,
        )
        self.assertIn("=== CABEÇALHO DO DOCUMENTO ===", texto)
        self.assertIn("=== RODAPÉ DO DOCUMENTO ===", texto)

    def test_doc_antigo_e_pdf_pedem_para_salvar_como_docx(self):
        with self.assertRaisesMessage(leitor.ArquivoRecusado, "Salvar como"):
            leitor.ler_docx(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"0" * 100, "velho.doc")
        with self.assertRaisesMessage(leitor.ArquivoRecusado, "Salvar como"):
            leitor.ler_docx(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"0" * 100, "renomeado.docx")
        with self.assertRaisesMessage(leitor.ArquivoRecusado, "não é Word (.docx) nem PDF"):
            leitor.ler_docx(b"texto qualquer", "orcamento.txt")

    def test_extensao_e_conteudo_tem_de_concordar(self):
        self.assertEqual(leitor.conferir_arquivo("a.docx", docx_com_tabela()), "docx")
        self.assertEqual(leitor.conferir_arquivo("a.PDF", montar_pdf()), "pdf")
        with self.assertRaisesMessage(leitor.ArquivoRecusado, "tem nome de PDF, mas o conteúdo não é"):
            leitor.conferir_arquivo("falso.pdf", b"PK\x03\x04 nao sou pdf")
        with self.assertRaisesMessage(leitor.ArquivoRecusado, "tem nome de .docx, mas é um PDF"):
            leitor.conferir_arquivo("trocado.docx", montar_pdf())
        with self.assertRaisesMessage(leitor.ArquivoRecusado, "não é um documento do Word (.docx) de verdade"):
            leitor.conferir_arquivo("falso.docx", b"<html>orcamento</html>")
        with self.assertRaisesMessage(leitor.ArquivoRecusado, "cortado"):
            leitor.conferir_pdf("cortado.pdf", montar_pdf()[:60])

    def test_a_transcricao_do_pdf_so_aceita_id_valido_e_uma_vez(self):
        linhas = leitor.linhas_transcritas([
            {"id": "P1", "texto": "Cliente: Marina"},
            {"id": "[T1L2C3]", "texto": "R$ 280,00"},
            {"id": "P1", "texto": "repetido"},
            {"id": "linha 7", "texto": "id inventado"},
            {"id": "CAB-P1", "texto": "Lazer & Sport"},
            {"id": "P2", "texto": "   "},
        ])
        self.assertEqual([l["id"] for l in linhas], ["P1", "T1L2C3", "CAB-P1"])
        self.assertEqual((linhas[1]["tabela"], linhas[1]["linha"], linhas[1]["coluna"]), ("T1", 2, 3))
        self.assertEqual(linhas[2]["parte"], "cabecalho")

    def test_zip_sem_documento_e_xml_com_entidade_sao_recusados(self):
        memoria = io.BytesIO()
        with zipfile.ZipFile(memoria, "w") as arquivo:
            arquivo.writestr("xl/workbook.xml", "<x/>")
        with self.assertRaisesMessage(leitor.ArquivoRecusado, "não tem o conteúdo"):
            leitor.ler_docx(memoria.getvalue(), "planilha-renomeada.docx")

        memoria = io.BytesIO()
        with zipfile.ZipFile(memoria, "w") as arquivo:
            arquivo.writestr("word/document.xml", '<!DOCTYPE x [<!ENTITY a "aaaa">]><x>&a;</x>')
        with self.assertRaisesMessage(leitor.ArquivoRecusado, "estrutura que o Word não produz"):
            leitor.ler_docx(memoria.getvalue(), "forjado.docx")

    def test_arquivo_grande_demais_e_recusado_antes_de_abrir(self):
        with self.assertRaisesMessage(leitor.ArquivoRecusado, "10 MB"):
            leitor.conferir_arquivo("grande.docx", b"PK" + b"0" * (leitor.TAMANHO_MAXIMO + 1))


# ======================================================================
# 2. DINHEIRO, QUANTIDADE E DOCUMENTOS
# ======================================================================
class DinheiroBrasileiroTests(SimpleTestCase):

    def test_os_formatos_de_reais_viram_decimal_exato(self):
        casos = {
            "R$ 1.234,56": Decimal("1234.56"),
            "1234,56": Decimal("1234.56"),
            "R$ 1.234": Decimal("1234.00"),
            "R$1.234.567,89": Decimal("1234567.89"),
            "80": Decimal("80.00"),
            "0,5": Decimal("0.50"),
            "1,234.56": Decimal("1234.56"),
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                valor = det.ler_dinheiro(texto)
                self.assertIsInstance(valor, Decimal)
                self.assertEqual(valor, esperado)

    def test_o_milhar_com_ponto_nao_vira_um_real_e_vinte_e_tres(self):
        """O erro clássico: Decimal("1.234") gravaria R$ 1,23."""
        self.assertEqual(det.ler_dinheiro("1.234"), Decimal("1234.00"))

    def test_por_extenso_e_ambiguo_nao_viram_numero(self):
        for texto in ("mil e duzentos", "mil e duzentos reais", "1,234", "12,345", "1.234.5", ""):
            with self.subTest(texto=texto):
                self.assertIsNone(det.ler_dinheiro(texto))
        self.assertEqual(det.valores_em_reais("mil e duzentos reais"), [])

    def test_valor_abreviado_e_recusado_com_motivo(self):
        achados = det.valores_em_reais("Investimento de R$ 1,2 mil")
        self.assertEqual(len(achados), 1)
        self.assertIsNone(achados[0]["valor"])
        self.assertIn("abreviado", achados[0]["recusa"])

    def test_no_texto_so_conta_o_que_tem_cara_de_dinheiro(self):
        achados = det.valores_em_reais("Cama 3 m, 10% de sinal, 05/11/2026, R$ 280 e 125,00")
        self.assertEqual([a["valor"] for a in achados], [Decimal("280.00"), Decimal("125.00")])

    def test_o_que_se_digita_no_campo_de_reais_vale_o_mesmo_no_servidor(self):
        # O campo `moeda-valor` deixa passar o que a pessoa digita: "18000",
        # "18.000" (com o ponto do milhar), "1234,5", "R$ 1.234,56" colado.
        # O formulário normal (decimal_br) e a conferência (valor_do_campo)
        # leem tudo igual -- e igual ao Painel.valorNumerico do navegador.
        from .utils import decimal_br

        casos = {
            "18000": "18000.00", "18.000": "18000.00", "18.000,00": "18000.00", "1234,5": "1234.50",
            "R$ 1.234,56": "1234.56", "1.234.567,89": "1234567.89", "18.5": "18.50", "2800,00": "2800.00",
            "450.00": "450.00",
        }
        for digitado, certo in casos.items():
            with self.subTest(digitado=digitado):
                self.assertEqual(decimal_br(digitado, "Valor"), Decimal(certo))
                self.assertEqual(det.valor_do_campo(digitado), Decimal(certo))
        # Começando em zero não há milhar: "0.125" não vira cento e vinte e cinco.
        self.assertEqual(decimal_br("0.125", "Valor"), Decimal("0.12"))

    def test_quantidade_e_inteira_ou_recusada(self):
        self.assertEqual(det.ler_quantidade("2")[0], 2)
        self.assertEqual(det.ler_quantidade("02 un")[:2], (2, "un"))
        self.assertEqual(det.ler_quantidade("1.000 peças")[0], 1000)
        quantidade, _, motivo = det.ler_quantidade("1,5 m²")
        self.assertIsNone(quantidade)
        self.assertIn("fracionária", motivo)
        self.assertIsNone(det.ler_quantidade("0")[0])
        self.assertIsNone(det.ler_quantidade("2 x 3")[0])

    def test_documento_e_validado_pelos_digitos(self):
        achados = det.documentos("CPF 529.982.247-25 e CNPJ 11.222.333/0001-82")
        self.assertEqual([(a["tipo"], a["valido"]) for a in achados], [("CPF", True), ("CNPJ", False)])
        # Onze dígitos soltos é celular -- só vira CPF ao lado do rótulo.
        self.assertEqual(det.documentos("Ligue 11987654321"), [])
        self.assertEqual(det.documentos("CPF: 52998224725")[0]["chave"], "52998224725")

    def test_telefone_sai_no_formato_do_painel(self):
        self.assertEqual(det.formatar_telefone("+55 11 98765-4321"), "(11) 98765-4321")
        self.assertEqual(det.formatar_telefone("1133334444"), "(11) 3333-4444")
        self.assertEqual(det.formatar_documento("52998224725"), "529.982.247-25")


# ======================================================================
# 3. LEITURA POR REGRA (sem IA)
# ======================================================================
@override_settings(EMPRESA_CNPJ="54.486.908/0001-86")
class LeituraPorRegraTests(SimpleTestCase):

    def ler(self, conteudo):
        return det.ler(linhas_de(conteudo), hoje=timezone.localdate(),
                       empresa=conferencia.identidade_da_empresa())

    def test_tabela_de_itens_pelo_cabecalho(self):
        lido = self.ler(docx_com_tabela())
        itens = [
            (i["descricao"]["valor"], i["quantidade"]["valor"], i["valor_unitario"]["valor"], i["total_linha"]["valor"])
            for i in lido["itens"]
        ]
        self.assertEqual(itens, [
            ("Cama elástica 3m com rede", 2, Decimal("280.00"), Decimal("560.00")),
            ("Pula pula", 1, Decimal("1234.00"), Decimal("1234.00")),
            ("Mola de reposição", 10, Decimal("12.50"), Decimal("125.00")),
        ])
        # A linha "Total" fecha a tabela: é resumo, não item.
        self.assertEqual(lido["campos"]["total"]["valor"], Decimal("1919.00"))
        self.assertEqual(lido["campos"]["total"]["fonte"]["id"], "T1L5C4")

    def test_o_cnpj_e_o_telefone_da_empresa_nao_viram_do_cliente(self):
        campos = self.ler(docx_com_tabela())["campos"]
        self.assertEqual(campos["documento"]["valor"], "11222333000181")
        self.assertEqual(campos["telefone"]["valor"], "11987654321")
        self.assertEqual(campos["email"]["valor"], "contato@buffetalegria.com.br")

    def test_frete_gratis_e_validade_em_dias(self):
        campos = self.ler(docx_com_tabela())["campos"]
        self.assertEqual(campos["frete"]["valor"], Decimal("0.00"))
        self.assertEqual(campos["validade"]["valor"], timezone.localdate() - timedelta(days=2) + timedelta(days=15))
        self.assertIn("data do documento", campos["validade"]["motivo"])

    def test_subtotal_frete_e_desconto_na_mesma_linha(self):
        campos = self.ler(docx_com_frete_e_desconto())["campos"]
        self.assertEqual(campos["subtotal"]["valor"], Decimal("1200.00"))
        self.assertEqual(campos["frete"]["valor"], Decimal("150.00"))
        self.assertEqual(campos["desconto"]["valor"], Decimal("100.00"))
        self.assertEqual(campos["total"]["valor"], Decimal("1250.00"))
        self.assertTrue(campos["documento"]["valido"])

    def test_itens_em_paragrafo(self):
        itens = self.ler(docx_com_paragrafos())["itens"]
        self.assertEqual(len(itens), 2)
        self.assertEqual(itens[0]["descricao"]["valor"], "Cama elástica 3 m")
        self.assertEqual(itens[0]["quantidade"]["valor"], 2)
        self.assertEqual(itens[0]["valor_unitario"]["valor"], Decimal("280.00"))
        self.assertEqual(itens[0]["total_linha"]["valor"], Decimal("560.00"))
        # Um valor só, de UMA unidade: o valor da linha é também o
        # unitário (a conta do total do documento confere logo adiante).
        self.assertEqual(itens[1]["total_linha"]["valor"], Decimal("450.00"))
        self.assertEqual(itens[1]["valor_unitario"]["valor"], Decimal("450.00"))
        self.assertEqual(itens[1]["quantidade"]["valor"], 1)

    def test_frete_no_meio_da_frase_nao_e_o_frete(self):
        campos = self.ler(montar_docx(par("Cama elástica com frete incluso R$ 280,00")))["campos"]
        self.assertNotIn("frete", campos)

    def test_desconto_em_porcentagem_sem_valor(self):
        campos = self.ler(montar_docx(par("Desconto: 10%")))["campos"]
        self.assertNotIn("desconto", campos)
        self.assertEqual(campos["desconto_percentual"]["valor"], Decimal("10"))


# ======================================================================
# 4. CATÁLOGO E CLIENTE
# ======================================================================
class CasamentoTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.brinquedos, cls.peca, cls.produto = criar_catalogo()
        cls.catalogo = catalogo.carregar_catalogo()

    def test_nome_exato_sem_acento_e_sem_caixa(self):
        resultado = catalogo.casar_item("PULA PULA", self.catalogo)
        self.assertEqual(resultado["confianca"], "alta")
        self.assertEqual(resultado["escolhido"], f"b:{self.brinquedos['Pula-pula'].pk}")

    def test_o_numero_do_modelo_decide(self):
        """Modelo 3 e Modelo 5 se parecem em tudo, menos no que importa."""
        resultado = catalogo.casar_item("Brinquedão modelo 3 (5 x 3 m)", self.catalogo)
        self.assertEqual(resultado["escolhido"], f"b:{self.brinquedos['Brinquedão Modelo 3'].pk}")
        pontos_5, motivo_5 = catalogo.pontuar("Brinquedão modelo 3", "Brinquedão Modelo 5")
        self.assertLess(pontos_5, catalogo.LIMITE_MEDIO)
        self.assertIn("outro", motivo_5)

    def test_a_medida_decide(self):
        resultado = catalogo.casar_item("Cama elástica 4,0 m", self.catalogo)
        self.assertEqual(resultado["escolhido"], f"b:{self.brinquedos['Cama elástica 4 m'].pk}")
        self.assertEqual(resultado["confianca"], "alta")

    def test_parecido_fica_como_sugestao_a_confirmar(self):
        resultado = catalogo.casar_item("Cama elastica 3m com rede de proteção", self.catalogo)
        self.assertEqual(resultado["confianca"], "media")
        self.assertEqual(resultado["escolhido"], f"b:{self.brinquedos['Cama elástica 3 m'].pk}")

    def test_o_que_nao_existe_fica_sem_vinculo(self):
        resultado = catalogo.casar_item("Tobogã gigante inflável 8 m", self.catalogo)
        self.assertEqual(resultado["confianca"], "baixa")

    def test_peca_e_produto_de_producao_tambem_casam(self):
        self.assertEqual(catalogo.casar_item("Mola de reposição", self.catalogo)["escolhido"], f"r:{self.peca.pk}")
        self.assertEqual(
            catalogo.casar_item("Máquina de algodão doce", self.catalogo)["escolhido"], f"p:{self.produto.pk}",
        )

    def test_cliente_por_documento_email_telefone_e_nome(self):
        pelo_cpf = Cliente.objects.create(nome_cliente="Marina Souza", documento="529.982.247-25",
                                          telefone="(11) 90000-1111")
        pelo_email = Cliente.objects.create(nome_cliente="Buffet Alegria", email="contato@buffetalegria.com.br")
        pelo_fone = Cliente.objects.create(nome_cliente="Carlos", telefone="(11) 97777-6655")
        Cliente.objects.create(nome_cliente="Escola Pequeno Príncipe")

        self.assertEqual(catalogo.casar_cliente(documento="52998224725")["cliente"], pelo_cpf)
        self.assertEqual(catalogo.casar_cliente(email="CONTATO@buffetalegria.com.br")["cliente"], pelo_email)
        self.assertEqual(catalogo.casar_cliente(telefone="+55 11 97777-6655")["cliente"], pelo_fone)
        por_nome = catalogo.casar_cliente(nome="escola pequeno principe")
        self.assertEqual(por_nome["confianca"], "media")
        self.assertIsNone(catalogo.casar_cliente(nome="Ninguém Conhecido")["cliente"])

    def test_documento_e_email_de_clientes_diferentes_viram_alerta(self):
        Cliente.objects.create(nome_cliente="Marina Souza", documento="529.982.247-25")
        Cliente.objects.create(nome_cliente="Outra Pessoa", email="marina@exemplo.com")
        resultado = catalogo.casar_cliente(documento="529.982.247-25", email="marina@exemplo.com")
        self.assertEqual(resultado["cliente"].nome_cliente, "Marina Souza")
        self.assertTrue(resultado["alertas"])


# ======================================================================
# 5. A CONFERÊNCIA
# ======================================================================
def campo_ia(texto=None, fonte_id=None, trecho=""):
    if texto is None:
        return {"texto": None, "fonte": None}
    return {"texto": texto, "fonte": {"id": fonte_id, "trecho": trecho or texto}}


def leitura_ia_vazia():
    nomes_cliente = ("nome", "estabelecimento", "documento", "contato", "telefone", "email", "endereco",
                     "cep", "logradouro", "numero", "complemento", "bairro", "cidade", "uf")
    return {
        "cliente": {nome: campo_ia() for nome in nomes_cliente},
        "itens": [],
        **{nome: campo_ia() for nome in (
            "subtotal", "frete", "desconto", "total_geral", "valor_negociado", "validade", "forma_pagamento",
            "prazo_entrega", "forma_envio", "observacoes", "data_documento",
        )},
    }


def item_ia(descricao, quantidade, unitario, total, linha):
    return {
        "descricao": campo_ia(descricao, f"{linha}C1"),
        "quantidade": campo_ia(quantidade, f"{linha}C2"),
        "valor_unitario": campo_ia(unitario, f"{linha}C3"),
        "total_linha": campo_ia(total, f"{linha}C4"),
    }


@override_settings(EMPRESA_CNPJ="54.486.908/0001-86")
class ConferenciaTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.brinquedos, cls.peca, cls.produto = criar_catalogo()

    def test_total_errado_vira_alerta_vermelho(self):
        proposta = proposta_de(docx_com_total_errado())
        alerta = alertas_por_id(proposta)["soma_total"]
        self.assertEqual(alerta["nivel"], "vermelho")
        self.assertIn("1.794,00", alerta["detalhe"])
        self.assertIn("1.850,00", alerta["detalhe"])

    def test_quantidade_vezes_unitario_que_nao_da_o_total_da_linha(self):
        conteudo = montar_docx(tabela(
            ["Descrição", "Qtd", "Valor unitário", "Total"],
            ["Pula-pula", "2", "R$ 1.234,00", "R$ 2.400,00"],
        ))
        alerta = alertas_por_id(proposta_de(conteudo))["linha:i1"]
        self.assertEqual(alerta["nivel"], "vermelho")
        self.assertIn("2.468,00", alerta["detalhe"])

    def test_documento_que_bate_nao_tem_alerta_de_conta(self):
        proposta = proposta_de(docx_com_frete_e_desconto())
        ids = alertas_por_id(proposta)
        self.assertNotIn("soma_total", ids)
        self.assertNotIn("soma_subtotal", ids)
        self.assertEqual(proposta["contas"]["total"], "1.250,00")

    def test_produto_que_nao_existe_fica_sem_vinculo_e_avisado(self):
        proposta = proposta_de(docx_com_produto_inexistente())
        self.assertIsNone(proposta["itens"][0]["produto"]["escolhido"])
        self.assertIn("produto:i1", alertas_por_id(proposta))

    def test_nome_do_catalogo_com_o_texto_do_word_ao_lado(self):
        item = proposta_de(docx_com_tabela())["itens"][1]
        self.assertEqual(item["descricao"]["valor"], "Pula-pula")
        self.assertEqual(item["original"], "Pula pula")
        self.assertTrue(item["descricao"]["normalizado"])

    def test_valor_da_ia_que_nao_esta_na_fonte_nao_entra(self):
        dados = leitura_ia_vazia()
        dados["itens"] = [
            item_ia("Cama elástica 3m com rede", "2", "R$ 290,00", "R$ 560,00", "T1L2"),
        ]
        dados["frete"] = campo_ia("R$ 75,00", "P9")
        proposta = proposta_de(docx_com_tabela(), dados_ia=dados)
        item = proposta["itens"][0]
        # O unitário da tabela (280) entra; o 290 da IA não está em T1L2C3.
        self.assertEqual(item["valor_unitario"]["valor"], "280,00")
        self.assertEqual(item["valor_unitario"]["origem"], "tabelas")
        descartes = [a for a in proposta["alertas"] if a["tipo"] == "sem_fonte"]
        self.assertTrue(any("290,00" in a["detalhe"] for a in descartes))
        self.assertTrue(any("75,00" in a["detalhe"] for a in descartes))
        self.assertEqual(proposta["valores"]["frete"]["valor"], "0,00")

    def test_item_inventado_pela_ia_nao_entra(self):
        dados = leitura_ia_vazia()
        dados["itens"] = [item_ia("Castelo inflável", "1", "R$ 900,00", "R$ 900,00", "T1L9")]
        proposta = proposta_de(docx_com_produto_inexistente(), dados_ia=dados)
        self.assertEqual([i["descricao"]["original"] for i in proposta["itens"]], ["Tobogã gigante inflável 8 m"])
        self.assertIn("item_descartado:1", alertas_por_id(proposta))

    def test_leituras_que_concordam_tem_confianca_alta(self):
        dados = leitura_ia_vazia()
        dados["itens"] = [item_ia("Air Game Kids", "1", "R$ 1.200,00", "R$ 1.200,00", "T1L2")]
        dados["itens"][0]["descricao"]["fonte"]["id"] = "T1L2C2"
        dados["itens"][0]["quantidade"]["fonte"]["id"] = "T1L2C3"
        dados["itens"][0]["valor_unitario"]["fonte"]["id"] = "T1L2C4"
        dados["itens"][0]["total_linha"]["fonte"]["id"] = "T1L2C5"
        dados["total_geral"] = campo_ia("R$ 1.250,00", "P5")
        proposta = proposta_de(docx_com_frete_e_desconto(), dados_ia=dados)
        self.assertEqual(proposta["itens"][0]["valor_unitario"]["confianca"], "alta")
        self.assertEqual(proposta["itens"][0]["valor_unitario"]["origem"], "ambas")
        self.assertEqual(proposta["valores"]["total"]["origem"], "ambas")

    def test_tabelas_e_ia_discordando_e_vermelho_e_o_campo_fica_vazio(self):
        conteudo = montar_docx(
            tabela(["Descrição", "Qtd", "Valor unitário", "Total"], ["Pula-pula", "1", "R$ 1.234,00", "R$ 1.234,00"])
            + par("Frete: R$ 150,00 (ou R$ 90,00 com retirada parcial)")
        )
        dados = leitura_ia_vazia()
        dados["frete"] = campo_ia("R$ 90,00", "P1")
        proposta = proposta_de(conteudo, dados_ia=dados)
        frete = proposta["valores"]["frete"]
        self.assertEqual(frete["valor"], "")
        self.assertEqual([o["valor"] for o in frete["opcoes"]], ["150,00", "90,00"])
        alerta = alertas_por_id(proposta)["divergencia:valores.frete"]
        self.assertEqual(alerta["nivel"], "vermelho")

    def test_cnpj_da_empresa_citado_pela_ia_e_descartado(self):
        dados = leitura_ia_vazia()
        dados["cliente"]["documento"] = campo_ia("54.486.908/0001-86", "CAB-P1")
        proposta = proposta_de(docx_com_tabela(), dados_ia=dados)
        # O documento do cliente continua sendo o que a tabela leu.
        self.assertEqual(proposta["cliente"]["documento"]["valor"], "11.222.333/0001-81")
        self.assertTrue(any("própria Lazer" in a["detalhe"] for a in proposta["alertas"]))
        proposta = proposta_de(docx_com_produto_inexistente(), dados_ia=dados)
        self.assertEqual(proposta["cliente"]["documento"]["valor"], "")

    def test_valor_do_word_que_nao_entrou_em_campo_nenhum(self):
        conteudo = montar_docx(
            tabela(["Descrição", "Qtd", "Valor unitário", "Total"], ["Pula-pula", "1", "R$ 1.234,00", "R$ 1.234,00"])
            + par("Taxa de montagem especial R$ 350,00 por dia")
        )
        alerta = alertas_por_id(proposta_de(conteudo))["valores_nao_usados"]
        self.assertIn("350,00", alerta["detalhe"])

    def test_sem_ia_a_leitura_por_regra_nao_tem_aviso_tecnico(self):
        # Sem a IA, a leitura é a de sempre (tabelas e textos): não há o que
        # avisar. Aviso só existe para o PDF que é imagem, transcrito pela IA.
        proposta = proposta_de(docx_com_tabela())
        self.assertFalse(proposta["ia"]["usada"])
        self.assertEqual(proposta["ia"]["aviso"], "")

    def test_validade_vencida_no_word_vira_sugestao_e_nao_valor(self):
        conteudo = montar_docx(par(f"Validade: {_data_br(-3)}") + par("Total: R$ 10,00"))
        validade = proposta_de(conteudo)["condicoes"]["validade"]
        self.assertEqual(validade["valor"], "")
        self.assertIn("já passou", validade["nota"])
        self.assertTrue(validade["sugestoes"])


# ======================================================================
# 6. O FLUXO PELA TELA
# ======================================================================
def formulario_de(envio, **mudancas):
    """O POST que a tela de conferência mandaria, a partir do envio."""
    envio = json.loads(json.dumps(envio))
    for chave, valor in mudancas.items():
        envio[chave] = valor
    dados = {"action": "criar", "itens_ordem": ",".join(i["uid"] for i in envio["itens"])}
    for chave in ("modo", "cliente_modo", "cliente_id", "nome", "estabelecimento", "documento", "tipo", "contato",
                  "telefone", "whatsapp", "email", "cep", "endereco", "numero", "complemento", "bairro", "cidade",
                  "estado",
                  "frete", "desconto", "validade", "forma_pagamento", "forma_envio", "prazo", "observacoes",
                  "total_escolha"):
        dados[chave] = envio.get(chave) or ""
    # A data do documento: a do envio (escrita no documento), ou a resposta
    # da pessoa ao primeiro passo do modal -- aqui, "hoje". Um teste que
    # quer a data em branco passa data_documento="".
    if "data_documento" in mudancas:
        dados["data_documento"] = mudancas["data_documento"]
    else:
        dados["data_documento"] = envio.get("data_documento") or timezone.localdate().isoformat()
    if envio.get("cliente_confirmado"):
        dados["cliente_confirmado"] = "1"
    if envio.get("publicar_no_mapa"):
        dados["publicar_no_mapa"] = "1"
    for item in envio["itens"]:
        prefixo = f"item-{item['uid']}-"
        dados[prefixo + "descricao"] = item["descricao"]
        dados[prefixo + "produto"] = item["produto"]
        dados[prefixo + "quantidade"] = item["quantidade"]
        dados[prefixo + "valor_unitario"] = item["valor_unitario"]
        if item.get("avulsa"):
            dados[prefixo + "avulsa"] = "1"
        if item.get("conferido"):
            dados[prefixo + "conferido"] = "1"
    for alerta, texto in (envio.get("justificativas") or {}).items():
        dados[f"aceite-{alerta}"] = "1"
        dados[f"justificativa-{alerta}"] = texto
    return dados


class _ComUsuario(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.brinquedos, cls.peca, cls.produto = criar_catalogo()
        cls.vendedor = User.objects.create_user("vendedor", "vendedor@exemplo.com", "senha")
        atribuir_funcoes(cls.vendedor, ["vendas"])

    def setUp(self):
        # Sem chave, por padrão: nenhum teste fala com a API de verdade,
        # nem por acaso, mesmo numa máquina que tenha a chave no ambiente.
        ambiente = mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""})
        ambiente.start()
        self.addCleanup(ambiente.stop)
        # Nem a busca da coordenada do mapa sai para a rede: o ponto vem
        # daqui (o centro de São Paulo), e cada teste do mapa troca.
        localizar = mock.patch.object(
            mapa, "procurar_coordenadas", return_value=(Decimal("-23.5505"), Decimal("-46.6333"), ""),
        )
        self.procurar_coordenadas = localizar.start()
        self.addCleanup(localizar.stop)
        # E a consulta do CEP também não: cada teste que precisa dela diz a resposta.
        cep = mock.patch.object(views_importacao, "buscar_dados_cep", return_value=None)
        self.buscar_dados_cep = cep.start()
        self.addCleanup(cep.stop)
        self.client.force_login(self.vendedor)

    def importar(self, conteudo, nome="orcamento.docx", para=""):
        dados = {"arquivo": SimpleUploadedFile(nome, conteudo)}
        if para:
            dados["para"] = para
        resposta = self.client.post(URL_IMPORTAR, dados, **HOST)
        self.assertEqual(resposta.status_code, 302, getattr(resposta, "content", b"")[:400])
        return resposta["Location"]

    def proposta_e_envio(self, url, modo="orcamento"):
        """A tela de conferência como abre -- e, por padrão, com "Criar o
        orçamento também" ligado, que é o que a maioria dos testes daqui
        confere. `modo=None` devolve a tela exatamente como abriu."""
        resposta = self.client.get(url, **HOST)
        self.assertEqual(resposta.status_code, 200)
        envio = resposta.context["envio"]
        if modo:
            envio["modo"] = modo
        return resposta.context["proposta"], envio


class PermissoesTests(_ComUsuario):

    def test_visitante_vai_para_o_login(self):
        self.client.logout()
        resposta = self.client.get(URL_IMPORTAR, **HOST)
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("login", resposta["Location"])

    def test_fora_do_subdominio_a_tela_nao_existe(self):
        resposta = self.client.get(URL_IMPORTAR)
        self.assertNotEqual(resposta.status_code, 200)

    def test_financeiro_ve_orcamento_mas_nao_importa(self):
        financeiro = User.objects.create_user("financeiro", "f@exemplo.com", "senha")
        atribuir_funcoes(financeiro, ["financeiro"])
        self.client.force_login(financeiro)
        self.assertEqual(self.client.get(URL_IMPORTAR, **HOST).status_code, 403)
        resposta = self.client.post(URL_IMPORTAR, {"arquivo": SimpleUploadedFile("a.docx", docx_com_tabela())}, **HOST)
        self.assertEqual(resposta.status_code, 403)
        # Nem o botão aparece na lista de orçamentos.
        self.assertNotContains(self.client.get("/orcamentos/", **HOST), "Importar Word ou PDF")

    def test_producao_nao_entra(self):
        producao = User.objects.create_user("producao", "p@exemplo.com", "senha")
        atribuir_funcoes(producao, ["producao"])
        self.client.force_login(producao)
        self.assertEqual(self.client.get(URL_IMPORTAR, **HOST).status_code, 302)

    def test_vendas_ve_o_botao_e_a_tela(self):
        lista = self.client.get("/orcamentos/", **HOST)
        self.assertContains(lista, "Importar Word ou PDF")
        self.assertNotContains(lista, "Importar Word ou PDF (IA)")
        self.assertEqual(self.client.get(URL_IMPORTAR, **HOST).status_code, 200)

    def test_a_leitura_de_um_nao_abre_para_outro(self):
        url = self.importar(docx_com_tabela())
        outro = User.objects.create_user("outro", "o@exemplo.com", "senha")
        atribuir_funcoes(outro, ["vendas"])
        self.client.force_login(outro)
        self.assertEqual(self.client.get(url, **HOST)["Location"], URL_IMPORTAR)


class EnvioDoArquivoTests(_ComUsuario):

    def test_doc_antigo_volta_com_a_instrucao(self):
        resposta = self.client.post(
            URL_IMPORTAR, {"arquivo": SimpleUploadedFile("velho.doc", b"\xd0\xcf\x11\xe0" + b"0" * 64)}, **HOST,
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertContains(resposta, "Salvar como", status_code=400)

    def test_pdf_falso_e_recusado(self):
        resposta = self.client.post(
            URL_IMPORTAR, {"arquivo": SimpleUploadedFile("orcamento.pdf", b"isto nao e um pdf")}, **HOST,
        )
        self.assertContains(resposta, "tem nome de PDF, mas o conteúdo não é de um PDF", status_code=400)

    def test_pdf_com_texto_e_lido_aqui_mesmo_sem_a_ia(self):
        url = self.importar(montar_pdf(), nome="orcamento.pdf")
        resposta = self.client.get(url, **HOST)
        self.assertEqual(resposta.context["proposta"]["formato"], "pdf")
        self.assertEqual(resposta.context["envio"]["nome"], "Buffet Alegria Ltda")
        self.assertEqual(resposta.context["proposta"]["valores"]["total"]["valor"], "1.919,00")
        for termo in JARGAO:
            self.assertNotIn(termo, texto_visivel(resposta))

    def test_pdf_imagem_sem_a_ia_pede_o_word_sem_jargao(self):
        with self.assertLogs("sistema_interno.views_importacao", "INFO"):
            resposta = self.client.post(
                URL_IMPORTAR, {"arquivo": SimpleUploadedFile("scan.pdf", montar_pdf_imagem())}, **HOST,
            )
        self.assertContains(resposta, "Este PDF é uma imagem", status_code=400)
        self.assertContains(resposta, "Envie o arquivo do Word", status_code=400)
        for termo in JARGAO:
            self.assertNotIn(termo, texto_visivel(resposta))

    def test_o_campo_aceita_word_e_pdf(self):
        resposta = self.client.get(URL_IMPORTAR, **HOST)
        self.assertContains(resposta, 'accept=".docx,.pdf,')
        self.assertContains(resposta, "Word (.docx) ou PDF")

    def test_sem_arquivo(self):
        self.assertEqual(self.client.post(URL_IMPORTAR, {}, **HOST).status_code, 400)

    def test_o_arquivo_nao_fica_na_sessao(self):
        url = self.importar(docx_com_tabela())
        token = url.rstrip("/").split("/")[-1]
        guardado = self.client.session["importacoes_orcamento_word"][token]
        # "datas_arquivo": só as datas de criado/salvo do arquivo (a opção
        # na pergunta "De quando é este documento?"), nada do conteúdo.
        self.assertEqual(set(guardado), {"arquivo", "formato", "linhas", "ia", "escolhas", "para", "cep_consultado",
                                         "datas_arquivo", "criado_em", "autor"})
        self.assertNotIn("PK", json.dumps(guardado))

    def test_token_inventado_volta_para_o_envio(self):
        resposta = self.client.get(URL_IMPORTAR + "nao-existe/", **HOST)
        self.assertEqual(resposta["Location"], URL_IMPORTAR)


class SemChaveDaIATests(_ComUsuario):

    def test_a_importacao_funciona_pela_regra_e_nao_fala_de_chave(self):
        with self.assertLogs("sistema_interno.views_importacao", "INFO") as registro:
            url = self.importar(docx_com_tabela())
        # O motivo fica no log do servidor, para quem cuida dele.
        self.assertIn("ANTHROPIC_API_KEY", "\n".join(registro.output))
        resposta = self.client.get(url, **HOST)
        self.assertContains(resposta, "R$ 1.919,00")
        for termo in JARGAO:
            self.assertNotIn(termo, texto_visivel(resposta))
        proposta = resposta.context["proposta"]
        self.assertEqual(len(proposta["itens"]), 3)
        self.assertEqual(proposta["cliente"]["documento"]["valor"], "11.222.333/0001-81")

    def test_a_tela_de_envio_nao_fala_de_chave_nem_de_ia(self):
        resposta = self.client.get(URL_IMPORTAR, **HOST)
        for termo in JARGAO:
            self.assertNotIn(termo, texto_visivel(resposta))
        self.assertNotContains(resposta, "Anthropic")
        self.assertNotContains(self.client.get("/orcamentos/", **HOST), "(IA)")


class CriacaoTests(_ComUsuario):

    def envio_completo(self, url, **mudancas):
        proposta, envio = self.proposta_e_envio(url)
        for item in envio["itens"]:
            item["conferido"] = True
        envio.update(mudancas)
        return proposta, envio

    def test_sem_os_obrigatorios_o_servidor_bloqueia(self):
        url = self.importar(docx_com_tabela())
        _, envio = self.proposta_e_envio(url)
        for item in envio["itens"]:
            item["conferido"] = True
        resposta = self.client.post(url, formulario_de(envio, forma_envio="", whatsapp="",
                                                       validade="", frete=""), **HOST)
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(Orcamento.objects.count(), 0)
        validado = resposta.context["validado"]
        # Só o dinheiro segura: frete em branco. WhatsApp, forma de envio e
        # validade em branco não travam mais (vêm da regra ou do padrão).
        self.assertEqual({p["campo"] for p in validado["pendencias"]}, {"valores.frete"})
        self.assertIn("condicoes.forma_envio", {p["campo"] for p in validado["recomendacoes"]})
        self.assertContains(resposta, "Falta preencher", status_code=400)

    def test_whatsapp_em_branco_segue_a_regra_e_nao_trava(self):
        url = self.importar(docx_com_tabela())
        proposta, envio = self.envio_completo(url, whatsapp="", forma_envio="", validade="")
        resposta = self.client.post(url, formulario_de(envio), **HOST)
        self.assertEqual(resposta.status_code, 302, resposta.context and resposta.context["validado"]["pendencias"])
        orcamento = Orcamento.objects.get()
        # (11) 98765-4321: celular de nove dígitos, então WhatsApp.
        self.assertEqual(orcamento.cliente.canal_telefone, Cliente.CanalTelefone.WHATSAPP)
        # Sem validade escrita: os 5 dias do padrão contam da data do
        # documento ("Data:" de dois dias atrás), e não de hoje.
        self.assertEqual(orcamento.data_documento, timezone.localdate() - timedelta(days=2))
        self.assertEqual(orcamento.validade, timezone.localdate() - timedelta(days=2) + timedelta(days=5))
        self.assertEqual(orcamento.forma_envio, "")

    def test_item_sem_produto_nem_linha_avulsa_bloqueia(self):
        url = self.importar(docx_com_produto_inexistente())
        _, envio = self.envio_completo(url, validade=(timezone.localdate() + timedelta(days=5)).isoformat(),
                                       frete="0,00", forma_pagamento="Pix", forma_envio="Retirada pelo cliente")
        resposta = self.client.post(url, formulario_de(envio), **HOST)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("itens.i1.produto", {p["campo"] for p in resposta.context["validado"]["pendencias"]})

        envio["itens"][0]["avulsa"] = True
        resposta = self.client.post(url, formulario_de(envio), **HOST)
        self.assertEqual(resposta.status_code, 302)
        item = Orcamento.objects.get().itens.get()
        self.assertIsNone(item.brinquedo_id)
        self.assertEqual(item.descricao, "Tobogã gigante inflável 8 m")

    def test_completo_cria_o_rascunho_com_itens_vinculos_e_atividade(self):
        url = self.importar(docx_com_tabela(), nome="Proposta Buffet Alegria.docx")
        _, envio = self.envio_completo(url, whatsapp="sim")
        resposta = self.client.post(url, formulario_de(envio), **HOST)

        self.assertEqual(resposta.status_code, 302, resposta.context and resposta.context["validado"]["pendencias"])
        orcamento = Orcamento.objects.get()
        self.assertEqual(resposta["Location"], f"/orcamentos/importar/concluido/{orcamento.pk}/")
        self.assertEqual(orcamento.status, Orcamento.Status.RASCUNHO)
        self.assertIsNone(orcamento.enviado_em)
        self.assertEqual(orcamento.responsavel, self.vendedor)
        self.assertEqual(orcamento.total, Decimal("1919.00"))

        itens = list(orcamento.itens.order_by("id"))
        self.assertEqual([i.descricao for i in itens], ["Cama elástica 3 m", "Pula-pula", "Mola de reposição"])
        self.assertEqual(itens[0].brinquedo, self.brinquedos["Cama elástica 3 m"])
        self.assertEqual(itens[1].brinquedo, self.brinquedos["Pula-pula"])
        self.assertEqual(itens[2].peca, self.peca)
        self.assertEqual([i.quantidade for i in itens], [2, 1, 10])
        self.assertEqual([i.valor_unitario for i in itens], [Decimal("280.00"), Decimal("1234.00"), Decimal("12.50")])

        cliente = orcamento.cliente
        self.assertEqual(cliente.nome_cliente, "Buffet Alegria Ltda")
        self.assertEqual(cliente.tipo, Cliente.Tipo.BUFFET)
        self.assertTrue(cliente.documento_valido)
        self.assertEqual(AvaliacaoBlocoOrcamento.objects.filter(orcamento=orcamento).count(), 2)

        atividades = list(AtividadeOrcamento.objects.filter(orcamento=orcamento).order_by("id"))
        principal = atividades[-1]
        self.assertIn("Proposta Buffet Alegria.docx", principal.resumo)
        self.assertIn("nada enviado ao cliente", principal.resumo)
        self.assertEqual(principal.autor, self.vendedor)
        self.assertTrue(any("«Cama elástica 3m com rede» → Cama elástica 3 m" in a.resumo for a in atividades))
        # A leitura sai da sessão quando o orçamento nasce.
        self.assertEqual(self.client.session.get("importacoes_orcamento_word"), {})

    def test_o_que_vem_do_word_sai_no_padrao_do_painel(self):
        url = self.importar(docx_com_tabela())
        proposta, envio = self.envio_completo(url, whatsapp="sim")
        self.assertEqual(envio["telefone"], "(11) 98765-4321")
        self.assertEqual(envio["email"], "contato@buffetalegria.com.br")
        self.assertEqual(envio["documento"], "11.222.333/0001-81")
        self.assertEqual(envio["forma_pagamento"], "Pix")
        self.assertEqual(envio["forma_envio"], "Entrega Lazer & Sport")
        self.assertEqual(envio["validade"], (timezone.localdate() + timedelta(days=13)).isoformat())
        self.assertEqual(envio["itens"][1]["valor_unitario"], "1.234,00")
        pagamento = proposta["condicoes"]["forma_pagamento"]
        self.assertTrue(pagamento["normalizado"])
        self.assertEqual((pagamento["original"], pagamento["valor"]), ("PIX", "Pix"))

        self.client.post(url, formulario_de(envio), **HOST)
        orcamento = Orcamento.objects.get()
        self.assertEqual(orcamento.whatsapp_cliente, "(11) 98765-4321")
        self.assertEqual(orcamento.cliente.telefone, "(11) 98765-4321")
        self.assertEqual(orcamento.cliente.canal_telefone, Cliente.CanalTelefone.WHATSAPP)
        self.assertEqual(orcamento.cliente.documento, "11.222.333/0001-81")
        self.assertEqual(orcamento.forma_pagamento, "Pix")
        self.assertTrue(orcamento.observacoes.startswith("Prazo de entrega: 20 dias úteis."))

    def test_a_validade_padrao_e_sugestao_e_nunca_vem_preenchida(self):
        url = self.importar(docx_com_produto_inexistente())
        proposta, envio = self.proposta_e_envio(url)
        self.assertEqual(envio["validade"], "")
        # Em branco não trava: vale o padrão do painel, que a tela mostra.
        self.assertNotIn("condicoes.validade", {
            p["campo"] for p in formulario.validar(proposta, envio)["pendencias"]})
        self.assertContains(self.client.get(url, **HOST), "Em branco, vale o padrão do painel")
        sugestao = proposta["condicoes"]["validade"]["sugestoes"][0]
        self.assertEqual(sugestao["valor"], (timezone.localdate() + timedelta(days=5)).isoformat())
        # O documento não fala de frete, e a linha já dá o total escrito:
        # o frete é zero, dito ao lado do campo (e a pessoa troca se for o caso).
        self.assertEqual(envio["frete"], "0,00")
        self.assertIn("não cobra frete", proposta["valores"]["frete"]["nota"])

    def test_alerta_vermelho_bloqueia_ate_corrigir_ou_justificar(self):
        url = self.importar(docx_com_total_errado())
        proposta, envio = self.envio_completo(
            url, frete="0,00", forma_envio="Retirada pelo cliente",
            validade=(timezone.localdate() + timedelta(days=5)).isoformat(),
        )
        resposta = self.client.post(url, formulario_de(envio), **HOST)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("alerta.soma_total", {p["campo"] for p in resposta.context["validado"]["pendencias"]})

        # Justificativa curta demais não vale.
        envio["justificativas"] = {"soma_total": "ok"}
        resposta = self.client.post(url, formulario_de(envio), **HOST)
        self.assertEqual(resposta.status_code, 400)

        envio["justificativas"] = {"soma_total": "O total do Word somou errado; as linhas conferem."}
        resposta = self.client.post(url, formulario_de(envio), **HOST)
        self.assertEqual(resposta.status_code, 302)
        orcamento = Orcamento.objects.get()
        self.assertEqual(orcamento.total, Decimal("1794.00"))
        aceito = AtividadeOrcamento.objects.filter(orcamento=orcamento, resumo__contains="alerta aceito").get()
        self.assertIn("O total do Word somou errado", aceito.resumo)
        self.assertEqual(aceito.autor, self.vendedor)

    def test_corrigir_o_valor_resolve_o_alerta_sem_justificativa(self):
        """Com frete de R$ 56,00 a conta passa a dar os R$ 1.850,00 do Word."""
        url = self.importar(docx_com_total_errado())
        _, envio = self.envio_completo(
            url, frete="56,00", forma_envio="Transportadora",
            validade=(timezone.localdate() + timedelta(days=5)).isoformat(),
        )
        resposta = self.client.post(url, formulario_de(envio), **HOST)
        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(AtividadeOrcamento.objects.filter(resumo__contains="alerta aceito").exists())

    def test_cliente_ja_cadastrado_e_vinculado_sem_alterar_o_cadastro(self):
        existente = Cliente.objects.create(
            nome_cliente="Buffet Alegria", email="contato@buffetalegria.com.br",
            telefone="(11) 3333-4444", canal_telefone=Cliente.CanalTelefone.TELEFONE,
        )
        url = self.importar(docx_com_tabela())
        _, envio = self.envio_completo(url, whatsapp="sim")
        self.assertEqual(envio["cliente_modo"], "existente")
        self.assertEqual(envio["cliente_id"], str(existente.pk))
        self.assertEqual(self.client.post(url, formulario_de(envio), **HOST).status_code, 302)

        orcamento = Orcamento.objects.get()
        self.assertEqual(orcamento.cliente, existente)
        self.assertEqual(orcamento.whatsapp_cliente, "(11) 98765-4321")
        existente.refresh_from_db()
        self.assertEqual(existente.telefone, "(11) 3333-4444")
        self.assertEqual(Cliente.objects.count(), 1)

    def test_cliente_pelo_nome_pede_confirmacao(self):
        Cliente.objects.create(nome_cliente="Condomínio Jardim das Flores", email="outro@exemplo.com")
        url = self.importar(docx_com_produto_inexistente())
        _, envio = self.envio_completo(
            url, frete="0,00", forma_pagamento="Pix", forma_envio="Transportadora",
            validade=(timezone.localdate() + timedelta(days=5)).isoformat(),
        )
        envio["itens"][0]["avulsa"] = True
        resposta = self.client.post(url, formulario_de(envio), **HOST)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("cliente.vinculo", {p["campo"] for p in resposta.context["validado"]["pendencias"]})
        envio["cliente_confirmado"] = True
        self.assertEqual(self.client.post(url, formulario_de(envio), **HOST).status_code, 302)

    def test_produto_sugerido_pede_confirmacao(self):
        url = self.importar(docx_com_tabela())
        _, envio = self.proposta_e_envio(url)
        envio["whatsapp"] = "sim"
        resposta = self.client.post(url, formulario_de(envio), **HOST)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("itens.i1.conferido", {p["campo"] for p in resposta.context["validado"]["pendencias"]})

    def test_trocar_o_produto_pela_busca_vale_como_escolha(self):
        url = self.importar(docx_com_tabela())
        _, envio = self.proposta_e_envio(url)
        envio["whatsapp"] = "sim"
        envio["itens"][0]["produto"] = f"b:{self.brinquedos['Cama elástica 4 m'].pk}"
        envio["itens"][0]["valor_unitario"] = "280,00"
        self.assertEqual(self.client.post(url, formulario_de(envio), **HOST).status_code, 302)
        self.assertEqual(Orcamento.objects.get().itens.order_by("id")[0].brinquedo, self.brinquedos["Cama elástica 4 m"])

    def test_desconto_so_em_porcentagem_exige_o_valor(self):
        conteudo = montar_docx(
            par("Cliente: Marina Souza") + par("E-mail: marina@exemplo.com")
            + tabela(["Descrição", "Qtd", "Valor unitário", "Total"], ["Pula-pula", "1", "R$ 1.000,00", "R$ 1.000,00"])
            + par("Desconto: 10%")
        )
        url = self.importar(conteudo)
        proposta, envio = self.envio_completo(
            url, frete="0,00", forma_pagamento="Pix", forma_envio="Transportadora",
            validade=(timezone.localdate() + timedelta(days=5)).isoformat(),
        )
        self.assertEqual(proposta["valores"]["desconto"]["sugestoes"][0]["valor"], "100,00")
        resposta = self.client.post(url, formulario_de(envio), **HOST)
        self.assertIn("valores.desconto", {p["campo"] for p in resposta.context["validado"]["pendencias"]})
        self.assertEqual(self.client.post(url, formulario_de(envio, desconto="100,00"), **HOST).status_code, 302)
        self.assertEqual(Orcamento.objects.get().total, Decimal("900.00"))

    def test_valor_negociado_escrito_vem_escolhido_como_valor_final(self):
        url = self.importar(docx_com_valor_negociado())
        proposta, envio = self.envio_completo(url, forma_envio="Transportadora")
        self.assertTrue(proposta["valor_final"]["oferecido"])
        self.assertTrue(proposta["valor_final"]["explicito"])
        self.assertEqual(proposta["valor_final"]["valor"], "9.800,00")
        self.assertEqual(proposta["valor_final"]["soma"], "10.200,00")
        # Escrito com rótulo próprio ("Valor total negociado"), é o preço
        # combinado: já vem escolhido, e a tela mostra a escolha.
        self.assertEqual(envio["total_escolha"], "valor_final")
        self.assertContains(self.client.get(url, **HOST), "Qual total vale?")

        resposta = self.client.post(url, formulario_de(envio, desconto="50,00"), **HOST)
        self.assertEqual(resposta.status_code, 302, resposta.context and resposta.context["validado"]["pendencias"])
        orcamento = Orcamento.objects.get()
        self.assertEqual(orcamento.valor_final, Decimal("9800.00"))
        self.assertEqual(orcamento.desconto, Decimal("0.00"))
        self.assertEqual(orcamento.total, Decimal("9800.00"))
        registro = AtividadeOrcamento.objects.get(orcamento=orcamento, resumo__contains="valor final combinado")
        self.assertIn("R$ 9.800,00", registro.resumo)
        self.assertIn("valor negociado escrito no documento", registro.resumo)
        self.assertIn("R$ 10.200,00", registro.resumo)

    def test_total_que_nao_bate_oferece_o_valor_final_e_nao_escolhe_sozinho(self):
        url = self.importar(docx_com_total_errado())
        proposta, envio = self.envio_completo(url, frete="0,00")
        self.assertTrue(proposta["valor_final"]["oferecido"])
        self.assertFalse(proposta["valor_final"]["explicito"])
        self.assertEqual(proposta["valor_final"]["valor"], "1.850,00")
        self.assertEqual(envio["total_escolha"], "")
        resposta = self.client.post(url, formulario_de(envio), **HOST)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("alerta.soma_total", {p["campo"] for p in resposta.context["validado"]["pendencias"]})
        resposta = self.client.post(url, formulario_de(envio, total_escolha="valor_final"), **HOST)
        self.assertEqual(resposta.status_code, 302, resposta.context and resposta.context["validado"]["pendencias"])
        self.assertEqual(Orcamento.objects.get().total, Decimal("1850.00"))

    def test_manter_a_soma_pede_justificativa(self):
        url = self.importar(docx_com_valor_negociado())
        _, envio = self.envio_completo(url, forma_envio="Transportadora", total_escolha="soma")
        self.assertEqual(self.client.post(url, formulario_de(envio), **HOST).status_code, 400)
        envio["justificativas"] = {"soma_total": "O cliente pediu a proposta cheia, sem o valor fechado."}
        self.assertEqual(self.client.post(url, formulario_de(envio), **HOST).status_code, 302)
        orcamento = Orcamento.objects.get()
        self.assertIsNone(orcamento.valor_final)
        self.assertEqual(orcamento.total, Decimal("10200.00"))
        self.assertTrue(AtividadeOrcamento.objects.filter(
            orcamento=orcamento, resumo__contains="O cliente pediu a proposta cheia").exists())

    def test_a_tela_final_mostra_cliente_e_orcamento_com_os_links(self):
        url = self.importar(docx_com_tabela(), nome="Proposta Buffet Alegria.docx")
        _, envio = self.envio_completo(url)
        destino = self.client.post(url, formulario_de(envio), **HOST)["Location"]
        orcamento = Orcamento.objects.get()
        cliente = orcamento.cliente
        resposta = self.client.get(destino, **HOST)
        self.assertContains(resposta, "Cliente cadastrado e orçamento criado")
        self.assertContains(resposta, "Cliente novo")
        self.assertContains(resposta, f"Orçamento #{orcamento.pk}")
        self.assertContains(resposta, f'href="/orcamentos/?editar={orcamento.pk}"')
        self.assertContains(resposta, f"abrir={cliente.pk}")
        self.assertContains(resposta, "Proposta Buffet Alegria.docx")
        self.assertContains(resposta, "R$ 1.919,00")
        # O link do cliente abre a ficha dele, já aberta.
        ficha = self.client.get(resposta.context["link_cliente"], **HOST)
        self.assertEqual(ficha.status_code, 200)
        self.assertContains(ficha, 'get("abrir")')
        # E é só de quem importou.
        outro = User.objects.create_user("outra", "outra@exemplo.com", "senha")
        atribuir_funcoes(outro, ["vendas"])
        self.client.force_login(outro)
        self.assertEqual(self.client.get(destino, **HOST).status_code, 404)

    def test_so_cadastrar_o_cliente_nao_pede_nada_do_orcamento(self):
        url = self.importar(docx_com_tabela())
        _, envio = self.proposta_e_envio(url, modo=None)
        # Nada do orçamento conferido: nem produto, nem frete, nem total.
        resposta = self.client.post(url, formulario_de(envio, modo="cliente", frete="", forma_envio=""), **HOST)
        self.assertEqual(resposta.status_code, 302, resposta.context and resposta.context["validado"]["pendencias"])
        self.assertEqual(Orcamento.objects.count(), 0)
        cliente = Cliente.objects.get()
        self.assertEqual(cliente.nome_cliente, "Buffet Alegria Ltda")
        self.assertEqual(cliente.documento, "11.222.333/0001-81")
        self.assertEqual(cliente.telefone, "(11) 98765-4321")
        self.assertEqual(cliente.canal_telefone, Cliente.CanalTelefone.WHATSAPP)
        self.assertEqual(cliente.email, "contato@buffetalegria.com.br")
        self.assertEqual(resposta["Location"], f"/orcamentos/importar/cliente/{cliente.pk}/")
        pagina = self.client.get(resposta["Location"], **HOST)
        self.assertContains(pagina, "Cliente cadastrado")
        self.assertContains(pagina, "nenhum orçamento foi criado")
        self.assertContains(pagina, f"/clientes/?q=Buffet+Alegria+Ltda&amp;abrir={cliente.pk}")
        self.assertEqual(self.client.session.get("importacoes_orcamento_word"), {})

    def test_documento_sem_itens_abre_em_so_o_cliente(self):
        ficha = montar_docx(
            par("FICHA DE CADASTRO")
            + tabela(["Nome", "Marina Souza"], ["CPF", "529.982.247-25"], ["Celular", "11 97777-6655"],
                     ["E-mail", "marina@festas.com.br"], ["CEP", "01310100"], ["Rua", "Avenida Paulista"],
                     ["Número", "1000"], ["Bairro", "Bela Vista"], ["Cidade", "São Paulo"], ["UF", "SP"]),
        )
        url = self.importar(ficha)
        proposta, envio = self.proposta_e_envio(url, modo=None)
        self.assertEqual(envio["modo"], "cliente")
        self.assertEqual((envio["nome"], envio["documento"], envio["telefone"], envio["cep"]),
                         ("Marina Souza", "529.982.247-25", "(11) 97777-6655", "01310-100"))
        self.assertEqual(formulario.validar(proposta, envio)["pendencias"], [])
        resposta = self.client.post(url, formulario_de(envio), **HOST)
        self.assertEqual(resposta.status_code, 302)
        cliente = Cliente.objects.get()
        endereco = cliente.endereco_principal
        self.assertEqual((endereco.cep, endereco.endereco, endereco.numero, endereco.bairro, endereco.cidade,
                          endereco.estado), ("01310-100", "Avenida Paulista", "1000", "Bela Vista", "São Paulo", "SP"))

    def test_so_o_cliente_que_ja_existe_atualiza_o_cadastro_sem_duplicar(self):
        existente = Cliente.objects.create(nome_cliente="Buffet Alegria Ltda", email="contato@buffetalegria.com.br")
        url = self.importar(docx_com_tabela())
        _, envio = self.proposta_e_envio(url, modo=None)
        self.assertEqual(envio["cliente_modo"], "existente")
        resposta = self.client.post(url, formulario_de(envio, modo="cliente"), **HOST)
        self.assertEqual(resposta.status_code, 302, resposta.context and resposta.context["validado"]["pendencias"])
        self.assertEqual(Cliente.objects.count(), 1)
        existente.refresh_from_db()
        self.assertEqual(existente.documento, "11.222.333/0001-81")
        self.assertEqual(existente.telefone, "(11) 98765-4321")
        self.assertEqual(resposta["Location"], f"/orcamentos/importar/cliente/{existente.pk}/")

    def test_cliente_que_ja_existe_e_completado_e_nao_sobrescrito(self):
        existente = Cliente.objects.create(
            nome_cliente="Buffet Alegria Ltda", email="contato@buffetalegria.com.br",
            telefone="(11) 3333-0000", canal_telefone=Cliente.CanalTelefone.TELEFONE,
        )
        url = self.importar(docx_com_tabela())
        _, envio = self.envio_completo(url)
        destino = self.client.post(url, formulario_de(envio), **HOST)["Location"]
        existente.refresh_from_db()
        # O telefone que o cadastro já tinha fica; o CNPJ que faltava entra.
        self.assertEqual(existente.telefone, "(11) 3333-0000")
        self.assertEqual(existente.documento, "11.222.333/0001-81")
        self.assertEqual(Orcamento.objects.get().cliente, existente)
        pronto = self.client.get(destino, **HOST)
        self.assertContains(pronto, "Cliente já cadastrado")
        self.assertContains(pronto, "Completado no cadastro com o documento: CPF/CNPJ")

    def test_descartar_apaga_a_leitura(self):
        url = self.importar(docx_com_tabela())
        resposta = self.client.post(url, {"action": "descartar"}, **HOST)
        self.assertEqual(resposta["Location"], "/orcamentos/")
        self.assertEqual(self.client.get(url, **HOST)["Location"], URL_IMPORTAR)

    def test_o_rascunho_abre_na_tela_normal_de_edicao(self):
        url = self.importar(docx_com_tabela())
        _, envio = self.envio_completo(url, whatsapp="sim")
        concluido = self.client.get(self.client.post(url, formulario_de(envio), **HOST)["Location"], **HOST)
        destino = concluido.context["link_orcamento"]
        resposta = self.client.get(destino, **HOST)
        self.assertEqual(resposta.status_code, 200)
        dados = {o["id"]: o for o in resposta.context["orcamentos_dados"]}
        orcamento = Orcamento.objects.get()
        self.assertTrue(dados[orcamento.pk]["pode_editar"])
        self.assertEqual(len(dados[orcamento.pk]["itens"]), 3)


# ======================================================================
# 7. A IA (com o cliente do SDK trocado por um falso)
# ======================================================================
class ClienteFalso:
    """Faz o papel de `anthropic.Anthropic()` sem rede nenhuma."""

    def __init__(self, leitura=None, escolhas=None, *, parar="end_turn", erro=None, sem_fallback=False,
                 transcricao=None):
        self.leitura = leitura
        self.transcricao = transcricao
        self.escolhas = escolhas or []
        self.parar = parar
        self.erro = erro
        self.sem_fallback = sem_fallback
        self.chamadas = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self.parse, create=self.create))

    def parse(self, **argumentos):
        if self.sem_fallback and "fallbacks" in argumentos:
            raise TypeError("parse() got an unexpected keyword argument 'fallbacks'")
        self.chamadas.append(("parse", argumentos))
        if self.erro:
            raise self.erro
        formato = argumentos["output_format"]
        if formato is ia.EscolhasDeProdutos:
            dados = ia.EscolhasDeProdutos(escolhas=self.escolhas)
        elif formato is ia.PdfLido:
            dados = ia.PdfLido.model_validate({"linhas": self.transcricao or [], "orcamento": self.leitura})
        else:
            dados = ia.OrcamentoLido.model_validate(self.leitura)
        return SimpleNamespace(stop_reason=self.parar, parsed_output=dados, model="claude-opus-5-5",
                               stop_details=SimpleNamespace(category="cyber"), content=[])

    def create(self, **argumentos):
        self.chamadas.append(("create", argumentos))
        texto = json.dumps(self.leitura)
        return SimpleNamespace(stop_reason=self.parar, model="claude-opus-5-5",
                               content=[SimpleNamespace(type="text", text=texto)])


def leitura_ia_do_exemplo_com_tabela():
    dados = leitura_ia_vazia()
    dados["cliente"]["nome"] = campo_ia("Buffet Alegria Ltda", "P3")
    dados["cliente"]["documento"] = campo_ia("11.222.333/0001-81", "P4")
    dados["cliente"]["contato"] = campo_ia("Marina Souza", "P5")
    dados["cliente"]["telefone"] = campo_ia("(11) 98765-4321", "P6")
    dados["itens"] = [
        item_ia("Cama elástica 3m com rede", "2", "R$ 280,00", "R$ 560,00", "T1L2"),
        item_ia("Pula pula", "1", "R$ 1.234", "R$ 1.234,00", "T1L3"),
        item_ia("Mola de reposição", "10 un", "12,50", "125,00", "T1L4"),
    ]
    dados["total_geral"] = campo_ia("R$ 1.919,00", "T1L5C4")
    dados["frete"] = campo_ia("grátis", "P7", "Frete: grátis")
    dados["validade"] = campo_ia("15 dias", "P8")
    dados["forma_pagamento"] = campo_ia("PIX", "P9")
    dados["prazo_entrega"] = campo_ia("20 dias úteis", "P11")
    return dados


@override_settings(ORCAMENTO_IA_MODELO="claude-opus-5-5")
class IATests(_ComUsuario):

    def setUp(self):
        super().setUp()
        ambiente = mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "chave-de-teste"})
        ambiente.start()
        self.addCleanup(ambiente.stop)

    def com_cliente(self, falso):
        trocar = mock.patch.object(ia, "_cliente", return_value=falso)
        trocar.start()
        self.addCleanup(trocar.stop)
        return falso

    def test_a_chamada_usa_o_modelo_o_esforco_o_fallback_e_o_esquema(self):
        falso = self.com_cliente(ClienteFalso(leitura_ia_do_exemplo_com_tabela()))
        dados, modelo = ia.ler_orcamento("[P1] teste")
        self.assertEqual(modelo, "claude-opus-5-5")
        self.assertEqual(dados["cliente"]["nome"]["texto"], "Buffet Alegria Ltda")
        _, argumentos = falso.chamadas[0]
        self.assertEqual(argumentos["model"], "claude-opus-5-5")
        self.assertEqual(argumentos["max_tokens"], 16000)
        self.assertEqual(argumentos["output_config"], {"effort": "high"})
        self.assertIs(argumentos["output_format"], ia.OrcamentoLido)
        self.assertEqual(argumentos["betas"], ["server-side-fallback-2026-07-01"])
        self.assertEqual(argumentos["fallbacks"], "default")
        self.assertNotIn("thinking", argumentos)
        self.assertIn("[P1] teste", argumentos["messages"][0]["content"])

    def test_sdk_sem_fallback_no_parse_usa_o_create_com_esquema(self):
        falso = self.com_cliente(ClienteFalso(leitura_ia_do_exemplo_com_tabela(), sem_fallback=True))
        dados, _ = ia.ler_orcamento("[P1] teste")
        self.assertEqual(dados["frete"]["texto"], "grátis")
        tipo, argumentos = falso.chamadas[0]
        self.assertEqual(tipo, "create")
        self.assertEqual(argumentos["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(argumentos["output_config"]["effort"], "high")

    def test_recusa_e_corte_nao_viram_leitura(self):
        self.com_cliente(ClienteFalso(leitura_ia_do_exemplo_com_tabela(), parar="refusal"))
        with self.assertRaisesMessage(ia.IAIndisponivel, "recusou"):
            ia.ler_orcamento("[P1] teste")

    def test_erros_do_sdk_viram_mensagem_clara(self):
        import anthropic
        import httpx2

        pedido = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
        casos = (
            (anthropic.RateLimitError("limite", response=httpx2.Response(429, request=pedido), body=None), "limite de uso"),
            (anthropic.InternalServerError("falha", response=httpx2.Response(500, request=pedido), body=None), "erro 500"),
            (anthropic.APIConnectionError(request=pedido), "não consegui falar"),
            (anthropic.APITimeoutError(request=pedido), "prazo"),
        )
        for erro, mensagem in casos:
            with self.subTest(erro=type(erro).__name__):
                with mock.patch.object(ia, "_cliente", return_value=ClienteFalso(erro=erro)):
                    with self.assertRaisesMessage(ia.IAIndisponivel, mensagem):
                        ia.ler_orcamento("[P1] teste")

    def test_a_escolha_de_produto_so_aceita_id_da_lista(self):
        self.com_cliente(ClienteFalso(escolhas=[
            ia.EscolhaDeProduto(item=1, produto="b:1"),
            ia.EscolhaDeProduto(item=2, produto="b:999"),
            ia.EscolhaDeProduto(item=3, produto="nenhum"),
        ]))
        escolhas = ia.escolher_produtos([
            {"item": 1, "descricao": "a", "candidatos": [{"id": "b:1", "nome": "A", "grupo": "Brinquedos"}]},
            {"item": 2, "descricao": "b", "candidatos": [{"id": "b:2", "nome": "B", "grupo": "Brinquedos"}]},
            {"item": 3, "descricao": "c", "candidatos": [{"id": "b:3", "nome": "C", "grupo": "Brinquedos"}]},
        ])
        self.assertEqual(escolhas, {1: "b:1"})

    def test_importacao_com_ia_le_confere_e_marca_a_origem(self):
        cama = self.brinquedos["Cama elástica 3 m"]
        falso = self.com_cliente(ClienteFalso(
            leitura_ia_do_exemplo_com_tabela(),
            escolhas=[ia.EscolhaDeProduto(item=1, produto=f"b:{cama.pk}")],
        ))
        url = self.importar(docx_com_tabela())
        resposta = self.client.get(url, **HOST)
        self.assertContains(resposta, "O texto do documento foi enviado à Anthropic")
        self.assertNotContains(resposta, "IA indisponível")
        proposta = resposta.context["proposta"]
        self.assertTrue(proposta["ia"]["usada"])
        self.assertEqual(proposta["ia"]["modelo"], "claude-opus-5-5")
        self.assertEqual(proposta["itens"][1]["valor_unitario"]["origem"], "ambas")
        self.assertEqual(proposta["cliente"]["contato"]["valor"], "Marina Souza")
        produto = proposta["itens"][0]["produto"]
        self.assertTrue(produto["por_ia"])
        self.assertEqual(produto["confianca"], "media")
        # Uma chamada para ler e uma para escolher os produtos em dúvida.
        self.assertEqual([a["output_format"] for _, a in falso.chamadas],
                         [ia.OrcamentoLido, ia.EscolhasDeProdutos])

    def test_ia_que_falha_cai_na_leitura_por_regra_e_o_motivo_vai_para_o_log(self):
        self.com_cliente(ClienteFalso(leitura_ia_do_exemplo_com_tabela(), parar="refusal"))
        with self.assertLogs("sistema_interno.views_importacao", "WARNING") as registro:
            url = self.importar(docx_com_tabela())
        self.assertIn("a IA recusou ler este documento", "\n".join(registro.output))
        resposta = self.client.get(url, **HOST)
        for termo in JARGAO + ("recusou",):
            self.assertNotIn(termo, texto_visivel(resposta))
        self.assertFalse(resposta.context["proposta"]["ia"]["usada"])
        self.assertEqual(len(resposta.context["proposta"]["itens"]), 3)


class PdfTests(IATests):
    """O PDF vai inteiro para o Claude, e volta transcrito e lido."""

    def transcricao(self):
        # A mesma transcrição que a IA faria do PDF gerado a partir do
        # orçamento de exemplo: as linhas do .docx, com os mesmos ids.
        return [{"id": linha["id"], "texto": linha["texto"]} for linha in linhas_de(docx_com_tabela())]

    def test_pdf_com_texto_e_lido_aqui_e_a_ia_le_as_mesmas_linhas(self):
        falso = self.com_cliente(ClienteFalso(leitura_ia_vazia()))
        url = self.importar(montar_pdf(), nome="Orcamento Buffet.pdf")
        # O PDF com texto não vai inteiro: vão as linhas tiradas dele aqui,
        # numeradas como as do Word.
        _, argumentos = falso.chamadas[0]
        self.assertIs(argumentos["output_format"], ia.OrcamentoLido)
        self.assertIn("Cliente: Buffet Alegria Ltda", argumentos["messages"][0]["content"])
        resposta = self.client.get(url, **HOST)
        self.assertEqual(resposta.context["proposta"]["formato"], "pdf")
        self.assertEqual(resposta.context["envio"]["nome"], "Buffet Alegria Ltda")

    def test_o_pdf_imagem_vai_como_documento_e_volta_para_a_conferencia(self):
        falso = self.com_cliente(ClienteFalso(leitura_ia_do_exemplo_com_tabela(), transcricao=self.transcricao()))
        url = self.importar(montar_pdf_imagem(), nome="Orcamento Buffet.pdf")
        _, argumentos = falso.chamadas[0]
        self.assertIs(argumentos["output_format"], ia.PdfLido)
        documento, pergunta = argumentos["messages"][0]["content"]
        self.assertEqual(documento["type"], "document")
        self.assertEqual(documento["source"]["type"], "base64")
        self.assertEqual(documento["source"]["media_type"], "application/pdf")
        self.assertEqual(base64.b64decode(documento["source"]["data"]), montar_pdf_imagem())
        self.assertNotIn("\n", documento["source"]["data"])
        self.assertEqual(pergunta["type"], "text")
        self.assertEqual(argumentos["fallbacks"], "default")

        resposta = self.client.get(url, **HOST)
        self.assertContains(resposta, "Este PDF é uma imagem")
        self.assertContains(resposta, "O PDF foi enviado à Anthropic")
        proposta = resposta.context["proposta"]
        self.assertEqual(proposta["formato"], "pdf_ia")
        self.assertEqual(len(proposta["itens"]), 3)
        # Concordância dentro da mesma transcrição não é prova independente.
        self.assertEqual(proposta["itens"][1]["valor_unitario"]["origem"], "ambas")
        self.assertEqual(proposta["itens"][1]["valor_unitario"]["confianca"], "media")
        self.assertIn("transcrito do PDF", proposta["itens"][1]["valor_unitario"]["nota"])

    def test_do_pdf_ao_rascunho_com_o_mesmo_padrao(self):
        self.com_cliente(ClienteFalso(leitura_ia_do_exemplo_com_tabela(), transcricao=self.transcricao()))
        url = self.importar(montar_pdf_imagem(), nome="Orcamento Buffet.pdf")
        _, envio = self.proposta_e_envio(url)
        for item in envio["itens"]:
            item["conferido"] = True
        envio.update(whatsapp="sim", forma_envio="Entrega Lazer & Sport")
        resposta = self.client.post(url, formulario_de(envio), **HOST)
        self.assertEqual(resposta.status_code, 302, resposta.context and resposta.context["validado"]["pendencias"])
        orcamento = Orcamento.objects.get()
        self.assertEqual(orcamento.status, Orcamento.Status.RASCUNHO)
        self.assertEqual(orcamento.total, Decimal("1919.00"))
        self.assertEqual(orcamento.forma_pagamento, "Pix")
        principal = AtividadeOrcamento.objects.filter(orcamento=orcamento).order_by("-id").first()
        self.assertIn("Importado do PDF «Orcamento Buffet.pdf»", principal.resumo)

    def test_pdf_que_volta_sem_texto_pede_outro_arquivo(self):
        self.com_cliente(ClienteFalso(leitura_ia_vazia(), transcricao=[]))
        resposta = self.client.post(URL_IMPORTAR, {"arquivo": SimpleUploadedFile("scan.pdf", montar_pdf_imagem())}, **HOST)
        self.assertContains(resposta, "sem texto legível", status_code=400)
        self.assertNotIn("importacoes_orcamento_word", self.client.session)

    def test_pdf_sem_orcamento_dentro_pergunta_se_e_o_arquivo_certo(self):
        self.com_cliente(ClienteFalso(leitura_ia_vazia(), transcricao=[{"id": "P1", "texto": "Ata da reunião"}]))
        resposta = self.client.post(URL_IMPORTAR, {"arquivo": SimpleUploadedFile("ata.pdf", montar_pdf_imagem())}, **HOST)
        self.assertContains(resposta, "não encontrei nele um orçamento", status_code=400)

    def test_pdf_imagem_que_a_ia_nao_leu_pede_o_word_sem_jargao(self):
        self.com_cliente(ClienteFalso(leitura_ia_vazia(), transcricao=[], parar="refusal"))
        with self.assertLogs("sistema_interno.views_importacao", "WARNING") as registro:
            resposta = self.client.post(
                URL_IMPORTAR, {"arquivo": SimpleUploadedFile("o.pdf", montar_pdf_imagem())}, **HOST,
            )
        self.assertIn("recusou", "\n".join(registro.output))
        self.assertContains(resposta, "Este PDF é uma imagem", status_code=400)
        for termo in JARGAO + ("recusou",):
            self.assertNotIn(termo, texto_visivel(resposta))


# ======================================================================
# 7b. O CLIENTE PRIMEIRO, E NO MAPA DA HOME
# ======================================================================
def docx_ficha_com_endereco():
    """Uma ficha de cadastro com endereço: o caso de quem povoa o mapa."""
    return montar_docx(
        par("FICHA DE CADASTRO")
        + tabela(["Nome", "Parque da Alegria"], ["CNPJ", "11.444.777/0001-61"], ["Celular", "11 97777-6655"],
                 ["CEP", "01310-100"], ["Rua", "Avenida Paulista"], ["Número", "1000"],
                 ["Bairro", "Bela Vista"], ["Cidade", "São Paulo"], ["UF", "SP"]),
    )


class ClientePrimeiroTests(_ComUsuario):
    """ "vc deve deixar facil acesso só o cadastro de cliente, ai é opcional
    o orçamento e deixe ligado a questão de aparecer no mapa". """

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)

    def criar_so_cliente(self, url, **mudancas):
        _, envio = self.proposta_e_envio(url, modo=None)
        envio.update(mudancas)
        return self.client.post(url, formulario_de(envio), **HOST)

    def test_a_conferencia_abre_em_so_o_cliente_com_o_mapa_ligado(self):
        url = self.importar(docx_com_tabela())
        resposta = self.client.get(url, **HOST)
        envio = resposta.context["envio"]
        self.assertEqual(envio["modo"], "cliente")
        self.assertTrue(envio["publicar_no_mapa"])
        self.assertContains(resposta, 'name="modo" value="orcamento" id="modoOrcamento" role="switch">')
        self.assertContains(resposta, 'name="publicar_no_mapa" value="1" id="campoMapa" role="switch" checked>')
        # O orçamento é opção -- e a opção diz o que o documento traz.
        self.assertContains(resposta, "Criar o orçamento também")
        self.assertContains(resposta, "O documento tem <b>3 itens</b>, <b>R$ 1.919,00</b>")
        self.assertEqual(resposta.context["oferta_orcamento"], {"itens": 3, "total": "1.919,00"})
        # As partes do orçamento abrem escondidas, e o botão é de cadastro.
        self.assertContains(resposta, 'data-painel="itens" data-so-orcamento hidden')
        self.assertContains(resposta, '<span data-rotulo-modo="cliente">Cadastrar cliente</span>')

    def test_ligar_o_orcamento_cria_os_dois_como_antes(self):
        url = self.importar(docx_com_tabela())
        _, envio = self.proposta_e_envio(url, modo=None)
        for item in envio["itens"]:
            item["conferido"] = True
        resposta = self.client.post(url, formulario_de(envio, modo="orcamento"), **HOST)
        self.assertEqual(resposta.status_code, 302, resposta.context and resposta.context["validado"]["pendencias"])
        orcamento = Orcamento.objects.get()
        self.assertEqual(orcamento.total, Decimal("1919.00"))
        self.assertTrue(orcamento.cliente.publicar_no_mapa)

    def test_a_tela_de_clientes_leva_ao_cadastro_pelo_documento(self):
        clientes = self.client.get("/clientes/", **HOST)
        self.assertContains(clientes, 'href="/orcamentos/importar/?para=cliente"')
        self.assertContains(clientes, "Cadastrar pelo Word ou PDF")
        envio = self.client.get(URL_IMPORTAR + "?para=cliente", **HOST)
        self.assertContains(envio, "Cadastrar cliente pelo Word ou PDF")
        self.assertContains(envio, '<input type="hidden" name="para" value="cliente">')
        url = self.importar(docx_ficha_com_endereco(), para="cliente")
        self.assertEqual(self.client.get(url, **HOST).context["envio"]["modo"], "cliente")
        # Descartar devolve para a aba de onde a pessoa veio.
        self.assertEqual(self.client.post(url, {"action": "descartar"}, **HOST)["Location"], "/clientes/")

    def test_quem_nao_cria_proposta_nao_ve_o_botao(self):
        financeiro = User.objects.create_user("fin", "fin@exemplo.com", "senha")
        atribuir_funcoes(financeiro, ["financeiro"])
        self.client.force_login(financeiro)
        resposta = self.client.get("/clientes/", **HOST)
        if resposta.status_code == 200:
            self.assertNotContains(resposta, "Cadastrar pelo Word ou PDF")

    def test_o_cliente_importado_vira_alfinete_no_mapa_da_home(self):
        url = self.importar(docx_ficha_com_endereco(), para="cliente")
        resposta = self.criar_so_cliente(url)
        cliente = Cliente.objects.get()
        self.assertEqual(resposta["Location"], f"/orcamentos/importar/cliente/{cliente.pk}/")
        self.assertTrue(cliente.publicar_no_mapa)
        self.assertTrue(cliente.no_mapa)
        endereco = cliente.endereco_principal
        self.assertEqual((endereco.latitude, endereco.longitude), (Decimal("-23.5505"), Decimal("-46.6333")))
        # A coordenada foi procurada para o endereço salvo, depois de salvar.
        self.assertEqual(self.procurar_coordenadas.call_args.args[0].pk, endereco.pk)

        pronto = self.client.get(resposta["Location"], **HOST)
        self.assertContains(pronto, "Entrou no mapa do site")
        self.assertContains(pronto, "São Paulo/SP")
        self.assertContains(pronto, "Criar um orçamento para ele")
        self.assertNotContains(pronto, "Orçamento #")

        home = self.client.get("/")
        self.assertIn(("Parque da Alegria", "São Paulo"),
                      {(p["nome"], p["cidade"]) for p in home.context["clientes_mapa"]})

    def test_sem_achar_o_endereco_o_cliente_fica_e_a_tela_diz_onde_conferir(self):
        self.procurar_coordenadas.return_value = (None, None, "")
        url = self.importar(docx_ficha_com_endereco())
        resposta = self.criar_so_cliente(url)
        cliente = Cliente.objects.get()
        self.assertTrue(cliente.publicar_no_mapa)
        self.assertFalse(cliente.no_mapa)
        pronto = self.client.get(resposta["Location"], **HOST)
        self.assertContains(pronto, "Ainda não está no mapa")
        self.assertContains(pronto, "não achei o endereço no mapa: confira")
        self.assertContains(pronto, f"/clientes/?q=Parque+da+Alegria&amp;editar={cliente.pk}")
        # A ficha abre o cadastro para editar quando chega com ?editar=.
        self.assertContains(self.client.get(f"/clientes/?editar={cliente.pk}", **HOST), 'get("editar")')
        self.assertNotIn("Parque da Alegria", {p["nome"] for p in self.client.get("/").context["clientes_mapa"]})

    def test_erro_na_busca_da_coordenada_nao_desfaz_o_cadastro(self):
        self.procurar_coordenadas.side_effect = RuntimeError("Nominatim fora do ar")
        url = self.importar(docx_ficha_com_endereco())
        with self.assertLogs("sistema_interno.importacao_word.mapa", "ERROR"):
            resposta = self.criar_so_cliente(url)
        self.assertEqual(resposta.status_code, 302)
        cliente = Cliente.objects.get()
        self.assertTrue(cliente.publicar_no_mapa)
        self.assertContains(self.client.get(resposta["Location"], **HOST), "não achei o endereço no mapa")

    def test_sem_endereco_no_documento_a_tela_diz_por_que_nao_ha_alfinete(self):
        url = self.importar(docx_com_tabela())
        resposta = self.criar_so_cliente(url)
        self.procurar_coordenadas.assert_not_called()
        self.assertContains(self.client.get(resposta["Location"], **HOST), "o documento não traz o endereço")

    def test_desligar_o_mapa_nao_publica(self):
        url = self.importar(docx_ficha_com_endereco())
        resposta = self.criar_so_cliente(url, publicar_no_mapa=False)
        cliente = Cliente.objects.get()
        self.assertFalse(cliente.publicar_no_mapa)
        self.procurar_coordenadas.assert_not_called()
        self.assertContains(self.client.get(resposta["Location"], **HOST), "Fora do mapa do site")

    def test_cliente_que_ja_existe_e_completado_e_entra_no_mapa(self):
        existente = Cliente.objects.create(nome_cliente="Parque da Alegria", telefone="(11) 97777-6655",
                                           canal_telefone=Cliente.CanalTelefone.WHATSAPP)
        url = self.importar(docx_ficha_com_endereco())
        _, envio = self.proposta_e_envio(url, modo=None)
        self.assertEqual(envio["cliente_modo"], "existente")
        resposta = self.client.post(url, formulario_de(envio, cliente_confirmado=True), **HOST)
        self.assertEqual(resposta.status_code, 302, resposta.context and resposta.context["validado"]["pendencias"])
        existente.refresh_from_db()
        self.assertEqual(Cliente.objects.count(), 1)
        self.assertTrue(existente.publicar_no_mapa)
        self.assertTrue(existente.no_mapa)
        self.assertEqual(existente.documento, "11.444.777/0001-61")

    def test_desligar_o_mapa_nao_tira_do_mapa_quem_ja_estava(self):
        existente = Cliente.objects.create(nome_cliente="Parque da Alegria", telefone="(11) 97777-6655",
                                           canal_telefone=Cliente.CanalTelefone.WHATSAPP, publicar_no_mapa=True)
        url = self.importar(docx_ficha_com_endereco())
        _, envio = self.proposta_e_envio(url, modo=None)
        self.client.post(url, formulario_de(envio, cliente_confirmado=True, publicar_no_mapa=False), **HOST)
        existente.refresh_from_db()
        self.assertTrue(existente.publicar_no_mapa)

    def test_a_tela_final_do_orcamento_tambem_diz_do_mapa(self):
        url = self.importar(docx_ficha_com_endereco())
        _, envio = self.proposta_e_envio(url)  # com o orçamento ligado
        envio["itens"] = [{"uid": "n1", "descricao": "Montagem", "produto": "", "avulsa": True,
                           "conferido": False, "quantidade": "1", "valor_unitario": "500,00"}]
        resposta = self.client.post(url, formulario_de(envio, frete="0,00"), **HOST)
        self.assertEqual(resposta.status_code, 302, resposta.context and resposta.context["validado"]["pendencias"])
        pronto = self.client.get(resposta["Location"], **HOST)
        self.assertContains(pronto, "Orçamento #")
        self.assertContains(pronto, "Entrou no mapa do site")


class MapaDoClienteImportadoTests(TestCase):
    """Onde a coordenada é procurada: o caminho do cadastro à mão, e depois o do painel."""

    def setUp(self):
        self.cliente = Cliente.objects.create(nome_cliente="Escola X", telefone="(11) 98888-7777",
                                              publicar_no_mapa=True)
        self.endereco = EnderecoCliente.objects.create(cliente=self.cliente, cep="01310-100",
                                                       endereco="Avenida Paulista", numero="1000",
                                                       cidade="São Paulo", estado="SP")

    def test_primeiro_a_consulta_rapida_do_cep(self):
        with mock.patch.object(mapa, "buscar_coordenadas_cep_rapido", return_value=(-23.56, -46.65)) as rapido, \
                mock.patch.object(EnderecoCliente, "localizar") as completo:
            self.assertEqual(mapa.procurar_coordenadas(self.endereco), (-23.56, -46.65, ""))
        rapido.assert_called_once_with("01310-100")
        completo.assert_not_called()

    def test_sem_resposta_rapida_vale_o_localizar_do_painel(self):
        def localizar(endereco):
            endereco.latitude, endereco.longitude, endereco.precisao = Decimal("-23.5"), Decimal("-46.6"), "rua"
            return True

        with mock.patch.object(mapa, "buscar_coordenadas_cep_rapido", return_value=(None, None)), \
                mock.patch.object(EnderecoCliente, "localizar", autospec=True, side_effect=localizar):
            resultado = mapa.colocar_no_mapa(self.cliente)
        self.assertEqual(resultado["no_mapa"], True)
        self.endereco.refresh_from_db()
        self.assertEqual((self.endereco.latitude, self.endereco.precisao), (Decimal("-23.5"), "rua"))

    def test_cadastro_arquivado_nao_vai_ao_mapa(self):
        self.cliente.ativo = False
        self.cliente.save()
        with mock.patch.object(mapa, "procurar_coordenadas") as procurar:
            resultado = mapa.colocar_no_mapa(self.cliente)
        procurar.assert_not_called()
        self.assertFalse(resultado["no_mapa"])
        self.assertEqual(resultado["motivo"], mapa.ARQUIVADO)


# ======================================================================
# 7c. O TEXTO LIVRE: COMO UMA IA, SEM A IA
# ======================================================================
def equipe(*nomes):
    """Usuários internos ("Marina Costa", ...) com função de Vendas."""
    usuarios = []
    for nome in nomes:
        primeiro, _, ultimo = nome.partition(" ")
        usuario = User.objects.create_user(_normalizar_usuario(nome), f"{_normalizar_usuario(nome)}@lazersport.com.br",
                                           "senha", first_name=primeiro, last_name=ultimo)
        atribuir_funcoes(usuario, ["vendas"])
        usuarios.append(usuario)
    return usuarios


def _normalizar_usuario(nome):
    return det.sem_acento(nome).replace(" ", ".")


class TextoLivreTests(_ComUsuario):
    """Contrato, carta e conversa: cada dado no campo certo, sem rótulo e sem IA."""

    def setUp(self):
        super().setUp()
        equipe("Marina Costa", "Carlos Pereira")

    def tela(self, conteudo):
        return self.proposta_e_envio(self.importar(conteudo), modo=None)

    def test_a_assinatura_de_quem_e_da_casa_nunca_vira_cliente(self):
        proposta, envio = self.tela(montar_docx(
            par("Prezada Sra. Helena Duarte,")
            + par("Segue o cadastro do Buffet Encantado, na Rua Tabapuã, 1200, Itaim Bibi, São Paulo/SP.")
            + par("Atenciosamente,") + par("Marina Costa") + par("Consultora Comercial")
            + par("(11) 97777-1111")
            + par("Vendedor: Carlos Pereira"),
        ))
        self.assertEqual(envio["nome"], "Helena Duarte")
        self.assertEqual(envio["estabelecimento"], "Buffet Encantado")
        # O celular de quem assina pela casa não é o do cliente.
        self.assertEqual(envio["telefone"], "")
        textos = " ".join(str(v) for v in envio.values())
        self.assertNotIn("Marina", textos)
        self.assertNotIn("Carlos", textos)
        self.assertEqual((envio["endereco"], envio["numero"], envio["bairro"], envio["cidade"], envio["estado"]),
                         ("Rua Tabapuã", "1200", "Itaim Bibi", "São Paulo", "SP"))
        # Sem rótulo nenhum: os dois vieram da leitura do texto, e dizem isso.
        self.assertEqual(proposta["cliente"]["nome"]["origem"], "texto")
        self.assertIn("Prezada Sra", proposta["cliente"]["nome"]["nota"])
        self.assertEqual(proposta["cliente"]["estabelecimento"]["origem"], "texto")

    def test_o_endereco_da_fabrica_nunca_e_o_do_cliente(self):
        _, envio = self.tela(montar_docx(
            par("Retirada na fábrica: Rua São Roque de Minas, 104 – Jardim Peri – São Paulo/SP")
            + par("Cliente: Escola Arco-Íris")
            + par("Entrega na Rua Augusta, 900 – Consolação – São Paulo/SP – CEP 01305-000"),
        ))
        self.assertEqual((envio["endereco"], envio["numero"], envio["bairro"], envio["cep"]),
                         ("Rua Augusta", "900", "Consolação", "01305-000"))

    def test_contrato_tira_a_qualificacao_do_nome(self):
        _, envio = self.tela(montar_docx(
            par("CONTRATANTE: HELENA DUARTE SANTOS, brasileira, casada, empresária, portadora do CPF "
                "nº 390.533.447-05, residente e domiciliada à Rua das Acácias, nº 45, apto 12, bairro "
                "Jardim Paulista, na cidade de São Paulo/SP, CEP 01427-000."),
        ))
        self.assertEqual(envio["nome"], "Helena Duarte Santos")
        self.assertEqual(envio["documento"], "390.533.447-05")
        self.assertEqual(
            (envio["endereco"], envio["numero"], envio["complemento"], envio["bairro"], envio["cidade"],
             envio["estado"], envio["cep"]),
            ("Rua das Acácias", "45", "apto 12", "Jardim Paulista", "São Paulo", "SP", "01427-000"),
        )

    def test_outras_leituras_viram_botao(self):
        url = self.importar(montar_docx(
            par("Olá! Sou a Helena Duarte, do Buffet Encantado.")
            + par("Minha sócia, Beatriz Lima, também pode responder: (11) 98888-1111.")
            + par("Meu celular: (11) 97777-2222."),
        ))
        resposta = self.client.get(url, **HOST)
        proposta = resposta.context["proposta"]
        self.assertEqual(resposta.context["envio"]["nome"], "Helena Duarte")
        outras = [a["valor"] for a in proposta["cliente"]["nome"]["alternativas"]]
        self.assertIn("Beatriz Lima", outras)
        self.assertContains(resposta, "Outras leituras:")
        self.assertContains(resposta, 'data-valor="Beatriz Lima"')
        telefones = [a["valor"] for a in proposta["cliente"]["telefone"]["alternativas"]]
        self.assertTrue(telefones)

    def test_so_o_cep_e_o_resto_vem_da_consulta(self):
        self.buscar_dados_cep.return_value = {"cep": "01310100", "rua": "Avenida Paulista",
                                              "bairro": "Bela Vista", "cidade": "São Paulo", "estado": "SP"}
        _, envio = self.tela(montar_docx(
            par("Cliente: Helena Duarte") + par("Telefone: (11) 97777-2222") + par("CEP: 01310-100") + par("Número: 1000"),
        ))
        self.assertEqual((envio["endereco"], envio["numero"], envio["bairro"], envio["cidade"], envio["estado"]),
                         ("Avenida Paulista", "1000", "Bela Vista", "São Paulo", "SP"))
        self.buscar_dados_cep.assert_called_once_with("01310-100")

    def test_brinquedos_citados_viram_a_pergunta_e_os_itens(self):
        url = self.importar(montar_docx(
            par("Cliente: Helena Duarte") + par("E-mail: helena@exemplo.com.br")
            + par("Queremos 2 camas elásticas de 3 metros e um pula pula para o sábado."),
        ))
        resposta = self.client.get(url, **HOST)
        self.assertContains(resposta, "Encontrei 2 brinquedos no documento (Cama elástica 3 m, Pula-pula).")
        self.assertContains(resposta, "Deseja criar um orçamento a partir do documento?")
        # A resposta padrão continua sendo só o cliente.
        self.assertEqual(resposta.context["envio"]["modo"], "cliente")
        itens = resposta.context["envio"]["itens"]
        self.assertEqual([(i["descricao"], i["quantidade"], i["valor_unitario"]) for i in itens],
                         [("Cama elástica 3 m", "2", "280,00"), ("Pula-pula", "1", "1.234,00")])
        valor = resposta.context["proposta"]["itens"][0]["valor_unitario"]
        self.assertEqual(valor["origem"], "catalogo")
        self.assertIn("preço do catálogo", valor["nota"])
        # "Sim": o orçamento nasce com os itens citados.
        _, envio = self.proposta_e_envio(url)
        for item in envio["itens"]:
            item["conferido"] = True
        resposta = self.client.post(url, formulario_de(envio, frete="0,00"), **HOST)
        self.assertEqual(resposta.status_code, 302, resposta.context and resposta.context["validado"]["pendencias"])
        self.assertEqual(Orcamento.objects.get().total, Decimal("1794.00"))

    def test_mesmo_nome_em_duas_cidades_a_cidade_decide_e_sem_ela_a_pessoa_escolhe(self):
        campinas = Cliente.objects.create(nome_cliente="Buffet Estrela", telefone="(19) 3333-1111")
        EnderecoCliente.objects.create(cliente=campinas, endereco="Rua A", cidade="Campinas", estado="SP")
        santos = Cliente.objects.create(nome_cliente="Buffet Estrela", telefone="(13) 3333-2222")
        EnderecoCliente.objects.create(cliente=santos, endereco="Rua B", cidade="Santos", estado="SP")
        proposta, envio = self.tela(montar_docx(
            par("Cliente: Buffet Estrela") + par("Endereço: Rua do Comércio, 10 – Centro – Santos/SP"),
        ))
        self.assertEqual(envio["cliente_id"], str(santos.pk))
        self.assertIn("mesma cidade", proposta["cliente"]["vinculo"]["motivo"])
        proposta, envio = self.tela(montar_docx(par("Cliente: Buffet Estrela") + par("E-mail: x@estrela.com.br")))
        self.assertEqual(envio["cliente_id"], "")
        self.assertEqual({c["valor"] for c in proposta["cliente"]["vinculo"]["candidatos"]},
                         {str(campinas.pk), str(santos.pk)})

    def test_cliente_achado_aparece_como_ja_cadastrado_e_so_completa(self):
        existente = Cliente.objects.create(nome_cliente="Helena Duarte", telefone="(11) 3333-0000",
                                           canal_telefone=Cliente.CanalTelefone.TELEFONE,
                                           email="helena@exemplo.com.br")
        EnderecoCliente.objects.create(cliente=existente, endereco="Rua Antiga", numero="1", cidade="São Paulo",
                                       estado="SP")
        url = self.importar(montar_docx(
            par("Cliente: Helena Duarte") + par("E-mail: helena@exemplo.com.br") + par("CPF: 390.533.447-05")
            + par("Telefone: (11) 97777-2222")
            + par("Endereço: Rua Nova, 50 – Centro – Campinas/SP"),
        ))
        resposta = self.client.get(url, **HOST)
        self.assertContains(resposta, f"Este cliente já está cadastrado: <strong>Helena Duarte</strong> (#{existente.pk})")
        _, envio = self.proposta_e_envio(url, modo=None)
        self.client.post(url, formulario_de(envio), **HOST)
        existente.refresh_from_db()
        self.assertEqual(Cliente.objects.count(), 1)
        self.assertEqual(existente.telefone, "(11) 3333-0000")  # o que o cadastro tinha fica
        self.assertEqual(existente.documento, "390.533.447-05")  # o que faltava entra
        self.assertEqual(existente.enderecos.count(), 1)
        self.assertEqual(existente.endereco_principal.endereco, "Rua Antiga")

    def test_orcamento_repetido_avisa_e_deixa_criar_mesmo_assim(self):
        cliente = Cliente.objects.create(nome_cliente="Buffet Alegria Ltda", email="contato@buffetalegria.com.br")
        anterior = Orcamento.objects.create(cliente=cliente, nome_cliente=cliente.nome_cliente)
        ItemOrcamento.objects.create(orcamento=anterior, descricao="Pula-pula", quantidade=1,
                                     valor_unitario=Decimal("1234.00"), brinquedo=self.brinquedos["Pula-pula"])
        url = self.importar(montar_docx(
            par("Cliente: Buffet Alegria Ltda") + par("E-mail: contato@buffetalegria.com.br")
            + tabela(["Descrição", "Qtd", "Valor unitário", "Total"], ["Pula-pula", "1", "R$ 1.234,00", "R$ 1.234,00"])
            + par("Frete: grátis"),
        ))
        _, envio = self.proposta_e_envio(url)
        resposta = self.client.get(url, **HOST)
        self.assertContains(resposta, f"Já existe o orçamento #{anterior.pk} com os mesmos itens")
        self.assertContains(resposta, f"/orcamentos/?editar={anterior.pk}")
        for item in envio["itens"]:
            item["conferido"] = True
        resposta = self.client.post(url, formulario_de(envio), **HOST)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("orcamento.repetido", {p["campo"] for p in resposta.context["validado"]["pendencias"]})
        dados = formulario_de(envio)
        dados["criar_mesmo_assim"] = "1"
        self.assertEqual(self.client.post(url, dados, **HOST).status_code, 302)
        self.assertEqual(Orcamento.objects.filter(cliente=cliente).count(), 2)

    def test_conversa_de_whatsapp_tira_a_fala_do_vendedor(self):
        _, envio = self.tela(montar_docx(
            par("[11/11/2026 09:14] Helena Duarte: Oi! Quero um orçamento")
            + par("[11/11/2026 09:20] Carlos Pereira: Claro, Helena! Meu número é (11) 97777-2222")
            + par("[11/11/2026 09:31] Helena Duarte: Meu e-mail é helena@exemplo.com.br"),
        ))
        self.assertEqual(envio["nome"], "Helena Duarte")
        self.assertEqual(envio["telefone"], "")
        self.assertEqual(envio["email"], "helena@exemplo.com.br")


# ======================================================================
# 7d. A DECISÃO (MODAL) E A TELA GUIADA
# ======================================================================
def docx_ficha_completa():
    """Tudo o que o cadastro pede, sem nada de orçamento: dá para criar direto."""
    return montar_docx(
        par("FICHA DE CADASTRO")
        + tabela(["Nome", "Helena Duarte"], ["CPF", "390.533.447-05"], ["Celular", "11 97777-6655"],
                 ["E-mail", "helena@exemplo.com.br"], ["CEP", "01310-100"], ["Rua", "Avenida Paulista"],
                 ["Número", "1000"], ["Bairro", "Bela Vista"], ["Cidade", "São Paulo"], ["UF", "SP"]),
    )


class TelaGuiadaTests(_ComUsuario):
    """ "Ponha um modal moderno estilo app para perguntar se quer ou não gerar
    o orçamento ou só o cliente, dê ênfase pros campos que ainda faltam". """

    def test_o_modal_abre_depois_da_leitura_com_o_resumo_e_os_dois_caminhos(self):
        url = self.importar(docx_com_tabela())
        resposta = self.client.get(url, **HOST)
        self.assertContains(resposta, 'id="decisaoImportacao" hidden data-abrir="1"')
        self.assertContains(resposta, 'role="dialog" aria-modal="true" aria-labelledby="decisaoTitulo"')
        self.assertContains(resposta, "O que fazer com este documento?")
        self.assertContains(resposta, "Cadastrar cliente e criar orçamento")
        self.assertContains(resposta, "Só cadastrar o cliente")
        # Com brinquedos no documento, o orçamento é o caminho recomendado e
        # diz o que achou.
        decisao = resposta.context["decisao"]
        self.assertTrue(decisao["orcamento"]["recomendado"])
        self.assertFalse(decisao["cliente"]["recomendado"])
        self.assertEqual(decisao["orcamento"]["itens"], 3)
        self.assertEqual(decisao["orcamento"]["total"], "1.919,00")
        self.assertContains(resposta, "Deseja criar um orçamento a partir do documento?")
        self.assertContains(resposta, '<span class="ls-imp-selo-recomendado">Recomendado</span>', count=1)
        # O resumo: cada dado com ✓ ou "falta", e de onde veio.
        linhas = {l["chave"]: l for l in decisao["linhas"]}
        self.assertEqual(linhas["nome"]["valor"], "Buffet Alegria Ltda")
        self.assertEqual(linhas["nome"]["origem"], "do documento")
        self.assertTrue(linhas["cidade"]["falta"])
        self.assertContains(resposta, '<li class="falta" data-linha="cidade">')
        # O orçamento ainda pede a conferência do produto sugerido: não há
        # "Criar agora" nele, e sim o que falta.
        self.assertFalse(decisao["orcamento"]["pronto"])
        self.assertNotContains(resposta, 'id="criarAgoraOrcamento"')
        self.assertContains(resposta, 'id="revisarOrcamento"')

    def test_tudo_lido_e_sem_alerta_cria_direto_do_modal(self):
        url = self.importar(docx_ficha_completa())
        resposta = self.client.get(url, **HOST)
        decisao = resposta.context["decisao"]
        self.assertTrue(decisao["cliente"]["pronto"])
        self.assertTrue(decisao["cliente"]["recomendado"])
        self.assertContains(resposta, 'id="criarAgoraCliente"')
        self.assertContains(resposta, "Revisar antes")
        # "Criar agora" envia o formulário como a tela abriu -- e o servidor
        # confere tudo de novo, como sempre.
        _, envio = self.proposta_e_envio(url, modo=None)
        criada = self.client.post(url, formulario_de(envio), **HOST)
        self.assertEqual(criada.status_code, 302)
        self.assertTrue(criada["Location"].startswith("/orcamentos/importar/cliente/"))

    def test_o_servidor_confere_mesmo_o_que_veio_do_modal(self):
        url = self.importar(docx_ficha_completa())
        _, envio = self.proposta_e_envio(url, modo=None)
        resposta = self.client.post(url, formulario_de(envio, nome="", telefone="", email=""), **HOST)
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(Cliente.objects.count(), 0)
        # De volta de um envio recusado, a tela não reabre a decisão.
        self.assertNotContains(resposta, 'data-abrir="1"', status_code=400)

    def test_paineis_completos_fecham_e_o_que_falta_abre(self):
        url = self.importar(docx_ficha_completa())
        resposta = self.client.get(url, **HOST)
        paineis = resposta.context["paineis"]
        self.assertFalse(paineis["cliente"]["aberto"])
        self.assertFalse(paineis["endereco"]["aberto"])
        self.assertContains(resposta, 'id="blocoCliente" data-painel="cliente">')
        self.assertEqual(paineis["cliente"]["resumo"], "Helena Duarte · CPF ✓ · WhatsApp ✓ · E-mail ✓")
        self.assertIn("São Paulo/SP", paineis["endereco"]["resumo"])
        self.assertContains(resposta, "Helena Duarte · CPF ✓ · WhatsApp ✓ · E-mail ✓")

        sem_contato = self.importar(montar_docx(par("Cliente: Helena Duarte")))
        resposta = self.client.get(sem_contato, **HOST)
        paineis = resposta.context["paineis"]
        self.assertTrue(paineis["cliente"]["aberto"])
        self.assertEqual(paineis["cliente"]["faltas"], 1)
        self.assertContains(resposta, 'id="blocoCliente" data-painel="cliente" open>')
        self.assertContains(resposta, "Falta 1")

    def test_o_progresso_lista_o_que_falta(self):
        url = self.importar(montar_docx(par("Cliente: Helena Duarte")))
        resposta = self.client.get(url, **HOST)
        self.assertContains(resposta, '<strong id="progressoTitulo">Faltam 1</strong>')
        self.assertContains(resposta, '<span id="progressoLista">Telefone ou e-mail</span>')
        self.assertContains(resposta, 'id="proximoCampo"')
        self.assertContains(resposta, "Falta preencher")
        # Com tudo preenchido, o progresso já vem como a ação verde.
        pronta = self.client.get(self.importar(docx_ficha_completa()), **HOST)
        self.assertContains(pronta, 'class="ls-panel ls-imp-progresso pronto"')
        self.assertContains(pronta, '<strong id="progressoTitulo">Tudo pronto</strong>')

    def test_cada_falta_tem_o_seu_painel(self):
        from .importacao_word import tela

        self.assertEqual(tela.painel_da_pendencia("cliente.nome"), "cliente")
        self.assertEqual(tela.painel_da_pendencia("cliente.endereco"), "endereco")
        self.assertEqual(tela.painel_da_pendencia("itens.i1.produto"), "itens")
        self.assertEqual(tela.painel_da_pendencia("orcamento.repetido"), "itens")
        self.assertEqual(tela.painel_da_pendencia("valores.frete"), "valores")
        self.assertEqual(tela.painel_da_pendencia("alerta.soma_total"), "valores")

    def test_as_condicoes_opcionais_ficam_dobradas(self):
        from .importacao_word import tela

        resposta = self.client.get(self.importar(docx_com_tabela()), **HOST)
        valores = resposta.context["paineis"]["valores"]
        self.assertFalse(valores["condicoes_abertas"])
        self.assertContains(resposta, '<details class="ls-imp-sub" id="blocoCondicoes">')
        self.assertContains(resposta, "data-resumo-condicoes")
        self.assertEqual(
            tela.resumo_das_condicoes({"validade": "2026-11-20", "forma_pagamento": "Pix", "prazo": "10 dias"}),
            "Validade 20/11/2026 · Pix · Prazo ✓",
        )
        self.assertEqual(tela.resumo_das_condicoes({}), "Validade padrão · pagamento e entrega em branco")


# ======================================================================
# 8. A TELA SEGUE O TEMA
# ======================================================================
class FolhaDaTelaTests(SimpleTestCase):

    def test_a_folha_nao_tem_cor_escrita_a_mao_e_toda_variavel_tem_dono(self):
        import re
        from pathlib import Path

        base = Path(__file__).resolve().parent / "static" / "interno"
        folha = (base / "importacao-word.css").read_text(encoding="utf-8")
        sem_comentarios = re.sub(r"/\*.*?\*/", "", folha, flags=re.S)
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", sem_comentarios), [])
        definidas = set(re.findall(r"(--[a-z0-9-]+)\s*:", (base / "interno_modern.css").read_text(encoding="utf-8")))
        usadas = set(re.findall(r"var\(\s*(--[a-z0-9-]+)\s*\)", sem_comentarios))
        self.assertEqual(sorted(usadas - definidas), [])


# ======================================================================
# AJUSTE 4: o contrato de compra e venda e a data do documento
# ======================================================================
#: Feito à semelhança do contrato da casa -- nunca o de um cliente de
#: verdade. O comprador tem o primeiro nome fora da lista do IBGE.
VENDEDOR_DO_CONTRATO = (
    "Pelo presente INSTRUMENTO PARTICULAR DE COMPRA E VENDA, e na forma da Lei, comparecem aqui, as partes, "
    "de um lado, na qualidade de fornecedor, aqui doravante denominado simplesmente VENDEDOR: Brinquedos "
    "Lazer & Sport, devidamente inscrita no CNPJ sob o n. 54.486.908/0001-86, neste ato representado por "
    "Otávio Brandão Lemos, portador da cédula de identidade RG: 27.418.905-3, residente e domiciliado na "
    "Travessa dos Ipês Roxos, n. 77, Vila Aurora, CEP: 02998-010, São Paulo, Capital; e, do outro lado, na "
    "qualidade de comprador, aqui doravante denominado simplesmente "
)


def docx_contrato(*, comprador="Kethellyn Souza Brandão", itens=(("1", "Cama elástica 3 m"), ("1", "Matrix")),
                  total="R$ 38.500,00 (trinta e oito mil e quinhentos reais)",
                  data="São Paulo,11 de novembro de 2026", com_valor=False):
    cabecalho = ["Quantidade", "Equipamento"] + (["Valor"] if com_valor else [])
    return montar_docx(
        par("INSTRUMENTO PARTICULAR DE COMPRA E VENDA DE")
        + par("EQUIPAMENTO DE ENTRETENIMENTO")
        + tabela(cabecalho, *[list(item) for item in itens])
        + ("" if com_valor else par("                                           Valor "))
        + par(VENDEDOR_DO_CONTRATO)
        + par(f"COMPRADOR {comprador}")
        + par("CPF ou CNPJ; 318.447.205-19")
        + par("Endereço completo; Rua das Acácias, 250, Centro, Ribeirão Preto/SP")
        + par("Email; comprador@exemplo.com.br")
        + par("Telefone; 16 99123-4567")
        + par("Cláusula 2ª – Pelo presente instrumento e na melhor forma do direito, o VENDEDOR vende ao "
              f"COMPRADOR o equipamento objeto deste contrato, descrito na Cláusula 1ª, no valor total {total}")
        + par("Condição de pagamento:")
        + par("5ª. . Cláusula As despesas com frete do equipamento,")
        + par("são por conta do COMPRADOR.")
        + par(data)
        + par("__________________________") + par("Proprietário") + par("Otávio Brandão Lemos")
        + par("__________________________") + par("COMPRADOR") + par(comprador),
        cabecalho=par("Brinquedos Lazer & Sport"),
        rodape=par("Rua São Roque de Minas; 104, Jardim Pery, São Paulo - SP, CNPJ: 54.486.908 / 0001-86"),
    )


def com_datas_do_arquivo(conteudo, *, criado="", salvo=""):
    """O mesmo .docx com o docProps/core.xml (quando foi criado e salvo)."""
    entrada = zipfile.ZipFile(io.BytesIO(conteudo))
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as arquivo:
        for nome in entrada.namelist():
            arquivo.writestr(nome, entrada.read(nome))
        partes = []
        if criado:
            partes.append(f'<dcterms:created xsi:type="dcterms:W3CDTF">{criado}</dcterms:created>')
        if salvo:
            partes.append(f'<dcterms:modified xsi:type="dcterms:W3CDTF">{salvo}</dcterms:modified>')
        arquivo.writestr("docProps/core.xml", (
            '<?xml version="1.0" encoding="UTF-8"?><cp:coreProperties '
            'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">' + "".join(partes) + "</cp:coreProperties>"
        ))
    return saida.getvalue()


@override_settings(EMPRESA_CNPJ="54.486.908/0001-86")
class ContratoDeCompraEVendaTests(_ComUsuario):
    """"Tinha uma cama elástica, matrix e etc em um doc, ele criou um objeto
    volume com o valor total, isso não deve acontecer"."""

    def proposta(self, conteudo=None, **parametros):
        return proposta_de(conteudo or docx_contrato(**parametros))

    def test_o_comprador_e_o_cliente_mesmo_com_primeiro_nome_fora_da_lista(self):
        envio = formulario.envio_inicial(self.proposta())
        self.assertEqual(envio["nome"], "Kethellyn Souza Brandão")
        self.assertEqual(envio["documento"], "318.447.205-19")
        self.assertEqual(envio["telefone"], "(16) 99123-4567")
        self.assertEqual(envio["email"], "comprador@exemplo.com.br")

    def test_quem_representa_a_fabrica_nunca_e_o_cliente(self):
        proposta = self.proposta()
        envio = formulario.envio_inicial(proposta)
        cliente = " | ".join(str(envio[c]) for c in (
            "nome", "estabelecimento", "contato", "documento", "telefone", "cep", "endereco", "numero",
            "bairro", "cidade",
        ))
        for marca in ("Otávio", "Ipês Roxos", "Aurora", "02998-010", "Brandão Lemos"):
            self.assertNotIn(marca, cliente)
        # Nem como "outra leitura" do nome.
        outras = [o["valor"] for o in proposta["cliente"]["nome"]["opcoes"]]
        self.assertFalse(any("Otávio" in valor for valor in outras), outras)
        # O endereço é o do comprador, escrito com ponto e vírgula no rótulo.
        self.assertEqual((envio["endereco"], envio["numero"], envio["bairro"], envio["cidade"], envio["estado"]),
                         ("Rua das Acácias", "250", "Centro", "Ribeirão Preto", "SP"))

    def test_o_lado_da_casa_atravessa_as_linhas_quebradas_do_pdf(self):
        from .importacao_word import identificar

        linhas = [
            {"id": "P1", "texto": "comparecem aqui, as partes, de um lado, na qualidade de fornecedor,", "parte": "corpo",
             "tabela": "", "linha": 0, "coluna": 0},
            {"id": "P2", "texto": "VENDEDOR: Brinquedos Lazer & Sport, inscrita no CNPJ sob o n.", "parte": "corpo",
             "tabela": "", "linha": 0, "coluna": 0},
            {"id": "P3", "texto": "neste ato representado por Otávio Brandão Lemos, residente na Travessa dos Ipês Roxos, 77,",
             "parte": "corpo", "tabela": "", "linha": 0, "coluna": 0},
            {"id": "P4", "texto": "CEP: 02998-010, São Paulo; e, do outro lado, na qualidade de comprador,",
             "parte": "corpo", "tabela": "", "linha": 0, "coluna": 0},
            {"id": "P5", "texto": "COMPRADOR Kethellyn Souza Brandão", "parte": "corpo", "tabela": "",
             "linha": 0, "coluna": 0},
        ]
        trechos = identificar.lado_da_casa(linhas)
        self.assertEqual(trechos["P2"], [(0, len(linhas[1]["texto"]))])  # "n." não fecha a frase
        self.assertEqual(trechos["P3"], [(0, len(linhas[2]["texto"]))])
        self.assertTrue(identificar.no_lado_da_casa(trechos, "P4", 0))
        self.assertFalse(identificar.no_lado_da_casa(trechos, "P4", linhas[3]["texto"].index("na qualidade")))
        self.assertNotIn("P5", trechos)

    def test_os_equipamentos_da_tabela_viram_itens_e_o_desconhecido_fica_para_escolher(self):
        proposta = self.proposta(itens=(("1", "Cama elástica 3 m"), ("1", "Matrix"), ("2", "Air Game Kids")))
        itens = proposta["itens"]
        self.assertEqual([i["original"] for i in itens], ["Cama elástica 3 m", "Matrix", "Air Game Kids"])
        self.assertEqual([i["quantidade"]["valor"] for i in itens], ["1", "1", "2"])
        # Sem valor na tabela: o preço do catálogo, marcado; o "Matrix", que o
        # catálogo não tem, fica com o nome do documento para a pessoa escolher.
        self.assertEqual(itens[0]["valor_unitario"]["valor"], "280,00")
        self.assertEqual(itens[0]["valor_unitario"]["origem"], "catalogo")
        self.assertIsNone(itens[1]["produto"]["escolhido"])
        self.assertEqual(itens[1]["descricao"]["valor"], "Matrix")
        self.assertIn("produto:i2", alertas_por_id(proposta))

    def test_o_total_da_clausula_e_o_total_e_nunca_um_item(self):
        proposta = self.proposta()
        self.assertEqual(proposta["valores"]["total"]["valor"], "38.500,00")
        # Os equipamentos vieram sem preço: o total do contrato é o valor fechado.
        self.assertEqual(proposta["valores"]["valor_final"]["valor"], "38.500,00")
        self.assertTrue(proposta["valor_final"]["explicito"])
        self.assertNotIn("soma_total", alertas_por_id(proposta))
        # Nenhuma linha do documento virou item com o total.
        valores = {i["valor_unitario"]["valor"] for i in proposta["itens"]} | {
            i["total_linha"]["valor"] for i in proposta["itens"]}
        self.assertNotIn("38.500,00", valores)
        self.assertEqual(len(proposta["itens"]), 2)
        # E o frete por conta do comprador, na cláusula, é zero no total.
        self.assertEqual(proposta["valores"]["frete"]["valor"], "0,00")
        self.assertEqual(proposta["condicoes"]["forma_envio"]["valor"], "Frete por conta do cliente")

    def test_o_modal_vai_em_passos_cliente_e_itens_com_o_que_falta(self):
        url = self.importar(docx_contrato(data="São Paulo,14 de março de 2016",
                                          itens=(("1", "Cama elástica 3 m"), ("1", "Matrix"))))
        tela = self.client.get(url, **HOST)
        # Data escrita e antiga: não pergunta; o modal começa no cliente.
        self.assertNotContains(tela, 'data-passo="data"')
        self.assertContains(tela, 'data-marca-passo="cliente"')
        self.assertContains(tela, 'data-passo="cliente"')
        self.assertContains(tela, 'data-passo="itens" aria-labelledby="passoItensTitulo" hidden')
        self.assertContains(tela, 'data-ir-passo="itens"')
        decisao = tela.context["decisao"]
        self.assertEqual([l["chave"] for l in decisao["linhas_falta"]], ["estabelecimento"])
        self.assertEqual([(i["nome"], i["faltas"]) for i in decisao["itens"]],
                         [("Cama elástica 3 m", []), ("Matrix", ["escolher o produto", "sem preço"])])
        self.assertContains(tela, "escolher o produto · sem preço")
        # A data fica na barra de cima, para trocar.
        self.assertContains(tela, 'id="campoDataDocumento" name="data_documento"')
        self.assertContains(tela, "escrito no documento")

    def test_tabela_com_valor_nao_vira_valor_final(self):
        proposta = self.proposta(itens=(("1", "Cama elástica 3 m", "R$ 280,00"), ("1", "Matrix", "R$ 12.900,00")),
                                 total="R$ 13.180,00", com_valor=True)
        self.assertEqual([i["valor_unitario"]["valor"] for i in proposta["itens"]], ["280,00", "12.900,00"])
        self.assertEqual(proposta["valores"]["total"]["valor"], "13.180,00")
        self.assertEqual(proposta["valores"]["valor_final"]["valor"], "")
        self.assertEqual([a for a in proposta["alertas"] if a["nivel"] == conferencia.NIVEL_VERMELHO], [])

    def test_frase_de_total_nunca_e_item_nem_pela_leitura_de_paragrafo(self):
        linha = {"id": "P9", "texto": "COMPRADOR o equipamento objeto deste contrato, descrito na Cláusula 1ª, "
                                      "no valor total R$ 38.500,00", "parte": "corpo", "tabela": "",
                 "linha": 0, "coluna": 0}
        self.assertEqual(det.itens_em_paragrafos([linha]), [])
        self.assertFalse(det.parece_produto("COMPRADOR o equipamento objeto deste contrato, no valor total"))
        self.assertTrue(det.parece_produto("Cama elástica 3 m com rede"))
        self.assertEqual(det.total_em_frase([linha])["valor"], Decimal("38500.00"))
        # Quebrada pelo PDF: "...no valor" / "total R$ 38.500,00 (...)".
        quebrada = [dict(linha, texto="ao COMPRADOR o equipamento, descrito na Cláusula 1ª, no valor"),
                    dict(linha, id="P10", texto="total R$ 38.500,00 (trinta e oito mil e quinhentos reais)")]
        lido = det.total_em_frase(quebrada)
        self.assertEqual((lido["valor"], lido["fonte"]["id"]), (Decimal("38500.00"), "P10"))
        # "Pula-pula no valor de R$ 300,00", fora de contrato, é preço de item.
        self.assertIsNone(det.total_em_frase([dict(linha, texto="Pula-pula no valor de R$ 300,00")]))

    def test_linha_que_nao_e_item_nao_entra_por_caminho_nenhum(self):
        def bruto(contexto, descricao, valor):
            dinheiro = (Decimal(valor), {"id": "P1", "texto": ""}, valor) if valor else None
            return {"contexto": contexto, "descricao": ((descricao, {"id": "P1"}, descricao), None),
                    "valor_unitario": (dinheiro, None), "total_linha": (None, None)}

        alertas = []
        lista = [
            bruto("tabela", "Cama elástica 3 m", "280.00"),
            bruto("ia", "Matrix", "38500.00"),  # o total do documento, fora da tabela
            bruto("paragrafo", "o equipamento objeto deste contrato, no valor total", "38500.00"),
            bruto("mencao", "Air Game Kids", ""),
        ]
        ficam = conferencia._sem_linhas_que_nao_sao_item(lista, alertas, total_doc=Decimal("38500.00"))
        self.assertEqual([conferencia._texto_do_bruto(b) for b in ficam], ["Cama elástica 3 m", "Air Game Kids"])
        self.assertEqual([a["tipo"] for a in alertas], ["nao_e_item", "nao_e_item"])

    def test_no_contrato_de_equipamento_o_brinquedo_ganha_da_peca(self):
        produtos = [
            {"id": "b:1", "nome": "Strike Kids Boliche", "grupo": "Brinquedos", "preco": Decimal("15000"), "ordem": 0},
            {"id": "r:1", "nome": "Bola de Boliche Kids", "grupo": "Peças de reposição", "preco": Decimal("39.90"),
             "ordem": 2},
        ]
        for produto in produtos:
            produto["chave"] = catalogo._normalizar(produto["nome"])
        self.assertEqual(catalogo.casar_item("Boliche kids", produtos)["escolhido"], "r:1")
        self.assertEqual(catalogo.casar_item("Boliche kids", produtos, preferir_brinquedos=True)["escolhido"], "b:1")
        # A peça só ganha com o nome igual ao do catálogo.
        self.assertEqual(
            catalogo.casar_item("Bola de boliche kids", produtos, preferir_brinquedos=True)["escolhido"], "r:1",
        )

    def test_a_tabela_de_duas_colunas_do_pdf_e_tabela_de_itens(self):
        pagina = "\n".join([
            "INSTRUMENTO PARTICULAR DE COMPRA E VENDA DE",
            "",
            "Quantidade                                               Equipamento",
            "",
            "1                                                        Cama elástica 3 m",
            "",
            "2                                                        Air Game Kids",
            "",
            "                                                         Valor",
            "Pelo presente INSTRUMENTO PARTICULAR DE COMPRA E VENDA, e na forma da Lei,",
            "Nome          Marina Souza",
        ])
        linhas = leitor._linhas_do_pdf([pagina])
        celulas = {(l["linha"], l["coluna"]): l["texto"] for l in linhas if l["tabela"] == "T1"}
        self.assertEqual(celulas, {(1, 1): "Quantidade", (1, 2): "Equipamento", (2, 1): "1",
                                   (2, 2): "Cama elástica 3 m", (3, 1): "2", (3, 2): "Air Game Kids"})
        # "Valor" sozinho embaixo não grudou no último item; a ficha de duas
        # colunas continua sendo rótulo e valor.
        self.assertIn("Valor", [l["texto"] for l in linhas if not l["tabela"]])
        self.assertEqual([l["texto"] for l in linhas if l["tabela"] == "T2"], ["Nome", "Marina Souza"])


class DataDoDocumentoTests(_ComUsuario):
    """"Puxar a informação da data e hora do documento; se for menos que 3
    dias do atual, você deve pedir pra quando é a data, pq tem documento de
    2016, 2012 para a gente pôr"."""

    def test_as_datas_escritas_que_dizem_quando_o_documento_foi_feito(self):
        def linha(texto):
            return {"id": "P1", "texto": texto, "parte": "corpo", "tabela": "", "linha": 0, "coluna": 0}

        for texto, data in (
            ("São Paulo,11 de novembro de 2026", "2026-11-11"),
            ("São Paulo, 14 de março de 2016.", "2016-03-14"),
            ("Guarulhos,09/11/2026", "2026-11-09"),
            ("Firmado em São Paulo, aos 02 dias do mês de julho de 2012.", "2012-07-02"),
            ("Data: 05/04/2016", "2016-04-05"),
        ):
            with self.subTest(texto=texto):
                self.assertEqual([d["data"].isoformat() for d in det.datas_escritas([linha(texto)])], [data])
        # A data do evento ou da validade não é a do documento.
        self.assertEqual(det.datas_escritas([linha("Entrega até 20/11/2026")]), [])

    def test_as_datas_do_arquivo_word_e_pdf(self):
        conteudo = com_datas_do_arquivo(docx_contrato(), criado="2013-12-23T23:15:00Z", salvo="2026-11-12T12:56:00Z")
        self.assertEqual(leitor.datas_do_arquivo(conteudo, "docx"),
                         [{"data": "2013-12-23", "origem": "criado"}, {"data": "2026-11-12", "origem": "salvo"}])
        from pypdf import PdfReader, PdfWriter

        escritor = PdfWriter()
        for pagina in PdfReader(io.BytesIO(montar_pdf())).pages:
            escritor.add_page(pagina)
        escritor.add_metadata({"/CreationDate": "D:20160314101500-03'00'", "/ModDate": "D:20261112125600Z"})
        pdf = io.BytesIO()
        escritor.write(pdf)
        self.assertEqual(leitor.datas_do_arquivo(pdf.getvalue(), "pdf"),
                         [{"data": "2016-03-14", "origem": "criado"}, {"data": "2026-11-12", "origem": "salvo"}])
        self.assertEqual(leitor.datas_do_arquivo(b"lixo", "pdf"), [])

    def data(self, texto_da_data, *, datas_arquivo=(), escolhida=""):
        leitura = {"arquivo": "c.docx", "linhas": linhas_de(docx_contrato(data=texto_da_data)),
                   "ia": {"usada": False}, "datas_arquivo": list(datas_arquivo), "data_escolhida": escolhida}
        return conferencia.montar_proposta(leitura)["data"]

    def test_quando_perguntar(self):
        hoje = timezone.localdate()
        antiga = self.data("São Paulo,14 de março de 2016")
        self.assertEqual((antiga["valor"], antiga["perguntar"]), ("2016-03-14", False))
        # De agora (menos de três dias): pergunta, com a data escrita sugerida.
        recente = self.data(f"São Paulo, {_data_br(-1)}")
        self.assertEqual((recente["valor"], recente["perguntar"]),
                         ((hoje - timedelta(days=1)).isoformat(), True))
        self.assertIn("é de agora", recente["motivo"])
        # Sem data escrita: pergunta, e a data do ARQUIVO é só opção -- nunca
        # entra sozinha (o modelo salvo de novo hoje diz "hoje").
        sem = self.data("Assinado pelas partes.", datas_arquivo=[{"data": "2013-12-23", "origem": "criado"}])
        self.assertEqual((sem["valor"], sem["perguntar"]), ("", True))
        self.assertEqual([(o["valor"], o["origem"]) for o in sem["opcoes"]],
                         [("2013-12-23", "arquivo criado"), (hoje.isoformat(), "hoje")])
        # Respondida, vale a resposta e não pergunta mais.
        respondida = self.data("Assinado pelas partes.", escolhida="2012-07-02")
        self.assertEqual((respondida["valor"], respondida["perguntar"], respondida["escolhida"]),
                         ("2012-07-02", False, True))

    def test_o_modal_pergunta_primeiro_e_a_resposta_fica_na_sessao(self):
        url = self.importar(com_datas_do_arquivo(docx_contrato(data="Assinado pelas partes."),
                                                 salvo=timezone.now().strftime("%Y-%m-%dT%H:%M:%SZ")))
        tela = self.client.get(url, **HOST)
        self.assertContains(tela, 'data-passo="data"')
        self.assertContains(tela, "De quando é este documento?")
        self.assertContains(tela, 'name="data_opcao"')
        self.assertContains(tela, "arquivo salvo")
        self.assertContains(tela, 'id="dataOutra" name="data_outra"')
        # A data no futuro (ou inválida) não entra: o toast diz o que fazer.
        resposta = self.client.post(url, {"action": "data", "data_outra": "2999-01-01"}, **HOST)
        self.assertRedirects(resposta, url, fetch_redirect_response=False)
        self.assertEqual(self.client.get(url, **HOST).context["proposta"]["data"]["valor"], "")
        # Um toque: fica guardada, a tela volta no passo do cliente.
        resposta = self.client.post(url, {"action": "data", "data_opcao": "2012-07-02"}, **HOST)
        self.assertRedirects(resposta, url, fetch_redirect_response=False)
        tela = self.client.get(url, **HOST)
        self.assertNotContains(tela, 'data-passo="data"')
        self.assertContains(tela, 'data-passo="cliente"')
        self.assertEqual(tela.context["envio"]["data_documento"], "2012-07-02")
        self.assertContains(tela, 'id="campoDataDocumento" name="data_documento"\n                   value="2012-07-02"')

    def test_o_orcamento_e_o_cliente_guardam_a_data_e_a_validade_conta_dela(self):
        url = self.importar(docx_contrato(data="São Paulo,14 de março de 2016"))
        proposta, envio = self.proposta_e_envio(url)
        self.assertEqual(envio["data_documento"], "2016-03-14")
        for item in envio["itens"]:
            item["conferido"] = True
            if not item["produto"]:
                item["avulsa"] = True
                item["valor_unitario"] = "12.900,00"
        resposta = self.client.post(url, formulario_de(envio), **HOST)
        self.assertEqual(resposta.status_code, 302, resposta.context and resposta.context["validado"]["pendencias"])
        orcamento = Orcamento.objects.get()
        self.assertEqual(orcamento.data_documento.isoformat(), "2016-03-14")
        # Os 5 dias do padrão contam da data do documento: o contrato de 2016
        # não vira uma proposta de hoje.
        self.assertEqual(orcamento.validade.isoformat(), "2016-03-19")
        self.assertEqual(orcamento.cliente.cliente_desde.isoformat(), "2016-03-14")
        self.assertEqual(orcamento.valor_final, Decimal("38500.00"))
        # A lista mostra a data do documento; a ficha do cliente, desde quando.
        lista = self.client.get("/orcamentos/", **HOST)
        self.assertContains(lista, "Documento de 14/03/2016")
        clientes = self.client.get("/clientes/", **HOST)
        self.assertContains(clientes, "Cliente desde 14/03/2016")

    def test_documento_mais_antigo_puxa_o_cliente_desde_para_tras(self):
        cliente = Cliente.objects.create(nome_cliente="Kethellyn Souza Brandão", documento="318.447.205-19",
                                         cliente_desde=timezone.localdate())
        url = self.importar(docx_contrato(data="Firmado aos 02 dias do mês de julho de 2012."))
        _, envio = self.proposta_e_envio(url, modo="cliente")
        self.assertEqual(envio["cliente_modo"], "existente")
        resposta = self.client.post(url, formulario_de(envio, modo="cliente", cliente_confirmado=True), **HOST)
        self.assertEqual(resposta.status_code, 302, resposta.context and resposta.context["validado"]["pendencias"])
        cliente.refresh_from_db()
        self.assertEqual(cliente.cliente_desde.isoformat(), "2012-07-02")

    def test_o_servidor_confere_a_data(self):
        url = self.importar(docx_contrato(data="Assinado pelas partes."))
        proposta, envio = self.proposta_e_envio(url)
        # Sem data, o orçamento não sai; só o cliente, sai.
        validado = formulario.validar(proposta, dict(envio, data_documento=""))
        self.assertIn("documento.data", {p["campo"] for p in validado["pendencias"]})
        validado = formulario.validar(proposta, dict(envio, modo="cliente", data_documento=""))
        self.assertNotIn("documento.data", {p["campo"] for p in validado["pendencias"]})
        futura = (timezone.localdate() + timedelta(days=3)).isoformat()
        validado = formulario.validar(proposta, dict(envio, data_documento=futura))
        self.assertIn("documento.data", {p["campo"] for p in validado["pendencias"]})
        # Documento antigo: validade de antes de hoje vale (é o registro), mas
        # não antes da data do documento.
        validado = formulario.validar(proposta, dict(envio, data_documento="2016-03-14", validade="2016-03-20"))
        self.assertNotIn("condicoes.validade", {p["campo"] for p in validado["pendencias"]})
        validado = formulario.validar(proposta, dict(envio, data_documento="2016-03-14", validade="2016-03-01"))
        self.assertIn("condicoes.validade", {p["campo"] for p in validado["pendencias"]})
