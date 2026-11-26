"""A tela "Dados do contrato": quem vende, no contrato que o cliente assina.

O PEDIDO (LEIA-ME-V10, seção 109). O contrato de compra e venda diz, no
preâmbulo, "neste ato representada por {nome}, portador da cédula de
identidade RG {rg}, residente e domiciliado na {endereço}". Os dados da
EMPRESA (nome fantasia, razão social, CNPJ, sede) são públicos e nascem
preenchidos; os do REPRESENTANTE são pessoais e não moram no código nem em
migração: o dono preenche aqui. Enquanto faltarem, a tela avisa, o cartão
do documento avisa e o contrato não sai para assinatura
(`documento_assinatura.gerar`).

QUEM MEXE. Só a Gestão (e o superusuário): é a identidade jurídica da
empresa no papel que o cliente assina. Mudar aqui vale para os contratos
gerados DEPOIS -- o contrato já gerado guarda a cópia dele (o retrato).
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from django.shortcuts import render
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.views.generic import View

from . import contrato
from .models import DadosContrato
from .permissoes import GESTAO
from .utils import ErroDeFormulario, texto
from .validacoes import chave_documento, documento_valido
from .views import InternoRequiredMixin, RespostaJSONMixin


def cnpj_pontuado(valor: str) -> str:
    """O CNPJ conferido pelos dígitos, escrito com pontos, barra e traço."""
    chave = chave_documento(valor)
    if len(chave) != 14 or not documento_valido(chave):
        raise ErroDeFormulario("CNPJ inválido. Confira os números.")
    return f"{chave[:2]}.{chave[2:5]}.{chave[5:8]}/{chave[8:12]}-{chave[12:]}"


#: "RG", "RG:", "R.G. nº" escritos antes do número (o contrato já escreve "RG: ").
RG_COM_ROTULO = re.compile(r"^\s*R\.?\s*G\.?\s*(?:n[.ºo°]*)?\s*[:\-–]?\s*(?=\d)", re.IGNORECASE)


class DadosContratoInnerView(RespostaJSONMixin, InternoRequiredMixin, View):
    template_name = "dados_contrato_inner.html"
    rota_padrao = "dados_contrato_inner"

    #: Cobrado no dispatch (o superusuário passa): vale para o GET e o POST.
    funcoes_necessarias = (GESTAO,)

    #: (campo, rótulo, limite, obrigatório ao salvar). Os do representante
    #: podem ficar vazios ao salvar -- o dono preenche aos poucos --, mas o
    #: contrato não sai enquanto faltarem (`DadosContrato.faltando`).
    CAMPOS = (
        ("nome_fantasia", "o nome fantasia", 120, True),
        ("razao_social", "a razão social", 160, True),
        ("cnpj", "o CNPJ", 18, True),
        ("endereco_sede", "o endereço da sede", 240, True),
        ("cidade", "a cidade do contrato", 80, True),
        ("representante_nome", "o nome do representante", 160, False),
        ("representante_rg", "o RG do representante", 30, False),
        ("representante_endereco", "o endereço do representante", 240, False),
    )

    @staticmethod
    def previa(dados):
        """O preâmbulo como sai no contrato, com cada dado num <mark>.

        O texto é o de `contrato.preambulo` (o mesmo do contrato, sem cópia
        aqui); cada dado vira um <mark data-dc-previa="campo"> que o
        dados-contrato.js troca enquanto se digita. Tudo escapado.
        """
        vendedor = contrato.dados_do_vendedor(dados)
        marcas = {campo: f"@@{campo}@@" for campo in vendedor}
        html = escape(contrato.preambulo(marcas)["abertura"])
        for campo, valor in vendedor.items():
            html = html.replace(
                marcas[campo],
                f'<mark data-dc-previa="{campo}"{"" if valor else " class=vazio"}>{escape(valor) or "…"}</mark>',
            )
        return mark_safe(html)

    @staticmethod
    def acrescimo_digitado(request):
        """O acréscimo do sistema de ficha (seções 143 e 148): "350", "350,00", "1.250,50". Vazio = sem a opção."""
        bruto = (request.POST.get("acrescimo_moedeiro") or "").strip().replace("R$", "").replace(" ", "")
        if not bruto:
            return None
        if "," in bruto:
            bruto = bruto.replace(".", "").replace(",", ".")
        try:
            valor = Decimal(bruto).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            raise ErroDeFormulario(
                "Digite o acréscimo do sistema de ficha em reais, como 999,00 — ou deixe vazio para não oferecer a opção.",
                campo="acrescimo_moedeiro",
            )
        if valor < 0 or valor > Decimal("99999.99"):
            raise ErroDeFormulario(
                "O acréscimo do sistema de ficha precisa ser um valor entre R$ 0,00 e R$ 99.999,99.",
                campo="acrescimo_moedeiro",
            )
        return valor or None

    def get(self, request):
        dados = DadosContrato.atual()
        return render(request, self.template_name, {
            "dados": dados,
            "faltando": dados.faltando,
            "previa": self.previa(dados),
        })

    def acao_salvar(self, request):
        dados = DadosContrato.atual()
        for campo, rotulo, limite, obrigatorio in self.CAMPOS:
            valor = " ".join(texto(request, campo, obrigatorio=obrigatorio, rotulo=rotulo, limite=limite).split())
            setattr(dados, campo, valor)
        # PARA SAIR COMO NO CONTRATO MODELO (seção 141): o texto já escreve
        # "RG: " antes do número e "; e, do outro lado" depois do endereço.
        # Quem digita "RG: 00.000.000-0" ou termina o endereço com ponto não
        # ganha "RG: RG: ..." nem "cidade.; e, do outro lado".
        dados.representante_rg = RG_COM_ROTULO.sub("", dados.representante_rg).strip()
        dados.representante_endereco = dados.representante_endereco.rstrip(" .;,")
        dados.endereco_sede = dados.endereco_sede.rstrip(" .;,")
        dados.acrescimo_moedeiro = self.acrescimo_digitado(request)
        dados.cnpj = cnpj_pontuado(dados.cnpj)
        dados.atualizado_por = request.user
        dados.save()
        if dados.faltando:
            return self.sucesso(
                request,
                "Salvo. Ainda falta: " + ", ".join(dados.faltando)
                + " -- sem isso o contrato não sai para assinatura.",
                faltando=dados.faltando,
            )
        return self.sucesso(
            request,
            "Dados do contrato salvos. O próximo contrato gerado já sai com eles.",
            faltando=[],
        )
