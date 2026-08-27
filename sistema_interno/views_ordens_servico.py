"""Central operacional de Ordens de Serviço.

Orçamento é negociação; O.S. é execução. Este módulo mantém os dois
documentos ligados quando a proposta aprovada libera o trabalho, sem usar
um como substituto do outro.
"""

import json
import logging
import re
from datetime import datetime
from decimal import Decimal
from urllib.parse import quote

from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import View

from core.email_utils import remetente, responder_para, smtp_configurado
from core.models import Manutencao

from . import clientes as svc_clientes
from .models import (
    Cliente,
    EnvioOrdemServico,
    ItemOrdemServico,
    OrdemServico,
)
from .permissoes import capacidades
from .utils import (
    ErroDeFormulario,
    decimal_br,
    endereco_do_site,
    exigir_confirmacao_exclusao,
    texto,
)
from .views import OrdemServicoInternoRequiredMixin, RespostaJSONMixin


def _data_hora(valor, rotulo):
    valor = (valor or "").strip()
    if not valor:
        return None
    try:
        momento = datetime.fromisoformat(valor)
    except ValueError:
        raise ErroDeFormulario(f"{rotulo}: data ou hora inválida.")
    if timezone.is_naive(momento):
        momento = timezone.make_aware(momento, timezone.get_current_timezone())
    return momento


class OrdensServicoInnerView(
    RespostaJSONMixin, OrdemServicoInternoRequiredMixin, View
):
    rota_padrao = "ordens_servico_inner"
    ACOES_SEM_TRANSACAO = ("enviar",)
    POR_PAGINA = 25

    def get(self, request):
        busca = (request.GET.get("q") or "").strip()
        filtro = (request.GET.get("filtro") or "todos").strip()

        consulta = (
            OrdemServico.objects
            .select_related(
                "cliente", "orcamento", "manutencao__usuario__user",
                "tecnico", "responsavel",
            )
            .prefetch_related("itens", "envios__responsavel")
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
            ))
        )
        filtros = {
            "todos": Q(),
            "abertas": Q(status__in=OrdemServico.ABERTAS),
            "aguardando": Q(status=OrdemServico.Status.AGUARDANDO_RESPOSTA),
            "agendadas": Q(status=OrdemServico.Status.AGENDADA),
            "execucao": Q(status=OrdemServico.Status.EM_EXECUCAO),
            "pecas": Q(status=OrdemServico.Status.AGUARDANDO_PECA),
            "concluidas": Q(status=OrdemServico.Status.CONCLUIDA),
            "a_receber": a_receber,
            "pagas": Q(status_pagamento=OrdemServico.StatusPagamento.PAGO),
        }
        if filtro not in filtros:
            filtro = "todos"

        base_cards = consulta
        contagens = base_cards.aggregate(
            todos=Count("pk"),
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
            pagas=Count("pk", filter=Q(status_pagamento=OrdemServico.StatusPagamento.PAGO)),
        )
        financeiro = base_cards.aggregate(
            recebido=Sum("valor_pago"),
        )
        consulta = consulta.filter(filtros[filtro])
        pagina = Paginator(consulta, self.POR_PAGINA).get_page(request.GET.get("page"))
        ordens = list(pagina.object_list)

        base_publica = endereco_do_site(request)
        for ordem in ordens:
            ordem.link_publico = f"{base_publica}{ordem.caminho_publico}"
            ordem.mensagem_whatsapp = self.mensagem(ordem, ordem.link_publico)
            ordem.whatsapp_url = self.conversa_whatsapp(
                ordem.whatsapp_destinatario, ordem.mensagem_whatsapp
            )

        clientes = (
            Cliente.objects
            .select_related("parceiro")
            .prefetch_related("enderecos")
            .order_by("nome_cliente")
        )
        clientes_dados = [
            svc_clientes.opcao_de_busca(cliente)
            for cliente in clientes
        ]

        acesso = capacidades(request.user)
        return render(request, "ordens_servico_inner.html", {
            "ordens": ordens,
            "ordens_dados": [self.serializar(ordem) for ordem in ordens],
            "page_obj": pagina,
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
            ),
            "total_recebido": financeiro["recebido"] or Decimal("0.00"),
            "clientes_dados": clientes_dados,
            "manutencoes": (
                Manutencao.objects
                .filter(status__in=("P", "A"))
                .select_related("brinquedo", "usuario__user")
                .order_by("criado_em")[:100]
            ),
            "tecnicos": self._tecnicos(),
            "tipos": OrdemServico.Tipo.choices,
            "status_opcoes": OrdemServico.Status.choices,
            "prioridades": OrdemServico.Prioridade.choices,
            "item_tipos": ItemOrdemServico.Tipo.choices,
            "email_configurado": smtp_configurado(),
            "pode_editar": acesso["ordens_servico_editar"],
            "pode_pagamento": acesso["ordens_servico_pagamento"],
        })

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
            "status_pagamento": ordem.status_pagamento,
            "valor_pago": f"{ordem.valor_pago:.2f}".replace(".", ","),
            "agendada_para": (
                timezone.localtime(ordem.agendada_para).strftime("%Y-%m-%dT%H:%M")
                if ordem.agendada_para else ""
            ),
            "garantia_ate": ordem.garantia_ate.isoformat() if ordem.garantia_ate else "",
            "tecnico": ordem.tecnico_id or "",
            "envios": [{
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
            } for envio in ordem.envios.all()[:12]],
            "itens": [{
                "tipo": item.tipo,
                "descricao": item.descricao,
                "quantidade": f"{item.quantidade:.2f}".replace(".", ","),
                "valor_unitario": f"{item.valor_unitario:.2f}".replace(".", ","),
            } for item in ordem.itens.all()],
        }

    def acao_save(self, request):
        if not capacidades(request.user)["ordens_servico_editar"]:
            return self.erro(request, "Somente Produção ou Gestão edita a O.S.", status=403)

        ordem_id = (request.POST.get("id") or "").strip()
        ordem = get_object_or_404(OrdemServico, pk=ordem_id) if ordem_id else OrdemServico()

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

        tipo = (request.POST.get("tipo") or "").strip()
        status = (request.POST.get("status") or "").strip()
        prioridade = (request.POST.get("prioridade") or "").strip()
        if tipo not in OrdemServico.Tipo.values:
            raise ErroDeFormulario("Escolha um tipo de serviço válido.")
        if status not in OrdemServico.Status.values:
            raise ErroDeFormulario("Escolha uma situação válida.")
        if prioridade not in OrdemServico.Prioridade.values:
            raise ErroDeFormulario("Escolha uma prioridade válida.")
        ordem.tipo = tipo
        ordem.status = status
        ordem.prioridade = prioridade
        ordem.agendada_para = _data_hora(request.POST.get("agendada_para"), "Agendamento")
        ordem.garantia_ate = (
            datetime.strptime(request.POST["garantia_ate"], "%Y-%m-%d").date()
            if (request.POST.get("garantia_ate") or "").strip() else None
        )
        from django.contrib.auth.models import User
        ordem.tecnico = User.objects.filter(pk=tecnico_id).first() if tecnico_id.isdigit() else None
        if not ordem.pk:
            ordem.responsavel = request.user
        if status == OrdemServico.Status.EM_EXECUCAO and not ordem.iniciada_em:
            ordem.iniciada_em = timezone.now()
        if status == OrdemServico.Status.CONCLUIDA and not ordem.concluida_em:
            ordem.concluida_em = timezone.now()
        ordem.save()
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
        if not isinstance(linhas, list) or not linhas:
            raise ErroDeFormulario("Adicione ao menos um serviço, peça ou material.")
        if len(linhas) > 80:
            raise ErroDeFormulario("Uma O.S. aceita no máximo 80 itens.")

        itens = []
        for indice, linha in enumerate(linhas, 1):
            tipo = (linha.get("tipo") or "").strip()
            descricao = (linha.get("descricao") or "").strip()
            if tipo not in ItemOrdemServico.Tipo.values:
                raise ErroDeFormulario(f"Item {indice}: tipo inválido.")
            if not descricao:
                raise ErroDeFormulario(f"Item {indice}: informe a descrição.")
            quantidade = decimal_br(
                str(linha.get("quantidade") or ""),
                f"Item {indice}: quantidade", obrigatorio=True,
                limite=Decimal("99999999.99"),
            )
            valor = decimal_br(
                str(linha.get("valor_unitario") or ""),
                f"Item {indice}: valor", obrigatorio=True,
                limite=Decimal("9999999999.99"),
            )
            if quantidade <= 0:
                raise ErroDeFormulario(f"Item {indice}: quantidade deve ser maior que zero.")
            itens.append(ItemOrdemServico(
                ordem=ordem,
                tipo=tipo,
                descricao=descricao[:200],
                quantidade=quantidade,
                valor_unitario=valor,
            ))
        ordem.itens.all().delete()
        ItemOrdemServico.objects.bulk_create(itens)

    def acao_pagamento(self, request):
        if not capacidades(request.user)["ordens_servico_pagamento"]:
            return self.erro(request, "Somente Financeiro ou Gestão registra pagamentos.", status=403)
        ordem = get_object_or_404(OrdemServico, pk=request.POST.get("id"))
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
        if not capacidades(request.user)["ordens_servico_editar"]:
            return self.erro(request, "Você não pode excluir esta O.S.", status=403)
        ordem = get_object_or_404(OrdemServico, pk=request.POST.get("id"))
        if ordem.status != OrdemServico.Status.RASCUNHO or ordem.enviada_em:
            return self.erro(
                request,
                "Somente rascunhos nunca enviados podem ser excluídos.",
                status=403,
            )
        exigir_confirmacao_exclusao(request)
        numero = ordem.numero_documento
        ordem.delete()
        return self.sucesso(request, f"{numero} removida.")

    def acao_enviar(self, request):
        if not capacidades(request.user)["ordens_servico_editar"]:
            return self.erro(request, "Você não pode enviar esta O.S.", status=403)
        ordem = get_object_or_404(
            OrdemServico.objects.prefetch_related("itens"),
            pk=request.POST.get("id"),
        )
        if not ordem.itens.exists():
            raise ErroDeFormulario("Adicione ao menos um item antes de enviar.")
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
            corpo = (
                f"Olá, {ordem.destinatario}.\n\n"
                f"A {ordem.numero_documento} está disponível em {link}.\n\n"
                "Você pode consultar, imprimir e confirmar o recebimento pelo link.\n\n"
                "Lazer & Sport Brinquedos"
            )
            email_msg = EmailMultiAlternatives(
                subject=f"Ordem de Serviço {ordem.numero_documento}",
                body=corpo,
                from_email=remetente(),
                to=[email],
                reply_to=responder_para(request.user),
            )
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
        return self.sucesso(
            request,
            f"{ordem.numero_documento} pronta para enviar.",
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
    def mensagem(ordem, link):
        linhas = [
            f"Olá, {ordem.destinatario}! Aqui é da Lazer & Sport.", "",
            f"Sua {ordem.numero_documento} está disponível.",
            f"Equipamento: {ordem.equipamento}",
            f"Situação: {ordem.get_status_display()}",
        ]
        if ordem.agendada_para:
            linhas.append(
                "Agendamento: "
                + timezone.localtime(ordem.agendada_para).strftime("%d/%m/%Y às %H:%M")
            )
        linhas.extend(["", "Abra para consultar, imprimir e confirmar:", link])
        return "\n".join(linhas)

    @staticmethod
    def conversa_whatsapp(telefone, mensagem):
        digitos = re.sub(r"\D", "", telefone or "")
        if len(digitos) in (10, 11):
            digitos = "55" + digitos
        if len(digitos) < 12:
            return ""
        return f"https://wa.me/{digitos}?text={quote(mensagem)}"


class OrdemServicoPreviaInnerView(OrdemServicoInternoRequiredMixin, View):
    def get(self, request, pk):
        from core.views_ordem_servico import carregar_ordem, contexto_ordem

        ordem = carregar_ordem(pk=pk)
        return render(
            request,
            "ordem_servico_publica.html",
            contexto_ordem(ordem, previsualizacao=True, request=request),
        )
