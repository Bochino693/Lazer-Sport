# Atualização V7 — tabelas compactas e campanhas

Este pacote é **cumulativo**: contém as melhorias profissionais da V6 e as
novidades da V7. Extraia na raiz do projeto e permita a substituição dos
arquivos existentes.

## O que mudou

### Tabelas e ações

- O antigo **Ver mais**, que aumentava a altura do registro, foi removido.
- Cada linha com várias operações agora possui um botão compacto de três
  pontos. O menu é flutuante, permanece fora do fluxo da tabela e fecha por
  toque fora, `Esc` ou escolha de uma ação.
- Formulários, CSRF e listeners originais são preservados; as ações não são
  copiadas nem reimplementadas.
- Desktop e tablet conservam colunas compactas, com ação fixa à direita e
  rolagem horizontal controlada quando necessária.
- No celular, cada linha vira um cartão compacto e o botão de ações fica no
  canto superior, sem criar uma seção enorme de botões.
- Navegação por teclado, foco, `aria-expanded` e setas no menu foram incluídos.

### Promoções, combos e cupons

- Cada card ativo ganhou **Divulgar aos clientes**.
- Um único fluxo atende os três tipos: público → mensagem → fila.
- Segmentação por tipo de cliente: todos, residencial, comercial, buffet,
  condomínio, escola ou órgão público.
- Prévia mostra quantos e-mails, WhatsApps confirmados e cadastros sem canal
  válido serão considerados, antes de gravar qualquer coisa.
- Contatos duplicados são unidos por campanha e canal.
- Cupons pessoais/restritos são bloqueados contra divulgação ampla.
- O cliente recebe uma página pública leve por UUID. O link enviado e o HTML
  público não expõem IDs sequenciais internos.
- A central **Campanhas** registra destinatário, canal, tentativas, erros e
  andamento. E-mails com falha podem ser recolocados na fila.

### Entrega robusta

- O clique do usuário não espera o SMTP. E-mails entram em uma outbox e o
  worker processa até 20 por ciclo.
- Há quatro tentativas com intervalo crescente e recuperação automática de
  processamento interrompido.
- O WhatsApp é assistido: abre uma conversa por vez com texto e link prontos.
  Disparo automático em massa só deve ser ligado futuramente por uma API
  oficial do WhatsApp Business; o sistema não simula envio que não aconteceu.
- O observador de urgências e a fila comercial compartilham o worker, mas são
  isolados: falha comercial não interrompe alertas de pedido/estoque.

## Como aplicar

1. Faça backup do banco e do projeto atual.
2. Extraia este ZIP na raiz do repositório, substituindo os arquivos.
3. No ambiente virtual, execute:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

4. Reinicie o serviço web e o worker. O `Procfile` já contém:

```text
worker: python manage.py observar_pendencias --intervalo 60
```

5. Confirme as variáveis `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`,
   `DEFAULT_FROM_EMAIL`, `SITE_URL` e `EMAIL_RESPOSTA` na hospedagem.

## Banco de dados

- `0029_aceite_validacoes_e_observador.py` — validações, aceite e observador V6.
- `0030_campanhadivulgacao_entregacampanha_and_more.py` — campanhas e outbox V7.

## Verificação executada

- `manage.py check`: sem problemas.
- `makemigrations --check --dry-run`: nenhuma alteração pendente.
- 75 testes integrados da área comercial/validações passaram, incluindo 6
  testes específicos de campanhas: deduplicação, privacidade do link público,
  idempotência do e-mail e WhatsApp assistido.
- JavaScript dos menus e campanhas validado por análise sintática do Node.
