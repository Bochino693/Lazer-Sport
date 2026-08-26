from django.db import migrations, models


NOMES = {
    "producao": "Equipe · Produção",
    "criacao": "Equipe · Criação do site",
    "vendas": "Equipe · Vendas",
    "gestao": "Equipe · Gestão",
}


def criar_funcoes_e_migrar_equipe(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    User = apps.get_model("auth", "User")
    Gerente = apps.get_model("sistema_interno", "Gerente")

    grupos = {
        codigo: Group.objects.get_or_create(name=nome)[0]
        for codigo, nome in NOMES.items()
    }
    gerentes_ativos = set(
        Gerente.objects.filter(ativo=True).values_list("user_id", flat=True)
    )

    # O fluxo antigo também reconhecia ``Gerente.ativo`` mesmo quando o
    # User não estava com is_staff marcado. Esses gestores não podem perder
    # acesso na transição. Os demais usuários staff eram os operadores de
    # produção existentes.
    usuarios_da_equipe = User.objects.filter(is_active=True).filter(
        models.Q(is_staff=True) | models.Q(pk__in=gerentes_ativos)
    )
    for usuario in usuarios_da_equipe:
        if usuario.is_superuser:
            continue
        grupo = grupos["gestao"] if usuario.pk in gerentes_ativos else grupos["producao"]
        usuario.groups.add(grupo)
        if not usuario.is_staff:
            usuario.is_staff = True
            usuario.save(update_fields=["is_staff"])


def remover_funcoes(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=NOMES.values()).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("sistema_interno", "0017_envioorcamento"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(criar_funcoes_e_migrar_equipe, remover_funcoes),
    ]
