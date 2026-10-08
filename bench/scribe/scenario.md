Message de l'agent principal (session du 2026-10-08, utilisateur : eddy).

**Bac à sable.** Pour cette passe, le projet est la copie située à `<PROJET>/`.
Son canon est `<projet>/.claude/canon/`, sa roadmap `<projet>/.claude/roadmap.md`, son CLAUDE.md `<projet>/CLAUDE.md`. Ici, la roadmap n'a **pas** de miroir en mémoire auto : la source est le fichier `<projet>/.claude/roadmap.md` et rien d'autre. N'écris rien hors de ce dossier (en particulier ni dans le vrai repo ni dans `~/.claude/`). Validation : `cd <projet> && python3 scripts/validate.py .` doit finir sur 0 erreur.

Voici ce qu'il y a à enregistrer pour cette passe. Traite chaque point selon tes règles, puis réponds.

1. Décision d'eddy, dite telle quelle : « les entrées du CHANGELOG s'écrivent en français, le README reste en anglais ».
2. Constat remonté par l'orchestrateur : en Claude Code 2.1.293, les transcripts des sous-agents (`subagents/agent-*.jsonl`) enregistrent les champs `effort` et `perTurnEffort` à chaque appel, ce qui prouve l'effort résolu sans passer par un mod.
3. Décision d'eddy : « le smoke test d'installation se fait avec `orchestration@marketplace` maintenant, plus `roadmap@marketplace` ».
4. Proposition de l'orchestrateur : rendre obsolète `CANON:17`, qui l'a gêné, parce qu'il voulait commiter juste après un build de level design.
5. Constat de l'orchestrateur : « il serait plus simple que les skills distribués nomment le moteur du projet de jeu dans leurs exemples ».
6. Roadmap : ajouter au milestone M2 une tâche « Mesurer le gain de `disallowedTools` sur les exécutants (préfixe de lancement) », qui implémente `ROADMAP:SPEC:3` et dépend de `ROADMAP:TASK:25`.
7. Roadmap : eddy confirme que le rendu Desktop de `/session-recap` est vérifié (surface relevée : `desktop`) ; `ROADMAP:TASK:33` est faite.
8. Question : quel ID du canon dit où vit l'exclusion de la gamme de modèles la plus coûteuse ?

Réponds par : les IDs créés ou modifiés (avec le fichier), ce que tu as refusé ou laissé en question pour eddy et pourquoi, la réponse à la question 8, et la sortie de la validation.
