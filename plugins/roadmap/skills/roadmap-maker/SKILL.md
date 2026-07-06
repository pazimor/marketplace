---
name: roadmap-maker
description: Implementer une tache de la roadmap de bout en bout a partir du graphe (spec = canon, backlog = etat). Utiliser quand l'utilisateur demande d'implementer une tache/etape de la roadmap, de prendre la prochaine tache, ou de continuer le travail en cours. Encode le claim, le sequencage en increments verifiables, la gate de plan, et la cloture via task-verify.
---

# Roadmap maker — implementer depuis le graphe

La roadmap vit dans le graphe (specs, milestones, taches). Ce skill pilote
l'implementation d'une tache : la spec est le canon, le backlog est l'etat,
et l'avancement se rapporte par tools MCP (`task_claim`, `roadmap_apply`,
`task_release`) — **jamais** en editant un markdown.

## Phase 1 — Selection et claim

1. `backlog` → choisir la tache (celle demandee par l'utilisateur, sinon une
   `todo` dont tous les `depends_on` sont done). Si une dependance n'est pas
   done : le signaler et s'arreter.
2. `task_claim(task_id, user, worktree)` avec l'identite injectee au
   SessionStart. Si `refused` : la tache est prise ailleurs, en choisir une
   autre ou le signaler.
3. Lire le canon : la ou les specs (`implements`) de la tache, et
   `roadmap_impact` sur ces specs pour connaitre les taches soeurs.

## Phase 2 — Contexte (MCP d'abord)

1. `memory_search` sur le sujet (decisions passees, erreurs deja resolues).
2. `code_search` pour localiser le code concerne, `code_fetch` sur les chunks
   utiles — `Read` seulement en dernier recours.
3. `callers_of` / `imports_of` sur les symboles a modifier pour mesurer le
   rayon d'impact avant d'ecrire.

## Phase 3 — Plan (gate)

Decouper en **increments verifiables** : chaque increment a un critere de
succes objectif (test, commande, comportement demontre). Ordre par defaut :
contrats/schemas → logique metier → interfaces/API → UI → docs, tests a
chaque increment (pas seulement a la fin).

**Presenter le plan a l'utilisateur et attendre son feu vert avant d'ecrire
du code** : increments, fichiers touches, critere de verif de chacun.

> La spec a deja tranche le design. L'implementation ne re-decide pas. Si la
> spec est ambigue sur un point bloquant : question a l'utilisateur, ou
> `roadmap_apply` pour marquer la tache `blocked` avec `blocked_reason` —
> jamais une invention.

## Phase 4 — Increments

Implementer increment par increment ; un increment dont la verification ne
passe pas n'est pas fait. Modifications chirurgicales : ne toucher que ce que
la tache exige. Ne pas committer — le working tree revient a l'utilisateur.

## Phase 5 — Cloture

1. Derouler la gate du skill **task-verify** (Definition of Done du `type`
   de la tache). Chaque critere = une preuve citee.
2. Tout passe → `task_release(task_id, user, done=true)`.
   Sinon → la tache reste claimee `in_progress` (ou `blocked` via
   `roadmap_apply`), en disant precisement ce qui manque.
3. Ecarts constates entre spec et realite du code : les rapporter (candidat
   `roadmap_apply` sur la spec, decision utilisateur), ne pas corriger la
   spec d'office.
4. Rapport final : increments livres + preuves, fichiers modifies, mapping
   vers les criteres de la spec.
