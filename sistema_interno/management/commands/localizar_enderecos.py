"""Procura agora o ponto de todo endereço de cliente que está sem (LEIA-ME-V10, seção 121).

O site já faz isto sozinho, por trás (sistema_interno/localizacao.py): ao
salvar e numa varredura a cada meia hora. Este comando é para ver o
resultado na hora, endereço por endereço:

    python manage.py localizar_enderecos            # todos os sem ponto
    python manage.py localizar_enderecos --limite 20

Respeita o ritmo do Nominatim (uma consulta por segundo): algumas dezenas
de endereços levam alguns minutos.
"""

from django.core.management.base import BaseCommand

from sistema_interno import localizacao


class Command(BaseCommand):
    help = "Procura o ponto no mapa de todo endereço de cliente que ainda está sem."

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=0, help="Quantos endereços no máximo (0 = todos).")

    def handle(self, *args, **opcoes):
        consulta = localizacao.pendentes().select_related("cliente")
        if opcoes["limite"]:
            consulta = consulta[: opcoes["limite"]]
        enderecos = list(consulta)
        if not enderecos:
            self.stdout.write(self.style.SUCCESS("Todo endereço de cliente já tem ponto no mapa."))
            return

        achados = 0
        for endereco in enderecos:
            nome = (endereco.cliente.nome_publico if endereco.cliente_id else f"#{endereco.pk}")[:38]
            achou = localizacao.localizar_um(endereco.pk)
            if achou:
                achados += 1
                endereco.refresh_from_db(fields=["latitude", "longitude", "precisao"])
                nivel = endereco.get_precisao_display() if endereco.precisao else "ponto do CEP"
                self.stdout.write(f"  {nome:40} {endereco.linha_curta:28} ok ({nivel})")
            elif achou is False:
                self.stdout.write(self.style.WARNING(
                    f"  {nome:40} {endereco.linha_curta:28} não achei: confira o CEP e a cidade"
                ))

        self.stdout.write(self.style.SUCCESS(f"{achados} de {len(enderecos)} endereço(s) localizado(s)."))
