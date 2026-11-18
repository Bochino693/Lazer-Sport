"""Onde moram os documentos dos colaboradores -- e por que NUNCA há URL.

O que se guarda aqui é dado pessoal sensível (LGPD): RG, CPF, carteira de
trabalho, comprovante de residência, exame admissional. Nenhum desses
arquivos pode ter endereço público, nem "secreto": um link que vaza num
print, num histórico de navegador ou num encaminhamento de WhatsApp é um
documento vazado.

POR ISSO `url()` LEVANTA ERRO, nos dois armazenamentos. Quem quer ver um
documento passa pela view `rh_documento_arquivo`, que confere a permissão,
lê o arquivo do lado do servidor, entrega com `Cache-Control: no-store` e
grava na trilha de auditoria quem abriu, quando e de onde.

COMO O PROJETO GUARDA O QUE É PRIVADO HOJE. A assinatura do termo de compra
(`DocumentoAssinatura.assinatura_png`) fica dentro do banco, como bytes,
servida só por view. Para um traço de 40 KB é o ideal; para documentos de
até 10 MB por colaborador, o banco do Supabase encheria rápido. Então:

  * PRODUÇÃO (Render): Cloudinary com `type="authenticated"` e
    `resource_type="raw"`. O arquivo não tem endereço de entrega público:
    só se baixa com uma URL ASSINADA pela API (api_key + api_secret), que o
    servidor gera na hora, usa uma vez para ler e descarta -- ela nunca
    chega ao navegador. "raw" porque é documento, não imagem: nada de
    transformação, miniatura ou derivado público.
  * DESENVOLVIMENTO E TESTES: pasta local FORA do MEDIA_ROOT (que é servido
    em /media/ no DEBUG). Padrão `<projeto>/privado/rh/`, ou o que estiver em
    `RH_ARQUIVOS_PRIVADOS_DIR`. A pasta `privado/` está no .gitignore.

Quem decide é `RH_ARMAZENAMENTO` ("cloudinary" ou "local"); sem ela, é
Cloudinary em produção e local no resto. A escolha é feita a cada operação
(e não ao importar o modelo), para os testes poderem trocar a pasta.
"""

from __future__ import annotations

import io
import logging
import time
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, Storage
from django.utils.deconstruct import deconstructible

log = logging.getLogger(__name__)

#: Quanto tempo a URL assinada do Cloudinary vale. Ela é usada na mesma
#: requisição, do servidor para o Cloudinary: um minuto é folga.
VALIDADE_DO_LINK_INTERNO = 60

#: Prazo para o Cloudinary entregar o arquivo ao servidor.
PRAZO_DE_LEITURA = 25


class ArquivoSemEnderecoPublico(Exception):
    """Documento de colaborador não tem URL: sirva pela view."""


def modo() -> str:
    escolhido = str(getattr(settings, "RH_ARMAZENAMENTO", "") or "").strip().lower()
    if escolhido in ("cloudinary", "local"):
        return escolhido
    ambiente = str(getattr(settings, "ENVIRONMENT", "") or "").lower()
    return "cloudinary" if ambiente == "production" else "local"


def pasta_privada() -> Path:
    configurada = getattr(settings, "RH_ARQUIVOS_PRIVADOS_DIR", "")
    if configurada:
        return Path(configurada)
    return Path(settings.BASE_DIR) / "privado" / "rh"


class _LocalPrivado(FileSystemStorage):
    """O FileSystemStorage, mas sem endereço e com a pasta lida na hora."""

    def __init__(self):
        super().__init__(location=str(pasta_privada()), base_url=None)

    def url(self, name):
        raise ArquivoSemEnderecoPublico(
            "Documento de colaborador não tem endereço: abra pela ficha."
        )


class _CloudinaryPrivado(Storage):
    """Cloudinary com entrega autenticada: guardar, ler pelo servidor e apagar."""

    OPCOES = {"resource_type": "raw", "type": "authenticated"}

    def _save(self, name, content):
        import cloudinary.uploader

        if hasattr(content, "seek"):
            content.seek(0)
        dados = content.read()
        cloudinary.uploader.upload(
            io.BytesIO(dados),
            public_id=name,
            overwrite=False,
            unique_filename=False,
            use_filename=False,
            invalidate=True,
            **self.OPCOES,
        )
        return name

    def _open(self, name, mode="rb"):
        import cloudinary.utils
        import requests

        link = cloudinary.utils.private_download_url(
            name, "", expires_at=int(time.time()) + VALIDADE_DO_LINK_INTERNO,
            **self.OPCOES,
        )
        resposta = requests.get(link, timeout=PRAZO_DE_LEITURA)
        if resposta.status_code != 200:
            raise FileNotFoundError(
                f"O armazenamento privado não entregou o documento (HTTP {resposta.status_code})."
            )
        return ContentFile(resposta.content, name=name)

    def delete(self, name):
        import cloudinary.uploader

        if not name:
            return
        try:
            cloudinary.uploader.destroy(name, invalidate=True, **self.OPCOES)
        except Exception:  # noqa: BLE001 -- apagar é melhor esforço; o log conta
            log.exception("Não foi possível apagar o documento privado %s", name)

    def exists(self, name):
        # Os nomes são aleatórios (uuid4): perguntar à API em todo envio
        # custaria uma viagem para uma colisão que não acontece.
        return False

    def size(self, name):
        raise NotImplementedError("O tamanho fica gravado no próprio documento.")

    def url(self, name):
        raise ArquivoSemEnderecoPublico(
            "Documento de colaborador não tem endereço: abra pela ficha."
        )


@deconstructible(path="rh.armazenamento.ArmazenamentoPrivado")
class ArmazenamentoPrivado(Storage):
    """O armazenamento dos documentos: escolhe Cloudinary ou pasta local."""

    def _real(self) -> Storage:
        return _CloudinaryPrivado() if modo() == "cloudinary" else _LocalPrivado()

    def _save(self, name, content):
        return self._real()._save(name, content)

    def _open(self, name, mode="rb"):
        return self._real()._open(name, mode)

    def get_available_name(self, name, max_length=None):
        return self._real().get_available_name(name, max_length=max_length)

    def delete(self, name):
        return self._real().delete(name)

    def exists(self, name):
        return self._real().exists(name)

    def size(self, name):
        return self._real().size(name)

    def url(self, name):
        raise ArquivoSemEnderecoPublico(
            "Documento de colaborador não tem endereço: abra pela ficha."
        )

    def path(self, name):
        real = self._real()
        if isinstance(real, FileSystemStorage):
            return real.path(name)
        raise NotImplementedError("No Cloudinary o documento não tem caminho local.")


armazenamento_privado = ArmazenamentoPrivado()
