# Extensions du projet : `.claude/level-design/`

Le plugin est générique. Un projet l'**étend sans le modifier** : ses règles propres, ses
références par type de scène, ses specs, son outillage et ses pièges sont déclarés dans un
index lu par les deux skills et par l'agent `level-design-reviewer`.

## Où

- `.claude/level-design/index.md` à la racine du projet — **le seul point d'entrée**.
- Les fichiers propres au projet vivent à côté (`.claude/level-design/arene.md`,
  `pieges.md`…) ou ailleurs dans le repo : l'index les cite par chemin relatif à la racine.

## Grammaire de l'index

Sections dans cet ordre ; une section vide s'omet. Chaque chemin est suivi de son rôle.

```markdown
# Level design — extensions du projet

## Contexte
<un paragraphe : genre, nombre de joueurs, déplacement, gabarit joueur mesuré, moteur,
pack d'assets, style de rendu.>

## Attentes de l'humain
- <attente qui vaut pour tout niveau, avec son ID canon>

## Toujours lire
- `<chemin>` — <rôle>

## <Type de scène>            (ex. « Arène extérieure », « Salle intérieure »)
- `<chemin>` — <rôle : règles, recettes, référence mesurée>
- <règle propre au projet pour ce type, avec son ID canon>

## Specs
- Dossier : `<chemin>` · nommage : `<motif>`
- Dernière spec validée par type : `<chemin>` (…)
- Recettes déjà mesurées : `<chemin>` — <référence mesurée>

## Contrôle qualité
- `<chemin>` — <checklist du projet, prime sur le pre-flight générique pour ce qu'elle couvre>

## Étapes
- Étape <n> (<nom>) — <précision du projet : commande, outil, agent, discipline>

## Pièges
- `<chemin>` — pièges propres au moteur et aux assets du projet
```

## Ordre de priorité

canon du projet `[USER]` > index et fichiers qu'il cite > skills du plugin > références
mesurées (démos du pack) > intuition. Quand l'index et le plugin divergent, l'index gagne ;
quand l'index et une entrée `[USER]` divergent, le canon gagne et on signale l'écart.

## Quand le lire

- **Toujours en premier** : au cadrage (`level-design-build` étape 1), avant d'appliquer
  `level-design-taste`, et au début de chaque review.
- Lire `Contexte`, `Attentes`, `Toujours lire`, la section du type de scène jugé ou
  construit, puis `Specs`. `Contrôle qualité`, `Étapes` et `Pièges` à l'étape concernée.

## Reprendre le travail déjà fait

- **Une nouvelle version d'un niveau reprend sa spec existante** : ses décisions (§0) restent
  acquises, ses défauts constatés deviennent le §2, sa passe de construction se corrige au
  lieu de repartir de zéro.
- **Un niveau neuf prend pour modèle la dernière spec validée du même type** listée dans
  l'index.
- **Une recette déjà mesurée pour la même référence se réutilise** : on la complète, on ne la
  remesure pas.
- Les leçons d'une session vont dans le canon **et**, si c'est un piège réutilisable, dans le
  fichier de pièges cité par l'index.

## Index absent

Chercher un dossier de specs (`.claude/level-specs/`, `docs/**/level*`) et grep le canon sur
« level design », « arène », « salle », « map ». Proposer à l'humain de créer l'index avec ce
qui a été trouvé ; ne pas l'écrire sans son accord.
