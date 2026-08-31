# Render: configuração para evitar 502

O endereço `/healthz/` responde sem consultar o Supabase e deve ser usado
como **Health Check Path** do serviço web no Render.

## Configuração do serviço web

- Runtime: `Python 3`
- Build Command: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
- Start Command: deixe vazio para usar o processo `web` do `Procfile`, ou
  copie exatamente a linha `web:` sem o prefixo `web:`.
- Health Check Path: `/healthz/`

O processo web usa um worker com quatro threads. Isso mantém quatro
requisições simultâneas, mas evita duplicar toda a aplicação em memória —
causa comum de `SIGKILL` e 502 em instâncias pequenas. O timeout de 90
segundos dá margem ao primeiro acesso depois de um reinício, enquanto as
consultas ao PostgreSQL continuam limitadas a 12 segundos pelas configurações
do Django.

## Se o erro reaparecer

No painel do Render, abra **Logs** e pesquise, nessa ordem:

1. o `Rndr-Id` mostrado na página de erro;
2. `WORKER TIMEOUT`;
3. `SIGKILL`, `SIGTERM` ou `Out of memory`;
4. `connection` ou `SUPABASE_DATABASE_URL`;
5. `request_failed`.

Um 502 que também atinge `/system/` e `/healthz/` ocorre antes de o Django
escolher a view; nesse caso, procurar somente a rota de orçamento ou O.S.
leva ao lugar errado. O identificador do Render localiza o processo e o
instante exatos da queda.
