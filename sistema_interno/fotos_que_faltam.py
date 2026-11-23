"""AS FOTOS QUE FALTAM: um card por foto, para o dono enviar de volta (LEIA-ME-V10, seção 133).

O Cloudinary desativou a conta e, para devolver a exportação (o ZIP da Media
Library), pede pagamento: "eu queria baixar em zip mas o sistema me brecha e
me joga para pagamento". Então a tela não depende mais da exportação: cada
foto que ainda não voltou vira um CARD -- o que ela é (o brinquedo e qual
foto, o cliente, o projeto, o combo, a peça, o jogo, o estabelecimento) e
onde ela aparece no site --, com o botão "Enviar foto". A foto enviada vai
para o nosso banco (core.espelho_midia.gravar_conteudo: exata, origem
"envio") e troca o nome em TODO campo que a usava; daí em diante ela nunca
mais depende do Cloudinary.

UMA CONSULTA, E NÃO UMA POR MODELO. O espelho (core.espelho_midia.referencias)
lê cada modelo à parte: ~25 idas ao banco, ~4 s com o Supabase a 170 ms. Aqui
os mesmos campos (espelho_midia.campos_de_arquivo) vão num UNION ALL só; se o
banco recusar (uma tabela que ainda não existe), cai no caminho do espelho.
O resultado tem a mesma forma ({nome: [Referencia]}), e é ele que o envio
passa ao gravar_conteudo.

O QUE É PRIVADO FICA SÓ NA CONTAGEM: os documentos do RH, das notas e das
O.S. (armazenamento que não guarda público) não viram card -- não se envia
documento de colaborador por uma tela de fotos.
"""

from __future__ import annotations

import logging
import posixpath
import re
from collections import OrderedDict

from django.conf import settings
from django.db import DatabaseError
from django.db.models import CharField, Q, Value
from django.db.models.functions import Cast

from core import espelho_midia
from core.arquivos_no_banco import PREFIXO, e_do_banco

log = logging.getLogger("lazer.midia")

#: Os tipos de cadastro, na ordem da tela: o que o site mostra primeiro, depois o que é só do painel.
#: (chave, título, ícone do painel, modelos)
TIPOS = (
    ("produtos", "Fotos dos produtos", "bi-controller", ("core.Brinquedos", "core.ImagemBrinquedo")),
    ("clientes", "Logos dos clientes", "bi-buildings", ("sistema_interno.Cliente",)),
    ("projetos", "Projetos", "bi-rulers", ("core.ImagemProjetoBrinquedo",)),
    ("combos", "Combos", "bi-collection", ("core.Combos",)),
    ("pecas", "Fotos das peças", "bi-gear-wide-connected", ("core.ImagemPeca",)),
    ("jogos", "Capas dos jogos", "bi-joystick", ("core.JogoCadastrado",)),
    ("estabelecimentos", "Estabelecimentos", "bi-shop", ("core.Estabelecimentos",)),
    ("categorias", "Categorias", "bi-grid-3x3-gap", ("core.CategoriasBrinquedos",)),
    ("promocoes", "Promoções", "bi-tags", ("core.Promocoes",)),
    ("eventos", "Eventos", "bi-calendar-event", ("core.ImagemEvento",)),
    ("site", "Imagens do site", "bi-window", ("core.ImagensSite",)),
)
#: O que não está em TIPOS e é público: só do painel (materiais, guias, manutenções, 3D...).
TIPO_PAINEL = ("painel", "Só no painel", "bi-window-sidebar")
_TIPO_DO_MODELO = {modelo: tipo for tipo in TIPOS for modelo in tipo[3]}

#: Os documentos privados, só contados.
NOMES_PRIVADOS = {
    "sistema_interno.NotaEntrada": "Notas fiscais",
    "sistema_interno.DocumentoOrdemServico": "Documentos das O.S.",
    "rh.DocumentoColaborador": "Documentos do RH",
    "rh.ImportacaoPonto": "Cartões de ponto",
}

#: Cards por "Mostrar mais" (a tela dos cards fecha a fileira de 4: múltiplo de 12).
POR_VEZ = 12


# ======================================================================
# QUEM USA CADA NOME (uma consulta)
# ======================================================================
def _consultar(filtro_do_campo, *, somente_publicos=False):
    """{nome: [Referencia]} -- os campos de arquivo num UNION ALL só (ver o topo)."""
    por_modelo = espelho_midia.campos_de_arquivo(somente_publicos)
    campos = {}
    partes = []
    for modelo, lista in por_modelo.items():
        for campo in lista:
            campos[(modelo._meta.label, campo.attname)] = (modelo, campo)
            partes.append(
                modelo._base_manager.filter(filtro_do_campo(campo.attname))
                .order_by()
                .annotate(
                    _m=Value(modelo._meta.label, output_field=CharField()),
                    _c=Value(campo.attname, output_field=CharField()),
                    _pk=Cast("pk", output_field=CharField()),
                    _n=Cast(campo.attname, output_field=CharField()),
                )
                .values_list("_m", "_c", "_pk", "_n")
            )
    if not partes:
        return {}
    consulta = partes[0].union(*partes[1:], all=True) if len(partes) > 1 else partes[0]
    saida = {}
    for rotulo, attname, pk, nome in consulta:
        modelo, campo = campos[(rotulo, attname)]
        grupo = saida.setdefault(nome, [])
        ref = next((r for r in grupo if r.modelo is modelo and r.campo == attname), None)
        if ref is None:
            ref = espelho_midia.Referencia(modelo, attname, campo.storage, campo.max_length or 100)
            grupo.append(ref)
        ref.pks.append(int(pk) if str(pk).isdigit() else pk)
    return saida


def _filtro_pendente(attname):
    return (~Q(**{f"{attname}__startswith": PREFIXO}) & ~Q(**{attname: ""})
            & Q(**{f"{attname}__isnull": False}))


def pendentes(*, somente_publicos=False):
    """{nome antigo: [Referencia]} do que ainda não está no banco (o mesmo que espelho_midia.referencias())."""
    try:
        return _consultar(_filtro_pendente, somente_publicos=somente_publicos)
    except DatabaseError:
        log.warning("fotos que faltam: a consulta única falhou; vai pelo espelho", exc_info=True)
        return espelho_midia.referencias(somente_publicos=somente_publicos)


def usos_de(nomes):
    """{nome: [Referencia]} só destes nomes (os de antes ou os "banco/..."), numa consulta."""
    nomes = [n for n in dict.fromkeys(nomes) if n]
    if not nomes:
        return {}
    try:
        return _consultar(lambda attname: Q(**{f"{attname}__in": nomes}))
    except DatabaseError:
        log.warning("fotos que faltam: a consulta dos nomes falhou; vai pelo espelho", exc_info=True)
        todos = {**espelho_midia.referencias(), **espelho_midia.referencias(do_banco=True)}
        return {nome: todos[nome] for nome in nomes if nome in todos}


def e_publico(grupo):
    return bool(getattr(grupo[0].storage, "guarda_publico", False))


def aceita(grupo):
    """O que o <input type=file> do card aceita: foto, ou o .glb do 3D."""
    return ".glb,model/gltf-binary" if getattr(grupo[0].storage, "legado", "image") == "raw" else "image/*"


# ======================================================================
# O QUE É CADA FOTO (para o card)
# ======================================================================
def _site(caminho):
    return f"{(getattr(settings, 'SITE_URL', '') or '').rstrip('/')}{caminho}"


def _objetos(grupos):
    """{(rótulo do modelo, pk): objeto} -- uma consulta por modelo, com o que a descrição lê."""
    from core.models import ImagemBrinquedo, ImagemPeca, ImagemProjetoBrinquedo

    pks = {}
    modelos = {}
    for grupo in grupos:
        for ref in grupo:
            modelos[ref.modelo._meta.label] = ref.modelo
            pks.setdefault(ref.modelo._meta.label, set()).update(ref.pks)
    junto = {
        ImagemBrinquedo: ("brinquedo", "variante"),
        ImagemPeca: ("peca_reposicao",),
        ImagemProjetoBrinquedo: ("brinquedo__projeto",),
    }
    saida = {}
    for rotulo, modelo in modelos.items():
        consulta = modelo._base_manager.filter(pk__in=pks[rotulo])
        if modelo in junto:
            consulta = consulta.select_related(*junto[modelo])
        elif rotulo == "core.ImagemEvento":
            consulta = consulta.select_related("evento")
        try:
            for objeto in consulta:
                saida[(rotulo, objeto.pk)] = objeto
        except DatabaseError:
            log.warning("fotos que faltam: não deu para ler %s", rotulo, exc_info=True)
    return saida


def _descrever(ref, objeto, nome):
    """(título, o que é a foto, [(onde, endereço ou "")]) de um uso do arquivo."""
    rotulo = ref.modelo._meta.label
    if objeto is None:
        return f"{ref.modelo._meta.verbose_name} #{ref.pks[0]}", "", []
    if rotulo == "core.Brinquedos":
        return objeto.nome_brinquedo, "A capa do produto", [
            ("A página do produto", _site(f"/brinquedo/{objeto.pk}/")),
            ("Os cards do catálogo, da home e das categorias", ""),
        ]
    if rotulo == "core.ImagemBrinquedo":
        brinquedo = objeto.brinquedo
        posicao = objeto.get_tipo_display() if objeto.tipo else "Foto da galeria"
        variante = getattr(objeto, "variante", None)
        adesivo = f" · adesivo {variante.nome}" if variante is not None and variante.pk != brinquedo.adesivo_padrao_id else ""
        return brinquedo.nome_brinquedo, f"{posicao}{adesivo}", [
            ("A galeria da página do produto", _site(f"/brinquedo/{brinquedo.pk}/")),
        ]
    if rotulo == "core.ImagemPeca":
        peca = objeto.peca_reposicao
        if ref.campo == "imagem_original":
            detalhe = "A foto original (antes do recorte)"
        elif "-sem-fundo" in nome:
            detalhe = "A foto da peça, sem o fundo"
        else:
            detalhe = f"Foto da peça · {objeto.get_posicao_display()}"
        return peca.nome, detalhe, [
            ("A página da peça", _site(f"/pecas/{peca.pk}/")),
            ("Os cards da loja, das peças e da home", _site("/pecas-reposicao/")),
        ]
    if rotulo == "core.Combos":
        return objeto.descricao, "A foto do combo", [
            ("A página do combo", _site(f"/combo/{objeto.pk}/")),
            ("Os combos da home e da loja", _site("/loja/")),
        ]
    if rotulo == "core.ImagemProjetoBrinquedo":
        brinquedo = objeto.brinquedo
        projeto = getattr(brinquedo, "projeto", None) if brinquedo is not None else None
        titulo = (projeto.titulo if projeto is not None else "") or (brinquedo.nome_brinquedo_projeto if brinquedo else "Projeto")
        # várias fotos do mesmo projeto: o nome do arquivo (sem o sufixo do Cloudinary) as separa
        return titulo, objeto.legenda or f"Foto do projeto · {_SUFIXO.sub('', posixpath.basename(nome))}", [
            ("A galeria do projeto", _site("/projetos/")),
            ("Os projetos da home", _site("/#projetos")),
        ]
    if rotulo == "core.JogoCadastrado":
        return objeto.nome, "A imagem grande do jogo" if ref.campo == "poster" else "A capa do jogo", [
            ("A biblioteca de jogos", _site("/jogos/")),
            ("A página do jogo", _site(f"/jogos/{objeto.slug}/") if getattr(objeto, "slug", "") else ""),
        ]
    if rotulo == "core.Estabelecimentos":
        return objeto.nome_estabelecimento, "A foto do tipo de lugar", [
            ("A página dos estabelecimentos", _site("/estabelecimentos/")),
        ]
    if rotulo == "sistema_interno.Cliente":
        return objeto.nome_publico or f"Cliente #{objeto.pk}", "O logo do cliente", [
            ("A faixa de clientes no rodapé de todas as páginas", ""),
        ]
    if rotulo == "core.CategoriasBrinquedos":
        return objeto.nome_categoria, "A foto da categoria", [("A página da categoria", _site(f"/categoria/{objeto.pk}/"))]
    if rotulo == "core.Promocoes":
        return objeto.descricao, "A arte da promoção" if ref.campo == "arte_promocao" else "A foto da promoção", [
            ("A página da promoção", _site(f"/promocao/{objeto.pk}/")),
        ]
    if rotulo == "core.ImagemEvento":
        evento = getattr(objeto, "evento", None)
        return (evento.titulo if evento else "Evento"), objeto.legenda or "Foto do evento", [("Os eventos", _site("/eventos/"))]
    return str(objeto)[:120] or f"{ref.modelo._meta.verbose_name} #{objeto.pk}", str(ref.modelo._meta.verbose_name).capitalize(), [
        ("O painel", ""),
    ]


def _tipo_do_grupo(grupo):
    for ref in grupo:
        tipo = _TIPO_DO_MODELO.get(ref.modelo._meta.label)
        if tipo:
            return tipo
    return None


def _card(nome, grupo, objetos, *, provisoria=False):
    principal = grupo[0]
    for ref in grupo:  # o produto (a capa) diz mais que a foto da galeria
        if ref.modelo._meta.label == "core.Brinquedos":
            principal = ref
            break
    objeto = objetos.get((principal.modelo._meta.label, principal.pks[0]))
    titulo, detalhe, onde = _descrever(principal, objeto, nome)
    usos = sum(len(ref.pks) for ref in grupo)
    antigo = nome[len(PREFIXO):] if e_do_banco(nome) else nome
    _pasta, base = posixpath.split(antigo)
    foto = ""
    if provisoria:
        from core.arquivos_no_banco import url_publica
        from core.fotos import reduzir_imagem

        foto = reduzir_imagem(url_publica(nome), 480)
    tipo = _tipo_do_grupo(grupo)
    return {
        "nome": nome,
        "antigo": antigo,
        "base": base,
        "url": foto,
        # o tipo do cadastro (o logo e a peça aparecem inteiros no card; a foto de cena, cheia)
        "tipo": tipo[0] if tipo else TIPO_PAINEL[0],
        "titulo": titulo,
        "detalhe": detalhe,
        "onde": [{"texto": texto, "url": endereco} for texto, endereco in onde],
        "outros_usos": max(0, usos - 1),
        "aceita": aceita(grupo),
        "provisoria": provisoria,
        "chaves": sorted(chaves_do_nome(nome)),
    }


# ======================================================================
# CASAR O ARQUIVO SOLTO COM A FOTO QUE FALTA
# ======================================================================
_SUFIXO = re.compile(r"_[a-z0-9]{6}$")
_EXTENSAO = re.compile(r"\.(jpe?g|png|webp|gif|avif|heic|heif|bmp|tiff?|glb)$", re.I)


def normalizar(nome_do_arquivo: str) -> str:
    """O nome como o Django o grava (get_valid_filename): espaço vira _, o resto sai. Sem extensão, minúsculo."""
    base = str(nome_do_arquivo or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    base = _EXTENSAO.sub("", base)
    base = re.sub(r"(?u)[^-\w.]", "", base.replace(" ", "_"))
    return base.lower()


def chaves_do_nome(nome) -> set:
    """Os jeitos de reconhecer a foto pelo nome do arquivo: o public id inteiro, o nome com o sufixo e sem ele."""
    antigo = nome[len(PREFIXO):] if e_do_banco(nome) else nome
    sem_ext = _EXTENSAO.sub("", antigo).lower()
    base = sem_ext.rsplit("/", 1)[-1]
    return {sem_ext, base, _SUFIXO.sub("", base)}


def casar(arquivos, cards):
    """Para cada nome de arquivo: o card que ele restaura (só se for UM) e os candidatos.

    Como o Mapa da exportação (core/restaurar_midia.py), pelo public id -- a
    pasta e o nome, ou o nome com o sufixo do Cloudinary --, e também pelo
    nome que o arquivo tinha ANTES de subir (o Cloudinary acrescenta
    "_ab12cd"): "Boliche Virtual Preto.jpg" é imagens_brinquedos/galeria/
    Boliche_Virtual_Preto_osn8q7. Dois cards com o mesmo nome (o "001.jpg"
    de três projetos) não casam sozinhos: o dono escolhe.
    """
    indice = {}
    for card in cards:
        for chave in card["chaves"]:
            indice.setdefault(chave, []).append(card["nome"])
    saida = []
    usados = set()
    for arquivo in arquivos:
        chave = normalizar(arquivo)
        caminho = _EXTENSAO.sub("", str(arquivo or "").replace("\\", "/")).lower()
        candidatos = []
        for tentativa in (caminho, chave, _SUFIXO.sub("", chave)):
            candidatos = [n for n in indice.get(tentativa, []) if n not in usados]
            if candidatos:
                break
        escolhido = candidatos[0] if len(candidatos) == 1 else None
        if escolhido:
            usados.add(escolhido)
        saida.append({"arquivo": arquivo, "nome": escolhido, "candidatos": candidatos if not escolhido else []})
    return saida


# ======================================================================
# A TELA
# ======================================================================
def _marcar_ocultos(cards):
    """Os 12 primeiros de cada tipo à vista; o resto chega pelo "Mostrar mais" (12 de cada vez)."""
    for ordem, card in enumerate(cards):
        card["oculto"] = ordem >= POR_VEZ


def montar(todos=None):
    """Os cards da tela, por tipo (o site primeiro), e a contagem do que é privado.

    `todos`: o que `pendentes()` já leu (a view lê uma vez para os números e os cards).
    """
    from core.models import ArquivoNoBanco

    todos = pendentes() if todos is None else todos
    publicos = {nome: grupo for nome, grupo in todos.items() if e_publico(grupo)}
    privados = OrderedDict()
    for nome, grupo in todos.items():
        if e_publico(grupo):
            continue
        for ref in grupo:
            rotulo = NOMES_PRIVADOS.get(ref.modelo._meta.label, str(ref.modelo._meta.verbose_name_plural).capitalize())
            privados[rotulo] = privados.get(rotulo, 0) + len(ref.pks)

    # as fotos que voltaram como cópia provisória (exata=False): o dono pode mandar a original
    nomes_provisorios = list(ArquivoNoBanco.objects.filter(exata=False, publico=True).values_list("nome", flat=True)[:400])
    provisorias = usos_de(nomes_provisorios) if nomes_provisorios else {}

    objetos = _objetos(list(publicos.values()) + list(provisorias.values()))
    grupos = OrderedDict((tipo[0], {"chave": tipo[0], "titulo": tipo[1], "icone": tipo[2], "cards": []}) for tipo in TIPOS)
    grupos[TIPO_PAINEL[0]] = {"chave": TIPO_PAINEL[0], "titulo": TIPO_PAINEL[1], "icone": TIPO_PAINEL[2], "cards": []}
    for nome, grupo in sorted(publicos.items(), key=lambda item: item[0].lower()):
        tipo = _tipo_do_grupo(grupo)
        grupos[tipo[0] if tipo else TIPO_PAINEL[0]]["cards"].append(_card(nome, grupo, objetos))
    for grupo in grupos.values():
        grupo["cards"].sort(key=lambda c: (c["titulo"].lower(), c["detalhe"].lower(), c["nome"]))
        grupo["quantos"] = len(grupo["cards"])
        _marcar_ocultos(grupo["cards"])
    cards_provisorios = [
        _card(nome, grupo, objetos, provisoria=True)
        for nome, grupo in sorted(provisorias.items(), key=lambda item: item[0].lower())
        if e_publico(grupo)
    ]
    cards_provisorios.sort(key=lambda c: (c["titulo"].lower(), c["detalhe"].lower()))
    _marcar_ocultos(cards_provisorios)
    return {
        "grupos": [g for g in grupos.values() if g["cards"]],
        "faltando": len(publicos),
        "provisorias": cards_provisorios,
        "grupo_provisorias": {"chave": "provisorias", "titulo": "Com foto provisória", "icone": "bi-life-preserver"},
        "privados": [{"titulo": titulo, "quantos": quantos} for titulo, quantos in privados.items()],
        "privados_total": sum(privados.values()),
        "por_vez": POR_VEZ,
    }
