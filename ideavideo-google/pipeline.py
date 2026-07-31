"""
Motor de video (Fase 2): idea -> guion -> voz -> imágenes por escena (Pexels) -> montaje ffmpeg + música -> MP4.
Voz: Piper (comercial/offline) -> edge-tts -> espeak. Marca de agua opcional. Música de fondo opcional.
"""
import os, re, io, json, math, glob, shutil, subprocess
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE = Path(__file__).parent
FONT_DIR = "/usr/share/fonts/truetype/dejavu"
def _font(name, size):
    for c in [f"{FONT_DIR}/{name}", f"{FONT_DIR}/DejaVuSans-Bold.ttf", f"{FONT_DIR}/DejaVuSans.ttf"]:
        if os.path.exists(c): return ImageFont.truetype(c, size)
    return ImageFont.load_default()

# Modo bajo consumo (LOW_MEM=1): renderiza en 720p, ideal para servidores con poca RAM (plan gratis).
LOW_MEM = os.getenv("LOW_MEM") == "1"
FORMATS = ({"16:9": (1280, 720), "9:16": (720, 1280)} if LOW_MEM
           else {"16:9": (1920, 1080), "9:16": (1080, 1920)})
BRAND = (109, 40, 217); ACCENT = (34, 197, 94)
BRAND_A = os.getenv("BRAND_A", "Idea"); BRAND_B = os.getenv("BRAND_B", "Video")
UA = {"User-Agent": "Mozilla/5.0 (compatible; IdeaVideo/2.0)"}

def ffprobe_duration(p):
    o = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1", p], capture_output=True, text=True)
    try: return float(o.stdout.strip())
    except Exception: return 3.0

# ---------- idea -> guion ----------
def _split(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+|•|·|;\s*", text)
    return [re.sub(r"\s+"," ",p).strip(" -•·\t") for p in parts if len(p.strip())>3]

TONE = {"informativo":("Esto es lo que necesitas saber.","Gracias por ver este video."),
        "educativo":("En este video vas a aprender algo nuevo.","Gracias por aprender. Suscríbete para más."),
        "motivacional":("Hoy quiero compartirte algo importante.","Tú puedes lograrlo. Comparte este video."),
        "marketing":("Descubre esto que preparamos para ti.","No te lo pierdas. Más info en el enlace."),
        "storytelling":("Déjame contarte una historia.","Y así termina. Gracias por acompañarme.")}

def _title(s, n=7):
    t=" ".join(s.split()[:n]); return (t[:1].upper()+t[1:]).rstrip(".,;: ")

def _clean_idea(idea):
    """Quita frases de mando ('crea un video de...') para que la narración no las repita."""
    t = (idea or "").strip()
    t = re.sub(r'(?i)^\s*(por favor[,\s]*)?(cr[eé]a|h[aá]z|hazme|genera|gener[aá]me|quiero|necesito|arma| armame|prepara|realiza|me gustar[ií]a)\b[^.]*?\b(videos?|shorts?|reels?|clips?)\b\s*(cortos?|verticales?)?\s*(sobre|acerca de|de)\s+', '', t)
    return t.strip() or (idea or "").strip()

def build_from_idea(idea, tone="informativo", n_scenes=5, lang="es"):
    intro_t, outro_t = TONE.get(tone, TONE["informativo"])
    idea = _clean_idea(idea)
    sents = _split(idea) or [idea.strip() or "IdeaVideo"]
    n = max(1, min(int(n_scenes), len(sents))); per = math.ceil(len(sents)/n)
    groups = [sents[i:i+per] for i in range(0,len(sents),per)]
    segs = [{"kind":"intro","headline":_title(sents[0],6),"text":intro_t,"query":sents[0]}]
    for g in groups:
        segs.append({"kind":"scene","headline":_title(g[0]),"text":" ".join(g),"query":g[0]})
    segs.append({"kind":"outro","headline":"¡Gracias!","text":outro_t,"query":""})
    return segs

def expand_idea_with_llm(idea, tone="informativo", n_scenes=5, lang="es"):
    key = os.getenv("GROQ_API_KEY")
    if not key: return None
    try:
        prompt = (f"Eres un guionista experto de videos cortos. A partir del siguiente TEMA, escribe el CONTENIDO REAL del video "
                  f"(NO repitas ni narres la instrucción del usuario; desarrolla el tema con información concreta y atractiva). "
                  f"Idioma: español. Tono: {tone}. Estructura: una intro que enganche, {n_scenes} escenas de contenido y un cierre con llamado a la acción. "
                  f"Cada escena debe tener una narración de 1 a 2 frases naturales para locutar en voz alta. "
                  f'Devuelve SOLO JSON válido con esta forma: {{"scenes":[{{"title":"titular corto","narration":"texto a locutar","keywords":"3 a 5 palabras EN INGLÉS para generar una imagen cinematográfica de la escena"}}]}}. '
                  f"TEMA: {idea}")
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization":f"Bearer {key}"},
            json={"model":os.getenv("GROQ_MODEL","openai/gpt-oss-120b"),"messages":[{"role":"user","content":prompt}],
                  "temperature":0.7,"response_format":{"type":"json_object"}}, timeout=40)
        scenes = json.loads(r.json()["choices"][0]["message"]["content"]).get("scenes", [])
        if not scenes: return None
        out=[]
        for i,s in enumerate(scenes):
            kind="intro" if i==0 else ("outro" if i==len(scenes)-1 else "scene")
            out.append({"kind":kind,"headline":(s.get("title") or "")[:120],
                        "text":(s.get("narration") or s.get("title") or ""),
                        "query":s.get("keywords") or s.get("title") or ""})
        return out
    except Exception:
        return None

# ---------- imágenes con IA (Pollinations, gratis y sin clave) ----------
def fetch_ai_image(prompt, fmt, workdir, idx):
    """Genera una imagen cinematográfica con IA (Pollinations). Devuelve la ruta o None."""
    prompt = (prompt or "").strip()
    if not prompt:
        return None
    try:
        import urllib.parse
        W, H = FORMATS[fmt]
        style = "cinematic photography, dramatic lighting, highly detailed, realistic, high quality, 8k"
        full = f"{prompt}, {style}"
        model = os.getenv("AI_IMAGE_MODEL", "flux")  # 'flux' (mejor) o 'turbo' (más rápido)
        url = (f"https://image.pollinations.ai/prompt/{urllib.parse.quote(full[:320])}"
               f"?width={W}&height={H}&nologo=true&model={model}&seed={idx+1}")
        r = requests.get(url, headers=UA, timeout=float(os.getenv("AI_IMAGE_TIMEOUT", "90")))
        if r.status_code == 200 and r.content and len(r.content) > 3000:
            path = str(Path(workdir) / f"ai{idx}.jpg")
            open(path, "wb").write(r.content)
            try:
                Image.open(path).verify()  # confirmar que es una imagen válida
            except Exception:
                return None
            return path
    except Exception:
        return None
    return None

# ---------- imágenes (Pexels, gratis con clave) ----------
def fetch_pexels_image(query, fmt, workdir, idx):
    key = os.getenv("PEXELS_API_KEY")
    if not key or not query: return None
    try:
        orient = "landscape" if fmt == "16:9" else "portrait"
        r = requests.get("https://api.pexels.com/v1/search",
            headers={"Authorization": key},
            params={"query": query[:60], "per_page": 1, "orientation": orient}, timeout=15)
        photos = r.json().get("photos", [])
        if not photos: return None
        url = photos[0]["src"]["large2x"]
        img = requests.get(url, headers=UA, timeout=15).content
        path = str(Path(workdir) / f"bg{idx}.jpg"); open(path, "wb").write(img)
        return path
    except Exception:
        return None

# ---------- voz: Piper -> edge -> espeak ----------
def synthesize(text, voice, out_path, engine="auto"):
    text = re.sub(r"\s+"," ",text).strip() or "..."
    order = {"auto":["piper","edge","espeak"],"piper":["piper","espeak"],
             "edge":["edge","espeak"],"espeak":["espeak"]}[engine if engine in ("auto","piper","edge","espeak") else "auto"]
    for eng in order:
        try:
            if eng=="piper" and _piper(text,out_path): return ffprobe_duration(out_path)
            if eng=="edge":
                import asyncio, edge_tts
                asyncio.run(edge_tts.Communicate(text, voice).save(out_path))
                if os.path.getsize(out_path)>0: return ffprobe_duration(out_path)
            if eng=="espeak":
                wav=out_path.rsplit(".",1)[0]+".wav"; v="es" if not voice.startswith("en") else "en"
                subprocess.run(["espeak-ng","-v",v,"-s","150","-w",wav,text], check=True, capture_output=True)
                if wav!=out_path: subprocess.run(["ffmpeg","-y","-i",wav,out_path], capture_output=True)
                return ffprobe_duration(out_path)
        except Exception:
            continue
    raise RuntimeError("No se pudo generar la voz.")

def _piper(text, out_path):
    model=os.getenv("PIPER_MODEL")
    if not model or not os.path.exists(model) or not shutil.which("piper"): return False
    wav=out_path.rsplit(".",1)[0]+".wav"
    subprocess.run(["piper","--model",model,"--output_file",wav], input=text.encode(), check=True, capture_output=True)
    if wav!=out_path: subprocess.run(["ffmpeg","-y","-i",wav,out_path], capture_output=True)
    return os.path.exists(out_path) and os.path.getsize(out_path)>0

# ---------- imágenes / escenas ----------
def _gradient(W,H):
    img=Image.new("RGB",(W,H),(14,12,28)); d=ImageDraw.Draw(img)
    for yy in range(H):
        t=yy/H; d.line([(0,yy),(W,yy)], fill=(int(BRAND[0]*(1-t)+10*t),int(BRAND[1]*(1-t)+10*t),int(BRAND[2]*(1-t)+30*t)))
    return img

def _wrap(d,text,font,mw):
    words,lines,cur=text.split(),[],""
    for w in words:
        t=(cur+" "+w).strip()
        if d.textlength(t,font=font)<=mw: cur=t
        else:
            if cur: lines.append(cur)
            cur=w
    if cur: lines.append(cur)
    return lines

def make_visual(seg, fmt, out_path, idx=0, watermark=False, bg_path=None):
    W,H=FORMATS[fmt]
    if bg_path and os.path.exists(bg_path):
        try:
            bg=Image.open(bg_path).convert("RGB"); sc=max(W/bg.width,H/bg.height)
            bg=bg.resize((int(bg.width*sc)+1,int(bg.height*sc)+1))
            x=(bg.width-W)//2; y=(bg.height-H)//2
            bg=bg.crop((x,y,x+W,y+H)).filter(ImageFilter.GaussianBlur(2))
            img=Image.blend(bg, Image.new("RGB",(W,H),(6,6,16)), 0.28)
        except Exception:
            img=_gradient(W,H)
    else:
        img=_gradient(W,H)
    d=ImageDraw.Draw(img); pad=int(W*0.07)
    d.rectangle([0,0,W,int(H*0.11)], fill=(0,0,0))
    bf=_font("DejaVuSans-Bold.ttf",int(H*0.045))
    d.text((pad,int(H*0.037)),BRAND_A,font=bf,fill=(255,255,255))
    d.text((pad+d.textlength(BRAND_A,font=bf)+4,int(H*0.037)),BRAND_B,font=bf,fill=ACCENT)
    if seg["kind"]=="scene":
        tf=_font("DejaVuSans-Bold.ttf",int(H*0.03)); tag=str(idx); cx=W-pad-int(H*0.03)
        d.ellipse([cx-int(H*0.03),int(H*0.035),cx+int(H*0.03),int(H*0.035)+int(H*0.06)], fill=ACCENT)
        d.text((cx-d.textlength(tag,font=tf)/2,int(H*0.045)),tag,font=tf,fill=(0,0,0))
    hl=seg["headline"] or ""; fs=int(H*(0.062 if fmt=="16:9" else 0.052)); hf=_font("DejaVuSans-Bold.ttf",fs)
    lines=_wrap(d,hl,hf,W-pad*2)[:5]; lh=int(fs*1.2); bh=lh*max(len(lines),1); y0=int(H*(0.66 if fmt=="16:9" else 0.62))-bh//2
    # panel oscuro detrás del titular (legibilidad sobre foto)
    panel=Image.new("RGBA",(W,bh+int(H*0.12)),(5,8,20,175))
    img.paste(Image.new("RGB",panel.size,(5,8,20)),(0,y0-int(H*0.05)),panel); d=ImageDraw.Draw(img)
    d.rectangle([pad,y0-int(H*0.03),pad+int(W*0.10),y0-int(H*0.03)+9], fill=ACCENT)
    yy=y0
    for ln in lines: d.text((pad,yy),ln,font=hf,fill=(255,255,255)); yy+=lh
    if watermark: _watermark(img,W,H)
    img.save(out_path, quality=90); return out_path

def _watermark(img,W,H):
    ov=Image.new("RGBA",(W,H),(0,0,0,0)); dd=ImageDraw.Draw(ov)
    wf=_font("DejaVuSans-Bold.ttf",int(H*0.045)); txt=f"{BRAND_A}{BRAND_B} · DEMO"; tw=dd.textlength(txt,font=wf)
    for yy in range(-H,H*2,int(H*0.22)):
        for xx in range(-W,W*2,int(tw*1.4)): dd.text((xx,yy),txt,font=wf,fill=(255,255,255,40))
    img.paste(Image.alpha_composite(img.convert("RGBA"),ov).convert("RGB"),(0,0))

# ---------- montaje ----------
def _clip(image,audio,dur,fmt,out):
    W,H=FORMATS[fmt]; frames=max(int(dur*30)+15,30)
    vf=(f"scale={W}:{H},zoompan=z='min(zoom+0.0005,1.10)':d={frames}"
        f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps=30,format=yuv420p")
    subprocess.run(["ffmpeg","-y","-loop","1","-i",image,"-i",audio,"-vf",vf,"-t",f"{dur:.2f}",
        "-c:v","libx264","-preset","veryfast","-threads","1","-c:a","aac","-b:a","128k","-pix_fmt","yuv420p","-shortest",out],
        check=True, capture_output=True)
    return out

def _srt_t(t):
    h=int(t//3600);m=int((t%3600)//60);s=int(t%60);ms=int((t-int(t))*1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def _find_music():
    env=os.getenv("MUSIC_FILE")
    if env and os.path.exists(env): return env
    files=glob.glob(str(BASE/"assets"/"music"/"*.mp3"))+glob.glob(str(BASE/"assets"/"music"/"*.m4a"))
    return files[0] if files else None

def render(segments, fmt, workdir, out_path, voice="es-PE-CamilaNeural", engine="auto",
           burn_subs=True, watermark=False, use_images=True, progress=None):
    workdir=Path(workdir); workdir.mkdir(parents=True, exist_ok=True); clips=[]; n=len(segments)
    for i,seg in enumerate(segments):
        if progress: progress(int(10+70*i/n), f"Generando escena {i+1}/{n}…")
        audio=str(workdir/f"a{i}.mp3"); seg["duration"]=synthesize(seg["text"],voice,audio,engine=engine)
        bg=None
        if use_images and seg["kind"] in ("scene","intro"):
            prompt = seg.get("query") or seg.get("headline") or seg.get("text","")
            if os.getenv("AI_IMAGES") == "1":
                # IA (Pollinations) como principal; si falla, cae a Pexels; si no, fondo de marca.
                bg = fetch_ai_image(prompt, fmt, workdir, i) or fetch_pexels_image(seg.get("query",""), fmt, workdir, i)
            else:
                bg = fetch_pexels_image(seg.get("query",""), fmt, workdir, i)
        image=str(workdir/f"img{i}.jpg"); make_visual(seg,fmt,image,idx=i,watermark=watermark,bg_path=bg)
        clip=str(workdir/f"c{i}.mp4"); _clip(image,audio,seg["duration"],fmt,clip); clips.append(clip)
    if progress: progress(84,"Uniendo escenas…")
    lf=workdir/"list.txt"; lf.write_text("".join(f"file '{c}'\n" for c in clips))
    merged=str(workdir/"merged.mp4")
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(lf),"-c","copy",merged], check=True, capture_output=True)
    final=merged
    music=_find_music()
    if music:
        if progress: progress(90,"Agregando música…")
        mixed=str(workdir/"mixed.mp4")
        r=subprocess.run(["ffmpeg","-y","-i",merged,"-stream_loop","-1","-i",music,
            "-filter_complex","[1:a]volume=0.10[m];[0:a][m]amix=inputs=2:duration=first[a]",
            "-map","0:v","-map","[a]","-c:v","copy","-c:a","aac","-shortest",mixed], capture_output=True)
        if os.path.exists(mixed) and r.returncode==0: final=mixed
    if burn_subs:
        if progress: progress(95,"Subtítulos…")
        srt=workdir/"s.srt"; t=0.0; L=[]
        for i,s in enumerate(segments,1):
            dd=s.get("duration",3.0); L.append(f"{i}\n{_srt_t(t)} --> {_srt_t(t+dd)}\n{s['headline']}\n"); t+=dd
        srt.write_text("\n".join(L)); subbed=str(workdir/"sub.mp4")
        r=subprocess.run(["ffmpeg","-y","-i",final,"-vf",
            f"subtitles={srt}:force_style='FontName=DejaVu Sans,FontSize=16,PrimaryColour=&H00FFFFFF,BorderStyle=3,Outline=1'",
            "-threads","1","-c:a","copy",subbed], capture_output=True)
        if os.path.exists(subbed) and r.returncode==0: final=subbed
    os.replace(final,out_path)
    if progress: progress(100,"¡Video listo!")
    return out_path
