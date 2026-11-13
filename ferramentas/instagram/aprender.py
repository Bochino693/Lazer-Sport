#!/usr/bin/env python3
"""Aprende com as publicacoes da conta e gera o guia de boas praticas.

Le todas as publicacoes do Instagram, mede o que rendeu mais curtidas e
comentarios e escreve ferramentas/instagram/aprendizado.md. O agente le esse
guia antes de criar conteudo. Rode de novo depois de cada publicacao: os
resultados novos entram na conta e o guia se atualiza sozinho.

Uso:
  python3 ferramentas/instagram/aprender.py              # busca na API
  python3 ferramentas/instagram/aprender.py dados.json   # usa um arquivo ja baixado

Limite: mede so curtidas + comentarios da propria conta. Alcance, visualizacoes
e salvamentos exigem a permissao instagram_manage_insights no token.
"""
import datetime
import json
import os
import re
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request

IG_ID = os.environ.get("IG_USER_ID", "17841403192592166")
AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, "aprendizado.md")
MESES_RECENTES = 18


def baixar():
    url = f"https://graph.facebook.com/{IG_ID}/media?" + urllib.parse.urlencode({
        "fields": "id,caption,media_type,media_product_type,permalink,timestamp,like_count,comments_count",
        "limit": 100})
    token = os.environ.get("IG_TOKEN", "injetado-pelo-proxy")
    itens = []
    while url:
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                d = json.load(resp)
        except urllib.error.HTTPError as e:
            sys.exit(f"ERRO HTTP {e.code}: {e.read().decode(errors='replace')[:400]}")
        except urllib.error.URLError as e:
            sys.exit(f"ERRO de rede: {e.reason}")
        itens += d.get("data", [])
        url = d.get("paging", {}).get("next")
    return itens


def formato(m):
    if m["media_type"] == "VIDEO":
        return "Reel/vídeo"
    return "Carrossel" if m["media_type"] == "CAROUSEL_ALBUM" else "Foto"


def tracos(m):
    """Caracteristicas da legenda que podem explicar o resultado."""
    c = m.get("caption") or ""
    primeira = c.strip().split("\n")[0] if c.strip() else ""
    return {
        "Abre com pergunta": "?" in primeira,
        "Legenda curta (até 300 caracteres)": len(c) <= 300,
        "Legenda longa (mais de 800 caracteres)": len(c) > 800,
        "Lista de especificações (3+ linhas curtas)": sum(
            1 for l in c.split("\n") if 3 <= len(l.strip()) <= 45) >= 5,
        "Cita WhatsApp ou orçamento": bool(re.search(r"whats|orçamento|orcamento", c, re.I)),
        "Mostra preço (R$)": "R$" in c,
        "Pede comentário": bool(re.search(r"comente|comenta |marque", c, re.I)),
        "Tem 5+ hashtags": c.count("#") >= 5,
    }


def main():
    if len(sys.argv) > 1:
        itens = json.load(open(sys.argv[1], encoding="utf8"))
    else:
        itens = baixar()
    if not itens:
        sys.exit("ERRO: nenhuma publicação encontrada.")
    for m in itens:
        m["eng"] = m.get("like_count", 0) + m.get("comments_count", 0)
        m["data"] = m["timestamp"][:10]

    hoje = max(m["data"] for m in itens)
    corte = (datetime.date.fromisoformat(hoje) - datetime.timedelta(days=30 * MESES_RECENTES)).isoformat()
    rec = [m for m in itens if m["data"] >= corte]
    med_rec = statistics.median(m["eng"] for m in rec) if rec else 0

    L = ["# Aprendizado do Instagram — Lazer & Sport", "",
         f"Gerado por `aprender.py` com {len(itens)} publicações (até {hoje}). "
         "Engajamento = curtidas + comentários. Não edite à mão: rode o script de novo.", ""]

    L += ["## Como a conta está indo", "", "| Ano | Publicações | Mediana de engajamento | Melhor |", "|---|---|---|---|"]
    for ano in sorted({m["data"][:4] for m in itens}):
        v = [m["eng"] for m in itens if m["data"].startswith(ano)]
        L.append(f"| {ano} | {len(v)} | {statistics.median(v):g} | {max(v)} |")

    L += ["", f"## O que funciona agora (últimos {MESES_RECENTES} meses, {len(rec)} publicações)", "",
          f"Mediana do período: {med_rec:g}.", "", "| Formato | Publicações | Mediana | Média de comentários |", "|---|---|---|---|"]
    for f in ("Reel/vídeo", "Carrossel", "Foto"):
        v = [m for m in rec if formato(m) == f]
        if v:
            L.append(f"| {f} | {len(v)} | {statistics.median(m['eng'] for m in v):g} | "
                     f"{statistics.mean(m.get('comments_count', 0) for m in v):.1f} |")

    L += ["", "| Característica da legenda | Com (mediana) | Sem (mediana) | Publicações com |", "|---|---|---|---|"]
    achados = []
    for nome in tracos(rec[0]) if rec else []:
        com = [m["eng"] for m in rec if tracos(m)[nome]]
        sem = [m["eng"] for m in rec if not tracos(m)[nome]]
        if len(com) >= 5 and len(sem) >= 5:
            a, b = statistics.median(com), statistics.median(sem)
            L.append(f"| {nome} | {a:g} | {b:g} | {len(com)} |")
            achados.append((a - b, nome, a, b))
    L += ["", "Amostras pequenas: trate como indício, não como regra.", ""]

    dias = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
    por_dia = {}
    for m in rec:
        por_dia.setdefault(datetime.date.fromisoformat(m["data"]).weekday(), []).append(m["eng"])
    L += ["| Dia da semana | Publicações | Mediana |", "|---|---|---|"]
    for d in sorted(por_dia):
        L.append(f"| {dias[d]} | {len(por_dia[d])} | {statistics.median(por_dia[d]):g} |")

    def bloco(titulo, lista, n):
        out = ["", f"## {titulo}", ""]
        for m in sorted(lista, key=lambda m: -m["eng"])[:n]:
            cap = (m.get("caption") or "").strip().split("\n")[0][:90]
            out.append(f"- {m['data']} · {formato(m)} · {m.get('like_count', 0)} curtidas, "
                       f"{m.get('comments_count', 0)} comentários · [{cap}]({m['permalink']})")
        return out

    L += bloco(f"Melhores dos últimos {MESES_RECENTES} meses", rec, 10)
    L += bloco("Melhores de todos os tempos", itens, 10)

    L += ["", "## Regras para a próxima publicação", ""]
    for dif, nome, a, b in sorted(achados, reverse=True):
        if dif > 0:
            L.append(f"- Preferir: **{nome}** (mediana {a:g} contra {b:g}).")
    for dif, nome, a, b in sorted(achados):
        if dif < 0:
            L.append(f"- Evitar: **{nome}** (mediana {a:g} contra {b:g}).")
    L += ["- Antes de criar, abrir os 3 melhores posts recentes acima e seguir a estrutura deles "
          "com produto e texto diferentes.",
          "- Depois de publicar, rodar este script de novo após 7 dias para o resultado entrar no guia.", ""]

    open(SAIDA, "w", encoding="utf8").write("\n".join(L))
    print(f"OK {SAIDA} ({len(itens)} publicações, {len(rec)} recentes)")


if __name__ == "__main__":
    main()
