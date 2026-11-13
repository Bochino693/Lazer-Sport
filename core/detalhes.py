"""A ficha completa de cada objeto das telas de gestão, sob demanda.

A LISTA CARREGA LEVE; O DETALHE VEM QUANDO ALGUÉM PEDE. Uma lista de
brinquedos que já trouxesse os orçamentos, os pedidos e as curtidas de
cada um pagaria dezenas de consultas que ninguém vai olhar. Aqui cada ficha
é montada quando a pessoa toca no item, com um número de consultas que não
cresce com o histórico do objeto (agregados e listas com limite).

UMA FORMA SÓ PARA TODOS OS TIPOS. A ficha é uma lista de SEÇÕES, e cada
seção tem campos (rótulo e valor), etiquetas, fotos ou uma lista de linhas.
O modal (core/static/site/paginas/gestao-analises.js) desenha qualquer uma
delas do mesmo jeito; o que muda de um tipo para outro é só o que entra.

A ATIVIDADE é a linha do tempo do objeto -- pedidos, orçamentos, visitas,
curtidas, acessos --, montada de várias tabelas e paginada: cada fonte
traz só o bastante para a página pedida, e a mistura é ordenada aqui.

NOME DE CLIENTE SÓ PARA QUEM É DO COMERCIAL. A ficha de um brinquedo é
aberta pela equipe de Criação, que não precisa saber para quem cada proposta
foi feita: o número e a situação aparecem, o nome do cliente não.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.db.models import Count, Max, Q, Sum
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from .formatos import dinheiro as _dinheiro

POR_PAGINA = 12
PAGINA_MAXIMA = 25
PEDIDO_PAGO = ("pago", "em_preparacao", "saiu_entrega", "finalizado")


class NaoEncontrado(LookupError):
    pass


# ----------------------------------------------------------------------
# formatação
# ----------------------------------------------------------------------

def reais(valor):
    return _dinheiro(valor or 0, prefixo="R$ ")


def quando(valor):
    if not valor:
        return "—"
    if isinstance(valor, dt.datetime):
        return f"{timezone.localtime(valor):%d/%m/%Y às %H:%M}"
    return f"{valor:%d/%m/%Y}"


def campo(rotulo, valor, icone=None, tom=None):
    if valor in (None, ""):
        valor = "—"
    return {"rotulo": rotulo, "valor": str(valor), "icone": icone, "tom": tom}


def selo(texto, tom="neutro", icone=None):
    return {"texto": texto, "tom": tom, "icone": icone}


def secao(titulo, icone=None, **conteudo):
    return {"titulo": titulo, "icone": icone, **{k: v for k, v in conteudo.items() if v not in (None, [], "")}}


def evento(momento, titulo, texto="", icone="bi-dot", tom="neutro"):
    return {"momento": momento, "titulo": titulo, "texto": texto, "icone": icone, "tom": tom}


def _url_imagem(arquivo):
    try:
        return arquivo.url if arquivo else None
    except Exception:  # noqa: BLE001 -- armazenamento fora do ar: a ficha segue sem a foto
        return None


def _link(nome, *args):
    try:
        return reverse(nome, args=args)
    except NoReverseMatch:
        return None


def _numero(valor):
    return f"{int(valor or 0):,}".replace(",", ".")


STATUS_PEDIDO = {
    "aguardando_pagamento": ("Aguardando pagamento", "atencao", "bi-hourglass-split"),
    "pago": ("Pago", "bom", "bi-check2-circle"),
    "em_preparacao": ("Em preparação", "bom", "bi-box-seam"),
    "saiu_entrega": ("Saiu para entrega", "bom", "bi-truck"),
    "finalizado": ("Finalizado", "bom", "bi-bag-check"),
    "cancelado": ("Cancelado", "ruim", "bi-x-circle"),
}


def _status_pedido(codigo):
    return STATUS_PEDIDO.get(codigo, (codigo or "—", "neutro", "bi-bag"))


def _status_orcamento(orcamento):
    tons = {"aprovado": "bom", "recusado": "ruim", "expirado": "ruim", "substituido": "neutro"}
    return orcamento.get_status_display(), tons.get(orcamento.status, "atencao")


# ----------------------------------------------------------------------
# a atividade: várias fontes, uma linha do tempo
# ----------------------------------------------------------------------

def paginar_atividade(fontes, pagina=1):
    """`fontes`: funções (limite) -> lista de eventos. Devolve a página pedida."""
    pagina = max(1, min(int(pagina or 1), PAGINA_MAXIMA))
    limite = pagina * POR_PAGINA + 1
    todos = []
    for fonte in fontes:
        todos.extend(e for e in fonte(limite) if e["momento"])
    todos.sort(key=lambda e: e["momento"], reverse=True)
    inicio = (pagina - 1) * POR_PAGINA
    pedaco = todos[inicio:inicio + POR_PAGINA]
    agora = timezone.now()
    itens = []
    for item in pedaco:
        momento = item["momento"]
        if isinstance(momento, dt.date) and not isinstance(momento, dt.datetime):
            momento = timezone.make_aware(dt.datetime.combine(momento, dt.time(12)))
        itens.append({
            **item,
            "momento": momento.isoformat(),
            "quando": _relativo(momento, agora),
        })
    return {"itens": itens, "pagina": pagina, "tem_mais": len(todos) > inicio + POR_PAGINA}


def _relativo(momento, agora):
    passado = agora - momento
    local = timezone.localtime(momento)
    hoje = timezone.localtime(agora).date()
    if passado < dt.timedelta(minutes=1):
        return "agora"
    if passado < dt.timedelta(hours=1):
        return f"há {int(passado.total_seconds() // 60)} min"
    if local.date() == hoje:
        return f"hoje às {local:%H:%M}"
    if local.date() == hoje - dt.timedelta(days=1):
        return f"ontem às {local:%H:%M}"
    if local.year == hoje.year:
        return f"{local:%d/%m} às {local:%H:%M}"
    return f"{local:%d/%m/%Y}"


def _atividade_pedidos_do_item(tipo_item, objeto_ids):
    from .models import ItemPedido

    def fonte(limite):
        linhas = (
            ItemPedido.objects.filter(tipo_item=tipo_item, object_id__in=objeto_ids)
            .select_related("pedido")
            .order_by("-pedido__criacao", "-id")[:limite]
        )
        eventos = []
        for linha in linhas:
            rotulo, tom, icone = _status_pedido(linha.pedido.status)
            eventos.append(evento(
                linha.pedido.criacao, f"Pedido nº {linha.pedido_id} · {rotulo}",
                f"{linha.quantidade} × {linha.nome_item} · {reais(linha.subtotal)}", icone, tom,
            ))
        return eventos
    return fonte


def _atividade_orcamentos_do_item(campo, objeto_id, comercial):
    from sistema_interno.models import ItemOrcamento

    def fonte(limite):
        linhas = (
            ItemOrcamento.objects.filter(**{f"{campo}_id": objeto_id})
            .select_related("orcamento", "orcamento__cliente")
            .order_by("-orcamento__criacao", "-id")[:limite]
        )
        eventos = []
        for linha in linhas:
            orcamento = linha.orcamento
            rotulo, tom = _status_orcamento(orcamento)
            para = f" para {orcamento.destinatario}" if comercial else ""
            eventos.append(evento(
                orcamento.criacao, f"Orçamento nº {orcamento.pk}{para}",
                f"{rotulo} · {linha.quantidade} × {reais(linha.valor_unitario)}", "bi-file-earmark-text", tom,
            ))
        return eventos
    return fonte


def _atividade_favoritos(campo, objeto_id=None, usuario_id=None):
    from .models import Favorito

    def fonte(limite):
        consulta = Favorito.objects.select_related("usuario", "brinquedo", "peca")
        if objeto_id is not None:
            consulta = consulta.filter(**{f"{campo}_id": objeto_id})
        if usuario_id is not None:
            consulta = consulta.filter(usuario_id=usuario_id)
        eventos = []
        for fav in consulta.order_by("-criacao", "-id")[:limite]:
            quem = (fav.usuario.username if fav.usuario_id else f"visitante do {fav.get_origem_display().lower()}")
            verbo = "Curtiu" if fav.tipo == "curtida" else "Pôs na lista de desejos"
            alvo = fav.nome_produto if usuario_id is not None else quem
            eventos.append(evento(
                fav.criacao, f"{verbo}" if usuario_id is not None else ("Curtida" if fav.tipo == "curtida" else "Lista de desejos"),
                alvo, "bi-heart-fill" if fav.tipo == "curtida" else "bi-bookmark-heart", "bom",
            ))
        return eventos
    return fonte


def _atividade_interacoes(alvo, objeto_ids):
    from .models import InteracaoPorHora

    def fonte(limite):
        eventos = []
        linhas = (
            InteracaoPorHora.objects.filter(alvo=alvo, objeto_id__in=objeto_ids)
            .values("evento", "hora").annotate(n=Sum("quantidade")).order_by("-hora")[:limite]
        )
        for linha in linhas:
            local = timezone.localtime(linha["hora"])
            if linha["evento"] == "visita":
                titulo = f"{_numero(linha['n'])} visita{'s' if linha['n'] != 1 else ''}"
                icone = "bi-eye"
            else:
                titulo = f"{_numero(linha['n'])} no carrinho"
                icone = "bi-cart-plus"
            eventos.append(evento(linha["hora"], titulo, f"entre {local:%H}h e {(local + dt.timedelta(hours=1)):%H}h", icone))
        return eventos
    return fonte


# ----------------------------------------------------------------------
# os tipos
# ----------------------------------------------------------------------

def _numeros_do_produto(tipo_item, campo, objeto_id, cliques=None):
    """Curtidas, desejos, orçamentos e pedidos de um brinquedo ou peça: 3 consultas."""
    from sistema_interno.models import ItemOrcamento, Orcamento

    from .models import Favorito, ItemPedido

    favoritos = Favorito.objects.filter(**{f"{campo}_id": objeto_id}).aggregate(
        curtidas=Count("id", filter=Q(tipo="curtida")), desejos=Count("id", filter=Q(tipo="desejo")),
    )
    orcamentos = ItemOrcamento.objects.filter(**{f"{campo}_id": objeto_id}).exclude(
        orcamento__status=Orcamento.Status.SUBSTITUIDO,
    ).aggregate(
        total=Count("orcamento_id", distinct=True),
        aprovados=Count("orcamento_id", distinct=True, filter=Q(orcamento__status=Orcamento.Status.APROVADO)),
    )
    pedidos = ItemPedido.objects.filter(tipo_item=tipo_item, object_id=objeto_id, pedido__status__in=PEDIDO_PAGO).aggregate(
        n=Count("pedido_id", distinct=True), unidades=Sum("quantidade"), valor=Sum("subtotal"),
    )
    itens = []
    if cliques is not None:
        itens.append(campo_("Cliques (total histórico)", _numero(cliques), "bi-hand-index"))
    itens += [
        campo_("Curtidas", _numero(favoritos["curtidas"]), "bi-heart"),
        campo_("Lista de desejos", _numero(favoritos["desejos"]), "bi-bookmark-heart"),
        campo_("Em orçamentos", _numero(orcamentos["total"]), "bi-file-earmark-text"),
        campo_("Orçamentos aprovados", _numero(orcamentos["aprovados"]), "bi-check2-circle"),
        campo_("Pedidos pagos", f"{_numero(pedidos['n'])} · {_numero(pedidos['unidades'])} un. · {reais(pedidos['valor'])}", "bi-bag-check"),
    ]
    return secao("Números de sempre", "bi-123", campos=itens)


campo_ = campo


def detalhe_brinquedo(pk, usuario, pagina=1, so_atividade=False):
    from .models import BrinquedoClick, Brinquedos

    comercial = _comercial(usuario)
    if so_atividade:
        return _atividade_brinquedo(pk, comercial, pagina)
    try:
        b = (
            Brinquedos.objects.select_related("objeto_3d")
            .prefetch_related(
                "categorias_brinquedos", "tags", "estabelecimentos", "imagens_brinquedo",
                "variantes_adesivo", "promocoes", "promocoes_extras", "combos", "eventos_brinquedos",
            )
            .get(pk=pk)
        )
    except Brinquedos.DoesNotExist:
        raise NaoEncontrado
    cliques = BrinquedoClick.objects.filter(brinquedo_clicado_id=pk).aggregate(n=Sum("quantidade_click"))["n"]
    fotos = [u for u in (_url_imagem(f.imagem) for f in sorted(b.imagens_brinquedo.all(), key=lambda f: (f.ordem, f.id))) if u]
    capa = _url_imagem(b.imagem_brinquedo) or (fotos[0] if fotos else None)
    try:
        objeto_3d = b.objeto_3d
    except Exception:  # noqa: BLE001 -- sem 3D
        objeto_3d = None
    promocoes = {p.pk: p for p in list(b.promocoes.all()) + list(b.promocoes_extras.all())}
    hoje = timezone.localdate()

    selos = [
        selo("Ativo", "bom", "bi-check-circle") if b.ativo else selo("Desativado", "ruim", "bi-slash-circle"),
        selo("Na loja", "bom", "bi-shop") if b.exibir_na_loja else selo("Só orçamento", "neutro", "bi-file-earmark-text"),
    ]
    if objeto_3d:
        selos.append(selo("Tem 3D", "neutro", "bi-badge-3d"))

    secoes = [
        secao("Ficha", "bi-card-text", campos=[
            campo("Preço", reais(b.valor_brinquedo) if b.valor_brinquedo else "Sob orçamento", "bi-tag"),
            campo("Medidas (A × L × P)", b.dimensoes_m or "Não informadas", "bi-rulers"),
            campo("Volume", b.volume_formatado or "—", "bi-box"),
            campo("Voltagem", b.voltz, "bi-lightning-charge"),
            campo("Avaliação", f"{b.avaliacao:.1f}".replace(".", ",") if b.avaliacao is not None else "—", "bi-star"),
            campo("Cadastrado em", quando(b.criacao), "bi-calendar-plus"),
            campo("Atualizado em", quando(b.atualizado), "bi-pencil"),
        ], texto=b.descricao),
        secao("Categorias e tags", "bi-tags", etiquetas=[c.nome_categoria for c in b.categorias_brinquedos.all()] + [f"#{t.nome_tags}" for t in b.tags.all()]),
        secao("Fotos", "bi-images", fotos=fotos[:12]),
        secao("Adesivos", "bi-stickies", lista=_adesivos(b)),
        secao("Promoções com ele", "bi-tags-fill", lista=[
            {
                "titulo": p.descricao,
                "texto": (reais(p.preco_promocao) if p.preco_promocao else "Sem preço · condição")
                + (" · no ar" if p.ativo and (p.valida_ate is None or p.valida_ate >= hoje) else " · fora do ar"),
                "detalhe": {"tipo": "promocao", "id": p.pk},
            }
            for p in promocoes.values()
        ]),
        secao("Combos com ele", "bi-collection", lista=[
            {"titulo": c.descricao, "texto": reais(c.valor_combo), "detalhe": {"tipo": "combo", "id": c.pk}}
            for c in b.combos.all()
        ]),
        secao("Eventos", "bi-balloon", etiquetas=[e.titulo for e in b.eventos_brinquedos.all()]),
        secao("Parceiros onde está", "bi-geo-alt", etiquetas=[e.nome_estabelecimento for e in b.estabelecimentos.all()]),
        _numeros_do_produto("brinquedo", "brinquedo", pk, cliques=cliques or 0),
    ]
    if objeto_3d:
        secoes.insert(3, secao("Objeto 3D", "bi-badge-3d", campos=[
            campo("Arquivo", "enviado" if (objeto_3d.arquivo or objeto_3d.arquivo_estatico) else "sem arquivo", "bi-file-earmark"),
            campo("Medidas do objeto", " × ".join(str(m) for m in (objeto_3d.medidas or [])) or "—", "bi-rulers"),
        ]))
    return {
        "titulo": b.nome_brinquedo,
        "subtitulo": reais(b.valor_brinquedo) if b.valor_brinquedo else "Sob orçamento",
        "imagem": capa,
        "selos": selos,
        "secoes": secoes,
        "links": [{"rotulo": "Abrir no site", "url": _link("brinquedo_detalhe", pk), "externo": True}],
        "atividade": _atividade_brinquedo(pk, comercial, pagina),
    }


def _adesivos(brinquedo):
    """Cada arte do brinquedo: as fotos e o 3D são dela (VarianteAdesivo, LEIA-ME 72)."""
    fotos_por_variante = {}
    for foto in brinquedo.imagens_brinquedo.all():
        variante_id = getattr(foto, "variante_id", None)
        if variante_id:
            fotos_por_variante[variante_id] = fotos_por_variante.get(variante_id, 0) + 1
    linhas = []
    for variante in sorted(brinquedo.variantes_adesivo.all(), key=lambda v: (v.ordem, v.pk)):
        if not variante.ativo:
            continue
        partes = [f"{fotos_por_variante.get(variante.pk, 0)} foto(s)"]
        if getattr(variante, "arquivo_3d", None) or getattr(variante, "arquivo_estatico_3d", ""):
            partes.append("3D próprio")
        if getattr(variante, "padrao", False):
            partes.append("abre a página")
        linhas.append({"titulo": variante.nome, "texto": " · ".join(partes)})
    return linhas


def _nomes_dos_jogos(slugs):
    """slug -> nome do jogo (os da casa e os cadastrados pelo painel), numa consulta."""
    from . import arena
    from .models import JogoCadastrado

    nomes = {j["slug"]: j["titulo"] for j in arena.JOGOS if j["slug"] in slugs}
    if slugs:
        nomes.update(dict(JogoCadastrado.objects.filter(slug__in=list(slugs)).values_list("slug", "nome")))
    return nomes


ORIGEM_DA_JOGADA = {"pagina": "pela página do jogo", "emulador": "no emulador", "app": "pelo app do portal", "casa": "jogo da casa", "html": "jogo HTML5"}


def _atividade_jogadas(usuario_id=None, slug=None):
    """As jogadas com data (core/jogadas.py), da conta ou do jogo."""
    from .models import JogadaRegistrada

    def fonte(limite):
        consulta = JogadaRegistrada.objects.select_related("usuario")
        if usuario_id is not None:
            consulta = consulta.filter(usuario_id=usuario_id)
        if slug is not None:
            consulta = consulta.filter(jogo=slug)
        linhas = list(consulta.order_by("-quando", "-id")[:limite])
        nomes = _nomes_dos_jogos({j.jogo for j in linhas}) if usuario_id is not None else {}
        eventos = []
        for jogada in linhas:
            origem = ORIGEM_DA_JOGADA.get(jogada.origem, "")
            if usuario_id is not None:
                titulo = f"Jogou {nomes.get(jogada.jogo, jogada.jogo)}"
            elif jogada.usuario_id:
                titulo = f"{jogada.usuario.username} jogou" + (" (equipe)" if jogada.equipe else "")
            else:
                titulo = "Visitante sem conta jogou"
            eventos.append(evento(jogada.quando, titulo, origem, "bi-controller", "bom" if jogada.usuario_id else "neutro"))
        return eventos
    return fonte


def _atividade_brinquedo(pk, comercial, pagina):
    return paginar_atividade([
        _atividade_pedidos_do_item("brinquedo", [pk]),
        _atividade_orcamentos_do_item("brinquedo", pk, comercial),
        _atividade_favoritos("brinquedo", objeto_id=pk),
        _atividade_interacoes("brinquedo", [pk]),
    ], pagina)


def detalhe_peca(pk, usuario, pagina=1, so_atividade=False):
    from .models import PecasReposicao

    comercial = _comercial(usuario)

    def atividade(p):
        return paginar_atividade([
            _atividade_pedidos_do_item("pecas", [pk]),
            _atividade_orcamentos_do_item("peca", pk, comercial),
            _atividade_favoritos("peca", objeto_id=pk),
            _atividade_interacoes("peca", [pk]),
        ], p)

    if so_atividade:
        return atividade(pagina)
    try:
        peca = PecasReposicao.objects.prefetch_related("categoria_peca", "imagem_peca_reposicao").get(pk=pk)
    except PecasReposicao.DoesNotExist:
        raise NaoEncontrado
    fotos = [u for u in (_url_imagem(i.imagem) for i in peca.imagem_peca_reposicao.all()) if u]
    margem = None
    if peca.preco_venda and peca.preco_fornecedor:
        margem = f"{reais(peca.preco_venda - peca.preco_fornecedor)} por unidade"
    return {
        "titulo": peca.nome,
        "subtitulo": reais(peca.preco_venda) if peca.preco_venda else "Sem preço de venda",
        "imagem": fotos[0] if fotos else None,
        "selos": [
            selo("Ativa", "bom", "bi-check-circle") if peca.ativo else selo("Desativada", "ruim", "bi-slash-circle"),
            selo(peca.get_uso_display(), "neutro", "bi-tools"),
        ],
        "secoes": [
            secao("Ficha", "bi-card-text", campos=[
                campo("Preço de venda", reais(peca.preco_venda) if peca.preco_venda else "—", "bi-tag"),
                campo("Preço do fornecedor", reais(peca.preco_fornecedor) if peca.preco_fornecedor else "—", "bi-truck"),
                campo("Margem", margem, "bi-graph-up"),
                campo("Cadastrada em", quando(peca.criacao), "bi-calendar-plus"),
            ], texto=peca.descricao_peca),
            secao("Categorias", "bi-tags", etiquetas=[c.nome_categoria_peca for c in peca.categoria_peca.all()]),
            secao("Fotos", "bi-images", fotos=fotos[:12]),
            _numeros_do_produto("pecas", "peca", pk),
        ],
        "links": [{"rotulo": "Abrir no site", "url": _link("reposicao_detalhe", pk), "externo": True}] if peca.ativo else [],
        "atividade": atividade(pagina),
    }


def _pedidos_do_objeto(tipo_item, pk):
    from .models import ItemPedido

    numeros = ItemPedido.objects.filter(tipo_item=tipo_item, object_id=pk, pedido__status__in=PEDIDO_PAGO).aggregate(
        n=Count("pedido_id", distinct=True), unidades=Sum("quantidade"), valor=Sum("subtotal"),
    )
    return f"{_numero(numeros['n'])} · {_numero(numeros['unidades'])} un. · {reais(numeros['valor'])}"


def _visitas_registradas(alvo, pk):
    from .models import InteracaoPorHora

    numeros = InteracaoPorHora.objects.filter(alvo=alvo, objeto_id=pk).aggregate(
        visitas=Sum("quantidade", filter=Q(evento="visita")), carrinho=Sum("quantidade", filter=Q(evento="carrinho")),
    )
    return numeros["visitas"] or 0, numeros["carrinho"] or 0


def detalhe_promocao(pk, usuario, pagina=1, so_atividade=False):
    from .models import PromocaoClick, Promocoes

    def atividade(p):
        return paginar_atividade([_atividade_pedidos_do_item("promocao", [pk]), _atividade_interacoes("promocao", [pk])], p)

    if so_atividade:
        return atividade(pagina)
    try:
        promo = Promocoes.objects.select_related("brinquedos").prefetch_related("brinquedos_extras").get(pk=pk)
    except Promocoes.DoesNotExist:
        raise NaoEncontrado
    cliques = PromocaoClick.objects.filter(promocao_id=pk).aggregate(n=Sum("quantidade_click"))["n"] or 0
    visitas, carrinho = _visitas_registradas("promocao", pk)
    tabela = promo.preco_tabela
    return {
        "titulo": promo.descricao,
        "subtitulo": reais(promo.preco_promocao) if promo.preco_promocao else "Sem preço · condição",
        "imagem": _url_imagem(promo.imagem_promocao) or _url_imagem(getattr(promo.brinquedos, "imagem_brinquedo", None)),
        "selos": [
            selo("No ar", "bom", "bi-broadcast") if promo.vigente else selo("Fora do ar", "ruim", "bi-slash-circle"),
            *([selo(f"−{promo.desconto_percentual}%", "neutro", "bi-percent")] if promo.desconto_percentual else []),
        ],
        "secoes": [
            secao("Oferta", "bi-tag", campos=[
                campo("Preço da promoção", reais(promo.preco_promocao) if promo.preco_promocao else "Sem preço (condição)", "bi-tag"),
                campo("Preço “de”", reais(tabela) if tabela else "—", "bi-tag"),
                campo("Desconto", f"{promo.desconto_percentual}%" if promo.desconto_percentual else "—", "bi-percent"),
                campo("Válida até", quando(promo.valida_ate) if promo.valida_ate else "até ser desligada", "bi-calendar-event"),
                campo("Criada em", quando(promo.criacao), "bi-calendar-plus"),
            ]),
            secao("Condições", "bi-list-check", etiquetas=promo.lista_condicoes),
            secao("Brinquedos da promoção", "bi-joystick", lista=[
                {"titulo": b.nome_brinquedo, "texto": reais(b.valor_brinquedo) if b.valor_brinquedo else "sob orçamento",
                 "detalhe": {"tipo": "brinquedo", "id": b.pk}}
                for b in promo.todos_brinquedos
            ]),
            secao("Números de sempre", "bi-123", campos=[
                campo("Cliques (total histórico)", _numero(cliques), "bi-hand-index"),
                campo("Visitas registradas por hora", _numero(visitas), "bi-eye"),
                campo("No carrinho", _numero(carrinho), "bi-cart-plus"),
                campo("Pedidos pagos", _pedidos_do_objeto("promocao", pk), "bi-bag-check"),
            ]),
        ],
        "links": [{"rotulo": "Abrir no site", "url": _link("promocao", pk), "externo": True}],
        "atividade": atividade(pagina),
    }


def detalhe_combo(pk, usuario, pagina=1, so_atividade=False):
    from .models import ComboClick, Combos

    def atividade(p):
        return paginar_atividade([_atividade_pedidos_do_item("combo", [pk]), _atividade_interacoes("combo", [pk])], p)

    if so_atividade:
        return atividade(pagina)
    try:
        combo = Combos.objects.prefetch_related("brinquedos").get(pk=pk)
    except Combos.DoesNotExist:
        raise NaoEncontrado
    brinquedos = list(combo.brinquedos.all())
    soma = sum((b.valor_brinquedo or Decimal("0")) for b in brinquedos)
    economia = soma - (combo.valor_combo or 0) if soma else None
    cliques = ComboClick.objects.filter(combo_clicado_id=pk).aggregate(n=Sum("quantidade_click"))["n"] or 0
    visitas, carrinho = _visitas_registradas("combo", pk)
    return {
        "titulo": combo.descricao,
        "subtitulo": reais(combo.valor_combo),
        "imagem": _url_imagem(combo.imagem_combo),
        "selos": [selo("Ativo", "bom", "bi-check-circle") if combo.ativo else selo("Desativado", "ruim", "bi-slash-circle")],
        "secoes": [
            secao("Oferta", "bi-tag", campos=[
                campo("Preço do combo", reais(combo.valor_combo), "bi-tag"),
                campo("Soma de tabela", reais(soma) if soma else "—", "bi-calculator"),
                campo("Economia para o cliente", reais(economia) if economia and economia > 0 else "—", "bi-piggy-bank"),
                campo("Criado em", quando(combo.criacao), "bi-calendar-plus"),
            ]),
            secao("Brinquedos do combo", "bi-joystick", lista=[
                {"titulo": b.nome_brinquedo, "texto": reais(b.valor_brinquedo) if b.valor_brinquedo else "sob orçamento",
                 "detalhe": {"tipo": "brinquedo", "id": b.pk}}
                for b in brinquedos
            ]),
            secao("Números de sempre", "bi-123", campos=[
                campo("Cliques (total histórico)", _numero(cliques), "bi-hand-index"),
                campo("Visitas registradas por hora", _numero(visitas), "bi-eye"),
                campo("No carrinho", _numero(carrinho), "bi-cart-plus"),
                campo("Pedidos pagos", _pedidos_do_objeto("combo", pk), "bi-bag-check"),
            ]),
        ],
        "links": [{"rotulo": "Abrir no site", "url": _link("combo", pk), "externo": True}],
        "atividade": atividade(pagina),
    }


def detalhe_cupom(pk, usuario, pagina=1, so_atividade=False):
    from .models import Carrinho, Cupom, Pedido, ResgateCupom

    try:
        cupom = Cupom.objects.select_related("brinquedo", "categoria").get(pk=pk)
    except Cupom.DoesNotExist:
        raise NaoEncontrado
    pedidos = Pedido.objects.filter(cupom_codigo__iexact=cupom.codigo)

    def fonte_pedidos(limite):
        eventos = []
        for pedido in pedidos.select_related("cliente__user").order_by("-criacao", "-id")[:limite]:
            rotulo, tom, icone = _status_pedido(pedido.status)
            quem = pedido.cliente.user.username if (pedido.cliente_id and pedido.cliente.user_id) else "sem conta"
            eventos.append(evento(
                pedido.criacao, f"Pedido nº {pedido.pk} · {rotulo}",
                f"{quem} · desconto {reais(pedido.valor_desconto)} · total {reais(pedido.total_final)}", icone, tom,
            ))
        return eventos

    def atividade(p):
        return paginar_atividade([fonte_pedidos], p)

    if so_atividade:
        return atividade(pagina)

    numeros = pedidos.filter(status__in=PEDIDO_PAGO).aggregate(n=Count("id"), desconto=Sum("valor_desconto"), total=Sum("total_final"))
    em_carrinhos = Carrinho.objects.filter(cupom_id=pk).count()
    resgate = ResgateCupom.objects.filter(cupom_id=pk).select_related("usuario", "recompensa").first()
    clientes = list(cupom.cliente.select_related("user").all()[:12]) if not cupom.todos_usuarios else []
    agora = timezone.now()
    vencido = bool(cupom.data_expiracao and cupom.data_expiracao < agora)
    if cupom.brinquedo_id:
        escopo = f"Só o brinquedo {cupom.brinquedo.nome_brinquedo}"
    elif cupom.categoria_id:
        escopo = f"Só a categoria {cupom.categoria.nome_categoria}"
    else:
        escopo = "Toda a loja"
    selos = [
        selo("Vencido", "ruim", "bi-calendar-x") if vencido
        else (selo("Ativo", "bom", "bi-check-circle") if cupom.ativo else selo("Desativado", "ruim", "bi-slash-circle")),
        selo("Público" if cupom.todos_usuarios else "Exclusivo", "neutro", "bi-people" if cupom.todos_usuarios else "bi-person-lock"),
    ]
    if cupom.exibir_na_vitrine:
        selos.append(selo("Na vitrine de parceiros", "neutro", "bi-shop-window"))
    return {
        "titulo": cupom.codigo,
        "subtitulo": f"{cupom.desconto_percentual:.0f}% de desconto",
        "imagem": None,
        "icone": "bi-ticket-perforated",
        "selos": selos,
        "secoes": [
            secao("Regras", "bi-sliders", campos=[
                campo("Desconto", f"{cupom.desconto_percentual:.2f}%".replace(".", ","), "bi-percent"),
                campo("Vale para", escopo, "bi-bullseye"),
                campo("Quem pode usar", "Qualquer cliente" if cupom.todos_usuarios else f"{cupom.cliente.count()} cliente(s) escolhido(s)", "bi-people"),
                campo("Usos permitidos", cupom.quantidade_uso if cupom.quantidade_uso is not None else "sem limite", "bi-123"),
                campo("O mesmo cliente repete", "Sim" if cupom.reutilizavel else "Não", "bi-arrow-repeat"),
                campo("Expira em", quando(cupom.data_expiracao) if cupom.data_expiracao else "não expira", "bi-calendar-x"),
                campo("Criado em", quando(cupom.criacao), "bi-calendar-plus"),
            ]),
            secao("Clientes do cupom", "bi-person-lock", etiquetas=[
                (c.nome_completo or c.user.username) for c in clientes
            ]),
            secao("Números de sempre", "bi-123", campos=[
                campo("Usos em pedidos pagos", _numero(numeros["n"]), "bi-ticket-perforated"),
                campo("Desconto concedido", reais(numeros["desconto"]), "bi-percent"),
                campo("Total dos pedidos com ele", reais(numeros["total"]), "bi-currency-dollar"),
                campo("Aplicado em carrinhos agora", _numero(em_carrinhos), "bi-cart"),
                campo(
                    "Resgate por pontos",
                    f"{resgate.usuario.username} · {resgate.pontos_gastos} pontos · {quando(resgate.criacao)}" if resgate else "—",
                    "bi-stars",
                ),
            ]),
        ],
        "links": [],
        "atividade": atividade(pagina),
    }


def detalhe_evento(pk, usuario, pagina=1, so_atividade=False):
    from .models import Eventos, Favorito

    try:
        ev = Eventos.objects.prefetch_related("brinquedos", "imagens_evento").get(pk=pk)
    except Eventos.DoesNotExist:
        raise NaoEncontrado
    brinquedos = list(ev.brinquedos.all())
    ids = [b.pk for b in brinquedos]

    def atividade(p):
        return paginar_atividade([_atividade_pedidos_do_item("brinquedo", ids), _atividade_interacoes("brinquedo", ids)], p)

    if so_atividade:
        return atividade(pagina)
    fotos = [u for u in (_url_imagem(i.imagem) for i in ev.imagens_evento.all()) if u]
    curtidas = Favorito.objects.filter(brinquedo_id__in=ids, tipo="curtida").count() if ids else 0
    return {
        "titulo": ev.titulo,
        "subtitulo": f"{len(brinquedos)} brinquedo{'s' if len(brinquedos) != 1 else ''}",
        "imagem": fotos[0] if fotos else None,
        "selos": [],
        "secoes": [
            secao("Sobre o evento", "bi-balloon", texto=ev.descricao),
            secao("Fotos", "bi-images", fotos=fotos),
            secao("Brinquedos do evento", "bi-joystick", lista=[
                {"titulo": b.nome_brinquedo, "texto": reais(b.valor_brinquedo) if b.valor_brinquedo else "sob orçamento",
                 "detalhe": {"tipo": "brinquedo", "id": b.pk}}
                for b in brinquedos
            ]),
            secao("Números dos brinquedos", "bi-123", campos=[
                campo("Curtidas somadas", _numero(curtidas), "bi-heart"),
                campo("Pedidos pagos", _pedidos_de_varios("brinquedo", ids), "bi-bag-check"),
            ]),
        ],
        "links": [{"rotulo": "Página de eventos", "url": _link("eventos"), "externo": True}],
        "atividade": atividade(pagina),
    }


def _pedidos_de_varios(tipo_item, ids):
    from .models import ItemPedido

    if not ids:
        return "—"
    numeros = ItemPedido.objects.filter(tipo_item=tipo_item, object_id__in=ids, pedido__status__in=PEDIDO_PAGO).aggregate(
        n=Count("pedido_id", distinct=True), valor=Sum("subtotal"),
    )
    return f"{_numero(numeros['n'])} · {reais(numeros['valor'])}"


def detalhe_projeto(pk, usuario, pagina=1, so_atividade=False):
    from .models import MontagemTresD, ObjetoTresDProjeto, Projetos

    try:
        projeto = Projetos.objects.select_related("brinquedo_projetado").get(pk=pk)
    except Projetos.DoesNotExist:
        raise NaoEncontrado
    projetado = projeto.brinquedo_projetado

    def fonte_montagens(limite):
        if not projetado:
            return []
        return [
            evento(m.criacao, f"Montagem 3D “{m.nome}”", f"por {m.feito_por}" if m.feito_por else "", "bi-boxes")
            for m in MontagemTresD.objects.filter(projeto=projetado).order_by("-criacao", "-id")[:limite]
        ]

    def atividade(p):
        return paginar_atividade([fonte_montagens], p)

    if so_atividade:
        return atividade(pagina)
    fotos, objeto_3d, montagens = [], None, 0
    if projetado:
        fotos = [u for u in (_url_imagem(i.imagem) for i in projetado.imagens_brinquedo_projeto.all()) if u]
        objeto_3d = ObjetoTresDProjeto.objects.select_related("produto").filter(projeto=projetado).first()
        montagens = MontagemTresD.objects.filter(projeto=projetado).count()
    secoes = [
        secao("Sobre o projeto", "bi-easel", texto=projeto.descricao),
        secao("Brinquedo projetado", "bi-joystick", campos=[
            campo("Nome", projetado.nome_brinquedo_projeto if projetado else "—", "bi-joystick"),
            campo("Cadastrado em", quando(projetado.criacao) if projetado else "—", "bi-calendar-plus"),
            campo("Objeto 3D", "sim" if objeto_3d else "não", "bi-badge-3d"),
            campo("Montagens 3D", _numero(montagens), "bi-boxes"),
        ], texto=projetado.descricao if projetado else ""),
        secao("Fotos", "bi-images", fotos=fotos[:12]),
    ]
    if objeto_3d and objeto_3d.produto_id:
        secoes.append(secao("Este projeto na loja", "bi-shop", lista=[{
            "titulo": objeto_3d.produto.nome_brinquedo,
            "texto": reais(objeto_3d.produto.valor_brinquedo) if objeto_3d.produto.valor_brinquedo else "sob orçamento",
            "detalhe": {"tipo": "brinquedo", "id": objeto_3d.produto_id},
        }]))
    return {
        "titulo": projeto.titulo,
        "subtitulo": projetado.nome_brinquedo_projeto if projetado else "Sem brinquedo projetado",
        "imagem": fotos[0] if fotos else None,
        "selos": [selo("Tem 3D", "neutro", "bi-badge-3d")] if objeto_3d else [],
        "secoes": secoes,
        "links": [{"rotulo": "Página de projetos", "url": _link("projetos"), "externo": True}],
        "atividade": atividade(pagina),
    }


def detalhe_cliente(pk, usuario, pagina=1, so_atividade=False):
    from sistema_interno.models import Cliente, Orcamento, OrdemServico

    def fonte_orcamentos(limite):
        eventos = []
        for orc in Orcamento.objects.filter(cliente_id=pk).prefetch_related("itens").order_by("-criacao", "-id")[:limite]:
            rotulo, tom = _status_orcamento(orc)
            eventos.append(evento(orc.criacao, f"Orçamento nº {orc.pk} (v{orc.versao})", f"{rotulo} · {reais(orc.total)}", "bi-file-earmark-text", tom))
            if orc.respondido_em:
                eventos.append(evento(
                    orc.respondido_em, f"Resposta ao orçamento nº {orc.pk}", rotulo,
                    "bi-check2-circle" if orc.status == "aprovado" else "bi-x-circle", tom,
                ))
        return eventos

    def fonte_os(limite):
        return [
            evento(os_.criacao, f"O.S. nº {os_.pk} · {os_.get_tipo_display()}", os_.get_status_display(), "bi-tools")
            for os_ in OrdemServico.objects.filter(cliente_id=pk).order_by("-criacao", "-id")[:limite]
        ]

    def atividade(p):
        return paginar_atividade([fonte_orcamentos, fonte_os], p)

    if so_atividade:
        return atividade(pagina)
    try:
        cliente = Cliente.objects.select_related("parceiro", "estabelecimento").prefetch_related("enderecos").get(pk=pk)
    except Cliente.DoesNotExist:
        raise NaoEncontrado
    numeros = Orcamento.objects.filter(cliente_id=pk).exclude(status=Orcamento.Status.SUBSTITUIDO).aggregate(
        total=Count("id"),
        abertos=Count("id", filter=Q(status__in=Orcamento.EM_ABERTO)),
        aprovados=Count("id", filter=Q(status=Orcamento.Status.APROVADO)),
        recusados=Count("id", filter=Q(status=Orcamento.Status.RECUSADO)),
    )
    aprovados = list(Orcamento.objects.filter(cliente_id=pk, status=Orcamento.Status.APROVADO).prefetch_related("itens"))
    valor_aprovado = sum((o.total for o in aprovados), Decimal("0"))
    ordens = OrdemServico.objects.filter(cliente_id=pk).count()
    endereco = cliente.endereco_principal
    taxa = f"{round(numeros['aprovados'] / numeros['total'] * 100)}%" if numeros["total"] else "—"
    return {
        "titulo": cliente.nome_cliente,
        "subtitulo": cliente.get_tipo_display() if hasattr(cliente, "get_tipo_display") else "",
        "imagem": _url_imagem(cliente.logo),
        "icone": "bi-person-vcard",
        "selos": [
            selo("Ativo", "bom", "bi-check-circle") if cliente.ativo else selo("Inativo", "ruim", "bi-slash-circle"),
            *([selo("No mapa do site", "neutro", "bi-geo-alt")] if cliente.no_mapa else []),
        ],
        "secoes": [
            secao("Contato", "bi-telephone", campos=[
                campo("Telefone / WhatsApp", cliente.telefone, "bi-whatsapp"),
                campo("E-mail", cliente.email, "bi-envelope"),
                campo("Documento", cliente.documento, "bi-person-vcard"),
                campo("Estabelecimento", cliente.nome_estabelecimento or (cliente.estabelecimento and str(cliente.estabelecimento)), "bi-shop"),
                campo("Parceiro", cliente.parceiro and str(cliente.parceiro), "bi-people"),
                campo("Endereço", str(endereco) if endereco else "—", "bi-geo-alt"),
                campo("Na carteira desde", quando(cliente.criacao), "bi-calendar-plus"),
            ], texto=cliente.observacoes),
            secao("Números de sempre", "bi-123", campos=[
                campo("Orçamentos", _numero(numeros["total"]), "bi-file-earmark-text"),
                campo("Em aberto", _numero(numeros["abertos"]), "bi-hourglass-split"),
                campo("Aprovados", f"{_numero(numeros['aprovados'])} · {reais(valor_aprovado)}", "bi-check2-circle"),
                campo("Recusados", _numero(numeros["recusados"]), "bi-x-circle"),
                campo("Taxa de aprovação", taxa, "bi-percent"),
                campo("Ordens de serviço", _numero(ordens), "bi-tools"),
            ]),
        ],
        "links": [],
        "atividade": atividade(pagina),
    }


def detalhe_pedido(pk, usuario, pagina=1, so_atividade=False):
    from .models import Pedido, Venda

    try:
        pedido = Pedido.objects.select_related("cliente__user").prefetch_related("itens").get(pk=pk)
    except Pedido.DoesNotExist:
        raise NaoEncontrado
    venda = Venda.objects.filter(pedido_id=pk).first()

    def fonte(limite):
        eventos = [evento(pedido.criacao, "Pedido criado", reais(pedido.total_final), "bi-bag")]
        if venda:
            eventos.append(evento(
                venda.criacao, "Venda registrada" + (" e confirmada" if venda.confirmado else " (a confirmar)"),
                f"{reais(venda.valor_pago)} · {venda.get_forma_pagamento_display() or '—'}", "bi-cash-coin",
                "bom" if venda.confirmado else "atencao",
            ))
        if pedido.atualizado and pedido.criacao and pedido.atualizado - pedido.criacao > dt.timedelta(minutes=1):
            rotulo, tom, icone = _status_pedido(pedido.status)
            eventos.append(evento(pedido.atualizado, "Última atualização", rotulo, icone, tom))
        return eventos

    def atividade(p):
        return paginar_atividade([fonte], p)

    if so_atividade:
        return atividade(pagina)
    rotulo, tom, icone = _status_pedido(pedido.status)
    cliente = pedido.cliente
    conta = cliente.user if (cliente and cliente.user_id) else None
    endereco = ", ".join(p for p in (pedido.rua, pedido.numero, pedido.bairro, pedido.cidade, pedido.estado, pedido.cep) if p)
    return {
        "titulo": f"Pedido nº {pedido.pk}",
        "subtitulo": f"{reais(pedido.total_final)} · {quando(pedido.criacao)}",
        "imagem": None,
        "icone": "bi-bag",
        "selos": [selo(rotulo, tom, icone), *([selo("Impresso", "neutro", "bi-printer")] if pedido.impresso else [])],
        "secoes": [
            secao("Cliente", "bi-person", campos=[
                campo("Nome", (cliente.nome_completo if cliente else None) or (conta.username if conta else "sem conta"), "bi-person"),
                campo("E-mail", conta.email if conta else None, "bi-envelope"),
                campo("Telefone", cliente.telefone if cliente else None, "bi-telephone"),
            ], detalhe={"tipo": "usuario", "id": conta.pk} if conta else None),
            secao("Valores", "bi-cash-stack", campos=[
                campo("Itens (bruto)", reais(pedido.total_bruto), "bi-basket"),
                campo("Desconto", f"{reais(pedido.valor_desconto)}" + (f" · cupom {pedido.cupom_codigo}" if pedido.cupom_codigo else ""), "bi-percent"),
                campo("Frete", reais(pedido.valor_frete), "bi-truck"),
                campo("Total", reais(pedido.total_final), "bi-currency-dollar"),
                campo("Pagamento", pedido.get_forma_pagamento_display() if pedido.forma_pagamento else "—", "bi-credit-card"),
                campo("Situação no Mercado Pago", pedido.mp_status, "bi-shield-check"),
            ]),
            secao("Entrega", "bi-truck", campos=[
                campo("Modo", pedido.get_tipo_envio_display(), "bi-signpost"),
                campo("Endereço", endereco or "—", "bi-geo-alt"),
                campo("Distância", f"{pedido.distancia_km} km" if pedido.distancia_km else "—", "bi-map"),
                campo("Tempo estimado", f"{pedido.tempo_estimado_min} min" if pedido.tempo_estimado_min else "—", "bi-clock"),
            ], texto=pedido.observacoes),
            secao("Itens", "bi-box2", lista=[
                {
                    "titulo": item.nome_item,
                    "texto": f"{item.quantidade} × {reais(item.preco_unitario)} = {reais(item.subtotal)}",
                    "detalhe": {"tipo": {"pecas": "peca"}.get(item.tipo_item, item.tipo_item), "id": item.object_id} if item.object_id else None,
                }
                for item in pedido.itens.all()
            ]),
        ],
        "links": [],
        "atividade": atividade(pagina),
    }


def detalhe_usuario(pk, usuario, pagina=1, so_atividade=False):
    from django.contrib.auth.models import User

    from sistema_interno.models import Orcamento
    from sistema_interno.permissoes import FUNCOES, nomes_das_funcoes

    from .models import (
        AcessoDiario,
        CarteiraPontos,
        Favorito,
        ItemCarrinho,
        JogadaRegistrada,
        Pedido,
        PontoGanho,
        RegistroCadastro,
    )
    from .presenca import cartao_da_conta, situacao_da_conta

    try:
        conta = User.objects.select_related("perfil", "presenca").get(pk=pk)
    except User.DoesNotExist:
        raise NaoEncontrado

    def fonte_pedidos(limite):
        eventos = []
        for pedido in Pedido.objects.filter(cliente__user_id=pk).order_by("-criacao", "-id")[:limite]:
            rotulo, tom, icone = _status_pedido(pedido.status)
            eventos.append(evento(pedido.criacao, f"Pedido nº {pedido.pk} · {rotulo}", reais(pedido.total_final), icone, tom))
        return eventos

    def fonte_acessos(limite):
        eventos = []
        for acesso in AcessoDiario.objects.filter(usuario_id=pk).order_by("-dia")[:limite]:
            primeiro, ultimo = timezone.localtime(acesso.primeiro), timezone.localtime(acesso.ultimo)
            faixa = f"das {primeiro:%H:%M} às {ultimo:%H:%M}" if ultimo - primeiro > dt.timedelta(minutes=1) else f"às {primeiro:%H:%M}"
            eventos.append(evento(acesso.ultimo, "Usou o site ou o painel", faixa, "bi-activity"))
        return eventos

    def fonte_pontos(limite):
        return [
            evento(p.criacao, f"{'+' if p.pontos >= 0 else ''}{p.pontos} pontos", p.descricao or p.get_origem_display(), "bi-stars", "bom" if p.pontos >= 0 else "neutro")
            for p in PontoGanho.objects.filter(usuario_id=pk).order_by("-criacao", "-id")[:limite]
        ]

    def fonte_conta(limite):
        eventos = [evento(conta.date_joined, "Conta criada", "", "bi-person-plus")]
        if conta.last_login:
            eventos.append(evento(conta.last_login, "Último login com senha", "", "bi-box-arrow-in-right"))
        return eventos

    def atividade(p):
        return paginar_atividade([
            fonte_pedidos, _atividade_favoritos(None, usuario_id=pk), _atividade_jogadas(usuario_id=pk),
            fonte_acessos, fonte_pontos, fonte_conta,
        ], p)

    if so_atividade:
        return atividade(pagina)

    # ------------------------------------------------------------------
    # O RESUMO DE UMA PESSOA: O QUE AJUDA A DECIDIR
    #
    # O cliente, depois do erro 500 da ficha: "eu quero dados realmente
    # interessantes e que precisamos de fato". A ficha de uma conta abre pelo
    # que o dono quer saber de uma pessoa, nesta ordem:
    #   1. É COMPRADORA? pedidos pagos, total gasto, ticket médio, o último
    #      pedido e o que ela comprou;
    #   2. ESTÁ POR PERTO? vista por último (e onde), o dia de hoje (entrou
    #      às 09:12, último sinal às 11:40), dias com acesso em 30 dias;
    #   3. O QUE ELA QUER? o que curtiu, o que pôs na lista de desejos e o
    #      que está parado no carrinho agora;
    #   4. JOGA? as jogadas no portal e os jogos de que mais gosta;
    #   5. e só então o cadastro (contato, perfil, origem, pontos).
    # Seção sem nada a dizer não aparece. Cada lista é uma consulta com
    # limite: a ficha de quem tem dois mil pedidos custa o mesmo que a de
    # quem tem dois.
    # ------------------------------------------------------------------
    from .models import ItemPedido

    perfil = getattr(conta, "perfil", None)
    estado = situacao_da_conta(conta)
    try:
        onde = conta.presenca.get_onde_display()
    except Exception:  # noqa: BLE001
        onde = None
    registro = RegistroCadastro.objects.filter(usuario_id=pk).order_by("criacao").first()
    pedidos = Pedido.objects.filter(cliente__user_id=pk).aggregate(
        total=Count("id"),
        pagos=Count("id", filter=Q(status__in=PEDIDO_PAGO)),
        abertos=Count("id", filter=Q(status="aguardando_pagamento")),
        gasto=Sum("total_final", filter=Q(status__in=PEDIDO_PAGO)),
    )
    ultimo_pedido = (
        Pedido.objects.filter(cliente__user_id=pk, status__in=PEDIDO_PAGO).order_by("-criacao", "-id").first()
        if pedidos["pagos"] else None
    )
    comprados = list(
        ItemPedido.objects.filter(pedido__cliente__user_id=pk, pedido__status__in=PEDIDO_PAGO)
        .values("nome_item", "tipo_item", "object_id")
        .annotate(unidades=Sum("quantidade"), valor=Sum("subtotal"))
        .order_by("-unidades", "-valor", "nome_item")[:6]
    ) if pedidos["pagos"] else []
    favoritos = Favorito.objects.filter(usuario_id=pk).aggregate(
        curtidas=Count("id", filter=Q(tipo="curtida")), desejos=Count("id", filter=Q(tipo="desejo")),
    )
    quer = list(
        Favorito.objects.filter(usuario_id=pk).select_related("brinquedo", "peca").order_by("-criacao", "-id")[:8]
    ) if (favoritos["curtidas"] or favoritos["desejos"]) else []
    carrinho = list(ItemCarrinho.objects.filter(carrinho__cliente__user_id=pk).prefetch_related("item")[:10])
    carteira = CarteiraPontos.objects.filter(usuario_id=pk).first()
    hoje = timezone.localdate()
    acessos = list(
        AcessoDiario.objects.filter(usuario_id=pk, dia__gte=hoje - dt.timedelta(days=29))
        .order_by("-dia").values_list("dia", "primeiro", "ultimo")
    )
    acesso_de_hoje = next((linha for linha in acessos if linha[0] == hoje), None)
    jogadas = JogadaRegistrada.objects.filter(usuario_id=pk).aggregate(
        total=Count("id"), jogos=Count("jogo", distinct=True),
        mes=Count("id", filter=Q(quando__gte=timezone.now() - dt.timedelta(days=30))),
    )
    mais_jogados = list(
        JogadaRegistrada.objects.filter(usuario_id=pk).values("jogo")
        .annotate(n=Count("id"), ultima=Max("quando")).order_by("-n", "-ultima")[:5]
    ) if jogadas["total"] else []
    nomes_dos_jogos = _nomes_dos_jogos({linha["jogo"] for linha in mais_jogados}) if mais_jogados else {}
    funcoes = sorted(
        f.titulo for f in FUNCOES if f.grupo in nomes_das_funcoes(conta)
    ) if (conta.is_staff or conta.is_superuser or conta.groups.exists()) else []
    if conta.is_superuser:
        perfil_texto = "Superadministrador"
    elif funcoes or conta.is_staff:
        perfil_texto = "Equipe"
    else:
        perfil_texto = "Cliente"

    def plural(quantidade, um, varios):
        return f"{_numero(quantidade)} {um if quantidade == 1 else varios}"

    # 1. é compradora?
    pagos = pedidos["pagos"] or 0
    gasto = pedidos["gasto"] or 0
    if pagos:
        compras = [
            campo("Pedidos pagos", _numero(pagos), "bi-bag-check", "bom"),
            campo("Total gasto", reais(gasto), "bi-cash-coin"),
            campo("Ticket médio", reais(gasto / pagos), "bi-receipt"),
            campo(
                "Último pedido pago",
                f"nº {ultimo_pedido.pk} · {timezone.localtime(ultimo_pedido.criacao):%d/%m/%Y} · {reais(ultimo_pedido.total_final)}",
                "bi-clock-history",
            ),
        ]
    else:
        compras = [campo("Pedidos pagos", "Nenhum ainda", "bi-bag")]
    if pedidos["abertos"]:
        compras.append(campo("Aguardando pagamento", plural(pedidos["abertos"], "pedido", "pedidos"), "bi-hourglass-split"))
    tipos_de_ficha = {"brinquedo": "brinquedo", "combo": "combo", "promocao": "promocao", "pecas": "peca"}
    o_que_comprou = [
        {
            "titulo": linha["nome_item"],
            "texto": f"{plural(linha['unidades'] or 0, 'unidade', 'unidades')} · {reais(linha['valor'])}",
            "detalhe": (
                {"tipo": tipos_de_ficha[linha["tipo_item"]], "id": linha["object_id"]}
                if linha["tipo_item"] in tipos_de_ficha and linha["object_id"] else None
            ),
        }
        for linha in comprados
    ]

    # 2. está por perto?
    if acesso_de_hoje:
        primeiro, ultimo = timezone.localtime(acesso_de_hoje[1]), timezone.localtime(acesso_de_hoje[2])
        if ultimo - primeiro > dt.timedelta(minutes=1):
            dia_de_hoje = f"entrou às {primeiro:%H:%M} · último sinal às {ultimo:%H:%M}"
        else:
            dia_de_hoje = f"um sinal só, às {primeiro:%H:%M}"
    else:
        dia_de_hoje = "ainda não apareceu"
    visto = estado["texto"] + (f" · {onde.lower()}" if onde and not estado["online"] else (f" · no {onde.lower()}" if onde else ""))
    presenca_da_conta = [
        campo("Visto por último", visto, "bi-broadcast", "bom" if estado["online"] else None),
        campo("Hoje", dia_de_hoje, "bi-sun"),
        campo("Dias com acesso (30 dias)", f"{len(acessos)} de 30", "bi-calendar-check"),
        campo("Último login com senha", quando(conta.last_login) if conta.last_login else "nunca", "bi-box-arrow-in-right"),
        campo("Criada em", quando(conta.date_joined), "bi-calendar-plus"),
    ]

    # 3. o que ela quer?
    no_carrinho = sum(item.quantidade for item in carrinho)
    valor_do_carrinho = sum((item.preco_unitario or 0) * item.quantidade for item in carrinho)
    desejos = [
        campo("Curtidas", _numero(favoritos["curtidas"]), "bi-heart"),
        campo("Lista de desejos", _numero(favoritos["desejos"]), "bi-bookmark-heart"),
        campo(
            "No carrinho agora",
            f"{plural(no_carrinho, 'item', 'itens')} · {reais(valor_do_carrinho)}" if no_carrinho else "vazio",
            "bi-cart", "bom" if no_carrinho else None,
        ),
    ] if (favoritos["curtidas"] or favoritos["desejos"] or no_carrinho) else []
    curtiu = [
        {
            "titulo": fav.nome_produto,
            "texto": ("Curtiu" if fav.tipo == "curtida" else "Lista de desejos") + f" · {timezone.localtime(fav.criacao):%d/%m/%Y}",
            "detalhe": (
                {"tipo": "brinquedo", "id": fav.brinquedo_id} if fav.brinquedo_id
                else ({"tipo": "peca", "id": fav.peca_id} if fav.peca_id else None)
            ),
        }
        for fav in quer
    ]

    # 4. joga?
    jogos = [
        campo("Jogadas no portal", _numero(jogadas["total"]), "bi-controller"),
        campo("Nos últimos 30 dias", _numero(jogadas["mes"]), "bi-calendar3"),
        campo("Jogos diferentes", _numero(jogadas["jogos"]), "bi-grid"),
    ] if jogadas["total"] else []
    preferidos = [
        {
            "titulo": nomes_dos_jogos.get(linha["jogo"], linha["jogo"]),
            "texto": f"{plural(linha['n'], 'jogada', 'jogadas')} · a última em {timezone.localtime(linha['ultima']):%d/%m/%Y}",
        }
        for linha in mais_jogados
    ]

    # 5. o cadastro
    origem = None
    if registro:
        origem = registro.get_origem_display() + (f" · {registro.regiao}" if registro.regiao else "")
    cadastro = [
        campo("Nome", perfil.nome_completo if perfil else None, "bi-person"),
        campo("Usuário", conta.username, "bi-at"),
        campo("E-mail", conta.email, "bi-envelope"),
        campo("Telefone", perfil.telefone if perfil else None, "bi-telephone"),
        campo("Perfil", perfil_texto, "bi-shield-lock"),
        campo("Origem do cadastro", origem, "bi-signpost-split"),
        campo("Pontos (saldo)", _numero(carteira.saldo) if carteira else "0", "bi-stars"),
    ]
    if perfil_texto != "Cliente":
        cadastro.append(campo("Orçamentos como responsável", _numero(Orcamento.objects.filter(responsavel_id=pk).count()), "bi-file-earmark-text"))

    # "Compras" e "Presença" abrem a ficha, lado a lado: compra? está por perto?
    secoes = [
        secao("Compras na loja", "bi-bag-check", campos=compras),
        secao("Presença", "bi-broadcast", campos=presenca_da_conta),
        secao("O que comprou", "bi-box-seam", lista=o_que_comprou),
        secao("O que quer", "bi-heart", campos=desejos),
        secao("Curtiu e pôs na lista de desejos", "bi-bookmark-heart", lista=curtiu),
        secao("Carrinho agora", "bi-cart", lista=[
            {"titulo": item.nome_com_adesivo, "texto": f"{item.quantidade} × {reais(item.preco_unitario)}"}
            for item in carrinho
        ]),
        secao("Jogos", "bi-controller", campos=jogos, lista=preferidos),
        secao("Conta", "bi-person-badge", campos=cadastro),
        secao("Funções na equipe", "bi-diagram-3", etiquetas=funcoes),
    ]
    cartao = cartao_da_conta(conta, "admin" if conta.is_superuser else ("equipe" if perfil_texto == "Equipe" else "cliente"))
    selos = [
        selo(estado["texto"], "bom" if estado["online"] else "neutro", "bi-broadcast" if estado["online"] else "bi-clock-history"),
        selo(perfil_texto, "neutro", "bi-shield-lock" if perfil_texto != "Cliente" else "bi-person"),
    ]
    if pagos:
        selos.append(selo(f"Comprou {pagos} {'vez' if pagos == 1 else 'vezes'} · {reais(gasto)}", "bom", "bi-bag-check"))
    selos.append(selo("Conta ativa", "bom", "bi-check-circle") if conta.is_active else selo("Conta inativa", "ruim", "bi-slash-circle"))

    return {
        "titulo": (perfil.nome_completo if perfil and perfil.nome_completo else None) or conta.username,
        "subtitulo": f"@{conta.username}",
        "imagem": None,
        "icone": "bi-person-circle",
        # as iniciais na cor da conta: as mesmas da faixa "Agora" e da lista
        "avatar": {"iniciais": cartao["iniciais"], "cor": cartao["cor"]},
        "presenca": estado,
        "selos": selos,
        # seção sem nada a dizer (a conta que nunca comprou, que não joga) não aparece
        "secoes": [bloco for bloco in secoes if len(bloco) > 2],
        "links": [],
        "atividade": atividade(pagina),
    }


def detalhe_jogo(pk, usuario, pagina=1, so_atividade=False):
    from .models import JogadaRegistrada, JogoCadastrado, PartidasDoJogo

    try:
        jogo = JogoCadastrado.objects.get(pk=pk)
    except JogoCadastrado.DoesNotExist:
        raise NaoEncontrado

    def atividade(p):
        return paginar_atividade([_atividade_jogadas(slug=jogo.slug)], p)

    if so_atividade:
        return atividade(pagina)
    agora = timezone.now()
    numeros = JogadaRegistrada.objects.filter(jogo=jogo.slug).aggregate(
        total=Count("id"),
        com_conta=Count("usuario", distinct=True),
        visitantes=Count("visitante", distinct=True, filter=Q(usuario__isnull=True) & ~Q(visitante="")),
        equipe=Count("id", filter=Q(equipe=True)),
        mes=Count("id", filter=Q(quando__gte=agora - dt.timedelta(days=30))),
        ultima=Max("quando"),
    )
    partidas = PartidasDoJogo.objects.filter(slug=jogo.slug).values_list("partidas", flat=True).first() or 0
    plataforma = " · ".join(p for p in (
        getattr(jogo, "get_sistema_display", lambda: "")() if getattr(jogo, "sistema", "") else "",
        "HTML5" if (jogo.endereco or jogo.arquivo_html) else "",
        "Android (APK)" if jogo.apk else "",
        "Windows" if (jogo.versao_pc or jogo.versao_pc_link) else "",
    ) if p)
    return {
        "titulo": jogo.nome,
        "subtitulo": f"/jogos/{jogo.slug}/",
        "imagem": _url_imagem(jogo.capa) or _url_imagem(jogo.poster),
        "icone": "bi-controller",
        "selos": [
            selo("No portal", "bom", "bi-broadcast") if jogo.ativo else selo("Desligado", "ruim", "bi-slash-circle"),
            *([selo("Particular", "neutro", "bi-lock")] if getattr(jogo, "particular", False) else []),
            *([selo("Destaque", "neutro", "bi-star")] if getattr(jogo, "destaque", False) else []),
        ],
        "secoes": [
            secao("Ficha", "bi-card-text", campos=[
                campo("Chamada", jogo.chamada, "bi-megaphone"),
                campo("Roda em", plataforma or "—", "bi-joystick"),
                campo("Categoria", jogo.get_categoria_display() if jogo.categoria else "—", "bi-tags"),
                campo("Feito pela Lazer & Sport", "Sim" if getattr(jogo, "feito_pela_lazer", False) else "Não", "bi-house-heart"),
                campo("Cadastrado em", quando(jogo.criacao), "bi-calendar-plus"),
            ], texto=jogo.descricao),
            secao("Números de sempre", "bi-123", campos=[
                campo("Jogadas com data", _numero(numeros["total"]), "bi-controller"),
                campo("Nos últimos 30 dias", _numero(numeros["mes"]), "bi-calendar3"),
                campo("Pessoas com conta", _numero(numeros["com_conta"]), "bi-person-check"),
                campo("Visitantes sem conta", _numero(numeros["visitantes"]), "bi-incognito"),
                campo("Jogadas da equipe", _numero(numeros["equipe"]), "bi-shield-lock"),
                campo("Última jogada", quando(numeros["ultima"]) if numeros["ultima"] else "—", "bi-clock-history"),
                campo("Partidas no “Mais jogados”", _numero(partidas), "bi-trophy"),
            ]),
        ],
        "links": [{"rotulo": "Abrir no portal", "url": f"/jogos/{jogo.slug}/", "externo": True}],
        "atividade": atividade(pagina),
    }


def _comercial(usuario):
    from sistema_interno.permissoes import AMBULANTE, FINANCEIRO, GESTAO, VENDAS, tem_funcao

    return tem_funcao(usuario, VENDAS, AMBULANTE, FINANCEIRO, GESTAO)


MONTADORES = {
    "brinquedo": detalhe_brinquedo,
    "peca": detalhe_peca,
    "promocao": detalhe_promocao,
    "combo": detalhe_combo,
    "cupom": detalhe_cupom,
    "evento": detalhe_evento,
    "projeto": detalhe_projeto,
    "cliente": detalhe_cliente,
    "pedido": detalhe_pedido,
    "usuario": detalhe_usuario,
    "jogo": detalhe_jogo,
}


def montar(tipo, pk, usuario, pagina=1, so_atividade=False):
    montador = MONTADORES.get(tipo)
    if montador is None:
        raise NaoEncontrado
    ficha = montador(pk, usuario, pagina=pagina, so_atividade=so_atividade)
    if so_atividade:
        return ficha
    ficha.setdefault("icone", None)
    # seção vazia (sem fotos, sem carrinho, sem adesivos) não vira caixa vazia no modal
    ficha["secoes"] = [
        s for s in ficha.get("secoes", [])
        if any(s.get(chave) for chave in ("campos", "etiquetas", "fotos", "lista", "texto"))
    ]
    ficha.update({"tipo": tipo, "id": pk})
    return ficha
