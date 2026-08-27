"""Confere e corrige as coordenadas que vão para o mapa público.

Roda em produção, onde o Nominatim é alcançável:

    python manage.py conferir_mapa            # só relata, não grava
    python manage.py conferir_mapa --corrigir # regrava o que estiver ruim

O relatório diz, para cada cliente publicado, até onde a busca conseguiu
chegar. É isso que separa "o alfinete está no endereço" de "o alfinete
está na região" -- distinção que antes se perdia, porque um resultado de
nível cidade era gravado igual a um resultado exato.
"""

import time

from django.core.management.base import BaseCommand

from core.models import EnderecoEmpresa
from sistema_interno.models import EnderecoCliente
from core.utils import (
    PRECISAO_CONFIAVEL,
    distancia_km,
    geocodificar_endereco,
    origem_da_empresa,
)

# O uso público do Nominatim pede no máximo uma consulta por segundo.
INTERVALO_S = 1.1


class Command(BaseCommand):
    help = "Confere as coordenadas do mapa e aponta as que estão imprecisas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--corrigir",
            action="store_true",
            help="Regrava as coordenadas dos cadastros imprecisos.",
        )
        parser.add_argument(
            "--incluir-manuais",
            action="store_true",
            help="Também refaz os que foram ajustados à mão (por padrão "
                 "eles são respeitados e nunca sobrescritos).",
        )

    def handle(self, *args, **opcoes):
        corrigir = opcoes["corrigir"]
        incluir_manuais = opcoes["incluir_manuais"]

        self.stdout.write(self.style.MIGRATE_HEADING("Endereço da empresa"))
        self._conferir_empresa(corrigir)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Clientes no mapa"))

        cadastros = (
            EnderecoCliente.objects
            .filter(cliente__publicar_no_mapa=True, cliente__ativo=True)
            .select_related("cliente")
            .order_by("cliente__nome_cliente")
        )
        if not cadastros:
            self.stdout.write("  nenhum cadastro para conferir.")
            return

        contagem = {"exato": 0, "rua": 0, "bairro": 0, "cidade": 0, "manual": 0, "sem": 0}

        for cadastro in cadastros:
            nome = (cadastro.cliente.nome_cliente or f"#{cadastro.pk}")[:38]

            if cadastro.precisao == EnderecoCliente.Precisao.MANUAL and not incluir_manuais:
                contagem["manual"] += 1
                self.stdout.write(f"  {nome:40} ajustado à mão, mantido")
                continue

            if not cadastro.cep:
                contagem["sem"] += 1
                self.stdout.write(self.style.WARNING(
                    f"  {nome:40} sem CEP -- só dá para chegar na cidade"
                ))
                continue

            lat, lon, precisao = geocodificar_endereco(
                cadastro.cep, cadastro.numero or ""
            )
            time.sleep(INTERVALO_S)

            if not lat or not lon:
                contagem["sem"] += 1
                self.stdout.write(self.style.ERROR(
                    f"  {nome:40} não foi possível localizar"
                ))
                continue

            contagem[precisao] = contagem.get(precisao, 0) + 1
            bom = precisao in PRECISAO_CONFIAVEL

            distancia = None
            if cadastro.latitude and cadastro.longitude:
                distancia = distancia_km(
                    float(cadastro.latitude), float(cadastro.longitude), lat, lon
                )

            recado = f"  {nome:40} {precisao}"
            if distancia is not None and distancia >= 0.15:
                recado += f" -- estava {distancia:.1f} km fora"

            estilo = self.style.SUCCESS if bom else self.style.WARNING
            self.stdout.write(estilo(recado))

            if corrigir and (distancia is None or distancia >= 0.05):
                cadastro.latitude = lat
                cadastro.longitude = lon
                cadastro.precisao = precisao
                cadastro.save(update_fields=["latitude", "longitude", "precisao"])

        self.stdout.write("")
        self.stdout.write(
            "  no endereço: {exato}  |  meio da rua: {rua}  |  "
            "bairro: {bairro}  |  cidade: {cidade}  |  "
            "à mão: {manual}  |  sem coordenada: {sem}".format(**contagem)
        )

        imprecisos = contagem["bairro"] + contagem["cidade"] + contagem["sem"]
        if imprecisos:
            self.stdout.write(self.style.WARNING(
                f"\n  {imprecisos} alfinete(s) apontam para uma região, não para o "
                "endereço.\n  Para esses, abra o Google Maps, clique com o botão "
                "direito no ponto\n  certo, copie as coordenadas e cole no cadastro "
                "-- o valor digitado à\n  mão nunca é sobrescrito."
            ))

        if not corrigir:
            self.stdout.write("\n  (nada foi gravado; use --corrigir para aplicar)")

    def _conferir_empresa(self, corrigir):
        endereco = EnderecoEmpresa.objects.filter(ativo=True).first()
        lat_atual, lon_atual = origem_da_empresa()

        if not endereco:
            self.stdout.write(self.style.WARNING(
                "  sem cadastro em EnderecoEmpresa -- mapa e frete usam as "
                f"coordenadas fixas do código ({lat_atual}, {lon_atual})."
            ))
            return

        self.stdout.write(
            f"  {endereco.rua}, {endereco.numero} -- {endereco.bairro}"
        )
        self.stdout.write(f"  em uso hoje: {lat_atual}, {lon_atual}")

        lat, lon, precisao = geocodificar_endereco(
            endereco.cep, endereco.numero or ""
        )
        if not lat or not lon:
            self.stdout.write(self.style.ERROR("  não foi possível localizar o endereço."))
            return

        distancia = distancia_km(lat_atual, lon_atual, lat, lon)
        self.stdout.write(f"  busca automática ({precisao}): {lat}, {lon}")

        if distancia >= 0.15:
            self.stdout.write(self.style.WARNING(
                f"  os dois pontos estão a {distancia:.2f} km um do outro."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"  diferença de {distancia * 1000:.0f} m -- coerente."
            ))

        if corrigir and precisao in PRECISAO_CONFIAVEL and distancia >= 0.05:
            endereco.latitude = lat
            endereco.longitude = lon
            endereco.save(update_fields=["latitude", "longitude"])
            self.stdout.write(self.style.SUCCESS("  cadastro atualizado."))
