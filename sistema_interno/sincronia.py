"""Revisões pequenas, calculadas no banco e limitadas ao acesso do usuário."""
import hashlib
import json
from django.db.models import Count, Max, Q
from core.models import Manutencao
from .models import Orcamento, OrdemServico
from .permissoes import capacidades, limitar_orcamentos


def revisao_modulo(usuario, modulo):
    acesso = capacidades(usuario)
    if not acesso.get(modulo):
        return None
    if modulo == 'orcamentos':
        consulta = limitar_orcamentos(usuario, Orcamento.objects.all())
        atualizado, estados = 'atualizado', Orcamento.Status.values
    elif modulo == 'ordens_servico':
        consulta = OrdemServico.objects.all()
        atualizado, estados = 'atualizado', OrdemServico.Status.values
    elif modulo == 'manutencoes':
        consulta = Manutencao.objects.all()
        atualizado, estados = 'atualizada_em', [s for s, _ in Manutencao.STATUS_CHOICES]
    else:
        return None
    # A distribuição detecta também mudanças de situação por QuerySet.update.
    estado = consulta.aggregate(
        total=Count('pk'), ultima=Max(atualizado), ultimo_id=Max('pk'),
        **{f'estado_{i}': Count('pk', filter=Q(status=s)) for i, s in enumerate(estados)},
    )
    return hashlib.sha256(json.dumps(estado, sort_keys=True, default=str).encode()).hexdigest()[:20]


def revisoes(usuario):
    return {m: r for m in ('orcamentos', 'ordens_servico', 'manutencoes')
            if (r := revisao_modulo(usuario, m)) is not None}


def revisoes_em_cache(usuario):
    """As mesmas revisões, recalculadas só quando alguma coisa muda.

    `revisoes` custa três agregados por chamada, e o painel a chamava a
    cada pulso de cada aba de cada pessoa -- inclusive nos noventa e nove
    pulsos em que nada tinha acontecido. Como as três saem das mesmas
    tabelas que o pulso do sino olha, o pulso é o carimbo natural delas:
    enquanto ele não muda, elas não têm como mudar.

    Mudou qualquer coisa no banco, o pulso muda, e estas são refeitas na
    hora. Nada envelhece por relógio.
    """
    from django.core.cache import cache
    from .pulso import agora as pulso_agora

    carimbo = pulso_agora()
    if not carimbo:
        # Sem pulso (banco fora do ar, tabela ainda não migrada) não se
        # guarda nada: melhor pagar as consultas do que servir revisão
        # velha para a tela decidir que não precisa recarregar.
        return revisoes(usuario)

    chave = f"interno:revisoes:v1:{getattr(usuario, 'pk', 0)}:{carimbo}"
    guardado = cache.get(chave)
    if guardado is None:
        guardado = revisoes(usuario)
        cache.set(chave, guardado, 120)
    return guardado
