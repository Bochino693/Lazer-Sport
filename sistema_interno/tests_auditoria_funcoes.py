"""AUDITORIA DAS FUNÇÕES (LEIA-ME-V10, seção 114).

"Tenho 5 tipos de usuário, vendedores, engenharia de produção e etc, vc
deve modularizar todas as funções." Cada função entra no painel e:

  1. abre TODO link da tela de entrada dela (o menu lateral, as abas do
     celular, os atalhos e os cartões do Início) -- link
     que dá 403/404/500, ou que devolve a pessoa para o início dela, é
     defeito: o menu ofereceu o que a tela não deixa abrir;
  2. abre as telas principais de acordo com a MATRIZ abaixo, e só elas --
     o que a função não deve ver não abre nem digitando o endereço.

A matriz é escrita à mão, de propósito: quem mudar uma permissão em
`permissoes.capacidades` muda aqui também, e o teste mostra a diferença.
"""

import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .permissoes import atribuir_funcoes

INTERNO = {"HTTP_HOST": "interno.testserver"}
FUNCOES = ("producao", "criacao", "vendas", "ambulante", "financeiro", "gestao")

TODOS = set(FUNCOES)
COMERCIAL = {"vendas", "ambulante", "gestao"}
FINANCEIRO = {"financeiro", "gestao"}
PRODUCAO = {"producao", "gestao"}
SITE = {"criacao"}
SO_ADMIN = set()

#: Rota -> funções que a abrem (o superusuário abre todas).
MATRIZ = {
    # comercial
    "clientes_inner": COMERCIAL,
    "orcamentos_inner": COMERCIAL | FINANCEIRO,
    "pedidos_projeto_3d": COMERCIAL,
    "dados_contrato_inner": {"gestao"},
    # as assinaturas num lugar só (seção 137): quem gera o documento do
    # orçamento (Comercial) e quem vê a O.S. (Produção, Financeiro, Gestão)
    "assinaturas_inner": COMERCIAL | PRODUCAO | FINANCEIRO,
    "transportadoras_inner": {"vendas", "gestao", "producao"},
    # financeiro
    "financeiro_inner": FINANCEIRO,
    "vendas_inner": FINANCEIRO,
    "pedidos_inner": FINANCEIRO,
    # a entrada de nota fiscal (seção 115): o Financeiro (e a Gestão) lança,
    # a Engenharia de produção vê as notas lançadas
    "notas_entrada": FINANCEIRO | {"producao"},
    # engenharia de produção: estoque e materiais são dela
    "stock": PRODUCAO,
    "estoque_inner": PRODUCAO,
    "materiais_inner": PRODUCAO,
    "movimentacoes_inner": PRODUCAO,
    "manutencao_inner": PRODUCAO,
    "minha_producao": {"producao"},
    "ordens_producao": {"producao"},
    "lista_montagem": {"producao", "gestao", "financeiro", "vendas", "ambulante"},
    "ordens_servico_inner": PRODUCAO | FINANCEIRO,
    "etiquetas_inner": PRODUCAO | FINANCEIRO,
    # site
    "brinquedos_admin": SITE,
    "banner_adm": SITE,
    "promocoes_admin": SITE,
    "campanhas_inner": SITE,
    # recursos humanos: a gestão vê tudo; o financeiro, a equipe (para
    # pagar); cada um, o próprio ponto e as próprias tarefas
    "rh_colaboradores": FINANCEIRO,
    "rh_colaborador_novo": {"gestao"},
    "rh_documentos": {"gestao"},
    "rh_ponto": TODOS,
    "rh_tarefas": TODOS,
    "rh_meu_termo": TODOS,
    # só o superusuário
    "usuarios_equipe": SO_ADMIN,
    "avaliacao_setores": SO_ADMIN,
    "objetos_3d_inner": SO_ADMIN,
    "jogos_inner": SO_ADMIN,
}

#: Links do menu que redirecionam DE PROPÓSITO: o Início leva à tela da
#: função, a loja abre o site, o RH abre o "meu ponto" de quem não é Gestão.
REDIRECIONAM = {"/", "/abrir-site/loja/", "/rh/"}


def _links_da_tela(html):
    """Os destinos que a tela de entrada oferece (menus, abas, atalhos e cartões)."""
    links = set(re.findall(r'href="(/[^"#?]*)', html))
    return {
        link for link in links
        if not link.startswith(("/static/", "/media/", "/logout")) and not link.endswith((".css", ".js", ".webmanifest"))
    }


class AuditoriaDasFuncoesTests(TestCase):
    maxDiff = None

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.usuarios = {}
        for codigo in FUNCOES:
            user = User.objects.create_user(f"aud-{codigo}", f"aud-{codigo}@exemplo.test", "x")
            atribuir_funcoes(user, [codigo])
            cls.usuarios[codigo] = user
        cls.usuarios["admin"] = User.objects.create_superuser("aud-admin", "aud-admin@exemplo.test", "x")

    def test_o_que_o_menu_mostra_a_tela_abre(self):
        quebrados = []
        for codigo, user in self.usuarios.items():
            self.client.force_login(user)
            inicio = self.client.get("/", follow=True, **INTERNO)
            links = _links_da_tela(inicio.content.decode())
            self.assertTrue(links, f"{codigo}: menu vazio")
            for link in sorted(links - REDIRECIONAM):
                resposta = self.client.get(link, **INTERNO)
                if resposta.status_code != 200:
                    destino = resposta.get("Location", "")
                    quebrados.append(f"{codigo}: {link} -> {resposta.status_code} {destino}".strip())
        self.assertEqual(quebrados, [])

    def test_cada_funcao_abre_so_o_que_e_dela(self):
        erradas = []
        for nome, quem in MATRIZ.items():
            caminho = reverse(nome, urlconf="sistema_interno.urls")
            for codigo, user in self.usuarios.items():
                self.client.force_login(user)
                abre = self.client.get(caminho, **INTERNO).status_code == 200
                deve = codigo == "admin" or codigo in quem
                if abre != deve:
                    erradas.append(f"{nome} ({caminho}) para {codigo}: abre={abre}, devia={deve}")
        self.assertEqual(erradas, [])
