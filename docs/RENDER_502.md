# Render: configuração para evitar 502

O endereço `/healthz/` responde sem consultar o Supabase e deve ser usado
como **Health Check Path** do serviço web no Render.

## Dois endereços, dois trabalhos

| Endereço    | Quem chama            | Toca o banco? |
|-------------|-----------------------|---------------|
| `/healthz/` | o Render              | não           |
| `/pronto/`  | o painel, no navegador| sim (`SELECT 1`) |

`/healthz/` **não pode** tocar o banco: ele é o que decide se a instância
está viva, e uma oscilação do Supabase passaria a derrubar o processo web
inteiro -- que não volta mais rápido por isso.

`/pronto/` existe para o outro problema. A instância dorme depois de
alguns minutos sem requisição, e o painel só bate o pulso da central de
avisos com a **aba visível**: painel numa aba de fundo, ou com a tela
bloqueada, é painel sem pulso. Quando a pessoa volta e clica, é esse
clique que paga a conta de acordar processo E conexão de banco -- dezenas
de segundos, e passando de 90 o gunicorn mata o worker e devolve 502.

O painel agora acorda antes de agir: ao voltar para a aba, e antes de
qualquer POST feito depois de mais de 4 minutos parado. A espera continua
existindo, mas acontece **antes** da ação, com "Reconectando..." escrito
no botão, em vez de virar erro depois. Quem repete é o GET, que é seguro
repetir; o POST sai uma vez só, porque repeti-lo às cegas criaria a
segunda proposta ou o segundo pagamento.

Ver o bloco "ACORDAR ANTES DE AGIR" em `sistema_interno/static/interno/painel.js`.

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
