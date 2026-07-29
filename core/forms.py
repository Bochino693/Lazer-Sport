from django import forms
from django.contrib.auth.models import User

from .models import (
    ClientePerfil,
    Promocoes,
    Projetos,
    Manutencao,
    Cupom,
    ImagensSite,
    Combos,
)


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        widgets = {
            "first_name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "Nome"}
            ),
            "last_name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "Sobrenome"}
            ),
            "email": forms.EmailInput(
                attrs={"class": "form-input", "placeholder": "Email"}
            ),
        }


class PerfilForm(forms.ModelForm):
    class Meta:
        model = ClientePerfil
        fields = ["nome_completo", "telefone"]


class PromocaoForm(forms.ModelForm):
    class Meta:
        model = Promocoes
        fields = "__all__"
        widgets = {
            "brinquedos": forms.Select(attrs={"id": "id_brinquedos"}),
        }


class ProjetoForm(forms.ModelForm):
    class Meta:
        model = Projetos
        fields = ["titulo", "descricao", "brinquedo_projetado"]


class ManutencaoForm(forms.ModelForm):
    class Meta:
        model = Manutencao
        fields = [
            "brinquedo",
            "brinquedo_nao_listado",
            "brinquedo_descricao_livre",
            "descricao",
            "telefone_contato",
            "cep",
            "endereco",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "estado",
        ]
        widgets = {
            "brinquedo": forms.HiddenInput(),
            "brinquedo_nao_listado": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # A escolha é validada no clean(): pode ser um item do catálogo
        # ou uma identificação manual, mas nunca ficar sem os dois.
        self.fields["brinquedo"].required = False
        self.fields["brinquedo_descricao_livre"].required = False

    def clean(self):
        cleaned_data = super().clean()
        brinquedo = cleaned_data.get("brinquedo")
        nao_listado = cleaned_data.get("brinquedo_nao_listado", False)
        descricao_livre = (
            cleaned_data.get("brinquedo_descricao_livre") or ""
        ).strip()

        if nao_listado:
            cleaned_data["brinquedo"] = None
            cleaned_data["brinquedo_descricao_livre"] = descricao_livre

            if not descricao_livre:
                raise forms.ValidationError(
                    "Descreva o equipamento não catalogado, informando "
                    "nome aproximado, modelo, cor ou detalhes do adesivo."
                )
        else:
            cleaned_data["brinquedo_descricao_livre"] = ""

            if not brinquedo:
                raise forms.ValidationError(
                    "Selecione um equipamento da lista ou marque a opção "
                    "“Não encontrei meu equipamento”."
                )

        return cleaned_data


class CupomForm(forms.ModelForm):
    class Meta:
        model = Cupom
        fields = ["codigo", "desconto_percentual"]


class ImagensSiteForm(forms.ModelForm):
    class Meta:
        model = ImagensSite
        fields = ["imagem"]


class ComboForm(forms.ModelForm):
    class Meta:
        model = Combos
        fields = [
            "descricao",
            "imagem_combo",
            "brinquedos",
            "valor_combo",
        ]
        widgets = {
            "descricao": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Descrição do combo",
                }
            ),
            "imagem_combo": forms.ClearableFileInput(
                attrs={
                    "class": "form-input",
                    "accept": "image/*",
                }
            ),
            "brinquedos": forms.SelectMultiple(
                attrs={
                    "class": "form-select",
                    "size": "10",
                }
            ),
            "valor_combo": forms.NumberInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "0,00",
                    "step": "0.01",
                    "min": "0.01",
                }
            ),
        }
        