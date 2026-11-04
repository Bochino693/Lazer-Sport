"""Teste de carga do Lazer & Sport: loja pública + painel interno.

Dois perfis de usuário, na proporção 4 clientes do site para 1 pessoa da
equipe no painel (peso 4:1):

* ``ClienteDoSite``  -- navega a loja pública (home, catálogo, produto,
  jogos, categoria e um CSS), com pausa de 1 a 3 s entre páginas.
  Passa pelo escudo de tráfego (``core/traffic_shield.py``): no máximo
  ``PUBLIC_CONCURRENCY`` (4) requisições públicas simultâneas; a quinta
  recebe 503 "busy". Esse 503 é contado à parte, com o nome
  ``503 escudo ocupado``, para a análise saber separar "o escudo cortou"
  de "o Django falhou".
* ``EquipeDoPainel`` -- entra pelo host ``interno.localhost`` (o
  ``SubdomainURLMiddleware`` troca o urlconf pelo do painel), faz login
  em ``/login/inner/`` com ``demo`` / ``demo-12345`` e percorre as telas
  mais usadas. O painel não disputa as vagas públicas do escudo.

Como rodar (ver ``rodar.sh`` para a sequência completa de estágios)::

    locust -f ferramentas/carga/locustfile.py --headless \
        --host http://127.0.0.1:8790 -u 50 -r 10 -t 60s --csv resultados/x

Variáveis de ambiente opcionais:

* ``CARGA_HOST_INTERNO``  host do painel (padrão ``interno.localhost``).
* ``CARGA_USUARIO`` / ``CARGA_SENHA``  credenciais do painel.
"""

from __future__ import annotations

import os
import random
import re
from urllib.parse import urlsplit

from locust import HttpUser, between, events, task


HOST_INTERNO = os.getenv("CARGA_HOST_INTERNO", "interno.localhost")
USUARIO = os.getenv("CARGA_USUARIO", "demo")
SENHA = os.getenv("CARGA_SENHA", "demo-12345")

# ids que existem no banco de demonstração (8 brinquedos, 5 categorias)
BRINQUEDOS = [1, 2, 3, 4, 5, 6, 7, 8]
CATEGORIAS = [1, 2, 3, 4, 5]

_CSRF_RE = re.compile(r'name="csrfmiddlewaretoken" value="([^"]+)"')


def _classificar(resposta, nome: str) -> None:
    """Marca a resposta como sucesso/falha, separando os cortes do escudo.

    Um 503 do escudo de tráfego ou um 429 do limitador de bots significam
    "a instância recusou", não "o Django quebrou". Nomeá-los deixa o CSV
    de falhas contar cada um, e a análise consegue dizer em que ponto o
    escudo passou a cortar.
    """
    if resposta.status_code == 503 and b"busy" in resposta.content[:64]:
        resposta.failure("503 escudo ocupado")
    elif resposta.status_code == 429:
        resposta.failure("429 limite de bot")
    elif resposta.status_code >= 400:
        resposta.failure(f"HTTP {resposta.status_code} em {nome}")
    else:
        resposta.success()


class ClienteDoSite(HttpUser):
    """Visitante da loja pública."""

    weight = 4
    wait_time = between(1, 3)

    def _pagina(self, caminho: str, nome: str) -> None:
        with self.client.get(caminho, name=nome, catch_response=True) as r:
            _classificar(r, nome)

    @task(3)
    def home(self):
        self._pagina("/", "/")

    @task(3)
    def catalogo(self):
        self._pagina("/brinquedos/", "/brinquedos/")

    @task(4)
    def produto(self):
        self._pagina(f"/brinquedo/{random.choice(BRINQUEDOS)}/", "/brinquedo/[id]/")

    @task(1)
    def jogos(self):
        self._pagina("/jogos/", "/jogos/")

    @task(2)
    def categoria(self):
        self._pagina(f"/categoria/{random.choice(CATEGORIAS)}/", "/categoria/[id]/")

    @task(2)
    def css(self):
        # O CSS também passa pelo escudo: o WhiteNoise mora dentro do
        # WSGI do Django, então um arquivo estático ocupa uma vaga pública.
        self._pagina("/static/site/ls-base.css", "/static/site/ls-base.css")


class EquipeDoPainel(HttpUser):
    """Pessoa da equipe usando o painel interno (host ``interno.``)."""

    weight = 1
    wait_time = between(2, 5)

    def on_start(self):
        # O cabeçalho Host decide o urlconf; o pedido continua indo para
        # 127.0.0.1:8790, então os cookies de csrf/sessão funcionam normal.
        porta = urlsplit(self.host).port
        self.client.headers["Host"] = f"{HOST_INTERNO}:{porta}" if porta else HOST_INTERNO
        self.logado = False
        self._entrar()

    def _entrar(self) -> None:
        with self.client.get("/login/inner/", name="painel GET /login/inner/", catch_response=True) as r:
            if r.status_code != 200:
                r.failure(f"tela de login respondeu {r.status_code}")
                return
            token = self.client.cookies.get("csrftoken") or ""
            if not token:
                achado = _CSRF_RE.search(r.text)
                token = achado.group(1) if achado else ""
            if not token:
                r.failure("sem token csrf na tela de login")
                return
            r.success()

        dados = {"csrfmiddlewaretoken": token, "login": USUARIO, "password": SENHA}
        with self.client.post(
            "/login/inner/",
            data=dados,
            name="painel POST /login/inner/",
            catch_response=True,
            allow_redirects=False,
        ) as r:
            destino = r.headers.get("Location", "")
            if r.status_code in (301, 302, 303) and "/login/" not in destino:
                self.logado = True
                r.success()
            elif r.status_code == 200:
                # a view devolve 200 com a própria tela quando a senha falha
                r.failure("login recusado (usuário/senha ou sem permissão)")
            else:
                r.failure(f"login respondeu {r.status_code} -> {destino}")

    def _tela(self, caminho: str) -> None:
        if not self.logado:
            self._entrar()
            if not self.logado:
                return
        nome = f"painel {caminho}"
        with self.client.get(caminho, name=nome, catch_response=True, allow_redirects=False) as r:
            if r.status_code in (301, 302, 303):
                destino = r.headers.get("Location", "")
                if "/login/" in destino:
                    self.logado = False
                    r.failure("sessão perdida: redirecionado para o login")
                else:
                    r.success()
            else:
                _classificar(r, nome)

    @task(2)
    def inicio(self):
        self._tela("/")

    @task(4)
    def orcamentos(self):
        self._tela("/orcamentos/")

    @task(2)
    def clientes(self):
        self._tela("/clientes/")

    @task(2)
    def producao(self):
        self._tela("/producao/")

    @task(2)
    def estoque(self):
        self._tela("/estoque/")


@events.quitting.add_listener
def _avisar_se_login_falhou(environment, **kwargs):
    """Deixa claro no fim da execução se o painel nunca conseguiu entrar."""
    stats = environment.stats
    post = stats.get("painel POST /login/inner/", "POST")
    if post.num_requests and post.num_failures == post.num_requests:
        print("ATENÇÃO: nenhum login do painel teve sucesso; os números do painel não valem.")
