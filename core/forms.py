from django import forms
from django.contrib.auth.models import User
from .models import ClientePerfil

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
