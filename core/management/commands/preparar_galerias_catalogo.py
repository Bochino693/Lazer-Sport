from django.core.management.base import BaseCommand
from django.db import transaction

from core.catalog_images import preparar_galerias_catalogo


class Command(BaseCommand):
    help = (
        "Adiciona as imagens atuais dos brinquedos como foto 1 e numera "
        "as imagens existentes das peças. Pode ser executado novamente."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra o que seria alterado e desfaz a operação.",
        )

    def handle(self, *args, **options):
        with transaction.atomic():
            resumo = preparar_galerias_catalogo()
            if options["dry_run"]:
                transaction.set_rollback(True)

        modo = "Simulação" if options["dry_run"] else "Concluído"
        self.stdout.write(self.style.SUCCESS(f"{modo}: galerias preparadas."))
        self.stdout.write(
            f"Fotos de brinquedos criadas: "
            f"{resumo['fotos_brinquedos_criadas']}"
        )
        self.stdout.write(
            f"Fotos de peças numeradas: "
            f"{resumo['fotos_pecas_numeradas']}"
        )
