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
        exclude = ['usuario']
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

    def save(self, commit=True, usuario=None):
        manutencao = super().save(commit=False)

        if usuario:
            manutencao.usuario = usuario

        if commit:
            manutencao.save()

        return manutencao
