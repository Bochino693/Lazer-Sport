"""As fotos de volta para o banco, sem esperar o Cloudinary (LEIA-ME-V10, seção 130).

    python manage.py restaurar_midia                  # das cópias do repositório
    python manage.py restaurar_midia --simular        # só diz o que voltaria
    python manage.py restaurar_midia --zip export.zip # da exportação da Media Library
    python manage.py restaurar_midia --relatorio      # o que ainda falta (modelo, pk, campo, nome)
    python manage.py restaurar_midia --orfaos         # o que está no banco e ninguém usa mais
    python manage.py restaurar_midia --orfaos --apagar

No Render, a restauração das cópias roda sozinha a cada publicação
(core/espelho_midia.py). O ZIP também entra pela tela "Restaurar fotos" do
painel (Administração).
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core import restaurar_midia


class Command(BaseCommand):
    help = "Restaura as fotos para o banco: das cópias do repositório ou de um ZIP exportado do Cloudinary."

    def add_arguments(self, parser):
        parser.add_argument("--zip", dest="zip", default="", help="O ZIP exportado do Cloudinary (ou uma foto solta).")
        parser.add_argument("--simular", action="store_true", help="Só diz o que voltaria (cópias do repositório).")
        parser.add_argument("--relatorio", action="store_true", help="Lista o que ainda não está no banco.")
        parser.add_argument("--orfaos", action="store_true",
                            help="Lista os arquivos do banco que nenhum cadastro usa (com --apagar, apaga).")
        parser.add_argument("--apagar", action="store_true", help="Com --orfaos: apaga os órfãos com mais de 24 h.")

    def handle(self, *args, **opcoes):
        if opcoes["relatorio"]:
            return self._relatorio()
        if opcoes["orfaos"]:
            return self._orfaos(opcoes["apagar"])
        if opcoes["zip"]:
            return self._zip(Path(opcoes["zip"]))
        resultado = restaurar_midia.restaurar_das_copias(simular=opcoes["simular"])
        for item in resultado.restaurados:
            marca = "exata" if item["exata"] else "reserva"
            self.stdout.write(f"[{marca}] {item['nome']} <- {item['de']} ({item['regra']})")
        self.stdout.write("")
        verbo = "Voltariam" if opcoes["simular"] else "Restauradas"
        self.stdout.write(self.style.SUCCESS(f"{verbo}: {len(resultado.restaurados)}"))
        self.stdout.write(f"Sem cópia no repositório: {len(resultado.faltando)} (veja --relatorio)")

    def _zip(self, caminho):
        if not caminho.is_file():
            raise CommandError(f"Arquivo não encontrado: {caminho}")
        mapa = restaurar_midia.Mapa()
        if restaurar_midia.e_zip(caminho):
            if caminho.stat().st_size > restaurar_midia.LIMITE_DO_ZIP:
                raise CommandError("O ZIP passa de 500 MB: exporte em partes (uma pasta por vez).")
            resultado, _proximo, total = restaurar_midia.importar_zip(caminho, mapa=mapa)
            self.stdout.write(f"Arquivos no ZIP: {total}")
        else:
            resultado = restaurar_midia.Resultado()
            restaurar_midia.importar_um(caminho.name, caminho.read_bytes(), mapa, resultado)
            if resultado.restaurados:
                restaurar_midia.espelho_midia.limpar_caches()
        for item in resultado.restaurados:
            self.stdout.write(f"Restaurado: {item['nome']} <- {item['de']}")
        for nome in resultado.nao_referenciados[:100]:
            self.stdout.write(f"Ninguém usa: {nome}")
        for item in resultado.recusados[:100]:
            self.stdout.write(f"Recusado: {item['nome']} ({item['motivo']})")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Restaurados: {len(resultado.restaurados)}"))
        self.stdout.write(f"Já estavam no banco: {len(resultado.ja)}")
        self.stdout.write(f"Ninguém usa: {len(resultado.nao_referenciados)}")
        self.stdout.write(f"Recusados: {len(resultado.recusados)}")
        self.stdout.write(f"Ainda faltam: {len(restaurar_midia.relatorio())} (veja --relatorio)")

    def _orfaos(self, apagar):
        from core.arquivos_no_banco import apagar as apagar_do_banco
        from core.espelho_midia import orfaos

        lista = orfaos()
        total = sum(tamanho for _nome, tamanho in lista)
        for nome, tamanho in lista:
            self.stdout.write(f"  {nome}  ({tamanho // 1024} KB)")
        self.stdout.write(f"Órfãos: {len(lista)} ({total / (1024 * 1024):.1f} MB)")
        if apagar and lista:
            for nome, _tamanho in lista:
                apagar_do_banco(nome)
            self.stdout.write(self.style.SUCCESS(f"Apagados: {len(lista)}"))

    def _relatorio(self):
        linhas = restaurar_midia.relatorio()
        if not linhas:
            self.stdout.write(self.style.SUCCESS("Tudo no banco: nenhum arquivo depende do Cloudinary."))
            return
        atual = None
        for linha in linhas:
            if linha["modelo"] != atual:
                atual = linha["modelo"]
                self.stdout.write("")
                self.stdout.write(self.style.MIGRATE_HEADING(atual))
            self.stdout.write(f"  #{linha['pk']}  {linha['campo']}  {linha['nome']}")
        self.stdout.write("")
        self.stdout.write(f"Total: {len(linhas)} referência(s) fora do banco.")
