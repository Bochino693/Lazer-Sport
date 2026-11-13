# Transportadoras recomendadas (LEIA-ME-V10, seção 89).
#
# SÓ ESQUEMA: a tabela, as checagens de "só dígitos" no telefone e no
# WhatsApp e o nome único sem diferença de maiúsculas. As transportadoras
# conferidas entram na 0064, em arquivo próprio -- ver tests_migracoes.py.
#
# Gerada pelo Django 5.2.8 em 2026-11-13.

import django.db.models.functions.text
import sistema_interno.transportadoras
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0062_orcamento_prazo_de_producao"),
    ]

    operations = [
        migrations.CreateModel(
            name="Transportadora",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("criacao", models.DateTimeField(auto_now_add=True, null=True)),
                ("atualizado", models.DateTimeField(auto_now=True, null=True)),
                (
                    "nome",
                    models.CharField(
                        help_text="Razão social ou nome completo da marca.",
                        max_length=120,
                    ),
                ),
                (
                    "nome_fantasia",
                    models.CharField(
                        blank=True,
                        help_text="O nome curto que aparece no cartão (ex.: Braspress).",
                        max_length=80,
                    ),
                ),
                (
                    "tipo",
                    models.CharField(
                        choices=[
                            ("nacional", "Nacional"),
                            ("regional", "Regional"),
                            ("mudancas", "Mudanças e cargas especiais"),
                        ],
                        db_index=True,
                        default="regional",
                        max_length=12,
                    ),
                ),
                (
                    "atende_todo_brasil",
                    models.BooleanField(
                        default=False,
                        help_text="Marcado, vale para os 27 estados e a lista abaixo é ignorada.",
                    ),
                ),
                (
                    "estados_atendidos",
                    models.CharField(
                        blank=True,
                        help_text="Siglas separadas por vírgula, na ordem do mapa: BA,PE,SE.",
                        max_length=82,
                        validators=[
                            sistema_interno.transportadoras.validar_lista_de_ufs
                        ],
                    ),
                ),
                ("cidade_sede", models.CharField(blank=True, max_length=80)),
                (
                    "uf_sede",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("AC", "AC · Acre"),
                            ("AL", "AL · Alagoas"),
                            ("AP", "AP · Amapá"),
                            ("AM", "AM · Amazonas"),
                            ("BA", "BA · Bahia"),
                            ("CE", "CE · Ceará"),
                            ("DF", "DF · Distrito Federal"),
                            ("ES", "ES · Espírito Santo"),
                            ("GO", "GO · Goiás"),
                            ("MA", "MA · Maranhão"),
                            ("MT", "MT · Mato Grosso"),
                            ("MS", "MS · Mato Grosso do Sul"),
                            ("MG", "MG · Minas Gerais"),
                            ("PA", "PA · Pará"),
                            ("PB", "PB · Paraíba"),
                            ("PR", "PR · Paraná"),
                            ("PE", "PE · Pernambuco"),
                            ("PI", "PI · Piauí"),
                            ("RN", "RN · Rio Grande do Norte"),
                            ("RS", "RS · Rio Grande do Sul"),
                            ("RJ", "RJ · Rio de Janeiro"),
                            ("RO", "RO · Rondônia"),
                            ("RR", "RR · Roraima"),
                            ("SC", "SC · Santa Catarina"),
                            ("SP", "SP · São Paulo"),
                            ("SE", "SE · Sergipe"),
                            ("TO", "TO · Tocantins"),
                        ],
                        max_length=2,
                    ),
                ),
                (
                    "telefone",
                    models.CharField(
                        blank=True,
                        help_text="Só dígitos: DDD + número, 0800/0300 ou número único (4003...).",
                        max_length=11,
                        validators=[sistema_interno.transportadoras.validar_telefone],
                    ),
                ),
                (
                    "whatsapp",
                    models.CharField(
                        blank=True,
                        help_text="Só dígitos, com DDD e sem o 55.",
                        max_length=11,
                        validators=[sistema_interno.transportadoras.validar_whatsapp],
                    ),
                ),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("site", models.URLField(blank=True, max_length=300)),
                (
                    "instagram",
                    models.CharField(
                        blank=True,
                        help_text="Só o perfil, sem @ (ex.: patrustransportes).",
                        max_length=30,
                        validators=[sistema_interno.transportadoras.validar_instagram],
                    ),
                ),
                (
                    "observacoes",
                    models.TextField(
                        blank=True,
                        help_text="Para que ela serve: carga grande ou frágil, caminhão com plataforma, horários...",
                    ),
                ),
                (
                    "fonte_url",
                    models.URLField(
                        blank=True,
                        help_text="A página onde o contato foi conferido.",
                        max_length=500,
                    ),
                ),
                (
                    "fontes_extras",
                    models.TextField(
                        blank=True,
                        help_text="Outras páginas consultadas, uma por linha (cobertura, Instagram...).",
                    ),
                ),
                ("verificado_em", models.DateField(blank=True, null=True)),
                ("ativo", models.BooleanField(db_index=True, default=True)),
                (
                    "ordem",
                    models.PositiveSmallIntegerField(
                        default=100, help_text="Menor aparece primeiro dentro do tipo."
                    ),
                ),
            ],
            options={
                "verbose_name": "Transportadora",
                "verbose_name_plural": "Transportadoras",
                "ordering": ("ordem", "nome"),
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("telefone__regex", "^[0-9]*$")),
                        name="transportadora_telefone_so_digitos",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("whatsapp__regex", "^[0-9]*$")),
                        name="transportadora_whatsapp_so_digitos",
                    ),
                    models.UniqueConstraint(
                        django.db.models.functions.text.Lower("nome"),
                        name="transportadora_nome_unico",
                        violation_error_message="Já existe uma transportadora com este nome.",
                    ),
                ],
            },
        ),
    ]
