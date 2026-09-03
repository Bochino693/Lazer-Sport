"""Migração de dados não anda junto com migração de esquema.

POR QUE ESTE TESTE EXISTE. A migração que unificou o cadastro de cliente
passou nos testes, passou num ensaio com dados de verdade em SQLite, foi
para o `main` — e morreu no primeiro `migrate` do servidor:

    cannot ALTER TABLE "sistema_interno_cliente"
    because it has pending trigger events
    cannot CREATE INDEX "sistema_interno_cliente"
    because it has pending trigger events

São duas coisas se somando. O Postgres adia a checagem das chaves
estrangeiras até o fim da transação: escrever linhas que mexem numa coluna
de chave estrangeira deixa gatilhos PENDENTES. E o Django adia a criação
de índice para o fim da migração. Resultado: num arquivo que grava dados e
mexe no esquema, o `CREATE INDEX` e o `ALTER TABLE` caem depois das
linhas, na mesma transação, e o banco recusa.

O teste roda em SQLite, que não adia nada disso e nunca reproduz o erro.
Por isso a trava não tenta EXECUTAR a migração: ela lê os arquivos e
reprova a forma. Migração de dados fica no seu próprio arquivo; cada uma
roda na sua transação, e é isso que faz os gatilhos dispararem entre uma e
outra.
"""

import ast
import io
from pathlib import Path

from django.test import SimpleTestCase


OPERACOES_DE_ESQUEMA = {
    "CreateModel", "DeleteModel", "AddField", "RemoveField", "AlterField",
    "RenameField", "RenameModel", "AddIndex", "RemoveIndex",
    "AddConstraint", "RemoveConstraint", "AlterUniqueTogether",
    "AlterIndexTogether", "AlterModelTable", "AlterOrderWithRespectTo",
}
OPERACOES_DE_DADOS = {"RunPython", "RunSQL"}

#: História já aplicada em produção, que não dá para reescrever.
#:
#: Todas gravam dados sem tocar em coluna de chave estrangeira -- um
#: `UPDATE` que só preenche uma coluna nova não enfileira gatilho nenhum,
#: e por isso passaram. Ficam registradas aqui como exceção conhecida, e
#: não como permissão: arquivo novo não entra nesta lista.
HERANCA = {
    "core/0098_galerias_ordenadas_catalogo",
    "core/0099_imagembrinquedo_tipo",
    "core/0103_cupom_data_expiracao_cupom_reutilizavel_and_more",
    "sistema_interno/0011_orcamento_token_resposta_item_brinquedo",
    "sistema_interno/0014_cliente_telefone_digitos",
    # Esta não grava linha nenhuma: a parte "de dados" é um DDL --
    # soltar, no PostgreSQL, a checagem antiga de quantidade antes de o
    # `AlterField` recriá-la. DDL não enfileira gatilho de chave
    # estrangeira, que é o que este teste protege, e separar as duas
    # operações faria o `AlterField` rodar de novo num servidor onde a
    # migração já passou -- justamente o erro de constraint duplicada
    # que ela existe para evitar.
    "sistema_interno/0039_item_os_quantidade_inteira_esquema",
}

RAIZ = Path(__file__).resolve().parent.parent


class MigracoesTests(SimpleTestCase):

    def _migracoes(self):
        for app in ("core", "sistema_interno"):
            pasta = RAIZ / app / "migrations"
            for arquivo in sorted(pasta.glob("0*.py")):
                yield app, arquivo

    def test_dados_e_esquema_nao_moram_no_mesmo_arquivo(self):
        misturadas = []

        for app, arquivo in self._migracoes():
            identidade = f"{app}/{arquivo.stem}"
            if identidade in HERANCA:
                continue

            arvore = ast.parse(io.open(arquivo, encoding="utf-8").read())
            usados = {
                no.attr for no in ast.walk(arvore) if isinstance(no, ast.Attribute)
            }
            esquema = usados & OPERACOES_DE_ESQUEMA
            dados = usados & OPERACOES_DE_DADOS

            if esquema and dados:
                misturadas.append(
                    f"{identidade}: esquema={sorted(esquema)} dados={sorted(dados)}"
                )

        self.assertEqual(
            misturadas,
            [],
            "Migração de dados no mesmo arquivo que mudança de esquema. No "
            "Postgres isso estoura com 'pending trigger events' -- e o SQLite "
            "dos testes não reproduz. Separe em dois arquivos:\n  "
            + "\n  ".join(misturadas),
        )

    def test_a_lista_de_heranca_nao_cresceu_com_arquivo_que_sumiu(self):
        """Entrada morta na lista esconde a trava do arquivo que a substituiu."""
        existentes = {f"{app}/{arq.stem}" for app, arq in self._migracoes()}
        sumidas = sorted(HERANCA - existentes)

        self.assertEqual(
            sumidas,
            [],
            "A lista de herança cita migração que não existe mais: " + ", ".join(sumidas),
        )
