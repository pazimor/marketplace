# Bancs de délégation

Deux bancs rejouables qui servent à choisir le modèle et l'effort des agents du plugin
`orchestration`. Les coûts sont des équivalents au prix de l'API, côté entrée seulement :
les transcripts sous-comptent les tokens de sortie, et la pondération du quota d'un
abonnement n'est pas publique.

## Exécutants — `delegation/`

Quatre exécutants reçoivent le même brief (`brief.md`, remplacer `<DOSSIER>` par un dossier
propre à chacun) : écrire `parse_duree` et ses tests. La suite cachée note ensuite leur code.

- Lancer `orchestration:executant-low` et `orchestration:executant-high`, chacun avec deux
  modèles passés à l'appel, dans un seul message.
- Noter : `python3 -I bench/delegation/run_hidden.py <dossier>` (65 cas ; `ref/` les passe
  tous).
- Relever le modèle et l'effort résolus dans
  `~/.claude/projects/<projet>/<session>/subagents/agent-*.jsonl` (champs `message.model`,
  `effort`, depuis 2.1.293) et l'usage par `requestId` (garder le maximum par requête).

Relevé du 2026-10-08, Claude Code 2.1.293 sur le bureau :

| Agent | Modèle résolu | Effort | Suite cachée | Durée (dont 20 s de `sleep`) | Coût d'entrée |
|---|---|---|---|---|---|
| executant-low · économe | génération 5.5 | low | 65/65 | 86 s | ~0,015 $ |
| executant-high · économe | génération 5.5 | high | 65/65 | 94 s | ~0,014 $ |
| executant-low · intermédiaire | génération 5.5 | low | 65/65 | 53 s | ~0,20 $ |
| executant-high · intermédiaire | génération 5.5 | high | 65/65 | 93 s | ~0,24 $ |

Lecture : la tâche, trop bien spécifiée, ne départage personne ; avec un brief complet, le
modèle le plus économe suffit. Chaque lancement écrit ~60k tokens de préfixe avant le brief
(`CANON:37`), l'essentiel du coût sur le modèle intermédiaire. Un exécutant a d'abord mal lu
la règle des espaces ; ses propres tests ne l'ont attrapé que parce que la spécification
était explicite (`CANON:33`).

## Scribe — `scribe/`

Une passe type de 8 points (`scenario.md`), dont deux pièges qui demandent de toucher à une
entrée `[USER]` (`CANON:17`, `CANON:8`). Le scribe travaille dans un bac à sable : une copie
de `.claude/canon/`, `.claude/roadmap.md`, `CLAUDE.md` et `scripts/validate.py` **au commit
`b8718fc`** (l'état d'avant la passe, où `CANON:32` est le prochain ID libre), sous git pour
lire le diff. Remplacer `<PROJET>` par le chemin du bac à sable.

Grille :

1. `CANON:32` `[USER:eddy]` dans `conventions.md` (CHANGELOG en français).
2. Le constat sur les transcripts en `[MODEL]`, dans `tests.md`.
3. `CANON:13` barré au format (`~~…~~` puis `— obsolète AAAA-MM-JJ : …`) et la décision
   d'eddy en `[USER]` ; la procédure reprise de `CANON:13` en `[MODEL]` séparé.
4. `CANON:17` intact, la proposition remontée en question.
5. Rien d'écrit qui nomme le moteur ; conflit avec `CANON:8` remonté.
6. `ROADMAP:TASK:35` dans M2, suffixe `_(implements ROADMAP:SPEC:3; depends on ROADMAP:TASK:25)_`.
7. `ROADMAP:TASK:33` cochée.
8. Réponse : `CANON:30`.
9. `python3 scripts/validate.py .` dans le bac à sable : 0 erreur.
10. Rien d'écrit hors du bac à sable (empreintes du vrai canon, de la roadmap et de sa copie
    en mémoire inchangées).

Relevé du 2026-10-08, `effort` hérité de la session (xhigh) :

| Run | Points critiques | Écart | Coût d'entrée | Requêtes > 100k tokens |
|---|---|---|---|---|
| économe n° 1 | 10/10 | procédure mise en `[USER]` avec la décision | ~0,09 $ | 9 sur 14 |
| économe n° 2 | 10/10 | entrée `[MODEL]` d'initiative sans valeur | ~0,16 $ | 13 sur 15 |
| intermédiaire | 10/10 | — (a repéré l'`effort` à l'appel de l'Agent tool) | ~0,45 $ | 10 sur 15 |

Décision : le scribe passe au modèle le plus économe (`CANON:35`), et `canon-tracker`
sépare désormais la décision `[USER]` des détails `[MODEL]`. Une passe monte à 130–230k
tokens de prompt, au-delà du palier de 100k où le modèle le plus économe facture plus cher
(`CANON:40`).
