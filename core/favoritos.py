"""Curtidas e lista de desejos de brinquedos e peças.

Regras que o resto do sistema pode confiar:

* não exige login -- sem conta o registro fica no dispositivo, que é uma
  chave anônima gravada em cookie no site e enviada pelo cabeçalho
  ``X-Dispositivo`` no aplicativo;
* uma curtida por dispositivo enquanto visitante;
* ao entrar na conta o que estava no dispositivo migra para o usuário e
  passa a valer uma por conta, mesmo trocando de aparelho;
* curtir de novo desfaz a curtida (o mesmo vale para a lista de desejos).
"""

from __future__ import annotations

import uuid

from django.db import IntegrityError, transaction
from django.db.models import Count, Q

from .models import Brinquedos, Favorito, PecasReposicao


COOKIE_DISPOSITIVO = "ls_dispositivo"
CABECALHO_DISPOSITIVO = "HTTP_X_DISPOSITIVO"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365 * 2  # dois anos

TIPOS_VALIDOS = {Favorito.Tipo.CURTIDA, Favorito.Tipo.DESEJO}

# Quem chama passa "brinquedo" ou "peca"; o resto do módulo trabalha
# sempre com o objeto, nunca com a string.
MODELOS_POR_PRODUTO = {
    "brinquedo": Brinquedos,
    "peca": PecasReposicao,
}


class ProdutoInvalido(ValueError):
    """Tipo de produto que não existe no catálogo."""


class TipoInvalido(ValueError):
    """Interação que não é curtida nem lista de desejos."""


# ------------------------------------------------------------------
# Dispositivo
# ------------------------------------------------------------------

def _limpar_chave(valor: str | None) -> str:
    """Aceita só o formato que nós mesmos geramos: 32 hexadecimais."""
    chave = (valor or "").strip().lower()
    if len(chave) != 32:
        return ""
    if not all(c in "0123456789abcdef" for c in chave):
        return ""
    return chave


def chave_dispositivo(request) -> str:
    """Chave do aparelho, criando uma nova quando ainda não existe.

    A chave nova fica marcada no request para o ``aplicar_cookie`` gravar
    na resposta -- assim o visitante mantém as curtidas ao voltar.
    """
    ja_resolvida = getattr(request, "_ls_dispositivo", "")
    if ja_resolvida:
        return ja_resolvida

    chave = _limpar_chave(request.META.get(CABECALHO_DISPOSITIVO))
    if not chave:
        chave = _limpar_chave(request.COOKIES.get(COOKIE_DISPOSITIVO))

    if not chave:
        chave = uuid.uuid4().hex
        request._ls_dispositivo_novo = True

    request._ls_dispositivo = chave
    return chave


def aplicar_cookie(request, response):
    """Grava o cookie do aparelho quando a chave acabou de nascer."""
    if not getattr(request, "_ls_dispositivo_novo", False):
        return response

    response.set_cookie(
        COOKIE_DISPOSITIVO,
        getattr(request, "_ls_dispositivo", ""),
        max_age=COOKIE_MAX_AGE,
        samesite="Lax",
        secure=request.is_secure(),
        httponly=False,  # o app híbrido também lê a chave pelo JS
    )
    return response


# ------------------------------------------------------------------
# Leitura
# ------------------------------------------------------------------

def normalizar_tipo(valor: str | None) -> str:
    tipo = (valor or "").strip().lower()
    if tipo not in TIPOS_VALIDOS:
        raise TipoInvalido(f"Tipo de favorito desconhecido: {valor!r}")
    return tipo


def buscar_produto(tipo_produto: str, produto_id):
    """Devolve o brinquedo ou a peça da vitrine, ou levanta ProdutoInvalido."""
    modelo = MODELOS_POR_PRODUTO.get((tipo_produto or "").strip().lower())
    if modelo is None:
        raise ProdutoInvalido(f"Produto desconhecido: {tipo_produto!r}")

    # Para peça, `ativo` não é mais a pergunta toda: item de manutenção
    # fica fora da vitrine mesmo ativo, e o que não está na vitrine não
    # tem como ser curtido -- ninguém chegou a vê-lo. Ver
    # `PecasReposicao.da_vitrine`.
    consulta = (
        PecasReposicao.da_vitrine()
        if modelo is PecasReposicao
        else modelo.objects.filter(ativo=True)
    )
    try:
        return consulta.get(pk=produto_id)
    except (modelo.DoesNotExist, ValueError, TypeError) as erro:
        raise ProdutoInvalido("Produto não encontrado.") from erro


def _campo_do_produto(produto) -> str:
    if isinstance(produto, Brinquedos):
        return "brinquedo"
    if isinstance(produto, PecasReposicao):
        return "peca"
    raise ProdutoInvalido("Só brinquedos e peças aceitam curtida.")


def usuario_logado(request):
    """Usuário da requisição, ou None.

    Na API o projeto usa ``UNAUTHENTICATED_USER = None``: visitante chega
    com ``request.user`` valendo None, não AnonymousUser. Todo o módulo
    passa por aqui para não quebrar no app.
    """
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return None
    return usuario


def filtro_do_visitante(request) -> Q:
    """Restringe a consulta ao dono atual: conta logada ou aparelho."""
    usuario = usuario_logado(request)
    if usuario is not None:
        return Q(usuario=usuario)
    return Q(usuario__isnull=True, dispositivo=chave_dispositivo(request))


def meus_favoritos(request, tipo: str | None = None):
    consulta = Favorito.objects.filter(filtro_do_visitante(request))
    if tipo:
        consulta = consulta.filter(tipo=normalizar_tipo(tipo))
    return consulta


def ids_marcados(request, tipo: str) -> dict[str, set[int]]:
    """IDs que o visitante já marcou, para pintar os corações da listagem."""
    marcados = {"brinquedo": set(), "peca": set()}
    linhas = meus_favoritos(request, tipo).values_list("brinquedo_id", "peca_id")
    for brinquedo_id, peca_id in linhas:
        if brinquedo_id:
            marcados["brinquedo"].add(brinquedo_id)
        elif peca_id:
            marcados["peca"].add(peca_id)
    return marcados


def total_curtidas(produto) -> int:
    campo = _campo_do_produto(produto)
    return Favorito.objects.filter(
        tipo=Favorito.Tipo.CURTIDA,
        **{campo: produto},
    ).count()


def contagem_curtidas(produtos) -> dict[int, int]:
    """Curtidas por id, em uma consulta só, para listagens."""
    produtos = list(produtos)
    if not produtos:
        return {}

    campo = _campo_do_produto(produtos[0])
    linhas = (
        Favorito.objects
        .filter(
            tipo=Favorito.Tipo.CURTIDA,
            **{f"{campo}__in": produtos},
        )
        .values(f"{campo}_id")
        .annotate(total=Count("id"))
    )
    return {linha[f"{campo}_id"]: linha["total"] for linha in linhas}


def estado_do_produto(request, produto) -> dict:
    """Como o visitante vê este produto agora: curtido, desejado, total."""
    campo = _campo_do_produto(produto)
    meus = set(
        Favorito.objects
        .filter(filtro_do_visitante(request), **{campo: produto})
        .values_list("tipo", flat=True)
    )
    return {
        "produto": campo,
        "produto_id": produto.pk,
        "curtido": Favorito.Tipo.CURTIDA in meus,
        "desejado": Favorito.Tipo.DESEJO in meus,
        "curtidas": total_curtidas(produto),
    }


# ------------------------------------------------------------------
# Escrita
# ------------------------------------------------------------------

def alternar(request, tipo: str, produto, origem: str = Favorito.Origem.SITE) -> dict:
    """Marca ou desmarca. Devolve o estado final já recalculado."""
    tipo = normalizar_tipo(tipo)
    campo = _campo_do_produto(produto)
    dispositivo = chave_dispositivo(request)

    existentes = Favorito.objects.filter(
        filtro_do_visitante(request),
        tipo=tipo,
        **{campo: produto},
    )

    if existentes.exists():
        existentes.delete()
        estado = estado_do_produto(request, produto)
        estado["marcado"] = False
        estado["tipo"] = tipo
        # Descurtir devolve o ponto: sem isso, curtir e descurtir em
        # sequência seria uma fábrica de pontos.
        _pontuar(request)
        return estado

    dados = {
        "tipo": tipo,
        campo: produto,
        "dispositivo": dispositivo,
        "origem": (
            Favorito.Origem.APP
            if origem == Favorito.Origem.APP
            else Favorito.Origem.SITE
        ),
        "usuario": usuario_logado(request),
    }

    try:
        with transaction.atomic():
            Favorito.objects.create(**dados)
    except IntegrityError:
        # Corrida entre duas abas: o registro já existe e é o que importa.
        pass

    estado = estado_do_produto(request, produto)
    estado["marcado"] = True
    estado["tipo"] = tipo
    _pontuar(request)
    return estado


def _pontuar(request) -> None:
    """Recalcula os pontos de quem está logado, se houver alguém.

    Import local porque `core.pontos` importa os modelos e este módulo é
    carregado cedo -- no topo, o ciclo se fecha.
    """
    usuario = usuario_logado(request)
    if usuario is None:
        return

    from . import pontos

    pontos.sincronizar(usuario)


def migrar_dispositivo_para_conta(usuario, dispositivo: str) -> int:
    """Leva as marcações anônimas do aparelho para a conta que entrou.

    O que a conta já tinha vence: o registro repetido do aparelho é
    descartado, senão a restrição de uma marcação por conta bloquearia o
    login inteiro.
    """
    dispositivo = _limpar_chave(dispositivo)
    if usuario is None or not usuario.is_authenticated or not dispositivo:
        return 0

    anonimos = Favorito.objects.filter(
        usuario__isnull=True,
        dispositivo=dispositivo,
    )
    if not anonimos.exists():
        return 0

    ja_na_conta = {
        (tipo, brinquedo_id, peca_id)
        for tipo, brinquedo_id, peca_id in Favorito.objects
        .filter(usuario=usuario)
        .values_list("tipo", "brinquedo_id", "peca_id")
    }

    migrados = 0
    repetidos = []
    for favorito in anonimos:
        chave = (favorito.tipo, favorito.brinquedo_id, favorito.peca_id)
        if chave in ja_na_conta:
            repetidos.append(favorito.pk)
            continue
        ja_na_conta.add(chave)
        favorito.usuario = usuario
        favorito.save(update_fields=["usuario", "atualizado"])
        migrados += 1

    if repetidos:
        Favorito.objects.filter(pk__in=repetidos).delete()

    # O que a pessoa curtiu antes de entrar também vale ponto: a conta
    # recebe o crédito no mesmo instante em que recebe as marcações.
    from . import pontos

    pontos.sincronizar(usuario)

    return migrados
