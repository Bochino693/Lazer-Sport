#!/usr/bin/env python3
"""Gera um Reel vertical (1080x1920) com cards animados a partir de videos e fotos reais.

Uso:
  python3 ferramentas/instagram/reel.py roteiro.json saida.mp4

O roteiro e um JSON assim (veja exemplos/strike_kids.json):
  {
    "marca": "LAZER & SPORT  ·  FABRICA DE BRINQUEDOS",
    "musica": "core/static/site/arena/jogos/strike-kids/sons/musica.mp3",
    "cenas": [
      {"video": "entrada.mov", "inicio": 30.0, "duracao": 3.2,
       "etiqueta": "FABRICACAO PROPRIA", "titulo": "STRIKE KIDS",
       "texto": ["O boliche infantil da Lazer & Sport"], "tamanho": 128},
      {"foto": "frente.jpg", "duracao": 3.0, "etiqueta": "MEDIDAS",
       "titulo": "CABE NO SEU ESPACO", "texto": ["linha 1", "linha 2"], "tamanho": 84},
      {"foto": "angulo.jpg", "duracao": 3.8, "final": true,
       "etiqueta": "DIRETO DA FABRICA", "titulo": ["QUER O STRIKE KIDS", "NO SEU ESPACO?"],
       "texto": ["Comente STRIKE", "e peca o seu orcamento"],
       "botao": "WhatsApp (11) 96056-3135"}
    ]
  }

Precisa de ffmpeg, Pillow e da fonte Inter instalados.
"""
import json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
W,H,FPS=1080,1920,30
if len(sys.argv)!=3: sys.exit(__doc__)
SPEC=json.load(open(sys.argv[1],encoding="utf8")); BASE=os.path.dirname(os.path.abspath(sys.argv[1]))
def caminho(p): return p if os.path.isabs(p) or os.path.exists(p) else os.path.join(BASE,p)
XB="/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"; SB="/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"; BD="/usr/share/fonts/opentype/inter/Inter-Bold.otf"
YEL=(255,209,26); GRN=(37,211,102); WHITE=(255,255,255); INK=(16,18,28)
def font(p,s): return ImageFont.truetype(p,s)
def tw(d,t,f):
    b=d.textbbox((0,0),t,font=f); return b[2]-b[0],b[3]-b[1],b
# bottom/top scrim for legibility
scrim=Image.new("L",(1,H),0)
for y in range(H):
    a=0
    if y>1050: a=int(170*min(1,(y-1050)/500))
    if y<420: a=max(a,int(110*(1-y/420)))
    scrim.putpixel((0,y),a)
scrim=scrim.resize((W,H))
BLACK=Image.new("RGB",(W,H),(0,0,0))
def chip(d):
    f=font(BD,34); t=SPEC.get("marca","LAZER & SPORT  ·  FÁBRICA DE BRINQUEDOS")
    w,h,b=tw(d,t,f); x=(W-w)//2-30; y=268
    d.rounded_rectangle([x,y,x+w+60,y+h+36],radius=40,fill=(255,255,255,235))
    d.text((x+30-b[0],y+18-b[1]),t,font=f,fill=INK+(255,))
def card_layer(kicker,title,sub,title_size=104):
    """returns (overlay RGBA, panel box) — glass panel drawn per frame"""
    ov=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(ov)
    fk=font(XB,36); ft=font(XB,title_size); fs=font(SB,50)
    pad=52; x0=60; x1=W-60
    lines=sub if isinstance(sub,list) else [sub]
    tl=title if isinstance(title,list) else [title]
    th=sum(tw(d,l,ft)[1] for l in tl)+18*(len(tl)-1)
    sh=sum(tw(d,l,fs)[1] for l in lines)+16*(len(lines)-1)
    kh=64
    total=pad+kh+30+th+30+sh+pad
    y1=1590; y0=y1-total
    y=y0+pad
    kw,_,kb=tw(d,kicker,fk)
    d.rounded_rectangle([x0+pad,y,x0+pad+kw+48,y+kh],radius=32,fill=YEL+(255,))
    d.text((x0+pad+24-kb[0],y+(kh-36)//2-kb[1]+2),kicker,font=fk,fill=INK+(255,))
    y+=kh+30
    for l in tl:
        w,h,b=tw(d,l,ft); d.text((x0+pad-b[0],y-b[1]),l,font=ft,fill=WHITE+(255,)); y+=h+18
    y+=12
    for l in lines:
        w,h,b=tw(d,l,fs); d.text((x0+pad-b[0],y-b[1]),l,font=fs,fill=(225,230,240,255)); y+=h+16
    return ov,(x0,y0,x1,y1)
def end_layer(c):
    ov=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(ov)
    ft=font(XB,c.get("tamanho",96)); fs=font(SB,50); fb=font(XB,60); fk=font(XB,36)
    y=700
    k=c.get("etiqueta","")
    if k:
        kw,_,kb=tw(d,k,fk)
        d.rounded_rectangle([(W-kw)//2-24,y,(W+kw)//2+24,y+64],radius=32,fill=YEL+(255,)); d.text(((W-kw)//2-kb[0],y+14-kb[1]+2),k,font=fk,fill=INK+(255,))
        y+=64+44
    for l in lista(c.get("titulo",[])):
        w,h,b=tw(d,l,ft); d.text(((W-w)//2-b[0],y-b[1]),l,font=ft,fill=WHITE+(255,)); y+=h+22
    y+=30
    for l in lista(c.get("texto",[])):
        w,h,b=tw(d,l,fs); d.text(((W-w)//2-b[0],y-b[1]),l,font=fs,fill=(225,230,240,255)); y+=h+16
    y+=50
    t=c.get("botao")
    if t:
        w,h,b=tw(d,t,fb)
        d.rounded_rectangle([(W-w)//2-56,y,(W+w)//2+56,y+h+72],radius=70,fill=GRN+(255,))
        d.text(((W-w)//2-b[0],y+36-b[1]),t,font=fb,fill=INK+(255,))
    return ov
def lista(v): return v if isinstance(v,list) else [v]
def glass(fr,box,a):
    x0,y0,x1,y1=box
    reg=fr.crop(box).filter(ImageFilter.GaussianBlur(22))
    reg=Image.blend(reg,Image.new("RGB",reg.size,(8,10,22)),0.62)
    m=Image.new("L",reg.size,0); ImageDraw.Draw(m).rounded_rectangle([0,0,reg.size[0]-1,reg.size[1]-1],radius=44,fill=int(255*a))
    fr.paste(reg,(x0,y0),m)
    if a>0.5:
        ImageDraw.Draw(fr,"RGBA").rounded_rectangle(box,radius=44,outline=(255,255,255,int(70*a)),width=2)
def ease(x): x=max(0,min(1,x)); return 1-(1-x)**3
def compose(fr,ov,box,t,dur,end=False):
    fr=Image.composite(BLACK,fr,scrim.point(lambda v:v)) if not end else fr
    a=ease((t-0.25)/0.45); out=1-ease((t-(dur-0.2))/0.2) if not end else 1; a*=out
    if a<=0: 
        return fr
    dy=int((1-a)*60)
    if end:
        dark=ImageEnhance.Brightness(fr.filter(ImageFilter.GaussianBlur(10))).enhance(0.38)
        fr=Image.blend(fr,dark,a)
    else:
        b=(box[0],box[1]+dy,box[2],box[3]+dy); glass(fr,b,a)
    o=ov.copy(); o.putalpha(ov.getchannel("A").point(lambda v:int(v*a)))
    fr.paste(o,(0,dy),o)
    return fr
chip_ov=Image.new("RGBA",(W,H),(0,0,0,0)); chip(ImageDraw.Draw(chip_ov))
def vid_frames(mov,ss,dur):
    p=subprocess.Popen(["ffmpeg","-v","error","-ss",str(ss),"-t",str(dur),"-i",mov,"-vf","scale=1080:1920:flags=lanczos,unsharp=5:5:0.6,eq=contrast=1.05:saturation=1.12","-r",str(FPS),"-f","rawvideo","-pix_fmt","rgb24","-"],stdout=subprocess.PIPE)
    n=int(dur*FPS)
    for k in range(n):
        b=p.stdout.read(W*H*3)
        if len(b)<W*H*3: break
        yield Image.frombytes("RGB",(W,H),b)
    p.stdout.close(); p.wait()
def photo_frames(path,dur,z0=1.0,z1=1.10):
    im=Image.open(path).convert("RGB"); sc=max(W/im.width,H/im.height)
    for k in range(int(dur*FPS)):
        z=sc*(z0+(z1-z0)*k/(dur*FPS)); w,h=int(im.width*z),int(im.height*z)
        r=im.resize((w,h),Image.BILINEAR); l=(w-W)//2; t=(h-H)//2
        yield r.crop((l,t,l+W,t+H))
out=sys.argv[2]; mudo=out+".mudo.mp4"
ff=subprocess.Popen(["ffmpeg","-v","error","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}","-r",str(FPS),"-i","-","-an","-c:v","libx264","-preset","medium","-crf","19","-pix_fmt","yuv420p",mudo],stdin=subprocess.PIPE)
n=0
for c in SPEC["cenas"]:
    dur=float(c["duracao"]); fim=bool(c.get("final"))
    if "video" in c: gen=vid_frames(caminho(c["video"]),c.get("inicio",0),dur)
    else: gen=photo_frames(caminho(c["foto"]),dur,1.0,1.06 if fim else 1.10)
    if fim: ov=end_layer(c); box=None
    else: ov,box=card_layer(c.get("etiqueta",""),c["titulo"],c.get("texto",[]),c.get("tamanho",100))
    for k,fr in enumerate(gen):
        fr=compose(fr,ov,box,k/FPS,dur,end=fim)
        fr.paste(chip_ov,(0,0),chip_ov)
        ff.stdin.write(fr.tobytes()); n+=1
ff.stdin.close(); ff.wait()
D=n/FPS; mus=SPEC.get("musica")
if mus:
    subprocess.check_call(["ffmpeg","-v","error","-y","-i",mudo,"-stream_loop","-1","-i",caminho(mus),"-filter_complex",
      f"[1:a]volume=0.8,afade=t=in:d=0.3,afade=t=out:st={D-1.2}:d=1.2[a]","-map","0:v","-map","[a]","-t",str(D),
      "-c:v","copy","-c:a","aac","-b:a","160k","-ar","44100","-movflags","+faststart",out])
else:  # o Instagram aceita Reel sem audio, mas uma trilha muda evita rejeicao em alguns casos
    subprocess.check_call(["ffmpeg","-v","error","-y","-i",mudo,"-f","lavfi","-i","anullsrc=r=44100:cl=stereo","-shortest",
      "-c:v","copy","-c:a","aac","-movflags","+faststart",out])
os.remove(mudo); print(f"OK {out} ({D:.1f} s)")
