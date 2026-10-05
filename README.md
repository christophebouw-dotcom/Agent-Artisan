# Agent Artisan · Jarvis Artisan, module devis

Démo · entreprise fictive, prix inventés. Aucune donnée de client réel.

Jarvis Artisan prépare les devis, les relances, les factures et les demandes d'avis d'un artisan. **L'artisan valide tout** : rien ne part chez le client tout seul. Ce dépôt contient le premier module, le **devis**, prêt à importer dans n8n. Fiche complète dans le cerveau : `wiki/agents/agent-jarvis-artisan.md` (dépôt Cerveau-Tof-).

## Ce que fait le module

```
Demande du client ──► Ollama lit la demande ──► Le code calcule le devis ──► Brouillon à l'artisan
 (webhook n8n)         (JSON : prestation,       (grille de prix de          (devis + réponse au client,
                        surface, options,         l'artisan, TVA,             rien n'est envoyé)
                        infos manquantes)         totaux)
```

- **L'IA ne donne jamais un prix.** Elle lit seulement la demande. Tous les montants viennent de `grille-prix/`.
- Si la surface manque, les lignes concernées restent « à chiffrer » et le devis n'a pas de total.
- Une demande hors grille (autre métier, démarchage) n'a pas de devis : l'artisan la traite à la main.
- La réponse au client est un gabarit fixe. Elle demande ce qui manque et dit qu'elle a été préparée avec un assistant IA (AI Act, article 50).

## Fichiers

| Fichier | Rôle |
| --- | --- |
| `n8n/jarvis-artisan-devis.json` | Le workflow à importer (généré, ne pas modifier à la main) |
| `grille-prix/plomberie-demo.json` | La grille de prix fictive d'un plombier |
| `prompt/prompt-systeme.md` | Le prompt de l'étape IA |
| `n8n/code/devis.js` | Le calcul du devis, sans IA |
| `demo/index.html` | L'écran de l'artisan pour la démo |
| `outils/construire_workflow.py` | Assemble le workflow à partir des fichiers ci-dessus |
| `tests/cas-tests.jsonl` | 10 demandes fictives et ce qui est attendu |
| `tests/evaluer.py` | Rejoue les 10 cas et vérifie chaque règle par du code |
| `tests/resultats-*.md` | Les rapports des essais |

## Installer sur ton Mac (zéro coût)

1. Ollama lancé, avec un modèle : `ollama pull llama3.1`.
2. Dans n8n (`localhost:5678`) : **Workflows › Import from file** › `n8n/jarvis-artisan-devis.json`.
3. Publie (active) le workflow.
4. Ouvre l'écran de démo : `http://localhost:5678/webhook/jarvis-artisan`.

Le workflow appelle Ollama à l'adresse `http://host.docker.internal:11434`, celle qui marche quand n8n tourne dans Docker sur le Mac. Pour changer de modèle : `python3 outils/construire_workflow.py --modele qwen2.5:7b`, puis réimporte.

## Tester

```bash
python3 tests/evaluer.py                                  # Ollama en local, llama3.1
python3 tests/evaluer.py --backend claude --modele haiku  # via Claude Code (consomme ton abonnement)
python3 tests/evaluer.py --backend n8n                    # le workflow importé, de bout en bout
```

| Date | Moteur | Score |
| --- | --- | --- |
| 2026-10-04 | Claude Haiku, prompt v1 | 10/10 |
| 2026-10-04 | Workflow n8n 2.41.6 de bout en bout, prompt v1 (Haiku derrière une fausse API Ollama) | 9/10 : « disponible demain matin » pas compris comme une date |
| 2026-10-04 | Claude Haiku, prompt v2 (règle des dates précisée) | 10/10 |
| 2026-10-04 | Workflow n8n de bout en bout, prompt v2 | 10/10 |
| à faire | Ollama llama3.1 sur le Mac | |

## Pour la démo de 5 minutes

Vidéo de vente (60 s) : `demo/video/jarvis-artisan-video-vente.mp4` (voix off + musique) et `demo/video/jarvis-artisan-video-vente-musique-seule.mp4`. Voix : Kokoro (voix française ff_siwis, en local). Musique : composée par programme (`demo/video/musique.py`), sans droits à payer. Les réponses de Jarvis ont été produites par le workflow n8n, puis rejouées pendant l'enregistrement pour caler l'image sur la voix. Fabrication : `demo/video/` (voix.py, musique.py, enregistrer.mjs, monter.py).


1. Ouvre l'écran de démo, colle la demande d'un faux client, clique sur **Recevoir la demande**.
2. Montre le résumé, l'urgence et la réponse préparée pour le client : l'artisan la relit, puis l'envoie lui-même.
3. Fais corriger une ligne à l'artisan (par exemple le prix du carrelage) : les totaux se recalculent.
4. **Valider et créer le PDF** ouvre la fenêtre d'impression, puis « Enregistrer en PDF ».

## Pas encore fait

- Entrée réelle : Gmail (gratuit) ou WhatsApp (API Meta payante, au nom du client).
- PDF généré par n8n et envoyé après validation, sans passer par l'impression du navigateur.
- Modules relances, factures et impayés, avis Google : fiches existantes dans le cerveau (`agent-relance-devis`, `agent-relance-impayes`, `agent-avis-google`).
- Mentions légales du devis (SIRET, assurance décennale, conditions de paiement) à faire valider par l'artisan pilote.
