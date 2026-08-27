ORÇAMENTO V4.2 — APLICAR COM SEGURANÇA
======================================

O pacote não contém .git, .idea, banco local nem ambiente virtual.
Ele pode ser copiado por cima do projeto sem apagar o histórico do Git.

ANTES DE COPIAR
---------------
Abra o PowerShell na pasta Lazer-Sport e execute:

git status
git pull --ff-only origin main

Se o Git informar que existe merge em andamento ou arquivos locais ainda
não salvos, pare e resolva isso antes de substituir os arquivos.

COMO APLICAR
------------
1. Extraia este ZIP em uma pasta temporária.
2. Copie todo o conteúdo extraído para a pasta Lazer-Sport.
3. Confirme a substituição dos arquivos existentes.
4. Não apague a pasta .git que já existe no seu projeto.

DEPOIS DE COPIAR
----------------
Execute dentro do ambiente virtual:

python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check
python manage.py test --settings=lazer.settings_test

Se tudo passar:

git add .
git commit -m "refina orçamento, CEP, prévia e aprovação do cliente"
git push origin main

O QUE MUDOU
-----------
- CEP preenche rua, bairro, cidade e UF, com segunda fonte quando necessário.
- CEP, telefone, CPF/CNPJ e dinheiro recebem máscaras no painel.
- Quantidade aceita somente número inteiro; dinheiro abre teclado numérico.
- Cliente criado dentro do orçamento volta imediatamente com todos os dados.
- Prévia interna funciona inclusive em rascunho e nunca aceita resposta.
- Link público marca como aguardando resposta e permite aprovar, pedir ajustes ou recusar.
- Corrigido o erro “Field 'id' expected a number but got ''” ao enviar.
- O modal de envio já abre com nome, WhatsApp e e-mail do cliente vinculado;
  esses dados continuam editáveis antes de enviar.
- O link só libera os botões de copiar e abrir depois que o servidor confirma
  a URL, evitando compartilhar endereço vazio ou quebrado.
- WhatsApp abre a conversa preparada mesmo quando o navegador do tablet
  bloquear pop-ups; o operador apenas confirma o envio no aplicativo.
- Aprovação/recusa atualiza automaticamente a situação no interno.
- Documento comercial responsivo com dados do cliente, itens, totais,
  pagamento, envio, observações e identidade Lazer & Sport.
- Nova migração: 0016_orcamento_formas_pagamento_envio.py.

IMPORTANTE
----------
O GitHub permitiu leitura neste atendimento, mas recusou escrita com erro
403. Por isso este pacote não foi publicado automaticamente em uma branch.
