"""Tarefas: as de todos (Gestão) e as minhas (cada um)."""

from __future__ import annotations

from django.contrib import messages
from django.db.models import Case, IntegerField, Value, When
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone

from sistema_interno.permissoes import GESTAO
from sistema_interno.utils import destino_de_retorno, pede_json

from . import acesso, tarefas as svc
from .forms import TarefaForm
from .models import Colaborador, Setor, Situacao, Tarefa
from .views import BaseRH

FILTROS = (
    ("abertas", "Abertas"),
    ("atrasadas", "Atrasadas"),
    ("feitas", "Feitas"),
    ("todas", "Todas"),
)
ORDEM_PRIORIDADE = Case(
    When(prioridade="urgente", then=Value(0)), When(prioridade="alta", then=Value(1)),
    When(prioridade="normal", then=Value(2)), default=Value(3), output_field=IntegerField(),
)
ORDEM_SITUACAO = Case(
    When(situacao="fazendo", then=Value(0)), When(situacao="a_fazer", then=Value(1)),
    default=Value(2), output_field=IntegerField(),
)


def _filtrar(consulta, filtro):
    hoje = timezone.localdate()
    if filtro == "abertas":
        return consulta.exclude(situacao=Tarefa.Estado.FEITA)
    if filtro == "atrasadas":
        return consulta.exclude(situacao=Tarefa.Estado.FEITA).filter(prazo__lt=hoje)
    if filtro == "feitas":
        return consulta.filter(situacao=Tarefa.Estado.FEITA)
    return consulta


class TarefasView(BaseRH):
    aba = "tarefas"

    def get(self, request, form=None):
        gere = acesso.gere(request.user)
        meu = self.meu(request)
        filtro = request.GET.get("filtro") or "abertas"
        if filtro not in dict(FILTROS):
            filtro = "abertas"
        consulta = Tarefa.objects.select_related("colaborador", "content_type")
        pessoa = request.GET.get("pessoa") or ""
        setor = request.GET.get("setor") or ""
        if gere:
            if pessoa.isdigit():
                consulta = consulta.filter(colaborador_id=int(pessoa))
            elif pessoa == "sem":
                consulta = consulta.filter(colaborador__isnull=True)
            if setor in Setor.values:
                consulta = consulta.filter(setor=setor)
        elif meu is not None:
            consulta = consulta.filter(colaborador=meu)
        else:
            consulta = consulta.none()
        lista = list(
            _filtrar(consulta, filtro).annotate(_p=ORDEM_PRIORIDADE, _s=ORDEM_SITUACAO)
            .order_by("_s", "prazo", "_p", "-id")[:300]
        )
        pessoas = (
            list(Colaborador.objects.exclude(situacao=Situacao.DESLIGADO).order_by("nome")) if gere else []
        )
        return self.responder(
            request, "rh/tarefas.html",
            tarefas=lista, filtros=FILTROS, filtro=filtro, gere=gere,
            pessoas=pessoas, pessoa=pessoa, setor=setor, setores=Setor.choices,
            form=form or (TarefaForm() if gere else None),
            ordens=svc.ordens_de_producao_de(meu) if meu else [],
            etapas=svc.ETAPAS_DA_PRODUCAO, prioridades=Tarefa.Prioridade.choices,
            estados=Tarefa.Estado.choices, hoje=timezone.localdate(),
        )

    def post(self, request):
        if not acesso.gere(request.user):
            raise Http404()
        form = TarefaForm(request.POST)
        if not form.is_valid():
            if pede_json(request):
                return self.falhou_form(request, form, titulo="A tarefa não foi criada", voltar=reverse("rh_tarefas"))
            erros = "; ".join(m for lista in form.errors.values() for m in lista)
            messages.error(request, f"A tarefa não foi criada: {erros}")
            return self.get(request, form=form)
        tarefa = form.save(commit=False)
        tarefa.criada_por = request.user
        if not tarefa.setor and tarefa.colaborador_id:
            tarefa.setor = tarefa.colaborador.setor
        tarefa.save()
        quem = tarefa.colaborador.primeiro_nome if tarefa.colaborador_id else "ninguém ainda"
        return self.ok(request, f"Tarefa criada para {quem}.", voltar=reverse("rh_tarefas"))


def _tarefa_minha_ou_da_gestao(request, pk):
    tarefa = Tarefa.objects.select_related("colaborador").filter(pk=pk).first()
    if tarefa is None:
        raise Http404()
    if acesso.gere(request.user):
        return tarefa
    meu = acesso.colaborador_de(request.user)
    if meu is not None and tarefa.colaborador_id == meu.pk:
        return tarefa
    raise Http404()


class TarefaSituacaoView(BaseRH):
    http_method_names = ["post"]

    def post(self, request, pk):
        tarefa = _tarefa_minha_ou_da_gestao(request, pk)
        nova = request.POST.get("situacao")
        if nova not in Tarefa.Estado.values:
            return self.falhou(request, "Situação inválida.", titulo="Não deu para mudar",
                               voltar=reverse("rh_tarefas"))
        svc.mudar_situacao(tarefa, nova, por=request.user)
        texto = f"“{tarefa.titulo}”: {tarefa.get_situacao_display().lower()}."
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"status": "sucesso", "msg": texto, "situacao": tarefa.situacao,
                                 "rotulo": tarefa.get_situacao_display()})
        messages.success(request, texto)
        return redirect(destino_de_retorno(request, request.POST.get("voltar"), reverse("rh_tarefas")))


class TarefaEditarView(BaseRH):
    funcoes_necessarias = (GESTAO,)
    http_method_names = ["post"]

    def post(self, request, pk):
        tarefa = get_object_or_404(Tarefa, pk=pk)
        if request.POST.get("action") == "excluir":
            titulo = tarefa.titulo
            tarefa.delete()
            return self.ok(request, f"Tarefa “{titulo}” excluída.", voltar=reverse("rh_tarefas"))
        form = TarefaForm(request.POST, instance=tarefa)
        if not form.is_valid():
            return self.falhou_form(request, form, titulo="A tarefa não foi salva", voltar=reverse("rh_tarefas"))
        form.save()
        return self.ok(request, "Tarefa salva.", voltar=reverse("rh_tarefas"))


class SugerirView(BaseRH):
    """Quem sugerir para uma etapa/setor (JSON para a tela de tarefas)."""

    funcoes_necessarias = (GESTAO,)

    def get(self, request):
        etapa = (request.GET.get("etapa") or "").strip()[:60]
        setor = request.GET.get("setor") or None
        if setor not in Setor.values:
            setor = None
        pessoas = svc.sugerir_responsaveis(etapa or None, setor=setor, limite=6)
        return JsonResponse({
            "status": "sucesso",
            "especialidade": svc.especialidade_da_etapa(etapa) or "",
            "setor": setor or svc.setor_da_etapa(etapa) or "",
            "pessoas": [
                {"id": p.pk, "nome": p.nome, "cargo": p.cargo, "abertas": p.abertas,
                 "especialista": p.especialista}
                for p in pessoas
            ],
        })
