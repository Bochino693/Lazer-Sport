# Segurança do site e do painel

Este arquivo é o resultado de uma varredura do projeto inteiro —
configuração, rotas, permissões, formulários, JavaScript e uploads — e
lista o que estava aberto, o que foi fechado e **o que ainda depende de
você cadastrar na hospedagem**.

Duas frases honestas antes da lista. Primeira: não existe sistema
"completamente seguro"; existe sistema em que cada porta conhecida está
fechada e em que abrir uma nova por engano fica difícil — é isso que os
testes em `core/tests_seguranca.py` sustentam. Segunda: as correções
abaixo já estão no código, mas três delas **só ficam completas com uma
variável de ambiente**, e essa parte não dá para fazer daqui.

---

## O que precisa ser feito na hospedagem

| Variável | Para quê | O que acontece sem ela |
|---|---|---|
| `IMPRESSAO_API_TOKEN` | Credencial do programa que imprime os pedidos na loja | As rotas de impressão só atendem quem está logado no painel; o programa de impressão para de conseguir ler a fila |
| `MP_WEBHOOK_SECRET` | Assinatura das notificações do Mercado Pago (painel → Suas integrações → Webhooks → Chave secreta) | O webhook continua funcionando e seguro (a aprovação sempre foi conferida consultando o Mercado Pago), mas aceita receber aviso falso e gastar uma consulta por ele |
| `SECRET_KEY` | Já era obrigatória em produção | O deploy nem sobe |

Valor bom para o token de impressão:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

E o programa de impressão passa a mandar, em cada chamada:

```
Authorization: Token <o valor cadastrado>
```

Duas variáveis existem só para emergência, e o normal é não mexer:
`CSP_SOMENTE_RELATO=1` (se alguma tela quebrar por causa da política de
conteúdo, isso a põe em modo de aviso enquanto se descobre o que faltou)
e `PROTECAO_LOGIN_ATIVA=0` (desliga o freio de tentativas de senha).

---

## O que estava aberto — e está fechado

### 1. A fila de impressão era pública (grave)

`GET /api/v1/pedidos-impressao/` respondia a **qualquer pessoa na
internet**, em JSON: nome, telefone, endereço completo com CEP, itens,
forma de pagamento e valores de todo pedido em aberto. Era, na prática,
a carteira de clientes exposta — e um problema de LGPD, não só de
segurança.

Junto dela, `POST /api/v1/pedido-impresso/<id>/` deixava qualquer um
marcar qualquer pedido como impresso — o pedido some da fila e nunca é
impresso de verdade.

Agora as duas exigem token da estação de impressão **ou** sessão de
equipe (com CSRF valendo). Quem não tem nem um nem outro recebe 403.

### 2. Havia um provador de senhas no código (grave)

Uma view recebia usuário e senha de qualquer origem e respondia se o par
valia, informando de quebra se a conta era `staff` ou superusuário. A
única tranca era comparar um campo com uma chave de exemplo escrita no
próprio repositório. Ela não tinha rota — e era isso que a tornava
perigosa: bastava alguém ligar a rota um dia sem reler o corpo. Foi
apagada.

### 3. O carrinho aceitava gravação de outro site (médio)

`POST /calcular/frete/` estava isenta de CSRF e gravava o endereço de
entrega no carrinho de quem estivesse logado. Uma página aberta noutra
aba conseguia trocar o endereço do cliente — o navegador manda o cookie
de sessão sozinho. A isenção nem era necessária: a tela do carrinho já
enviava o cabeçalho `X-CSRFToken`.

No mesmo pacote: `salvar_cpf_carrinho` e `cancelar_manutencao` não
exigiam login (visitante recebia erro 500 em vez de convite a entrar), e
o CPF passou a ser guardado só como dígitos.

### 4. Faltavam os cabeçalhos que o navegador obedece (médio)

Agora, em produção:

- **HTTPS obrigatório** (`SECURE_SSL_REDIRECT`) e **HSTS de um ano** —
  antes, um link `http://` era atendido em texto puro antes de qualquer
  redirecionamento, e numa rede aberta o cookie de sessão ia junto,
  legível;
- **Content-Security-Policy** (`core.middleware.PoliticaDeConteudoMiddleware`):
  script só do próprio domínio (mais o SDK do Mercado Pago), sem
  `object`, sem emolduramento por outro site, e formulário que não pode
  ser desviado para fora. É a rede de baixo do trapézio: se um dia um
  escape falhar em algum canto, o estrago fica limitado;
- **Permissions-Policy**: o site deixa de poder pedir câmera, microfone,
  localização e USB;
- cookies com `HttpOnly`, `Secure` e `SameSite` escritos de propósito, em
  vez de depender do padrão;
- `nosniff`, `Referrer-Policy` e `X-Frame-Options: DENY` explícitos.

`python manage.py check --deploy` passa limpo.

### 5. Hosts e origens confiáveis eram largos demais (médio)

`ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` aceitavam `.vercel.app` e
`.onrender.com` inteiros — plataformas onde qualquer pessoa publica um
subdomínio. Host aceito vira link absoluto em e-mail de proposta e de
recuperação de senha. Agora a lista é de endereços nossos, mais o
endereço que a própria hospedagem publica (`RENDER_EXTERNAL_HOSTNAME`,
`VERCEL_URL`).

### 6. Senha podia ser tentada infinitas vezes (médio)

Login do site, login do painel, `/system/` e a rota do aplicativo
aceitavam tentativas sem limite. Agora toda falha — de onde quer que
venha, porque quem avisa é o sinal do próprio Django — soma em dois
contadores (mesma conta a partir desta origem; qualquer conta a partir
desta origem), e estourado o limite a porta recusa por dez minutos, com
HTTP 429 e `Retry-After`.

Duas honestidades sobre este freio: ele conta na memória do processo, e
com vários workers o limite real é multiplicado por eles (configurar
Redis no `CACHES` resolve, sem mudar código); e o bloqueio é do par
conta+origem, de propósito — travar só pela conta permitiria a qualquer
um deixar o gerente de fora errando a senha dele.

### 7. O banco de desenvolvimento estava versionado (médio)

`db.sqlite3` viajava no repositório com contas (hashes de senha) e
perfis de clientes dentro. Saiu do controle de versão, e `.gitignore`
passou a barrar `*.sqlite3`, `.env` e a pasta `/media/`.

**Isto ainda não está completo, e depende de uma decisão sua:** o
arquivo continua no HISTÓRICO do Git. Quem clonar o repositório e olhar
commits antigos ainda o encontra. Limpar histórico reescreve todos os
commits e obriga todo mundo a reclonar — é uma operação que precisa da
sua autorização. Enquanto isso não acontece, o certo é **trocar as senhas
das contas que existiam nesse arquivo**.

### 8. Notificação de pagamento sem assinatura (baixo)

O webhook do Mercado Pago aceitava qualquer mensagem. O risco real era
menor do que parece — a aprovação de um pedido nunca dependeu da
mensagem recebida, e sim da consulta que o servidor faz ao Mercado Pago
com a nossa credencial. O que faltava era barrar o disparo em massa de
avisos falsos. Com `MP_WEBHOOK_SECRET` cadastrada, mensagem sem
assinatura válida é descartada na porta.

---

## O que foi conferido e já estava certo

Vale registrar, porque é trabalho que não precisa ser refeito:

- **Injeção de SQL**: não há concatenação de dado de usuário em consulta.
  Os poucos `cursor.execute` com f-string usam nomes de tabela fixos,
  escritos no código;
- **XSS nos modelos**: nenhum `|safe` e nenhum `autoescape off` em todo o
  projeto. O JavaScript que monta HTML (busca do painel, cartões do mapa)
  escapa o texto antes;
- **Links públicos de proposta e de O.S.**: o token tem ~190 bits de
  aleatoriedade — não se chega à proposta de um cliente adivinhando a de
  outro —, a resposta é registrada uma vez só e proposta vencida não
  aceita resposta;
- **Permissões do painel**: toda tela interna passa por
  `InternoRequiredMixin`/`AdminOnlyMixin` — subdomínio interno, conta de
  equipe e função atribuída;
- **API do aplicativo**: cada rota declara `permission_classes`, mesmo com
  o padrão do projeto sendo `AllowAny`;
- **Upload de fotos de manutenção**: limite de quantidade, de tamanho por
  arquivo e do conjunto, tipos permitidos e nome de arquivo gerado pelo
  servidor (nada de caminho vindo do cliente);
- **Servir arquivo de mídia**: o caminho é resolvido e conferido contra a
  pasta raiz — `../../etc/passwd` não sai de lá;
- **Redirecionamento após login**: passa por
  `url_has_allowed_host_and_scheme`, então `?next=` não leva para fora.

## O que fica como risco conhecido

- **O token do aplicativo não expira.** É o padrão do
  `rest_framework.authtoken`: quem obtiver o token de um celular continua
  entrando até alguém apagá-lo. Trocar por token com validade é uma
  mudança de fôlego, que mexe no aplicativo também;
- **`'unsafe-inline'` na política de conteúdo.** O site tem estilo e
  script escritos dentro do HTML em dezenas de telas; uma política que
  quebra a página é desligada no dia seguinte. Tirar isso significa mover
  esses trechos para arquivo — dá para fazer aos poucos, tela por tela;
- **Sair da conta por link (`ACCOUNT_LOGOUT_ON_GET`).** Um site
  malicioso consegue deslogar quem visita. Incomoda, não vaza nada.

---

## Acessibilidade

Feito na mesma passada, porque as duas coisas se encontram no mesmo HTML:

- **"Pular para o conteúdo"** como primeiro ponto de tabulação de toda
  página. Antes, quem navega por teclado passava por catorze itens de
  menu, busca e carrinho antes do texto — em toda página;
- **Toda imagem se descreve** (`alt` com o nome do produto) ou se declara
  enfeite (`alt=""`), em vez de o leitor de tela ler o nome do arquivo;
- **Campos com nome**: os rótulos do endereço de entrega eram texto solto
  na tela (`<label>CEP</label>`, sem ligação com o campo) — o leitor de
  tela anunciava "caixa de texto" em CEP, telefone e endereço. Idem para
  a busca do site, o campo de cupom e a confirmação da ordem de serviço;
- **Erro que se anuncia**: o aviso de CEP inválido virou `role="alert"`, e
  o resultado do cupom, `role="status"`;
- **Foco visível e sem moldura sobrando**: o anel amarelo continua em
  link, botão e campo; sumiu o retângulo preto que o navegador desenhava
  em volta da seção inteira depois de um clique no menu.

`core/tests_acessibilidade.py` cobra essas regras a cada rodada da suíte.
