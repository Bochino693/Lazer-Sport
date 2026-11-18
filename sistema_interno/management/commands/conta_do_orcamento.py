"""A conta do site de um orçamento: ver, desfazer ou passar para outra.

O pedido (LEIA-ME-V10, seção 104): o cliente digita o código em Meus
pedidos e acompanha a proposta "sem necessidade de contato". Quando o
código cai na conta errada (foi repassado, a pessoa criou duas contas), o
site não troca de dono sozinho -- diz "fale com a equipe". É aqui que a
equipe resolve, enquanto a janela do orçamento no painel não ganha o botão.

    python manage.py conta_do_orcamento LS-7K3QX9
    python manage.py conta_do_orcamento LS-7K3QX9 --desvincular
    python manage.py conta_do_orcamento LS-7K3QX9 --para fulano

Vale para a negociação inteira (todas as versões), como o vínculo.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from sistema_interno.codigo_orcamento import normalizar, versao_mais_nova
from sistema_interno.models import Orcamento


class Command(BaseCommand):
    help = "Mostra, desfaz ou troca a conta do site que acompanha um orçamento (pelo código)."

    def add_arguments(self, parser):
        parser.add_argument("codigo", help="O código do orçamento (LS-...).")
        grupo = parser.add_mutually_exclusive_group()
        grupo.add_argument("--desvincular", action="store_true", help="Tira a conta de todas as versões.")
        grupo.add_argument("--para", metavar="USUARIO", help="Passa todas as versões para esta conta (o login).")

    def handle(self, *args, **opcoes):
        codigo = normalizar(opcoes["codigo"])
        orcamento = Orcamento.objects.filter(codigo=codigo).first() if codigo else None
        if orcamento is None:
            raise CommandError(f"Nenhum orçamento com o código {opcoes['codigo']!r}.")
        mais_nova = versao_mais_nova(orcamento)
        cadeia = mais_nova.cadeia_de_versoes()
        ids = [versao.pk for versao in cadeia]

        for versao in cadeia:
            conta = f"@{versao.conta.get_username()}" if versao.conta_id else "sem conta"
            self.stdout.write(f"#{versao.pk} v{versao.versao} {versao.codigo} · {versao.get_status_display()} · {conta}")

        if opcoes["desvincular"]:
            with transaction.atomic():
                Orcamento.objects.filter(pk__in=ids).update(conta=None, vinculado_em=None)
            self.stdout.write(self.style.SUCCESS(f"{len(ids)} versão(ões) sem conta do site."))
        elif opcoes["para"]:
            usuario = get_user_model().objects.filter(username=opcoes["para"]).first()
            if usuario is None:
                raise CommandError(f"Nenhuma conta com o login {opcoes['para']!r}.")
            with transaction.atomic():
                Orcamento.objects.filter(pk__in=ids).update(conta=usuario, vinculado_em=timezone.now())
            self.stdout.write(self.style.SUCCESS(f"{len(ids)} versão(ões) na conta @{usuario.get_username()}."))
