"""O Espaço Esportivo Modelo 1 traz dois círculos do Gol Flash e duas cestas do Swish.

É o que o objeto 3D dele tem desenhado (core/arena.MODELOS_3D). Liga no
cadastro só se as máquinas existirem e a ligação ainda não existir: rodar de
novo não muda nada, e apagar a ligação no painel não faz ela voltar.
"""
import unicodedata

from django.db import migrations


def _normal(texto):
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", texto or "") if not unicodedata.combining(c))
    return " ".join(sem_acento.lower().split())


def ligar(apps, schema_editor):
    Brinquedos = apps.get_model("core", "Brinquedos")
    ComponenteBrinquedo = apps.get_model("core", "ComponenteBrinquedo")
    todos = list(Brinquedos.objects.filter(ativo=True).values_list("pk", "nome_brinquedo"))
    espacos = [pk for pk, nome in todos if "espaco esportivo modelo 1" in _normal(nome)]
    if not espacos:
        return
    for espaco in espacos:
        if ComponenteBrinquedo.objects.filter(conjunto_id=espaco).exists():
            continue  # a lista deste espaço já foi montada (à mão ou antes): não mexe
        for ordem, (trecho, quantidade) in enumerate((("gol flash", 2), ("swish", 2))):
            # o nome mais curto primeiro: "Gol Flash" antes de "Gol Flash — peças"
            itens = [pk for pk, nome in sorted(todos, key=lambda t: len(t[1])) if trecho in _normal(nome) and pk not in espacos]
            if itens:
                ComponenteBrinquedo.objects.create(conjunto_id=espaco, item_id=itens[0], quantidade=quantidade, ordem=ordem)


class Migration(migrations.Migration):
    dependencies = [("core", "0131_brinquedos_que_vem_junto")]
    operations = [migrations.RunPython(ligar, migrations.RunPython.noop)]
