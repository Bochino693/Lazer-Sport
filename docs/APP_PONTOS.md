# Pontos, metas e loja de cupons — o que o aplicativo precisa fazer

O servidor já tem tudo pronto. Este documento é o contrato para quem
programa o aplicativo Android.

## A ideia em uma frase

O cliente curte produtos **no aplicativo**, isso vira ponto, e ponto vira
cupom de desconto usado no carrinho do site.

É de propósito que a curtida só exista no app: o site mostra o número de
curtidas (prova social) mas não deixa curtir. Sem essa diferença, não há
motivo para instalar.

## Como o cliente ganha

| O quê | Quanto | Observação |
|---|---|---|
| Cada curtida | **5 pontos** | Desfazer a curtida devolve o ponto |
| 5 produtos na lista de desejos | **30 pontos** | Meta, paga uma vez |
| 10 produtos na lista | **70 pontos** | |
| 25 produtos na lista | **200 pontos** | |
| 10 curtidas | **40 pontos** | |
| 30 curtidas | **150 pontos** | |

Meta cumprida **não se perde**: tirar itens da lista depois não apaga o
que já foi conquistado. Curtida desfeita, sim, devolve o ponto — senão
curtir e descurtir em sequência viraria uma fábrica de pontos.

Os valores estão todos em `core/pontos.py`, no topo do arquivo.

## Sem conta também vale

Curtir e guardar funcionam antes do cadastro: o registro fica no
aparelho. O app gera uma chave de 32 hexadecimais na instalação e a envia
no cabeçalho `X-Dispositivo` em toda chamada.

Quando a pessoa entra na conta, **o servidor migra sozinho** o que estava
no aparelho e credita os pontos retroativos. O app não precisa reenviar
nada.

## Endpoints

Todos abaixo de `/api/v1/`. Autenticação por token:
`Authorization: Token <token>`.

### Curtir e guardar
```
POST /api/v1/favoritos/alternar/
Cabeçalho: X-Dispositivo: <32 hex>
Corpo: {"tipo": "curtida" | "desejo", "produto": "brinquedo" | "peca", "id": 12}

→ {"ok": true, "marcado": true, "curtidas": 13, "total_desejos": 4,
   "dispositivo": "<32 hex>", "logado": true}
```
Chamar de novo desfaz. `dispositivo` volta sempre: na primeira vez, é a
chave que o app deve guardar.

```
GET /api/v1/favoritos/
→ {"curtidas": {...}, "lista_desejos": {...}, "total_desejos": 4}
```

### Pontos e metas
```
GET /api/v1/pontos/          (exige conta)
→ {
    "saldo": 85,
    "total_ganho": 135,
    "curtidas": 7,
    "desejos": 5,
    "pontos_por_curtida": 5,
    "metas": [
      {"chave": "desejo:5", "titulo": "Guarde 5 produtos na lista de desejos",
       "alvo": 5, "alcancado": 5, "falta": 0, "premio": 30,
       "concluida": true, "percentual": 100},
      ...
    ],
    "extrato": [{"quando": "...", "pontos": 5, "descricao": "Curtida no aplicativo"}]
  }
```
`percentual` já vem calculado — a barra de progresso não precisa fazer
conta.

### Loja de cupons
```
GET /api/v1/cupons/loja/     (aberta, para mostrar o prêmio antes do cadastro)
→ {"saldo": 85, "recompensas": [
     {"id": 3, "nome": "10% de desconto", "custo_pontos": 100,
      "desconto": "10%", "validade_dias": 30, "disponivel": true,
      "pode_resgatar": false, "faltam": 15}
   ]}

POST /api/v1/cupons/resgatar/    (exige conta)
Corpo: {"recompensa": 3}
→ {"ok": true,
   "cupom": {"codigo": "LSK7M2QX", "desconto": "10%",
             "expira_em": "...", "recompensa": "10% de desconto"},
   "saldo": 85,          // saldo já descontado
   "mensagem": "Cupom LSK7M2QX liberado. Use no carrinho do site..."}

Erro (400): {"ok": false, "erro": "Faltam 15 pontos para resgatar ..."}

GET /api/v1/cupons/meus/     (exige conta)
→ {"cupons": [{"codigo": "LSK7M2QX", "recompensa": "...", "desconto": "10%",
               "resgatado_em": "...", "expira_em": "...", "pontos_gastos": 100}]}
```

O cupom resgatado é um cupom **de verdade**: exclusivo daquele cliente,
com validade, e aceito no carrinho do site como qualquer outro. O app não
precisa fazer nada além de mostrar o código.

## O que cadastrar antes de lançar

No `/system/` → **Recompensas da loja de pontos**: nome, custo em pontos,
desconto e validade. Sem nenhuma recompensa cadastrada, a loja abre
vazia.

Sugestão de partida, considerando que uma curtida vale 5 pontos:

| Recompensa | Custo | Desconto |
|---|---|---|
| Primeiro desconto | 50 | 5% |
| Desconto do cliente fiel | 100 | 10% |
| Desconto especial | 250 | 15% |

## Telas que o app precisa ter

1. **Coração no card** do catálogo, com o número, e o toque curtindo.
2. **Minha lista** — o que foi guardado.
3. **Meus pontos** — saldo, barra de cada meta e extrato.
4. **Loja de cupons** — vitrine, botão resgatar e "meus cupons".
