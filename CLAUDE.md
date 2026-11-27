# Règles du projet : Annuaire Pro Luxembourg

Site : https://annuaireproluxembourg.eu (GitHub Pages, branche main, dossier /docs). Générateur : `python3 build.py` (lit data/*.json, écrit docs/). Ne jamais éditer docs/ à la main.

## Décisions validées
- 12 groupes de catégories (data/categories.json), métiers à l'intérieur. Ne pas en ajouter sans accord.
- Pages métier/commune créées seulement à partir de `seuil_pages` = 3 fiches. Groupes vides en noindex.
- Couleur d'accent #21724e. En-tête figé (sticky). Titre : « L'annuaire des professionnels au Luxembourg ».
- Éditeur : Agence R-P Visibility, contact rpvisibility@proton.me.

## SEO / Google
- Fiche gratuite : lien rel="nofollow". Premium/sponsorisé : toujours rel="sponsored". Ne jamais écrire « backlinks » comme argument marketing.
- Indexation : une fiche est indexée si premium, ou `index: true`, ou si au moins `seuil_index` (3) infos parmi téléphone, email, site, horaires, description > 60 car. Sinon noindex + hors sitemap.
- Aucune statistique ni donnée inventée.

## Données
- Import OSM : l'utilisateur exporte un JSON depuis overpass-turbo.eu (overpass-api.de est bloqué), puis `python3 -I tools/import_osm.py <export.json>`. Montrer le lot à l'utilisateur avant publication.
- Fiches sans commune : data/osm_a_completer.json. Attribution OpenStreetMap (ODbL) à conserver dans le pied de page et les mentions légales.
- Bannières premium : assets/bannieres/, 1200×400 px, <200 Ko ; le build échoue si le fichier est absent.

## Git
- Commit : `git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit`, push : `git -c push.negotiate=true push origin HEAD`.
- Terminer les messages de commit par les lignes Co-Authored-By et Claude-Session.
- Après déploiement, demander à l'utilisateur de faire Ctrl+F5.

## Blog (articles invités / sponsorisés)
- Un article = un fichier `data/articles/<slug>.md` (modèle : `data/articles/_modele.md`, les fichiers commençant par `_` sont ignorés). En-tête `clé: valeur`, puis `---`, puis le texte (mini-Markdown : `##`, `- `, `**gras**`, `[texte](url)`).
- `sponsorise: oui` (défaut) : badge « Article sponsorisé » + tous les liens externes en rel="sponsored noopener". `sponsorise: non` : article éditorial, liens rel="noopener".
- La page /blog/ est en noindex et hors sitemap tant qu'il n'y a aucun article ; elle devient indexable dès le premier article.

## Rédaction (voix de Sébastien)
- Avant d'écrire tout texte (descriptions de fiches, intros de pages, blog, X, e-mails), lire `REDACTION.md` et l'appliquer. Aucune donnée, statistique, avis ou opinion inventés ; hashtags : 4 minimum sur X ; vouvoiement sur le site.

## Fiches Premium (logo et ancre)
- Champs : `premium: true`, `logo` (fichier dans assets/logos/, préparé avec `tools/logo.py`), `ancre` (texte du lien), `banniere` optionnelle.
- Ancre : courte, descriptive (nom de l'activité), jamais composée uniquement de mots-clés ; lien toujours en rel="sponsored". Description Premium : 100 à 150 mots, uniquement des faits fournis.
