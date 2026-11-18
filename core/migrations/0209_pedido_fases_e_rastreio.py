"""As fases do pedido, com data, e o rastreio do envio (LEIA-ME-V10, seção 106).

SÓ ESQUEMA. O dono: "em todos os pedidos devemos ter esse faseamento, para o
cliente conseguir ver tudo certinho até a entrega." Cinco datas (pago, em
preparação, saiu para entrega / pronto para retirada, entregue / retirado,
cancelado), gravadas sozinhas pelo `Pedido.save()` quando a situação muda, e
o envio: transportadora (texto -- o `core` não depende do `sistema_interno`),
código e link de rastreio.

Escrita à mão, com só estes campos: outra frente mexe no `core` ao mesmo
tempo (os kits, 0207 e 0208), e o `makemigrations` poderia trazer mudança
dela para cá. Os pedidos de antes ganham as datas na 0210 (só dados).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0208_kits_iniciais"),
    ]

    operations = [
        migrations.AddField(
            model_name="pedido",
            name="pago_em",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Pago em"),
        ),
        migrations.AddField(
            model_name="pedido",
            name="preparacao_em",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Em preparação desde"),
        ),
        migrations.AddField(
            model_name="pedido",
            name="enviado_em",
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name="Saiu para entrega (ou pronto para retirada) em",
            ),
        ),
        migrations.AddField(
            model_name="pedido",
            name="entregue_em",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Entregue (ou retirado) em"),
        ),
        migrations.AddField(
            model_name="pedido",
            name="cancelado_em",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Cancelado em"),
        ),
        migrations.AddField(
            model_name="pedido",
            name="transportadora_envio",
            field=models.CharField(
                blank=True, default="", max_length=120,
                help_text="Quem leva o pedido (ou “Entrega própria”).",
                verbose_name="Transportadora",
            ),
        ),
        migrations.AddField(
            model_name="pedido",
            name="codigo_rastreio",
            field=models.CharField(blank=True, default="", max_length=60, verbose_name="Código de rastreio"),
        ),
        migrations.AddField(
            model_name="pedido",
            name="link_rastreio",
            field=models.URLField(blank=True, default="", max_length=500, verbose_name="Link de rastreio"),
        ),
    ]
