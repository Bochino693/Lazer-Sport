# Atualização V6 — operação profissional

Pacote cumulativo preparado para ser sobreposto na raiz do projeto.

## Instalação

```powershell
python manage.py migrate
python manage.py collectstatic --noinput
```

Reinicie o processo web. O `Procfile` inclui também o processo:

```text
worker: python manage.py observar_pendencias --intervalo 60
```

Na hospedagem, ative uma instância desse worker. Para conferir sem manter o
processo aberto:

```powershell
python manage.py observar_pendencias --uma-vez
```

O envio exige as variáveis SMTP já usadas pelo projeto (`EMAIL_HOST_USER`,
`EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` e `EMAIL_RESPOSTA`).

## O que mudou

- fechamento global de modais, limpeza de backdrop e scroll ao navegar;
- navegação suave preservada, com cache curto, sem guardar respostas `no-store`;
- CPF, CNPJ numérico e o novo CNPJ alfanumérico validados pelos dígitos;
- documento normalizado para detectar cadastro duplicado;
- número classificado como WhatsApp confirmado, telefone comum ou não confirmado;
- números não confirmados não são usados automaticamente no WhatsApp;
- novo pedido envia push e e-mail a todos os superusuários ativos;
- observador envia e-mail quando o conjunto de urgências muda, sem repetir o
  mesmo estado a cada minuto;
- aceite eletrônico do orçamento com consentimento, CPF/CNPJ, data, UUID de
  comprovante, hash da proposta e contexto pseudonimizado;
- resposta pública travada em transação, impedindo decisões concorrentes;
- notificações de tela bloqueada não expõem PK, nome do cliente ou busca por ID;
- lista de clientes soma propostas no banco sem baixar todos os itens.

## Limites seguros

A validação de CPF/CNPJ comprova formato e dígitos verificadores; não consulta a
situação cadastral na Receita Federal. O sistema aceita o CNPJ alfanumérico em
produção desde julho de 2026.

Não foi usada consulta não oficial para descobrir se um telefone pertence ao
WhatsApp. Enviar a agenda de clientes a terceiros seria um risco de privacidade,
e a API oficial da Meta gerencia números empresariais da conta — não oferece uma
consulta pública segura da existência de qualquer usuário. A confirmação fica
explícita no cadastro.

O aceite criado aqui é uma assinatura eletrônica com trilha de auditoria. Caso a
empresa precise de assinatura avançada/qualificada ICP-Brasil, será necessário
integrar um provedor de assinatura e definir o fluxo jurídico correspondente.
