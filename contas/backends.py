"""O freio do login vale até para quem chama authenticate() direto.

É o PRIMEIRO da lista AUTHENTICATION_BACKENDS. Ele nunca autentica
ninguém: só confere se a conta (ou o IP) está pausada pelo freio
(contas/freio.py) e, se estiver, levanta PermissionDenied -- o Django
para ali, não pergunta aos outros backends e devolve None. Assim o
/accounts/login/ do allauth, o /system/ e qualquer tela futura respeitam
a mesma pausa que o /login/ do site, sem precisar lembrar de chamar nada.
"""

from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import PermissionDenied

from . import freio


class FreioDeLoginBackend:
    def authenticate(self, request, username=None, password=None, **credenciais):
        if request is None or not freio.ativo():
            return None
        login = username or credenciais.get("email") or credenciais.get("login") or ""
        if login and freio.segundos_de_bloqueio(request, login):
            raise PermissionDenied("login pausado pelo freio de tentativas")
        return None

    def get_user(self, user_id):
        # Sendo o primeiro da lista, é ele que o `force_login` (e quem loga
        # sem dizer o backend) grava na sessão: a conta é lida como no
        # ModelBackend, que só devolve conta ativa.
        return ModelBackend().get_user(user_id)
