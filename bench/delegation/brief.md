## Contexte
Mini-benchmark de délégation : quatre exécutants reçoivent le même brief, chacun dans son propre dossier. Le résultat est noté ensuite par une suite de tests que tu ne vois pas. Commence par exécuter `sleep 20` (laisse le temps d'observer le lancement), puis fais la tâche.

## Canon cité
Aucune entrée de canon ne s'applique : le travail se fait hors du repo, dans un dossier temporaire.

## Périmètre
Un seul dossier, à toi : `<DOSSIER>/`
Y créer `duree.py` (fonction `parse_duree(texte: str) -> int`) et `test_duree.py` (unittest).

## Spécification de `parse_duree(texte: str) -> int` (renvoie des secondes)
1. Les espaces en tête et en fin sont ignorés. Les lettres d'unité sont insensibles à la casse. Les chiffres sont uniquement les chiffres ASCII `0`–`9`.
2. **Forme unités** : une ou plusieurs composantes `<nombre><unité>`. Unités : `j` (jour, 86400 s), `h` (3600 s), `m` (minute, 60 s), `s` (1 s). Aucune autre unité.
   - Des espaces (un ou plusieurs) sont permis entre deux composantes, jamais entre un nombre et son unité.
   - Chaque unité apparaît au plus une fois, dans l'ordre strictement décroissant `j`, `h`, `m`, `s`.
   - Un nombre est un entier sans signe (zéros de tête permis : `05m`). Seule la **dernière** composante peut avoir une partie décimale, séparée par `.` ou `,`, avec au moins un chiffre de chaque côté du séparateur.
   - Le total, calculé en valeur mathématique exacte (sans erreur d'arrondi flottant), doit être un nombre entier de secondes, sinon erreur. Exemple : `1.5m` = 90 ; `0.5s` est une erreur.
3. **Forme raccourcie** `<H>h<MM>` : un nombre entier d'heures, la lettre `h`, puis exactement deux chiffres de minutes, inférieurs à 60 (`1h30` = 5400). Cette forme n'est valide que seule : rien avant, rien après (hors espaces de tête et de fin).
4. **Forme horloge** `H:MM` ou `H:MM:SS` : `H` entier d'un ou plusieurs chiffres, `MM` et `SS` exactement deux chiffres chacun, inférieurs à 60. `1:30` = 5400 (heures:minutes).
5. Toute autre entrée lève `ValueError` : chaîne vide ou blanche, signe `+` ou `-`, nombre seul sans unité, unité inconnue ou répétée, ordre non décroissant, mélange de formes, etc.
6. Le résultat est un `int`. `0s` et `0:00` sont valides et valent 0.

## Critère de succès
`python3 -m unittest discover -s <DOSSIER> -v` passe, avec des tests qui couvrent chaque règle de la spécification (cas valides et cas d'erreur).

## Interdits
- Ne rien lire ni écrire hors de ton dossier ; ne pas regarder les dossiers des autres exécutants ni le reste du scratchpad.
- Bibliothèque standard uniquement. Pas de commit, pas de push. Ne lance aucun agent.

## Retour attendu
Chemins créés, résumé court, sortie du critère telle quelle, nombre de tests écrits, points ambigus de la spécification et comment tu les as tranchés.

## Fin de tour
Personne ne répondra en cours de route : ne t'arrête pas pour demander, va au bout, mets toute ambiguïté dans « points ambigus ».
