"""Completa a região (cidade/estado/país) dos registros de cadastro que ficaram sem.

A consulta ao geo-IP acontece logo depois do cadastro, numa thread; se o
serviço estava fora, se o limite do dia estourou ou se GEOIP_ATIVO estava
desligado, o registro fica com a região vazia. Este comando passa por
esses registros e consulta de novo, devagar (um por vez, com pausa), para
não estourar o limite do serviço gratuito.

    python manage.py preencher_regioes            # até 200 registros
    python manage.py preencher_regioes --limite 50 --pausa 1.5
"""

import time

from django.core.management.base import BaseCommand

from core.models import RegistroCadastro
from core.registro_cadastro import consultar_regiao, ip_privado


class Command(BaseCommand):
    help = "Consulta a região aproximada (pelo IP) dos registros de cadastro que ficaram sem ela."

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=200, help="Quantos registros consultar nesta rodada.")
        parser.add_argument("--pausa", type=float, default=1.0, help="Segundos entre uma consulta e outra.")

    def handle(self, *args, **opcoes):
        pendentes = (
            RegistroCadastro.objects.filter(regiao_conferida=False, pais="")
            .exclude(ip__isnull=True)
            .order_by("-criacao")[: opcoes["limite"]]
        )
        feitos = pulados = falhas = 0
        for registro in pendentes:
            if ip_privado(registro.ip):
                # IP interno não tem região: marca como conferido para não voltar sempre
                RegistroCadastro.objects.filter(pk=registro.pk).update(regiao_conferida=True)
                pulados += 1
                continue
            regiao = consultar_regiao(registro.ip)
            if regiao:
                RegistroCadastro.objects.filter(pk=registro.pk).update(regiao_conferida=True, **regiao)
                feitos += 1
                self.stdout.write(f"{registro.ip}: {regiao['cidade']}, {regiao['estado']}, {regiao['pais']}")
            else:
                falhas += 1
            time.sleep(max(0.0, opcoes["pausa"]))
        self.stdout.write(self.style.SUCCESS(f"Regiões preenchidas: {feitos}; IPs internos: {pulados}; sem resposta: {falhas}."))
