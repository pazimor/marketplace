---
name: canon-tracker
description: Tenir le canon du projet dans des fichiers markdown versionnés (`.claude/canon/` — attentes, conventions, instructions de test, invariants), chaque entrée portant sa provenance `[USER:<nom>]` intouchable ou `[MODEL]` déclassable. Utiliser dès que la conversation touche à ce que l'utilisateur attend du produit, aux façons de faire du projet, à comment on teste, à ce qu'il ne faut pas casser, à une contrainte ou une convention à retenir — et systématiquement avant d'écrire du code sur le projet ainsi qu'à la clôture de chaque tâche, même si le mot « canon » n'est jamais prononcé.
---

# Canon tracker — l'implicite, écrit au fil de l'eau

Ce qui se met au point en première passe — comment on teste, ce qu'il ne faut
pas casser, ce que l'utilisateur attend vraiment — n'est jamais écrit et meurt
avec la conversation. Le canon est le lieu où on l'écrit, entrée par entrée,
avec sa source. Le fichier est le canon ; la conversation n'est qu'un brouillon.

## Où vit le canon

- **Source de vérité** : `.claude/canon/` à la racine du repo du projet.
  Commité, versionné, synchronisé par git — c'est du projet, pas du personnel.
- **Pas de miroir mémoire.** Contrairement à la roadmap, le canon ne se recopie
  jamais dans la mémoire auto (`~/.claude/projects/…`) : il appartient au repo
  et à toute personne qui le clone.
- **Fichiers thématiques**, un thème par fichier :
  - `attentes.md` — ce que l'utilisateur attend du produit (comportements
    voulus, non-buts, priorités).
  - `conventions.md` — les façons de faire du projet (nommage, structure,
    style, outillage imposé).
  - `tests.md` — comment on vérifie : commandes exactes, à lancer d'où, ce
    qu'une sortie saine ressemble.
  - `invariants.md` — états et comportements à ne **JAMAIS** casser.
- Un thème nouveau et clairement distinct peut justifier un fichier
  supplémentaire (`perf.md`, `securite.md`…). Jamais de `divers.md` ni de
  fourre-tout : une entrée qui ne rentre nulle part signale un thème à nommer.

## Grammaire d'une entrée (ne jamais s'en écarter)

Une entrée = **un** point, tenant sur une ligne (une phrase, deux au plus).
Jamais de prose flottante, jamais de paragraphe hors entrée.

```
- `CANON:n` [USER:<nom> AAAA-MM-JJ] <le point>
- `CANON:n` [MODEL AAAA-MM-JJ] <le point>
```

- Les IDs `CANON:n` sont **stables, croissants, uniques sur tout le dossier**
  (pas par fichier) : le prochain numéro libre se cherche dans `.claude/canon/`
  entier. Jamais renumérotés, jamais réutilisés, même après dépréciation.
- La date est celle de l'écriture de l'entrée (ou de la confirmation, en cas de
  promotion).
- `<nom>` est le nom ou l'identifiant de la personne qui a dit ou validé le
  point ; en cas de doute, le demander plutôt que d'inventer.

Exemple complet (`.claude/canon/tests.md`) :

```markdown
# Tests

- `CANON:12` [USER:eddy 2026-08-14] La suite se lance avec `pytest -q` depuis la
  racine du repo ; jamais depuis un sous-dossier (les fixtures cassent).
- `CANON:13` [MODEL 2026-08-14] `pytest -q tests/test_graph.py` prend ~40 s : le
  premier appel télécharge le modèle, les suivants sont instantanés.
- `CANON:14` [USER:eddy 2026-08-20] Un test qui touche le réseau est refusé en
  revue, même marqué `skip`. (promu de MODEL)
- ~~`CANON:9` [MODEL 2026-07-02] Les tests tournent via `make test`.~~
  — obsolète 2026-08-14 : `make test` a été supprimé, remplacé par `CANON:12`.
```

## Provenance — la règle centrale

**`[USER:<nom>]` = dit ou validé explicitement par l'humain. INTOUCHABLE.**
Jamais réécrit, jamais supprimé, jamais contredit, jamais « amélioré ». Un
conflit — entre deux entrées `[USER]`, ou entre le code observé et une entrée
`[USER]` — se **signale à l'utilisateur** et s'arrête là ; il ne se corrige
jamais d'office.

**`[MODEL]` = déduit ou constaté par l'agent en travaillant.** Face à toute
entrée `[USER]` qui frotte, l'entrée `[MODEL]` est déclassée d'office : c'est
l'utilisateur qui a raison. Une entrée `[MODEL]` ne devient `[USER:<nom>]` que
sur **confirmation explicite** de l'utilisateur — jamais parce qu'elle a l'air
solide, jamais parce qu'elle est ancienne, jamais parce qu'elle est vérifiée
par le code.

**Rien ne se supprime.** Une entrée devenue fausse se barre (`~~texte~~`) avec
la raison et la date, et reste en place : l'historique du canon fait partie du
canon.

## Opérations courantes

**Ajouter une entrée** — choisir le fichier thématique, prendre le prochain
`CANON:n` libre sur tout le dossier, écrire une ligne à la grammaire ci-dessus.
Point venu de l'utilisateur (dit ou validé dans la conversation) → `[USER:<nom>]`.
Point constaté en travaillant → `[MODEL]`. Ne jamais toucher aux entrées
voisines au passage.

**Promouvoir `[MODEL]` → `[USER:<nom>]`** — uniquement après une confirmation
explicite de l'utilisateur sur ce point précis (« oui, c'est bien la règle »).
La promotion garde l'ID, retagge la ligne avec le nom et la **date de la
confirmation**, et ajoute `(promu de MODEL)` en fin de ligne. Sans confirmation
explicite : l'entrée reste `[MODEL]`, point final.

**Déprécier une entrée** — barrer le texte (`~~…~~`), ajouter en dessous ou en
fin de ligne `— obsolète AAAA-MM-JJ : <raison>` et, s'il y a lieu, l'ID de
l'entrée qui la remplace. Une entrée `[USER]` ne se déprécie **que** sur
décision de l'utilisateur.

**Résoudre un conflit** — ne rien réécrire. Citer les entrées en cause avec
leurs IDs, décrire précisément la contradiction (avec ce qui l'a révélée : code
lu, test lancé, demande reçue), et demander à l'utilisateur laquelle fait foi.
Tant que la réponse n'est pas venue : l'entrée `[USER]` prime, le travail en
cours s'aligne dessus ou s'arrête.

**Initialiser le canon** — si `.claude/canon/` n'existe pas, le proposer et
créer les quatre fichiers avec leur seul titre (`# Attentes`, `# Conventions`,
`# Tests`, `# Invariants`). **Ne jamais inventer d'historique** : pas d'entrée
déduite rétroactivement du code au moment de l'amorçage, le canon se remplit au
fil de l'eau.

## Rituel de capture (obligatoire à chaque clôture de tâche)

L'agent orchestrateur exécute ce rituel à la clôture de **chaque** tâche, avant
de cocher quoi que ce soit. Ce n'est pas optionnel et ça ne se reporte pas.

1. Se demander explicitement : **« qu'est-ce qui a été mis au point d'implicite
   pendant cette passe ? »**
2. Repasser la conversation : chaque demande, arbitrage ou validation venus de
   l'utilisateur en cours de route → entrée `[USER:<nom>]` (attentes,
   conventions, invariants selon le thème).
3. Repasser le travail : commande de test qui marche vraiment, invariant
   observé, piège rencontré, contrainte découverte → entrée `[MODEL]`.
4. Écrire les entrées **avant** de cocher la tâche dans la roadmap, puis
   rappeler qu'il reste à committer `.claude/canon/`.
5. Rien de nouveau ? Le dire explicitement — c'est une réponse valable, pas une
   raison de sauter l'étape.

## Gate de lecture (avant toute action de code)

Avant d'écrire ou de modifier du code sur le projet, lire les fichiers canon
pertinents (au minimum `invariants.md` et `conventions.md` ; `tests.md` dès
qu'il s'agit de vérifier ; `attentes.md` dès qu'il s'agit de comportement).
Une entrée `[USER]` prime sur toute intuition du modèle, sur toute habitude
générale et sur tout précédent trouvé ailleurs dans le code. Une entrée
`[MODEL]` sert d'indice, pas de loi.

## Garde-fous

- Éditions **chirurgicales** : ajouter une ligne, barrer une ligne, retagger
  une ligne. Jamais de réécriture globale d'un fichier, jamais de
  renumérotation, jamais de « nettoyage » ou de reformulation d'entrées
  existantes.
- `[USER]` prime **toujours**, sur le modèle comme sur le code. Le modèle
  signale, il ne tranche pas.
- Une entrée floue ne vaut rien : un point qui ne se vérifie pas (commande
  exacte, comportement observable, règle applicable) se reformule ou se
  demande.
- Le canon n'est pas un journal de bord : pas de récit de session, pas de
  « j'ai fait X », uniquement des points durables.
- Jamais de canon inventé pour remplir : mieux vaut quatre fichiers presque
  vides et vrais qu'un canon plausible et faux.
