"""A tela "Segurança das contas" do painel (interno.).

O que as regras de conta barraram, para alguém da Gestão olhar e decidir:

  * E-MAIL REPETIDO (a migração contas/0002 bloqueou a conta): REATIVAR --
    a conta volta a entrar, mas sem e-mail; um endereço novo é cadastrado
    depois, em "Contas de clientes", pela regra de sempre -- ou MANTER
    BLOQUEADA;
  * LOGIN BLOQUEADO (o freio de senhas erradas): LIBERAR AGORA, antes de a
    pausa vencer sozinha, ou CIENTE;
  * LOGIN SOCIAL RECUSADO: CIENTE.

Toda decisão grava quem resolveu e quando. Nenhuma ação apaga a ocorrência:
ela muda de situação e continua na lista "Resolvidas".
"""

from __future__ import annotations

from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.generic import View

from sistema_interno.permissoes import GESTAO
from sistema_interno.utils import ErroDeFormulario
from sistema_interno.views import InternoRequiredMixin, RespostaJSONMixin

from . import freio
from .models import OcorrenciaSeguranca

Tipo = OcorrenciaSeguranca.Tipo
Situacao = OcorrenciaSeguranca.Situacao

FILTROS_DE_SITUACAO = (
    ("pendentes", "Esperando revisão"),
    ("resolvidas", "Resolvidas"),
    ("todas", "Todas"),
)
FILTROS_DE_TIPO = (("", "Todos os tipos"),) + tuple(Tipo.choices)


class SegurancaContasView(RespostaJSONMixin, InternoRequiredMixin, View):
    template_name = "contas/seguranca_contas.html"
    rota_padrao = "seguranca_contas"
    funcoes_necessarias = (GESTAO,)
    POR_PAGINA = 25

    def get(self, request):
        situacao = request.GET.get("situacao") or "pendentes"
        if situacao not in dict(FILTROS_DE_SITUACAO):
            situacao = "pendentes"
        tipo = request.GET.get("tipo") or ""
        if tipo not in dict(FILTROS_DE_TIPO):
            tipo = ""

        ocorrencias = OcorrenciaSeguranca.objects.select_related(
            "usuario", "conta_mantida", "resolvido_por",
        )
        if situacao == "pendentes":
            ocorrencias = ocorrencias.filter(situacao=Situacao.PENDENTE)
        elif situacao == "resolvidas":
            ocorrencias = ocorrencias.exclude(situacao=Situacao.PENDENTE)
        if tipo:
            ocorrencias = ocorrencias.filter(tipo=tipo)

        pagina = Paginator(ocorrencias, self.POR_PAGINA).get_page(request.GET.get("page"))
        query = request.GET.copy()
        query.pop("page", None)

        semana = timezone.now() - timedelta(days=7)
        pendente = Q(situacao=Situacao.PENDENTE)
        numeros = OcorrenciaSeguranca.objects.aggregate(
            pendentes=Count("id", filter=pendente),
            repetidos=Count("id", filter=pendente & Q(tipo=Tipo.EMAIL_REPETIDO)),
            logins=Count("id", filter=Q(tipo=Tipo.LOGIN_BLOQUEADO, criado_em__gte=semana)),
            sociais=Count("id", filter=Q(tipo=Tipo.SOCIAL_RECUSADO, criado_em__gte=semana)),
        )

        return render(request, self.template_name, {
            "ocorrencias": pagina.object_list,
            "pagina": pagina,
            "query_sem_pagina": query.urlencode(),
            "situacao": situacao,
            "tipo": tipo,
            "filtros_situacao": FILTROS_DE_SITUACAO,
            "filtros_tipo": FILTROS_DE_TIPO,
            "numeros": numeros,
            "Tipo": Tipo,
            "freio": {
                "conta": freio.limite_por_conta(),
                "ip": freio.limite_por_ip(),
                "janela": freio.janela() // 60,
                "bloqueio": freio.duracao_do_bloqueio() // 60,
                "ativo": freio.ativo(),
            },
        })

    # ------------------------------------------------------------ ações
    def _ocorrencia(self, request, *tipos):
        ocorrencia = get_object_or_404(
            OcorrenciaSeguranca.objects.select_for_update(), pk=request.POST.get("id") or 0,
        )
        if tipos and ocorrencia.tipo not in tipos:
            raise ErroDeFormulario("Esta ação não vale para este tipo de ocorrência.")
        if not ocorrencia.pendente:
            raise ErroDeFormulario(
                f"Esta ocorrência já foi resolvida ({ocorrencia.get_situacao_display().lower()})."
            )
        return ocorrencia

    def acao_reativar(self, request):
        ocorrencia = self._ocorrencia(request, Tipo.EMAIL_REPETIDO)
        conta = ocorrencia.usuario
        if conta is None:
            raise ErroDeFormulario("A conta desta ocorrência não existe mais.")
        conta.is_active = True
        conta.save(update_fields=["is_active"])
        ocorrencia.resolver(Situacao.REATIVADA, request.user)
        return self.sucesso(
            request,
            f"Conta @{conta.username} reativada, sem e-mail. Cadastre um endereço "
            "novo para ela em Contas de clientes.",
        )

    def acao_manter(self, request):
        ocorrencia = self._ocorrencia(request, Tipo.EMAIL_REPETIDO)
        ocorrencia.resolver(Situacao.MANTIDA, request.user)
        return self.sucesso(request, "A conta continua bloqueada.")

    def acao_liberar(self, request):
        ocorrencia = self._ocorrencia(request, Tipo.LOGIN_BLOQUEADO)
        freio.liberar(conta=ocorrencia.usuario_id, ip=ocorrencia.ip, login=ocorrencia.login_tentado)
        ocorrencia.resolver(Situacao.LIBERADA, request.user)
        return self.sucesso(request, "Login liberado: a pessoa já pode tentar de novo.")

    def acao_ciente(self, request):
        ocorrencia = self._ocorrencia(request, Tipo.LOGIN_BLOQUEADO, Tipo.SOCIAL_RECUSADO)
        ocorrencia.resolver(Situacao.CIENTE, request.user)
        return self.sucesso(request, "Ocorrência marcada como revisada.")
