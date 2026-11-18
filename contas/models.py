"""O registro do que foi barrado, para o dono revisar no painel.

Três coisas viram ocorrência:

  * E-MAIL REPETIDO -- a migração contas/0002 achou duas contas com o mesmo
    endereço (sem diferença de maiúsculas, espaços ou variantes Unicode):
    a conta canônica ficou, a outra foi BLOQUEADA (inativa, sem e-mail) e
    está aqui com o endereço que tinha;
  * LOGIN BLOQUEADO -- senhas erradas demais numa conta ou num IP pausaram
    o acesso (contas/freio.py);
  * LOGIN SOCIAL RECUSADO -- o Google/Apple trouxe o e-mail de uma conta que
    já existe sem garantir que o endereço é da pessoa, ou um endereço da
    própria empresa (contas/adapters.py).

A tela "Segurança das contas" (interno.) lista, e cada uma é resolvida por
alguém: reativar ou manter bloqueada, liberar o login ou só "ciente". Quem
resolveu e quando ficam gravados.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class OcorrenciaSeguranca(models.Model):
    class Tipo(models.TextChoices):
        EMAIL_REPETIDO = "email_repetido", "E-mail repetido"
        LOGIN_BLOQUEADO = "login_bloqueado", "Login bloqueado"
        SOCIAL_RECUSADO = "social_recusado", "Login social recusado"

    class Situacao(models.TextChoices):
        PENDENTE = "pendente", "Esperando revisão"
        REATIVADA = "reativada", "Conta reativada"
        MANTIDA = "mantida", "Mantida bloqueada"
        LIBERADA = "liberada", "Login liberado"
        CIENTE = "ciente", "Revisada"

    tipo = models.CharField("Tipo", max_length=20, choices=Tipo.choices, db_index=True)
    situacao = models.CharField(
        "Situação", max_length=12, choices=Situacao.choices,
        default=Situacao.PENDENTE, db_index=True,
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ocorrencias_de_seguranca", verbose_name="Conta",
    )
    conta_mantida = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", verbose_name="Conta que ficou com o e-mail",
    )
    username = models.CharField("Usuário (na hora)", max_length=150, blank=True)
    email_original = models.CharField("E-mail que a conta tinha", max_length=254, blank=True)
    login_tentado = models.CharField("Login digitado", max_length=254, blank=True)
    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    origem = models.CharField("Por onde", max_length=20, blank=True)
    motivo = models.TextField("Motivo", blank=True)
    criado_em = models.DateTimeField("Quando", default=timezone.now, db_index=True)
    resolvido_em = models.DateTimeField("Resolvida em", null=True, blank=True)
    resolvido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", verbose_name="Resolvida por",
    )

    class Meta:
        verbose_name = "Ocorrência de segurança"
        verbose_name_plural = "Ocorrências de segurança"
        ordering = ("-criado_em", "-id")

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.username or self.login_tentado or self.ip or '-'}"

    ORIGENS = {
        "site": "login do site",
        "painel": "login do painel",
        "admin": "login do /system/",
        "api": "aplicativo",
        "allauth": "/accounts/ (allauth)",
        "migracao": "migração contas/0002",
        "google": "Google",
        "apple": "Apple",
    }

    @property
    def origem_rotulo(self) -> str:
        return self.ORIGENS.get(self.origem, self.origem or "")

    @property
    def pendente(self) -> bool:
        return self.situacao == self.Situacao.PENDENTE

    def resolver(self, situacao, por=None):
        self.situacao = situacao
        self.resolvido_em = timezone.now()
        self.resolvido_por = por if getattr(por, "pk", None) else None
        self.save(update_fields=["situacao", "resolvido_em", "resolvido_por"])
