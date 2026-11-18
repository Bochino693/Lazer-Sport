"""Onde mora o arquivo da nota fiscal: o mesmo cofre dos documentos do RH.

Nota fiscal é documento da empresa (preço pago, fornecedor, CNPJ): não
tem endereço público. O armazenamento é o de `rh/armazenamento.py`,
reaproveitado -- Cloudinary com entrega AUTENTICADA em produção, pasta
local fora do MEDIA no resto --, só que numa pasta própria:

  * Cloudinary: o nome começa com "notas/" (os do RH, com "rh/");
  * local: `<projeto>/privado/notas/`, ou NOTAS_ARQUIVOS_PRIVADOS_DIR
    (a pasta `privado/` está no .gitignore).

`url()` levanta erro: o arquivo só sai pela view `nota_entrada_arquivo`,
que confere a permissão e entrega com no-store.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible

from rh.armazenamento import (
    ArmazenamentoPrivado,
    ArquivoSemEnderecoPublico,
    _CloudinaryPrivado,
    modo,
)

EXTENSOES = (".pdf", ".xml")


def pasta_das_notas() -> Path:
    configurada = getattr(settings, "NOTAS_ARQUIVOS_PRIVADOS_DIR", "")
    if configurada:
        return Path(configurada)
    return Path(settings.BASE_DIR) / "privado" / "notas"


def caminho_da_nota(instancia, nome_arquivo):
    """Nome aleatório: nem fornecedor nem número da nota no caminho."""
    extensao = ""
    if "." in (nome_arquivo or ""):
        extensao = "." + nome_arquivo.rsplit(".", 1)[-1].lower()
    if extensao not in EXTENSOES:
        extensao = ".bin"
    aleatorio = uuid.uuid4().hex
    return f"notas/{aleatorio[:2]}/{aleatorio}{extensao}"


class _LocalDasNotas(FileSystemStorage):
    def __init__(self):
        super().__init__(location=str(pasta_das_notas()), base_url=None)

    def url(self, name):
        raise ArquivoSemEnderecoPublico("Nota fiscal não tem endereço: abra pela tela da nota.")


@deconstructible(path="sistema_interno.notas_entrada.armazenamento.ArmazenamentoDasNotas")
class ArmazenamentoDasNotas(ArmazenamentoPrivado):
    def _real(self):
        return _CloudinaryPrivado() if modo() == "cloudinary" else _LocalDasNotas()

    def url(self, name):
        raise ArquivoSemEnderecoPublico("Nota fiscal não tem endereço: abra pela tela da nota.")


armazenamento_das_notas = ArmazenamentoDasNotas()
