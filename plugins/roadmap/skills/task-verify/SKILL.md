---
name: task-verify
description: Gate de validation avant de declarer une tache terminee — Definition of Done deterministe par type de tache (feature, bug, doc, test, infra). Utiliser AVANT tout task_release(done=true), quand l'utilisateur demande de verifier qu'une tache est finie, ou quand l'agent s'apprete a dire "termine".
---

# Task verify — Definition of Done

L'agent ne declare jamais "termine" sans critere objectif. Ce skill est la
gate : chaque type de tache a sa Definition of Done, et chaque critere doit
etre **demontre** (commande executee, sortie citee), pas affirme.

## Procedure

1. Recuperer la tache (`backlog`) : son `type`, sa spec (`implements`), ses
   `depends_on`.
2. Derouler la checklist du type ci-dessous. Chaque item = une preuve
   concrete dans la reponse (commande + resultat).
3. Si un critere echoue → la tache reste `in_progress` (ou passe `blocked`
   avec `blocked_reason` via `roadmap_apply`). Le dire explicitement.
4. Si tout passe → `task_release(task_id, user, done=true)`, puis rapporter
   les preuves.

## Definition of Done par type

**feature**
- [ ] Les criteres de la spec implementee sont rejouables un par un (test ou
      scenario demontre).
- [ ] Tests cibles verts (commande + sortie).
- [ ] Typecheck/lint du projet vert sur le perimetre touche.
- [ ] Aucun `depends_on` non-done.

**bug**
- [ ] Reproduction du bug capturee AVANT le fix (ou citee depuis la tache).
- [ ] Test de non-regression ajoute et vert.
- [ ] Suite de tests du module touche verte.

**test**
- [ ] Les nouveaux tests echouent si on inverse/retire le comportement teste
      (verification par mutation rapide ou justification precise).
- [ ] Suite complete du module verte.

**doc**
- [ ] Les extraits de code/commandes de la doc ont ete executes tels quels.
- [ ] Les chemins et noms cites existent (verifies, pas supposes).

**infra / chore**
- [ ] La commande de build/deploiement/migration a ete executee avec succes
      (sortie citee) ou, si impossible localement, la limite est signalee et
      la tache reste `in_progress`.
- [ ] Rollback ou idempotence verifie quand pertinent.

## Garde-fous

- Pas de type sur la tache → appliquer la checklist **feature** (la plus
  stricte applicable) et proposer un `roadmap_apply` pour typer la tache.
- Une verification non-executable (service externe, secret manquant) ne se
  coche pas "sur parole" : elle se remonte a l'utilisateur.
- Ce skill ne modifie pas le code : s'il manque un test, c'est un retour en
  implementation, pas une exception a la gate.
