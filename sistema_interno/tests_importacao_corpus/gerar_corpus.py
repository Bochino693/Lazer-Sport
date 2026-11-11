"""Gera o corpus de orçamentos de verdade usado em tests_importacao_corpus.py.

POR QUE ARQUIVOS DE VERDADE. Os testes de unidade montam o XML mínimo do
Word à mão, e isso prova a regra -- mas não prova que um .docx salvo pelo
Word (ou pelo LibreOffice), com estilos, cabeçalho, rodapé e tabela com
borda, chega inteiro nos campos certos. Este corpus é o que a equipe
manda de verdade: tabela de itens, texto corrido, dados do cliente no
cabeçalho, ficha de cadastro sem itens, desconto com valor final
negociado, e o PDF de um deles.

COMO RODAR (fora do servidor; nada disto é dependência do projeto):

    python -m venv /tmp/venv-corpus
    /tmp/venv-corpus/bin/pip install python-docx==1.1.2
    /tmp/venv-corpus/bin/python sistema_interno/tests_importacao_corpus/gerar_corpus.py
    soffice --headless --convert-to pdf --outdir sistema_interno/tests_importacao_corpus \\
        sistema_interno/tests_importacao_corpus/01-tabela-buffet-alegria.docx
    mv sistema_interno/tests_importacao_corpus/01-tabela-buffet-alegria.pdf \\
       sistema_interno/tests_importacao_corpus/06-pdf-tabela-buffet-alegria.pdf

O valor esperado de cada campo está em `esperado.json`, escrito à mão --
não gerado a partir da leitura, que é justamente o que se quer conferir.
"""

from pathlib import Path

from docx import Document
from docx.shared import Pt

PASTA = Path(__file__).resolve().parent

RODAPE_DA_EMPRESA = (
    "Lazer & Sport Brinquedos Ltda — CNPJ 54.486.908/0001-86",
    "Endereço: Av. Industrial, 900 – Cumbica – Guarulhos/SP – CEP 07220-000",
    "(11) 96056-3135 · contato@lazersport.com · www.lazersport.com.br",
)


def novo(cabecalho=(), rodape=RODAPE_DA_EMPRESA):
    documento = Document()
    documento.styles["Normal"].font.name = "Arial"
    documento.styles["Normal"].font.size = Pt(10.5)
    secao = documento.sections[0]
    if cabecalho:
        secao.header.paragraphs[0].text = cabecalho[0]
        for linha in cabecalho[1:]:
            secao.header.add_paragraph(linha)
    if rodape:
        secao.footer.paragraphs[0].text = rodape[0]
        for linha in rodape[1:]:
            secao.footer.add_paragraph(linha)
    return documento


def tabela(documento, linhas, mesclar_resumo=0):
    colunas = len(linhas[0])
    grade = documento.add_table(rows=0, cols=colunas)
    grade.style = "Table Grid"
    for linha in linhas:
        celulas = grade.add_row().cells
        if len(linha) == 2 and colunas > 2:
            # Linha de resumo: o rótulo ocupa as colunas da esquerda.
            primeira = celulas[0].merge(celulas[colunas - 2])
            primeira.text = linha[0]
            celulas[colunas - 1].text = linha[1]
            continue
        for celula, texto in zip(celulas, linha):
            celula.text = texto
    return grade


def paragrafos(documento, *linhas):
    for linha in linhas:
        documento.add_paragraph(linha)


# ---------------------------------------------------------------- 01
d = novo()
paragrafos(
    d,
    "PROPOSTA COMERCIAL Nº 118/2026",
    "Guarulhos, 09/11/2026.",
    "À",
    "Buffet Alegria",
    "CNPJ: 11.444.777/0001-61",
    "A/C: Marina Souza",
    "Telefone: (11) 98765-4321 (WhatsApp)",
    "E-mail: contato@buffetalegria.com.br",
    "Endereço: Rua das Palmeiras, 45, Sala 3 – Centro – Guarulhos/SP – CEP 07010-020",
    "Prezados, segue nossa proposta para fornecimento dos equipamentos abaixo:",
)
tabela(d, [
    ("Item", "Descrição", "Qtd.", "Valor unitário", "Valor total"),
    ("1", "Cama elástica 3 m com rede de proteção", "2", "R$ 2.800,00", "R$ 5.600,00"),
    ("2", "Pula-pula", "1", "R$ 1.234,00", "R$ 1.234,00"),
    ("3", "Air Game Kids", "1", "R$ 18.000,00", "R$ 18.000,00"),
    ("Subtotal", "R$ 24.834,00"),
    ("Frete (entrega e montagem)", "R$ 450,00"),
    ("Total", "R$ 25.284,00"),
])
paragrafos(
    d,
    "Condições de pagamento: 50% na aprovação e 50% na entrega, via PIX.",
    "Forma de envio: entrega e montagem pela equipe Lazer & Sport.",
    "Prazo de entrega: 25 dias úteis após a aprovação.",
    "Validade da proposta: 15 dias.",
    "Garantia: 12 meses contra defeitos de fabricação.",
    "Atenciosamente,",
    "Equipe Comercial",
)
d.save(PASTA / "01-tabela-buffet-alegria.docx")

# ---------------------------------------------------------------- 02
d = novo(rodape=())
paragrafos(
    d,
    "ORÇAMENTO 121/2026",
    "São Paulo, 9 de novembro de 2026.",
    "Cliente: Escola Pequeno Príncipe",
    "Responsável: Juliana Ramos",
    "CNPJ: 11.222.333/0001-81",
    "Telefone: 11 98877 6655",
    "E-mail: compras@pequenoprincipe.com.br",
    "Endereço: Rua das Flores, 120, apto 12 - Vila Mariana - São Paulo - SP - 04101000",
    "Itens do orçamento:",
    "2x Cama elástica 3m – R$ 2.800,00 cada",
    "1x Pula-pula – R$ 1.234,00",
    "3x Piscina de bolinhas – R$ 450,00 cada – total R$ 1.350,00",
    "Frete: R$ 350,00",
    "Total: R$ 8.534,00",
    "Pagamento: boleto em 3 parcelas",
    "Envio: transportadora",
    "Validade: 10 dias",
    "Observações: montagem inclusa no local do evento.",
    "Lazer & Sport Brinquedos – (11) 96056-3135 – contato@lazersport.com",
)
d.save(PASTA / "02-texto-livre-escola.docx")

# ---------------------------------------------------------------- 03
d = novo(cabecalho=(
    "Cliente: Condomínio Jardim das Flores · CNPJ 33.000.167/0001-01",
    "Síndico: Paulo Mendes · Tel.: (11)3333-4444 · sindico@jardimdasflores.com.br",
    "Endereço: Av. das Acácias, 300 – Jardim Bela Vista – Santo André/SP – CEP 09040200",
))
paragrafos(d, "Proposta para instalação de playground", "Santo André, 10/11/2026.")
tabela(d, [
    ("Descrição", "Quantidade", "Preço unitário", "Total"),
    ("Brinquedão Modelo 3", "1", "R$ 9.000,00", "R$ 9.000,00"),
    ("Tobogã inflável 6 m", "1", "R$ 3.500,00", "R$ 3.500,00"),
    ("Total", "R$ 12.500,00"),
])
paragrafos(d, "Frete: grátis", "Forma de pagamento: Pix", "Validade: 30/11/2026")
d.save(PASTA / "03-cabecalho-condominio.docx")

# ---------------------------------------------------------------- 04
d = novo()
paragrafos(d, "FICHA DE CADASTRO DE CLIENTE", "Preenchida em 10/11/2026.")
tabela(d, [
    ("Nome", "Marina Souza"),
    ("Empresa", "Festas da Marina"),
    ("CPF", "529.982.247-25"),
    ("Celular", "+55 11 97777-6655"),
    ("E-mail", "marina@festasdamarina.com.br"),
    ("CEP", "01310-100"),
    ("Rua", "Avenida Paulista"),
    ("Número", "1000"),
    ("Complemento", "Conjunto 42"),
    ("Bairro", "Bela Vista"),
    ("Cidade", "São Paulo"),
    ("UF", "SP"),
])
d.save(PASTA / "04-ficha-cadastro-marina.docx")

# ---------------------------------------------------------------- 05
d = novo()
paragrafos(
    d,
    "Rio de Janeiro, 10 de novembro de 2026.",
    "Cliente: Ricardo Alves",
    "Estabelecimento: Arena Kids Diversões",
    "CPF: 111.444.777-35",
    "WhatsApp: (21) 99876-5432",
    "E-mail: ricardo@arenakids.com.br",
    "Endereço: Rua Voluntários da Pátria, 190 – Botafogo – Rio de Janeiro/RJ – CEP 22270-010",
)
tabela(d, [
    ("Descrição", "Qtd", "Unitário", "Total"),
    ("Brinquedão Modelo 3", "1", "9300,00", "9300,00"),
    ("Piscina de bolinhas", "2", "450,00", "900,00"),
])
paragrafos(
    d,
    "Subtotal: R$ 10.200,00",
    "Desconto: R$ 500,00",
    "Total: R$ 9.700,00",
    "Valor final negociado: R$ 9.500,00",
    "Pagamento: 50% de entrada e 50% na entrega",
    "Forma de envio: transportadora",
    "Validade: 20 dias",
    "Observações: inclui treinamento da equipe do cliente.",
)
d.save(PASTA / "05-desconto-valor-final.docx")

print("ok")
