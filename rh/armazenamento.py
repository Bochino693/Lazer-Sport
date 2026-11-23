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

  * PRODUÇÃO (Render): NO NOSSO BANCO (LEIA-ME-V10, seção 130), numa
    linha de `core.ArquivoNoBanco` com `publico=False` -- a rota pública
    /midia/banco/ não a entrega nunca. Antes era o Cloudinary autenticado; em
    23/11/2026 a conta foi desativada e TODO envio do RH voltava 500 ("não
    consigo gerar o ponto para os funcionários"). O banco já é o ponto único
    de verdade: guardar o documento nele não cria um ponto de falha novo.
    O nome novo começa com "banco/" (ex.: banco/rh/ab/ab12....pdf).
  * O DOCUMENTO ANTIGO (o nome sem "banco/"): em produção continua sendo
    lido do Cloudinary autenticado -- `type="authenticated"`,
    `resource_type="raw"`, só por URL ASSINADA que o servidor gera, usa uma
    vez e descarta (nunca chega ao navegador). O espelho
    (core/espelho_midia.py) o copia para o banco assim que a conta voltar.
  * DESENVOLVIMENTO E TESTES: pasta local FORA do MEDIA_ROOT (que é servido
    em /media/ no DEBUG). Padrão `<projeto>/privado/rh/`, ou o que estiver em
    `RH_ARQUIVOS_PRIVADOS_DIR`. A pasta `privado/` está no .gitignore.

Quem decide é `RH_ARMAZENAMENTO` ("banco", "cloudinary" ou "local"); sem ela,
é o banco em produção e a pasta local no resto. A escolha é feita a cada
operação (e não ao importar o modelo), para os testes poderem trocar. A
LEITURA vai pelo nome: "banco/..." é do banco; o resto é do legado
(Cloudinary em produção, a pasta local no computador).
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


def _em_producao() -> bool:
    return str(getattr(settings, "ENVIRONMENT", "") or "").lower() == "production"


def modo() -> str:
    """Onde o documento NOVO vai: "banco", "cloudinary" ou "local"."""
    escolhido = str(getattr(settings, "RH_ARMAZENAMENTO", "") or "").strip().lower()
    if escolhido in ("banco", "cloudinary", "local"):
        return escolhido
    return "banco" if _em_producao() else "local"


def legado_e_cloudinary() -> bool:
    """O nome antigo (sem "banco/") mora no Cloudinary? Em produção, sim (salvo o modo "local")."""
    escolhido = modo()
    if escolhido == "cloudinary":
        return True
    return escolhido == "banco" and _em_producao()


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
        if resposta.status_code in (401, 403) or "disabled" in (resposta.headers.get("x-cld-error") or "").lower():
            from core.arquivos_no_banco import CloudinaryForaDoAr

            raise CloudinaryForaDoAr(
                f"O Cloudinary recusou o documento (HTTP {resposta.status_code}): a conta está fora do ar."
            )
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


class _BancoPrivado(Storage):
    """O documento no nosso banco, como linha PRIVADA (`publico=False`): sem endereço."""

    def get_available_name(self, name, max_length=None):
        from core.arquivos_no_banco import PREFIXO

        # os nomes já são aleatórios (uuid4): conferir se existe custaria uma
        # ida ao banco por uma colisão que não acontece
        name = str(name).lstrip("/")
        nome = name if name.startswith(PREFIXO) else PREFIXO + name
        if max_length and len(nome) > max_length:
            nome = nome[:max_length]
        return nome

    def _save(self, name, content):
        from django.db import DatabaseError

        from core.arquivos_no_banco import ArmazenamentoIndisponivel, guardar, tipo_do_conteudo

        try:
            if hasattr(content, "seek"):
                content.seek(0)
            dados = content.read()
        except Exception as erro:  # noqa: BLE001
            raise ArmazenamentoIndisponivel("O arquivo enviado não pôde ser lido. Envie de novo.") from erro
        try:
            guardar(name, dados, publico=False, tipo=tipo_do_conteudo(dados, name))
        except DatabaseError as erro:  # IntegrityError incluso: o nome sorteado repetido
            log.exception("Documento privado: o banco não guardou %s", name)
            raise ArmazenamentoIndisponivel() from erro
        return name

    def _open(self, name, mode="rb"):
        from core.arquivos_no_banco import ler

        linha = ler(name)
        if linha is None:
            raise FileNotFoundError("O documento não está no banco.")
        return ContentFile(linha[0], name=name)

    def delete(self, name):
        from core.arquivos_no_banco import apagar

        if name:
            apagar(name)

    def exists(self, name):
        from core.models import ArquivoNoBanco

        return ArquivoNoBanco.objects.filter(nome=name).exists()

    def size(self, name):
        from core.models import ArquivoNoBanco

        tamanho = ArquivoNoBanco.objects.filter(nome=name).values_list("tamanho", flat=True).first()
        if tamanho is None:
            raise FileNotFoundError(name)
        return tamanho

    def url(self, name):
        raise ArquivoSemEnderecoPublico(
            "Documento de colaborador não tem endereço: abra pela ficha."
        )


@deconstructible(path="rh.armazenamento.ArmazenamentoPrivado")
class ArmazenamentoPrivado(Storage):
    """O armazenamento dos documentos: o banco (produção), o Cloudinary antigo ou a pasta local.

    O que é NOVO vai para onde `modo()` manda. O que se LÊ vai pelo nome:
    "banco/..." é do banco; o resto, do legado (`_legado`). As subclasses
    (O.S., notas) só trocam a pasta local (`_local`).
    """

    #: o espelho (core/espelho_midia.py) copia para o banco os nomes antigos
    guarda_publico = False

    @property
    def espelha_no_banco(self):
        return modo() == "banco"

    def _local(self) -> Storage:
        return _LocalPrivado()

    def _banco(self) -> Storage:
        return _BancoPrivado()

    def _legado(self) -> Storage:
        return _CloudinaryPrivado() if legado_e_cloudinary() else self._local()

    def _real(self) -> Storage:
        """Onde o documento novo vai."""
        escolhido = modo()
        if escolhido == "banco":
            return self._banco()
        if escolhido == "cloudinary":
            return _CloudinaryPrivado()
        return self._local()

    def _para(self, name) -> Storage:
        """Onde o documento `name` mora."""
        from core.arquivos_no_banco import e_do_banco

        return self._banco() if e_do_banco(name) else self._legado()

    def baixar_legado(self, name) -> bytes:
        with self._legado()._open(name, "rb") as arquivo:
            return arquivo.read()

    def _save(self, name, content):
        from core.arquivos_no_banco import ArmazenamentoIndisponivel

        try:
            return self._real()._save(name, content)
        except ArmazenamentoIndisponivel:
            raise
        except Exception as erro:  # noqa: BLE001 -- o Cloudinary (forçado) ou o disco: janela, nunca 500
            log.exception("Documento privado: o armazenamento (%s) recusou %s", modo(), name)
            raise ArmazenamentoIndisponivel() from erro

    def _open(self, name, mode="rb"):
        return self._para(name)._open(name, mode)

    def get_available_name(self, name, max_length=None):
        return self._real().get_available_name(name, max_length=max_length)

    def delete(self, name):
        return self._para(name).delete(name)

    def exists(self, name):
        return self._para(name).exists(name)

    def size(self, name):
        return self._para(name).size(name)

    def url(self, name):
        raise ArquivoSemEnderecoPublico(
            "Documento de colaborador não tem endereço: abra pela ficha."
        )

    def path(self, name):
        real = self._para(name)
        if isinstance(real, FileSystemStorage):
            return real.path(name)
        raise NotImplementedError("No banco (ou no Cloudinary) o documento não tem caminho local.")


armazenamento_privado = ArmazenamentoPrivado()
