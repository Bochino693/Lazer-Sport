"""FOTOS QUE FALTAM (/restaurar-fotos/): o dono devolve as fotos ao site (LEIA-ME-V10, seções 130 e 133).

Com o Cloudinary desativado, as fotos que só existiam lá sumiram -- e ele
pede pagamento para devolver a exportação. Desde a seção 133 a tela começa
pelo que importa: UM CARD POR FOTO QUE FALTA (sistema_interno/fotos_que_faltam.py),
com o que ela é, onde aparece e o botão "Enviar foto" (do celular ou do
computador); várias fotos soltas de uma vez casam pelo nome, e o que não
casa o dono põe no lugar tocando no card. Cada foto enviada vai para o
banco (core.espelho_midia.gravar_conteudo, exata) e troca o nome em todo
campo que a usava.

Esta tela (só do superadministrador, como o resto da Administração) também:

  * mostra o que ainda não está no banco, por tipo de cadastro (os
    produtos, as peças, os clientes...), com o nome de cada arquivo;
  * recebe a EXPORTAÇÃO do Cloudinary (o ZIP da Media Library: selecionar
    tudo -> Download) ou fotos soltas: cada arquivo casa pelo public id (a
    pasta e o nome sem a extensão) e volta para o banco, trocando o nome em
    todo campo que o usava (core/restaurar_midia.py);
  * restaura na hora o que tem cópia no repositório (o mesmo que o Render
    faz sozinho a cada publicação).

O ENVIO EM PEDAÇOS. Um ZIP de centenas de MB não passa inteiro por um POST
(o proxy corta, a conexão do celular cai): o navegador corta o arquivo em
pedaços de 8 MB e manda um por vez para uma pasta própria do envio, no
disco da instância; depois pede "processar" até acabar -- cada ida lê as
entradas do ZIP por uns 20 segundos e devolve onde parou. Nada é extraído
para o disco: cada entrada é lida, conferida e gravada no banco.
"""

from __future__ import annotations

import io
import json
import logging
import re
import secrets
import shutil
import tempfile
import time
from collections import Counter
from pathlib import Path

from django.http import JsonResponse
from django.shortcuts import render

from core import espelho_midia, restaurar_midia
from core.arquivos_no_banco import PREFIXO, ArmazenamentoIndisponivel, url_publica
from core.fotos import reduzir_imagem

from . import fotos_que_faltam
from .views import SuperusuarioInternoRequiredMixin

log = logging.getLogger("lazer.midia")

#: O pedaço que o navegador manda por vez.
PEDACO = 8 * 1024 * 1024
#: Quanto tempo cada "processar" lê o ZIP antes de devolver onde parou.
PRAZO_POR_IDA = 20
#: Os envios esquecidos (aba fechada no meio) saem depois disto.
VIDA_DO_ENVIO = 6 * 3600

_MAPAS = {}  # envio -> (Mapa, quando): o mapa dos nomes não é refeito a cada ida

NOMES_DOS_MODELOS = {
    "core.ImagemBrinquedo": "Fotos dos produtos",
    "core.Brinquedos": "Capas dos produtos",
    "core.CategoriasBrinquedos": "Categorias",
    "core.ImagemPeca": "Fotos das peças",
    "core.Combos": "Combos",
    "core.Promocoes": "Promoções",
    "core.Estabelecimentos": "Clientes no mapa (logos)",
    "core.ImagemEvento": "Eventos",
    "core.ImagemProjetoBrinquedo": "Projetos",
    "core.JogoCadastrado": "Capas dos jogos",
    "core.ImagensSite": "Imagens do site",
    "core.ManutencaoImagem": "Fotos das manutenções",
    "core.FotoDoEspaco": "Fotos dos espaços",
    "core.ObjetoTresD": "Objetos 3D",
    "core.VarianteAdesivo": "Objetos 3D dos adesivos",
    "core.ObjetoTresDProjeto": "Objetos 3D dos projetos",
    "core.ModuloTresD": "Módulos 3D",
    "core.MontagemTresD": "Montagens 3D",
    "sistema_interno.Cliente": "Logos dos clientes",
    "sistema_interno.Material": "Fotos dos materiais",
    "sistema_interno.ImagemGuiaProducao": "Guias de produção",
    "sistema_interno.NotaEntrada": "Notas fiscais (privado)",
    "sistema_interno.DocumentoOrdemServico": "Documentos das O.S. (privado)",
    "rh.DocumentoColaborador": "Documentos do RH (privado)",
    "rh.ImportacaoPonto": "Cartões de ponto (privado)",
}


def _pasta_dos_envios() -> Path:
    return Path(tempfile.gettempdir()) / "ls-restaurar-fotos"


def _limpar_esquecidos():
    agora = time.time()
    raiz = _pasta_dos_envios()
    if not raiz.is_dir():
        return
    for pasta in raiz.iterdir():
        try:
            if agora - pasta.stat().st_mtime > VIDA_DO_ENVIO:
                shutil.rmtree(pasta, ignore_errors=True)
                _MAPAS.pop(pasta.name, None)
        except OSError:
            continue


def _envio(token) -> Path | None:
    if not re.fullmatch(r"[0-9a-f]{32}", str(token or "")):
        return None
    pasta = _pasta_dos_envios() / token
    return pasta if (pasta / "meta.json").is_file() else None


def _meta(pasta: Path) -> dict:
    return json.loads((pasta / "meta.json").read_text(encoding="utf-8"))


def _gravar_meta(pasta: Path, meta: dict):
    temporario = pasta / "meta.json.tmp"
    temporario.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    temporario.replace(pasta / "meta.json")


def _faltando_por_grupo(linhas):
    contagem = Counter(l["modelo"] for l in linhas)
    grupos = []
    for modelo, quantos in contagem.most_common():
        nomes = sorted({l["nome"] for l in linhas if l["modelo"] == modelo})
        grupos.append({
            "modelo": modelo,
            "titulo": NOMES_DOS_MODELOS.get(modelo, modelo),
            "quantos": quantos,
            "privado": "(privado)" in NOMES_DOS_MODELOS.get(modelo, ""),
            "nomes": nomes[:60],
            "mais": max(0, len(nomes) - 60),
        })
    return grupos


def painel(pendentes=None):
    """Os números da tela: no banco, faltando (por grupo), e o que a linha de fundo fez.

    `pendentes` (o {nome: [Referencia]} de fotos_que_faltam.pendentes) evita ler
    tudo de novo quando a tela já leu. As duas contagens do banco vão numa
    consulta só.
    """
    from django.db.models import Count, Q

    from core.models import ArquivoNoBanco

    pendentes = fotos_que_faltam.pendentes() if pendentes is None else pendentes
    faltando = sorted(
        ({"modelo": r.modelo._meta.label, "pk": pk, "campo": r.campo, "nome": nome}
         for nome, grupo in pendentes.items() for r in grupo for pk in r.pks),
        key=lambda l: (l["modelo"], l["campo"], str(l["pk"])),
    )
    numeros = ArquivoNoBanco.objects.aggregate(
        no_banco=Count("id", filter=Q(publico=True)), reserva=Count("id", filter=Q(exata=False)),
    )
    publicos = [nome for nome, grupo in pendentes.items() if fotos_que_faltam.e_publico(grupo)]
    return {
        "faltando_total": len(faltando),
        "faltando_nomes": len({l["nome"] for l in faltando}),
        "faltando_site": len(publicos),
        "pendentes": sorted(publicos),
        "grupos": _faltando_por_grupo(faltando),
        "no_banco": numeros["no_banco"],
        "reserva": numeros["reserva"],
        "espelho": espelho_midia.estado(),
    }


def _url_da_foto(nome, largura=480):
    """O endereço da foto no banco, no tamanho do card (o mesmo que o site pede)."""
    return reduzir_imagem(url_publica(nome), largura)


def _resultado_json(resultado: restaurar_midia.Resultado, limite=200):
    def onde(item):
        return [f"{NOMES_DOS_MODELOS.get(m, m)} #{pk}" for m, _c, pk in item.get("onde", [])][:4]

    return {
        "restaurados": [
            {"nome": i["nome"], "de": i.get("de", ""), "regra": i.get("regra", ""), "exata": i.get("exata", True),
             "onde": onde(i), "url": _url_da_foto(i["para"]) if i.get("para") else ""}
            for i in resultado.restaurados[:limite]
        ],
        "nao_referenciados": resultado.nao_referenciados[:limite],
        "recusados": resultado.recusados[:limite],
        "ja": len(resultado.ja),
        "resumo": resultado.resumo(),
    }


class RestaurarFotosView(SuperusuarioInternoRequiredMixin):
    def get(self, request):
        if request.GET.get("formato") == "json":
            return JsonResponse({"status": "sucesso", **painel()})
        pendentes = fotos_que_faltam.pendentes()
        return render(request, "restaurar_fotos_inner.html", {
            "dados": painel(pendentes),
            "faltam": fotos_que_faltam.montar(pendentes),
            "pedaco": PEDACO,
            "limite_zip": restaurar_midia.LIMITE_DO_ZIP,
            "limite_arquivo_mb": int(espelho_midia._limite() / (1024 * 1024)),
        })

    def post(self, request):
        acao = request.POST.get("acao", "")
        try:
            if acao == "enviar":
                return self._enviar(request)
            if acao == "casar":
                return self._casar(request)
            if acao == "comecar":
                return self._comecar(request)
            if acao == "pedaco":
                return self._pedaco(request)
            if acao == "processar":
                return self._processar(request)
            if acao == "copias":
                return self._copias()
            if acao == "cancelar":
                pasta = _envio(request.POST.get("envio"))
                if pasta is not None:
                    shutil.rmtree(pasta, ignore_errors=True)
                    _MAPAS.pop(pasta.name, None)
                return JsonResponse({"status": "sucesso", "msg": "Envio cancelado."})
        except ArmazenamentoIndisponivel as erro:
            return self._erro(str(erro), erro.titulo)
        except OSError:
            log.exception("restaurar fotos: o disco da instância recusou")
            return self._erro("O servidor não conseguiu guardar o envio agora. Tente de novo em instantes.",
                              "Envio interrompido", status=409)
        return self._erro("Ação desconhecida.", "Não deu para continuar")

    @staticmethod
    def _erro(texto, titulo, status=400, campo=""):
        corpo = {"status": "erro", "msg": texto, "titulo": titulo}
        if campo:
            corpo["campo"] = campo
        return JsonResponse(corpo, status=status)

    # ------------------------------------------------------------------
    # A FOTO DE UM CARD (seção 133)
    # ------------------------------------------------------------------
    def _enviar(self, request):
        """A foto que o dono escolheu para UM card: vai para o banco e troca o nome em todo campo que o usava."""
        from PIL import Image, UnidentifiedImageError

        nome = str(request.POST.get("nome") or "").strip()
        arquivo = request.FILES.get("arquivo")
        if not nome:
            return self._erro("Escolha o card da foto que vai receber este arquivo.", "Qual foto?")
        if arquivo is None or not arquivo.size:
            return self._erro("Escolha a foto no celular ou no computador.", "Nenhuma foto escolhida", campo="arquivo")
        limite = espelho_midia._limite()
        if arquivo.size > limite:
            return self._erro(f"A foto passa de {int(limite / (1024 * 1024))} MB. Envie uma versão menor.",
                              "Foto grande demais", campo="arquivo")
        grupo = fotos_que_faltam.usos_de([nome]).get(nome)
        if not grupo or not fotos_que_faltam.e_publico(grupo):
            # já voltou (outro envio, a exportação, o espelho) ou ninguém usa mais
            return JsonResponse({"status": "ja", "nome": nome, "titulo": "Esta foto já voltou",
                                 "msg": "Ela não está mais faltando: atualize a tela para ver como ficou."})
        dados = arquivo.read(limite + 1)
        serve, tipo = restaurar_midia._aceita(dados, grupo)
        if serve and tipo.startswith("image/"):
            try:
                with Image.open(io.BytesIO(dados)) as foto:
                    foto.verify()
            except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
                serve = False
        if not serve:
            esperado = "um arquivo 3D (.glb)" if "glb" in fotos_que_faltam.aceita(grupo) else "uma foto (JPG, PNG ou WebP)"
            return self._erro(f"O arquivo “{arquivo.name}” não é {esperado}.", "Este arquivo não serve", campo="arquivo")
        antigo = nome[len(PREFIXO):] if nome.startswith(PREFIXO) else nome
        para, houve = espelho_midia.gravar_conteudo(antigo, grupo, dados, origem="envio", exata=True)
        espelho_midia.limpar_caches()
        log.info("fotos que faltam: %s voltou pelo envio do dono (%s)", antigo, houve)
        faltam = len(fotos_que_faltam.pendentes(somente_publicos=True))
        url = _url_da_foto(para)
        if houve == "trocado":
            # a original no lugar da provisória fica no MESMO endereço: o card do painel pede a nova
            # (a entrega ignora o "v"; no site, a provisória sai com cache de um dia e o espelho/disco já trocou)
            url += f"&v={int(time.time())}"
        return JsonResponse({
            "status": "sucesso", "nome": nome, "para": para, "houve": houve,
            "url": url, "faltam": faltam,
            "msg": "A foto voltou e já aparece no site.",
        })

    def _casar(self, request):
        """Os nomes dos arquivos soltos (sem os arquivos): qual card cada um restaura, ou os candidatos."""
        arquivos = [str(a)[-200:] for a in request.POST.getlist("arquivos") if str(a).strip()][:200]
        pendentes = fotos_que_faltam.pendentes(somente_publicos=True)
        cards = [{"nome": nome, "chaves": fotos_que_faltam.chaves_do_nome(nome)} for nome in pendentes]
        return JsonResponse({"status": "sucesso", "resultado": fotos_que_faltam.casar(arquivos, cards)})

    def _comecar(self, request):
        _limpar_esquecidos()
        nome = str(request.POST.get("nome") or "arquivo")[-180:]
        try:
            tamanho = int(request.POST.get("tamanho") or 0)
        except ValueError:
            tamanho = 0
        if tamanho <= 0:
            return self._erro("O arquivo está vazio.", "Arquivo vazio", campo="arquivos")
        if tamanho > restaurar_midia.LIMITE_DO_ZIP:
            return self._erro(
                "O arquivo passa de 500 MB. No Cloudinary, exporte por pasta (uma pasta por vez) e envie cada ZIP.",
                "Arquivo grande demais", campo="arquivos",
            )
        token = secrets.token_hex(16)
        pasta = _pasta_dos_envios() / token
        pasta.mkdir(parents=True, exist_ok=False)
        (pasta / "arquivo").write_bytes(b"")
        _gravar_meta(pasta, {"nome": nome, "tamanho": tamanho, "recebido": 0, "inicio": 0,
                             "resultado": None, "criado": time.time()})
        return JsonResponse({"status": "sucesso", "envio": token, "pedaco": PEDACO})

    def _pedaco(self, request):
        pasta = _envio(request.POST.get("envio"))
        if pasta is None:
            return self._erro("Este envio não existe mais (o servidor foi reiniciado?). Envie de novo.",
                              "Envio perdido", status=410)
        meta = _meta(pasta)
        pedaco = request.FILES.get("pedaco")
        try:
            posicao = int(request.POST.get("posicao") or -1)
        except ValueError:
            posicao = -1
        if pedaco is None or pedaco.size > PEDACO or posicao != meta["recebido"]:
            # a posição que o navegador mandou não é a que o servidor tem: ele recomeça daqui
            return JsonResponse({"status": "erro", "msg": "Pedaço fora de ordem.", "titulo": "Envio interrompido",
                                 "recebido": meta["recebido"]}, status=409)
        if meta["recebido"] + pedaco.size > meta["tamanho"]:
            return self._erro("O envio passou do tamanho do arquivo.", "Envio interrompido", status=409)
        with open(pasta / "arquivo", "ab") as destino:
            for bloco in pedaco.chunks():
                destino.write(bloco)
        meta["recebido"] += pedaco.size
        _gravar_meta(pasta, meta)
        return JsonResponse({"status": "sucesso", "recebido": meta["recebido"], "tamanho": meta["tamanho"]})

    def _processar(self, request):
        pasta = _envio(request.POST.get("envio"))
        if pasta is None:
            return self._erro("Este envio não existe mais (o servidor foi reiniciado?). Envie de novo.",
                              "Envio perdido", status=410)
        meta = _meta(pasta)
        if meta["recebido"] != meta["tamanho"]:
            return self._erro("O arquivo ainda não chegou inteiro.", "Envio incompleto", status=409)
        arquivo = pasta / "arquivo"
        mapa, _quando = _MAPAS.get(pasta.name, (None, 0))
        if mapa is None:
            mapa = restaurar_midia.Mapa()
            _MAPAS[pasta.name] = (mapa, time.time())
        anterior = meta.get("resultado") or {}
        resultado = restaurar_midia.Resultado(
            restaurados=anterior.get("restaurados", []), nao_referenciados=anterior.get("nao_referenciados", []),
            ja=anterior.get("ja", []), recusados=anterior.get("recusados", []),
        )
        if restaurar_midia.e_zip(arquivo):
            try:
                resultado, proximo, total = restaurar_midia.importar_zip(
                    arquivo, inicio=int(meta.get("inicio") or 0), prazo=PRAZO_POR_IDA, mapa=mapa, resultado=resultado,
                )
            except Exception:  # noqa: BLE001 -- o ZIP quebrado vira janela, não 500
                log.exception("restaurar fotos: o ZIP %s não abriu", meta["nome"])
                shutil.rmtree(pasta, ignore_errors=True)
                return self._erro("O ZIP não abriu (está corrompido ou incompleto). Baixe de novo do Cloudinary.",
                                  "ZIP com defeito", campo="arquivos")
        else:
            dados = arquivo.read_bytes()
            if len(dados) > espelho_midia._limite():
                shutil.rmtree(pasta, ignore_errors=True)
                return self._erro("A foto passa do limite por arquivo.", "Arquivo grande demais", campo="arquivos")
            restaurar_midia.importar_um(meta["nome"], dados, mapa, resultado)
            if resultado.restaurados:
                espelho_midia.limpar_caches()
            proximo, total = None, 1
        meta["inicio"] = proximo or total
        meta["resultado"] = {
            "restaurados": resultado.restaurados, "nao_referenciados": resultado.nao_referenciados,
            "ja": resultado.ja, "recusados": resultado.recusados,
        }
        if proximo is None:
            shutil.rmtree(pasta, ignore_errors=True)
            _MAPAS.pop(pasta.name, None)
        else:
            _gravar_meta(pasta, meta)
        return JsonResponse({
            "status": "sucesso", "proximo": proximo, "total": total, "feitos": proximo or total,
            "nome": meta["nome"], **_resultado_json(resultado),
        })

    def _copias(self):
        resultado = restaurar_midia.restaurar_das_copias()
        quantos = len(resultado.restaurados)
        texto = (
            ("1 foto voltou" if quantos == 1 else f"{quantos} fotos voltaram") + " do repositório para o banco."
            if quantos else "Nenhuma foto nova com cópia certa no repositório."
        ) + (
            f" Ainda {'falta 1' if len(resultado.faltando) == 1 else f'faltam {len(resultado.faltando)}'} sem cópia: "
            "elas voltam com a exportação do Cloudinary."
            if resultado.faltando else " Nenhuma foto do site depende mais do Cloudinary."
        )
        return JsonResponse({
            "status": "sucesso", "msg": texto,
            "janela": {
                "titulo": "Cópias do repositório", "texto": texto, "nivel": "sucesso" if quantos else "info",
                "icone": "salvo" if quantos else "info",
                "lista": [f"{i['nome']} ← {i['de']}" for i in resultado.restaurados[:12]] or None,
            },
            **_resultado_json(resultado),
        })
