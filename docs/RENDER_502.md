# Render: configuração para evitar 502

O endereço `/healthz/` responde sem consultar o Supabase e deve ser usado
como **Health Check Path** do serviço web no Render.

## Dois endereços, dois trabalhos

| Endereço    | Quem chama                          | Toca o banco?    |
|-------------|-------------------------------------|------------------|
| `/healthz/` | o Render                            | não              |
| `/pronto/`  | o painel no navegador, e a batida do próprio servidor | sim (`SELECT 1`) |

> **`/pronto/` não respondia no subdomínio, e isso custava caro.** Ele
> mora em `core/urls.py`, mas o painel atende por `interno.`, onde o
> `SubdomainURLMiddleware` troca o urlconf — e ele não estava na lista de
> rotas globais. Toda chamada voltava **404**.
>
> O estrago não era um endereço quebrado. O painel lê 404 como "o
> servidor não respondeu", então concluía que a instância estava dormindo
> em **toda gravação feita depois de dois minutos parado**, e pagava a
> escada de espera inteira antes de mandar o POST — com o servidor de pé
> o tempo todo. A tarja "Servidor acordando…" aparecia com o servidor
> acordado. Corrigido em `core/middleware.py`.

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

Os parâmetros do gunicorn moram em **`gunicorn.conf.py`**, na raiz do
projeto, e não mais na linha do `Procfile`. Cada número está explicado lá
dentro, e todos podem ser mudados por variável de ambiente no painel do
Render, sem publicar código: `WEB_WORKERS`, `WEB_THREADS`, `WEB_TIMEOUT`,
`WEB_MAX_REQUESTS`.

O processo continua sendo **um worker**, para não duplicar a aplicação em
memória — causa comum de `SIGKILL` e 502 em instância pequena. O que mudou:

| Parâmetro | Antes | Agora | Por quê |
|---|---|---|---|
| `--threads` | 4 | 8 | O trabalho aqui é esperar o Supabase, não calcular. Enquanto uma thread espera o banco, a outra atende. Threads custam pilha, não cópia da aplicação. |
| `--max-requests` | 600 | **0 (desligado)** | Era causa direta de lentidão e de 502 intermitente. Ver abaixo. |
| `backlog` | padrão | 2048 | Segura a conexão durante a partida a frio em vez de deixá-la ser recusada. |

### Por que `--max-requests 600` saiu

Com **um** worker, reciclar significa derrubar o site. A cada 600
requisições o único processo era morto e refeito; tudo que chegava
enquanto o Django subia — allauth, cloudinary, o resto — esperava a
partida inteira, e o que estourava o prazo do proxy voltava como 502 sem
explicação nenhuma. Reciclar worker existe para conter vazamento de
memória; não há vazamento medido neste aplicativo que justifique pagar
esse preço várias vezes por dia.

Se um dia for preciso de volta: `WEB_MAX_REQUESTS=600` no painel. Mas o
certo, nesse caso, é primeiro subir `WEB_WORKERS` para 2 — com dois
processos, a reciclagem de um deixa de ser a queda do site.

> **Antes de subir `WEB_WORKERS`:** o cache do painel é `LocMemCache`, que
> vive dentro do processo. Com dois workers cada um tem o seu, e os
> contadores das bolinhas podem divergir por até
> `INTERNO_AVISOS_CACHE_TTL` segundos entre uma tela e outra. Para mais de
> um worker sem esse efeito, configure um cache compartilhado (Redis)
> antes.

## A instância não pode dormir

Este é o item que mais pesa na percepção de lentidão, e o único que não
tem nada a ver com o código do painel.

O Render suspende um serviço web gratuito depois de **15 minutos sem
requisição de entrada**. Voltar custa de vinte a sessenta segundos: o
contêiner sobe, o Python importa Django, allauth e cloudinary, e só então
a primeira requisição começa a ser atendida. Medido neste projeto, o
Django sobe em menos de um segundo — o resto é a hospedagem.

Para quem usa, a diferença é grosseira: a mesma tela abre em meio segundo
com a instância de pé e leva quase um minuto com ela voltando do sono.

### O que o código faz a respeito

`core/sempre_pronto.py` sobe uma thread que bate em `/pronto/`, pelo
endereço público, a cada 4 minutos. Isso resolve as duas metades do
problema de uma vez:

- **É tráfego de entrada**, e é ausência de tráfego de entrada que decide
  a suspensão. Enquanto a batida existir, a instância não dorme.
- **Aquece a conexão do banco.** `/pronto/` faz um `SELECT 1` e chega
  pela rede, ou seja, cai numa das threads que atendem requisição — que é
  onde a conexão precisa estar quente. O pooler do Supabase encerra
  conexão ociosa, e sem isto a primeira tela depois de uma pausa paga DNS,
  TCP e TLS antes de ler a primeira linha. Isso vale **mesmo numa
  instância paga**, que não dorme.

Roda no processo web e também no `worker` do Procfile — dois processos
batendo é redundância barata.

| Variável | Padrão | Para quê |
|---|---|---|
| `SEMPRE_PRONTO` | ligado em produção | `0` desliga |
| `SEMPRE_PRONTO_INTERVALO` | `240` (segundos) | Cabe com folga nos 15 minutos |
| `SEMPRE_PRONTO_URL` | vazio | Só se o painel atende num domínio diferente do publicado |

Nos logs, procure `sempre_pronto`. Uma linha `sempre_pronto acordou
duration_ms=…` significa que a batida encontrou a instância dormindo —
se ela aparecer, o intervalo está frouxo demais para o seu plano.

### O que isto NÃO resolve

Nada disso encurta a partida a frio de um **deploy**, nem a de uma
instância que já estava dormindo quando o processo subiu. Também não é
substituto para o plano certo: a solução suportada, sem contorno nenhum,
é uma instância paga, que não é suspensa. O que está aqui é o melhor que
o código consegue fazer sozinho.

Duas alternativas, se preferir não depender do próprio processo:

1. **Render Cron Job** (plano pago) chamando `curl -sS
   https://interno.lazersport.com.br/pronto/` a cada 5 minutos.
2. **Um pinger externo gratuito** (UptimeRobot, cron-job.org) no mesmo
   endereço, no mesmo intervalo. É o caminho mais confiável no plano
   gratuito, porque não depende de o processo estar de pé para começar.

### Enquanto ela ainda estiver acordando

O painel deixou de martelar o servidor com tentativas curtas. Uma
sondagem de 8 segundos separa "rede lenta" de "servidor subindo"; a
partir daí é **um pedido só, com 50 segundos de janela**, atendido no
instante em que o processo sobe.

O formato antigo — quatro tentativas de doze segundos — era pior que o
tempo que gastava: cada estouro de prazo é um `abort`, e cada `abort`
joga fora o pedido que já estava na fila do servidor. A instância que ia
responder no segundo 40 nunca chegava a responder.

E a tela diz o que está acontecendo desde o primeiro segundo: tarja
"Servidor acordando (até 1 minuto na primeira vez)…" com contador. Sem
isso, quem está olhando toca de novo — e o toque cancela justamente o
pedido que ia ser respondido.

### Ordem de investigação

Se abrir o aplicativo e trocar de tela continua levando minutos:

1. **A instância estava dormindo?** Nos logs, a primeira requisição depois
   de um período parado leva dezenas de segundos. Se for isso, a correção
   é o plano pago (instância sempre de pé) ou um ping externo de alguns em
   alguns minutos em `/healthz/`.
2. **`DB_CONN_MAX_AGE` está valendo?** Sem reaproveitar conexão, cada
   requisição abre TLS novo com o Supabase antes da primeira consulta. O
   padrão agora é 60 segundos em produção; confirme que `ENVIRONMENT` está
   como `production` ou que `RENDER` vale `true`.
3. **`Server-Timing` na resposta.** Toda resposta traz `app;dur=<ms>`, que
   é o tempo gasto DENTRO do Django. Se ele for pequeno e a espera for
   grande, o tempo está na rede ou na partida da instância, não no código.

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
