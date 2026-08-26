"""Painel interno (interno.lazersport.com).

O foco deste módulo é o estoque de materiais: o que existe, onde está
guardado, quanto foi pago e quem mexeu.
"""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Count, DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import View

from core.models import Manutencao, Pedido, Venda

from .models import (
    CentralPedidos,
    CentralVendas,
    EstoqueMaterial,
    Fornecedor,
    Gerente,
    Material,
    MovimentoEstoque,
    Orcamento,
    OrdemProducao,
    TipoMaterial,
)
from .context_processors import invalidar_avisos
from .permissoes import (
    CRIACAO,
    GESTAO,
    PRODUCAO,
    VENDAS,
    capacidades,
    faz_parte_da_equipe,
    tem_funcao,
)
from .utils import ErroDeFormulario, data, decimal_br, inteiro, pede_json, texto


ZERO = Value(Decimal("0.00"), output_field=DecimalField(max_digits=14, decimal_places=2))

# quantidade * preço pago: o total investido no que está guardado.
VALOR_EM_ESTOQUE = Coalesce(
    Sum(
        F("quantidade") * F("preco_fornecedor"),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    ),
    ZERO,
)


class InternoRequiredMixin(View):
    """Só entra pelo subdomínio interno e só com conta de equipe."""

    funcoes_necessarias = ()

    @staticmethod
    def destino_do_usuario(user):
        acesso = capacidades(user)
        if acesso["gestao"]:
            return "home_inner"
        if acesso["vendas"]:
            return "orcamentos_inner"
        if acesso["producao"]:
            return "minha_producao"
        if acesso["criacao"]:
            return "brinquedos_admin"
        return "login_inner"

    def dispatch(self, request, *args, **kwargs):
        # A flag vem do SubdomainURLMiddleware. Antes a checagem era
        # feita de novo aqui com startswith('interno.'), o que duplicava
        # a regra e deixava de fora qualquer host alternativo.
        if not getattr(request, "is_interno", False):
            return redirect("/")

        if not request.user.is_authenticated:
            return redirect("login_inner")

        if not faz_parte_da_equipe(request.user):
            return redirect("login_inner")

        if self.funcoes_necessarias and not tem_funcao(
            request.user, *self.funcoes_necessarias
        ):
            return redirect(self.destino_do_usuario(request.user))

        return super().dispatch(request, *args, **kwargs)


def eh_gestor_interno(user):
    """Compatibilidade dos templates antigos com a função Gestão."""
    return tem_funcao(user, GESTAO)


class GestorInternoRequiredMixin(InternoRequiredMixin):
    """Compatibilidade: telas comerciais aceitam Vendas ou Gestão."""

    funcoes_necessarias = (VENDAS, GESTAO)


class FinanceiroInternoRequiredMixin(InternoRequiredMixin):
    funcoes_necessarias = (GESTAO,)


class ProducaoInternoRequiredMixin(InternoRequiredMixin):
    funcoes_necessarias = (PRODUCAO,)


class EstoqueInternoRequiredMixin(InternoRequiredMixin):
    funcoes_necessarias = (PRODUCAO, GESTAO)


class OperacaoInternoRequiredMixin(InternoRequiredMixin):
    funcoes_necessarias = (PRODUCAO, VENDAS, GESTAO)


class CriacaoInternoRequiredMixin(InternoRequiredMixin):
    funcoes_necessarias = (CRIACAO,)


class SuperusuarioInternoRequiredMixin(InternoRequiredMixin):
    """Delegar acesso altera segurança da empresa: somente o super."""

    def dispatch(self, request, *args, **kwargs):
        if (
            getattr(request, "is_interno", False)
            and request.user.is_authenticated
            and faz_parte_da_equipe(request.user)
            and not request.user.is_superuser
        ):
            return redirect(self.destino_do_usuario(request.user))
        return super().dispatch(request, *args, **kwargs)



class RespostaJSONMixin:
    """Erro de validação volta pro modal em vez de recarregar a página."""

    rota_padrao = "stock"

    def erro(self, request, mensagem, /, status=400):
        # Ação declarada em ACOES_SEM_TRANSACAO não abriu transação, então
        # não tem nada para desfazer -- e marcar rollback aqui derrubaria
        # a transação de quem chamou (em teste, a do próprio TestCase),
        # impedindo qualquer consulta seguinte.
        if not getattr(self, "_acao_sem_transacao", False):
            transaction.set_rollback(True)

        if pede_json(request):
            return JsonResponse({"status": "erro", "msg": mensagem}, status=status)
        return redirect(self.rota_padrao)

    #: Chaves que a resposta usa para dizer se deu certo. Nenhum extra
    #: pode ocupá-las -- ver `sucesso`.
    CAMPOS_RESERVADOS = ("status", "msg")

    def sucesso(self, request, mensagem, /, **extras):
        """Resposta de sucesso, com os dados extras que a tela pediu.

        A BARRA NA ASSINATURA NÃO É ENFEITE. Sem ela, um extra chamado
        `mensagem` -- nome óbvio para "o texto que vai ao cliente" -- não
        cai em `**extras`: colide com este parâmetro e a ação estoura com
        TypeError. Posicional-só, qualquer nome de extra é aceito.

        OS EXTRAS NÃO PODEM SOBRESCREVER `status` E `msg`.

        Isto já custou caro uma vez: a ação de enviar orçamento passava
        `status=orcamento.status` como extra, o dicionário final saía com
        `"status": "rascunho"` no lugar de `"sucesso"`, e o JavaScript --
        que confere `json.status !== "sucesso"` -- tratava um envio bem
        sucedido como falha. O link da proposta nunca aparecia na tela e a
        mensagem de sucesso ia parar na tarja vermelha de erro.

        O acidente é silencioso porque o servidor responde 200 e o teste
        de servidor passa. Por isso a proteção mora aqui, e não na
        lembrança de quem escreve a próxima ação: extra com nome
        reservado é renomeado, e quem lê a resposta continua achando o
        valor -- só que em outra chave.
        """
        invalidar_avisos(getattr(request, "user", None))

        if not pede_json(request):
            return redirect(self.rota_padrao)

        corpo = {}
        for chave, valor in extras.items():
            if chave in self.CAMPOS_RESERVADOS:
                corpo[f"{chave}_do_registro"] = valor
            else:
                corpo[chave] = valor

        corpo["status"] = "sucesso"
        corpo["msg"] = mensagem

        return JsonResponse(corpo)

    def despachar_acao(self, request):
        acao = request.POST.get("action", "")
        metodo = getattr(self, f"acao_{acao}", None)

        if metodo is None:
            raise ErroDeFormulario("Ação inválida.")

        return metodo(request)

    #: Ações que NÃO rodam dentro de uma transação.
    #
    # Quase tudo aqui salva um cadastro inteiro e precisa de tudo-ou-nada.
    # Envio de proposta é outra coisa: ele registra a TENTATIVA, e a
    # tentativa que interessa guardar é justamente a que falhou. Dentro da
    # transação, o rollback do erro apagava o registro junto -- e o
    # histórico ficava sem a única linha que explicava o problema.
    ACOES_SEM_TRANSACAO = ()

    def post(self, request, *args, **kwargs):
        acao = request.POST.get("action", "")
        self._acao_sem_transacao = acao in self.ACOES_SEM_TRANSACAO

        if self._acao_sem_transacao:
            return self._executar(request)

        with transaction.atomic():
            return self._executar(request)

    def _executar(self, request):
        try:
            return self.despachar_acao(request)
        except ErroDeFormulario as exc:
            return self.erro(request, str(exc))
        except ValueError as exc:
            return self.erro(request, str(exc))
        except IntegrityError:
            return self.erro(
                request,
                "Já existe um registro com esses dados. "
                "Confira o nome e o local antes de salvar.",
            )


# ======================================================================
# ACESSO
# ======================================================================
class LoginInternoView(View):
    template_name = "login_inner.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("home_inner")
        return render(request, self.template_name)

    def post(self, request):
        user = authenticate(
            request,
            username=request.POST.get("login"),
            password=request.POST.get("password"),
        )

        if not user:
            return render(request, self.template_name, {
                "error": "Usuário ou senha inválidos.",
            })

        if not faz_parte_da_equipe(user):
            return render(request, self.template_name, {
                "error": "Usuário sem permissão para acesso interno.",
            })

        login(request, user)
        return redirect(InternoRequiredMixin.destino_do_usuario(user))


class LogoutInnerView(View):
    def post(self, request):
        logout(request)
        return render(request, "logout_inner.html")


class MinhaContaView(InternoRequiredMixin, View):
    """Dados da própria pessoa; separado do admin e acessível no tablet."""

    template_name = "minha_conta.html"

    def get(self, request):
        from core.email_utils import remetente, responder_para, smtp_configurado

        return render(request, self.template_name, {
            # Quem envia proposta precisa saber, sem abrir documentação,
            # se o e-mail sai deste servidor -- e para onde volta a
            # resposta do cliente.
            "email_configurado": smtp_configurado(),
            "email_remetente": remetente(),
            "email_resposta": responder_para(request.user),
        })

    def post(self, request):
        if request.POST.get("action") == "testar_email":
            return self._testar_email(request)

        user = request.user
        primeiro_nome = (request.POST.get("first_name") or "").strip()[:150]
        sobrenome = (request.POST.get("last_name") or "").strip()[:150]
        email = (request.POST.get("email") or "").strip().lower()

        if not primeiro_nome:
            messages.error(request, "Informe seu nome.")
            return render(request, self.template_name, status=400)
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Informe um e-mail válido.")
            return render(request, self.template_name, status=400)
        if User.objects.exclude(pk=user.pk).filter(email__iexact=email).exists():
            messages.error(request, "Este e-mail já está sendo usado por outra conta.")
            return render(request, self.template_name, status=400)

        user.first_name = primeiro_nome
        user.last_name = sobrenome
        user.email = email
        user.save(update_fields=["first_name", "last_name", "email"])

        try:
            gerente = user.gerente
        except (AttributeError, Gerente.DoesNotExist):
            gerente = None
        if gerente:
            gerente.nome = user.get_full_name()
            gerente.telefone = (request.POST.get("telefone") or "").strip()[:20]
            gerente.save(update_fields=["nome", "telefone", "atualizado"])

        senha_atual = request.POST.get("senha_atual") or ""
        senha_nova = request.POST.get("senha_nova") or ""
        senha_confirmacao = request.POST.get("senha_confirmacao") or ""
        if senha_atual or senha_nova or senha_confirmacao:
            if not user.check_password(senha_atual):
                messages.error(request, "A senha atual está incorreta; os demais dados foram salvos.")
                return redirect("minha_conta_inner")
            if len(senha_nova) < 8:
                messages.error(request, "A nova senha precisa ter pelo menos 8 caracteres.")
                return redirect("minha_conta_inner")
            if senha_nova != senha_confirmacao:
                messages.error(request, "A confirmação da nova senha não confere.")
                return redirect("minha_conta_inner")
            user.set_password(senha_nova)
            user.save(update_fields=["password"])
            update_session_auth_hash(request, user)
            messages.success(request, "Conta e senha atualizadas.")
        else:
            messages.success(request, "Seus dados foram atualizados.")

        return redirect("minha_conta_inner")

    def _testar_email(self, request):
        """Manda um e-mail de teste para o próprio usuário.

        POR QUE ISTO EXISTE. "Enviei a proposta e o cliente não recebeu"
        era um beco sem saída: ninguém tinha como saber se o problema era
        o endereço do cliente, a caixa dele ou o servidor de e-mail. Um
        teste para a própria conta separa as três coisas em dez segundos,
        e o erro do provedor aparece na tela em vez de ficar no log.
        """
        from django.core.mail import EmailMultiAlternatives

        from core.email_utils import remetente, responder_para, smtp_configurado

        destino = (request.user.email or "").strip()
        if not destino:
            messages.error(
                request,
                "Cadastre seu e-mail acima antes de testar o envio.",
            )
            return redirect("minha_conta_inner")

        if not smtp_configurado():
            messages.error(
                request,
                "O servidor de e-mail ainda não está configurado nesta "
                "hospedagem: faltam EMAIL_HOST_USER e EMAIL_HOST_PASSWORD. "
                "O passo a passo está em docs/CONFIGURAR_EMAIL.md.",
            )
            return redirect("minha_conta_inner")

        mensagem = EmailMultiAlternatives(
            subject="Teste de envio — Lazer & Sport",
            body=(
                "Se você está lendo isto, o envio de e-mail do sistema está "
                "funcionando: as propostas saem por aqui.\n\n"
                "Responda esta mensagem para conferir também o endereço de "
                "resposta."
            ),
            from_email=remetente(),
            to=[destino],
            reply_to=responder_para(request.user),
        )

        try:
            enviados = mensagem.send(fail_silently=False)
        except Exception as erro:
            messages.error(
                request,
                f"O servidor de e-mail recusou o envio: {type(erro).__name__}: "
                f"{erro}",
            )
            return redirect("minha_conta_inner")

        if enviados != 1:
            messages.error(
                request,
                "O servidor aceitou a conexão mas não confirmou o envio.",
            )
            return redirect("minha_conta_inner")

        messages.success(
            request,
            f"E-mail de teste enviado para {destino}. Se não chegar em "
            "alguns minutos, confira a caixa de spam.",
        )
        return redirect("minha_conta_inner")


# ======================================================================
# HOME
# ======================================================================
class HomeInnerView(InternoRequiredMixin, View):
    def get(self, request):
        if not tem_funcao(request.user, GESTAO):
            return redirect(self.destino_do_usuario(request.user))

        hoje = timezone.localdate()
        estoques = EstoqueMaterial.objects.select_related("material")

        resumo = estoques.aggregate(
            locais=Count("id"),
            pecas=Coalesce(Sum("quantidade"), 0),
            investido=VALOR_EM_ESTOQUE,
        )

        criticos = EstoqueMaterial.objects.criticos().select_related("material")

        orcamentos_base = (
            Orcamento.objects.filter(status__in=Orcamento.EM_ABERTO)
            .order_by("validade", "-criacao")
        )
        # Antes a home carregava TODOS os itens de TODOS os orçamentos em
        # aberto apenas para descobrir quais venciam em três dias. Agora o
        # banco filtra validade; só as cinco propostas desenhadas trazem itens.
        orcamentos_abertos = list(
            orcamentos_base.select_related("cliente").prefetch_related("itens")[:5]
        )
        orcamentos_vencendo = list(
            orcamentos_base
            .filter(validade__lte=hoje + timezone.timedelta(days=3))
            .select_related("cliente")[:20]
        )
        total_orcamentos_abertos = orcamentos_base.count()
        total_orcamentos_vencendo = (
            orcamentos_base
            .filter(validade__lte=hoje + timezone.timedelta(days=3))
            .count()
        )
        pedidos_abertos = (
            Pedido.objects.exclude(status__in=["finalizado", "cancelado"])
            .select_related("cliente").order_by("-criacao")
        )
        manutencoes_abertas = (
            Manutencao.objects.filter(status__in=["P", "A"])
            .select_related("brinquedo", "usuario__user").order_by("criado_em")
        )
        producao_aberta = (
            OrdemProducao.objects.exclude(status__in=[
                OrdemProducao.Status.CONCLUIDA, OrdemProducao.Status.CANCELADA,
            ])
            .select_related("produto", "colaborador")
            .prefetch_related("etapas_execucao")
            .order_by("prevista_para", "criacao")
        )

        fila_trabalho = []
        for orcamento in orcamentos_vencendo[:3]:
            dias = orcamento.dias_para_vencer
            fila_trabalho.append({
                "nivel": "critico" if dias < 0 else "atencao",
                "icone": "bi-file-earmark-text",
                "titulo": f"Orçamento #{orcamento.pk} · {orcamento.destinatario}",
                "detalhe": (
                    f"Vencido há {abs(dias)} dia(s). Renove ou fale com o cliente."
                    if dias < 0 else
                    ("Vence hoje. Faça o retorno ao cliente." if dias == 0 else
                     f"Vence em {dias} dia(s). Ainda dá tempo de acompanhar.")
                ),
                "url": f"{reverse('orcamentos_inner', urlconf='sistema_interno.urls')}?q={orcamento.pk}",
                "acao": "Abrir proposta",
            })
        for manutencao in manutencoes_abertas[:3]:
            fila_trabalho.append({
                "nivel": "atencao" if manutencao.status == "P" else "info",
                "icone": "bi-wrench-adjustable",
                "titulo": manutencao.nome_equipamento,
                "detalhe": "Novo chamado esperando triagem." if manutencao.status == "P" else "Serviço em andamento.",
                "url": reverse("manutencao_inner", urlconf="sistema_interno.urls"),
                "acao": "Ver manutenção",
            })
        for ordem in producao_aberta.filter(
            status__in=[OrdemProducao.Status.BLOQUEADA, OrdemProducao.Status.PAUSADA]
        )[:3]:
            fila_trabalho.append({
                "nivel": "critico" if ordem.status == OrdemProducao.Status.BLOQUEADA else "atencao",
                "icone": "bi-hammer",
                "titulo": f"Produção #{ordem.pk} · {ordem.produto}",
                "detalhe": f"{ordem.get_status_display()}. A equipe precisa de uma decisão.",
                "url": reverse("producao_ordem_detalhe", kwargs={"pk": ordem.pk}, urlconf="sistema_interno.urls"),
                "acao": "Resolver etapa",
            })
        fila_trabalho.sort(key=lambda item: {"critico": 0, "atencao": 1, "info": 2}[item["nivel"]])

        ctx = {
            "hoje": hoje,
            "materiais": Material.objects.filter(ativo=True),
            "total_materiais": Material.objects.filter(ativo=True).count(),
            "total_locais": resumo["locais"],
            "total_pecas": resumo["pecas"],
            "valor_investido": resumo["investido"],
            "criticos": criticos[:8],
            "total_criticos": criticos.count(),
            "ultimos_movimentos": (
                MovimentoEstoque.objects
                .select_related("estoque__material", "responsavel")[:8]
            ),
            "fila_trabalho": fila_trabalho[:7],
            "orcamentos_abertos": orcamentos_abertos,
            "total_orcamentos_abertos": total_orcamentos_abertos,
            "total_orcamentos_vencendo": total_orcamentos_vencendo,
            "pedidos_abertos": pedidos_abertos[:5],
            "total_pedidos_abertos": pedidos_abertos.count(),
            "manutencoes_abertas": manutencoes_abertas[:5],
            "total_manutencoes_abertas": manutencoes_abertas.count(),
            "producao_aberta": producao_aberta[:5],
            "total_producao_aberta": producao_aberta.count(),
            "vendas_a_confirmar": Venda.objects.filter(confirmado=False).count(),
        }
        return render(request, "home_inner.html", ctx)


# ======================================================================
# ESTOQUE DE MATERIAIS
# ======================================================================
class EstoqueInnerView(RespostaJSONMixin, EstoqueInternoRequiredMixin, View):
    rota_padrao = "stock"

    def get(self, request):
        busca = (request.GET.get("q") or "").strip()
        tipo = (request.GET.get("tipo") or "").strip()
        fornecedor = (request.GET.get("fornecedor") or "").strip()
        situacao = (request.GET.get("situacao") or "").strip()

        estoques = (
            EstoqueMaterial.objects
            .select_related("material", "material__tipo_material", "fornecedor")
        )

        if busca:
            estoques = estoques.filter(
                Q(material__nome_material__icontains=busca)
                | Q(material__codigo_interno__icontains=busca)
                | Q(descricao_local__icontains=busca)
                | Q(nota_fiscal__icontains=busca)
                | Q(fornecedor__nome__icontains=busca)
            )

        if tipo.isdigit():
            estoques = estoques.filter(material__tipo_material_id=tipo)

        if fornecedor.isdigit():
            estoques = estoques.filter(fornecedor_id=fornecedor)

        estoques = list(estoques)

        # situação depende de estoque_minimo, então é filtrada em Python:
        # traduzir a regra para SQL só para repetir a lógica duas vezes
        # sairia mais caro do que percorrer a lista de locais de guarda.
        if situacao in (EstoqueMaterial.CRITICO, EstoqueMaterial.ATENCAO, EstoqueMaterial.ESTAVEL):
            estoques = [e for e in estoques if e.situacao == situacao]

        investido = sum((e.valor_total for e in estoques), Decimal("0.00"))
        criticos = [e for e in estoques if e.situacao == EstoqueMaterial.CRITICO]

        ctx = {
            "estoques": estoques,
            "materiais": Material.objects.filter(ativo=True),
            "tipos": TipoMaterial.objects.all().order_by("descricao"),
            "fornecedores": Fornecedor.objects.filter(ativo=True),
            "busca": busca,
            "tipo_ativo": tipo,
            "fornecedor_ativo": fornecedor,
            "situacao_ativa": situacao,
            "total_locais": len(estoques),
            "total_pecas": sum(e.quantidade for e in estoques),
            "valor_investido": investido,
            "total_criticos": len(criticos),
            "estoques_dados": [self.serializar(e) for e in estoques],
            "tipos_movimento": MovimentoEstoque.Tipo.choices,
            "hoje": timezone.localdate(),
        }
        return render(request, "estoque_inner.html", ctx)

    @staticmethod
    def serializar(estoque):
        return {
            "id": estoque.id,
            "material_id": estoque.material_id,
            "material": estoque.material.nome_material,
            "descricao_local": estoque.descricao_local,
            "quantidade": estoque.quantidade,
            "preco_fornecedor": f"{estoque.preco_fornecedor:.2f}".replace(".", ","),
            "fornecedor_id": estoque.fornecedor_id or "",
            "estoque_minimo": estoque.estoque_minimo,
            "nota_fiscal": estoque.nota_fiscal,
            "comprado_em": estoque.comprado_em.isoformat() if estoque.comprado_em else "",
            "observacoes": estoque.observacoes,
        }

    # ---------------- ações ----------------
    def acao_save(self, request):
        estoque_id = request.POST.get("id")
        estoque = (
            get_object_or_404(EstoqueMaterial, pk=estoque_id)
            if estoque_id else EstoqueMaterial()
        )

        material_id = texto(request, "material", obrigatorio=True, rotulo="o material")
        estoque.material = get_object_or_404(Material, pk=material_id)
        estoque.descricao_local = texto(
            request, "descricao_local",
            obrigatorio=True, rotulo="o local de guarda", limite=90,
        )
        estoque.preco_fornecedor = decimal_br(
            request.POST.get("preco_fornecedor"),
            "Valor pago por unidade",
            obrigatorio=True,
            limite=Decimal("9999999999.99"),
        )
        estoque.estoque_minimo = inteiro(
            request.POST.get("estoque_minimo"), "Quantidade mínima",
        ) or 0
        estoque.nota_fiscal = texto(request, "nota_fiscal", limite=60)
        estoque.comprado_em = data(request.POST.get("comprado_em"), "Data da compra")
        estoque.observacoes = texto(request, "observacoes")

        fornecedor_id = (request.POST.get("fornecedor") or "").strip()
        estoque.fornecedor = (
            get_object_or_404(Fornecedor, pk=fornecedor_id)
            if fornecedor_id.isdigit() else None
        )

        # A quantidade inicial só é aceita no cadastro. Depois disso ela
        # muda por movimento, para o histórico não ficar com buraco.
        if not estoque.pk:
            estoque.quantidade = inteiro(
                request.POST.get("quantidade"), "Quantidade", minimo=0,
            ) or 0

        estoque.save()

        if not estoque_id and estoque.quantidade:
            MovimentoEstoque.objects.create(
                estoque=estoque,
                tipo=MovimentoEstoque.Tipo.ENTRADA,
                quantidade=estoque.quantidade,
                quantidade_resultante=estoque.quantidade,
                valor_unitario=estoque.preco_fornecedor,
                documento=estoque.nota_fiscal,
                motivo="Cadastro inicial do item",
                responsavel=request.user,
            )

        return self.sucesso(
            request,
            f"{estoque.material} salvo em {estoque.descricao_local}.",
            id=estoque.pk,
        )

    def acao_movimento(self, request):
        estoque = get_object_or_404(
            EstoqueMaterial, pk=request.POST.get("id"),
        )
        tipo = (request.POST.get("tipo") or "").strip()

        if tipo not in MovimentoEstoque.Tipo.values:
            raise ErroDeFormulario("Escolha entrada, saída ou ajuste.")

        quantidade = inteiro(
            request.POST.get("quantidade"),
            "Quantidade",
            obrigatorio=True,
            minimo=0 if tipo == MovimentoEstoque.Tipo.AJUSTE else 1,
        )

        valor = decimal_br(
            request.POST.get("valor_unitario"),
            "Valor pago por unidade",
            limite=Decimal("9999999999.99"),
        )

        if tipo == MovimentoEstoque.Tipo.AJUSTE and quantidade == 0:
            # registrar() recusa zero; o ajuste para zero é legítimo.
            movimento = MovimentoEstoque.objects.create(
                estoque=estoque, tipo=tipo, quantidade=0,
                quantidade_resultante=0, valor_unitario=valor,
                documento=texto(request, "documento", limite=60),
                motivo=texto(request, "motivo", limite=150),
                responsavel=request.user,
            )
            EstoqueMaterial.objects.filter(pk=estoque.pk).update(quantidade=0)
        else:
            movimento = MovimentoEstoque.registrar(
                estoque,
                tipo,
                quantidade,
                valor_unitario=valor,
                documento=texto(request, "documento", limite=60),
                motivo=texto(request, "motivo", limite=150),
                responsavel=request.user,
            )

        return self.sucesso(
            request,
            (
                f"{movimento.get_tipo_display()} registrada. "
                f"Saldo agora: {movimento.quantidade_resultante}."
            ),
            saldo=movimento.quantidade_resultante,
        )

    def acao_delete(self, request):
        estoque = get_object_or_404(EstoqueMaterial, pk=request.POST.get("id"))
        nome = str(estoque)
        estoque.delete()
        return self.sucesso(request, f"{nome} removido do estoque.")


# ======================================================================
# MATERIAIS, TIPOS E FORNECEDORES
# ======================================================================
class MateriaisInnerView(RespostaJSONMixin, EstoqueInternoRequiredMixin, View):
    rota_padrao = "materiais_inner"

    def get(self, request):
        busca = (request.GET.get("q") or "").strip()

        materiais = (
            Material.objects
            .select_related("tipo_material")
            .prefetch_related("estoque", "brinquedos_associados")
        )

        if busca:
            materiais = materiais.filter(
                Q(nome_material__icontains=busca)
                | Q(codigo_interno__icontains=busca)
                | Q(descricao__icontains=busca)
            )

        materiais = list(materiais)

        ctx = {
            "materiais": materiais,
            "tipos": TipoMaterial.objects.all().order_by("descricao"),
            "fornecedores": Fornecedor.objects.all(),
            "busca": busca,
            "unidades": Material.Unidade.choices,
            "total_materiais": len(materiais),
            "total_tipos": TipoMaterial.objects.count(),
            "total_fornecedores": Fornecedor.objects.filter(ativo=True).count(),
            "materiais_dados": [
                {
                    "id": m.id,
                    "nome_material": m.nome_material,
                    "descricao": m.descricao or "",
                    "codigo_interno": m.codigo_interno,
                    "unidade": m.unidade,
                    "tipo_material": m.tipo_material_id or "",
                    "ativo": m.ativo,
                }
                for m in materiais
            ],
            "tipos_dados": [
                {"id": t.id, "descricao": t.descricao}
                for t in TipoMaterial.objects.all().order_by("descricao")
            ],
            "fornecedores_dados": [
                {
                    "id": f.id,
                    "nome": f.nome,
                    "telefone": f.telefone,
                    "email": f.email,
                    "cnpj": f.cnpj,
                    "site": f.site,
                    "observacoes": f.observacoes,
                    "ativo": f.ativo,
                }
                for f in Fornecedor.objects.all()
            ],
        }
        return render(request, "material_inner.html", ctx)

    def acao_save_material(self, request):
        material_id = request.POST.get("id")
        material = (
            get_object_or_404(Material, pk=material_id)
            if material_id else Material()
        )

        material.nome_material = texto(
            request, "nome_material",
            obrigatorio=True, rotulo="o nome do material", limite=90,
        )
        material.descricao = texto(request, "descricao", limite=150)
        material.codigo_interno = texto(request, "codigo_interno", limite=30)
        material.unidade = (
            request.POST.get("unidade") or Material.Unidade.UNIDADE
        )

        if material.unidade not in Material.Unidade.values:
            raise ErroDeFormulario("Escolha uma unidade de medida válida.")

        tipo_id = (request.POST.get("tipo_material") or "").strip()
        material.tipo_material = (
            get_object_or_404(TipoMaterial, pk=tipo_id)
            if tipo_id.isdigit() else None
        )
        material.ativo = request.POST.get("ativo") == "on"
        material.save()

        return self.sucesso(
            request,
            f"Material '{material.nome_material}' salvo.",
            id=material.pk,
        )

    def acao_delete_material(self, request):
        material = get_object_or_404(Material, pk=request.POST.get("id"))

        if material.estoque.exists():
            raise ErroDeFormulario(
                "Este material ainda tem saldo em estoque. "
                "Zere os locais de guarda ou desative o material."
            )

        nome = material.nome_material
        material.delete()
        return self.sucesso(request, f"Material '{nome}' excluído.")

    def acao_save_tipo(self, request):
        tipo_id = request.POST.get("id")
        tipo = (
            get_object_or_404(TipoMaterial, pk=tipo_id)
            if tipo_id else TipoMaterial()
        )
        tipo.descricao = texto(
            request, "descricao",
            obrigatorio=True, rotulo="o nome do tipo", limite=120,
        )
        tipo.save()
        return self.sucesso(
            request, f"Tipo '{tipo.descricao}' salvo.",
            id=tipo.pk, nome=tipo.descricao,
        )

    def acao_save_fornecedor(self, request):
        fornecedor_id = request.POST.get("id")
        fornecedor = (
            get_object_or_404(Fornecedor, pk=fornecedor_id)
            if fornecedor_id else Fornecedor()
        )
        fornecedor.nome = texto(
            request, "nome",
            obrigatorio=True, rotulo="o nome do fornecedor", limite=120,
        )
        fornecedor.telefone = texto(request, "telefone", limite=20)
        fornecedor.email = texto(request, "email", limite=150)
        fornecedor.cnpj = texto(request, "cnpj", limite=20)
        fornecedor.site = texto(request, "site", limite=200)
        fornecedor.observacoes = texto(request, "observacoes")
        fornecedor.ativo = request.POST.get("ativo") == "on"
        fornecedor.save()

        return self.sucesso(
            request, f"Fornecedor '{fornecedor.nome}' salvo.",
            id=fornecedor.pk, nome=fornecedor.nome,
        )

    def acao_delete_fornecedor(self, request):
        fornecedor = get_object_or_404(Fornecedor, pk=request.POST.get("id"))
        nome = fornecedor.nome
        fornecedor.delete()
        return self.sucesso(request, f"Fornecedor '{nome}' excluído.")


# ======================================================================
# MOVIMENTAÇÕES
# ======================================================================
class MovimentacoesInnerView(EstoqueInternoRequiredMixin, View):
    def get(self, request):
        tipo = (request.GET.get("tipo") or "").strip()
        busca = (request.GET.get("q") or "").strip()

        # Data digitada torta vira filtro vazio, não erro 500.
        try:
            desde = data(request.GET.get("desde"), "Data inicial")
            ate = data(request.GET.get("ate"), "Data final")
        except ErroDeFormulario:
            desde = ate = None

        movimentos = (
            MovimentoEstoque.objects
            .select_related("estoque__material", "estoque__fornecedor", "responsavel")
        )

        if tipo in MovimentoEstoque.Tipo.values:
            movimentos = movimentos.filter(tipo=tipo)

        if busca:
            movimentos = movimentos.filter(
                Q(estoque__material__nome_material__icontains=busca)
                | Q(estoque__descricao_local__icontains=busca)
                | Q(documento__icontains=busca)
                | Q(motivo__icontains=busca)
            )

        if desde:
            movimentos = movimentos.filter(ocorrido_em__date__gte=desde)
        if ate:
            movimentos = movimentos.filter(ocorrido_em__date__lte=ate)

        movimentos = list(movimentos[:400])

        entradas = [m for m in movimentos if m.tipo == MovimentoEstoque.Tipo.ENTRADA]
        saidas = [m for m in movimentos if m.tipo == MovimentoEstoque.Tipo.SAIDA]

        ctx = {
            "movimentos": movimentos,
            "tipos": MovimentoEstoque.Tipo.choices,
            "tipo_ativo": tipo,
            "busca": busca,
            "desde": desde.isoformat() if desde else "",
            "ate": ate.isoformat() if ate else "",
            "total_movimentos": len(movimentos),
            "total_entradas": len(entradas),
            "total_saidas": len(saidas),
            "valor_comprado": sum(
                (m.valor_total or Decimal("0.00") for m in entradas),
                Decimal("0.00"),
            ),
        }
        return render(request, "saidas_estoque.html", ctx)


# ======================================================================
# DASHBOARD DO ESTOQUE
# ======================================================================
class DashboardEstoqueView(EstoqueInternoRequiredMixin, View):
    def get(self, request):
        estoques = list(
            EstoqueMaterial.objects
            .select_related("material", "material__tipo_material", "fornecedor")
        )

        investido = sum((e.valor_total for e in estoques), Decimal("0.00"))

        por_tipo = {}
        for item in estoques:
            chave = (
                item.material.tipo_material.descricao
                if item.material.tipo_material else "Sem tipo"
            )
            atual = por_tipo.setdefault(
                chave, {"nome": chave, "valor": Decimal("0.00"), "pecas": 0},
            )
            atual["valor"] += item.valor_total
            atual["pecas"] += item.quantidade

        for linha in por_tipo.values():
            # String com ponto: vai direto pro width do CSS, e em pt-BR
            # o template localizaria o float para "12,5" -- que a regra
            # de estilo descarta.
            fatia = float(linha["valor"] / investido * 100) if investido else 0.0
            linha["percentual"] = f"{fatia:.1f}"

        por_fornecedor = (
            EstoqueMaterial.objects
            .values("fornecedor__nome")
            .annotate(valor=VALOR_EM_ESTOQUE, itens=Count("id"))
            .order_by("-valor")[:8]
        )

        limite = timezone.now() - timezone.timedelta(days=30)

        ctx = {
            "total_locais": len(estoques),
            "total_pecas": sum(e.quantidade for e in estoques),
            "valor_investido": investido,
            "criticos": [
                e for e in estoques if e.situacao == EstoqueMaterial.CRITICO
            ],
            "mais_valiosos": sorted(
                estoques, key=lambda e: e.valor_total, reverse=True,
            )[:10],
            "por_tipo": sorted(
                por_tipo.values(), key=lambda x: x["valor"], reverse=True,
            ),
            "por_fornecedor": por_fornecedor,
            "movimentos_mes": (
                MovimentoEstoque.objects
                .filter(ocorrido_em__gte=limite)
                .select_related("estoque__material", "responsavel")[:12]
            ),
            "comprado_no_mes": sum(
                (
                    m.valor_total or Decimal("0.00")
                    for m in MovimentoEstoque.objects.filter(
                        ocorrido_em__gte=limite,
                        tipo=MovimentoEstoque.Tipo.ENTRADA,
                    )
                ),
                Decimal("0.00"),
            ),
        }
        return render(request, "dashboard_estoque.html", ctx)


# ======================================================================
# TELAS EXISTENTES
# ======================================================================
class VendasView(OperacaoInternoRequiredMixin, View):
    def get(self, request):
        return render(request, "vendas_inner.html", {
            "vendas": CentralVendas.objects.all(),
        })


class PedidosView(OperacaoInternoRequiredMixin, View):
    def get(self, request):
        return render(request, "pedidos_inner.html", {
            "pedidos": CentralPedidos.objects.all(),
        })


class ManutencaoInnerView(OperacaoInternoRequiredMixin, View):
    def get(self, request):
        return render(request, "manutencao_inner.html", {
            "manutencoes": Manutencao.objects.all(),
        })
