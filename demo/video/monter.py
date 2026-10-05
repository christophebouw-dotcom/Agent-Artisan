import json, subprocess
C = json.load(open("clip.json")); COUPE = 0.25; FONDU = 0.35
def duree(f): return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f]))
# 1. Vidéo : chaque segment rogné au début (flash blanc du chargement), fondu entrant/sortant, puis concaténation.
entrees, filtres, debut_seg, t = [], [], {}, 0.0
for i, s in enumerate(C["segments"]):
    d = duree(s["video"]) - COUPE; debut_seg[s["nom"]] = t
    entrees += ["-i", s["video"]]
    filtres.append(f"[{i}:v]trim=start={COUPE},setpts=PTS-STARTPTS,fps=30,fade=t=in:st=0:d={FONDU},fade=t=out:st={d-FONDU:.3f}:d={FONDU}[v{i}]")
    t += d
total = t
filtres.append("".join(f"[v{i}]" for i in range(len(C["segments"]))) + f"concat=n={len(C['segments'])}:v=1:a=0[video]")
# 2. Voix : chaque phrase posée à son instant.
n = len(C["segments"]); voix = []
for j, v in enumerate(C["voix"]):
    entrees += ["-i", f"tts/vo/{v['cle']}.wav"]
    ms = int((debut_seg[v["segment"]] + v["debut"] - COUPE) * 1000)
    filtres.append(f"[{n+j}:a]aresample=44100,aformat=channel_layouts=stereo,adelay={ms}|{ms},volume=1.6[vo{j}]")
    voix.append(f"[vo{j}]")
filtres.append("".join(voix) + f"amix=inputs={len(voix)}:normalize=0,apad=whole_dur={total:.3f}[voixmix]")
filtres.append("[voixmix]asplit=2[voixA][voixB]")
# 3. Musique : coupée à la durée, fondu de fin, baissée sous la voix (sidechain).
m = n + len(voix); entrees += ["-i", "tts/musique.wav"]
filtres.append(f"[{m}:a]atrim=0:{total:.3f},afade=t=in:d=1,afade=t=out:st={total-3:.3f}:d=3,volume=0.55[mus]")
filtres.append("[mus][voixA]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[musbaisse]")
filtres.append("[musbaisse][voixB]amix=inputs=2:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[son]")
cmd = ["ffmpeg","-y","-loglevel","error",*entrees,"-filter_complex",";".join(filtres),"-map","[video]","-map","[son]",
       "-c:v","libx264","-pix_fmt","yuv420p","-crf","20","-preset","medium","-c:a","aac","-b:a","160k","-ar","44100","-movflags","+faststart","-shortest","/home/user/jarvis-artisan-video-vente.mp4"]
subprocess.run(cmd, check=True)
# Version musique seule
f2 = [f for f in filtres if not f.startswith("[mus][voixA]") and not f.startswith("[musbaisse]")]
f2 = [f.replace("volume=0.55[mus]", "volume=1[mus]") for f in f2]
f2.append("[mus]loudnorm=I=-16:TP=-1.5:LRA=11[son]")
f2 = [f for f in f2 if not f.startswith("[voixmix]asplit")] + ["[voixmix]anullsink"]
subprocess.run(["ffmpeg","-y","-loglevel","error",*entrees,"-filter_complex",";".join(f2),"-map","[video]","-map","[son]",
       "-c:v","libx264","-pix_fmt","yuv420p","-crf","20","-preset","medium","-c:a","aac","-b:a","160k","-ar","44100","-movflags","+faststart","-shortest","/home/user/jarvis-artisan-video-vente-musique-seule.mp4"], check=True)
print(f"durée {total:.1f} s")
