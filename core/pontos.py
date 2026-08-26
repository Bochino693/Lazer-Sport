"""Pontos, metas e resgate de cupons.

COMO O CLIENTE GANHA
--------------------
* **Curtida** vale 5 pontos, e só existe no aplicativo. É a moeda de
  entrada: um toque, uma recompensa imediata.
* **Metas da lista de desejos** pagam de uma vez ao serem atingidas --
  5 itens valem 30 pontos, e assim por diante. Metas existem porque
  ponto pingado não move ninguém: o que faz voltar é ver a barra perto
  do fim.

DUAS DECISÕES QUE SUSTENTAM O RESTO
-----------------------------------
1. **Curtida desfeita devolve o ponto.** Sem isso, curtir e descurtir em
   sequência seria uma fábrica de pontos, e a loja de cupons viraria
   piada em uma tarde.
2. **Meta cumprida não se perde.** Ela premia ter chegado lá; tirar itens
   da lista depois não apaga o que já foi conquistado -- e evita saldo
   sumindo sem o cliente entender por quê.

O saldo é sempre a soma do extrato (`PontoGanho`). A carteira guarda o
mesmo número para a tela não varrer o extrato e para o resgate poder
travar a linha.
"""

from __future__ import annotations

import secrets
from datetime import timedelta

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import (
    CarteiraPontos,
    Cupom,
    Favorito,
    PontoGanho,
    RecompensaCupom,
    ResgateCupom,
)


# ----------------------------------------------------------------- regras
PONTOS_POR_CURTIDA = 5

#: (quantos itens na lista, quantos pontos) -- cumprida uma vez cada.
METAS_DESEJO = (
    (5, 30),
    (10, 70),
    (25, 200),
)

#: (quantas curtidas, quantos pontos).
METAS_CURTIDA = (
    (10, 40),
    (30, 150),
)

ALFABETO_CODIGO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem I, O, 0 e 1


class ErroDeResgate(Exception):
    """Falha prevista no resgate: vira mensagem para o cliente."""


# ------------------------------------------------------------- utilidades
def _usuario_valido(usuario):
    return bool(usuario) and getattr(usuario, "is_authenticated", False)


def carteira_de(usuario) -> CarteiraPontos:
    carteira, _ = CarteiraPontos.objects.get_or_create(usuario=usuario)
    return carteira


def _recalcular_carteira(usuario) -> CarteiraPontos:
    linhas = PontoGanho.objects.filter(usuario=usuario)

    saldo = linhas.aggregate(total=Sum("pontos"))["total"] or 0
    ganho = (
        linhas.filter(pontos__gt=0).aggregate(total=Sum("pontos"))["total"] or 0
    )

    carteira = carteira_de(usuario)
    carteira.saldo = saldo
    carteira.total_ganho = ganho
    carteira.save(update_fields=["saldo", "total_ganho", "atualizado"])
    return carteira


# ------------------------------------------------------------ sincronismo
def sincronizar(usuario) -> CarteiraPontos | None:
    """Refaz os pontos automáticos a partir do que o cliente marcou.

    Roda depois de curtir, de guardar na lista e do login (quando o que
    estava no aparelho migra para a conta). É idempotente de propósito:
    chamar duas vezes dá o mesmo resultado, então nenhuma tela precisa
    saber se já chamou.

    Mexe apenas nas origens automáticas -- resgate e ajuste manual são
    fatos definitivos e ficam de fora.
    """
    if not _usuario_valido(usuario):
        return None

    favoritos = Favorito.objects.filter(usuario=usuario)
    curtidas = list(
        favoritos.filter(tipo=Favorito.Tipo.CURTIDA).values_list("id", flat=True)
    )
    total_desejos = favoritos.filter(tipo=Favorito.Tipo.DESEJO).count()

    with transaction.atomic():
        _sincronizar_curtidas(usuario, curtidas)
        _pagar_metas(
            usuario,
            PontoGanho.Origem.META_DESEJO,
            METAS_DESEJO,
            total_desejos,
            "itens na lista de desejos",
        )
        _pagar_metas(
            usuario,
            PontoGanho.Origem.META_CURTIDA,
            METAS_CURTIDA,
            len(curtidas),
            "curtidas no aplicativo",
        )

        return _recalcular_carteira(usuario)


def _sincronizar_curtidas(usuario, ids_atuais):
    """Uma linha de ponto por curtida viva. Curtida desfeita perde a linha."""
    chaves_atuais = {f"favorito:{identificador}" for identificador in ids_atuais}

    existentes = set(
        PontoGanho.objects
        .filter(usuario=usuario, origem=PontoGanho.Origem.CURTIDA)
        .values_list("chave", flat=True)
    )

    # Estorno: quem descurtiu devolve o ponto.
    sobrando = existentes - chaves_atuais
    if sobrando:
        PontoGanho.objects.filter(
            usuario=usuario,
            origem=PontoGanho.Origem.CURTIDA,
            chave__in=sobrando,
        ).delete()

    faltando = chaves_atuais - existentes
    if faltando:
        PontoGanho.objects.bulk_create([
            PontoGanho(
                usuario=usuario,
                origem=PontoGanho.Origem.CURTIDA,
                chave=chave,
                pontos=PONTOS_POR_CURTIDA,
                descricao="Curtida no aplicativo",
            )
            for chave in sorted(faltando)
        ])


def _pagar_metas(usuario, origem, metas, alcancado, rotulo):
    """Paga cada degrau alcançado, uma vez só. Nunca estorna."""
    for alvo, premio in metas:
        if alcancado < alvo:
            continue

        PontoGanho.objects.get_or_create(
            usuario=usuario,
            origem=origem,
            chave=f"meta:{alvo}",
            defaults={
                "pontos": premio,
                "descricao": f"Meta de {alvo} {rotulo}",
            },
        )


# ------------------------------------------------------------------ metas
def progresso(usuario, curtidas=None, desejos=None) -> dict:
    """Saldo, metas e o que falta para a próxima.

    Aceita as contagens de fora porque o visitante sem conta também
    precisa ver as metas -- e vê-las com o progresso DELE, contado pelo
    aparelho. Uma barra em "2 de 5" convence a criar conta; um "entre
    para participar" não convence ninguém.
    """
    logado = _usuario_valido(usuario)

    if logado:
        favoritos = Favorito.objects.filter(usuario=usuario)
        curtidas = favoritos.filter(tipo=Favorito.Tipo.CURTIDA).count()
        desejos = favoritos.filter(tipo=Favorito.Tipo.DESEJO).count()
        carteira = carteira_de(usuario)
    else:
        curtidas = curtidas or 0
        desejos = desejos or 0
        carteira = None

    metas = []
    for alvo, premio in METAS_DESEJO:
        metas.append(_meta(
            f"desejo:{alvo}",
            f"Guarde {alvo} produtos na lista de desejos",
            desejos,
            alvo,
            premio,
        ))
    for alvo, premio in METAS_CURTIDA:
        metas.append(_meta(
            f"curtida:{alvo}",
            f"Curta {alvo} produtos no aplicativo",
            curtidas,
            alvo,
            premio,
        ))

    return {
        "saldo": carteira.saldo if carteira else 0,
        "total_ganho": carteira.total_ganho if carteira else 0,
        "curtidas": curtidas,
        "desejos": desejos,
        "pontos_por_curtida": PONTOS_POR_CURTIDA,
        "metas": metas,
        # Quanto o visitante já teria conquistado se estivesse na conta.
        # É esse número que faz valer a pena criar cadastro agora.
        "a_creditar": (
            0 if logado
            else sum(m["premio"] for m in metas if m["concluida"])
            + curtidas * PONTOS_POR_CURTIDA
        ),
        "logado": logado,
    }


def _meta(chave, titulo, alcancado, alvo, premio) -> dict:
    concluida = alcancado >= alvo
    return {
        "chave": chave,
        "titulo": titulo,
        "alvo": alvo,
        "alcancado": min(alcancado, alvo),
        "falta": max(alvo - alcancado, 0),
        "premio": premio,
        "concluida": concluida,
        # Percentual pronto: a barra do aplicativo não precisa calcular.
        "percentual": 100 if concluida else int(alcancado * 100 / alvo),
    }


# ----------------------------------------------------------------- resgate
def _codigo_de_cupom() -> str:
    """Código curto, legível em voz alta e sem letra que se confunde."""
    for _ in range(12):
        codigo = "LS" + "".join(
            secrets.choice(ALFABETO_CODIGO) for _ in range(6)
        )
        if not Cupom.objects.filter(codigo__iexact=codigo).exists():
            return codigo

    raise ErroDeResgate("Não consegui gerar o código do cupom. Tente de novo.")


def resgatar(usuario, recompensa_id) -> ResgateCupom:
    """Troca pontos por um cupom de verdade, válido no carrinho do site.

    Tudo em uma transação, com a carteira travada: dois toques no mesmo
    botão -- que é o que acontece quando a conexão do tablet oscila -- não
    podem gastar o mesmo ponto duas vezes.
    """
    if not _usuario_valido(usuario):
        raise ErroDeResgate("Entre na sua conta para resgatar um cupom.")

    perfil = getattr(usuario, "perfil", None)
    if perfil is None:
        raise ErroDeResgate("Complete seu cadastro antes de resgatar.")

    with transaction.atomic():
        recompensa = (
            RecompensaCupom.objects
            .select_for_update()
            .filter(pk=recompensa_id)
            .first()
        )

        if recompensa is None or not recompensa.ativo:
            raise ErroDeResgate("Esta recompensa não está mais disponível.")

        if recompensa.estoque is not None and recompensa.estoque <= 0:
            raise ErroDeResgate("Esta recompensa acabou por enquanto.")

        carteira = (
            CarteiraPontos.objects
            .select_for_update()
            .filter(usuario=usuario)
            .first()
        )
        if carteira is None:
            carteira = carteira_de(usuario)

        if carteira.saldo < recompensa.custo_pontos:
            faltam = recompensa.custo_pontos - carteira.saldo
            raise ErroDeResgate(
                f"Faltam {faltam} ponto{'s' if faltam > 1 else ''} para "
                f"resgatar {recompensa.nome}."
            )

        expira_em = timezone.now() + timedelta(days=recompensa.validade_dias)

        cupom = Cupom.objects.create(
            codigo=_codigo_de_cupom(),
            desconto_percentual=recompensa.desconto_percentual,
            quantidade_uso=1,
            todos_usuarios=False,   # exclusivo de quem resgatou
            reutilizavel=False,
            data_expiracao=expira_em,
        )
        cupom.cliente.add(perfil)

        resgate = ResgateCupom.objects.create(
            usuario=usuario,
            recompensa=recompensa,
            cupom=cupom,
            pontos_gastos=recompensa.custo_pontos,
            expira_em=expira_em,
        )

        PontoGanho.objects.create(
            usuario=usuario,
            origem=PontoGanho.Origem.RESGATE,
            chave=f"resgate:{resgate.pk}",
            pontos=-recompensa.custo_pontos,
            descricao=f"Resgate: {recompensa.nome}",
        )

        if recompensa.estoque is not None:
            recompensa.estoque -= 1
            recompensa.save(update_fields=["estoque", "atualizado"])

        _recalcular_carteira(usuario)

        return resgate


def meus_cupons(usuario):
    """Cupons que o cliente comprou com pontos, do mais novo ao mais velho."""
    if not _usuario_valido(usuario):
        return ResgateCupom.objects.none()

    return (
        ResgateCupom.objects
        .filter(usuario=usuario)
        .select_related("cupom", "recompensa")
    )


def extrato(usuario, limite=40):
    if not _usuario_valido(usuario):
        return PontoGanho.objects.none()

    return PontoGanho.objects.filter(usuario=usuario)[:limite]
