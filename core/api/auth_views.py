# core/api/auth_views.py
#
# Autenticação do app por token.
#
# Como funciona: o app manda usuário e senha uma vez, recebe um token,
# e daí em diante manda esse token no cabeçalho de toda requisição:
#
#     Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
#
# O token não expira sozinho -- some quando o usuário faz logout ou
# quando você apaga no admin. Pra e-commerce isso é o comportamento
# desejado: o cliente não quer relogar toda semana.
#
# IMPORTANTE: cada view aqui declara permission_classes explicitamente.
# O DEFAULT_PERMISSION_CLASSES do projeto é AllowAny -- se você criar
# uma view nova e esquecer de declarar, ela nasce aberta pro mundo.

from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import ClientePerfil


# ============================================================
# SERIALIZERS
# ============================================================

class PerfilSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = ClientePerfil
        fields = ["id", "username", "email", "nome_completo", "telefone"]
        read_only_fields = ["id"]


class RegistroSerializer(serializers.Serializer):
    nome_completo = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    telefone = serializers.CharField(max_length=20)
    senha = serializers.CharField(min_length=8, write_only=True)

    def validate_email(self, valor):
        # A regra das contas (contas/emails.py): normalizado, livre em todas
        # as contas (principal e endereços do allauth) e nunca da empresa.
        from contas.emails import EmailIndisponivel, validar_email_de_conta

        try:
            return validar_email_de_conta(valor, obrigatorio=True)
        except EmailIndisponivel as erro:
            if erro.code == "em_uso":
                raise serializers.ValidationError(
                    "Já existe uma conta com este e-mail."
                ) from erro
            raise serializers.ValidationError(erro.messages) from erro

    def validate(self, dados):
        from contas.senhas import validar_senha

        futura = User(
            username=dados.get("email", ""),
            email=dados.get("email", ""),
            first_name=(dados.get("nome_completo") or "").split(" ")[0][:30],
        )
        erros = validar_senha(dados.get("senha"), futura)
        if erros:
            raise serializers.ValidationError({"senha": erros})
        return dados

    @transaction.atomic
    def create(self, dados):
        # O username vira o próprio e-mail: um campo a menos pro
        # cliente digitar, e o allauth já aceita login por e-mail. Se esse
        # usuário já existe (uma conta que trocou de e-mail continua com o
        # antigo como usuário), ganha um sufixo.
        from contas.adapters import username_livre

        username = dados["email"]
        if User.objects.filter(username__iexact=username).exists():
            username = username_livre(dados["email"])
        user = User.objects.create_user(
            username=username,
            email=dados["email"],
            password=dados["senha"],
        )
        # first_name ajuda o admin a exibir algo legível
        primeiro = dados["nome_completo"].split(" ")[0]
        user.first_name = primeiro[:30]
        user.save(update_fields=["first_name"])

        # O signal de User já cria um ClientePerfil vazio. Atualize esse
        # registro em vez de tentar criar outro e violar o OneToOne.
        ClientePerfil.objects.update_or_create(
            user=user,
            defaults={
                "nome_completo": dados["nome_completo"],
                "telefone": dados["telefone"],
            },
        )
        return user


# ============================================================
# VIEWS
# ============================================================

def _resposta_com_token(user):
    token, _ = Token.objects.get_or_create(user=user)

    # O signal de User cria um ClientePerfil vazio, e essa instância fica
    # em cache na relação. O registro grava nome e telefone logo depois,
    # mas por outro caminho — sem limpar o cache, a resposta sairia com os
    # dois campos vazios mesmo com o banco já correto.
    if "perfil" in getattr(user, "_state").fields_cache:
        del user._state.fields_cache["perfil"]

    perfil = getattr(user, "perfil", None)

    return {
        "token": token.key,
        "usuario": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "nome_completo": getattr(perfil, "nome_completo", "") or "",
            "telefone": getattr(perfil, "telefone", "") or "",
            "is_staff": user.is_staff,
        },
    }


class LoginAPI(APIView):
    """POST /api/v1/auth/login/  {"login": "...", "senha": "..."}

    Aceita username OU e-mail no campo `login`, igual ao site
    (ACCOUNT_LOGIN_METHODS = {"username", "email"}).
    """

    permission_classes = [AllowAny]

    def post(self, request):
        login = (request.data.get("login") or "").strip()
        senha = request.data.get("senha") or ""

        if not login or not senha:
            return Response(
                {"detail": "Informe login e senha."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Usuário ou e-mail, uma tentativa só, com o freio de senhas
        # erradas (contas/freio.py): pausado, o app recebe 429 e a hora.
        from contas.freio import autenticar

        tentativa = autenticar(request._request, login, senha, origem="api")
        if tentativa.bloqueada:
            return Response(
                {"detail": tentativa.mensagem, "tente_em_segundos": tentativa.bloqueio},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(tentativa.bloqueio)},
            )
        user = tentativa.usuario

        if user is None:
            # Mensagem genérica de propósito: não confirma se o
            # e-mail existe ou se só a senha está errada.
            return Response(
                {"detail": "Login ou senha inválidos."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"detail": "Esta conta está desativada."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(_resposta_com_token(user))


class RegistroAPI(APIView):
    """POST /api/v1/auth/registro/"""

    permission_classes = [AllowAny]

    def post(self, request):
        # O freio de contas falsas vale para o aplicativo também: contas
        # demais do mesmo IP na janela (core/registro_cadastro.py).
        from core.registro_cadastro import MENSAGEM_LIMITE, limite_de_cadastros_estourado

        if limite_de_cadastros_estourado(request):
            return Response({"detail": MENSAGEM_LIMITE}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        serializer = RegistroSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # O mesmo e-mail de confirmação do site; nunca trava o cadastro.
        from core.views_conta import enviar_confirmacao_de_email

        enviar_confirmacao_de_email(request._request, user)

        return Response(
            _resposta_com_token(user),
            status=status.HTTP_201_CREATED,
        )


class LogoutAPI(APIView):
    """POST /api/v1/auth/logout/ -- invalida o token atual."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PerfilAPI(APIView):
    """GET e PATCH /api/v1/auth/perfil/"""

    permission_classes = [IsAuthenticated]

    def _perfil(self, request):
        perfil, _ = ClientePerfil.objects.get_or_create(
            user=request.user,
            defaults={
                "nome_completo": request.user.get_full_name() or "",
                "telefone": "",
            },
        )
        return perfil

    def get(self, request):
        return Response(PerfilSerializer(self._perfil(request)).data)

    def patch(self, request):
        serializer = PerfilSerializer(
            self._perfil(request),
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
