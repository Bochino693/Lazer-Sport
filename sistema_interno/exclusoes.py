"""A última palavra sobre excluir é do superusuário -- e ela deixa rastro.

O PROBLEMA. Cada tela tinha a sua própria regra de exclusão, e todas
diziam "não" para as mesmas coisas: proposta enviada é histórico, O.S.
concluída é histórico, cliente com pedido é histórico. As regras estão
certas para o dia a dia -- ninguém deve poder apagar a linha do tempo
comercial por engano.

Só que elas diziam "não" também para quem responde pela empresa. Quem
cadastrou errado, duplicou um cliente ou testou uma proposta em
produção ficava com o registro errado para sempre, ou tinha de mexer no
banco por fora -- que é exatamente o caminho onde as coisas somem sem
ninguém saber.

A SOLUÇÃO TEM DUAS METADES, E UMA SÓ NÃO SERVE.

A primeira: o superusuário passa por cima de qualquer regra. Não é
exceção espalhada em vinte `if`; é uma pergunta só, feita no mesmo lugar
por todas as telas.

A segunda: quando ele passa por cima, fica registrado. Histórico apagado
em silêncio é pior do que histórico errado -- daqui a seis meses "onde
foi parar a proposta 412?" não pode ser pergunta sem resposta. O rastro
guarda o que era, quem apagou, quando e o motivo escrito na hora.

E há um terceiro caso, que é o que faz uma exclusão "impossível"
realmente acontecer: objeto protegido por outro (`on_delete=PROTECT`).
O aceite eletrônico protege o orçamento, a venda protege o pedido. Para
o superusuário, `remover` desmonta essa corrente -- e diz no rastro o que
levou junto, porque isso é justamente o que ninguém lembraria depois.
"""

from __future__ import annotations

from django.db import transaction
from django.db.models import ProtectedError

from .models import ExclusaoRegistrada
from .utils import ErroDeFormulario


def pode_excluir(user, regra_normal: bool) -> bool:
    """Junta a regra da tela com a palavra final do superusuário.

    `regra_normal` é o que a tela já decidia sozinha. Superusuário
    verdadeiro (não "staff", que é outra coisa) passa por cima.
    """
    return bool(regra_normal) or bool(getattr(user, "is_superuser", False))


def forcando(user, regra_normal: bool) -> bool:
    """A exclusão está acontecendo SÓ porque quem pediu é superusuário?

    É a diferença entre apagar um rascunho e apagar um documento que já
    foi ao cliente. Marca o rastro.
    """
    return bool(getattr(user, "is_superuser", False)) and not bool(regra_normal)


def _protegido_por(erro: ProtectedError) -> list:
    """Os objetos que impediram a exclusão, como lista concreta."""
    return sorted(erro.protected_objects, key=lambda obj: str(obj))


def remover(
    objeto,
    *,
    autor,
    tipo: str,
    identificacao: str,
    resumo: str = "",
    motivo: str = "",
    forcada: bool = False,
):
    """Apaga e registra, na mesma transação.

    Se as duas coisas não acontecerem juntas, o rastro mente: ou aponta
    para algo que continua existindo, ou falta para algo que sumiu.

    Devolve a lista do que foi arrastado junto por proteção -- vazia no
    caso normal. Quem chama usa isso para contar ao usuário o que
    aconteceu de verdade, porque "excluído" esconde que outro registro
    foi embora atrás.
    """
    arrastados = []

    with transaction.atomic():
        try:
            objeto.delete()
        except ProtectedError as erro:
            protegidos = _protegido_por(erro)
            if not getattr(autor, "is_superuser", False):
                nomes = ", ".join(str(item) for item in protegidos[:3])
                raise ErroDeFormulario(
                    "Não dá para excluir: existe registro dependendo deste "
                    f"({nomes}). Remova o dependente primeiro, ou peça a um "
                    "superusuário."
                )
            # Superusuário: desmonta a corrente, e o rastro conta.
            arrastados = [f"{type(item).__name__}: {item}" for item in protegidos]
            for item in protegidos:
                item.delete()
            objeto.delete()

        if arrastados:
            resumo = (
                (resumo + "\n" if resumo else "")
                + "Removidos junto por dependência: "
                + "; ".join(arrastados)
            )

        ExclusaoRegistrada.objects.create(
            autor=autor if getattr(autor, "pk", None) else None,
            autor_nome=(
                getattr(autor, "get_full_name", lambda: "")() or
                getattr(autor, "username", "") or "desconhecido"
            ),
            tipo=tipo,
            identificacao=identificacao[:200],
            resumo=resumo,
            motivo=(motivo or "")[:240],
            forcada=forcada,
        )

    return arrastados
