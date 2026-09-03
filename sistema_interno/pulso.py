"""O relógio comum do sino: mudou alguma coisa, para QUALQUER pessoa?

POR QUE ISSO PRECISOU EXISTIR.

A central de avisos custa uma dúzia de consultas, então o resultado ficava
guardado por 45 segundos. Guardado ONDE é que era o problema:

  * o cache é `LocMemCache` -- memória do processo. No servidor há vários
    workers, e cada um tem o seu. Dois pedidos seguidos do mesmo navegador
    caem em workers diferentes e recebem fotografias diferentes: é isso, e
    não um erro de contagem, que faz o número ir de 22 para 19 e voltar
    para 22 ao abrir o sino;

  * a chave era por USUÁRIO, e só quem gravava limpava a sua. Quem
    cadastrava um cliente incompleto via na hora. Todos os outros -- que
    são justamente quem precisa ser avisado -- continuavam com o número
    velho até os 45 segundos vencerem, no worker deles, um por um. Somando
    a sondagem da tela, passava de um minuto e meio;

  * e o HTML da página e o endereço de avisos guardavam o mesmo número em
    DUAS chaves diferentes, cada uma com o seu prazo. Hoje as bolinhas do
    painel são preenchidas pelo JavaScript, então isso não aparecia ali --
    mas eram duas fotografias independentes da mesma coisa, esperando
    para divergir na primeira tela que imprimisse o número direto.

A CORREÇÃO NÃO É UM CACHE MENOR, É OUTRA CHAVE.

Aqui se lê do BANCO um resumo minúsculo de tudo que o sino conta. O banco
é o único lugar que todos os workers enxergam igual. Enquanto esse resumo
não muda, ninguém recalcula nada; assim que qualquer pessoa cadastra,
altera ou apaga qualquer coisa, ele muda -- e muda para TODO MUNDO ao
mesmo tempo. O próximo pulso de cada painel aberto já traz o número novo,
sem recarregar a página e sem depender de quem fez a ação.

O CUSTO, QUE É O MOTIVO DE O RESUMO SER PEQUENO.

  * uma viagem só ao banco, não uma por tabela: as somas vão juntas num
    `UNION ALL`;
  * `COUNT` mais `MAX(atualizado)` por tabela. O MAX pega o que nasceu e o
    que mudou; o COUNT pega o que foi apagado, que nenhum dos dois MAX
    enxerga -- e um aviso que some é tão importante quanto um que chega;
  * o resultado fica guardado por poucos segundos. Dez painéis abertos
    perguntando ao mesmo tempo custam uma consulta, não dez.

Os nomes de tabela e de coluna saem do `_meta` de cada modelo, e não
escritos à mão: renomear um campo continua funcionando, e um modelo que
saia do projeto quebra na importação em vez de silenciosamente parar de
avisar.
"""

import hashlib

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, connection
from django.db.models.signals import post_delete, post_save

from core.models import Manutencao, Pedido, Venda

from .models import (
    AtividadeOrcamento,
    Cliente,
    EstoqueMaterial,
    Orcamento,
    OrdemProducao,
    OrdemServico,
)

#: Tudo que a central de avisos olha. Se um aviso novo passar a depender de
#: outra tabela, ela entra aqui -- senão o aviso nasce mudo para quem não
#: fez a ação, que é o defeito que este módulo existe para não repetir.
FONTES = (
    (Orcamento, "atualizado"),
    (AtividadeOrcamento, "atualizado"),
    (OrdemServico, "atualizado"),
    (OrdemProducao, "atualizado"),
    (Cliente, "atualizado"),
    (EstoqueMaterial, "atualizado"),
    (Manutencao, "atualizada_em"),
    (Pedido, "atualizado"),
    (Venda, "atualizado"),
)

#: Segundos que o resumo vale.
#:
#: É o atraso máximo entre a gravação de uma pessoa e o número mudar na
#: tela das outras -- somado ao intervalo da sondagem. Curto de propósito:
#: o que este prazo economiza é UMA consulta barata; o que ele custa é o
#: aviso chegar tarde, e chegar tarde é o defeito que estamos consertando.
#:
#: Dois segundos existem para o caso real de várias abas perguntarem no
#: mesmo instante -- cinco pessoas com o painel aberto sondam quase em
#: sincronia -- e não para poupar banco ao longo do dia. Abaixo da
#: percepção de quem está olhando a tela.
SEGUNDOS = 2

CHAVE = "interno:pulso:v1"


def _consulta():
    """Uma viagem ao banco para todas as tabelas.

    Cada trecho leva o nome da tabela junto. `UNION ALL` não promete
    ordem nenhuma, e sem o nome a leitura seria ordenada de um jeito numa
    consulta e de outro na seguinte: o resumo mudaria sozinho, o cache
    nunca acertaria e a central voltaria a ser recalculada a cada pulso.
    """
    partes = []
    for modelo, campo in FONTES:
        tabela = connection.ops.quote_name(modelo._meta.db_table)
        coluna = connection.ops.quote_name(modelo._meta.get_field(campo).column)
        nome = modelo._meta.db_table.replace("'", "")
        partes.append(
            f"SELECT '{nome}' AS fonte, COUNT(*) AS total, "
            f"MAX({coluna}) AS ultima FROM {tabela}"
        )
    return " UNION ALL ".join(partes)


def _ler_do_banco():
    with connection.cursor() as cursor:
        cursor.execute(_consulta())
        return sorted(cursor.fetchall())


def agora():
    """Um texto curto que muda quando qualquer coisa contada pelo sino muda.

    Nunca levanta: o painel com um resumo velho ainda funciona, e um
    servidor recém-implantado, entre o reinício e o `migrate`, não pode
    responder 502 por causa de uma tabela que ainda não existe.
    """
    guardado = cache.get(CHAVE)
    if guardado:
        return guardado

    try:
        linhas = _ler_do_banco()
    except DatabaseError:
        return ""

    cru = "|".join(f"{fonte}:{total}@{ultima}" for fonte, total, ultima in linhas)
    resumo = hashlib.sha1(cru.encode("utf-8")).hexdigest()[:20]
    try:
        segundos = max(1, int(getattr(settings, "INTERNO_PULSO_SEGUNDOS", SEGUNDOS)))
    except (TypeError, ValueError):
        segundos = SEGUNDOS
    cache.set(CHAVE, resumo, segundos)
    return resumo


def esquecer(**kwargs):
    """Joga fora o resumo guardado. Ligado às gravações deste processo."""
    try:
        cache.delete(CHAVE)
    except Exception:
        # Cache fora do ar não pode derrubar um `save()`. O pior que
        # acontece sem esta linha é o resumo vencer sozinho em segundos.
        pass


def ligar_ouvintes():
    """Gravou aqui, o resumo cai aqui -- na hora.

    O prazo de dois segundos existe para o caso de várias abas
    perguntarem no mesmo instante. Ele não deve valer para quem ACABOU de
    gravar: a pessoa salva um cliente e a tela dela precisa mostrar o
    resultado, não a fotografia de dois segundos atrás.

    Isto cobre o processo que atendeu a gravação. Os outros workers não
    veem sinal nenhum -- sinal não atravessa processo -- e continuam
    dependendo do prazo curto, que é justamente o que ele existe para
    cobrir. Um é instantâneo, os outros levam até dois segundos.

    Chamado uma vez, do `ready()` da aplicação.
    """
    for modelo, _campo in FONTES:
        post_save.connect(
            esquecer, sender=modelo, dispatch_uid=f"pulso:{modelo._meta.label}",
        )
        post_delete.connect(
            esquecer, sender=modelo, dispatch_uid=f"pulso:del:{modelo._meta.label}",
        )
