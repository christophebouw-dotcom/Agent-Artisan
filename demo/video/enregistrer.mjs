// Clip de vente Jarvis Artisan : écrans de titre + appli réelle (réponses n8n rejouées), calés sur la voix off.
import { chromium } from "playwright-core";
import fs from "fs";

const ICI = process.cwd();
const exe = fs.readdirSync("/opt/pw-browsers").map((d) => `/opt/pw-browsers/${d}/chrome-linux/chrome`).find((f) => fs.existsSync(f));
const D = JSON.parse(fs.readFileSync(`${ICI}/tts/vo/durees.json`));
const REP = { sdb: fs.readFileSync(`${ICI}/reponses/sdb.json`, "utf8"), fuite: fs.readFileSync(`${ICI}/reponses/fuite.json`, "utf8") };
fs.rmSync(`${ICI}/clips`, { recursive: true, force: true });
fs.mkdirSync(`${ICI}/clips`);
const b = await chromium.launch({ executablePath: exe });
const sortie = { segments: [], voix: [] };

async function enregistrer(nom, fn) {
  const ctx = await b.newContext({ viewport: { width: 1280, height: 800 }, recordVideo: { dir: `${ICI}/clips/${nom}`, size: { width: 1280, height: 800 } } });
  const p = await ctx.newPage();
  const t0 = Date.now();
  await fn(p, () => (Date.now() - t0) / 1000);
  const v = p.video();
  await ctx.close();
  sortie.segments.push({ nom, video: await v.path() });
}

// --- Écrans de titre ---
for (const [nom, scene, voix, marge] of [["a", "A", "intro1", 1.4], ["b", "B", "intro2", 1.2]]) {
  await enregistrer(nom, async (p, t) => {
    await p.goto(`file://${ICI}/cartes.html?scene=${scene}`);
    sortie.voix.push({ segment: nom, cle: voix, debut: t() + 0.5 });
    await p.waitForTimeout((D[voix] + 0.5 + marge) * 1000);
  });
}

// --- L'appli ---
await enregistrer("app", async (p, t) => {
  let suivante = "sdb";
  await p.route("**/webhook/jarvis-artisan/devis", async (r) => {
    await new Promise((ok) => setTimeout(ok, 1100)); // le temps de lire la demande, raccourci pour la vidéo
    await r.fulfill({ status: 200, contentType: "application/json", body: REP[suivante] });
  });
  await p.goto(`file:///home/user/Agent-Artisan/demo/index.html`);
  await p.addStyleTag({ content: `
    header, main { zoom: 1.06; }
    body { padding-top: 66px; background: #0f172a; }
    #st { position: fixed; left: 0; right: 0; top: 0; height: 66px; display: flex; align-items: center; justify-content: center; z-index: 99; background: #0f172a; color: #f8fafc;
          font: 700 22px/1.35 "DejaVu Sans", system-ui, sans-serif; padding: 0 24px; border-bottom: 4px solid #f59e0b; transition: opacity .25s; }
    .encadre { outline: 3px solid #f59e0b !important; outline-offset: 4px; border-radius: 6px; transition: outline-color .3s; }
    header { padding-right: 16px; }` });
  await p.evaluate(() => { window.print = () => {}; document.getElementById("demande").value = ""; });
  const dire = async (cle, texte, extra = 0.6) => {
    await p.evaluate((x) => {
      let d = document.getElementById("st");
      if (!d) { d = document.createElement("div"); d.id = "st"; document.body.appendChild(d); }
      d.style.opacity = 0; setTimeout(() => { d.textContent = x; d.style.opacity = 1; }, 150);
    }, texte);
    sortie.voix.push({ segment: "app", cle, debut: t() + 0.2 });
    return (D[cle] + extra) * 1000;
  };
  const encadrer = (sel) => p.evaluate((s) => {
    document.querySelectorAll(".encadre").forEach((x) => x.classList.remove("encadre"));
    const el = s && document.querySelector(s);
    if (el) { el.classList.add("encadre"); el.scrollIntoView({ behavior: "smooth", block: "center" }); }
  }, sel);
  const attendre = (ms) => p.waitForTimeout(ms);

  // s1 : la demande
  await attendre(500);
  let ms = await dire("s1", "Un client vous écrit");
  await encadrer("#demande");
  const debut = Date.now();
  await p.click("#demande");
  await p.keyboard.type("Bonjour, je voudrais refaire ma salle de bain, 6 m², avec une douche à l'italienne. Voici deux photos. Chantier possible en janvier.", { delay: 22 });
  await attendre(Math.max(300, ms - (Date.now() - debut) - 1200));
  await p.click("#envoyer");
  await p.waitForSelector("#resultat:not(.cache)");
  // s2 : compris
  ms = await dire("s2", "En quelques secondes, Jarvis a compris la demande");
  await encadrer("#resume");
  await attendre(ms);
  // s3 : la réponse au client
  ms = await dire("s3", "Il prépare la réponse au client · vous la relisez et l'envoyez");
  await encadrer("#bloc-message");
  await attendre(ms);
  // s4 : le devis
  ms = await dire("s4", "Il chiffre le devis avec vos propres prix");
  await encadrer("#bloc-devis table");
  await attendre(ms);
  // s5 : la correction
  ms = await dire("s5", "Un prix à ajuster ? Tout se recalcule");
  const prix = '[data-champ="prix_unitaire_ht"][data-i="2"]';
  await encadrer(prix);
  await attendre(900);
  await p.click(prix, { clickCount: 3 });
  await p.keyboard.type("70", { delay: 200 });
  await attendre(300);
  await encadrer("tfoot");
  await attendre(Math.max(400, ms - 1800));
  // s6 : validation
  ms = await dire("s6", "Un clic : le devis est prêt en PDF · 2 minutes au lieu de 30 à 60", 0.8);
  await encadrer("#valider");
  await attendre(1000);
  await p.click("#valider");
  await attendre(400);
  await p.evaluate(() => {
    const t = document.createElement("div");
    t.textContent = "✓  Devis validé · PDF prêt";
    t.style.cssText = "position:fixed;left:50%;top:50%;transform:translate(-50%,-50%) scale(.9);background:#16a34a;color:#fff;font:800 34px system-ui,sans-serif;padding:26px 40px;border-radius:18px;box-shadow:0 20px 60px rgba(0,0,0,.3);opacity:0;transition:all .35s;z-index:98";
    document.body.appendChild(t);
    requestAnimationFrame(() => { t.style.opacity = 1; t.style.transform = "translate(-50%,-50%) scale(1)"; });
    setTimeout(() => { t.style.opacity = 0; }, 2600);
    setTimeout(() => t.remove(), 3100);
  });
  await attendre(Math.max(400, ms - 1400));
  // s7 : l'urgence
  suivante = "fuite";
  await p.evaluate(() => { window.scrollTo({ top: 0, behavior: "smooth" }); document.getElementById("vide").classList.remove("cache"); document.getElementById("resultat").classList.add("cache"); document.getElementById("demande").value = ""; });
  ms = await dire("s7", "Une urgence ? Jarvis vous prévient tout de suite", 0.9);
  await encadrer("#demande");
  const d2 = Date.now();
  await p.click("#demande");
  await p.keyboard.type("Il y a de l'eau qui coule sous mon évier, ça goutte encore. Au secours !", { delay: 16 });
  await p.click("#envoyer");
  await p.waitForSelector("#resultat:not(.cache)");
  await encadrer("#a-faire");
  await attendre(Math.max(1500, ms - (Date.now() - d2)));
});

// --- Écran de fin ---
await enregistrer("c", async (p, t) => {
  await p.goto(`file://${ICI}/cartes.html?scene=C`);
  sortie.voix.push({ segment: "c", cle: "outro", debut: t() + 0.4 });
  await p.waitForTimeout((D.outro + 0.4 + 2.6) * 1000);
});

await b.close();
fs.writeFileSync(`${ICI}/clip.json`, JSON.stringify(sortie, null, 1));
console.log(JSON.stringify(sortie.voix));
