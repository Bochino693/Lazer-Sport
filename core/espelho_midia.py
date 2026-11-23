"""O ESPELHO: o que ainda está só no Cloudinary vem para o nosso banco (seção 130).

Todo campo de arquivo (foto, .glb, documento privado) cujo nome NÃO começa
com "banco/" ainda aponta para o Cloudinary. O espelho baixa cada um (a foto
pelo endereço público; o documento privado pela URL assinada do Cloudinary
autenticado), guarda em `ArquivoNoBanco` como "banco/<nome de antes>" e
troca o nome no campo -- com `update()`, sem sinal nenhum, e só se o campo
ainda tem o nome de antes (quem trocou a foto nesse meio-tempo ganha).

ENQUANTO O CLOUDINARY ESTÁ DESATIVADO (401 "cloud_name ... is disabled"), a
rodada para no primeiro "fora do ar" e espera (MIDIA_ESPELHO_ESPERA_MIN, 30
min) para tentar de novo. No instante em que o dono reativar a conta, tudo é
copiado sozinho, e daí em diante o Cloudinary não faz mais falta.

ONDE RODA. `python manage.py espelhar_midia` (na frente de quem rodou) e,
no Render, uma linha de fundo por processo (`ligar()`, do CoreConfig.ready),
nunca nos testes nem num comando de manutenção. Dois processos não espelham
ao mesmo tempo: no PostgreSQL a rodada segura um advisory lock. A primeira
coisa que a linha de fundo faz é restaurar das cópias do repositório
(core/restaurar_midia.py) -- o que tem cópia volta sem esperar o Cloudinary.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from dataclasses import dataclass, field

from django.conf import settings

from .arquivos_no_banco import (
    CloudinaryForaDoAr,
    PREFIXO,
    e_do_banco,
    guardar,
    nome_do_espelho,
    preparar_imagem,
    substituir,
    tipo_do_conteudo,
)

log = logging.getLogger("lazer.midia")

#: Chave do advisory lock do PostgreSQL ("LSMIDIA" em números).
TRAVA = 7_653_770_073


@dataclass
class Referencia:
    """Um campo de arquivo de um modelo e as linhas que usam um nome."""

    modelo: type
    campo: str
    storage: object
    max_length: int
    pks: list = field(default_factory=list)

    @property
    def rotulo(self):
        return f"{self.modelo._meta.label}.{self.campo}"


def _de_nos(storage) -> bool:
    try:
        return bool(getattr(storage, "espelha_no_banco", False))
    except Exception:  # noqa: BLE001 -- um storage estranho não é nosso
        return False


def campos_de_arquivo(somente_publicos=False):
    """{modelo: [campo, ...]} dos campos cujo armazenamento guarda no banco."""
    from django.apps import apps
    from django.db import models

    from .models import ArquivoNoBanco

    por_modelo = {}
    for modelo in apps.get_models():
        if modelo is ArquivoNoBanco or modelo._meta.proxy or not modelo._meta.managed:
            continue
        for campo in modelo._meta.concrete_fields:
            if not isinstance(campo, models.FileField) or not _de_nos(campo.storage):
                continue
            if somente_publicos and not getattr(campo.storage, "guarda_publico", False):
                continue
            por_modelo.setdefault(modelo, []).append(campo)
    return por_modelo


def referencias(*, somente_publicos=False, do_banco=False):
    """{nome: [Referencia, ...]} -- uma consulta por modelo (todos os campos de arquivo juntos).

    Sem `do_banco`, só os nomes de fora ("pendentes"); com ele, só os que já
    começam com "banco/".
    """
    from django.db.models import Q

    saida = {}
    for modelo, campos in campos_de_arquivo(somente_publicos).items():
        filtro = Q()
        for campo in campos:
            if do_banco:
                filtro |= Q(**{f"{campo.attname}__startswith": PREFIXO})
            else:
                filtro |= (
                    ~Q(**{f"{campo.attname}__startswith": PREFIXO})
                    & ~Q(**{campo.attname: ""})
                    & Q(**{f"{campo.attname}__isnull": False})
                )
        nomes = [c.attname for c in campos]
        try:
            linhas = list(modelo._base_manager.filter(filtro).values_list("pk", *nomes))
        except Exception:  # noqa: BLE001 -- a tabela que ainda não existe não para o espelho
            log.warning("midia: não deu para ler %s", modelo._meta.label, exc_info=True)
            continue
        for pk, *valores in linhas:
            for campo, valor in zip(campos, valores):
                if not valor or e_do_banco(valor) != do_banco:
                    continue
                grupo = saida.setdefault(valor, [])
                ref = next((r for r in grupo if r.modelo is modelo and r.campo == campo.attname), None)
                if ref is None:
                    ref = Referencia(modelo, campo.attname, campo.storage, campo.max_length or 100)
                    grupo.append(ref)
                ref.pks.append(pk)
    return saida


def nome_novo_para(nome_antigo, grupo):
    return nome_do_espelho(nome_antigo, min(r.max_length for r in grupo))


def repontar(nome_antigo, nome_novo, grupo) -> int:
    """Troca o nome nos campos (só onde ainda está o de antes). Devolve as linhas mudadas."""
    mudadas = 0
    for ref in grupo:
        filtro = {"pk__in": ref.pks, ref.campo: nome_antigo}
        mudadas += ref.modelo._base_manager.filter(**filtro).update(**{ref.campo: nome_novo})
        # a foto de peça guarda o nome já conferido pelo recorte (recorte_de):
        # acompanha, senão o recorte rodaria de novo numa foto que não mudou
        if any(f.name == "recorte_de" for f in ref.modelo._meta.concrete_fields):
            ref.modelo._base_manager.filter(pk__in=ref.pks, recorte_de=nome_antigo).update(recorte_de=nome_novo)
    return mudadas


def _publico_e_foto(grupo):
    storage = grupo[0].storage
    return bool(getattr(storage, "guarda_publico", False)) and getattr(storage, "legado", "image") == "image"


def gravar_conteudo(nome_antigo, grupo, dados, *, origem, exata=True):
    """Guarda `dados` como banco/<nome_antigo> e reponta os campos. Devolve (nome_novo, o que houve).

    O que houve: "novo", "trocado" (a cópia de reserva deu lugar à exata) ou
    "ja" (já estava no banco e não precisava mudar).
    """
    from django.db import IntegrityError

    from .models import ArquivoNoBanco

    nome_novo = nome_novo_para(nome_antigo, grupo)
    publico = bool(getattr(grupo[0].storage, "guarda_publico", False))
    tipo = tipo_do_conteudo(dados, nome_antigo)
    if _publico_e_foto(grupo):
        dados, tipo, _mudou = preparar_imagem(dados, tipo)
    existente = ArquivoNoBanco.objects.filter(nome=nome_novo).values_list("exata", flat=True).first()
    houve = "novo"
    if existente is None:
        try:
            guardar(nome_novo, dados, publico=publico, tipo=tipo, origem=origem, exata=exata)
        except IntegrityError:  # outro processo guardou no mesmo instante
            houve = "ja"
    elif not existente and exata:
        substituir(nome_novo, dados, tipo=tipo, origem=origem, exata=True)
        houve = "trocado"
    else:
        houve = "ja"
    if not e_do_banco(nome_antigo):
        repontar(nome_antigo, nome_novo, grupo)
    return nome_novo, houve


def limpar_caches():
    """As páginas guardadas em cache ainda têm o endereço de antes: o cache recomeça."""
    try:
        from django.core.cache import cache

        cache.clear()
    except Exception:  # noqa: BLE001
        log.warning("midia: não deu para limpar o cache", exc_info=True)
    try:
        from . import fotos

        fotos._URLS.clear()
    except Exception:  # noqa: BLE001
        pass


def _limite():
    try:
        return int(getattr(settings, "MIDIA_ESPELHO_LIMITE_MB", 25)) * 1024 * 1024
    except (TypeError, ValueError):
        return 25 * 1024 * 1024


def espelhar(*, avisar=None, simular=False, limite=None, parar_depois_de=None):
    """Uma rodada. Devolve o resumo: copiados, repontados, faltando, grandes, falhas, fora_do_ar, pendentes."""
    from .models import ArquivoNoBanco

    avisar = avisar or (lambda texto: None)
    limite = limite or _limite()
    resultado = {
        "copiados": 0, "repontados": 0, "trocados": 0, "faltando": [], "grandes": [], "falhas": 0,
        "fora_do_ar": False, "pendentes": 0,
    }
    pendentes = referencias()
    resultado["pendentes"] = len(pendentes)
    candidatos = {nome: nome_novo_para(nome, grupo) for nome, grupo in pendentes.items()}
    ja_no_banco = set()
    lista = list(candidatos.values())
    for i in range(0, len(lista), 500):
        ja_no_banco.update(ArquivoNoBanco.objects.filter(nome__in=lista[i:i + 500]).values_list("nome", flat=True))

    seguidas = 0
    mudou = False
    for ordem, (nome, grupo) in enumerate(pendentes.items(), start=1):
        if parar_depois_de and ordem > parar_depois_de:
            break
        novo = candidatos[nome]
        if novo in ja_no_banco:
            if not simular:
                repontar(nome, novo, grupo)
                mudou = True
            resultado["repontados"] += 1
            continue
        if simular:
            continue
        try:
            dados = grupo[0].storage.baixar_legado(nome)
            seguidas = 0
        except CloudinaryForaDoAr as erro:
            resultado["fora_do_ar"] = True
            avisar(f"O Cloudinary está fora do ar ({erro}): o espelho tenta de novo mais tarde.")
            break
        except FileNotFoundError:
            resultado["faltando"].append(nome)
            continue
        except Exception as erro:  # noqa: BLE001 -- rede: conta e segue; cinco seguidas, para
            resultado["falhas"] += 1
            seguidas += 1
            log.warning("midia: o espelho não baixou %s: %r", nome, erro)
            if seguidas >= 5:
                avisar("Cinco falhas seguidas de rede: a rodada para aqui.")
                break
            continue
        if len(dados) > limite:
            resultado["grandes"].append(nome)
            continue
        gravar_conteudo(nome, grupo, dados, origem="cloudinary", exata=True)
        resultado["copiados"] += 1
        mudou = True
        avisar(f"Copiado: {nome}")

    if not resultado["fora_do_ar"] and not simular:
        resultado["trocados"] = _trocar_reservas(avisar)
        mudou = mudou or bool(resultado["trocados"])
    if mudou:
        limpar_caches()
    return resultado


def _trocar_reservas(avisar):
    """A cópia de reserva (exata=False) dá lugar à original do Cloudinary, quando ele responde."""
    from cloudinary_storage.storage import MediaCloudinaryStorage

    from .arquivos_no_banco import baixar_endereco
    from .models import ArquivoNoBanco

    trocados = 0
    legado = MediaCloudinaryStorage()
    for nome in ArquivoNoBanco.objects.filter(exata=False, publico=True).values_list("nome", flat=True):
        antigo = nome[len(PREFIXO):]
        try:
            dados = baixar_endereco(legado.url(antigo))
        except CloudinaryForaDoAr:
            break
        except Exception:  # noqa: BLE001 -- a original não veio: a reserva fica
            continue
        dados, tipo, _mudou = preparar_imagem(dados, tipo_do_conteudo(dados, antigo))
        substituir(nome, dados, tipo=tipo, origem="cloudinary", exata=True)
        trocados += 1
        avisar(f"Trocada pela original: {nome}")
    return trocados


def orfaos(horas=24):
    """As linhas do banco que nenhum campo usa mais (a foto trocada no painel): [(nome, tamanho)].

    O banco não apaga sozinho a foto que um cadastro trocou (o Cloudinary
    também não apagava). Só entram as linhas com mais de `horas` horas, para
    não pegar um envio que ainda está sendo gravado. Confere TODO campo de
    arquivo (de qualquer armazenamento) e o `recorte_de` das peças.
    """
    from datetime import timedelta

    from django.apps import apps
    from django.db import models
    from django.db.models import Q
    from django.utils import timezone

    from .models import ArquivoNoBanco

    usados = set()
    for modelo in apps.get_models():
        if modelo is ArquivoNoBanco or modelo._meta.proxy or not modelo._meta.managed:
            continue
        nomes = [c.attname for c in modelo._meta.concrete_fields
                 if isinstance(c, models.FileField) or c.name == "recorte_de"]
        if not nomes:
            continue
        filtro = Q()
        for nome in nomes:
            filtro |= Q(**{f"{nome}__startswith": PREFIXO})
        try:
            for valores in modelo._base_manager.filter(filtro).values_list(*nomes):
                usados.update(v for v in valores if v and e_do_banco(v))
        except Exception:  # noqa: BLE001 -- sem a tabela, nada dela conta (e nada se apaga por isso)
            log.warning("midia: não deu para ler %s ao procurar órfãos", modelo._meta.label)
            return []
    limite = timezone.now() - timedelta(hours=horas)
    return [
        (nome, tamanho)
        for nome, tamanho in ArquivoNoBanco.objects.filter(criado_em__lt=limite).values_list("nome", "tamanho")
        if nome not in usados
    ]


# ======================================================================
# A LINHA DE FUNDO (só no Render)
# ======================================================================
_trava = threading.Lock()
_thread = None
_estado = {"ultima": None, "proxima": None, "resultado": None, "restauracao": None}


def estado():
    """O que a linha de fundo fez por último (para a tela "Restaurar fotos")."""
    return dict(_estado)


def ativo() -> bool:
    if not getattr(settings, "MIDIA_ESPELHO_AUTOMATICO", False) or not getattr(settings, "IS_RENDER", False):
        return False
    from .sempre_pronto import _comando_de_manutencao

    # nunca num comando (`manage.py ...`): só no processo do site
    programa = (sys.argv[0] if sys.argv else "").rsplit("/", 1)[-1]
    return not _comando_de_manutencao() and programa != "manage.py"


def _com_trava(funcao):
    """Roda `funcao` segurando o advisory lock (PostgreSQL); None se outro processo está rodando."""
    from django.db import connection

    if connection.vendor != "postgresql":
        return funcao()
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [TRAVA])
        if not cursor.fetchone()[0]:
            return None
    try:
        return funcao()
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [TRAVA])


def _laco():
    from django.db import close_old_connections, connection

    time.sleep(90)  # o processo acabou de subir: a primeira tela é de quem abriu o site
    try:
        from . import restaurar_midia

        _estado["restauracao"] = _com_trava(lambda: restaurar_midia.restaurar_das_copias(avisar=log.info).resumo())
    except Exception:  # noqa: BLE001 -- a linha de fundo nunca derruba o site
        log.exception("midia: a restauração das cópias falhou")
    finally:
        connection.close()
    espera = max(5, int(getattr(settings, "MIDIA_ESPELHO_ESPERA_MIN", 30))) * 60
    while True:
        resultado = None
        try:
            close_old_connections()
            resultado = _com_trava(lambda: espelhar(avisar=log.info))
            if resultado is not None:
                _estado["resultado"] = {k: (len(v) if isinstance(v, list) else v) for k, v in resultado.items()}
                log.info("midia: espelho %s", _estado["resultado"])
        except Exception:  # noqa: BLE001
            log.exception("midia: a rodada do espelho falhou")
        finally:
            connection.close()
        _estado["ultima"] = time.time()
        if resultado and resultado.get("fora_do_ar"):
            pausa = espera
        elif resultado and resultado.get("pendentes") and (resultado["copiados"] or resultado["falhas"]):
            pausa = 60  # andou: a próxima rodada vem logo
        else:
            pausa = 6 * 3600  # nada a copiar (ou só o que o Cloudinary não tem)
        _estado["proxima"] = time.time() + pausa
        time.sleep(pausa)


def ligar() -> bool:
    """Sobe a linha de fundo, uma vez por processo, só no Render."""
    global _thread
    if not ativo():
        return False
    with _trava:
        if _thread is not None and _thread.is_alive():
            return False
        _thread = threading.Thread(target=_laco, name="espelho-midia", daemon=True)
        _thread.start()
    log.info("midia: espelho ligado")
    return True
