"""Funções combináveis da equipe e capacidades do painel interno.

Não existem subclasses de usuário. Cada integrante continua sendo um
``auth.User`` normal e recebe uma ou mais funções por meio dos ``Group`` do
Django. Isso permite, por exemplo, que a mesma pessoa seja Vendas e Gestão
sem duplicar conta ou criar uma hierarquia rígida.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.models import Group


PRODUCAO = "Equipe · Produção"
CRIACAO = "Equipe · Criação do site"
VENDAS = "Equipe · Vendas"
AMBULANTE = "Equipe · Vendedor ambulante"
FINANCEIRO = "Equipe · Financeiro"
GESTAO = "Equipe · Gestão"


@dataclass(frozen=True)
class Funcao:
    codigo: str
    grupo: str
    titulo: str
    descricao: str
    icone: str


FUNCOES = (
    Funcao(
        "producao",
        PRODUCAO,
        "Engenharia de produção",
        "Estoque, materiais, fichas técnicas, etapas e ordens de produção.",
        "bi-hammer",
    ),
    Funcao(
        "criacao",
        CRIACAO,
        "Criação e site",
        "Catálogo, imagens, banners, projetos, eventos, promoções e vitrine.",
        "bi-palette2",
    ),
    Funcao(
        "vendas",
        VENDAS,
        "Vendas",
        "Clientes, propostas e acompanhamento do bloco comercial dos orçamentos.",
        "bi-file-earmark-text",
    ),
    Funcao(
        "ambulante",
        AMBULANTE,
        "Vendedor ambulante",
        "Visitas externas, clientes compartilhados e os próprios orçamentos.",
        "bi-geo-alt-fill",
    ),
    Funcao(
        "financeiro",
        FINANCEIRO,
        "Financeiro",
        "Vendas, pedidos, recebimentos, despesas e indicadores financeiros.",
        "bi-cash-stack",
    ),
    Funcao(
        "gestao",
        GESTAO,
        "Gestão",
        "Supervisão de indicadores, clientes, orçamentos e de todas as áreas.",
        "bi-graph-up-arrow",
    ),
)

FUNCOES_POR_CODIGO = {funcao.codigo: funcao for funcao in FUNCOES}
NOMES_DOS_GRUPOS = tuple(funcao.grupo for funcao in FUNCOES)


def grupos_de_funcoes():
    """Garante e devolve os grupos, sem depender de cadastro manual.

    Os seis numa consulta; só o que faltar é criado. Eram seis
    `get_or_create` seguidos -- seis viagens ao Supabase (~1 s, LEIA-ME-V10
    §120) em cada "Salvar" da tela de acessos, para grupos que existem
    desde o primeiro dia.
    """
    existentes = {
        grupo.name: grupo
        for grupo in Group.objects.filter(name__in=NOMES_DOS_GRUPOS)
    }
    for nome in NOMES_DOS_GRUPOS:
        if nome not in existentes:
            existentes[nome] = Group.objects.get_or_create(name=nome)[0]
    return {nome: existentes[nome] for nome in NOMES_DOS_GRUPOS}


# ----------------------------------------------------------------------
# AS FUNÇÕES DE CADA CONTA, GUARDADAS ENTRE UMA REQUISIÇÃO E OUTRA
# (LEIA-ME-V10, seção 120)
#
# Toda requisição de quem não é superusuário perguntava ao banco "de que
# grupos esta conta é?" -- uma viagem ao Supabase (~170 ms) em cada tela,
# cada gravação e cada pulso do sino, para uma resposta que muda uma vez
# por mês. Agora a resposta fica no cache, com uma VERSÃO na chave: QUALQUER
# mudança de grupo (a tela de acessos, o /system/, um grupo renomeado ou
# apagado -- os sinais em `ligar_ouvintes`) troca a versão, e a próxima
# requisição de todo mundo pergunta de novo. A REGRA não muda: o que se
# guarda é o mesmo conjunto de nomes que a consulta devolveria.
#
# SÓ ONDE O CACHE É UM SÓ. Com o cache na memória do processo
# (`LocMemCache`) e mais de um worker, a troca de versão feita num worker
# não chegaria ao outro, e uma função retirada continuaria valendo lá até o
# prazo. Nesse caso nada é guardado (`_cache_das_funcoes` devolve um cache
# que não guarda nada) -- o comportamento de antes. Com um worker (o do
# Render hoje) ou com Redis, guarda.
# ----------------------------------------------------------------------
CHAVE_VERSAO_DAS_FUNCOES = "interno:funcoes:versao"
PRAZO_DAS_FUNCOES = 300


class _SemCache:
    def get(self, chave, padrao=None):
        return padrao

    def set(self, *args, **kwargs):
        return None


def _cache_das_funcoes():
    import os

    from django.conf import settings
    from django.core.cache import cache

    backend = str(settings.CACHES.get("default", {}).get("BACKEND", ""))
    try:
        workers = int(os.getenv("WEB_WORKERS", "1") or 1)
    except ValueError:
        workers = 2
    if backend.endswith("LocMemCache") and workers > 1:
        return _SemCache()
    return cache


def _versao_das_funcoes():
    versao = _cache_das_funcoes().get(CHAVE_VERSAO_DAS_FUNCOES)
    if versao is None:
        _trocar_versao_das_funcoes()
        versao = _cache_das_funcoes().get(CHAVE_VERSAO_DAS_FUNCOES) or 0
    return versao


def _trocar_versao_das_funcoes():
    import time

    try:
        _cache_das_funcoes().set(CHAVE_VERSAO_DAS_FUNCOES, time.time_ns(), None)
    except Exception:  # noqa: BLE001 -- sem cache, cada requisição pergunta ao banco
        pass


def esquecer_funcoes(**kwargs):
    """Algum grupo mudou: as funções guardadas de TODAS as contas perdem a validade.

    NA HORA E DEPOIS DO COMMIT, como o cache do catálogo (core/signals.py):
    uma requisição de outra thread pode ler a função antiga entre a troca e
    o commit e guardá-la com a versão nova; a segunda troca apaga essa cópia.
    """
    from django.db import transaction

    _trocar_versao_das_funcoes()
    try:
        transaction.on_commit(_trocar_versao_das_funcoes)
    except Exception:  # noqa: BLE001
        pass


def _chave_das_funcoes(user):
    """A conta, o instante em que ela nasceu (um id reaproveitado não herda) e a versão."""
    if not getattr(user, "pk", None):
        return ""
    criada = getattr(user, "date_joined", None)
    try:
        nascimento = int(criada.timestamp() * 1_000_000) if criada else 0
        return f"interno:funcoes:v1:{user.pk}:{nascimento}:{_versao_das_funcoes()}"
    except Exception:  # noqa: BLE001 -- sem cache, pergunta ao banco
        return ""


def ligar_ouvintes():
    """Qualquer mudança de grupo troca a versão (chamado uma vez, de core/signals.py)."""
    from django.contrib.auth import get_user_model
    from django.db.models.signals import m2m_changed, post_delete, post_save

    # `m2m_changed` cobre add/remove/clear/set por qualquer caminho (a tela
    # de acessos, o /system/, os dois lados da relação). Nada é ligado ao
    # post_save/post_delete da tabela de ligação: isso tiraria do Django a
    # exclusão rápida dela, e uma viagem a mais em cada "Salvar" de acesso.
    Usuario = get_user_model()
    m2m_changed.connect(esquecer_funcoes, sender=Usuario.groups.through, dispatch_uid="interno.funcoes.m2m")
    post_save.connect(esquecer_funcoes, sender=Group, dispatch_uid="interno.funcoes.save.Group")
    post_delete.connect(esquecer_funcoes, sender=Group, dispatch_uid="interno.funcoes.delete.Group")


def nomes_das_funcoes(user) -> set[str]:
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return set()
    if user.is_superuser:
        return set(NOMES_DOS_GRUPOS)

    memorizadas = getattr(user, "_funcoes_interno_cache", None)
    if memorizadas is not None:
        return set(memorizadas)

    grupos_prefetched = getattr(user, "_prefetched_objects_cache", {}).get("groups")
    if grupos_prefetched is not None:
        nomes = {
            grupo.name for grupo in grupos_prefetched
            if grupo.name in NOMES_DOS_GRUPOS
        }
    else:
        chave = _chave_das_funcoes(user)
        guardadas = _cache_das_funcoes().get(chave) if chave else None
        if guardadas is not None:
            nomes = set(guardadas)
        else:
            nomes = set(
                user.groups.filter(name__in=NOMES_DOS_GRUPOS)
                .values_list("name", flat=True)
            )
            if chave:
                _cache_das_funcoes().set(chave, frozenset(nomes), PRAZO_DAS_FUNCOES)

    user._funcoes_interno_cache = frozenset(nomes)
    return nomes


def tem_funcao(user, *funcoes: str) -> bool:
    if getattr(user, "is_superuser", False) and user.is_active:
        return True
    return bool(nomes_das_funcoes(user).intersection(funcoes))


def faz_parte_da_equipe(user) -> bool:
    return bool(nomes_das_funcoes(user))


def capacidades(user) -> dict[str, bool]:
    """Permissões da interface e das views, calculadas no mesmo lugar."""
    superusuario = bool(
        getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and getattr(user, "is_superuser", False)
    )
    producao = tem_funcao(user, PRODUCAO)
    criacao = tem_funcao(user, CRIACAO)
    vendas = tem_funcao(user, VENDAS)
    ambulante = tem_funcao(user, AMBULANTE)
    funcao_financeiro = tem_funcao(user, FINANCEIRO)
    gestao = tem_funcao(user, GESTAO)
    comercial = vendas or ambulante or gestao
    acesso_financeiro = funcao_financeiro or gestao

    return {
        "superusuario": superusuario,
        "producao": producao,
        "criacao": criacao,
        "vendas": vendas,
        "ambulante": ambulante,
        "financeiro_funcao": funcao_financeiro,
        "gestao": gestao,
        "estoque": producao or gestao,
        "clientes": comercial,
        # Financeiro participa do mesmo orçamento, mas somente no bloco
        # de preço/condições. Criar a proposta e definir os itens continua
        # sendo responsabilidade comercial.
        "orcamentos": comercial or acesso_financeiro,
        "orcamentos_criar": comercial,
        "orcamentos_editar_comercial": comercial,
        "orcamentos_editar_financeiro": acesso_financeiro,
        # Uma conta exclusivamente Ambulante trabalha apenas a própria
        # carteira de propostas. Se também receber Vendas ou Gestão, passa
        # a participar da central compartilhada como essas funções preveem.
        "orcamentos_proprios": ambulante and not (vendas or gestao),
        # Vendas corrige o próprio rascunho; Gestão pode remover qualquer
        # rascunho. Clientes não têm autoria, então a exclusão fica com
        # Gestão. O estado do orçamento ainda é conferido por objeto abaixo.
        "excluir_clientes": gestao,
        "excluir_orcamentos": comercial,
        "excluir_orcamentos_alheios": gestao,
        "financeiro": acesso_financeiro,
        "vendas_financeiro": acesso_financeiro,
        "pedidos": acesso_financeiro,
        "manutencoes": producao or gestao,
        # A LISTA DE MONTAGEM (seção 112) é da ENGENHARIA DE PRODUÇÃO: só ela
        # (e o superusuário) marca as etapas, mexe na fila e nas regras. A
        # Gestão e o Financeiro veem tudo sem mexer; Vendas e o Ambulante
        # veem só o andamento e a previsão do que eles venderam (os próprios
        # orçamentos). O menu e a view perguntam às mesmas três chaves.
        "lista_montagem": producao or gestao or funcao_financeiro or vendas or ambulante,
        "lista_montagem_editar": producao,
        "lista_montagem_tudo": producao or gestao or funcao_financeiro,
        "ordens_servico": producao or acesso_financeiro or gestao,
        "ordens_servico_editar": producao or gestao,
        "ordens_servico_pagamento": acesso_financeiro,
        # Etiquetas de transporte: lista os clientes com endereço -- quem
        # despacha a caixa (seção 114; views_etiquetas confere o mesmo).
        "etiquetas": producao or acesso_financeiro,
        # Compatibilidade com pontos antigos que perguntam se existe alguma
        # operação acessível. As telas usam as capacidades específicas.
        "operacao": producao or acesso_financeiro or gestao,
        # Transportadoras recomendadas (o frete saiu do site): quem vende
        # indica, quem despacha combina a coleta, e Gestão mantém a lista
        # -- é ela que responde por um número errado passado ao cliente.
        "transportadoras": vendas or gestao or producao,
        "transportadoras_editar": gestao,
        # Os dados do vendedor no contrato de compra e venda (o representante
        # da empresa): quem responde pela identidade jurídica no papel.
        "dados_contrato": gestao,
        # AS ASSINATURAS NUM LUGAR SÓ (seção 137): a tela junta os documentos
        # que o cliente assina, organizados pelo objeto. Cada um vê as do
        # objeto que já abre: as do ORÇAMENTO, quem gera o documento dele (o
        # Comercial -- e o Ambulante só as da própria carteira); as da O.S.,
        # quem vê a O.S. (o Financeiro incluído, que cobra pelo papel
        # assinado). `assinaturas_menu_operacao` só decide em que bloco do
        # menu o item aparece para quem não é do Comercial.
        "assinaturas": comercial or producao or acesso_financeiro,
        # O Financeiro também vê as dos orçamentos (o dono liberou: ele cobra
        # pelo contrato assinado). Só LÊ e imprime: gerar o documento, o QR e
        # o link continuam com o Comercial (`orcamentos_editar_comercial`).
        "assinaturas_orcamentos": comercial or acesso_financeiro,
        "assinaturas_os": producao or acesso_financeiro or gestao,
        # os contratos dos PEDIDOS DO SITE (seção 145): quem já vê os pedidos
        # do site (`pedidos`: Financeiro e Gestão). Só leitura: quem gera e
        # assina é o cliente, em Meus pedidos.
        "assinaturas_pedidos": acesso_financeiro,
        # o item no bloco Comercial do menu: só para quem é do Comercial (o
        # Financeiro, que agora também vê as dos orçamentos, fica no Operação)
        "assinaturas_menu_comercial": comercial,
        "assinaturas_menu_operacao": (producao or acesso_financeiro) and not comercial,
        # ENTRADA DE NOTA FISCAL (seção 115): lança quem paga a compra -- o
        # Financeiro, e a Gestão (o superusuário tem todas). A Engenharia de
        # produção, dona do estoque, VÊ as notas lançadas (não as que ainda
        # estão em conferência) e não lança.
        "entrada_nota": acesso_financeiro,
        "entrada_nota_ver": acesso_financeiro or producao,
        "site": criacao,
        # RECURSOS HUMANOS (app `rh`), com as MESMAS funções: não há grupo
        # "RH" à parte. Gestão (e o superusuário, que tem todas) vê e
        # edita todas as fichas, documentos, ajustes de ponto e tarefas.
        # Financeiro vê o que precisa para pagar -- salário, banco e Pix,
        # e o espelho de ponto -- sem editar a ficha. Qualquer integrante
        # da equipe (Produção, Criação, Vendas, Ambulante...) vê só o
        # próprio: o ponto, as tarefas e a ficha básica.
        "rh": gestao,
        "rh_pagamento": acesso_financeiro,
        "rh_equipe": gestao or funcao_financeiro,
        "rh_proprio": bool(nomes_das_funcoes(user)),
        # toda a equipe: "Minha área" do menu (o próprio ponto, as tarefas,
        # a conta e abrir a loja -- seção 114)
        "equipe": bool(nomes_das_funcoes(user)),
        "usuarios": superusuario,
        "avaliar_blocos_orcamento": superusuario,
        "avaliar_setores": superusuario,
    }


def pode_excluir_cliente(user) -> bool:
    """Cadastro comercial sem histórico só pode ser apagado por Gestão."""
    return capacidades(user)["excluir_clientes"]


def pode_excluir_orcamento(user, orcamento) -> bool:
    """Limita exclusão a rascunhos e respeita a autoria em Vendas.

    Uma proposta enviada, respondida ou expirada já é histórico comercial.
    Ela pode mudar de situação, mas não deve desaparecer da linha do tempo.
    """
    acesso = capacidades(user)
    if not acesso["excluir_orcamentos"]:
        return False
    if getattr(orcamento, "status", None) != "rascunho":
        return False
    if acesso["excluir_orcamentos_alheios"]:
        return True
    return getattr(orcamento, "responsavel_id", None) == getattr(user, "pk", None)


def limitar_orcamentos(user, queryset):
    """Aplica a carteira individual da função Ambulante no próprio banco."""
    if capacidades(user)["orcamentos_proprios"]:
        return queryset.filter(responsavel=user)
    return queryset


def pode_acessar_orcamento(user, orcamento) -> bool:
    """Confere o objeto, inclusive em POST e prévia por URL direta."""
    acesso = capacidades(user)
    if not acesso["orcamentos"]:
        return False
    if not acesso["orcamentos_proprios"]:
        return True
    return getattr(orcamento, "responsavel_id", None) == getattr(user, "pk", None)


def origem_padrao_orcamento(user) -> str:
    """Origem confiável, derivada da função em vez de um campo do navegador."""
    return "ambulante" if capacidades(user)["orcamentos_proprios"] else "interno"


def atribuir_funcoes(user, codigos) -> list[Funcao]:
    """Substitui somente as funções internas, preservando outros grupos."""
    escolhidas = [
        FUNCOES_POR_CODIGO[codigo]
        for codigo in dict.fromkeys(codigos)
        if codigo in FUNCOES_POR_CODIGO
    ]
    grupos = grupos_de_funcoes()

    # Os mesmos grupos que a consulta acima acabou de trazer (todos os das
    # funções): tirar por eles poupa reler a tabela.
    user.groups.remove(*grupos.values())
    if escolhidas:
        user.groups.add(*(grupos[funcao.grupo] for funcao in escolhidas))
    user._funcoes_interno_cache = frozenset(
        funcao.grupo for funcao in escolhidas
    )

    # is_staff passa a significar "pode usar interfaces de equipe"; o que
    # aparece em cada uma vem das funções acima.
    novo_staff = bool(escolhidas) or user.is_superuser
    if user.is_staff != novo_staff:
        user.is_staff = novo_staff
        user.save(update_fields=["is_staff"])
    return escolhidas


# ----------------------------------------------------------------------
# OS USUÁRIOS POR FUNÇÃO (o menu "Pessoas" do superusuário, seção 114)
# ----------------------------------------------------------------------
CHAVE_RESUMO_DE_USUARIOS = "menu:usuarios_por_funcao"


def resumo_de_usuarios() -> dict:
    """Quantas contas ATIVAS há em cada função, na equipe e entre os clientes.

    Três consultas, guardadas por um minuto (a tela de acessos esquece o
    resumo ao salvar). Só o superusuário vê -- o menu pergunta antes.
    """
    from django.core.cache import cache

    def contar():
        from django.contrib.auth.models import Group, User
        from django.db.models import Count, Q

        por_grupo = dict(
            Group.objects.filter(name__in=NOMES_DOS_GRUPOS)
            .annotate(total=Count("user", filter=Q(user__is_active=True), distinct=True))
            .values_list("name", "total")
        )
        equipe = (
            User.objects.filter(is_active=True)
            .filter(Q(is_superuser=True) | Q(is_staff=True) | Q(groups__name__in=NOMES_DOS_GRUPOS))
            .distinct().count()
        )
        clientes = (
            User.objects.filter(is_active=True, is_superuser=False, is_staff=False)
            .exclude(groups__name__in=NOMES_DOS_GRUPOS).count()
        )
        return {
            "equipe": equipe,
            "clientes": clientes,
            "funcoes": [
                {"codigo": f.codigo, "titulo": f.titulo, "icone": f.icone, "total": por_grupo.get(f.grupo, 0)}
                for f in FUNCOES
            ],
        }

    try:
        return cache.get_or_set(CHAVE_RESUMO_DE_USUARIOS, contar, 60)
    except Exception:  # noqa: BLE001 -- sem cache, conta na hora
        return contar()


def esquecer_resumo_de_usuarios():
    from django.core.cache import cache

    try:
        cache.delete(CHAVE_RESUMO_DE_USUARIOS)
    except Exception:  # noqa: BLE001
        pass
