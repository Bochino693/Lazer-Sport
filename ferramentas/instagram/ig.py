#!/usr/bin/env python3
"""Cliente de linha de comando para a API oficial do Instagram (graph.facebook.com).

O token de acesso NAO fica neste arquivo: o proxy do ambiente injeta o
cabecalho Authorization nas chamadas para graph.facebook.com. Fora desse
ambiente, defina a variavel IG_TOKEN.

Uso:
  python3 ferramentas/instagram/ig.py perfil
  python3 ferramentas/instagram/ig.py posts [N]
  python3 ferramentas/instagram/ig.py comentarios <media_id>
  python3 ferramentas/instagram/ig.py insights <media_id>
  python3 ferramentas/instagram/ig.py publicar-foto <url_publica_da_imagem> <legenda>
  python3 ferramentas/instagram/ig.py publicar-reel <url_publica_do_video> <legenda>
  python3 ferramentas/instagram/ig.py responder <comment_id> <mensagem>
  python3 ferramentas/instagram/ig.py ocultar <comment_id>
  python3 ferramentas/instagram/ig.py apagar-comentario <comment_id>
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://graph.facebook.com"
# Conta @lazersportbrinquedos; troque com a variavel IG_USER_ID se precisar.
IG_ID = os.environ.get("IG_USER_ID", "17841403192592166")


def call(method, path, params=None):
    url = f"{BASE}/{path.lstrip('/')}"
    data = None
    if params:
        encoded = urllib.parse.urlencode(params)
        if method == "GET":
            url += "?" + encoded
        else:
            data = encoded.encode()
    token = os.environ.get("IG_TOKEN", "injetado-pelo-proxy")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        sys.exit(f"ERRO HTTP {e.code} em {method} {path}: {body}")
    except urllib.error.URLError as e:
        sys.exit(f"ERRO de rede em {method} {path}: {e.reason}")


def show(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def publish(container_params):
    uid = IG_ID
    container = call("POST", f"{uid}/media", container_params)["id"]
    # Videos precisam terminar de processar antes de publicar.
    for _ in range(60):
        status = call("GET", container, {"fields": "status_code"}).get("status_code")
        if status in (None, "FINISHED"):
            break
        if status == "ERROR":
            sys.exit(f"ERRO: o Instagram rejeitou a midia (container {container}).")
        time.sleep(5)
    else:
        sys.exit(f"ERRO: a midia nao terminou de processar (container {container}).")
    show(call("POST", f"{uid}/media_publish", {"creation_id": container}))


def main(argv):
    if not argv:
        sys.exit(__doc__)
    cmd, args = argv[0], argv[1:]

    if cmd == "perfil":
        show(call("GET", IG_ID, {
            "fields": "id,username,name,followers_count,follows_count,media_count"}))
    elif cmd == "posts":
        limit = args[0] if args else "5"
        show(call("GET", f"{IG_ID}/media", {
            "fields": "id,caption,media_type,permalink,timestamp,like_count,comments_count",
            "limit": limit}))
    elif cmd == "comentarios" and len(args) == 1:
        show(call("GET", f"{args[0]}/comments", {
            "fields": "id,text,username,timestamp,like_count,hidden"}))
    elif cmd == "insights" and len(args) == 1:
        show(call("GET", f"{args[0]}/insights", {
            "metric": "reach,likes,comments,shares,saved,total_interactions"}))
    elif cmd == "publicar-foto" and len(args) == 2:
        publish({"image_url": args[0], "caption": args[1]})
    elif cmd == "publicar-reel" and len(args) == 2:
        publish({"media_type": "REELS", "video_url": args[0], "caption": args[1]})
    elif cmd == "responder" and len(args) == 2:
        show(call("POST", f"{args[0]}/replies", {"message": args[1]}))
    elif cmd == "ocultar" and len(args) == 1:
        show(call("POST", args[0], {"hide": "true"}))
    elif cmd == "apagar-comentario" and len(args) == 1:
        show(call("DELETE", args[0]))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
