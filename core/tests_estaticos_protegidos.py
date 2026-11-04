"""O JavaScript da casa sai do `collectstatic` sem as explicações.

Os jogos do simulador são módulos ES comentados linha a linha: é o
conhecimento da casa, e o navegador baixava tudo pronto para ler. Em
produção o storage é `core.estaticos.EstaticosProtegidosStorage`, que
minifica o JS escrito aqui, tira a referência ao mapa de fonte e apaga
qualquer `.map` -- e só depois deixa o WhiteNoise comprimir.

Este teste coleta os estáticos numa pasta temporária com esse storage e
confere o que chega ao STATIC_ROOT, que é o que o WhiteNoise serve. A
coleta inteira roda uma vez por classe: é a parte lenta, e os testes só
leem o resultado. Nos testes e no `runserver` o storage continua o
padrão (`lazer/settings_test.py`): o fonte legível não sai daqui.
"""

import gzip
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from core import estaticos

JOGO = "site/arena/jogos/strike-kids.js"
BIBLIOTECA = "vendor/three/three.module.min.js"
BIBLIOTECA_DO_PAINEL = "interno/vendor/bootstrap.bundle.min.js"

#: Uma linha do cabeçalho do jogo: está no fonte, não pode estar no servido.
EXPLICACAO = "STRIKE KIDS 3D — a prévia do boliche infantil do Bob e da Mia."

#: Um módulo de mentira, posto numa pasta extra de estáticos só durante a
#: coleta: ele traz o que o repositório não tem hoje -- um mapa de fonte
#: ao lado e a linha que aponta para ele -- para o teste ver os dois
#: sumirem de verdade, e não por falta de ocasião.
SONDA = "site/arena/jogos/_sonda_protegida.js"
SONDA_FONTE = """/* A sonda: um módulo de mentira que só existe durante este teste. */
// A linha no fim apontaria o navegador de volta ao fonte legível.
export default { nome: "sonda", largura: 320, altura: 240 };
//# sourceMappingURL=_sonda_protegida.js.map
"""
SONDA_MAPA = '{"version":3,"sources":["_sonda_protegida.js"],"mappings":""}\n'


class EstaticosProtegidosTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pasta = Path(tempfile.mkdtemp(prefix="ls-estaticos-protegidos-"))
        cls.addClassCleanup(shutil.rmtree, cls.pasta, ignore_errors=True)

        extra = cls.pasta / "origem-extra"
        (extra / SONDA).parent.mkdir(parents=True)
        (extra / SONDA).write_text(SONDA_FONTE, encoding="utf-8")
        (extra / (SONDA + ".map")).write_text(SONDA_MAPA, encoding="utf-8")

        cls.destino = cls.pasta / "staticfiles"
        cls.configuracao = override_settings(
            STATIC_ROOT=str(cls.destino),
            STATICFILES_DIRS=[str(extra)],
            # O assunto aqui é o JS. Comprimir as 150 músicas e os modelos
            # 3D do simulador é o que faz a coleta demorar (uns 15 s), e
            # não conta nada para estes testes; o .gz do JS continua saindo.
            WHITENOISE_SKIP_COMPRESS_EXTENSIONS=(
                *settings.WHITENOISE_SKIP_COMPRESS_EXTENSIONS,
                "mp3", "glb", "bin", "json", "svg", "css",
            ),
            STORAGES={
                "default": {
                    "BACKEND": "django.core.files.storage.FileSystemStorage",
                },
                "staticfiles": {
                    "BACKEND": "core.estaticos.EstaticosProtegidosStorage",
                },
            },
        )
        cls.configuracao.enable()
        cls.addClassCleanup(cls.configuracao.disable)

        call_command("collectstatic", interactive=False, verbosity=0)

    def servido(self, caminho):
        """Os bytes que o WhiteNoise serviria para este caminho."""
        return (self.destino / caminho).read_bytes()

    def fonte(self, caminho):
        """Os bytes do arquivo como está no repositório."""
        return Path(finders.find(caminho)).read_bytes()

    def test_o_jogo_sai_sem_as_explicacoes_e_bem_menor(self):
        fonte = self.fonte(JOGO).decode("utf-8")
        servido = self.servido(JOGO).decode("utf-8")

        # O teste só vale enquanto o fonte tiver o cabeçalho que ele procura.
        self.assertIn(EXPLICACAO, fonte)
        self.assertNotIn(EXPLICACAO, servido)
        # Continua um módulo ES: o console faz `import(url)` e lê o default.
        self.assertIn("export default", servido)
        # Sem comentário e sem espaço sobra bem menos de 80% do arquivo.
        self.assertLess(len(servido), len(fonte) * 0.8)

    def test_o_comprimido_nasce_do_minificado(self):
        """O .gz que o WhiteNoise serve é o do arquivo pequeno."""
        comprimido = self.destino / (JOGO + ".gz")
        self.assertTrue(comprimido.exists(), "o WhiteNoise não comprimiu o jogo")
        self.assertEqual(gzip.decompress(comprimido.read_bytes()), self.servido(JOGO))

    def test_nenhum_mapa_de_fonte_sobrevive(self):
        mapas = sorted(
            str(arquivo.relative_to(self.destino))
            for arquivo in self.destino.rglob("*")
            if arquivo.name.endswith(estaticos.SUFIXOS_DE_MAPA)
        )
        self.assertEqual(mapas, [], "mapa de fonte servido: " + ", ".join(mapas))

        # A sonda tinha um mapa ao lado e a linha que apontava para ele.
        sonda = self.servido(SONDA).decode("utf-8")
        self.assertNotIn("sourceMappingURL", sonda)
        self.assertNotIn("módulo de mentira", sonda)
        self.assertIn("export default", sonda)
        self.assertIn('"sonda"', sonda)

    def test_o_resto_do_js_da_casa_tambem_sai_minificado(self):
        for caminho, explicacao in (
            ("site/ls-page-loader.js", "barra de carregamento no topo da página"),
            ("interno/painel.js", "Utilidades do painel interno"),
        ):
            with self.subTest(caminho=caminho):
                fonte = self.fonte(caminho).decode("utf-8")
                servido = self.servido(caminho).decode("utf-8")
                self.assertIn(explicacao, fonte)
                self.assertNotIn(explicacao, servido)
                self.assertLess(len(servido), len(fonte))

    def test_o_que_veio_de_fora_fica_byte_a_byte(self):
        """three.js e Bootstrap já chegam minificados, com a licença: não se mexe."""
        for caminho in (BIBLIOTECA, BIBLIOTECA_DO_PAINEL):
            with self.subTest(caminho=caminho):
                self.assertEqual(self.servido(caminho), self.fonte(caminho))

    def test_quem_e_protegido(self):
        protegidos = (
            "site/arena/jogos/strike-kids.js",
            "site/arena/console.js",
            "site/paginas/home.js",
            "interno/painel.js",
            "app/qualquer.js",
        )
        for caminho in protegidos:
            with self.subTest(caminho=caminho):
                self.assertTrue(estaticos.e_protegido(caminho))

        deixados_em_paz = (
            "vendor/three/three.module.min.js",
            "vendor/three/GLTFLoader.js",
            "interno/vendor/bootstrap.bundle.min.js",
            "admin/js/core.js",
            "rest_framework/js/jquery-3.7.1.min.js",
            "site/arena/jogos/strike-kids/modelos.json",
            "site/arena/jogos/strike-kids.js.map",
        )
        for caminho in deixados_em_paz:
            with self.subTest(caminho=caminho):
                self.assertFalse(estaticos.e_protegido(caminho))

        # No Windows o collectstatic entrega barra invertida.
        self.assertTrue(estaticos.e_protegido("site\\arena\\jogos\\strike-kids.js"))
        self.assertTrue(estaticos.e_mapa("site\\arena\\jogos\\strike-kids.js.map"))

    def test_a_producao_usa_este_storage(self):
        """O deploy só protege se `lazer/settings.py` apontar para cá."""
        from lazer import settings as producao

        self.assertEqual(
            producao.STORAGES["staticfiles"]["BACKEND"],
            "core.estaticos.EstaticosProtegidosStorage",
        )
