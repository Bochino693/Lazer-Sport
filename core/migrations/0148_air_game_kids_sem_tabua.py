"""O Air Game Kids Alienígenas sem a tábua azul embaixo das cabeceiras.

Na folha de adesivos, as cabeceiras vêm com um retângulo azul liso embaixo da
arte. Essa tábua não existe na mesa: a cabeceira é só a faixa da arte, logo
abaixo do tampo, e embaixo dela a mesa é aberta entre os pés das laterais. O
recorte tira a faixa (`sem_faixa_lisa`, ferramentas/modelos3d/), e o .glb, as
fotos do cadastro e as fotos das categorias em que a mesa aparece foram
refeitos.

SÓ NO RENDER (o Cloudinary só está lá; no computador e nos testes não faz
nada):
  * a galeria do Air Game Kids Alienígenas, se é a que o cadastro subiu (e não
    fotos postas pelo painel), é trocada pelas vistas do 3D novo;
  * as fotos das categorias que mudaram sobem (o nome do arquivo leva a
    assinatura do conteúdo: as que não mudaram ficam como estão).
Se a subida falhar, o deploy segue, e estes comandos refazem:
    python manage.py cadastrar_variantes_adesivo --so air-game-kids-alienigenas --fotos
    python manage.py atualizar_capas_categorias
"""

from django.db import migrations, transaction

CHAVE = "air-game-kids-alienigenas"
CATEGORIAS = ("espaco-kids-play", "eletronicos", "jogos-de-mesa", "competitivos", "famosos", "kids")


def refazer_fotos(apps, schema_editor):
    from django.conf import settings

    if not getattr(settings, "IS_RENDER", False):
        return
    from core.cadastro_modelos import CADASTROS, cadastrar, fotos_do_cadastro
    from core.categorias_capas import atualizar_capas

    Brinquedos = apps.get_model("core", "Brinquedos")
    CategoriasBrinquedos = apps.get_model("core", "CategoriasBrinquedos")
    ImagemBrinquedo = apps.get_model("core", "ImagemBrinquedo")
    dados = CADASTROS[CHAVE]
    brinquedo = Brinquedos.objects.filter(nome_brinquedo=dados["nome"]).first()
    do_cadastro = brinquedo is not None and any(
        fotos_do_cadastro(brinquedo, chave) for chave in (CHAVE, *dados.get("antes", {}))
    )
    if do_cadastro:
        try:
            with transaction.atomic():
                cadastrar(CHAVE, Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, refazer_fotos=True)
        except Exception as erro:  # o deploy segue; o comando refaz depois
            print(f"As fotos do {dados['nome']} não foram refeitas agora ({erro!r}). "
                  f"Rode: python manage.py cadastrar_variantes_adesivo --so {CHAVE} --fotos")
    try:
        atualizar_capas(CategoriasBrinquedos, so=CATEGORIAS)
    except Exception as erro:  # o deploy segue; o comando refaz depois
        print(f"As fotos das categorias não subiram agora ({erro!r}). "
              "Rode: python manage.py atualizar_capas_categorias")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0147_categorias_capas_e_nomes"),
    ]

    operations = [
        migrations.RunPython(refazer_fotos, migrations.RunPython.noop),
    ]
