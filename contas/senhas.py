"""Senha forte para conta nova e para troca de senha.

Vale onde uma senha é ESCOLHIDA: o cadastro do site e do aplicativo, o
painel (Usuários, Equipe e acessos, Minha conta), o /system/ e as telas do
allauth. Quem já tem conta continua entrando com a senha de hoje -- nada
obriga a trocar; a regra vale na próxima vez que ela for trocada.

Os validadores (settings.AUTH_PASSWORD_VALIDATORS):

  * o tamanho mínimo (10, o MinimumLengthValidator do Django);
  * parecida com o usuário, o nome ou o e-mail (o do Django);
  * as 20 mil senhas mais comuns (o do Django) e só números (o do Django);
  * `SenhaPrevisivelValidator`, daqui: as previsíveis em português e as da
    casa -- "senha123", "mudar123", "brasil2026", "lazersport", "flamengo"
    -- com ou sem números e símbolos em volta;
  * `VariedadeValidator`, daqui: pelo menos 5 caracteres diferentes e
    nada de sequência de teclado ou de alfabeto ("1234567890",
    "qwertyuiop", "aaaaaaaaaa").

Sem exigir maiúscula, número e símbolo ao mesmo tempo: regra de
composição faz a pessoa escrever "Senha@123", que cai no primeiro chute.
O que protege é tamanho e não ser previsível.
"""

from __future__ import annotations

import re
import unicodedata

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

#: O miolo (só letras) de senhas que qualquer um tenta primeiro aqui.
PREVISIVEIS = {
    "senha", "minhasenha", "suasenha", "novasenha", "mudar", "mudarsenha", "trocar",
    "trocarsenha", "acesso", "entrar", "login", "admin", "administrador", "adm",
    "usuario", "cliente", "teste", "qwerty", "qwe", "asdf", "abc", "abcd",
    "brasil", "saopaulo", "sp", "flamengo", "corinthians", "palmeiras", "santos",
    "vasco", "gremio", "cruzeiro", "botafogo", "fluminense", "amor", "deus",
    "jesus", "familia", "lazer", "sport", "lazersport", "lazerandsport",
    "lazeresport", "brinquedo", "brinquedos", "fliperama", "maquina",
    "maquinas", "empresa",
}

SEQUENCIAS = (
    "abcdefghijklmnopqrstuvwxyz",
    "0123456789",
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm",
    "1qaz2wsx3edc",
)


def _miolo(senha: str) -> str:
    texto = unicodedata.normalize("NFKD", senha.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", texto)


class SenhaPrevisivelValidator:
    """Recusa as senhas previsíveis em português e as que levam o nome da casa."""

    def validate(self, password, user=None):
        miolo = _miolo(password or "")
        if not miolo or miolo in PREVISIVEIS or any(
            nome in miolo for nome in ("lazersport", "lazerandsport")
        ):
            raise ValidationError(
                "Essa senha é das primeiras que alguém tentaria. Use uma frase "
                "ou uma combinação que só você saiba.",
                code="senha_previsivel",
            )

    def get_help_text(self):
        return "A senha não pode ser previsível (senha123, mudar123, o nome da empresa...)."


class VariedadeValidator:
    """Pelo menos 5 caracteres diferentes, e nada de sequência de teclado."""

    minimo_distintos = 5

    def __init__(self, minimo_distintos=5):
        self.minimo_distintos = minimo_distintos

    def validate(self, password, user=None):
        senha = (password or "").lower()
        if len(set(senha)) < self.minimo_distintos:
            raise ValidationError(
                f"Use pelo menos {self.minimo_distintos} caracteres diferentes na senha.",
                code="senha_repetitiva",
            )
        compacta = re.sub(r"[^a-z0-9]", "", senha)
        for sequencia in SEQUENCIAS:
            for texto in (sequencia, sequencia[::-1]):
                if len(compacta) >= 6 and compacta in texto * 2:
                    raise ValidationError(
                        "A senha não pode ser uma sequência do teclado ou do alfabeto.",
                        code="senha_sequencia",
                    )

    def get_help_text(self):
        return f"Use pelo menos {self.minimo_distintos} caracteres diferentes, sem sequência de teclado."


def validar_senha(senha, usuario=None) -> list[str]:
    """As mensagens de recusa da senha (lista vazia = senha aceita).

    `usuario` pode ser uma conta ainda não gravada: o validador de
    semelhança compara com o usuário, o nome e o e-mail que ela vai ter.
    """
    try:
        validate_password(senha or "", usuario)
    except ValidationError as erro:
        return list(erro.messages)
    return []
