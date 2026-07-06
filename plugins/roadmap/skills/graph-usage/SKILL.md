---
name: graph-usage
description: Mode d'emploi detaille des 3 axes du graphe projet (memory, roadmap, code) exposes par le serveur MCP. Utiliser quand l'agent doit savoir QUAND et COMMENT utiliser memory_search, code_search, backlog, roadmap_apply, task_claim, roadmap_impact ou graph_overview, ou quand l'utilisateur demande comment fonctionne le systeme de workflow/memoire/roadmap.
---

# Graph usage — les 3 axes

Un seul graphe FalkorDB par projet, trois axes de donnees :

| Axe | Contenu | Lecture | Ecriture |
|---|---|---|---|
| **Memory** | decisions passees, erreurs resolues, patterns (append-only) | `memory_search`, `memory_query` | haiku via hooks (jamais le master) |
| **Roadmap** | specs, milestones, taches, dependances | `backlog`, `roadmap_impact`, `roadmap_export` | `roadmap_apply` (deltas structures), `task_claim`/`task_release` |
| **Code** | chunks indexes (AST, niveau fonction) | `code_search`, `code_fetch`, `impact_of`, `callers_of` | hooks (ingestion automatique) |

`graph_overview` donne l'etat des trois axes en un seul call — commencer par la.

## Workflows types

**Demarrer une tache**
1. `backlog` → choisir une tache `todo` non claimee dont les `depends_on` sont done.
2. `task_claim(task_id, user, worktree)` — si `refused`, prendre une autre tache.
3. `memory_search` sur le sujet de la tache (decisions passees pertinentes).
4. `code_search` pour localiser le code concerne — **avant** tout `Read`.

**Avant de modifier une spec**
1. `roadmap_impact(spec_id)` → taches impactees et specs dependantes.
2. Modifier via `roadmap_apply` (patch structure), jamais en editant un document.
3. Le lint est retourne automatiquement — corriger les `errors` immediatement.

**Consulter du code**
- `code_search` (10-20x moins de tokens qu'un `Read`) puis `code_fetch` sur le
  chunk precis. `Read` seulement si le chunk ne suffit pas.
- Impact d'un changement de fonction : `impact_of` / `callers_of`, pas une
  exploration manuelle.

**Terminer une tache**
1. Verifier la Definition of Done (skill `task-verify`).
2. `task_release(task_id, user, done=true)` — jamais `done` sans verification.
3. `roadmap_export` si l'utilisateur veut le markdown a jour.

## Anti-patterns

- **Pas de reformulations en memoire** : la memoire est ecrite par haiku via
  les hooks ; ne pas re-stocker ce qui y est deja, ne pas paraphraser le code.
- **Pas de doublons roadmap** : chercher dans `backlog` avant de creer une
  tache ; un `roadmap_apply` update vaut mieux qu'un create duplique.
- **Jamais editer le markdown roadmap a la main** : il est genere par
  `roadmap_export`, la verite est dans le graphe.
- **Jamais marquer une tache `done` declarativement** : passer par le skill
  `task-verify` d'abord.
- **Ne pas contourner `task_claim`** : `roadmap_apply` refuse volontairement
  les champs `claimed_*`.
