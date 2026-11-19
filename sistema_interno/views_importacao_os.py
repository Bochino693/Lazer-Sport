"""O automatizador da O.S. (LEIA-ME-V10, seção 122): as rotas da folha.

UM ARQUIVO POR PEDIDO. A folha da tela de Ordens de Serviço manda os
documentos um de cada vez (os-automatizador.js), e cada pedido lê, decide e
responde em poucos segundos -- muito abaixo do limite do gunicorn, mesmo
com o banco longe. Um lote de dez é uma fila de dez pedidos curtos, com o
progresso na tela, e não um pedido de minutos que cai no meio.

  * `ImportarDocumentosOSView` (/ordens-servico/importar/): POST com o
    arquivo -> a O.S. criada, o que falta, o repetido ou a recusa (JSON).
    GET com `?formato=json` -> os documentos que esperam completar; GET
    comum -> a tela de O.S. com a folha aberta.
  * `DocumentoOSView` (/ordens-servico/importar/<id>/): POST "completar"
    com o que faltava, ou "descartar"; GET -> a linha desse documento.
  * `ArquivoDocumentoOSView` (/ordens-servico/documentos/<id>/arquivo/):
    o arquivo original, só por aqui (cofre privado, `no-store`).
  * `DocumentosDaOrdemView` (/ordens-servico/<id>/documentos/): os
    documentos de uma O.S., para a janela da O.S. mostrar o anexo.

QUEM: cria O.S. quem pode criar O.S. à mão -- `capacidades
["ordens_servico_editar"]` (Produção, Gestão e o superusuário). O
Financeiro vê a O.S. e o documento anexado, mas não importa; pela URL
direta, a resposta é 403.
"""

from __future__ import annotations

import logging

from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import View

from core.ls_aviso import avisar

from .context_processors import invalidar_avisos
from .importacao_os import arquivo as arq
from .importacao_os import gravar
from .models import DocumentoOrdemServico, OrdemServico
from .permissoes import capacidades
from .views import OrdemServicoInternoRequiredMixin

logger = logging.getLogger(__name__)

#: O mesmo cabeçalho de segurança do arquivo da nota fiscal: nada roda, nada
#: fica em cache, nada vaza pelo Referer.
CABECALHOS_DO_ARQUIVO = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; sandbox",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store, private",
}
TIPOS_DO_ARQUIVO = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain; charset=utf-8",
}


class _Base(OrdemServicoInternoRequiredMixin, View):
    """Produção, Financeiro e Gestão passam da porta; importar é de quem cria O.S."""

    def dispatch(self, request, *args, **kwargs):
        if getattr(request, "is_interno", False) and request.user.is_authenticated:
            self.acesso = capacidades(request.user)
        else:
            self.acesso = {}
        return super().dispatch(request, *args, **kwargs)

    @property
    def pode_importar(self) -> bool:
        return bool(self.acesso.get("ordens_servico_editar"))

    def negar(self, request):
        return JsonResponse(
            {"estado": "negado", "motivo": "Ler documentos e criar O.S. é da Produção (ou da Gestão)."},
            status=403,
        )

    @staticmethod
    def tela(request, **parametros):
        destino = reverse("ordens_servico_inner")
        if parametros:
            from urllib.parse import urlencode

            destino += "?" + urlencode(parametros)
        return redirect(destino)


class ImportarDocumentosOSView(_Base):
    def get(self, request):
        if not self.pode_importar:
            if request.GET.get("formato") == "json":
                return self.negar(request)
            return self.tela(request)
        if request.GET.get("formato") == "json":
            return JsonResponse({"pendentes": gravar.pendentes()})
        return self.tela(request, importar=1)

    def post(self, request):
        if not self.pode_importar:
            return self.negar(request)
        enviado = request.FILES.get("arquivo")
        if enviado is None:
            return JsonResponse({"estado": "ilegivel", "arquivo": "",
                                 "motivo": "Escolha o documento: Word (.docx), PDF ou .txt."}, status=400)
        nome = (enviado.name or "documento").rsplit("/", 1)[-1].rsplit("\\", 1)[-1][:150]
        # O tamanho antes de ler: o arquivo de 200 MB não chega a ocupar a
        # memória do servidor só para ser recusado.
        if enviado.size > arq.TAMANHO_MAXIMO:
            return JsonResponse({"estado": "ilegivel", "arquivo": nome, "motivo": (
                f"O arquivo passa de {arq.TAMANHO_MAXIMO // (1024 * 1024)} MB. Salve uma cópia sem as fotos "
                "(ou com as fotos compactadas) e envie de novo."
            )})
        try:
            conteudo = enviado.read()
        finally:
            enviado.close()
        try:
            resposta = gravar.importar(request, nome, conteudo)
        except Exception:  # noqa: BLE001 -- um documento estranho não para o lote
            logger.exception("Automatizador da O.S.: o documento %s quebrou a leitura", nome)
            return JsonResponse({"estado": "ilegivel", "arquivo": nome, "motivo": (
                "Não consegui ler este documento agora. Nada foi criado; tente de novo, ou abra no Word, "
                "salve uma cópia e envie a cópia."
            )}, status=500)
        if resposta.get("estado") == "criada":
            invalidar_avisos(request.user)
        return JsonResponse(resposta)


class DocumentoOSView(_Base):
    def _documento(self, pk):
        return DocumentoOrdemServico.objects.select_related("ordem").filter(pk=pk).first()

    def get(self, request, pk):
        documento = self._documento(pk)
        if not self.pode_importar or documento is None:
            return self.tela(request)
        if documento.ordem_id:
            return redirect(gravar.link_da_ordem(documento.ordem))
        return JsonResponse(gravar.resposta_pendente(
            documento, documento.leitura or {}, gravar.pendencias_guardadas(documento.leitura or {}),
        ))

    def post(self, request, pk):
        if not self.pode_importar:
            return self.negar(request)
        documento = self._documento(pk)
        if documento is None:
            return JsonResponse({"estado": "sumiu", "motivo": "Este documento não está mais aqui: alguém "
                                 "já o descartou ou a O.S. foi excluída."}, status=404)
        acao = (request.POST.get("action") or "").strip()
        if acao == "descartar":
            return JsonResponse(gravar.descartar(documento))
        if acao != "completar":
            return JsonResponse({"estado": "erro", "motivo": "Ação inválida."}, status=400)
        resposta = gravar.completar(request, documento, request.POST)
        if resposta.get("estado") == "criada":
            invalidar_avisos(request.user)
        return JsonResponse(resposta)


class ArquivoDocumentoOSView(_Base):
    """O documento original. Quem vê a O.S. vê o anexo; o pendente, só quem importa."""

    def get(self, request, pk):
        documento = DocumentoOrdemServico.objects.filter(pk=pk).first()
        visivel = documento is not None and self.acesso.get("ordens_servico") and (
            documento.ordem_id or self.pode_importar
        )
        if not visivel:
            avisar(request, "Este documento não está disponível.", titulo="Documento da O.S.", icone="arquivo")
            return self.tela(request)
        if not documento.arquivo:
            raise Http404("Documento sem arquivo guardado.")
        try:
            with documento.arquivo.open("rb") as aberto:
                dados = aberto.read()
        except (FileNotFoundError, OSError):
            avisar(request, "O arquivo deste documento não foi encontrado no armazenamento.",
                   titulo="Documento da O.S.", icone="arquivo")
            return self.tela(request)
        tipo = TIPOS_DO_ARQUIVO.get(documento.formato, "application/octet-stream")
        resposta = HttpResponse(dados, content_type=tipo)
        nome = (documento.nome_arquivo or f"documento-os.{documento.formato}").replace('"', "")
        disposicao = "inline" if documento.formato == "pdf" and request.GET.get("baixar") != "1" else "attachment"
        from urllib.parse import quote

        import unicodedata

        simples = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode() or f"documento.{documento.formato}"
        resposta["Content-Disposition"] = f'{disposicao}; filename="{simples}"; filename*=UTF-8\'\'{quote(nome)}'
        for cabecalho, valor in CABECALHOS_DO_ARQUIVO.items():
            resposta[cabecalho] = valor
        return resposta


class DocumentosDaOrdemView(_Base):
    """Os documentos de onde a O.S. foi lida -- a janela da O.S. mostra o anexo."""

    def get(self, request, pk):
        if not self.acesso.get("ordens_servico"):
            return self.tela(request)
        if request.GET.get("formato") != "json":
            ordem = OrdemServico.objects.filter(pk=pk).first()
            return redirect(gravar.link_da_ordem(ordem)) if ordem else self.tela(request)
        documentos = [
            {
                "id": d.pk, "arquivo": d.nome_arquivo, "formato": d.formato,
                "url": reverse("documento_ordem_servico_arquivo", args=[d.pk]),
                "enviado_em": timezone.localtime(d.criacao).strftime("%d/%m/%Y") if d.criacao else "",
                "avisos": (d.leitura or {}).get("avisos", [])[:6],
            }
            for d in DocumentoOrdemServico.objects.filter(ordem_id=pk).order_by("id")[:5]
        ]
        return JsonResponse({"documentos": documentos})
