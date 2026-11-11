"""Importar orçamento do Word: subir o .docx, conferir, criar o rascunho.

DUAS TELAS, NESTA ORDEM, E NENHUM ATALHO ENTRE ELAS.

  1. `ImportarOrcamentoWordView` recebe o .docx, lê (regras e, com a chave
     configurada, IA), guarda a leitura na sessão e manda para a
     conferência. O arquivo é lido da memória e descartado aqui mesmo.
  2. `ConferirImportacaoView` mostra o orçamento como vai ficar, com a
     fonte e a confiança de cada campo, o que falta preencher e os
     alertas -- e só cria quando está tudo completo e todo alerta
     vermelho foi resolvido ou aceito com justificativa. Cria RASCUNHO e
     abre na tela normal de edição; nunca envia nada ao cliente.

QUEM ENTRA. As mesmas portas do orçamento (`OrcamentoInternoRequiredMixin`)
e, dentro delas, só quem pode CRIAR proposta (`orcamentos_criar`): o
Financeiro participa das propostas existentes, mas a criação é do
Comercial -- a mesma regra de `OrcamentosInnerView.acao_save`.
"""

from __future__ import annotations

import logging

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import View

from .context_processors import invalidar_avisos
from .importacao_word import conferencia, formulario, ia, leitor, sessao
from .permissoes import capacidades
from .utils import ErroDeFormulario
from .views import OrcamentoInternoRequiredMixin

logger = logging.getLogger(__name__)


class _SoQuemCriaProposta(OrcamentoInternoRequiredMixin):
    """Financeiro vê orçamento; criar proposta é do Comercial."""

    def negar(self, request):
        return render(request, "importar_orcamento_inner.html", {"negado": True}, status=403)

    def pode_criar(self, request):
        return capacidades(request.user)["orcamentos_criar"]


class ImportarOrcamentoWordView(_SoQuemCriaProposta, View):
    template_name = "importar_orcamento_inner.html"

    def contexto(self, **extras):
        contexto = {
            "ia_ligada": ia.chave_configurada(),
            "modelo_ia": ia.modelo_configurado(),
            "tamanho_maximo_mb": leitor.TAMANHO_MAXIMO // (1024 * 1024),
        }
        contexto.update(extras)
        return contexto

    def get(self, request):
        if not self.pode_criar(request):
            return self.negar(request)
        return render(request, self.template_name, self.contexto())

    def post(self, request):
        if not self.pode_criar(request):
            return self.negar(request)
        arquivo = request.FILES.get("arquivo")
        if arquivo is None:
            return render(request, self.template_name, self.contexto(
                erro="Escolha o arquivo do orçamento: Word (.docx) ou PDF.",
            ), status=400)
        nome = (arquivo.name or "documento.docx")[:120]
        # O tamanho é conferido ANTES de ler: o arquivo de 200 MB não chega
        # a ocupar a memória do servidor só para ser recusado depois.
        if arquivo.size > leitor.TAMANHO_MAXIMO:
            return self.recusar(
                request,
                f"O arquivo passa de {leitor.TAMANHO_MAXIMO // (1024 * 1024)} MB. Salve uma "
                "cópia sem as fotos (ou com as fotos compactadas) e importe de novo.",
            )
        try:
            conteudo = arquivo.read()
        finally:
            arquivo.close()
        try:
            formato = leitor.conferir_arquivo(nome, conteudo)
            if formato == "pdf":
                leitura = self.ler_pdf(nome, conteudo)
            else:
                leitura = self.ler_docx(nome, conteudo)
        except leitor.ArquivoRecusado as exc:
            return self.recusar(request, str(exc))
        finally:
            # O conteúdo do arquivo não passa deste ponto: dali em diante só
            # existem as linhas de texto e a leitura.
            del conteudo

        if leitura["ia"]["usada"]:
            # A IA escolhe entre os candidatos só dos itens que ficaram em
            # dúvida, e só pode responder um id da lista ou "nenhum".
            proposta = conferencia.montar_proposta(leitura)
            perguntas = [
                {
                    "item": item["posicao"],
                    "descricao": item["original"],
                    "candidatos": [
                        {"id": c["id"], "nome": c["nome"], "grupo": c["grupo"],
                         "preco": f"R$ {c['preco']}" if c["preco"] else ""}
                        for c in item["produto"]["candidatos"]
                    ],
                }
                for item in proposta["itens"]
                if item["produto"]["confianca"] != "alta" and item["produto"]["candidatos"]
            ]
            if perguntas:
                leitura["escolhas"] = {str(k): v for k, v in ia.escolher_produtos(perguntas).items()}

        token = sessao.guardar(request, leitura)
        return redirect("conferir_importacao_word", token=token)


    def recusar(self, request, mensagem):
        return render(request, self.template_name, self.contexto(erro=mensagem), status=400)

    def ler_docx(self, nome, conteudo):
        linhas = leitor.ler_docx(conteudo, nome)
        leitura = {"arquivo": nome, "formato": "docx", "linhas": linhas, "ia": {"usada": False}, "escolhas": {}}
        if ia.chave_configurada():
            try:
                dados, modelo = ia.ler_orcamento(leitor.texto_numerado(linhas))
                leitura["ia"] = {"usada": True, "modelo": modelo, "dados": dados}
            except ia.IAIndisponivel as exc:
                leitura["ia"] = {"usada": False, "motivo": str(exc)}
        else:
            leitura["ia"] = {"usada": False, "motivo": "a chave da IA (ANTHROPIC_API_KEY) não está configurada"}
        return leitura

    def ler_pdf(self, nome, conteudo):
        """O PDF só é lido pela IA; sem ela, a pessoa é PERGUNTADA, não adivinhada.

        Não há leitor de PDF no servidor (e o PDF digitalizado nem texto
        tem). Sem a chave, ou quando a leitura volta vazia, a tela diz o
        que fazer -- importar o .docx, ou um PDF com texto nítido -- em vez
        de montar um orçamento a partir de nada.
        """
        leitor.conferir_pdf(nome, conteudo)
        if not ia.chave_configurada():
            raise leitor.ArquivoRecusado(
                "PDF é lido pela IA, e a chave dela (ANTHROPIC_API_KEY) não está configurada "
                "neste servidor. Abra o orçamento no Word e importe o .docx -- a leitura pelas "
                "tabelas do Word funciona sem a IA."
            )
        try:
            transcricao, dados, modelo = ia.ler_pdf(conteudo)
        except ia.IAIndisponivel as exc:
            raise leitor.ArquivoRecusado(
                f"Não consegui ler o PDF: {exc}. Tente de novo em instantes ou importe o .docx original."
            ) from exc
        linhas = leitor.linhas_transcritas(transcricao)
        if not any(l["parte"] in ("corpo", "caixa") for l in linhas):
            raise leitor.ArquivoRecusado(
                "O PDF voltou sem texto legível (digitalização apagada, foto torta ou arquivo "
                "protegido). Envie o .docx original ou um PDF com o texto nítido."
            )
        if not _tem_orcamento(dados):
            raise leitor.ArquivoRecusado(
                "Li o PDF, mas não encontrei nele um orçamento: nem cliente, nem itens, nem "
                "valores. Confira se é o arquivo certo -- ou importe o .docx original."
            )
        return {
            "arquivo": nome, "formato": "pdf", "linhas": linhas, "escolhas": {},
            "ia": {"usada": True, "modelo": modelo, "dados": dados},
        }


def _tem_orcamento(dados: dict) -> bool:
    """Algo que se possa conferir: um item, um valor, ou o cliente."""
    if any((item.get("descricao") or {}).get("texto") for item in dados.get("itens") or []):
        return True
    for nome in ("total_geral", "subtotal"):
        if (dados.get(nome) or {}).get("texto"):
            return True
    return bool(((dados.get("cliente") or {}).get("nome") or {}).get("texto"))


class ConferirImportacaoView(_SoQuemCriaProposta, View):
    template_name = "conferir_importacao_inner.html"

    def _abrir(self, request, token):
        leitura = sessao.abrir(request, token)
        if leitura is None:
            messages.info(
                request,
                "Esta importação não está mais aberta (ela vale 12 horas e some quando o "
                "orçamento é criado). Importe o documento de novo.",
            )
        return leitura

    def get(self, request, token):
        if not self.pode_criar(request):
            return self.negar(request)
        leitura = self._abrir(request, token)
        if leitura is None:
            return redirect("importar_orcamento_word")
        proposta = conferencia.montar_proposta(leitura)
        envio = formulario.envio_inicial(proposta)
        return self.desenhar(request, token, leitura, proposta, envio)

    def post(self, request, token):
        if not self.pode_criar(request):
            return self.negar(request)
        leitura = self._abrir(request, token)
        if leitura is None:
            return redirect("importar_orcamento_word")

        if request.POST.get("action") == "descartar":
            sessao.descartar(request, token)
            messages.info(request, f"A importação de “{leitura['arquivo']}” foi descartada.")
            return redirect("orcamentos_inner")

        proposta = conferencia.montar_proposta(leitura)
        envio = formulario.ler_envio(request.POST)
        validado = formulario.validar(proposta, envio)
        if not validado["pronto"]:
            return self.desenhar(
                request, token, leitura, formulario.aplicar_envio(proposta, envio), envio,
                validado=validado, status=400,
                erro="O orçamento ainda não pode ser criado: veja o que falta preencher.",
            )
        try:
            orcamento = formulario.criar_rascunho(request, proposta, validado, arquivo=leitura["arquivo"])
        except ErroDeFormulario as exc:
            # O cadastro de clientes tem a última palavra (nome repetido,
            # CPF de outro cliente): a tela volta com o motivo dele.
            return self.desenhar(
                request, token, leitura, formulario.aplicar_envio(proposta, envio), envio,
                validado=validado, status=400, erro=str(exc),
            )
        sessao.descartar(request, token)
        invalidar_avisos(request.user)
        messages.success(
            request,
            f"Orçamento #{orcamento.pk} criado como rascunho a partir de “{leitura['arquivo']}”. "
            "Confira e salve para seguir com o envio.",
        )
        return redirect(f"{reverse('orcamentos_inner')}?editar={orcamento.pk}")

    def desenhar(self, request, token, leitura, proposta, envio, *, validado=None, status=200, erro=""):
        validado = validado or formulario.validar(proposta, envio)
        alertas = validado["alertas"]
        for alerta in alertas:
            if alerta["id"] in envio["justificativas"]:
                alerta["aceito"] = True
                alerta["justificativa"] = envio["justificativas"][alerta["id"]]
        vermelhos = [a for a in alertas if a["nivel"] == conferencia.NIVEL_VERMELHO]

        # O motivo de cada pendência vai para junto do campo, além da
        # lista do topo: quem rola até o frete vê ali mesmo o que falta.
        # Chaves com "_" no lugar do ponto, para o template alcançar.
        faltas = {}
        faltas_item: dict[str, dict] = {}
        for pendencia in validado["pendencias"]:
            partes = pendencia["campo"].split(".")
            if partes[0] == "itens" and len(partes) == 3:
                nome = "produto" if partes[2] == "conferido" else partes[2]
                faltas_item.setdefault(partes[1], {}).setdefault(nome, pendencia["motivo"])
            else:
                faltas.setdefault("_".join(partes), pendencia["motivo"])
        itens_tela = []
        for item, env in zip(proposta["itens"], envio["itens"]):
            item["faltas"] = faltas_item.get(item["uid"], {})
            itens_tela.append({"item": item, "env": env})

        contexto = {
            "token": token,
            "proposta": proposta,
            "envio": envio,
            "validado": validado,
            "faltas": faltas,
            "itens_tela": itens_tela,
            "item_modelo": formulario.item_em_branco("__uid__", "__posicao__"),
            "env_modelo": {"uid": "__uid__", "descricao": "", "produto": "", "avulsa": False,
                           "conferido": False, "quantidade": "", "valor_unitario": ""},
            "alertas_vermelhos": vermelhos,
            "alertas_amarelos": [a for a in alertas if a["nivel"] != conferencia.NIVEL_VERMELHO],
            "erro": erro,
            "linhas": leitura["linhas"],
            "hoje": timezone.localdate(),
            "tipos_cliente": formulario.Cliente.Tipo.choices,
            "dados_tela": {
                "itens": {
                    item["uid"]: {
                        "totalWord": item["total_linha"]["valor"],
                        "totalWordFonte": (item["total_linha"]["fonte"] or {}).get("id", ""),
                        "sugerido": item["produto"]["escolhido"] or "",
                        "confianca": item["produto"]["confianca"],
                        "opcao": item["produto"]["opcao"],
                        "posicao": item["posicao"],
                    }
                    for item in proposta["itens"]
                },
                "subtotalWord": proposta["valores"]["subtotal"]["valor"],
                "totalWord": proposta["valores"]["total"]["valor"],
                "descontoExigido": bool(proposta["valores"]["desconto"].get("exigir")),
                "descontoPercentual": proposta["valores"]["desconto"].get("percentual", ""),
                "cliente": {
                    "modo": proposta["cliente"]["vinculo"]["modo"],
                    "id": str(proposta["cliente"]["vinculo"]["cliente_id"] or ""),
                    "confianca": proposta["cliente"]["vinculo"]["confianca"],
                    "opcao": proposta["cliente"]["vinculo"]["opcao"],
                },
                "hoje": timezone.localdate().isoformat(),
                "justificativaMinima": formulario.JUSTIFICATIVA_MINIMA,
                "buscaItens": reverse("buscar_itens_orcamento"),
                "buscaClientes": reverse("buscar_clientes_orcamento"),
            },
        }
        return render(request, self.template_name, contexto, status=status)
