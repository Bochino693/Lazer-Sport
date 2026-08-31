"""Preenche o documento normalizado e o canal do telefone dos clientes.

SEPARADA DE PROPÓSITO. Os campos nasceram na 0029, junto com o aceite
eletrônico; a gravação das linhas estava no MESMO arquivo. No Postgres
isso é a receita do `cannot ALTER TABLE ... because it has pending trigger
events`: escrever linhas deixa gatilhos pendentes, o Django adia índices e
constraints para o fim da migração, e o banco recusa os dois na mesma
transação. O SQLite dos testes não reproduz -- quem reprova a forma é
`tests_migracoes`.

Rodar duas vezes não faz mal: o cálculo só relê o que já está na linha.
Em banco que já passou pela 0029 antiga, isto reescreve os mesmos valores.
"""

import re

from django.db import migrations


def _digito(valores, pesos):
    resto = sum(valor * peso for valor, peso in zip(valores, pesos)) % 11
    return 0 if resto < 2 else 11 - resto


def _documento_valido(valor):
    chave = re.sub(r"[^0-9A-Z]", "", (valor or "").upper())[:14]
    if len(chave) == 11 and chave.isdigit():
        if len(set(chave)) == 1:
            return False
        base = [int(c) for c in chave[:9]]
        d1 = _digito(base, range(10, 1, -1))
        d2 = _digito(base + [d1], range(11, 1, -1))
        return chave[-2:] == f"{d1}{d2}"
    if len(chave) != 14 or not re.fullmatch(r"[0-9A-Z]{12}[0-9]{2}", chave):
        return False
    base = [ord(c) - 48 for c in chave[:12]]
    d1 = _digito(base, (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    d2 = _digito(base + [d1], (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    return chave[-2:] == f"{d1}{d2}"


def preencher_clientes(apps, schema_editor):
    Cliente = apps.get_model("sistema_interno", "Cliente")
    lote = []
    campos = ("documento_chave", "documento_valido", "canal_telefone")

    def descarregar():
        if lote:
            Cliente.objects.bulk_update(lote, campos)
            lote.clear()

    for cliente in Cliente.objects.all().iterator(chunk_size=500):
        cliente.documento_chave = re.sub(
            r"[^0-9A-Z]", "", (cliente.documento or "").upper()
        )[:14]
        cliente.documento_valido = _documento_valido(cliente.documento)
        if cliente.telefone:
            # Compatibilidade: antes todo campo era rotulado WhatsApp e as
            # propostas existentes dependem dessa interpretação.
            cliente.canal_telefone = "whatsapp"
        lote.append(cliente)
        if len(lote) == 500:
            descarregar()
    descarregar()


class Migration(migrations.Migration):

    dependencies = [
        ("sistema_interno", "0031_orcamento_status_validade_idx"),
    ]

    operations = [
        migrations.RunPython(preencher_clientes, migrations.RunPython.noop),
    ]
