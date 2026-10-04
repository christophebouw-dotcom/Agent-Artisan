"""Assemble le workflow n8n du module devis à partir des fichiers sources.

    python3 outils/construire_workflow.py              # modèle Ollama par défaut : llama3.1
    python3 outils/construire_workflow.py --modele qwen2.5:7b

Sources : grille-prix/plomberie-demo.json, prompt/prompt-systeme.md, n8n/code/devis.js, demo/index.html.
Sortie : n8n/jarvis-artisan-devis.json, à importer dans n8n (Workflows › Import from file).
On modifie les sources, puis on relance ce script : on ne modifie pas le JSON à la main.
"""

import argparse
import json
import re
import uuid
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
OLLAMA = "http://host.docker.internal:11434/api/chat"  # n8n dans Docker sur le Mac → Ollama sur le Mac


def ident(graine):
    """Identifiant stable (le JSON ne change pas d'une construction à l'autre)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "jarvis-artisan/" + graine))


def code_commun(modele):
    grille = json.loads((RACINE / "grille-prix" / "plomberie-demo.json").read_text())
    prompt = (RACINE / "prompt" / "prompt-systeme.md").read_text()
    lib = (RACINE / "n8n" / "code" / "devis.js").read_text()
    lib = re.sub(r"// @export-debut.*?// @export-fin\n", "", lib, flags=re.S)
    return (
        "// Généré par outils/construire_workflow.py : modifier les sources du dépôt, pas ce nœud.\n"
        f"const MODELE = {json.dumps(modele)}; // modèle Ollama (ollama list)\n"
        f"const GRILLE = {json.dumps(grille, ensure_ascii=False, indent=2)};\n"
        f"const PROMPT = {json.dumps(prompt, ensure_ascii=False)};\n\n"
        + lib
    )


def construire(modele):
    commun = code_commun(modele)
    preparer = commun + """
// --- Nœud : préparer la requête pour Ollama ---
const corps = $input.first().json.body || {};
const message = String(corps.message || "").trim().slice(0, 4000);
return [{ json: {
  message,
  vide: message.length === 0,
  requete: {
    model: MODELE,
    stream: false,
    format: schemaExtraction(GRILLE),
    options: { temperature: 0 },
    messages: [
      { role: "system", content: promptSysteme(PROMPT, GRILLE) },
      { role: "user", content: `Demande : « ${message} »` },
    ],
  },
} }];
"""
    calculer = commun + """
// --- Nœud : calculer le devis (sans IA) ---
const r = $input.first().json;
let extraction = null;
try { extraction = JSON.parse(r.message.content); } catch (e) { /* sortie illisible : traitée plus bas */ }
const resultat = calculerDevis(extraction, GRILLE);
if (r.error) {
  resultat.erreurs = [String(r.error.message || r.error)];
  resultat.a_faire = "Ollama ne répond pas (lancé ? modèle « " + MODELE + " » installé ?). Traiter la demande à la main.";
}
return [{ json: resultat }];
"""
    vide = """return [{ json: {
  statut: "erreur_entree",
  a_faire: "Demande vide : rien à lire. Envoyer {\\"message\\": \\"texte de la demande\\"}.",
} }];
"""
    html = (RACINE / "demo" / "index.html").read_text()

    noeuds = [
        {
            "parameters": {
                "content": "## Jarvis Artisan · module devis\nDémo · entreprise fictive, prix inventés.\n\n1. Le client écrit (webhook POST `jarvis-artisan/devis`, champ `message`).\n2. Ollama lit la demande et rend un JSON (prestation, surface, options, infos manquantes). **Il ne chiffre rien.**\n3. Le code calcule le devis avec la grille de l'artisan.\n4. Le brouillon revient à l'artisan. **Rien n'est envoyé au client.**\n\nÉcran de démo : ouvrir l'URL du webhook GET `jarvis-artisan`.\nSources et tests : dépôt Agent-Artisan.",
                "height": 360,
                "width": 420,
            },
            "id": ident("note"),
            "name": "Mode d'emploi",
            "type": "n8n-nodes-base.stickyNote",
            "typeVersion": 1,
            "position": [-520, -140],
        },
        {
            "parameters": {"httpMethod": "POST", "path": "jarvis-artisan/devis", "responseMode": "responseNode", "options": {"allowedOrigins": "*"}},
            "id": ident("webhook"),
            "name": "Demande client",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 2,
            "position": [0, 0],
            "webhookId": ident("webhook-id"),
        },
        {
            "parameters": {"jsCode": preparer},
            "id": ident("preparer"),
            "name": "Préparer la requête IA",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [220, 0],
        },
        {
            "parameters": {
                "conditions": {
                    "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                    "conditions": [
                        {
                            "id": ident("condition-vide"),
                            "leftValue": "={{ $json.vide }}",
                            "rightValue": "",
                            "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                        }
                    ],
                    "combinator": "and",
                },
                "options": {},
            },
            "id": ident("si-vide"),
            "name": "Demande vide ?",
            "type": "n8n-nodes-base.if",
            "typeVersion": 2.2,
            "position": [440, 0],
        },
        {
            "parameters": {"jsCode": vide},
            "id": ident("vide"),
            "name": "Erreur : demande vide",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [660, -160],
        },
        {
            "parameters": {
                "method": "POST",
                "url": OLLAMA,
                "sendBody": True,
                "specifyBody": "json",
                "jsonBody": "={{ JSON.stringify($json.requete) }}",
                "options": {"timeout": 300000},
            },
            "id": ident("ollama"),
            "name": "Ollama : lire la demande",
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.2,
            "position": [660, 80],
            "onError": "continueRegularOutput",
        },
        {
            "parameters": {"jsCode": calculer},
            "id": ident("calculer"),
            "name": "Calculer le devis",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [880, 80],
        },
        {
            "parameters": {"respondWith": "firstIncomingItem", "options": {}},
            "id": ident("repondre"),
            "name": "Brouillon à l'artisan",
            "type": "n8n-nodes-base.respondToWebhook",
            "typeVersion": 1.1,
            "position": [1100, 0],
        },
        {
            "parameters": {"httpMethod": "GET", "path": "jarvis-artisan", "responseMode": "responseNode", "options": {}},
            "id": ident("ecran"),
            "name": "Écran de démo",
            "type": "n8n-nodes-base.webhook",
            "typeVersion": 2,
            "position": [0, 320],
            "webhookId": ident("ecran-id"),
        },
        {
            "parameters": {
                "respondWith": "text",
                "responseBody": html,
                "options": {"responseHeaders": {"entries": [{"name": "Content-Type", "value": "text/html; charset=utf-8"}]}},
            },
            "id": ident("page"),
            "name": "Page HTML",
            "type": "n8n-nodes-base.respondToWebhook",
            "typeVersion": 1.1,
            "position": [220, 320],
        },
    ]
    liens = {
        "Demande client": {"main": [[{"node": "Préparer la requête IA", "type": "main", "index": 0}]]},
        "Préparer la requête IA": {"main": [[{"node": "Demande vide ?", "type": "main", "index": 0}]]},
        "Demande vide ?": {"main": [
            [{"node": "Erreur : demande vide", "type": "main", "index": 0}],
            [{"node": "Ollama : lire la demande", "type": "main", "index": 0}],
        ]},
        "Erreur : demande vide": {"main": [[{"node": "Brouillon à l'artisan", "type": "main", "index": 0}]]},
        "Ollama : lire la demande": {"main": [[{"node": "Calculer le devis", "type": "main", "index": 0}]]},
        "Calculer le devis": {"main": [[{"node": "Brouillon à l'artisan", "type": "main", "index": 0}]]},
        "Écran de démo": {"main": [[{"node": "Page HTML", "type": "main", "index": 0}]]},
    }
    return {
        "name": "Jarvis Artisan · module devis (démo)",
        "nodes": noeuds,
        "connections": liens,
        "settings": {"executionOrder": "v1"},
        "pinData": {},
        "meta": {"templateCredsSetupCompleted": True},
        "tags": [],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--modele", default="llama3.1")
    args = p.parse_args()
    sortie = RACINE / "n8n" / "jarvis-artisan-devis.json"
    sortie.write_text(json.dumps(construire(args.modele), ensure_ascii=False, indent=2) + "\n")
    print(f"Écrit : {sortie.relative_to(RACINE)} (modèle {args.modele})")


if __name__ == "__main__":
    main()
