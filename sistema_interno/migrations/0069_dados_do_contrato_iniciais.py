# OS DADOS DO VENDEDOR NO CONTRATO (LEIA-ME-V10, seção 107).
#
# SÓ DADOS: a linha única da tabela criada na 0068, com os dados PÚBLICOS
# da empresa (os padrões do modelo: nome fantasia, razão social, CNPJ,
# sede e cidade). Os do REPRESENTANTE ficam VAZIOS de propósito -- nome,
# RG e endereço residencial são pessoais e não entram em código nem em
# migração. Enquanto estiverem vazios, o painel avisa e o contrato não
# sai para assinatura.
#
# Separada da 0068 de propósito: gravar linha no mesmo arquivo de um
# CREATE TABLE é o que o PostgreSQL recusa com "pending trigger events"
# (ver tests_migracoes.py). Rodar de novo não duplica; desfazer não apaga
# nada (a linha pode já ter os dados que o dono digitou -- quem a leva
# embora é desfazer a 0068).

from django.db import migrations


def criar_linha(apps, schema_editor):
    DadosContrato = apps.get_model("sistema_interno", "DadosContrato")
    if not DadosContrato.objects.exists():
        DadosContrato.objects.create()


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0068_dados_do_contrato"),
    ]

    operations = [
        migrations.RunPython(criar_linha, migrations.RunPython.noop),
    ]
