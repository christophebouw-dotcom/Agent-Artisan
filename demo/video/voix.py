import json, soundfile as sf
from kokoro_onnx import Kokoro
k = Kokoro("kokoro.onnx", "voices.bin")
textes = {
 "intro1": "Vous êtes artisan ? Le soir, après le chantier, il reste encore les devis à faire.",
 "intro2": "Voici Djarvisse Artisan : l'assistant qui prépare vos devis pendant que vous travaillez.",
 "s1": "Un client vous écrit. Il veut refaire sa salle de bain de six mètres carrés, avec une douche à l'italienne.",
 "s2": "En quelques secondes, Djarvisse a tout compris.",
 "s3": "Il prépare la réponse au client, pour demander ce qui manque. Vous la relisez, et vous l'envoyez.",
 "s4": "Puis il chiffre le devis, ligne par ligne, avec vos propres prix.",
 "s5": "Un prix à ajuster ? Vous le changez, et tout se recalcule.",
 "s6": "Un clic, et le devis est prêt en PDF. Deux minutes, au lieu de trente minutes à une heure.",
 "s7": "Une fuite en pleine journée ? Djarvisse repère l'urgence, et vous prévient : client à rappeler aujourd'hui.",
 "outro": "Djarvisse prépare. Vous validez. Rien ne part sans votre accord. Objectif : cinq heures de gagnées chaque semaine. Réservez votre démonstration gratuite de trente minutes.",
}
durees = {}
for cle, t in textes.items():
    s, sr = k.create(t, voice="ff_siwis", speed=1.0, lang="fr-fr")
    sf.write(f"vo/{cle}.wav", s, sr); durees[cle] = round(len(s) / sr, 2)
print(k.tokenizer.phonemize("Djarvisse Artisan, six mètres carrés, PDF", "fr-fr"))
json.dump(durees, open("vo/durees.json", "w")); print(durees, sum(durees.values()))
