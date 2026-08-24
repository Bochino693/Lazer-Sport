# Confirmação assíncrona do pagamento.
#
# Escrita à mão de propósito. O `makemigrations` queria trazer junto uma
# divergência antiga do app (campos de Cupom e a ordem de ImagemBrinquedo)
# que já existia antes desta alteração: misturar as duas coisas faria um
# deploy de pagamento carregar uma mudança de schema não relacionada, que
# pode até já ter sido aplicada à mão no banco. Aqui só entram os dois
# campos novos do Pedido.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0099_imagembrinquedo_tipo"),
    ]

    operations = [
        migrations.AddField(
            model_name="pedido",
            name="confirmacao_notificada",
            field=models.BooleanField(
                default=False,
                db_index=True,
                verbose_name="Confirmação já exibida ao cliente",
            ),
        ),
        migrations.AddField(
            model_name="pedido",
            name="email_confirmacao_enviado",
            field=models.BooleanField(
                default=False,
                verbose_name="E-mail de confirmação enviado",
            ),
        ),
    ]
