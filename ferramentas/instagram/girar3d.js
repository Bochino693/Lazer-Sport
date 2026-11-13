// Renderiza um modelo 3D (.glb) do site girando, em PNGs com fundo transparente,
// para usar como cena "quadros" no reel.py.
//
// Uso:  node ferramentas/instagram/girar3d.js <modelo.glb> <pasta_de_saida> [quadros=78]
// Ex.:  node ferramentas/instagram/girar3d.js core/static/site/arena/modelos/strike-kids.glb /tmp/giro
//
// Precisa do Playwright com Chromium. Usa o three.js que ja esta em core/static/vendor/three.
const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const [modelo, saida, qtd] = process.argv.slice(2);
if (!modelo || !saida) { console.error('Uso: node girar3d.js <modelo.glb> <pasta_de_saida> [quadros]'); process.exit(1); }
const RAIZ = path.resolve(__dirname, '../../core/static');
const N = parseInt(qtd || '78', 10);
const PAGINA = `<!doctype html><meta charset="utf8"><style>html,body{margin:0;background:transparent}canvas{display:block}</style>
<script type="importmap">{"imports":{"three":"/vendor/three/three.module.min.js"}}</script>
<script type="module">
import * as THREE from 'three';
import { GLTFLoader } from '/vendor/three/GLTFLoader.js';
const W=1080,H=1300;
const r=new THREE.WebGLRenderer({antialias:true,alpha:true,preserveDrawingBuffer:true});
r.setSize(W,H); r.setPixelRatio(1); r.setClearColor(0x000000,0); r.outputColorSpace=THREE.SRGBColorSpace;
r.toneMapping=THREE.ACESFilmicToneMapping; r.toneMappingExposure=1.25;
document.body.appendChild(r.domElement);
const cena=new THREE.Scene();
cena.add(new THREE.HemisphereLight(0xffffff,0x334466,1.6));
const l1=new THREE.DirectionalLight(0xffffff,2.2); l1.position.set(3,5,4); cena.add(l1);
const l2=new THREE.DirectionalLight(0x66ccff,1.2); l2.position.set(-4,2,-3); cena.add(l2);
const l3=new THREE.DirectionalLight(0xff66aa,0.9); l3.position.set(4,1,-4); cena.add(l3);
const cam=new THREE.PerspectiveCamera(30,W/H,0.01,100);
const eixo=new THREE.Group(); cena.add(eixo);
new GLTFLoader().load('/__modelo.glb',g=>{
  const o=g.scene, b=new THREE.Box3().setFromObject(o), c=b.getCenter(new THREE.Vector3()), s=b.getSize(new THREE.Vector3());
  o.position.sub(c); eixo.add(o);
  const R=Math.max(s.x,s.y,s.z); cam.position.set(0,R*0.50,R*2.75); cam.lookAt(0,0,0);
  window.girar=a=>{eixo.rotation.y=a; r.render(cena,cam);}; window.girar(0); window.pronto=true;
},undefined,e=>{window.erro=String(e&&e.message||e)});
</script>`;
const tipos = { '.js': 'text/javascript', '.glb': 'model/gltf-binary' };
const srv = http.createServer((q, s) => {
  const u = decodeURIComponent(q.url.split('?')[0]);
  if (u === '/') { s.writeHead(200, { 'Content-Type': 'text/html' }); return s.end(PAGINA); }
  const f = u === '/__modelo.glb' ? path.resolve(modelo) : path.join(RAIZ, u);
  fs.readFile(f, (e, d) => { if (e) { s.writeHead(404); return s.end(); } s.writeHead(200, { 'Content-Type': tipos[path.extname(f)] || 'application/octet-stream' }); s.end(d); });
}).listen(0, '127.0.0.1', async () => {
  fs.mkdirSync(saida, { recursive: true });
  const nav = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const pg = await nav.newPage({ viewport: { width: 1080, height: 1300 } });
  await pg.goto(`http://127.0.0.1:${srv.address().port}/`);
  await pg.waitForFunction('window.pronto||window.erro', null, { timeout: 60000 });
  const erro = await pg.evaluate('window.erro');
  if (erro) { console.error('ERRO ao carregar o modelo:', erro); await nav.close(); srv.close(); process.exit(1); }
  for (let i = 0; i < N; i++) {  // vai de um lado ao outro pela frente, com aceleracao suave
    await pg.evaluate(a => window.girar(a), -0.95 + 1.9 * (0.5 - 0.5 * Math.cos(Math.PI * i / (N - 1))));
    await pg.screenshot({ path: path.join(saida, String(i).padStart(3, '0') + '.png'), omitBackground: true });
  }
  await nav.close(); srv.close(); console.log(`OK ${N} quadros em ${saida}`);
});
