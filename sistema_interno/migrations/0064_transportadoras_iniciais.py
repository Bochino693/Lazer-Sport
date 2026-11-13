# As transportadoras conferidas (LEIA-ME-V10, seção 89).
#
# SÓ DADOS: a tabela nasce na 0063. Separadas de propósito -- gravar linha
# no mesmo arquivo que um CREATE TABLE/ALTER TABLE é o que o PostgreSQL
# recusa com "pending trigger events" (ver tests_migracoes.py).
#
# DE ONDE VEIO CADA NÚMERO. Todo telefone, WhatsApp, e-mail e Instagram
# abaixo foi conferido em 13/11/2026 numa página pública -- de preferência
# a da própria empresa -- e essa página está em `fonte_url` (a principal)
# e em `fontes_extras` (cobertura, Instagram, outros canais). O que não
# deu para confirmar ficou EM BRANCO e está listado em `nao_verificado`:
# campo vazio a equipe completa depois; número errado manda o cliente
# para a empresa errada. A mesma tabela, para revisão, está em
# ferramentas/transportadoras/transportadoras.csv (há teste que confere
# que as duas dizem a mesma coisa).
#
# RODAR DE NOVO NÃO DUPLICA NEM SOBRESCREVE: quem já existe com o mesmo
# nome (sem diferença de maiúsculas) fica como a equipe deixou. Desfazer
# apaga só as transportadoras desta lista.

from datetime import date

from django.db import migrations

CONFERIDO_EM = date(2026, 11, 13)

TRANSPORTADORAS = (
    # ------------------------------------------------------------ nacionais
    {
        "nome": "Braspress Transportes Urgentes",
        "nome_fantasia": "Braspress",
        "tipo": "nacional",
        "atende_todo_brasil": True,
        "estados_atendidos": "",
        "cidade_sede": "Guarulhos",
        "uf_sede": "SP",
        "telefone": "1121889000",
        "whatsapp": "",
        "email": "sac@braspress.com",
        "site": "https://www.braspress.com",
        "instagram": "braspresstransportesurgentes",
        "observacoes": (
            "Carga fracionada de grande volume: diz atender todo o território "
            "nacional com estrutura própria (mais de 110 filiais). Boa primeira "
            "opção para máquina paletizada. Telefone da Central de Atendimento/SAC; "
            "a página de contato traz também o 0800 775 3333. A Braspress avisa "
            "que não cobra por WhatsApp nem por boleto avulso."
        ),
        "fonte_url": "https://www.braspress.com/area-do-cliente/informacoes-uteis/evite-fraudes/",
        "fontes_extras": (
            "https://www.braspress.com/contato/\n"
            "https://www.braspress.com/diferenciais/\n"
            "https://www.instagram.com/braspresstransportesurgentes/"
        ),
        "ordem": 10,
        "nao_verificado": "WhatsApp (a empresa diz que não atende pagamentos por WhatsApp)",
    },
    {
        "nome": "Jamef Transportes",
        "nome_fantasia": "Jamef",
        "tipo": "nacional",
        "atende_todo_brasil": True,
        "estados_atendidos": "",
        "cidade_sede": "São Paulo",
        "uf_sede": "SP",
        "telefone": "1121216100",
        "whatsapp": "",
        "email": "",
        "site": "https://www.jamef.com.br",
        "instagram": "jameftransportes",
        "observacoes": (
            "Carga fracionada rodoviária e aérea; afirma atender todo o território "
            "nacional (32 unidades). O telefone é o indicado na página de cotação; "
            "cotação e pedido de coleta também pelo site. A Jamef só divulga canais "
            "oficiais no próprio site e nas redes oficiais."
        ),
        "fonte_url": "https://www.jamef.com.br/cotacao-de-frete",
        "fontes_extras": (
            "https://www.jamef.com.br/infraestrutura\n"
            "https://www.instagram.com/jameftransportes/"
        ),
        "ordem": 20,
        "nao_verificado": "WhatsApp, e-mail",
    },
    {
        "nome": "Jadlog Transportes e Logística",
        "nome_fantasia": "Jadlog",
        "tipo": "nacional",
        "atende_todo_brasil": True,
        "estados_atendidos": "",
        "cidade_sede": "",
        "uf_sede": "",
        "telefone": "11991004606",
        "whatsapp": "",
        "email": "",
        "site": "https://www.jadlog.com.br",
        "instagram": "jadlog.oficial",
        "observacoes": (
            "Rede de franquias com mais de 5.500 pontos de atendimento. Para carga "
            "grande, a cotação costuma sair pela unidade Jadlog mais próxima (lista "
            "em jadlog.com.br/jadlog/unidades) ou pelo chat do site. O único "
            "telefone publicado no site é o do “Fale conosco” da área "
            "internacional."
        ),
        "fonte_url": "https://www.jadlog.com.br/jadlog/legislacaoInternacional",
        "fontes_extras": (
            "https://www.jadlog.com.br/jadlog/atendimento\n"
            "https://www.jadlog.com.br/jadlog/unidades\n"
            "https://www.instagram.com/jadlog.oficial/"
        ),
        "ordem": 30,
        "nao_verificado": "WhatsApp, e-mail (oculto no site), cidade-sede",
    },
    {
        "nome": "Azul Cargo Express",
        "nome_fantasia": "Azul Cargo",
        "tipo": "nacional",
        "atende_todo_brasil": True,
        "estados_atendidos": "",
        "cidade_sede": "",
        "uf_sede": "",
        "telefone": "1140038399",
        "whatsapp": "",
        "email": "",
        "site": "https://www.azulcargoexpress.com.br",
        "instagram": "azulcargoexpress",
        "observacoes": (
            "Carga aérea expressa; o perfil oficial fala em mais de 5.100 cidades "
            "atendidas. Bom para peça e volume médio com pressa; confira peso e "
            "medidas aceitos antes de mandar uma máquina inteira."
        ),
        "fonte_url": "https://www.azulcargoexpress.com.br/Institucional/Contato/Salvar",
        "fontes_extras": "https://www.instagram.com/azulcargoexpress/",
        "ordem": 40,
        "nao_verificado": "WhatsApp, e-mail, cidade-sede",
    },
    {
        "nome": "LATAM Cargo Brasil",
        "nome_fantasia": "LATAM Cargo",
        "tipo": "nacional",
        "atende_todo_brasil": True,
        "estados_atendidos": "",
        "cidade_sede": "",
        "uf_sede": "",
        "telefone": "03001159999",
        "whatsapp": "",
        "email": "",
        "site": "https://www.latamcargo.com/pt/",
        "instagram": "",
        "observacoes": (
            "Carga aérea doméstica, entre os terminais de carga dos aeroportos, "
            "com coleta e entrega opcionais no Brasil. Atendimento de segunda a "
            "domingo, das 8h às 23h; vendas e cotações acima de 30 kg pelo "
            "formulário do site."
        ),
        "fonte_url": "https://www.latamcargo.com/en/customercare",
        "fontes_extras": "https://www.latamcargo.com/pt/faqs",
        "ordem": 50,
        "nao_verificado": "WhatsApp, e-mail, Instagram (não há perfil só da LATAM Cargo), cidade-sede",
    },
    {
        "nome": "GOLLOG (GOL Linhas Aéreas)",
        "nome_fantasia": "GOLLOG",
        "tipo": "nacional",
        "atende_todo_brasil": True,
        "estados_atendidos": "",
        "cidade_sede": "",
        "uf_sede": "",
        "telefone": "03001465564",
        "whatsapp": "",
        "email": "crc.cargas@voegol.com.br",
        "site": "https://www.gollog.com.br",
        "instagram": "",
        "observacoes": (
            "Carga aérea da GOL, entregue e retirada nas lojas GOLLOG dos "
            "aeroportos. Central de vendas de segunda a sexta, das 8h às 20h "
            "(tarifa local). Reclamações: 0800 704 0465."
        ),
        "fonte_url": "https://www.gollog.com.br/en/atendimento/canais-de-atendimento",
        "fontes_extras": "https://www.gollog.com.br/en/atendimento/lojas-gollog",
        "ordem": 60,
        "nao_verificado": "WhatsApp, Instagram, cidade-sede",
    },
    {
        "nome": "FedEx Brasil Logística e Transporte",
        "nome_fantasia": "FedEx",
        "tipo": "nacional",
        "atende_todo_brasil": True,
        "estados_atendidos": "",
        "cidade_sede": "",
        "uf_sede": "",
        "telefone": "08007033339",
        "whatsapp": "",
        "email": "",
        "site": "https://www.fedex.com/pt-br/home.html",
        "instagram": "fedex_bra",
        "observacoes": (
            "Serviços nacionais (Nacional Prioritário, Standard, Econômico e Carga). "
            "SAC de segunda a sexta, das 8h às 18h30; nas capitais e regiões "
            "metropolitanas, também 3003-3339."
        ),
        "fonte_url": "https://www.fedex.com/content/dam/fedex/international/rates/fedex-rates-all-pt-br-2026.pdf",
        "fontes_extras": (
            "https://www.fedex.com/pt-br/open-account.html\n"
            "https://www.instagram.com/fedex_bra/"
        ),
        "ordem": 70,
        "nao_verificado": "WhatsApp, e-mail, cidade-sede",
    },
    {
        "nome": "Total Express",
        "nome_fantasia": "",
        "tipo": "nacional",
        "atende_todo_brasil": True,
        "estados_atendidos": "",
        "cidade_sede": "Barueri",
        "uf_sede": "SP",
        "telefone": "1136275900",
        "whatsapp": "",
        "email": "",
        "site": "https://www.totalexpress.com.br",
        "instagram": "totalexpressbrasil",
        "observacoes": (
            "Foco em encomendas de e-commerce; atende diretamente cerca de 5.165 "
            "municípios (out/2026), inclusive rotas fluviais no AM e no PA. O "
            "telefone foi conferido em diretório de rastreio, e não no site "
            "oficial (fora do alcance na conferência): confirme na primeira ligação."
        ),
        "fonte_url": "https://www.ordertracker.com/pt/transportes/total-express",
        "fontes_extras": (
            "https://mundologistica.com.br/noticias/total-express-cobertura-logistica-5-mil-cidades\n"
            "https://www.instagram.com/totalexpressbrasil/"
        ),
        "ordem": 80,
        "nao_verificado": "telefone no site oficial (só em diretório), WhatsApp, e-mail",
    },
    {
        "nome": "Correios",
        "nome_fantasia": "",
        "tipo": "nacional",
        "atende_todo_brasil": True,
        "estados_atendidos": "",
        "cidade_sede": "Brasília",
        "uf_sede": "DF",
        "telefone": "30030100",
        "whatsapp": "",
        "email": "",
        "site": "https://www.correios.com.br",
        "instagram": "correiosoficial",
        "observacoes": (
            "Só para peça, controle e reposição pequena: encomenda tem limite de "
            "peso e de medida, e máquina inteira não passa. 3003-0100 nas capitais "
            "e regiões metropolitanas; 0800 725 7282 nas demais localidades."
        ),
        "fonte_url": "https://www.correios.com.br/central-de-informacoes/boletim-aos-clientes/mensagens-falsas-sobre-encomendas",
        "fontes_extras": (
            "https://www.correios.com.br/falecomoscorreios\n"
            "https://www.instagram.com/correiosoficial/"
        ),
        "ordem": 90,
        "nao_verificado": "WhatsApp, e-mail (atendimento pelo Fale Conosco)",
    },
    # ------------------------------------------------------------ regionais
    {
        "nome": "Pacífico Log",
        "nome_fantasia": "",
        "tipo": "regional",
        "atende_todo_brasil": False,
        "estados_atendidos": "AC,AM,AP,PA,RO,RR,TO,AL,BA,CE,MA,PB,PE,PI,RN,SE",
        "cidade_sede": "Guarulhos",
        "uf_sede": "SP",
        "telefone": "1142403100",
        "whatsapp": "",
        "email": "",
        "site": "https://pacificolog.com.br",
        "instagram": "",
        "observacoes": (
            "Carga fracionada de São Paulo para todo o Norte e o Nordeste, com a "
            "matriz expedidora em Guarulhos -- perto da fábrica. Quem ainda não é "
            "cliente pede orçamento pelo formulário do site."
        ),
        "fonte_url": "https://pacificolog.com.br/atendimento",
        "fontes_extras": (
            "https://pacificolog.com.br/atuacao.php\n"
            "https://www.pacificolog.com.br/orcamentos"
        ),
        "ordem": 10,
        "nao_verificado": "WhatsApp, e-mail (oculto no site), Instagram",
    },
    {
        "nome": "Patrus Transportes",
        "nome_fantasia": "Patrus",
        "tipo": "regional",
        "atende_todo_brasil": False,
        "estados_atendidos": "BA,CE,SE,ES,MG,RJ,SP",
        "cidade_sede": "Contagem",
        "uf_sede": "MG",
        "telefone": "40033277",
        "whatsapp": "1140033277",
        "email": "",
        "site": "https://patrus.com.br",
        "instagram": "patrustransportes",
        "observacoes": (
            "Carga fracionada, 98 unidades. Entrega no Sudeste e em BA, SE e CE; no "
            "Sul (PR, SC, RS) as unidades são só de embarque. Central e WhatsApp no "
            "mesmo número, com a assistente virtual Paty."
        ),
        "fonte_url": "https://patrus.com.br/rastreie-sua-carga/",
        "fontes_extras": (
            "https://patrus.com.br/blog/conheca-a-paty-a-assistente-virtual-da-patrus-transportes/\n"
            "https://patrus.com.br/quem-somos/unidades/\n"
            "https://www.instagram.com/patrustransportes/"
        ),
        "ordem": 20,
        "nao_verificado": "e-mail",
    },
    {
        "nome": "Rodonaves Transportes",
        "nome_fantasia": "Rodonaves",
        "tipo": "regional",
        "atende_todo_brasil": False,
        "estados_atendidos": "DF,GO,ES,MG,SP,PR,RS,SC",
        "cidade_sede": "Ribeirão Preto",
        "uf_sede": "SP",
        "telefone": "1640002345",
        "whatsapp": "1640002345",
        "email": "",
        "site": "https://rodonaves.com.br",
        "instagram": "rodonavesoficial",
        "observacoes": (
            "Carga fracionada rodoviária e aérea; diz atender mais de 5 mil cidades "
            "com 300 unidades. Em MT, MS, RO, AC, RJ e ES trabalha com parceiros: "
            "confirme a cidade em rodonaves.com.br/cidades-atendidas. Em São Paulo "
            "e Guarulhos aceita volumes de até 3 m; acima de 6 m, só com "
            "autorização. Reclamações: SAC 0800 701 3799."
        ),
        "fonte_url": "https://rodonaves.com.br/fale-conosco",
        "fontes_extras": (
            "https://rodonaves.com.br/rastreio-de-mercadoria\n"
            "https://rodonaves.com.br/quem-somos\n"
            "https://www.instagram.com/rodonavesoficial/"
        ),
        "ordem": 30,
        "nao_verificado": "e-mail (atendimento pelo formulário do site)",
    },
    {
        "nome": "Transportes Translovato (Grupo BBM)",
        "nome_fantasia": "Translovato",
        "tipo": "regional",
        "atende_todo_brasil": False,
        "estados_atendidos": "AC,RO,TO,BA,CE,MA,PI,SE,DF,GO,MS,MT,ES,MG,RJ,SP,PR,RS,SC",
        "cidade_sede": "Caxias do Sul",
        "uf_sede": "RS",
        "telefone": "1124132727",
        "whatsapp": "",
        "email": "saopaulo@translovato.com.br",
        "site": "https://www.translovato.com.br",
        "instagram": "",
        "observacoes": (
            "Divisão de carga fracionada do Grupo BBM, com cerca de 140 unidades. "
            "Telefone e e-mail da unidade São Paulo (coletas); a matriz em Caxias "
            "do Sul atende no (54) 3026-2777. Confira a cidade no buscador "
            "“Área de atuação” do site. Avisa que não negocia pelo OLX."
        ),
        "fonte_url": "https://www.translovato.com.br/siglas-das-unidades",
        "fontes_extras": (
            "https://www.translovato.com.br/fale-conosco/relacao-de-telefones-e-enderecos\n"
            "https://www.translovato.com.br/diferenciais/centrais-de-relacionamento\n"
            "https://www.translovato.com.br/area-de-atuacao\n"
            "https://bbmlogistica.com.br/bbm-logistica-amplia-area-de-atendimento-no-nordeste/"
        ),
        "ordem": 40,
        "nao_verificado": "WhatsApp, Instagram (o @translovato é de uma pessoa)",
    },
    {
        "nome": "Alfa Transportes",
        "nome_fantasia": "",
        "tipo": "regional",
        "atende_todo_brasil": False,
        "estados_atendidos": "DF,GO,MS,ES,MG,RJ,SP,PR,RS,SC",
        "cidade_sede": "Caçador",
        "uf_sede": "SC",
        "telefone": "4935615100",
        "whatsapp": "47996131256",
        "email": "",
        "site": "https://alfatransportes.com.br",
        "instagram": "",
        "observacoes": (
            "Carga fracionada em 10 estados do Sul, Sudeste e Centro-Oeste. "
            "WhatsApp de cotações (47) 99613-1256 ou 99613-1258; a matriz também "
            "atende por WhatsApp no (49) 3561-5100. A Alfa não faz cobrança por "
            "WhatsApp."
        ),
        "fonte_url": "https://blog.alfatransportes.com.br/conheca-nossos-canais-de-atendimento/",
        "fontes_extras": (
            "https://blog.alfatransportes.com.br/category/cotacao/\n"
            "https://alfatransportes.com.br/"
        ),
        "ordem": 50,
        "nao_verificado": "e-mail comercial, Instagram (dois perfis com o nome, nenhum confirmado)",
    },
    {
        "nome": "Expresso São Miguel",
        "nome_fantasia": "",
        "tipo": "regional",
        "atende_todo_brasil": False,
        "estados_atendidos": "SP,PR,RS,SC",
        "cidade_sede": "Chapecó",
        "uf_sede": "SC",
        "telefone": "4933616666",
        "whatsapp": "4933616666",
        "email": "",
        "site": "https://expressosaomiguel.com.br",
        "instagram": "",
        "observacoes": (
            "Carga fracionada no Sul e em São Paulo (mais de 920 cidades). Telefone "
            "e WhatsApp da matriz; cada unidade tem telefone e e-mail próprios na "
            "página de unidades."
        ),
        "fonte_url": "https://expressosaomiguel.com.br/unidades/",
        "fontes_extras": "https://expressosaomiguel.com.br/seja-um-parceiro/",
        "ordem": 60,
        "nao_verificado": "e-mail geral, Instagram (nenhum perfil oficial encontrado)",
    },
    {
        "nome": "Carvalima Transportes",
        "nome_fantasia": "Carvalima",
        "tipo": "regional",
        "atende_todo_brasil": False,
        "estados_atendidos": "AC,AM,AP,PA,RO,RR,TO,MS,MT",
        "cidade_sede": "Cuiabá",
        "uf_sede": "MT",
        "telefone": "6533163900",
        "whatsapp": "",
        "email": "cotacao@carvalima.com.br",
        "site": "https://carvalima.com.br",
        "instagram": "carvalimatransportes",
        "observacoes": (
            "Especialista em Centro-Oeste e Norte: entrega forte em MT, MS, RO, AC e "
            "PA; AM, AP, RR e TO são operação mais nova (confirme a cidade). "
            "Atendimento de segunda a sexta, das 7h30 às 17h30. SAC: "
            "sac@carvalima.com.br."
        ),
        "fonte_url": "https://carvalima.com.br/atendimento",
        "fontes_extras": (
            "https://carvalima.com.br/quem-somos\n"
            "https://www.carvalima.com.br/regioes-atendidas\n"
            "https://www.instagram.com/carvalimatransportes/"
        ),
        "ordem": 70,
        "nao_verificado": "WhatsApp",
    },
    {
        "nome": "Transportes Bertolini (TBL)",
        "nome_fantasia": "TBL Bertolini",
        "tipo": "regional",
        "atende_todo_brasil": False,
        "estados_atendidos": "AM,PA,RO",
        "cidade_sede": "",
        "uf_sede": "",
        "telefone": "9221251000",
        "whatsapp": "",
        "email": "comercial@tbl.com.br",
        "site": "https://www.tbl.com.br",
        "instagram": "",
        "observacoes": (
            "Integração rodofluvial (balsas Belém–Manaus e pelo rio Madeira): "
            "indicada para carga volumosa com destino ao Amazonas. Telefone da "
            "unidade Manaus; Belém (91) 4006-5100; canal geral (54) 2102-3000. "
            "Confirme se aceita volume fracionado pequeno."
        ),
        "fonte_url": "https://www.tbl.com.br/fale-conosco",
        "fontes_extras": "https://www.tbl.com.br/quem-somos/estrutura",
        "ordem": 80,
        "nao_verificado": "WhatsApp, Instagram, cidade-sede",
    },
    # ------------------------------------------------ mudanças e cargas especiais
    {
        "nome": "Granero Transportes",
        "nome_fantasia": "Granero",
        "tipo": "mudancas",
        "atende_todo_brasil": True,
        "estados_atendidos": "",
        "cidade_sede": "",
        "uf_sede": "",
        "telefone": "1140409085",
        "whatsapp": "11913662652",
        "email": "",
        "site": "https://www.granero.com.br",
        "instagram": "granerotransportes",
        "observacoes": (
            "Mudanças residenciais e comerciais com embalagem, equipe de carga e "
            "guarda-volumes; unidades em várias capitais (Salvador, Curitiba, "
            "Fortaleza, São Luís, Teresina...). Indicada para máquina grande ou "
            "frágil que precisa ser embalada e carregada com cuidado. A Granero "
            "só faz orçamento pelo site oficial e por estes canais."
        ),
        "fonte_url": "https://www.granero.com.br/alerta-golpes",
        "fontes_extras": "https://www.instagram.com/granerotransportes/",
        "ordem": 10,
        "nao_verificado": "e-mail geral (cada unidade tem o seu), cidade-sede",
    },
    {
        "nome": "Fink Mobility",
        "nome_fantasia": "Fink",
        "tipo": "mudancas",
        "atende_todo_brasil": True,
        "estados_atendidos": "",
        "cidade_sede": "Rio de Janeiro",
        "uf_sede": "RJ",
        "telefone": "2134109700",
        "whatsapp": "21971001960",
        "email": "",
        "site": "https://www.fink.com.br/mobility/",
        "instagram": "",
        "observacoes": (
            "Mudanças nacionais por região: o escritório do Rio (acima) cuida do "
            "Sudeste, Norte e Nordeste; São Paulo, do Sul, (11) 3839-5400 / "
            "(11) 99496-9660; Brasília, do Centro-Oeste, (61) 3046-9750 / "
            "(61) 99953-9073."
        ),
        "fonte_url": "https://www.fink.com.br/mobility/mudancas-nacionais/",
        "fontes_extras": "",
        "ordem": 20,
        "nao_verificado": "e-mail (oculto na página nacional), Instagram",
    },
)

#: Só para documentação (o CSV e o relatório); não vira coluna.
SO_DOCUMENTACAO = ("nao_verificado",)


def criar(apps, schema_editor):
    Transportadora = apps.get_model("sistema_interno", "Transportadora")
    existentes = {
        nome.casefold() for nome in Transportadora.objects.values_list("nome", flat=True)
    }
    novas = []
    for dados in TRANSPORTADORAS:
        if dados["nome"].casefold() in existentes:
            continue
        campos = {chave: valor for chave, valor in dados.items() if chave not in SO_DOCUMENTACAO}
        novas.append(Transportadora(**campos, verificado_em=CONFERIDO_EM, ativo=True))
    Transportadora.objects.bulk_create(novas)


def apagar(apps, schema_editor):
    Transportadora = apps.get_model("sistema_interno", "Transportadora")
    Transportadora.objects.filter(
        nome__in=[dados["nome"] for dados in TRANSPORTADORAS],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0063_transportadora"),
    ]

    operations = [
        migrations.RunPython(criar, apagar),
    ]
