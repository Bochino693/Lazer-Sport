"""A Black Friday 2026: as 11 promoções das artes e os produtos que faltavam.

As artes vieram da equipe (LEIA-ME, seção 74). Daqui saem:

  * os PRODUTOS NOVOS que as artes mostram e o catálogo não tinha: Basquete
    Duplo, Basquete Kids, Kid Play e as três casinhas cenográficas
    (Cozinha Infantil, Oficina de Engenharia e Salão de Beleza, numa
    categoria nova "Casinhas Cenográficas"). Entram fora da loja ("sob
    consulta"). A CAPA é a foto da máquina inteira no showroom (a seção 78:
    o recorte da própria arte tinha o fundo de neon vermelho do cartaz, ou
    era panorâmico, e o card quadrado cortava): a de core/static/site/
    capas_catalogo/<chave>.webp, marcada como a capa em cena
    (core/capas_catalogo.py, VERMELHAS). O recorte do cartaz (`fotos`) fica
    no repositório e não sobe mais; a categoria nova nasce com a foto das
    casinhas na brinquedoteca. O Brinquedão Modelo 5 (o playground da arte
    7) entra com a imagem da fábrica, se ainda não estiver no catálogo. O AIR
    ROCK não é um produto: é o Air Game Premium com outra adesivagem (LEIA-ME
    72, a 0190) -- entra como o ADESIVO "Air Rock" dele (`adesivo_de`), com
    a capa em cena do showroom como a foto do adesivo;
  * as 11 PROMOÇÕES, com o preço (ou sem preço, quando a oferta é um brinde
    ou "leve 4"), o preço "de" da arte, as condições (10x, PIX, à vista com
    desconto), válidas até 21/11/2026 (eram até 13/11; a 0191 estendeu -- no dia 22
    somem sozinhas do site), a
    foto quadrada do card e a arte inteira (o cartaz) para a página e a
    divulgação.

Os brinquedos que já existem são achados pelo nome (sem acento nem
maiúscula). Rodar de novo não duplica: produto e promoção são achados pelo
nome; a foto só sobe se ainda não está lá.

No deploy do Render a migração 0163 roda isto (o Cloudinary só está lá). Se a
subida falhar, o deploy segue e o aviso diz o comando:
    python manage.py black_friday_2026
"""

from __future__ import annotations

import datetime
import hashlib
import unicodedata
from decimal import Decimal
from pathlib import Path

from django.core.files import File
from django.db import transaction

PASTA = Path(__file__).resolve().parent / "static" / "site" / "black_friday"
VALIDA_ATE = datetime.date(2026, 11, 21)
#: A validade de antes da extensão (a 0191 leva as promoções daqui para VALIDA_ATE).
VALIDA_ATE_ANTES = datetime.date(2026, 11, 13)
CATEGORIA_CASINHAS = "Casinhas Cenográficas"


def _normalizar(texto):
    texto = unicodedata.normalize("NFD", (texto or "").lower())
    return " ".join("".join(c for c in texto if unicodedata.category(c) != "Mn").split())


def _nome_do_arquivo(arquivo):
    """O nome que sobe: a foto e a assinatura dela (a foto que mudou sobe de novo)."""
    assinatura = hashlib.sha1((PASTA / arquivo).read_bytes()).hexdigest()[:8]
    return f"black-friday-2026-{Path(arquivo).stem}-{assinatura}.webp"


PERFIL = "perfil"
#: A capa em cena (core/capas_catalogo.py): o produto já nasce com ela.
CENA = "cena"

PRODUTOS = [
    {
        "nome": "Basquete Duplo",
        "fotos": ["produto-basquete-duplo.webp"],
        "cena": "basquete-duplo",
        "voltz": "220V",
        "categorias": ["Competitivos", "Eletrônicos", "Esportivos"],
        "descricao": (
            "Basquete Duplo: a máquina de basquete de arcade para dois jogadores lado a lado, com duas "
            "cestas, placar digital para cada jogador, rampa de retorno das bolas e a adesivagem em estilo "
            "história em quadrinhos (BOOM!, POW!). Fabricada pela Lazer & Sport para buffets, shoppings, "
            "parques e espaços kids."
        ),
    },
    {
        "nome": "Basquete Kids",
        "fotos": ["produto-basquete-kids.webp"],
        "cena": "basquete-kids",
        "voltz": "220V",
        "categorias": ["Kids", "Competitivos", "Eletrônicos", "Espaço Esportivo Kids"],
        "descricao": (
            "Basquete Kids: o basquete de arcade em tamanho infantil, com cesta, bolas, placar e a "
            "adesivagem dos alienígenas (a mesma do Air Game Kids). Feito pela fábrica Lazer & Sport para "
            "espaços kids, buffets, parques e condomínios."
        ),
    },
    {
        "nome": "Air Rock",
        # o mesmo móvel do Air Game Premium, com a adesivagem Air Rock: um adesivo dele (LEIA-ME 72)
        "adesivo_de": "Air Game Premium",
        "slug": "air-rock",
        "fotos": ["produto-air-rock.webp"],
        "cena": "air-rock",
        "voltz": "220V",
        "categorias": ["Competitivos", "Jogos de Mesa"],
        "descricao": (
            "Air Rock: a mesa de air hockey profissional da Lazer & Sport, com estrutura reforçada, arco com "
            "a placa da marca, iluminação de LED azul nas bordas e nos pés e a adesivagem Air Rock em preto "
            "e vermelho. Para shoppings, buffets, parques e salões de jogos."
        ),
    },
    {
        "nome": "Kid Play",
        "fotos": ["produto-kid-play.webp"],
        "cena": "kid-play",
        "voltz": "",
        "categorias": ["Brinquedão", "Espaço Kids Play"],
        "descricao": (
            "Kid Play: o brinquedão (playground) com a estrutura iluminada em LED, escorregadores, tubo "
            "espiral, painéis interativos e piso de grama. Projeto sob medida para buffets, restaurantes, "
            "condomínios e espaços kids, com estrutura segura, acabamento de alta qualidade e personalização "
            "de cores."
        ),
    },
    {
        "nome": "Cozinha Infantil",
        "fotos": ["produto-cozinha-infantil.webp", "produto-casinhas-cenograficas.webp"],
        "cena": "cozinha-infantil",
        "voltz": "",
        "categorias": [CATEGORIA_CASINHAS, "Kids", "Espaço Kids Play"],
        "descricao": (
            "Cozinha Infantil: casinha cenográfica de faz de conta em madeira, com fogão, forno, pia, "
            "micro-ondas, geladeira, prateleiras e utensílios. Para espaços kids, buffets, escolas e "
            "brinquedotecas. Combina com a Oficina de Engenharia e o Salão de Beleza."
        ),
    },
    {
        "nome": "Oficina de Engenharia",
        "fotos": ["produto-oficina-de-engenharia.webp", "produto-casinhas-cenograficas.webp"],
        "cena": "oficina-de-engenharia",
        "voltz": "",
        "categorias": [CATEGORIA_CASINHAS, "Kids", "Espaço Kids Play"],
        "descricao": (
            "Oficina de Engenharia: casinha cenográfica de faz de conta em madeira, com bancada, painel de "
            "ferramentas, capacete, gavetas coloridas e armário. Para espaços kids, buffets, escolas e "
            "brinquedotecas. Combina com a Cozinha Infantil e o Salão de Beleza."
        ),
    },
    {
        "nome": "Salão de Beleza",
        "fotos": ["produto-salao-de-beleza.webp", "produto-casinhas-cenograficas.webp"],
        "cena": "salao-de-beleza",
        "voltz": "",
        "categorias": [CATEGORIA_CASINHAS, "Kids", "Espaço Kids Play"],
        "descricao": (
            "Salão de Beleza: casinha cenográfica de faz de conta em madeira, com penteadeira de espelho "
            "iluminado, secador, produtos de beleza, gavetas e armário. Para espaços kids, buffets, escolas "
            "e brinquedotecas. Combina com a Cozinha Infantil e a Oficina de Engenharia."
        ),
    },
    {
        # só se ainda não estiver no catálogo (a migração 0151 o cadastra com as fotos do projeto)
        "nome": "Brinquedão Modelo 5",
        "fotos": ["produto-brinquedao-modelo-5.webp"],
        "voltz": "",
        "categorias": ["Brinquedão", "Espaço Kids Play"],
        "descricao": (
            "Brinquedão Modelo 5: o playground de madeira em L, com as casinhas rosa e azul, rolos, "
            "escorregador amarelo e piso de grama. Estrutura segura, acabamento de alta qualidade e "
            "personalização de cores, para buffets, condomínios e espaços kids."
        ),
    },
]

DEZ_X = "Em até 10x sem juros"

# Na ordem em que aparecem no site (a primeira é a mais nova, a do topo).
PROMOCOES = [
    {
        "arte": 1,
        "descricao": "Black Friday: Air Game Kids + Boliche Kids + Basquete Duplo",
        "brinquedos": ["Air Game Kids", "Strike Kids", "Basquete Duplo"],
        "preco": "31970.00",
        "condicoes": [
            "Em até 10x sem juros de R$ 3.197,00",
            "À vista com 7% de desconto: R$ 29.732,10",
            "Air Game Kids R$ 6.990 · Boliche Kids 32\" R$ 7.990 · Basquete Duplo R$ 16.990",
        ],
    },
    {
        "arte": 2,
        "descricao": "Black Friday: Air Game Kids por R$ 4.990 no PIX",
        "brinquedos": ["Air Game Kids"],
        "preco": "4990.00",
        "condicoes": ["Pagamento à vista no PIX: R$ 4.990,00", "Ou em 10x de R$ 599,90 no cartão"],
    },
    {
        "arte": 6,
        "descricao": "Kit Black Friday: Boliche Kids + Air Game Kids + Basquete Kids",
        "brinquedos": ["Strike Kids", "Air Game Kids", "Basquete Kids"],
        "preco": "19990.00",
        "preco_de": "22990.00",
        "condicoes": [DEZ_X, "Diversão e interatividade, produção própria, qualidade e durabilidade"],
    },
    {
        "arte": 11,
        # A máquina das luzes da arte é o MATRIX, não o Nervo Teste (o cliente: "arrume a
        # nomenclatura, não é o nervo teste, é o matrix"); a arte e o card foram corrigidos
        # e a promoção que já existe com o nome antigo é acertada (`antes`, migração 0175).
        "descricao": "Kit Sucesso e Inovação: Air Game + Matrix + Boliche Kids",
        "antes": ["Kit Sucesso e Inovação: Air Game + Nervo Teste + Boliche Kids"],
        "brinquedos": ["Air Game Home", "Matrix", "Strike Kids"],
        "preco": "23990.00",
        "preco_de": "27990.00",
        "condicoes": [DEZ_X],
    },
    {
        "arte": 3,
        "descricao": "Black Friday: Basquete Duplo",
        "brinquedos": ["Basquete Duplo"],
        "preco": "16990.00",
        "condicoes": [DEZ_X],
    },
    {
        "arte": 10,
        "descricao": "Black Friday: Air Rock",
        # o Air Rock é o adesivo do Air Game Premium (a 0190): a promoção é dele, com a arte do Air Rock
        "brinquedos": ["Air Game Premium"],
        "preco": "12990.00",
        "preco_de": "14990.00",
        "condicoes": [DEZ_X],
    },
    {
        "arte": 9,
        "descricao": "Black Friday: Boliche Eletrônico Dragon Bowling",
        "brinquedos": ["Boliche Virtual"],
        "preco": "12990.00",
        "condicoes": [DEZ_X, "Recorde de vendas, inovação e novidades"],
    },
    {
        "arte": 8,
        "descricao": "Black Friday: Nervo Teste",
        "brinquedos": ["Nervo Teste"],
        "preco": "7990.00",
        "condicoes": [
            DEZ_X,
            "Prazo de produção: 45 a 50 dias",
            "Frete por conta do cliente",
            "Garantia de 6 meses contra defeitos de fabricação",
            "Validade da proposta: 30 dias",
        ],
    },
    {
        "arte": 7,
        "descricao": "Black: promoção especial do playground (Brinquedão Modelo 5)",
        "brinquedos": ["Brinquedão Modelo 5"],
        "preco": "12000.00",
        "condicoes": [
            "12x de R$ 1.000,00 no cartão de crédito",
            "Estrutura segura, acabamento de alta qualidade e personalização de cores",
        ],
    },
    {
        "arte": 4,
        "descricao": "Black Friday: na compra de 3 cenográficos, leve 4",
        "brinquedos": ["Cozinha Infantil", "Oficina de Engenharia", "Salão de Beleza"],
        "preco": None,
        "condicoes": ["Na compra de 3 cenográficos, leve 4!", "Parcelamos em até 10x sem juros"],
    },
    {
        "arte": 5,
        "descricao": "Black Friday: Kid Play + kit de mesinha kids de cortesia",
        "brinquedos": ["Kid Play"],
        "preco": None,
        "condicoes": [
            "Na compra de um Kid Play, ganhe um kit de mesinha kids de cortesia",
            "Estrutura segura, acabamento de alta qualidade e personalização de cores",
        ],
    },
]


def achar(nome, Brinquedos):
    """O brinquedo do catálogo com este nome (o ativo primeiro), ou None."""
    alvo = _normalizar(nome)
    return next(
        (b for b in Brinquedos.objects.order_by("-ativo", "id") if _normalizar(b.nome_brinquedo) == alvo),
        None,
    )


def _categorias(nomes, CategoriasBrinquedos, avisar):
    todas = {_normalizar(c.nome_categoria): c for c in CategoriasBrinquedos.objects.all() if c.nome_categoria}
    escolhidas = []
    for nome in nomes:
        categoria = todas.get(_normalizar(nome))
        if categoria is None and nome == CATEGORIA_CASINHAS:
            # a foto da categoria: as três casinhas na brinquedoteca, com as crianças (seção 78), com o
            # nome que o `atualizar_capas_categorias` reconhece (a chave e a assinatura)
            from .categorias_capas import arquivo_da_capa, nome_no_cadastro

            categoria = CategoriasBrinquedos(nome_categoria=CATEGORIA_CASINHAS)
            with open(arquivo_da_capa("casinhas-cenograficas"), "rb") as origem:
                categoria.imagem_categoria.save(f"{nome_no_cadastro('casinhas-cenograficas')}.webp", File(origem), save=True)
            todas[_normalizar(nome)] = categoria
            avisar(f"Categoria nova: {CATEGORIA_CASINHAS}.")
        if categoria is not None:
            escolhidas.append(categoria)
    return escolhidas


def _capa_em_cena(brinquedo, chave, ImagemBrinquedo):
    """A capa do produto novo: a foto dele no showroom (core/capas_catalogo.py), marcada como a capa em cena."""
    from . import capas_catalogo

    foto = ImagemBrinquedo(
        brinquedo=brinquedo, tipo=PERFIL, ordem=1, papel_na_capa=CENA,
        texto_alternativo=f"{brinquedo.nome_brinquedo} no showroom da Lazer & Sport"[:180],
    )
    with open(capas_catalogo.arquivo(chave), "rb") as origem:
        foto.imagem.save(capas_catalogo.nome_no_cadastro(chave), File(origem), save=True)
    brinquedo.imagem_brinquedo = foto.imagem.name
    brinquedo.save(update_fields=["imagem_brinquedo"])
    return foto


def _campo(modelo, nome):
    return any(f.name == nome for f in modelo._meta.get_fields())


def cadastrar_adesivo(dados, base, ImagemBrinquedo, simular=False, avisar=print):
    """O ADESIVO `dados["nome"]` do produto `base` (LEIA-ME 72: o Air Rock é o Air Game Premium com outra arte).

    A foto do adesivo é a capa em cena do showroom (a capa quadrada do adesivo: `papel_na_capa`
    "cena", com a posição "perfil"), se ele ainda não tem. Devolve o adesivo (ou None ao simular).
    """
    from . import capas_catalogo

    VarianteAdesivo = ImagemBrinquedo._meta.get_field("variante").related_model
    variante = (VarianteAdesivo.objects.filter(brinquedo=base, slug=dados["slug"]).first()
                or VarianteAdesivo.objects.filter(brinquedo=base, nome=dados["nome"]).first())
    if simular:
        avisar(f"{dados['nome']}: {'já é' if variante else 'seria'} um adesivo do {base.nome_brinquedo}.")
        return None
    with transaction.atomic():
        if variante is None:
            ordem = max(VarianteAdesivo.objects.filter(brinquedo=base).values_list("ordem", flat=True), default=1) + 1
            variante = VarianteAdesivo.objects.create(brinquedo=base, nome=dados["nome"], slug=dados["slug"],
                                                      ordem=ordem, padrao=False)
            avisar(f"{dados['nome']}: adesivo novo do {base.nome_brinquedo}.")
        if dados.get("cena") and not ImagemBrinquedo.objects.filter(variante=variante, papel_na_capa=CENA).exists():
            ocupada = ImagemBrinquedo.objects.filter(variante=variante, tipo=PERFIL).exists()
            foto = ImagemBrinquedo(
                brinquedo=base, variante=variante, tipo=None if ocupada else PERFIL, ordem=1, papel_na_capa=CENA,
                texto_alternativo=f"{base.nome_brinquedo} ({dados['nome']}) no showroom da Lazer & Sport"[:180],
            )
            with open(capas_catalogo.arquivo(dados["cena"]), "rb") as origem:
                foto.imagem.save(capas_catalogo.nome_no_cadastro(dados["cena"]), File(origem), save=True)
            avisar(f"{dados['nome']}: a capa do adesivo (o showroom) subiu.")
    return variante


def cadastrar_produto(dados, Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, simular=False, avisar=print):
    """Cria o produto (com as fotos) se ainda não está no catálogo. Devolve o brinquedo (ou None ao simular).

    Com `cena` (seção 78), a capa é a foto no showroom (a capa em cena) e o recorte do cartaz não sobe.
    Com `adesivo_de` (LEIA-ME 72), não é um produto: é um adesivo daquele (`cadastrar_adesivo`); a
    ficha à parte que já existir (a de antes da 0190) fica como está, e a 0190 a junta ao produto.
    """
    if dados.get("adesivo_de") and _campo(ImagemBrinquedo, "variante"):
        base = achar(dados["adesivo_de"], Brinquedos)
        if base is not None and achar(dados["nome"], Brinquedos) is None:
            cadastrar_adesivo(dados, base, ImagemBrinquedo, simular=simular, avisar=avisar)
            return base
    existente = achar(dados["nome"], Brinquedos)
    if existente is not None:
        if not existente.imagem_brinquedo and not simular:
            if dados.get("cena") and not ImagemBrinquedo.objects.filter(brinquedo=existente, tipo=PERFIL).exists():
                with transaction.atomic():
                    _capa_em_cena(existente, dados["cena"], ImagemBrinquedo)
            else:
                with open(PASTA / dados["fotos"][0], "rb") as origem:
                    existente.imagem_brinquedo.save(_nome_do_arquivo(dados["fotos"][0]), File(origem), save=True)
            avisar(f"{dados['nome']}: já estava no catálogo (id {existente.pk}); ganhou a foto.")
        else:
            avisar(f"{dados['nome']}: já está no catálogo (id {existente.pk}).")
        return existente
    if simular:
        quantas = "a capa em cena (o showroom)" if dados.get("cena") else f"{len(dados['fotos'])} foto(s)"
        avisar(f"{dados['nome']}: seria criado, fora da loja, com {quantas}.")
        return None
    with transaction.atomic():
        brinquedo = Brinquedos.objects.create(
            nome_brinquedo=dados["nome"],
            descricao=dados["descricao"][:999],
            valor_brinquedo=None,
            avaliacao=Decimal("5.00"),
            exibir_na_loja=False,
            voltz=dados["voltz"],
        )
        brinquedo.categorias_brinquedos.set(_categorias(dados["categorias"], CategoriasBrinquedos, avisar))
        if dados.get("cena"):
            # a foto no showroom é a capa; o recorte do cartaz (o fundo vermelho, a panorâmica) fica no repositório
            _capa_em_cena(brinquedo, dados["cena"], ImagemBrinquedo)
        for ordem, arquivo in enumerate([] if dados.get("cena") else dados["fotos"], start=1):
            with open(PASTA / arquivo, "rb") as origem:
                foto = ImagemBrinquedo(
                    brinquedo=brinquedo, tipo=PERFIL if ordem == 1 else None, ordem=ordem,
                    texto_alternativo=f"{dados['nome']} da Lazer & Sport"[:180],
                )
                foto.imagem.save(_nome_do_arquivo(arquivo), File(origem), save=True)
            if ordem == 1:
                brinquedo.imagem_brinquedo = foto.imagem.name
                brinquedo.save(update_fields=["imagem_brinquedo"])
    avisar(f"{dados['nome']}: criado (id {brinquedo.pk}), fora da loja, sob consulta.")
    return brinquedo


def cadastrar_promocao(dados, Brinquedos, Promocoes, simular=False, avisar=print):
    """Cria (ou acerta) a promoção. As fotos só sobem se ainda não estão lá."""
    brinquedos = [achar(nome, Brinquedos) for nome in dados["brinquedos"]]
    faltando = [nome for nome, b in zip(dados["brinquedos"], brinquedos) if b is None]
    if faltando:
        avisar(f"{dados['descricao']}: falta no catálogo {', '.join(faltando)}; a promoção fica para depois.")
        return None
    if simular:
        avisar(f"{dados['descricao']}: seria criada/acertada ({', '.join(b.nome_brinquedo for b in brinquedos)}).")
        return None
    nomes = [dados["descricao"], *dados.get("antes", [])]
    promocao = (Promocoes.objects.filter(descricao=dados["descricao"]).first()
                or Promocoes.objects.filter(descricao__in=nomes).first()
                or Promocoes(descricao=dados["descricao"]))
    nova = promocao.pk is None
    promocao.descricao = dados["descricao"]  # o nome antigo (ex.: o Nervo Teste no Kit Sucesso) é acertado
    promocao.brinquedos = brinquedos[0]
    promocao.preco_promocao = Decimal(dados["preco"]) if dados.get("preco") else None
    promocao.preco_de = Decimal(dados["preco_de"]) if dados.get("preco_de") else None
    from .parcelas_texto import condicoes_em_6x  # "tudo em 6x" (migração 0195)

    promocao.condicoes = condicoes_em_6x("\n".join(dados["condicoes"]), dados.get("preco"))
    promocao.valida_ate = VALIDA_ATE
    if nova:
        promocao.ativo = True
    with transaction.atomic():
        promocao.save()
        promocao.brinquedos_extras.set(brinquedos[1:])
        for campo, arquivo in (("imagem_promocao", f"card-{dados['arte']:02d}.webp"),
                               ("arte_promocao", f"arte-{dados['arte']:02d}.webp")):
            atual = getattr(promocao, campo)
            novo = _nome_do_arquivo(arquivo)
            if atual and Path(novo).stem in (atual.name or ""):
                continue
            with open(PASTA / arquivo, "rb") as origem:
                getattr(promocao, campo).save(novo, File(origem), save=True)
    avisar(f"{dados['descricao']}: {'criada' if nova else 'acertada'} (id {promocao.pk}).")
    return promocao


def rodar(Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, Promocoes, simular=False, forcar=False,
          hoje=None, avisar=print):
    """Cadastra os produtos que faltam e as promoções (as que ainda estão na validade)."""
    for dados in PRODUTOS:
        cadastrar_produto(dados, Brinquedos, CategoriasBrinquedos, ImagemBrinquedo, simular=simular, avisar=avisar)
    from django.utils import timezone

    hoje = hoje or timezone.localdate()
    if hoje > VALIDA_ATE and not forcar:
        avisar(f"A Black Friday terminou em {VALIDA_ATE:%d/%m/%Y}: as promoções não foram criadas (use --forcar).")
        return
    # de trás para a frente: a primeira da lista fica com o id maior (o site mostra as mais novas antes)
    for dados in reversed(PROMOCOES):
        cadastrar_promocao(dados, Brinquedos, Promocoes, simular=simular, avisar=avisar)


def kit_sucesso_com_matrix(apps, schema_editor, avisar=print):
    """A migração 0175: o Kit Sucesso é Air Game + MATRIX + Boliche Kids (não o Nervo Teste).

    Em todo lugar: a promoção que já existe com o nome antigo ganha o nome certo e o Matrix
    no lugar do Nervo Teste. Só no Render (o Cloudinary só está lá): a arte e o card
    corrigidos sobem. Sem a promoção (nunca criada) ou sem o Matrix no catálogo, nada muda.
    """
    from django.conf import settings

    Brinquedos = apps.get_model("core", "Brinquedos")
    Promocoes = apps.get_model("core", "Promocoes")
    dados = next(d for d in PROMOCOES if d["arte"] == 11)
    nomes = [dados["descricao"], *dados["antes"]]
    promocao = Promocoes.objects.filter(descricao__in=nomes).first()
    if promocao is None:
        return
    if getattr(settings, "IS_RENDER", False):
        try:
            cadastrar_promocao(dados, Brinquedos, Promocoes, avisar=avisar)
        except Exception as erro:  # noqa: BLE001 -- o deploy segue
            avisar(f"O Kit Sucesso não foi acertado agora ({erro!r}). Rode: python manage.py black_friday_2026 --forcar")
            return
        try:
            from django.core.cache import cache

            cache.clear()
        except Exception:  # noqa: BLE001
            pass
        return
    brinquedos = [achar(nome, Brinquedos) for nome in dados["brinquedos"]]
    if any(b is None for b in brinquedos):
        avisar(f"{dados['descricao']}: falta no catálogo o Matrix; a promoção fica como está.")
        return
    with transaction.atomic():
        promocao.descricao = dados["descricao"]
        promocao.brinquedos = brinquedos[0]
        promocao.save()
        promocao.brinquedos_extras.set(brinquedos[1:])


def _promocoes_da_black_friday(Promocoes, dados):
    """A promoção de uma arte: pelo nome (ou um nome antigo) ou pela foto da arte que ela carrega."""
    from django.db.models import Q

    nomes = [dados["descricao"], *dados.get("antes", [])]
    foto = f"black-friday-2026-card-{dados['arte']:02d}-"
    return Promocoes.objects.filter(Q(descricao__in=nomes) | Q(imagem_promocao__contains=foto))


def estender_ate_21(apps, schema_editor, avisar=print):
    """A migração 0191: a Black Friday vai até 21/11/2026 (era até 13/11).

    "Ampliar as promoções até dia 21/11, alterando as imagens e a data certinho, pois vou
    jogar o tráfego pago nelas." Só o que a extensão pede, e mais nada -- o cadastro
    (`cadastrar_promocao`) reescreveria preço, condições e brinquedos a partir daqui, e o que
    a equipe acertou no painel se perderia:
      * em todo lugar: a validade passa a 21/11 (a promoção que já ia além fica como está;
        a desligada no painel continua desligada);
      * só no Render (o Cloudinary só está lá): as artes e os cards que mudaram (01, 02 e 03,
        que traziam "válida até 13 de novembro" escrito) sobem no lugar dos antigos.
    """
    from django.conf import settings

    Promocoes = apps.get_model("core", "Promocoes")
    no_render = getattr(settings, "IS_RENDER", False)
    for dados in PROMOCOES:
        for promocao in _promocoes_da_black_friday(Promocoes, dados):
            if promocao.valida_ate is None or promocao.valida_ate < VALIDA_ATE:
                promocao.valida_ate = VALIDA_ATE
                promocao.save(update_fields=["valida_ate"])
            if not no_render:
                continue
            try:
                for campo, arquivo in (("imagem_promocao", f"card-{dados['arte']:02d}.webp"),
                                       ("arte_promocao", f"arte-{dados['arte']:02d}.webp")):
                    atual = getattr(promocao, campo)
                    novo = _nome_do_arquivo(arquivo)
                    if atual and Path(novo).stem in (atual.name or ""):
                        continue
                    with open(PASTA / arquivo, "rb") as origem:
                        getattr(promocao, campo).save(novo, File(origem), save=True)
            except Exception as erro:  # noqa: BLE001 -- o deploy segue; a data já está certa
                avisar(f"{dados['descricao']}: a arte nova não subiu agora ({erro!r}).")
    try:  # a home, o catálogo e a página da promoção guardados em cache passam a mostrar o 21
        from django.core.cache import cache

        cache.clear()
    except Exception:  # noqa: BLE001
        pass


def voltar_para_13(apps, schema_editor):
    """A volta da 0191: as promoções que estão em 21/11 voltam a 13/11 (as artes ficam)."""
    Promocoes = apps.get_model("core", "Promocoes")
    for dados in PROMOCOES:
        _promocoes_da_black_friday(Promocoes, dados).filter(valida_ate=VALIDA_ATE).update(valida_ate=VALIDA_ATE_ANTES)


def subir_no_deploy(apps, schema_editor, avisar=print):
    """A migração 0163: só no Render (o Cloudinary só está lá); se algo falhar, o deploy segue."""
    from django.conf import settings

    if not getattr(settings, "IS_RENDER", False):
        return
    try:
        rodar(
            apps.get_model("core", "Brinquedos"), apps.get_model("core", "CategoriasBrinquedos"),
            apps.get_model("core", "ImagemBrinquedo"), apps.get_model("core", "Promocoes"), avisar=avisar,
        )
    except Exception as erro:  # o deploy segue; o comando refaz depois
        avisar(f"A Black Friday não subiu agora ({erro!r}). Rode: python manage.py black_friday_2026")
        return
    try:  # a home e o catálogo guardados em cache passam a mostrar as promoções
        from django.core.cache import cache

        cache.clear()
    except Exception:  # noqa: BLE001
        pass
