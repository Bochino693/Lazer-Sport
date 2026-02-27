from django import forms
from django.contrib.auth.models import User
from .models import ClientePerfil, Promocoes, Projetos, Manutencao

class UserForm(forms.ModelForm):
    telefone = forms.CharField(
        max_length=14,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': '(00)90000-0000'
        })
    )

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
        fields = ['nome_completo']
        widgets = {
            'nome_completo': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Nome completo'}),
        }


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