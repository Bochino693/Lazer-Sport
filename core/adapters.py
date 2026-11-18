"""Os adapters do allauth mudaram-se para o app `contas` (contas/adapters.py).

Este módulo fica só para quem ainda importa de `core.adapters`: as regras de
e-mail, do Google/Apple e do cadastro moram lá, num lugar só. O settings
aponta para `contas.adapters`.
"""

from contas.adapters import (  # noqa: F401
    AccountAdapter,
    SocialAccountAdapter,
    _cadastro_aberto,
    _nome_do_social,
    _slug_username,
    sincronizar_perfil,
)
