"""As fotos das categorias com as máquinas de verdade do catálogo, e o fundo com vida.

O cliente pediu: "vc pode por as máquinas reais ao invés de improvisar estas
nas categorias" e "não quero nenhuma máquina fake, você tem os itens nas
categorias, é só pegar e posicionar, além de caprichar mais no fundo, está
muito sem vida". As fotos de core/static/site/categorias/ foram refeitas
(ferramentas/categorias/): em cada uma só há itens reais da categoria -- o
.glb nosso ou a foto do próprio catálogo, recortada e em pé no chão --, e o
lugar ganhou as crianças, os balões, o confete, as luzes acesas e o reflexo
no piso. A da Área Baby fica como estava (a categoria não tem produto).

SÓ NO RENDER (o Cloudinary só está lá; no computador e nos testes não faz
nada): sobem as fotos que mudaram (o nome do arquivo leva a assinatura do
conteúdo). Se a subida falhar, o deploy segue, e
`python manage.py atualizar_capas_categorias` refaz.
"""

from django.db import migrations

from core.categorias_capas import subir_fotos_no_deploy


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0150_basquete_quadrinhos_fotos"),
    ]

    operations = [
        migrations.RunPython(subir_fotos_no_deploy, migrations.RunPython.noop),
    ]
