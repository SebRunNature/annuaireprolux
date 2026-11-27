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
from urllib.parse import quote as urlquote
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
    GROUPES = json.load(f)  # {slug: {"nom": ..., "metiers": {slug: libellé}}}
with open(os.path.join(ROOT, "data", "entreprises.json"), encoding="utf-8") as f:
    ENTREPRISES = json.load(f)

SEUIL = int(CFG.get("seuil_pages", 3))  # nb min. de fiches pour créer une page métier / commune

for e in ENTREPRISES:
    g, m = e["groupe"], e["metier"]
    if g not in GROUPES or m not in GROUPES[g]["metiers"]:
        raise SystemExit(f"Groupe/métier inconnu: {g}/{m} ({e['nom']})")
    e["groupe_nom"] = GROUPES[g]["nom"]
    e["metier_nom"] = GROUPES[g]["metiers"][m]
    e["slug"] = slugify(f"{e['nom']}-{e['ville']}")
    e["ville_slug"] = slugify(e["ville"])
    e["premium"] = bool(e.get("premium"))

_vus = {}
for e in ENTREPRISES:  # slugs uniques : un même nom dans une même commune reçoit l'adresse en suffixe
    if e["slug"] in _vus:
        e["slug"] = slugify(f"{e['nom']}-{e.get('adresse') or ''}-{e['ville']}")
        if e["slug"] in _vus:
            e["slug"] += f"-{len(_vus)}"
    _vus[e["slug"]] = True

SEUIL_INDEX = int(CFG.get("seuil_index", 3))  # nb d'informations pour qu'une fiche soit indexée par Google


def est_indexable(e):
    """Une fiche gratuite n'est indexée que si elle est assez complète (anti-contenu pauvre)."""
    if e.get("index") is not None:  # forçage manuel dans les données
        return bool(e["index"])
    if e["premium"]:
        return True
    score = sum(1 for k in ("telephone", "email", "site", "horaires") if e.get(k))
    score += 1 if len(e.get("description", "")) > 60 else 0
    return score >= SEUIL_INDEX


for e in ENTREPRISES:
    e["indexable"] = est_indexable(e)

# Premium d'abord, puis ordre alphabétique
ENTREPRISES.sort(key=lambda e: (not e["premium"], e["nom"].lower()))

PAR_GROUPE = defaultdict(list)
PAR_METIER = defaultdict(list)
PAR_VILLE = defaultdict(list)
VILLES = {}
for e in ENTREPRISES:
    PAR_GROUPE[e["groupe"]].append(e)
    PAR_METIER[(e["groupe"], e["metier"])].append(e)
    PAR_VILLE[e["ville_slug"]].append(e)
    VILLES[e["ville_slug"]] = e["ville"]

PAGES_VILLE = {v for v, l in PAR_VILLE.items() if len(l) >= SEUIL}
PAGES_METIER = {k for k, l in PAR_METIER.items() if len(l) >= SEUIL}


# ---------------------------------------------------------------- blog
def md_html(texte, rel):
    """Mini-Markdown : ## titres, - listes, **gras**, [texte](url). Les liens externes reçoivent `rel`."""
    def inline(t):
        t = esc(t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)

        def lien(m):
            href = html.unescape(m.group(2))
            if href.startswith(("http://", "https://")):
                return f'<a href="{esc(href)}" rel="{rel}" target="_blank">{m.group(1)}</a>'
            return f'<a href="{esc(href)}">{m.group(1)}</a>'
        return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lien, t)

    sortie, liste_ouverte = [], False
    for bloc in re.split(r"\n\s*\n", texte.strip()):
        lignes = bloc.strip().splitlines()
        if all(l.startswith("- ") for l in lignes):
            sortie.append("<ul>" + "".join(f"<li>{inline(l[2:])}</li>" for l in lignes) + "</ul>")
        elif bloc.startswith("## "):
            sortie.append(f"<h2>{inline(bloc[3:].strip())}</h2>")
        else:
            sortie.append(f"<p>{inline(' '.join(l.strip() for l in lignes))}</p>")
    return "\n".join(sortie)


def charger_articles():
    dossier = os.path.join(ROOT, "data", "articles")
    res = []
    for nom in sorted(os.listdir(dossier)) if os.path.isdir(dossier) else []:
        if not nom.endswith(".md") or nom.startswith("_"):
            continue
        brut = open(os.path.join(dossier, nom), encoding="utf-8").read()
        entete, _, corps = brut.partition("\n---\n")
        meta = {}
        for l in entete.splitlines():
            if ":" in l:
                k, v = l.split(":", 1)
                meta[k.strip()] = v.strip()
        for k in ("titre", "date", "resume"):
            if not meta.get(k):
                raise SystemExit(f"Article {nom} : champ « {k} » manquant")
        meta["slug"] = meta.get("slug") or slugify(nom[:-3])
        meta["sponsorise"] = meta.get("sponsorise", "oui").lower() in ("oui", "true", "1")
        meta["corps"] = corps
        res.append(meta)
    return sorted(res, key=lambda a: a["date"], reverse=True)


ARTICLES = charger_articles()


def date_fr(iso):
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
            "septembre", "octobre", "novembre", "décembre"]
    a, m, j = iso.split("-")
    return f"{int(j)} {mois[int(m) - 1]} {a}"


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
      <a href="{url('/blog/')}">Blog</a>
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
    <a href="{url('/blog/')}">Blog</a> ·
    <a href="{url('/mentions-legales/')}">Mentions légales</a> ·
    <a href="{url('/confidentialite/')}">Confidentialité</a>
    <p>© {date.today().year} {esc(SITE_NAME)} · Édité par {esc(CFG["legal"]["editeur"])}</p>
  </div>
</footer>
</body>
</html>
"""


def logo_html(e, classe):
    """Logo d'une fiche Premium : fichier dans assets/logos/, affiché dans une boîte fixe (toute taille acceptée)."""
    if not (e["premium"] and e.get("logo")):
        return ""
    if not os.path.isfile(os.path.join(ROOT, "assets", "logos", e["logo"])):
        raise SystemExit(f"Logo introuvable : assets/logos/{e['logo']} ({e['nom']})")
    return (f'<span class="{classe}"><img src="{url("/logos/" + e["logo"])}" '
            f'alt="Logo de {esc(e["nom"])}" loading="lazy"></span>')


def description_html(e, rel):
    """Description de fiche ; pour une fiche Premium, l'ancre (phrase présente dans le texte) devient un lien vers le site."""
    texte = esc(e.get("description", ""))
    if e["premium"]:
        nb = len(e.get("description", "").split())
        if not 100 <= nb <= 115:
            print(f"ATTENTION : description Premium de {e['nom']} = {nb} mots (cible : 100 à 115)")
        ancre = e.get("ancre", "")
        if ancre and e.get("site"):
            if esc(ancre) not in texte:
                raise SystemExit(f"L'ancre « {ancre} » doit figurer dans la description de {e['nom']}")
            texte = texte.replace(esc(ancre), f'<a href="{esc(e["site"])}" rel="{rel}" target="_blank">{esc(ancre)}</a>', 1)
    return texte


def carte(e):
    lignes = [f'<h3>{logo_html(e, "logo-mini")}<a href="{url("/entreprise/" + e["slug"] + "/")}">{esc(e["nom"])}</a>'
              + (' <span class="badge">Premium</span>' if e["premium"] else "") + "</h3>"]
    lignes.append(f'<p class="meta">{esc(e["groupe_nom"])} · {esc(e["metier_nom"])} · {esc(e["ville"])}</p>')
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
    logo_src = os.path.join(ROOT, "assets", "logos")
    if os.path.isdir(logo_src):
        shutil.copytree(logo_src, os.path.join(OUT, "logos"))
    bann_src = os.path.join(ROOT, "assets", "bannieres")
    if os.path.isdir(bann_src):
        shutil.copytree(bann_src, os.path.join(OUT, "bannieres"))
    if CFG.get("domaine_perso"):
        with open(os.path.join(OUT, "CNAME"), "w") as f:
            f.write(CFG["domaine_perso"] + "\n")
    open(os.path.join(OUT, ".nojekyll"), "w").close()

    index = [
        {
            "n": e["nom"], "c": f"{e['groupe_nom']} · {e['metier_nom']}", "v": e["ville"],
            "w": bool(e.get("site")), "m": bool(e.get("email")), "t": bool(e.get("telephone")),
            "p": e["premium"], "u": url(f"/entreprise/{e['slug']}/"),
        }
        for e in ENTREPRISES
    ]
    with open(os.path.join(OUT, "search.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)

    def lien_ville(v, avec_nb=True):
        nb = f' <span>({len(PAR_VILLE[v])})</span>' if avec_nb else ""
        if v in PAGES_VILLE:
            return f'<li><a href="{url("/ville/" + v + "/")}">{esc(VILLES[v])}</a>{nb}</li>'
        return f"<li>{esc(VILLES[v])}{nb}</li>"

    # Accueil
    pop = [g for g in sorted(PAR_GROUPE, key=lambda g: -len(PAR_GROUPE[g]))][:6]
    raccourcis = " ".join(
        f'<a class="chip" href="{url("/categorie/" + g + "/")}">{esc(GROUPES[g]["nom"])}</a>' for g in pop
    )
    tuiles = "".join(
        f'<li><a href="{url("/categorie/" + g + "/")}">{esc(GROUPES[g]["nom"])}</a> <span>({len(PAR_GROUPE.get(g, []))})</span></li>'
        for g in GROUPES
    )
    top_villes = sorted(PAR_VILLE, key=lambda v: (-len(PAR_VILLE[v]), VILLES[v]))[:10]
    par_ville = "".join(lien_ville(v) for v in sorted(top_villes, key=lambda v: VILLES[v]))
    corps = f"""
<section class="hero">
  <h1>L'annuaire des professionnels au Luxembourg</h1>
  <p class="band"><span><strong>100 % gratuit</strong> pour inscrire votre entreprise</span><span>Audience : <strong>Luxembourg · France · Belgique</strong></span></p>
  <div class="searchbox">
    <svg class="loupe" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
    <input id="q" type="search" placeholder="Je cherche… un plombier, un restaurant, une ville" aria-label="Rechercher une entreprise, un métier ou une ville" autocomplete="off">
  </div>
  <div class="filters">
    <label><input id="f-web" type="checkbox"> Avec site web</label>
    <label><input id="f-mail" type="checkbox"> Avec e-mail</label>
    <label><input id="f-tel" type="checkbox"> Avec téléphone</label>
  </div>
  <p class="chips">{raccourcis}</p>
  <ul id="results" class="list"></ul>
</section>
<section class="cols">
  <div><h2>Parcourir par catégorie</h2><ul class="tiles">{tuiles}</ul></div>
  <div><h2>Parcourir par commune</h2><ul class="plain">{par_ville}</ul>
  <p><a href="{url('/communes/')}">Toutes les communes →</a></p></div>
</section>
<section class="about">
  <h2>L'annuaire des entreprises et des professionnels au Luxembourg</h2>
  <p>{esc(SITE_NAME)} est un annuaire gratuit qui permet de trouver rapidement une entreprise, un artisan ou un prestataire de services au Luxembourg. Chaque fiche rassemble les informations utiles : adresse, numéro de téléphone, adresse e-mail et site web.</p>
  <p>Utilisez la barre de recherche ou parcourez les catégories : <a href="{url('/categorie/sante/')}">santé et bien-être</a>, <a href="{url('/categorie/batiment/')}">bâtiment et artisans</a> (plombiers, électriciens, chauffagistes), <a href="{url('/categorie/restauration/')}">restauration et hôtellerie</a>, <a href="{url('/categorie/droit-finance/')}">droit, comptabilité et finance</a> (avocats, comptables, fiduciaires), <a href="{url('/categorie/immobilier/')}">immobilier</a>, <a href="{url('/categorie/informatique-web/')}">informatique et web</a>, <a href="{url('/categorie/auto-transport/')}">auto et transport</a> et bien d'autres. Vous pouvez aussi filtrer par commune, ou ne garder que les entreprises qui ont un site web, un e-mail ou un téléphone.</p>
  <p>Vous dirigez une entreprise au Luxembourg ? <a href="{url('/ajouter/')}">L'inscription est 100 % gratuite</a>. Pour gagner en visibilité auprès des clients du Luxembourg, de la France et de la Belgique, découvrez la <a href="{url('/visibilite/')}">fiche Premium et les articles sponsorisés</a>.</p>
</section>
<script>window.SITE_SEARCH = "{url('/search.json')}";</script>
<script src="{url('/search.js')}" defer></script>
"""
    ecrire("/", page(f"{SITE_NAME} – L'annuaire des professionnels au Luxembourg",
                     "Trouvez une entreprise au Luxembourg par métier ou par commune : coordonnées, site web et e-mail.",
                     "/", corps))

    # Groupes (12 catégories principales)
    for g, info in GROUPES.items():
        ch = f"/categorie/{g}/"
        items = PAR_GROUPE.get(g, [])
        vide = not items
        if not vide:
            urls.append(ch)
        chips = "".join(
            f'<a class="chip" href="{url("/categorie/" + g + "/" + m + "/")}">{esc(lib)} ({len(PAR_METIER[(g, m)])})</a>'
            for m, lib in info["metiers"].items() if (g, m) in PAGES_METIER
        )
        if vide:
            liste_html = f'<p>Les premières entreprises arrivent bientôt. <a href="{url("/ajouter/")}">Ajoutez la vôtre gratuitement.</a></p>'
        else:
            liste_html = liste(items)
        corps = f'<h1>{esc(info["nom"])} au Luxembourg</h1>' + (f'<p class="chips">{chips}</p>' if chips else "") + liste_html
        ecrire(ch, page(f"{info['nom']} au Luxembourg – {SITE_NAME}",
                        f"Annuaire des entreprises : {info['nom'].lower()} au Luxembourg. Coordonnées et site web.",
                        ch, corps, noindex=vide))

    # Métiers (seulement à partir de SEUIL fiches)
    for (g, m) in PAGES_METIER:
        ch = f"/categorie/{g}/{m}/"
        urls.append(ch)
        lib = GROUPES[g]["metiers"][m]
        corps = (f'<p class="crumbs"><a href="{url("/")}">Accueil</a> › <a href="{url("/categorie/" + g + "/")}">{esc(GROUPES[g]["nom"])}</a></p>'
                 f"<h1>{esc(lib)} au Luxembourg</h1>{liste(PAR_METIER[(g, m)])}")
        ecrire(ch, page(f"{lib} au Luxembourg – {SITE_NAME}",
                        f"Annuaire : {lib.lower()} au Luxembourg. Coordonnées, téléphone et site web.",
                        ch, corps))

    # Communes (seulement à partir de SEUIL fiches)
    for v in PAGES_VILLE:
        ch = f"/ville/{v}/"
        urls.append(ch)
        corps = f"<h1>Entreprises à {esc(VILLES[v])}</h1>{liste(PAR_VILLE[v])}"
        ecrire(ch, page(f"Entreprises à {VILLES[v]} – {SITE_NAME}",
                        f"Annuaire des entreprises et professionnels à {VILLES[v]} (Luxembourg).",
                        ch, corps))

    # Liste de toutes les communes
    toutes = "".join(lien_ville(v) for v in sorted(PAR_VILLE, key=lambda v: VILLES[v]))
    urls.append("/communes/")
    ecrire("/communes/", page(f"Toutes les communes – {SITE_NAME}",
                              "Liste des communes du Luxembourg ayant des entreprises référencées.",
                              "/communes/", f'<h1>Toutes les communes</h1><ul class="plain">{toutes}</ul>'))

    # Fiches
    for e in ENTREPRISES:
        ch = f"/entreprise/{e['slug']}/"
        if e["indexable"]:
            urls.append(ch)
        rel = "sponsored noopener" if e["premium"] else "nofollow noopener"
        lignes = []
        adr = ", ".join(x for x in [e.get("adresse"), f"{e.get('code_postal', '')} {e['ville']}".strip()] if x)
        itin = ""
        if e.get("adresse"):
            q = urlquote(f"{adr}, Luxembourg")
            itin = f' · <a href="https://www.google.com/maps/search/?api=1&query={q}" rel="nofollow noopener" target="_blank">Itinéraire</a>'
        lignes.append(f"<dt>Adresse</dt><dd>{esc(adr)}{itin}</dd>")
        if e.get("horaires"):
            lignes.append(f"<dt>Horaires</dt><dd>{esc(e['horaires'])}</dd>")
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
        ville_crumb = (f'<a href="{url("/ville/" + e["ville_slug"] + "/")}">{esc(e["ville"])}</a>'
                       if e["ville_slug"] in PAGES_VILLE else esc(e["ville"]))
        banniere = ""
        if e["premium"] and e.get("banniere"):
            if not os.path.isfile(os.path.join(ROOT, "assets", "bannieres", e["banniere"])):
                raise SystemExit(f"Bannière introuvable : assets/bannieres/{e['banniere']} ({e['nom']})")
            alt = e.get("banniere_alt") or f"{e['nom']} – {e['metier_nom']} à {e['ville']}"
            banniere = f'<img class="banniere" src="{url("/bannieres/" + e["banniere"])}" alt="{esc(alt)}" width="1200" height="400">'
        corps = f"""
<p class="crumbs"><a href="{url('/')}">Accueil</a> › <a href="{url('/categorie/' + e['groupe'] + '/')}">{esc(e['groupe_nom'])}</a> › {ville_crumb}</p>
<div class="entete">{logo_html(e, "logo-box")}<div>
<h1>{esc(e['nom'])}{' <span class="badge">Premium</span>' if e['premium'] else ''}</h1>
<p class="meta">{esc(e['metier_nom'])} · {esc(e['ville'])}</p>
</div></div>
<p>{description_html(e, rel)}</p>
{banniere}
<dl class="infos">{''.join(lignes)}</dl>
<p class="small">Une information est incorrecte ? <a href="{url('/ajouter/')}">Écrivez-nous</a> pour la corriger ou la supprimer.</p>
"""
        ecrire(ch, page(f"{e['nom']} – {e['metier_nom']} à {e['ville']}",
                        f"{e['nom']} : {e['metier_nom'].lower()} à {e['ville']}. Adresse, téléphone et site web.",
                        ch, corps, extra_head=extra, noindex=not e["indexable"]))

    # Ajouter
    options_cat = '<option value="">Choisissez une catégorie…</option>' + "".join(
        f'<optgroup label="{esc(info["nom"])}">'
        + "".join(f'<option value="{esc(info["nom"])} – {esc(lib)}">{esc(lib)}</option>' for lib in info["metiers"].values())
        + "</optgroup>"
        for info in GROUPES.values()
    ) + '<optgroup label="Autre"><option value="Autre (précisé dans la description)">Autre (précisez dans la description)</option></optgroup>'
    corps = f"""
<h1>Ajouter votre entreprise</h1>
<p>L'inscription est <strong>gratuite</strong>. Votre fiche est vérifiée puis publiée sous quelques jours.</p>
<form action="{esc(FORM_ACTION)}" method="POST" class="form">
  <label>Nom de l'entreprise <input name="nom" required></label>
  <label>Catégorie <select name="categorie" required>{options_cat}</select></label>
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
                             "Inscrivez gratuitement votre entreprise dans l'annuaire des professionnels au Luxembourg.",
                             "/ajouter/", corps))

    # Visibilité (offres payantes) — tarifs et contenu dans data/config.json
    from urllib.parse import quote
    contact = CFG["legal"]["contact"]

    def cta(nom):
        sujet = quote(f"Demande de devis - {nom}")
        return f'<a class="btn" href="mailto:{esc(contact)}?subject={sujet}">Demander un devis</a>'

    offres = "".join(
        f'<li class="card"><h3>{esc(o["nom"])}</h3>'
        f'<p class="meta">{esc(o["public"])} · {esc(o["prix"])}</p>'
        f'<p>{esc(o["detail"])}</p>'
        '<ul class="check">' + "".join(f"<li>{esc(x)}</li>" for x in o["inclus"]) + "</ul>"
        f"<p>{cta(o['nom'])}</p></li>"
        for o in CFG["offres"]
    )
    corps = f"""
<h1>Boostez votre visibilité au Luxembourg</h1>
<p class="lead">Une fiche Premium ou un article sponsorisé vous rend plus visible auprès des internautes qui cherchent un professionnel au Luxembourg, en France et en Belgique. Nos offres s'adressent aux entreprises, aux agences SEO, aux freelances et aux solopreneurs.</p>

<h2>Ce que vous obtenez</h2>
<ul class="check">
  <li><strong>De la visibilité locale :</strong> votre entreprise apparaît en tête de sa catégorie et de sa commune.</li>
  <li><strong>Des visiteurs qualifiés :</strong> des internautes qui cherchent justement votre métier et peuvent cliquer vers votre site.</li>
  <li><strong>Une citation d'entreprise :</strong> vos coordonnées (nom, adresse, téléphone) publiées de façon cohérente sur un annuaire luxembourgeois.</li>
  <li><strong>Votre logo :</strong> avec la fiche Premium, votre logo s'affiche en tête de votre fiche et dans les listes, quelle que soit sa taille ou sa forme.</li>
  <li><strong>Un lien dans le texte de votre fiche :</strong> la description Premium (100 à 115 mots) contient un lien vers votre site avec l'intitulé que vous choisissez, en plus de l'adresse complète de votre site. Les deux liens sont balisés <code>rel="sponsored"</code>.</li>
  <li><strong>Une mention de marque :</strong> votre nom associé à un site spécialisé sur les professionnels du Luxembourg.</li>
</ul>

<h2>Nos offres</h2>
<ul class="list">{offres}</ul>

<h2>Transparence sur les liens</h2>
<p>Les liens des fiches Premium et des articles sponsorisés sont balisés <code>rel="sponsored"</code>, conformément aux consignes de Google, et les contenus concernés sont signalés comme tels. Nous ne vendons pas de liens cachés et nous ne garantissons aucun classement dans les moteurs de recherche : ce que vous achetez, c'est de la visibilité et de l'audience.</p>

<h2>Comment ça marche</h2>
<ol>
  <li>Vous nous écrivez en indiquant l'offre qui vous intéresse.</li>
  <li>Nous convenons du contenu et du tarif.</li>
  <li>Nous publions la fiche ou l'article, puis nous vous envoyons le lien de la page en ligne.</li>
</ol>

<h2>Questions fréquentes</h2>
<details><summary>Les liens sont-ils « dofollow » ?</summary><p>Non. Les liens payants portent l'attribut <code>rel="sponsored"</code>. C'est ce que demande Google pour les liens sponsorisés.</p></details>
<details><summary>Cela améliore-t-il mon classement sur Google ?</summary><p>Nous ne promettons aucun classement. Une fiche ou un article sponsorisé apporte de la visibilité, des visiteurs et une citation locale, qui complètent un travail de référencement.</p></details>
<details><summary>Quelles entreprises acceptez-vous ?</summary><p>Des entreprises et des professionnels réels, avec un contenu légal et pertinent pour l'annuaire. Nous refusons les contenus trompeurs, illégaux ou sans rapport avec l'activité de l'entreprise.</p></details>
<details><summary>Je suis une agence ou un indépendant, puis-je commander pour mes clients ?</summary><p>Oui, le pack agences et indépendants est prévu pour cela. Écrivez-nous avec le nombre de clients ou de projets concernés.</p></details>
<details><summary>Quel logo dois-je envoyer ?</summary><p>Le logo que vous avez, en PNG, SVG, WebP ou JPG, de préférence avec un fond transparent et d'au moins 300 pixels de large. Nous l'adaptons à la fiche, quelles que soient ses proportions. Il est affiché sans déformation.</p></details>
<details><summary>Puis-je choisir le texte du lien vers mon site ?</summary><p>Oui, avec la fiche Premium. Votre description (100 à 115 mots) contient un lien dont vous choisissez l'intitulé : court, descriptif, en rapport avec votre activité. L'adresse complète de votre site reste affichée dans vos informations. Nous pouvons refuser un intitulé trompeur ou composé uniquement de mots-clés.</p></details>
<details><summary>Quels sont les tarifs ?</summary><p>Les tarifs dépendent de l'offre et du volume. Demandez un devis par e-mail : <a href="mailto:{esc(contact)}">{esc(contact)}</a>.</p></details>

<p style="margin-top:28px">{cta("Fiche Premium ou article sponsorisé")}</p>
"""
    urls.append("/visibilite/")
    ecrire("/visibilite/", page(f"Boostez votre visibilité au Luxembourg – {SITE_NAME}",
                                "Fiche Premium, article sponsorisé et pack agences : gagnez en visibilité locale auprès des clients du Luxembourg, de la France et de la Belgique.",
                                "/visibilite/", corps))

    # Pages légales
    L = CFG["legal"]
    editeur = (f'<a href="{esc(L["editeur_url"])}" rel="noopener" target="_blank">{esc(L["editeur"])}</a>'
               if L.get("editeur_url") else esc(L["editeur"]))
    mail = f'<a href="mailto:{esc(L["contact"])}">{esc(L["contact"])}</a>'
    corps = f"""
<h1>Mentions légales</h1>
<h2>1. Éditeur du site</h2>
<p>Le site {esc(SITE_NAME)} est édité par {editeur}, depuis le {esc(L['lieu'])}. Pour toute question, écrivez à {mail}.</p>
<p>L'éditeur dispose d'une autorisation d'établissement délivrée par le ministère de l'Économie du Luxembourg. Il n'est pas assujetti à la TVA (régime de franchise, sous le seuil de chiffre d'affaires applicable).</p>
<h2>2. Hébergement</h2>
<p>Le site est hébergé par GitHub Pages (GitHub, Inc., San Francisco, États-Unis). Le nom de domaine est enregistré chez EuroDNS.</p>
<h2>3. Objet du site</h2>
<p>{esc(SITE_NAME)} est un annuaire gratuit d'entreprises et de professionnels installés au Luxembourg. Il permet de les trouver par catégorie ou par commune et d'accéder à leurs coordonnées professionnelles.</p>
<p>L'inscription d'une entreprise est gratuite. Des options payantes (fiche Premium, article sponsorisé) existent : les liens correspondants portent l'attribut <code>rel="sponsored"</code> et la fiche ou l'article est signalé comme tel. Un contenu sponsorisé n'est pas une recommandation de l'éditeur.</p>
<h2>4. Exactitude des informations</h2>
<p>Les fiches reprennent des informations professionnelles publiques (nom, adresse, téléphone, e-mail, site web) fournies par les entreprises ou collectées dans des sources publiques. L'éditeur s'efforce de les tenir à jour mais ne garantit ni leur exactitude ni leur exhaustivité. Une information erronée peut être corrigée ou supprimée sur simple demande à {mail}.</p>
<p>Certaines données des fiches proviennent d'OpenStreetMap : © <a href="https://www.openstreetmap.org/copyright" rel="noopener" target="_blank">contributeurs OpenStreetMap</a>, publiées sous licence ODbL.</p>
<h2>5. Propriété intellectuelle</h2>
<p>La structure du site, ses textes et ses éléments graphiques appartiennent à l'éditeur, sauf mention contraire. Les noms, marques et coordonnées des entreprises référencées restent la propriété de leurs titulaires. Toute reproduction non autorisée est interdite ; une courte citation accompagnée d'un lien vers la page d'origine est tolérée.</p>
<h2>6. Données personnelles et cookies</h2>
<p>Le site n'utilise ni outil d'analyse d'audience, ni cookie publicitaire, ni cookie de suivi. Les détails figurent dans la <a href="{url('/confidentialite/')}">politique de confidentialité</a>.</p>
<h2>7. Responsabilité</h2>
<p>L'éditeur ne peut être tenu responsable des décisions prises à partir des informations de l'annuaire, ni du contenu des sites externes vers lesquels les fiches renvoient. Ces liens sont fournis à titre indicatif, sans contrôle de l'éditeur sur leur contenu.</p>
<h2>8. Contact</h2>
<p>{mail}</p>
<p class="small">Dernière mise à jour : {esc(L['maj'])}.</p>
"""
    ecrire("/mentions-legales/", page(f"Mentions légales – {SITE_NAME}", "Mentions légales de l'annuaire.", "/mentions-legales/", corps, noindex=True))
    corps = f"""
<h1>Politique de confidentialité</h1>
<h2>Données publiées dans l'annuaire</h2>
<p>Les fiches contiennent des informations professionnelles : nom de l'entreprise, adresse, téléphone, e-mail, site web et description. Elles sont publiées à des fins d'annuaire, à partir d'informations fournies par les entreprises ou issues de sources publiques.</p>
<h2>Vos droits</h2>
<p>Vous pouvez demander l'accès, la rectification ou la suppression d'une fiche, ou vous opposer à sa publication, à tout moment : écrivez à {mail}. La demande est traitée dans les meilleurs délais. Vous pouvez aussi saisir l'autorité de contrôle luxembourgeoise, la CNPD (Commission nationale pour la protection des données).</p>
<h2>Formulaire d'inscription</h2>
<p>Les informations saisies dans le formulaire « Ajouter votre entreprise » sont transmises par un service tiers de formulaires (Formspree) à l'éditeur. Elles servent uniquement à créer, modifier ou supprimer la fiche concernée et à répondre à votre demande.</p>
<h2>Cookies et mesure d'audience</h2>
<p>Le site n'utilise pas de cookies de suivi ni d'outil de mesure d'audience. Comme tout site web, il est hébergé par GitHub Pages, dont les serveurs peuvent enregistrer techniquement l'adresse IP des visiteurs.</p>
<p class="small">Dernière mise à jour : {esc(L['maj'])}. Éditeur : {editeur}.</p>
"""
    ecrire("/confidentialite/", page(f"Confidentialité – {SITE_NAME}", "Politique de confidentialité de l'annuaire.", "/confidentialite/", corps, noindex=True))

    # blog
    L = CFG["legal"]
    mail_contact = L["contact"]
    blog_indexe = bool(ARTICLES)
    cartes = ""
    for a in ARTICLES:
        ch = f"/blog/{a['slug']}/"
        rel = "sponsored noopener" if a["sponsorise"] else "noopener"
        if a["sponsorise"]:
            bandeau = '<p class="small"><span class="badge">Article sponsorisé</span> Cet article est un contenu sponsorisé : les liens sortants sont balisés rel="sponsored".</p>'
        else:
            bandeau = ""
        auteur = esc(a.get("auteur", "")) if a.get("auteur") else ""
        if a.get("auteur") and a.get("auteur_url"):
            auteur = f'<a href="{esc(a["auteur_url"])}" rel="{rel}" target="_blank">{auteur}</a>'
        ld = {"@context": "https://schema.org", "@type": "Article", "headline": a["titre"],
              "datePublished": a["date"], "description": a["resume"],
              "mainEntityOfPage": f"{SITE_URL}{ch}",
              "publisher": {"@type": "Organization", "name": SITE_NAME}}
        if a.get("auteur"):
            ld["author"] = {"@type": "Person", "name": a["auteur"]}
        corps = f"""
<p class="meta"><a href="{url('/blog/')}">Blog</a> › {esc(a['titre'])}</p>
<article>
<h1>{esc(a['titre'])}</h1>
<p class="meta">Publié le {date_fr(a['date'])}{(' · par ' + auteur) if auteur else ''}</p>
{bandeau}
{md_html(a['corps'], rel)}
</article>
<p class="small">Vous souhaitez publier un article sur l'annuaire ? <a href="{url('/blog/')}#publier">Découvrez les conditions</a>.</p>
"""
        ecrire(ch, page(f"{a['titre']} – {SITE_NAME}", a["resume"], ch, corps,
                        extra_head='<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False) + "</script>"))
        urls.append(ch)
        cartes += (f'<li class="card"><h3><a href="{url(ch)}">{esc(a["titre"])}</a>'
                   + (' <span class="badge">Sponsorisé</span>' if a["sponsorise"] else "")
                   + f'</h3><p class="meta">{date_fr(a["date"])}</p><p>{esc(a["resume"])}</p></li>')
    liste_blog = f'<ul class="list">{cartes}</ul>' if cartes else "<p>Les premiers articles arrivent bientôt.</p>"
    sujet = urlquote("Proposition d'article invité")
    corps = f"""
<h1>Blog : actualités et conseils pour les professionnels au Luxembourg</h1>
<p>Articles sur la vie des entreprises, le référencement local et la visibilité en ligne au Luxembourg, la Belgique et la France.</p>
{liste_blog}
<h2 id="publier">Publier un article invité</h2>
<p>Vous êtes une entreprise, une agence ou un indépendant et souhaitez publier un article sur {esc(SITE_NAME)} ? Nous acceptons des articles utiles pour nos lecteurs, sur des sujets en lien avec les entreprises, les métiers et les services au Luxembourg.</p>
<ul class="plain">
<li><strong>Article original</strong> : texte inédit, rédigé en français, de 600 mots minimum, sans contenu copié.</li>
<li><strong>Lien sponsorisé</strong> : les articles proposés par des annonceurs sont signalés comme sponsorisés et leurs liens sortants portent l'attribut rel="sponsored", conformément aux recommandations de Google.</li>
<li><strong>Validation éditoriale</strong> : nous relisons chaque article et nous réservons le droit de le refuser ou de demander des modifications.</li>
</ul>
<p><a class="btn" href="mailto:{esc(mail_contact)}?subject={sujet}">Proposer un article</a> · <a href="{url('/visibilite/')}">Voir les offres de visibilité</a></p>
"""
    if blog_indexe:
        urls.append("/blog/")
    ecrire("/blog/", page(f"Blog – {SITE_NAME}",
                          "Articles et conseils pour les professionnels au Luxembourg : visibilité, référencement local, vie des entreprises.",
                          "/blog/", corps, noindex=not blog_indexe))

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

    print(f"OK : {len(ENTREPRISES)} fiches, {len(GROUPES)} groupes, {len(PAGES_METIER)} pages métier, {len(PAGES_VILLE)} pages commune, {len(urls)} URLs dans le sitemap, {sum(1 for e in ENTREPRISES if e['indexable'])} fiches indexables sur {len(ENTREPRISES)}.")


if __name__ == "__main__":
    build()
