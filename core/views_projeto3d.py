"""Monte seu projeto (/monte-seu-projeto/): a página e o pedido (as regras: core/projeto3d.py).

A página é a ARENA 3D (/arena/, core/views_arena.py): os objetos 3D da
fábrica e, logo abaixo, o "Monte seu espaço". Ela abre inteira sem
JavaScript: as áreas e as máquinas do catálogo com as medidas, como lista, e
o botão do WhatsApp. Com JavaScript (e WebGL), vira o app: as escolhas de um
lado, o 3D do outro. /monte-seu-projeto/ (o endereço antigo) leva para lá.

O pedido é público (não pede conta): por isso tem a armadilha para robôs
(um campo que só robô preenche), um teto por endereço (5 por hora) e o
tamanho de tudo conferido. Não se guarda IP: o teto vive só no cache.

AS FOTOS DO ESPAÇO ("Veja no seu espaço"). O pedido pode vir em partes
(multipart): `dados` (o mesmo JSON de sempre), `foto_N` (até 3), os pontos
marcados nela (`cantos_N`) e o projeto montado nela (`montagem_N`). Cada
imagem é aberta e regravada aqui (JPEG, no máximo 1600 px): o que não é
imagem não entra, e os dados do aparelho gravados na foto (o EXIF, com o
lugar onde ela foi tirada) ficam para trás. Uma foto que não grava não
derruba o pedido: ele já está salvo, e a resposta diz quantas chegaram.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
from urllib.parse import quote

from django.core.cache import cache
from django.db import DatabaseError, transaction
from django.http import JsonResponse
from django.views import View

from . import projeto3d
from .registro_cadastro import ip_da_requisicao

logger = logging.getLogger(__name__)

WHATSAPP = "5511960563135"
#: Quantos pedidos um mesmo endereço pode mandar por hora (gente de verdade manda um ou dois).
PEDIDOS_POR_HORA = 5
#: O corpo do pedido (a escolha e o resumo) nunca passa disto.
TAMANHO_MAXIMO = 64 * 1024
#: As fotos do espaço que vão com o pedido (cada uma com a sua montagem).
MAX_FOTOS = 3
#: Cada imagem que chega (a página manda bem menos: até 1400 px em JPEG).
TAMANHO_DA_IMAGEM = 4 * 1024 * 1024
#: O pedido inteiro com as fotos.
TAMANHO_COM_FOTOS = MAX_FOTOS * 2 * TAMANHO_DA_IMAGEM + TAMANHO_MAXIMO
#: O lado maior da imagem guardada.
LADO_GUARDADO = 1600


class ImagemInvalida(ValueError):
    pass


def preparar_imagem(arquivo, nome):
    """A imagem que chegou, conferida e regravada: JPEG, até LADO_GUARDADO px, sem os dados do aparelho.

    Levanta ImagemInvalida se não for uma imagem (JPEG, PNG ou WEBP) de tamanho razoável.
    """
    from django.core.files.base import ContentFile
    from PIL import Image, ImageOps, UnidentifiedImageError

    if getattr(arquivo, "size", 0) > TAMANHO_DA_IMAGEM:
        raise ImagemInvalida("Uma das fotos é grande demais.")
    try:
        bruto = arquivo.read()
        with Image.open(io.BytesIO(bruto)) as conferir:
            conferir.verify()
        with Image.open(io.BytesIO(bruto)) as imagem:
            if imagem.format not in {"JPEG", "PNG", "WEBP"}:
                raise ImagemInvalida("Mande as fotos em JPG ou PNG.")
            if imagem.width * imagem.height > 40_000_000:
                raise ImagemInvalida("Uma das fotos é grande demais.")
            imagem = ImageOps.exif_transpose(imagem)
            if imagem.mode != "RGB":
                fundo = Image.new("RGB", imagem.size, (255, 255, 255))
                fundo.paste(imagem.convert("RGBA"), mask=imagem.convert("RGBA").split()[-1])
                imagem = fundo
            imagem.thumbnail((LADO_GUARDADO, LADO_GUARDADO))
            saida = io.BytesIO()
            # sem exif=: a foto regravada não leva os dados do aparelho
            imagem.save(saida, "JPEG", quality=85, optimize=True)
    except ImagemInvalida:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as erro:
        raise ImagemInvalida("Uma das fotos não abriu. Mande em JPG ou PNG.") from erro
    return ContentFile(saida.getvalue(), name=nome)


def _cantos(texto):
    """Os pontos que o cliente marcou na foto: {pontos [[x, y] x4], giro, frente} ou {} se não vierem certos."""
    try:
        c = json.loads(texto or "{}")
    except (ValueError, TypeError):
        return {}
    if not isinstance(c, dict):
        return {}
    pontos = c.get("pontos")
    if not (isinstance(pontos, list) and len(pontos) == 4):
        return {}
    limpos = []
    for p in pontos:
        if not (isinstance(p, (list, tuple)) and len(p) == 2):
            return {}
        try:
            x, y = float(p[0]), float(p[1])
        except (TypeError, ValueError):
            return {}
        # fração da foto; o canto fora dela vai um pouco além (o palco tem margem)
        if not (-3 <= x <= 4 and -3 <= y <= 4):
            return {}
        limpos.append([round(x, 5), round(y, 5)])
    giro = c.get("giro")
    return {
        "pontos": limpos,
        "giro": giro if isinstance(giro, int) and 0 <= giro <= 3 else 0,
        "frente": c.get("frente") is not False,
    }


def _fotos_do_pedido(request):
    """As fotos (e montagens) que vieram com o pedido, já conferidas: [(tipo, ContentFile, cantos)]."""
    fotos = []
    for n in range(MAX_FOTOS):
        foto = request.FILES.get(f"foto_{n}")
        if not foto:
            continue
        fotos.append(("foto", preparar_imagem(foto, f"espaco-{n + 1}.jpg"), _cantos(request.POST.get(f"cantos_{n}"))))
        montagem = request.FILES.get(f"montagem_{n}")
        if montagem:
            fotos.append(("montagem", preparar_imagem(montagem, f"projeto-na-foto-{n + 1}.jpg"), {}))
    return fotos


def guardar_fotos(pedido, fotos):
    """Grava as fotos do pedido; devolve quantas fotos do espaço (sem contar as montagens) ficaram."""
    from . import objetos_3d
    from .models import FotoDoEspaco

    if not fotos or not objetos_3d.tabela_pronta(FotoDoEspaco):
        return 0
    guardadas = 0
    for tipo, conteudo, cantos in fotos:
        try:
            with transaction.atomic():
                foto = FotoDoEspaco(pedido=pedido, tipo=tipo, cantos=cantos)
                foto.imagem.save(conteudo.name, conteudo, save=False)
                foto.save()
            guardadas += tipo == "foto"
        except Exception:  # noqa: BLE001 -- o pedido já está salvo; a foto que não foi não o derruba
            logger.exception("Monte seu projeto: uma foto do pedido %s não gravou", pedido.pk)
    if guardadas:
        try:
            resumo = dict(pedido.resumo or {})
            resumo["fotos"] = guardadas
            pedido.resumo = resumo
            pedido.save(update_fields=["resumo"])
        except DatabaseError:
            logger.exception("Monte seu projeto: a contagem das fotos do pedido %s não gravou", pedido.pk)
    return guardadas


def _chave_do_teto(request):
    ip, _ = ip_da_requisicao(request)
    # só o resumo do endereço, e só no cache (some em uma hora)
    return "projeto3d:pedidos:" + hashlib.sha256((ip or "sem-ip").encode()).hexdigest()[:24]


def texto_do_whatsapp(campos):
    """A mensagem pronta para o WhatsApp: o tamanho, o modelo e o que entrou."""
    linhas = [
        "Olá! Montei meu projeto no site da Lazer & Sport.",
        f"Espaço: {campos['largura']} × {campos['comprimento']} m" + (f", pé-direito {campos['pe_direito']} m" if campos.get("pe_direito") else ""),
        f"Modelo: {campos['principal']}",
    ]
    coube = (campos.get("resumo") or {}).get("coube") or []
    if coube:
        linhas.append("Com: " + ", ".join(f"{c.get('qtd', '1')}× {c.get('nome', '')}" for c in coube[:20]))
    return "\n".join(linhas)


def contexto_do_projeto(request):
    """O que o "Monte seu espaço" pede no template: o catálogo, as áreas e o contato de quem está logado."""
    dados = projeto3d.catalogo()
    usuario = request.user if request.user.is_authenticated else None
    return {
        "projeto_dados": dados,
        "areas": [{"chave": k, **v} for k, v in projeto3d.AREAS.items()],
        "maquinas": [i for i in dados["itens"] if i["tipo"] == "maquina"],
        "grandes": [i for i in dados["itens"] if i["tipo"] == "grande"],
        "contato_inicial": {
            "nome": (usuario.get_full_name() or usuario.username) if usuario else "",
            "email": usuario.email if usuario else "",
            "whatsapp": (getattr(getattr(usuario, "perfil", None), "telefone", "") or "") if usuario else "",
        },
        "whatsapp": WHATSAPP,
    }


def monte_seu_projeto(request):
    """O endereço antigo: o "Monte seu espaço" mora na Arena 3D (/arena/#monte-seu-espaco).

    O link compartilhado leva o projeto no fim (#p=...): ele segue junto.
    """
    from django.http import HttpResponsePermanentRedirect
    from django.urls import reverse

    return HttpResponsePermanentRedirect(reverse("arena") + "#monte-seu-espaco")


class PedirProjeto3DView(View):
    """POST JSON {contato, espaco, escolha, resumo, site (a armadilha)} -> {status, numero, fotos}.

    Com as fotos do espaço, o mesmo JSON vai em `dados` de um multipart (veja o topo do arquivo).
    """

    def post(self, request):
        grande = JsonResponse({"status": "erro", "mensagem": "O pedido ficou grande demais."}, status=413)
        em_partes = (request.content_type or "").startswith("multipart/")
        if em_partes:
            try:
                tamanho = int(request.META.get("CONTENT_LENGTH") or 0)
            except ValueError:
                tamanho = 0
            if tamanho > TAMANHO_COM_FOTOS:
                return grande
            bruto = request.POST.get("dados") or ""
            if len(bruto.encode()) > TAMANHO_MAXIMO:
                return grande
        else:
            bruto = request.body or b""
            if len(bruto) > TAMANHO_MAXIMO:
                return grande
        try:
            dados = json.loads(bruto or "{}")
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({"status": "erro", "mensagem": "Pedido em formato inválido."}, status=400)
        if not isinstance(dados, dict):
            return JsonResponse({"status": "erro", "mensagem": "Pedido em formato inválido."}, status=400)

        # a armadilha: o campo escondido que só robô preenche -- responde como se fosse, e não grava
        if str(dados.get("site") or "").strip():
            return JsonResponse({"status": "sucesso", "numero": 0})

        chave = _chave_do_teto(request)
        if cache.get(chave, 0) >= PEDIDOS_POR_HORA:
            return JsonResponse({
                "status": "erro",
                "mensagem": "Recebemos vários pedidos daqui agora há pouco. Fale com a gente pelo WhatsApp.",
            }, status=429)

        try:
            campos = projeto3d.validar_pedido(dados, projeto3d.catalogo())
        except projeto3d.PedidoInvalido as erro:
            return JsonResponse({"status": "erro", "mensagem": str(erro)}, status=400)
        # as fotos são conferidas antes de gravar o pedido: o que não é imagem volta com o motivo
        try:
            fotos = _fotos_do_pedido(request) if em_partes else []
        except ImagemInvalida as erro:
            return JsonResponse({"status": "erro", "mensagem": f"{erro} Ou tire a foto e mande o pedido sem ela."}, status=400)

        from .models import PedidoProjeto3D

        try:
            with transaction.atomic():
                pedido = PedidoProjeto3D.objects.create(
                    usuario=request.user if request.user.is_authenticated else None, **campos,
                )
        except DatabaseError:
            # o banco sem a tabela (a migração ainda não rodou): o cliente não perde o projeto
            logger.exception("Monte seu projeto: o pedido não foi gravado")
            return JsonResponse({
                "status": "erro",
                "mensagem": "Não conseguimos gravar agora. Mande pelo WhatsApp: a mensagem já vai pronta.",
                "whatsapp": f"https://wa.me/{WHATSAPP}?text={quote(texto_do_whatsapp(campos))}",
            }, status=503)

        try:
            cache.add(chave, 0, 3600)
            cache.incr(chave)
        except ValueError:
            cache.set(chave, 1, 3600)
        guardadas = guardar_fotos(pedido, fotos)
        mensagem = texto_do_whatsapp(campos) + f"\nPedido nº {pedido.pk}"
        if guardadas:
            mensagem += f" (com {guardadas} {'foto' if guardadas == 1 else 'fotos'} do espaço)"
        return JsonResponse({
            "status": "sucesso",
            "numero": pedido.pk,
            "fotos": guardadas,
            "whatsapp": f"https://wa.me/{WHATSAPP}?text={quote(mensagem)}",
        })
