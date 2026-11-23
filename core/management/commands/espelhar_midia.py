"""Copia para o banco o que ainda está só no Cloudinary (LEIA-ME-V10, seção 130).

    python manage.py espelhar_midia            # uma rodada, contando o que fez
    python manage.py espelhar_midia --simular  # só conta o que falta

No Render a mesma rodada roda sozinha em segundo plano (core/espelho_midia.py);
o comando é para ver na hora, na frente de quem rodou.
"""

from django.core.management.base import BaseCommand

from core import espelho_midia


class Command(BaseCommand):
    help = "Copia para o banco os arquivos que ainda estão só no Cloudinary (fotos, .glb, documentos)."

    def add_arguments(self, parser):
        parser.add_argument("--simular", action="store_true", help="Só conta; não baixa nem grava nada.")
        parser.add_argument("--limite-mb", type=int, default=0, help="Pula o arquivo maior que isto (padrão: MIDIA_ESPELHO_LIMITE_MB).")

    def handle(self, *args, **opcoes):
        limite = opcoes["limite_mb"] * 1024 * 1024 if opcoes["limite_mb"] else None
        resultado = espelho_midia.espelhar(
            avisar=lambda texto: self.stdout.write(texto), simular=opcoes["simular"], limite=limite,
        )
        self.stdout.write("")
        self.stdout.write(f"Nomes fora do banco no começo: {resultado['pendentes']}")
        self.stdout.write(f"Copiados do Cloudinary: {resultado['copiados']}")
        self.stdout.write(f"Já estavam no banco (só o campo mudou): {resultado['repontados']}")
        self.stdout.write(f"Cópias de reserva trocadas pela original: {resultado['trocados']}")
        self.stdout.write(f"O Cloudinary não tem (404): {len(resultado['faltando'])}")
        for nome in resultado["faltando"][:50]:
            self.stdout.write(f"  - {nome}")
        self.stdout.write(f"Grandes demais (ficaram no Cloudinary): {len(resultado['grandes'])}")
        self.stdout.write(f"Falhas de rede: {resultado['falhas']}")
        if resultado["fora_do_ar"]:
            self.stdout.write(self.style.WARNING(
                "O Cloudinary respondeu que a conta está fora do ar (401/disabled): nada mais foi copiado. "
                "Quando o dono reativar a conta, rode de novo (no Render isso acontece sozinho)."
            ))
