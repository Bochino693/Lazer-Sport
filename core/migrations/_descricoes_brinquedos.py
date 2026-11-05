"""As descrições dos brinquedos do catálogo, reescritas em novembro de 2026.

Lidas do site no ar (as fotos de cada brinquedo e o texto que estava
cadastrado) e reescritas fiéis ao que aparece nas fotos e às medidas e
especificações que já estavam no cadastro -- nenhuma medida ou recurso
foi inventado. Usadas pela migração 0126.

Por id do site no ar: o nome confere que é o mesmo brinquedo, a
`antiga` diz que ninguém mexeu no texto desde então (se mexeu, a
migração respeita e não troca), e a `nova` é o texto novo.
"""

DESCRICOES = {1: {'nome': 'AIR GAME PREMIUM',
     'antiga': 'desafie seus reflexos no clássico jogo de air hockey, ataque e defenda para marcar pontos '
               'contra seu adversário!',
     'nova': 'O Air Game Premium é a versão profissional do air hockey: mesa grande, de 2,50 m de '
             'comprimento, com arco superior iluminado sobre o campo de jogo e LEDs coloridos em todo o '
             'corpo, em efeito de equalizador. Um equipamento que vira atração só de ficar ligado.\n'
             '\n'
             'Dois jogadores disputam cada ponto rebatendo o disco que flutua sobre o colchão de ar, '
             'atacando e defendendo o próprio gol. Partidas rápidas, emocionantes e com muita torcida em '
             'volta.\n'
             '\n'
             'Medidas aproximadas: 1,90 m de altura (com o arco), 1,20 m de largura e 2,50 m de comprimento. '
             '220V.\n'
             '\n'
             'Ideal para shoppings, parques de diversão, game centers, buffets, hotéis e espaços '
             'esportivos.'},
 2: {'nome': 'AIR GAME HOME',
     'antiga': 'AIR GAME HOME',
     'nova': 'O Air Game Home leva o clássico air hockey para dentro de casa, do salão de festas ou da área '
             'de lazer. A mesa compacta, de 1,83 m de comprimento, chama atenção pelo visual vibrante em '
             'laranja, com estrelas e o logotipo Air Game nas laterais.\n'
             '\n'
             'A partida é simples e viciante: cada jogador defende o próprio gol com o rebatedor e tenta '
             'mandar o disco, que desliza sobre o colchão de ar, para o lado do adversário. Disputa rápida, '
             'competitiva e que agrada crianças e adultos.\n'
             '\n'
             'Medidas aproximadas: 0,80 m de altura, 0,90 m de largura e 1,83 m de comprimento. 220V.\n'
             '\n'
             'Ideal para residências, condomínios, salões de festas, escolas e espaços de recreação.'},
 3: {'nome': 'BASQUETE HOME',
     'antiga': 'BASQUETE HOME',
     'nova': 'O Basquete Home traz a emoção do arremesso de basquete de arcade num formato compacto, pensado '
             'para casas, salões de festas e espaços menores. A rampa leva as bolas até o jogador, que '
             'arremessa na cesta para somar pontos antes de o tempo acabar.\n'
             '\n'
             'O gabinete azul tem arte em estilo história em quadrinhos, com balões de "BOOM!" e "POW!", '
             'personagens jogando bola e o letreiro Basketball no topo, um visual alegre que combina com '
             'qualquer ambiente. 220V.\n'
             '\n'
             'Um jogo fácil de entender, competitivo e ótimo para desafiar amigos e família. Ideal para '
             'residências, condomínios, escolas, brinquedotecas e áreas de lazer.'},
 4: {'nome': 'MUNDO ZUMBI',
     'antiga': '"Teste sua precisão: acerte o buraco e suba no ranking!" Adesivo em impressão digital, '
               'iluminação em led, 4 rodízios para facilitar a movimentação e placar digital.',
     'nova': 'No Mundo Zumbi o jogador pega as bolinhas da bandeja e arremessa nos alvos com rosto de zumbi: '
             'acertou o buraco, marcou ponto. Teste sua precisão e suba no ranking!\n'
             '\n'
             'O gabinete tem tema de cemitério assombrado, alvos com iluminação verde, contorno neon e o '
             'letreiro Mundo Zumbi no topo, com a mão do zumbi saindo da terra. Adesivo em impressão '
             'digital, iluminação em LED, placar digital e 4 rodízios para facilitar a movimentação.\n'
             '\n'
             'Medidas aproximadas: 1,94 m de altura, 0,81 m de largura e 1,41 m de comprimento. 220V.\n'
             '\n'
             'Ideal para buffets, shoppings, parques, game centers e áreas de lazer.'},
 5: {'nome': 'PORSCHE SIMULADOR',
     'antiga': 'O Simulador Porsche é um brinquedo que permite dirigir como um carro esportivo, com volante, '
               'pedais e sons reais, para uma experiência divertida e imersiva. Feito em fibra de vidro, '
               'pintura automotiva, iluminação em led, tela de 40 polegadas, rodizios para facilitara '
               'movimentação a policarbonato para proteção de tela.',
     'nova': 'O Porsche Simulador coloca o jogador ao volante de um carro esportivo em tamanho real: senta, '
             'segura o volante, pisa nos pedais e corre na tela com sons de motor de verdade. Uma '
             'experiência imersiva que encanta crianças e adultos e vira foto obrigatória.\n'
             '\n'
             'Carroceria em fibra de vidro com pintura automotiva em branco, preto e verde-limão, iluminação '
             'em LED embaixo do carro, tela de 40 polegadas com proteção em policarbonato e rodízios para '
             'facilitar a movimentação.\n'
             '\n'
             'Medidas aproximadas: 1,70 m de altura, 1,23 m de largura e 2,80 m de comprimento. 220V.\n'
             '\n'
             'Ideal para shoppings, game centers, parques, eventos, concessionárias e espaços de '
             'entretenimento.'},
 6: {'nome': 'SIMULADOR MARIO KART',
     'antiga': 'O Simulador Mario é um brinquedo que permite correr e se aventurar no mundo do Mario, com '
               'volante e controles intuitivos para diversão garantida. Carrinho feito em fibra de vidro, '
               'pintura automotiva, gabinete feito em mdf, adesivo em impressão digital, tela de 40 '
               'polegadas, iluminação em led e rodizios para facilitar a movimentação.',
     'nova': 'O Simulador Mario Kart leva o jogador para as pistas do Mario a bordo de um kart de verdade: '
             'assento com volante, controles intuitivos e a corrida na tela grande do gabinete, cheio de '
             'arte do jogo. Diversão garantida para quem gosta de velocidade e de personagens famosos.\n'
             '\n'
             'Carrinho em fibra de vidro com pintura automotiva, bandeira quadriculada e escapamentos '
             'iluminados, gabinete em MDF com adesivo em impressão digital, tela de 40 polegadas, iluminação '
             'em LED e rodízios para facilitar a movimentação.\n'
             '\n'
             'Medidas aproximadas: 2,14 m de altura, 1,14 m de largura e 2,80 m de comprimento. 220V.\n'
             '\n'
             'Ideal para shoppings, game centers, parques, buffets e espaços de entretenimento.'},
 7: {'nome': 'PAC MAN',
     'antiga': 'O Pac-Man 4 Jogadores é um jogo multiplayer divertido onde até quatro pessoas podem competir '
               'e se divertir juntos no clássico labirinto comendo pontos e evitando fantasmas. Gabinete '
               'feito em mdf, adesivo em impressão digital, tela de 32 polegadas, iluminação em led, 4 '
               'jogadores com policarbonato para proteção da tela e rodizios para facilitar a movimentação.',
     'nova': 'O Pac-Man 4 Jogadores leva o clássico do labirinto para uma mesa de fliperama em que até '
             'quatro pessoas jogam ao mesmo tempo, uma de cada lado, comendo os pontos e fugindo dos '
             'fantasmas. Diversão em grupo, competitiva e nostálgica.\n'
             '\n'
             'Gabinete em MDF com adesivo em impressão digital, tela de 32 polegadas protegida por '
             'policarbonato, 4 comandos com manche, iluminação em LED e rodízios para facilitar a '
             'movimentação.\n'
             '\n'
             'Medidas aproximadas: 1,10 m de altura, 0,86 m de largura e 1,82 m de comprimento. 220V.\n'
             '\n'
             'Ideal para residências, bares, restaurantes, salões de festas, condomínios, hotéis e game '
             'centers.'},
 8: {'nome': 'BASQUETE STREET',
     'antiga': 'O Basquete Street é um jogo divertido e dinâmico, perfeito para disputar partidas rápidas de '
               'basquete com estilo urbano e muita ação. Adesivos em impressão digital, iluminação em led, '
               'cesta que se movimenta, rodizios para facilitar a movimentação e tela de 32 polegadas.',
     'nova': 'O Basquete Street é o basquete de arcade em tamanho profissional, com o estilo das quadras de '
             'rua: grafite, pôr do sol e iluminação neon contornando todo o gabinete. A rede de proteção '
             'cerca a área de arremesso e a cesta se movimenta, deixando cada partida mais desafiadora.\n'
             '\n'
             'Tela de 32 polegadas com o placar e o jogo, adesivos em impressão digital, iluminação em LED e '
             'rodízios para facilitar a movimentação do equipamento.\n'
             '\n'
             'Medidas aproximadas: 2,70 m de altura, 1,00 m de largura e 2,40 m de comprimento. 220V.\n'
             '\n'
             'Ideal para shoppings, game centers, parques, buffets, clubes e espaços esportivos que querem '
             'uma atração disputada.'},
 9: {'nome': 'SHOW DE BOLA',
     'antiga': 'O Show de Bola é um jogo divertido e interativo, ideal para partidas rápidas de futebol com '
               'amigos, cheio de emoção e cestas. Proteção de tela em policarbonato, jogo de XBOX 360, 2 '
               'jogadores e tela de 42 polegadas.',
     'nova': 'O Show de Bola é o futebol de arcade para dois jogadores: cada um no seu posto, disputando '
             'partidas rápidas, cheias de emoção e com a torcida em volta. A base de grama sintética e a '
             'arte com bolas e jogadores em ação dão ao equipamento o clima de estádio.\n'
             '\n'
             'Tela de 42 polegadas com proteção em policarbonato, jogo de futebol em console Xbox 360 e '
             'controles para 2 jogadores.\n'
             '\n'
             'Medidas aproximadas: 2,40 m de altura, 1,20 m de largura e 2,00 m de comprimento. 220V.\n'
             '\n'
             'Ideal para shoppings, game centers, buffets, bares, clubes e espaços esportivos.'},
 10: {'nome': 'HOMEM ARANHA KIDS',
      'antiga': 'O Homem-Aranha Kids é um brinquedo divertido que permite às crianças entrar no mundo do '
                'herói, balançando entre aventuras e ação segura. Tela de 22 polegadas, adesivo em impressão '
                'digital, 4 rodizios para facilitar a movimentação e iluminação em led.',
      'nova': 'O Homem-Aranha Kids é a versão infantil do fliperama do herói: mais baixo, com o painel na '
              'altura das crianças e dois botões grandes e iluminados, fáceis de usar. A arte em teia '
              'vermelha e azul e o Homem-Aranha em versão mirim deixam o equipamento irresistível para os '
              'pequenos.\n'
              '\n'
              'Tela de 22 polegadas, adesivo em impressão digital, iluminação em LED e 4 rodízios para '
              'facilitar a movimentação.\n'
              '\n'
              'Medidas aproximadas: 1,50 m de altura, 0,63 m de largura e 0,70 m de profundidade. 220V.\n'
              '\n'
              'Ideal para buffets infantis, brinquedotecas, shoppings, restaurantes, hotéis e áreas kids.'},
 11: {'nome': 'TOMB RAIDER KIDS',
      'antiga': 'O Tomb Raider Kids é um jogo divertido e seguro que leva as crianças a aventuras '
                'emocionantes, explorando tesouros e mistérios em mundos cheios de ação. Tela de 22 '
                'polegadas, adesivo em impressão digital, 4 rodizios para facilitar a movimentação e '
                'iluminação em led.',
      'nova': 'O Tomb Raider Kids leva as crianças a uma aventura de exploração por templos antigos, '
              'corredores e tesouros escondidos. O gabinete tem arte de pirâmide maia na selva, letreiro '
              'Tomb Raider iluminado e o painel na altura dos pequenos.\n'
              '\n'
              'Tela de 22 polegadas, adesivo em impressão digital, iluminação em LED e 4 rodízios para '
              'facilitar a movimentação.\n'
              '\n'
              'Medidas aproximadas: 1,50 m de altura, 0,63 m de largura e 0,70 m de profundidade. 220V.\n'
              '\n'
              'Ideal para buffets infantis, brinquedotecas, shoppings, restaurantes, hotéis e áreas kids.'},
 12: {'nome': 'CORRIDA DOS MINIONS',
      'antiga': 'O Corrida dos Minions é um jogo divertido e cheio de ação, onde as crianças correm e '
                'desviam de obstáculos ao lado dos Minions em uma aventura animada. Direcional em led e '
                'botões adicionais, tela de 43 polegadas, 4 rodizios para facilitar a movimentação',
      'nova': 'Na Corrida dos Minions a criança senta no banco do gabinete e corre ao lado dos Minions, '
              'desviando de obstáculos e pegando bananas numa aventura animada. A tela grande e a arte '
              'colorida, com os personagens por todo o equipamento, garantem a atenção de quem passa.\n'
              '\n'
              'Tela de 43 polegadas, direcional em LED com botões adicionais, contorno iluminado e 4 '
              'rodízios para facilitar a movimentação.\n'
              '\n'
              'Medidas aproximadas: 2,10 m de altura, 0,95 m de largura e 1,20 m de comprimento. 220V.\n'
              '\n'
              'Ideal para buffets infantis, shoppings, parques, restaurantes, hotéis e áreas kids.'},
 13: {'nome': 'PEGA TOUPEIRA',
      'antiga': 'O Pega Toupeira é um jogo rápido e divertido que desafia a agilidade das crianças ao '
                'acertar as toupeiras que aparecem, garantindo muita risada e ação. Iluminação em led, tela '
                'de 19 polegadas, adesivo em impreesão digital',
      'nova': 'O Pega Toupeira é rápido, divertido e garante muita risada: as toupeiras aparecem e a criança '
              'precisa acertá-las antes que se escondam de novo. Desafia agilidade e reflexo, e cada partida '
              'dura o suficiente para todo mundo querer jogar outra vez.\n'
              '\n'
              'Topo com a toupeira sorridente, cinco botões grandes no painel, tela de 19 polegadas, '
              'iluminação em LED e adesivo em impressão digital com tema de floresta.\n'
              '\n'
              'Medidas aproximadas: 1,23 m de altura, 0,72 m de largura e 0,55 m de profundidade. 220V.\n'
              '\n'
              'Compacto e na altura das crianças, é ideal para buffets infantis, brinquedotecas, shoppings, '
              'restaurantes e áreas kids.'},
 14: {'nome': 'MATRIX',
      'antiga': 'O Matrix é um jogo cheio de ação e efeitos envolventes, que proporciona uma experiência '
                'dinâmica e emocionante para quem busca muita adrenalina.',
      'nova': 'O Matrix é um jogo de reflexo e agilidade cheio de luzes e efeitos: os pontos acendem e o '
              'jogador precisa reagir rápido para acertar o máximo possível antes de o tempo acabar. '
              'Partidas curtas, intensas e que dão vontade de jogar de novo.\n'
              '\n'
              'O gabinete em formato de mesa tem arte de cidade neon com disco voador, alienígenas e o '
              'logotipo Matrix em verde, num visual que se destaca em qualquer ambiente.\n'
              '\n'
              'Medidas aproximadas: 0,90 m de altura, 0,90 m de largura e 1,20 m de comprimento. 220V.\n'
              '\n'
              'Ideal para buffets, shoppings, parques, game centers, restaurantes e áreas de lazer.'},
 15: {'nome': 'MULTI JOGOS RETRO',
      'antiga': 'O Multijogos Retrô reúne vários clássicos em um só lugar, oferecendo diversão nostálgica e '
                'partidas rápidas para todas as idades. Tela de 32 polegadas, 1 mil jogos multi player '
                'iluminação em led, adesivo em impressão digital e 4 rodizios para facilitar a movimentação.',
      'nova': 'O Multi Jogos Retrô é o fliperama clássico, do jeito que os anos 90 ensinaram a gostar: '
              'gabinete em pé, painel para dois jogadores e mil jogos na memória, de luta, plataforma e '
              'corrida. A arte em estilo história em quadrinhos, com heróis dos games, completa o clima '
              'nostálgico.\n'
              '\n'
              'Tela de 32 polegadas, mil jogos multiplayer, iluminação em LED, adesivo em impressão digital '
              'e 4 rodízios para facilitar a movimentação.\n'
              '\n'
              'Medidas aproximadas: 1,86 m de altura, 0,93 m de largura e 0,80 m de profundidade. 220V.\n'
              '\n'
              'Ideal para residências, bares, restaurantes, salões de festas, condomínios e game centers.'},
 16: {'nome': 'MULTI JOGOS',
      'antiga': 'O Multi Jogos reúne vários jogos em um só lugar, garantindo diversão rápida e variada para '
                'todas as idades. Tela de 32 polegadas, 2 mil jogos multi player, 2 puffs de decoração e '
                'iluminação em leds neon',
      'nova': 'O Multi Jogos reúne dois mil jogos num só equipamento, em formato de mesa com a tela no alto, '
              'inspirado num console portátil gigante, com as laterais azul e vermelha. O painel tem dois '
              'comandos com manche e botões para partidas lado a lado.\n'
              '\n'
              'Tela de 32 polegadas, 2 mil jogos multiplayer, iluminação em LED neon com os símbolos dos '
              'controles e 2 puffs de decoração para os jogadores.\n'
              '\n'
              'Medidas aproximadas: 1,52 m de altura, 1,25 m de largura e 0,68 m de profundidade. 220V.\n'
              '\n'
              'Diversão variada para todas as idades. Ideal para residências, salões de festas, bares, '
              'restaurantes, condomínios e game centers.'},
 17: {'nome': 'GABINETE GAMES',
      'antiga': 'O Gabinete Games é ideal para montar seu setup gamer, com design moderno, ótima ventilação '
                'e espaço para seus componentes. Tela de 32 polegadas, mil jogos e mdf adesivado.',
      'nova': 'O Gabinete Games é um fliperama completo com banco estofado para dois jogadores lado a lado. '
              'O painel tem dois comandos com manche e botões, e a tela traz um menu com mil jogos para '
              'escolher: luta, aventura, corrida e clássicos dos arcades.\n'
              '\n'
              'Tela de 32 polegadas, gabinete em MDF adesivado com arte dos games em amarelo e preto, e '
              'assento confortável para partidas longas.\n'
              '\n'
              'Medidas aproximadas: 1,90 m de altura, 1,10 m de largura e 1,25 m de profundidade. 220V.\n'
              '\n'
              'Ideal para residências, salões de festas, condomínios, bares, restaurantes, game centers e '
              'espaços de lazer.'},
 18: {'nome': 'PIMBAL',
      'antiga': 'O Pinball 32 Polegadas é um jogo clássico e envolvente, com tela ampla que garante mais '
                'emoção e diversão em cada partida. Tela de 32 polegadas mais uma tela de 19 polegadas, '
                'adesivo em impressão digital, sendo um multi jogos de 430 mesas',
      'nova': 'O Pinball 32 Polegadas é o fliperama de bola na versão digital: o campo de jogo aparece na '
              'tela inclinada e o jogador comanda os batedores pelos botões laterais. Um multi jogos com 430 '
              'mesas diferentes para escolher, do clássico ao temático.\n'
              '\n'
              'Tela de 32 polegadas no campo de jogo e mais uma tela de 19 polegadas no painel superior, '
              'adesivo em impressão digital e o letreiro Multi Pinball no topo.\n'
              '\n'
              'Medidas aproximadas: 1,73 m de altura, 0,63 m de largura e 0,91 m de comprimento. 220V.\n'
              '\n'
              'Ideal para residências, bares, restaurantes, salões de festas, condomínios e game centers.'},
 19: {'nome': 'PIMBAL',
      'antiga': 'O Pinball 40 Polegadas é um jogo clássico e envolvente, com tela maior para ainda mais '
                'emoção e diversão em cada partida. Gabinete feito em mdf de 15mm, tela de 40 polegadas mais '
                'uma tela de 24 polegadas, adesivos em impressão digital sendo um multi jogos de 430 mesas e '
                'iliminação em led.',
      'nova': 'O Pinball 40 Polegadas é a versão maior do pinball digital, com o campo de jogo numa tela '
              'ampla e ainda mais emoção em cada partida. Um multi jogos com 430 mesas diferentes, '
              'comandadas pelos botões laterais, como no fliperama de bola tradicional.\n'
              '\n'
              'Gabinete em MDF de 15 mm, tela de 40 polegadas no campo de jogo mais uma tela de 24 polegadas '
              'no painel superior, adesivos em impressão digital com tema de heróis e iluminação em LED.\n'
              '\n'
              'Medidas aproximadas: 1,75 m de altura, 0,75 m de largura e 1,20 m de comprimento. 220V.\n'
              '\n'
              'Ideal para residências, bares, restaurantes, salões de festas, condomínios e game centers.'},
 20: {'nome': 'PEBOLIM ELETRÔNICO',
      'antiga': 'O Pebolim Eletrônico é um jogo divertido e moderno que traz partidas emocionantes de '
                'futebol de mesa com placar digital e muita competição. Bonecos em aluminio fundido com '
                'pintura epóxi, fechamento superior em acrilico eletrônico.',
      'nova': 'O Pebolim Eletrônico é o futebol de mesa com cara de estádio: placar digital num arco '
              'iluminado sobre o campo, LEDs nas bordas e arte com bolas e respingos coloridos. Partidas '
              'emocionantes entre dois ou quatro jogadores, com o placar contando cada gol.\n'
              '\n'
              'Bonecos em alumínio fundido com pintura epóxi, fechamento superior em acrílico e placar '
              'eletrônico.\n'
              '\n'
              'Medidas aproximadas: 2,30 m de altura (com o arco), 1,10 m de largura e 1,40 m de '
              'comprimento. 220V.\n'
              '\n'
              'Ideal para bares, restaurantes, clubes, condomínios, salões de festas, hotéis e espaços '
              'esportivos.'},
 21: {'nome': 'HOMEM ARANHA',
      'antiga': 'O Homem-Aranha é um brinquedo cheio de ação que leva a aventura do herói para outro nível, '
                'garantindo diversão e emoção para as crianças. Tela de 32 olegadas, Adesivo em impressão '
                'digital, 4 rodizios para facilitar a movimentação e iluminação em led.',
      'nova': 'O Homem-Aranha leva a ação do herói para um gabinete de fliperama cheio de estilo, com a teia '
              'vermelha e azul em todos os lados, o personagem em várias poses e contorno iluminado em LED. '
              'No painel, manche e botão para comandar a aventura na tela.\n'
              '\n'
              'Tela de 32 polegadas, adesivo em impressão digital, iluminação em LED e 4 rodízios para '
              'facilitar a movimentação.\n'
              '\n'
              'Medidas aproximadas: 2,10 m de altura, 0,63 m de largura e 0,70 m de profundidade. 220V.\n'
              '\n'
              'Uma atração que encanta fãs de todas as idades. Ideal para buffets, shoppings, parques, '
              'restaurantes, hotéis e áreas de lazer.'},
 22: {'nome': 'SONIC DASH',
      'antiga': 'O Sonic Dash é um brinquedo cheio de velocidade e diversão, perfeito para crianças que '
                'adoram aventuras rápidas e cheias de ação.',
      'nova': 'O Sonic Dash é puro movimento: no gabinete do ouriço azul, a criança corre a toda velocidade, '
              'pula obstáculos e junta anéis dourados com o manche e o botão do painel. Uma aventura rápida, '
              'cheia de ação, para fãs de todas as idades.\n'
              '\n'
              'Gabinete alto com tela vertical, arte do Sonic e dos anéis em todos os lados, adesivo em '
              'impressão digital, contorno em LED e rodízios para facilitar a movimentação.\n'
              '\n'
              'Medidas aproximadas: 2,10 m de altura, 0,63 m de largura e 0,70 m de profundidade. 220V.\n'
              '\n'
              'Ideal para buffets, shoppings, parques, game centers, restaurantes e áreas de lazer.'},
 23: {'nome': 'SUBWAY SURFERS',
      'antiga': 'O Subway Surfers é um jogo cheio de ação e velocidade, onde as crianças correm, desviam de '
                'obstáculos e se divertem em uma aventura super animada. Tela de 32 polegadas, adesivo de '
                'impressão digital, 4 rodizios para facilitar a movimentação e iluminação em led.',
      'nova': 'O Subway Surfers leva para o fliperama a corrida mais famosa dos celulares: o jogador corre '
              'pelos trilhos, desvia dos trens, pula barreiras e junta moedas com o manche do painel. Ação, '
              'velocidade e personagens que as crianças já conhecem.\n'
              '\n'
              'Tela de 32 polegadas, arte colorida dos personagens em todos os lados, adesivo em impressão '
              'digital, contorno em LED verde e 4 rodízios para facilitar a movimentação.\n'
              '\n'
              'Medidas aproximadas: 2,10 m de altura, 0,63 m de largura e 0,70 m de profundidade. 220V.\n'
              '\n'
              'Ideal para buffets, shoppings, parques, game centers, restaurantes e áreas de lazer.'},
 24: {'nome': 'FLAPYY BIRD',
      'antiga': 'O Flappy Bird é um jogo simples e viciante que desafia a habilidade e a concentração ao '
                'passar pelos obstáculos. Tela de 32 polegadas, adesivo em impressão digital, 4 rodizios '
                'para facilitar a movimentação e iluminação em led.',
      'nova': 'O Flappy Bird leva para o gabinete de fliperama o jogo simples e viciante do passarinho que '
              'precisa passar entre os canos: um toque no tempo certo e ele voa, um erro e a partida '
              'recomeça. Desafia habilidade e concentração e faz todo mundo querer bater o próprio recorde.\n'
              '\n'
              'Tela de 32 polegadas, arte com os canos verdes e o passarinho amarelo, adesivo em impressão '
              'digital, contorno em LED verde e 4 rodízios para facilitar a movimentação.\n'
              '\n'
              'Medidas aproximadas: 2,10 m de altura, 0,63 m de largura e 0,70 m de profundidade. 220V.\n'
              '\n'
              'Ideal para buffets, shoppings, parques, game centers, restaurantes e áreas de lazer.'},
 25: {'nome': 'SPEED TURBO',
      'antiga': 'O Speed Turbo é um jogo de corrida cheio de velocidade e adrenalina, perfeito para quem '
                'busca emoção e desafios rápidos. Tela de 32 polegadas, adesivo de impressão digital, 4 '
                'rodizios para facilitar a movimentação e iluminação em led.',
      'nova': 'O Speed Turbo é corrida com muita adrenalina: carros esportivos, robôs e o semáforo da '
              'largada estampados no gabinete anunciam o desafio. Na tela, o jogador acelera, desvia e '
              'disputa cada posição até a linha de chegada.\n'
              '\n'
              'Tela de 32 polegadas, adesivo em impressão digital, contorno em LED vermelho e 4 rodízios '
              'para facilitar a movimentação.\n'
              '\n'
              'Medidas aproximadas: 2,10 m de altura, 0,63 m de largura e 0,70 m de profundidade. 220V.\n'
              '\n'
              'Ideal para buffets, shoppings, parques, game centers, restaurantes e áreas de lazer.'},
 26: {'nome': 'PANTERA COR DE ROSA KIDS',
      'antiga': 'O Pantera Cor-de-Rosa Kids é um jogo divertido e colorido que garante aventuras leves e '
                'muita diversão para as crianças. Tela de 22 polegadas, adesivo em impressão digital, 4 '
                'rodizios para facilitar a movimentação e iluminação em led.',
      'nova': 'O Pantera Cor-de-Rosa Kids é um fliperama infantil todo em rosa, com a personagem por todo o '
              'gabinete e iluminação em LED rosa nas laterais. Painel na altura das crianças e comandos '
              'fáceis para aventuras leves e divertidas.\n'
              '\n'
              'Tela de 22 polegadas, adesivo em impressão digital, iluminação em LED e 4 rodízios para '
              'facilitar a movimentação.\n'
              '\n'
              'Medidas aproximadas: 1,50 m de altura, 0,63 m de largura e 0,70 m de profundidade. 220V.\n'
              '\n'
              'Ideal para buffets infantis, brinquedotecas, shoppings, restaurantes, hotéis e áreas kids.'},
 27: {'nome': 'SONIC KIDS',
      'antiga': 'O Sonic Kids é um jogo divertido e cheio de velocidade, perfeito para as crianças se '
                'aventurarem em fases rápidas e cheias de ação. Tela de 22 polegaadas, adesivo em impressão '
                'digital, 4 rodizios para facilitar a movimentação e iluminação em led.',
      'nova': 'O Sonic Kids é a versão infantil do fliperama do Sonic, com o painel na altura das crianças e '
              'comandos fáceis para correr pelas fases cheias de anéis, molas e esmeraldas. A arte da Green '
              'Hill, colorida por todo o gabinete, chama a atenção de longe.\n'
              '\n'
              'Tela de 22 polegadas, adesivo em impressão digital, iluminação em LED e 4 rodízios para '
              'facilitar a movimentação.\n'
              '\n'
              'Medidas aproximadas: 1,50 m de altura, 0,63 m de largura e 0,70 m de profundidade. 220V.\n'
              '\n'
              'Ideal para buffets infantis, brinquedotecas, shoppings, restaurantes, hotéis e áreas kids.'},
 28: {'nome': 'MINIONS KIDS',
      'antiga': 'O Minions Kids é um jogo divertido e colorido, perfeito para as crianças viverem aventuras '
                'animadas ao lado dos Minions. Tela de 22 polegadas, adesivo em impressão digital, 4 '
                'rodizios para facilitar a movimentação e iluminação em led.',
      'nova': 'O Minions Kids é o fliperama infantil da corrida dos Minions: com o manche e o botão, a '
              'criança corre pela cidade, desvia de obstáculos e pega bananas ao lado dos personagens. A '
              'arte azul e amarela e a iluminação lateral deixam o gabinete alegre e chamativo.\n'
              '\n'
              'Tela de 22 polegadas, adesivo em impressão digital, iluminação em LED e 4 rodízios para '
              'facilitar a movimentação.\n'
              '\n'
              'Medidas aproximadas: 1,50 m de altura, 0,63 m de largura e 0,70 m de profundidade. 220V.\n'
              '\n'
              'Ideal para buffets infantis, brinquedotecas, shoppings, restaurantes, hotéis e áreas kids.'},
 29: {'nome': 'LABAMBA',
      'antiga': 'Labamba é um divertido brinquedo, usando a mecânica para entreter qualquer pessoa. Tração '
                'por correia, iluminação em led com 6 cores, painel de fundo com a logo marca do seu '
                'estabelecimento, 220V, capacidade para 7 lugares.',
      'nova': 'O Labamba é um brinquedo mecânico giratório que anima qualquer evento: a plataforma circular '
              'gira e balança com os jogadores sentados ao redor, entre risadas e muita adrenalina. O painel '
              'de fundo em arco-íris, com o letreiro Labamba, e a cerca de proteção completam o visual.\n'
              '\n'
              'Tração por correia, iluminação em LED com 6 cores, capacidade para 7 lugares e painel de '
              'fundo que pode levar a marca do seu estabelecimento.\n'
              '\n'
              'Medidas aproximadas: 2,30 m de altura, 2,50 m de largura e 2,50 m de profundidade. 220V.\n'
              '\n'
              'Ideal para parques de diversão, shoppings, eventos, festas, clubes e espaços de '
              'entretenimento.'},
 30: {'nome': 'CARROSSEL SORVETINHO',
      'antiga': 'O Carrossel Sorvetinho é um brinquedo encantador e colorido que garante diversão suave e '
                'segura para as crianças. Pintura automotiva, assento para 3 crianças, motor 110\\220V de 2 '
                'a 4 anos de idade.',
      'nova': 'O Carrossel Sorvetinho é um brinquedo encantador para os pequenos: os assentos são casquinhas '
              'de sorvete com cobertura e cereja, a coluna central é um doce em espiral colorido e a base '
              'imita um bolo com cobertura escorrendo. Gira devagar, com diversão suave e segura.\n'
              '\n'
              'Pintura automotiva, assento para 3 crianças de 2 a 4 anos e motor 110/220V.\n'
              '\n'
              'Medidas aproximadas: 1,95 m de altura e 2,10 m de diâmetro.\n'
              '\n'
              'Ideal para shoppings, buffets infantis, brinquedotecas, restaurantes, hotéis e espaços kids '
              'que querem uma atração delicada para a primeira infância.'},
 31: {'nome': 'MINI RODA SORVETE',
      'antiga': 'O Mini Roda Sorvete é um brinquedo compacto e colorido que garante diversão leve e '
                'encantadora para as crianças. 3 Lugares e iluminação em led.',
      'nova': 'A Mini Roda Sorvete é uma roda-gigante em miniatura com tema de doces: as cabines têm formato '
              'de cupcake e sorvete, a roda é decorada com luzes e o letreiro Sweet Candy, e a base tem '
              'cercado de proteção com biscoitos e confeitos. Um passeio suave e encantador para as '
              'crianças.\n'
              '\n'
              '3 lugares e iluminação em LED.\n'
              '\n'
              'Medidas aproximadas: 2,70 m de altura, 2,60 m de largura e 2,10 m de profundidade. 220V.\n'
              '\n'
              'Ideal para shoppings, buffets infantis, parques, hotéis, restaurantes e espaços kids.'},
 32: {'nome': 'NERVO TESTE',
      'antiga': 'O Nervo Teste é um jogo divertido que desafia a coordenação e a precisão, garantindo '
                'momentos de tensão e muita diversão.',
      'nova': 'O Nervo Teste é o clássico desafio da mão firme: o jogador conduz a argola por um fio de '
              'metal cheio de curvas, de uma ponta à outra, sem encostar. Encostou, o jogo avisa. Tensão, '
              'concentração e muita risada para quem está jogando e para quem está assistindo.\n'
              '\n'
              'Cabine iluminada com tema colorido, letreiro em formato de estrela no topo e adesivagem que '
              'pode ser personalizada com a marca do seu evento ou estabelecimento.\n'
              '\n'
              'Medidas aproximadas: 2,19 m de altura, 1,75 m de largura e 0,45 m de profundidade. 220V.\n'
              '\n'
              'Ideal para eventos, festas, buffets, shoppings, parques e ações promocionais.'},
 33: {'nome': 'BRINQUEDÃO MODELO 1',
      'antiga': 'Este playground indoor foi projetado para oferecer uma experiência divertida, segura e '
                'estimulante para crianças. A estrutura possui um design moderno com cores vibrantes e '
                'elementos que incentivam o movimento, a exploração e a imaginação.',
      'nova': 'O Brinquedão Modelo 1 é um playground indoor completo para as crianças explorarem, pularem e '
              'escorregarem num só lugar. A estrutura em tubos, com tema de floresta tropical e personagem '
              'simpático no painel, reúne tobogã em espiral, piscina de bolinhas, cama elástica, blocos de '
              'espuma e áreas de passagem, tudo cercado por telas de proteção.\n'
              '\n'
              'Cores vibrantes, circuito que estimula o movimento e a imaginação, e espaço para várias '
              'crianças brincarem ao mesmo tempo com segurança.\n'
              '\n'
              'Medidas aproximadas: 2,60 m de altura, 7,00 m de comprimento e 2,00 m de profundidade.\n'
              '\n'
              'Projeto ilustrativo: cores, painéis e itens podem ser ajustados conforme o espaço. Ideal para '
              'buffets infantis, shoppings, restaurantes, hotéis e áreas kids.'},
 34: {'nome': 'BOLICHE VIRTUAL',
      'antiga': 'O Dragon Bowling  é um jogo muito divertido, voltado para todos os públicos que amam a arte '
                'do boliche virtual .',
      'nova': 'O Boliche Virtual roda o Dragon Bowling, o boliche de arcade da Lazer & Sport, divertido para '
              'todas as idades. O jogador lança a bola pela pista de madeira e a jogada aparece na tela '
              'vertical, com os pinos, o dragão e o placar de cada rodada.\n'
              '\n'
              'Pista com bordas iluminadas em LED, pino gigante decorativo ao lado da tela, letreiro do '
              'Dragon Bowling no topo e adesivo com a bola em chamas. Disponível em acabamento branco, rosa '
              'ou preto.\n'
              '\n'
              'Medidas aproximadas: 2,40 m de altura, 1,35 m de largura e 2,60 m de comprimento. 220V.\n'
              '\n'
              'Experimente a prévia do Dragon Bowling no simulador do site. Ideal para shoppings, game '
              'centers, parques, buffets e espaços de entretenimento.'},
 35: {'nome': 'LAZER SHOT',
      'antiga': 'O Lazer Shot é um jogo de tiro ao alvo, voltado parao treinamento de precisão de mira dos '
                'jogadores, com pontuações, rankings e dificuldades de jogo baseada em cada cenário.',
      'nova': 'O Lazer Shot é o tiro ao alvo da Lazer & Sport: com a pistola de luz feita para a máquina, o '
              'jogador mira nos alvos de cada cenário, soma pontos e disputa o ranking. Cada cenário tem a '
              'sua dificuldade, e a câmera tira a foto do jogador para aparecer no ranking.\n'
              '\n'
              'Gabinete alto com tela vertical, letreiro iluminado no topo, contorno em LED e arte com o '
              'tema "Torne-se o melhor atirador".\n'
              '\n'
              'Medidas aproximadas: 2,30 m de altura, 0,80 m de largura e 1,25 m de profundidade. 220V.\n'
              '\n'
              'Experimente a prévia do Lazer Shot no simulador do site. Ideal para shoppings, game centers, '
              'parques, buffets e espaços de entretenimento.'},
 36: {'nome': 'MATRIX ONE PIECE',
      'antiga': 'O Matrix do One Piece foi criado com a intenção de inovar e modernizar um jogo que já era '
                'um sucesso e ficou ainda mehor.',
      'nova': 'O Matrix One Piece leva o jogo de reflexo Matrix para um painel vertical de duelo: dois '
              'jogadores, um de cada lado, acertam os botões iluminados assim que acendem, e o placar '
              'digital de cada um mostra quem está na frente. Vence quem fizer mais pontos.\n'
              '\n'
              'Arte inspirada em One Piece, com os piratas de um lado e a Marinha do outro, contorno em LED '
              'e placares Player 1 e Player 2 no alto. Uma versão renovada de um jogo que já era sucesso.\n'
              '\n'
              'Medidas aproximadas: 2,30 m de altura, 1,70 m de largura e 0,70 m de profundidade. 220V.\n'
              '\n'
              'Ideal para shoppings, game centers, parques, buffets e eventos.'},
 37: {'nome': 'SONIC RACING ALL-STARS',
      'antiga': 'O Sonic Racing All-Stars éum jogo moderno e divertido, trazendo a simulação de uma corrida '
                'real com desafios e obstaculos, trazendo 3 modos de jogo e diferentes pistas.',
      'nova': 'O Sonic Racing All-Stars é um simulador de corrida em formato de carro, com o Sonic no alto '
              'do equipamento e a tela grande à frente do piloto. A simulação traz pistas diferentes, '
              'desafios e obstáculos, com 3 modos de jogo para variar a diversão.\n'
              '\n'
              'Carroceria com pintura em azul e amarelo, iluminação em LED e assento com volante para uma '
              'experiência de corrida completa.\n'
              '\n'
              'Medidas aproximadas: 2,10 m de altura, 1,40 m de largura e 3,40 m de comprimento. 220V.\n'
              '\n'
              'Uma atração de destaque para shoppings, parques, game centers, eventos e espaços de '
              'entretenimento.'},
 38: {'nome': 'SIMULADOR DE CORRIDA TOP RACER',
      'antiga': 'O Top Racer oferece uma experiência de corrida envolvente, com design moderno e visual '
                'impactante. Sua estrutura é fabricada em madeira MDF de alta resistência, com adesivação '
                'temática de alta durabilidade, perfis de acabamento e iluminação em LED que valoriza o '
                'equipamento no ambiente.\r\n'
                '\r\n'
                'Possui banco estofado em formato esportivo, volante e comandos posicionados para '
                'proporcionar conforto e imersão durante as partidas. Para facilitar a movimentação e '
                'garantir segurança durante o uso, o equipamento conta com quatro rodízios giratórios com '
                'freio.\r\n'
                '\r\n'
                'Ideal para buffets infantis, restaurantes, hotéis, condomínios, brinquedotecas, shopping '
                'centers, parques indoor e espaços de entretenimento.',
      'nova': 'O Top Racer é um simulador de corrida compacto, com banco estofado em formato esportivo, '
              'volante e comandos posicionados para dar conforto e imersão desde a primeira volta. O visual '
              'impressiona: arte de carros esportivos com respingos de tinta neon e iluminação em LED '
              'contornando o gabinete.\n'
              '\n'
              'Estrutura em MDF de alta resistência, adesivação temática de alta durabilidade, perfis de '
              'acabamento e quatro rodízios giratórios com freio, que facilitam a movimentação e deixam o '
              'equipamento firme durante o uso.\n'
              '\n'
              'Medidas aproximadas: 1,50 m de altura, 0,58 m de largura e 1,37 m de comprimento. 220V.\n'
              '\n'
              'Ideal para buffets infantis, restaurantes, hotéis, condomínios, brinquedotecas, shopping '
              'centers, parques indoor e espaços de entretenimento.'},
 39: {'nome': 'BOB ESPONJA HAMMER KIDS',
      'antiga': 'O Brinquedo Bob Esponja é uma atração divertida e cheia de cores, perfeita para encantar '
                'crianças e valorizar qualquer espaço de entretenimento. Com visual temático inspirado no '
                'fundo do mar, painel interativo e design marcante, proporciona uma experiência envolvente e '
                'estimula a atenção, a coordenação motora e a agilidade dos jogadores.\r\n'
                '\r\n'
                'Ideal para buffets infantis, parques, hotéis, restaurantes, brinquedotecas, condomínios e '
                'áreas de lazer. Sua estrutura possui acabamento resistente, excelente apresentação visual e '
                'rodízios que facilitam o transporte e o posicionamento do equipamento.\r\n'
                '\r\n'
                'Uma opção alegre, compacta e atrativa para completar seu espaço com muita diversão!',
      'nova': 'O Bob Esponja Hammer Kids é uma atração alegre e cheia de cores, com o topo no formato do '
              'personagem e arte inspirada no fundo do mar. No painel, os botões iluminados acendem e a '
              'criança precisa acertar cada um no tempo certo: um jogo de agilidade e reflexo que diverte e '
              'prende a atenção.\n'
              '\n'
              'Contorno em LED, pequena tela com o jogo, acabamento resistente e rodízios que facilitam o '
              'transporte e o posicionamento.\n'
              '\n'
              'Medidas aproximadas: 1,47 m de altura, 0,57 m de largura e 0,60 m de profundidade. 220V.\n'
              '\n'
              'Compacto e muito chamativo, é ideal para buffets infantis, brinquedotecas, parques, hotéis, '
              'restaurantes, condomínios e áreas kids.'},
 40: {'nome': 'AIR GAME KIDS',
      'antiga': 'O Air Hockey Space Kids transforma cada partida em uma divertida aventura pelo espaço! Com '
                'visual colorido, temática espacial e personagens infantis, o brinquedo chama a atenção das '
                'crianças e deixa o ambiente ainda mais atrativo.\r\n'
                '\r\n'
                'Desenvolvido para partidas rápidas entre dois jogadores, estimula a coordenação motora, a '
                'concentração, a agilidade e os reflexos de maneira divertida. Seu formato compacto é ideal '
                'para buffets infantis, brinquedotecas, parques, hotéis, restaurantes, condomínios, escolas '
                'e áreas de lazer.\r\n'
                '\r\n'
                'Uma excelente opção para quem procura diversão, interação e um visual moderno em um único '
                'brinquedo.',
      'nova': 'O Air Game Kids transforma cada partida de air hockey numa aventura pelo espaço. A mesa tem '
              'formato recortado com contorno em LED colorido e arte com astronautas mirins, planetas e o '
              'logotipo Air Hockey Espacial Kids no centro.\n'
              '\n'
              'Feito para partidas rápidas entre dois jogadores, estimula reflexo, coordenação motora e '
              'concentração de forma divertida. O tamanho compacto (0,90 m de altura, 0,86 m de largura e '
              '1,50 m de comprimento) facilita a instalação mesmo em espaços menores. 220V.\n'
              '\n'
              'Ideal para buffets infantis, brinquedotecas, parques, hotéis, restaurantes, condomínios, '
              'escolas e áreas kids.'}}
