"""Ler uma página inteira, esteja o estilo e o script onde estiverem.

POR QUE ISTO EXISTE. Vários testes cobram regras lendo o arquivo do
template: a folha A4 do documento, a tinta do painel, o empilhamento do
modal, o gráfico que não depende de CDN. Eram regras que só podiam ser
conferidas ali porque o CSS e o JavaScript moravam dentro do HTML.

Os dois saíram de dentro do HTML -- juntos eram o maior peso de cada
página, e ali dentro o navegador não tinha como guardá-los. As regras
continuam valendo exatamente como antes; o que mudou foi o endereço.

Estas funções juntam o template com os arquivos que ele referencia. O
teste continua cobrando a REGRA, e não o lugar onde ela está escrita --
que é o que um teste deve fazer.
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

#: `{% estatico 'site/paginas/x.css' %}` e `{% static 'site/x.js' %}`.
REFERENCIA = re.compile(r"""\{%\s*(?:estatico|static)\s+['"]([^'"]+)['"]""")


def _juntar(nome_do_template, app, extensoes):
    base = RAIZ if app == "core" else RAIZ.parent / app
    texto = (base / "templates" / nome_do_template).read_text(encoding="utf-8")

    partes = [texto]
    for referencia in REFERENCIA.findall(texto):
        if not referencia.endswith(extensoes):
            continue
        for raiz in (RAIZ / "static", RAIZ.parent / "sistema_interno" / "static"):
            arquivo = raiz / referencia
            if arquivo.is_file():
                partes.append(arquivo.read_text(encoding="utf-8"))
                break

    return "\n".join(partes)


def estilo_da_pagina(nome_do_template, app="core"):
    """O template mais as folhas de estilo que ele liga.

    `nome_do_template` é o caminho dentro de templates/ (por exemplo
    "orcamento_publico.html" ou "gestao/pecas_adm.html").
    """
    return _juntar(nome_do_template, app, (".css",))


def script_da_pagina(nome_do_template, app="core"):
    """O template mais os scripts que ele carrega."""
    return _juntar(nome_do_template, app, (".js",))
