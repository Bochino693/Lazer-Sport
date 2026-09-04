"""Formatação de números do painel interno.

`{{ valor|floatformat:2|intcomma }}` parece o caminho óbvio, mas em
pt-BR devolve "5,140,00": o intcomma não consegue converter a string
que o floatformat já localizou e cai no separador americano. Aqui o
número é formatado uma vez só, direto do Decimal.
"""

from decimal import Decimal, InvalidOperation

from django import template
from django.utils.formats import number_format

register = template.Library()


def _para_decimal(valor):
    if valor is None or valor == "":
        return None
    if isinstance(valor, Decimal):
        return valor
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        return None


@register.filter
def moeda(valor):
    """1234567.8 -> 1.234.567,80"""
    from core.formatos import dinheiro

    return dinheiro(valor)


@register.filter
def reais(valor):
    """1234567.8 -> R$ 1.234.567,80 -- o cifrão junto, uma vez só.

    Existe porque `R$ {{ x|moeda }}` espalhado por cinquenta templates é
    cinquenta chances de alguém escrever `R$ {{ x }}` sem o filtro -- que
    foi exatamente o que aconteceu. Com o cifrão dentro, esquecer o
    filtro apaga o cifrão junto, e o erro salta aos olhos.
    """
    from core.formatos import dinheiro

    return dinheiro(valor, prefixo="R$")


@register.filter
def extenso(valor):
    """1250.5 -> 'mil, duzentos e cinquenta reais e cinquenta centavos'.

    O recibo escreve o valor duas vezes -- em algarismos e por extenso --
    porque é o extenso que impede um "1.500,00" de virar "11.500,00" com
    uma canetada depois de assinado.
    """
    from core.formatos import por_extenso

    return por_extenso(valor)


@register.filter
def porcento(valor):
    """20 -> 20%; 12.5 -> 12,5%.

    Sem o zero à toa: "20,00% OFF" num selo de promoção ocupa espaço
    dizendo menos que "20% OFF". Sem espaço antes do sinal, que é a
    convenção em português.
    """
    from core.formatos import medida as _medida

    escrito = _medida(valor, unidade="")
    return f"{escrito}%" if escrito else ""


@register.filter
def medida(valor, unidade="m"):
    """2.00 -> 2 m; 2.50 -> 2,5 m. Vazio continua vazio.

    `{{ brinquedo.altura_m|medida }}` ou `{{ peso|medida:"kg" }}`. Ver
    `core/formatos.py`: os zeros à direita caem de propósito, porque é
    assim que se lê uma fita métrica.
    """
    from core.formatos import medida as _medida

    return _medida(valor, unidade)


@register.filter
def numero(valor):
    """5140 -> 5.140"""
    convertido = _para_decimal(valor)
    if convertido is None:
        return "0"

    return number_format(int(convertido), force_grouping=True)


# ======================================================================
# A VERSÃO DO ESTÁTICO SAI DO ARQUIVO, E NÃO DA MEMÓRIA DE QUEM EDITA
# ======================================================================
# O QUE ACONTECEU. A folha do painel era pedida como
# `{% static 'interno/interno_modern.css' %}?v=35` -- um número digitado
# à mão. Quem mexia no CSS precisava lembrar de trocá-lo. Uma rodada
# inteira de correções de cor foi para produção com o `v=35` intacto, e
# durante 24 horas (o `max-age` do WhiteNoise) todo navegador que já
# tinha aberto o painel continuou usando a folha velha.
#
# O sintoma é cruel de diagnosticar: o HTML é sempre novo, porque página
# não se cacheia; só o CSS fica para trás. A tela mostra a marcação nova
# com o estilo antigo, e a leitura óbvia é "a correção não funcionou" --
# quando ela nunca chegou.
#
# Aqui a versão é a impressão digital do conteúdo. Mudou o arquivo,
# mudou a URL, o navegador busca de novo; não mudou, ele reaproveita o
# que tem. Não há número para lembrar, então não há número para
# esquecer.

import hashlib
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static

#: Hash por caminho. Em produção os arquivos não mudam enquanto o
#: processo vive, então calcular uma vez é o certo -- e ler o CSS inteiro
#: a cada requisição de página seria caro à toa.
_IMPRESSOES = {}


def _caminho_no_disco(caminho):
    """Onde este estático está agora: no app (dev) ou no STATIC_ROOT (prod).

    `finders` só enxerga os diretórios de origem, e é o que vale em
    desenvolvimento. Em produção o `collectstatic` já juntou tudo no
    STATIC_ROOT, e é de lá que o WhiteNoise serve.
    """
    achado = finders.find(caminho)
    if achado:
        return Path(achado)

    raiz = getattr(settings, "STATIC_ROOT", None)
    if raiz:
        candidato = Path(raiz) / caminho
        if candidato.is_file():
            return candidato
    return None


def _impressao_digital(caminho):
    arquivo = _caminho_no_disco(caminho)
    if arquivo is None:
        # Estático que não existe não pode derrubar a página inteira: sem
        # versão, o navegador ainda carrega o arquivo (ou toma 404 nele
        # sozinho), e o resto da tela continua de pé.
        return ""

    # Em desenvolvimento o arquivo muda debaixo do processo, então a
    # chave carrega o mtime: salvar o CSS e recarregar precisa bastar.
    chave = (caminho, arquivo.stat().st_mtime_ns) if settings.DEBUG else caminho
    if chave not in _IMPRESSOES:
        _IMPRESSOES[chave] = hashlib.sha256(
            arquivo.read_bytes()
        ).hexdigest()[:10]
    return _IMPRESSOES[chave]


@register.simple_tag
def estatico(caminho):
    """Como `{% static %}`, com uma versão que acompanha o conteúdo.

    Use no lugar de `{% static '...' %}?v=N` para qualquer CSS ou JS do
    painel. O `?v=` continua existindo na URL -- é ele que faz o
    navegador buscar de novo --, só não é mais digitado por ninguém.
    """
    endereco = static(caminho)
    versao = _impressao_digital(caminho)
    return f"{endereco}?v={versao}" if versao else endereco
