import re

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import (
    ClientePerfil,
    Promocoes,
    Projetos,
    Manutencao,
    Cupom,
    ImagensSite,
    Combos,
    validar_telefone,
)


# ============================================================
# TELEFONE
# ============================================================

def normalizar_telefone(valor):
    """
    Aceita qualquer coisa que o cliente digitar e devolve no formato que
    o validar_telefone do models.py exige: (11)91234-5678 para celular
    ou (11)1234-5678 para fixo.

    Existe porque a máscara em JS não é garantia de nada: autofill do
    navegador, teclado de celular antigo e número colado do WhatsApp
    chegam aqui como "11912345678" ou "(11) 91234-5678". Sem essa
    normalização o validador recusa números perfeitamente válidos.

    Se não der para reconhecer, devolve o valor original -- assim o
    validador reclama com a mensagem certa em vez de silenciar o erro.
    """
    digitos = re.sub(r"\D", "", valor or "")

    if len(digitos) == 11:
        return f"({digitos[:2]}){digitos[2:7]}-{digitos[7:]}"

    if len(digitos) == 10:
        return f"({digitos[:2]}){digitos[2:6]}-{digitos[6:]}"

    return (valor or "").strip()


# ============================================================
# CONTA DO CLIENTE
# ============================================================

class UserForm(forms.ModelForm):
    def clean_email(self):
        from .identidade_email import validar_email_de_usuario
        from sistema_interno.utils import ErroDeFormulario
        try:
            return validar_email_de_usuario(self.cleaned_data.get("email"), usuario_id=self.instance.pk)
        except ErroDeFormulario as exc:
            raise forms.ValidationError(str(exc)) from exc

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
    """Edição do perfil pela tela /perfil/."""

    class Meta:
        model = ClientePerfil
        fields = ["nome_completo", "telefone"]

    def clean_telefone(self):
        # Roda antes do full_clean do modelo, então o validador do
        # ClientePerfil já recebe o número no formato certo.
        return normalizar_telefone(self.cleaned_data.get("telefone"))


class CadastroForm(forms.Form):
    """
    Cadastro manual (/registrar/).

    Não é ModelForm de propósito: precisa gravar em dois modelos
    (User e ClientePerfil) e conferir senha/confirmação, coisas que um
    ModelForm de User sozinho não cobre.
    """

    first_name = forms.CharField(max_length=150, label="Nome")
    last_name = forms.CharField(max_length=150, label="Sobrenome")
    username = forms.CharField(max_length=150, label="Nome de usuário")
    email = forms.EmailField(label="E-mail")
    # Sem validators aqui de propósito: o Django roda os validators do
    # campo ANTES do clean_telefone, então o validador veria o texto
    # cru. A validação acontece no clean_telefone, já normalizado.
    telefone = forms.CharField(max_length=20, label="Telefone")
    password = forms.CharField(widget=forms.PasswordInput, label="Senha")
    password2 = forms.CharField(
        widget=forms.PasswordInput, label="Confirmar senha"
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Esse nome de usuário já está em uso.")

        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Já existe uma conta com esse e-mail. "
                "Faça login ou entre com Google."
            )

        from .identidade_email import validar_email_de_usuario
        from sistema_interno.utils import ErroDeFormulario
        try:
            return validar_email_de_usuario(email)
        except ErroDeFormulario as exc:
            raise forms.ValidationError(str(exc)) from exc

    def clean_telefone(self):
        telefone = normalizar_telefone(self.cleaned_data.get("telefone"))

        try:
            validar_telefone(telefone)
        except DjangoValidationError as erro:
            # validar_telefone levanta a ValidationError de
            # django.core.exceptions, que é uma classe diferente da
            # forms.ValidationError -- sem a conversão o erro subiria
            # como 500 em vez de aparecer no campo.
            raise forms.ValidationError(erro.messages)

        return telefone

    def clean(self):
        dados = super().clean()

        senha = dados.get("password")
        senha2 = dados.get("password2")

        if senha and senha2 and senha != senha2:
            self.add_error("password2", "As senhas não conferem.")

        if senha and len(senha) < 8:
            self.add_error("password", "Use pelo menos 8 caracteres.")

        return dados

    def salvar(self):
        """
        Cria User + ClientePerfil. Chamado pela RegistrarView dentro de
        transaction.atomic() -- se qualquer passo falhar, nada é gravado.
        """
        dados = self.cleaned_data

        user = User(
            username=dados["username"],
            email=dados["email"],
            first_name=dados["first_name"].strip(),
            last_name=dados["last_name"].strip(),
        )
        user.set_password(dados["password"])
        user.save()  # o signal post_save cria o ClientePerfil

        perfil, _ = ClientePerfil.objects.get_or_create(user=user)
        perfil.telefone = dados["telefone"]
        perfil.nome_completo = f"{user.first_name} {user.last_name}".strip()
        perfil.save(update_fields=["telefone", "nome_completo"])

        # Registra o e-mail na tabela do allauth. Sem isso, quem se
        # cadastra aqui e depois clica em "Entrar com Google" viraria
        # um segundo usuário com o mesmo e-mail (o Django não impõe
        # unicidade em User.email).
        try:
            from allauth.account.models import EmailAddress

            EmailAddress.objects.get_or_create(
                user=user,
                email=user.email,
                defaults={"verified": False, "primary": True},
            )
        except Exception:
            # allauth ausente ou tabela não migrada: o cadastro não
            # pode quebrar por causa disso.
            pass

        return user


class CompletarPerfilForm(forms.ModelForm):
    """
    Um campo só. É a única coisa que quem entra por Google ou Apple
    ainda precisa digitar, porque nenhum provedor OAuth devolve
    telefone.
    """

    class Meta:
        model = ClientePerfil
        fields = ["telefone"]
        widgets = {
            "telefone": forms.TextInput(
                attrs={
                    "id": "telefone",
                    "placeholder": "(11)90000-0000",
                    "inputmode": "numeric",
                    "autocomplete": "tel",
                }
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # O campo é opcional no modelo, mas nesta tela ele é o objetivo.
        self.fields["telefone"].required = True

    def clean_telefone(self):
        return normalizar_telefone(self.cleaned_data.get("telefone"))


# ============================================================
# ADMINISTRAÇÃO
# ============================================================

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