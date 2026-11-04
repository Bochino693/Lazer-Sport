"""O JavaScript da casa sai do `collectstatic` minificado e sem mapa de fonte.

POR QUE. Os jogos do simulador (`site/arena/`) são módulos ES escritos
como quem explica: cabeçalho contando de onde vem cada conta, comentário
em cada passo, nome de variável que diz o que ela guarda, a tabela de
jogadas calibrada com o porquê de cada número. É o conhecimento da casa
-- e, servido como está, qualquer pessoa com o navegador aberto baixava
tudo pronto para ler, uns 2 MB de explicação.

O QUE ESTA CLASSE FAZ. Entra no lugar do storage do WhiteNoise em
produção. Depois que o `collectstatic` copia os arquivos para o
STATIC_ROOT e ANTES de o WhiteNoise comprimir, ela:

  * passa o `rjsmin` em cada `.js` escrito aqui (site/, app/ e interno/;
    nunca vendor/, que já chega minificado de fora com a licença no
    cabeçalho): some comentário, some espaço, some quebra de linha;
  * tira a linha `sourceMappingURL` que apontaria o navegador de volta
    ao fonte legível;
  * apaga qualquer mapa de fonte (`.map`) que a coleta tenha trazido,
    inclusive os que vêm de pacotes (o Django REST Framework traz dois).

Só então o compressor do WhiteNoise roda, já em cima do minificado: o
`.gz` e o `.br` servidos nascem do arquivo pequeno.

O QUE ISTO PROTEGE -- E O QUE NÃO PROTEGE. Vale ser honesto com quem lê
este arquivo daqui a um ano. O navegador precisa receber o programa
inteiro para rodá-lo, então nenhum arranjo no servidor esconde a lógica
de um jogo que roda no navegador. Quem quiser continua baixando o `.js`
e passando num "beautifier"; o que sai dali é um programa que roda e
que se lê -- só que sem explicação nenhuma: sem o cabeçalho, sem o
porquê de cada número, com as linhas coladas. O `rjsmin` não renomeia
variável nem embaralha nada: ele tira comentário e espaço, e só. Ou
seja: a minificação remove as explicações, não torna o algoritmo
secreto. O que fica mesmo em sigilo é o que nunca sai do servidor: as
regras do ranking e a validação da partida (`core/ranking.py`) e o jogo
de verdade das máquinas (o APK), que não está no site -- aqui vai só a
prévia.

Em desenvolvimento e nos testes (`lazer/settings_test.py`) o storage é o
padrão do Django, e o `runserver` continua servindo o fonte legível.
"""

import os
import re
from pathlib import Path

import rjsmin
from whitenoise.storage import CompressedStaticFilesStorage

#: O código escrito aqui. Tudo que mora nestas pastas é da casa.
PASTAS_PROTEGIDAS = ("site/", "app/", "interno/")

#: O que veio de fora (three.js, Leaflet, Bootstrap) já chega minificado,
#: com a licença no cabeçalho; não se mexe. Vale em qualquer nível:
#: `vendor/three/...` e `interno/vendor/...`.
PASTA_DE_TERCEIROS = "vendor/"

#: Mapa de fonte é o caminho de volta para o código legível. Nenhum
#: sobrevive à coleta -- nem o `.gz`/`.br` que uma coleta anterior tenha
#: deixado ao lado dele.
SUFIXOS_DE_MAPA = (".map", ".map.gz", ".map.br")

# `//# sourceMappingURL=x.js.map` numa linha própria, ou a forma em bloco
# `/*# sourceMappingURL=x.css.map */`. O `rjsmin` já tira os dois como
# comentário; isto é o cinto além do suspensório.
_SOURCE_MAPPING_URL = re.compile(
    r"^[ \t]*//[#@][ \t]*sourceMappingURL=[^\n]*$"
    r"|/\*[#@][ \t]*sourceMappingURL=[\s\S]*?\*/",
    re.MULTILINE,
)


def e_protegido(caminho):
    """Verdadeiro para o `.js` escrito pela casa -- o que sai minificado.

    `caminho` é o relativo ao STATIC_ROOT, como o `collectstatic` entrega
    (no Windows, com barra invertida -- caminho de estático nunca tem
    barra invertida por outro motivo, então ela vira barra sempre).
    """
    caminho = caminho.replace("\\", "/")
    if not caminho.endswith(".js") or caminho.endswith(".min.js"):
        return False
    if PASTA_DE_TERCEIROS in caminho:
        return False
    return caminho.startswith(PASTAS_PROTEGIDAS)


def e_mapa(caminho):
    """Verdadeiro para um mapa de fonte (ou o comprimido de um)."""
    return caminho.replace("\\", "/").endswith(SUFIXOS_DE_MAPA)


def minificar(texto):
    """O módulo sem comentário, sem espaço e sem a referência ao mapa.

    O `rjsmin` respeita o que não pode encolher: string, template
    literal, regex e o `import`/`export` do módulo ES -- o programa que
    sai é o mesmo que entrou (a árvore sintática é idêntica), só que
    sem as explicações.
    """
    texto = _SOURCE_MAPPING_URL.sub("", texto)
    texto = rjsmin.jsmin(texto, keep_bang_comments=False)
    texto = _SOURCE_MAPPING_URL.sub("", texto)
    return texto.strip() + "\n"


class EstaticosProtegidosStorage(CompressedStaticFilesStorage):
    """O storage de produção: minifica o JS da casa e só depois comprime."""

    def post_process(self, paths, dry_run=False, **options):
        if dry_run:
            return

        para_comprimir = {}
        for nome, origem in paths.items():
            if e_mapa(nome):
                # O collectstatic acabou de copiá-lo; some antes que o
                # WhiteNoise o comprima.
                self.delete(nome)
                continue
            if e_protegido(nome):
                try:
                    self._minificar_no_disco(nome)
                except Exception as erro:  # noqa: BLE001 -- o collectstatic relança
                    # Um `.js` que não pôde ser minificado não vai para o
                    # ar legível por acidente: fica fora da compressão e o
                    # deploy para com a mensagem.
                    yield nome, None, erro
                    continue
                yield nome, nome, True
            para_comprimir[nome] = origem

        self._apagar_mapas_antigos()

        # O compressor do WhiteNoise lê o que está no disco agora: o .gz e
        # o .br nascem do minificado.
        yield from super().post_process(para_comprimir, dry_run=dry_run, **options)

    def _minificar_no_disco(self, nome):
        arquivo = Path(self.path(nome))
        fonte = arquivo.read_text(encoding="utf-8")
        arquivo.write_text(minificar(fonte), encoding="utf-8")

    def _apagar_mapas_antigos(self):
        """Mapas de coletas anteriores (e o .gz/.br deles) também somem.

        Em máquina de desenvolvimento o STATIC_ROOT sobrevive de uma coleta
        para a outra, e o `collectstatic` não apaga o que ele mesmo não
        copiou nesta rodada.
        """
        raiz = self.location
        if not raiz or not os.path.isdir(raiz):
            return
        for pasta, _, arquivos in os.walk(raiz):
            for arquivo in arquivos:
                if arquivo.endswith(SUFIXOS_DE_MAPA):
                    os.remove(os.path.join(pasta, arquivo))
