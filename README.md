# Lazer & Sport

Duas coisas no mesmo projeto Django, servidas pelo mesmo deploy e
separadas pelo **subdomínio**:

| Onde | O quê | Código |
|---|---|---|
| `lazersport.com.br` | A loja: catálogo, carrinho, pedidos, pontos | `core/` |
| `interno.lazersport.com.br` | O aplicativo da fábrica: orçamento, produção, estoque, clientes, financeiro, manutenção — e a gestão do conteúdo do site | `sistema_interno/` |

Quem faz a troca é `core.middleware.SubdomainURLMiddleware`: host começando
com `interno.` passa a resolver por `sistema_interno/urls.py`. Não há dois
deploys, dois bancos nem dois logins.

> **Já houve um terceiro lugar.** O painel `/adm/` do site era um segundo
> painel, azul, com cadastro de cliente próprio. Ele deixou de existir: as
> telas foram para dentro do aplicativo interno (`core/templates/gestao/`,
> servidas em `/site/...`) e o cadastro de cliente virou um só. Se você
> encontrar `/adm/` em algum link antigo, ele redireciona.

## Rodar na sua máquina

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Crie um `.env` na raiz, ao lado do `manage.py`:

```
SUPABASE_DATABASE_URL=postgresql://...      # obrigatório
SECRET_KEY=qualquer-coisa-em-desenvolvimento
CLOUDINARY_CLOUD_NAME=...                   # imagens
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
```

Depois:

```bash
python manage.py migrate
python manage.py runserver
```

- A loja abre em `http://localhost:8000/`.
- O aplicativo interno abre em `http://interno.localhost:8000/` — o
  navegador resolve `*.localhost` sozinho, sem mexer no arquivo `hosts`.

## Testes

O banco de teste é sqlite em memória e **nunca** toca no Supabase:

```bash
python manage.py test --settings=lazer.settings_test
```

Vale rodar antes de qualquer entrega. Boa parte dos testes existe para
proteger comportamento que já quebrou uma vez — o CEP com fonte fora do
ar, o rodapé da janela sumindo atrás do teclado do tablet, o cadastro de
cliente perdendo o vínculo com o mapa.

## Por onde começar a ler

| Arquivo | Para quê |
|---|---|
| `docs/INTERNO_DIRETRIZ.md` | **Leia antes de mexer no aplicativo interno.** Cor, forma, componentes, contrato de janela, cadastro de cliente e o checklist de tela nova. |
| `docs/CLOUDFLARE_INTERNO.md` | Pôr o subdomínio interno no ar |
| `docs/CONFIGURAR_EMAIL.md` | Envio de proposta por e-mail |
| `docs/APP_PONTOS.md` | Contrato do programa de pontos com o aplicativo Android |

## Publicação

`Procfile` na raiz; o deploy é no Render, com Postgres no Supabase e
imagens no Cloudinary. Estáticos são servidos pelo WhiteNoise a partir de
`staticfiles/` — Bootstrap e os ícones vêm do próprio servidor, e não de
CDN, porque no galpão a rede cai e um CDN fora do ar levava junto todos os
modais do painel.

## Sobras de mudanças antigas

Na raiz ainda estão `APLICAR_REPARO_ADM.py`, `README_APLICAR.txt`,
`mandarparamain.ps1`, `substituirarquivos.ps1`, `remove_index.py` e três
`Lazer-Sport-orcamento-v4*.zip`. São aplicadores de pacote de uma época em
que a mudança chegava por arquivo copiado, e não por commit. Nada no
projeto depende deles; ficam por enquanto para consulta e podem ser
apagados quando ninguém mais precisar olhar para trás.
