---
name: roadmap-tracker
description: Tenir la roadmap du projet dans un fichier markdown de la mémoire native (specs canon, milestones avec DoD, tâches à IDs stables, claims). Utiliser dès que l'utilisateur parle de roadmap, backlog, milestone, spec, tâche ou avancement — ajouter/modifier une entrée, prendre ou continuer une tâche, marquer terminé, demander où on en est — même si le mot « roadmap » n'est pas prononcé explicitement.
---

# Roadmap tracker — la roadmap comme fichier mémoire

La roadmap vit dans un fichier markdown à grammaire stricte. La spec est le
canon, le fichier est l'état, et l'avancement se rapporte en éditant ce
fichier — de façon chirurgicale, sans jamais casser sa grammaire.

## Où vit la roadmap

- **Source de vérité** : `roadmap.md` dans le dossier de mémoire auto du
  projet — `~/.claude/projects/<projet>/memory/roadmap.md`. Localiser le
  dossier avec `ls -d ~/.claude/projects/*` (le nom dérive du chemin du
  repo) ; en cas de doute, la commande `/memory` liste les fichiers chargés.
- **Miroir versionné** : après CHAQUE modification, recopier le fichier à
  l'identique dans le repo sous `.claude/roadmap.md` (créer au besoin).
  C'est ce miroir, commité avec le projet, qui suit les changements de
  machine.
- **Amorçage sur une nouvelle machine** : si la mémoire auto n'a pas de
  `roadmap.md` mais que le repo contient `.claude/roadmap.md` (ou un ancien
  export comme `_memory_migration/memory/roadmap.md`), copier le fichier du
  repo vers la mémoire auto avant toute opération — le plus récent des deux
  gagne (comparer les dates de modification, signaler tout conflit).

## Grammaire du fichier (ne jamais s'en écarter)

Trois familles d'IDs stables, numérotées en croissant, **jamais renumérotées
ni réutilisées** même après suppression :
`ROADMAP:SPEC:n`, `ROADMAP:MILESTONE:n`, `ROADMAP:TASK:n`.

Structure du fichier :

```markdown
# Roadmap

## Specs

- `ROADMAP:SPEC:1` **Titre de la spec** [draft|active|retired]
  - Canon : <le design tranché, les références aux docs du repo>

Règles :
- <règle 1>
- <règle 2>

## M1 — Titre du milestone (`ROADMAP:MILESTONE:1`, planned|active|done)

<Description : pourquoi ce milestone, décisions de portée datées.>

DoD du milestone : <critère observable et rejouable de bout en bout.>

- [x] `ROADMAP:TASK:1` Titre _(implements ROADMAP:SPEC:1)_
- [ ] `ROADMAP:TASK:2` Titre _(implements ROADMAP:SPEC:1; depends on ROADMAP:TASK:1)_
- [~] `ROADMAP:TASK:3` Titre _(claimed by <user>)_

## Backlog (no milestone)

- [ ] `ROADMAP:TASK:4` Titre
```

Conventions :

- Cases : `[ ]` todo · `[~]` in_progress (toujours accompagné de
  `_(claimed by <user>)_`) · `[x]` done. Une tâche bloquée reste `[~]` avec
  `_(blocked: <raison>)_` dans le suffixe.
- Le suffixe italique regroupe, dans cet ordre et séparés par `; ` :
  `implements <SPEC...>`, `depends on <TASK...>`, `claimed by <user>`,
  `blocked: <raison>`.
- Préfixes de titre normalisés : `[BUG]`, `[JALON]` (placeholder non
  détaillé), `[RÉCURRENT]`, `[FOND]` (tâche de fond), `[RÉFLEXION]`.
  Le type implicite d'une tâche sans préfixe est `feature`.
- Les décisions de portée se datent dans le texte
  (« décision commanditaire 2026-07-30 ») — la roadmap porte son historique.
- Un milestone passe `done` quand toutes ses tâches sont `[x]` ; le noter
  dans son en-tête sans rien supprimer.

## Opérations courantes

**« Où on en est ? »** — lire le fichier, répondre avec : milestones et leur
ratio done, tâches `[~]` claimées, prochaines tâches débloquées (toutes
dépendances `[x]`). Ne pas paraphraser tout le fichier.

**Ajouter une spec / un milestone / une tâche** — prendre le prochain numéro
libre de la famille, respecter la grammaire, raccrocher la tâche à son
milestone et sa spec (`implements`), déclarer ses `depends_on`. Une idée non
rattachée va en Backlog. Ne jamais réécrire les entrées existantes au
passage.

**Prendre une tâche (claim)** — choisir la tâche demandée, sinon une `todo`
dont toutes les dépendances sont `[x]`. Si une dépendance n'est pas done :
le signaler et s'arrêter. Marquer `[~]` + `claimed by <user>`, puis suivre
« Implémenter une tâche ».

**Terminer une tâche** — dérouler la Definition of Done de son type
(ci-dessous) avec preuves. Tout passe → `[x]` (retirer le `claimed by`).
Sinon → la tâche reste `[~]`, dire précisément ce qui manque.

**Toujours finir par** : recopier le fichier vers le miroir
`.claude/roadmap.md` du repo, et rappeler qu'il reste à committer.

## Implémenter une tâche

1. **Canon d'abord** : lire la ou les specs de la tâche et les docs du repo
   qu'elles citent. La spec a déjà tranché le design — l'implémentation ne
   re-décide pas. Point bloquant ambigu : question à l'utilisateur ou
   marquage `blocked`, jamais une invention.
2. **Contexte mémoire** : consulter les fichiers de mémoire du projet
   (`decisions.md`, `conventions.md`, `bugs-pieges.md`,
   `faits-contraintes.md`) sur le sujet avant de choisir une approche — les
   décisions passées peuvent invalider un plan.
3. **Plan (gate)** : découper en incréments vérifiables — chaque incrément a
   un critère de succès objectif (test, commande, comportement démontré).
   Ordre par défaut : contrats/schémas → logique → interfaces → UI → docs.
   **Présenter le plan et attendre le feu vert avant d'écrire du code.**
4. **Incréments** : un incrément dont la vérification ne passe pas n'est pas
   fait. Modifications chirurgicales. Ne pas committer — le working tree
   revient à l'utilisateur.
5. **Clôture** : DoD + mise à jour du fichier + miroir (cf. ci-dessus).
   Écart constaté entre spec et réalité du code : le rapporter comme
   proposition d'amendement de la spec, ne pas corriger la spec d'office.

## Definition of Done par type

Chaque critère se **démontre** (commande exécutée, sortie citée), il ne
s'affirme pas.

**feature** — critères de la spec rejouables un par un ; tests ciblés verts ;
typecheck/lint vert sur le périmètre touché ; aucune dépendance non-done.

**bug** — reproduction capturée AVANT le fix ; test de non-régression ajouté
et vert ; suite du module touchée verte.

**test** — les nouveaux tests échouent si on retire le comportement testé
(mutation rapide ou justification précise) ; suite complète du module verte.

**doc** — extraits et commandes exécutés tels quels ; chemins et noms cités
vérifiés, pas supposés.

**infra / chore** — commande de build/migration exécutée avec succès (sortie
citée), sinon limite signalée et tâche laissée `[~]` ; rollback ou
idempotence vérifié quand pertinent.

## Garde-fous

- Le fichier est la seule source de vérité : pas d'état d'avancement gardé
  « de tête » ou dans la conversation seulement.
- Éditions minimales : changer une case, un suffixe ou ajouter une entrée —
  jamais de réécriture globale, jamais de renumérotation.
- Une vérification non exécutable (service externe, secret manquant) ne se
  coche pas sur parole : elle se remonte à l'utilisateur.
- Si le fichier est introuvable des deux côtés, proposer d'en initialiser un
  vide à la grammaire ci-dessus — ne jamais inventer un historique.
