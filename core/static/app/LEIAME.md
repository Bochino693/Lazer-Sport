# APK do aplicativo Android

Coloque aqui o arquivo com o nome exato **`lazer-sport.apk`**.

Assim que ele existir neste diretório, o botão "Baixar o APK" passa a
aparecer sozinho no rodapé do site — só para quem entra pelo Android. Não
é preciso mexer em nenhuma configuração nem em variável de ambiente.

Para gerar o arquivo, no projeto do aplicativo:

    ./gradlew assembleRelease

O APK sai em `app/build/outputs/apk/release/`.

## Trocar de versão

1. Substitua o `lazer-sport.apk` por aqui.
2. Atualize `APP_ANDROID_VERSAO` (variável de ambiente) para o número novo —
   é ele que aparece embaixo do botão.
3. Faça o deploy. O rodapé leva até 5 minutos para trocar (tempo de cache).

## Quando o app entrar na Play Store

Preencha a variável de ambiente `APP_ANDROID_PLAY_URL` com o link da loja.
O botão da Play Store passa a ser o principal e o APK vira a opção
secundária, sem precisar remover nada daqui.

> Este diretório é servido como arquivo estático. Não guarde aqui nada que
> não possa ser baixado por qualquer visitante.
