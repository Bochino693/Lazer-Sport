"""Quem é o cliente num documento SEM rótulos -- lido como uma pessoa lê.

O PEDIDO, NAS PALAVRAS DO CLIENTE: "vc deve auto preencher os campos,
indentificando nomes, endereços, que nao sejam da fabrica e nomes que nao
sejam dos usuarios internos, isso é como uma ia". Em produção não há a
chave da IA; então ISTO é a IA: uma leitura local, sem rede e sem custo,
de contrato, carta, e-mail colado no Word, ficha e conversa de WhatsApp.

COMO LÊ. Cada dado do cliente vira CANDIDATO, com pontos:
  * nome de pessoa: palavras com inicial maiúscula (ou TUDO MAIÚSCULO, como
    em contrato) que começam por um primeiro nome brasileiro conhecido
    (dados/primeiros_nomes.txt, base IBGE), com "da", "de", "dos" no meio;
  * nome de empresa: "Buffet", "Espaço", "Escola", "Clube"... no começo, ou
    "Ltda", "ME", "Eireli", "S.A." no fim;
  * endereço: "Rua", "Av.", "Alameda", "Estrada", "Rod.", "Travessa",
    "Praça"... com número, bairro, cidade/UF e CEP, com vírgula ou traço;
  * CPF/CNPJ, telefone e e-mail: as regras de deterministica.py.
A PISTA ao lado decide os pontos: "Contratante:", "Cliente:", "Sr./Sra.",
"Prezada", "A/C", "Aos cuidados", "Responsável", "Razão social", "Nome
fantasia", "meu nome é", "residente à", "local do evento"... Pesam também
a posição (o começo do documento), a repetição, o dado do cliente colado
(o CPF na mesma frase) e, numa conversa de WhatsApp, quem fala. O melhor
candidato preenche o campo; os outros viram botões na conferência ("outras
leituras"), para trocar com um toque.

O QUE NUNCA É O CLIENTE:
  * a Lazer & Sport: as linhas com o CNPJ, telefone, e-mail, site, nome ou
    endereço da casa (`deterministica.linha_da_empresa`), e as coladas nelas;
  * a EQUIPE: todo usuário interno (função de equipe no painel, staff ou
    superusuário) e os colaboradores da fábrica -- nome, nome completo,
    usuário e e-mail. "Atenciosamente, Marina -- Comercial" e "Vendedor:
    Carlos" não viram cliente; a assinatura de quem é da casa sai inteira
    (com o celular de quem assina), e numa conversa a fala do vendedor
    também;
  * a pista contrária: "Vendedor", "Consultora", "Atendente",
    "Contratada", "Locadora", "Elaborado por", "Equipe", "Departamento".
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from core.arena import _normalizar

from . import deterministica as det

PASTA_DADOS = Path(__file__).resolve().parent / "dados"

#: Abaixo disto o candidato não preenche sozinho -- só aparece como opção.
PONTOS_PARA_PREENCHER = 3.0
PONTOS_PARA_SUGERIR = 1.5


@lru_cache(maxsize=1)
def primeiros_nomes() -> frozenset:
    linhas = (PASTA_DADOS / "primeiros_nomes.txt").read_text(encoding="utf-8").splitlines()
    return frozenset(_normalizar(l) for l in linhas if l.strip() and not l.startswith("#"))


# ======================================================================
# QUEM É DA CASA
# ======================================================================
def pessoas_internas() -> dict:
    """Nomes e e-mails de quem é da Lazer & Sport, para nunca virarem cliente.

    Interno é quem tem função de equipe no painel (os grupos de
    permissoes.py), quem é staff ou superusuário, e o colaborador da
    fábrica (sem login, mas citado na produção).
    """
    from django.contrib.auth.models import User
    from django.db.models import Q

    from ..models import Colaborador
    from ..permissoes import NOMES_DOS_GRUPOS

    completos, pares, primeiros, usuarios, emails = set(), set(), set(), set(), set()

    def guardar(nome_completo, primeiro="", ultimo="", usuario="", email=""):
        completo = _normalizar(nome_completo)
        if completo:
            completos.add(completo)
            partes = completo.split()
            primeiros.add(partes[0])
            if len(partes) >= 2:
                pares.add((partes[0], partes[-1]))
        if primeiro:
            primeiros.add(_normalizar(primeiro).split()[0] if _normalizar(primeiro) else "")
        if primeiro and ultimo:
            pares.add((_normalizar(primeiro).split()[0], _normalizar(ultimo).split()[-1]))
        if usuario:
            usuarios.add(_normalizar(usuario))
        if email:
            emails.add(email.strip().lower())

    equipe = (
        User.objects.filter(Q(is_staff=True) | Q(is_superuser=True) | Q(groups__name__in=NOMES_DOS_GRUPOS))
        .distinct()
        .values_list("first_name", "last_name", "username", "email")
    )
    for primeiro, ultimo, usuario, email in equipe:
        guardar(f"{primeiro} {ultimo}".strip(), primeiro, ultimo, usuario, email)
    for nome in Colaborador.objects.values_list("nome", flat=True):
        guardar(nome)
    primeiros.discard("")
    return {"completos": completos, "pares": pares, "primeiros": primeiros,
            "usuarios": usuarios, "emails": emails}


def eh_interno(nome: str, internos: dict) -> bool:
    """O nome é de alguém da casa?

    Nome completo igual, usuário igual, o par primeiro + último nome igual
    -- ou, quando o candidato é UM nome só ("Marina"), o primeiro nome de
    alguém da equipe: sozinho, ele não basta para dizer que é o cliente.
    """
    if not internos:
        return False
    normal = _normalizar(nome)
    if not normal:
        return False
    if normal in internos["completos"] or normal in internos["usuarios"]:
        return True
    partes = normal.split()
    if len(partes) == 1:
        return partes[0] in internos["primeiros"]
    return (partes[0], partes[-1]) in internos["pares"]


# ======================================================================
# O QUE O TEXTO DIZ
# ======================================================================
_MAIUSCULA = "A-ZÀ-ÖØ-Þ"
_MINUSCULA = "a-zß-öø-ÿ"
_PALAVRA_DE_NOME = rf"(?:[{_MAIUSCULA}][{_MINUSCULA}']+|[{_MAIUSCULA}]{{2,}})"
_NOME = re.compile(
    rf"(?<![\w@.]){_PALAVRA_DE_NOME}(?:[ \t]+(?:(?:d[aeo]s?|e|D[AEO]S?|E)[ \t]+)?{_PALAVRA_DE_NOME}){{0,5}}(?![\w@])"
)
_MARCA_DE_EMPRESA = (
    r"buffet|espa[çc]o|parque|escola|col[ée]gio|condom[íi]nio|clube|hotel|pousada|restaurante|"
    r"igreja|par[óo]quia|associa[çc][ãa]o|instituto|shopping|arena|academia|creche|ch[áa]cara|"
    r"s[íi]tio|fazenda|festas|recrea[çc][ãa]o|playground|loja|mercado|supermercado|lanchonete|"
    r"pizzaria|sal[ãa]o|prefeitura|secretaria|funda[çc][ãa]o|grupo|est[úu]dio|kids|mundo|"
    r"planeta|reino|castelo|toca|cantinho|casa\s+de\s+festas|hamburgueria|churrascaria|cl[íi]nica|"
    r"hospital|empresa|companhia|cia\.?"
)
_PALAVRA_DE_EMPRESA = rf"(?:[{_MAIUSCULA}0-9][\w'&.-]*)"
# A marca ("Buffet", "BUFFET") vale em qualquer caixa; as palavras depois
# dela, não: só com inicial maiúscula ("Buffet Alegria", e não "buffet de
# festas infantis").
_EMPRESA_PELA_MARCA = re.compile(
    rf"(?<![\w])(?i:{_MARCA_DE_EMPRESA})(?:[ \t]+(?:(?:d[aeo]s?|e|&|D[AEO]S?|E)[ \t]+)?{_PALAVRA_DE_EMPRESA}){{1,6}}"
)
_EMPRESA_PELO_SUFIXO = re.compile(
    rf"(?<![\w]){_PALAVRA_DE_EMPRESA}(?:[ \t]+(?:(?:d[aeo]s?|e|&|D[AEO]S?|E)[ \t]+)?{_PALAVRA_DE_EMPRESA}){{0,6}}"
    r"[ \t]+(?:LTDA|Ltda|ME|MEI|EIRELI|Eireli|EPP|S\.?A\.?|S/A)\.?(?![\w])"
)
#: "a empresa Open Spice Sushi Lounge", "Empresa: Doces Finos": o nome com
#: inicial maiúscula logo depois da palavra "empresa".
_EMPRESA_CHAMADA_ASSIM = re.compile(
    rf"(?i:\b(?:a\s+)?empresa\s*[:,]?\s+)((?:{_PALAVRA_DE_EMPRESA})(?:[ \t]+(?:(?:d[aeo]s?|e|&)[ \t]+)?{_PALAVRA_DE_EMPRESA}){{0,6}})"
)
#: O nome logo antes do CNPJ: "Doces Finos Comércio de Alimentos, CNPJ
#: 12.345.678/0001-90" / "Doces Finos – CNPJ: ...".
_NOME_ANTES_DO_CNPJ = re.compile(
    rf"((?:{_PALAVRA_DE_EMPRESA})(?:[ \t]+(?:(?:d[aeo]s?|e|&)[ \t]+)?{_PALAVRA_DE_EMPRESA}){{1,7}})"
    r"\s*[,–—-]?\s*(?:inscrit[ao]\s+no\s+)?(?:CNPJ|C\.N\.P\.J\.?)\s*(?:/?MF)?\s*(?:sob\s+o\s+)?(?:n[º°o.]?\s*)?[:]?\s*$"
)
_LOGRADOURO = re.compile(
    rf"(?<![\w])(?:Rua|R\.|Avenida|Av\.?|Alameda|Al\.|Estrada|Estr\.|Rodovia|Rod\.|Travessa|Trav\.|Tv\.|"
    rf"Pra[çc]a|P[çc]a\.|Largo|Viela|Servid[ãa]o|Beco|Ladeira|Passagem)[ \t]+(?=(?:d[aeo]s?[ \t]+)?[{_MAIUSCULA}0-9])"
)
#: Palavras que, dentro de uma sequência de maiúsculas, mostram que aquilo
#: não é nome de gente: lugar, documento, mês, cargo, a própria casa.
_NAO_E_NOME = {
    "rua", "avenida", "av", "alameda", "travessa", "rodovia", "estrada", "praca", "largo", "bairro",
    "cidade", "estado", "brasil", "cpf", "cnpj", "cep", "rg", "ltda", "eireli", "lazer", "sport",
    "sports", "brinquedos", "contratante", "contratada", "cliente", "proposta", "orcamento",
    "contrato", "clausula", "prezado", "prezada", "prezados", "atenciosamente", "assunto", "para",
    "de", "data", "valor", "total", "pagamento", "telefone", "email", "whatsapp", "instagram",
    "janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro",
    "outubro", "novembro", "dezembro", "segunda", "terca", "quarta", "quinta", "sexta", "sabado",
    "domingo", "bom", "boa", "dia", "tarde", "noite", "obrigado", "obrigada", "ola", "oi", "sim",
    "nao", "pix", "boleto", "jardim", "vila", "parque", "centro", "sao", "santa", "santo",
    "equipe", "comercial", "departamento", "setor", "objeto", "local", "evento", "festa",
    # Os títulos das cláusulas do contrato ("DA MULTA", "DO FORO").
    "multa", "multas", "foro", "inadimplencia", "obrigacoes", "obrigacao", "garantia", "garantias",
    "rescisao", "entrega", "prazo", "prazos", "clausulas", "condicoes", "disposicoes", "gerais", "finais",
    "penalidades", "vigencia", "responsabilidade", "responsabilidades", "comprador", "compradora",
    "vendedor", "vendedora", "testemunha", "testemunhas", "proprietario", "proprietaria", "frete",
    "instalacao", "montagem", "assistencia", "tecnica", "partes", "despesas", "juros", "reajuste",
} | {uf.lower() for uf in det.UFS}
#: "DA MULTA", "DO OBJETO DO CONTRATO", "DAS OBRIGAÇÕES E GARANTIAS": o
#: título de seção do contrato, sozinho na linha. Nunca é o nome de ninguém.
_TITULO_DE_SECAO = re.compile(
    r"^(?:cl[aá]usula\s+\S+\s*[-–—.:]?\s*)?(?:d[oa]s?|de)\s+"
    r"(?:objeto|multas?|foro|inadimpl[eê]ncia|obriga[cç](?:[oõ]es|[aã]o)|garantias?|pagamentos?|prazos?|"
    r"entregas?|rescis[aã]o|cl[aá]usulas?|contrato|valor(?:es)?|pre[cç]os?|condi[cç](?:[oõ]es|[aã]o)|"
    r"disposi[cç][oõ]es|responsabilidades?|penalidades?|vig[eê]ncia|frete|instala[cç][aã]o|montagem|"
    r"assist[eê]ncia|partes|despesas|reajuste|juros|tributos)\b",
    re.IGNORECASE,
)
#: "da", "de", "do", "das", "dos" e "e" ligam nomes; nunca começam um.
_LIGACOES = ("de", "da", "do", "das", "dos", "e")


def titulo_de_secao(texto: str) -> bool:
    """A linha é o título de uma seção do contrato ("DA MULTA", "DO FORO")?"""
    limpo = (texto or "").strip(" .:;-–—")
    if not limpo or len(limpo) > 70:
        return False
    letras = [c for c in limpo if c.isalpha()]
    em_maiusculas = bool(letras) and sum(c.isupper() for c in letras) / len(letras) > 0.8
    return bool(_TITULO_DE_SECAO.match(limpo)) and (em_maiusculas or len(limpo.split()) <= 5)

#: (padrão no fim do texto ANTES do candidato, para qual campo, pontos)
_PISTAS = [
    (r"(?:contratante|locatari(?:[oa]|o\s*\(a\))|cliente|comprador(?:a|\s*\(a\))?|adquirente|solicitante|destinatari[oa]|"
     r"nome\s+completo|nome\s+do\s+cliente|proposta\s+para|orcamento\s+para|"
     r"meu\s+nome\s+e|me\s+chamo|aqui\s+e\s+[oa]|sou\s+[oa]|em\s+nome\s+de)", "cliente", 5.0),
    (r"(?:razao\s+social|nome\s+fantasia|empresa|estabelecimento|instituicao)", "empresa", 5.0),
    (r"(?:sr|sra|srta|senhor|senhora|prezad[oa]s?|ilm[oa]|exm[oa]|a\s*/\s*c|aos\s+cuidados(?:\s+d[aeo])?|"
     r"att|attn|responsavel|proprietari[oa]|sindic[oa]|representad[oa]\s+(?:neste\s+ato\s+)?por"
     r"(?:\s+(?:seu|sua))?(?:\s+(?:socio|socia|diretor[a]?|administrador[a]?|proprietari[oa]|"
     r"representante\s+legal)(?:\s+administrador[a]?)?)?|contato|nome)", "pessoa", 4.0),
    (r"(?:vendedor[a]?|consultor[a]?|atendente|representante\s+comercial|comercial|contratad[oa]|"
     r"locador[a]?|elaborad[oa]\s+por|emitid[oa]\s+por|responsavel\s+tecnic[oa]|equipe|"
     r"departamento|setor|gerente\s+comercial|assinad[oa]\s+por)", "fora", -20.0),
]
_PISTAS = [(re.compile(padrao + r"\s*[:,.\-–—]?\s*(?:[ao]\s+)?$"), campo, pontos) for padrao, campo, pontos in _PISTAS]
_DESPEDIDA = re.compile(
    r"^(?:atenciosamente|att|atte|cordialmente|abracos?|obrigad[oa]|grat[oa]|sds|saudacoes|"
    r"respeitosamente|um abraco|forte abraco|ate mais)\b"
)
#: Cargo de quem atende pela casa. "Gerente" e "Diretora" ficam de fora de
#: propósito: o cliente também assina assim ("Ana -- Gerente do Buffet X").
_CARGO_DA_CASA = re.compile(r"\b(?:consultor[a]?|vendedor[a]?|comercial|atendimento|equipe|sac)\b")
_LINHA_DO_WHATSAPP = re.compile(
    r"^\[?\s*(\d{1,2}/\d{1,2}(?:/\d{2,4})?)[ ,]+(\d{1,2}:\d{2})(?::\d{2})?\s*\]?\s*(?:-\s*)?([^:]{2,60}?):\s*(.*)$"
)
_PISTA_DE_ENDERECO = re.compile(
    r"(?:residente|domiciliad[oa]|endereco|end\.|local\s+do\s+evento|local\s+da\s+festa|entrega|"
    r"instalacao|montagem|situad[oa]|localizad[oa]|sede|fica\s+n[ao]|nosso\s+endereco|moro\s+n[ao])"
)
_ESTADOS = {
    "acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM", "bahia": "BA", "ceara": "CE",
    "distrito federal": "DF", "espirito santo": "ES", "goias": "GO", "maranhao": "MA",
    "mato grosso": "MT", "mato grosso do sul": "MS", "minas gerais": "MG", "para": "PA",
    "paraiba": "PB", "parana": "PR", "pernambuco": "PE", "piaui": "PI", "rio de janeiro": "RJ",
    "rio grande do norte": "RN", "rio grande do sul": "RS", "rondonia": "RO", "roraima": "RR",
    "santa catarina": "SC", "sao paulo": "SP", "sergipe": "SE", "tocantins": "TO",
}


def _pista(antes: str):
    """A pista no fim do texto que vem antes do candidato: (campo, pontos) ou None."""
    final = det.sem_acento(antes)[-70:]
    for padrao, campo, pontos in _PISTAS:
        if padrao.search(final):
            return campo, pontos
    return None


def _segmentos(linhas: list[dict]) -> list[dict]:
    """As linhas como trechos: numa conversa, o remetente fica à parte do texto."""
    saida = []
    for posicao, linha in enumerate(linhas):
        texto = linha["texto"]
        remetente = ""
        achado = _LINHA_DO_WHATSAPP.match(texto.strip())
        if achado:
            remetente = achado.group(3).strip()
            texto = achado.group(4)
        saida.append({"linha": linha, "texto": texto, "remetente": remetente, "posicao": posicao})
    return saida


# ======================================================================
# O LADO DA CASA NUM CONTRATO
# ======================================================================
#: Quem vende, aluga ou é contratado: a Lazer & Sport. Em maiúsculas
#: ("o VENDEDOR vende ao COMPRADOR"), com dois-pontos ("Contratada:") ou
#: na frase de apresentação das partes ("na qualidade de fornecedor").
_PAPEL_DA_CASA = re.compile(
    r"\b(?:VENDEDOR[A]?|CONTRATAD[AO]|LOCADOR[A]?|FORNECEDOR[A]?|PRESTADOR[A]?)\b"
    r"|\b(?:Vendedor[a]?|Contratad[ao]|Locador[a]?|Fornecedor[a]?|Prestador[a]?)\s*:"
    r"|(?i:\bna\s+qualidade\s+de\s+(?:vendedor|contratad|locador|fornecedor|prestador))"
)
#: Quem compra, aluga ou contrata: o cliente.
_PAPEL_DO_CLIENTE = re.compile(
    r"\b(?:COMPRADOR[A]?|CONTRATANTE|LOCAT[AÁ]RI[OA]|ADQUIRENTE|CLIENTE)\b"
    r"|\b(?:Comprador[a]?|Contratante|Locat[aá]ri[oa]|Adquirente|Cliente)\s*:"
    r"|(?i:\bna\s+qualidade\s+de\s+(?:comprador|contratante|locat|adquirente|cliente)|\bdo\s+outro\s+lado\b)"
)
#: A linha de assinatura que é SÓ o papel: "Proprietário", "VENDEDOR".
_ASSINATURA_DA_CASA = re.compile(r"(?i)^(?:s[óo]ci[oa][\s-]*)?propriet[áa]ri[oa]\s*:?$")
_LINHA_DE_ASSINATURA = re.compile(r"^[_\-–—.\s]{6,}$")
#: Quantas linhas uma frase da casa atravessa, no máximo, sem fechar.
_LINHAS_DA_FRASE = 8


def _fim_de_frase(texto: str) -> bool:
    """A linha termina a frase? "...inscrita no CNPJ sob o n." não termina."""
    final = texto.rstrip()
    if not final.endswith((".", "!", "?")):
        return False
    ultima = re.search(r"(\S+)\.$", final)
    # "n.", "nº.", "Av.", "Ltda." e companhia: abreviação, a frase continua.
    return not (ultima and (len(ultima.group(1)) <= 4 or _ABREVIACOES.search(final)))


def lado_da_casa(linhas: list[dict]) -> dict[str, list[tuple[int, int]]]:
    """Os trechos de cada linha que falam da Lazer & Sport no contrato.

    "VENDEDOR: Brinquedos Lazer & Sport ..., neste ato representado por
    Fulano ..., residente e domiciliado na Rua X, 411 ...; e, do
    outro lado, na qualidade de comprador, ...": tudo entre o papel da casa
    e o papel do cliente é da casa -- o nome de quem representa a fábrica,
    o RG e o endereço residencial dele. Nada disso pode virar o cliente.

    No PDF a frase vem quebrada em várias linhas; o trecho continua na
    linha de baixo enquanto a frase não termina (linha sem ponto final), por
    no máximo oito linhas. Na assinatura, o papel sozinho na linha
    ("VENDEDOR", e "Proprietário" quando o documento é um contrato com
    VENDEDOR) leva as linhas de baixo até o traço da próxima assinatura.

    Devolve {id da linha: [(início, fim), ...]}.
    """
    corpo = [l for l in linhas if l["parte"] in ("corpo", "caixa")]
    contrato = any(_PAPEL_DA_CASA.search(l["texto"]) for l in corpo)
    trechos: dict[str, list[tuple[int, int]]] = {}
    restam = 0  # quantas linhas de baixo o trecho aberto ainda pode levar
    for linha in corpo:
        texto = linha["texto"]
        limpo = texto.strip()
        if _LINHA_DE_ASSINATURA.match(limpo):
            restam = 0
            continue
        eventos = [(a.start(), "casa") for a in _PAPEL_DA_CASA.finditer(texto)]
        eventos += [(a.start(), "cliente") for a in _PAPEL_DO_CLIENTE.finditer(texto)]
        assinatura = len(limpo) <= 25 and (
            (contrato and _ASSINATURA_DA_CASA.match(limpo)) or bool(re.fullmatch(r"[A-ZÀ-Ý ]+:?", limpo)
                                                                    and _PAPEL_DA_CASA.fullmatch(limpo.rstrip(":")))
        )
        if contrato and _ASSINATURA_DA_CASA.match(limpo):
            eventos.append((0, "casa"))
        eventos.sort()
        inicio = 0 if restam else None
        for posicao, papel in eventos:
            if papel == "casa" and inicio is None:
                inicio = posicao
            elif papel == "cliente" and inicio is not None:
                if posicao > inicio:
                    trechos.setdefault(linha["id"], []).append((inicio, posicao))
                inicio = None
        if inicio is None:
            restam = 0
            continue
        trechos.setdefault(linha["id"], []).append((inicio, len(texto)))
        if assinatura:
            # "VENDEDOR" / "Proprietário" sozinho: o nome vem logo abaixo.
            restam = 2
        elif restam:
            restam = restam - 1 if not _fim_de_frase(texto) else 0
        else:
            # A frase quebrada pelo PDF continua na linha de baixo; a linha
            # curta ("Vendedor: Carlos") não leva nada consigo.
            restam = _LINHAS_DA_FRASE if (len(limpo) >= 60 and not _fim_de_frase(texto)) else 0
    return trechos


def no_lado_da_casa(trechos: dict, id_linha: str, inicio: int, fim: int | None = None) -> bool:
    """O pedaço [início, fim) da linha cai num trecho da casa?"""
    fim = inicio + 1 if fim is None else fim
    return any(a <= inicio < b or a < fim <= b for a, b in trechos.get(id_linha, ()))


def linhas_inteiras_da_casa(linhas: list[dict], trechos: dict) -> set:
    """As linhas que são SÓ da casa (o trecho cobre o texto todo)."""
    inteiras = set()
    for linha in linhas:
        texto = linha["texto"]
        for a, b in trechos.get(linha["id"], ()):
            if not texto[:a].strip() and not texto[b:].strip(" .,;:"):
                inteiras.add(linha["id"])
    return inteiras


# ======================================================================
# O QUE FICA DE FORA
# ======================================================================
def linhas_de_fora(linhas: list[dict], *, empresa: dict, internos: dict) -> set:
    """Linhas que não falam do cliente: assinatura da casa, fala do vendedor.

    A linha da empresa em si (CNPJ, telefone da casa) a leitura por regra
    já tira; aqui sai o que ela não teria como saber: o bloco depois de
    "Atenciosamente" quando quem assina é da equipe (com o celular dela), a
    linha "Vendedor: Carlos", e numa conversa as falas de quem é da casa.
    """
    fora = set()
    segmentos = _segmentos(linhas)

    def da_casa(texto):
        if det.linha_da_empresa(texto, empresa):
            return True
        if any(e["email"] in internos.get("emails", ()) for e in det.emails(texto)):
            return True
        for achado in _NOME.finditer(texto):
            if len(achado.group(0).split()) >= 2 and eh_interno(achado.group(0), internos):
                return True
        if eh_interno(texto.strip(" .,;-–—"), internos):
            return True
        return bool(_CARGO_DA_CASA.search(det.sem_acento(texto)))

    for posicao, segmento in enumerate(segmentos):
        linha = segmento["linha"]
        if segmento["remetente"] and (
            eh_interno(segmento["remetente"], internos) or det.linha_da_empresa(segmento["remetente"], empresa)
        ):
            fora.add(linha["id"])
            continue
        sem = det.sem_acento(segmento["texto"]).strip()
        # "Vendedor: Carlos" / "Consultora: Marina"
        par = re.match(r"^([^:]{2,40}):\s*(.+)$", sem)
        if par and _PISTAS[3][0].search(par.group(1) + ":"):
            fora.add(linha["id"])
            continue
        if _DESPEDIDA.match(sem):
            bloco = [s for s in segmentos[posicao + 1:posicao + 7] if s["linha"]["parte"] == linha["parte"]]
            if any(da_casa(s["texto"]) for s in bloco):
                fora.update(s["linha"]["id"] for s in bloco)
    return fora


# ======================================================================
# CANDIDATOS
# ======================================================================
def _limpar_pessoa(texto: str) -> str:
    """Corta a sequência de maiúsculas onde deixa de ser nome de gente."""
    palavras = texto.split()
    saida = []
    for palavra in palavras:
        normal = _normalizar(palavra)
        if normal in _NAO_E_NOME and normal not in ("de", "da", "do", "das", "dos", "e"):
            break
        saida.append(palavra)
    while saida and _normalizar(saida[-1]) in ("de", "da", "do", "das", "dos", "e"):
        saida.pop()
    return " ".join(saida)


# ======================================================================
# O ESTABELECIMENTO: o nome que vai para o mapa (e não o da pessoa)
# ======================================================================
#: Palavras que fazem um nome ser de negócio, e não de gente.
_PALAVRAS_DE_NEGOCIO = {
    "buffet", "buffets", "escola", "colegio", "condominio", "clube", "hotel", "pousada", "restaurante", "bar",
    "lanchonete", "pizzaria", "hamburgueria", "churrascaria", "sushi", "lounge", "cafe", "cafeteria", "doces",
    "confeitaria", "padaria", "mercado", "supermercado", "loja", "lojas", "parque", "espaco", "festa", "festas",
    "eventos", "kids", "infantil", "playground", "shopping", "academia", "arena", "creche", "chacara", "sitio",
    "fazenda", "igreja", "paroquia", "associacao", "instituto", "fundacao", "prefeitura", "secretaria",
    "salao", "recreacao", "diversoes", "comercio", "industria", "servicos", "alimentos",
    "distribuidora", "empreendimentos", "participacoes", "grupo", "studio", "estudio", "clinica", "hospital",
    "centro", "casa", "mundo", "planeta", "reino", "castelo", "toca", "cantinho", "pub", "bistro", "cervejaria",
}
_SUFIXOS_DE_EMPRESA = {"ltda", "me", "mei", "eireli", "epp", "sa", "s a", "s/a"}
#: Palavras do nome do ARQUIVO que dizem o que o documento é -- não quem é.
_PALAVRAS_DE_DOCUMENTO = {
    "contrato", "contratos", "orcamento", "orcamentos", "proposta", "propostas", "pedido", "pedidos", "compra",
    "venda", "compra e venda", "instrumento", "particular", "termo", "termos", "aditivo", "copia", "final",
    "assinado", "assinada", "revisado", "revisada", "versao", "rev", "novo", "nova", "atualizado", "ficha",
    "cadastro", "cliente", "comercial", "equipamento", "equipamentos", "entretenimento", "locacao", "aluguel",
    "de", "da", "do", "das", "dos", "e", "para", "com", "n", "no", "nº", "num", "numero", "doc", "documento",
    "scan", "digitalizado", "pdf", "word", "docx", "editado", "modelo", "minuta", "ok", "def", "definitivo",
    "tabela", "lista", "cotacao", "recibo", "nota", "fiscal", "nf", "via", "anexo", "carta", "email",
    "e mail", "conversa", "whatsapp", "zap", "print", "foto", "imagem", "texto", "livre", "cabecalho", "rodape",
}


def parece_empresa(nome: str) -> bool:
    """O nome é de negócio (sufixo LTDA/ME..., ou palavra de negócio)?"""
    palavras = _normalizar(nome).split()
    if not palavras:
        return False
    if palavras[-1] in _SUFIXOS_DE_EMPRESA or " ".join(palavras[-2:]) in _SUFIXOS_DE_EMPRESA:
        return True
    if any(p in _PALAVRAS_DE_NEGOCIO for p in palavras):
        return True
    return bool(_EMPRESA_PELA_MARCA.match(nome.strip()) or _EMPRESA_PELO_SUFIXO.search(nome))


def _capitalizar_empresa(texto: str) -> str:
    """"OPEN SPICE SUSHI LOUNGE LTDA" -> "Open Spice Sushi Lounge Ltda"; "S/A" e "ME" ficam."""
    saida = []
    for posicao, palavra in enumerate(texto.split()):
        normal = _normalizar(palavra)
        if normal in ("me", "mei", "epp", "sa") or palavra.upper() in ("S/A", "S.A.", "S.A"):
            saida.append("S.A." if normal == "sa" else palavra.upper())
        elif posicao and normal in ("de", "da", "do", "das", "dos", "e"):
            saida.append(normal)
        else:
            saida.append(palavra[:1].upper() + palavra[1:].lower())
    return " ".join(saida)


def estabelecimento_do_arquivo(nome_arquivo: str, *, pessoas=(), empresa=None) -> str:
    """O nome do negócio escrito no NOME DO ARQUIVO, quando há.

    "CONTRATO OPEN SPICE SUSHI LOUNGE LTDA.docx" -> "Open Spice Sushi Lounge
    Ltda": o modelo de contrato da casa não escreve o nome do negócio no
    texto, mas quem salva o arquivo escreve. Saem as palavras de documento
    (contrato, orçamento, proposta, compra e venda, cópia, final, v2...), os
    números e as datas e a extensão. O que sobra vale se tem cara de
    negócio: sufixo de empresa, palavra de negócio, ou duas palavras ou
    mais que NÃO são o nome da pessoa já achada nem um nome de gente
    (primeiro nome da lista do IBGE). O nome da fábrica nunca.
    """
    base = re.sub(r"\.(docx?|pdf|odt|rtf)$", "", (nome_arquivo or "").strip(), flags=re.IGNORECASE)
    base = re.sub(r"\d{1,4}[-./_]\d{1,2}[-./_]\d{1,4}", " ", base)   # datas
    base = re.sub(r"\b[vV]\d+\b", " ", base)                          # v2, V3
    base = re.sub(r"\bS\.\s?A\.?(?=\s|$)|\bS/A\b", " SA ", base)   # S.A. e S/A antes de partir nos pontos
    palavras = []
    for palavra in re.split(r"[\s_\-–—.,;:()\[\]{}#]+", base):
        normal = _normalizar(palavra)
        if not normal or normal in _PALAVRAS_DE_DOCUMENTO or re.fullmatch(r"[\d\s]+", normal):
            continue
        if re.fullmatch(r"n[º°o]?\s?\d+|\d+[a-z]?", normal):
            continue
        palavras.append(palavra)
    # "de/da/do" que sobrou na ponta não é nome.
    while palavras and _normalizar(palavras[0]) in _LIGACOES:
        palavras.pop(0)
    while palavras and _normalizar(palavras[-1]) in _LIGACOES:
        palavras.pop()
    if not palavras:
        return ""
    candidato = " ".join(palavras)
    if empresa and det.linha_da_empresa(candidato, empresa):
        return ""
    if re.search(r"\blazer\b|\bsport\b", _normalizar(candidato)):
        return ""
    normal_palavras = set(_normalizar(candidato).split()) - set(_LIGACOES)
    for pessoa in pessoas:
        if pessoa and normal_palavras <= set(_normalizar(pessoa).split()):
            return ""  # o nome da pessoa (o cliente), e não o do negócio
    if len(normal_palavras) < 2:
        return ""  # uma palavra solta ("buffet", "marina") não é o nome de ninguém
    if not parece_empresa(candidato):
        # Sem cara de negócio, só nome escrito como nome (iniciais
        # maiúsculas, ou TUDO MAIÚSCULO) e que não seja de gente.
        if not all(p[:1].isupper() for p in palavras if _normalizar(p) not in _LIGACOES):
            return ""
        if _vale_como_pessoa(candidato):
            return ""
    return _capitalizar_empresa(candidato)


def _limpar_empresa(texto: str) -> str:
    texto = det.espacos(texto).strip(" -–—,;.:")
    # "Buffet Alegria Festas CNPJ" -> para antes de um rótulo de dado.
    texto = re.split(r"(?i)\s+(?:cnpj|cpf|cep|tel|telefone|e-?mail|whatsapp|n[º°]|no)\b", texto)[0]
    return det.capitalizar(texto.strip(" -–—,;.:"))


def _vale_como_pessoa(nome: str) -> bool:
    partes = _normalizar(nome).split()
    return bool(partes) and partes[0] not in _LIGACOES and partes[0] in primeiros_nomes()


#: O papel escrito colado no nome, sem dois-pontos: "COMPRADOR Renata
#: Moura Teixeira", "CONTRATANTE JOSÉ...". Sai da frente do nome e vira a
#: pista.
_PAPEIS_NA_FRENTE = {
    "comprador", "compradora", "contratante", "cliente", "locatario", "locataria", "adquirente",
    "solicitante", "destinatario", "destinataria",
}
#: Com o papel do cliente escrito logo antes, o nome vale mesmo que o
#: primeiro nome não esteja na lista do IBGE ("COMPRADOR Kethellyn ...").
_PISTAS_DE_PAPEL = re.compile(
    r"(?:contratante|locatari(?:[oa]|o\s*\(a\))|cliente|comprador(?:a|\s*\(a\))?|adquirente)\s*[:,.\-–—;]?\s*$"
)


def _tirar_papel_da_frente(texto: str, inicio: int) -> tuple[str, int]:
    """("COMPRADOR Renata Moura", 10) -> ("Renata Moura", 20)."""
    deslocamento = 0
    for palavra in re.finditer(r"\S+", texto):
        if _normalizar(re.sub(r"\(a\)$", "", palavra.group(0), flags=re.I)) in _PAPEIS_NA_FRENTE:
            deslocamento = palavra.end()
            continue
        break
    resto = texto[deslocamento:]
    espacos_na_frente = len(resto) - len(resto.lstrip())
    return resto.strip(), inicio + deslocamento + espacos_na_frente


def _nome_desconhecido_vale(nome: str) -> bool:
    """Nome inteiro com cara de nome, ainda que o primeiro não esteja na lista."""
    partes = nome.split()
    if len(partes) < 2 or len(partes) > 7:
        return False
    if _normalizar(partes[0]) in _LIGACOES or _normalizar(partes[-1]) in _LIGACOES:
        return False
    if sum(1 for parte in partes if _normalizar(parte) not in _LIGACOES) < 2:
        return False  # "Da Multa": uma palavra só de nome não basta
    for parte in partes:
        normal = _normalizar(parte)
        if normal in ("de", "da", "do", "das", "dos", "e"):
            continue
        if normal in _NAO_E_NOME or len(normal) < 2 or not normal.isalpha():
            return False
    return True


class _Candidatos:
    """Os candidatos de um campo, somando os pontos do mesmo valor."""

    def __init__(self):
        self.por_chave: dict[str, dict] = {}

    def acrescentar(self, valor, pontos, segmento, motivo, chave=None, pista=None):
        chave = chave or _normalizar(valor)
        if not chave:
            return
        atual = self.por_chave.get(chave)
        if atual is None:
            self.por_chave[chave] = {"valor": valor, "pontos": pontos, "vezes": 1, "motivo": motivo,
                                     "fonte": {"id": segmento["linha"]["id"], "texto": segmento["linha"]["texto"]},
                                     "posicao": segmento["posicao"], "pistas": {pista} - {None}}
            return
        atual["vezes"] += 1
        if pista:
            atual["pistas"].add(pista)
        if pontos > atual["pontos"]:
            atual.update(pontos=pontos, motivo=motivo, valor=valor,
                         fonte={"id": segmento["linha"]["id"], "texto": segmento["linha"]["texto"]},
                         posicao=segmento["posicao"])

    def ordenados(self):
        lista = []
        for item in self.por_chave.values():
            total = item["pontos"] + 0.75 * min(item["vezes"] - 1, 4)
            if item["vezes"] >= 2 and "cliente" in item["pistas"]:
                # O mesmo nome com o papel do cliente duas vezes -- na
                # apresentação das partes e na assinatura, embaixo de
                # "COMPRADOR" --: confirmação forte.
                total += 1.5
            lista.append(dict(item, total=round(total, 2)))
        return sorted(lista, key=lambda c: (-c["total"], c["posicao"]))


def _juntar_nomes_contidos(candidatos: _Candidatos):
    """"Juliana Martins" e "Juliana Martins Rocha" são a mesma pessoa: fica o maior."""
    chaves = sorted(candidatos.por_chave, key=lambda c: -len(c.split()))
    for menor in list(chaves):
        if menor not in candidatos.por_chave:
            continue
        partes_menor = menor.split()
        for maior in chaves:
            if maior == menor or maior not in candidatos.por_chave:
                continue
            partes_maior = maior.split()
            if len(partes_maior) > len(partes_menor) and partes_maior[:len(partes_menor)] == partes_menor:
                pequeno = candidatos.por_chave.pop(menor)
                grande = candidatos.por_chave[maior]
                grande["pontos"] = max(grande["pontos"], pequeno["pontos"]) + 0.5
                grande["vezes"] += pequeno["vezes"]
                grande["pistas"] |= pequeno["pistas"]
                break


def ler_endereco_livre(trecho: str) -> dict:
    """O endereço escrito em frase: vírgulas, "nº", "bairro", "na cidade de".

    "Rua das Acácias, nº 45, apto 12, bairro Jardim Paulista, na cidade de
    São Paulo/SP, CEP 01234-000" e "Rua Aurora, 155 apto 34, Santa
    Ifigênia, São Paulo SP, 01209-001". Com traços, vale `ler_endereco`.
    """
    partes = {"cep": "", "rua": "", "numero": "", "complemento": "", "bairro": "", "cidade": "", "uf": ""}
    texto = det.espacos(trecho)
    ceps = list(det._CEP.finditer(texto))
    if ceps:
        partes["cep"] = f"{ceps[-1].group(1)}-{ceps[-1].group(2)}"
        texto = texto[:ceps[-1].start()] + texto[ceps[-1].end():]
    texto = re.sub(r"(?i)\bCEP\b[:.]?", "", texto)
    # "São Paulo (SP)" e "Estado de São Paulo"
    texto = re.sub(r"\s*\(\s*([A-Za-z]{2})\s*\)", r"/\1", texto)
    pedacos = [p.strip(" .;:") for p in re.split(r"\s*,\s*|\s+[–—-]\s+|\s*;\s*", texto)]
    pedacos = [p for p in pedacos if p]
    if not pedacos:
        return partes
    rua = pedacos.pop(0)
    achado = re.fullmatch(r"(.+?)\s+(?:n[º°o.]?\s*|numero\s+)?(\d{1,6}[A-Za-z]?)(?:\s+(.+))?", rua)
    if achado and not re.search(r"\d", achado.group(1)[-3:]):
        rua, partes["numero"] = achado.group(1), achado.group(2)
        if achado.group(3):
            pedacos.insert(0, achado.group(3))
    partes["rua"] = rua
    complementos = []
    for pedaco in pedacos:
        sem = det.sem_acento(pedaco)
        numero = re.fullmatch(r"(?:n[º°o.]?\s*|numero\s+)?(\d{1,6}[A-Za-z]?|s/?n)(?:\s+(.+))?", pedaco, re.IGNORECASE)
        estado = re.fullmatch(r"(?:estado\s+de\s+|estado\s+do\s+)(.+)", sem)
        cidade_uf = re.fullmatch(r"(?:(?:na\s+)?cidade\s+de\s+|(?:no\s+)?municipio\s+de\s+)?(.+?)\s*[/\s]\s*([a-z]{2})", sem)
        if numero and not partes["numero"]:
            partes["numero"] = numero.group(1)
            if numero.group(2):
                complementos.append(numero.group(2))
        elif det._COMPLEMENTO.match(pedaco) or re.match(r"(?i)^\d+\s*[º°o]?\s*andar\b", pedaco):
            complementos.append(pedaco)
        elif estado and estado.group(1).strip() in _ESTADOS:
            partes["uf"] = partes["uf"] or _ESTADOS[estado.group(1).strip()]
        elif sem.strip() in _ESTADOS and not partes["uf"] and partes["cidade"]:
            partes["uf"] = _ESTADOS[sem.strip()]
        elif cidade_uf and cidade_uf.group(2).upper() in det.UFS and not partes["cidade"]:
            inicio = len(pedaco) - len(pedaco.lstrip())
            corte = re.match(r"(?i)^(?:(?:na\s+)?cidade\s+de\s+|(?:no\s+)?munic[íi]pio\s+de\s+)?", pedaco).end()
            nome_cidade = re.sub(r"\s*[/\s]\s*[A-Za-z]{2}$", "", pedaco[corte + inicio:]).strip()
            partes["cidade"], partes["uf"] = nome_cidade, cidade_uf.group(2).upper()
        elif pedaco.upper() in det.UFS and partes["cidade"] and not partes["uf"]:
            partes["uf"] = pedaco.upper()
        elif re.match(r"(?i)^(?:na\s+)?cidade\s+de\s+|^(?:no\s+)?munic[íi]pio\s+de\s+", pedaco) and not partes["cidade"]:
            partes["cidade"] = re.sub(r"(?i)^(?:na\s+)?cidade\s+de\s+|^(?:no\s+)?munic[íi]pio\s+de\s+", "", pedaco)
        elif re.match(r"(?i)^bairro\s+", pedaco):
            partes["bairro"] = re.sub(r"(?i)^bairro\s+", "", pedaco)
        elif not partes["bairro"] and not partes["cidade"]:
            partes["bairro"] = pedaco
        elif not partes["cidade"]:
            partes["cidade"] = pedaco
        else:
            complementos.append(pedaco)
    partes["complemento"] = ", ".join(complementos)
    return partes


_FIM_DO_ENDERECO = re.compile(
    r"(?i)(?:,?\s+(?:doravante|neste\s+ato|portador|inscrit|telefone|tel\.|celular|e-?mail|whatsapp|"
    r"meu\s+whats|onde|para\s+o\s+evento|no\s+dia)\b)|;|\.\s+(?=[A-ZÀ-Ý])"
)
_ABREVIACOES = re.compile(r"(?i)(?:\b(?:av|r|n|no|nº|jd|pq|vl|sta|sto|dr|dra|prof|cel|gal|eng|rod|estr|al|tv|trav|apto?|bl|cj|sl|pça|lj)\.)$")


def _trecho_do_endereco(texto: str, inicio: int) -> str:
    resto = texto[inicio:]
    posicao = 0
    while True:
        achado = _FIM_DO_ENDERECO.search(resto, posicao)
        if not achado:
            return resto
        if achado.group(0).startswith(".") and _ABREVIACOES.search(resto[:achado.start() + 1]):
            posicao = achado.end()
            continue
        # O CEP vem depois de um ponto às vezes: "..., São Paulo/SP. CEP 01234-000"
        trecho = resto[:achado.start()]
        seguinte = resto[achado.end():achado.end() + 20]
        if re.match(r"(?i)\s*CEP\b", seguinte):
            cep = det._CEP.search(resto, achado.end())
            if cep:
                return resto[:cep.end()]
        return trecho


def _endereco_da_empresa(partes: dict, empresa: dict) -> bool:
    rua_numero = _normalizar(f"{partes['rua']} {partes['numero']}")
    for linha in empresa.get("enderecos", ()):
        if linha and _normalizar(linha) == rua_numero:
            return True
    return bool(partes["cep"] and det.somente_digitos(partes["cep"]) in empresa.get("ceps", ()))


# ======================================================================
# A LEITURA
# ======================================================================
def identificar(linhas: list[dict], *, empresa: dict, internos: dict, fora=frozenset(),
                trechos_da_casa=None) -> dict:
    """Os candidatos de cada dado do cliente, já ordenados pelos pontos.

    Devolve {"pessoas", "empresas", "enderecos", "documentos", "telefones",
    "emails"}: listas de {"valor", "total", "motivo", "fonte"} (endereço:
    "valor" é o dicionário das partes).
    """
    segmentos = _segmentos(linhas)
    da_casa_no_contrato = lado_da_casa(linhas) if trechos_da_casa is None else trechos_da_casa
    da_empresa = {l["id"] for l in linhas if det.linha_da_empresa(l["texto"], empresa)}
    marcantes = {l["id"] for l in linhas if det.linha_da_empresa(l["texto"], empresa, pelo_endereco=False)}
    vizinhas = set()
    for posicao, linha in enumerate(linhas):
        if linha["id"] in marcantes:
            for vizinho in (posicao - 1, posicao + 1):
                if 0 <= vizinho < len(linhas) and linhas[vizinho]["parte"] == linha["parte"]:
                    vizinhas.add(linhas[vizinho]["id"])
    total_linhas = max(len(segmentos), 1)

    def usavel(segmento):
        linha = segmento["linha"]
        if linha["id"] in fora or linha["id"] in da_empresa:
            return False
        if linha["id"] in vizinhas:
            # O endereço colado no timbre é da casa; com "Cliente:" na
            # própria linha, é do cliente.
            return bool(re.match(
                r"(?i)\s*(cliente|contratante|comprador|locat[aá]ri|adquirente|nome|a/c|respons)", segmento["texto"],
            ))
        if linha["parte"] in ("cabecalho", "rodape"):
            return bool(re.search(r"(?i)\b(cliente|contratante|a/c|s[íi]ndic|respons[áa]vel)\b", segmento["texto"]))
        return True

    def timbre_do_cliente(segmento):
        """O cabeçalho que não é o da fábrica: o timbre do próprio cliente
        ("Buffet Sonho Mágico Ltda" no alto da carta dele). Só serve para o
        nome da empresa."""
        linha = segmento["linha"]
        return (linha["parte"] == "cabecalho" and linha["id"] not in fora and linha["id"] not in da_empresa
                and linha["id"] not in vizinhas)

    pessoas, empresas, enderecos = _Candidatos(), _Candidatos(), []
    documentos, telefones, emails = _Candidatos(), _Candidatos(), _Candidatos()
    ocupado: dict[str, list[tuple[int, int]]] = {}

    def bonus_de_posicao(segmento):
        return 1.0 if segmento["posicao"] / total_linhas < 0.4 else 0.0

    for indice, segmento in enumerate(segmentos):
        if not usavel(segmento):
            if timbre_do_cliente(segmento):
                for padrao in (_EMPRESA_PELO_SUFIXO, _EMPRESA_PELA_MARCA):
                    for achado in padrao.finditer(segmento["texto"]):
                        nome = _limpar_empresa(achado.group(0))
                        if len(nome) >= 5 and not det.linha_da_empresa(nome, empresa) and not eh_interno(nome, internos):
                            empresas.acrescentar(nome, 2.5, segmento, "no timbre do documento", pista="empresa")
            continue
        texto = segmento["texto"]
        id_linha = segmento["linha"]["id"]
        # O texto do segmento é o fim da linha (na conversa, sem o remetente):
        # o deslocamento leva a posição do segmento para a da linha.
        recuo = len(segmento["linha"]["texto"]) - len(texto) if segmento["remetente"] else 0

        def da_casa(inicio, fim=None):
            return no_lado_da_casa(da_casa_no_contrato, id_linha, inicio + recuo,
                                   None if fim is None else fim + recuo)

        anterior = segmentos[indice - 1]["texto"] if indice else ""
        # Pista sozinha na linha de cima: "À", "Contratante:", "Prezados,"
        pista_de_cima = None
        if anterior and len(anterior.strip()) <= 40:
            pista_de_cima = _pista(anterior.strip() + " ")
            if not pista_de_cima and _normalizar(anterior) in ("a", "ao", "aos", "a sra", "ao sr"):
                pista_de_cima = ("cliente", 4.0)

        # ------------------------------------------------- endereços
        for achado in _LOGRADOURO.finditer(texto):
            if da_casa(achado.start()):
                continue  # o endereço de quem assina pela casa ("residente na Rua...")
            trecho = _trecho_do_endereco(texto, achado.start())
            # Dois jeitos de escrever (com traço ou com vírgula): vale a
            # leitura que separa mais partes.
            leituras = [ler_endereco_livre(trecho)]
            if re.search(r"\s[–—-]\s|\|", trecho):
                leituras.append(det.ler_endereco(trecho))
            partes = max(leituras, key=lambda p: (bool(p["rua"]), sum(
                bool(p[c]) for c in ("numero", "bairro", "cidade", "uf", "cep"))))
            if not partes["rua"] or _endereco_da_empresa(partes, empresa):
                continue
            ocupado.setdefault(id_linha, []).append((achado.start(), achado.start() + len(trecho)))
            pontos = 1.0 + sum(1.0 for chave in ("numero", "cidade", "cep") if partes[chave])
            if _PISTA_DE_ENDERECO.search(det.sem_acento(texto[:achado.start()])[-60:] + " " +
                                         det.sem_acento(anterior)[-40:]):
                pontos += 3.0
            enderecos.append({"valor": partes, "total": pontos + bonus_de_posicao(segmento) * 0.5,
                              "motivo": "endereço escrito no documento",
                              "fonte": {"id": id_linha, "texto": segmento["linha"]["texto"]},
                              "posicao": segmento["posicao"]})

        def dentro_de_endereco(inicio, fim):
            return any(a <= inicio < b for a, b in ocupado.get(id_linha, ()))

        dados_na_linha = bool(det.documentos(texto) or det.telefones(texto) or det.emails(texto))

        # ------------------------------------------------- empresas
        vistos_empresa = []
        for padrao in (_EMPRESA_PELO_SUFIXO, _EMPRESA_PELA_MARCA):
            for achado in padrao.finditer(texto):
                if dentro_de_endereco(achado.start(), achado.end()) or da_casa(achado.start()):
                    continue
                if any(a <= achado.start() < b for a, b in vistos_empresa):
                    continue
                nome = _limpar_empresa(achado.group(0))
                if len(nome) < 5 or det.linha_da_empresa(nome, empresa) or eh_interno(nome, internos):
                    continue
                if _normalizar(nome) in ("empresa", "companhia"):
                    continue
                vistos_empresa.append((achado.start(), achado.end()))
                pista = _pista(texto[:achado.start()]) or pista_de_cima
                pontos = 1.5 + bonus_de_posicao(segmento) + (1.0 if dados_na_linha else 0.0)
                motivo = "nome de empresa no documento"
                if pista:
                    pontos += pista[1] if pista[0] in ("cliente", "empresa", "fora") else 1.0
                    if pista[0] in ("cliente", "empresa"):
                        motivo = "perto de “" + texto[:achado.start()].strip(" :,-")[-30:] + "”"
                if segmento["remetente"]:
                    pontos += 1.0
                empresas.acrescentar(nome, pontos, segmento, motivo, pista=pista[0] if pista else None)

        # "a empresa Open Spice", e o nome colado no CNPJ.
        for achado in _EMPRESA_CHAMADA_ASSIM.finditer(texto):
            if da_casa(achado.start(1)):
                continue
            nome = _limpar_empresa(achado.group(1))
            if len(nome) >= 4 and not det.linha_da_empresa(nome, empresa) and not eh_interno(nome, internos):
                empresas.acrescentar(nome, 4.0 + bonus_de_posicao(segmento), segmento,
                                     "perto de “empresa”", pista="empresa")
                vistos_empresa.append((achado.start(1), achado.end(1)))
        for documento in det.documentos(texto):
            if documento["tipo"] != "CNPJ" or da_casa(documento["inicio"]):
                continue
            achado = _NOME_ANTES_DO_CNPJ.search(texto[:documento["inicio"]])
            if not achado:
                continue
            nome = _limpar_empresa(achado.group(1))
            if len(nome) < 4 or det.linha_da_empresa(nome, empresa) or eh_interno(nome, internos):
                continue
            if _normalizar(nome) in ("razao social", "nome fantasia", "empresa", "inscrita"):
                continue
            empresas.acrescentar(nome, 3.0 + bonus_de_posicao(segmento), segmento,
                                 "o nome ao lado do CNPJ", pista="empresa")

        # ------------------------------------------------- pessoas
        if segmento["remetente"] and _vale_como_pessoa(segmento["remetente"]) \
                and not eh_interno(segmento["remetente"], internos):
            pessoas.acrescentar(det.capitalizar(segmento["remetente"]), 3.0, segmento, "quem escreve na conversa",
                                pista="cliente")
        titulo = titulo_de_secao(texto)
        for achado in _NOME.finditer(texto):
            if titulo:
                break  # "DA MULTA", "DO FORO": título de cláusula, nunca nome
            bruto, inicio_nome = _tirar_papel_da_frente(achado.group(0), achado.start())
            if not bruto:
                continue
            if dentro_de_endereco(inicio_nome, achado.end()) or da_casa(inicio_nome, achado.end()):
                continue
            if any(a <= inicio_nome < b for a, b in vistos_empresa):
                continue
            nome = det.capitalizar(_limpar_pessoa(bruto))
            if not nome or eh_interno(nome, internos):
                continue
            antes = texto[:inicio_nome]
            de_cima = pista_de_cima if inicio_nome < 3 else None
            if not _vale_como_pessoa(nome):
                # Primeiro nome fora da lista: vale só com o papel do cliente
                # escrito logo antes ("COMPRADOR Kethellyn Souza") ou na
                # linha de cima ("COMPRADOR" / o nome, na assinatura).
                papel = _PISTAS_DE_PAPEL.search(det.sem_acento(antes)[-30:]) or (
                    de_cima and inicio_nome < 3 and _PISTAS_DE_PAPEL.search(det.sem_acento(anterior.strip()))
                )
                if not papel or not _nome_desconhecido_vale(nome):
                    continue
            partes = nome.split()
            pista = _pista(antes) or de_cima
            pontos = 1.0 + bonus_de_posicao(segmento) + (1.0 if dados_na_linha else 0.0)
            motivo = "nome de pessoa no documento"
            if pista:
                pontos += pista[1]
                if pista[0] != "fora":
                    motivo = "perto de “" + (antes.strip(" :,-")[-30:] or anterior.strip()[-30:]) + "”"
            if len(partes) == 1:
                # Um nome só ("Prezada Ana") só vale com pista forte.
                if not pista or pista[1] < 4:
                    continue
                pontos -= 1.0
            pessoas.acrescentar(nome, pontos, segmento, motivo, pista=pista[0] if pista else None)

        # ---------------------------------- documento, telefone, e-mail
        sem = det.sem_acento(texto)
        for achado in det.documentos(texto):
            if da_casa(achado["inicio"]):
                continue
            pontos = 2.0 + (2.0 if achado["valido"] else -3.0)
            documentos.acrescentar(achado["chave"], pontos, segmento, f"{achado['tipo']} no documento",
                                   chave=achado["chave"])
        for achado in det.telefones(texto):
            if da_casa(achado["inicio"]):
                continue
            pontos = 1.5 + (1.0 if re.search(r"tel|cel|fone|whats|zap|contato|numero", sem) else 0.0)
            telefones.acrescentar(achado["digitos"], pontos, segmento, "telefone no documento",
                                  chave=achado["digitos"])
            if det._WHATSAPP.search(sem):
                telefones.por_chave[achado["digitos"]]["whatsapp"] = True
        for achado in det.emails(texto):
            if achado["email"] in internos.get("emails", ()) or da_casa(achado["inicio"]):
                continue
            emails.acrescentar(achado["email"], 2.0, segmento, "e-mail no documento", chave=achado["email"])
        if segmento["remetente"]:
            for achado in det.telefones(segmento["remetente"]):
                telefones.acrescentar(achado["digitos"], 4.0, segmento, "quem escreve na conversa",
                                      chave=achado["digitos"])

    _juntar_nomes_contidos(pessoas)
    enderecos.sort(key=lambda c: (-c["total"], c["posicao"]))
    return {
        "pessoas": [c for c in pessoas.ordenados() if c["total"] >= PONTOS_PARA_SUGERIR],
        "empresas": [c for c in empresas.ordenados() if c["total"] >= PONTOS_PARA_SUGERIR],
        "enderecos": enderecos,
        "documentos": documentos.ordenados(),
        "telefones": telefones.ordenados(),
        "emails": emails.ordenados(),
    }


# ======================================================================
# COMPLETAR A LEITURA POR REGRA
# ======================================================================
def _campo(valor, candidato, motivo=""):
    fonte = candidato["fonte"]
    return {"valor": valor, "original": valor if isinstance(valor, str) else str(valor),
            "fonte": {"id": fonte["id"], "texto": fonte["texto"]},
            "motivo": motivo or candidato.get("motivo", ""), "identificado": True}


def completar(campos: dict, achados: dict, *, internos: dict, empresa: dict, contrato: bool = False) -> dict:
    """Preenche, nos campos da leitura por regra, o que ela não achou.

    O rótulo escrito ("Cliente: ...") vale mais que qualquer palpite -- a
    não ser que o nome rotulado seja de alguém da casa, aí ele sai. Devolve
    as "outras leituras" de cada campo, para a conferência oferecer como
    botão.
    """
    alternativas: dict[str, list[dict]] = {}

    def sem_os_da_casa(nome_campo):
        valor = (campos.get(nome_campo) or {}).get("valor")
        if valor and isinstance(valor, str) and (eh_interno(valor, internos) or det.linha_da_empresa(valor, empresa)):
            campos.pop(nome_campo)

    for nome_campo in ("cliente", "contato", "estabelecimento"):
        sem_os_da_casa(nome_campo)
    # No contrato de compra e venda, "Comprador: Fulana" é o CLIENTE (fora
    # dele, o rótulo "Comprador" é a pessoa que compra pela empresa).
    rotulo_do_contato = det.sem_acento(((campos.get("contato") or {}).get("fonte") or {}).get("texto", ""))
    if contrato and "cliente" not in campos and re.match(r"\s*compr(?:ador|adora)\b", rotulo_do_contato):
        campos["cliente"] = campos.pop("contato")
    email = (campos.get("email") or {}).get("valor")
    if email and email in internos.get("emails", ()):
        campos.pop("email")

    pessoas = [c for c in achados["pessoas"] if c["total"] >= PONTOS_PARA_SUGERIR]
    empresas = [c for c in achados["empresas"] if c["total"] >= PONTOS_PARA_SUGERIR]
    usados = {_normalizar((campos.get(c) or {}).get("valor", "")) for c in ("cliente", "contato", "estabelecimento")}
    usados.discard("")

    def primeiro_livre(lista, minimo=0.0, pista=None):
        for candidato in lista:
            if _normalizar(candidato["valor"]) in usados or candidato["total"] < minimo:
                continue
            if pista and pista not in candidato["pistas"]:
                continue
            return candidato
        return None

    def usar(nome_campo, candidato):
        if candidato is None:
            return
        campos[nome_campo] = _campo(candidato["valor"], candidato, "lido do texto: " + candidato["motivo"])
        usados.add(_normalizar(candidato["valor"]))

    # QUEM É O CLIENTE, NESTA ORDEM: a empresa que o texto chama de
    # contratante/cliente; a pessoa que ele chama assim; a pessoa com mais
    # pontos; a empresa. A empresa cliente leva a pessoa como contato; a
    # pessoa cliente leva a empresa como estabelecimento.
    if "cliente" not in campos:
        empresa_cliente = primeiro_livre(empresas, PONTOS_PARA_PREENCHER, "cliente") \
            or primeiro_livre(empresas, PONTOS_PARA_PREENCHER, "empresa")
        pessoa_cliente = primeiro_livre(pessoas, PONTOS_PARA_PREENCHER, "cliente")
        if empresa_cliente and not pessoa_cliente:
            usar("cliente", empresa_cliente)
        elif pessoa_cliente:
            usar("cliente", pessoa_cliente)
        elif primeiro_livre(pessoas, PONTOS_PARA_PREENCHER) and not (
            "contato" in campos and primeiro_livre(empresas, 2.0)
        ):
            usar("cliente", primeiro_livre(pessoas, PONTOS_PARA_PREENCHER))
        elif primeiro_livre(empresas, 2.0):
            usar("cliente", primeiro_livre(empresas, 2.0))
    cliente_valor = _normalizar((campos.get("cliente") or {}).get("valor", ""))
    cliente_e_empresa = bool(cliente_valor) and (
        any(_normalizar(c["valor"]) == cliente_valor for c in empresas)
        or bool(_EMPRESA_PELA_MARCA.search((campos.get("cliente") or {}).get("valor", ""))
                or _EMPRESA_PELO_SUFIXO.search((campos.get("cliente") or {}).get("valor", "")))
    )
    if cliente_e_empresa:
        if "contato" not in campos:
            usar("contato", primeiro_livre(pessoas, 2.5))
    elif "estabelecimento" not in campos:
        usar("estabelecimento", primeiro_livre(empresas, 2.0))

    # O que sobrou de nome vira opção, nos campos de nome.
    sobras = [c for c in pessoas + empresas if _normalizar(c["valor"]) not in usados][:4]
    for nome_campo in ("cliente", "estabelecimento", "contato"):
        alternativas[nome_campo] = [
            {"valor": c["valor"], "fonte": c["fonte"], "motivo": c["motivo"]} for c in sobras
        ]

    # ------------------------------------------------------- dados
    def completar_lista(nome_campo, lista, formatar):
        validos = [c for c in lista if c["total"] >= 1.0]
        if nome_campo not in campos and validos:
            melhor = validos[0]
            campos[nome_campo] = _campo(melhor["valor"], melhor, "lido do texto: " + melhor["motivo"])
            if nome_campo == "telefone":
                campos[nome_campo]["whatsapp_escrito"] = bool(melhor.get("whatsapp"))
            if nome_campo == "documento":
                chave = melhor["valor"]
                campos[nome_campo]["valido"] = det.documentos(det.formatar_documento(chave))[0]["valido"] \
                    if det.documentos(det.formatar_documento(chave)) else False
        escolhido = det.somente_digitos(str((campos.get(nome_campo) or {}).get("valor", ""))) \
            if nome_campo != "email" else (campos.get(nome_campo) or {}).get("valor", "")
        alternativas[nome_campo] = [
            {"valor": formatar(c["valor"]), "fonte": c["fonte"], "motivo": c["motivo"]}
            for c in validos
            if (det.somente_digitos(c["valor"]) if nome_campo != "email" else c["valor"]) != escolhido
        ][:3]

    completar_lista("documento", achados["documentos"], det.formatar_documento)
    completar_lista("telefone", achados["telefones"], det.formatar_telefone)
    completar_lista("email", achados["emails"], lambda v: v)

    # ------------------------------------------------------- endereço
    tem_endereco = any(campos.get(c) for c in ("endereco", "logradouro"))
    enderecos = achados["enderecos"]
    if not tem_endereco and enderecos:
        melhor = enderecos[0]
        for parte, nome_campo in (("cep", "cep"), ("rua", "logradouro"), ("numero", "numero"),
                                  ("complemento", "complemento"), ("bairro", "bairro"),
                                  ("cidade", "cidade"), ("uf", "uf")):
            if melhor["valor"][parte] and nome_campo not in campos:
                campos[nome_campo] = _campo(melhor["valor"][parte], melhor,
                                            "lido do texto: " + melhor["motivo"])
    alternativas["endereco"] = [
        {"valor": e["valor"], "fonte": e["fonte"], "motivo": e["motivo"]} for e in enderecos[1:3]
    ]
    return alternativas
