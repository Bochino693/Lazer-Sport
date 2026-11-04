"""Amostra CPU e memória do gunicorn (mestre + workers) durante o teste.

Uso::

    python cpu_amostra.py <pid_do_mestre> <arquivo_csv> [intervalo_s]

Cada linha do CSV: ``epoch,cpu_pct,rss_mb,workers,threads,load1``.

``cpu_pct`` é a soma de utime+stime do mestre e de todos os filhos entre
duas amostras, dividida pelo intervalo -- ou seja, "quantos núcleos" o
servidor usou (100 = um núcleo inteiro). Preferido ao ``ps -o %cpu``, que
mostra a média desde que o processo nasceu e esconde o pico.
"""

from __future__ import annotations

import os
import sys
import time


CLK = os.sysconf("SC_CLK_TCK")
PAGINA = os.sysconf("SC_PAGE_SIZE")


def _stat(pid: int):
    try:
        with open(f"/proc/{pid}/stat") as f:
            dados = f.read()
    except OSError:
        return None
    # o nome do processo vai entre parênteses e pode ter espaço
    resto = dados[dados.rindex(")") + 2:].split()
    return {
        "ppid": int(resto[1]),
        "ticks": int(resto[11]) + int(resto[12]),
        "threads": int(resto[17]),
        "rss": int(resto[21]) * PAGINA,
    }


def _familia(mestre: int):
    pids = [mestre]
    for nome in os.listdir("/proc"):
        if not nome.isdigit():
            continue
        pid = int(nome)
        if pid == mestre:
            continue
        s = _stat(pid)
        if s and s["ppid"] == mestre:
            pids.append(pid)
    return pids


def main():
    mestre = int(sys.argv[1])
    destino = sys.argv[2]
    intervalo = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0

    ticks_antes: dict[int, int] = {}
    t_antes = time.monotonic()
    with open(destino, "w") as saida:
        saida.write("epoch,cpu_pct,rss_mb,workers,threads,load1\n")
        saida.flush()
        while True:
            time.sleep(intervalo)
            agora = time.monotonic()
            pids = _familia(mestre)
            if not pids or _stat(mestre) is None:
                break
            total = 0
            rss = 0
            threads = 0
            novos: dict[int, int] = {}
            for pid in pids:
                s = _stat(pid)
                if not s:
                    continue
                novos[pid] = s["ticks"]
                total += s["ticks"] - ticks_antes.get(pid, s["ticks"])
                rss += s["rss"]
                threads += s["threads"]
            cpu = 100.0 * total / CLK / (agora - t_antes)
            load1 = os.getloadavg()[0]
            saida.write(
                f"{time.time():.0f},{cpu:.1f},{rss / 1048576:.0f},{len(pids) - 1},{threads},{load1:.2f}\n"
            )
            saida.flush()
            ticks_antes = novos
            t_antes = agora


if __name__ == "__main__":
    main()
