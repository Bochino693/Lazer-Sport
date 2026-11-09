"""Monte seu projeto (/monte-seu-projeto/): o cliente monta o espaço dele em 3D.

O cliente diz SÓ o tamanho do lugar (largura × comprimento e, se quiser, o
pé-direito) e escolhe o modelo do espaço (o principal: um espaço esportivo
kids, um brinquedão, uma área baby... sob medida ou um dos prontos da
fábrica), as outras áreas e as máquinas do catálogo. O arrumador
(core/static/site/projeto3d/arrumador.js) põe tudo na planta, com o
corredor de 1,20 m até cada coisa, e diz o que não coube e por quê; a
página desenha o 3D (as áreas sob medida pelo mesmo projetista do painel,
as máquinas pelo .glb delas ou, sem ele, por um mini 3D na medida, com a
foto). "Pedir este projeto" grava um PedidoProjeto3D, que a equipe abre no
painel (Comercial > Projetos 3D do site) no mesmo 3D.

AS REGRAS MORAM AQUI, e não no JavaScript: o tamanho mínimo, ideal e
máximo de cada área sob medida, a faixa de segurança em volta, o
pé-direito que cada uma pede e o lugar de quem joga na frente de cada
máquina. A página recebe tudo em JSON; o painel, o mesmo; os testes leem
daqui. São números do ramo (os catálogos de playground indoor, a NBR 16071
dos playgrounds, a NBR 9050 das rotas acessíveis) para um RASCUNHO: o
projeto final é da engenharia da fábrica.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from . import arena

# ======================================================================
# AS ÁREAS SOB MEDIDA (o projetista do painel desenha o miolo)
# ======================================================================

#: Cada área: o nome, o ícone (Font Awesome do site), o tamanho do miolo em
#: metros (largura × profundidade: mínimo, ideal e máximo), a faixa livre em
#: volta (de queda, de segurança), o pé-direito que pede e onde prefere ficar.
#: `projetista` é o tipo do gerador (sistema_interno/static/interno/montar3d-gerador.js).
AREAS = {
    "esportivo": {
        "nome": "Espaço esportivo kids",
        "sub": "Quadra com traves e tabelas na altura das crianças, tela de proteção, parede de escalada e camas elásticas.",
        "icone": "fa-futbol",
        "min": (7.0, 5.0), "ideal": (18.0, 10.0), "max": (36.0, 22.0),
        "seguranca": 0.3, "pe_direito_minimo": 3.0,
        "prefere": "canto",
    },
    "brinquedao": {
        "nome": "Brinquedão",
        "sub": "Playground indoor em torres: pisos, redes, tobogã, piscina de bolinhas, rolos e túneis.",
        "icone": "fa-cubes-stacked",
        "min": (4.0, 2.5), "ideal": (6.5, 3.25), "max": (12.0, 6.0),
        "seguranca": 1.0, "pe_direito_minimo": 2.6,
        "prefere": "canto",
    },
    "baby": {
        "nome": "Área baby",
        "sub": "De 0 a 3 anos, tudo baixo: piso de EVA, cerca, piscina rasa, rampa e escorregador pequeno.",
        "icone": "fa-baby",
        "min": (3.0, 3.0), "ideal": (5.0, 4.0), "max": (8.0, 6.0),
        "seguranca": 0.4, "pe_direito_minimo": 2.2,
        # perto da entrada: os pais ficam de olho e os pequenos não cruzam o espaço
        "prefere": "perto_da_entrada",
    },
    "trampolim": {
        "nome": "Trampolim park",
        "sub": "Camas elásticas em grade, piscina de espuma e pista de enterrada, com tela em volta.",
        "icone": "fa-arrows-up-down",
        "min": (5.5, 5.5), "ideal": (14.0, 9.0), "max": (30.0, 20.0),
        "seguranca": 0.6, "pe_direito_minimo": 4.0,
        "prefere": "canto",
    },
    "ninja": {
        "nome": "Área ninja",
        "sub": "Circuito de obstáculos sobre colchões: degraus, trave, argolas, barra de macaco, corda e parede curva.",
        "icone": "fa-person-running",
        "min": (7.0, 2.5), "ideal": (16.0, 5.0), "max": (24.0, 8.0),
        "seguranca": 0.8, "pe_direito_minimo": 3.0,
        "prefere": "canto",
    },
}

#: O principal pode ser "só máquinas" (um espaço de fliperamas, sem área no meio).
SO_MAQUINAS = "maquinas"

#: Os estilos do projetista (os mesmos do painel).
ESTILOS = ("colorido", "neon", "selva")

#: As cores raiz do projetista (as do painel).
CORES = (
    "#2563eb", "#0ea5e9", "#14b8a6", "#22c55e", "#84cc16", "#facc15", "#f97316", "#ef4444",
    "#ec4899", "#a855f7", "#7c3aed", "#1e3a8a",
)

#: Que área cada brinquedo grande do catálogo é (o modelo pronto daquela área).
AREA_DO_DESENHO = {"playground": "brinquedao", "cama_elastica": "trampolim"}

# ======================================================================
# O LUGAR DE CADA MÁQUINA
# ======================================================================

#: O lugar de quem joga (em metros), por desenho (core/arena.py): `frente`,
#: `tras`, `lados` ou `todos` (a faixa em volta), e se a máquina fica de
#: costas para a PAREDE (as de gabinete) ou solta no meio (as mesas, o
#: carrossel). A frente da máquina é o lado de quem joga.
USO_POR_DESENHO = {
    "fliperama": {"frente": 0.9, "parede": True},
    "pinball": {"frente": 0.8, "parede": True},
    "garra": {"frente": 0.8, "parede": True},
    "musica": {"frente": 1.2, "parede": True},
    "simulador": {"frente": 0.7, "parede": True},
    "tiro": {"frente": 1.2, "parede": True},
    "boxe": {"frente": 1.5, "lados": 0.4, "parede": True},
    "basquete": {"frente": 1.0, "parede": True},
    "boliche": {"frente": 1.0, "parede": True},
    "futebol": {"frente": 1.5, "parede": True},
    # o colchão de queda na frente da parede
    "escalada": {"frente": 2.0, "parede": True},
    "montaria": {"frente": 0.6, "lados": 0.2, "parede": True},
    # as mesas: no hockey joga-se nas pontas; no pebolim, nos lados compridos
    "hockey": {"frente": 0.9, "tras": 0.9, "lados": 0.3, "parede": False},
    "pebolim": {"lados": 0.8, "frente": 0.3, "tras": 0.3, "parede": False},
    "carrossel": {"todos": 1.0, "parede": False},
    "touro": {"todos": 1.2, "parede": False},
    "cama_elastica": {"todos": 1.0, "parede": False},
    "playground": {"todos": 1.0, "parede": False},
}

#: Os desenhos que são BRINQUEDO GRANDE (a lista dos grandes, à parte das máquinas).
DESENHOS_GRANDES = {"playground", "cama_elastica"}

#: Os limites do que se aceita no pedido (o resto é erro de digitação ou abuso).
LIMITES = {
    "largura": (3, 150), "comprimento": (3, 150), "pe_direito": (2, 20),
    "itens": 60, "qtd": 30, "areas": 5,
}


def _uso(desenho):
    """O lugar de quem joga desta máquina, como o arrumador lê."""
    regra = dict(USO_POR_DESENHO.get(desenho) or USO_POR_DESENHO[arena.PADRAO])
    parede = bool(regra.pop("parede", True))
    return regra, parede


def item_do_catalogo(dados):
    """Uma máquina ou brinquedo grande do catálogo (o dicionário da arena) para o arrumador.

    A medida é a do .glb quando há objeto 3D (é o que se desenha); sem ele,
    a do cadastro ou a do desenho (core/arena.py, medidas_para_3d).
    """
    medidas = dados.get("medidas_modelo") or []
    if len(medidas) != 3:
        medidas = dados.get("medidas") or []
    medidas = [round(float(v), 3) for v in medidas] if len(medidas) == 3 else list(arena.MEDIDAS_PADRAO[arena.PADRAO])
    desenho = dados.get("desenho") or arena.PADRAO
    if str(dados["id"]).startswith("modelo-"):
        # o objeto do site fora do catálogo vem como "playground": o nome diz o que é
        desenho = arena.modelo_3d(dados["nome"], dados.get("categorias") or ())
    grande = desenho in DESENHOS_GRANDES or dados.get("grupo") in ("brinquedoes", "esportivos") or bool(dados.get("reino"))
    if grande:
        # o brinquedo grande fica solto, com a faixa de segurança (de queda) em volta
        uso, parede = {"todos": 1.0}, False
    else:
        uso, parede = _uso(desenho)
    return {
        "id": str(dados["id"]),
        "nome": dados["nome"],
        "desenho": desenho,
        "tipo": "grande" if grande else "maquina",
        # o modelo pronto de qual área (o Brinquedão Ninja é um brinquedão; o Espaço Esportivo, um esportivo)
        "area": "esportivo" if dados.get("reino") or dados.get("grupo") == "esportivos" else AREA_DO_DESENHO.get(desenho, "brinquedao" if grande else ""),
        "medidas": medidas,
        "medidas_reais": bool(dados.get("medidas_reais")) or len(dados.get("medidas_modelo") or []) == 3,
        "modelo": dados.get("modelo") or "",
        "capa": dados.get("capa") or "",
        "categorias": list(dados.get("categorias") or []),
        "jogo": dados.get("jogo") or "",
        "uso": uso,
        "parede": parede,
    }


def catalogo():
    """O que a página e o painel mandam para o arrumador: as áreas e os itens do catálogo.

    Os itens são as máquinas e os brinquedos ativos (com as medidas e o 3D
    da arena) e os objetos 3D do site que ainda não estão no catálogo.
    """
    from .views_arena import brinquedos_da_arena

    dados = [arena.dados_do_brinquedo(b, "") for b in brinquedos_da_arena()]
    dados += arena.modelos_fora_do_catalogo(dados)
    itens = sorted((item_do_catalogo(d) for d in dados), key=lambda i: (i["tipo"] != "maquina", arena._normalizar(i["nome"])))
    return {
        "areas": {
            chave: {**a, "min": list(a["min"]), "ideal": list(a["ideal"]), "max": list(a["max"])}
            for chave, a in AREAS.items()
        },
        "itens": itens,
        "estilos": list(ESTILOS),
        "cores": list(CORES),
    }


# ======================================================================
# O PEDIDO
# ======================================================================

class PedidoInvalido(ValueError):
    """O pedido não pode ser gravado; a mensagem diz o que corrigir (vai para o cliente)."""


def _numero(valor, campo, minimo, maximo, obrigatorio=True):
    if valor in (None, "") and not obrigatorio:
        return None
    try:
        numero = Decimal(str(valor).replace(",", "."))
    except (InvalidOperation, ValueError):
        raise PedidoInvalido(f"Informe {campo} em metros.")
    if not numero.is_finite() or numero < minimo or numero > maximo:
        raise PedidoInvalido(f"{campo.capitalize()} tem de ficar entre {minimo} e {maximo} m.")
    return numero.quantize(Decimal("0.01"))


def _texto(valor, limite):
    return re.sub(r"\s+", " ", str(valor or "")).strip()[:limite]


def _resumo(bruto):
    """O que coube e o que ficou de fora, como a página contou (só textos e números curtos)."""
    if not isinstance(bruto, dict):
        return {}

    def lista(chave, campos):
        saida = []
        for linha in (bruto.get(chave) or [])[:120]:
            if isinstance(linha, dict):
                saida.append({c: _texto(linha.get(c), 200) for c in campos if linha.get(c) not in (None, "")})
        return saida

    numeros = {}
    for chave, valor in (bruto.get("numeros") or {}).items():
        if chave in ("area", "ocupada", "uso", "livre", "ocupacao") and isinstance(valor, (int, float)):
            numeros[chave] = round(float(valor), 2)
    sugestao = bruto.get("espaco_para_tudo")
    return {
        "coube": lista("coube", ("nome", "qtd")),
        "ficou_de_fora": lista("ficou_de_fora", ("nome", "motivo")),
        "numeros": numeros,
        "espaco_para_tudo": (
            {k: round(float(sugestao[k]), 2) for k in ("largura", "comprimento") if isinstance(sugestao.get(k), (int, float))}
            if isinstance(sugestao, dict) else {}
        ),
    }


def validar_pedido(dados, catalogo_atual):
    """Confere o pedido que a página mandou e devolve os campos do PedidoProjeto3D.

    Levanta PedidoInvalido com o que o cliente tem de corrigir. A escolha é
    guardada como chegou depois de conferida (só o que o catálogo tem), para
    o painel refazer o mesmo 3D.
    """
    if not isinstance(dados, dict):
        raise PedidoInvalido("Pedido em formato inválido.")
    contato = dados.get("contato") or {}
    nome = _texto(contato.get("nome"), 120)
    if len(nome) < 2:
        raise PedidoInvalido("Diga o seu nome.")
    whatsapp = re.sub(r"\D", "", str(contato.get("whatsapp") or ""))
    if not 10 <= len(whatsapp) <= 13:
        raise PedidoInvalido("Informe o WhatsApp com DDD (só números).")
    email = _texto(contato.get("email"), 254)
    if email:
        try:
            validate_email(email)
        except ValidationError:
            raise PedidoInvalido("O e-mail não parece certo.")

    espaco = dados.get("espaco") or {}
    largura = _numero(espaco.get("largura"), "a largura", *LIMITES["largura"])
    comprimento = _numero(espaco.get("comprimento"), "o comprimento", *LIMITES["comprimento"])
    pe_direito = _numero(espaco.get("pe_direito"), "o pé-direito", *LIMITES["pe_direito"], obrigatorio=False)

    escolha = dados.get("escolha") or {}
    ids = {i["id"]: i for i in catalogo_atual["itens"]}
    principal = escolha.get("principal") or {}
    if principal.get("tipo") == "area" and principal.get("area") in AREAS:
        principal = {"tipo": "area", "area": principal["area"]}
        principal_nome = AREAS[principal["area"]]["nome"] + " (sob medida)"
    elif principal.get("tipo") == "item" and str(principal.get("id")) in ids:
        principal = {"tipo": "item", "id": str(principal["id"])}
        principal_nome = ids[principal["id"]]["nome"]
    else:
        principal, principal_nome = None, "Só máquinas"
    areas = [a for a in dict.fromkeys(escolha.get("areas") or []) if a in AREAS][: LIMITES["areas"]]
    itens = []
    for linha in (escolha.get("itens") or [])[: LIMITES["itens"]]:
        if not isinstance(linha, dict) or str(linha.get("id")) not in ids:
            continue
        try:
            qtd = int(linha.get("qtd") or 0)
        except (TypeError, ValueError):
            continue
        if qtd > 0:
            itens.append({"id": str(linha["id"]), "qtd": min(qtd, LIMITES["qtd"])})
    if not principal and not areas and not itens:
        raise PedidoInvalido("Escolha o modelo do espaço ou ao menos uma máquina.")
    estilo = escolha.get("estilo") if escolha.get("estilo") in ESTILOS else "colorido"
    cor = escolha.get("cor") if re.fullmatch(r"#[0-9a-fA-F]{6}", str(escolha.get("cor") or "")) else CORES[0]
    try:
        semente = max(1, min(2_000_000_000, int(escolha.get("semente") or 1)))
    except (TypeError, ValueError):
        semente = 1

    return {
        "nome": nome,
        "whatsapp": whatsapp,
        "email": email,
        "cidade": _texto(contato.get("cidade"), 80),
        "mensagem": str(contato.get("mensagem") or "").strip()[:1500],
        "largura": largura,
        "comprimento": comprimento,
        "pe_direito": pe_direito,
        "principal": principal_nome[:150],
        "estilo": estilo,
        "cor": cor.lower(),
        "semente": semente,
        "escolhas": {"principal": principal, "areas": areas, "itens": itens, "estilo": estilo, "cor": cor.lower(), "semente": semente},
        "resumo": _resumo(dados.get("resumo")),
    }
