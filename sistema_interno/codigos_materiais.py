"""Padronização idempotente, sem alterar IDs ou perder códigos anteriores."""
import re
from django.db import transaction
from .models import HistoricoCodigoMaterial, Material, SequenciaMaterial


@transaction.atomic
def padronizar_codigos(*, aplicar=False):
    sequencias = SequenciaMaterial.objects.order_by("pk")
    materiais = Material.objects.select_related("tipo_material").order_by("pk")
    if aplicar:
        sequencias = sequencias.select_for_update()
        # Não trava o lado anulável do outer join no PostgreSQL.
        materiais = materiais.select_for_update(of=("self",))
    materiais = list(materiais)
    contadores = {s.prefixo: s.ultimo for s in sequencias}
    ocupados = {m.codigo_interno.lower() for m in materiais if m.codigo_interno}
    vistos, alteracoes = set(), []
    for material in materiais:
        prefixo = material.tipo_material.prefixo if material.tipo_material_id else "mat"
        codigo = material.codigo_interno
        correto = re.fullmatch(re.escape(prefixo) + r"-[0-9]{4,}", codigo or "")
        if correto and codigo not in vistos and len(codigo.rsplit("-", 1)[1]) <= 12 and int(codigo.rsplit("-", 1)[1]) > 0:
            vistos.add(codigo)
            contadores[prefixo] = max(contadores.get(prefixo, 0), int(codigo.rsplit("-", 1)[1]))
            continue
        while True:
            contadores[prefixo] = contadores.get(prefixo, 0) + 1
            novo = f"{prefixo}-{contadores[prefixo]:04d}"
            if novo not in ocupados:
                break
        ocupados.add(novo)
        vistos.add(novo)
        alteracoes.append({"id": material.pk, "nome": material.nome_material, "anterior": codigo, "novo": novo})
        if aplicar:
            HistoricoCodigoMaterial.objects.create(material=material, anterior=codigo, novo=novo)
            Material.objects.filter(pk=material.pk).update(codigo_interno=novo)
    if aplicar:
        for prefixo, ultimo in contadores.items():
            SequenciaMaterial.objects.update_or_create(prefixo=prefixo, defaults={"ultimo": ultimo})
    return alteracoes
