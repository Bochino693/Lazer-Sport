# Teste de carga: quantas pessoas o site aguenta, onde quebra primeiro e o que a nuvem de jogos vai exigir

Medido em 04/11/2026 com `ferramentas/carga/rodar.sh` (locust + o gunicorn de produção). Os CSVs brutos ficam em `ferramentas/carga/resultados/` e o resumo gerado pela ferramenta em `ferramentas/carga/resultados/resumo.md`.

> **Atualização (mesmo dia, à noite):** as recomendações 1 e 2 da §7 foram feitas -- cache público das telas do catálogo e estáticos fora do escudo -- e tudo foi medido de novo, inclusive com latência artificial de 40 ms por consulta para imitar o Supabase. Os números novos, a conta refeita para o Render e o que ainda falta para "milhares" estão na **§10, "Depois do cache"**. As seções 1-8 descrevem o estado ANTES e continuam valendo como referência.

## Resumo em uma tela

| Pergunta | Resposta medida (esta máquina, sqlite local) | Estimativa para o Render Starter (0,5 CPU, 512 MB, Supabase pela rede) |
|---|---|---|
| Teto de um worker × 8 threads | **~37 páginas/s entregues** (um núcleo inteiro); a partir de ~50 usuários ativos o escudo começa a cortar (2,6 %), com 100 corta 14 %, com 200 corta 51 % | **~13-18 páginas/s pela CPU**, mas o escudo (4 vagas públicas) passa a cortar antes, em **3-5 páginas/s** nas telas que consultam o banco, porque cada consulta custa 20-60 ms de rede |
| Usuários simultâneos "confortáveis" (< 2 % de recusa) | **~50 usuários agressivos** (uma página a cada 1-3 s) com 1 worker; **~100** com 2 workers | **~8-12 usuários agressivos** ou **40-60 visitantes reais** (uma página a cada 10-15 s) no catálogo; o painel aguenta a fábrica inteira (10 pessoas) com folga de threads, mas cada tela leva 0,4-1,0 s pela rede do banco |
| O que quebra primeiro | **CPU do único worker** (GIL): o escudo devolve 503 e o painel fica 10× mais lento sem falhar | **As 4 vagas públicas do escudo**, ocupadas por páginas que esperam o Supabase; CPU vem depois |
| Ganho de `WEB_WORKERS=2` | Dobra a capacidade (100 usuários com 1,3 % de recusa em vez de 14 %) porque aqui há um segundo núcleo | No Starter não há segundo núcleo: o ganho é só resiliência (um worker cai, o outro atende). O dobro medido aqui só aparece no plano com 1 CPU (Standard) |
| Maior alavanca | — | **Cachear as páginas públicas do catálogo** como a home já é (0 consultas, 7 ms): remove 8-12 idas ao banco por página e multiplica por ~10 o que as 4 vagas do escudo atendem |
| Nuvem de jogos (tempo real) | — | **Inviável no gunicorn atual** (8 threads = 8 ligações abertas). Precisa de um serviço separado (ASGI/uvicorn ou Node) ou do Supabase Realtime; ~100 jogadores de ação ou 1.000-2.000 ligações casuais por instância Starter (ver §8) |

## 1. O que foi medido e como

### Ambiente

* **Servidor**: o gunicorn de produção, com o `gunicorn.conf.py` do projeto e `lazer.wsgi:application` -- ou seja, com `HealthcheckWSGI` e `TrafficShieldWSGI` (escudo de tráfego) no caminho. `worker_class=gthread`, `WEB_THREADS=8`, `PUBLIC_CONCURRENCY=4`, porta 8790. Duas variantes: `WEB_WORKERS=1` (como no Render hoje) e `WEB_WORKERS=2`.
* **Configuração**: `ls_carga_settings` (herda a demonstração local: sqlite em arquivo, Cloudinary falso, e-mail em memória), com `DEBUG=False` e WhiteNoise servindo os estáticos pelos finders, como em produção. O banco é uma **cópia** do banco de demonstração (8 brinquedos, 5 categorias, usuário `demo`).
* **Máquina**: 4 vCPU Intel Xeon 2,10 GHz, 16 GB. O locust rodou **na mesma máquina** (com 200 usuários o `load1` chegou a 3,9-4,7, ou seja, a máquina inteira estava ocupada); o estágio de 200 usuários é, por isso, um pouco pessimista.
* **Banco**: sqlite local. O tempo gasto em SQL foi de 0-2 ms por página: **os números abaixo medem só o custo de CPU do Python/Django** (ORM, templates, middlewares). A seção 5 traduz isso para o Postgres remoto.

### Perfis de usuário (`ferramentas/carga/locustfile.py`)

Proporção 4 : 1 (peso do locust).

| Perfil | Host | O que faz | Pausa entre páginas |
|---|---|---|---|
| `ClienteDoSite` (peso 4) | `127.0.0.1` | `/` (3), `/brinquedos/` (3), `/brinquedo/<id>/` (4, id sorteado entre os 8), `/jogos/` (1), `/categoria/<id>/` (2, entre as 5), `/static/site/ls-base.css` (2) | 1-3 s |
| `EquipeDoPainel` (peso 1) | `interno.localhost` | login `POST /login/inner/` (`demo` / `demo-12345`, csrf lido do cookie) e depois `/` (2), `/orcamentos/` (4), `/clientes/` (2), `/producao/` (2), `/estoque/` (2); confere que nenhuma tela redireciona para o login | 2-5 s |

O login funcionou em todos os estágios (POST devolve 302 para `/`; `/orcamentos/` devolve 200, nunca redirecionamento) -- 0 falhas no painel em qualquer estágio.

Um "usuário" do teste é **agressivo**: pede uma página a cada 2 s em média (0,45 req/s). Um visitante real lê a página por 10-15 s antes da próxima, ou seja, **1 usuário do teste ≈ 5 visitantes reais**.

### Estágios

Cinco execuções separadas por variante: 10, 25, 50, 100 e 200 usuários, 60 s cada, criação de 10 usuários/s, com aquecimento prévio (uma passada em cada tela). O escudo devolve `503 busy` quando já há 4 pedidos públicos em andamento; o locustfile conta esse 503 à parte (`503 escudo ocupado`) para separá-lo de falha do Django. O painel (host `interno.`) não disputa essas vagas.

CPU e memória do gunicorn (mestre + workers) foram amostradas a cada 5 s por `cpu_amostra.py` (delta de `utime+stime` lido em `/proc`, e não o `%cpu` do `ps`, que é média desde o início do processo). 100 % = um núcleo inteiro.

## 2. Resultados com 1 worker × 8 threads (configuração atual do Render)

| Usuários | Req/s | Recusas (todas 503 do escudo) | p50 | p95 | máx | CPU média / máx | RSS |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 4,6 | 2 (0,7 %) -- as duas no 1º segundo (rajada de criação) | 26 ms | 56 ms | 341 ms | 9 % / 13 % | 136 MB |
| 25 | 11,4 | 7 (1,0 %) -- todas nos 2 primeiros segundos | 26 ms | 63 ms | 372 ms | 24 % / 49 % | 141 MB |
| 50 | 22,4 | 35 (2,6 %) -- espalhadas pelo estágio inteiro | 31 ms | 110 ms | 398 ms | 55 % / 73 % | 142 MB |
| 100 | 42,8 | 362 (14,3 %) | 50 ms | 180 ms | 490 ms | **97 % / 124 %** | 143 MB |
| 200 | 75,4 | 2 318 (51,2 %) | 84 ms | 420 ms | 852 ms | 124 % / 182 % | 143 MB |

Nenhum erro 5xx do Django, nenhum `WORKER TIMEOUT`, nenhum 429 (o teste não se apresenta como bot). O "máx" dos estágios pequenos é o `POST /login/inner/` (340-370 ms de PBKDF2, custo esperado de um login).

Páginas **entregues** (fora as recusadas): 100 usuários → 36,7/s; 200 usuários → 36,8/s. **O teto de um worker nesta máquina é ~37 páginas/s**: acima disso o escudo só troca páginas por 503.

Por endpoint (p50 / p95 em ms · recusas):

| Endpoint | 10 us. | 50 us. | 100 us. | 200 us. |
|---|---:|---:|---:|---:|
| `/` (home, em cache) | 18 / 31 · 0 % | 25 / 61 · 2 % | 36 / 97 · 16 % | 58 / 380 · 57 % |
| `/brinquedos/` | 30 / 63 · 2 % | 40 / 120 · 4 % | 73 / 180 · 15 % | 74 / 410 · 62 % |
| `/brinquedo/<id>/` | 29 / 44 · 1 % | 35 / 110 · 3 % | 67 / 160 · 20 % | 86 / 410 · 59 % |
| `/categoria/<id>/` | 25 / 44 · 0 % | 33 / 93 · 3 % | 60 / 170 · 16 % | 78 / 370 · 62 % |
| `/jogos/` | 20 / 29 · 0 % | 24 / 86 · 3 % | 47 / 140 · 18 % | 95 / 370 · 59 % |
| `/static/site/ls-base.css` | 4 / 20 · 0 % | 6 / 34 · 4 % | 10 / 34 · 14 % | 27 / 310 · 58 % |
| painel `/` | 33 / 34 · 0 % | 57 / 130 · 0 % | 120 / 220 · 0 % | 240 / 570 · 0 % |
| painel `/orcamentos/` | 48 / 150 · 0 % | 72 / 160 · 0 % | 150 / 290 · 0 % | 300 / 620 · 0 % |
| painel `/clientes/` | 23 / 30 · 0 % | 37 / 89 · 0 % | 88 / 260 · 0 % | 180 / 460 · 0 % |
| painel `/producao/` | 16 / 83 · 0 % | 17 / 77 · 0 % | 47 / 120 · 0 % | 120 / 390 · 0 % |
| painel `/estoque/` | 20 / 34 · 0 % | 21 / 90 · 0 % | 61 / 140 · 0 % | 150 / 450 · 0 % |
| painel `POST /login/inner/` | 340 / 340 · 0 % | 350 / 400 · 0 % | 350 / 490 · 0 % | 440 / 630 · 0 % |

## 3. Resultados com 2 workers × 8 threads

| Usuários | Req/s | Recusas (503 do escudo) | p50 | p95 | máx | CPU média / máx | RSS (2 workers) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 4,6 | 1 (0,4 %) | 26 ms | 66 ms | 495 ms | 9 % / 13 % | 235 MB |
| 25 | 11,5 | 6 (0,9 %) | 27 ms | 86 ms | 917 ms | 27 % / 46 % | 253 MB |
| 50 | 22,4 | 8 (0,6 %) | 33 ms | 100 ms | 421 ms | 52 % / 72 % | 261 MB |
| 100 | 42,6 | 33 (1,3 %) | 31 ms | 110 ms | 508 ms | 103 % / 139 % | 263 MB |
| 200 | 76,6 | 1 181 (26,1 %) | 59 ms | 290 ms | 874 ms | 161 % / 204 % | 265 MB |

Por endpoint (p50 / p95 em ms · recusas):

| Endpoint | 10 us. | 50 us. | 100 us. | 200 us. |
|---|---:|---:|---:|---:|
| `/` | 20 / 230 · 0 % | 23 / 74 · 0 % | 23 / 60 · 2 % | 41 / 140 · 32 % |
| `/brinquedos/` | 30 / 58 · 2 % | 38 / 110 · 1 % | 40 / 120 · 1 % | 72 / 280 · 29 % |
| `/brinquedo/<id>/` | 28 / 49 · 0 % | 36 / 120 · 1 % | 36 / 110 · 2 % | 86 / 280 · 27 % |
| `/categoria/<id>/` | 28 / 39 · 0 % | 38 / 97 · 1 % | 37 / 120 · 0 % | 75 / 270 · 33 % |
| `/jogos/` | 21 / 33 · 0 % | 29 / 75 · 0 % | 28 / 89 · 1 % | 47 / 240 · 32 % |
| `/static/site/ls-base.css` | 4 / 8 · 0 % | 5 / 22 · 0 % | 5 / 23 · 2 % | 14 / 61 · 32 % |
| painel `/` | 35 / 39 · 0 % | 37 / 71 · 0 % | 40 / 130 · 0 % | 200 / 400 · 0 % |
| painel `/orcamentos/` | 61 / 94 · 0 % | 67 / 170 · 0 % | 67 / 180 · 0 % | 250 / 430 · 0 % |
| painel `/clientes/` | 31 / 36 · 0 % | 38 / 72 · 0 % | 34 / 99 · 0 % | 130 / 300 · 0 % |
| painel `/producao/` | 14 / 22 · 0 % | 17 / 61 · 0 % | 24 / 69 · 0 % | 71 / 190 · 0 % |
| painel `/estoque/` | 23 / 27 · 0 % | 25 / 62 · 0 % | 27 / 75 · 0 % | 100 / 240 · 0 % |

Com dois workers, 100 usuários passam de 14,3 % para 1,3 % de recusa e o p50 do painel volta de 120-150 ms para 40-67 ms. A 200 usuários o teto sobe para ~57 páginas/s entregues (subestimado: o locust disputava os 4 núcleos). O ganho vem de **um segundo núcleo** -- ver §6 sobre o que isso significa no Starter.

Memória: 1 worker = 143 MB; 2 workers = 265 MB (≈ 115 MB cada + mestre). Em produção, com psycopg2, Cloudinary e dados reais, conte 150-180 MB por worker.

## 4. Onde satura primeiro

1. **CPU do único worker.** O custo medido é de ~22-25 ms de CPU por requisição (mistura das telas; 55 % de um núcleo para 22,4 req/s). A curva de CPU encosta em 100 % entre 50 e 100 usuários (25-37 req/s). A partir daí cada página demora mais (p50 de 31 → 50 → 84 ms) e, pela lei de Little, mais pedidos ficam "em andamento" ao mesmo tempo.
2. **O escudo corta quando há mais de 4 pedidos públicos em andamento.** Com páginas de 30-40 ms e 20 req/s há em média 0,7 pedidos em andamento, e só rajadas estouram as 4 vagas (2,6 % a 50 usuários). Com a CPU saturada, 40 req/s × 70 ms = 2,8 em andamento, e o estouro vira rotina (14 %). O 503 custa ~1 ms, por isso o servidor continuou entregando ~37 páginas/s e **o painel nunca falhou** -- o escudo está fazendo o que foi feito para fazer.
3. **O painel não falha, mas fica lento junto.** Ele não disputa as vagas públicas, mas disputa as mesmas 8 threads e o mesmo GIL: a 200 usuários públicos o p50 de `/orcamentos/` foi de 48 ms para 300 ms (6×) e o p95 para 620 ms. O escudo protege threads; não protege CPU.
4. **Os estáticos passam pelo escudo.** O WhiteNoise mora dentro do WSGI do Django, então `/static/site/ls-base.css` ocupa uma vaga pública: 305 dos 2 318 cortes a 200 usuários foram em CSS. Um navegador real pede 10-20 estáticos por página; em produção isso compete com as páginas pelas 4 vagas, a menos que uma CDN (Cloudflare) os sirva do cache.
5. **Login custa 350 ms de CPU** (PBKDF2, 870 mil iterações) e segura o GIL. É o certo para senha; só não é coisa de se fazer a cada tela (o painel não faz: a sessão dura).
6. Rajadas de criação de usuários (10 por segundo, todos sem pausa inicial) explicam **100 % dos 503 a 10 e 25 usuários**: a partir do 3º segundo não houve recusa nesses estágios. Em produção o equivalente é uma campanha de WhatsApp/Instagram em que dezenas de pessoas abrem o link no mesmo segundo.

## 5. Consultas por tela e o que o Postgres remoto muda

`ferramentas/carga/consultas_por_tela.py` conta as consultas de cada tela (segunda visita, caches quentes):

| Tela | Consultas | Tempo medido aqui | Estimativa no Render com Supabase (20-60 ms por ida e volta) |
|---|---:|---:|---:|
| `/` (home) | 0 (vitrine em cache 30 min) | 7 ms | 15-20 ms |
| `/brinquedos/` | 8 | 18 ms | 0,2-0,5 s |
| `/brinquedo/<id>/` | 11 | 21 ms | 0,27-0,7 s |
| `/jogos/` | 3 | 16 ms | 0,1-0,2 s |
| `/categoria/<id>/` | 12 | 22 ms | 0,3-0,75 s |
| `/static/site/ls-base.css` | 0 | 0,3 ms | ~1 ms |
| painel `/` | 19 | 18 ms | 0,4-1,2 s |
| painel `/orcamentos/` | 16 | 32 ms | 0,4-1,0 s |
| painel `/clientes/` | 8 | 15 ms | 0,2-0,5 s |
| painel `/producao/` | 3 | 6 ms | 0,1-0,2 s |
| painel `/estoque/` | 7 | 8 ms | 0,15-0,45 s |
| painel `/avisos/estado/` (pulso do sino, a cada 4 s por aba ativa) | 4 | 2 ms | 0,1-0,25 s |

Some a cada tela **+1 consulta** (`SELECT 1` do `conn_health_checks`, que o `CONN_MAX_AGE=60` liga) e mais uma `UPDATE` de sessão quando ela muda. As consultas são sequenciais dentro de uma requisição: o tempo delas se soma, não se sobrepõe. Esse tempo é espera de rede (psycopg2 solta o GIL), não CPU -- é exatamente o que threads escondem bem e o que **ocupa as vagas do escudo** mal.

## 6. Estimativa honesta para o Render

### Premissas, explícitas

* **Render Starter = 0,5 vCPU compartilhada e 512 MB.** Assumo núcleo com velocidade parecida com o Xeon 2,1 GHz daqui; se a vCPU compartilhada render 30 % menos, multiplique as capacidades de CPU por 0,7. Se o serviço ainda estiver no plano **Free** (0,1 CPU, dorme após 15 min -- é o cenário que `docs/RENDER_502.md` e `core/sempre_pronto.py` descrevem), divida tudo por mais 5.
* **Supabase pelo pooler em modo transação**, compute pequeno/free: `pool_size` 15 no lado do servidor, até 200 conexões de cliente. Latência de 20-60 ms por consulta (ida e volta pela rede + pooler); uso 40 ms como valor central.
* Django `CONN_MAX_AGE=60`: cada thread do gunicorn mantém a própria conexão. 1 worker × 8 threads = até 8 conexões de cliente, + 1 do processo `worker` do Procfile (`observar_pendencias`), + 1 do `migrate` de deploy = ~10 de 200. Com 2 workers, ~18. **Conexões não são o gargalo**; o `pool_size` 15 limita a 15 consultas executando ao mesmo tempo, e este site, com 8-16 threads, nunca passa disso sozinho.
* Mistura de páginas e pausa entre páginas iguais às do teste (usuário "agressivo", 0,45 req/s). Para visitantes reais (uma página a cada 10-15 s), multiplique a quantidade de pessoas por ~5.
* `PUBLIC_CONCURRENCY=4`, `WEB_THREADS=8`, `WEB_WORKERS=1`, como hoje.

### Conta

**Pela CPU.** 22-25 ms de CPU por requisição aqui → 45-50 ms em meia vCPU → teto de ~20 req/s; a 70 % de uso (o máximo antes de a fila crescer), **~13-18 páginas/s** ≈ 30-40 usuários agressivos ≈ 150-200 visitantes reais. (Hoje: 1 worker nesta máquina = 37 páginas/s.)

**Pelo escudo, com o banco pela rede.** O tempo de serviço de uma página pública no Render fica em ~0,3 s na média da mistura (home e CSS rápidos; catálogo, produto e categoria com 0,3-0,5 s cada, a 40 ms por consulta). Com 4 vagas, a probabilidade de encontrar as 4 ocupadas (fórmula de perda de Erlang, chegadas aleatórias) é:

| Páginas públicas por segundo | Em andamento (λ × S) | 503 esperados |
|---:|---:|---:|
| 3 | 0,9 | ~1 % |
| 5 | 1,5 | ~5 % |
| 7 | 2,1 | ~10 % |
| 10 | 3,0 | ~20 % |

Rajadas (link aberto por muita gente ao mesmo tempo) dobram isso. Ou seja, **o escudo começa a recusar em 3-5 páginas/s -- bem antes da CPU (13-18/s)**. Em pessoas: **8-12 usuários agressivos, ou 40-60 visitantes reais, no catálogo, antes de 1-5 % de recusa**. Se as 8 threads estiverem todas esperando o banco, o painel também espera.

Aqui o mesmo escudo só começou a cortar a 19 páginas públicas/s, porque uma página levava 35 ms e não 300. **A diferença entre esta máquina e o Render não é a CPU: é a latência do banco multiplicada pelo número de consultas por tela.**

**Painel.** 4 a 10 pessoas na fábrica, cada uma com uma tela a cada 5-10 s mais o pulso de `/avisos/estado/` a cada 4 s por aba ativa (0,25 req/s por aba, 4 consultas cada): 10 pessoas ≈ 4 req/s × 0,4 s médio = 1,6 threads ocupadas, das 4+ que o escudo deixa para o painel. **Cabe**, mas cada tela do painel leva 0,4-1,0 s no Render (16-19 consultas em `/` e `/orcamentos/`), e o pulso do sino, sozinho, faz ~10 consultas/s contínuas no Supabase com 10 abas abertas.

**Memória no Starter.** 1 worker: ~150-180 MB + processo `worker` do Procfile (~100 MB) = ~280 MB, folga. 2 workers: ~400-450 MB em 512 -- cabe sem folga, e um pico (upload de foto, relatório) derruba o processo por OOM. **Não ligue `WEB_WORKERS=2` no Starter sem antes ler a memória real nas métricas do Render.**

**`WEB_WORKERS=2` no Starter não dobra nada**: não há segundo núcleo; dois processos só repartem a mesma meia CPU. O que se ganha é resiliência (um worker preso ou morto não é o site fora do ar) e paralelismo em espera de I/O -- que as threads já dão. O dobro medido aqui aparece no **Standard (1 CPU, 2 GB)**: nele, 2 workers × 8 threads é a configuração que replica o cenário `w2` deste teste (~100 usuários agressivos, ~500 visitantes reais, sem recusa relevante), ainda sujeito ao escudo enquanto as páginas consultarem o banco.

### Em uma frase

Hoje, no Starter, o site público atende confortavelmente algumas dezenas de visitantes simultâneos (um "estouro" de campanha com 50-100 pessoas ao mesmo tempo já produz 503 "busy" em 10-20 % dos cliques), e o painel atende a fábrica inteira, com telas de 0,5-1 s. O limite não é CPU nem conexões: é o tempo que cada página passa esperando o banco enquanto ocupa uma das 4 vagas do escudo.

## 7. Recomendações

Em ordem de retorno por esforço.

1. **Cachear o catálogo público como a home já é.** `/brinquedos/`, `/categoria/<id>/` e `/brinquedo/<id>/` fazem 8-12 consultas por visita e o conteúdo muda só quando a equipe edita o cadastro -- e já existe a chave de versão (`ADMIN_CATALOG_VERSION_KEY` em `core/home_cache.py`) para invalidar. Cache de fragmento (a lista/ficha, não o header com carrinho e usuário) com TTL de 5-30 min e a versão na chave. Efeito: página pública de 0,3-0,5 s para ~0,05 s no Render, e as 4 vagas do escudo passam a atender **~30-50 páginas/s** em vez de 3-5, o que empurra o limite para a CPU (13-18/s). É a mudança que mais pessoas simultâneas compra.
2. **Tirar os estáticos das vagas do escudo.** Duas formas, que se somam: Cloudflare na frente do domínio público com cache de `/static/` (o WhiteNoise já manda `Cache-Control: immutable` para arquivos com hash; `docs/CLOUDFLARE_INTERNO.md` já descreve o DNS), e/ou liberar `/static/` do semáforo no `TrafficShieldWSGI` (três linhas: se o caminho começa com `/static/`, não adquire vaga). Um navegador pede 10-20 estáticos por página; hoje cada um compete com as páginas.
3. **gunicorn no Starter: `WEB_WORKERS=1`, `WEB_THREADS=12`, `PUBLIC_CONCURRENCY=6`.** O trabalho no Render é esperar o banco, e thread é barata (pilha, não cópia da aplicação; 12 threads = 12 conexões de cliente, longe das 200). Mais vagas públicas em troca de mais threads mantém a reserva do painel (12 − 6 = 6). Subir `PUBLIC_CONCURRENCY` **sem** subir threads tiraria vagas do painel. Mantenha `statement_timeout=12 s` e `max_requests=0`.
   No **Standard (1 CPU, 2 GB)**: `WEB_WORKERS=2`, `WEB_THREADS=8`, `PUBLIC_CONCURRENCY=4` (o semáforo é por processo: 8 vagas públicas no total). Antes de 2 workers, cache compartilhado (Redis) para o `LocMemCache` do painel e para o limitador de bots do escudo, que também é por processo -- o aviso já está no `gunicorn.conf.py`.
4. **Menos consultas nas telas do painel que mais abrem.** `painel /` (19) e `/orcamentos/` (16) são 0,4-1,2 s no Render só de rede. Apontar com `django-debug-toolbar` ou `connection.queries` localmente e resolver com `select_related`/`prefetch_related`/`annotate` ou com os contadores já cacheados pelo pulso. Meta: ≤ 6 consultas por tela. Cada consulta a menos são 40 ms a menos para a fábrica inteira, em toda tela, o dia inteiro.
5. **Pulso do sino.** `/avisos/estado/` a cada 4 s por aba ativa é a maior carga contínua do painel (10 abas = 2,5 req/s = ~10 consultas/s no Supabase). Subir o passo ativo para 8-10 s, ou responder 304/`{"mudou": false}` sem tocar o banco quando o pulso (`sistema_interno/pulso.py`) não mudou, corta isso em 2-4×.
6. **Rajadas.** O 503 do escudo devolve `Retry-After: 2`; a tela pública pode tratá-lo (tentar de novo sozinha depois de 1-2 s, em vez de mostrar "busy, retry shortly"). Um `backlog` maior não resolve rajada: a vaga é a do semáforo, não a do socket.
7. **O que medir em produção, antes de mexer em mais alguma coisa:**
   * p50/p95 **por rota** a partir do log de acesso do gunicorn (ele já grava `%(M)sms` por requisição): um `grep '" 200 ' | awk` no log do Render, ou exportar o log para uma planilha, uma semana.
   * quantidade de `503 busy` por hora (escudo) e de `slow_request` (RequestTimingMiddleware, ≥ 1,8 s) -- são os dois sintomas desta análise.
   * CPU % e memória no painel do Render; no Supabase, latência média de consulta e conexões de cliente no pooler.
   * `Server-Timing: app;dur=…` já vai em toda resposta: dá para ler no navegador (aba Network) o tempo do Django sem a rede.
   * Repetir `ferramentas/carga/rodar.sh` depois de cada uma das mudanças acima; o antes/depois está nos CSVs.

## 8. Nuvem de jogos online (tempo real)

### Como é hoje

Os jogos da Arena rodam inteiros no navegador. O servidor só recebe um `POST /jogos/partida/` ao fim da partida e serve `GET /jogos/ranking/` (JSON, sem cache) quando o jogador abre o ranking. É tráfego HTTP curto, cabe no que foi medido. O app `cloud_jogos` guarda apenas os arquivos/builds dos jogos; não há nada em tempo real ainda.

### Por que o gunicorn atual não serve

Um jogo online (sala com outros jogadores, ranking ao vivo, presença) precisa de **uma ligação persistente por jogador** (WebSocket). No gunicorn `gthread`, uma ligação aberta é **uma thread presa pelo tempo da ligação**: com `WEB_THREADS=8`, o 9º jogador conectado esperaria na fila -- e o site e o painel junto, porque são as mesmas 8 threads. O escudo não ajuda (ele limita pedidos públicos, não ligações longas) e `WEB_THREADS=500` não é saída (pilha por thread e GIL). Websocket é incompatível com thread-por-requisição; precisa de um laço de eventos (ASGI).

### Três caminhos

| Caminho | O que é | Capacidade por instância Starter (0,5 CPU, 512 MB) | Prós | Contras |
|---|---|---|---|---|
| **A. O mesmo Django em ASGI** (Django Channels + daphne/uvicorn) | Trocar o servidor do site inteiro de WSGI para ASGI; views atuais rodam num pool de threads; sockets no laço de eventos; Redis como camada de canais | Ligações: milhares (30-60 KB cada → 1 000 ligações ≈ 50 MB). Mensagens: ~3-5 mil/s | Um código só, sessão/autenticação do Django direto no socket | O site inteiro muda de servidor; `HealthcheckWSGI` e `TrafficShieldWSGI` são WSGI e precisariam ser reescritos; qualquer travamento do jogo derruba a loja e o painel; exige Redis (custo) |
| **B. Serviço separado de tempo real** (recomendado para jogo de ação) | Um segundo Web Service no Render só para sockets e salas: Python (FastAPI/uvicorn + `websockets`) ou Node (`ws`). Estado da sala em memória. O Django emite um **token assinado** (HMAC/JWT curto com id do jogador) ao abrir `/jogos/<slug>/`; o serviço valida sem tocar no banco; ao fim da partida, ele (ou o navegador, como hoje) grava no Django por `POST /jogos/partida/` | Jogo de ação (10 atualizações/s por jogador, salas de 4, fan-out ~40 msg/s por jogador): **~100 jogadores**. Casual/turnos/ranking ao vivo (≤ 1 msg/s): **1 000-2 000 ligações**. Node/Go: 2-4× isso | Isola a loja e o painel; escala sozinho (mais instâncias, sala presa a uma instância ou Redis pub/sub); fica no mesmo Render | Mais um serviço para publicar e vigiar; `ping` a cada ~30 s para o proxy do Render não fechar o socket ocioso; instância Free dorme |
| **C. Supabase Realtime** (Broadcast/Presence) | Nenhum servidor de socket próprio: o navegador liga direto no Supabase; o Django só autentica (JWT do Supabase) e grava resultados | Pelos limites do plano, não da instância: no Free, da ordem de 200 ligações simultâneas e cota mensal de mensagens; no Pro, ~500 ligações e cota maior (confirmar na página de preços -- os limites mudam) | Zero infraestrutura; presença e ranking ao vivo prontos; já é o banco do site | Latência de 100-200 ms (passa pelo relé); cota de mensagens inviabiliza jogo de ação a 10-60 Hz; nenhum código do jogo roda no servidor (anti-trapaça fraco) |

Premissas dos números de B: mensagens de ~200 bytes em JSON; servidor só como relé (não roda a física do jogo -- se rodar, divida por 2); ~40 KB de memória por ligação; Python asyncio em meia vCPU processando 3-5 mil mensagens pequenas por segundo. A largura de banda (~1-2 MB/s para 100 jogadores de ação) não é limitante.

### Sugestão de arquitetura

1. **Ranking ao vivo e presença ("quem está jogando agora")**: Supabase Realtime (C). Barato, pronto, e o site já tem o Supabase. O Django continua sendo quem grava o recorde (hoje já valida a partida em `core/ranking.py`).
2. **Partidas multijogador de ação**: serviço separado (B), `jogos-tempo-real.<domínio>`, começando no Starter (~100 jogadores simultâneos de ação). Autenticação por token assinado emitido pelo Django -- o serviço nunca abre conexão com o banco, então não entra na conta das 200 conexões nem do `pool_size` 15. Gravação do resultado pelo caminho que já existe.
3. **Não** mover a loja e o painel para ASGI por causa dos jogos (A): o risco recai sobre o que hoje dá dinheiro, e a proteção WSGI (`traffic_shield`, `healthcheck`) teria que ser refeita.
4. Em qualquer caminho: um `ping`/`pong` a cada 30 s, reconexão automática no navegador, e o estado da sala sobrevivendo à reconexão (o jogador cai e volta na mesma sala por 30-60 s).

## 9. Como repetir

```
ferramentas/carga/
├── locustfile.py            # ClienteDoSite (peso 4) + EquipeDoPainel (peso 1)
├── rodar.sh                 # sobe gunicorn (gunicorn.conf.py, lazer.wsgi) em :8790, roda 10/25/50/100/200 usuários × 60 s, com WEB_WORKERS=1 e =2
├── cpu_amostra.py           # CPU/RSS do gunicorn a cada 5 s (lido de /proc)
├── resumir.py               # tabelas Markdown a partir dos CSVs
├── consultas_por_tela.py    # consultas ao banco por tela (tabelas da §5 e da §10)
├── latencia_db.py           # latência artificial por consulta (CARGA_LATENCIA_MS): o sqlite local "vira" o Supabase pela rede
└── resultados/              # CSVs do locust, logs do gunicorn, amostras de CPU, resumo.md
```

* `rodar.sh` usa `ls_carga_settings` (fora do repositório, na pasta de demonstração): herda `ls_demo_settings`, troca o banco por `carga.sqlite3` (cópia de `demo.sqlite3`, para não travar o servidor de demonstração) e liga `DEBUG=False`. Caminhos ajustáveis por `CARGA_SCRATCH`, `CARGA_VENV`, `CARGA_PYTHONPATH`; estágios por `CARGA_ESTAGIOS`, `CARGA_DURACAO`, `CARGA_SPAWN`, `CARGA_WORKERS`.
* `CARGA_LATENCIA_MS=40` faz cada consulta ao banco dormir 40 ms antes de executar (`latencia_db.py`, ligado pelo `ls_carga_settings`): é a forma de medir aqui o que o Supabase custa pela rede. `CARGA_ROTULO=antes_` / `depois_` dá um prefixo aos arquivos de resultado, para guardar duas medições lado a lado; a etiqueta ganha `_l40` quando a latência está ligada. A comparação da §10 foi: `CARGA_ROTULO=antes_ CARGA_WORKERS=1 CARGA_ESTAGIOS="50 100 200 400" CARGA_DURACAO=60s CARGA_SPAWN=20 ferramentas/carga/rodar.sh`, com `CARGA_LATENCIA_MS=0` e `=40`, antes e depois da mudança.
* Para testar outra configuração do escudo: `PUBLIC_CONCURRENCY=6 WEB_THREADS=12 CARGA_WORKERS=1 ferramentas/carga/rodar.sh`.
* Para apontar o locust à produção (**só fora do horário da fábrica e com poucos usuários**): `locust -f ferramentas/carga/locustfile.py --headless --host https://<dominio> -u 10 -r 2 -t 60s --csv x`, com `CARGA_HOST_INTERNO=interno.<dominio>` e credenciais de uma conta de teste em `CARGA_USUARIO`/`CARGA_SENHA`. Lembre que o teste pede páginas de catálogo sem se identificar como bot; o limitador de 24/min por família de bot não entra.

### Limites desta medição

* sqlite local: o custo do banco está ausente; a §5 e a §6 o repõem por estimativa, não por medida. O próximo passo honesto é rodar o mesmo `locustfile.py` contra um ambiente de homologação ligado a um Supabase (mesmo que o plano Free) e comparar.
* locust na mesma máquina que o servidor: os estágios de 200 usuários (e o `w2` em geral) são subestimados.
* 60 s por estágio: suficiente para ver a curva, curto para ver vazamento de memória ou efeito de `max_requests` (que está desligado).
* 8 brinquedos no banco: páginas de catálogo em produção, com dezenas de produtos e fotos no Cloudinary, custam mais CPU de template do que as daqui.
* A árvore do projeto estava sendo editada por outras pessoas durante a medição (`core/views.py`, templates e CSS do catálogo, entre 17:39 e 17:58). Cada gunicorn carrega o código ao subir: `w1` rodou com a árvore de 17:42:39 e `w2` com a de 17:48:11. Os estágios de carga baixa deram o mesmo resultado nas duas (p50 de 26-33 ms), então a comparação vale, mas a confirmação limpa é repetir `rodar.sh` com a árvore parada (um commit).

## 10. Depois do cache

Medido em 04/11/2026 à noite, na mesma máquina e com a mesma ferramenta, depois de duas mudanças na aplicação:

1. **Cache público das telas do catálogo** (`core/home_cache.py`, `core/views.py`, `core/views_jogos.py`): `/brinquedos/` com os seus filtros e páginas, `/categoria/<id>/` (com `?ordenar=` e `?disp=`), `/brinquedo/<id>/`, `/pecas-reposicao/`, `/pecas/<id>/` e `/jogos/` passam a montar os dados uma vez e a servi-los do cache para todo visitante. Entra no cache só o que é igual para todo mundo (produtos com fotos, categorias e tags já trazidos, totais, textos); o que é de quem está olhando (lista de desejos, curtida, conta, carrinho, ranking pessoal) continua sendo resolvido a cada requisição -- e para o visitante novo, sem conta e sem o cookie do aparelho, sem consulta nenhuma. Toda chave leva a **versão do catálogo**, que os signals apagam no instante em que qualquer produto, foto, categoria, tag, peça, objeto 3D ou jogo cadastrado é salvo ou apagado (`core/signals.py`): a edição aparece na visita seguinte; o TTL (`CATALOG_CACHE_TTL`, 30 min) é só rede de segurança. Busca livre (`?q=`), faixa de preço e valores de categoria/voltagem que não existem não entram no cache (entradas sem limite esgotariam as 300 chaves do `LocMemCache`); são montados na hora, como antes. O contador de cliques de produto e de categoria continua por visita, mas virou um `UPDATE` só (era `get_or_create` + `update`).
2. **Estáticos fora do escudo** (`core/traffic_shield.py`): `/static/`, `/media/`, `/favicon.ico`, `/robots.txt`, `/manifest.webmanifest` e `/sw.js` não disputam mais as 4 vagas públicas. Sondas (`.php`, `.env`, `wp-admin`...) continuam barradas antes, e o limite de bots nas páginas caras continua igual.

O que **não** foi feito, de propósito: cache HTTP público (`Cache-Control: public` / ETag) do HTML das telas. Toda resposta do site carrega `Set-Cookie: csrftoken=...` (o `base.html` cita `{{ csrf_token }}` para o JS) e `Vary: Cookie`; um cache compartilhado que respeitasse o `Vary` não acertaria nunca (o cookie é único por visitante) e um que o ignorasse entregaria o token CSRF e o cookie do aparelho de uma pessoa para as outras. Os estáticos já saem com `Cache-Control: public, max-age=315360000, immutable` (CSS/JS versionados) ou 30 dias (imagens), como antes.

### 10.1 Consultas por tela, antes e depois

`ferramentas/carga/consultas_por_tela.py`, segunda visita de um visitante novo (sem cookie, sem conta). A coluna "com 40 ms" é a mesma medição com `CARGA_LATENCIA_MS=40`: o que a tela custaria no Render só de espera do banco.

| Tela | Consultas antes | Consultas depois | Tempo aqui (sqlite) depois | Tempo com 40 ms por consulta: antes → depois |
|---|---:|---:|---:|---:|
| `/` (home) | 0 | 0 | 5 ms | 5 → 5 ms |
| `/brinquedos/` | 8 | **0** | 9 ms | 341 → 11 ms |
| `/brinquedos/?disponibilidade=loja&ordenar=az` | 8 | **0** | 5 ms | ~340 → 6 ms |
| `/brinquedo/<id>/` | 11 | **1** (contador de cliques) | 10 ms | 460 → 54 ms |
| `/categoria/<id>/` | 12 | **1** (contador de cliques) | 10 ms | 506 → 48 ms |
| `/pecas-reposicao/` | 7 (contadas no código) | **0** | 8 ms | ~280 → 6 ms |
| `/pecas/<id>/` | 5 (contadas no código) | **0** | 6 ms | ~200 → 5 ms |
| `/jogos/` | 3 | **0** (ranking já tinha cache de 60 s) | 10 ms | 131 → 7 ms |
| `/static/site/ls-base.css` | 0 | 0 | 0,2 ms | 0,2 → 0,2 ms |

Quem já marcou algo (cookie do aparelho) paga **+1 consulta** nas listas e nas fichas (as marcações dele, numa consulta só; antes eram duas). Quem está logado paga as consultas da própria conta -- sessão, usuário, perfil, carrinho, selos do cabeçalho, marcações: 8-9 ao todo -- e **nenhuma do catálogo** (`core/tests_cache_catalogo.py` garante). O painel não mudou: `painel /` continua com 19 consultas (0,8 s com 40 ms cada) e `/orcamentos/` com 16 (0,7 s) -- é o próximo alvo (§7, item 4).

### 10.2 Carga com 1 worker × 8 threads, banco rápido (sqlite): o custo de CPU

Estágios de 50, 100, 200 e 400 usuários agressivos (uma página a cada 1-3 s), 60 s cada, criação de 20 usuários/s. "Entregues" = requisições menos os 503 do escudo.

| Usuários | Antes: req/s · 503 · p50/p95 | Depois: req/s · 503 · p50/p95 | Páginas entregues/s: antes → depois | CPU média: antes → depois |
|---:|---|---|---:|---:|
| 50 | 22,6/s · 2,3 % · 26/94 ms | 23,4/s · **1,6 %** · 17/66 ms | 22 → 23 | 42 % → 31 % |
| 100 | 44,3/s · 12,9 % · 43/170 ms | 45,0/s · **3,6 %** · 23/110 ms | 39 → 43 | 98 % → 68 % |
| 200 | 82,7/s · 51,2 % · 78/340 ms | 80,9/s · **23,1 %** · 100/650 ms | 40 → **62** | 133 % → 119 % |
| 400 | 99,7/s · 59,8 % · 1,3/2,3 s | 102,8/s · **42,4 %** · 1,1/2,5 s | 40 → **59** | 149 % → 148 % |

O teto de um worker nesta máquina subiu de **~40 para ~60 páginas entregues por segundo** (1,5×): cada página custa menos CPU sem o ORM montar e hidratar 8-12 consultas, e os estáticos deixaram de ser cortados (0 % de 503 em `/static/site/ls-base.css` em todos os estágios; antes acompanhavam as páginas, 15-68 %). Com 100 usuários agressivos (~500 visitantes reais) a CPU foi de 98 % para 68 % e a recusa de 12,9 % para 3,6 %. (Os p50 acima de 1 s a 400 usuários são o locust saturando a própria máquina, como na §1; esse estágio é pessimista nos dois lados.)

### 10.3 Carga com 40 ms por consulta: o cenário do Render

A mesma sequência com `CARGA_LATENCIA_MS=40` -- cada consulta espera 40 ms antes de executar, soltando o GIL como o psycopg2 faz esperando a rede. É a medição mais próxima do Render Starter com Supabase que esta máquina consegue dar.

| Usuários | Antes: req/s · 503 · p50/p95 | Depois: req/s · 503 · p50/p95 | Páginas entregues/s: antes → depois |
|---:|---|---|---:|
| 50 | 21,2/s · **37,0 %** · 60/700 ms | 22,5/s · **2,0 %** · 35/700 ms | 13 → 22 |
| 100 | 41,4/s · **57,4 %** · 64/750 ms | 43,9/s · **3,4 %** · 54/740 ms | 18 → 42 |
| 200 | 57,0/s · 62,8 % · 1,1/2,0 s | 71,0/s · **10,1 %** · 0,44/1,2 s | 21 → **64** |
| 400 | 52,1/s · 57,3 % · 4,9/6,1 s | 64,1/s · **9,6 %** · 3,7/4,4 s | 22 → **58** |

Por tela pública, com 100 usuários (p50 / p95 · recusa):

| Tela | Antes (40 ms/consulta) | Depois (40 ms/consulta) |
|---|---:|---:|
| `/` | 35 / 370 ms · 66 % | 18 / 120 ms · 5 % |
| `/brinquedos/` | 45 / 590 ms · 67 % | 24 / 96 ms · 5 % |
| `/brinquedo/<id>/` | 74 / 700 ms · 67 % | 68 / 140 ms · 5 % |
| `/categoria/<id>/` | 66 / 660 ms · 66 % | 65 / 150 ms · 3 % |
| `/jogos/` | 57 / 400 ms · 62 % | 21 / 86 ms · 5 % |
| `/static/site/ls-base.css` | 6 / 360 ms · 66 % | 4 / 73 ms · **0 %** |

Antes, com o banco "pela rede", as 4 vagas do escudo saturavam em ~13-22 páginas/s e recusavam 37 % dos cliques já com 50 usuários; depois, o escudo só volta a aparecer a partir de ~60 páginas/s (10 % a 200-400 usuários), quando a CPU do único worker já está em 107-121 %. **O gargalo mudou de lugar: deixou de ser a espera do banco nas vagas do escudo e passou a ser a CPU** -- que é o gargalo "bom", porque escala com o plano. Os p95 de 700 ms dos estágios de 50 e 100 usuários são as telas do painel (16-19 consultas × 40 ms) e o `POST` de login (PBKDF2), não o site público.

### 10.4 Com 2 workers × 8 threads e 40 ms por consulta

| Usuários | Req/s | 503 escudo | p50 / p95 | Páginas entregues/s | CPU média / máx | RSS |
|---:|---:|---:|---:|---:|---:|---:|
| 50 | 22,7 | 1,4 % | 25 / 690 ms | 22 | 32 % / 73 % | 258 MB |
| 100 | 44,1 | 1,7 % | 35 / 690 ms | 43 | 63 % / 138 % | 259 MB |
| 200 | 84,1 | 3,8 % | 52 / 700 ms | 81 | 120 % / 200 % | 260 MB |
| 400 | 127,3 | 8,8 % | 420 / 1 400 ms | **116** | 181 % / 247 % | 261 MB |

Com um segundo núcleo, 200 usuários agressivos (~1 000 visitantes reais) passam com 3,8 % de recusa e p50 de 52 ms; a 400 o teto foi ~116 páginas/s com 8,8 % (e o locust já consumindo a máquina). É o cenário do **Standard** (1 vCPU inteira), não do Starter.

### 10.5 Estimativa refeita para o Render

Premissas: as mesmas da §6 (Starter = 0,5 vCPU compartilhada e 512 MB; Supabase a ~40 ms por consulta; `WEB_WORKERS=1`, `WEB_THREADS=8`, `PUBLIC_CONCURRENCY=4`). **Conversão de "visitantes simultâneos" em pedidos por segundo**: um visitante ativo lê uma página por 15-30 s antes da próxima -- **1 visitante ativo ≈ 0,033-0,067 páginas/s**, ou seja, **1 000 visitantes ≈ 33-67 páginas/s** (mais os estáticos, que o navegador só baixa na primeira página e guarda por 30 dias / um ano). O teste usa usuários agressivos (0,45 req/s): 100 usuários do teste ≈ 700-1 400 visitantes reais nessa conversão.

* **CPU por requisição depois do cache**: 15-16 ms de CPU nesta máquina (68-70 % de um núcleo para 44-45 req/s), contra 22-25 ms antes. Em meia vCPU: ~30-32 ms → teto ~31-33 req/s; a 70 % de uso, **~20-25 páginas/s**.
* **Escudo**: uma página pública no Render passa a custar ~15-20 ms de CPU + 0-1 consulta (40 ms) = 20-60 ms de tempo de serviço, em vez de 300-500 ms. A 20 páginas/s há em média 0,8 pedidos em andamento; a chance de as 4 vagas estarem ocupadas cai para **< 1 %** (Erlang). O escudo deixa de ser o limite; a CPU é.
* **Starter, depois**: **~20-25 páginas/s ≈ 300-700 visitantes ativos** (1 página a cada 15-30 s) **ou 150-250 visitantes "lendo rápido"** (1 página a cada 10 s), com recusa abaixo de 2 %, contra 40-60 antes. Se a vCPU compartilhada render 30 % menos que o Xeon daqui, multiplique por 0,7. **Sem CDN, cada visitante novo também pede 10-20 estáticos** (~1 ms de CPU cada): no primeiro acesso de uma campanha isso dobra o custo de CPU por pessoa -- é o que o Cloudflare na frente de `/static/` resolve.
* **Standard (1 vCPU, 2 GB), `WEB_WORKERS=2` + Redis**: o cenário da §10.4 em uma vCPU inteira → **~50-60 páginas/s** (teto; 40-45 confortável) ≈ **600-1 300 visitantes ativos**, p50 abaixo de 100 ms, painel com folga. Memória: 2 workers = ~260 MB aqui, 350-450 MB em produção, cabe com sobra em 2 GB.
* **Pro (2 vCPU, 4 GB), `WEB_WORKERS=4` + Redis**: ~100-120 páginas/s ≈ **1 500-3 000 visitantes ativos**.

Em uma frase: **o Starter passa de "algumas dezenas" para "algumas centenas" de visitantes simultâneos no catálogo; "milhares" é Standard ou Pro com 2-4 workers, Redis e Cloudflare na frente.**

### 10.6 O que falta para milhares (em ordem)

1. **Plano do Render**: Standard (1 vCPU, 2 GB) para ~1 000 visitantes ativos; Pro (2 vCPU, 4 GB) para 2 000-3 000. No Starter, meia vCPU é o teto, e nenhum cache muda isso.
2. **`WEB_WORKERS=2` (Standard) ou `4` (Pro) + Redis.** O cache é `LocMemCache`, memória de cada processo: com dois workers, a edição feita por um invalida só o cache dele e o outro mostra o catálogo velho por até `CATALOG_CACHE_TTL` (30 min). Antes de subir os workers, criar um Redis (Render Key Value, o plano menor basta) e apontar `CACHES["default"]` para `django.core.cache.backends.redis.RedisCache` com a URL dele -- isso vale para a home, o catálogo, o sino do painel e o ranking dos jogos de uma vez. (O limitador de bots do escudo também é por processo; com 2 workers a cota de um bot dobra -- aceitável.)
3. **Cloudflare na frente do domínio público**, com cache de `/static/` e `/media/` (os cabeçalhos já são os certos: `immutable` para CSS/JS versionados, 30 dias para imagens). Tira da instância os 10-20 arquivos por primeira visita e a banda das fotos. Opcional, para campanhas: regra de cache do HTML anônimo (sem cookie de sessão) por 30-60 s, com `Bypass Cache on Cookie` para `sessionid` -- aí o Render só vê uma fração dos cliques de uma rajada. `docs/CLOUDFLARE_INTERNO.md` já descreve o DNS.
4. **Tamanho das imagens.** Cada card do catálogo pede a foto do Cloudinary já reduzida (`arena.reduzir_imagem`, filtro `foto:720`); confira no painel do Cloudinary que as transformações estão com `f_auto,q_auto` e que nenhuma foto original acima de 300 KB está sendo entregue inteira. É banda e tempo de tela do visitante, não CPU do servidor -- mas é o que "página rápida" significa para quem está no celular.
5. **Painel**: `painel /` (19 consultas) e `/orcamentos/` (16) continuam em 0,7-0,8 s com o banco pela rede (§7, item 4); o pulso do sino (§7, item 5) continua sendo a maior carga contínua no Supabase.
6. **Medir em produção** (§7, item 7): a contagem de `503 busy` por hora no log do Render e o `Server-Timing` por rota dizem se a conta acima bateu.

### Limites desta medição (além dos da §9)

* A latência de 40 ms é uniforme e artificial; o Supabase varia (20-60 ms) e tem o pooler no meio. O que ela mede bem é a **forma** do ganho (espera do banco saindo das vagas do escudo), não o número exato.
* 8 brinquedos e 5 categorias no banco: o cache guarda poucas combinações. Em produção, com dezenas de produtos e as combinações de filtro que as pessoas usam de fato, o `LocMemCache` guarda até 300 chaves e descarta um terço quando enche; se isso aparecer no log como reconstruções frequentes, suba `OPTIONS["MAX_ENTRIES"]` em `CACHES` (cada tela do catálogo pesa 20-100 KB serializada) ou vá para o Redis.
* A árvore do projeto continuou sendo editada por outras pessoas durante a medição (templates e CSS do catálogo). Os estágios "antes" e "depois" rodaram com 25 min de diferença, na mesma máquina ociosa; a diferença entre eles é a das duas mudanças acima, mas a confirmação limpa continua sendo repetir `rodar.sh` com a árvore parada.
