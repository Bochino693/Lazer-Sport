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

from django.contrib.auth import authenticate
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
        valor = valor.strip().lower()
        if User.objects.filter(email__iexact=valor).exists():
            raise serializers.ValidationError(
                "Já existe uma conta com este e-mail."
            )
        return valor

    @transaction.atomic
    def create(self, dados):
        # O username vira o próprio e-mail: um campo a menos pro
        # cliente digitar, e o allauth já aceita login por e-mail.
        user = User.objects.create_user(
            username=dados["email"],
            email=dados["email"],
            password=dados["senha"],
        )
        # first_name ajuda o admin a exibir algo legível
        primeiro = dados["nome_completo"].split(" ")[0]
        user.first_name = primeiro[:30]
        user.save(update_fields=["first_name"])

        ClientePerfil.objects.create(
            user=user,
            nome_completo=dados["nome_completo"],
            telefone=dados["telefone"],
        )
        return user


# ============================================================
# VIEWS
# ============================================================

def _resposta_com_token(user):
    token, _ = Token.objects.get_or_create(user=user)
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

        user = authenticate(request, username=login, password=senha)

        # Se falhou e parece e-mail, tenta achar o username correspondente.
        if user is None and "@" in login:
            achado = (
                User.objects
                .filter(email__iexact=login)
                .only("username")
                .first()
            )
            if achado:
                user = authenticate(
                    request,
                    username=achado.username,
                    password=senha,
                )

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
        serializer = RegistroSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

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