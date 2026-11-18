"""O kit eletrônico vira produto (LEIA-ME-V10, seção 107). 2/3: SÓ DADOS.

O dono: "vc criou outra sub section e nem sei se outro objeto, mas eles
devem estar junto com os produtos". Cada peça-kit (PecasReposicao com
`eh_kit`) vira um produto (Brinquedos com `eh_kit`), igual às máquinas:

  * NOME, DESCRIÇÃO, PREÇO E PARCELAS: os da peça (preço vazio continua
    "Sob consulta"); `ativo` e o ajuste das curtidas também. Vai para a loja
    (`exibir_na_loja`), como ia a peça -- o carrinho só aceita com preço;
  * A MÁQUINA do kit (`maquina`) e, dela, a voltagem, a nota e as
    categorias; e a categoria "Kits eletrônicos" (criada se não existe, com
    a foto do primeiro kit de capa);
  * A FOTO: o produto aponta para o MESMO arquivo que a peça já tinha no
    Cloudinary (nada sobe de novo): a capa (`imagem_brinquedo`) e a frente
    da galeria, no adesivo padrão (todo produto tem um, LEIA-ME 72). Nome
    de arquivo com mais de 100 letras (a coluna) não é copiado;
  * O QUE VEM NO KIT: os itens passam a apontar para o produto;
  * as CURTIDAS E A LISTA DE DESEJOS da peça passam para o produto (são do
    mesmo kit para o cliente), e o item de CARRINHO também;
  * o NÚMERO DA PEÇA fica em `id_kit_antigo`: /kits/<número>/ e
    /pecas/<número>/ levam ao produto (301);
  * A PEÇA DE ANTES: sem nada que aponte para ela (pedido, orçamento, O.S.,
    item de outro kit), é apagada -- a foto no Cloudinary fica, é do
    produto agora (modelo histórico: nenhum sinal apaga arquivo); com algo
    apontando, fica desligada (fora da vitrine).

Em produção (18/11/2026) são três: as peças 24 (Kit Boliche Virtual), 25
(Kit Strike Kids) e 26 (Kit Lazer Shot), cada uma com 7 itens e 1 foto.

CADA KIT NO SEU PONTO DE SALVAMENTO: no PostgreSQL um erro aborta a
transação inteira. Um kit que falha não leva os outros junto -- mas a
migração termina com o erro (e nada fica gravado), porque a 0213 apaga a
coluna antiga: seguir com um kit pela metade perderia os itens dele.

IDEMPOTENTE: o produto é procurado antes (pelo número da peça e, depois,
pelo nome entre os kits); o que já existe não é tocado -- só os itens, as
curtidas e o carrinho que ainda apontem para a peça seguem para ele. Num
banco sem kit (o dos testes, um novo) nada acontece. O item solto (de uma
peça que deixou de ser kit no painel e que ninguém via) é apagado: a 0213
exige o kit de todo item.

Separada da 0211 e da 0213 (só esquema): sistema_interno/tests_migracoes.py.
DESFAZER não volta os kits a peça (a volta é só do esquema).
"""

import re
import unicodedata
from decimal import Decimal

from django.db import migrations, transaction
from django.db.models import Avg

#: Copiados: a migração não pode depender do código de hoje, que muda.
NOME_DA_CATEGORIA = "Kits eletrônicos"
#: A coluna do arquivo (ImageField) guarda até 100 caracteres.
LIMITE_DO_NOME = 100
#: As posições da galeria do produto, na ordem (a frente é a capa).
POSICOES = ("perfil", "tres_quartos", "lado_direito", "lado_esquerdo", "verso", "de_cima")
#: A posição da foto da peça que tem par na galeria do produto.
POSICAO_DA_PECA = {"frente": "perfil", "lado_direito": "lado_direito", "lado_esquerdo": "lado_esquerdo",
                   "tras": "verso"}


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", texto.lower()).strip()


def _cabe(nome):
    return bool(nome) and len(nome) <= LIMITE_DO_NOME


def _fotos_da_peca(ImagemPeca, peca):
    return [f for f in ImagemPeca.objects.filter(peca_reposicao_id=peca.pk).order_by("ordem", "id") if f.imagem]


def _categoria_dos_kits(apps, capa, avisar):
    """A categoria "Kits eletrônicos" (a que já existe pelo nome, ou nova, com a capa)."""
    Categoria = apps.get_model("core", "CategoriasBrinquedos")
    alvo = _normalizar(NOME_DA_CATEGORIA)
    existente = next((c for c in Categoria.objects.order_by("id") if _normalizar(c.nome_categoria) == alvo), None)
    if existente is not None:
        return existente
    with transaction.atomic():
        # a foto é única entre as categorias: sem capa livre, nasce com um nome
        # de passagem e fica NULL (vazio "" brigaria com outra categoria sem foto)
        livre = _cabe(capa) and not Categoria.objects.filter(imagem_categoria=capa).exists()
        categoria = Categoria.objects.create(
            nome_categoria=NOME_DA_CATEGORIA, ativo=True,
            imagem_categoria=capa if livre else "categorias/kits-eletronicos-sem-foto",
        )
        if not livre:
            Categoria.objects.filter(pk=categoria.pk).update(imagem_categoria=None)
    avisar(f"{NOME_DA_CATEGORIA}: categoria criada" + (" com a foto do primeiro kit" if livre else " (sem foto)"))
    return categoria


def _produto_existente(Brinquedos, peca):
    achado = Brinquedos.objects.filter(eh_kit=True, id_kit_antigo=peca.pk).order_by("id").first()
    if achado is not None:
        return achado
    alvo = _normalizar(peca.nome)
    return next((b for b in Brinquedos.objects.filter(eh_kit=True).order_by("id")
                 if _normalizar(b.nome_brinquedo) == alvo), None)


def _nota_padrao(Brinquedos, maquina):
    """A nota do kit: a da máquina dele; sem máquina, a média do catálogo (o dono muda no painel)."""
    if maquina is not None and maquina.avaliacao is not None:
        return maquina.avaliacao
    media = Brinquedos.objects.filter(ativo=True, eh_kit=False).aggregate(m=Avg("avaliacao"))["m"]
    return Decimal(str(round(float(media), 1))) if media else Decimal("5.0")


def _criar_produto(apps, peca, fotos, categoria):
    Brinquedos = apps.get_model("core", "Brinquedos")
    Variante = apps.get_model("core", "VarianteAdesivo")
    Imagem = apps.get_model("core", "ImagemBrinquedo")

    maquina = Brinquedos.objects.filter(pk=peca.maquina_id).first() if peca.maquina_id else None
    capa = fotos[0].imagem.name if fotos and _cabe(fotos[0].imagem.name) else ""
    produto = Brinquedos.objects.create(
        nome_brinquedo=peca.nome[:150],
        descricao=(peca.descricao_peca or peca.nome)[:999],
        valor_brinquedo=peca.preco_venda,
        parcelas_sem_juros=peca.parcelas_sem_juros,
        avaliacao=_nota_padrao(Brinquedos, maquina),
        voltz=(maquina.voltz if maquina is not None else "") or "",
        exibir_na_loja=True,
        ajuste_curtidas=peca.ajuste_curtidas or 0,
        ativo=peca.ativo,
        eh_kit=True,
        maquina=maquina,
        id_kit_antigo=peca.pk,
        imagem_brinquedo=capa or None,
    )
    # o adesivo padrão (LEIA-ME 72): o `save()` do modelo de hoje cria; o histórico, não
    padrao = Variante.objects.create(brinquedo=produto, nome="Padrão", slug="padrao", ordem=1, padrao=True)
    Brinquedos.objects.filter(pk=produto.pk).update(adesivo_padrao=padrao)

    usadas = set()
    for ordem, foto in enumerate(fotos, start=1):
        nome = foto.imagem.name
        if not _cabe(nome):
            continue
        tipo = "perfil" if not usadas else POSICAO_DA_PECA.get(foto.posicao)
        if tipo is None or tipo in usadas:
            tipo = next((p for p in POSICOES if p not in usadas), None)
        if tipo is None:
            break
        usadas.add(tipo)
        Imagem.objects.create(
            brinquedo=produto, variante=padrao, imagem=nome, tipo=tipo, ordem=ordem,
            texto_alternativo=f"{produto.nome_brinquedo}"[:180],
            # a arte do kit tem fundo de verdade (o recorte das peças a deixou como estava)
            fundo="com" if (foto.recorte_de == nome and not foto.imagem_original) else "",
        )

    produto.categorias_brinquedos.add(categoria)
    if maquina is not None:
        produto.categorias_brinquedos.add(*maquina.categorias_brinquedos.all())
    return produto


def _referencias(apps, peca, tipo_peca):
    """O que ainda aponta para a peça (fora as fotos e os itens dela): [descrição]."""
    Peca = apps.get_model("core", "PecasReposicao")
    achadas = []
    for relacao in Peca._meta.related_objects:
        if relacao.many_to_many or relacao.related_name in ("imagem_peca_reposicao", "componentes_kit"):
            continue
        quantos = relacao.related_model._base_manager.filter(**{relacao.field.name: peca.pk}).count()
        if quantos:
            achadas.append(f"{quantos} {relacao.related_model._meta.verbose_name_plural}")
    if tipo_peca is not None:
        for nome in ("ItemPedido", "ItemCarrinho"):
            Modelo = apps.get_model("core", nome)
            quantos = Modelo._base_manager.filter(content_type=tipo_peca, object_id=peca.pk).count()
            if quantos:
                achadas.append(f"{quantos} {Modelo._meta.verbose_name_plural}")
    return achadas


def _converter_um(apps, peca, categoria, avisar):
    Brinquedos = apps.get_model("core", "Brinquedos")
    Peca = apps.get_model("core", "PecasReposicao")
    ImagemPeca = apps.get_model("core", "ImagemPeca")
    Componente = apps.get_model("core", "ComponenteKit")
    Favorito = apps.get_model("core", "Favorito")
    ItemCarrinho = apps.get_model("core", "ItemCarrinho")
    ContentType = apps.get_model("contenttypes", "ContentType")

    produto = _produto_existente(Brinquedos, peca)
    novo = produto is None
    if novo:
        produto = _criar_produto(apps, peca, _fotos_da_peca(ImagemPeca, peca), categoria)
    elif produto.id_kit_antigo is None:
        Brinquedos.objects.filter(pk=produto.pk).update(id_kit_antigo=peca.pk)

    itens = Componente.objects.filter(kit_id=peca.pk).update(kit_produto=produto, kit=None)
    curtidas = Favorito.objects.filter(peca_id=peca.pk).update(peca=None, brinquedo=produto)
    tipo_peca = ContentType.objects.filter(app_label="core", model="pecasreposicao").first()
    carrinhos = 0
    if tipo_peca is not None:
        tipo_produto, _ = ContentType.objects.get_or_create(app_label="core", model="brinquedos")
        carrinhos = ItemCarrinho.objects.filter(content_type=tipo_peca, object_id=peca.pk).update(
            content_type=tipo_produto, object_id=produto.pk)

    referencias = _referencias(apps, peca, tipo_peca)
    if referencias:
        Peca.objects.filter(pk=peca.pk).update(ativo=False)
        destino = "desligada (ainda citada: " + ", ".join(referencias) + ")"
    else:
        Peca.objects.filter(pk=peca.pk).delete()
        destino = "apagada"
    avisar(
        f"{peca.nome} (peça {peca.pk}) -> produto {produto.pk}" + (" (novo)" if novo else " (já existia)")
        + f": {itens} itens, {curtidas} curtidas/desejos, {carrinhos} no carrinho; a peça foi {destino}."
    )
    return produto


def converter(apps, schema_editor=None, avisar=print):
    Peca = apps.get_model("core", "PecasReposicao")
    ImagemPeca = apps.get_model("core", "ImagemPeca")
    Componente = apps.get_model("core", "ComponenteKit")

    kits = list(Peca.objects.filter(eh_kit=True).order_by("id"))
    feitos, falhas = [], []
    if kits:
        capa = next((f.imagem.name for k in kits for f in _fotos_da_peca(ImagemPeca, k)[:1]), "")
        categoria = _categoria_dos_kits(apps, capa, avisar)
        for peca in kits:
            try:
                with transaction.atomic():
                    feitos.append(_converter_um(apps, peca, categoria, avisar).pk)
            except Exception as erro:  # noqa: BLE001 -- os outros kits seguem; o fim decide
                falhas.append(f"{peca.nome} (peça {peca.pk}): {erro!r}")
                avisar(f"{peca.nome}: não deu para converter ({erro!r}).")

    # o item que ficou sem produto (de uma peça que deixou de ser kit) sai: a 0213 exige o kit
    soltos = Componente.objects.filter(kit_produto__isnull=True)
    if soltos.exists():
        avisar(f"{soltos.count()} item(ns) solto(s), de peça que não é mais kit, apagado(s).")
        soltos.delete()

    if falhas:
        raise RuntimeError(
            "Kits que não viraram produto (nada foi gravado; a 0213 apagaria os itens deles): "
            + "; ".join(falhas)
        )

    if feitos:
        try:  # a home, as categorias, a loja e as páginas guardadas passam a mostrar os kits
            from django.core.cache import cache

            cache.clear()
        except Exception:  # noqa: BLE001 -- o deploy segue
            pass
    return feitos


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("core", "0211_kit_vira_produto_inicio"),
    ]

    operations = [
        migrations.RunPython(converter, migrations.RunPython.noop),
    ]
