#!/usr/bin/env python3
"""Générateur du site Annuaire Pro Luxembourg.

Aucune dépendance : Python 3 suffit.
  python3 build.py
Lit data/*.json et écrit le site statique dans docs/ (servi par GitHub Pages).
"""
import html
import json
import os
import re
import shutil
import unicodedata
from collections import defaultdict
from datetime import date

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs")

# ---------------------------------------------------------------- config
with open(os.path.join(ROOT, "data", "config.json"), encoding="utf-8") as f:
    CFG = json.load(f)

SITE_NAME = CFG["nom_site"]
SITE_URL = CFG["url_site"].rstrip("/")          # ex. https://annuaireprolux.eu
BASE_PATH = CFG["base_path"].rstrip("/")        # "" avec domaine perso, "/annuaireprolux" sinon
FORM_ACTION = CFG["formulaire_action"]


def esc(s):
    return html.escape(str(s or ""), quote=True)


def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def url(path):
    return f"{BASE_PATH}{path}"


# ---------------------------------------------------------------- données
with open(os.path.join(ROOT, "data", "categories.json"), encoding="utf-8") as f:
    CATEGORIES = json.load(f)  # {slug: libellé}
with open(os.path.join(ROOT, "data", "entreprises.json"), encoding="utf-8") as f:
    ENTREPRISES = json.load(f)

for e in ENTREPRISES:
    e["slug"] = slugify(f"{e['nom']}-{e['ville']}")
    e["ville_slug"] = slugify(e["ville"])
    e["premium"] = bool(e.get("premium"))
    if e["categorie"] not in CATEGORIES:
        raise SystemExit(f"Catégorie inconnue: {e['categorie']} ({e['nom']})")

# Premium d'abord, puis ordre alphabétique
ENTREPRISES.sort(key=lambda e: (not e["premium"], e["nom"].lower()))

PAR_CAT = defaultdict(list)
PAR_VILLE = defaultdict(list)
VILLES = {}
for e in ENTREPRISES:
    PAR_CAT[e["categorie"]].append(e)
    PAR_VILLE[e["ville_slug"]].append(e)
    VILLES[e["ville_slug"]] = e["ville"]


# ---------------------------------------------------------------- gabarits
def page(titre, description, chemin, corps, extra_head="", noindex=False):
    canon = f"{SITE_URL}{chemin}"
    robots = '<meta name="robots" content="noindex,follow">' if noindex else ""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(titre)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canon)}">
{robots}
<link rel="stylesheet" href="{url('/style.css')}">
{extra_head}
</head>
<body>
<header class="top">
  <div class="wrap">
    <a class="brand" href="{url('/')}">{esc(SITE_NAME)}</a>
    <nav>
      <a href="{url('/ajouter/')}">Ajouter votre entreprise</a>
      <a href="{url('/visibilite/')}">Visibilité</a>
    </nav>
  </div>
</header>
<main class="wrap">
{corps}
</main>
<footer class="foot">
  <div class="wrap">
    <a href="{url('/ajouter/')}">Ajouter une entreprise</a> ·
    <a href="{url('/visibilite/')}">Boostez votre visibilité</a> ·
    <a href="{url('/mentions-legales/')}">Mentions légales</a> ·
    <a href="{url('/confidentialite/')}">Confidentialité</a>
    <p>© {date.today().year} {esc(SITE_NAME)}</p>
  </div>
</footer>
</body>
</html>
"""


def carte(e):
    lignes = [f'<h3><a href="{url("/entreprise/" + e["slug"] + "/")}">{esc(e["nom"])}</a>'
              + (' <span class="badge">Premium</span>' if e["premium"] else "") + "</h3>"]
    lignes.append(f'<p class="meta">{esc(CATEGORIES[e["categorie"]])} · {esc(e["ville"])}</p>')
    if e.get("description"):
        lignes.append(f'<p>{esc(e["description"])}</p>')
    return '<li class="card">' + "".join(lignes) + "</li>"


def liste(entreprises):
    if not entreprises:
        return "<p>Aucune entreprise pour le moment.</p>"
    return '<ul class="list">' + "".join(carte(e) for e in entreprises) + "</ul>"


def ecrire(chemin, contenu):
    dest = os.path.join(OUT, chemin.strip("/"), "index.html") if chemin != "/" else os.path.join(OUT, "index.html")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(contenu)


# ---------------------------------------------------------------- pages
def build():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    urls = ["/"]

    # CSS + recherche
    shutil.copy(os.path.join(ROOT, "assets", "style.css"), os.path.join(OUT, "style.css"))
    shutil.copy(os.path.join(ROOT, "assets", "search.js"), os.path.join(OUT, "search.js"))
    if CFG.get("domaine_perso"):
        with open(os.path.join(OUT, "CNAME"), "w") as f:
            f.write(CFG["domaine_perso"] + "\n")
    open(os.path.join(OUT, ".nojekyll"), "w").close()

    index = [
        {
            "n": e["nom"], "c": CATEGORIES[e["categorie"]], "v": e["ville"],
            "w": bool(e.get("site")), "m": bool(e.get("email")),
            "p": e["premium"], "u": url(f"/entreprise/{e['slug']}/"),
        }
        for e in ENTREPRISES
    ]
    with open(os.path.join(OUT, "search.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)

    # Accueil
    cats_pop = sorted(PAR_CAT, key=lambda c: -len(PAR_CAT[c]))[:6]
    raccourcis = " ".join(
        f'<a class="chip" href="{url("/categorie/" + c + "/")}">{esc(CATEGORIES[c])}</a>' for c in cats_pop
    )
    par_cat = "".join(
        f'<li><a href="{url("/categorie/" + c + "/")}">{esc(CATEGORIES[c])}</a> <span>({len(PAR_CAT[c])})</span></li>'
        for c in sorted(PAR_CAT, key=lambda c: CATEGORIES[c])
    )
    par_ville = "".join(
        f'<li><a href="{url("/ville/" + v + "/")}">{esc(VILLES[v])}</a> <span>({len(PAR_VILLE[v])})</span></li>'
        for v in sorted(PAR_VILLE, key=lambda v: VILLES[v])
    )
    corps = f"""
<section class="hero">
  <h1>L'annuaire professionnel du Luxembourg</h1>
  <input id="q" type="search" placeholder="Rechercher une entreprise, un métier, une ville…" autocomplete="off">
  <div class="filters">
    <label><input id="f-web" type="checkbox"> Avec site web</label>
    <label><input id="f-mail" type="checkbox"> Avec e-mail</label>
  </div>
  <p class="chips">{raccourcis}</p>
  <ul id="results" class="list"></ul>
</section>
<section class="cols">
  <div><h2>Parcourir par catégorie</h2><ul class="plain">{par_cat}</ul></div>
  <div><h2>Parcourir par ville</h2><ul class="plain">{par_ville}</ul></div>
</section>
<script>window.SITE_SEARCH = "{url('/search.json')}";</script>
<script src="{url('/search.js')}" defer></script>
"""
    ecrire("/", page(f"{SITE_NAME} – L'annuaire professionnel du Luxembourg",
                     "Trouvez une entreprise au Luxembourg par métier ou par ville : coordonnées, site web et e-mail.",
                     "/", corps))

    # Catégories
    for c, items in PAR_CAT.items():
        ch = f"/categorie/{c}/"
        urls.append(ch)
        corps = f"<h1>{esc(CATEGORIES[c])} au Luxembourg</h1>{liste(items)}"
        ecrire(ch, page(f"{CATEGORIES[c]} au Luxembourg – {SITE_NAME}",
                        f"Annuaire des entreprises : {CATEGORIES[c].lower()} au Luxembourg. Coordonnées et site web.",
                        ch, corps))

    # Villes
    for v, items in PAR_VILLE.items():
        ch = f"/ville/{v}/"
        urls.append(ch)
        corps = f"<h1>Entreprises à {esc(VILLES[v])}</h1>{liste(items)}"
        ecrire(ch, page(f"Entreprises à {VILLES[v]} – {SITE_NAME}",
                        f"Annuaire des entreprises et professionnels à {VILLES[v]} (Luxembourg).",
                        ch, corps))

    # Fiches
    for e in ENTREPRISES:
        ch = f"/entreprise/{e['slug']}/"
        urls.append(ch)
        rel = "sponsored noopener" if e["premium"] else "nofollow noopener"
        lignes = []
        adr = ", ".join(x for x in [e.get("adresse"), f"{e.get('code_postal', '')} {e['ville']}".strip()] if x)
        lignes.append(f"<dt>Adresse</dt><dd>{esc(adr)}</dd>")
        if e.get("telephone"):
            lignes.append(f'<dt>Téléphone</dt><dd><a href="tel:{esc(re.sub(r"[^+0-9]", "", e["telephone"]))}">{esc(e["telephone"])}</a></dd>')
        if e.get("email"):
            lignes.append(f'<dt>E-mail</dt><dd><a href="mailto:{esc(e["email"])}">{esc(e["email"])}</a></dd>')
        if e.get("site"):
            lignes.append(f'<dt>Site web</dt><dd><a href="{esc(e["site"])}" rel="{rel}" target="_blank">{esc(e["site"])}</a></dd>')
        ld = {
            "@context": "https://schema.org", "@type": "LocalBusiness", "name": e["nom"],
            "address": {"@type": "PostalAddress", "streetAddress": e.get("adresse", ""),
                        "postalCode": e.get("code_postal", ""), "addressLocality": e["ville"],
                        "addressCountry": "LU"},
        }
        if e.get("telephone"):
            ld["telephone"] = e["telephone"]
        if e.get("site"):
            ld["url"] = e["site"]
        extra = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>'
        corps = f"""
<p class="crumbs"><a href="{url('/')}">Accueil</a> › <a href="{url('/categorie/' + e['categorie'] + '/')}">{esc(CATEGORIES[e['categorie']])}</a> › <a href="{url('/ville/' + e['ville_slug'] + '/')}">{esc(e['ville'])}</a></p>
<h1>{esc(e['nom'])}{' <span class="badge">Premium</span>' if e['premium'] else ''}</h1>
<p class="meta">{esc(CATEGORIES[e['categorie']])} · {esc(e['ville'])}</p>
<p>{esc(e.get('description', ''))}</p>
<dl class="infos">{''.join(lignes)}</dl>
<p class="small">Une information est incorrecte ? <a href="{url('/ajouter/')}">Écrivez-nous</a> pour la corriger ou la supprimer.</p>
"""
        ecrire(ch, page(f"{e['nom']} – {CATEGORIES[e['categorie']]} à {e['ville']}",
                        f"{e['nom']} : {CATEGORIES[e['categorie']].lower()} à {e['ville']}. Adresse, téléphone et site web.",
                        ch, corps, extra_head=extra))

    # Ajouter
    corps = f"""
<h1>Ajouter votre entreprise</h1>
<p>L'inscription est <strong>gratuite</strong>. Votre fiche est vérifiée puis publiée sous quelques jours.</p>
<form action="{esc(FORM_ACTION)}" method="POST" class="form">
  <label>Nom de l'entreprise <input name="nom" required></label>
  <label>Catégorie <input name="categorie" required placeholder="ex. Plombiers"></label>
  <label>Adresse <input name="adresse" required></label>
  <label>Code postal et ville <input name="ville" required></label>
  <label>Téléphone <input name="telephone"></label>
  <label>E-mail <input name="email" type="email" required></label>
  <label>Site web <input name="site" type="url" placeholder="https://"></label>
  <label>Description (2 phrases) <textarea name="description" rows="3"></textarea></label>
  <button type="submit">Envoyer</button>
</form>
"""
    urls.append("/ajouter/")
    ecrire("/ajouter/", page(f"Ajouter votre entreprise – {SITE_NAME}",
                             "Inscrivez gratuitement votre entreprise dans l'annuaire professionnel du Luxembourg.",
                             "/ajouter/", corps))

    # Visibilité (offre payante) — tarifs à compléter dans data/config.json
    offres = "".join(
        f'<li class="card"><h3>{esc(o["nom"])} — {esc(o["prix"])}</h3><p>{esc(o["detail"])}</p>'
        + (f'<p><a class="btn" href="{esc(o["lien_paiement"])}">Commander</a></p>' if o.get("lien_paiement") else "")
        + "</li>"
        for o in CFG["offres"]
    )
    corps = f"""
<h1>Boostez votre visibilité</h1>
<p>Les liens des fiches Premium et des articles sponsorisés portent l'attribut <code>rel="sponsored"</code>,
conformément aux recommandations de Google.</p>
<ul class="list">{offres}</ul>
"""
    urls.append("/visibilite/")
    ecrire("/visibilite/", page(f"Boostez votre visibilité – {SITE_NAME}",
                                "Fiche Premium et article sponsorisé pour gagner en visibilité au Luxembourg.",
                                "/visibilite/", corps))

    # Pages légales (à compléter avant lancement)
    legal = CFG["legal"]
    corps = f"""
<h1>Mentions légales</h1>
<p>Éditeur du site : {esc(legal['editeur'])}<br>Adresse : {esc(legal['adresse'])}<br>Contact : {esc(legal['contact'])}</p>
<p>Hébergement : GitHub Pages (GitHub, Inc.).</p>
"""
    ecrire("/mentions-legales/", page(f"Mentions légales – {SITE_NAME}", "Mentions légales.", "/mentions-legales/", corps, noindex=True))
    corps = f"""
<h1>Politique de confidentialité</h1>
<p>Ce site publie des informations professionnelles (nom, adresse, téléphone, e-mail, site web) à des fins d'annuaire.</p>
<p>Pour demander la correction ou la suppression d'une fiche, écrivez à {esc(legal['contact'])}. La demande est traitée sous quelques jours.</p>
<p>Le site n'utilise pas de cookies de suivi.</p>
"""
    ecrire("/confidentialite/", page(f"Confidentialité – {SITE_NAME}", "Politique de confidentialité.", "/confidentialite/", corps, noindex=True))

    # sitemap + robots
    today = date.today().isoformat()
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f"<url><loc>{SITE_URL}{u}</loc><lastmod>{today}</lastmod></url>" for u in urls]
    sm.append("</urlset>")
    with open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(sm))
    with open(os.path.join(OUT, "robots.txt"), "w") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")

    print(f"OK : {len(ENTREPRISES)} fiches, {len(PAR_CAT)} catégories, {len(PAR_VILLE)} villes, {len(urls)} URLs.")


if __name__ == "__main__":
    build()
