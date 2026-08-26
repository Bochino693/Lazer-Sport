from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sistema_interno", "0018_funcoes_equipe"),
    ]

    operations = [
        # A atribuição antiga apontava para auth.User. Ela não representa
        # quem monta fisicamente o produto e é retirada antes de o campo
        # operacional assumir o nome definitivo.
        migrations.RemoveField(
            model_name="ordemproducao",
            name="colaborador",
        ),
        migrations.RenameModel(
            old_name="Montadores",
            new_name="Colaborador",
        ),
        migrations.RenameField(
            model_name="colaborador",
            old_name="nome_montador",
            new_name="nome",
        ),
        migrations.AddField(
            model_name="colaborador",
            name="ativo",
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name="colaborador",
            name="nome",
            field=models.CharField(max_length=90),
        ),
        migrations.AlterModelOptions(
            name="colaborador",
            options={
                "ordering": ("nome",),
                "verbose_name": "Colaborador",
                "verbose_name_plural": "Colaboradores",
            },
        ),
        migrations.RenameField(
            model_name="ordemproducao",
            old_name="montador",
            new_name="colaborador",
        ),
        migrations.AlterField(
            model_name="ordemproducao",
            name="colaborador",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Pessoa que está montando o brinquedo; não é uma conta do sistema."
                ),
                null=True,
                on_delete=models.SET_NULL,
                related_name="ordens",
                to="sistema_interno.colaborador",
            ),
        ),
    ]
