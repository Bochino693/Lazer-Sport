"""As capas novas dos kits eletrônicos (LEIA-ME-V10, seção 107). SÓ DADOS.

O dono: "tire o fundo com zoom do jogo, e ponha a tela de televisão para
demonstrar, esses 3 jogos são tela vertical" e "não coloque itens
fictícios". A arte nova (ferramentas/kits/artes.html) é a TV em pé com a
tela de VERDADE do nosso jogo, o título e a lista do que vem no kit; os itens
entram com foto real quando o dono mandar as fotos.

O topo e o pé da arte ficam livres: no card do site moram ali o selo "KIT",
os botões de curtir/favoritar e o selo "Sob consulta / À venda".

SÓ NO RENDER (o Cloudinary só está configurado lá): sobe a arte de
core/static/site/kits/<chave>.webp e troca a capa do produto-kit
(`imagem_brinquedo`) e a frente da galeria do adesivo padrão (tipo
"perfil"); a categoria "Kits eletrônicos" que usava a capa de antes passa a
usar a nova. Nome curto (o ImageField guarda até 100 caracteres), cada kit
no seu ponto de salvamento (no PostgreSQL um erro aborta a transação
inteira) e IDEMPOTENTE: a capa que já tem a assinatura do arquivo não sobe
de novo. Se algo falhar, o deploy segue e o aviso diz o que houve.
"""

import hashlib
from pathlib import Path

from django.db import migrations, transaction

#: (nome do produto-kit, chave do arquivo da arte)
KITS = (
    ("Kit Boliche Virtual", "kit-boliche-virtual"),
    ("Kit Strike Kids", "kit-strike-kids"),
    ("Kit Lazer Shot", "kit-lazer-shot"),
)
PASTA = Path(__file__).resolve().parent.parent / "static" / "site" / "kits"
LIMITE_DO_NOME = 100
NOME_DA_CATEGORIA = "Kits eletrônicos"


def _assinatura(caminho):
    return hashlib.sha1(caminho.read_bytes()).hexdigest()[:10]


def trocar(apps, schema_editor=None, avisar=print, forcar=False):
    """Troca as capas dos kits pelas artes do repositório. `forcar` liga fora do Render (testes)."""
    from django.conf import settings
    from django.core.files import File

    if not (forcar or getattr(settings, "IS_RENDER", False)):
        return {"trocados": [], "fora_do_render": True}

    Brinquedos = apps.get_model("core", "Brinquedos")
    Imagem = apps.get_model("core", "ImagemBrinquedo")
    Categoria = apps.get_model("core", "CategoriasBrinquedos")
    resultado = {"trocados": [], "ja_estavam": [], "falhas": []}

    for nome, chave in KITS:
        arquivo = PASTA / f"{chave}.webp"
        kit = Brinquedos.objects.filter(eh_kit=True, nome_brinquedo=nome).first()
        if kit is None or not arquivo.exists():
            continue
        marca = _assinatura(arquivo)
        if marca in (kit.imagem_brinquedo.name or ""):
            resultado["ja_estavam"].append(nome)
            continue
        capa_antiga = kit.imagem_brinquedo.name or ""
        try:
            with transaction.atomic():
                frente = (
                    Imagem.objects.filter(brinquedo_id=kit.pk, tipo="perfil", variante_id=kit.adesivo_padrao_id).first()
                    or Imagem(brinquedo_id=kit.pk, tipo="perfil", variante_id=kit.adesivo_padrao_id, ordem=1)
                )
                with open(arquivo, "rb") as origem:
                    frente.imagem.save(f"{chave}-{marca}.webp", File(origem), save=False)
                novo = frente.imagem.name or ""
                if not novo or len(novo) > LIMITE_DO_NOME:
                    raise ValueError(f"nome do arquivo inválido ({len(novo)} caracteres): {novo!r}")
                frente.fundo = "com"
                frente.texto_alternativo = nome[:180]
                frente.save()
                Brinquedos.objects.filter(pk=kit.pk).update(imagem_brinquedo=novo)
                if capa_antiga:
                    Categoria.objects.filter(nome_categoria=NOME_DA_CATEGORIA, imagem_categoria=capa_antiga).update(
                        imagem_categoria=novo
                    )
            resultado["trocados"].append(nome)
            avisar(f"{nome}: capa nova ({novo})")
        except Exception as erro:  # noqa: BLE001 -- o deploy segue; dá para refazer pelo painel
            resultado["falhas"].append(nome)
            avisar(f"{nome}: a capa nova não subiu agora ({erro!r})")

    try:
        from django.core.cache import cache

        cache.clear()
    except Exception:  # noqa: BLE001
        pass
    return resultado


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0213_kit_vira_produto_fim"),
    ]

    operations = [
        migrations.RunPython(trocar, migrations.RunPython.noop),
    ]
