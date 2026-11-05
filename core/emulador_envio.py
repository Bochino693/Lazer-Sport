"""O envio dos arquivos de um jogo de console, do navegador ao armazenamento -- usado pelo painel e pelo /system/.

O CAMINHO (o mesmo nas duas telas; o navegador roda
`sistema_interno/static/interno/emulador-envio.js`):

1. CONFERIR. O navegador manda só o nome, o tamanho e o começo de cada
   arquivo (e o fim dos .zip). `conferir` lê o .cue/.m3u, diz o que falta e
   reconhece o sistema (`core/jogos_emulador.py`). Com o jogo já salvo,
   devolve também o PLANO: cada arquivo (menos o índice, que fica no banco)
   em pedaços de ~9 MB para o Cloudinary, ou inteiro para o balde de jogos
   grandes quando ele está ligado -- cada envio já assinado.
2. ENVIAR. O navegador manda cada pedaço DIRETO para o armazenamento (o
   disco não passa pelo servidor). Sem o Cloudinary (computador de quem
   desenvolve, testes), os pedaços vêm para o site: `guardar_pedaco`.
3. CONFIRMAR. `confirmar` confere a resposta de cada pedaço (assinada pelo
   Cloudinary), relê o começo de cada arquivo do armazenamento, analisa de
   novo e troca o conjunto do jogo inteiro de uma vez. O que deu errado sai
   do armazenamento; o conjunto antigo sai depois do commit.

Os erros que a pessoa precisa ler são `ErroDeEnvio` (um ValueError): o
painel e o /system/ devolvem a frase como está.
"""

from __future__ import annotations

import json
import logging
import secrets

from django.core import signing
from django.db import transaction

from . import armazenamento_grande, armazenamento_pedacos
from . import jogos_emulador as emu
from .models import ArquivoEmulador, JogoCadastrado

log = logging.getLogger("sistema_interno.jogos")

MB = 1024 * 1024
SAL_DO_PLANO = "sistema_interno.jogos.emulador.plano"
#: Os trechos de uma conferência: o navegador manda no máximo uns 8 MB.
MAX_TRECHOS = 12 * MB
#: O link de envio vale 6 h; o plano assinado, um pouco mais.
VALIDADE_DO_PLANO = armazenamento_grande.VALIDADE_DO_ENVIO + 3600


class ErroDeEnvio(ValueError):
    """Falha que a pessoa precisa ler (arquivo faltando, pedaço que não chegou...)."""


def modo_de_envio():
    """"grande" (o balde S3/R2 ligado: arquivo inteiro, direto) ou "pedacos" (o Cloudinary de sempre)."""
    return "grande" if armazenamento_grande.configurado() else "pedacos"


def limite_do_modo(modo):
    """O teto de cada arquivo do jogo, conforme para onde ele vai."""
    if modo == "grande":
        return armazenamento_grande.limite_por_arquivo()
    return armazenamento_pedacos.limite_por_arquivo()


def contexto():
    """O que a tela precisa saber para montar o envio (vai como JSON para o navegador)."""
    modo = modo_de_envio()
    ligados = emu.sistemas_ligados()
    return {
        "modo": modo,
        "destino": armazenamento_pedacos.destino() if modo == "pedacos" else "balde",
        "pedaco_mb": round(armazenamento_pedacos.tamanho_do_pedaco() / MB, 1),
        "limite_mb": round(limite_do_modo(modo) / MB),
        "faltando": armazenamento_grande.faltando(),
        "sistemas": [
            {"codigo": codigo, "nome": s.nome, "ligado": codigo in ligados, "licenca": s.licenca, "nucleo": s.nucleo,
             "formato": s.formato, "comandos": s.comandos}
            for codigo, s in emu.SISTEMAS.items()
        ],
        # o que o painel sabe o que é: o resto, solto numa pasta, vira o .zip do fliperama
        "extensoes": sorted(emu.CONHECIDAS),
        # a capa que o painel desenha ("Criar capa"): a cor, a estante e o selo de cada console
        "temas": _temas_das_capas(),
        "cabeca": emu.CABECA,
        "cauda": emu.CAUDA,
        "max_arquivos": emu.MAX_ARQUIVOS,
    }


def particular_pedido(jogo, post):
    """O jogo é (ou vai ser salvo como) particular: aí qualquer console reconhecido roda."""
    marcado = str(post.get("particular") or "").strip().lower() in ("on", "true", "1")
    return marcado or bool(jogo is not None and getattr(jogo, "particular", False))


def _temas_das_capas():
    from . import portal_jogos

    temas = {
        codigo: {"estante": estante, "cor": portal_jogos.TEMA[estante]["cor"], "nome": portal_jogos.TEMA[estante]["nome"],
                 "sigla": portal_jogos.SIGLAS.get(codigo, "")}
        for codigo, estante in portal_jogos.FAMILIAS.items()
    }
    for chave in ("nosso", "html"):
        tema = portal_jogos.TEMA[chave]
        temas[chave] = {"estante": chave, "cor": tema["cor"], "nome": tema["nome"], "sigla": "L&S" if chave == "nosso" else "HTML5"}
    return temas


def sistema_pedido(post):
    sistema = (post.get("sistema") or "").strip()
    if sistema in ("", JogoCadastrado.AUTOMATICO):
        return ""
    if sistema not in emu.SISTEMAS:
        raise ErroDeEnvio("Sistema desconhecido.")
    return sistema


def exigir_ok(analise):
    if analise.ok:
        return
    erros = analise.erros or ["Não deu para montar o jogo com esses arquivos."]
    extra = f" (e mais {len(erros) - 1} problema{'s' if len(erros) > 2 else ''})" if len(erros) > 1 else ""
    raise ErroDeEnvio(erros[0] + extra)


# ---------------------------------------------------------------- 1. conferir


def conferir(jogo, post, files, url_da_acao):
    """Analisa o conjunto pelos trechos; com `jogo` salvo, devolve também o plano de envio."""
    try:
        manifesto = json.loads(post.get("manifesto") or "[]")
    except ValueError as exc:
        raise ErroDeEnvio("A lista de arquivos veio quebrada.") from exc
    if not isinstance(manifesto, list) or not manifesto:
        raise ErroDeEnvio("Selecione os arquivos do jogo.")
    if len(manifesto) > emu.MAX_ARQUIVOS + 20:
        raise ErroDeEnvio(f"São arquivos demais (o limite é {emu.MAX_ARQUIVOS} por jogo).")
    # os trechos (o começo de cada arquivo, o fim dos .zip) vêm colados num
    # arquivo só, com o lugar de cada um no manifesto: um por arquivo
    # estouraria o teto de arquivos por requisição do Django (100)
    enviados = files.get("trechos")
    if enviados is not None and enviados.size > MAX_TRECHOS:
        raise ErroDeEnvio("Os trechos para conferir vieram grandes demais.")
    trechos = enviados.read() if enviados is not None else b""

    def trecho(item, campo, teto):
        par = item.get(campo)
        if not par:
            return b""
        inicio, quantos = int(par[0]), int(par[1])
        if inicio < 0 or quantos < 0 or quantos > teto or inicio + quantos > len(trechos):
            raise ErroDeEnvio("Os trechos para conferir vieram quebrados.")
        return trechos[inicio:inicio + quantos]

    entradas = []
    for item in manifesto:
        try:
            entradas.append(emu.entrada_de_trechos(
                str(item["nome"]), int(item["tamanho"]),
                trecho(item, "cabeca", emu.CABECA), trecho(item, "cauda", emu.CAUDA),
            ))
        except ErroDeEnvio:
            raise
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ErroDeEnvio("A lista de arquivos veio quebrada.") from exc
    modo = modo_de_envio()
    analise = emu.analisar(entradas, sistema_pedido(post), ligados=emu.sistemas_para(particular_pedido(jogo, post)),
                           limite_por_arquivo=limite_do_modo(modo))
    resposta = {"analise": analise.para_json(), "modo": modo}
    if jogo is not None and analise.ok:
        resposta.update(_plano_de_envio(jogo, analise, modo, url_da_acao))
    return analise, resposta


def _plano_de_envio(jogo, analise, modo, url_da_acao):
    """Para cada arquivo (menos o índice, que o site guarda): os envios, um por pedaço."""
    lote = secrets.token_hex(6)
    destino = armazenamento_pedacos.destino()
    envios, arquivos = [], []
    for numero, peca in enumerate(p for p in analise.pecas if p.conteudo is None):
        tamanho = peca.entrada.tamanho
        base = f"jogos/emulador/{jogo.slug}/{lote}"
        partes = []
        if modo == "grande":
            chave = f"{base}/{peca.nome}"
            partes.append({"id": chave, "inicio": 0, "fim": tamanho,
                           "url": armazenamento_grande.url_para_enviar(chave), "metodo": "PUT", "campos": {}})
        else:
            for ordem, (de, ate) in enumerate(armazenamento_pedacos.dividir(tamanho)):
                ident = f"{base}/{numero:02d}-{ordem:04d}.parte"
                envio = (armazenamento_pedacos.envio_cloudinary(ident) if destino == "cloudinary"
                         else armazenamento_pedacos.envio_site(url_da_acao, jogo.pk, ident, ate - de))
                partes.append({"id": ident, "inicio": de, "fim": ate, **envio})
        envios.append({"enviado": peca.entrada.nome, "nome": peca.nome, "tamanho": tamanho, "partes": partes})
        arquivos.append({"nome": peca.nome, "tamanho": tamanho,
                         "partes": [{k: p[k] for k in ("id", "inicio", "fim")} for p in partes]})
    plano = signing.dumps(
        {"jogo": jogo.pk, "lote": lote, "modo": modo, "destino": destino, "arquivos": arquivos}, salt=SAL_DO_PLANO,
    )
    return {"envios": envios, "plano": plano, "destino": destino if modo == "pedacos" else "balde"}


# ---------------------------------------------------------------- 2. o pedaço que veio para o site


def guardar_pedaco(post, files):
    """Um pedaço que veio para o próprio site (sem o Cloudinary): guarda e responde como o Cloudinary."""
    arquivo = files.get("file")
    if arquivo is None:
        raise ErroDeEnvio("O pedaço não veio.")
    try:
        jogo_id, resposta = armazenamento_pedacos.guardar_no_site(post.get("pedaco") or "", arquivo)
    except signing.BadSignature as exc:
        raise ErroDeEnvio("O envio expirou ou não é deste painel: confira os arquivos de novo.") from exc
    if not JogoCadastrado.objects.filter(pk=jogo_id).exists():
        raise ErroDeEnvio("Jogo não encontrado.")
    return resposta


# ---------------------------------------------------------------- 3. confirmar


def confirmar(jogo, post, files, origem_do_site):
    """Confere o que chegou, relê o começo de cada arquivo, analisa de novo e guarda. -> (analise, problemas)."""
    try:
        plano = signing.loads(post.get("plano") or "", salt=SAL_DO_PLANO, max_age=VALIDADE_DO_PLANO)
    except signing.BadSignature as exc:
        raise ErroDeEnvio("O envio expirou ou não é deste painel: confira os arquivos de novo.") from exc
    if plano.get("jogo") != jogo.pk:
        raise ErroDeEnvio("Esse envio é de outro jogo.")
    modo = plano.get("modo", "grande")
    if modo == "grande" and not armazenamento_grande.configurado():
        raise ErroDeEnvio("O armazenamento de jogos grandes não está ligado.")
    try:
        respostas = json.loads(post.get("respostas") or "{}")
    except ValueError as exc:
        raise ErroDeEnvio("As respostas do envio vieram quebradas.") from exc
    if not isinstance(respostas, dict):
        raise ErroDeEnvio("As respostas do envio vieram quebradas.")

    enviados = []  # o que já está no armazenamento, para apagar se der errado
    entradas, guardado = [], {}
    try:
        for item in plano["arquivos"]:
            if modo == "grande":
                entrada, onde = _conferir_no_balde(item)
            else:
                entrada, onde = _conferir_pedacos(item, respostas, plano["destino"], enviados)
            entradas.append(entrada)
            guardado[item["nome"]] = onde
        # os índices (.cue, .m3u...) não vão para o armazenamento: vêm de novo aqui, pequenos
        for arquivo in files.getlist("indices"):
            if emu.extensao(arquivo.name) not in emu.INDICES or arquivo.size > emu.MAX_INDICE:
                raise ErroDeEnvio(f"“{arquivo.name}” não é um índice (.cue, .ccd, .toc, .m3u).")
            entradas.append(emu.entrada_de_arquivo(arquivo))
        analise = emu.analisar(entradas, sistema_pedido(post), ligados=emu.sistemas_para(particular_pedido(jogo, post)),
                           limite_por_arquivo=limite_do_modo(modo))
        exigir_ok(analise)
    except ErroDeEnvio:
        _desfazer_envio(plano, modo, enviados)
        raise

    novos = []
    for ordem, peca in enumerate(analise.pecas):
        registro = ArquivoEmulador(
            jogo=jogo, nome=peca.nome, papel=peca.papel, disco=peca.disco,
            tamanho=peca.entrada.tamanho, lote=plano["lote"], ordem=ordem,
        )
        if peca.conteudo is not None:
            registro.conteudo = peca.conteudo
        elif modo == "grande":
            registro.chave = guardado[peca.entrada.nome]
        else:
            registro.pedacos = guardado[peca.entrada.nome]
        novos.append(registro)
    usados = {r.nome for r in novos if not r.e_indice}
    sobras_balde = [onde for nome, onde in guardado.items() if nome not in usados and modo == "grande"]
    sobras_pedacos = [p for nome, lista in guardado.items() if nome not in usados and modo != "grande" for p in lista]
    antigos = trocar_conjunto(jogo, novos, analise)

    def limpar():
        apagar_do_armazenamento(antigos, jogo.slug)
        if sobras_balde:
            armazenamento_grande.apagar(sobras_balde)
        if sobras_pedacos:
            _apagar_pedacos(sobras_pedacos, jogo.slug)

    transaction.on_commit(limpar)
    problemas = []
    if modo == "grande" and usados:
        # o balde mal configurado deixa o jogo abrir sem as faixas: conferir como o visitante confere
        principal = next((r.chave for r in novos if r.papel == ArquivoEmulador.JOGO and r.chave), None)
        chaves = sorted(r.chave for r in novos if r.chave)
        problemas = armazenamento_grande.diagnosticar(principal or chaves[0], origem_do_site, principal)
        for problema in problemas:
            log.warning("balde dos jogos grandes (%s): %s", jogo.slug, problema)
    return analise, problemas


def _conferir_no_balde(item):
    chave = item["partes"][0]["id"]
    tamanho = armazenamento_grande.tamanho(chave)
    if tamanho is None:
        raise ErroDeEnvio(f"“{item['nome']}” não chegou ao armazenamento. Envie de novo.")
    if tamanho != item["tamanho"]:
        raise ErroDeEnvio(f"“{item['nome']}” chegou com outro tamanho. Envie de novo.")
    return armazenamento_grande.entrada_remota(item["nome"], chave, tamanho), chave


def _conferir_pedacos(item, respostas, destino, enviados):
    pedacos = []
    total = len(item["partes"])
    for ordem, parte in enumerate(item["partes"], start=1):
        tamanho = parte["fim"] - parte["inicio"]
        resposta = respostas.get(parte["id"])
        try:
            if destino == "cloudinary":
                pedaco = armazenamento_pedacos.conferir_cloudinary(resposta, parte["id"], tamanho)
            else:
                pedaco = armazenamento_pedacos.conferir_site(resposta, parte["id"], tamanho)
        except (ValueError, KeyError, TypeError) as exc:
            raise ErroDeEnvio(
                f"O pedaço {ordem} de {total} de “{item['nome']}” não chegou certo ({exc}). Envie de novo."
            ) from exc
        pedacos.append(pedaco)
        enviados.append(pedaco)
    guardado = {}

    def ler(inicio, quantos):
        if inicio + quantos <= emu.CABECA:
            if "cabeca" not in guardado:
                guardado["cabeca"] = armazenamento_pedacos.ler(pedacos, 0, min(emu.CABECA, item["tamanho"]))
            return guardado["cabeca"][inicio:inicio + quantos]
        return armazenamento_pedacos.ler(pedacos, inicio, quantos)

    return emu.Entrada(item["nome"], item["tamanho"], ler, pedacos), pedacos


def _desfazer_envio(plano, modo, enviados):
    """O envio não vai ser guardado: o que já subiu sai do armazenamento (melhor esforço)."""
    if modo == "grande":
        try:
            armazenamento_grande.apagar([a["partes"][0]["id"] for a in plano["arquivos"]])
        except Exception as erro:  # noqa: BLE001
            log.warning("envio desfeito, mas o balde não apagou: %r", erro)
    elif enviados:
        _apagar_pedacos(enviados, "")


# ---------------------------------------------------------------- o conjunto do jogo


def trocar_conjunto(jogo, novos, analise):
    """Troca o conjunto inteiro de uma vez; devolve os antigos (para apagar depois do commit)."""
    antigos = list(jogo.arquivos_emulador.all())
    jogo.arquivos_emulador.all().delete()
    ArquivoEmulador.objects.bulk_create(novos)
    jogo.sistema = analise.sistema
    jogo.emulador_resumo = analise.resumo()[:200]
    jogo.save(update_fields=["sistema", "emulador_resumo", "atualizado"])
    return antigos


def remover(jogo):
    """Tira todos os arquivos do emulador do jogo (do armazenamento, depois do commit)."""
    antigos = list(jogo.arquivos_emulador.all())
    jogo.arquivos_emulador.all().delete()
    jogo.emulador_resumo = ""
    jogo.save(update_fields=["emulador_resumo", "atualizado"])
    transaction.on_commit(lambda: apagar_do_armazenamento(antigos, jogo.slug))


def mensagem_de_pronto(jogo, analise, problemas):
    if problemas:
        situacao = " ATENÇÃO: " + " ".join(problemas)
    elif jogo.ativo and not (jogo.endereco or jogo.arquivo_html):
        situacao = " Já está no ar."
    else:
        situacao = ""
    return f"Arquivos guardados: {analise.resumo()}.{situacao}"


def _apagar_pedacos(pedacos, slug):
    try:
        armazenamento_pedacos.apagar(pedacos)
    except Exception as erro:  # noqa: BLE001
        log.warning("pedaços do emulador de %s não apagados: %r", slug, erro)


def apagar_do_armazenamento(registros, slug):
    """Apaga do armazenamento os arquivos de um conjunto que saiu (melhor esforço)."""
    chaves = [r.chave for r in registros if r.chave]
    if chaves:
        try:
            armazenamento_grande.apagar(chaves)
        except Exception as erro:  # noqa: BLE001
            log.warning("arquivos do emulador de %s não apagados do balde: %r", slug, erro)
    pedacos = [p for r in registros for p in (r.pedacos or [])]
    if pedacos:
        _apagar_pedacos(pedacos, slug)
    for registro in registros:
        if registro.arquivo:
            try:
                registro.arquivo.storage.delete(registro.arquivo.name)
            except Exception as erro:  # noqa: BLE001
                log.warning("arquivo do emulador de %s não apagado: %r", slug, erro)
