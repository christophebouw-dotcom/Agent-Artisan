"""Évalue le module devis de Jarvis Artisan sur les cas de cas-tests.jsonl.

Usage :
    python3 tests/evaluer.py                                  # Ollama en local (zéro coût), modèle llama3.1
    python3 tests/evaluer.py --modele qwen2.5:7b              # autre modèle Ollama
    python3 tests/evaluer.py --backend claude --modele haiku  # via Claude Code (consomme ton abonnement)
    python3 tests/evaluer.py --backend n8n                    # le workflow importé dans n8n, de bout en bout
    python3 tests/evaluer.py --backend n8n --url http://localhost:5678/webhook-test/jarvis-artisan/devis

Le calcul du devis (prix, totaux, message au client) est fait par n8n/code/devis.js, sans IA.
Écrit un rapport tests/resultats-<backend>-<modele>.md. Demandes fictives : aucune donnée de client réel.
"""

import argparse
import json
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
GRILLE = json.loads((RACINE / "grille-prix" / "plomberie-demo.json").read_text())
MODELE_PROMPT = (RACINE / "prompt" / "prompt-systeme.md").read_text()
DEVIS_JS = RACINE / "n8n" / "code" / "devis.js"


def node(fonction, *args):
    """Appelle une fonction de devis.js avec Node et renvoie son résultat."""
    script = (
        f"const d = require({json.dumps(str(DEVIS_JS))});"
        f"const args = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
        f"process.stdout.write(JSON.stringify(d.{fonction}(...args)));"
    )
    sortie = subprocess.run(["node", "-e", script], input=json.dumps(args), capture_output=True, text=True, check=True)
    return json.loads(sortie.stdout)


SCHEMA = node("schemaExtraction", GRILLE)
PROMPT = node("promptSysteme", MODELE_PROMPT, GRILLE)


def appeler_ollama(demande, modele, url):
    corps = {
        "model": modele,
        "stream": False,
        "format": SCHEMA,
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": f"Demande : « {demande} »"},
        ],
    }
    requete = urllib.request.Request(url or "http://localhost:11434/api/chat", data=json.dumps(corps).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(requete, timeout=300) as r:
        extraction = json.loads(json.loads(r.read())["message"]["content"])
    return node("calculerDevis", extraction, GRILLE)


def appeler_claude(demande, modele, url):
    # Dossier vide : la session ne charge ni CLAUDE.md ni hooks.
    with tempfile.TemporaryDirectory() as vide:
        sortie = subprocess.run(
            [
                "claude", "-p", f"Demande : « {demande} »",
                "--system-prompt", PROMPT,
                "--model", modele,
                "--output-format", "json",
                "--json-schema", json.dumps(SCHEMA),
                "--tools", "",
                "--permission-mode", "dontAsk",
            ],
            cwd=vide, capture_output=True, text=True, timeout=300,
        )
    resultat = json.loads(sortie.stdout)
    if resultat.get("structured_output") is None:
        raise RuntimeError(resultat.get("result") or sortie.stderr[:300])
    return node("calculerDevis", resultat["structured_output"], GRILLE)


def appeler_n8n(demande, modele, url):
    requete = urllib.request.Request(
        url or "http://localhost:5678/webhook/jarvis-artisan/devis",
        data=json.dumps({"message": demande}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(requete, timeout=300) as r:
        return json.loads(r.read())


def verifier(cas, r):
    """Renvoie la liste des écarts entre le résultat et l'attendu (vide = réussi)."""
    a, e = cas["attendu"], r.get("extraction") or {}
    ecarts = []
    if r.get("statut") == "erreur_ia":
        return [f"erreur IA : {r.get('erreurs')}"]
    acceptees = a.get("prestations_acceptees") or ([a["prestation"]] if "prestation" in a else None)
    if acceptees and e.get("prestation") not in acceptees:
        ecarts.append(f"prestation {e.get('prestation')} au lieu de {' ou '.join(acceptees)}")
    if "surface" in a and e.get("surface_m2") != a["surface"]:
        ecarts.append(f"surface {e.get('surface_m2')} au lieu de {a['surface']}")
    if "options" in a and sorted(e.get("options", [])) != sorted(a["options"]):
        ecarts.append(f"options {e.get('options')} au lieu de {a['options']}")
    for i in a.get("infos_contient", []):
        if i not in e.get("infos_manquantes", []) and not (i == "surface" and r.get("statut") == "brouillon_incomplet"):
            ecarts.append(f"info manquante non relevée : {i}")
    for i in a.get("infos_exclut", []):
        if i in e.get("infos_manquantes", []):
            ecarts.append(f"info demandée à tort : {i}")
    if "urgence" in a and e.get("urgence") != a["urgence"]:
        ecarts.append(f"urgence {e.get('urgence')} au lieu de {a['urgence']}")
    if "statut" in a and r.get("statut") != a["statut"]:
        ecarts.append(f"statut {r.get('statut')} au lieu de {a['statut']}")
    if a.get("a_verifier") and not e.get("a_verifier"):
        ecarts.append("a_verifier devrait être true")
    for mot in a.get("resume_exclut", []):
        if mot.lower() in e.get("resume", "").lower():
            ecarts.append(f"donnée personnelle recopiée dans le résumé : {mot}")
    # Règles communes, vérifiées par le code : totaux justes, mention IA, aucun envoi.
    d = r.get("devis")
    if d and d["complet"]:
        somme = round(sum(l["montant_ht"] or 0 for l in d["lignes"]), 2)
        if abs(somme - d["total_ht"]) > 0.01 or abs(d["total_ht"] + d["tva"] - d["total_ttc"]) > 0.01:
            ecarts.append("totaux incohérents")
    if "assistant IA" not in r.get("message_client_brouillon", ""):
        ecarts.append("le message au client ne dit pas qu'il a été préparé avec une IA")
    if d and not d["complet"] and d["total_ttc"] is not None:
        ecarts.append("total affiché sur un devis incomplet")
    return ecarts


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["ollama", "claude", "n8n"], default="ollama")
    p.add_argument("--modele", default="llama3.1")
    p.add_argument("--url", help="URL d'Ollama (/api/chat) ou du webhook n8n")
    args = p.parse_args()
    appeler = {"ollama": appeler_ollama, "claude": appeler_claude, "n8n": appeler_n8n}[args.backend]

    cas_liste = [json.loads(l) for l in (RACINE / "tests" / "cas-tests.jsonl").read_text().splitlines() if l.strip()]
    lignes, reussis = [], 0
    for cas in cas_liste:
        debut = time.time()
        try:
            r = appeler(cas["demande"], args.modele, args.url)
            ecarts = verifier(cas, r)
        except Exception as exc:  # une erreur d'appel compte comme un échec
            r, ecarts = {}, [f"appel impossible : {exc}"]
        duree = time.time() - debut
        reussis += not ecarts
        e = r.get("extraction") or {}
        total = (r.get("devis") or {}).get("total_ttc")
        print(f"cas {cas['id']:>2} ({cas['type']}) : {'OK' if not ecarts else 'ÉCHEC'} {'; '.join(ecarts)}")
        lignes.append(
            f"| {cas['id']} | {cas['type']} | {e.get('prestation', '')} | {e.get('surface_m2', '')} | "
            f"{', '.join(e.get('options', []))} | {e.get('urgence', '')} | {r.get('statut', '')} | "
            f"{'' if total is None else f'{total:.2f} €'} | {duree:.1f} s | {'✅' if not ecarts else '❌ ' + '; '.join(ecarts)} |"
        )

    nom = f"resultats-{args.backend}-{args.modele.replace(':', '-').replace('/', '-')}.md"
    rapport = [
        f"# Résultats : {args.backend}, modèle {args.modele}",
        "",
        f"Date : {time.strftime('%Y-%m-%d')}. Score : **{reussis}/{len(cas_liste)}**. Demandes fictives.",
        "",
        "| Cas | Type | Prestation | Surface | Options | Urgence | Statut | Total TTC | Durée | Verdict |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        *lignes,
        "",
    ]
    (RACINE / "tests" / nom).write_text("\n".join(rapport))
    print(f"\nScore : {reussis}/{len(cas_liste)}. Rapport : tests/{nom}")


if __name__ == "__main__":
    main()
