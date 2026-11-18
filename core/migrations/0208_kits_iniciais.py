"""Os três kits eletrônicos iniciais (LEIA-ME, seção 105). SÓ DADOS.

Kit Boliche Virtual, Kit Strike Kids e Kit Lazer Shot, cada um com os seus
itens e ligado à máquina do catálogo com o mesmo nome (sem máquina, o kit
nasce sem ela). SEM PREÇO: o dono põe no painel; até lá o site mostra "Sob
consulta". O item "Cabo HDMI" liga à peça "Cabo HDMI" quando ela existe.

NESTA ÉPOCA O KIT ERA UMA PEÇA MARCADA (PecasReposicao.eh_kit). Desde a
seção 107 ele é um produto (Brinquedos.eh_kit): a 0212 converte o que esta
criou. O código desta migração foi COPIADO para cá (era core/kits.py, que
mudou com o modelo novo): num banco novo com o catálogo, ela cria as peças-kit
como antes e a 0212 as converte, como em produção.

IDEMPOTENTE: o kit é procurado pelo nome antes de ser criado; o que já existe
não é tocado. A foto de capa (as artes de core/static/site/kits/) sobe para o
Cloudinary SÓ NO RENDER; se não subir, o deploy segue.
"""

import hashlib
import re
import unicodedata
from pathlib import Path

from django.db import migrations

PASTA = Path(__file__).resolve().parent.parent / "static" / "site" / "kits"
LIMITE_DO_NOME = 100

#: (nome do kit, nome da máquina, chave da foto, descrição, [(item, detalhe, quantidade)]).
KITS = (
    (
        "Kit Boliche Virtual",
        "Boliche Virtual",
        "kit-boliche-virtual",
        "A parte eletrônica completa do Boliche Virtual, sem a máquina: placa Zero Delay, "
        "TV Box com o jogo Dragon Bowling, chicote, cabo HDMI, fonte, webcam e a barra "
        "com 5 sensores. Para montar a sua própria máquina, trocar a eletrônica de uma que "
        "parou ou instalar tudo na máquina que você já tem. Kit completo e pronto para instalar.",
        (
            ("Placa Zero Delay", "", 1),
            ("TV Box", "Com o jogo Dragon Bowling", 1),
            ("Chicote", "", 1),
            ("Cabo HDMI", "", 1),
            ("Fonte", "", 1),
            ("Webcam", "", 1),
            ("Barra com 5 sensores", "Leem cada jogada da bola na pista", 1),
        ),
    ),
    (
        "Kit Strike Kids",
        "Strike Kids",
        "kit-strike-kids",
        "A parte eletrônica completa do Strike Kids, sem a máquina: TV Box com o jogo Strike "
        "Kids, a barra com 5 sensores de precisão, a câmera que tira a foto do jogador para o "
        "ranking, placa Zero Delay, chicote, cabo HDMI e fonte. Para montar a sua própria "
        "máquina, trocar a eletrônica de uma que parou ou instalar tudo na máquina que você "
        "já tem. Kit completo e pronto para instalar.",
        (
            ("TV Box", "Com o jogo Strike Kids", 1),
            ("Barra com 5 sensores de precisão", "Leem cada jogada da bola na pista", 1),
            ("Câmera", "Tira a foto do jogador para o ranking", 1),
            ("Placa Zero Delay", "", 1),
            ("Chicote", "", 1),
            ("Cabo HDMI", "", 1),
            ("Fonte", "", 1),
        ),
    ),
    (
        "Kit Lazer Shot",
        "Lazer Shot",
        "kit-lazer-shot",
        "A parte eletrônica completa do Lazer Shot, sem a máquina: a arma personalizada "
        "(a pistola de luz feita para a máquina), TV Box com o jogo Lazer Shot, a câmera que "
        "tira a foto do jogador para o ranking, placa Zero Delay, chicote, cabo HDMI e fonte. "
        "Para montar a sua própria máquina, trocar a eletrônica de uma que parou ou instalar "
        "tudo na máquina que você já tem. Kit completo e pronto para instalar.",
        (
            ("Arma personalizada", "Pistola de luz feita para a máquina", 1),
            ("TV Box", "Com o jogo Lazer Shot", 1),
            ("Câmera", "Tira a foto do jogador para o ranking", 1),
            ("Placa Zero Delay", "", 1),
            ("Chicote", "", 1),
            ("Cabo HDMI", "", 1),
            ("Fonte", "", 1),
        ),
    ),
)


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", texto.lower()).strip()


def _pelo_nome(objetos, campo, nome):
    alvo = _normalizar(nome)
    return next((o for o in objetos if _normalizar(getattr(o, campo)) == alvo), None)


def _criar(PecasReposicao, Brinquedos, ComponenteKit, avisar):
    existentes = list(PecasReposicao.objects.only("id", "nome"))
    maquinas = list(Brinquedos.objects.order_by("-ativo", "id").only("id", "nome_brinquedo", "ativo"))
    avulsas = list(PecasReposicao.objects.filter(eh_kit=False).order_by("-ativo", "id").only("id", "nome", "ativo"))
    for nome, nome_maquina, _chave, descricao, itens in KITS:
        if _pelo_nome(existentes, "nome", nome) is not None:
            continue
        maquina = _pelo_nome(maquinas, "nome_brinquedo", nome_maquina)
        kit = PecasReposicao.objects.create(
            nome=nome, descricao_peca=descricao, uso="loja", ativo=True, eh_kit=True, maquina=maquina,
            preco_venda=None, preco_fornecedor=None,
        )
        for ordem, (item, detalhe, quantidade) in enumerate(itens, start=1):
            peca = _pelo_nome(avulsas, "nome", "Cabo HDMI") if _normalizar(item) == "cabo hdmi" else None
            ComponenteKit.objects.create(kit=kit, nome=item, detalhe=detalhe, quantidade=quantidade, ordem=ordem,
                                         peca=peca)
        avisar(f"{nome}: criado" + (f" (máquina {maquina.nome_brinquedo})" if maquina else " (sem máquina no catálogo)"))


def _subir_fotos(PecasReposicao, ImagemPeca, avisar):
    from django.core.files import File
    from django.db import transaction

    kits = list(PecasReposicao.objects.filter(eh_kit=True).only("id", "nome"))
    for nome, _maquina, chave, _descricao, _itens in KITS:
        arquivo = PASTA / f"{chave}.webp"
        kit = _pelo_nome(kits, "nome", nome)
        if kit is None or not arquivo.exists() or ImagemPeca.objects.filter(peca_reposicao_id=kit.pk).exists():
            continue
        try:
            with transaction.atomic(), open(arquivo, "rb") as origem:
                foto = ImagemPeca(peca_reposicao_id=kit.pk, posicao="frente", ordem=1)
                assinatura = hashlib.sha1(arquivo.read_bytes()).hexdigest()[:10]
                foto.imagem.save(f"{chave}-{assinatura}.webp", File(origem), save=False)
                guardado = foto.imagem.name or ""
                if len(guardado) > LIMITE_DO_NOME:
                    raise ValueError(f"nome do arquivo com mais de {LIMITE_DO_NOME} caracteres: {guardado!r}")
                foto.recorte_de = guardado
                foto.save()
            avisar(f"{nome}: foto de capa ({guardado})")
        except Exception as erro:  # noqa: BLE001 -- o deploy segue
            avisar(f"{nome}: a foto não subiu agora ({erro!r}).")


def criar(apps, schema_editor, avisar=print):
    from django.conf import settings

    PecasReposicao = apps.get_model("core", "PecasReposicao")
    Brinquedos = apps.get_model("core", "Brinquedos")
    # num banco SEM máquina nenhuma (o dos testes, um novo) não há kit a criar
    if not Brinquedos.objects.exists():
        return
    _criar(PecasReposicao, Brinquedos, apps.get_model("core", "ComponenteKit"), avisar)
    if getattr(settings, "IS_RENDER", False):
        _subir_fotos(PecasReposicao, apps.get_model("core", "ImagemPeca"), avisar)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0207_kit_eletronico"),
    ]

    operations = [
        migrations.RunPython(criar, migrations.RunPython.noop),
    ]
