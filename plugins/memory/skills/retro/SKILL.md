---
name: retro
description: Boucle retro de fin de milestone — analyser les memoires accumulees pendant le milestone et proposer de promouvoir les patterns recurrents en skills, en regles CLAUDE.md ou en specs roadmap. Utiliser quand un milestone passe a done, ou quand l'utilisateur demande une retro / un bilan / une consolidation des apprentissages.
---

# Retro — fin de milestone

Fermer la boucle du workflow : roadmap → orchestration → memoire → **retro** →
mise a jour roadmap/skills. La retro transforme les faits episodiques
accumules en ameliorations durables du systeme.

## Workflow

1. **Perimetre** : identifier le milestone termine via `backlog(include_done=true)`
   — ses taches, leurs specs, la fenetre temporelle (created_at → derniere
   task done).

2. **Collecte** : rassembler les memoires de la periode :
   - `memory_search` sur les themes du milestone (une requete par spec/theme) ;
   - `memory_query` ancre sur les symboles les plus touches ;
   - `graph_overview` pour les stats globales.

3. **Analyse des patterns** (dans la session courante — c'est ici que le LLM
   a de la valeur, pas dans le pipeline) :
   - erreurs resolues plus d'une fois → candidat regle/garde-fou ;
   - decisions re-expliquees plusieurs fois → candidat CLAUDE.md ;
   - sequence d'actions repetee → candidat skill ;
   - friction roadmap (taches bloquees longtemps, dependances decouvertes
     tard) → candidat restructuration de specs.

4. **Propositions** — presenter a l'utilisateur un tableau :
   | Pattern observe | Occurrences | Promotion proposee | Cible |
   avec pour chaque ligne le texte exact propose (regle CLAUDE.md, squelette
   de skill, ou patch `roadmap_apply`). **Ne rien appliquer sans validation.**

5. **Application** (apres accord) :
   - regles → editer le CLAUDE.md du projet cible ;
   - skills → creer le SKILL.md dans le plugin adequat ;
   - roadmap → `roadmap_apply` (deltas structures) ;
   - immuniser les memoires fondatrices : `memory_immunize` sur les faits
     promus (ils ne doivent plus expirer) — les autres suivent la retention
     normale.

6. **Trace** : demander la memorisation d'un fait "retro milestone X faite le
   YYYY-MM-DD, promotions : …" pour que la prochaine retro connaisse la
   precedente.

## Garde-fous

- Une promotion = un pattern **recurrent et verifie**, pas une observation
  unique.
- Ne pas dupliquer une regle deja presente dans CLAUDE.md ou un skill — les
  lire avant de proposer.
- La retro ne re-planifie pas le projet : les changements de roadmap proposes
  restent des ajustements de structure, pas des re-decisions produit.
