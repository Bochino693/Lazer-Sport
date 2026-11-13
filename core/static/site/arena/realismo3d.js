/* ======================================================================
   O 3D COM CARA DE FOTO DE CATÁLOGO (LEIA-ME V10, seção 91): o que os três
   visores (a página do produto, visor3d.js; a vitrine, vitrine3d.js; a
   Arena, arena3d.js) fazem igual com as máquinas. Sem import fixo: recebe o
   three.js de quem chama e busca o RoomEnvironment na mesma pasta dele.

   O chefe do cliente: "o 3D está sem vida, apagado e sem definição -- como
   no McDonald's: olha a foto e dá vontade de comer". Então:
   - LUZ DE AMBIENTE de estúdio (a sala do RoomEnvironment, filtrada pelo
     PMREMGenerator): o verniz dos adesivos e o cromo refletem uma sala de
     verdade, com brilho e volume, e não uma luz chapada;
   - o tom NEUTRO (o "Khronos PBR Neutral" do three.js, feito para foto de
     produto): a cor da arte sai como foi impressa, viva, sem o desbotado e
     o desvio de cor do ACES em cima das cores fortes;
   - a NITIDEZ das texturas: o filtro anisotrópico (a pista e as laterais
     vistas de lado continuam nítidas) e os mipmaps do .glb;
   - a SOMBRA DE CONTATO macia no chão, no formato da máquina;
   - no aparelho fraco, as texturas grandes (2048 px) descem para 1024 e a
     densidade de pixels cai sozinha quando os quadros ficam lentos.
   ====================================================================== */

const ambientes = new WeakMap(); // renderer -> Promise<textura do ambiente>

/** O aparelho fraco: pouca memória, poucos núcleos ou a placa que não aguenta textura grande. */
export function aparelhoFraco(renderer) {
  const memoria = navigator.deviceMemory || 8;
  const nucleos = navigator.hardwareConcurrency || 4;
  const placa = renderer && renderer.capabilities ? renderer.capabilities.maxTextureSize : 8192;
  return memoria <= 2 || nucleos <= 2 || placa < 4096;
}

/** A saída de cor e o tom: sRGB e o tom neutro (o ACES onde a versão do three.js não tem o neutro). */
export function configurarRenderer(T, renderer, exposicao = 1) {
  renderer.outputColorSpace = T.SRGBColorSpace;
  renderer.toneMapping = T.NeutralToneMapping !== undefined ? T.NeutralToneMapping : T.ACESFilmicToneMapping;
  renderer.toneMappingExposure = exposicao;
}

/**
 * A luz de ambiente (a sala de estúdio filtrada pelo PMREM), uma vez por renderer.
 * `urlThree`: o endereço do three.module.min.js (o RoomEnvironment.js fica ao lado).
 */
export function ambiente(T, renderer, urlThree) {
  if (!ambientes.has(renderer)) {
    const pasta = urlThree.slice(0, urlThree.lastIndexOf("/") + 1);
    ambientes.set(renderer, import(pasta + "RoomEnvironment.js").then(({ RoomEnvironment }) => {
      const pmrem = new T.PMREMGenerator(renderer);
      const sala = new RoomEnvironment();
      const textura = pmrem.fromScene(sala, 0.04).texture;
      sala.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); });
      pmrem.dispose();
      return textura;
    }).catch((erro) => {
      console.warn("3D: sem a luz de ambiente", erro);
      return null;
    }));
  }
  return ambientes.get(renderer);
}

const MAPAS = ["map", "emissiveMap", "roughnessMap", "metalnessMap", "normalMap", "aoMap", "clearcoatMap"];

/**
 * Prepara um objeto que chegou: o filtro anisotrópico em todas as texturas e, no
 * aparelho fraco (`limite`), as texturas maiores que `limite` px reduzidas
 * (antes de subir para a placa). `envMap`: a luz de ambiente só nos materiais
 * do objeto (a Arena tem a luz dela no resto da cena).
 */
export function prepararObjeto(T, objeto, renderer, { limite = 0, envMap = null, intensidade = 1 } = {}) {
  const aniso = Math.min(8, renderer.capabilities.getMaxAnisotropy ? renderer.capabilities.getMaxAnisotropy() : 1);
  const vistas = new Set();
  objeto.traverse((o) => {
    if (!o.isMesh) return;
    for (const m of [].concat(o.material || [])) {
      if (envMap && m.isMeshStandardMaterial) {
        m.envMap = envMap;
        m.envMapIntensity = intensidade;
        m.needsUpdate = true;
      }
      for (const chave of MAPAS) {
        const t = m[chave];
        if (!t || !t.isTexture || vistas.has(t)) continue;
        vistas.add(t);
        t.anisotropy = aniso;
        const img = t.image;
        const w = img && (img.width || img.naturalWidth);
        const h = img && (img.height || img.naturalHeight);
        if (limite && w && h && Math.max(w, h) > limite) {
          const k = limite / Math.max(w, h);
          const tela = document.createElement("canvas");
          tela.width = Math.max(1, Math.round(w * k));
          tela.height = Math.max(1, Math.round(h * k));
          const g = tela.getContext("2d");
          g.imageSmoothingQuality = "high";
          g.drawImage(img, 0, 0, tela.width, tela.height);
          if (img.close) img.close();
          t.image = tela;
          t.needsUpdate = true;
        }
      }
    }
  });
}

/**
 * A sombra de contato: o retângulo do pé da máquina (`largura` x `fundo`, em m),
 * escuro e firme rente à base e esfumado para fora. Um plano só, sem luz de
 * sombra (leve no celular). Fica um tico acima do chão.
 */
export function sombraDeContato(T, largura, fundo, forca = 0.62) {
  const N = 256;
  const tela = document.createElement("canvas");
  tela.width = tela.height = N;
  const g = tela.getContext("2d");
  // o pé ocupa o meio (60%); a margem é o esfumado
  const desenhar = (borrar, alfa, folga) => {
    g.filter = `blur(${borrar}px)`;
    g.fillStyle = `rgba(2, 6, 18, ${alfa})`;
    const m = N * (0.2 - folga);
    const raio = N * 0.06;
    g.beginPath();
    if (g.roundRect) g.roundRect(m, m, N - 2 * m, N - 2 * m, raio);
    else g.rect(m, m, N - 2 * m, N - 2 * m);
    g.fill();
  };
  desenhar(26, 0.55, 0.06); // a penumbra larga
  desenhar(9, 0.75, 0.0); // o contato, rente ao pé
  g.filter = "none";
  const textura = new T.CanvasTexture(tela);
  textura.colorSpace = T.SRGBColorSpace;
  const sombra = new T.Mesh(
    new T.PlaneGeometry(1, 1),
    new T.MeshBasicMaterial({ map: textura, transparent: true, opacity: forca, depthWrite: false, toneMapped: false }),
  );
  sombra.rotation.x = -Math.PI / 2;
  sombra.position.y = 0.003;
  sombra.renderOrder = -1;
  sombra.scale.set(largura / 0.6, fundo / 0.6, 1);
  sombra.userData.sombraDeContato = true;
  return sombra;
}

/**
 * A densidade que se ajusta: começa na do aparelho (até 2) e, se os quadros
 * passam de ~30 ms em média (a placa não dá conta), desce em passos de 0,25 até
 * 1. Chame `quadro(agora)` a cada quadro desenhado em sequência; `parou()` quando
 * o laço para (a pausa não conta como lentidão).
 */
export function densidadeAdaptavel(renderer, maxima = 2) {
  let densidade = Math.min(window.devicePixelRatio || 1, maxima);
  if (aparelhoFraco(renderer)) densidade = Math.min(densidade, 1.5);
  renderer.setPixelRatio(densidade);
  let anterior = 0;
  let soma = 0;
  let n = 0;
  return {
    get densidade() { return densidade; },
    quadro(agora) {
      if (anterior) {
        soma += agora - anterior;
        n += 1;
        if (n >= 45) {
          const media = soma / n;
          soma = 0;
          n = 0;
          if (media > 30 && densidade > 1) {
            densidade = Math.max(1, densidade - 0.25);
            renderer.setPixelRatio(densidade);
            return true; // quem chama mede de novo o tamanho
          }
        }
      }
      anterior = agora;
      return false;
    },
    parou() { anterior = 0; },
  };
}
