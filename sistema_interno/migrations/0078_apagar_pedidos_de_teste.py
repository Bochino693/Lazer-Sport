# OS PEDIDOS DE TESTE SAEM DO BANCO -- SÓ DADOS, SÓ NO RENDER.
#
# O pedido do dono (com a tela do /adm): "apague esses pedidos de teste".
# São os pedidos #88 a #97, das contas de teste thiago2 e lazer.sport2
# (valores de R$ 0,01 a R$ 5.049,90, pagos e cancelados). Só eles: o id E
# a conta têm de bater -- um pedido de verdade com o mesmo número em outro
# banco (cópia local, teste) não é tocado, e fora do Render nada roda.
#
# O que vai junto, para não sobrar nada solto:
#   * a venda que o pagamento registrou (core.Venda protege o pedido, então
#     sai antes; a CentralVendas, filha dela, cai junto);
#   * a linha da lista de montagem e as máquinas dela (CASCADE);
#   * as tarefas do RH das máquinas (a ligação é genérica, não cai sozinha).
# As contas dos clientes de teste ficam. Rodar de novo não muda nada.

from django.conf import settings
from django.db import migrations

IDS = tuple(range(88, 98))
CONTAS_DE_TESTE = ("thiago2", "lazer.sport2")


def apagar(apps, schema_editor=None, forcar=False, avisar=print, ids=IDS):
    if not (forcar or getattr(settings, "IS_RENDER", False)):
        return
    Pedido = apps.get_model("core", "Pedido")
    Venda = apps.get_model("core", "Venda")
    Unidade = apps.get_model("sistema_interno", "UnidadeMontagem")
    Tarefa = apps.get_model("rh", "Tarefa")
    ContentType = apps.get_model("contenttypes", "ContentType")

    ids = list(
        Pedido.objects.filter(pk__in=ids, cliente__user__username__in=CONTAS_DE_TESTE)
        .values_list("pk", flat=True)
    )
    if not ids:
        return
    unidades = list(Unidade.objects.filter(producao__pedido_id__in=ids).values_list("pk", flat=True))
    tipo = ContentType.objects.filter(app_label="sistema_interno", model="unidademontagem").first()
    if tipo is not None and unidades:
        Tarefa.objects.filter(content_type_id=tipo.pk, object_id__in=unidades).delete()
    Venda.objects.filter(pedido_id__in=ids).delete()
    Pedido.objects.filter(pk__in=ids).delete()
    avisar(f"Pedidos de teste apagados: {', '.join('#%s' % pk for pk in sorted(ids))}.")


class Migration(migrations.Migration):

    dependencies = [
        # sem dependência nova no core: a cadeia do sistema_interno já passa
        # pelo core com Pedido e Venda (e os testes que voltam o core a uma
        # migração antiga não arrastam esta junto)
        ("sistema_interno", "0077_espaco_esportivo_kids_nao_e_brinquedao"),
        ("rh", "0002_marcacao_imutavel_no_banco"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(apagar, migrations.RunPython.noop),
    ]
