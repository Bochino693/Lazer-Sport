"""As fotos sem fundo saem do site (a 0177; LEIA-ME 72). Só dados, só no Render.

A varredura (core.conferir_fotos.marcar_sem_fundo): cada foto ainda não
conferida é baixada pequena do Cloudinary (240 px); a sem fundo (branca ou
transparente) vira "recorte para artes" (fica guardada, com a posição dela,
e só o painel a mostra, para baixar); a capa sem fundo dá lugar à primeira
foto com fundo do adesivo padrão (a de antes fica guardada em
`capa_sem_fundo`). Nunca apaga nada; não toca a capa em cena nem as
máquinas da Black Friday. A foto que a rede não trouxe fica para a próxima
(com aviso); o prazo é de 4 minutos, e o resto continua com o comando:
    python manage.py fotos_sem_fundo [--simular]
Rodar de novo não muda o que já foi conferido. A volta põe as capas de antes
e devolve as fotos marcadas por ela.
"""

from django.db import migrations


def marcar(apps, schema_editor):
    from django.conf import settings

    if not getattr(settings, "IS_RENDER", False):
        return
    from core import conferir_fotos

    try:
        resumo = conferir_fotos.marcar_sem_fundo(
            apps.get_model("core", "Brinquedos"), apps.get_model("core", "ImagemBrinquedo"), prazo=240)
    except Exception as erro:  # o deploy segue; o comando refaz depois
        print(f"As fotos sem fundo não foram conferidas agora ({erro!r}). Rode: python manage.py fotos_sem_fundo")
        return
    print(f"Fotos sem fundo: {resumo['conferidas']} conferidas, {len(resumo['marcadas'])} viraram recorte para artes, "
          f"{len(resumo['capas'])} capas trocadas, {len(resumo['falhas'])} ficaram para depois.")
    if resumo["sem_foto_com_fundo"]:
        print("Precisam de foto com fundo: " + ", ".join(resumo["sem_foto_com_fundo"]))


def desmarcar(apps, schema_editor):
    from core import conferir_fotos

    conferir_fotos.desmarcar_sem_fundo(apps.get_model("core", "Brinquedos"), apps.get_model("core", "ImagemBrinquedo"))


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0176_conferencia_do_fundo"),
    ]

    operations = [
        migrations.RunPython(marcar, desmarcar),
    ]
