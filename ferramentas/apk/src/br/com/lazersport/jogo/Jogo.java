/*
 * O APLICATIVO DE UM JOGO DA LAZER & SPORT (o APK que o painel gera).
 *
 * Uma tela só: o jogo em tela cheia, deitado, sem as barras do Android. O jogo
 * mora DENTRO do APK (assets/www/): o reprodutor do site, o emulador, o núcleo do
 * console e os arquivos do jogo -- abre sem internet. As páginas são servidas
 * por este app num endereço https "de mentira" (https://jogo.lazersport.app/), que
 * nunca sai do aparelho: assim o jogo tem tudo o que um site seguro tem (guardar o
 * jogo salvo, o controle Bluetooth, o som).
 *
 * Mudou este arquivo? Rode ferramentas/apk/montar_casca.sh (gera o
 * core/apk_casca/classes.dex que o painel usa).
 */
package br.com.lazersport.jogo;

import android.app.Activity;
import android.content.Intent;
import android.content.res.AssetManager;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.Method;

public class Jogo extends Activity {
    static final String ENDERECO = "https://jogo.lazersport.app/";
    private WebView tela;
    private long ultimoVoltar = 0;

    @Override
    protected void onCreate(Bundle salvo) {
        super.onCreate(salvo);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        Window janela = getWindow();
        janela.setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN, WindowManager.LayoutParams.FLAG_FULLSCREEN);
        janela.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        janela.addFlags(0x01000000); // FLAG_HARDWARE_ACCELERATED

        tela = new WebView(this);
        tela.setBackgroundColor(0xff000000);
        setContentView(tela);

        WebSettings ajustes = tela.getSettings();
        ajustes.setJavaScriptEnabled(true);
        ajustes.setDomStorageEnabled(true);
        ajustes.setDatabaseEnabled(true);
        ajustes.setAllowFileAccess(false);
        ajustes.setSupportZoom(false);
        ajustes.setUseWideViewPort(true);
        ajustes.setLoadWithOverviewMode(true);
        // o som sem esperar um toque (API 17+)
        chamar(ajustes, "setMediaPlaybackRequiresUserGesture", false);

        tela.setWebChromeClient(new WebChromeClient());
        tela.setWebViewClient(new Cliente(getAssets()));
        imersivo();
        if (salvo != null) tela.restoreState(salvo);
        else tela.loadUrl(ENDERECO + "index.html");
    }

    /* Sem as barras do Android (o modo imersivo: volta a sumir depois de um toque na borda). */
    private void imersivo() {
        // LAYOUT_STABLE | LAYOUT_HIDE_NAVIGATION | LAYOUT_FULLSCREEN | HIDE_NAVIGATION | FULLSCREEN | IMMERSIVE_STICKY
        int bandeiras = 0x00000100 | 0x00000200 | 0x00000400 | 0x00000002 | 0x00000004 | 0x00001000;
        getWindow().getDecorView().setSystemUiVisibility(bandeiras);
    }

    @Override
    public void onWindowFocusChanged(boolean comFoco) {
        super.onWindowFocusChanged(comFoco);
        if (comFoco) imersivo();
    }

    @Override
    protected void onSaveInstanceState(Bundle estado) {
        super.onSaveInstanceState(estado);
        tela.saveState(estado);
    }

    @Override
    protected void onPause() {
        super.onPause();
        tela.onPause(); // o jogo e o som param junto com o app
    }

    @Override
    protected void onResume() {
        super.onResume();
        tela.onResume();
        imersivo();
    }

    @Override
    protected void onDestroy() {
        if (tela != null) tela.destroy();
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
        long agora = System.currentTimeMillis();
        if (agora - ultimoVoltar < 2000) {
            finish();
            return;
        }
        ultimoVoltar = agora;
        Toast.makeText(this, "Toque de novo em voltar para sair do jogo", Toast.LENGTH_SHORT).show();
    }

    static void chamar(Object alvo, String metodo, boolean valor) {
        try {
            Method m = alvo.getClass().getMethod(metodo, boolean.class);
            m.invoke(alvo, valor);
        } catch (Exception e) {
            // aparelho antigo: segue sem
        }
    }

    /* Quem serve o jogo: tudo o que é de https://jogo.lazersport.app/ sai de assets/www/. */
    static class Cliente extends WebViewClient {
        private final AssetManager arquivos;

        Cliente(AssetManager arquivos) {
            this.arquivos = arquivos;
        }

        @Override
        public WebResourceResponse shouldInterceptRequest(WebView tela, String url) {
            if (url == null || !url.startsWith(ENDERECO)) return null;
            String caminho = url.substring(ENDERECO.length());
            int corte = caminho.indexOf('?');
            if (corte >= 0) caminho = caminho.substring(0, corte);
            corte = caminho.indexOf('#');
            if (corte >= 0) caminho = caminho.substring(0, corte);
            if (caminho.length() == 0 || caminho.endsWith("/")) caminho = caminho + "index.html";
            caminho = Uri.decode(caminho);
            try {
                InputStream dados = arquivos.open("www/" + caminho);
                return new WebResourceResponse(tipo(caminho), tipo(caminho).startsWith("text/") ? "utf-8" : null, dados);
            } catch (IOException e) {
                return new WebResourceResponse("text/plain", "utf-8", null);
            }
        }

        @Override
        public boolean shouldOverrideUrlLoading(WebView tela, String url) {
            if (url != null && url.startsWith(ENDERECO)) return false;
            // link para fora (o site, o WhatsApp): abre no navegador do aparelho
            try {
                tela.getContext().startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
            } catch (Exception e) {
                // nada para abrir
            }
            return true;
        }

        static String tipo(String caminho) {
            String c = caminho.toLowerCase();
            if (c.endsWith(".html") || c.endsWith(".htm")) return "text/html";
            if (c.endsWith(".js") || c.endsWith(".mjs")) return "text/javascript";
            if (c.endsWith(".css")) return "text/css";
            if (c.endsWith(".json")) return "application/json";
            if (c.endsWith(".wasm")) return "application/wasm";
            if (c.endsWith(".svg")) return "image/svg+xml";
            if (c.endsWith(".png")) return "image/png";
            if (c.endsWith(".webp")) return "image/webp";
            if (c.endsWith(".jpg") || c.endsWith(".jpeg")) return "image/jpeg";
            if (c.endsWith(".gif")) return "image/gif";
            if (c.endsWith(".woff2")) return "font/woff2";
            if (c.endsWith(".woff")) return "font/woff";
            if (c.endsWith(".mp3")) return "audio/mpeg";
            if (c.endsWith(".ogg")) return "audio/ogg";
            if (c.endsWith(".wav")) return "audio/wav";
            if (c.endsWith(".mp4")) return "video/mp4";
            return "application/octet-stream";
        }
    }
}
