"""Central operacional de Ordens de Serviço.

Orçamento é negociação; O.S. é execução. Este módulo mantém os dois
documentos ligados quando a proposta aprovada libera o trabalho, sem usar
um como substituto do outro.
"""

import json
import logging
import re
from collections import defaultdict
from decimal import Decimal
from urllib.parse import quote

from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count, Prefetch, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.generic import View

from core.email_utils import (
    cnpj_empresa,
    diagnostico_smtp,
    nome_empresa,
    remetente,
    responder_para,
    smtp_configurado,
)
from core.models import CategoriaPeca, Manutencao, PecasReposicao

from .busca_local import montar_indice
from . import clientes as svc_clientes
from . import fragmento
from .models import (
    Cliente,
    EnderecoCliente,
    EnvioOrdemServico,
    ItemOrdemServico,
    OrdemServico,
)
from .exclusoes import forcando, pode_excluir, remover
from . import pecas as svc_pecas
from .permissoes import capacidades
from .rotas import dados_rota, origem_empresa, texto_endereco
from .utils import (
    ErroDeFormulario,
    decimal_br,
    endereco_do_site,
    exigir_confirmacao_exclusao,
    inteiro,
    texto,
)
from .views import OrdemServicoInternoRequiredMixin, RespostaJSONMixin


def _data_hora(valor, rotulo):
    valor = (valor or "").strip()
    if not valor:
        return None
    # Aceita o formato nativo dos navegadores (YYYY-MM-DDTHH:MM) e o
    # equivalente com espaço. Segundos são descartados: a agenda é uma
    # decisão operacional, não um cronômetro.
    momento = parse_datetime(valor.replace(" ", "T"))
    if momento is None:
        raise ErroDeFormulario(f"{rotulo}: data ou hora inválida.")
    if timezone.is_naive(momento):
        try:
            momento = timezone.make_aware(
                momento, timezone.get_current_timezone()
            )
        except (OverflowError, ValueError):
            raise ErroDeFormulario(
                f"{rotulo}: este horário não existe no fuso configurado."
            )
    return momento.replace(second=0, microsecond=0)


def _data_calendario(valor, rotulo):
    valor = (valor or "").strip()
    if not valor:
        return None
    resultado = parse_date(valor)
    if resultado is None:
        raise ErroDeFormulario(f"{rotulo}: data inválida.")
    return resultado


def _agendar(ordem, request, status):
    """Lê agendamento e garantia sem deixar marcar serviço para ontem.

    O CUIDADO AQUI NÃO É "DATA NO PASSADO É ERRADA". Metade das O.S. da
    fábrica é digitada DEPOIS do atendimento: o técnico foi ontem, o
    serviço acabou, e alguém registra hoje. Recusar data passada nesse
    caso impediria de fechar a O.S. do trabalho que já foi feito.

    O que não pode existir é O.S. que ainda VAI acontecer marcada para um
    dia que já passou. Ninguém vai. Ela some da agenda de amanhã, não
    aparece em atraso em lugar nenhum, e o cliente fica esperando.

    Por isso a recusa vale só quando as duas coisas são verdade ao mesmo
    tempo: a data mudou agora (O.S. antiga continua salvando com a data
    que sempre teve) E a O.S. está num estado de trabalho por fazer.

    A garantia é mais simples: garantia que terminou antes de ser escrita
    não protege ninguém, então só é recusada quando muda para trás.
    """
    agendada = _data_hora(request.POST.get("agendada_para"), "Agendamento")
    garantia = _data_calendario(request.POST.get("garantia_ate"), "Garantia")

    # O campo do navegador não tem segundos, e `_data_hora` zera o que
    # sobra. Uma O.S. gravada pelo sistema TEM segundos: comparar os dois
    # crus dava "mudou" para uma agenda que ninguém tocou, e editar a
    # observação de uma O.S. antiga passava a exigir remarcar o serviço.
    agenda_atual = (
        ordem.agendada_para.replace(second=0, microsecond=0)
        if ordem.agendada_para else None
    )

    por_fazer = status in (
        OrdemServico.Status.RASCUNHO,
        OrdemServico.Status.AGUARDANDO_RESPOSTA,
        OrdemServico.Status.ABERTA,
        OrdemServico.Status.AGENDADA,
    )

    if (
        agendada
        and por_fazer
        and agendada != agenda_atual
        and agendada < timezone.now()
    ):
        raise ErroDeFormulario(
            "O agendamento está no passado. Uma O.S. que ainda vai "
            "acontecer não pode ser marcada para um dia que já passou — "
            "escolha uma data de hoje em diante, ou registre a situação "
            "como Em execução ou Concluída se o serviço já foi feito."
        )

    if (
        garantia
        and garantia != ordem.garantia_ate
        and garantia < timezone.localdate()
    ):
        raise ErroDeFormulario(
            "A garantia terminaria antes de hoje. Escolha uma data de hoje "
            "em diante ou deixe o campo em branco."
        )

    ordem.agendada_para = agendada
    ordem.garantia_ate = garantia


def _moeda_br(valor):
    numero = Decimal(valor or 0).quantize(Decimal("0.01"))
    return f"{numero:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def espelho_da_manutencao(manutencao, ja_tem_os=False):
    """Tudo que o chamado já sabe, no formato que o formulário da O.S. usa.

    POR QUE ISTO EXISTE NO SERVIDOR, E NÃO NO `data-` DA <option>.

    O espelho morava em atributos da opção do <select>. Isso amarrava a
    cópia à existência da opção: chamado já concluído, cancelado, ou
    simplesmente fora dos 100 mais antigos que a tela carrega, e o link
    "Gerar O.S." abria o formulário VAZIO -- sem aviso, sem erro, sem
    nada. Quem clicou digitava tudo de novo achando que o sistema nunca
    tinha prometido copiar.

    Aqui o painel recebe o espelho pronto de cada chamado que ele pode
    abrir, e o chamado pedido pela URL entra na lista mesmo quando não
    caberia nela. Também é aqui que o endereço vira uma linha só, com
    bairro e CEP -- que era o que faltava para o técnico não ter de abrir
    o chamado noutra aba para saber onde é.
    """
    perfil = manutencao.usuario
    usuario = getattr(perfil, "user", None)
    nome = (
        (getattr(perfil, "nome_completo", "") or "").strip()
        or (getattr(usuario, "get_full_name", lambda: "")() or "").strip()
        or (getattr(usuario, "username", "") or "").strip()
    )
    telefone = (
        (manutencao.telefone_contato or "").strip()
        or (getattr(perfil, "telefone", "") or "").strip()
    )
    return {
        "id": manutencao.id,
        "codigo": "MAN-%05d" % manutencao.id,
        "equipamento": manutencao.nome_equipamento,
        "nome_cliente": nome,
        # Quem abriu o chamado é o responsável no local até que se diga
        # outra coisa: é o nome para quem o técnico pergunta ao chegar.
        "contato": nome,
        "whatsapp_cliente": telefone,
        "email_cliente": (getattr(usuario, "email", "") or "").strip(),
        "defeito_relatado": (manutencao.descricao or "").strip(),
        "endereco_servico": texto_endereco(manutencao),
        "cidade": (manutencao.cidade or "").strip(),
        "estado": (manutencao.estado or "").strip(),
        "situacao": manutencao.get_status_display(),
        "aberto_em": timezone.localtime(manutencao.criado_em).strftime(
            "%d/%m/%Y %H:%M"
        ) if manutencao.criado_em else "",
        "ja_tem_os": bool(ja_tem_os),
    }


class OrdensServicoInnerView(
    RespostaJSONMixin, OrdemServicoInternoRequiredMixin, View
):
    rota_padrao = "ordens_servico_inner"
    ACOES_SEM_TRANSACAO = ("enviar",)
    POR_PAGINA = 25

    def indice_de_busca(self, consulta):
        """Os mesmos campos que a busca do servidor percorre.

        Se divergirem, a pessoa vê um resultado ao digitar e outro ao
        apertar "Trazer todos", e passa a não confiar em nenhum dos dois.
        """
        base = list(
            consulta.values_list(
                "pk", "criacao", "nome_cliente", "cliente__nome_cliente",
                "equipamento", "numero_serie", "defeito_relatado",
                "servico_executado",
            )
        )
        itens = defaultdict(list)
        for ordem_id, descricao in ItemOrdemServico.objects.filter(
            ordem_id__in=[linha[0] for linha in base]
        ).values_list("ordem_id", "descricao"):
            itens[ordem_id].append(descricao)

        def numero(pk, criacao):
            # Mesmo texto de `OrdemServico.numero_documento`: quem procura
            # digita o que está na tela, não a chave do banco.
            ano = criacao.year if criacao else timezone.localdate().year
            return "OS-%05d/%s" % (pk, ano)

        return montar_indice(
            (
                linha[0],
                [numero(linha[0], linha[1]), str(linha[0])]
                + list(linha[2:])
                + itens.get(linha[0], []),
            )
            for linha in base
        )

    def get(self, request):
        busca = (request.GET.get("q") or "").strip()
        filtro = (request.GET.get("filtro") or "todos").strip()

        # TROCAR O FILTRO NÃO PRECISA REMONTAR O FORMULÁRIO.
        #
        # Baixar menos foi metade do problema; a outra metade é o
        # servidor deixar de PRODUZIR o que ninguém vai receber. Quando o
        # pedido é só a lista, ficam de fora: os 300 clientes do
        # autocompletar (com os endereços de cada um), os chamados de
        # manutenção que o formulário copia, o catálogo de peças da
        # reserva local e a checagem de SMTP. Nada disso aparece na
        # tabela -- e cada um custa consulta, serialização ou rede.
        so_a_lista = fragmento.pediu_lista(request)

        consulta = (
            OrdemServico.objects
            .select_related(
                "cliente", "orcamento", "manutencao__usuario__user",
                "tecnico", "responsavel",
                # A linha imprime "refeita da OS-00041" e "virou a
                # OS-00043" quando existem. Sem estes dois, cada O.S. com
                # histórico custava duas consultas extras só para
                # escrever o número da vizinha.
                "ordem_anterior", "ordem_refeita",
            )
            .prefetch_related(
                "itens",
                "envios__responsavel",
                Prefetch(
                    "cliente__enderecos",
                    queryset=EnderecoCliente.objects.order_by("id"),
                ),
            )
        )
        if busca:
            condicao = (
                Q(nome_cliente__icontains=busca)
                | Q(cliente__nome_cliente__icontains=busca)
                | Q(equipamento__icontains=busca)
                | Q(numero_serie__icontains=busca)
                | Q(defeito_relatado__icontains=busca)
                | Q(servico_executado__icontains=busca)
                | Q(itens__descricao__icontains=busca)
            )
            busca_id = busca.upper().replace("OS-", "").split("/")[0].lstrip("0")
            if busca_id.isdigit():
                condicao |= Q(pk=int(busca_id))
            consulta = consulta.filter(condicao).distinct()

        a_receber = (
            ~Q(status_pagamento=OrdemServico.StatusPagamento.PAGO)
            & ~Q(status__in=(
                OrdemServico.Status.RASCUNHO,
                OrdemServico.Status.CANCELADA,
                OrdemServico.Status.SUBSTITUIDA,
            ))
        )
        # A VERSÃO SUBSTITUÍDA NÃO APARECE DE PRIMEIRA.
        #
        # Ela continua inteira, e continua achável -- o cartão "Versões
        # anteriores" é o caminho, e a busca por número acha as duas.
        # O que ela não faz é dividir a lista de trabalho com a versão
        # que está valendo: duas linhas do mesmo serviço, com totais
        # diferentes, é como alguém cobra duas vezes.
        arquivadas = Q(status__in=OrdemServico.ARQUIVADAS)
        filtros = {
            "todos": ~arquivadas,
            "abertas": Q(status__in=OrdemServico.ABERTAS),
            "aguardando": Q(status=OrdemServico.Status.AGUARDANDO_RESPOSTA),
            "agendadas": Q(status=OrdemServico.Status.AGENDADA),
            "execucao": Q(status=OrdemServico.Status.EM_EXECUCAO),
            "pecas": Q(status=OrdemServico.Status.AGUARDANDO_PECA),
            "concluidas": Q(status=OrdemServico.Status.CONCLUIDA),
            "a_receber": a_receber,
            "pagas": (
                Q(status_pagamento=OrdemServico.StatusPagamento.PAGO)
                & ~arquivadas
            ),
            "substituidas": arquivadas,
        }
        if filtro not in filtros:
            filtro = "todos"

        base_cards = consulta
        contagens = base_cards.aggregate(
            todos=Count("pk", filter=~arquivadas),
            abertas=Count("pk", filter=Q(status__in=OrdemServico.ABERTAS)),
            aguardando=Count(
                "pk", filter=Q(status=OrdemServico.Status.AGUARDANDO_RESPOSTA)
            ),
            agendadas=Count("pk", filter=Q(status=OrdemServico.Status.AGENDADA)),
            execucao=Count("pk", filter=Q(status=OrdemServico.Status.EM_EXECUCAO)),
            pecas=Count("pk", filter=Q(status=OrdemServico.Status.AGUARDANDO_PECA)),
            concluidas=Count("pk", filter=Q(status=OrdemServico.Status.CONCLUIDA)),
            a_receber=Count(
                "pk", filter=a_receber
            ),
            pagas=Count(
                "pk",
                filter=(
                    Q(status_pagamento=OrdemServico.StatusPagamento.PAGO)
                    & ~arquivadas
                ),
            ),
            substituidas=Count("pk", filter=arquivadas),
        )
        financeiro = self.dinheiro_do_topo(base_cards, arquivadas)
        consulta = consulta.filter(filtros[filtro])

        # O índice cobre o filtro inteiro; a página é só o que se desenha.
        # É o que permite ao navegador dizer "existe, mas está na página
        # seguinte" em vez de responder "nada encontrado".
        indice_busca = self.indice_de_busca(consulta)

        pagina = Paginator(consulta, self.POR_PAGINA).get_page(request.GET.get("page"))
        ordens = list(pagina.object_list)

        base_publica = endereco_do_site(request)
        origem = origem_empresa()
        for ordem in ordens:
            # Mesma regra do orçamento: a página do cliente recusa uma
            # O.S. que ainda não foi enviada, então o painel não mostra o
            # endereço dela. Ver `OrdemServico.publicado`.
            ordem.link_publico = (
                f"{base_publica}{ordem.caminho_publico}"
                if ordem.publicado else ""
            )
            ordem.mensagem_whatsapp = (
                self.mensagem(ordem, ordem.link_publico)
                if ordem.link_publico else ""
            )
            ordem.whatsapp_url = self.conversa_whatsapp(
                ordem.whatsapp_destinatario, ordem.mensagem_whatsapp
            )
            endereco_cliente = (
                ordem.cliente.endereco_principal if ordem.cliente_id else None
            )
            usar_coordenadas = (
                endereco_cliente
                if not ordem.endereco_servico
                or ordem.endereco_servico == texto_endereco(endereco_cliente)
                else None
            )
            ordem.rota = dados_rota(
                destino_texto=ordem.endereco_servico,
                destino=usar_coordenadas,
                origem=origem,
            )

        clientes_dados = []
        if not so_a_lista:
            clientes = (
                Cliente.objects
                .select_related("parceiro")
                .prefetch_related(Prefetch(
                    "enderecos",
                    queryset=EnderecoCliente.objects.order_by("id"),
                ))
                .order_by("nome_cliente")
            )
            clientes_dados = [
                svc_clientes.opcao_de_busca(cliente)
                for cliente in clientes
            ]

        # ------------------------------------------------------------------
        # CHAMADOS DE MANUTENÇÃO QUE O FORMULÁRIO PODE COPIAR
        # ------------------------------------------------------------------
        # A fila normal é a dos chamados em aberto. Mas o link "Gerar O.S."
        # da central de manutenções aponta para UM chamado específico, e
        # esse chamado precisa existir na lista mesmo que já esteja
        # concluído ou fora da janela dos 100 -- senão o formulário abre
        # vazio e a promessa de poupar digitação não se cumpre.
        manutencoes = []
        manutencoes_dados = {}
        manutencao_pedida = 0
        if not so_a_lista:
            manutencoes = list(
                Manutencao.objects
                .filter(status__in=("P", "A"))
                .select_related("brinquedo", "usuario__user")
                .order_by("criado_em")[:100]
            )
            pedido = (request.GET.get("manutencao") or "").strip()
            if pedido.isdigit():
                manutencao_pedida = int(pedido)
                if not any(m.id == manutencao_pedida for m in manutencoes):
                    extra = (
                        Manutencao.objects
                        .select_related("brinquedo", "usuario__user")
                        .filter(pk=manutencao_pedida)
                        .first()
                    )
                    if extra:
                        manutencoes.insert(0, extra)
                    else:
                        manutencao_pedida = 0

            # Um chamado já atendido continua podendo virar outra O.S.
            # (uma segunda visita é comum), mas quem escolhe precisa
            # saber disso antes de clicar -- e não depois de gerar a
            # segunda.
            com_os = set(
                OrdemServico.objects
                .filter(manutencao_id__in=[m.id for m in manutencoes])
                .exclude(status=OrdemServico.Status.SUBSTITUIDA)
                .values_list("manutencao_id", flat=True)
            )
            manutencoes_dados = {
                str(m.id): espelho_da_manutencao(m, m.id in com_os)
                for m in manutencoes
            }

        acesso = capacidades(request.user)
        contexto = {
            "ordens": ordens,
            "ordens_dados": [self.serializar(ordem) for ordem in ordens],
            "page_obj": pagina,
            "indice_busca": indice_busca,
            "busca": busca,
            "filtro_ativo": filtro,
            "cards": (
                ("todos", "Todas", contagens["todos"], "bi-grid"),
                ("abertas", "Em aberto", contagens["abertas"], "bi-clipboard2-pulse"),
                ("aguardando", "Aguardando ciência", contagens["aguardando"], "bi-hourglass-split"),
                ("agendadas", "Agendadas", contagens["agendadas"], "bi-calendar2-check"),
                ("execucao", "Em execução", contagens["execucao"], "bi-tools"),
                ("pecas", "Aguardando peça", contagens["pecas"], "bi-gear"),
                ("concluidas", "Concluídas", contagens["concluidas"], "bi-check2-circle"),
                ("a_receber", "A receber", contagens["a_receber"], "bi-wallet2"),
                ("pagas", "Pagas", contagens["pagas"], "bi-cash-coin"),
                ("substituidas", "Versões anteriores", contagens["substituidas"], "bi-clock-history"),
            ),
            "total_recebido": financeiro["recebido"],
            "total_em_servico": financeiro["em_servico"],
            "total_a_receber": financeiro["a_receber"],
            "total_concluido": financeiro["concluido"],
            "clientes_dados": clientes_dados,
            "tipos_cliente": Cliente.Tipo.choices,
            "empresa_localizacao": origem,
            "manutencoes": manutencoes,
            # O espelho de cada chamado, pronto para o formulário copiar.
            # Ver `espelho_da_manutencao`.
            "manutencoes_dados": manutencoes_dados,
            "manutencao_pedida": manutencao_pedida,
            "tecnicos": self._tecnicos(),
            "categorias_peca": CategoriaPeca.objects.order_by("nome_categoria_peca"),
            "tipos": OrdemServico.Tipo.choices,
            # Que etapa cada situação já alcançou. É o que faz o
            # formulário revelar o bloco de execução só quando existe
            # execução para relatar. Ver `OrdemServico.Etapa`.
            "etapas_por_situacao": {
                valor: [
                    etapa
                    for etapa in OrdemServico.SEQUENCIA_DE_ETAPAS
                    if OrdemServico.etapa_alcancada(valor, etapa)
                ]
                for valor, _ in OrdemServico.Status.choices
            },
            # SUBSTITUÍDA NÃO É UMA SITUAÇÃO QUE SE ESCOLHE.
            #
            # Ela é o efeito de refazer, e só. Oferecê-la no seletor
            # deixaria alguém congelar uma O.S. sem criar a versão que a
            # substitui -- um documento fora da lista, sem sucessor, e
            # sem caminho de volta.
            "status_opcoes": [
                (valor, rotulo)
                for valor, rotulo in OrdemServico.Status.choices
                if valor != OrdemServico.Status.SUBSTITUIDA
            ],
            "prioridades": OrdemServico.Prioridade.choices,
            "item_tipos": ItemOrdemServico.Tipo.choices,
            # Reserva local da busca de peças. A tela já conseguiu abrir,
            # então esta consulta simples também conseguiu; se a chamada
            # assíncrona cair, o técnico continua trabalhando sem perder a O.S.
            "itens_os_fallback": [] if so_a_lista else [
                {
                    "valor": f"r:{peca.pk}",
                    "rotulo": peca.nome,
                    "grupo": (
                        "Itens de manutenção"
                        if peca.uso == PecasReposicao.Uso.MANUTENCAO
                        else "Peças de reposição"
                    ),
                    "detalhe": (
                        peca.descricao_peca
                        or (
                            "Item de manutenção"
                            if peca.uso == PecasReposicao.Uso.MANUTENCAO
                            else "Peça da loja"
                        )
                    )[:90],
                    "valorDireita": (
                        f"R$ {peca.preco_venda:.2f}".replace(".", ",")
                        if peca.preco_venda is not None else "sem preço"
                    ),
                    "preco": (
                        f"{peca.preco_venda:.2f}".replace(".", ",")
                        if peca.preco_venda is not None else ""
                    ),
                    "imagem": "",
                }
                for peca in PecasReposicao.objects.all().order_by("nome")
            ],
            # A checagem de SMTP fala com a configuração de e-mail. É
            # barata, mas não é grátis, e a tabela não a usa.
            "email_configurado": so_a_lista or smtp_configurado(),
            "email_diagnostico": None if so_a_lista else diagnostico_smtp(),
            "pode_editar": acesso["ordens_servico_editar"],
            "pode_pagamento": acesso["ordens_servico_pagamento"],
        }
        return fragmento.responder(
            request, "ordens_servico_inner.html",
            "partes/os_lista.html", contexto,
        )

    @staticmethod
    def dinheiro_do_topo(consulta, arquivadas):
        """Os quatro números da faixa de valores.

        O QUE ESTAVA ALI ANTES NÃO ERA NÚMERO.

        Três das quatro caixas diziam "Documento: Operacional",
        "Orçamento: Negociação separada" e "Impressão: A4 e PDF". São
        frases verdadeiras e completamente inúteis: não mudam, não
        respondem nada e ninguém as lê duas vezes. Ocupavam, no topo da
        tela, exatamente o lugar onde a tela de propostas mostra quatro
        valores que mudam todo dia.

        Agora respondem o que se pergunta ao chegar: quanto já entrou,
        quanto está preso em serviço que ainda não acabou, quanto falta
        receber do que já foi entregue, e quanto o mês fechou.

        POR QUE DUAS CONSULTAS, E NÃO UMA. O total de uma O.S. é a soma
        dos itens mais frete menos desconto -- e a soma dos itens vem de
        outra tabela. Somar tudo num `aggregate` só significaria juntar
        `valor_pago` (uma linha por O.S.) com um JOIN de itens (várias
        linhas por O.S.) na mesma consulta: cada pagamento seria contado
        uma vez por item da ordem. São grandezas de cardinalidade
        diferente, então são duas consultas.
        """
        from django.db.models import DecimalField, F, Value
        from django.db.models.functions import Coalesce

        zero = Decimal("0.00")
        vivas = consulta.filter(~arquivadas)

        recebido = vivas.aggregate(total=Sum("valor_pago"))["total"] or zero

        # O bruto de cada O.S., linha a linha. `distinct` não cabe aqui
        # -- a soma é sobre os itens, e dois itens de mesmo valor na
        # mesma ordem são duas cobranças, não uma repetição.
        bruto = Coalesce(
            Sum(F("itens__quantidade") * F("itens__valor_unitario")),
            Value(zero),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
        por_ordem = vivas.annotate(bruto_itens=bruto).annotate(
            valor=F("bruto_itens") + F("frete") - F("desconto")
        )

        em_servico = por_ordem.filter(
            status__in=OrdemServico.ABERTAS
        ).aggregate(total=Sum("valor"))["total"] or zero

        # A RECEBER É SALDO, E SALDO NÃO É NEGATIVO.
        #
        # Uma O.S. em que entrou mais do que o total (entrada dobrada,
        # troco pendente) não pode abater o que os outros clientes ainda
        # devem -- e é isso que uma subtração de somas faria. Por isso o
        # `max` é por linha, e a soma vem depois.
        #
        # `values` em vez de `only`: a consulta que desenha as linhas
        # carrega `select_related` e prefetches de que esta conta não
        # precisa, e adiar campos por cima daquilo o Django recusa.
        # Pedindo só as duas colunas, nada disso entra na conta.
        a_receber = sum(
            (
                max(linha["valor"] - (linha["valor_pago"] or zero), zero)
                for linha in por_ordem.exclude(
                    status__in=(
                        OrdemServico.Status.RASCUNHO,
                        OrdemServico.Status.CANCELADA,
                    )
                ).exclude(
                    status_pagamento=OrdemServico.StatusPagamento.PAGO
                ).values("valor", "valor_pago")
            ),
            zero,
        )

        concluido = por_ordem.filter(
            status=OrdemServico.Status.CONCLUIDA
        ).aggregate(total=Sum("valor"))["total"] or zero

        return {
            "recebido": recebido,
            "em_servico": em_servico,
            "a_receber": a_receber,
            "concluido": concluido,
        }

    @staticmethod
    def _tecnicos():
        from django.contrib.auth.models import User
        from .permissoes import PRODUCAO, GESTAO, tem_funcao

        return [
            usuario for usuario in User.objects.filter(is_active=True).order_by(
                "first_name", "username"
            )
            if tem_funcao(usuario, PRODUCAO) or tem_funcao(usuario, GESTAO)
        ]

    @staticmethod
    def serializar(ordem):
        # Importado aqui, e não no topo: `views_gestao` já importa deste
        # módulo, e subir a dependência fecharia o ciclo na carga do app.
        # O que se aproveita é a montagem da opção do catálogo, para a
        # linha da O.S. mostrar a peça exatamente como o orçamento mostra.
        from .views_gestao import OrcamentosInnerView

        return {
            "id": ordem.pk,
            "cliente": ordem.cliente_id or "",
            "manutencao": ordem.manutencao_id or "",
            "orcamento": ordem.orcamento_id or "",
            "nome_cliente": ordem.nome_cliente,
            "contato": ordem.contato,
            "whatsapp_cliente": ordem.whatsapp_destinatario,
            "email_cliente": ordem.email_destinatario,
            "endereco_servico": ordem.endereco_servico,
            "tipo": ordem.tipo,
            "status": ordem.status,
            "prioridade": ordem.prioridade,
            "equipamento": ordem.equipamento,
            "numero_serie": ordem.numero_serie,
            "defeito_relatado": ordem.defeito_relatado,
            "diagnostico": ordem.diagnostico,
            "servico_executado": ordem.servico_executado,
            "observacoes": ordem.observacoes,
            "forma_pagamento": ordem.forma_pagamento,
            "frete": f"{ordem.frete:.2f}".replace(".", ","),
            "desconto": f"{ordem.desconto:.2f}".replace(".", ","),
            "status_pagamento": ordem.status_pagamento,
            "valor_pago": f"{ordem.valor_pago:.2f}".replace(".", ","),
            "link_publico": getattr(ordem, "link_publico", ""),
            "mensagem_whatsapp": getattr(ordem, "mensagem_whatsapp", ""),
            "preview_url": reverse(
                "ordem_servico_previa_inner", args=[ordem.pk],
                urlconf="sistema_interno.urls",
            ),
            "agendada_para": (
                timezone.localtime(ordem.agendada_para).strftime("%Y-%m-%dT%H:%M")
                if ordem.agendada_para else ""
            ),
            "garantia_ate": ordem.garantia_ate.isoformat() if ordem.garantia_ate else "",
            "tecnico": ordem.tecnico_id or "",
            "envios": OrdensServicoInnerView.historico_envios(ordem),
            "versao": ordem.versao,
            "motivo_refacao": ordem.motivo_refacao,
            "pode_editar": ordem.pode_editar,
            # As versões viajam com a O.S., e não na lista -- mesma regra
            # da proposta. A prévia é o caminho de cada uma: a
            # substituída não está na lista da página, então reabri-la
            # pelo id nesta tela não acharia nada.
            "versoes": [
                {
                    "id": v.pk,
                    "versao": v.versao,
                    "numero": v.numero_documento,
                    "rotulo": v.get_status_display(),
                    "total": f"{v.total:.2f}".replace(".", ","),
                    "quando": (
                        timezone.localtime(v.criacao).strftime("%d/%m/%Y")
                        if v.criacao else ""
                    ),
                    "motivo": v.motivo_refacao,
                    "atual": v.pk == ordem.pk,
                    "previa": reverse(
                        "ordem_servico_previa_inner", args=[v.pk],
                        urlconf="sistema_interno.urls",
                    ),
                }
                for v in ordem.cadeia_de_versoes()
            ] if ordem.versao > 1 or ordem.ordem_anterior_id else [],
            "itens": [{
                "tipo": item.tipo,
                "descricao": item.descricao,
                "peca": item.peca_id or "",
                "opcao": (
                    OrcamentosInnerView.opcao_peca(item.peca)
                    if item.peca_id and item.peca else None
                ),
                "quantidade": str(item.quantidade),
                "valor_unitario": f"{item.valor_unitario:.2f}".replace(".", ","),
            } for item in ordem.itens.all()],
        }

    def acao_save(self, request):
        if not capacidades(request.user)["ordens_servico_editar"]:
            return self.erro(request, "Somente Produção ou Gestão edita a O.S.", status=403)

        ordem_id = (request.POST.get("id") or "").strip()
        ordem = get_object_or_404(OrdemServico, pk=ordem_id) if ordem_id else OrdemServico()
        if not ordem.pode_editar:
            # Editar a versão que o cliente leu apagaria o papel que ele
            # tem na mão. O que se edita é a versão que está valendo.
            raise ErroDeFormulario(
                "Esta versão foi substituída e permanece somente no "
                "histórico. Edite a versão que está valendo."
            )

        cliente_id = (request.POST.get("cliente") or "").strip()
        manutencao_id = (request.POST.get("manutencao") or "").strip()
        tecnico_id = (request.POST.get("tecnico") or "").strip()

        ordem.cliente = Cliente.objects.filter(pk=cliente_id).first() if cliente_id.isdigit() else None
        ordem.manutencao = Manutencao.objects.filter(pk=manutencao_id).first() if manutencao_id.isdigit() else None
        ordem.nome_cliente = texto(request, "nome_cliente", limite=120)
        ordem.contato = texto(request, "contato", limite=120)
        ordem.whatsapp_cliente = texto(request, "whatsapp_cliente", limite=24)
        ordem.email_cliente = texto(request, "email_cliente", limite=254)
        if ordem.email_cliente:
            try:
                validate_email(ordem.email_cliente)
            except ValidationError:
                raise ErroDeFormulario("Informe um e-mail válido para o cliente.")

        ordem.endereco_servico = texto(request, "endereco_servico", limite=320)
        ordem.equipamento = texto(
            request, "equipamento", obrigatorio=True,
            rotulo="o equipamento", limite=180,
        )
        ordem.numero_serie = texto(request, "numero_serie", limite=80)
        ordem.defeito_relatado = texto(request, "defeito_relatado")
        ordem.diagnostico = texto(request, "diagnostico")
        ordem.servico_executado = texto(request, "servico_executado")
        ordem.observacoes = texto(request, "observacoes")
        ordem.forma_pagamento = texto(request, "forma_pagamento", limite=120)
        ordem.frete = decimal_br(
            request.POST.get("frete") or "0", "Frete",
            limite=Decimal("9999999999.99"),
        )
        ordem.desconto = decimal_br(
            request.POST.get("desconto") or "0", "Desconto",
            limite=Decimal("9999999999.99"),
        )
        if ordem.frete < 0 or ordem.desconto < 0:
            raise ErroDeFormulario("Frete e desconto não podem ser negativos.")

        tipo = (request.POST.get("tipo") or "").strip()
        status = (request.POST.get("status") or "").strip()
        prioridade = (request.POST.get("prioridade") or "").strip()
        if tipo not in OrdemServico.Tipo.values:
            raise ErroDeFormulario("Escolha um tipo de serviço válido.")
        if status not in OrdemServico.Status.values:
            raise ErroDeFormulario("Escolha uma situação válida.")
        if status == OrdemServico.Status.SUBSTITUIDA:
            raise ErroDeFormulario(
                "“Substituída” não se escolhe: ela é o resultado de "
                "refazer a O.S., que cria a versão nova no mesmo passo."
            )
        if prioridade not in OrdemServico.Prioridade.values:
            raise ErroDeFormulario("Escolha uma prioridade válida.")
        # NÃO SE CONCLUI SEM DIZER O QUE FOI FEITO.
        #
        # É a contrapartida de não perguntar cedo demais. "Serviço
        # executado" saiu da abertura porque lá ninguém sabe a resposta;
        # na conclusão, ele é a resposta -- é o que o cliente lê para
        # entender pelo que está pagando, e o que a garantia cobre.
        # Concluída em branco vira, meses depois, uma O.S. que ninguém
        # sabe explicar.
        if (
            status == OrdemServico.Status.CONCLUIDA
            and not texto(request, "servico_executado")
        ):
            raise ErroDeFormulario(
                "Para concluir, escreva o serviço executado: é o que o "
                "cliente lê para saber pelo que está pagando."
            )

        ordem.tipo = tipo
        ordem.status = status
        ordem.prioridade = prioridade
        _agendar(ordem, request, status)
        from django.contrib.auth.models import User
        ordem.tecnico = User.objects.filter(pk=tecnico_id).first() if tecnico_id.isdigit() else None
        if not ordem.pk:
            ordem.responsavel = request.user
        if status == OrdemServico.Status.EM_EXECUCAO and not ordem.iniciada_em:
            ordem.iniciada_em = timezone.now()
        if status == OrdemServico.Status.CONCLUIDA and not ordem.concluida_em:
            ordem.concluida_em = timezone.now()
        ordem.save()
        # NÚMERO DE SÉRIE NÃO PODE SER UMA ADIVINHAÇÃO OBRIGATÓRIA.
        #
        # Se o equipamento tiver etiqueta do fabricante, a equipe pode
        # digitá-la. Quando não tiver -- brinquedo antigo, fabricação
        # própria ou patrimônio sem plaqueta -- a própria O.S. ganha uma
        # identificação interna estável. O id só existe depois do primeiro
        # save, por isso o preenchimento acontece aqui.
        if not ordem.numero_serie:
            ordem.numero_serie = f"LS-PAT-{ordem.pk:06d}"
            ordem.save(update_fields=["numero_serie", "atualizado"])
        self._gravar_itens(ordem, request.POST.get("itens"))

        return self.sucesso(
            request,
            f"{ordem.numero_documento} salva — total R$ {ordem.total:.2f}.",
            id=ordem.pk,
        )

    @staticmethod
    def _gravar_itens(ordem, bruto):
        try:
            linhas = json.loads(bruto or "[]")
        except (TypeError, ValueError):
            raise ErroDeFormulario("Não consegui ler os itens da O.S.")
        # ITEM NÃO É EXIGIDO PARA SALVAR.
        #
        # Era: toda O.S. precisava de ao menos uma linha antes de gravar.
        # Mas um chamado que acabou de entrar não tem item nenhum -- não
        # se sabe que peça vai ser usada antes de o técnico abrir o
        # equipamento. A exigência obrigava quem abria a inventar uma
        # linha de R$ 0,00 só para conseguir salvar, e essa linha
        # inventada ia junto para o documento do cliente.
        #
        # Há também o serviço em garantia, que se conclui legitimamente
        # sem cobrar nada. Uma O.S. sem item é um fato do trabalho, e não
        # um erro de preenchimento.
        if not isinstance(linhas, list):
            raise ErroDeFormulario("Não consegui ler os itens da O.S.")
        if len(linhas) > 80:
            raise ErroDeFormulario("Uma O.S. aceita no máximo 80 itens.")

        # Uma consulta para todas as peças da O.S. A versão anterior fazia
        # um SELECT por linha; em banco remoto, dez peças eram dez viagens
        # de rede antes de o bulk_create sequer começar.
        ids_pecas = {
            int(str(linha.get("peca") or "").strip())
            for linha in linhas
            if isinstance(linha, dict)
            and (linha.get("tipo") or "").strip() == ItemOrdemServico.Tipo.PECA
            and str(linha.get("peca") or "").strip().isdigit()
        }
        pecas = PecasReposicao.objects.in_bulk(ids_pecas)

        itens = []
        for indice, linha in enumerate(linhas, 1):
            tipo = (linha.get("tipo") or "").strip()
            descricao = (linha.get("descricao") or "").strip()
            if tipo not in ItemOrdemServico.Tipo.values:
                raise ErroDeFormulario(f"Item {indice}: tipo inválido.")

            # A DESCRIÇÃO SÓ É OBRIGATÓRIA ONDE ELA DIZ ALGO NOVO.
            #
            # "Serviço / mão de obra" já é a descrição de si mesmo: pedir
            # que alguém escreva "mão de obra" na linha do tipo "mão de
            # obra" é pedir para repetir o rótulo. O mesmo vale para
            # deslocamento. Nesses casos o que falta saber é o valor, e
            # é só isso que a linha pergunta.
            #
            # Peça é outra história: "peça" não identifica peça nenhuma.
            # Ali a descrição é o que vai no documento e o que o cliente
            # confere ao receber, então continua obrigatória -- e vem
            # pronta quando a linha sai do catálogo.
            if not descricao:
                if tipo == ItemOrdemServico.Tipo.PECA:
                    raise ErroDeFormulario(
                        f"Item {indice}: diga qual peça ou material. "
                        f"Escolha no catálogo ou escreva o nome."
                    )
                descricao = ItemOrdemServico.Tipo(tipo).label

            # O vínculo com o catálogo é opcional: "recolar a emenda da
            # lona" é o serviço daquele dia e não tem cadastro nenhum.
            # Quando vem, vem da busca -- peça da loja ou item de
            # manutenção, os dois valem aqui.
            peca_id = str(linha.get("peca") or "").strip()
            peca = (
                pecas.get(int(peca_id))
                if tipo == ItemOrdemServico.Tipo.PECA and peca_id.isdigit()
                else None
            )
            quantidade = inteiro(
                str(linha.get("quantidade") or ""),
                f"Item {indice}: quantidade", obrigatorio=True,
                minimo=1, maximo=99999999,
            )
            valor = decimal_br(
                str(linha.get("valor_unitario") or ""),
                f"Item {indice}: valor", obrigatorio=True,
                limite=Decimal("9999999999.99"),
            )
            itens.append(ItemOrdemServico(
                ordem=ordem,
                tipo=tipo,
                peca=peca,
                descricao=descricao[:200],
                quantidade=quantidade,
                valor_unitario=valor,
            ))
        ordem.itens.all().delete()
        ItemOrdemServico.objects.bulk_create(itens)
        cache_relacoes = getattr(ordem, "_prefetched_objects_cache", {})
        cache_relacoes["itens"] = itens
        ordem._prefetched_objects_cache = cache_relacoes

    def acao_pagamento(self, request):
        if not capacidades(request.user)["ordens_servico_pagamento"]:
            return self.erro(request, "Somente Financeiro ou Gestão registra pagamentos.", status=403)
        ordem = get_object_or_404(OrdemServico, pk=request.POST.get("id"))
        if not ordem.pode_receber_pagamento:
            return self.erro(
                request,
                "Esta O.S. já está paga, foi cancelada ou não tem saldo para receber.",
            )
        valor = decimal_br(
            request.POST.get("valor_pago"), "Valor pago",
            obrigatorio=True, limite=Decimal("9999999999.99"),
        )
        observacao = texto(request, "observacao_pagamento", limite=240)
        ordem.registrar_pagamento(valor, observacao)
        return self.sucesso(
            request,
            f"Pagamento de {ordem.numero_documento} atualizado.",
            status_pagamento=ordem.status_pagamento,
        )

    def acao_delete(self, request):
        superusuario = bool(getattr(request.user, "is_superuser", False))
        if not capacidades(request.user)["ordens_servico_editar"] and not superusuario:
            return self.erro(request, "Você não pode excluir esta O.S.", status=403)

        ordem = get_object_or_404(OrdemServico, pk=request.POST.get("id"))

        # Rascunho nunca enviado some sem cerimônia; o resto é histórico
        # operacional e fica. Menos para quem responde pela empresa: ali a
        # exclusão passa, e passa registrada. Ver `exclusoes.py`.
        regra = (
            ordem.status == OrdemServico.Status.RASCUNHO
            and not ordem.enviada_em
        )
        if not pode_excluir(request.user, regra):
            return self.erro(
                request,
                "Somente rascunhos nunca enviados podem ser excluídos.",
                status=403,
            )

        exigir_confirmacao_exclusao(request)
        numero = ordem.numero_documento
        forcada = forcando(request.user, regra)

        arrastados = remover(
            ordem,
            autor=request.user,
            tipo="Ordem de Serviço",
            identificacao=f"{numero} — {ordem.destinatario}",
            resumo=(
                f"Situação: {ordem.get_status_display()}. "
                f"Equipamento: {ordem.equipamento or '—'}. "
                f"{ordem.itens.count()} item(ns). Total: R$ {ordem.total}."
            ),
            motivo=texto(request, "motivo_exclusao", limite=240),
            forcada=forcada,
        )

        recado = f"{numero} removida."
        if forcada:
            recado += " Não era um rascunho: a exclusão ficou registrada."
        if arrastados:
            recado += f" Levou junto: {', '.join(arrastados)}."
        return self.sucesso(request, recado)

    def acao_peca_nova(self, request):
        """Cadastrar a peça sem largar a O.S. pela metade.

        O técnico está com o equipamento aberto na frente dele e descobre
        que precisa cobrar um retentor que ninguém cadastrou. Mandá-lo
        abrir a tela de produtos, cadastrar e voltar significa perder a
        O.S. -- e, na prática, significa escrever "retentor" na descrição
        e seguir, o que deixa a peça fora de qualquer controle de
        estoque e de preço.

        Mesma regra do orçamento, mesmo código: ver `pecas.cadastrar`. O
        que muda é quem pode -- ali é do Comercial, aqui da Produção.
        """
        if not capacidades(request.user)["ordens_servico_editar"]:
            return self.erro(
                request, "Somente Produção ou Gestão cadastra item aqui.", status=403,
            )

        peca = svc_pecas.cadastrar(request)
        return self.sucesso(
            request, svc_pecas.recado(peca), peca=svc_pecas.resumo(peca),
        )

    def acao_cliente_novo(self, request):
        """Cadastra e devolve o cliente sem abandonar a O.S. em montagem.

        O cadastro usa exatamente as regras da aba Clientes e do orçamento.
        Assim o atalho da Produção não cria uma ficha incompleta nem uma
        segunda versão do mesmo cliente.
        """
        if not capacidades(request.user)["ordens_servico_editar"]:
            return self.erro(
                request,
                "Somente Produção ou Gestão cadastra cliente por esta O.S.",
                status=403,
            )

        cliente = svc_clientes.salvar_cliente(request)
        svc_clientes.salvar_endereco(request, cliente)
        return self.sucesso(
            request,
            f"“{cliente.nome_cliente}” foi cadastrado e selecionado na O.S.",
            cliente=svc_clientes.opcao_de_busca(cliente),
        )

    def acao_refazer(self, request):
        """Cria a versão seguinte e congela esta -- mesmo esquema da proposta.

        POR QUE UMA O.S. PRECISA DE VERSÃO.

        A O.S. que o cliente leu e assinou como ciente é o registro do
        que foi combinado naquele dia: qual defeito, qual peça, quanto.
        Ao abrir o equipamento o técnico descobre outra coisa -- era o
        motor, não a lona -- e o caminho era reescrever a O.S. por cima.
        O papel que o cliente tinha na mão deixava de existir, e com ele
        a explicação do valor cobrado. Quando o cliente reclamava do
        preço, não havia como mostrar o que tinha sido combinado antes.

        Aqui a anterior fica inteira e congelada, e a nova nasce
        rascunho, com os mesmos itens, para ser ajustada e enviada. O
        motivo é obrigatório: uma versão sem motivo, meses depois, é uma
        segunda O.S. que ninguém sabe explicar.
        """
        if not capacidades(request.user)["ordens_servico_editar"]:
            return self.erro(
                request, "Somente Produção ou Gestão refaz uma O.S.", status=403,
            )

        anterior = get_object_or_404(OrdemServico, pk=request.POST.get("id"))

        if anterior.status == OrdemServico.Status.RASCUNHO:
            raise ErroDeFormulario(
                "Esta O.S. ainda é rascunho e pode ser editada no lugar."
            )
        if hasattr(anterior, "ordem_refeita"):
            # O SEGUNDO CLIQUE NÃO É ERRO, É O MESMO PEDIDO.
            #
            # Esta verificação vem antes da de "substituída" de
            # propósito: refazer já deixou a anterior nesse estado, e
            # recusar aqui transformaria o clique repetido -- rede lenta,
            # dedo duplo -- num erro vermelho para quem já tinha
            # conseguido o que queria. Devolve a versão que existe.
            nova = anterior.ordem_refeita
            return self.sucesso(
                request,
                f"A versão {nova.versao} desta O.S. já existe.",
                id=nova.pk,
            )
        if anterior.status == OrdemServico.Status.SUBSTITUIDA:
            raise ErroDeFormulario(
                "Esta versão já foi substituída. Refaça a que está valendo."
            )
        if anterior.status == OrdemServico.Status.CANCELADA:
            raise ErroDeFormulario(
                "Uma O.S. cancelada não ganha outra versão: ela não foi "
                "trocada, foi encerrada. Abra uma O.S. nova."
            )
        if anterior.quitado:
            raise ErroDeFormulario(
                "Esta O.S. já está paga e não ganha outra versão: o "
                "pagamento recebido precisa continuar apontando para ela. "
                "Para o que vier depois, abra uma O.S. nova."
            )

        motivo = texto(
            request,
            "motivo_refacao",
            obrigatorio=True,
            rotulo="o motivo da nova versão",
            limite=600,
        )

        with transaction.atomic():
            anterior = OrdemServico.objects.select_for_update().get(pk=anterior.pk)
            nova = OrdemServico.objects.create(
                cliente=anterior.cliente,
                # A PROPOSTA NÃO ACOMPANHA. O vínculo é um-para-um: uma
                # proposta aprovada liberou UMA execução, e apontar as
                # duas versões para ela quebraria a unicidade além de
                # sugerir que a mesma venda gerou dois serviços. Quem
                # quiser a origem comercial a encontra pela versão
                # anterior, que continua inteira.
                orcamento=None,
                manutencao=anterior.manutencao,
                nome_cliente=anterior.nome_cliente,
                contato=anterior.contato,
                whatsapp_cliente=anterior.whatsapp_cliente,
                email_cliente=anterior.email_cliente,
                endereco_servico=anterior.endereco_servico,
                tipo=anterior.tipo,
                # Nasce rascunho: a versão nova ainda vai ser ajustada, e
                # até ser enviada ela não é documento de cliente nenhum.
                status=OrdemServico.Status.RASCUNHO,
                prioridade=anterior.prioridade,
                equipamento=anterior.equipamento,
                numero_serie=anterior.numero_serie,
                defeito_relatado=anterior.defeito_relatado,
                diagnostico=anterior.diagnostico,
                servico_executado=anterior.servico_executado,
                observacoes=anterior.observacoes,
                forma_pagamento=anterior.forma_pagamento,
                frete=anterior.frete,
                desconto=anterior.desconto,
                # AGENDA VENCIDA NÃO ACOMPANHA A VERSÃO NOVA.
                #
                # Refazer é justamente o caminho de quando a data passou.
                # Copiada, a versão nova nascia prometendo um dia que já
                # foi -- e, pela regra de envio, nascia sem poder ser
                # enviada. Vazia, o campo pede a data nova, que é o que
                # falta mesmo. Agenda futura continua vindo junto: ali
                # ela ainda é o combinado.
                agendada_para=(
                    anterior.agendada_para
                    if anterior.agendada_para
                    and anterior.agendada_para >= timezone.now()
                    else None
                ),
                garantia_ate=anterior.garantia_ate,
                tecnico=anterior.tecnico,
                responsavel=request.user,
                ordem_anterior=anterior,
                versao=anterior.versao + 1,
                motivo_refacao=motivo,
            )
            ItemOrdemServico.objects.bulk_create([
                ItemOrdemServico(
                    ordem=nova,
                    tipo=item.tipo,
                    peca=item.peca,
                    descricao=item.descricao,
                    quantidade=item.quantidade,
                    valor_unitario=item.valor_unitario,
                )
                for item in anterior.itens.select_related("peca")
            ])
            # O valor recebido NÃO acompanha. Ele responde ao documento
            # contra o qual entrou, que é o anterior; copiá-lo aqui faria
            # a mesma entrada aparecer duas vezes no financeiro.
            anterior.status = OrdemServico.Status.SUBSTITUIDA
            anterior.save(update_fields=["status", "atualizado"])

        return self.sucesso(
            request,
            f"{nova.numero_com_versao} criada a partir de "
            f"{anterior.numero_documento}, que ficou congelada no "
            f"histórico. Ajuste e envie quando estiver pronta.",
            id=nova.pk,
        )

    def acao_enviar(self, request):
        if not capacidades(request.user)["ordens_servico_editar"]:
            return self.erro(request, "Você não pode enviar esta O.S.", status=403)
        ordem = get_object_or_404(
            OrdemServico.objects.prefetch_related("itens"),
            pk=request.POST.get("id"),
        )
        # SEM ITEM TAMBÉM SE ENVIA.
        #
        # A regra antiga exigia ao menos uma linha para mandar a O.S. ao
        # cliente. Isso barrava dois casos legítimos: o chamado agendado
        # que se manda para o cliente confirmar dia e hora (ainda não há
        # peça nenhuma), e o atendimento em garantia, que se conclui sem
        # cobrar. O documento desses dois diz o que precisa dizer --
        # equipamento, defeito, agenda, o que foi feito -- e o total sai
        # zerado, que é a informação correta.
        if not ordem.pode_enviar:
            # AS AÇÕES SÃO EM CIMA DA SITUAÇÃO. Mandar ao cliente a O.S.
            # de um serviço cancelado, a versão que já foi trocada por
            # outra, ou uma agenda que já passou é pedir decisão sobre um
            # papel que não vale mais. Cada caso tem uma saída diferente,
            # e o recado diz qual é. Ver `OrdemServico.pode_enviar`.
            raise ErroDeFormulario(ordem.motivo_de_nao_enviar)
        canal = (request.POST.get("canal") or "link").strip()
        if canal not in EnvioOrdemServico.Canal.values:
            raise ErroDeFormulario("Escolha WhatsApp, e-mail ou copiar link.")

        link = f"{endereco_do_site(request)}{ordem.caminho_publico}"
        mensagem_texto = self.mensagem(ordem, link)
        destino = ""
        extras = {"link": link, "mensagem": mensagem_texto}

        if canal == EnvioOrdemServico.Canal.WHATSAPP:
            telefone = texto(request, "whatsapp", limite=24) or ordem.whatsapp_destinatario
            if len(re.sub(r"\D", "", telefone)) < 10:
                raise ErroDeFormulario("Informe o WhatsApp do cliente com DDD.")
            ordem.whatsapp_cliente = telefone
            ordem.save(update_fields=["whatsapp_cliente", "atualizado"])
            destino = telefone
            extras["whatsapp_url"] = self.conversa_whatsapp(telefone, mensagem_texto)

        elif canal == EnvioOrdemServico.Canal.EMAIL:
            email = texto(request, "email", limite=254) or ordem.email_destinatario
            try:
                validate_email(email)
            except ValidationError:
                raise ErroDeFormulario("Informe um e-mail válido.")
            if not smtp_configurado():
                self._registrar_envio(request, ordem, canal, email, False, "SMTP não configurado.")
                raise ErroDeFormulario("E-mail não configurado na hospedagem; use WhatsApp ou link.")
            destino = email
            ordem.email_cliente = email
            ordem.save(update_fields=["email_cliente", "atualizado"])
            corpo = (
                f"Olá, {ordem.destinatario}.\n\n"
                f"A {ordem.numero_documento} está disponível em {link}.\n\n"
                "Você pode consultar, imprimir e confirmar o recebimento pelo link.\n\n"
                f"{nome_empresa()}\nCNPJ {cnpj_empresa()}"
            )
            html = render(
                request,
                "emails/ordem_servico_enviada.html",
                {
                    "ordem": ordem,
                    "itens": ordem.itens.all(),
                    "link": link,
                    "total_formatado": _moeda_br(ordem.total),
                    "empresa_nome": nome_empresa(),
                    "empresa_cnpj": cnpj_empresa(),
                },
            ).content.decode()
            email_msg = EmailMultiAlternatives(
                subject=f"Ordem de Serviço {ordem.numero_documento}",
                body=corpo,
                from_email=remetente(),
                to=[email],
                reply_to=responder_para(request.user),
            )
            email_msg.attach_alternative(html, "text/html")
            try:
                enviados = email_msg.send(fail_silently=False)
            except Exception as erro:
                self._registrar_envio(
                    request, ordem, canal, email, False,
                    f"{type(erro).__name__}: {erro}"[:240],
                )
                raise ErroDeFormulario("Não foi possível enviar o e-mail agora.")
            if enviados != 1:
                raise ErroDeFormulario("O servidor não confirmou o envio do e-mail.")

        ordem.marcar_enviada()
        self._registrar_envio(request, ordem, canal, destino)
        extras["envios"] = self.historico_envios(ordem)
        return self.sucesso(
            request,
            (
                f"{ordem.numero_documento} enviada por e-mail."
                if canal == EnvioOrdemServico.Canal.EMAIL
                else f"{ordem.numero_documento} liberada para o cliente."
            ),
            whatsapp=ordem.whatsapp_destinatario,
            email=ordem.email_destinatario,
            **extras,
        )

    @staticmethod
    def _registrar_envio(request, ordem, canal, destino, sucesso=True, detalhe=""):
        try:
            EnvioOrdemServico.objects.create(
                ordem=ordem,
                canal=canal,
                destino=(destino or "")[:254],
                sucesso=sucesso,
                detalhe=(detalhe or "")[:240],
                responsavel=request.user,
            )
        except Exception:
            logging.getLogger(__name__).exception(
                "Falha ao registrar envio da O.S. %s", ordem.pk
            )

    @staticmethod
    def historico_envios(ordem, limite=12):
        try:
            return [{
                "canal": envio.get_canal_display(),
                "destino": envio.destino,
                "sucesso": envio.sucesso,
                "detalhe": envio.detalhe,
                "quando": (
                    timezone.localtime(envio.criacao).strftime("%d/%m/%Y %H:%M")
                    if envio.criacao else ""
                ),
                "por": (
                    envio.responsavel.get_full_name()
                    or envio.responsavel.username
                ) if envio.responsavel else "",
            # `select_related` AQUI DERRUBAVA O PREFETCH DA TELA.
            #
            # A lista já busca `envios__responsavel` de uma vez. Repetir o
            # select_related monta uma consulta nova e joga o cache fora:
            # eram 26 idas ao banco numa página de 25 O.S., uma por linha,
            # para buscar o que já estava na memória. `all()` usa o cache;
            # o corte acontece em Python, sobre uma lista curta.
            } for envio in list(ordem.envios.all())[:limite]]
        except Exception:
            logging.getLogger(__name__).exception(
                "Falha ao ler histórico de envio da O.S. %s", ordem.pk
            )
            return []

    @staticmethod
    def mensagem(ordem, link):
        linhas = [
            f"Olá, {ordem.destinatario}! 👋", "",
            f"Sua *{ordem.numero_documento}* da Lazer & Sport está disponível.", "",
            f"*Equipamento:* {ordem.equipamento}",
            f"*Situação:* {ordem.get_status_display()}",
            f"*Total:* R$ {_moeda_br(ordem.total)}",
        ]
        if ordem.agendada_para:
            linhas.append(
                "Agendamento: "
                + timezone.localtime(ordem.agendada_para).strftime("%d/%m/%Y às %H:%M")
            )
        linhas.extend([
            "",
            "Abra o documento para consultar itens, fotos do atendimento, "
            "imprimir e confirmar o recebimento:",
            link,
            "",
            "Se precisar, responda esta mensagem. 😊",
            f"{nome_empresa()} · CNPJ {cnpj_empresa()}",
        ])
        return "\n".join(linhas)

    @staticmethod
    def conversa_whatsapp(telefone, mensagem):
        digitos = re.sub(r"\D", "", telefone or "")
        if len(digitos) in (10, 11):
            digitos = "55" + digitos
        if len(digitos) < 12:
            return ""
        return f"https://wa.me/{digitos}?text={quote(mensagem, safe='')}"


class OrdemServicoPreviaInnerView(OrdemServicoInternoRequiredMixin, View):
    def get(self, request, pk):
        from core.views_ordem_servico import carregar_ordem, contexto_ordem

        ordem = carregar_ordem(pk=pk)
        return render(
            request,
            "ordem_servico_publica.html",
            contexto_ordem(ordem, previsualizacao=True, request=request),
        )
