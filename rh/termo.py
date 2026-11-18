"""O termo de exclusividade e confidencialidade, assinado pelo colaborador.

O PEDIDO: "nos funcionários, devemos pôr uma situação de contrato, onde o
funcionário deve assinar que não pode trabalhar com coisas relacionadas a
lazer e sport enquanto contratado para outras empresas, com o aviso de falta
de assinatura virando um grande tópico no sistema."

O TEXTO É UM MODELO PARA REVISÃO DO ADVOGADO DA EMPRESA. A tela e o LEIA-ME
dizem isso; trocar o texto é trocar `PARAGRAFOS` (e subir `VERSAO_DO_TERMO`).

REAPROVEITA O FLUXO DO TERMO DE COMPRA (sistema_interno/documento_assinatura.py):

  * o RETRATO: o texto é montado com os dados da ficha e da empresa e
    congelado num JSON na hora de gerar; o SHA-256 dele (o mesmo
    `hash_do_retrato`) vai para a trilha;
  * o LINK DE 5 MINUTOS: o mesmo assinador (HMAC em base 62, com sal
    próprio), para quem assina no celular sem conta -- o RH mostra o QR,
    que se renova sozinho;
  * o QUADRO de assinar e a conferência do traço (`png_da_assinatura`);
  * o FREIO de tentativas por IP.

E acrescenta o que o termo de compra não precisava: quem TEM conta assina
no próprio painel (a faixa no alto de todas as telas leva até lá), o CPF
digitado tem de ser o da ficha, e o PDF assinado (texto, traço e trilha)
entra na pasta de documentos do colaborador, no armazenamento privado.

VERSÃO. Quando o texto muda, `VERSAO_DO_TERMO` sobe: todo termo assinado
de versão anterior deixa de contar, e a pessoa volta a "pendente".
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from django.core import signing
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from core.email_utils import cnpj_empresa, nome_empresa
from sistema_interno import documento_assinatura as assinatura_base
from sistema_interno.utils import ErroDeFormulario
from sistema_interno.validacoes import somente_digitos

from . import pdf_simples
from .arquivos import ArquivoConferido
from .models import Colaborador, RegistroRH, Situacao, TermoExclusividade, TipoDocumento, Vinculo
from .validadores import formatar_cpf, mascarar_cpf

#: Muda quando o TEXTO muda. Termo assinado de outra versão não vale mais.
VERSAO_DO_TERMO = "2026-11"

TITULO = "Termo de exclusividade e confidencialidade"

#: Reaproveitado do termo de compra: a mesma janela do link.
VALIDADE_DO_LINK = assinatura_base.VALIDADE_DO_LINK
SAL_DO_LINK = "rh.termo.link"
PEDACO_DO_HASH = 16

MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro")

AVISO_DO_MODELO = (
    "Modelo de texto para revisão do advogado da empresa antes de valer como "
    "contrato. Os dados entre chaves vêm da ficha do colaborador e do cadastro da empresa."
)


# ======================================================================
# QUEM ESTÁ PENDENTE
# ======================================================================
def _assinado_na_versao():
    return TermoExclusividade.objects.filter(
        colaborador=OuterRef("pk"), versao=VERSAO_DO_TERMO, situacao=TermoExclusividade.Estado.ASSINADO,
    )


def _enviado_na_versao():
    return TermoExclusividade.objects.filter(
        colaborador=OuterRef("pk"), versao=VERSAO_DO_TERMO, situacao=TermoExclusividade.Estado.ENVIADO,
    )


def com_situacao(consulta=None):
    """Anota `termo_assinado` e `termo_enviado` (versão atual) em cada colaborador."""
    consulta = Colaborador.objects.all() if consulta is None else consulta
    return consulta.annotate(termo_assinado=Exists(_assinado_na_versao()), termo_enviado=Exists(_enviado_na_versao()))


def pendentes():
    """Quem está sob contrato (não desligado) e sem o termo da versão atual assinado."""
    return (
        Colaborador.objects.exclude(situacao=Situacao.DESLIGADO)
        .annotate(termo_assinado=Exists(_assinado_na_versao()))
        .filter(termo_assinado=False)
    )


def situacao_de(colaborador) -> str:
    """"assinado", "enviado" ou "pendente" (na versão atual do texto)."""
    if getattr(colaborador, "termo_assinado", None) is not None:
        if colaborador.termo_assinado:
            return "assinado"
        return "enviado" if getattr(colaborador, "termo_enviado", False) else "pendente"
    termos = TermoExclusividade.objects.filter(colaborador=colaborador, versao=VERSAO_DO_TERMO)
    if termos.filter(situacao=TermoExclusividade.Estado.ASSINADO).exists():
        return "assinado"
    if termos.filter(situacao=TermoExclusividade.Estado.ENVIADO).exists():
        return "enviado"
    return "pendente"


ROTULOS = {"assinado": "Assinado", "enviado": "Enviado · esperando assinatura", "pendente": "Pendente"}


def termo_atual(colaborador):
    """O termo da versão atual que vale: o assinado, ou o que espera assinatura."""
    return (
        TermoExclusividade.objects.filter(colaborador=colaborador, versao=VERSAO_DO_TERMO)
        .exclude(situacao=TermoExclusividade.Estado.SUBSTITUIDO)
        .order_by("-id")  # só há um por vez: gerar recusa se já houver assinado
        .first()
    )


def ultimo_assinado(colaborador):
    return (
        TermoExclusividade.objects.filter(colaborador=colaborador, situacao=TermoExclusividade.Estado.ASSINADO)
        .order_by("-assinado_em", "-id").first()
    )


# ======================================================================
# O RETRATO (o texto congelado)
# ======================================================================
def data_por_extenso(dia) -> str:
    return f"{dia.day} de {MESES[dia.month - 1]} de {dia.year}"


def dados_da_empresa() -> dict:
    """Razão social e CNPJ (os mesmos dos documentos do cliente) e a cidade.

    A cidade sai do endereço da fábrica ("Dados da empresa" do site); sem
    ele, São Paulo.
    """
    cidade = "São Paulo"
    try:
        from core.models import EnderecoEmpresa

        cadastro = EnderecoEmpresa.objects.filter(ativo=True).order_by("id").first()
        if cadastro and cadastro.cidade:
            cidade = cadastro.cidade.strip()
    except Exception:  # noqa: BLE001 -- sem o cadastro, a cidade padrão
        pass
    return {"nome": nome_empresa(), "cnpj": cnpj_empresa(), "cidade": cidade}


def paragrafos(colaborador, empresa, dia) -> dict:
    """O texto do modelo, com os dados entre chaves já preenchidos."""
    prestador = colaborador.vinculo in (Vinculo.PJ, Vinculo.TEMPORARIO)
    estagio = colaborador.vinculo == Vinculo.ESTAGIO
    if prestador:
        qualificacao = f"prestador(a) de serviços para {empresa['nome']}"
    elif estagio:
        qualificacao = f"estagiário(a) de {empresa['nome']}"
    else:
        qualificacao = f"contratado(a) por {empresa['nome']}"
    admissao = colaborador.data_admissao.strftime("%d/%m/%Y") if colaborador.data_admissao else "—"
    abertura = (
        f"Eu, {colaborador.nome}, CPF {formatar_cpf(colaborador.cpf)}, {qualificacao}, "
        f"CNPJ {empresa['cnpj']}, na função de {colaborador.cargo}, desde {admissao}, "
        "declaro estar ciente e de acordo com o seguinte:"
    )
    if prestador:
        consequencia = (
            "Estou ciente de que o descumprimento pode motivar a rescisão do contrato de "
            "prestação de serviços, sem prejuízo da reparação por perdas e danos."
        )
    elif estagio:
        consequencia = (
            "Estou ciente de que o descumprimento pode motivar o desligamento do estágio "
            "(Lei 11.788/2008), sem prejuízo da reparação por perdas e danos."
        )
    else:
        consequencia = (
            "Estou ciente de que o descumprimento pode caracterizar falta grave (art. 482, "
            "alíneas “c” e “g”, da CLT), sem prejuízo da reparação por perdas e danos."
        )
    return {
        "abertura": abertura,
        "itens": [
            (
                "Enquanto durar o meu vínculo com a empresa, não prestarei serviços, direta ou "
                "indiretamente, com ou sem remuneração, a outras empresas ou pessoas em atividades "
                "relacionadas ao ramo da empresa — fabricação, montagem, manutenção, venda ou locação "
                "de brinquedos, máquinas de entretenimento, jogos eletrônicos, espaços de lazer e "
                "esporte e seus componentes —, nem desenvolverei por conta própria produtos ou "
                "serviços que concorram com os dela."
            ),
            (
                "Não usarei nem divulgarei, durante ou após o vínculo, projetos, desenhos, moldes, "
                "softwares, jogos, listas de clientes e fornecedores, preços ou quaisquer "
                "informações internas da empresa."
            ),
            (
                "Comunicarei por escrito qualquer outra atividade profissional que eu venha a "
                "exercer, para avaliação prévia da empresa."
            ),
            consequencia,
        ],
        "local_data": f"{empresa['cidade']}, {data_por_extenso(dia)}.",
    }


def retrato(colaborador) -> dict:
    """O termo inteiro, como será assinado: só texto, nada de id interno."""
    agora = timezone.localtime()
    empresa = dados_da_empresa()
    return {
        "modelo": VERSAO_DO_TERMO,
        "titulo": TITULO.upper(),
        "emitido_em": agora.isoformat(timespec="seconds"),
        "emitido_em_texto": agora.strftime("%d/%m/%Y às %H:%M"),
        "empresa": empresa,
        "colaborador": {
            "nome": colaborador.nome,
            "cpf": colaborador.cpf,
            "cargo": colaborador.cargo,
            "vinculo": colaborador.get_vinculo_display(),
            "admissao": colaborador.data_admissao.isoformat() if colaborador.data_admissao else "",
        },
        "texto": paragrafos(colaborador, empresa, agora.date()),
        "aviso_modelo": AVISO_DO_MODELO,
    }


hash_do_retrato = assinatura_base.hash_do_retrato


# ======================================================================
# GERAR (= "Enviar para assinatura")
# ======================================================================
def gerar(colaborador, usuario=None):
    """Congela o termo da versão atual para a pessoa assinar.

    Já assinado na versão atual: erro (o assinado é o que vale). Esperando
    assinatura com o MESMO texto: devolve o mesmo (dois cliques não fazem
    dois termos). Com o texto diferente (a ficha mudou: cargo, nome...): o
    anterior vira "substituído" e os links dele morrem.
    """
    with transaction.atomic():
        colaborador = Colaborador.objects.select_for_update().get(pk=colaborador.pk)
        if colaborador.situacao == Situacao.DESLIGADO:
            raise ErroDeFormulario("Essa pessoa foi desligada: não há vínculo para o termo.")
        anteriores = list(
            TermoExclusividade.objects.select_for_update()
            .filter(colaborador=colaborador, versao=VERSAO_DO_TERMO)
            .exclude(situacao=TermoExclusividade.Estado.SUBSTITUIDO)
        )
        if any(t.assinado for t in anteriores):
            raise ErroDeFormulario("O termo desta versão já está assinado.")
        conteudo = retrato(colaborador)
        for termo in anteriores:
            if _mesmo_texto(termo.conteudo, conteudo):
                return termo
        for termo in anteriores:
            termo.situacao = TermoExclusividade.Estado.SUBSTITUIDO
            termo.save(update_fields=["situacao"])
        return TermoExclusividade.objects.create(
            colaborador=colaborador,
            versao=VERSAO_DO_TERMO,
            conteudo=conteudo,
            hash_conteudo=hash_do_retrato(conteudo),
            gerado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
        )


def _mesmo_texto(antes: dict, agora: dict) -> bool:
    """Só o que é assinado conta: a data de emissão muda a cada geração."""
    def chave(c):
        texto = dict((c or {}).get("texto") or {})
        texto.pop("local_data", None)
        return (c or {}).get("modelo"), c.get("colaborador"), texto, (c or {}).get("empresa")

    return chave(antes) == chave(agora)


def gerar_para_todos(usuario=None) -> int:
    total = 0
    for colaborador in pendentes():
        try:
            gerar(colaborador, usuario)
            total += 1
        except ErroDeFormulario:
            continue
    return total


# ======================================================================
# O LINK DE 5 MINUTOS (o mesmo assinador do termo de compra)
# ======================================================================
def _assinador():
    return assinatura_base._AssinadorDoLink(salt=SAL_DO_LINK, sep=".")


def emitir_link(termo):
    from django.db.models import F

    token = _assinador().sign(f"{termo.pk}.{termo.hash_conteudo[:PEDACO_DO_HASH]}")
    TermoExclusividade.objects.filter(pk=termo.pk).update(
        links_gerados=F("links_gerados") + 1, ultimo_link_em=timezone.now(),
    )
    termo.refresh_from_db(fields=["links_gerados", "ultimo_link_em"])
    return token, assinatura_base._nasceu_em(token) + VALIDADE_DO_LINK


@dataclass
class Leitura:
    situacao: str  # valido, expirado, substituido, assinado, invalido
    termo: TermoExclusividade | None = None
    expira_em: int = 0

    @property
    def valido(self):
        return self.situacao == "valido"

    @property
    def segundos_restantes(self):
        return max(0, int(self.expira_em - time.time()))


def ler_link(token, *, bloquear=False) -> Leitura:
    token = (token or "").strip()
    if len(token) > 200 or token.count(".") != 3:
        return Leitura("invalido")
    assinador = _assinador()
    try:
        carga = assinador.unsign(token, max_age=VALIDADE_DO_LINK)
        expirado = False
    except signing.SignatureExpired:
        carga = assinador.unsign(token)
        expirado = True
    except signing.BadSignature:
        return Leitura("invalido")
    pk, _, pedaco = carga.partition(".")
    if not pk.isdigit():
        return Leitura("invalido")
    consulta = TermoExclusividade.objects.select_related("colaborador")
    if bloquear:
        consulta = consulta.select_for_update(of=("self",))
    termo = consulta.filter(pk=int(pk)).first()
    if termo is None:
        return Leitura("invalido")
    expira_em = assinatura_base._nasceu_em(token) + VALIDADE_DO_LINK
    if termo.assinado:
        return Leitura("assinado", termo, expira_em)
    if termo.situacao == TermoExclusividade.Estado.SUBSTITUIDO or termo.hash_conteudo[:PEDACO_DO_HASH] != pedaco:
        return Leitura("substituido", termo, expira_em)
    if expirado:
        return Leitura("expirado", termo, expira_em)
    return Leitura("valido", termo, expira_em)


def mensagem_whatsapp(termo, link) -> str:
    nome = ((termo.conteudo or {}).get("colaborador") or {}).get("nome", "")
    primeiro = nome.split(" ")[0] if nome else ""
    return "\n".join([
        f"Olá, {primeiro}!" if primeiro else "Olá!",
        "",
        "Este é o termo de exclusividade e confidencialidade da Lazer & Sport. "
        "Leia com calma e assine direto no seu celular:",
        link,
        "",
        "O link vale por 5 minutos. Se passar, é só pedir outro.",
    ])


# ======================================================================
# ASSINAR
# ======================================================================
AssinaturaRecusada = assinatura_base.AssinaturaRecusada
png_da_assinatura = assinatura_base.png_da_assinatura
tentativas_estouradas = assinatura_base.tentativas_estouradas


def conferir_campos(termo, *, nome, cpf, concordo):
    """Nome completo, o CPF DA FICHA e o "Li e concordo"."""
    import re

    nome = re.sub(r"\s+", " ", (nome or "").strip())[:160]
    palavras = [p for p in nome.split(" ") if len(p.strip(".")) >= 2]
    if len(palavras) < 2:
        raise AssinaturaRecusada("Escreva o nome completo (nome e sobrenome).", "nome")
    numero = somente_digitos(cpf)
    if numero != termo.colaborador.cpf:
        raise AssinaturaRecusada(
            f"O CPF não confere com o da ficha ({mascarar_cpf(termo.colaborador.cpf)}). "
            "Confira os números.",
            "documento",
        )
    if not concordo:
        raise AssinaturaRecusada("Marque “Li e concordo” para assinar.", "concordo")
    return nome, numero


def assinar(termo, *, nome, cpf, png, ip, navegador, canal, request=None):
    """Grava a assinatura, gera o PDF e o guarda na pasta do colaborador.

    Quem chama já travou a linha do termo e conferiu link/conta e campos.
    Tudo numa transação: sem PDF guardado, sem assinatura.
    """
    from . import servicos

    agora = timezone.now()
    termo.assinado_em = agora
    termo.assinante_nome = nome
    termo.assinante_cpf = cpf
    termo.assinatura_png = png
    termo.assinatura_ip = ip or None
    termo.assinatura_navegador = (navegador or "")[:400]
    termo.hash_assinado = hash_do_retrato(termo.conteudo)
    termo.canal = canal

    dados = pdf_do_termo(termo)
    import hashlib

    conferido = ArquivoConferido(
        formato="pdf", tipo_conteudo="application/pdf", extensao=".pdf", tamanho=len(dados),
        sha256=hashlib.sha256(dados).hexdigest(),
        nome_original=f"termo-exclusividade-{termo.versao}.pdf", dados=dados,
    )
    documento = servicos.guardar_documento(
        termo.colaborador, conferido, tipo=TipoDocumento.TERMO,
        descricao=f"Termo de exclusividade · versão {termo.versao}",
        emissao=timezone.localdate(agora), usuario=getattr(request, "user", None),
    )
    termo.documento = documento
    termo.situacao = TermoExclusividade.Estado.ASSINADO
    termo.save()
    if request is not None:
        servicos.registrar(
            request, RegistroRH.Acao.DOC_ENVIADO, colaborador=termo.colaborador, documento=documento,
            descricao=(
                f"Termo de exclusividade assinado ({termo.get_canal_display().lower()}) · "
                f"integridade {termo.hash_assinado[:12]}…"
            ),
        )
    return termo


def pdf_do_termo(termo) -> bytes:
    """O PDF do termo assinado: o texto congelado, o traço e a trilha."""
    conteudo = termo.conteudo or {}
    texto = conteudo.get("texto") or {}
    empresa = conteudo.get("empresa") or {}
    doc = pdf_simples.Documento(titulo=TITULO, autor=empresa.get("nome", ""))
    doc.texto(empresa.get("nome", ""), corpo=9, cinza=True, depois=0)
    doc.texto(f"CNPJ {empresa.get('cnpj', '')}", corpo=9, cinza=True, depois=14)
    doc.texto(conteudo.get("titulo", TITULO.upper()), corpo=14, negrito=True, centro=True, depois=14)
    doc.texto(texto.get("abertura", ""), corpo=11, depois=8)
    for numero, item in enumerate(texto.get("itens", []), start=1):
        doc.texto(f"{numero}. {item}", corpo=11, recuo=8, depois=6)
    doc.espaco(8)
    doc.texto(texto.get("local_data", ""), corpo=11, depois=18)
    if termo.assinatura_png:
        doc.imagem_png(bytes(termo.assinatura_png))
    doc.linha(x2=pdf_simples.MARGEM + 260)
    doc.texto(termo.assinante_nome or "", corpo=10.5, negrito=True, depois=0)
    doc.texto(f"CPF {formatar_cpf(termo.assinante_cpf)} · Assinatura do colaborador", corpo=9.5, depois=18)

    quando = timezone.localtime(termo.assinado_em) if termo.assinado_em else None
    doc.texto("REGISTRO DA ASSINATURA ELETRÔNICA", corpo=9, negrito=True, depois=2)
    linhas = [
        f"Assinado em {quando:%d/%m/%Y às %H:%M:%S} (horário de Brasília)" if quando else "",
        f"Canal: {termo.get_canal_display()}" if termo.canal else "",
        f"Endereço de internet (IP): {termo.assinatura_ip or 'não informado'}",
        f"Aparelho: {(termo.assinatura_navegador or 'não informado')[:160]}",
        f"Texto gerado em {conteudo.get('emitido_em_texto', '')} · versão do modelo {termo.versao}",
        f"Integridade (SHA-256 do texto): {termo.hash_assinado}",
    ]
    for linha in linhas:
        if linha:
            doc.texto(linha, corpo=8.5, cinza=True, depois=0)
    doc.espaco(10)
    doc.texto(conteudo.get("aviso_modelo", AVISO_DO_MODELO), corpo=8, cinza=True)
    return doc.gerar()
