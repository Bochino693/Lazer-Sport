# Lições de edição — Lazer & Sport

Regras aprendidas com as correções do dono da conta. O agente `editor-de-video`
lê este arquivo antes de editar e acrescenta uma linha nova (com a data) sempre
que receber uma correção. Não apague lições; se uma mudar, reescreva a linha.

## Enquadramento
- 2026-11-13 — O brinquedo tem que aparecer INTEIRO. Foto de produto vai sempre
  com `"enquadre": "inteiro"`; nunca cortar a máquina para preencher a tela.
- 2026-11-13 — Em vídeo, preferir os trechos abertos em que a máquina aparece
  toda; close só para mostrar um detalhe citado no card (ex.: a câmera).
- 2026-11-13 — Escolher os trechos mais nítidos e estáveis da gravação, não os
  primeiros que aparecem.

## Material
- 2026-11-13 — Usar as fotos e vídeos reais enviados pelo dono. Foto do site e
  modelo 3D entram só como complemento.
- 2026-11-13 — Gravação que passou por WhatsApp chega em baixa resolução; pedir
  o arquivo original quando a nitidez fizer falta.

## Visual
- 2026-11-13 — Cores vivas e autênticas: saturação alta, degradês fortes, nada
  de card cinza ou apagado.
- 2026-11-13 — Todo card tem símbolo (ícone) e moldura moderna; variar o modelo
  de card e o ícone de uma cena para outra.
- 2026-11-13 — O logo da empresa aparece em todas as cenas e grande no final.
- 2026-11-13 — Mais edição, não menos: cortes de 2 a 3 s, flash e zoom no corte,
  movimento em toda cena.

## Texto e nomes
- 2026-11-13 — Os boliches se chamam "Boliche Premium" (jogo Dragon Bowling) e
  "Boliche Kids" (jogo Strike Kids). Os dois juntos são a "Dupla Strike".
- 2026-11-13 — Especificações só do site ou do dono; nunca inventar.
- 2026-11-13 — Legenda no padrão que mais rendeu na conta: pergunta de abertura,
  lista curta de especificações, sem preço, pedido de comentário e WhatsApp.

## Publicação
- 2026-11-13 — Só publicar com autorização explícita do dono, depois de ele ver
  o vídeo e a legenda.
- 2026-11-13 — O link do site tem que ser clicável (bio e direct), não desenhado
  no vídeo nem na arte.

## Abertura e formato
- 2026-11-13 — Os primeiros 3 segundos têm que prender: abrir com gancho forte
  (preço de/por, pergunta direta ou vitrine de ofertas em cortes rápidos), nunca
  com tela parada ou logo.
- 2026-11-13 — Para cada comercial, entregar 3 versões com ganchos diferentes
  para o dono comparar e escolher qual postar.
- 2026-11-13 — Sem voz robotizada: só trilha e legenda. Legenda clara e
  informativa, com os números reais (preço, parcelas, prazo da oferta).
- 2026-11-13 — Passo a passo de compra: usar as telas reais do site como estão
  hoje, dentro de um celular, com o toque animado em cada botão
  (`tutorial.py` + `gravar_compra.js`).

## Comercial estilo apresentação
- 2026-11-14 — Referência aprovada pelo dono: apresentador no showroom, legenda
  amarela em itálico entrando uma palavra por vez, logo redondo fixo no canto,
  fotos pequenas entrando por cima da cena e logo animado no final
  (`comercial.py`, modelo em `exemplos/institucional.json`).
- 2026-11-14 — As fotos de showroom do site (`cena-*` na galeria de cada
  brinquedo) são o melhor material para esse formato quando não há gravação.
- 2026-11-14 — Não há gravação do patrão falando. Não criar fala nem imagem
  dele por IA; se chegar uma gravação real, usá-la como cena principal e
  legendar exatamente o que ele diz.
- 2026-11-14 — Entregar o vídeo sempre como arquivo MP4 direto na conversa,
  pronto para baixar.

## Black Friday e ofertas
- 2026-11-18 — Antes de citar preço, parcela ou prazo, reler a página da
  promoção no dia: os valores do cartão mudaram de uma semana para a outra.
- 2026-11-18 — Vídeo de oferta de 1 minuto: gancho, vitrine com todas as
  ofertas (arte inteira, de/por no Pix, selo de desconto, prazo no topo), depois
  o passo a passo do cadastro e da compra (`exemplos/black_friday_1min.json`).
- 2026-11-18 — O cadastro rápido do site é o botão "Continuar com Google";
  mostrar o toque nele, sem clicar de verdade na gravação.
- 2026-11-18 — Vídeo de oferta tem que ser intuitivo e chamativo: abrir com o
  preço de/por da melhor oferta, não com texto genérico.
- 2026-11-18 — O checkout tem três formas de pagar e as três aparecem no vídeo:
  Pix, cartão em até 10x sem juros e boleto (preço do Pix, vence em 3 dias).

## Área de jogos
- 2026-11-18 — Mostrar os jogos próprios E os clássicos (o dono informou que
  tem licença de todos os jogos da biblioteca).
- 2026-11-18 — Regras a citar: 2 partidas grátis sem cadastro; conta grátis
  para jogar à vontade; cada recorde entra no ranking; no geral, cada jogo
  vale até 1.000 pontos.
- 2026-11-18 — Os jogos só rodam lentos no navegador automático: filmar quadro
  a quadro com `filmar_jogo.js` (um jogo por vez; em paralelo fica inviável).
- 2026-11-18 — Os vídeos não têm narração. Voz só com gravação real ou serviço
  de voz natural contratado pelo dono; nunca voz robotizada.
