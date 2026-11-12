"""Importar orçamento do Word ou PDF: subir, conferir, criar.

DUAS TELAS, NESTA ORDEM, E NENHUM ATALHO ENTRE ELAS.

  1. `ImportarOrcamentoWordView` recebe o .docx ou o PDF, lê, guarda a
     leitura na sessão e manda para a conferência. O arquivo é lido da
     memória e descartado aqui mesmo.
  2. `ConferirImportacaoView` mostra cliente e orçamento como vão ficar,
     com a fonte e a confiança de cada campo, o que falta e os alertas
     de dinheiro. A pessoa escolhe "Cadastrar cliente e criar orçamento"
     ou "Só cadastrar o cliente". O orçamento nasce RASCUNHO; nada é
     enviado ao cliente.
  3. `ImportacaoConcluidaView` (com orçamento) e `ClienteImportadoView`
     (só o cliente) dizem o que foi criado -- e se o cliente entrou no
     mapa da home --, com os links.

O CLIENTE PRIMEIRO. A conferência abre sempre em "Só cadastrar o
cliente", com "Aparecer no mapa do site" ligado; o orçamento é uma chave.
Da aba Clientes, o botão "Cadastrar pelo Word ou PDF" chega aqui com
`?para=cliente`: a mesma importação, com os textos e a volta da aba
Clientes.

A LEITURA É POR REGRA; A IA É REFORÇO. O Word é lido pelas tabelas e
pelos textos; o PDF com texto, pelo texto de cada página (pypdf, aqui
no servidor). Sem a chave da IA, é isso e funciona. Com ela, a IA lê as
MESMAS linhas numeradas e a conferência aceita só o que estiver escrito
nelas. Falha da IA vai para o log, nunca para a tela: quem importa não
tem nada a fazer com "chave" ou "limite de uso". A única coisa que só a
IA lê é o PDF que é foto (digitalização); sem ela, a tela pede o Word.

QUEM ENTRA. As mesmas portas do orçamento (`OrcamentoInternoRequiredMixin`)
e, dentro delas, só quem pode CRIAR proposta (`orcamentos_criar`): o
Financeiro participa das propostas existentes, mas a criação é do
Comercial -- a mesma regra de `OrcamentosInnerView.acao_save`.
"""

from __future__ import annotations

import logging

from urllib.parse import urlencode

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import View

from core.ls_aviso import avisar
from core.utils import buscar_dados_cep

from .context_processors import invalidar_avisos
from .importacao_word import conferencia, formulario, ia, leitor, mapa, sessao, tela
from .models import Cliente, Orcamento
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
            "para_cliente": self.para_cliente,
            "ia_ligada": ia.chave_configurada(),
            "modelo_ia": ia.modelo_configurado(),
            "tamanho_maximo_mb": leitor.TAMANHO_MAXIMO // (1024 * 1024),
        }
        contexto.update(extras)
        return contexto

    @staticmethod
    def _para_cliente(request) -> bool:
        """Veio da aba Clientes ("Cadastrar pelo Word ou PDF")?"""
        return (request.GET.get("para") or request.POST.get("para") or "") == "cliente"

    def get(self, request):
        self.para_cliente = self._para_cliente(request)
        if not self.pode_criar(request):
            return self.negar(request)
        return render(request, self.template_name, self.contexto())

    def post(self, request):
        self.para_cliente = self._para_cliente(request)
        if not self.pode_criar(request):
            return self.negar(request)
        arquivo = request.FILES.get("arquivo")
        if arquivo is None:
            return render(request, self.template_name, self.contexto(
                erro="Escolha o documento: Word (.docx) ou PDF.",
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

        proposta = conferencia.montar_proposta(leitura)
        # O CEP sem a rua (ou sem a cidade): a mesma consulta do cadastro à
        # mão completa, uma vez só, aqui -- e não a cada abertura da tela.
        leitura["cep_consultado"] = _consultar_cep(proposta)
        if leitura["ia"]["usada"]:
            # A IA escolhe entre os candidatos só dos itens que ficaram em
            # dúvida, e só pode responder um id da lista ou "nenhum".
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

        # De onde a pessoa veio: é para lá que o "Descartar" a devolve.
        leitura["para"] = "cliente" if self.para_cliente else "orcamento"
        token = sessao.guardar(request, leitura)
        return redirect("conferir_importacao_word", token=token)


    def recusar(self, request, mensagem):
        return render(request, self.template_name, self.contexto(erro=mensagem), status=400)

    def ler_docx(self, nome, conteudo):
        linhas = leitor.ler_docx(conteudo, nome)
        leitura = {"arquivo": nome, "formato": "docx", "linhas": linhas, "ia": {"usada": False}, "escolhas": {}}
        leitura["ia"] = _reforco_da_ia(linhas)
        return leitura

    def ler_pdf(self, nome, conteudo):
        """PDF com texto: lido aqui, como o Word. PDF que é foto: só a IA lê.

        O PDF salvo pelo Word ou pelo sistema que fez o orçamento tem o
        texto dentro, e `leitor.ler_pdf_local` tira dele as mesmas linhas
        numeradas do Word -- com a tabela remontada pelas colunas. A IA,
        quando ligada, lê essas linhas como lê as do Word.

        O PDF digitalizado (foto da página) não tem texto nenhum. Com a IA
        ligada, ela transcreve a página; sem ela, a tela pede o Word ou um
        PDF com texto -- em vez de montar um orçamento a partir de nada.
        """
        leitor.conferir_pdf(nome, conteudo)
        try:
            linhas = leitor.ler_pdf_local(conteudo, nome)
        except leitor.PdfSemTexto:
            if not ia.chave_configurada():
                logger.info("PDF sem texto e sem a IA configurada: pedindo o Word (%s).", nome)
                raise
            return self.ler_pdf_pela_ia(nome, conteudo)
        return {
            "arquivo": nome, "formato": "pdf", "linhas": linhas, "escolhas": {},
            "ia": _reforco_da_ia(linhas),
        }

    def ler_pdf_pela_ia(self, nome, conteudo):
        try:
            transcricao, dados, modelo = ia.ler_pdf(conteudo)
        except ia.IAIndisponivel as exc:
            logger.warning("Leitura do PDF digitalizado pela IA falhou (%s): %s", nome, exc)
            raise leitor.ArquivoRecusado(leitor.MENSAGEM_PDF_IMAGEM) from exc
        linhas = leitor.linhas_transcritas(transcricao)
        if not any(l["parte"] in ("corpo", "caixa") for l in linhas):
            raise leitor.ArquivoRecusado(
                "O PDF voltou sem texto legível (digitalização apagada, foto torta ou arquivo "
                "protegido). Envie o arquivo do Word ou um PDF com o texto nítido."
            )
        if not _tem_orcamento(dados):
            raise leitor.ArquivoRecusado(
                "Li o PDF, mas não encontrei nele um orçamento nem um cadastro de cliente. "
                "Confira se é o arquivo certo, ou envie o arquivo do Word."
            )
        return {
            "arquivo": nome, "formato": "pdf_ia", "linhas": linhas, "escolhas": {},
            "ia": {"usada": True, "modelo": modelo, "dados": dados},
        }


def _consultar_cep(proposta) -> dict:
    cliente = proposta["cliente"]
    cep = cliente["cep"]["valor"]
    if not cep or all(cliente[nome]["valor"] for nome in ("logradouro", "bairro", "cidade", "uf")):
        return {}
    try:
        dados = buscar_dados_cep(cep)
    except Exception:  # noqa: BLE001 -- consulta de fora nunca derruba a importação
        logger.warning("Consulta do CEP %s na importação falhou.", cep, exc_info=True)
        return {}
    return dict(dados) if dados else {}


def _reforco_da_ia(linhas) -> dict:
    """A IA lê as linhas numeradas, quando ligada. Sem ela, nada muda na tela.

    O motivo de não ter usado (sem chave, chave recusada, limite de uso)
    fica no log do servidor. A conferência segue com a leitura por regra,
    que é a mesma de sempre.
    """
    if not ia.chave_configurada():
        logger.info("Importação lida só pelas regras: ANTHROPIC_API_KEY não configurada.")
        return {"usada": False}
    try:
        dados, modelo = ia.ler_orcamento(leitor.texto_numerado(linhas))
    except ia.IAIndisponivel as exc:
        logger.warning("Leitura pela IA não aconteceu; seguindo com as regras: %s", exc)
        return {"usada": False}
    return {"usada": True, "modelo": modelo, "dados": dados}


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
            avisar(
                request,
                "Esta importação não está mais aberta (ela vale 12 horas e some quando o "
                "orçamento é criado). Importe o documento de novo.",
                titulo="Importação expirada", icone="arquivo",
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
        # Logo depois da leitura, a tela abre com a decisão (o modal); de
        # volta de um envio recusado, não -- a pessoa já decidiu.
        return self.desenhar(request, token, leitura, proposta, envio, decidir=True)

    def post(self, request, token):
        if not self.pode_criar(request):
            return self.negar(request)
        leitura = self._abrir(request, token)
        if leitura is None:
            return redirect("importar_orcamento_word")

        if request.POST.get("action") == "descartar":
            sessao.descartar(request, token)
            # O toast de aplicativo (core/ls_aviso.py), e não mais a caixa
            # no alto da tela: o título diz o que aconteceu, o texto diz com
            # qual arquivo, e o botão leva a outra importação.
            para_cliente = leitura.get("para") == "cliente"
            importar = reverse("importar_orcamento_word") + ("?para=cliente" if para_cliente else "")
            avisar(
                request,
                f"“{leitura['arquivo']}” foi descartado. Nada foi cadastrado.",
                nivel=messages.SUCCESS, titulo="Importação descartada", icone="arquivo-x",
                acao=(importar, "Importar outro"),
            )
            return redirect("clientes_inner" if para_cliente else "orcamentos_inner")

        proposta = conferencia.montar_proposta(leitura)
        envio = formulario.ler_envio(request.POST)
        validado = formulario.validar(proposta, envio)
        if not validado["pronto"]:
            return self.desenhar(
                request, token, leitura, formulario.aplicar_envio(proposta, envio), envio,
                validado=validado, status=400,
                erro=(
                    "O cliente ainda não pode ser cadastrado: veja o que falta preencher."
                    if envio["modo"] == "cliente"
                    else "O orçamento ainda não pode ser criado: veja o que falta preencher."
                ),
            )
        try:
            criado = formulario.criar(request, proposta, validado, arquivo=leitura["arquivo"])
        except ErroDeFormulario as exc:
            # O cadastro de clientes tem a última palavra (nome repetido,
            # CPF de outro cliente): a tela volta com o motivo dele.
            return self.desenhar(
                request, token, leitura, formulario.aplicar_envio(proposta, envio), envio,
                validado=validado, status=400, erro=str(exc),
            )
        sessao.descartar(request, token)
        invalidar_avisos(request.user)
        cliente = criado["cliente"]
        orcamento = criado["orcamento"]
        # O alfinete: depois de salvar e fora da transação (ver mapa.py).
        # Achando ou não o endereço, o cliente já está cadastrado.
        no_mapa = mapa.colocar_no_mapa(cliente) if criado["mapa_pedido"] else {
            "marcado": cliente.publicar_no_mapa, "no_mapa": cliente.no_mapa, "onde": "", "motivo": "",
            "ja_estava": cliente.no_mapa,
        }
        resumo = {
            "arquivo": leitura["arquivo"],
            "cliente_novo": criado["cliente_novo"],
            "completados": criado["completados"],
            "mapa": no_mapa,
            "para": leitura.get("para", ""),
        }
        if orcamento is None:
            sessao.guardar_conclusao(request, f"c{cliente.pk}", resumo)
            return redirect("cliente_importado", pk=cliente.pk)
        sessao.guardar_conclusao(request, orcamento.pk, resumo)
        return redirect("importacao_concluida", pk=orcamento.pk)

    def desenhar(self, request, token, leitura, proposta, envio, *, validado=None, status=200, erro="",
                 decidir=False):
        validado = validado or formulario.validar(proposta, envio)
        # No "Só cadastrar o cliente" os alertas de dinheiro não contam --
        # mas a tela tem de tê-los prontos, para quem troca para "criar
        # orçamento" ver ali mesmo o que a conta diz.
        do_orcamento = validado if envio["modo"] == "orcamento" else formulario.validar(
            proposta, dict(envio, modo="orcamento"),
        )
        do_cliente = validado if envio["modo"] == "cliente" else formulario.validar(
            proposta, dict(envio, modo="cliente"),
        )
        pergunta = formulario.pergunta_de_orcamento(proposta)
        oferta = formulario.oferta_de_orcamento(proposta)
        alertas = do_orcamento["alertas"]
        for alerta in alertas:
            if alerta["id"] in envio["justificativas"]:
                alerta["aceito"] = True
                alerta["justificativa"] = envio["justificativas"][alerta["id"]]
        vermelhos = [a for a in alertas if a["nivel"] == conferencia.NIVEL_VERMELHO]
        # O cliente que a leitura achou no cadastro: se ele já está no mapa,
        # a chave do mapa diz isso em vez de prometer um alfinete novo.
        vinculo_id = proposta["cliente"]["vinculo"]["cliente_id"]
        ligado = Cliente.objects.filter(pk=vinculo_id).first() if vinculo_id else None

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
            "validade_padrao": Orcamento.validade_padrao(),
            "oferta_orcamento": oferta,
            "pergunta_orcamento": pergunta,
            # A decisão (o modal que abre logo depois da leitura) e os
            # painéis da tela guiada: ver importacao_word/tela.py.
            "decidir": decidir,
            "decisao": tela.decisao(proposta, envio, do_cliente=do_cliente, do_orcamento=do_orcamento,
                                    pergunta=pergunta, oferta=oferta),
            "paineis": tela.paineis(proposta, envio, validado, do_orcamento),
            "repetido": do_orcamento.get("repetido"),
            "ja_no_mapa": bool(ligado and ligado.no_mapa),
            "contas": do_orcamento["contas"],
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
                # O valor final que a escolha "Qual total vale?" grava: o
                # negociado escrito no documento, ou o total que não bate.
                "valorFinal": (proposta.get("valor_final") or {}).get("valor", ""),
                "valorFinalExplicito": bool((proposta.get("valor_final") or {}).get("explicito")),
                "nomeDocumento": proposta["cliente"]["nome"]["valor"],
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


def _links_do_cliente(cliente) -> dict:
    busca = {"q": cliente.nome_cliente}
    return {
        # A ficha (histórico) aberta na lista de clientes.
        "link_cliente": f"{reverse('clientes_inner')}?{urlencode(dict(busca, abrir=cliente.pk))}",
        # O cadastro aberto para editar: é onde se acerta o endereço.
        "link_editar_cliente": f"{reverse('clientes_inner')}?{urlencode(dict(busca, editar=cliente.pk))}",
    }


class ImportacaoConcluidaView(_SoQuemCriaProposta, View):
    """O que a importação criou, com o caminho para cada coisa.

    Abrir direto a edição do orçamento escondia a outra metade: que o
    cliente também foi cadastrado (ou ligado ao que já existia, e
    completado) -- e se ele entrou no mapa. Esta tela diz tudo e leva a
    cada coisa.

    Só quem importou vê: o orçamento é dele (`responsavel`), e o resumo
    do que mudou no cliente vem da sessão dele.
    """

    template_name = "importacao_concluida_inner.html"

    def get(self, request, pk):
        if not self.pode_criar(request):
            return self.negar(request)
        orcamento = get_object_or_404(
            Orcamento.objects.select_related("cliente"), pk=pk, responsavel=request.user,
        )
        resumo = sessao.conclusao(request, pk) or {}
        cliente = orcamento.cliente
        itens = list(orcamento.itens.select_related("brinquedo", "produto", "peca").order_by("id"))
        contexto = {
            "orcamento": orcamento,
            "cliente": cliente,
            "itens": itens,
            "resumo": resumo,
            "mapa": resumo.get("mapa") or {},
            "link_orcamento": f"{reverse('orcamentos_inner')}?editar={orcamento.pk}",
            **(_links_do_cliente(cliente) if cliente else {"link_cliente": "", "link_editar_cliente": ""}),
        }
        return render(request, self.template_name, contexto)


class ClienteImportadoView(_SoQuemCriaProposta, View):
    """A tela final do "Só cadastrar o cliente": quem é, e se está no mapa.

    O cadastro pelo documento existe para povoar o mapa da home. Então a
    tela diz, com todas as letras, se o alfinete foi desenhado (e onde) ou
    por que não -- com o caminho para acertar o endereço na ficha.

    Só quem importou vê: o resumo vem da sessão dele.
    """

    template_name = "importacao_concluida_inner.html"

    def get(self, request, pk):
        if not self.pode_criar(request):
            return self.negar(request)
        resumo = sessao.conclusao(request, f"c{pk}")
        if resumo is None:
            return redirect(f"{reverse('clientes_inner')}?{urlencode({'abrir': pk})}")
        cliente = get_object_or_404(Cliente, pk=pk)
        mapa_agora = dict(resumo.get("mapa") or {})
        # O endereço pode ter sido acertado na ficha depois: vale o de agora.
        if mapa_agora.get("marcado") and cliente.no_mapa:
            mapa_agora.update(no_mapa=True, motivo="")
        contexto = {
            "orcamento": None,
            "cliente": cliente,
            "itens": [],
            "resumo": resumo,
            "mapa": mapa_agora,
            "link_orcamento": "",
            "link_novo_orcamento": f"{reverse('orcamentos_inner')}?{urlencode({'novo': 1, 'cliente': cliente.pk})}",
            **_links_do_cliente(cliente),
        }
        return render(request, self.template_name, contexto)
