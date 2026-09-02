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
