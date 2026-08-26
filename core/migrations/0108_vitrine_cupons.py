from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("core", "0107_recompensacupom_carteirapontos_resgatecupom_and_more")]

    operations = [
        migrations.AlterField(
            model_name="cupom",
            name="cliente",
            field=models.ManyToManyField(
                blank=True,
                help_text="Somente perfis de cliente podem receber cupons exclusivos.",
                related_name="cupons",
                to="core.clienteperfil",
            ),
        ),
        migrations.AddField(
            model_name="cupom",
            name="exibir_na_vitrine",
            field=models.BooleanField(
                default=False,
                help_text="Mostra o código como benefício público no site. Cupons pessoais nunca aparecem para outros clientes.",
                verbose_name="Exibir na área de parceiros",
            ),
        ),
        migrations.AddField(
            model_name="recompensacupom",
            name="exibir_na_vitrine_site",
            field=models.BooleanField(
                default=True,
                help_text="Exibe a recompensa na área de parceiros, com aviso de que o resgate por pontos acontece somente no aplicativo.",
                verbose_name="Mostrar prévia no site",
            ),
        ),
    ]
