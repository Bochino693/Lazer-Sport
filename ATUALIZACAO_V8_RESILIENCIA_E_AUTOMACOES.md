# Atualização V8 — resiliência, carregamento e automações

Este ZIP é cumulativo: pode ser extraído sobre a mesma pasta em que as
atualizações anteriores foram aplicadas. Ele preserva as melhorias de
Orçamentos, O.S., Clientes e Campanhas e acrescenta os reparos desta versão.

## O que mudou

- O menu flutuante de ações agora só existe visualmente depois do clique.
  Ele é renderizado fora da tabela, não é cortado pelo scroll e fecha antes
  de abrir modais, navegar ou executar uma ação.
- A navegação mantém a tela atual quando a internet oscila, tenta novamente
  apenas requisições GET e nunca repete POST, e-mail ou gravação.
- Prefetch foi limitado e é desligado em economia de dados, 2G e aba oculta.
- Links internos antigos voltam com segurança ao painel, sem página 404.
- Falhas temporárias do servidor recebem uma tela leve de recuperação e um
  código de referência, sem depender do banco para renderizar.
- Consultas PostgreSQL agora encerram antes do timeout do Gunicorn, liberando
  as outras threads para atender o painel.
- Vendas, Pedidos e Manutenções carregam 30 registros por página.
- Promoções, Combos e Cupons carregam 24 cards por página.
- Imagens abaixo da dobra usam carregamento e decodificação tardios.
- O aplicativo instalado guarda localmente apenas CSS, JavaScript, fontes e
  ícones; páginas, APIs e dados operacionais continuam sempre na rede.
- O observador expira automaticamente somente propostas já enviadas que
  passaram da validade. Rascunho e negociação permanecem manuais.
- Corrigido também `Brinquedos.object` para `Brinquedos.objects`, que poderia
  causar erro 500 na tela Sobre.

## Aplicar localmente

1. Faça uma cópia da pasta atual.
2. Extraia o ZIP na raiz do projeto e confirme a substituição dos arquivos.
3. Com a virtualenv ativa, execute:

```powershell
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check
```

4. Envie as alterações ao GitHub e reinicie no Render os serviços `web` e
   `worker`. O `Procfile` já contém os dois processos.

## Variável opcional

`DB_STATEMENT_TIMEOUT_MS=12000` controla o limite de cada consulta no
PostgreSQL. O padrão de 12 segundos já é aplicado se a variável não existir.

## Validação realizada

- `python manage.py check`: sem problemas.
- `makemigrations --check --dry-run`: nenhuma migração ausente.
- 123 testes direcionados de telas, orçamento, campanhas, validações,
  automações e resiliência.
- Sintaxe dos arquivos JavaScript verificada pelo Node.js.

Uma aplicação não consegue impedir uma indisponibilidade da hospedagem ou da
operadora, mas agora uma oscilação previsível não apaga a tela, não duplica
envios e não transforma uma falha transitória em uma página opaca.
