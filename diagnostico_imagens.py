"""
Sincroniza os campos de imagem que ficaram vazios no Supabase, copiando
o valor original do banco antigo do Render (que ja funciona certinho).

Por que copiar em vez de tentar "adivinhar" o formato certo: os valores
salvos no banco do Render ja sao exatamente os que fazem a imagem
aparecer hoje. Copiar direto elimina qualquer chance de erro de
formatacao (prefixo, extensao, maiusculo/minusculo etc).

O QUE ESSE SCRIPT NAO FAZ:
- Nao apaga nada.
- Nao mexe em nenhuma coluna que nao seja de imagem.
- So preenche onde o Supabase esta NULL ou vazio -- nunca sobrescreve
  um valor que ja existe (pra nao perder imagem nova que voce subiu
  depois da migracao).

Como usar:
    pip install psycopg2-binary --break-system-packages
    python sincronizar_imagens.py            # so mostra o que faria (dry-run)
    python sincronizar_imagens.py --aplicar   # aplica de verdade
"""

import sys
import psycopg2

RENDER_DATABASE_URL = "postgresql://lazer_db_user:Q87NOM8DmALIGK4KfvPU0sEDL6NYEHmv@dpg-d6jeqhnkijhs739fnol0-a.oregon-postgres.render.com/lazer_db_3a61"
SUPABASE_DATABASE_URL = "postgresql://postgres.yjcponeqpyuhntwoiacs:633lazersport@aws-1-sa-east-1.pooler.supabase.com:5432/postgres"

# (tabela, coluna, apelido) -- extraido direto dos models.py que voce mandou
CAMPOS_IMAGEM = [
    ("core_imagenssite", "imagem", "Banner do Site"),
    ("core_clientes", "logo_cliente", "Logo de Cliente"),
    ("core_categoriasbrinquedos", "imagem_categoria", "Categoria"),
    ("core_estabelecimentos", "imagem_estabelecimento", "Estabelecimento"),
    ("core_brinquedos", "imagem_brinquedo", "Brinquedo"),
    ("core_imagempeca", "imagem", "Imagem de Peca"),
    ("core_combos", "imagem_combo", "Combo"),
    ("core_promocoes", "imagem_promocao", "Promocao"),
    ("core_imagemprojetobrinquedo", "imagem", "Imagem de Projeto"),
    ("core_imagemevento", "imagem", "Imagem de Evento"),
    ("core_manutencaoimagem", "imagem", "Imagem de Manutencao"),
]


def main():
    aplicar = "--aplicar" in sys.argv

    origem = psycopg2.connect(RENDER_DATABASE_URL)
    destino = psycopg2.connect(SUPABASE_DATABASE_URL)
    cur_origem = origem.cursor()
    cur_destino = destino.cursor()

    total_corrigidos = 0
    total_sem_correspondencia = 0

    for tabela, coluna, apelido in CAMPOS_IMAGEM:
        cur_destino.execute("SELECT to_regclass(%s)", (f"public.{tabela}",))
        if cur_destino.fetchone()[0] is None:
            print(f"[pular] tabela {tabela} nao existe no Supabase")
            continue

        cur_origem.execute("SELECT to_regclass(%s)", (f"public.{tabela}",))
        if cur_origem.fetchone()[0] is None:
            print(f"[pular] tabela {tabela} nao existe no Render")
            continue

        cur_destino.execute(
            f"SELECT id FROM public.{tabela} WHERE {coluna} IS NULL OR {coluna} = ''"
        )
        ids_vazios = [row[0] for row in cur_destino.fetchall()]

        if not ids_vazios:
            print(f"[ok] {apelido} ({tabela}): nenhum registro vazio")
            continue

        cur_origem.execute(
            f"SELECT id, {coluna} FROM public.{tabela} WHERE id = ANY(%s)",
            (ids_vazios,),
        )
        valores_origem = {reg_id: valor for reg_id, valor in cur_origem.fetchall() if valor}

        corrigidos_aqui = 0
        for reg_id in ids_vazios:
            valor = valores_origem.get(reg_id)
            if not valor:
                total_sem_correspondencia += 1
                continue

            corrigidos_aqui += 1
            total_corrigidos += 1
            if aplicar:
                cur_destino.execute(
                    f"UPDATE public.{tabela} SET {coluna} = %s WHERE id = %s",
                    (valor, reg_id),
                )
            else:
                print(f"  [{apelido}] id={reg_id}: definiria {coluna} = '{valor}'")

        print(
            f"[{'aplicado' if aplicar else 'dry-run'}] {apelido} ({tabela}): "
            f"{corrigidos_aqui} de {len(ids_vazios)} corrigidos"
        )

    if aplicar:
        destino.commit()
        print(f"\nPronto. {total_corrigidos} imagens restauradas.")
    else:
        print(
            f"\nDRY-RUN: {total_corrigidos} imagens SERIAM restauradas. "
            f"Rode de novo com --aplicar para gravar de verdade."
        )

    if total_sem_correspondencia:
        print(
            f"{total_sem_correspondencia} registros nao tem imagem nem no Render "
            f"-- esses precisam ser resolvidos subindo a foto de novo pelo admin."
        )

    cur_origem.close()
    cur_destino.close()
    origem.close()
    destino.close()


if __name__ == "__main__":
    main()