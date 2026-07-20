"""
Diagnostico e correcao de imagens Cloudinary <-> banco de dados.

Como usar:
    1. Confira as credenciais na secao "PREENCHA AQUI" abaixo.
    2. No terminal do PyCharm (com o venv do projeto ativo), rode:
           pip install psycopg2-binary requests --break-system-packages
           python diagnostico_imagens.py
    3. Leia o resumo no final. Registros "QUEBRADO" sao os que precisam de ajuste.
"""

import psycopg2
import requests

# ====== PREENCHA AQUI (pode copiar direto do que voce ja tem) ======
DATABASE_URL = "postgresql://postgres.yjcponeqpyuhntwoiacs:633lazersport@aws-1-sa-east-1.pooler.supabase.com:5432/postgres"
CLOUDINARY_CLOUD_NAME = "dgikjmki8"
CLOUDINARY_API_KEY = "342516516215559"
CLOUDINARY_API_SECRET = "6G3Zg2Y31tiZ_6mzx8atuAFz8Xc"
# =====================================================================

# Prefixo que o django-cloudinary-storage aplica automaticamente
# (vem do MEDIA_URL do settings.py, que e '/media/')
PREFIX = "media/"

# Tabela, coluna e um "apelido" pra exibir no relatorio.
# Adicione/remova linhas aqui se tiver mais campos de imagem no projeto.
CAMPOS_IMAGEM = [
    ("core_categoriasbrinquedos", "imagem_categoria", "Categoria"),
    ("core_brinquedos", "imagem_brinquedo", "Brinquedo"),
    ("core_estabelecimentos", "imagem_estabelecimento", "Estabelecimento"),
    ("core_combos", "imagem_combo", "Combo"),
    ("core_promocoes", "imagem_promocao", "Promocao"),
    ("core_imagempeca", "imagem", "Imagem de Peca"),
    ("core_imagemprojetobrinquedo", "imagem", "Imagem de Projeto"),
    ("core_imagemevento", "imagem", "Imagem de Evento"),
    ("core_manutencaoimagem", "imagem", "Imagem de Manutencao"),
    ("core_imagenssite", "imagem", "Banner do Site"),
]


def listar_todos_recursos_cloudinary():
    """Busca TODOS os public_ids reais que existem na conta Cloudinary."""
    todos = {}
    next_cursor = None
    while True:
        params = {"type": "upload", "max_results": 500}
        if next_cursor:
            params["next_cursor"] = next_cursor
        resp = requests.get(
            f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/resources/image",
            auth=(CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET),
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        for recurso in data.get("resources", []):
            pid = recurso["public_id"]
            todos[pid] = recurso.get("secure_url", "")
        next_cursor = data.get("next_cursor")
        if not next_cursor:
            break
    return todos


def sugerir_correcao(esperado, existentes_por_pasta):
    """Tenta achar um arquivo parecido na mesma pasta (caso de sufixo diferente)."""
    pasta = "/".join(esperado.split("/")[:-1])
    base = esperado.split("/")[-1].split("_")[0].lower()
    candidatos = existentes_por_pasta.get(pasta, [])
    for candidato in candidatos:
        nome = candidato.split("/")[-1].lower()
        if nome.startswith(base):
            return candidato
    return None


def main():
    print("Buscando lista real de imagens no Cloudinary...")
    existentes = listar_todos_recursos_cloudinary()
    print(f"Encontradas {len(existentes)} imagens na conta Cloudinary.\n")

    por_pasta = {}
    for pid in existentes:
        pasta = "/".join(pid.split("/")[:-1])
        por_pasta.setdefault(pasta, []).append(pid)

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    total_ok = 0
    quebrados = []

    for tabela, coluna, apelido in CAMPOS_IMAGEM:
        cur.execute(
            f"SELECT to_regclass('public.{tabela}')"
        )
        if cur.fetchone()[0] is None:
            continue  # tabela nao existe nesse projeto, pula

        cur.execute(
            f"SELECT id, {coluna} FROM public.{tabela} "
            f"WHERE {coluna} IS NOT NULL AND {coluna} != ''"
        )
        linhas = cur.fetchall()

        for reg_id, caminho in linhas:
            esperado = PREFIX + caminho
            if esperado in existentes:
                total_ok += 1
            else:
                sugestao = sugerir_correcao(esperado, por_pasta)
                quebrados.append((apelido, tabela, coluna, reg_id, caminho, sugestao))

    cur.close()
    conn.close()

    print(f"OK: {total_ok} imagens batem certinho com o Cloudinary.\n")

    if not quebrados:
        print("Nenhum registro quebrado encontrado. Tudo certo!")
        return

    print(f"QUEBRADOS: {len(quebrados)} registros nao encontraram a imagem no Cloudinary:\n")
    for apelido, tabela, coluna, reg_id, caminho, sugestao in quebrados:
        print(f"- [{apelido}] {tabela}.id={reg_id} ({coluna}='{caminho}')")
        if sugestao:
            sugerido_sem_prefixo = sugestao[len(PREFIX):] if sugestao.startswith(PREFIX) else sugestao
            print(f"    Sugestao: existe um arquivo parecido -> '{sugerido_sem_prefixo}'")
            print(
                f"    SQL para corrigir: UPDATE public.{tabela} SET {coluna} = "
                f"'{sugerido_sem_prefixo}' WHERE id = {reg_id};"
            )
        else:
            print("    Nenhum arquivo parecido encontrado na mesma pasta -- "
                  "provavelmente precisa subir essa imagem de novo pelo admin.")
        print()


if __name__ == "__main__":
    main()