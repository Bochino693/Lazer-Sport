"""Quem vê o quê no RH -- com as funções que o painel já tem.

Não existe grupo "RH": as capacidades saem de
`sistema_interno.permissoes.capacidades`, no mesmo lugar das outras telas
(e o menu usa as mesmas chaves):

  * `rh` (Gestão; o superusuário tem todas as funções): vê e edita todas
    as fichas, abre documentos, decide ajustes de ponto, distribui
    tarefas, manda o termo de exclusividade.
  * `rh_pagamento` (Financeiro e Gestão): vê o que precisa para pagar --
    salário, banco e Pix, e o espelho de ponto -- sem editar a ficha.
  * `rh_equipe` (Gestão e Financeiro): a lista da equipe.
  * `rh_proprio` (todo integrante: Produção, Criação, Vendas, Ambulante...):
    só o PRÓPRIO -- o ponto, as tarefas e a ficha básica. Nunca o salário,
    nem o documento, nem o ponto de outra pessoa.

A conferência por OBJETO (esta ficha, este documento, este espelho) mora
aqui, e as views a chamam inclusive em POST e em URL digitada à mão.
"""

from __future__ import annotations

from sistema_interno.permissoes import capacidades

from .models import Colaborador

#: As partes da ficha, e quem vê cada uma.
PARTES_COMPLETAS = frozenset({
    "identidade", "pessoal", "endereco", "contato", "trabalho", "jornada",
    "pagamento", "documentos", "observacoes", "auditoria", "conta", "termo",
})
PARTES_PAGAMENTO = frozenset({"identidade", "trabalho", "pagamento"})
PARTES_PROPRIAS = frozenset({
    "identidade", "pessoal", "endereco", "contato", "trabalho", "jornada", "documentos", "termo",
})


def acesso(user) -> dict:
    return capacidades(user)


def gere(user) -> bool:
    return capacidades(user)["rh"]


def ve_pagamento(user) -> bool:
    return capacidades(user)["rh_pagamento"]


def ve_equipe(user) -> bool:
    return capacidades(user)["rh_equipe"]


def colaborador_de(user):
    """A ficha ligada à conta (ou None). Guardada no objeto da requisição."""
    if not getattr(user, "is_authenticated", False):
        return None
    if not hasattr(user, "_rh_colaborador"):
        user._rh_colaborador = Colaborador.objects.filter(usuario_id=user.pk).first()
    return user._rh_colaborador


def eh_o_proprio(user, colaborador) -> bool:
    return bool(colaborador and colaborador.usuario_id and colaborador.usuario_id == getattr(user, "pk", None))


def partes_da_ficha(user, colaborador) -> frozenset:
    """O que desta ficha a pessoa pode ver. Vazio: nem a ficha."""
    if gere(user):
        return PARTES_COMPLETAS
    partes = set()
    if eh_o_proprio(user, colaborador):
        partes |= PARTES_PROPRIAS
    if ve_pagamento(user):
        partes |= PARTES_PAGAMENTO
    return frozenset(partes)


def pode_abrir_documento(user, documento) -> bool:
    return gere(user) or eh_o_proprio(user, documento.colaborador)


def pode_ver_ponto(user, colaborador) -> bool:
    return gere(user) or ve_pagamento(user) or eh_o_proprio(user, colaborador)
