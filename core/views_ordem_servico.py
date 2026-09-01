"""Documento público da Ordem de Serviço enviado ao cliente."""

import logging

from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.views.generic import View

from .impressao import densidade, peso_do_documento
from core.models import EnderecoEmpresa
from core.email_utils import cnpj_empresa, dados_bancarios_empresa, nome_empresa
from sistema_interno.models import OrdemServico
from sistema_interno.pix import dados_pix


def carregar_ordem(**filtros):
    return get_object_or_404(
        OrdemServico.objects
        .select_related(
            "cliente", "orcamento", "manutencao__usuario__user",
            "tecnico", "responsavel",
        )
        .prefetch_related("itens", "manutencao__imagens"),
        **filtros,
    )


def contexto_ordem(ordem, *, previsualizacao=False, request=None):
    empresa = EnderecoEmpresa.objects.filter(ativo=True).first()
    responsavel = "Equipe Lazer & Sport"
    if ordem.responsavel_id:
        responsavel = (
            ordem.responsavel.get_full_name().strip()
            or ordem.responsavel.username
        )
    tecnico = "A definir"
    if ordem.tecnico_id:
        tecnico = ordem.tecnico.get_full_name().strip() or ordem.tecnico.username

    itens = list(ordem.itens.all())
    fotos = list(ordem.manutencao.imagens.all()) if ordem.manutencao_id else []
    contexto = {
        "ordem": ordem,
        "itens": itens,
        # QUÃO APERTADA A FOLHA PRECISA SAIR. Ver `core/impressao.py`.
        #
        # O peso conta o documento inteiro, e não só os itens: uma O.S.
        # de quatro itens com um diagnóstico de dez linhas, seis fotos e
        # o quadro do Pix ocupa mais folha do que uma de doze itens
        # secos. Contar só a tabela acertaria a segunda e erraria a
        # primeira.
        "densidade_folha": densidade(peso_do_documento(
            itens=len(itens),
            textos=(
                ordem.defeito_relatado,
                ordem.diagnostico,
                ordem.servico_executado,
                ordem.observacoes,
                ordem.endereco_servico,
            ),
            fotos=len(fotos),
            com_pagamento=(
                ordem.status_pagamento != ordem.StatusPagamento.PAGO
            ),
        )),
        "fotos": fotos,
        "empresa": empresa,
        "empresa_nome": nome_empresa(),
        "empresa_cnpj": cnpj_empresa(),
        "dados_bancarios": dados_bancarios_empresa(),
        "responsavel_nome": responsavel,
        "tecnico_nome": tecnico,
        "previsualizacao": previsualizacao,
        "pode_confirmar": (
            not previsualizacao
            and bool(ordem.enviada_em)
            and not ordem.cliente_ciente
        ),
        "telefone_empresa": (
            getattr(settings, "EMPRESA_TELEFONE", "")
            or (empresa.telefone if empresa else "")
        ),
        "whatsapp_empresa": getattr(settings, "EMPRESA_WHATSAPP", ""),
        "email_empresa": getattr(settings, "EMPRESA_EMAIL", ""),
        "instagram_empresa": getattr(settings, "EMPRESA_INSTAGRAM", ""),
    }
    contexto.update(dados_pix(ordem))
    return contexto


class OrdemServicoPublicaView(View):
    template_name = "ordem_servico_publica.html"

    def get(self, request, token):
        ordem = carregar_ordem(token=token)
        if not ordem.enviada_em:
            raise Http404("Ordem de Serviço ainda não enviada.")
        return render(
            request,
            self.template_name,
            contexto_ordem(ordem, request=request),
        )

    def post(self, request, token):
        ordem = carregar_ordem(token=token)
        if not ordem.enviada_em:
            raise Http404("Ordem de Serviço ainda não enviada.")
        contexto = contexto_ordem(ordem, request=request)
        if not contexto["pode_confirmar"]:
            return redirect("ordem_servico_publica", token=token)
        nome = (request.POST.get("nome") or "").strip()
        if not nome:
            contexto["erro"] = "Escreva seu nome para confirmar o recebimento."
            return render(request, self.template_name, contexto, status=400)
        ordem.registrar_ciencia(nome)
        try:
            from sistema_interno.notificacoes import avisar_ciencia_ordem_servico

            avisar_ciencia_ordem_servico(ordem)
        except Exception:
            logging.getLogger(__name__).exception(
                "Falha ao avisar ciência da O.S. %s", ordem.pk
            )
        return redirect("ordem_servico_publica", token=token)


ordem_servico_publica = require_http_methods(["GET", "POST"])(
    OrdemServicoPublicaView.as_view()
)
