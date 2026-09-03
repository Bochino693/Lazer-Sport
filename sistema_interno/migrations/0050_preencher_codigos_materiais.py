"""Dados separados do esquema para evitar pending trigger events no PostgreSQL."""
from django.db import migrations
from django.utils.text import slugify


def preencher_codigos(apps, schema_editor):
    banco = schema_editor.connection.alias
    Tipo = apps.get_model("sistema_interno", "TipoMaterial")
    Material = apps.get_model("sistema_interno", "Material")
    Sequencia = apps.get_model("sistema_interno", "SequenciaMaterial")
    usados = {"mat"}
    prefixos = {None: "mat"}
    for tipo in Tipo.objects.using(banco).order_by("pk").iterator():
        base = slugify(tipo.descricao).replace("-", "")[:3] or "tip"
        prefixo, indice = base, 1
        while prefixo in usados:
            indice += 1
            prefixo = f"{base}{indice}"
        usados.add(prefixo)
        prefixos[tipo.pk] = prefixo
        Tipo.objects.using(banco).filter(pk=tipo.pk).update(prefixo=prefixo)
    codigos = set(Material.objects.using(banco).exclude(codigo_interno="").values_list("codigo_interno", flat=True))
    codigos = {codigo.lower() for codigo in codigos}
    contadores = dict.fromkeys(usados, 0)
    for codigo in codigos:
        prefixo, _, numero = codigo.rpartition("-")
        if prefixo in contadores and len(numero) <= 12 and numero.isascii() and numero.isdigit():
            contadores[prefixo] = max(contadores[prefixo], int(numero))
    for material in Material.objects.using(banco).filter(codigo_interno="").order_by("pk").iterator():
        prefixo = prefixos[material.tipo_material_id]
        contadores[prefixo] += 1
        codigo = f"{prefixo}-{contadores[prefixo]:04d}"
        Material.objects.using(banco).filter(pk=material.pk).update(codigo_interno=codigo)
    Sequencia.objects.using(banco).bulk_create([
        Sequencia(prefixo=prefixo, ultimo=numero) for prefixo, numero in contadores.items()
    ])


class Migration(migrations.Migration):
    dependencies = [("sistema_interno", "0049_materiais_codigos_fotos")]
    operations = [migrations.RunPython(preencher_codigos, migrations.RunPython.noop)]
