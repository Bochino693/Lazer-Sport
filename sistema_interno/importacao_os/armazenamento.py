"""Onde mora o documento original de uma O.S.: o cofre das notas e do RH.

Ficha de O.S., laudo e pedido de serviço trazem nome, telefone, CPF e
endereço do cliente: dado pessoal. Nada disso pode ter endereço público.
O armazenamento é o de `rh/armazenamento.py`, reaproveitado como a nota
fiscal já faz (`notas_entrada/armazenamento.py`) -- o nosso banco em produção
(linha privada, seção 130), pasta local fora do MEDIA no resto --, numa pasta
própria:

  * banco: o nome começa com "banco/os/" (o antigo, do Cloudinary, só com "os/";
    os do RH com "rh/", as notas com "notas/");
  * local: `<projeto>/privado/os/`, ou OS_DOCUMENTOS_PRIVADOS_DIR (a pasta
    `privado/` está no .gitignore).

`url()` levanta erro: o arquivo só sai pela view `documento_ordem_servico`,
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

EXTENSOES = (".docx", ".pdf", ".txt")


def pasta_dos_documentos() -> Path:
    configurada = getattr(settings, "OS_DOCUMENTOS_PRIVADOS_DIR", "")
    if configurada:
        return Path(configurada)
    return Path(settings.BASE_DIR) / "privado" / "os"


def caminho_do_documento(instancia, nome_arquivo):
    """Nome aleatório: nem o cliente nem o número da O.S. no caminho."""
    extensao = ""
    if "." in (nome_arquivo or ""):
        extensao = "." + nome_arquivo.rsplit(".", 1)[-1].lower()
    if extensao not in EXTENSOES:
        extensao = ".bin"
    aleatorio = uuid.uuid4().hex
    return f"os/{aleatorio[:2]}/{aleatorio}{extensao}"


class _LocalDosDocumentos(FileSystemStorage):
    def __init__(self):
        super().__init__(location=str(pasta_dos_documentos()), base_url=None)

    def url(self, name):
        raise ArquivoSemEnderecoPublico("Documento de O.S. não tem endereço: abra pela tela da O.S.")


@deconstructible(path="sistema_interno.importacao_os.armazenamento.ArmazenamentoDosDocumentosOS")
class ArmazenamentoDosDocumentosOS(ArmazenamentoPrivado):
    def _local(self):
        return _LocalDosDocumentos()

    def url(self, name):
        raise ArquivoSemEnderecoPublico("Documento de O.S. não tem endereço: abra pela tela da O.S.")


armazenamento_dos_documentos = ArmazenamentoDosDocumentosOS()
