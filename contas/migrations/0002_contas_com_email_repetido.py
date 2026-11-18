"""Resolve as contas que já têm o mesmo e-mail (só dados).

O QUE ACONTECE NO AR. Para cada endereço que aparece em mais de uma conta
-- como e-mail principal (auth_user) ou endereço do allauth
(account_emailaddress), comparado sem diferença de maiúsculas, espaços,
caracteres invisíveis, ponto final do domínio ou variante Unicode (NFKC) --
UMA conta fica com ele, a canônica, escolhida sempre do mesmo jeito:

  1. superusuário, depois staff, depois conta com função de equipe no
     painel ("Equipe · ..."), depois cliente;
  2. entre iguais, a que tem esse endereço CONFIRMADO no allauth;
  3. depois, a mais antiga (date_joined) e, no empate, o menor id.

As outras são BLOQUEADAS, cada uma na sua transação:

  * `is_active = False` (a sessão e o token do aplicativo param de valer);
  * o e-mail principal esvaziado, se era ele o repetido;
  * os endereços do allauth com aquele e-mail apagados;
  * uma OcorrenciaSeguranca "E-mail repetido" com o endereço que a conta
    tinha e a conta que ficou com ele -- é a lista que a tela "Segurança
    das contas" (interno.) mostra para o dono reativar ou manter bloqueada.

Depois, todo e-mail que sobrou é regravado na forma normalizada (minúsculas,
NFKC, sem espaço), nas contas e nos endereços do allauth -- é o que deixa o
índice único da 0003 (lower(email)) valer pela mesma regra das telas. Dois
endereços do allauth da MESMA conta que viram o mesmo são juntados num só
(confirmado se qualquer um era; principal se qualquer um era).

Rodar de novo não muda nada. Não tem volta automática: as ocorrências
guardam o e-mail que cada conta bloqueada tinha.

`atomic = False`: cada conta resolvida é confirmada no banco na hora. Se
algo falhar no meio, o que já foi feito está certo e rodar de novo continua
do ponto em que parou.
"""

import unicodedata
from collections import defaultdict

from django.db import migrations, transaction

#: Os grupos das funções do painel (sistema_interno/permissoes.py), copiados
#: aqui: a migração não pode mudar de comportamento se o código mudar.
GRUPOS_DA_EQUIPE = (
    "Equipe · Produção",
    "Equipe · Criação do site",
    "Equipe · Vendas",
    "Equipe · Vendedor ambulante",
    "Equipe · Financeiro",
    "Equipe · Gestão",
)

_INVISIVEIS = {"Cf", "Cc", "Zs", "Zl", "Zp"}


def normalizar(valor):
    """A mesma regra de contas/emails.py (copiada: migração é congelada)."""
    texto = unicodedata.normalize("NFKC", str(valor or ""))
    texto = "".join(
        c for c in texto
        if not c.isspace() and unicodedata.category(c) not in _INVISIVEIS
    )
    texto = unicodedata.normalize("NFKC", texto.lower())
    if "@" in texto:
        local, _, dominio = texto.rpartition("@")
        texto = f"{local}@{dominio.rstrip('.')}"
    return texto


def _nivel(conta, equipe):
    if conta.is_superuser:
        return 0
    if conta.is_staff:
        return 1
    if conta.pk in equipe:
        return 2
    return 3


def resolver(apps, schema_editor=None):
    User = apps.get_model("auth", "User")
    EmailAddress = apps.get_model("account", "EmailAddress")
    Ocorrencia = apps.get_model("contas", "OcorrenciaSeguranca")

    donos = defaultdict(set)
    for pk, email in User.objects.values_list("pk", "email"):
        chave = normalizar(email)
        if chave:
            donos[chave].add(pk)
    confirmados = defaultdict(set)
    for user_id, email, verificado in EmailAddress.objects.values_list("user_id", "email", "verified"):
        chave = normalizar(email)
        if chave:
            donos[chave].add(user_id)
            if verificado:
                confirmados[chave].add(user_id)

    equipe = set(
        User.groups.through.objects
        .filter(group__name__in=GRUPOS_DA_EQUIPE)
        .values_list("user_id", flat=True)
    )

    bloqueadas = set()
    for chave in sorted(c for c, ids in donos.items() if len(ids) > 1):
        contas = list(User.objects.filter(pk__in=donos[chave]))
        contas.sort(key=lambda conta: (
            conta.pk in bloqueadas,
            _nivel(conta, equipe),
            conta.pk not in confirmados[chave],
            conta.date_joined,
            conta.pk,
        ))
        canonica = contas[0]
        for conta in contas[1:]:
            with transaction.atomic():
                _bloquear(User, EmailAddress, Ocorrencia, conta, chave, canonica)
            bloqueadas.add(conta.pk)

    _normalizar_o_que_ficou(User, EmailAddress)


def _bloquear(User, EmailAddress, Ocorrencia, conta, chave, canonica):
    conta = User.objects.select_for_update().get(pk=conta.pk)
    principal = normalizar(conta.email) == chave
    original = conta.email if principal else ""

    for endereco in EmailAddress.objects.filter(user_id=conta.pk):
        if normalizar(endereco.email) == chave:
            original = original or endereco.email
            endereco.delete()

    campos = {"is_active": False}
    if principal:
        campos["email"] = ""
    User.objects.filter(pk=conta.pk).update(**campos)

    if principal:
        como = "como e-mail principal"
    else:
        como = "como endereço extra (allauth)"
    Ocorrencia.objects.create(
        tipo="email_repetido",
        situacao="pendente",
        usuario_id=conta.pk,
        conta_mantida_id=canonica.pk,
        username=(conta.username or "")[:150],
        email_original=(original or chave)[:254],
        origem="migracao",
        motivo=(
            f"O mesmo e-mail estava {como} nesta conta e na conta #{canonica.pk} "
            f"(@{canonica.username}), que ficou com ele. Esta foi bloqueada: "
            "inativa e sem o e-mail. Reative só se a conta for legítima -- ela "
            "volta sem e-mail, e um endereço novo precisa ser cadastrado."
        ),
    )


def _normalizar_o_que_ficou(User, EmailAddress):
    for pk, email in User.objects.exclude(email="").values_list("pk", "email"):
        chave = normalizar(email)
        if chave != email:
            with transaction.atomic():
                User.objects.filter(pk=pk).update(email=chave)

    por_conta = defaultdict(lambda: defaultdict(list))
    for endereco in EmailAddress.objects.order_by("pk"):
        por_conta[endereco.user_id][normalizar(endereco.email)].append(endereco)

    for grupos in por_conta.values():
        for chave, enderecos in grupos.items():
            if len(enderecos) == 1 and enderecos[0].email == chave:
                continue
            with transaction.atomic():
                enderecos.sort(key=lambda e: (not e.verified, not e.primary, e.pk))
                fica, sobram = enderecos[0], enderecos[1:]
                verificado = any(e.verified for e in enderecos)
                principal = any(e.primary for e in enderecos)
                for endereco in sobram:
                    endereco.delete()
                EmailAddress.objects.filter(pk=fica.pk).update(
                    email=chave, verified=verificado, primary=principal,
                )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("contas", "0001_ocorrencia_seguranca"),
        ("account", "0009_emailaddress_unique_primary_email"),
        ("auth", "0012_alter_user_first_name_max_length"),
        # Os gatilhos de e-mail por escopo já estão no banco: o que esta
        # migração grava passa por eles, e eles concordam.
        ("sistema_interno", "0047_email_por_escopo"),
    ]

    operations = [migrations.RunPython(resolver, migrations.RunPython.noop)]
