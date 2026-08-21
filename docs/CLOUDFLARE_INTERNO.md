# interno.lazersport.com no Cloudflare

Guia para colocar o painel interno no ar em `interno.lazersport.com`,
apontando para o mesmo deploy do site (Render — `lazerandsport.onrender.com`).

O Django já está preparado: `core.middleware.SubdomainURLMiddleware` troca o
`urlconf` para `sistema_interno.urls` sempre que o host começa com `interno.`,
e `interno.lazersport.com` já está em `ALLOWED_HOSTS` e em
`CSRF_TRUSTED_ORIGINS`. O que falta é DNS, TLS, cache e controle de acesso.

---

## 1. Antes do Cloudflare: registre o domínio na hospedagem

O Cloudflare só encaminha; quem responde é o Render. Se o subdomínio não
estiver cadastrado lá, o Cloudflare entrega um erro 404 ou 525 e parece
problema de DNS.

No painel do Render, no serviço do site:
**Settings → Custom Domains → Add Custom Domain** → `interno.lazersport.com`.

O Render mostra o alvo do CNAME (algo como `lazerandsport.onrender.com`).
É esse valor que entra no passo 2.

> Na Vercel o caminho equivalente é **Project → Settings → Domains**.

---

## 2. DNS

Em **DNS → Records**, no domínio `lazersport.com`:

| Tipo  | Nome      | Conteúdo                     | Proxy            | TTL  |
|-------|-----------|------------------------------|------------------|------|
| CNAME | `interno` | `lazerandsport.onrender.com` | Proxied (laranja)| Auto |

Pontos que costumam dar dor de cabeça:

- **Nome é `interno`, não `interno.lazersport.com`.** O Cloudflare completa o
  domínio sozinho; digitando o nome inteiro você cria
  `interno.lazersport.com.lazersport.com`.
- **Deixe o proxy ligado (nuvem laranja).** É ele que dá o WAF, o cache
  control e — principalmente — o Cloudflare Access do passo 5. Com a nuvem
  cinza, o tráfego vai direto pro Render e nada disso vale.
- Se você usa `lazersport.com.br` além do `.com`, repita o registro na zona
  do `.com.br`. São duas zonas separadas no Cloudflare.

Propagação: 1 a 5 minutos com o proxy ligado.

---

## 3. SSL/TLS

Em **SSL/TLS → Overview**, modo de criptografia: **Full (strict)**.

- **Flexible quebra o login.** O Cloudflare falaria HTTP com o Render, o Django
  veria `X-Forwarded-Proto: http`, e o `SESSION_COOKIE_SECURE = True` faria o
  navegador descartar o cookie de sessão: a tela de login aceita a senha e
  volta pra tela de login, sem mensagem de erro.
- O Render já serve certificado válido, então **Full (strict)** funciona sem
  configuração extra.

Ainda em SSL/TLS:

- **Edge Certificates → Always Use HTTPS: ligado.**
- **Automatic HTTPS Rewrites: ligado.**
- **Minimum TLS Version: 1.2.**
- Confira se o **Universal SSL** cobre `interno.lazersport.com`. O certificado
  gratuito cobre `lazersport.com` e `*.lazersport.com` — um nível só. Isso
  basta aqui.

O `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` já está no
`settings.py` e é o que faz o Django reconhecer a conexão como HTTPS atrás do
proxy.

---

## 4. Cache: o painel interno não pode ser cacheado

Sessão, CSRF e saldo de estoque são por usuário e mudam a cada clique. Uma
página do painel guardada no cache do Cloudflare vira dado errado na tela de
outra pessoa — ou o token CSRF de um usuário entregue a outro.

Em **Rules → Cache Rules → Create rule**:

- Nome: `Painel interno sem cache`
- Quando: `Hostname` `equals` `interno.lazersport.com`
- Então: **Bypass cache**

Os arquivos estáticos continuam vindo do WhiteNoise com `Cache-Control` longo;
o navegador cuida deles. Se quiser cache de borda para eles também, crie uma
segunda regra **acima** desta:

- Quando: `Hostname equals interno.lazersport.com` **AND** `URI Path starts with /static/`
- Então: **Eligible for cache**, Edge TTL 1 mês

Verifique **Speed → Optimization** e deixe **Rocket Loader desligado** para
esse hostname. Rocket Loader adia a execução do JavaScript e quebra os modais
de cadastro, que dependem da ordem de carregamento do Bootstrap.

---

## 5. Cloudflare Access: quem entra no painel

O login do Django já exige `is_staff` ou um `Gerente`. O Access põe uma
tranca **antes** disso: quem não estiver na lista nem chega na tela de login,
o que remove o painel do alcance de varredura automática e de tentativa de
senha.

Em **Zero Trust → Access → Applications → Add an application → Self-hosted**:

1. **Application name**: `Painel interno Lazer & Sport`
2. **Session Duration**: 24 horas (o suficiente para um turno)
3. **Application domain**: `interno.lazersport.com` — caminho vazio, para
   cobrir o site inteiro
4. **Policy**:
   - Nome: `Equipe`
   - Action: `Allow`
   - Include → `Emails` com os e-mails da equipe, ou `Emails ending in` com o
     domínio corporativo
5. Método de login: **One-time PIN** já resolve (o Cloudflare manda um código
   por e-mail). Google Workspace, se a equipe usar, é mais confortável.

O plano gratuito do Zero Trust cobre até 50 usuários.

> Se preferir não usar o Access agora, no mínimo crie uma **WAF Rate Limiting
> Rule**: `Hostname equals interno.lazersport.com AND URI Path equals
> /login/inner/`, 5 requisições por minuto por IP, ação Block. Isso corta
> tentativa de senha em massa.

---

## 6. Cookies: mantenha o painel separado do site

Não configure `COOKIE_DOMAIN=.lazersport.com`. Essa variável existe no
`settings.py` e faz o cookie de sessão valer para todos os subdomínios — ou
seja, a sessão do site público passaria a valer no painel interno e
vice-versa. Deixando a variável vazia, cada host tem seu próprio cookie, que
é o comportamento correto aqui.

---

## 7. Checklist de validação

Depois de aplicar tudo, confira nesta ordem:

```bash
# 1. o DNS resolve e passa pelo Cloudflare
dig +short interno.lazersport.com
# deve devolver IPs da Cloudflare (104.x / 172.67.x), nao do Render

# 2. o Cloudflare responde e o certificado e valido
curl -sSI https://interno.lazersport.com/login/inner/ | head -n 12

# 3. o cache esta desligado no painel
curl -sSI https://interno.lazersport.com/ | grep -i cf-cache-status
# esperado: cf-cache-status: BYPASS  (ou DYNAMIC)

# 4. HTTP redireciona para HTTPS
curl -sSI http://interno.lazersport.com/ | head -n 3
```

E no navegador:

1. `https://interno.lazersport.com/` pede login (ou o PIN do Access antes disso).
2. Entrar com um usuário `is_staff` abre a home com os números do estoque.
3. `https://lazersport.com/stock/` **não** abre o painel — cai no catálogo
   público (`/brinquedos/`). É o middleware fazendo o trabalho dele: fora do
   `interno.`, as rotas do painel simplesmente não existem.
4. Cadastrar um item em **Estoque → Novo item** e recarregar: o item continua lá.

---

## 8. Quando algo dá errado

| Sintoma | Causa provável |
|---|---|
| `DisallowedHost` no log do Render | O host não está em `ALLOWED_HOSTS` — confira se o acesso é por `.com` ou `.com.br` |
| Erro 1016 (Origin DNS error) | O CNAME aponta pra um alvo que não existe; confirme o valor no Render |
| Erro 525 / 526 | Modo SSL errado, ou o domínio não foi cadastrado no Render |
| Login aceita a senha e volta pro login | SSL em **Flexible**; troque para **Full (strict)** |
| `CSRF verification failed` | Origem faltando em `CSRF_TRUSTED_ORIGINS` — precisa do `https://` na frente |
| Página de outro usuário aparecendo | Cache Rule de bypass ausente ou abaixo de outra regra |
| Modal de cadastro não abre | Rocket Loader ligado nesse hostname |

---

## 9. Desenvolvimento local

Não precisa de DNS nem de mexer no arquivo `hosts`: o navegador resolve
qualquer `*.localhost` para 127.0.0.1 sozinho.

```bash
python manage.py runserver 0.0.0.0:8000
```

- Site público: <http://localhost:8000/>
- Painel interno: <http://interno.localhost:8000/>

`.localhost` já está em `ALLOWED_HOSTS` e `http://interno.localhost:8000` em
`CSRF_TRUSTED_ORIGINS`.
