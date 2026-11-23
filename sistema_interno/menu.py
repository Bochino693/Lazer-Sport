"""O MENU LATERAL POR FUNÇÃO (LEIA-ME-V10, seção 114).

"Quero as opções baseadas nas funções, elas devem vir antes dos blocos":
o menu abre pela FUNÇÃO e, dentro dela, pelos blocos dela --

    Engenharia de produção  ->  Produção · Estoque · Operação · Logística
    Criação e site          ->  Site e aplicativo
    Vendas                  ->  Comercial · Produção · Logística
    Vendedor ambulante      ->  Comercial · Produção
    Financeiro              ->  Financeiro · Estoque · Comercial · Operação ·
                                Produção · Pessoas
    Gestão                  ->  Painel · Comercial · Financeiro · Pessoas ·
                                Estoque · Produção · Operação · Logística
    Administração (o dono)  ->  Equipe e acessos · Lazer & Sport Games ·
                                Estúdio 3D
    Minha área (todos)      ->  Meu dia (ponto, tarefas, termo, conta) · Loja

"Aqui você deve modularizar melhor pelas funções": nada fica solto depois
das funções -- o RH entra na Gestão e no Financeiro (bloco Pessoas), o
que é só do dono vira o grupo Administração e o que é de cada um (o
próprio ponto, as tarefas, a conta, abrir a loja) vira Minha área.

Cada pessoa vê as funções que tem (o superusuário, todas). Dentro de uma
função só entra a tela que AQUELA função abre -- a conta é a mesma de
`permissoes.capacidades`, feita como se a pessoa tivesse só a função --,
e só se a própria pessoa também a abre (as duas perguntas dão a mesma
resposta; a segunda é o cinto de segurança). Uma tela que duas funções
usam (Orçamentos em Vendas e no Financeiro) aparece nas duas: é o
caminho de cada uma.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

from .permissoes import FUNCOES, capacidades


@dataclass(frozen=True)
class Item:
    titulo: str
    rota: str
    icone: str
    chave: str  # a capacidade que abre a tela
    ativo: tuple = ()  # outras rotas em que o item fica aceso
    selo: str = ""  # o contador (data-selo) que o pulso do painel pinta
    selo_zero: bool = False
    selo_titulo: str = ""
    rotulo: str = ""  # o texto curto no menu (o título vai no balão)
    externo: bool = False  # abre noutra aba (a loja)
    sem_navegacao_suave: bool = False  # a tela que carrega a página inteira (o 3D)

    @property
    def rotas_ativas(self):
        return (self.rota, *self.ativo)

    @property
    def nome(self):
        return self.rotulo or self.titulo


#: Os blocos e as telas de cada um, na ordem do menu.
BLOCOS = {
    "Painel": (
        Item("Visão geral", "home_inner", "bi-grid-fill", "gestao"),
        Item("Indicadores", "dashboard_estoque", "bi-activity", "gestao"),
        Item("Segurança das contas", "seguranca_contas", "bi-shield-check", "gestao"),
    ),
    "Estoque": (
        Item("Estoque", "stock", "bi-box-seam-fill", "estoque", ativo=("estoque_inner",)),
        Item("Materiais", "materiais_inner", "bi-tools", "estoque"),
        Item("Movimentações", "movimentacoes_inner", "bi-arrow-left-right", "estoque"),
        # a nota fiscal do fornecedor (PDF ou XML) que entra no estoque (seção 115):
        # o Financeiro lança, a Produção e a Gestão veem
        Item("Notas de entrada", "notas_entrada", "bi-receipt-cutoff", "entrada_nota_ver",
             ativo=("nota_entrada",)),
    ),
    "Produção": (
        Item("Lista de montagem", "lista_montagem", "bi-list-ol", "lista_montagem"),
        Item("Acompanhamento", "minha_producao", "bi-list-check", "producao",
             ativo=("producao_ordem_detalhe",), selo="count_producao"),
        Item("Produtos e ficha técnica", "produtos_producao", "bi-diagram-3-fill", "producao"),
        Item("Guias das etapas", "guias_producao", "bi-journal-richtext", "producao"),
        Item("Ordens de produção", "ordens_producao", "bi-hammer", "producao"),
    ),
    "Comercial": (
        Item("Clientes", "clientes_inner", "bi-people-fill", "clientes", selo="count_clientes_incompletos"),
        Item("Orçamentos", "orcamentos_inner", "bi-file-earmark-text-fill", "orcamentos",
             selo="count_orcamentos", selo_zero=True, selo_titulo="Em aberto"),
        Item("Projetos 3D do site", "pedidos_projeto_3d", "bi-badge-3d-fill", "clientes",
             ativo=("pedido_projeto_3d",)),
        Item("Clientes no mapa", "clientes_admin", "bi-geo-alt-fill", "gestao"),
        Item("Dados do contrato", "dados_contrato_inner", "bi-file-earmark-ruled-fill", "dados_contrato"),
    ),
    "Financeiro": (
        Item("Financeiro", "financeiro_inner", "bi-graph-up-arrow", "financeiro"),
        Item("Vendas", "vendas_inner", "bi-receipt-cutoff", "vendas_financeiro", selo="count_vendas"),
        Item("Pedidos", "pedidos_inner", "bi-box2-heart-fill", "pedidos",
             selo="count_pedidos", selo_zero=True, selo_titulo="Pedidos em aberto"),
    ),
    "Operação": (
        Item("Ordens de Serviço", "ordens_servico_inner", "bi-clipboard2-check-fill", "ordens_servico",
             ativo=("ordem_servico_previa_inner",), selo="count_ordens_servico", selo_zero=True,
             selo_titulo="Em aberto"),
        Item("Manutenções", "manutencao_inner", "bi-wrench-adjustable-circle-fill", "manutencoes",
             selo="count_manutencao", selo_zero=True, selo_titulo="Manutenções abertas"),
        Item("Etiquetas de transporte", "etiquetas_inner", "bi-upc-scan", "etiquetas", rotulo="Etiquetas"),
    ),
    "Logística": (
        Item("Transportadoras", "transportadoras_inner", "bi-truck", "transportadoras"),
    ),
    # RECURSOS HUMANOS da equipe (app `rh`): a Gestão vê tudo; o Financeiro,
    # o que precisa para pagar (as fichas e o ponto da equipe)
    "Pessoas": (
        Item("RH da equipe", "rh_inicio", "bi-person-badge-fill", "rh", ativo=("rh_termo", "rh_termo_via")),
        Item("Colaboradores", "rh_colaboradores", "bi-people-fill", "rh_equipe",
             ativo=("rh_ficha", "rh_colaborador_novo", "rh_colaborador_editar", "rh_ficha_imprimir")),
        Item("Ponto da equipe", "rh_ponto_equipe", "bi-clock-history", "rh_equipe",
             ativo=("rh_espelho", "rh_espelho_imprimir")),
        Item("Documentos da equipe", "rh_documentos", "bi-folder2-open", "rh"),
    ),
    # SÓ DO DONO (o superusuário)
    "Equipe e acessos": (
        Item("Usuários da equipe", "usuarios_equipe", "bi-shield-lock-fill", "usuarios"),
        Item("Avaliação dos setores", "avaliacao_setores", "bi-clipboard-data-fill", "usuarios"),
        Item("Contas de clientes", "clients", "bi-person-vcard-fill", "usuarios"),
    ),
    "Lazer & Sport Games": (
        Item("Jogos do portal", "jogos_inner", "bi-controller", "usuarios", rotulo="Jogos · APK · Windows"),
        Item("Ao vivo no portal", "jogos_ao_vivo", "bi-broadcast", "usuarios"),
    ),
    "Estúdio 3D": (
        Item("Objetos 3D", "objetos_3d_inner", "bi-box", "usuarios"),
        Item("Montar em 3D", "montar_3d_inner", "bi-bricks", "usuarios", sem_navegacao_suave=True),
    ),
    # as fotos guardadas no banco: o que ainda falta e a exportação do Cloudinary (seção 130)
    "Fotos e arquivos": (
        Item("Restaurar fotos", "restaurar_fotos", "bi-images", "usuarios"),
    ),
    # DE CADA UM (toda a equipe)
    "Meu dia": (
        Item("Meu ponto", "rh_ponto", "bi-fingerprint", "equipe", ativo=("rh_comprovante", "rh_ajuste_pedir")),
        Item("Minhas tarefas", "rh_tarefas", "bi-check2-square", "equipe", ativo=("rh_tarefa_editar",)),
        Item("Meu termo de exclusividade", "rh_meu_termo", "bi-file-earmark-lock", "equipe", rotulo="Meu termo"),
        Item("Minha conta", "minha_conta_inner", "bi-person-gear", "equipe"),
    ),
    "Loja": (
        Item("Abrir a loja", "abrir_loja", "bi-box-arrow-up-right", "equipe", externo=True),
    ),
    "Site e aplicativo": (
        Item("Brinquedos do site", "brinquedos_admin", "bi-controller", "site", rotulo="Brinquedos"),
        Item("Peças de reposição", "pecas_admin", "bi-wrench-adjustable", "site"),
        Item("Combos", "combos_admin", "bi-box2-heart-fill", "site"),
        Item("Promoções", "promocoes_admin", "bi-tags-fill", "site"),
        Item("Banners", "banner_adm", "bi-images", "site"),
        Item("Eventos", "eventos_admin", "bi-calendar2-event-fill", "site"),
        Item("Projetos", "projetos_admin", "bi-folder-fill", "site"),
        Item("Cupons", "cupons_admin", "bi-ticket-perforated-fill", "site"),
        Item("Campanhas", "campanhas_inner", "bi-megaphone-fill", "site", ativo=("campanha_detalhe",)),
        Item("Curtidas e desejos", "engajamento_admin", "bi-heart-fill", "site"),
        Item("Avisos do aplicativo", "avisos_app", "bi-bell-fill", "site"),
        Item("Indicadores do site", "dashboards", "bi-bar-chart-fill", "site"),
    ),
}

#: A ordem dos blocos dentro de cada função (o que ela mais usa primeiro).
BLOCOS_DA_FUNCAO = {
    "producao": ("Produção", "Estoque", "Operação", "Logística"),
    "criacao": ("Site e aplicativo",),
    "vendas": ("Comercial", "Produção", "Logística"),
    "ambulante": ("Comercial", "Produção"),
    "financeiro": ("Financeiro", "Estoque", "Comercial", "Operação", "Produção", "Pessoas"),
    "gestao": ("Painel", "Comercial", "Financeiro", "Pessoas", "Estoque", "Produção", "Operação", "Logística"),
}

#: Os grupos que não são função: o do dono e o de cada um. (código, título,
#: ícone, blocos, a chave que mostra o grupo, aparece no topo?)
GRUPOS_EXTRAS = (
    ("admin", "Administração", "bi-shield-lock-fill",
     ("Equipe e acessos", "Lazer & Sport Games", "Estúdio 3D", "Fotos e arquivos"), "usuarios", True),
    ("pessoal", "Minha área", "bi-person-circle", ("Meu dia", "Loja"), "equipe", False),
)


#: O nome curto da função no botão do topo.
CURTO = {
    "producao": "Produção", "criacao": "Site", "vendas": "Vendas",
    "ambulante": "Ambulante", "financeiro": "Financeiro", "gestao": "Gestão",
    "admin": "Admin", "pessoal": "Eu",
}

#: As ações de um toque no atalho do topo: (título, rota, sufixo, capacidade, ícone).
ACOES_DA_FUNCAO = {
    "producao": (
        ("Abrir Ordem de Serviço", "ordens_servico_inner", "?novo=1", "ordens_servico_editar", "bi-clipboard2-plus"),
        ("Movimentar estoque", "stock", "", "estoque", "bi-arrow-left-right"),
    ),
    "vendas": (
        ("Novo orçamento", "orcamentos_inner", "?novo=1", "orcamentos_criar", "bi-file-earmark-plus"),
        ("Cadastrar cliente", "clientes_inner", "", "clientes", "bi-person-plus"),
    ),
    "ambulante": (
        ("Novo orçamento", "orcamentos_inner", "?novo=1", "orcamentos_criar", "bi-file-earmark-plus"),
        ("Cadastrar cliente", "clientes_inner", "", "clientes", "bi-person-plus"),
    ),
    "gestao": (
        ("Novo orçamento", "orcamentos_inner", "?novo=1", "orcamentos_criar", "bi-file-earmark-plus"),
        ("Abrir Ordem de Serviço", "ordens_servico_inner", "?novo=1", "ordens_servico_editar", "bi-clipboard2-plus"),
        ("Lançar nota de entrada", "notas_entrada", "", "entrada_nota", "bi-receipt-cutoff"),
    ),
    "financeiro": (
        ("Lançar nota de entrada", "notas_entrada", "", "entrada_nota", "bi-receipt-cutoff"),
    ),
}


def capacidades_da_funcao(codigo) -> dict:
    """O que a função abre sozinha (como se a pessoa tivesse só ela)."""
    funcao = next(f for f in FUNCOES if f.codigo == codigo)
    so_ela = SimpleNamespace(
        is_authenticated=True, is_active=True, is_superuser=False,
        _funcoes_interno_cache=frozenset({funcao.grupo}),
    )
    return capacidades(so_ela)


_DA_FUNCAO = {}


def _abre(codigo, chave) -> bool:
    if codigo not in _DA_FUNCAO:
        _DA_FUNCAO[codigo] = capacidades_da_funcao(codigo)
    return bool(_DA_FUNCAO[codigo].get(chave))


@dataclass
class Grupo:
    codigo: str
    titulo: str
    icone: str
    blocos: list = field(default_factory=list)  # [(nome do bloco, [Item, ...])]
    acoes: list = field(default_factory=list)  # [{"titulo", "rota", "sufixo", "icone"}]
    papel: str = "funcao"  # "funcao", "admin" (o dono) ou "pessoal" (de cada um)
    no_topo: bool = True  # tem botão nos atalhos do topo

    @property
    def curto(self):
        return CURTO.get(self.codigo, self.titulo)


#: A chave de `capacidades` que diz se a pessoa TEM a função ("financeiro"
#: lá é o acesso ao dinheiro, que a Gestão também tem).
CHAVE_DA_FUNCAO = {"financeiro": "financeiro_funcao"}


def menu_do_usuario(acesso) -> list:
    """As funções da pessoa, cada uma com os blocos e as telas dela."""
    grupos = []
    for funcao in FUNCOES:
        if not (acesso.get("superusuario") or acesso.get(CHAVE_DA_FUNCAO.get(funcao.codigo, funcao.codigo))):
            continue
        grupo = Grupo(funcao.codigo, funcao.titulo, funcao.icone)
        for nome in BLOCOS_DA_FUNCAO.get(funcao.codigo, ()):
            itens = [
                item for item in BLOCOS[nome]
                if _abre(funcao.codigo, item.chave) and acesso.get(item.chave)
            ]
            if itens:
                grupo.blocos.append((nome, itens))
        grupo.acoes = [
            {"titulo": titulo, "rota": rota, "sufixo": sufixo, "icone": icone}
            for titulo, rota, sufixo, chave, icone in ACOES_DA_FUNCAO.get(funcao.codigo, ())
            if _abre(funcao.codigo, chave) and acesso.get(chave)
        ]
        if grupo.blocos:
            grupos.append(grupo)
    for codigo, titulo, icone, blocos, chave, no_topo in GRUPOS_EXTRAS:
        if not acesso.get(chave):
            continue
        grupo = Grupo(codigo, titulo, icone, papel=codigo, no_topo=no_topo)
        for nome in blocos:
            itens = [item for item in BLOCOS[nome] if acesso.get(item.chave)]
            if itens:
                grupo.blocos.append((nome, itens))
        if grupo.blocos:
            grupos.append(grupo)
    return grupos
