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

from django import forms
from django.contrib.auth.models import User

class UserForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Nome'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Sobrenome'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Email'}),
        }

class PerfilForm(forms.ModelForm):

    class Meta:
        model = ClientePerfil
        fields = ['nome_completo', 'telefone']

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
            'brinquedo',
            'descricao',
            'telefone_contato',
            'cep',
            'endereco',
            'numero',
            'complemento',
            'bairro',
            'cidade',
            'estado',
        ]
        widgets = {
            'brinquedo': forms.HiddenInput()
        }

# forms.py
from django import forms
from .models import Cupom

class CupomForm(forms.ModelForm):
    class Meta:
        model = Cupom
        fields = ["codigo", "desconto_percentual"]



from .models import ImagensSite


class ImagensSiteForm(forms.ModelForm):
    class Meta:
        model = ImagensSite
        fields = ['imagem']


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
            "descricao": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Descrição do combo",
            }),
            "imagem_combo": forms.ClearableFileInput(attrs={
                "class": "form-input",
                "accept": "image/*",
            }),
            "brinquedos": forms.SelectMultiple(attrs={
                "class": "form-select",
                "size": "10",
            }),
            "valor_combo": forms.NumberInput(attrs={
                "class": "form-input",
                "placeholder": "0,00",
                "step": "0.01",
                "min": "0.01",
            }),
        }
        