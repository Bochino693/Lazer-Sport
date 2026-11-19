"""Quanto custa cada AÇÃO do painel, com o que o navegador faz logo depois.

POR QUE ESTA FERRAMENTA. `consultas_por_tela.py` mede telas abertas. O que
a fábrica sente é outra coisa: tocar em "Salvar" e esperar a tela mostrar o
resultado. Isso é o POST da ação MAIS o que o navegador pede em seguida --
a tela (inteira ou só a lista), o estado do sino e, às vezes, a régua do
orçamento. Cada consulta ao banco é uma viagem até o Supabase (~170 ms em
11/2026, LEIA-ME-V10 §120), então o que importa é contar viagens.

O QUE É CONTADO COMO VIAGEM, por requisição:
  * cada consulta capturada (CaptureQueriesContext), inclusive SAVEPOINT e
    RELEASE SAVEPOINT (cada `transaction.atomic()` aninhado são duas);
  * cada BEGIN capturado vale DUAS: no PostgreSQL (psycopg2) o BEGIN e o
    COMMIT são idas ao banco; no SQLite o COMMIT não aparece na captura;
  * mais a conferência da conexão reaproveitada (`SELECT 1` do
    conn_health_checks), que no SQLite não existe. `--conferencia antes`
    conta uma em toda requisição (o código de antes); `--conferencia agora`
    (padrão) conta na ação e não nos pedidos que o navegador manda logo atrás
    dela -- a conexão acabou de ser usada e o socket está quieto
    (lazer/banco_postgres, LEIA-ME-V10 §120).

O TEMPO "NO AR" = CPU medida aqui (sem latência) + viagens x --latencia ms.
Não conta a rede até o navegador nem a abertura de conexão nova (~1,2 s,
paga no máximo uma vez por conexão).

Uso (cria um banco de teste em memória, povoa e mede; ~40 s):

    DJANGO_SETTINGS_MODULE=lazer.settings_test \\
        python ferramentas/carga/acoes_do_painel.py [--latencia 170] \\
        [--conferencia antes|agora] [--detalhe "Orçamentos: salvar"] [--json saida.json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from decimal import Decimal

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lazer.settings_test")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.core.cache import cache  # noqa: E402
from django.db import connection  # noqa: E402
from django.test import Client  # noqa: E402
from django.test.utils import CaptureQueriesContext, setup_test_environment  # noqa: E402
from django.utils import timezone  # noqa: E402

HOST = "interno.testserver"
JSON = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
NAVEGACAO = {"HTTP_X_REQUESTED_WITH": "LS-Soft-Navigation"}
PEDACO = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest", "HTTP_X_LS_FRAGMENTO": "lista"}


# ----------------------------------------------------------------------
# O banco: parecido com o do ar, em tamanho
# ----------------------------------------------------------------------
def povoar():
    from django.contrib.auth.models import User

    from core.models import Brinquedos, CategoriasBrinquedos, PecasReposicao
    from rh.apoio_testes import criar_colaborador
    from sistema_interno.models import (
        Cliente, EnderecoCliente, EstoqueMaterial, GuiaEtapaProducao, ItemOrcamento,
        ItemOrdemServico, Material, Orcamento, OrdemProducao, OrdemServico, ProdutoInterno,
        TipoMaterial,
    )
    from sistema_interno.permissoes import atribuir_funcoes

    dono = User.objects.create_superuser("dono", "dono@exemplo.invalid", "senha-de-teste")
    gestora = User.objects.create_user("gestora", "gestora@exemplo.invalid", "senha-de-teste", first_name="Gestora")
    atribuir_funcoes(gestora, ["gestao", "producao", "financeiro", "vendas"])
    vendedor = User.objects.create_user("vendedor", "vendedor@exemplo.invalid", "senha-de-teste", first_name="Vendedor")
    atribuir_funcoes(vendedor, ["vendas"])
    producao = User.objects.create_user("producao", "producao@exemplo.invalid", "senha-de-teste", first_name="Montador")
    atribuir_funcoes(producao, ["producao"])
    # as contas dos clientes da loja: o painel não as mostra, mas uma tela que
    # ande por "todas as contas ativas" paga por elas (a lista de técnicos da O.S.)
    User.objects.bulk_create([
        User(username=f"cliente-loja-{i}", email=f"loja{i}@exemplo.invalid", is_active=True)
        for i in range(40)
    ])

    categoria = CategoriasBrinquedos.objects.create(nome_categoria="Infláveis")
    brinquedos = []
    for i in range(30):
        b = Brinquedos.objects.create(
            nome_brinquedo=f"Brinquedo {i}", imagem_brinquedo=f"imagens_brinquedos/b{i}.jpg",
            descricao="Brinquedo de teste", valor_brinquedo=Decimal("280.00") + i,
            avaliacao=Decimal("5.00"), voltz="110",
        )
        b.categorias_brinquedos.add(categoria)
        brinquedos.append(b)
    for i in range(30):
        PecasReposicao.objects.create(
            nome=f"Peça {i}", descricao_peca="Reposição", preco_venda=Decimal("12.00") + i, ativo=True,
        )

    clientes = []
    for i in range(300):
        c = Cliente.objects.create(
            nome_cliente=f"Cliente {i:03d}", telefone=f"1199{i:07d}",
            email=f"cliente{i}@exemplo.invalid",
        )
        EnderecoCliente.objects.create(
            cliente=c, endereco="Rua das Flores", numero=str(i), bairro="Centro",
            cidade="São Paulo", estado="SP",
        )
        clientes.append(c)

    situacoes = [
        Orcamento.Status.AGUARDANDO_RESPOSTA, Orcamento.Status.EM_NEGOCIACAO,
        Orcamento.Status.APROVADO, Orcamento.Status.RECUSADO, Orcamento.Status.RASCUNHO,
    ]
    for i in range(150):
        cliente = clientes[i % len(clientes)]
        o = Orcamento.objects.create(
            cliente=cliente, nome_cliente=cliente.nome_cliente, contato=cliente.telefone,
            status=situacoes[i % len(situacoes)], responsavel=dono if i % 2 else vendedor,
            validade=timezone.localdate() + timezone.timedelta(days=10 - (i % 20)),
        )
        ItemOrcamento.objects.bulk_create([
            ItemOrcamento(orcamento=o, descricao=f"Item {j}", brinquedo=brinquedos[(i + j) % 30],
                          quantidade=1, valor_unitario=Decimal("300.00"))
            for j in range(3)
        ])

    for i in range(80):
        cliente = clientes[(i * 7) % len(clientes)]
        os_ = OrdemServico.objects.create(cliente=cliente, nome_cliente=cliente.nome_cliente, equipamento=f"Tobogã {i}")
        ItemOrdemServico.objects.create(
            ordem=os_, tipo=ItemOrdemServico.Tipo.SERVICO, descricao="Reparo",
            quantidade=1, valor_unitario=Decimal("120.00"),
        )

    tipo = TipoMaterial.objects.create(descricao="Lona")
    for i in range(40):
        m = Material.objects.create(nome_material=f"Material {i}", tipo_material=tipo)
        EstoqueMaterial.objects.create(
            material=m, descricao_local="Galpão", quantidade=10 + i, estoque_minimo=5,
            preco_fornecedor=Decimal("10.00"),
        )

    produto = ProdutoInterno.objects.create(nome="Máquina de teste")
    for n in range(1, 5):
        GuiaEtapaProducao.objects.create(produto=produto, ordem=n, titulo=f"Etapa {n}", instrucoes="Faça.")
    for _ in range(10):
        ordem = OrdemProducao.objects.create(produto=produto, quantidade=1)
        ordem.preparar_etapas()

    for n in range(1, 13):
        criar_colaborador(n, usuario=producao if n == 1 else None)

    # a lista de montagem se acerta ao abrir (aprovados viram máquinas)
    from sistema_interno import montagem

    montagem.sincronizar_tudo()
    return {"dono": dono, "gestora": gestora, "vendedor": vendedor, "producao": producao}


# ----------------------------------------------------------------------
# A medida
# ----------------------------------------------------------------------
class Medida:
    def __init__(self, latencia_ms, conferencia):
        self.latencia_ms = latencia_ms
        self.conferencia = conferencia
        self.linhas = []

    @staticmethod
    def viagens(capturadas):
        total = 0
        begins = 0
        for consulta in capturadas:
            sql = (consulta.get("sql") or "").strip().upper()
            total += 1
            if sql == "BEGIN" or sql.startswith("BEGIN "):
                begins += 1
        return total + begins, begins

    def pedir(self, cliente, metodo, caminho, dados=None, cabecalhos=None, conferir=True):
        cabecalhos = dict(cabecalhos or {})
        funcao = getattr(cliente, metodo.lower())
        with CaptureQueriesContext(connection) as capturadas:
            inicio = time.perf_counter()
            if metodo == "POST":
                resposta = funcao(caminho, dados or {}, HTTP_HOST=HOST, **cabecalhos)
            else:
                resposta = funcao(caminho, dados or {}, HTTP_HOST=HOST, **cabecalhos)
            ms = (time.perf_counter() - inicio) * 1000
        viagens, begins = self.viagens(capturadas.captured_queries)
        if self.conferencia == "antes" or (self.conferencia == "agora" and conferir):
            viagens += 1
        return resposta, {
            "metodo": metodo, "caminho": caminho, "status": resposta.status_code,
            "consultas": len(capturadas), "viagens": viagens, "transacoes": begins,
            "savepoints": sum(1 for q in capturadas.captured_queries if q["sql"].upper().startswith("SAVEPOINT")),
            "cpu_ms": ms, "sql": [q["sql"] for q in capturadas.captured_queries],
        }

    def acao(self, rotulo, passos, detalhe=None):
        """`passos`: [(cliente, metodo, caminho, dados, cabecalhos, papel)] -- a ação e o que vem depois."""
        pedidos = []
        resposta_acao = None
        for cliente, metodo, caminho, dados, cabecalhos, papel in passos:
            if callable(dados):
                dados = dados(resposta_acao)
            if callable(caminho):
                caminho = caminho(resposta_acao)
            resposta, linha = self.pedir(cliente, metodo, caminho, dados, cabecalhos, conferir=papel == "acao")
            linha["papel"] = papel
            if papel == "acao":
                resposta_acao = resposta
                if resposta.status_code >= 400 or (
                    "json" in resposta.get("Content-Type", "") and resposta.json().get("status") == "erro"
                ):
                    corpo = resposta.content[:300].decode("utf-8", "replace")
                    print(f"  !! {rotulo}: {resposta.status_code} {corpo}", file=sys.stderr)
            pedidos.append(linha)
        total_viagens = sum(p["viagens"] for p in pedidos)
        cpu = sum(p["cpu_ms"] for p in pedidos)
        # O que a pessoa espera: a ação e, depois dela, a tela (ou a lista)
        # nova -- a tarja "Atualizando a lista…" sai quando ela chega. O sino
        # vai em paralelo e não segura a tarja; aparece à parte.
        def segundos(p):
            return p["cpu_ms"] + p["viagens"] * self.latencia_ms

        acao = [p for p in pedidos if p["papel"] == "acao"]
        depois = [p for p in pedidos if p["papel"] in ("tela", "lista")]
        espera = sum(segundos(p) for p in acao)
        if depois:
            espera += max(segundos(p) for p in depois)
        self.linhas.append({
            "acao": rotulo, "pedidos": pedidos, "viagens": total_viagens, "cpu_ms": cpu,
            "segundos_no_ar": espera / 1000,
            "segundos_em_serie": (cpu + total_viagens * self.latencia_ms) / 1000,
        })
        if detalhe and re.search(detalhe, rotulo, re.I):
            for p in pedidos:
                print(f"\n--- {rotulo} | {p['papel']} {p['metodo']} {p['caminho']} -> {p['status']}: "
                      f"{p['consultas']} consultas, {p['viagens']} viagens")
                for sql in p["sql"]:
                    print("   ", sql[:220])
        return resposta_acao

    def imprimir(self):
        print(f"\n{'ação':46} {'viagens':>7} {'cpu ms':>7} {'espera (s)':>10}  viagens por pedido")
        for linha in self.linhas:
            partes = " + ".join(f"{p['papel']}:{p['viagens']}" for p in linha["pedidos"])
            print(f"{linha['acao'][:46]:46} {linha['viagens']:>7} "
                  f"{linha['cpu_ms']:>7.0f} {linha['segundos_no_ar']:>10.2f}  {partes}")


def roteiro(m, contas, detalhe=None):
    """Cada ação com o que o navegador pede logo depois (conferido com a aba Rede, LEIA-ME §120).

    * Orçamentos: salvar e mudar a situação trocam só a LISTA (`partes: true`
      em orcamentos_inner.html); as outras telas trocam a tela inteira
      (`LSAtualizarTela()`); a produção por etapa é um formulário comum
      (POST -> 302 -> a página de novo).
    * Toda gravação pede o sino junto (`Painel.confirmarGravacao`).
    """
    from core.models import Brinquedos, PecasReposicao
    from rh.models import Tarefa
    from sistema_interno.models import (
        Cliente, EstoqueMaterial, ExecucaoEtapaProducao, ItemOrcamento, Orcamento, OrdemProducao,
        OrdemServico, UnidadeMontagem,
    )

    dono = Client()
    dono.force_login(contas["dono"])
    gestora = Client()
    gestora.force_login(contas["gestora"])
    montador = Client()
    montador.force_login(contas["producao"])

    def json_id(resposta):
        try:
            return resposta.json().get("id")
        except Exception:  # noqa: BLE001
            return None

    for c in (dono, gestora, montador):  # aquece templates e caches de processo
        c.get("/", HTTP_HOST=HOST)
        c.get("/orcamentos/", HTTP_HOST=HOST)
        c.get("/avisos/estado/", HTTP_HOST=HOST, **JSON)

    def sino(c):
        return (c, "GET", "/avisos/estado/", None, JSON, "sino")

    def tela(c, caminho):
        return (c, "GET", caminho, None, NAVEGACAO, "tela")

    def lista(c, caminho):
        return (c, "GET", caminho, None, PEDACO, "lista")

    def abrir(c, caminho):
        return (c, "GET", caminho, None, NAVEGACAO, "acao")

    def post(c, caminho, dados, cabecalhos=JSON):
        return (c, "POST", caminho, dados, cabecalhos, "acao")

    # ------------------------------------------------------------ telas
    for nome, c in (("dono", dono), ("gestora", gestora)):
        m.acao(f"[{nome}] Abrir Início", [abrir(c, "/"), sino(c)], detalhe)
        m.acao(f"[{nome}] Abrir Orçamentos", [abrir(c, "/orcamentos/"), sino(c)], detalhe)
        # o pulso de 12 s: o navegador manda o ETag da última resposta, e o
        # resumo do pulso (1 s no cache) já venceu
        etag = c.get("/avisos/estado/", HTTP_HOST=HOST, **JSON).get("ETag", "")
        cache.delete("interno:pulso:v1")
        m.acao(f"[{nome}] Sino (a cada 12 s, nada mudou)", [
            (c, "GET", "/avisos/estado/", None, {**JSON, "HTTP_IF_NONE_MATCH": etag}, "acao"),
        ], detalhe)

    # o sino conta ao servidor o que ele acabou de mostrar (a cada número novo)
    vistos = {chave: 10 + i for i, chave in enumerate((
        "orcamentos_em_aberto", "orcamentos_vencidos", "orcamentos_vencendo", "orcamentos_aprovados",
        "clientes_incompletos", "pedidos", "ordens_servico", "estoque",
    ))}
    for rodada in (1, 2):
        m.acao(f"Sino: guardar o que mostrou ({rodada}ª vez)", [
            post(dono, "/avisos/estado/", {"acao": "avisos_vistos", "vistos": json.dumps(
                {k: v + rodada for k, v in vistos.items()})}),
        ], detalhe)

    brinquedo = Brinquedos.objects.order_by("pk").first()
    cliente_obj = Cliente.objects.order_by("pk").first()

    def itens(n):
        return json.dumps([
            {"descricao": f"Item {j}", "brinquedo": str(brinquedo.pk), "quantidade": "1", "valor_unitario": "300,00"}
            for j in range(n)
        ])

    c = dono
    # ------------------------------------------------------- Orçamentos
    r = m.acao("Orçamentos: salvar novo", [
        post(c, "/orcamentos/", {
            "action": "save", "cliente": str(cliente_obj.pk), "nome_cliente": cliente_obj.nome_cliente,
            "contato": "11999990000", "itens": itens(3), "desconto": "", "frete": "", "valor_final": "",
        }),
        lista(c, "/orcamentos/"), sino(c),
    ], detalhe)
    novo_id = json_id(r)
    m.acao("Orçamentos: abrir a janela (régua)", [(c, "GET", f"/orcamentos/{novo_id}/etapas/", None, JSON, "acao")], detalhe)

    def editar(n):
        o = Orcamento.objects.get(pk=novo_id)
        return {
            "action": "save", "id": str(o.pk), "revisao": o.atualizado.isoformat(),
            "cliente": str(cliente_obj.pk), "nome_cliente": cliente_obj.nome_cliente,
            "contato": "11999990000", "itens": itens(n), "desconto": "", "frete": "", "valor_final": "",
        }

    # a proposta salva fica "aguardando resposta"; volta a rascunho para ser editada como na tela
    Orcamento.objects.filter(pk=novo_id).update(status=Orcamento.Status.RASCUNHO)
    m.acao("Orçamentos: editar (adicionar item)", [
        (c, "POST", "/orcamentos/", lambda _r: editar(4), JSON, "acao"), lista(c, "/orcamentos/"), sino(c),
    ], detalhe)
    Orcamento.objects.filter(pk=novo_id).update(status=Orcamento.Status.RASCUNHO)
    m.acao("Orçamentos: editar (remover item)", [
        (c, "POST", "/orcamentos/", lambda _r: editar(2), JSON, "acao"), lista(c, "/orcamentos/"), sino(c),
    ], detalhe)
    m.acao("Orçamentos: mudar situação (negociação)", [
        post(c, "/orcamentos/", {"action": "status", "id": str(novo_id), "status": "em_negociacao"}),
        lista(c, "/orcamentos/"), sino(c),
    ], detalhe)
    m.acao("Orçamentos: aprovar", [
        post(c, "/orcamentos/", {"action": "status", "id": str(novo_id), "status": "aprovado"}),
        lista(c, "/orcamentos/"), sino(c),
    ], detalhe)
    m.acao("Orçamentos: registrar pagamento", [
        post(c, "/orcamentos/", {"action": "pagamento", "id": str(novo_id), "valor_pago": "100,00"}),
        tela(c, "/orcamentos/"), sino(c),
    ], detalhe)
    rascunho = Orcamento.objects.create(nome_cliente="Rascunho a excluir", responsavel=contas["dono"])
    ItemOrcamento.objects.create(orcamento=rascunho, descricao="Item", quantidade=1, valor_unitario=Decimal("1.00"))
    m.acao("Orçamentos: excluir rascunho", [
        post(c, "/orcamentos/", {"action": "delete", "id": str(rascunho.pk), "confirmacao_exclusao": "CONFIRMAR"}),
        tela(c, "/orcamentos/"), sino(c),
    ], detalhe)

    # --------------------------------------------------------- Clientes
    m.acao("Clientes: abrir", [abrir(c, "/clientes/"), sino(c)], detalhe)
    cliente_novo = {
        "action": "save", "nome_cliente": "Cliente medido", "telefone": "11988887777",
        "canal_telefone": "whatsapp", "tipo": "residencial", "email": "medido@exemplo.invalid",
        "endereco": "Rua A", "numero": "1", "cidade": "São Paulo", "estado": "SP", "cep": "",
    }
    r = m.acao("Clientes: salvar novo", [post(c, "/clientes/", cliente_novo), tela(c, "/clientes/"), sino(c)], detalhe)
    cid = json_id(r)
    m.acao("Clientes: editar", [
        post(c, "/clientes/", {**cliente_novo, "id": str(cid), "telefone": "11988886666"}), tela(c, "/clientes/"), sino(c),
    ], detalhe)
    m.acao("Clientes: excluir", [
        post(c, "/clientes/", {"action": "delete", "id": str(cid), "confirmacao_exclusao": "CONFIRMAR"}),
        tela(c, "/clientes/"), sino(c),
    ], detalhe)

    # ----------------------------------------------------------- O.S.
    m.acao("O.S.: abrir", [abrir(c, "/ordens-servico/"), sino(c)], detalhe)
    os_dados = {
        "action": "save", "tipo": "manutencao", "status": "rascunho", "prioridade": "normal",
        "cliente": str(cliente_obj.pk), "equipamento": "Tobogã medido",
        "itens": json.dumps([{"tipo": "servico", "descricao": "Reparo", "quantidade": "1", "valor_unitario": "120,00"}]),
    }
    r = m.acao("O.S.: salvar nova", [post(c, "/ordens-servico/", os_dados), tela(c, "/ordens-servico/"), sino(c)], detalhe)
    os_id = json_id(r)

    def os_editar(_r):
        o = OrdemServico.objects.get(pk=os_id)
        return {**os_dados, "id": str(o.pk), "revisao": o.atualizado.isoformat()}

    m.acao("O.S.: editar", [
        (c, "POST", "/ordens-servico/", os_editar, JSON, "acao"), tela(c, "/ordens-servico/"), sino(c),
    ], detalhe)

    # ------------------------------------------------ Produção / montagem
    g = gestora
    m.acao("Lista de montagem: abrir", [abrir(g, "/producao/montagem/"), sino(g)], detalhe)
    unidade = UnidadeMontagem.objects.filter(situacao=UnidadeMontagem.Situacao.PRODUCAO).order_by("pk").first()
    if unidade is not None:
        m.acao("Lista de montagem: marcar etapa", [
            post(g, "/producao/montagem/", {"action": "etapa", "id": str(unidade.pk), "etapa": "corte"}),
            tela(g, "/producao/montagem/"), sino(g),
        ], detalhe)
    ordem = OrdemProducao.objects.order_by("pk").first()
    etapa = ExecucaoEtapaProducao.objects.filter(ordem_producao=ordem).order_by("guia_etapa__ordem").first()
    p = montador
    m.acao("Produção: abrir a ordem", [abrir(p, f"/producao/ordens/{ordem.pk}/"), sino(p)], detalhe)
    m.acao("Produção: avançar etapa (iniciar)", [
        (p, "POST", f"/producao/ordens/{ordem.pk}/etapas/{etapa.pk}/", {"acao": "iniciar"}, {}, "acao"),
        (p, "GET", f"/producao/ordens/{ordem.pk}/", None, {}, "tela"), sino(p),
    ], detalhe)
    m.acao("Produção: minha produção (montador)", [abrir(p, "/producao/"), sino(p)], detalhe)

    # --------------------------------------------------------- Estoque
    m.acao("Estoque: abrir", [abrir(c, "/estoque/"), sino(c)], detalhe)
    est = EstoqueMaterial.objects.order_by("pk").first()
    m.acao("Estoque: entrada de material", [
        post(c, "/estoque/", {"action": "movimento", "id": str(est.pk), "tipo": "entrada", "quantidade": "2",
                              "motivo": "Compra", "valor_unitario": "10,00"}),
        tela(c, "/estoque/"), sino(c),
    ], detalhe)
    m.acao("Notas de entrada: abrir", [abrir(c, "/estoque/notas/"), sino(c)], detalhe)

    # ---------------------------------------------------- Catálogo (site)
    m.acao("Brinquedos: abrir", [abrir(c, "/site/brinquedos/"), sino(c)], detalhe)
    m.acao("Peças: abrir", [abrir(c, "/site/pecas/"), sino(c)], detalhe)
    peca = PecasReposicao.objects.order_by("pk").first()
    m.acao("Peças: ativar/desativar", [
        post(c, "/site/pecas/", {"action": "alternar_ativo", "id": str(peca.pk)}), tela(c, "/site/pecas/"), sino(c),
    ], detalhe)
    m.acao("Peças: salvar", [
        post(c, "/site/pecas/", {"action": "save", "id": str(peca.pk), "nome": peca.nome, "descricao_peca": "Reposição",
                                 "preco_venda": "15,00", "preco_fornecedor": "8,00", "ativo": "1"}),
        tela(c, "/site/pecas/"), sino(c),
    ], detalhe)

    # -------------------------------------------------------------- RH
    m.acao("RH: colaboradores", [abrir(c, "/rh/colaboradores/"), sino(c)], detalhe)
    m.acao("RH: tarefas", [abrir(c, "/rh/tarefas/"), sino(c)], detalhe)
    m.acao("RH: meu ponto (montador)", [abrir(p, "/rh/ponto/"), sino(p)], detalhe)
    m.acao("RH: marcar o ponto (montador)", [post(p, "/rh/ponto/marcar/", {}), sino(p)], detalhe)
    tarefa = Tarefa.objects.order_by("pk").first()
    if tarefa is not None:
        m.acao("RH: mudar a tarefa", [
            post(c, f"/rh/tarefas/{tarefa.pk}/situacao/", {"situacao": "fazendo"}), tela(c, "/rh/tarefas/"), sino(c),
        ], detalhe)

    # ------------------------------------------------- Usuários / funções
    m.acao("Usuários/funções: abrir", [abrir(c, "/equipe/"), sino(c)], detalhe)
    vendedor = contas["vendedor"]
    m.acao("Usuários/funções: salvar", [
        post(c, "/equipe/", {"action": "save", "id": str(vendedor.pk), "username": vendedor.username,
                             "email": vendedor.email, "first_name": "Vendedor", "is_active": "on",
                             "funcoes": ["vendas", "ambulante"]}),
        tela(c, "/equipe/"), sino(c),
    ], detalhe)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--latencia", type=float, default=170.0, help="ms por viagem ao banco (padrão 170)")
    parser.add_argument(
        "--conferencia", choices=("antes", "agora", "nenhuma"), default="agora",
        help="o SELECT 1 da conexão: 'antes' = em toda requisição (o código de antes); "
             "'agora' = só na ação, não nos pedidos que vêm logo atrás (lazer/banco_postgres)",
    )
    parser.add_argument("--detalhe", default=None, help="expressão: imprime o SQL das ações que casarem")
    parser.add_argument("--json", default=None, help="grava o resultado em JSON")
    args = parser.parse_args()

    setup_test_environment()
    settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + [HOST, "testserver"]
    connection.creation.create_test_db(verbosity=0, autoclobber=True, keepdb=False)
    cache.clear()
    contas = povoar()
    cache.clear()
    m = Medida(args.latencia, args.conferencia)
    roteiro(m, contas, args.detalhe)
    m.imprimir()
    if args.json:
        with open(args.json, "w", encoding="utf-8") as saida:
            json.dump(m.linhas, saida, ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main()
