# remove_index.py
from django.db import connection

def run():
    with connection.cursor() as cursor:
        cursor.execute("DROP INDEX IF EXISTS core_pedido_mp_payment_id_81fce9bf;")
        print("Índice removido com sucesso")

run()