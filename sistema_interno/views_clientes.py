"""Aba de clientes do painel interno.

POR QUE ESTA TELA EXISTE. O cliente aparecia no sistema só como um nome
digitado dentro de um orçamento. Quem ligava pela segunda vez virava um
cadastro novo, o histórico nascia partido e não havia como responder duas
perguntas simples: quanto este cliente já fechou, e quais clientes vieram
por qual buffet.

O buffet é cliente também -- aluga brinquedo, pede peça, chama
manutenção --, então mora na mesma lista, marcado como parceiro. O que os
liga é `Cliente.parceiro`.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import (
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Prefetch,
    Q,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, Greatest
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import View

from core.models import Estabelecimentos

from . import clientes as svc
from .completude_clientes import filtro_incompletos, pendencias_do_cliente
from .busca_local import montar_indice
from .models import Cliente, EnderecoCliente, Orcamento
from .exclusoes import forcando, remover
from .permissoes import limitar_orcamentos, pode_excluir_cliente
from .rotas import dados_rota, origem_empresa
from .utils import ErroDeFormulario, exigir_confirmacao_exclusao, texto
from .views import (
    GestorInternoRequiredMixin,
    InternoRequiredMixin,
    RespostaJSONMixin,
)


ZERO = Decimal("0.00")


class ClientesInnerView(RespostaJSONMixin, GestorInternoRequiredMixin, View):
    """Lista, cadastra e liga clientes a buffets parceiros."""

    rota_padrao = "clientes_inner"
    template_name = "clientes_inner.html"
    POR_PAGINA = 30

    # ------------------------------------------------------------ leitura
    def get(self, request):
        busca = (request.GET.get("q") or "").strip()
        tipo = (request.GET.get("tipo") or "").strip()
        parceiro = (request.GET.get("parceiro") or "").strip()
        apenas_incompletos = (request.GET.get("incompletos") or "") == "1"

        consulta = (
            svc.com_publicacao_mapa()
            .select_related("parceiro", "estabelecimento")
            .prefetch_related(
                Prefetch(
                    "enderecos",
                    queryset=EnderecoCliente.objects.order_by("id"),
                ),
                Prefetch("orcamentos", queryset=self._orcamentos_resumidos()),
            )
            .annotate(
                clientes_do_buffet=Count("clientes_atendidos", distinct=True),
            )
            .order_by("nome_cliente", "id")
        )

        consulta = svc.buscar(consulta, busca)

        if tipo in Cliente.Tipo.values:
            consulta = consulta.filter(tipo=tipo)

        if parceiro.isdigit():
            consulta = consulta.filter(parceiro_id=int(parceiro))

        if apenas_incompletos:
            consulta = consulta.filter(filtro_incompletos()).distinct()

        # O índice cobre o filtro inteiro; a página é só o que se desenha.
        # É por ele que o navegador filtra sem ir ao servidor, e é ele que
        # sabe dizer quando o cliente procurado está em outra página.
        indice_busca = montar_indice(
            (
                pk,
                [nome, telefone, telefone_digitos, email, documento, parceiro, negocio, cnpj],
            )
            for pk, nome, telefone, telefone_digitos, email, documento, parceiro, negocio, cnpj
            in consulta.values_list(
                "pk", "nome_cliente", "telefone", "telefone_digitos", "email",
                "documento", "parceiro__nome_cliente", "nome_estabelecimento", "cnpj_estabelecimento",
            )
        )

        pagina = Paginator(consulta, self.POR_PAGINA).get_page(
            request.GET.get("page")
        )

        # A lista vira list() para os totais calculados abaixo não se
        # perderem quando o template percorrer a página de novo.
        pagina.object_list = list(pagina.object_list)
        origem = origem_empresa()
        fichas = [self.ficha(cliente, origem) for cliente in pagina.object_list]

        todos = svc.com_publicacao_mapa()
        buffets = list(
            todos.filter(tipo=Cliente.Tipo.BUFFET).order_by("nome_cliente")
        )
        totais = todos.aggregate(
            clientes=Count("id", distinct=True),
            buffets=Count("id", filter=Q(tipo=Cliente.Tipo.BUFFET), distinct=True),
            vinculados=Count("id", filter=Q(parceiro__isnull=False), distinct=True),
            sem_contato=Count(
                "id",
                filter=(Q(telefone="") | Q(telefone__isnull=True))
                & (Q(email="") | Q(email__isnull=True)),
                distinct=True,
            ),
            no_mapa=Count("id", filter=(Q(publicar_no_mapa=True) | Q(_proposta_mapa=True)) & Q(ativo=True, enderecos__latitude__isnull=False, enderecos__longitude__isnull=False), distinct=True),
            incompletos=Count("id", filter=filtro_incompletos(), distinct=True),
        )

        ids_da_pagina = [cliente.pk for cliente in pagina.object_list]
        estabelecimentos_disponiveis = (
            Estabelecimentos.objects
            .filter(Q(clientes_internos__isnull=True) | Q(clientes_internos__id__in=ids_da_pagina))
            .distinct()
            .order_by("nome_estabelecimento")
        )

        contexto = {
            "fichas": fichas,
            "page_obj": pagina,
            "indice_busca": indice_busca,
            "busca": busca,
            "tipo_ativo": tipo,
            "parceiro_ativo": parceiro,
            "apenas_incompletos": apenas_incompletos,
            "tipos": Cliente.Tipo.choices,
            "buffets": buffets,
            "estabelecimentos": estabelecimentos_disponiveis,
            "total_clientes": totais["clientes"],
            "total_buffets": totais["buffets"],
            "total_vinculados": totais["vinculados"],
            "total_sem_contato": totais["sem_contato"],
            "total_no_mapa": totais["no_mapa"],
            "total_incompletos": totais["incompletos"],
            "empresa_localizacao": origem,
            "clientes_dados": [self.serializar(c) for c in pagina.object_list],
            "opcoes_buffets": [
                {
                    "valor": str(b.id),
                    "rotulo": b.nome_cliente,
                    "detalhe": b.contato_curto,
                }
                for b in buffets
            ],
            "opcoes_estabelecimentos": [
                {
                    "valor": str(estabelecimento.pk),
                    "rotulo": estabelecimento.nome_estabelecimento,
                    "detalhe": "Parceiro exibido no site",
                    "grupo": "Parceiros públicos",
                }
                for estabelecimento in estabelecimentos_disponiveis
            ],
        }

        return render(request, self.template_name, contexto)

    @staticmethod
    def _orcamentos_resumidos():
        """Uma linha agregada por proposta; não baixa cada item para a lista."""
        dinheiro = DecimalField(max_digits=14, decimal_places=2)
        linha = ExpressionWrapper(
            F("itens__quantidade") * F("itens__valor_unitario"),
            output_field=dinheiro,
        )
        return (
            Orcamento.objects
            .only("id", "cliente_id", "status", "criacao", "desconto", "frete")
            .annotate(
                _subtotal_calculado=Coalesce(
                    Sum(linha), Value(ZERO), output_field=dinheiro
                )
            )
            .annotate(
                _total_calculado=Greatest(
                    ExpressionWrapper(
                        F("_subtotal_calculado") + F("frete") - F("desconto"),
                        output_field=dinheiro,
                    ),
                    Value(ZERO),
                )
            )
        )

    @staticmethod
    def ficha(cliente: Cliente, origem: dict) -> dict:
        """O que a lista mostra de cada cliente, já somado.

        Os orçamentos vêm no prefetch, então a soma acontece em memória:
        uma consulta a mais por cliente encheria a tela de idas ao banco
        justamente na hora em que a lista cresce.
        """
        orcamentos = list(cliente.orcamentos.all())
        aprovados = [
            o for o in orcamentos
            if o.status == Orcamento.Status.APROVADO
        ]
        abertos = [o for o in orcamentos if o.status in Orcamento.EM_ABERTO]

        endereco = cliente.endereco_principal

        # Cliente com histórico é protegido pelas regras normais: apagar
        # deixaria propostas já enviadas sem cliente vinculado. O
        # superusuário passa por cima, mas a janela de confirmação precisa
        # dizer isso antes -- ver `data-protegido` no template.
        cliente.tem_historico = bool(orcamentos) or bool(
            getattr(cliente, "clientes_do_buffet", 0)
        )

        return {
            "obj": cliente,
            "endereco": endereco,
            "pendencias": pendencias_do_cliente(cliente),
            "rota": dados_rota(destino=endereco, origem=origem),
            "orcamentos": len(orcamentos),
            "aprovados": len(aprovados),
            "abertos": len(abertos),
            "total_aprovado": sum(
                (getattr(o, "_total_calculado", ZERO) for o in aprovados),
                ZERO,
            ),
            "ultimo": max(
                (o.criacao for o in orcamentos if o.criacao),
                default=None,
            ),
        }

    @staticmethod
    def serializar(cliente: Cliente) -> dict:
        """Payload que o modal usa para reabrir um cadastro."""
        endereco = cliente.endereco_principal

        return {
            "id": cliente.id,
            "nome_cliente": cliente.nome_cliente,
            "tipo": cliente.tipo,
            "documento": cliente.documento,
            "nome_estabelecimento": cliente.nome_estabelecimento,
            "cnpj_estabelecimento": cliente.cnpj_estabelecimento,
            "publicacao_automatica": bool(getattr(cliente, "_proposta_mapa", False)),
            "telefone": cliente.telefone,
            "canal_telefone": cliente.canal_telefone,
            "email": cliente.email or "",
            "parceiro": str(cliente.parceiro_id or ""),
            "estabelecimento": str(cliente.estabelecimento_id or ""),
            "observacoes": cliente.observacoes,
            "cep": endereco.cep if endereco else "",
            "endereco": endereco.endereco if endereco else "",
            "numero": endereco.numero if endereco else "",
            "complemento": endereco.complemento if endereco else "",
            "bairro": endereco.bairro if endereco else "",
            "cidade": endereco.cidade if endereco else "",
            "estado": endereco.estado if endereco else "",
            "pais": (endereco.pais if endereco else "") or "Brasil",
            "latitude": str(endereco.latitude) if endereco and endereco.latitude is not None else "",
            "longitude": str(endereco.longitude) if endereco and endereco.longitude is not None else "",
            # O que o site mostra deste cliente.
            "publicar_no_mapa": cliente.publicar_no_mapa,
            "site_cliente": cliente.site_cliente or "",
            "logo_url": cliente.logo.url if cliente.logo else "",
            "ativo": cliente.ativo,
            # "Marcado para o mapa" e "desenhado no mapa" são coisas
            # diferentes: sem coordenada, o alfinete não existe. A tela
            # precisa dizer isso em vez de deixar a pessoa achar que
            # publicou.
            "no_mapa": cliente.no_mapa,
        }

    # ------------------------------------------------------------- ações
    def acao_save(self, request):
        cliente_id = (request.POST.get("id") or "").strip()
        cliente = (
            get_object_or_404(Cliente, pk=cliente_id) if cliente_id else None
        )

        salvo = svc.salvar_cliente(request, cliente)
        svc.salvar_endereco(request, salvo)

        # Proposta já fechada põe o cliente no mapa sem ninguém precisar
        # lembrar de marcar a caixa.
        if salvo.orcamentos.filter(status=Orcamento.Status.APROVADO).exists():
            svc.publicar_no_mapa(salvo)

        salvo.refresh_from_db()
        return self.sucesso(
            request,
            (
                f"Cliente “{salvo.nome_cliente}” salvo e no mapa do site."
                if salvo.no_mapa
                else f"Cliente “{salvo.nome_cliente}” salvo."
            ),
            id=salvo.id,
            cliente=svc.opcao_de_busca(salvo),
            mapa_publicado=salvo.no_mapa,
        )

    def acao_completar(self, request):
        """Preenche o que faltava, sem abrir o cadastro inteiro.

        A lista já dizia "Falta contato, endereço" -- mas o único caminho
        para resolver era "Editar", que abre o formulário completo e
        espalha os três campos vazios no meio de vinte preenchidos. Quem
        estava com o cliente no telefone procurava onde digitar.
        """
        cliente = get_object_or_404(Cliente, pk=request.POST.get("id"))

        svc.completar_cadastro(request, cliente)
        svc.salvar_endereco(request, cliente)
        cliente.refresh_from_db()

        # O que ainda falta volta junto: é com isso que a linha atualiza
        # (ou apaga) o aviso sem recarregar a tela.
        faltando = pendencias_do_cliente(cliente)
        return self.sucesso(
            request,
            (
                f"Cadastro de “{cliente.nome_cliente}” completo."
                if not faltando
                else f"“{cliente.nome_cliente}” atualizado. Ainda falta: "
                     + ", ".join(faltando) + "."
            ),
            id=cliente.id,
            pendencias=faltando,
            resumo=svc.opcao_de_busca(cliente),
        )

    def acao_delete(self, request):
        superusuario = bool(getattr(request.user, "is_superuser", False))
        if not pode_excluir_cliente(request.user) and not superusuario:
            return self.erro(
                request,
                "Somente a equipe de Gestão pode excluir clientes.",
                status=403,
            )

        cliente = get_object_or_404(Cliente, pk=request.POST.get("id"))
        exigir_confirmacao_exclusao(request)

        # Apagar levaria junto o vínculo dos orçamentos (SET_NULL) e o
        # histórico do cliente sumiria da proposta já enviada. Vale para
        # todo mundo -- menos para quem responde pela empresa, que precisa
        # poder desfazer um cadastro duplicado sem mexer no banco por
        # fora. Nesse caso a exclusão fica registrada. Ver `exclusoes.py`.
        orcamentos = cliente.orcamentos.count()
        atendidos = cliente.clientes_atendidos.count()
        limpo = not orcamentos and not atendidos

        if not limpo and not superusuario:
            if orcamentos:
                raise ErroDeFormulario(
                    f"“{cliente.nome_cliente}” tem orçamento no histórico e "
                    "não pode ser excluído. Corrija o cadastro em vez de "
                    "apagar."
                )
            raise ErroDeFormulario(
                f"“{cliente.nome_cliente}” é o buffet responsável por outros "
                "clientes. Troque o buffet deles antes de excluir."
            )

        nome = cliente.nome_cliente
        forcada = forcando(request.user, limpo)

        remover(
            cliente,
            autor=request.user,
            tipo="Cliente",
            identificacao=nome,
            resumo=(
                f"Documento: {cliente.documento or '—'}. "
                f"Telefone: {cliente.telefone or '—'}. "
                f"{orcamentos} orçamento(s) no histórico, "
                f"{atendidos} cliente(s) atendido(s)."
            ),
            motivo=texto(request, "motivo_exclusao", limite=240),
            forcada=forcada,
        )

        recado = f"Cliente “{nome}” excluído."
        if forcada and orcamentos:
            recado += (
                f" Ele tinha {orcamentos} orçamento(s) no histórico, que"
                " ficaram sem cliente vinculado. A exclusão foi registrada."
            )
        elif forcada:
            recado += " A exclusão foi registrada."
        return self.sucesso(request, recado)


class DossieClienteView(InternoRequiredMixin, View):
    """Tudo o que a empresa já fez com este cliente, num lugar só.

    POR QUE ISTO FALTAVA. Cliente, orçamento e O.S. viviam em três telas
    que não se olhavam. Para responder "o que já vendemos para o Buffet
    Alegria?" era preciso abrir Orçamentos, filtrar pelo nome, abrir
    Ordens de Serviço, filtrar de novo, e somar de cabeça -- na frente do
    cliente, no telefone. O sistema tinha a informação e não a juntava.

    Junto vem o que dá para FAZER a partir daí: mandar uma promoção ou um
    combo para esta pessoa. A divulgação nasceu em massa ("todos os
    buffets"), mas a conversa comercial de verdade é um a um -- o
    atendente está olhando a ficha de quem acabou de ligar. Sem isto, a
    única saída era disparar para o segmento inteiro ou copiar o texto na
    mão, que é como a mensagem sai sem registro nenhum.

    Devolve JSON: a lista de clientes é grande, e carregar o histórico de
    todos junto com ela seria pagar por dezenas de consultas que ninguém
    vai olhar. O painel busca quando alguém abre a ficha.
    """

    #: O suficiente para reconhecer o padrão do cliente sem virar
    #: relatório. Quem precisa do histórico inteiro tem a tela de
    #: Orçamentos, com filtro e paginação.
    LIMITE = 10

    def get(self, request, pk):
        cliente = get_object_or_404(Cliente, pk=pk)

        orcamentos = list(
            limitar_orcamentos(request.user, cliente.orcamentos.all())
            .prefetch_related("itens")
            .order_by("-criacao", "-id")[:self.LIMITE]
        )
        ordens = list(
            cliente.ordens_servico
            .prefetch_related("itens")
            .order_by("-criacao", "-id")[:self.LIMITE]
        )

        aprovados = [
            o for o in orcamentos if o.status == Orcamento.Status.APROVADO
        ]

        return JsonResponse({
            "status": "sucesso",
            "cliente": {
                "id": cliente.pk,
                "nome": cliente.nome_cliente,
                "email": cliente.email or "",
                "telefone": cliente.telefone or "",
                "whatsapp_confirmado": (
                    cliente.canal_telefone == Cliente.CanalTelefone.WHATSAPP
                ),
                "tipo": cliente.get_tipo_display(),
            },
            "resumo": {
                "orcamentos": cliente.orcamentos.count(),
                "aprovados": len(aprovados),
                "ordens": cliente.ordens_servico.count(),
                "total_aprovado": f"{sum((o.total for o in aprovados), ZERO):.2f}",
            },
            "orcamentos": [
                {
                    "id": o.pk,
                    "situacao": o.get_status_display(),
                    "estado": o.status,
                    "total": f"{o.total:.2f}",
                    "criado": timezone.localtime(o.criacao).strftime("%d/%m/%Y")
                    if o.criacao else "",
                    "validade": o.validade.strftime("%d/%m/%Y") if o.validade else "",
                    "vencido": o.vencido,
                    "itens": o.itens.count(),
                    "previa": reverse(
                        "orcamento_previa_inner", args=[o.pk],
                        urlconf="sistema_interno.urls",
                    ),
                }
                for o in orcamentos
            ],
            "ordens": [
                {
                    "id": ordem.pk,
                    "numero": ordem.numero_documento,
                    "situacao": ordem.get_status_display(),
                    "estado": ordem.status,
                    "equipamento": ordem.equipamento or "",
                    "total": f"{ordem.total:.2f}",
                    "agendada": (
                        timezone.localtime(ordem.agendada_para).strftime("%d/%m/%Y %H:%M")
                        if ordem.agendada_para else ""
                    ),
                    "previa": reverse(
                        "ordem_servico_previa_inner", args=[ordem.pk],
                        urlconf="sistema_interno.urls",
                    ),
                }
                for ordem in ordens
            ],
        })


class ConsultaCepInnerView(GestorInternoRequiredMixin, View):
    """Uma rota interna para todos os formulários reaproveitarem o CEP."""

    def get(self, request):
        try:
            dados = svc.consultar_cep(request.GET.get("cep") or "")
        except ErroDeFormulario as exc:
            return JsonResponse({"status": "erro", "msg": str(exc)}, status=400)

        return JsonResponse({"status": "sucesso", "endereco": dados})
