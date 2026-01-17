from django import forms
from django.contrib.auth.models import User
from .models import ClientePerfil, Promocoes, Projetos, Manutencao


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
            'brinquedo', 'descricao', 'telefone_contato', 'cep', 'endereco',
            'numero', 'complemento', 'bairro', 'cidade', 'estado'
        ]
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Descreva o problema'}),
            'telefone_contato': forms.TextInput(attrs={'placeholder': '(00) 00000-0000'}),
            'cep': forms.TextInput(attrs={'placeholder': '00000-000'}),
            'endereco': forms.TextInput(attrs={'placeholder': 'Rua / Avenida'}),
            'numero': forms.TextInput(attrs={'placeholder': 'Número'}),
            'complemento': forms.TextInput(attrs={'placeholder': 'Complemento'}),
            'bairro': forms.TextInput(attrs={'placeholder': 'Bairro'}),
            'cidade': forms.TextInput(attrs={'placeholder': 'Cidade'}),
            'estado': forms.TextInput(attrs={'placeholder': 'UF'}),
        }
