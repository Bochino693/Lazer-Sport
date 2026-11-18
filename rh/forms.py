"""Os formulários do RH: a mesma regra do modelo, com a frase para a tela.

As conferências fortes (CPF, PIS, datas, idade, jornada, Pix) moram no
modelo (`Colaborador.clean`) e valem para qualquer caminho de gravação; o
formulário acrescenta o que é da tela: dinheiro em "1.234,56", os dias da
semana e as especialidades em caixinhas, a conta do painel pelo login, a
mensagem "CPF já cadastrado" em vez do erro de banco.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from sistema_interno.permissoes import NOMES_DOS_GRUPOS
from sistema_interno.validacoes import somente_digitos

from . import arquivos
from .models import (
    DIAS_DA_SEMANA,
    AjustePonto,
    Colaborador,
    DocumentoColaborador,
    Especialidade,
    Setor,
    Tarefa,
    TipoDocumento,
    TipoMarcacao,
)


class CampoDinheiro(forms.CharField):
    """ "1.234,56" (ou "1234.56") -> Decimal. Vazio -> None."""

    def to_python(self, valor):
        valor = (super().to_python(valor) or "").strip().replace("R$", "").replace(" ", "")
        if not valor:
            return None
        if "," in valor:
            valor = valor.replace(".", "").replace(",", ".")
        try:
            numero = Decimal(valor).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            raise forms.ValidationError("Valor inválido: use o formato 1.234,56.")
        if numero < 0 or numero > Decimal("99999999.99"):
            raise forms.ValidationError("Valor fora do limite.")
        return numero


class ColaboradorForm(forms.ModelForm):
    salario = CampoDinheiro(required=False, label="Salário")
    jornada_dias = forms.MultipleChoiceField(
        choices=DIAS_DA_SEMANA, widget=forms.CheckboxSelectMultiple, label="Dias de trabalho",
        error_messages={"required": "Marque ao menos um dia de trabalho."},
    )
    especialidades = forms.MultipleChoiceField(
        choices=Especialidade.choices, widget=forms.CheckboxSelectMultiple, required=False,
        label="Especialidades na produção",
    )
    conta_painel = forms.CharField(
        required=False, max_length=150, label="Conta do painel (login)",
        help_text="O usuário com que a pessoa entra no painel. Vazio: sem conta.",
    )
    # Com máscara na tela ("529.982.247-25"): o limite do campo do modelo
    # (só dígitos) barraria antes de a pontuação sair.
    cpf = forms.CharField(max_length=14, label="CPF")
    pis = forms.CharField(max_length=14, required=False, label="PIS/NIS")
    cep = forms.CharField(max_length=9, label="CEP")
    telefone = forms.CharField(max_length=16, label="Telefone")
    emergencia_telefone = forms.CharField(max_length=16, label="Telefone de emergência")

    class Meta:
        model = Colaborador
        fields = (
            "nome", "cpf", "rg", "rg_orgao", "data_nascimento", "pis", "ctps_numero", "ctps_serie",
            "ctps_uf", "cep", "logradouro", "numero", "complemento", "bairro", "cidade", "uf",
            "telefone", "email", "emergencia_nome", "emergencia_telefone", "emergencia_parentesco",
            "cargo", "setor", "especialidades", "data_admissao", "vinculo", "situacao",
            "data_desligamento", "jornada_inicio", "jornada_fim", "jornada_intervalo_min",
            "jornada_dias", "salario", "banco", "agencia", "conta", "tipo_conta", "pix_tipo",
            "pix_chave", "observacoes",
        )
        widgets = {
            "data_nascimento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "data_admissao": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "data_desligamento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "jornada_inicio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "jornada_fim": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        # Os de escolha viram chips de rádio na tela (nunca <select>).
        for nome in ("setor", "vinculo", "situacao", "tipo_conta", "pix_tipo"):
            campo = self.fields[nome]
            campo.widget = forms.RadioSelect(choices=[c for c in campo.choices if c[0] != ""])
        for nome in ("tipo_conta", "pix_tipo"):
            self.fields[nome].required = False
        instancia = self.instance
        if instancia and instancia.pk:
            self.initial["jornada_dias"] = list(instancia.jornada_dias or "")
            self.initial["especialidades"] = list(instancia.especialidades or [])
            self.initial["conta_painel"] = instancia.usuario.get_username() if instancia.usuario_id else ""
            if instancia.salario is not None:
                self.initial["salario"] = f"{instancia.salario:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            self.initial.setdefault("jornada_dias", list("12345"))
            self.initial.setdefault("situacao", "ativo")
        for nome, campo in self.fields.items():
            if not isinstance(campo.widget, (forms.RadioSelect, forms.CheckboxSelectMultiple)):
                campo.widget.attrs.setdefault("class", "form-control")
        mascaras = {"cpf": "documento", "cep": "cep", "telefone": "telefone",
                    "emergencia_telefone": "telefone", "salario": "moeda"}
        for nome, mascara in mascaras.items():
            self.fields[nome].widget.attrs["data-mascara"] = mascara
        for nome in ("cpf", "pis", "cep", "telefone", "emergencia_telefone", "jornada_intervalo_min"):
            self.fields[nome].widget.attrs["inputmode"] = "numeric"
        self.fields["salario"].widget.attrs["inputmode"] = "decimal"
        self.fields["uf"].widget.attrs.update({"list": "rhUfs", "maxlength": "2", "autocomplete": "off"})
        self.fields["ctps_uf"].widget.attrs.update({"list": "rhUfs", "maxlength": "2", "autocomplete": "off"})
        self.fields["banco"].widget.attrs.update({"list": "rhBancos", "autocomplete": "off"})
        self.fields["conta_painel"].widget.attrs.update({"list": "rhContas", "autocomplete": "off"})
        self.fields["data_admissao"].widget.attrs["max"] = timezone.localdate().isoformat()
        self.fields["data_nascimento"].widget.attrs["max"] = timezone.localdate().isoformat()

    # ---------------- campos ----------------
    def clean_cpf(self):
        cpf = somente_digitos(self.cleaned_data.get("cpf"))
        repetido = Colaborador.objects.filter(cpf=cpf).exclude(pk=self.instance.pk)
        if cpf and repetido.exists():
            raise forms.ValidationError("Já existe uma ficha com este CPF.")
        return cpf

    def clean_pis(self):
        pis = somente_digitos(self.cleaned_data.get("pis")) or None
        if pis and Colaborador.objects.filter(pis=pis).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Já existe uma ficha com este PIS/NIS.")
        return pis

    def clean_cep(self):
        return somente_digitos(self.cleaned_data.get("cep"))

    def clean_telefone(self):
        return somente_digitos(self.cleaned_data.get("telefone"))

    def clean_emergencia_telefone(self):
        return somente_digitos(self.cleaned_data.get("emergencia_telefone"))

    def clean_uf(self):
        return (self.cleaned_data.get("uf") or "").strip().upper()

    def clean_ctps_uf(self):
        return (self.cleaned_data.get("ctps_uf") or "").strip().upper()

    def clean_jornada_dias(self):
        return "".join(sorted(set(self.cleaned_data.get("jornada_dias") or [])))

    def clean_conta_painel(self):
        login = (self.cleaned_data.get("conta_painel") or "").strip()
        if not login:
            return None
        Usuario = get_user_model()
        conta = (
            Usuario.objects.filter(Q(username__iexact=login) | Q(email__iexact=login))
            .filter(Q(is_superuser=True) | Q(groups__name__in=NOMES_DOS_GRUPOS))
            .filter(is_active=True).distinct().first()
        )
        if conta is None:
            raise forms.ValidationError(
                "Nenhuma conta ativa da equipe com esse login. Crie a conta em "
                "Administração › Equipe e acessos e dê a ela a função do setor."
            )
        outra = Colaborador.objects.filter(usuario=conta).exclude(pk=self.instance.pk).first()
        if outra:
            raise forms.ValidationError(f"Essa conta já está ligada à ficha de {outra.nome}.")
        return conta

    def clean(self):
        dados = super().clean()
        if dados.get("setor") != Setor.PRODUCAO:
            dados["especialidades"] = []
        return dados

    def save(self, commit=True):
        colaborador = super().save(commit=False)
        colaborador.especialidades = list(self.cleaned_data.get("especialidades") or [])
        colaborador.jornada_dias = self.cleaned_data.get("jornada_dias") or ""
        colaborador.usuario = self.cleaned_data.get("conta_painel")
        if not colaborador.pk and getattr(self.usuario, "is_authenticated", False):
            colaborador.criado_por = self.usuario
        if commit:
            colaborador.save()
        return colaborador


class DocumentoForm(forms.Form):
    tipo = forms.ChoiceField(choices=TipoDocumento.choices, widget=forms.RadioSelect, label="Tipo")
    descricao = forms.CharField(required=False, max_length=120, label="Descrição")
    emissao = forms.DateField(required=False, label="Emissão", widget=forms.DateInput(attrs={"type": "date"}))
    validade = forms.DateField(required=False, label="Validade", widget=forms.DateInput(attrs={"type": "date"}))
    arquivo = forms.FileField(label="Arquivo", widget=forms.ClearableFileInput(attrs={"accept": arquivos.ACEITOS_NO_CAMPO}))

    def __init__(self, *args, colaborador=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.colaborador = colaborador
        # O termo assinado entra sozinho, pela assinatura: não se envia à mão.
        self.fields["tipo"].choices = [c for c in TipoDocumento.choices if c[0] != TipoDocumento.TERMO]
        for nome in ("descricao", "emissao", "validade", "arquivo"):
            self.fields[nome].widget.attrs.setdefault("class", "form-control")
        self.fields["emissao"].widget.attrs["max"] = timezone.localdate().isoformat()
        self.conferido = None

    def clean_arquivo(self):
        try:
            self.conferido = arquivos.conferir(self.cleaned_data.get("arquivo"))
        except forms.ValidationError:
            raise
        except Exception as erro:  # noqa: BLE001
            raise forms.ValidationError("Não foi possível ler o arquivo.") from erro
        return self.cleaned_data.get("arquivo")

    def clean(self):
        dados = super().clean()
        provisorio = DocumentoColaborador(
            colaborador=self.colaborador, tipo=dados.get("tipo") or "",
            descricao=dados.get("descricao") or "", emissao=dados.get("emissao"),
            validade=dados.get("validade"),
        )
        try:
            provisorio.clean()
        except forms.ValidationError as erro:
            for campo, mensagens in erro.message_dict.items():
                for mensagem in mensagens:
                    self.add_error(campo if campo in self.fields else None, mensagem)
        return dados


class AjusteForm(forms.Form):
    tipo = forms.ChoiceField(choices=AjustePonto.Tipo.choices, widget=forms.RadioSelect)
    data = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    hora = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"type": "time"}))
    tipo_marcacao = forms.ChoiceField(choices=TipoMarcacao.choices, required=False, widget=forms.RadioSelect)
    marcacao = forms.IntegerField(required=False, widget=forms.HiddenInput)
    motivo_abono = forms.ChoiceField(choices=AjustePonto.Motivo.choices, required=False, widget=forms.RadioSelect)
    justificativa = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={"rows": 3}))

    def montar(self, colaborador, usuario):
        """O ajuste, conferido pelo modelo (levanta ValidationError)."""
        dados = self.cleaned_data
        ajuste = AjustePonto(
            colaborador=colaborador,
            tipo=dados["tipo"],
            data=dados["data"],
            hora=dados.get("hora") if dados["tipo"] == AjustePonto.Tipo.INCLUIR else None,
            tipo_marcacao=dados.get("tipo_marcacao") or "" if dados["tipo"] == AjustePonto.Tipo.INCLUIR else "",
            marcacao_id=dados.get("marcacao") if dados["tipo"] == AjustePonto.Tipo.DESCONSIDERAR else None,
            motivo_abono=dados.get("motivo_abono") or "" if dados["tipo"] == AjustePonto.Tipo.ABONO else "",
            justificativa=re.sub(r"\s+", " ", dados["justificativa"]).strip(),
            solicitado_por=usuario,
        )
        ajuste.full_clean()
        return ajuste


class TarefaForm(forms.ModelForm):
    class Meta:
        model = Tarefa
        fields = ("titulo", "descricao", "prazo", "prioridade", "colaborador", "setor", "etapa")
        widgets = {
            "prazo": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "descricao": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["prioridade"].widget = forms.RadioSelect(choices=Tarefa.Prioridade.choices)
        self.fields["setor"].widget = forms.RadioSelect(choices=[("", "Nenhum")] + list(Setor.choices))
        self.fields["setor"].required = False
        self.fields["colaborador"].queryset = Colaborador.objects.exclude(situacao="desligado").order_by("nome")
        self.fields["colaborador"].widget = forms.HiddenInput()
        self.fields["etapa"].widget.attrs.update({"list": "rhEtapas", "autocomplete": "off"})
        for nome in ("titulo", "descricao", "prazo", "etapa"):
            self.fields[nome].widget.attrs.setdefault("class", "form-control")
