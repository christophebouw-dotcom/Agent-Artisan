# Musique de fond originale, synthétisée : pop légère et positive, 104 bpm, Do – Sol – La m – Fa.
import numpy as np, soundfile as sf
SR = 44100; BPM = 104; BEAT = 60 / BPM; BAR = 4 * BEAT; DUREE = 78.0
n = int(SR * DUREE); g = np.zeros((n, 2))
def note(f): return 440 * 2 ** ((f - 69) / 12)
def env(L, a, r):
    e = np.ones(L); A = min(int(a * SR), L); R = min(int(r * SR), L - A)
    e[:A] = np.linspace(0, 1, A); e[L - R:] *= np.linspace(1, 0, R); return e
def ajoute(sig, t, pan=0.0, vol=1.0):
    i = int(t * SR); j = min(n, i + len(sig))
    if i >= n: return
    g[i:j, 0] += sig[: j - i] * vol * (1 - pan) ; g[i:j, 1] += sig[: j - i] * vol * (1 + pan)
accords = [[60, 64, 67], [55, 59, 62], [57, 60, 64], [53, 57, 60]]  # C G Am F
basses = [36, 43, 45, 41]
rng = np.random.default_rng(7)
nb_mesures = int(DUREE / BAR) + 1
for m in range(nb_mesures):
    t0 = m * BAR; acc = accords[m % 4]; intro = m < 2
    # nappe douce (sinus + harmoniques, légère désaccordation)
    L = int(BAR * SR); tt = np.arange(L) / SR; pad = np.zeros(L)
    for f in acc:
        for d in (-0.15, 0.15):
            fr = note(f + 12) + d
            pad += np.sin(2 * np.pi * fr * tt) + 0.3 * np.sin(4 * np.pi * fr * tt)
    ajoute(pad * env(L, 0.4, 0.5) * 0.018, t0, pan=0.0)
    # arpège pincé en croches
    motif = [0, 1, 2, 1, 0, 2, 1, 2]
    for k, idx in enumerate(motif):
        fr = note(acc[idx] + 12); L2 = int(0.6 * SR); t2 = np.arange(L2) / SR
        s = (np.sin(2 * np.pi * fr * t2) + 0.4 * np.sin(4 * np.pi * fr * t2) + 0.15 * np.sin(6 * np.pi * fr * t2)) * np.exp(-t2 * 7)
        ajoute(s * 0.05, t0 + k * BEAT / 2, pan=0.3 if k % 2 else -0.3)
    if intro: continue
    # basse
    for k in (0, 2.5):
        fr = note(basses[m % 4]); L3 = int(BEAT * 1.4 * SR); t3 = np.arange(L3) / SR
        s = np.sin(2 * np.pi * fr * t3) * np.exp(-t3 * 2.2) + 0.25 * np.sin(4 * np.pi * fr * t3) * np.exp(-t3 * 4)
        ajoute(s * 0.16 * env(L3, 0.005, 0.1), t0 + k * BEAT)
    # grosse caisse douce
    for k in (0, 2):
        L4 = int(0.35 * SR); t4 = np.arange(L4) / SR
        fr = 110 * np.exp(-t4 * 18) + 45
        s = np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-t4 * 9)
        ajoute(s * 0.22, t0 + k * BEAT)
    # claquement léger sur 2 et 4, shaker sur les contretemps
    for k in (1, 3):
        L5 = int(0.18 * SR); s = rng.normal(0, 1, L5) * np.exp(-np.arange(L5) / SR * 28)
        ajoute(np.convolve(s, [0.5, 0.5], "same") * 0.05, t0 + k * BEAT)
    for k in range(8):
        L6 = int(0.05 * SR); s = np.diff(rng.normal(0, 1, L6 + 1)) * np.exp(-np.arange(L6) / SR * 90)
        ajoute(s * (0.014 if k % 2 else 0.007), t0 + k * BEAT / 2, pan=0.4)
# fondu final
f = int(4 * SR); g[-f:] *= np.linspace(1, 0, f)[:, None]
g /= np.abs(g).max() / 0.8
sf.write("musique.wav", g, SR); print("ok", DUREE)
