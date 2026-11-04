"""O objeto 3D (.glb) de cada brinquedo: onde fica e o que ele traz.

POR QUE ISTO EXISTE. Toda máquina vai ganhar o seu objeto 3D, para quem
visita o site ver além das fotos -- e nas cores que a fábrica oferece. O
arquivo entra no cadastro do brinquedo (o painel), e as CORES vêm de dentro
dele: as variações de material do glTF (a extensão KHR_materials_variants,
que é como os programas de 3D gravam "a mesma máquina em várias cores").
As MEDIDAS também: é o tamanho de verdade da máquina, com que a Arena
reserva o lugar dela antes de o objeto chegar. Aqui se lê esse arquivo
sem abrir o 3D: só o cabeçalho e o JSON do .glb.
"""

import json
import struct
import time

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import DatabaseError, connection

#: O maior .glb aceito no cadastro (o Cloudinary recusa arquivos "raw"
#: maiores que 10 MB no plano de entrada; acima disso, o upload falharia
#: no meio, depois da validação).
TAMANHO_MAXIMO = 10 * 1024 * 1024


# ----------------------------------------------------------------------
# ANTES DA MIGRAÇÃO
#
# O código novo pode chegar ao servidor antes de a migração que cria a
# tabela dos objetos 3D (0115) rodar no banco -- num deploy, ou num
# computador que puxou o código e ainda não rodou `migrate`. Sem a tabela,
# a consulta do 3D derrubava a Arena e a página do brinquedo com erro 500.
# Agora as telas conferem primeiro: sem a tabela, seguem sem o 3D do
# cadastro (as fotos e o resto da página de pé) até a migração rodar.
# ----------------------------------------------------------------------

_tabelas = {}  # db_table -> {"pronta": bool, "conferida": monotonic}


def tabela_pronta(modelo=None):
    """A tabela do modelo (por padrão, a dos objetos 3D) já existe no banco?

    Uma vez achada, não se confere mais. Enquanto não existe, confere de
    novo a cada 30 s (a migração pode rodar com o site no ar).
    """
    if modelo is None:
        from .models import ObjetoTresD

        modelo = ObjetoTresD
    nome = modelo._meta.db_table
    estado = _tabelas.setdefault(nome, {"pronta": False, "conferida": 0.0})
    if estado["pronta"]:
        return True
    agora = time.monotonic()
    if estado["conferida"] and agora - estado["conferida"] < 30:
        return False
    estado["conferida"] = agora
    try:
        with connection.cursor() as cursor:
            tabelas = connection.introspection.table_names(cursor)
    except DatabaseError:
        return False
    estado["pronta"] = nome in tabelas
    return estado["pronta"]


def prefetch_do_objeto():
    """O `prefetch_related` do objeto 3D, só quando a tabela existe."""
    return ("objeto_3d",) if tabela_pronta() else ()


def objeto_do_brinquedo(brinquedo, so_ativo=True):
    """O objeto 3D já trazido com o brinquedo (prefetch), ou None.

    Nunca consulta o banco: sem o `prefetch_do_objeto()` (ou sem a tabela),
    é None -- e a tela segue sem o 3D, em vez de cair.
    """
    if not type(brinquedo).objeto_3d.is_cached(brinquedo):
        return None
    objeto = getattr(brinquedo, "objeto_3d", None)
    if objeto is None or (so_ativo and not (objeto.ativo and objeto.url)):
        return None
    return objeto


def armazenamento():
    """Onde o .glb enviado fica: o Cloudinary em produção, o disco no resto.

    O .glb não é imagem: no Cloudinary ele vai como arquivo "raw" (o
    armazenamento das fotos recusaria). Fora da produção (o computador, os
    testes), vale o armazenamento padrão do projeto.
    """
    padrao = settings.STORAGES.get("default", {}).get("BACKEND", "")
    if "cloudinary" in padrao.lower():
        from cloudinary_storage.storage import RawMediaCloudinaryStorage

        return RawMediaCloudinaryStorage()
    return default_storage


def ler_json_do_glb(arquivo):
    """O JSON de dentro do .glb (o primeiro bloco do arquivo), ou ValidationError."""
    arquivo.seek(0)
    cabecalho = arquivo.read(20)
    arquivo.seek(0)
    if len(cabecalho) < 20:
        raise ValidationError("O arquivo é pequeno demais para ser um .glb.")
    magica, versao, _total, tamanho_json, tipo = struct.unpack("<4sIIII", cabecalho)
    if magica != b"glTF" or versao != 2 or tipo != 0x4E4F534A:  # "JSON"
        raise ValidationError("O arquivo não é um .glb (glTF 2.0 binário).")
    arquivo.seek(20)
    bloco = arquivo.read(tamanho_json)
    arquivo.seek(0)
    try:
        return json.loads(bloco.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValidationError("O .glb está corrompido (o JSON de dentro não abre).") from exc


def cores_do_glb(dados):
    """As cores (variações de material) gravadas no .glb, na ordem do arquivo."""
    variantes = (dados.get("extensions") or {}).get("KHR_materials_variants") or {}
    return [
        (v.get("name") or f"Cor {i + 1}").strip()[:60]
        for i, v in enumerate(variantes.get("variants") or [])
    ]


#: O maior valor de cada tipo inteiro do glTF (para as posições "normalizadas"
#: da compressão KHR_mesh_quantization).
_MAXIMO_DO_TIPO = {5120: 127, 5121: 255, 5122: 32767, 5123: 65535}


def _matriz_do_no(no):
    """A matriz 4x4 (por colunas, como no glTF) do nó: a dele ou a de T·R·E."""
    if "matrix" in no:
        return [float(v) for v in no["matrix"]]
    tx, ty, tz = no.get("translation") or (0, 0, 0)
    x, y, z, w = no.get("rotation") or (0, 0, 0, 1)
    ex, ey, ez = no.get("scale") or (1, 1, 1)
    return [
        (1 - 2 * (y * y + z * z)) * ex, 2 * (x * y + z * w) * ex, 2 * (x * z - y * w) * ex, 0,
        2 * (x * y - z * w) * ey, (1 - 2 * (x * x + z * z)) * ey, 2 * (y * z + x * w) * ey, 0,
        2 * (x * z + y * w) * ez, 2 * (y * z - x * w) * ez, (1 - 2 * (x * x + y * y)) * ez, 0,
        tx, ty, tz, 1,
    ]


def _multiplicar(a, b):
    return [sum(a[k * 4 + r] * b[c * 4 + k] for k in range(4)) for c in range(4) for r in range(4)]


def medidas_do_glb(dados):
    """[altura, largura, profundidade] do objeto, em metros (o glTF é em metros).

    Sai das caixas que o próprio arquivo grava para as posições de cada
    malha (`min`/`max`, obrigatórias no glTF), levadas pela posição, giro
    e escala de cada nó até a cena. Sem malha medível: [].
    """
    try:
        cenas = dados.get("scenes") or []
        cena = cenas[dados.get("scene", 0)] if cenas else None
        nos = dados.get("nodes") or []
        malhas = dados.get("meshes") or []
        acessores = dados.get("accessors") or []
        baixo = [float("inf")] * 3
        alto = [float("-inf")] * 3

        def andar(indice, pai, profundidade=0):
            if profundidade > 64:  # arquivo com laço: para
                return
            no = nos[indice]
            matriz = _multiplicar(pai, _matriz_do_no(no))
            if "mesh" in no:
                for primitiva in malhas[no["mesh"]].get("primitives") or []:
                    posicao = (primitiva.get("attributes") or {}).get("POSITION")
                    if posicao is None:
                        continue
                    acessor = acessores[posicao]
                    menor, maior = acessor.get("min"), acessor.get("max")
                    if not menor or not maior or len(menor) < 3 or len(maior) < 3:
                        continue
                    if acessor.get("normalized") and acessor.get("componentType") in _MAXIMO_DO_TIPO:
                        teto = _MAXIMO_DO_TIPO[acessor["componentType"]]
                        menor = [max(v / teto, -1.0) for v in menor]
                        maior = [max(v / teto, -1.0) for v in maior]
                    for x in (menor[0], maior[0]):
                        for y in (menor[1], maior[1]):
                            for z in (menor[2], maior[2]):
                                ponto = (
                                    matriz[0] * x + matriz[4] * y + matriz[8] * z + matriz[12],
                                    matriz[1] * x + matriz[5] * y + matriz[9] * z + matriz[13],
                                    matriz[2] * x + matriz[6] * y + matriz[10] * z + matriz[14],
                                )
                                for eixo in range(3):
                                    baixo[eixo] = min(baixo[eixo], ponto[eixo])
                                    alto[eixo] = max(alto[eixo], ponto[eixo])
            for filho in no.get("children") or []:
                andar(filho, matriz, profundidade + 1)

        identidade = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        raizes = (cena or {}).get("nodes") if cena else range(len(nos))
        for raiz in raizes or []:
            andar(raiz, identidade)
    except (IndexError, KeyError, TypeError, ValueError):
        return []
    if baixo[0] == float("inf"):
        return []
    # no glTF, y é a altura e z, a profundidade (a frente olha para +z)
    return [round(alto[1] - baixo[1], 2), round(alto[0] - baixo[0], 2), round(alto[2] - baixo[2], 2)]


def ler_glb(arquivo):
    """O que o .glb traz: as cores e as medidas (ValidationError se não for um .glb)."""
    dados = ler_json_do_glb(arquivo)
    return {"cores": cores_do_glb(dados), "medidas": medidas_do_glb(dados)}


def ler_glb_do_site(caminho):
    """As cores e as medidas de um .glb que vem com o site (static/...)."""
    from django.contrib.staticfiles import finders

    achado = finders.find(caminho)
    if not achado:
        return {"cores": [], "medidas": []}
    with open(achado, "rb") as arquivo:
        try:
            return ler_glb(arquivo)
        except ValidationError:
            return {"cores": [], "medidas": []}


def validar_glb(arquivo):
    """Confere o .glb enviado; devolve as cores e as medidas dele."""
    if arquivo.size > TAMANHO_MAXIMO:
        raise ValidationError(f"Use um .glb de até {TAMANHO_MAXIMO // (1024 * 1024)} MB.")
    if not arquivo.name.lower().endswith(".glb"):
        raise ValidationError("O objeto 3D precisa ser um arquivo .glb.")
    return ler_glb(arquivo)
