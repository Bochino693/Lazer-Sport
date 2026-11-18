"""Contas especiais da equipe e delegação de funções."""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.generic import View

from .permissoes import (
    FUNCOES,
    FUNCOES_POR_CODIGO,
    NOMES_DOS_GRUPOS,
    atribuir_funcoes,
    esquecer_resumo_de_usuarios,
    nomes_das_funcoes,
    resumo_de_usuarios,
)
from .models import AvaliacaoSetor
from .utils import ErroDeFormulario, texto
from .views import RespostaJSONMixin, SuperusuarioInternoRequiredMixin


class UsuariosEquipeInnerView(
    RespostaJSONMixin,
    SuperusuarioInternoRequiredMixin,
    View,
):
    """Uma conta, várias funções; nenhuma subclasse de usuário."""

    rota_padrao = "usuarios_equipe"
    template_name = "usuarios_equipe.html"

    def get(self, request):
        busca = (request.GET.get("q") or "").strip()
        usuarios = (
            User.objects.filter(
                Q(is_superuser=True)
                | Q(groups__name__in=NOMES_DOS_GRUPOS)
                | Q(is_staff=True)
            )
            .prefetch_related("groups")
            .distinct()
            .order_by("-is_superuser", "first_name", "username")
        )
        if busca:
            usuarios = usuarios.filter(
                Q(username__icontains=busca)
                | Q(first_name__icontains=busca)
                | Q(last_name__icontains=busca)
                | Q(email__icontains=busca)
            )
        # A SUBDIVISÃO DO MENU "Pessoas": ?funcao=vendas mostra só quem é de
        # Vendas (a pessoa com duas funções aparece nas duas).
        funcao_ativa = FUNCOES_POR_CODIGO.get((request.GET.get("funcao") or "").strip())
        if funcao_ativa is not None:
            usuarios = usuarios.filter(groups__name=funcao_ativa.grupo)

        linhas = [self._serializar(usuario) for usuario in usuarios]
        resumo = resumo_de_usuarios()
        return render(request, self.template_name, {
            "linhas": linhas,
            "usuarios_dados": linhas,
            "funcoes": FUNCOES,
            "funcoes_com_total": resumo["funcoes"],
            "total_equipe": resumo["equipe"],
            "funcao_ativa": funcao_ativa,
            "busca": busca,
            "total_ativos": sum(1 for linha in linhas if linha["ativo"]),
        })

    @staticmethod
    def _serializar(usuario):
        grupos = nomes_das_funcoes(usuario)
        return {
            "id": usuario.pk,
            "username": usuario.username,
            "first_name": usuario.first_name,
            "last_name": usuario.last_name,
            "nome": usuario.get_full_name() or usuario.username,
            "email": usuario.email or "",
            "ativo": usuario.is_active,
            "superusuario": usuario.is_superuser,
            "funcoes": [
                funcao.codigo for funcao in FUNCOES
                if funcao.grupo in grupos
            ],
            "funcoes_titulos": [
                funcao.titulo for funcao in FUNCOES
                if funcao.grupo in grupos
            ],
        }

    def acao_save(self, request):
        bruto_id = (request.POST.get("id") or "").strip()
        usuario = (
            get_object_or_404(User, pk=int(bruto_id))
            if bruto_id.isdigit() else None
        )
        if usuario and usuario.is_superuser:
            raise ErroDeFormulario(
                "A conta superadministradora é protegida. Altere apenas os "
                "dados da própria conta na tela Minha conta."
            )

        username = texto(
            request, "username", obrigatorio=True,
            rotulo="o usuário", limite=150,
        )
        senha = request.POST.get("password") or ""
        codigos = request.POST.getlist("funcoes")

        if not codigos:
            raise ErroDeFormulario(
                "Escolha ao menos uma função. É ela que define o que a pessoa pode ver."
            )
        # O e-mail pela regra das contas (contas/emails.py): normalizado e
        # livre em TODAS as contas -- inclusive nos endereços do allauth, que
        # esta tela não olhava. Quem grava é a equipe: os endereços da
        # empresa valem aqui.
        from contas.emails import (
            EmailIndisponivel,
            mensagem_de,
            sincronizar_enderecos,
            validar_email_de_conta,
        )
        try:
            email = validar_email_de_conta(
                texto(request, "email", limite=254), usuario=usuario, pela_equipe=True,
            )
        except EmailIndisponivel as exc:
            raise ErroDeFormulario(
                "Esse e-mail já está em uso." if exc.code == "em_uso" else mensagem_de(exc)
            ) from exc

        repetido = User.objects.filter(username__iexact=username)
        if usuario:
            repetido = repetido.exclude(pk=usuario.pk)
        if repetido.exists():
            raise ErroDeFormulario("Esse nome de usuário já está em uso.")
        if usuario is None and not senha:
            raise ErroDeFormulario("Informe a senha inicial.")
        if senha:
            from contas.senhas import validar_senha

            erros = validar_senha(senha, usuario or User(username=username, email=email))
            if erros:
                raise ErroDeFormulario("Senha fraca: " + " ".join(erros))

        usuario = usuario or User()
        usuario.username = username
        usuario.first_name = texto(request, "first_name", limite=150)
        usuario.last_name = texto(request, "last_name", limite=150)
        usuario.email = email
        usuario.is_active = request.POST.get("is_active") == "on"
        if senha:
            usuario.set_password(senha)
        usuario.save()
        sincronizar_enderecos(usuario)
        escolhidas = atribuir_funcoes(usuario, codigos)
        esquecer_resumo_de_usuarios()  # o número de "Pessoas da função" no menu

        return self.sucesso(
            request,
            f"Acesso de {usuario.get_full_name() or usuario.username} salvo.",
            usuario=self._serializar(usuario),
            funcoes=[funcao.titulo for funcao in escolhidas],
        )

    def acao_alternar(self, request):
        usuario = get_object_or_404(User, pk=request.POST.get("id"))
        if usuario.is_superuser or usuario == request.user:
            raise ErroDeFormulario("Essa conta é protegida e não pode ser desativada aqui.")
        usuario.is_active = not usuario.is_active
        usuario.save(update_fields=["is_active"])
        esquecer_resumo_de_usuarios()
        return self.sucesso(
            request,
            f"{usuario.get_full_name() or usuario.username} "
            f"{'reativado' if usuario.is_active else 'desativado'}.",
        )


class AvaliacaoSetoresInnerView(
    RespostaJSONMixin,
    SuperusuarioInternoRequiredMixin,
    View,
):
    """Avaliação mensal dos setores, reservada ao superadministrador."""

    rota_padrao = "avaliacao_setores"
    template_name = "avaliacao_setores.html"

    @staticmethod
    def _periodo(valor):
        valor = (valor or "").strip()
        try:
            ano, mes = (int(parte) for parte in valor.split("-", 1))
            periodo = date(ano, mes, 1)
        except (TypeError, ValueError):
            hoje = timezone.localdate()
            periodo = date(hoje.year, hoje.month, 1)
        return periodo

    def get(self, request):
        periodo = self._periodo(request.GET.get("periodo"))
        existentes = {
            avaliacao.setor: avaliacao
            for avaliacao in AvaliacaoSetor.objects.filter(periodo=periodo)
            .select_related("avaliador")
        }
        grupos = {funcao.codigo: funcao for funcao in FUNCOES}
        linhas = []
        for valor, rotulo in AvaliacaoSetor.Setor.choices:
            funcao = grupos.get(valor)
            integrantes = (
                User.objects.filter(is_active=True, groups__name=funcao.grupo)
                .distinct().count()
                if funcao else 0
            )
            linhas.append({
                "codigo": valor,
                "rotulo": rotulo,
                "icone": funcao.icone if funcao else "bi-diagram-3",
                "integrantes": integrantes,
                "avaliacao": existentes.get(valor),
            })

        historico = (
            AvaliacaoSetor.objects.select_related("avaliador")
            .exclude(periodo=periodo)[:36]
        )
        return render(request, self.template_name, {
            "periodo": periodo,
            "periodo_campo": periodo.strftime("%Y-%m"),
            "linhas": linhas,
            "historico": historico,
            "avaliados": len(existentes),
            "total_setores": len(AvaliacaoSetor.Setor.choices),
        })

    def acao_save(self, request):
        setor = (request.POST.get("setor") or "").strip()
        if setor not in AvaliacaoSetor.Setor.values:
            raise ErroDeFormulario("Escolha um setor válido.")
        periodo = self._periodo(request.POST.get("periodo"))
        try:
            nota = int(request.POST.get("nota") or 0)
        except (TypeError, ValueError):
            nota = 0
        if nota not in range(1, 6):
            raise ErroDeFormulario("A nota precisa estar entre 1 e 5.")

        avaliacao, criada = AvaliacaoSetor.objects.update_or_create(
            setor=setor,
            periodo=periodo,
            defaults={
                "nota": nota,
                "observacao": texto(request, "observacao"),
                "avaliador": request.user,
            },
        )
        verbo = "registrada" if criada else "atualizada"
        return self.sucesso(
            request,
            f"Avaliação de {avaliacao.get_setor_display()} {verbo} com nota {nota}.",
        )
