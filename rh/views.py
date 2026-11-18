"""As telas do RH: UMA entrada no menu, com abas.

Para a Gestão (e o superusuário): Início · Colaboradores · Ponto · Tarefas ·
Documentos (e "Meu ponto", se a conta dela também tem ficha). Para o
Financeiro: Colaboradores (com o que precisa para pagar) · Ponto (os
espelhos). Para todo o resto da equipe: Meu ponto · Minhas tarefas · Minha
ficha. Quem pode o quê está em `acesso.py`; as telas de lista barram pela
função (o mesmo `funcoes_necessarias` das outras telas do painel) e as de
um registro conferem o objeto -- ficha, documento e espelho alheios dão 404,
inclusive em URL digitada à mão.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import View

from sistema_interno.permissoes import FINANCEIRO, GESTAO, NOMES_DOS_GRUPOS
from sistema_interno.views import InternoRequiredMixin

from . import acesso, servicos, termo as svc_termo
from .forms import ColaboradorForm, DocumentoForm
from .models import (
    Colaborador,
    DocumentoColaborador,
    Especialidade,
    RegistroRH,
    Setor,
    Situacao,
    TipoDocumento,
)
from .validadores import UFS

BANCOS_COMUNS = (
    "001 Banco do Brasil", "033 Santander", "104 Caixa Econômica Federal", "237 Bradesco",
    "260 Nubank", "341 Itaú", "077 Banco Inter", "336 C6 Bank", "290 PagBank", "323 Mercado Pago",
    "380 PicPay", "748 Sicredi", "756 Sicoob",
)


def sem_cache(resposta):
    """Dado pessoal não fica no cache do navegador nem da navegação suave."""
    resposta["Cache-Control"] = "no-store, private"
    resposta["X-LS-No-Store"] = "1"
    return resposta


def abas_de(user, meu=None):
    """As abas do RH para esta pessoa (a entrada única do menu)."""
    gere = acesso.gere(user)
    equipe = acesso.ve_equipe(user)
    abas = []
    if gere:
        abas.append(("inicio", "Início", "bi-grid-1x2-fill", reverse("rh_inicio")))
    if equipe:
        abas.append(("colaboradores", "Colaboradores", "bi-people-fill", reverse("rh_colaboradores")))
        abas.append(("ponto_equipe", "Ponto", "bi-clock-history", reverse("rh_ponto_equipe")))
    if gere:
        abas.append(("tarefas", "Tarefas", "bi-check2-square", reverse("rh_tarefas")))
        abas.append(("documentos", "Documentos a vencer", "bi-folder2-open", reverse("rh_documentos")))
    if meu is not None or not equipe:
        abas.append(("ponto", "Meu ponto", "bi-fingerprint", reverse("rh_ponto")))
        if not gere:
            abas.append(("tarefas", "Minhas tarefas", "bi-check2-square", reverse("rh_tarefas")))
    if meu is not None and not equipe:
        abas.append(("ficha", "Minha ficha", "bi-person-vcard", reverse("rh_ficha", args=[meu.pk])))
    return abas


class BaseRH(InternoRequiredMixin, View):
    """Toda tela do RH: dentro do painel, com as abas e o "quem sou eu"."""

    aba = ""

    def meu(self, request):
        return acesso.colaborador_de(request.user)

    def contexto(self, request, **extra):
        meu = self.meu(request)
        return {
            "abas_rh": abas_de(request.user, meu),
            "aba_rh": self.aba,
            "meu_colaborador": meu,
            "acesso_rh": acesso.acesso(request.user),
            **extra,
        }

    def responder(self, request, modelo, **extra):
        return sem_cache(render(request, modelo, self.contexto(request, **extra)))


# ======================================================================
# INÍCIO (o painel compacto da Gestão)
# ======================================================================
class InicioView(BaseRH):
    aba = "inicio"

    def get(self, request):
        if not acesso.gere(request.user):
            if acesso.ve_equipe(request.user):
                return redirect("rh_colaboradores")
            return redirect("rh_ponto")
        return self.responder(request, "rh/inicio.html", painel=servicos.painel())


# ======================================================================
# COLABORADORES
# ======================================================================
FILTROS_SITUACAO = (
    ("ativos", "Em atividade"),
    ("ferias", "Férias"),
    ("afastado", "Afastados"),
    ("desligado", "Desligados"),
    ("todos", "Todos"),
)


class ColaboradoresView(BaseRH):
    aba = "colaboradores"
    funcoes_necessarias = (GESTAO, FINANCEIRO)

    def get(self, request):
        gere = acesso.gere(request.user)
        situacao = request.GET.get("situacao") or "ativos"
        setor = request.GET.get("setor") or ""
        busca = (request.GET.get("q") or "").strip()[:80]
        so_termo = request.GET.get("termo") == "pendente"
        so_docs = request.GET.get("docs") == "pendente"

        consulta = svc_termo.com_situacao(Colaborador.objects.select_related("usuario"))
        if situacao == "ativos":
            consulta = consulta.exclude(situacao=Situacao.DESLIGADO)
        elif situacao in Situacao.values:
            consulta = consulta.filter(situacao=situacao)
        if setor in Setor.values:
            consulta = consulta.filter(setor=setor)
        if busca:
            digitos = "".join(c for c in busca if c.isdigit())
            filtro = Q(nome__icontains=busca) | Q(cargo__icontains=busca)
            if len(digitos) >= 3:
                filtro |= Q(cpf__contains=digitos)
            consulta = consulta.filter(filtro)
        if so_termo:
            consulta = consulta.exclude(situacao=Situacao.DESLIGADO).filter(termo_assinado=False)
        if gere:
            consulta = consulta.prefetch_related("documentos")
        pessoas = list(consulta.order_by("nome"))
        linhas = []
        for pessoa in pessoas:
            falta = servicos.faltando(pessoa, list(pessoa.documentos.all())) if gere else []
            if so_docs and not falta:
                continue
            linhas.append({
                "c": pessoa,
                "falta": falta,
                "termo": svc_termo.situacao_de(pessoa),
            })
        contagem = {
            "termo_pendentes": svc_termo.pendentes().count() if gere else 0,
        }
        return self.responder(
            request, "rh/colaboradores.html",
            linhas=linhas, total=len(linhas), filtros_situacao=FILTROS_SITUACAO, situacao=situacao,
            setores=Setor.choices, setor=setor, busca=busca, so_termo=so_termo, so_docs=so_docs,
            gere=gere, pagamento=acesso.ve_pagamento(request.user), contagem=contagem,
            rotulos_termo=svc_termo.ROTULOS,
        )


class _FormularioColaborador(BaseRH):
    aba = "colaboradores"
    funcoes_necessarias = (GESTAO,)

    def contas_da_equipe(self):
        Usuario = get_user_model()
        ligadas = set(Colaborador.objects.exclude(usuario=None).values_list("usuario_id", flat=True))
        return [
            u for u in Usuario.objects.filter(
                Q(is_superuser=True) | Q(groups__name__in=NOMES_DOS_GRUPOS), is_active=True,
            ).distinct().order_by("username")
            if u.pk not in ligadas
        ][:200]

    def tela(self, request, form, colaborador=None):
        return self.responder(
            request, "rh/colaborador_form.html",
            form=form, colaborador=colaborador, ufs=UFS, bancos=BANCOS_COMUNS,
            contas=self.contas_da_equipe(), especialidades=Especialidade.choices,
        )

    def salvar(self, request, form, novo):
        with transaction.atomic():
            colaborador = form.save()
            servicos.ligar_na_producao(colaborador)
            mudou = ", ".join(form.changed_data[:12]) if not novo else ""
            servicos.registrar(
                request,
                RegistroRH.Acao.FICHA_CRIADA if novo else RegistroRH.Acao.FICHA_ALTERADA,
                colaborador=colaborador,
                descricao=("Ficha cadastrada" if novo else f"Campos: {mudou}" if mudou else "Ficha salva sem mudança"),
            )
        messages.success(
            request,
            f"Ficha de {colaborador.primeiro_nome} {'cadastrada' if novo else 'atualizada'}."
            + (" Falta o termo de exclusividade: envie para assinatura na ficha." if novo else ""),
        )
        return redirect("rh_ficha", pk=colaborador.pk)


class ColaboradorNovoView(_FormularioColaborador):
    def get(self, request):
        return self.tela(request, ColaboradorForm(usuario=request.user))

    def post(self, request):
        form = ColaboradorForm(request.POST, usuario=request.user)
        if not form.is_valid():
            return self.tela(request, form)
        return self.salvar(request, form, novo=True)


class ColaboradorEditarView(_FormularioColaborador):
    def get(self, request, pk):
        colaborador = get_object_or_404(Colaborador, pk=pk)
        return self.tela(request, ColaboradorForm(instance=colaborador, usuario=request.user), colaborador)

    def post(self, request, pk):
        colaborador = get_object_or_404(Colaborador, pk=pk)
        form = ColaboradorForm(request.POST, instance=colaborador, usuario=request.user)
        if not form.is_valid():
            return self.tela(request, form, colaborador)
        return self.salvar(request, form, novo=False)


def colaborador_visivel(request, pk):
    """A ficha, se a pessoa pode vê-la; senão 404 (sem dizer se existe)."""
    colaborador = Colaborador.objects.select_related("usuario", "colaborador_producao").filter(pk=pk).first()
    if colaborador is None:
        raise Http404("Ficha não encontrada.")
    partes = acesso.partes_da_ficha(request.user, colaborador)
    if not partes:
        raise Http404("Ficha não encontrada.")
    return colaborador, partes


class FichaView(BaseRH):
    aba = "colaboradores"

    def get(self, request, pk):
        colaborador, partes = colaborador_visivel(request, pk)
        if acesso.eh_o_proprio(request.user, colaborador) and not acesso.ve_equipe(request.user):
            self.aba = "ficha"
        documentos = list(colaborador.documentos.select_related("enviado_por")) if "documentos" in partes else []
        termo_atual = svc_termo.termo_atual(colaborador) if "termo" in partes else None
        contexto = {
            "c": colaborador,
            "partes": partes,
            "documentos": documentos,
            "checklist": servicos.checklist(colaborador, documentos) if "documentos" in partes else [],
            "form_documento": DocumentoForm(colaborador=colaborador) if acesso.gere(request.user) else None,
            "gere": acesso.gere(request.user),
            "proprio": acesso.eh_o_proprio(request.user, colaborador),
            "termo_situacao": svc_termo.situacao_de(colaborador) if "termo" in partes else "",
            "termo_atual": termo_atual,
            "termo_assinado": svc_termo.ultimo_assinado(colaborador) if "termo" in partes else None,
            "rotulos_termo": svc_termo.ROTULOS,
            "registros": (
                list(colaborador.registros.select_related("documento")[:25]) if "auditoria" in partes else []
            ),
            "tarefas_abertas": colaborador.tarefas.exclude(situacao="feita").count(),
            "conta_sem_funcao": self._conta_sem_funcao(colaborador),
            "tipos_documento": [c for c in TipoDocumento.choices if c[0] != TipoDocumento.TERMO],
        }
        return self.responder(request, "rh/ficha.html", **contexto)

    @staticmethod
    def _conta_sem_funcao(colaborador):
        """A conta ligada não tem a função do setor (aviso, não erro)."""
        conta = colaborador.usuario
        if not conta or conta.is_superuser:
            return False
        from sistema_interno.permissoes import FUNCOES_POR_CODIGO

        funcao = FUNCOES_POR_CODIGO.get(colaborador.setor)
        return bool(funcao and not conta.groups.filter(name=funcao.grupo).exists())


class FichaImprimirView(BaseRH):
    """A ficha em folha A4, para "Salvar em PDF" (o caminho das outras folhas)."""

    def get(self, request, pk):
        colaborador, partes = colaborador_visivel(request, pk)
        documentos = list(colaborador.documentos.all()) if "documentos" in partes else []
        servicos.registrar(request, RegistroRH.Acao.FICHA_IMPRESSA, colaborador=colaborador,
                           descricao="Ficha em PDF" + (" (com salário)" if "pagamento" in partes else ""))
        return sem_cache(render(request, "rh/folha_ficha.html", {
            "c": colaborador,
            "partes": partes,
            "documentos": documentos,
            "checklist": servicos.checklist(colaborador, documentos) if "documentos" in partes else [],
            "termo_situacao": svc_termo.situacao_de(colaborador),
            "termo_assinado": svc_termo.ultimo_assinado(colaborador),
            "rotulos_termo": svc_termo.ROTULOS,
            "empresa": svc_termo.dados_da_empresa(),
            "gerado_em": timezone.localtime(),
            "gerado_por": request.user.get_full_name() or request.user.get_username(),
            "voltar_url": reverse("rh_ficha", args=[colaborador.pk]),
            "imprimir_ao_abrir": request.GET.get("imprimir") == "1",
        }))


# ======================================================================
# DOCUMENTOS
# ======================================================================
class DocumentoEnviarView(BaseRH):
    funcoes_necessarias = (GESTAO,)
    http_method_names = ["post"]

    def post(self, request, pk):
        colaborador = get_object_or_404(Colaborador, pk=pk)
        form = DocumentoForm(request.POST, request.FILES, colaborador=colaborador)
        if not form.is_valid():
            erros = "; ".join(m for lista in form.errors.values() for m in lista)
            messages.error(request, f"O documento não foi guardado: {erros}", extra_tags="titulo:Documento recusado")
            return redirect(reverse("rh_ficha", args=[pk]) + "#documentos")
        dados = form.cleaned_data
        documento = servicos.guardar_documento(
            colaborador, form.conferido, tipo=dados["tipo"], descricao=dados.get("descricao", ""),
            emissao=dados.get("emissao"), validade=dados.get("validade"), usuario=request.user,
        )
        servicos.registrar(
            request, RegistroRH.Acao.DOC_ENVIADO, colaborador=colaborador, documento=documento,
            descricao=f"{documento.rotulo} · {documento.tamanho_texto} · SHA-256 {documento.sha256[:12]}…",
        )
        messages.success(request, f"{documento.rotulo} guardado na pasta de {colaborador.primeiro_nome}.")
        return redirect(reverse("rh_ficha", args=[pk]) + "#documentos")


class DocumentoArquivoView(BaseRH):
    """Entrega o arquivo -- só por aqui, conferindo a permissão e anotando."""

    def get(self, request, pk):
        documento = DocumentoColaborador.objects.select_related("colaborador").filter(pk=pk).first()
        if documento is None:
            raise Http404("Documento não encontrado.")
        if not acesso.pode_abrir_documento(request.user, documento):
            servicos.registrar(
                request, RegistroRH.Acao.ACESSO_NEGADO, colaborador=documento.colaborador,
                descricao=f"Tentou abrir {documento.rotulo} (#{documento.pk})",
            )
            raise Http404("Documento não encontrado.")
        try:
            with documento.arquivo.open("rb") as arquivo:
                dados = arquivo.read()
        except (FileNotFoundError, OSError):
            messages.error(request, "O arquivo deste documento não foi encontrado no armazenamento.")
            return redirect("rh_ficha", pk=documento.colaborador_id)
        servicos.registrar(
            request, RegistroRH.Acao.DOC_ABERTO, colaborador=documento.colaborador, documento=documento,
            descricao=documento.rotulo,
        )
        extensao = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
        # Sem nome de pessoa no nome do arquivo (ele fica no histórico de downloads).
        nome = f"{documento.tipo}-{documento.pk}.{extensao.get(documento.tipo_conteudo, 'bin')}"
        resposta = HttpResponse(dados, content_type=documento.tipo_conteudo)
        disposicao = "attachment" if request.GET.get("baixar") == "1" else "inline"
        resposta["Content-Disposition"] = f'{disposicao}; filename="{nome}"'
        resposta["X-Content-Type-Options"] = "nosniff"
        # O arquivo abre sozinho, sem rodar nada e sem ser posto em moldura alheia.
        resposta["Content-Security-Policy"] = "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; sandbox"
        resposta["Referrer-Policy"] = "no-referrer"
        return sem_cache(resposta)


class DocumentoRemoverView(BaseRH):
    funcoes_necessarias = (GESTAO,)
    http_method_names = ["post"]

    def post(self, request, pk):
        documento = get_object_or_404(DocumentoColaborador.objects.select_related("colaborador"), pk=pk)
        if hasattr(documento, "termo") and documento.termo is not None and documento.termo.assinado:
            messages.error(request, "O PDF do termo assinado não se remove: ele é a prova da assinatura.")
            return redirect(reverse("rh_ficha", args=[documento.colaborador_id]) + "#documentos")
        colaborador = documento.colaborador
        servicos.registrar(
            request, RegistroRH.Acao.DOC_REMOVIDO, colaborador=colaborador,
            descricao=f"{documento.rotulo} (#{documento.pk}, enviado em {timezone.localtime(documento.enviado_em):%d/%m/%Y})",
        )
        documento.delete()
        messages.success(request, "Documento removido. O registro de quem removeu fica na trilha da ficha.")
        return redirect(reverse("rh_ficha", args=[colaborador.pk]) + "#documentos")


class DocumentosView(BaseRH):
    aba = "documentos"
    funcoes_necessarias = (GESTAO,)

    def get(self, request):
        hoje = timezone.localdate()
        vencendo = servicos.documentos_a_vencer(hoje=hoje)
        return self.responder(
            request, "rh/documentos.html",
            vencendo=vencendo,
            vencidos=[d for d in vencendo if d.validade < hoje],
            a_vencer=[d for d in vencendo if d.validade >= hoje],
            pendencias=servicos.fichas_com_pendencia(),
            janela=servicos.JANELA_DE_VENCIMENTO,
        )
