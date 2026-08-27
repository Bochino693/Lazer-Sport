"""Dá ao cliente do painel o que faltava para ele sozinho alimentar o mapa.

Só ESQUEMA: colunas novas (logo, link, "aparece no mapa", país, precisão
da coordenada) e os tamanhos de campo que estavam curtos demais. O
transporte das linhas do cadastro do site é a 0021, e a queda da coluna
que ligava os dois é a 0022.

POR QUE TRÊS MIGRAÇÕES, E NÃO UMA. Não separe de volta.

O Postgres adia a checagem das chaves estrangeiras até o fim da
transação, e o Django adia a criação de índice até o fim da migração.
Junte dados e esquema no mesmo arquivo e o `CREATE INDEX` de
`publicar_no_mapa` cai DEPOIS das linhas escritas, na mesma transação:

    cannot CREATE INDEX "sistema_interno_cliente"
    because it has pending trigger events

O mesmo vale para o `ALTER TABLE` que derruba `cliente_mapa`. O SQLite não
adia nada disso, então nem os testes nem o ensaio com dados de verdade
pegaram: quem pegou foi o primeiro `migrate` no servidor. Cada migração
roda na sua própria transação -- é isso que faz os gatilhos dispararem
entre uma e outra.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0108_vitrine_cupons"),
        ("sistema_interno", "0019_colaborador_operacional"),
    ]

    operations = [
        migrations.AddField(
            model_name="cliente",
            name="ativo",
            field=models.BooleanField(
                default=True,
                help_text="Desmarque para arquivar sem apagar o histórico de propostas.",
                verbose_name="Cadastro ativo",
            ),
        ),
        migrations.AddField(
            model_name="cliente",
            name="publicar_no_mapa",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text=(
                    "Põe o alfinete deste cliente no mapa da página inicial. "
                    "Precisa do endereço do estabelecimento com localização."
                ),
                verbose_name="Aparece no mapa do site",
            ),
        ),
        migrations.AddField(
            model_name="cliente",
            name="logo",
            field=models.ImageField(
                blank=True,
                help_text="Aparece no mapa e na faixa de clientes do rodapé do site.",
                null=True,
                upload_to="logo_clientes/",
                verbose_name="Logo do cliente",
            ),
        ),
        migrations.AddField(
            model_name="cliente",
            name="site_cliente",
            field=models.URLField(
                blank=True,
                help_text='Vira o link "Visitar Instagram" no balão do mapa.',
                null=True,
                verbose_name="Instagram ou site",
            ),
        ),
        migrations.AddField(
            model_name="enderecocliente",
            name="pais",
            field=models.CharField(
                default="Brasil",
                help_text=(
                    "Cliente fora do Brasil não tem CEP: preencha cidade, estado e país."
                ),
                max_length=60,
            ),
        ),
        migrations.AddField(
            model_name="enderecocliente",
            name="precisao",
            field=models.CharField(
                blank=True,
                choices=[
                    ("exato", "Endereço exato"),
                    ("rua", "Meio da rua"),
                    ("bairro", "Centro do bairro"),
                    ("cidade", "Centro da cidade"),
                    ("manual", "Informada à mão"),
                ],
                default="",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="enderecocliente",
            name="complemento",
            field=models.CharField(blank=True, default="", max_length=60),
            preserve_default=False,
        ),
        # O número do imóvel cabia em 5 caracteres. "1250-A" não cabe.
        migrations.AlterField(
            model_name="enderecocliente",
            name="numero",
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AlterField(
            model_name="enderecocliente",
            name="cep",
            field=models.CharField(blank=True, max_length=18),
        ),
        migrations.AlterField(
            model_name="enderecocliente",
            name="bairro",
            field=models.CharField(blank=True, max_length=50),
        ),
        # 25 caracteres não cabem "Embu das Artes" com o estado junto, e
        # cortavam nomes reais de município.
        migrations.AlterField(
            model_name="enderecocliente",
            name="cidade",
            field=models.CharField(max_length=60),
        ),
        migrations.AlterField(
            model_name="enderecocliente",
            name="estado",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AlterField(
            model_name="cliente",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("residencial", "Residencial"),
                    ("comercial", "Comercial"),
                    ("buffet", "Buffet parceiro"),
                    ("condominio", "Condomínio"),
                    ("escola", "Escola"),
                    ("orgao", "Órgão público"),
                ],
                db_index=True,
                default="residencial",
                max_length=12,
                verbose_name="Tipo de cadastro",
            ),
        ),
        migrations.AlterField(
            model_name="cliente",
            name="parceiro",
            field=models.ForeignKey(
                blank=True,
                help_text="Buffet que atende este cliente, quando a festa vem por ele.",
                limit_choices_to={"tipo": "buffet"},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="clientes_atendidos",
                to="sistema_interno.cliente",
                verbose_name="Buffet responsável",
            ),
        ),
    ]
