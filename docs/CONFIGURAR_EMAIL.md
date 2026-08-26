# Colocar o seu e-mail no envio das propostas

O site já envia orçamento, confirmação de pedido e aviso de manutenção.
O que falta é dizer **qual conta envia** e **para onde volta a resposta**.
São duas coisas diferentes, e confundir as duas é o motivo mais comum de
a mensagem cair em spam ou ser recusada pelo provedor.

| Papel | Variável | O que é |
|---|---|---|
| Quem envia (autenticação) | `EMAIL_HOST_USER` | a conta que faz login no servidor de e-mail |
| Como o cliente vê o remetente | `DEFAULT_FROM_EMAIL` + `EMAIL_REMETENTE_NOME` | o "de" que aparece na caixa de entrada |
| Para onde vai a resposta | `EMAIL_RESPOSTA` | o **seu** e-mail, o que recebe quando o cliente responde |

Regra que vale para Gmail, Zoho, Outlook, Brevo e afins: **o "de" precisa
ser o mesmo endereço autenticado no SMTP**. Colocar o e-mail pessoal no
"de" sem ele estar autenticado faz a mensagem ser rejeitada ou marcada
como falsificada. O jeito certo de receber no seu e-mail é o
`EMAIL_RESPOSTA` — o cliente clica em "responder" e a mensagem vai para
você.

Além disso, se você estiver logado no painel interno com o seu e-mail
cadastrado em **Minha conta**, a proposta que você enviar já sai com o
seu endereço no "responder para", na frente do `EMAIL_RESPOSTA`. Ou seja:
cada vendedor recebe a resposta do próprio cliente.

## Configuração na hospedagem (Render ou Vercel)

Em **Environment / Environment Variables**, crie:

```
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
EMAIL_HOST_USER=lazersport@gmail.com
EMAIL_HOST_PASSWORD=senha-de-aplicativo-de-16-letras
DEFAULT_FROM_EMAIL=lazersport@gmail.com
EMAIL_REMETENTE_NOME=Lazer & Sport Brinquedos
EMAIL_RESPOSTA=seu-email@dominio.com.br
```

O cliente vai ver na caixa de entrada:

```
De:      Lazer & Sport Brinquedos <lazersport@gmail.com>
Responder para: seu-email@dominio.com.br
```

### Gmail

`EMAIL_HOST_PASSWORD` **não** é a senha da conta: é uma *senha de
aplicativo* de 16 letras, gerada em
<https://myaccount.google.com/apppasswords>. Ela só aparece depois de
ativar a verificação em duas etapas. Se der `535 Username and Password
not accepted`, é porque foi usada a senha normal.

### E-mail no domínio próprio (@lazersport.com.br)

Se você tem e-mail no domínio (Zoho, Google Workspace, Locaweb, Hostinger):

```
EMAIL_HOST=smtp.zoho.com          # ou o servidor do seu provedor
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=contato@lazersport.com.br
EMAIL_HOST_PASSWORD=a-senha-desse-e-mail
DEFAULT_FROM_EMAIL=contato@lazersport.com.br
EMAIL_REMETENTE_NOME=Lazer & Sport Brinquedos
EMAIL_RESPOSTA=contato@lazersport.com.br
```

Esta é a opção que chega melhor: e-mail no próprio domínio, com SPF e
DKIM do provedor, quase não cai em spam. O Gmail comum funciona, mas
entrega pior porque o domínio de envio não é o do site.

## O contato que aparece na proposta

Este é outro assunto — não é por onde o e-mail **sai**, é o que o cliente
**lê** no documento e para onde ele liga.

```
EMPRESA_TELEFONE=(11) 96056-3135
EMPRESA_WHATSAPP=5511960563135
EMPRESA_EMAIL=contato@lazersport.com
EMPRESA_INSTAGRAM=@lazersportbrinquedos
```

Sem essas variáveis o sistema já usa esses mesmos valores — são o telefone
e o e-mail que estão no rodapé do site e no botão de WhatsApp de todas as
páginas. Defina só o que quiser mudar.

Três coisas que decorrem daí:

* a proposta mostra esse telefone, e ele abre a conversa no WhatsApp da
  empresa com a dúvida já escrita;
* `EMAIL_RESPOSTA`, se não for definido, passa a ser o `EMPRESA_EMAIL` —
  antes ficava vazio e a resposta do cliente caía na conta técnica do SMTP,
  onde ninguém olhava;
* quem precisar de um contato diferente **só na proposta** pode usar
  `ORCAMENTO_TELEFONE`, `ORCAMENTO_EMAIL`, `ORCAMENTO_WHATSAPP` e
  `ORCAMENTO_INSTAGRAM`, que ganham do contato geral.

> Se a proposta ainda mostrar um telefone antigo depois de configurar,
> ele está no cadastro **Endereço da empresa** do painel — a configuração
> ganha dele, mas o cadastro é o que preenche quando ela está vazia.

## Conferir se funcionou

No servidor (Render Shell) ou na sua máquina:

```
python manage.py testar_email seu-email@dominio.com.br
```

O comando mostra a configuração que está valendo (sem expor a senha),
manda um e-mail de teste e diz exatamente o que falhou quando falha.
Responda a mensagem de teste: se a resposta chegar no endereço certo, o
`EMAIL_RESPOSTA` está correto.

## Erros comuns

| Mensagem | O que é |
|---|---|
| `535 Username and Password not accepted` | senha normal no lugar da senha de aplicativo |
| `550 not allowed to send as` | `DEFAULT_FROM_EMAIL` diferente do `EMAIL_HOST_USER` |
| Trava e devolve timeout | porta 587 bloqueada; tente `EMAIL_PORT=465` com `EMAIL_USE_SSL=true` e `EMAIL_USE_TLS=false` |
| "O envio por e-mail ainda não está configurado" no painel | faltam `EMAIL_HOST_USER` e/ou `EMAIL_HOST_PASSWORD` na hospedagem |

## E o WhatsApp?

Não precisa de nada configurado. O botão abre a conversa com o texto da
proposta e o link já preenchidos — quem envia é você, pelo seu próprio
WhatsApp.
