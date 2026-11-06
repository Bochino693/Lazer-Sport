"""MONTAR em 3D, como num CAD: o brinquedão ou o espaço peça por peça (/site/objetos-3d/montar/).

O passo 2 do laboratório (Objetos 3D > Laboratório). Uma planta com grade, em
metros, onde se põem:

  * as peças que se desenham sozinhas na medida pedida -- da estrutura
    (coluna, barra, plataforma, painéis, rede, cerca, telhados, piso de
    EVA, LED), das brincadeiras (escorregador, tobogã espiral, túneis,
    rolos, colmeia, bolas penduradas, piscinas, camas, espuma, rampa,
    degraus, portal) e do esporte e da área ninja (quadra, gol, tabela,
    escalada, colchão, degraus ninja, trave, argolas, barra de macaco,
    corda, parede curva) -- o desenho é do navegador
    (sistema_interno/static/interno/montar3d.js e montar3d-pecas.js);
  * o PROJETISTA monta sozinho um brinquedão, um espaço esportivo, uma
    área ninja, um trampolim park ou um espaço baby pela medida, pelo
    estilo e pela cor raiz (montar3d-gerador.js); a cor-tema pinta a
    montagem inteira, inclusive os objetos .glb;
  * as peças guardadas no laboratório (ModuloTresD, .glb);
  * os objetos 3D que já existem: os dos brinquedos e os dos projetos.

Cada peça se move na grade, gira, sobe em cima da outra, muda de medida e de
cor. A montagem é guardada (MontagemTresD: as peças em JSON) e exportada
num .glb só, que vai para um ou vários brinquedos e/ou para um projeto (a
mesma gravação da janela "Criar objeto 3D") ou é baixado.

A BIBLIOTECA APRENDE. (1) As medidas mais usadas nas montagens viram
atalhos ("Coluna 3,50 m -- 24 vezes"). (2) "Aprender de um arquivo": as
peças que se repetem num .3ds/.dae/.obj da fábrica viram peças novas da
biblioteca, com nome e medida (core/conversor_3d.pecas_que_se_repetem).
Quanto mais objetos entram, mais peças prontas para montar.
"""

from __future__ import annotations

import base64
import json
import logging
import math
from collections import Counter

from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, render
from django.utils.text import slugify
from django.views import View

from core import conversor_3d
from core.models import (
    Brinquedos,
    BrinquedosProjeto,
    ModuloTresD,
    MontagemTresD,
    ObjetoTresD,
    ObjetoTresDProjeto,
)
from core.objetos_3d import tabela_pronta, validar_glb

from .utils import ErroDeFormulario, exigir_confirmacao_exclusao
from .views import RespostaJSONMixin, SuperusuarioInternoRequiredMixin
from .views_objetos_3d import TETO_DO_ARQUIVO_3D, _medidas_texto, _titulo_e_texto_do_projeto

log = logging.getLogger("sistema_interno.montar_3d")

#: As peças que o navegador desenha, e as medidas de cada uma (o desenho é do montar3d.js e do
#: montar3d-pecas.js). As medidas são em metros, menos as de MEDIDAS_ESPECIAIS.
PARAMETRICAS = {
    # estrutura
    "coluna": ("altura", "diametro"),
    "barra": ("comprimento", "diametro"),
    "plataforma": ("largura", "profundidade", "espessura"),
    "painel": ("largura", "altura", "espessura"),
    "janela": ("largura", "altura", "espessura"),
    "abaco": ("largura", "altura"),
    "rede": ("largura", "altura"),
    "cerca": ("comprimento", "altura"),
    "telhado": ("largura", "profundidade", "altura"),
    "teto_arco": ("largura", "profundidade", "altura"),
    "piso_eva": ("largura", "profundidade"),
    "led": ("comprimento",),
    # brincadeiras
    "escorregador": ("comprimento", "altura", "largura", "fechado"),
    "toboga": ("altura", "raio", "voltas", "fechado", "espelhado"),
    "escada": ("altura", "largura", "degraus"),
    "tunel": ("comprimento", "diametro"),
    "tunel_rede": ("comprimento", "diametro"),
    "rolos": ("altura", "largura", "quantidade"),
    "colmeia": ("largura", "altura", "profundidade"),
    "pendulos": ("largura", "altura", "quantidade"),
    "cama": ("largura", "profundidade", "altura"),
    "piscina": ("largura", "profundidade", "altura"),
    "piscina_redonda": ("diametro", "altura"),
    "espuma": ("largura", "profundidade", "altura"),
    "rampa": ("comprimento", "altura", "largura"),
    "degraus_espuma": ("largura", "altura", "degraus"),
    "arco": ("largura", "altura"),
    # esporte e ninja
    "quadra": ("largura", "profundidade"),
    "gol": ("largura", "altura"),
    "tabela": ("altura",),
    "escalada": ("largura", "altura"),
    "colchao": ("largura", "profundidade", "espessura"),
    "degraus": ("comprimento", "largura"),
    "trave": ("comprimento", "altura"),
    "argolas": ("comprimento", "altura", "quantidade"),
    "macaco": ("comprimento", "altura", "largura"),
    "corda": ("altura",),
    "parede_curva": ("largura", "altura"),
}
#: As medidas que não são metros: (menor, maior, inteiro?).
MEDIDAS_ESPECIAIS = {
    "degraus": (1, 60, True),
    "quantidade": (1, 60, True),
    "voltas": (0.25, 6, False),
    "fechado": (0, 1, True),
    "espelhado": (0, 1, True),
}
#: As que aceitam a segunda cor (a diagonal das plataformas, o xadrez do EVA, a moldura da rede).
COM_COR2 = {"plataforma", "piso_eva", "rede"}
#: As que vêm de um .glb: a peça do laboratório, o objeto do brinquedo, o do projeto.
DE_ARQUIVO = ("modulo", "objeto", "projeto")
MAXIMO_DE_PECAS = 3000


def _numero(valor, menor, maior, padrao=None):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return padrao
    if math.isnan(numero) or math.isinf(numero):
        return padrao
    return min(maior, max(menor, numero))


def _cor(valor):
    cor = str(valor or "")
    if len(cor) == 7 and cor.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in cor[1:]):
        return cor.lower()
    return ""


def _medida(chave, valor):
    menor, maior, inteiro = MEDIDAS_ESPECIAIS.get(chave, (0.01, 100, False))
    numero = _numero(valor, menor, maior, menor if chave in ("fechado", "espelhado") else max(menor, 1.0))
    return int(round(numero)) if inteiro else round(numero, 4)


def limpar_pecas(bruto):
    """A lista de peças que veio do navegador, conferida peça por peça (o resto é descartado)."""
    try:
        pecas = json.loads(bruto or "[]")
    except ValueError as exc:
        raise ErroDeFormulario("A montagem veio quebrada.") from exc
    if not isinstance(pecas, list):
        raise ErroDeFormulario("A montagem veio quebrada.")
    if len(pecas) > MAXIMO_DE_PECAS:
        raise ErroDeFormulario(f"A montagem passa de {MAXIMO_DE_PECAS} peças.")
    limpas = []
    for peca in pecas:
        if not isinstance(peca, dict):
            continue
        tipo = str(peca.get("tipo") or "")
        if tipo not in PARAMETRICAS and tipo not in DE_ARQUIVO:
            continue
        p = peca.get("p") or [0, 0, 0]
        if not isinstance(p, list) or len(p) != 3:
            p = [0, 0, 0]
        limpa = {
            "tipo": tipo,
            "p": [round(_numero(v, -500, 500, 0.0), 4) for v in p],
            "r": round(_numero(peca.get("r"), -360, 360, 0.0), 3),
        }
        cor = _cor(peca.get("cor"))
        if cor:
            limpa["cor"] = cor
        if tipo in PARAMETRICAS:
            medidas = peca.get("d") if isinstance(peca.get("d"), dict) else {}
            limpa["d"] = {chave: _medida(chave, medidas.get(chave))
                          for chave in PARAMETRICAS[tipo] if medidas.get(chave) is not None}
            cor2 = _cor(peca.get("cor2")) if tipo in COM_COR2 else ""
            if cor2:
                limpa["cor2"] = cor2
        else:
            ref = peca.get("ref")
            if not str(ref).isdigit():
                continue
            limpa["ref"] = int(ref)
            escala = _numero(peca.get("s"), 0.05, 20, 1.0)
            if escala != 1.0:
                limpa["s"] = round(escala, 4)
            tema = _cor(peca.get("tema"))
            if tema:
                limpa["tema"] = tema
        limpas.append(limpa)
    return limpas


def aprendido_das_montagens(minimo=3):
    """O que o projetista aprende com as montagens guardadas: o módulo e a distância entre os pisos.

    O módulo é a largura de plataforma que mais se repete (arredondada a 5 cm); a distância entre
    os pisos é o degrau de altura mais comum entre plataformas empilhadas no mesmo lugar. Só vale
    com `minimo` montagens guardadas -- antes disso o projetista usa as medidas das fábricas.
    """
    modulos, niveis, quantas = Counter(), Counter(), 0
    for pecas in MontagemTresD.objects.filter(ativo=True).values_list("pecas", flat=True)[:300]:
        plataformas = [p for p in (pecas or []) if p.get("tipo") == "plataforma" and isinstance(p.get("d"), dict)]
        if not plataformas:
            continue
        quantas += 1
        alturas_por_lugar = {}
        for p in plataformas:
            largura = p["d"].get("largura")
            if isinstance(largura, (int, float)) and 0.8 <= largura <= 1.7:
                modulos[round(round((largura + 0.04) * 20) / 20, 2)] += 1
            x, y, z = (p.get("p") or [0, 0, 0])[:3]
            alturas_por_lugar.setdefault((round(x, 1), round(z, 1)), []).append(y)
        for alturas in alturas_por_lugar.values():
            alturas.sort()
            for de, ate in zip(alturas, alturas[1:]):
                if 0.6 <= ate - de <= 1.4:
                    niveis[round(round((ate - de) * 20) / 20, 2)] += 1
    if quantas < minimo:
        return {"vezes": quantas}
    saida = {"vezes": quantas}
    if modulos:
        saida["modulo"] = modulos.most_common(1)[0][0]
    if niveis:
        saida["nivel"] = niveis.most_common(1)[0][0]
    return saida


def mais_usadas(quantas=10):
    """As peças desenhadas que mais se repetem nas montagens, com a medida usada: os atalhos.

    É o aprendizado pelo uso: a coluna de 3,50 m que entra em toda montagem
    aparece pronta no topo da biblioteca.
    """
    contagem = Counter()
    for pecas in MontagemTresD.objects.filter(ativo=True).values_list("pecas", flat=True):
        for peca in pecas or []:
            if peca.get("tipo") in PARAMETRICAS and peca.get("d"):
                chave = (peca["tipo"], tuple(sorted((k, round(float(v), 2)) for k, v in peca["d"].items())))
                contagem[chave] += 1
    return [{"tipo": tipo, "d": dict(medidas), "vezes": vezes}
            for (tipo, medidas), vezes in contagem.most_common(quantas) if vezes >= 2]


class MontarTresDView(RespostaJSONMixin, SuperusuarioInternoRequiredMixin, View):
    rota_padrao = "montar_3d_inner"
    template_name = "montar_3d_inner.html"

    def get(self, request):
        if not tabela_pronta(MontagemTresD):
            return render(request, self.template_name, {"tabela_ausente": True})
        montagens = list(MontagemTresD.objects.filter(ativo=True).select_related("projeto")[:200])
        atual = None
        pedido = (request.GET.get("m") or "").strip()
        if pedido.isdigit():
            atual = next((m for m in montagens if m.pk == int(pedido)), None) or MontagemTresD.objects.filter(pk=int(pedido)).first()

        biblioteca = {
            "modulos": [
                {"id": m.pk, "nome": m.nome, "categoria": m.categoria, "categoria_nome": m.get_categoria_display(),
                 "url": m.url, "medidas": list(m.medidas or [])}
                for m in (ModuloTresD.objects.filter(ativo=True) if tabela_pronta(ModuloTresD) else []) if m.url
            ],
            "objetos": [],
            "projetos": [],
            "mais_usadas": mais_usadas(),
        }
        for objeto in ObjetoTresD.objects.filter(ativo=True, brinquedo__ativo=True).select_related("brinquedo"):
            if objeto.url:
                biblioteca["objetos"].append({"id": objeto.brinquedo_id, "nome": objeto.brinquedo.nome_brinquedo,
                                              "url": objeto.url, "medidas": list(objeto.medidas or [])})
        projetos_lista = []
        com_tabela = tabela_pronta(ObjetoTresDProjeto)
        for projeto in BrinquedosProjeto.objects.order_by("-id"):
            titulo, _texto = _titulo_e_texto_do_projeto(projeto)
            projetos_lista.append({"id": projeto.pk, "titulo": titulo})
            if com_tabela:
                objeto = ObjetoTresDProjeto.objects.filter(projeto=projeto).first()
                if objeto and objeto.url:
                    biblioteca["projetos"].append({"id": projeto.pk, "nome": titulo, "url": objeto.url,
                                                   "medidas": list(objeto.medidas or [])})
        brinquedos = [{"id": b.pk, "nome": b.nome_brinquedo, "tem_3d": False}
                      for b in Brinquedos.objects.filter(ativo=True).order_by("nome_brinquedo")]
        com_3d = {o["id"] for o in biblioteca["objetos"]}
        for b in brinquedos:
            b["tem_3d"] = b["id"] in com_3d
        return render(request, self.template_name, {
            "montagens": [
                {"id": m.pk, "nome": m.nome, "pecas": len(m.pecas or []), "medidas": _medidas_texto(m.medidas or []),
                 "atualizado": m.atualizado, "url": m.url}
                for m in montagens
            ],
            "atual": atual,
            "dados": {
                "biblioteca": biblioteca,
                "montagem": {
                    "id": atual.pk, "nome": atual.nome, "descricao": atual.descricao, "pecas": atual.pecas or [],
                    "projeto": atual.projeto_id,
                } if atual else None,
                "brinquedos": brinquedos,
                "projetos": projetos_lista,
                "tipos": {tipo: list(medidas) for tipo, medidas in PARAMETRICAS.items()},
                "aprendido": aprendido_das_montagens(),
            },
            "categorias_modulo": ModuloTresD.Categoria.choices,
        })

    # ------------------------------------------------------------ ações

    def acao_salvar(self, request):
        nome = (request.POST.get("nome") or "").strip()[:120]
        if not nome:
            raise ErroDeFormulario("Dê um nome à montagem (ex.: Brinquedão 3 torres — shopping).")
        pecas = limpar_pecas(request.POST.get("pecas"))
        if not pecas:
            raise ErroDeFormulario("A montagem está vazia: ponha pelo menos uma peça.")
        try:
            medidas = [round(float(v), 2) for v in json.loads(request.POST.get("medidas") or "[]")][:3]
        except (TypeError, ValueError):
            medidas = []
        bruto = (request.POST.get("id") or "").strip()
        montagem = get_object_or_404(MontagemTresD, pk=int(bruto)) if bruto.isdigit() else MontagemTresD(feito_por=request.user.username)
        projeto_id = (request.POST.get("projeto") or "").strip()
        montagem.projeto = get_object_or_404(BrinquedosProjeto, pk=int(projeto_id)) if projeto_id.isdigit() else None
        montagem.nome = nome
        montagem.descricao = (request.POST.get("descricao") or "").strip()[:2000]
        montagem.pecas = pecas
        montagem.medidas = medidas

        arquivo = request.FILES.get("arquivo")
        antigo = montagem.arquivo.name if montagem.arquivo else ""
        novo = ""
        if arquivo:
            try:
                lido = validar_glb(arquivo)
            except ValidationError as exc:
                raise ErroDeFormulario(" ".join(exc.messages)) from exc
            montagem.medidas = lido["medidas"] or medidas
        try:
            with transaction.atomic():
                if arquivo:
                    arquivo.seek(0)
                    montagem.arquivo.save(f"montagem-{slugify(nome) or 'nova'}.glb", arquivo, save=False)
                    novo = montagem.arquivo.name
                montagem.save()
        except Exception:
            if novo:
                try:
                    montagem.arquivo.storage.delete(novo)
                except Exception as erro:  # noqa: BLE001
                    log.warning("montagem: arquivo órfão não apagado (%s): %r", novo, erro)
            raise
        if novo and antigo and antigo != novo:
            try:
                montagem.arquivo.storage.delete(antigo)
            except Exception as erro:  # noqa: BLE001
                log.warning("montagem: arquivo antigo não apagado (%s): %r", antigo, erro)
        log.info("montagem %s (%d peças) gravada por %s", nome, len(pecas), request.user.username)
        return self.sucesso(request, f"Montagem “{nome}” guardada: {len(pecas)} peça{'s' if len(pecas) > 1 else ''}.",
                            id=montagem.pk, url=montagem.url)

    def acao_apagar(self, request):
        bruto = (request.POST.get("id") or "").strip()
        if not bruto.isdigit():
            raise ErroDeFormulario("Escolha a montagem.")
        montagem = get_object_or_404(MontagemTresD, pk=int(bruto))
        exigir_confirmacao_exclusao(request)
        nome, arquivo = montagem.nome, montagem.arquivo.name if montagem.arquivo else ""
        montagem.delete()
        if arquivo:
            try:
                MontagemTresD._meta.get_field("arquivo").storage.delete(arquivo)
            except Exception as erro:  # noqa: BLE001
                log.warning("montagem: arquivo %s não apagado: %r", arquivo, erro)
        log.warning("montagem %s apagada por %s", nome, request.user.username)
        return self.sucesso(request, f"A montagem “{nome}” foi apagada.")

    def acao_aprender(self, request):
        """As peças que se repetem num arquivo 3D da fábrica (para guardar no laboratório)."""
        arquivo = request.FILES.get("arquivo3d")
        if not arquivo:
            raise ErroDeFormulario("Escolha o arquivo 3D (.3ds, .dae, .kmz ou .obj).")
        if arquivo.size > TETO_DO_ARQUIVO_3D:
            raise ErroDeFormulario(f"O arquivo passa de {TETO_DO_ARQUIVO_3D // (1024 * 1024)} MB.")
        try:
            pecas = conversor_3d.pecas_que_se_repetem(
                arquivo.name, arquivo.read(),
                eixo=request.POST.get("eixo") or "auto", unidade=request.POST.get("unidade") or "auto",
            )
        except conversor_3d.ErroDeConversao as exc:
            raise ErroDeFormulario(str(exc)) from exc
        if not pecas:
            return self.sucesso(request, "Nenhuma peça se repete 3 vezes ou mais neste arquivo.", pecas=[])
        return self.sucesso(
            request,
            f"{len(pecas)} peça{'s' if len(pecas) > 1 else ''} que se repete{'m' if len(pecas) > 1 else ''} no arquivo.",
            pecas=[{**{k: v for k, v in p.items() if k != "glb"}, "glb": base64.b64encode(p["glb"]).decode("ascii"),
                    "medidas_texto": _medidas_texto(p["medidas"])} for p in pecas],
        )
