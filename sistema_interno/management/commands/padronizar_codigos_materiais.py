from django.core.management.base import BaseCommand
from sistema_interno.codigos_materiais import padronizar_codigos


class Command(BaseCommand):
    help = "Simula a padronização dos códigos. Use --aplicar para gravar com histórico."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true")

    def handle(self, *args, **options):
        mudancas = padronizar_codigos(aplicar=options["aplicar"])
        for item in mudancas:
            self.stdout.write(f"{item['id']} | {item['nome']} | {item['anterior'] or '(vazio)'} -> {item['novo']}")
        self.stdout.write(f"{len(mudancas)} alterações. " + ("Aplicadas com histórico." if options["aplicar"] else "Simulação: nada foi gravado."))
