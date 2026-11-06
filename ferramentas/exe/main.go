// O PROGRAMA DE UM JOGO DA LAZER & SPORT PARA WINDOWS (o .exe que o painel gera).
//
// O jogo mora DENTRO deste .exe: no fim do arquivo vai um .zip com o reprodutor do
// site, o emulador, o núcleo do console e os arquivos do jogo (o mesmo conteúdo do
// APK: core/jogos_apk_gerar.conteudo_do_jogo), e depois dele 16 bytes -- onde o .zip
// começa (8 bytes) e a marca "LSJOGOV1". O painel monta o .exe sem compilar nada:
// é esta casca (core/exe_casca/jogo-windows.exe) + o .zip + a marca
// (core/jogos_exe_gerar.py).
//
// Ao abrir: serve o jogo só para este computador (http://127.0.0.1, numa porta fixa
// por jogo -- o jogo salvo fica guardado entre uma vez e outra), com o isolamento
// que o PSP e o DOS pedem (COOP/COEP), e abre uma janela de app do Edge (ou do
// Chrome), sem barra de endereço, com a pasta própria do jogo. Fechou a janela,
// o programa termina. Sem Edge nem Chrome, abre no navegador padrão e termina
// quando a página para de dar sinal de vida.
//
// Mudou este arquivo? Rode ferramentas/exe/montar_casca.sh.
package main

import (
	"archive/zip"
	"bytes"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"hash/fnv"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"runtime"
	"strings"
	"sync/atomic"
	"time"
)

const marca = "LSJOGOV1"

type info struct {
	Nome string `json:"nome"`
	Slug string `json:"slug"`
}

var tipos = map[string]string{
	".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8",
	".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
	".css": "text/css; charset=utf-8", ".json": "application/json", ".wasm": "application/wasm",
	".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp", ".jpg": "image/jpeg",
	".jpeg": "image/jpeg", ".gif": "image/gif", ".ico": "image/x-icon", ".woff2": "font/woff2",
	".woff": "font/woff", ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".wav": "audio/wav", ".mp4": "video/mp4",
}

// o sinal de vida da página (só quando a janela não é nossa: navegador padrão)
const sinalDeVida = `<script>setInterval(function(){fetch("/__lsjogo/vivo",{cache:"no-store"}).catch(function(){})},5000)</script>`

func main() {
	if err := rodar(); err != nil {
		avisar("Lazer & Sport Games", "Não deu para abrir o jogo:\n\n"+err.Error())
		os.Exit(1)
	}
}

func abrirPacote() (*zip.Reader, *os.File, error) {
	exe, err := os.Executable()
	if err != nil {
		return nil, nil, err
	}
	f, err := os.Open(exe)
	if err != nil {
		return nil, nil, err
	}
	st, err := f.Stat()
	if err != nil {
		return nil, nil, err
	}
	if st.Size() < 16 {
		return nil, nil, errors.New("o programa está incompleto (baixe de novo)")
	}
	fim := make([]byte, 16)
	if _, err := f.ReadAt(fim, st.Size()-16); err != nil {
		return nil, nil, err
	}
	if string(fim[8:]) != marca {
		return nil, nil, errors.New("este programa não traz um jogo dentro (baixe de novo pelo painel)")
	}
	inicio := int64(binary.LittleEndian.Uint64(fim[:8]))
	tamanho := st.Size() - 16 - inicio
	if inicio <= 0 || tamanho <= 0 {
		return nil, nil, errors.New("o jogo dentro do programa está corrompido (baixe de novo)")
	}
	z, err := zip.NewReader(io.NewSectionReader(f, inicio, tamanho), tamanho)
	if err != nil {
		return nil, nil, fmt.Errorf("o jogo dentro do programa está corrompido: %w", err)
	}
	return z, f, nil
}

func rodar() error {
	pacote, _, err := abrirPacote()
	if err != nil {
		return err
	}
	arquivos := map[string]*zip.File{}
	for _, a := range pacote.File {
		arquivos[a.Name] = a
	}
	var jogo info
	if a := arquivos["lsjogo.json"]; a != nil {
		if r, err := a.Open(); err == nil {
			_ = json.NewDecoder(r).Decode(&jogo)
			r.Close()
		}
	}
	if jogo.Slug == "" {
		jogo.Slug = "jogo"
	}

	// a porta fixa do jogo: o mesmo endereço sempre (o jogo salvo é guardado por endereço)
	h := fnv.New32a()
	h.Write([]byte(jogo.Slug))
	porta := 41000 + int(h.Sum32()%18000)
	var ouvinte net.Listener
	for tentativa := 0; tentativa < 15; tentativa++ {
		endereco := fmt.Sprintf("127.0.0.1:%d", porta+tentativa)
		if tentativa == 0 && jaAberto(endereco, jogo.Slug) {
			// o mesmo jogo já está aberto: só mostra a janela de novo
			return abrirJanela("http://"+endereco+"/", jogo)
		}
		if ouvinte, err = net.Listen("tcp", endereco); err == nil {
			break
		}
	}
	if ouvinte == nil {
		return errors.New("nenhuma porta livre neste computador")
	}
	url := "http://" + ouvinte.Addr().String() + "/"

	var ultimoSinal atomic.Int64
	janelaPropria := atomic.Bool{}
	mux := http.NewServeMux()
	mux.HandleFunc("/__lsjogo/quem", func(w http.ResponseWriter, r *http.Request) { io.WriteString(w, jogo.Slug) })
	mux.HandleFunc("/__lsjogo/vivo", func(w http.ResponseWriter, r *http.Request) {
		ultimoSinal.Store(time.Now().Unix())
		w.WriteHeader(http.StatusNoContent)
	})
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		caminho := strings.TrimPrefix(path.Clean("/"+r.URL.Path), "/")
		if caminho == "" || strings.HasSuffix(r.URL.Path, "/") {
			caminho = strings.TrimSuffix(caminho, "/")
			if caminho != "" {
				caminho += "/"
			}
			caminho += "index.html"
		}
		a := arquivos[caminho]
		if a == nil {
			http.NotFound(w, r)
			return
		}
		// tudo o que um site seguro tem (o jogo salvo, o som, o controle) e o
		// isolamento que o núcleo de várias linhas (PSP, DOS) precisa
		cab := w.Header()
		cab.Set("Cross-Origin-Opener-Policy", "same-origin")
		cab.Set("Cross-Origin-Embedder-Policy", "require-corp")
		cab.Set("Cross-Origin-Resource-Policy", "same-origin")
		cab.Set("Cache-Control", "no-cache")
		cab.Set("X-Content-Type-Options", "nosniff")
		tipo := tipos[strings.ToLower(filepath.Ext(caminho))]
		if tipo == "" {
			tipo = "application/octet-stream"
		}
		cab.Set("Content-Type", tipo)
		if a.Method == zip.Store {
			// guardado sem compressão (a ROM, o núcleo): lido direto do .exe, com pedaços (Range)
			inicio, err := a.DataOffset()
			if err == nil {
				if leitor, ok := leitorDoPacote(); ok {
					http.ServeContent(w, r, "", a.Modified, io.NewSectionReader(leitor, inicio, int64(a.UncompressedSize64)))
					return
				}
			}
		}
		rc, err := a.Open()
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		defer rc.Close()
		dados, err := io.ReadAll(rc)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		if caminho == "index.html" && !janelaPropria.Load() {
			dados = bytes.Replace(dados, []byte("</body>"), []byte(sinalDeVida+"</body>"), 1)
		}
		http.ServeContent(w, r, "", a.Modified, bytes.NewReader(dados))
	})
	servidor := &http.Server{Handler: mux, ReadHeaderTimeout: 10 * time.Second}
	go servidor.Serve(ouvinte)

	if os.Getenv("LSJOGO_SEM_JANELA") != "" {
		// para testar: só serve (e diz onde)
		fmt.Println(url)
		select {}
	}
	if cmd := comandoDaJanela(url, jogo); cmd != nil {
		janelaPropria.Store(true)
		if err := cmd.Start(); err == nil {
			_ = cmd.Wait() // fechou a janela: acabou
			return nil
		}
		janelaPropria.Store(false)
	}
	// sem Edge/Chrome: o navegador padrão; o programa fica enquanto a página der sinal de vida
	if err := abrirNoPadrao(url); err != nil {
		return fmt.Errorf("não achei um navegador para abrir %s", url)
	}
	comeco := time.Now()
	for {
		time.Sleep(5 * time.Second)
		ultimo := ultimoSinal.Load()
		if ultimo == 0 && time.Since(comeco) > 3*time.Minute {
			return nil
		}
		if ultimo != 0 && time.Since(time.Unix(ultimo, 0)) > 40*time.Second {
			return nil
		}
	}
}

// comandoDaJanela: o Edge (ou o Chrome) em modo app, com a pasta própria do jogo; nil sem eles.
func comandoDaJanela(url string, jogo info) *exec.Cmd {
	navegador := acharNavegador()
	if navegador == "" {
		return nil
	}
	pasta := filepath.Join(pastaDeDados(), "LazerSportJogos", jogo.Slug)
	_ = os.MkdirAll(pasta, 0o755)
	return exec.Command(navegador,
		"--app="+url, "--user-data-dir="+pasta, "--no-first-run", "--no-default-browser-check",
		"--autoplay-policy=no-user-gesture-required", "--window-size=1280,760", "--disable-features=Translate",
	)
}

// abrirJanela mostra o jogo que já está rodando (outra vez o mesmo programa aberto).
func abrirJanela(url string, jogo info) error {
	if cmd := comandoDaJanela(url, jogo); cmd != nil {
		return cmd.Start()
	}
	return abrirNoPadrao(url)
}

var pacoteAberto *os.File

// o próprio .exe aberto para ler os arquivos guardados sem compressão
func leitorDoPacote() (io.ReaderAt, bool) {
	if pacoteAberto == nil {
		exe, err := os.Executable()
		if err != nil {
			return nil, false
		}
		f, err := os.Open(exe)
		if err != nil {
			return nil, false
		}
		st, _ := f.Stat()
		fim := make([]byte, 16)
		if _, err := f.ReadAt(fim, st.Size()-16); err != nil {
			return nil, false
		}
		pacoteAberto = f
		deslocamento = int64(binary.LittleEndian.Uint64(fim[:8]))
	}
	return io.NewSectionReader(pacoteAberto, deslocamento, 1<<62), true
}

var deslocamento int64

func jaAberto(endereco, slug string) bool {
	cliente := http.Client{Timeout: 700 * time.Millisecond}
	r, err := cliente.Get("http://" + endereco + "/__lsjogo/quem")
	if err != nil {
		return false
	}
	defer r.Body.Close()
	corpo, _ := io.ReadAll(r.Body)
	return string(corpo) == slug
}

func pastaDeDados() string {
	if runtime.GOOS == "windows" {
		if p := os.Getenv("LOCALAPPDATA"); p != "" {
			return p
		}
	}
	if p, err := os.UserCacheDir(); err == nil {
		return p
	}
	return os.TempDir()
}

func acharNavegador() string {
	if p := os.Getenv("LSJOGO_NAVEGADOR"); p != "" {
		return p
	}
	var candidatos []string
	if runtime.GOOS == "windows" {
		for _, base := range []string{os.Getenv("ProgramFiles(x86)"), os.Getenv("ProgramFiles"), os.Getenv("LOCALAPPDATA")} {
			if base == "" {
				continue
			}
			candidatos = append(candidatos,
				filepath.Join(base, "Microsoft", "Edge", "Application", "msedge.exe"),
				filepath.Join(base, "Google", "Chrome", "Application", "chrome.exe"),
			)
		}
	} else {
		for _, nome := range []string{"microsoft-edge", "google-chrome", "chromium", "chromium-browser"} {
			if p, err := exec.LookPath(nome); err == nil {
				candidatos = append(candidatos, p)
			}
		}
	}
	for _, c := range candidatos {
		if st, err := os.Stat(c); err == nil && !st.IsDir() {
			return c
		}
	}
	return ""
}

func abrirNoPadrao(url string) error {
	switch runtime.GOOS {
	case "windows":
		return exec.Command("rundll32", "url.dll,FileProtocolHandler", url).Start()
	case "darwin":
		return exec.Command("open", url).Start()
	default:
		return exec.Command("xdg-open", url).Start()
	}
}
