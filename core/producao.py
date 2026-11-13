"""O tempo de produção: dias úteis e a previsão de quando fica pronto.

O PEDIDO DO DONO. "O tempo de produção a gente deve poder informar em cada
pedido ou orçamento." A equipe diz QUANTOS dias úteis a máquina leva para
ficar pronta; a data sai sozinha, contada a partir do começo (o pagamento
do pedido do site, a aprovação do orçamento).

POR QUE DIAS ÚTEIS, E NÃO CORRIDOS. É assim que a fábrica fala ("15 dias
úteis") e é assim que o cliente cobra: prometer "15 dias" e contar o fim
de semana faz a máquina "atrasar" sem que nada tenha mudado no galpão.

O QUE NÃO É DIA ÚTIL. Sábado, domingo e os feriados NACIONAIS (a lista da
lei, mais a Sexta-feira Santa, que muda com a Páscoa). Feriado estadual e
municipal ficam de fora de propósito: a fábrica entrega para o Brasil
inteiro, e a data é uma PREVISÃO -- quem tiver uma emenda de feriado na
cidade ajusta o número de dias.

O DIA DO COMEÇO NÃO CONTA. Pago na sexta, 3 dias úteis: segunda, terça e
quarta -- a previsão é a quarta. Zero dias é "pronta entrega": a data é o
próprio dia do começo.

Mora no `core` porque o pedido (core) e o orçamento (sistema_interno) usam
a mesma conta, e o `core` não pode depender do `sistema_interno`.
"""

from __future__ import annotations

import datetime as dt
from functools import lru_cache

#: O teto do campo nas telas. Um ano útil é mais que qualquer máquina
#: da casa; acima disso é dedo escorregando no teclado ("150" virando
#: "1500"), e a previsão sairia em 2031.
PRAZO_MAXIMO = 250

#: Os feriados nacionais de data fixa (mês, dia). O 20 de novembro
#: (Consciência Negra) é nacional desde 2024 (Lei 14.759/2023).
FERIADOS_FIXOS = (
    (1, 1),    # Confraternização Universal
    (4, 21),   # Tiradentes
    (5, 1),    # Dia do Trabalho
    (9, 7),    # Independência
    (10, 12),  # Nossa Senhora Aparecida
    (11, 2),   # Finados
    (11, 15),  # Proclamação da República
    (11, 20),  # Consciência Negra
    (12, 25),  # Natal
)


def pascoa(ano: int) -> dt.date:
    """O domingo de Páscoa (algoritmo de Meeus/Jones/Butcher)."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    mes, dia = divmod(h + m - 7 * n + 114, 31)
    return dt.date(ano, mes, dia + 1)


@lru_cache(maxsize=64)
def feriados_nacionais(ano: int) -> frozenset:
    datas = {
        dt.date(ano, mes, dia)
        for mes, dia in FERIADOS_FIXOS
        if not (mes == 11 and dia == 20 and ano < 2024)
    }
    datas.add(pascoa(ano) - dt.timedelta(days=2))  # Sexta-feira Santa
    return frozenset(datas)


def dia_util(data: dt.date) -> bool:
    return data.weekday() < 5 and data not in feriados_nacionais(data.year)


def somar_dias_uteis(inicio, dias):
    """O dia em que `dias` dias úteis terminam, contados DEPOIS de `inicio`.

    `inicio` pode ser data ou data e hora (vale o dia). Sem começo ou sem
    prazo, não há previsão: devolve None.
    """
    if inicio is None or dias is None:
        return None
    if isinstance(inicio, dt.datetime):
        inicio = inicio.date()
    data = inicio
    restantes = max(int(dias), 0)
    while restantes:
        data += dt.timedelta(days=1)
        if dia_util(data):
            restantes -= 1
    return data


def texto_dos_dias(dias) -> str:
    """15 -> "15 dias úteis"; 1 -> "1 dia útil"; 0 -> "pronta entrega"."""
    if dias is None:
        return ""
    dias = int(dias)
    if dias == 0:
        return "pronta entrega"
    return "1 dia útil" if dias == 1 else f"{dias} dias úteis"


def texto_da_producao(dias, previsao=None, *, ano=False) -> str:
    """A frase que o cliente e a equipe leem.

    "Produção: 15 dias úteis — previsão 04/12" (com a data quando o começo
    já existe; sem ela, só o prazo). Vazio quando ninguém informou o prazo:
    prazo que ninguém deu não é prazo zero.
    """
    if dias is None:
        return ""
    frase = f"Produção: {texto_dos_dias(dias)}"
    if previsao is not None:
        formato = "%d/%m/%Y" if ano else "%d/%m"
        frase += f" — previsão {previsao.strftime(formato)}"
    return frase


def ler_prazo(valor):
    """O que veio do campo da tela: None (apagou) ou um inteiro válido.

    Levanta ValueError com a frase da tela quando não é um número de dias.
    """
    texto = str(valor if valor is not None else "").strip()
    if not texto:
        return None
    if not texto.isdigit():
        raise ValueError("Informe o prazo em dias úteis, só com números (ex.: 15).")
    dias = int(texto)
    if dias > PRAZO_MAXIMO:
        raise ValueError(
            f"Prazo de {dias} dias úteis passa de um ano de fábrica. "
            f"O máximo é {PRAZO_MAXIMO}."
        )
    return dias
