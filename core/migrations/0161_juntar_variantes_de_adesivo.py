"""Os pares de adesivos viram um produto só (a 0161; LEIA-ME, seção 72).

O cliente: "os dois devem se tornar o mesmo objeto, como um adesivo
diferente". Cada par (core.variantes.PARES):
  * o Air Game Kids (os astronautas, as fotos dele) é o produto, com o adesivo
    padrão "Astronautas"; o Air Game Kids Alienígenas vira o adesivo
    "Alienígenas" (as fotos e o .glb dele);
  * o Basquete Home (o gabinete azul) é o produto, com o adesivo padrão
    "Azul"; o "Basquete Street Quadrinhos" -- que é o gabinete do Basquete
    Home com a folha em quadrinhos (LEIA-ME 61) -- antes ganha o nome de hoje,
    "Basquete Home Quadrinhos" (com as descrições das fotos), e vira o adesivo
    "Quadrinhos" (as fotos e o .glb dele). O Basquete Street fica sozinho.
A ficha que vira adesivo sai das listas: fica desativada, sem apagar nada
(pedidos, orçamentos e favoritos continuam apontando para ela), e o endereço
dela redireciona para o produto com ?adesivo=<slug>.

O preço do produto que fica não muda (nada da ficha passa para ele); o Air
Game Kids sem preço fica com R$ 6.990,00 (core.variantes.PRECO_SE_VAZIO).

Em todo lugar (só o banco: nada sobe para o Cloudinary). Pode rodar de novo.
Sem o produto no catálogo, aquele par não faz nada. Desfazer:
core.variantes.separar (o nome de hoje fica).

AS FOTOS MAIS VIVAS E OS FUROS DE VERDADE (a segunda operação; LEIA-ME 72).
As capas do catálogo, as capas e as vistas da galeria dos nossos 3D foram
refeitas com o brinquedo mais vivo (ferramentas/categorias/compor.py,
`vivo`: só no brinquedo, o fundo fica como estava); as do Basquete Home, do
Basquete Street e do Air Game Premium, com o recorte novo (o braço vazado, a
rede sem a parede da loja atrás, o chão sem a sombra do estúdio), e as fotos
de Competitivos e Esportivos. SÓ NO RENDER (o Cloudinary só está lá):
  * as capas do catálogo em cena ganham a foto de hoje (a assinatura no nome
    mudou: core/capas_catalogo.py); a capa trocada no painel fica;
  * a galeria de cada um dos nossos 3D que é a que o cadastro subiu é
    refeita, como na 0158 (a mesma função), e sobem as fotos das categorias
    que mudaram.
Se uma subida falhar, o deploy segue e o aviso diz o comando:
    python manage.py capas_em_cena
    python manage.py cadastrar_modelo_3d <chave> --fotos
    python manage.py atualizar_capas_categorias
"""

import importlib

from django.db import migrations


def juntar(apps, schema_editor):
    from core import variantes

    variantes.migrar(apps, schema_editor)


def subir_fotos(apps, schema_editor):
    from core import capas_catalogo

    # as fotos dos nossos 3D e as categorias: a mesma subida da 0158 (os arquivos mudaram de novo)
    importlib.import_module("core.migrations.0158_fotos_no_showroom").refazer(apps, schema_editor)
    capas_catalogo.subir_no_deploy(apps, schema_editor)


def separar(apps, schema_editor):
    from core import variantes

    for (produto, _padrao), _fichas in variantes.PARES:
        variantes.separar(produto, apps.get_model("core", "Brinquedos"), apps.get_model("core", "VarianteAdesivo"))


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0160_variantes_de_adesivo"),
    ]

    operations = [
        migrations.RunPython(juntar, separar),
        migrations.RunPython(subir_fotos, migrations.RunPython.noop),
    ]
