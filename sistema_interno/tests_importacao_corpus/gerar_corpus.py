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

Os documentos 07 a 13 (AJUSTE 2 do LEIA-ME, item 71) não têm rótulos: um
contrato, um e-mail assinado por alguém da equipe, uma proposta com o
endereço da fábrica e o do cliente, um pedido que só cita os brinquedos, o
cliente que já está cadastrado, o orçamento repetido e uma conversa de
WhatsApp colada no Word. Rodar o script inteiro refaz todos (o conteúdo é
o mesmo; muda só a data dentro do zip).
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

# ======================================================================
# AJUSTE 2: DOCUMENTOS SEM RÓTULOS -- contrato, carta, conversa
# ======================================================================
# ---------------------------------------------------------------- 07
d = novo(rodape=())
paragrafos(
    d,
    "CONTRATO DE LOCAÇÃO DE BRINQUEDOS Nº 045/2026",
    "CONTRATANTE: BUFFET SONHO MÁGICO LTDA, pessoa jurídica de direito privado, inscrita no CNPJ sob o "
    "nº 45.678.901/0001-75, com sede na Rua Doutor Arnaldo, nº 1500, Sala 2, bairro Sumaré, na cidade de "
    "São Paulo/SP, CEP 01255-000, neste ato representada por sua sócia administradora, Patrícia Gomes "
    "Ribeiro, brasileira, empresária, telefone (11) 99123-4567, e-mail patricia@sonhomagico.com.br.",
    "CONTRATADA: LAZER & SPORT BRINQUEDOS LTDA, inscrita no CNPJ sob o nº 54.486.908/0001-86, com sede na "
    "Av. Industrial, 900, Cumbica, Guarulhos/SP, CEP 07220-000.",
    "CLÁUSULA PRIMEIRA – DO OBJETO",
    "O presente contrato tem por objeto a locação de 1 (um) Pula-pula e 2 (duas) Piscinas de bolinhas "
    "para o evento do dia 20/11/2026.",
    "CLÁUSULA SEGUNDA – DO VALOR",
    "Pelo objeto deste contrato, a CONTRATANTE pagará o valor combinado em proposta, via Pix.",
    "São Paulo, 10 de novembro de 2026.",
    "_______________________________",
    "Patrícia Gomes Ribeiro",
    "Buffet Sonho Mágico Ltda",
    "_______________________________",
    "Carlos Pereira",
    "Lazer & Sport Brinquedos",
)
d.save(PASTA / "07-contrato-buffet.docx")

# ---------------------------------------------------------------- 08
d = novo(rodape=())
paragrafos(
    d,
    "De: Marina Costa <marina.costa@lazersport.com.br>",
    "Para: Ana Paula Ferreira <anapaula@espacoalegria.com.br>",
    "Assunto: Cadastro – Espaço Alegria Festas",
    "Prezada Sra. Ana Paula Ferreira,",
    "Conforme conversamos, vou cadastrar o Espaço Alegria Festas, na Rua Maria Antônia, 300, Vila Buarque, "
    "São Paulo - SP, CEP 01222-010.",
    "Anotei o seu CPF 390.533.447-05 e o telefone (11) 98123-4567 para o contato.",
    "Atenciosamente,",
    "Marina Costa",
    "Consultora Comercial",
    "(11) 97777-1111",
)
d.save(PASTA / "08-email-assinatura-interna.docx")

# ---------------------------------------------------------------- 09
d = novo(cabecalho=(
    "LAZER & SPORT BRINQUEDOS",
    "Rua São Roque de Minas, 104 – Jardim Peri – São Paulo/SP – CEP 02679-110",
), rodape=())
paragrafos(
    d,
    "Proposta 077/2026",
    "Escola Infantil Pequenos Passos",
    "CNPJ: 98.765.432/0001-98",
    "Responsável: Fernanda Lima Duarte",
    "Celular: 11 9 8456-1234",
    "Retirada e devolução na fábrica: Rua São Roque de Minas, 104 – Jardim Peri – São Paulo/SP.",
    "Local do evento: Avenida Brigadeiro Faria Lima, 2000, 5º andar – Jardim Paulistano – São Paulo/SP – "
    "CEP 01452-000",
    "1x Cama elástica 3m – R$ 2.800,00",
    "Total: R$ 2.800,00",
)
d.save(PASTA / "09-fabrica-e-cliente.docx")

# ---------------------------------------------------------------- 10
d = novo(rodape=())
paragrafos(
    d,
    "Pedido de orçamento",
    "Olá! Sou o Ricardo Nunes, do Clube Recreativo Vila Nova.",
    "Gostaria de um orçamento para alugar duas camas elásticas de 3 metros, um Air Game Kids e o Strike "
    "Kids para a festa de fim de ano do clube.",
    "Nosso endereço é Rua Coronel Oscar Porto, 800 – Paraíso, São Paulo/SP, CEP 04003-004.",
    "Meu WhatsApp: (11) 99555-8888.",
    "Obrigado,",
    "Ricardo Nunes",
    "Clube Recreativo Vila Nova",
)
d.save(PASTA / "10-brinquedos-sem-preco.docx")

# ---------------------------------------------------------------- 11
d = novo(rodape=())
paragrafos(
    d,
    "Condomínio Parque das Árvores — Administração",
    "Aos cuidados de: Sr. Roberto Almeida (síndico)",
    "Telefone: 11 3456 7890",
    "E-mail: administracao@parquedasarvores.com.br",
    "Av. das Árvores, 500 – Morumbi – São Paulo/SP – CEP 05650-000",
    "Solicitamos a visita técnica para avaliação do playground do condomínio.",
)
d.save(PASTA / "11-cliente-ja-cadastrado.docx")

# ---------------------------------------------------------------- 12
d = novo()
paragrafos(d, "ORÇAMENTO 130/2026", "Cliente: Buffet Alegria", "E-mail: contato@buffetalegria.com.br")
tabela(d, [
    ("Descrição", "Qtd", "Valor unitário", "Total"),
    ("Pula-pula", "1", "R$ 1.234,00", "R$ 1.234,00"),
    ("Air Game Kids", "1", "R$ 18.000,00", "R$ 18.000,00"),
    ("Total", "R$ 19.234,00"),
])
paragrafos(d, "Frete: grátis", "Pagamento: Pix")
d.save(PASTA / "12-orcamento-repetido.docx")

# ---------------------------------------------------------------- 13
d = novo(rodape=())
paragrafos(
    d,
    "[11/11/2026 09:14] Juliana Martins: Bom dia! Vi o Instagram de vocês",
    "[11/11/2026 09:15] Juliana Martins: Quero fazer orçamento de 1 pula pula e 2 piscinas de bolinha pra festa da minha filha",
    "[11/11/2026 09:20] Carlos Pereira: Bom dia, Juliana! Claro. Me passa seu nome completo, CPF e endereço?",
    "[11/11/2026 09:31] Juliana Martins: Juliana Martins Rocha, CPF 714.602.380-01",
    "[11/11/2026 09:32] Juliana Martins: Rua Aurora, 155 apto 34, Santa Ifigênia, São Paulo SP, 01209-001",
    "[11/11/2026 09:33] Juliana Martins: meu email é ju.martins@gmail.com",
    "[11/11/2026 09:35] Carlos Pereira: Perfeito! Te mando já. Qualquer coisa meu número é (11) 97777-2222",
)
d.save(PASTA / "13-conversa-whatsapp.docx")

# ======================================================================
# 14 a 17: o contrato de compra e venda da casa (AJUSTE 4, LEIA-ME 71).
# Feitos à semelhança do modelo de verdade -- NUNCA o contrato de um
# cliente, que é dado particular: comprador e documentos são inventados.
# A estrutura é a do modelo: o cabeçalho "Brinquedos Lazer & Sport", o
# rodapé com o endereço e o CNPJ da fábrica, a tabela "Quantidade |
# Equipamento" (às vezes com "Valor"), o "Valor" que boia sozinho embaixo
# da tabela de duas colunas, o parágrafo do VENDEDOR com o representante
# da fábrica e o endereço residencial dele, os rótulos com ponto e vírgula
# ("CPF ou CNPJ; ..."), o total na cláusula 2ª, a data de carta sem espaço
# depois da vírgula e as assinaturas (Proprietário / COMPRADOR).
# O 15 é o PDF do 14: soffice --headless --convert-to pdf, como o 06.
# ======================================================================
VENDEDOR = (
    "Pelo presente INSTRUMENTO PARTICULAR DE COMPRA E VENDA, e na forma da Lei, comparecem aqui, as partes, "
    "de um lado, na qualidade de fornecedor, aqui doravante denominado simplesmente VENDEDOR: Brinquedos "
    "Lazer & Sport, razão social Fábrica de Brinquedos Lazer & Sport Oficial – LTDA, devidamente inscrita no "
    "CNPJ sob o n. 54.486.908/0001-86, com sede na Rua São Roque de Minas, n. 104, Jardim Peri, São Paulo, "
    "Capital, neste ato representado por Otávio Brandão Lemos, portador da cédula de identidade RG: "
    "27.418.905-3, residente e domiciliado na Travessa dos Ipês Roxos, n. 77, Vila Aurora, CEP: 02998-010, São "
    "Paulo, Capital; e, do outro lado, na qualidade de comprador, aqui doravante denominado simplesmente "
)


def contrato(nome, comprador, cpf, endereco, email, telefone, itens, valor_total, data, com_valor=False):
    d = novo(cabecalho=("Brinquedos Lazer & Sport",), rodape=(
        "Rua São Roque de Minas; 104, Jardim Pery, São Paulo - SP, CEP: 02679-110 1 "
        "Fone: (11) 96056-3135  / CNPJ: 54.486.908 / 0001-86",
    ))
    paragrafos(d, "INSTRUMENTO PARTICULAR DE COMPRA E VENDA DE", "EQUIPAMENTO DE ENTRETENIMENTO")
    tabela(d, [("Quantidade", "Equipamento") + (("Valor",) if com_valor else ())] + itens)
    if not com_valor:
        paragrafos(d, "                                           Valor ")
    paragrafos(
        d,
        VENDEDOR,
        f"COMPRADOR {comprador}",
        f"CPF ou CNPJ; {cpf}",
        f"Endereço completo; {endereco}",
        f"Email; {email}",
        f"Telefone; {telefone}",
        "DO OBJETO DO CONTRATO",
        "Cláusula 1ª. O presente instrumento tem como objeto equipamento de entretenimento, conforme "
        "características da imagem abaixo, sendo o VENDEDOR o único proprietário do referido equipamento, vejamos: ",
        " Cláusula 2ª – Pelo presente instrumento e na melhor forma do direito, o VENDEDOR vende ao COMPRADOR o "
        "equipamento objeto deste contrato, descrito na Cláusula 1ª, no valor total " + valor_total,
        "que deverá ser pago da seguinte forma:",
        "Condição de pagamento:",
        "Conforme negociação entre as partes, o pagamento será realizado da seguinte forma: 50% de entrada e o "
        "restante na entrega.",
        "DAS OBRIGAÇÕES E GARANTIAS",
        "Cláusula 3ª. O VENDEDOR obriga-se a entregar, o equipamento descrito na Cláusula 1ª, na data  45 dias "
        "úteis atos a confirmação do pagamento.",
        "Cláusula 4ª. O equipamento tem garantia de 90 dias contra defeito de fabricação.",
        "5ª. . Cláusula As despesas com frete do equipamento,",
        "são por conta do COMPRADOR.",
        # Os títulos de seção do modelo, cada um sozinho na linha: "DA
        # MULTA" logo depois de "...do COMPRADOR." já virou o nome do
        # cliente ("Da Multa"). Nunca é nome.
        "DA MULTA",
        "Cláusula 6ª. A desistência depois da produção implica multa de 30% do valor total.",
        "DA INADIMPLENCIA",
        "Cláusula 7ª. O atraso no pagamento acarreta juros de 1% ao mês.",
        "DO FORO",
        "Cláusula 8ª. Fica eleito o foro da Comarca de São Paulo.",
        "Por estarem assim justos e contratados, firmam o presente instrumento em duas vias de igual teor na "
        "presença de duas testemunhas.",
        data,
        "__________________________", "Proprietário", "Otávio Brandão Lemos",
        "__________________________", "COMPRADOR", comprador,
        "__________________________", "TESTEMUNHA",
    )
    d.save(PASTA / nome)


# ---------------------------------------------------------------- 14
# O comprador com o primeiro nome fora da lista do IBGE, escrito como no
# modelo: "COMPRADOR Fulano" (um espaço, sem dois-pontos), e logo depois do
# parágrafo do VENDEDOR; três equipamentos sem preço (um fora do
# catálogo); o total só na cláusula; a data de hoje.
contrato(
    "14-contrato-compra-venda.docx", "Kauyr Ribeiro Abdala", "318.447.205-19",
    "Rua das Acácias, 250, Centro, Ribeirão Preto/SP", "kauyr.abdala@exemplo.com.br", "16 99123-4567",
    [("1", "Cama elástica 3 m"), ("1", "Matrix"), ("2", "Air Game Kids")],
    "R$ 38.500,00 (trinta e oito mil e quinhentos reais)", "São Paulo,11 de novembro de 2026",
)
# ---------------------------------------------------------------- 16
# A tabela com "Valor"; a venda de 2016.
contrato(
    "16-contrato-com-valores-2016.docx", "Renata Moura Teixeira", "527.193.648-19",
    "Av. Brasil, 1500, apto 12, Jardim América, São Paulo/SP", "renata.teixeira@exemplo.com.br",
    "(11) 98123-4455",
    [("1", "Cama elástica 3 m", "R$ 2.800,00"), ("1", "Matrix", "R$ 12.900,00")],
    "R$ 15.700,00", "São Paulo,14 de março de 2016", com_valor=True,
)
# ---------------------------------------------------------------- 17
# Um equipamento só, a venda de 2012, a data escrita como em contrato.
contrato(
    "17-contrato-antigo-2012.docx", "Joana Prado Lins", "640.281.935-24",
    "Rua Voluntários da Pátria, 2200, Santana, São Paulo/SP", "joana.lins@exemplo.com.br",
    "(11) 3456-0099",
    [("1", "Cama elástica 4 m")],
    "R$ 3.500,00 (três mil e quinhentos reais)",
    "Firmado em São Paulo, aos 02 dias do mês de julho de 2012.",
)

print("ok")
