"""Resume os CSVs do locust em tabelas Markdown (um bloco por variante).

Uso::

    python resumir.py ferramentas/carga/resultados > resumo.md

Lê, para cada variante ``wN`` (WEB_WORKERS=N):

* ``wN_estagios.csv``      -- janelas de tempo e contagem de 503/429 no log do gunicorn;
* ``wN_uXXX_stats.csv``    -- estatísticas do locust por endpoint (e "Aggregated");
* ``wN_uXXX_failures.csv`` -- falhas por endpoint, com a mensagem;
* ``wN_cpu.csv``           -- amostras de CPU/RSS do gunicorn (cpu_amostra.py).
"""

from __future__ import annotations

import csv
import glob
import os
import re
import sys
from collections import defaultdict


def _ler(caminho):
    with open(caminho, newline="") as f:
        return list(csv.DictReader(f))


def _num(valor, padrao=0.0):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return padrao


def _cpu_na_janela(amostras, inicio, fim):
    dentro = [a for a in amostras if inicio <= _num(a["epoch"]) <= fim]
    if not dentro:
        return None
    cpus = [_num(a["cpu_pct"]) for a in dentro]
    rss = [_num(a["rss_mb"]) for a in dentro]
    return {
        "cpu_media": sum(cpus) / len(cpus),
        "cpu_max": max(cpus),
        "rss_max": max(rss),
        "amostras": len(dentro),
    }


def resumir(pasta):
    saida = []
    etiquetas = sorted(
        os.path.basename(p)[: -len("_estagios.csv")]
        for p in glob.glob(os.path.join(pasta, "*_estagios.csv"))
    )
    for etiqueta in etiquetas:
        estagios = _ler(os.path.join(pasta, f"{etiqueta}_estagios.csv"))
        caminho_cpu = os.path.join(pasta, f"{etiqueta}_cpu.csv")
        amostras = _ler(caminho_cpu) if os.path.exists(caminho_cpu) else []
        workers = estagios[0]["workers"] if estagios else "?"
        saida.append(f"## Variante `{etiqueta}` (WEB_WORKERS={workers})\n")
        saida.append(
            "| Usuários | Req/s | Falhas | 503 escudo | p50 ms | p95 ms | máx ms | "
            "CPU média | CPU máx | RSS máx |"
        )
        saida.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

        por_endpoint = defaultdict(list)
        for estagio in estagios:
            usuarios = int(estagio["usuarios"])
            prefixo = os.path.join(pasta, f"{etiqueta}_u{usuarios:03d}")
            try:
                stats = _ler(prefixo + "_stats.csv")
            except FileNotFoundError:
                continue
            falhas = _ler(prefixo + "_failures.csv") if os.path.exists(prefixo + "_failures.csv") else []
            agregado = next((s for s in stats if s["Name"] == "Aggregated"), None)
            if not agregado:
                continue
            n503_locust = sum(
                int(f["Occurrences"]) for f in falhas if "503 escudo" in f["Error"]
            )
            total = int(agregado["Request Count"])
            falhou = int(agregado["Failure Count"])
            cpu = _cpu_na_janela(amostras, _num(estagio["inicio"]), _num(estagio["fim"]))
            saida.append(
                "| {u} | {rps:.1f} | {f} ({pct:.1f}%) | {s503} | {p50:.0f} | {p95:.0f} | {mx:.0f} | "
                "{cm} | {cx} | {rss} |".format(
                    u=usuarios,
                    rps=_num(agregado["Requests/s"]),
                    f=falhou,
                    pct=100.0 * falhou / total if total else 0.0,
                    s503=f"{n503_locust} (log: {estagio['http503']})",
                    p50=_num(agregado["50%"]),
                    p95=_num(agregado["95%"]),
                    mx=_num(agregado["Max Response Time"]),
                    cm=f"{cpu['cpu_media']:.0f}%" if cpu else "-",
                    cx=f"{cpu['cpu_max']:.0f}%" if cpu else "-",
                    rss=f"{cpu['rss_max']:.0f} MB" if cpu else "-",
                )
            )
            for s in stats:
                if s["Name"] == "Aggregated":
                    continue
                por_endpoint[s["Name"]].append((usuarios, s))

        saida.append("")
        saida.append("### Por endpoint (p50 / p95 / máx em ms; req/s; falhas)\n")
        cabecalho = "| Endpoint | " + " | ".join(f"{int(e['usuarios'])} us." for e in estagios) + " |"
        saida.append(cabecalho)
        saida.append("|---|" + "---:|" * len(estagios))
        for nome in sorted(por_endpoint):
            celulas = []
            linhas = dict(por_endpoint[nome])
            for estagio in estagios:
                s = linhas.get(int(estagio["usuarios"]))
                if not s:
                    celulas.append("-")
                    continue
                total = int(s["Request Count"])
                falhou = int(s["Failure Count"])
                celulas.append(
                    "{p50:.0f}/{p95:.0f}/{mx:.0f} · {rps:.1f}/s · {pct:.0f}%".format(
                        p50=_num(s["50%"]),
                        p95=_num(s["95%"]),
                        mx=_num(s["Max Response Time"]),
                        rps=_num(s["Requests/s"]),
                        pct=100.0 * falhou / total if total else 0.0,
                    )
                )
            saida.append(f"| `{nome}` | " + " | ".join(celulas) + " |")
        saida.append("")

        # mensagens de falha distintas, para o relatório saber o que quebrou
        mensagens = defaultdict(int)
        for p in sorted(glob.glob(os.path.join(pasta, f"{etiqueta}_u*_failures.csv"))):
            usuarios = re.search(r"_u(\d+)_", p).group(1)
            for f in _ler(p):
                mensagens[(int(usuarios), f["Name"], f["Error"][:90])] += int(f["Occurrences"])
        if mensagens:
            saida.append("### Falhas registradas pelo locust\n")
            saida.append("| Usuários | Endpoint | Erro | Ocorrências |")
            saida.append("|---:|---|---|---:|")
            for (u, nome, erro), n in sorted(mensagens.items()):
                saida.append(f"| {u} | `{nome}` | {erro} | {n} |")
            saida.append("")
    return "\n".join(saida)


if __name__ == "__main__":
    print(resumir(sys.argv[1] if len(sys.argv) > 1 else "resultados"))
