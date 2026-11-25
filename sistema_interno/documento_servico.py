"""A ORDEM DE SERVIÇO assinada no celular -- manutenção e serviços (LEIA-ME-V10, 124).

O PEDIDO DO DONO: "veja também referente aos orçamentos e os sem receber o
pagamento, também deve emitir contrato ou ordem de serviço, destinado a
manutenções e serviços, para padronizar."

O QUE ESTE MÓDULO FAZ. O contrato de compra e venda (`contrato.py`) é o
papel da VENDA de um equipamento. Manutenção, instalação, revisão e visita
técnica são outra coisa: o cliente não compra o brinquedo, contrata um
serviço sobre ele. Este módulo monta o papel padronizado desse serviço --
"ORDEM DE SERVIÇO E CONTRATO DE PRESTAÇÃO DE SERVIÇOS" -- com:

  * a empresa (CONTRATADA) e o representante lidos de `DadosContrato`,
    o mesmo lugar do contrato de compra e venda (nada pessoal no código);
  * o cliente (CONTRATANTE), o equipamento, a identificação, o defeito
    relatado, o diagnóstico, o serviço a fazer ou feito, o local, a
    agenda, o técnico e a garantia;
  * as linhas de serviço e peça com os valores, o frete/deslocamento, o
    desconto e o total -- em número e por extenso;
  * a SITUAÇÃO DO PAGAMENTO na emissão, escrita do jeito certo: "nenhum
    valor recebido até a emissão" quando nada entrou, a entrada e o saldo
    quando é parcial, "quitado" só quando está quitado;
  * as onze cláusulas de serviço (objeto, execução, acesso ao local,
    peças, obrigações do contratante, garantia, pagamento, atraso,
    cancelamento, dados pessoais e foro), no estilo do contrato da
    empresa. O TEXTO DAS CLÁUSULAS É UM MODELO GENÉRICO: o dono deve
    revisá-lo (está dito no LEIA-ME, seção 124).

DE ONDE ELE SAI. De duas origens, com o MESMO papel:

  1. da O.S. (`gerar_da_ordem`), em qualquer situação que não seja
     rascunho, cancelada ou substituída -- com ou sem pagamento;
  2. do orçamento APROVADO de manutenção ou serviço
     (`retrato_do_orcamento`, chamado por `documento_assinatura.gerar`),
     também sem exigir pagamento. Se o orçamento é de serviço ou de venda
     sai de `sugestao_do_orcamento` (pelos itens), e a tela deixa trocar
     (chips "Contrato de compra e venda" / "Ordem de serviço").

O RESTO É O DO CONTRATO. O retrato congelado com o SHA-256, o link de 10
minutos com o QR e o WhatsApp, a página do cliente, o CPF conferido, o
traço do dedo, o diário de bordo, a via em PDF e a trilha de auditoria
moram em `documento_assinatura.py` e valem igual para os dois papéis.
A tabela é a mesma (`DocumentoAssinatura`, com `ordem_servico` em vez de
`orcamento`).

E A CIÊNCIA DA O.S.? A O.S. já tinha um link permanente para o cliente
consultar e "confirmar ciência" digitando o nome. O documento assinado é
a evolução dele: assinar a ordem de serviço REGISTRA a ciência
(`depois_de_assinar`), e a página da O.S. troca o "confirmar ciência" por
"assine pelo link" enquanto o documento espera, e pelo comprovante depois.
O link permanente continua sendo o da consulta e do Pix -- não há dois
caminhos para o cliente aceitar a mesma O.S.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import DocumentoAssinatura, ItemOrdemServico, OrdemServico, Orcamento
from .utils import ErroDeFormulario

log = logging.getLogger(__name__)

#: O tipo que o retrato carrega (o contrato de venda é "contrato").
TIPO = "servico"

#: Muda quando o TEXTO mudar: o retrato guarda a versão, e o que já foi
#: assinado continua dizendo o que dizia.
VERSAO_DO_MODELO = "2026-11-os1"

TITULO = "ORDEM DE SERVIÇO E CONTRATO DE PRESTAÇÃO DE SERVIÇOS"
TITULO_CURTO = "Ordem de serviço"

#: A garantia do serviço quando a O.S. não diz outra: os 90 dias da
#: garantia legal dos serviços duráveis (CDC, art. 26, II).
GARANTIA_PADRAO_DIAS = 90

# ----------------------------------------------------------------------
# Os dois papéis que um orçamento aprovado pode gerar (os chips da tela).
# ----------------------------------------------------------------------
MODELO_COMPRA_E_VENDA = "compra_venda"
MODELO_SERVICO = "servico"
MODELOS = (
    (MODELO_COMPRA_E_VENDA, "Contrato de compra e venda"),
    (MODELO_SERVICO, "Ordem de serviço (manutenção e serviços)"),
)

#: As situações da O.S. em que o documento NÃO sai: o rascunho ainda não
#: é um serviço combinado, a cancelada não tem serviço e a substituída é
#: história (o documento sai da versão que vale).
SITUACOES_SEM_DOCUMENTO = (
    OrdemServico.Status.RASCUNHO,
    OrdemServico.Status.CANCELADA,
    OrdemServico.Status.SUBSTITUIDA,
)

#: O nome do serviço na Cláusula 1ª, pelo tipo da O.S.
SERVICO_DO_TIPO = {
    OrdemServico.Tipo.MANUTENCAO: "manutenção",
    OrdemServico.Tipo.INSTALACAO: "instalação",
    OrdemServico.Tipo.REVISAO: "revisão preventiva",
    OrdemServico.Tipo.VISITA: "visita técnica",
    OrdemServico.Tipo.OUTRO: "prestação de serviço",
}


def e_servico(conteudo) -> bool:
    """O retrato é desta ordem de serviço (e não do contrato de venda)?"""
    return (conteudo or {}).get("tipo") == TIPO


# ======================================================================
# PEQUENAS PEÇAS
# ======================================================================
def _dinheiro(valor) -> str:
    return f"{Decimal(valor or 0).quantize(Decimal('0.01')):.2f}"


def _reais(valor) -> str:
    from core.formatos import dinheiro

    return dinheiro(valor, prefixo="R$")


def _texto(valor) -> str:
    return " ".join(str(valor or "").split())


def _paragrafos(valor) -> str:
    """O texto livre como foi escrito, sem espaço sobrando nas pontas."""
    linhas = [" ".join(linha.split()) for linha in str(valor or "").splitlines()]
    return "\n".join(linha for linha in linhas if linha).strip()


def _data(quando) -> str:
    if not quando:
        return ""
    if hasattr(quando, "hour"):
        quando = timezone.localtime(quando)
    return quando.strftime("%d/%m/%Y")


def _data_hora(quando) -> str:
    if not quando:
        return ""
    return timezone.localtime(quando).strftime("%d/%m/%Y às %H:%M")


def _nome_de(usuario) -> str:
    if usuario is None:
        return ""
    return (usuario.get_full_name() or "").strip() or usuario.get_username()


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", (texto or "").lower())
    return " ".join("".join(c for c in texto if unicodedata.category(c) != "Mn").split())


# ======================================================================
# O ORÇAMENTO É DE VENDA OU DE SERVIÇO?
# ======================================================================
#: Palavras que, numa linha escrita à mão, dizem "serviço" (sem acento,
#: minúsculas -- ver `_normalizar`).
_PALAVRAS_DE_SERVICO = re.compile(
    r"\b(manutenc\w*|consert\w*|repar\w*|mao de obra|servic\w*|instalac\w*|"
    r"desinstalac\w*|revis\w*|visita\w*|troca\w*|substituic\w*|deslocament\w*|"
    r"diagnostic\w*|laudo\w*|recuperac\w*|reforma\w*|higieniz\w*|limpeza\w*|"
    r"regulag\w*|ajuste\w*|montagem|desmontagem|vistoria\w*|tecnic[oa]s?)\b"
)


def sugestao_do_orcamento(orcamento) -> tuple[str, str]:
    """O papel que o orçamento aprovado pede, e por quê: (modelo, motivo).

    Pelo que dá para conferir nos itens (já carregados com o orçamento):

      * algum equipamento do catálogo (brinquedo) ou da fábrica (produto)
        -> é VENDA ("Contrato de compra e venda");
      * só serviços (linhas escritas à mão que dizem manutenção, conserto,
        mão de obra, instalação, revisão, visita, troca...) e peças, com
        ao menos um serviço ou item de manutenção -> é SERVIÇO;
      * peças da loja sozinhas, ou linhas que não dizem o que são -> VENDA
        (o papel de sempre), e a tela pede para conferir.

    A tela sempre mostra os dois chips com este já marcado: a sugestão
    poupa o clique, não decide sozinha.
    """
    from core.models import PecasReposicao

    itens = list(orcamento.itens.all())
    if not itens:
        return MODELO_COMPRA_E_VENDA, "O orçamento não tem itens."
    equipamentos = [i for i in itens if i.brinquedo_id or i.produto_id]
    if equipamentos:
        return MODELO_COMPRA_E_VENDA, (
            "Tem equipamento do catálogo ou da fábrica nos itens: é uma venda."
        )
    pecas = [i for i in itens if i.peca_id]
    soltas = [i for i in itens if not i.peca_id]
    servicos = [i for i in soltas if _PALAVRAS_DE_SERVICO.search(_normalizar(i.descricao))]
    outras = [i for i in soltas if i not in servicos]
    de_manutencao = 0
    if pecas:
        de_manutencao = PecasReposicao.objects.filter(
            pk__in={i.peca_id for i in pecas}, uso=PecasReposicao.Uso.MANUTENCAO,
        ).count()
    if not outras and (servicos or de_manutencao):
        partes = []
        if servicos:
            partes.append(f"{len(servicos)} serviço{'s' if len(servicos) != 1 else ''}")
        if pecas:
            partes.append(f"{len(pecas)} peça{'s' if len(pecas) != 1 else ''}")
        return MODELO_SERVICO, (
            "Os itens são de manutenção e serviço (" + " e ".join(partes) + "): "
            "sai a ordem de serviço."
        )
    if outras:
        return MODELO_COMPRA_E_VENDA, (
            "Os itens não dizem se é venda ou serviço: confira a escolha antes de gerar."
        )
    return MODELO_COMPRA_E_VENDA, "Só peças da loja: é uma venda de peças."


def modelo_do_orcamento(orcamento, pedido=None, anteriores=()) -> str:
    """O papel que `documento_assinatura.gerar` monta para este orçamento.

    O escolhido na tela (`pedido`) vale; sem escolha, o do documento que
    está sendo refeito ("Gerar de novo" não troca o papel sozinho); sem
    nenhum dos dois, a sugestão pelos itens.
    """
    pedido = (pedido or "").strip()
    if pedido:
        if pedido not in dict(MODELOS):
            raise ErroDeFormulario(
                "Escolha o documento: contrato de compra e venda ou ordem de serviço."
            )
        return pedido
    for documento in anteriores:
        if not documento.assinado:
            return MODELO_SERVICO if e_servico(documento.conteudo) else MODELO_COMPRA_E_VENDA
    return sugestao_do_orcamento(orcamento)[0]


# ======================================================================
# O PAGAMENTO, ESCRITO DO JEITO CERTO
# ======================================================================
_ORIGEM_DA_CONDICAO = {
    "escrita": "escrita na ordem de serviço",
    "texto": "lida do texto",
    "pagamento": "tirada do pagamento registrado",
    "padrao": "no padrão, porque nada diz",
}


def condicao_de_pagamento(fonte, *, total, pago, quitado, pago_em) -> tuple[str, str]:
    """A condição da Cláusula 7ª e de onde ela veio. NUNCA vazia.

    1. o que a equipe escreveu em "Forma de pagamento";
    2. o trecho de pagamento do texto (observação do pagamento,
       observações) -- "50% na aprovação e 50% na conclusão";
    3. o pagamento registrado (quitado, ou a entrada e o saldo);
    4. o padrão: à vista, na conclusão do serviço.
    """
    from .contrato import _condicao_no_texto

    escrita = _texto(getattr(fonte, "forma_pagamento", ""))
    if escrita:
        return escrita, "escrita"
    for campo in ("observacao_pagamento", "observacoes"):
        achada = _condicao_no_texto(getattr(fonte, campo, ""))
        if achada:
            return achada, "texto"
    em = f" em {_data(pago_em)}" if pago_em else ""
    if total > 0 and (quitado or pago >= total):
        return f"à vista, em parcela única, quitado{em}", "pagamento"
    if pago > 0:
        return (
            f"entrada de {_reais(pago)} já paga e o saldo de {_reais(total - pago)} "
            "na conclusão do serviço"
        ), "pagamento"
    return "à vista, na conclusão do serviço", "padrao"


def situacao_do_pagamento(*, total, pago, quitado, pago_em) -> dict:
    """Em que pé está o pagamento NA EMISSÃO -- sem dizer "pago" do que não está.

    `codigo`: "sem_custo", "pago", "parcial" ou "pendente". `texto` é a
    frase do papel, `rotulo` a palavra do selo.
    """
    total = Decimal(total or 0)
    pago = max(Decimal(pago or 0), Decimal("0.00"))
    if total <= 0:
        return {
            "codigo": "sem_custo", "rotulo": "Sem custo",
            "texto": "Não há valor a pagar por esta ordem de serviço (total de R$ 0,00).",
        }
    if quitado or pago >= total:
        em = f" em {_data(pago_em)}" if pago_em else ""
        return {
            "codigo": "pago", "rotulo": "Pago",
            "texto": f"Valor integralmente pago{em}: {_reais(max(pago, total))}.",
        }
    if pago > 0:
        return {
            "codigo": "parcial", "rotulo": "Pagamento parcial",
            "texto": (
                f"Recebido até a emissão deste documento: {_reais(pago)}. "
                f"Saldo a pagar: {_reais(total - pago)}."
            ),
        }
    return {
        "codigo": "pendente", "rotulo": "Pagamento pendente",
        "texto": (
            "Nenhum valor foi recebido até a emissão deste documento. "
            f"Valor a pagar: {_reais(total)}."
        ),
    }


# ======================================================================
# AS CLÁUSULAS
# ======================================================================
def _clausula(numero, texto, **extra):
    return {"numero": numero, "rotulo": f"Cláusula {numero}ª.", "texto": texto, **extra}


def _paragrafo(rotulo, texto):
    return {"rotulo": rotulo, "texto": texto}


def _com_ponto(texto: str) -> str:
    texto = (texto or "").strip()
    return texto if not texto or texto[-1] in ".!?;" else texto + "."


def secoes(*, objeto, prazo_texto, garantia_texto, total, total_texto,
           total_extenso, condicao, pagamento_texto, foro) -> list[dict]:
    """As onze cláusulas, já com os dados do serviço.

    MODELO GENÉRICO, PARA O DONO REVISAR (LEIA-ME-V10, seção 124): o estilo
    é o do contrato de compra e venda da empresa (seções em maiúsculas,
    "Cláusula Nª.", parágrafos), e o conteúdo é o de uma prestação de
    serviço de manutenção comum, com as referências do CDC e da LGPD.
    """
    if total > 0:
        setima = _clausula(
            7,
            "Pelos serviços e peças descritos nesta ordem de serviço, o CONTRATANTE "
            f"pagará à CONTRATADA o valor total de R$ {total_texto} ({total_extenso}), "
            "já considerados o frete ou deslocamento e os descontos indicados no "
            "quadro de valores, da seguinte forma:",
            complemento="Condição de pagamento: " + _com_ponto(condicao),
            situacao="Situação do pagamento na emissão: " + pagamento_texto,
        )
    else:
        setima = _clausula(
            7,
            "Os serviços e peças descritos nesta ordem de serviço não têm custo para "
            "o CONTRATANTE (valor total de R$ 0,00), seja por estarem em garantia, "
            "seja por cortesia da CONTRATADA.",
            situacao="Situação do pagamento na emissão: " + pagamento_texto,
        )
    return [
        {
            "titulo": "DO OBJETO",
            "clausulas": [
                _clausula(
                    1, objeto,
                    paragrafos=[_paragrafo(
                        "Parágrafo único.",
                        "Serviços ou peças que não constem desta ordem de serviço "
                        "dependem de novo orçamento e da aprovação prévia do CONTRATANTE.",
                    )],
                ),
            ],
        },
        {
            "titulo": "DA EXECUÇÃO E DO ACESSO AO LOCAL",
            "clausulas": [
                _clausula(
                    2,
                    "A CONTRATADA executará o serviço por meio de técnicos de sua "
                    "equipe, com as ferramentas e os materiais adequados, observando "
                    "as normas técnicas aplicáveis e as orientações do fabricante do "
                    "equipamento. " + prazo_texto,
                    paragrafos=[
                        _paragrafo(
                            "Parágrafo primeiro.",
                            "Se, durante a execução, for constatado defeito diferente do "
                            "relatado ou a necessidade de serviço ou peça não previstos, a "
                            "CONTRATADA comunicará o CONTRATANTE e emitirá nova versão "
                            "desta ordem de serviço, que somente será executada após a "
                            "sua aprovação.",
                        ),
                        _paragrafo(
                            "Parágrafo segundo.",
                            "Os prazos ficam prorrogados pelo tempo em que a execução "
                            "estiver impedida por falta de acesso ao local, por condições "
                            "climáticas que comprometam a segurança, pela espera de peça "
                            "de reposição ou por outro motivo alheio à vontade da "
                            "CONTRATADA, que informará o novo prazo ao CONTRATANTE.",
                        ),
                    ],
                ),
                _clausula(
                    3,
                    "O CONTRATANTE garantirá à equipe técnica, na data combinada, o "
                    "acesso ao local do serviço e ao equipamento, com espaço livre e "
                    "seguro para o trabalho, ponto de energia elétrica adequado quando "
                    "necessário e a presença de um responsável para acompanhar e "
                    "receber o serviço.",
                    paragrafos=[_paragrafo(
                        "Parágrafo único.",
                        "Se a visita não puder ser realizada por ausência do responsável "
                        "ou por impedimento de acesso, uma nova data será combinada entre "
                        "as partes, e o deslocamento da visita perdida poderá ser cobrado "
                        "quando previsto nesta ordem de serviço.",
                    )],
                ),
            ],
        },
        {
            "titulo": "DAS PEÇAS DE REPOSIÇÃO",
            "clausulas": [
                _clausula(
                    4,
                    "As peças e os materiais aplicados no serviço são os relacionados "
                    "nesta ordem de serviço. A CONTRATADA empregará componentes de "
                    "reposição novos e originais, ou que mantenham as especificações "
                    "técnicas do fabricante, salvo autorização expressa do CONTRATANTE "
                    "em sentido diverso, nos termos do artigo 21 do Código de Defesa do "
                    "Consumidor.",
                    paragrafos=[_paragrafo(
                        "Parágrafo único.",
                        "As peças substituídas ficam à disposição do CONTRATANTE na "
                        "entrega do serviço; as que não forem retiradas poderão ser "
                        "descartadas pela CONTRATADA de forma ambientalmente adequada.",
                    )],
                ),
            ],
        },
        {
            "titulo": "DAS OBRIGAÇÕES DO CONTRATANTE",
            "clausulas": [
                _clausula(
                    5,
                    # "a)", e não "(a)": na fonte do papel, "(c)" vira o símbolo ©.
                    "São obrigações do CONTRATANTE: a) informar com veracidade o "
                    "defeito apresentado e o histórico de uso do equipamento; b) não "
                    "permitir a intervenção de terceiros no equipamento durante a "
                    "execução do serviço; c) utilizar o equipamento conforme as "
                    "orientações de uso e de segurança do fabricante e da CONTRATADA, "
                    "respeitando os limites de idade, peso e número de usuários; e d) "
                    "efetuar o pagamento na forma da Cláusula 7ª.",
                ),
            ],
        },
        {
            "titulo": "DA GARANTIA",
            "clausulas": [
                _clausula(
                    6,
                    "A CONTRATADA garante o serviço executado e as peças por ela "
                    "fornecidas e aplicadas, contra defeitos de execução e de "
                    f"fabricação, {garantia_texto}, sem prejuízo da garantia legal "
                    "prevista no artigo 26, inciso II, do Código de Defesa do "
                    "Consumidor.",
                    paragrafos=[
                        _paragrafo(
                            "Parágrafo primeiro.",
                            "A garantia não cobre defeitos causados por mau uso, uso em "
                            "desacordo com as orientações do fabricante ou da CONTRATADA, "
                            "sobrecarga, acidentes, quedas, vandalismo, agentes da "
                            "natureza, desgaste natural de partes de consumo, nem "
                            "intervenção de terceiros não autorizada pela CONTRATADA, "
                            "hipótese em que a garantia se perde.",
                        ),
                        _paragrafo(
                            "Parágrafo segundo.",
                            "Para acionar a garantia, o CONTRATANTE comunicará o defeito "
                            "à CONTRATADA pelos canais de atendimento, informando o número "
                            "desta ordem de serviço. O equipamento será avaliado por "
                            "técnico da CONTRATADA e, constatado defeito por mau uso, será "
                            "emitido orçamento para o reparo.",
                        ),
                    ],
                ),
            ],
        },
        {
            "titulo": "DO PREÇO E DO PAGAMENTO",
            "clausulas": [
                setima,
                _clausula(
                    8,
                    "O atraso no pagamento sujeitará o CONTRATANTE à multa de 2% (dois "
                    "por cento) sobre o valor em atraso, a juros de mora de 1% (um por "
                    "cento) ao mês e à correção monetária, até o efetivo pagamento.",
                    paragrafos=[_paragrafo(
                        "Parágrafo único.",
                        "A tolerância da CONTRATADA com eventual atraso, com ou sem a "
                        "cobrança de multa, juros e correção, é mera liberalidade e não "
                        "configura novação nem renúncia aos seus direitos.",
                    )],
                ),
            ],
        },
        {
            "titulo": "DO CANCELAMENTO",
            "clausulas": [
                _clausula(
                    9,
                    "O CONTRATANTE poderá cancelar o serviço antes do início da "
                    "execução, sem ônus, mediante comunicação à CONTRATADA. Iniciada a "
                    "execução, serão devidos o serviço já realizado, as peças já "
                    "aplicadas ou adquiridas especificamente para o equipamento e o "
                    "deslocamento já efetuado. Resguardado o direito de arrependimento "
                    "previsto no artigo 49 do Código de Defesa do Consumidor, quando "
                    "cabível.",
                    paragrafos=[_paragrafo(
                        "Parágrafo único.",
                        "A CONTRATADA poderá suspender ou reagendar a execução quando as "
                        "condições do local ou do equipamento não permitirem o trabalho "
                        "com segurança, comunicando o CONTRATANTE.",
                    )],
                ),
            ],
        },
        {
            "titulo": "DOS DADOS PESSOAIS",
            "clausulas": [
                _clausula(
                    10,
                    "Os dados pessoais do CONTRATANTE informados neste documento são "
                    "tratados pela CONTRATADA exclusivamente para a execução deste "
                    "contrato, a emissão de documentos fiscais, o atendimento em "
                    "garantia e o cumprimento de obrigações legais, nos termos da Lei "
                    "nº 13.709/2018 (Lei Geral de Proteção de Dados), e não são "
                    "compartilhados com terceiros fora dessas finalidades. O "
                    "CONTRATANTE pode pedir o acesso, a correção ou a eliminação dos "
                    "seus dados pelos canais de atendimento, observados os prazos "
                    "legais de guarda.",
                ),
            ],
        },
        {
            "titulo": "DO FORO",
            "clausulas": [
                _clausula(
                    11,
                    "Para dirimir quaisquer controvérsias oriundas do presente "
                    f"instrumento, as partes elegem o foro da Comarca de {foro}, por "
                    "mais privilegiado que outro seja, ressalvado ao CONTRATANTE "
                    "consumidor o direito de propor a ação no foro do seu domicílio "
                    "(artigo 101, inciso I, do Código de Defesa do Consumidor).",
                ),
            ],
        },
    ]


#: O foro do contrato de compra e venda da empresa (Cláusula 11ª de lá).
FORO = "São Paulo"

FECHO = (
    "Por estarem assim justos e contratados, as partes firmam o presente "
    "instrumento, que vale como ordem de serviço e contrato de prestação de "
    "serviços, em duas vias de igual teor, na presença de duas testemunhas."
)


def preambulo(prestador: dict) -> dict:
    """A abertura (com a CONTRATADA por inteiro) e o fechamento do preâmbulo.

    O representante em branco não trava o documento (a mesma regra do
    contrato de venda): sai "seu representante legal".
    """
    nome = prestador.get("representante_nome") or ""
    representante = nome or "seu representante legal"
    if nome and prestador.get("representante_rg"):
        representante += f", portador da cédula de identidade RG: {prestador['representante_rg']}"
    if nome and prestador.get("representante_endereco"):
        representante += f", residente e domiciliado na {prestador['representante_endereco']}"
    empresa = prestador.get("nome_fantasia") or prestador.get("razao_social") or "a empresa prestadora"
    partes = [empresa]
    if prestador.get("razao_social") and prestador.get("razao_social") != empresa:
        partes.append(f"razão social {prestador['razao_social']}")
    if prestador.get("cnpj"):
        partes.append(f"devidamente inscrita no CNPJ sob o n. {prestador['cnpj']}")
    if prestador.get("endereco_sede"):
        partes.append(f"com sede na {prestador['endereco_sede']}")
    return {
        "abertura": (
            "Pelo presente INSTRUMENTO PARTICULAR DE PRESTAÇÃO DE SERVIÇOS, que vale "
            # A mesma redação do contrato de venda (seção 141), com a
            # concordância da O.S.: a CONTRATADA é "denominada" e
            # "representada"; o resto ("comparecem aqui, as partes, de um
            # lado", "aqui doravante", "RG:") é igual.
            "também como ORDEM DE SERVIÇO, e na forma da Lei, comparecem aqui, as "
            "partes, de um lado, na qualidade de prestadora dos serviços, aqui doravante "
            "denominada simplesmente CONTRATADA: " + ", ".join(partes)
            + f", neste ato representada por {representante}; e, do outro lado, na "
            "qualidade de tomador dos serviços, aqui doravante denominado simplesmente "
            "CONTRATANTE:"
        ),
        "fechamento": (
            "As partes acima identificadas têm, entre si, justo e acertado o presente "
            "instrumento de prestação de serviços, que se regerá pelas cláusulas "
            "seguintes e pelas condições de serviço, preço, forma de pagamento e prazo "
            "descritas nesta ordem de serviço."
        ),
    }


# ======================================================================
# O RETRATO
# ======================================================================
def _cliente(*, nome, cliente, telefone, email, endereco_cliente):
    from .documento_assinatura import _endereco_completo

    return {
        "nome": nome,
        "documento": (cliente.documento or "").strip() if cliente else "",
        "telefone": telefone or (cliente.telefone if cliente and cliente.telefone else ""),
        "email": email or "",
        "endereco": _endereco_completo(endereco_cliente),
    }


def _garantia(garantia_ate) -> dict:
    from .contrato import numero_por_extenso

    if garantia_ate:
        data = garantia_ate.strftime("%d/%m/%Y")
        return {"dias": None, "ate": data, "texto": f"até {data}", "rotulo": f"Até {data}"}
    dias = GARANTIA_PADRAO_DIAS
    return {
        "dias": dias,
        "ate": "",
        "texto": (
            f"pelo prazo de {dias} ({numero_por_extenso(dias)}) dias, contados da "
            "conclusão do serviço"
        ),
        "rotulo": f"{dias} dias após a conclusão",
    }


def _montar(*, origem, numero, versao, codigo, servico, itens, frete, desconto,
            acrescimo, total, pago, quitado, pago_em, fonte_condicao, cliente,
            prazo_texto, garantia, dados, quando, extra) -> dict:
    """O retrato do papel, o mesmo para a O.S. e para o orçamento."""
    from .contrato import dados_do_vendedor, data_por_extenso, reais_por_extenso
    from .documento_assinatura import _empresa

    prestador = dados_do_vendedor(dados)
    total = Decimal(total or 0).quantize(Decimal("0.01"))
    pago = Decimal(pago or 0).quantize(Decimal("0.01"))
    subtotal = sum((Decimal(i["subtotal"]) for i in itens), Decimal("0.00"))
    condicao, origem_condicao = condicao_de_pagamento(
        fonte_condicao, total=total, pago=pago, quitado=quitado, pago_em=pago_em,
    )
    situacao = situacao_do_pagamento(total=total, pago=pago, quitado=quitado, pago_em=pago_em)
    tipo = servico.get("tipo_texto") or "prestação de serviço"
    if servico.get("equipamento"):
        objeto = (
            "O presente instrumento tem como objeto a prestação, pela CONTRATADA ao "
            f"CONTRATANTE, do serviço de {tipo} no equipamento "
            f"“{servico['equipamento']}”"
            + (f", identificação {servico['numero_serie']}" if servico.get("numero_serie") else "")
            + ", conforme a solicitação do CONTRATANTE e o serviço, as peças e os "
            "valores descritos nesta ordem de serviço."
        )
    else:
        objeto = (
            "O presente instrumento tem como objeto a prestação, pela CONTRATADA ao "
            "CONTRATANTE, dos serviços de manutenção e dos demais serviços descritos "
            "nesta ordem de serviço, com as peças, os materiais e os valores "
            "relacionados no quadro de valores."
        )
    total_texto = _reais(total).replace("R$ ", "")
    total_extenso = reais_por_extenso(total)
    return {
        "modelo": VERSAO_DO_MODELO,
        "tipo": TIPO,
        "origem": origem,
        "titulo": TITULO,
        "titulo_curto": TITULO_CURTO,
        "numero": numero,
        "versao": versao,
        "codigo": codigo,
        "emitido_em": quando.isoformat(timespec="seconds"),
        "emitido_em_texto": quando.strftime("%d/%m/%Y às %H:%M"),
        "empresa": _empresa(),
        # A CONTRATADA: os mesmos dados (e o mesmo representante) do contrato
        # de compra e venda -- `DadosContrato`, preenchido pelo dono.
        "prestador": prestador,
        "vendedor": prestador,
        "preambulo": preambulo(prestador),
        "cliente": cliente,
        "servico": servico,
        "itens": itens,
        "valores": {
            "subtotal": _dinheiro(subtotal),
            "frete": _dinheiro(frete),
            "desconto": _dinheiro(desconto),
            "acrescimo": _dinheiro(acrescimo),
            "total": _dinheiro(total),
            "pago": _dinheiro(pago),
            "saldo": _dinheiro(max(total - pago, Decimal("0.00"))),
        },
        "valores_texto": {
            "subtotal": _reais(subtotal),
            "frete": _reais(frete),
            "desconto": _reais(desconto),
            "acrescimo": _reais(acrescimo),
            "total": _reais(total),
        },
        "valor_total_texto": total_texto,
        "valor_total_extenso": total_extenso,
        "condicao_pagamento": condicao,
        "condicao_origem": origem_condicao,
        "pagamento": {
            **situacao,
            "situacao": situacao["rotulo"],
            "quitado": situacao["codigo"] == "pago",
            "pago_em": _data(pago_em) if situacao["codigo"] == "pago" else "",
            "forma": _texto(getattr(fonte_condicao, "forma_pagamento", "")),
        },
        "garantia": garantia,
        "prazo_texto": prazo_texto,
        "secoes": secoes(
            objeto=objeto,
            prazo_texto=prazo_texto,
            garantia_texto=garantia["texto"],
            total=total,
            total_texto=total_texto,
            total_extenso=total_extenso,
            condicao=condicao,
            pagamento_texto=situacao["texto"],
            foro=FORO,
        ),
        "fecho": FECHO,
        "local_data": f"{prestador['cidade']}, {data_por_extenso(quando.date())}",
        **extra,
    }


def itens_da_ordem(ordem) -> list[dict]:
    rotulos = dict(ItemOrdemServico.Tipo.choices)
    return [
        {
            "tipo": rotulos.get(item.tipo, "Serviço"),
            "tipo_codigo": item.tipo,
            "descricao": item.descricao,
            "quantidade": item.quantidade,
            "valor_unitario": _dinheiro(item.valor_unitario),
            "subtotal": _dinheiro(item.subtotal),
            "valor_unitario_texto": _reais(item.valor_unitario),
            "subtotal_texto": _reais(item.subtotal),
        }
        for item in ordem.itens.all()
    ]


def _prazo_da_ordem(ordem) -> str:
    """A frase da agenda na Cláusula 2ª, pela situação da O.S."""
    Status = OrdemServico.Status
    if ordem.status == Status.CONCLUIDA and ordem.concluida_em:
        return f"O serviço foi concluído em {_data(ordem.concluida_em)}."
    if ordem.status in (Status.EM_EXECUCAO, Status.AGUARDANDO_PECA):
        inicio = f", iniciado em {_data(ordem.iniciada_em)}" if ordem.iniciada_em else ""
        return f"O serviço está em execução{inicio}, e a conclusão será comunicada ao CONTRATANTE."
    if ordem.agendada_para:
        return (
            f"O serviço está agendado para {_data_hora(ordem.agendada_para)}, no local "
            "indicado nesta ordem de serviço."
        )
    return (
        "A data da execução será combinada entre as partes e informada ao "
        "CONTRATANTE com antecedência."
    )


def retrato_da_ordem(ordem, dados=None, *, quando=None) -> dict:
    """O papel da O.S., como será assinado. Só texto e números já escritos."""
    from .models import DadosContrato

    dados = dados or DadosContrato.atual()
    quando = quando or timezone.localtime()
    cliente_cadastro = ordem.cliente if ordem.cliente_id else None
    endereco_cliente = cliente_cadastro.endereco_principal if cliente_cadastro else None
    status_pagamento = ordem.status_pagamento
    pago = Decimal("0.00") if status_pagamento == OrdemServico.StatusPagamento.ESTORNADO else (ordem.valor_pago or 0)
    tecnico = _nome_de(ordem.tecnico) if ordem.tecnico_id else ""
    itens = itens_da_ordem(ordem)
    local = _texto(ordem.endereco_servico)
    if not local and endereco_cliente is not None:
        from .documento_assinatura import _endereco_completo

        local = _endereco_completo(endereco_cliente)
    servico = {
        "tipo": ordem.get_tipo_display(),
        "tipo_texto": SERVICO_DO_TIPO.get(ordem.tipo, "prestação de serviço"),
        "situacao": ordem.get_status_display(),
        "prioridade": ordem.get_prioridade_display(),
        "equipamento": _texto(ordem.equipamento),
        "numero_serie": _texto(ordem.numero_serie),
        "defeito": _paragrafos(ordem.defeito_relatado),
        "diagnostico": _paragrafos(ordem.diagnostico) if ordem.registra_execucao else "",
        "servico_executado": _paragrafos(ordem.servico_executado) if ordem.registra_execucao else "",
        "observacoes": _paragrafos(ordem.observacoes),
        "local": local,
        "contato_local": _texto(ordem.contato),
        "agendada_para": _data_hora(ordem.agendada_para),
        "iniciada_em": _data(ordem.iniciada_em),
        "concluida_em": _data(ordem.concluida_em),
        "tecnico": tecnico or "A definir",
    }
    responsavel = _nome_de(ordem.responsavel) if ordem.responsavel_id else ""
    return _montar(
        origem="ordem",
        numero=ordem.numero_documento,
        versao=ordem.versao,
        codigo="",
        servico=servico,
        itens=itens,
        frete=ordem.frete,
        desconto=ordem.desconto,
        acrescimo=Decimal("0.00"),
        total=ordem.total,
        pago=pago,
        quitado=ordem.quitado,
        pago_em=ordem.pago_em,
        fonte_condicao=ordem,
        cliente=_cliente(
            nome=ordem.destinatario,
            cliente=cliente_cadastro,
            telefone=ordem.whatsapp_destinatario,
            email=ordem.email_destinatario,
            endereco_cliente=endereco_cliente,
        ),
        prazo_texto=_prazo_da_ordem(ordem),
        garantia=_garantia(ordem.garantia_ate),
        dados=dados,
        quando=quando,
        extra={
            "ordem": {
                "id": ordem.pk,
                "numero": ordem.numero_documento,
                "versao": ordem.versao,
                "data": _data(ordem.criacao),
                "responsavel": responsavel or "Equipe Lazer & Sport",
                "orcamento": ordem.orcamento_id or None,
            },
        },
    )


def _tipo_da_linha(item) -> str:
    if item.peca_id:
        return "Peça / material"
    if item.brinquedo_id or item.produto_id:
        return "Equipamento"
    if _PALAVRAS_DE_SERVICO.search(_normalizar(item.descricao)):
        return "Serviço / mão de obra"
    return "Item"


def retrato_do_orcamento(orcamento, dados=None, *, quando=None) -> dict:
    """O papel da ordem de serviço do orçamento APROVADO de manutenção.

    A chave "orcamento" vai junto, igual à do contrato de venda: Meus
    pedidos, o WhatsApp e o rodapé do papel leem o número e o código dali.
    Se a proposta tem uma O.S. ligada, o equipamento e o defeito vêm dela.
    """
    from .contrato import numero_por_extenso
    from .models import DadosContrato

    dados = dados or DadosContrato.atual()
    quando = quando or timezone.localtime()
    cliente_cadastro = orcamento.cliente if orcamento.cliente_id else None
    endereco_cliente = cliente_cadastro.endereco_principal if cliente_cadastro else None
    ordem = None
    try:
        ordem = orcamento.ordem_servico
    except OrdemServico.DoesNotExist:
        ordem = None
    itens = [
        {
            "tipo": _tipo_da_linha(item),
            "tipo_codigo": "peca" if item.peca_id else "servico",
            "descricao": item.descricao,
            "quantidade": item.quantidade,
            "valor_unitario": _dinheiro(item.valor_unitario),
            "subtotal": _dinheiro(item.subtotal),
            "valor_unitario_texto": _reais(item.valor_unitario),
            "subtotal_texto": _reais(item.subtotal),
        }
        for item in orcamento.itens.all()
    ]
    dias = getattr(orcamento, "prazo_producao_dias", None)
    if dias:
        prazo_texto = (
            f"O serviço será executado em até {dias:02d} ({numero_por_extenso(dias)}) "
            f"{'dia útil' if dias == 1 else 'dias úteis'} após a aprovação, em data "
            "combinada entre as partes."
        )
    else:
        prazo_texto = (
            "A data da execução será combinada entre as partes e informada ao "
            "CONTRATANTE com antecedência."
        )
    servico = {
        "tipo": ordem.get_tipo_display() if ordem else "Manutenção e serviços",
        "tipo_texto": SERVICO_DO_TIPO.get(ordem.tipo) if ordem else "manutenção",
        "situacao": orcamento.get_status_display(),
        "prioridade": "",
        "equipamento": _texto(ordem.equipamento) if ordem else "",
        "numero_serie": _texto(ordem.numero_serie) if ordem else "",
        "defeito": _paragrafos(ordem.defeito_relatado) if ordem else "",
        "diagnostico": "",
        "servico_executado": "",
        "observacoes": _paragrafos(orcamento.observacoes),
        "local": (_texto(ordem.endereco_servico) if ordem else "")
        or (_endereco(endereco_cliente)),
        "contato_local": _texto(orcamento.contato),
        "agendada_para": "",
        "iniciada_em": "",
        "concluida_em": "",
        "tecnico": "",
    }
    responsavel = _nome_de(orcamento.responsavel) if orcamento.responsavel_id else ""
    status_pagamento = orcamento.status_pagamento
    pago = (
        Decimal("0.00") if status_pagamento == Orcamento.StatusPagamento.ESTORNADO
        else (orcamento.valor_pago or 0)
    )
    return _montar(
        origem="orcamento",
        numero=orcamento.numero_documento,
        versao=orcamento.versao,
        codigo=orcamento.codigo or "",
        servico=servico,
        itens=itens,
        frete=orcamento.frete,
        desconto=orcamento.desconto_aplicado,
        acrescimo=orcamento.acrescimo_aplicado,
        total=orcamento.total,
        pago=pago,
        quitado=orcamento.quitado,
        pago_em=orcamento.pago_em,
        fonte_condicao=orcamento,
        cliente=_cliente(
            nome=orcamento.destinatario,
            cliente=cliente_cadastro,
            telefone=orcamento.whatsapp_destinatario,
            email=orcamento.email_destinatario,
            endereco_cliente=endereco_cliente,
        ),
        prazo_texto=prazo_texto,
        garantia=_garantia(None),
        dados=dados,
        quando=quando,
        extra={
            # A mesma chave do contrato de venda (Meus pedidos, WhatsApp, rodapé).
            "orcamento": {
                "id": orcamento.pk,
                "numero": orcamento.numero_documento,
                "codigo": orcamento.codigo or "",
                "versao": orcamento.versao,
                "data": _data(orcamento.criacao),
                "aprovado_em": _data(orcamento.respondido_em),
                "responsavel": responsavel or "Equipe Lazer & Sport",
            },
            "condicoes": {
                "forma_envio": _texto(orcamento.forma_envio),
                "observacoes": _paragrafos(orcamento.observacoes),
            },
        },
    )


def _endereco(endereco) -> str:
    from .documento_assinatura import _endereco_completo

    return _endereco_completo(endereco)


# ======================================================================
# A O.S.: GERAR, O DOCUMENTO QUE VALE, A SUSPENSÃO, O CARTÃO
# ======================================================================
def motivo_para_nao_gerar(ordem) -> str:
    """Por que esta O.S. não gera o documento agora ("" = gera).

    NÃO DEPENDE DE PAGAMENTO: pendente, parcial ou pago, o documento sai.
    O que impede é a situação (rascunho, cancelada, substituída) e a
    agenda vencida -- o papel afirmaria ao cliente uma data que já passou
    (a mesma regra do "Enviar O.S.", `OrdemServico.pode_enviar`).
    """
    if ordem.status == OrdemServico.Status.RASCUNHO:
        return "A O.S. ainda é rascunho: salve-a antes de gerar o documento."
    if ordem.status == OrdemServico.Status.CANCELADA:
        return "O.S. cancelada não gera documento para o cliente assinar."
    if ordem.status == OrdemServico.Status.SUBSTITUIDA:
        return "Esta versão foi substituída: gere o documento da versão que está valendo."
    if ordem.agenda_vencida:
        return (
            "A data agendada já passou e o serviço não andou. Reagende a O.S. "
            "antes de gerar o documento: ele diria ao cliente uma data que já passou."
        )
    return ""


def documento_atual_da_ordem(ordem):
    """O documento que vale: o assinado, ou o que espera assinatura."""
    return (
        DocumentoAssinatura.objects
        .filter(ordem_servico=ordem)
        .exclude(situacao=DocumentoAssinatura.Situacao.SUBSTITUIDO)
        .order_by("-id")
        .first()
    )


def motivo_da_suspensao_da_ordem(documento, ordem=None) -> str:
    """"ordem" quando a O.S. deixou de valer depois de o papel sair; "" se não.

    Cancelada ou substituída por uma versão nova: o serviço que o papel
    descreve não é mais o combinado. O PAGAMENTO NÃO SUSPENDE: o papel
    conta o que tinha entrado até a emissão.
    """
    ordem = ordem or documento.ordem_servico
    if ordem.status in (OrdemServico.Status.CANCELADA, OrdemServico.Status.SUBSTITUIDA):
        return "ordem"
    return ""


def situacao_do_cartao_da_ordem(ordem, documento, *, situacao_documento=None) -> str:
    """A cara do cartão numa palavra: gerar, bloqueado, aguardando, assinado, suspenso.

    `situacao_documento` serve à lista, que traz só a situação do documento
    numa subconsulta (sem carregar o retrato de cada linha).
    """
    situacao = situacao_documento if documento is None else documento.situacao
    if not situacao:
        return "bloqueado" if motivo_para_nao_gerar(ordem) else "gerar"
    if situacao == DocumentoAssinatura.Situacao.ASSINADO:
        return "assinado"
    if ordem.status in (OrdemServico.Status.CANCELADA, OrdemServico.Status.SUBSTITUIDA):
        return "suspenso"
    return situacao


def _ordem_completa(pk, *, travar=False):
    """A O.S. com tudo o que o retrato lê, em poucas viagens ao banco."""
    from django.db.models import Prefetch

    from .models import EnderecoCliente

    consulta = OrdemServico.objects.select_related(
        "cliente", "tecnico", "responsavel", "manutencao__usuario__user", "orcamento",
    ).prefetch_related(
        "itens",
        Prefetch("cliente__enderecos", queryset=EnderecoCliente.objects.order_by("id")),
    )
    if travar:
        # Só a linha da O.S. fica travada: no PostgreSQL o FOR UPDATE não
        # pode cair no lado anulável dos LEFT JOIN (cliente, técnico...).
        consulta = consulta.select_for_update(of=("self",))
    return consulta.get(pk=pk)


def gerar_da_ordem(ordem, usuario):
    """Congela a O.S. num documento novo -- com ou sem pagamento.

    O anterior que esperava assinatura vira "substituído" na mesma
    transação (os links dele morrem). Depois de assinado não há "gerar de
    novo": o assinado é o documento -- para mudar o serviço, refaça a O.S.
    (versão nova) e gere o documento dela.
    """
    from . import documento_assinatura as svc
    from .models import DadosContrato

    with transaction.atomic():
        ordem = _ordem_completa(ordem.pk, travar=True)
        motivo = motivo_para_nao_gerar(ordem)
        if motivo:
            raise ErroDeFormulario(motivo)
        dados = DadosContrato.atual()
        anteriores = list(
            DocumentoAssinatura.objects.select_for_update()
            .filter(ordem_servico=ordem)
            .exclude(situacao=DocumentoAssinatura.Situacao.SUBSTITUIDO)
            .defer("assinatura_png")
        )
        if any(doc.assinado for doc in anteriores):
            raise ErroDeFormulario(
                "Esta O.S. já tem a ordem de serviço assinada pelo cliente. Ela é o "
                "documento que vale; para mudar o serviço, refaça a O.S. (versão nova)."
            )
        if anteriores:
            DocumentoAssinatura.objects.filter(pk__in=[d.pk for d in anteriores]).update(
                situacao=DocumentoAssinatura.Situacao.SUBSTITUIDO, atualizado=timezone.now(),
            )
        conteudo = retrato_da_ordem(ordem, dados)
        documento = DocumentoAssinatura.objects.create(
            ordem_servico=ordem,
            conteudo=conteudo,
            hash_conteudo=svc.hash_do_retrato(conteudo),
            criado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
        )
    por = _nome_de(usuario) if getattr(usuario, "is_authenticated", False) else ""
    svc.anotar(documento, "gerado", por=por or "equipe")
    return documento


def mensagem_whatsapp(documento, link) -> str:
    """O texto pronto da conversa da O.S., com o link de 24 horas."""
    from core.email_utils import cnpj_empresa, nome_empresa

    from .documento_assinatura import prazo_do_link

    conteudo = documento.conteudo or {}
    nome = (conteudo.get("cliente") or {}).get("nome", "")
    numero = conteudo.get("numero", "")
    equipamento = (conteudo.get("servico") or {}).get("equipamento", "")
    total = (conteudo.get("valores_texto") or {}).get("total", "")
    linhas = [
        f"Olá, {nome}! 👋" if nome else "Olá! 👋",
        "",
        f"Sua *ordem de serviço {numero}* da Lazer & Sport está pronta para assinar. 🛠️",
    ]
    if equipamento:
        linhas.append(f"*Equipamento:* {equipamento}")
    if total:
        linhas.append(f"*Total:* {total}")
    linhas.extend([
        "Leia e assine direto no seu celular:",
        link,
        "",
        f"⏱️ O link vale por *{prazo_do_link()}*. Se passar, é só pedir outro aqui.",
        f"{nome_empresa()} · CNPJ {cnpj_empresa()}",
    ])
    return "\n".join(linhas)


def depois_de_assinar(documento):
    """A assinatura da ordem de serviço vale como a ciência da O.S.

    Registra "cliente ciente" (quem assinou), e a O.S. que esperava a
    ciência passa a "Aberta" -- o mesmo efeito do "confirmar ciência" da
    página da O.S. Quando a ciência já existia, só o carimbo de
    atualização muda (a lista e a janela das outras abas se renovam).
    Nunca derruba a assinatura: é o rastro, não o trabalho.
    """
    try:
        # Num ponto de salvamento: se falhar, só ele volta -- a transação da
        # assinatura (a view pública) continua inteira.
        with transaction.atomic():
            ordem = OrdemServico.objects.get(pk=documento.ordem_servico_id)
            if not ordem.registrar_ciencia(documento.assinante_nome):
                OrdemServico.objects.filter(pk=ordem.pk).update(atualizado=timezone.now())
    except Exception:  # noqa: BLE001
        log.exception("Ciência da O.S. pela assinatura do documento %s", documento.pk)


def papel_curto(conteudo) -> str:
    """"Ordem de serviço", "Contrato de compra e venda" ou "Termo de compra"."""
    from .contrato import e_contrato

    if e_servico(conteudo):
        return TITULO_CURTO
    if e_contrato(conteudo):
        return "Contrato de compra e venda"
    return "Termo de compra"


def numero_do_documento(conteudo) -> str:
    """O número que identifica o papel: o da O.S. ou o do orçamento."""
    conteudo = conteudo or {}
    if conteudo.get("numero"):
        return str(conteudo["numero"])
    return str((conteudo.get("orcamento") or {}).get("numero", ""))
