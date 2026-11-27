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
