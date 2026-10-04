// Jarvis Artisan, module devis : logique sans IA.
// L'IA ne fait que lire la demande (type de travaux, surface, options, infos manquantes).
// Tous les prix et tous les calculs viennent d'ici et de la grille de l'artisan, jamais du modèle.
// Ce fichier est copié dans les nœuds Code du workflow n8n par outils/construire_workflow.py,
// et testé tel quel par tests/evaluer.py (via Node).

const INFOS = ["adresse", "date_souhaitee", "budget", "surface", "photos", "precisions"];

const QUESTIONS = {
  adresse: "l'adresse du chantier",
  date_souhaitee: "la période souhaitée pour les travaux",
  budget: "le budget que vous envisagez",
  surface: "la surface de la pièce (en m²)",
  photos: "une ou deux photos de l'existant",
  precisions: "quelques précisions sur ce que vous souhaitez",
};

function schemaExtraction(grille) {
  const prestations = Object.keys(grille.prestations).concat(["hors_grille"]);
  const options = [];
  for (const p of Object.values(grille.prestations)) {
    for (const code of Object.keys(p.options || {})) if (!options.includes(code)) options.push(code);
  }
  return {
    type: "object",
    properties: {
      prestation: { type: "string", enum: prestations },
      surface_m2: { type: "number" },
      options: { type: "array", items: { type: "string", enum: options } },
      infos_manquantes: { type: "array", items: { type: "string", enum: INFOS } },
      urgence: { type: "string", enum: ["urgent", "normal"] },
      resume: { type: "string" },
      a_verifier: { type: "boolean" },
    },
    required: ["prestation", "surface_m2", "options", "infos_manquantes", "urgence", "resume", "a_verifier"],
  };
}

function listePrestations(grille) {
  const lignes = [];
  for (const [code, p] of Object.entries(grille.prestations)) {
    const opts = Object.entries(p.options || {}).map(([c, o]) => `${c} (${o.libelle})`);
    lignes.push(`- ${code} : ${p.libelle}` + (opts.length ? `. Options possibles : ${opts.join(" ; ")}` : ""));
  }
  lignes.push("- hors_grille : tout le reste (autre métier, travaux non listés, message qui n'est pas une demande de travaux)");
  return lignes.join("\n");
}

function promptSysteme(modele, grille) {
  return modele
    .replace("{{ENTREPRISE}}", grille.entreprise)
    .replace("{{METIER}}", grille.metier)
    .replace("{{PRESTATIONS}}", listePrestations(grille));
}

function arrondi(x) {
  return Math.round(x * 100) / 100;
}

function quantite(regle, surface) {
  if (regle.fixe !== undefined) return regle.fixe;
  if (regle.par === "surface") return surface > 0 ? arrondi(surface * (regle.coef || 1)) : null;
  return null;
}

function messageClient(infos, grille) {
  const demandes = infos.filter((i) => QUESTIONS[i]).map((i) => QUESTIONS[i]);
  const corps = demandes.length
    ? `Pour préparer votre devis, pourriez-vous m'indiquer ${demandes.length === 1 ? demandes[0] : demandes.slice(0, -1).join(", ") + " et " + demandes[demandes.length - 1]} ?`
    : "J'ai bien toutes les informations, je vous envoie votre devis très vite.";
  return (
    `Bonjour, merci pour votre demande. ${corps}\n` +
    `Bonne journée,\n[Prénom de l'artisan] – ${grille.entreprise}\n` +
    `(Message préparé avec l'aide d'un assistant IA et relu par l'artisan.)`
  );
}

function verifierExtraction(e, grille) {
  const erreurs = [];
  if (!e || typeof e !== "object") return ["sortie IA vide ou illisible"];
  const prestations = Object.keys(grille.prestations).concat(["hors_grille"]);
  if (!prestations.includes(e.prestation)) erreurs.push(`prestation inconnue : ${e.prestation}`);
  if (typeof e.surface_m2 !== "number" || e.surface_m2 < 0 || e.surface_m2 > 500) erreurs.push(`surface invalide : ${e.surface_m2}`);
  if (!Array.isArray(e.options)) erreurs.push("options absentes");
  if (!Array.isArray(e.infos_manquantes)) erreurs.push("infos_manquantes absentes");
  return erreurs;
}

function calculerDevis(e, grille) {
  const erreurs = verifierExtraction(e, grille);
  if (erreurs.length) {
    return { statut: "erreur_ia", erreurs, a_faire: "L'IA n'a pas su lire la demande : la traiter à la main." };
  }
  const infos = e.infos_manquantes.filter((i) => INFOS.includes(i));
  const p = grille.prestations[e.prestation];
  if (!p) {
    return {
      statut: "hors_grille",
      extraction: e,
      devis: null,
      message_client_brouillon: messageClient(infos.length ? infos : ["precisions"], grille),
      a_faire: "Demande hors grille de prix : à lire et chiffrer par l'artisan.",
    };
  }
  const surface = e.surface_m2 > 0 ? e.surface_m2 : 0;
  if (p.besoin_surface && !surface && !infos.includes("surface")) infos.push("surface");

  const lignes = [];
  for (const l of p.lignes) {
    const q = quantite(l.quantite, surface);
    lignes.push({ code: l.code, libelle: l.libelle, unite: l.unite, quantite: q, prix_unitaire_ht: l.prix_unitaire_ht, montant_ht: q === null ? null : arrondi(q * l.prix_unitaire_ht) });
  }
  const ignorees = [];
  for (const code of [...new Set(e.options)]) { // une option citée deux fois ne compte qu'une fois
    const o = (p.options || {})[code];
    if (!o) { ignorees.push(code); continue; }
    lignes.push({ code, libelle: o.libelle, unite: o.unite, quantite: 1, prix_unitaire_ht: o.prix_unitaire_ht, montant_ht: o.prix_unitaire_ht });
  }

  const complet = lignes.every((l) => l.montant_ht !== null);
  const totalHt = arrondi(lignes.reduce((s, l) => s + (l.montant_ht || 0), 0));
  const tva = arrondi(totalHt * grille.tva.taux);
  const aFaire = [];
  if (e.urgence === "urgent") aFaire.push("URGENT : rappeler le client aujourd'hui.");
  aFaire.push(complet ? "Relire le brouillon, corriger les lignes si besoin, puis valider." : "Devis incomplet : attendre la surface du client avant de chiffrer les lignes vides.");
  if (e.a_verifier) aFaire.push("L'IA a un doute sur sa lecture : relire la demande.");
  if (ignorees.length) aFaire.push(`Options citées hors grille (ignorées) : ${ignorees.join(", ")}.`);

  return {
    statut: complet ? "brouillon_a_valider" : "brouillon_incomplet",
    extraction: e,
    devis: {
      entreprise: grille.entreprise,
      prestation: p.libelle,
      lignes,
      // Pas de total tant qu'une ligne reste à chiffrer : un total partiel induirait le client en erreur.
      total_ht: complet ? totalHt : null,
      taux_tva: grille.tva.taux,
      tva: complet ? tva : null,
      total_ttc: complet ? arrondi(totalHt + tva) : null,
      complet,
      validite_jours: grille.validite_jours,
      mentions: "Brouillon à valider par l'artisan. Démo · entreprise fictive. Mentions légales du devis à compléter (SIRET, assurance décennale, conditions de paiement).",
    },
    message_client_brouillon: messageClient(infos, grille),
    a_faire: aFaire.join(" "),
  };
}

// @export-debut (retiré dans n8n)
if (typeof module !== "undefined") module.exports = { schemaExtraction, promptSysteme, calculerDevis, messageClient, INFOS };
// @export-fin
