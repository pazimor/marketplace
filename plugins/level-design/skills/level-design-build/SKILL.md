---
name: level-design-build
description: Procédure pour construire ou faire évoluer un niveau 3D — nouvelle arène, nouvelle map, nouveau biome, nouvelle salle, ou nouvelle version d'une scène après les retours de l'humain (« fais une nouvelle map », « v3 de la gorge », « refais cette salle »). Enchaîne cadrage, recettes mesurées de la référence, spec avec questions, passe de construction scriptée et idempotente, audit, captures, revue et livraison honnête. Utiliser avant d'écrire la moindre spec ou le moindre script de construction de scène.
---

# Construire un niveau — la procédure

Ce skill dit **quand** et **dans quel ordre**. Le skill `level-design-taste` dit **ce qui est
bon** ; l'agent `level-design-reviewer` **juge**. Les règles propres au projet (moteur,
outils, pièges, chartes) vivent dans son canon (`.claude/canon/`) et dans ses **extensions**
(`.claude/level-design/index.md`) : quand ce skill et l'index divergent, l'index gagne ;
quand l'index et une entrée `[USER]` divergent, le canon gagne.

## Extensions du projet — à lire en premier

Si `.claude/level-design/index.md` existe, lis-le **avant l'étape 1**. Il déclare le
contexte du jeu, les attentes de l'humain, les références par type de scène, les specs et
recettes déjà écrites, la checklist du projet, les précisions de chaque étape (outils,
commandes, agents) et le fichier de pièges. À chaque étape ci-dessous, applique aussi la
ligne `Étape n` de l'index. Grammaire, ordre de priorité et reprise de l'existant :
[references/extensions.md](references/extensions.md). Index absent : chercher les specs et
proposer de le créer.

## Ce que l'humain attend, toujours

- **L'humain décide du design.** Les questions se posent **avant** de construire, chacune
  avec options (a)/(b)/(c) et une recommandation argumentée en premier. Sa réponse est
  gravée telle quelle dans le canon (`[USER]`), puis on construit sans redemander.
- **On construit, l'humain se promène.** Il dit ce qui le dérange ; il ne place pas les
  choses à notre place. **Ses retouches à la main sont sacrées** : la passe les préserve.
- **Une passe de construction scriptée et idempotente par scène.** Rejouée N fois : même
  résultat, zéro doublon, le 2ᵉ passage annonce « rien à faire ». L'écrasement vit dans une
  commande séparée, marquée dangereuse, que seul l'humain déclenche.
- **Qualité avant vitesse.** On juge soi-même les captures et on refait plutôt que de montrer
  un rendu faible.
- Rien n'est commité ni poussé : le working tree revient à l'humain.

## Les étapes

Les ⏸ sont des arrêts : on attend l'humain. « Agent capable » = le modèle le plus fort
disponible ; si un orchestrateur délègue, il choisit selon la mention entre
parenthèses de chaque étape.

1. **Cadrage** (orchestration) — relire ce skill, l'index des extensions, `level-design-taste`,
   les entrées du canon du domaine depuis la dernière scène livrée, la ligne de roadmap.
   **Lister les specs et recettes existantes** (section `Specs` de l'index) : une nouvelle
   version reprend sa spec, un niveau neuf prend la dernière spec validée du même type. Graver l'intention de
   l'humain en `[USER]`, telle qu'il la donne. Écrire la **Lecture du niveau**
   (`level-design-taste` §0.B).

2. **Recettes de la référence** (agent capable, lecture seule) — mesurer la scène de
   référence la plus proche (démo du pack d'assets, niveau déjà validé) **à la source** :
   chiffres, pas impressions. Méthode : [references/recettes.md](references/recettes.md).
   Livrable : un fichier de recettes à côté des specs du projet. Une recette déjà mesurée
   pour la même référence se complète, elle ne se refait pas.

3. **Spec** (même agent) — gabarit : [references/spec.md](references/spec.md). Exigences
   numérotées, défauts à ne pas reproduire, déjà mesuré, intention, **trois concepts de plan
   masse cotés**, modularité, vivant, objectif/lumière/budget, passe, **questions**, DoD.
   Modèle : la dernière spec validée du même type dans le projet. **Nouvelle version** : on
   met à jour la spec existante (décisions acquises en §0, défauts constatés en §2) au lieu
   d'en écrire une neuve.

4. ⏸ **Questions à l'humain** — relayées en clair, courtes, recommandation en premier. Les
   plus structurantes d'abord ; ≈ 10 à 18 pour un niveau neuf. Il valide en bloc ou répond
   point par point. Réponses gravées en `[USER]` (noter « interp. » ce qui est interprété)
   et recopiées en tête de spec (§ Décisions). Un point non tranché reste listé en attente :
   on ne décide pas à sa place.

5. **Prérequis de code** (agent capable) — ce que la scène exige et que le runtime n'a pas
   (nouveaux types d'objets, réplication, points sûrs…). Contrats sérialisés en ajout
   seulement (jamais réordonner une liste qui entre dans un tirage à graine). Compilation
   verte avant de continuer.

6. **Passe de construction** (agent capable) — un script par scène, commandes numérotées
   (`1 — Construire`, `2 — Auditer`…), sans dialogue bloquant, idempotente, avec :
   - **empreinte** des objets créés : un objet dont la pose a changé depuis la création est
     une retouche humaine → préservé, nommé au journal, jamais écrasé ; le décor neuf va
     dans un groupe neuf ;
   - **réglages exposés** comme repères visibles et déplaçables (ancres, pivots, planchers),
     jamais en dur ;
   - **audits intégrés** en lecture seule ([level-design-taste/references/audits.md](../level-design-taste/references/audits.md)) ;
   - **caméras de capture nommées** et persistantes, réglées comme la caméra joueur.
   Pour un kit modulaire : une description déclarative (layout) + un constructeur
   déterministe qui **refuse en bloc** un layout invalide avec un message nommé.

7. **Jeu** (agent opérateur du moteur) — chaque commande jouée **deux fois** (la 2ᵉ = « rien
   à faire »), audit, captures, puis le niveau **joué** : tenir debout sur chaque surface,
   tester chaque chute, chaque mode. Sessions de jeu courtes. Un objet qui n'existe qu'à
   l'exécution est absent des captures hors jeu.

8. **Jugement** — l'orchestration regarde **elle-même** les captures en pleine résolution,
   puis l'agent `level-design-reviewer` avec la spec. Dérouler le pre-flight de
   `level-design-taste` §8 en entier, puis la checklist du projet citée par l'index. Barème : bloquant > majeur > mineur ; on ne traite une
   gravité que lorsque la précédente est vide. Faible → retour à l'étape 6 **avant** de
   montrer.

9. ⏸ **Livraison** — résultat honnête : ce qui marche (mesuré), ce qui reste (mesuré), ce
   qui n'a **pas** pu être vérifié et pourquoi. L'humain se promène ; ses
   retours → canon `[USER]` → nouvelle version par l'étape 6 (mode : `level-design-taste`
   §6).

## Tenir la procédure à jour

Chaque leçon nouvelle → une entrée datée dans le canon du projet **et**, si c'est un piège
réutilisable, une ligne dans le fichier de pièges cité par l'index. Une règle propre au
projet qui revient à chaque niveau va dans l'index ou le fichier de type de scène qu'il cite,
jamais dans ce plugin. Les pièges génériques déjà
payés sont dans [references/pieges.md](references/pieges.md) : les lire avant d'écrire la
passe.

## Garde-fous

- Pas de pose à la main par l'agent dans la scène de l'humain : tout passe par la passe.
  Quand l'humain retouche, la retouche est reportée dans le script ou préservée par
  l'empreinte.
- Une passe qui ne converge pas (deux critères qui font osciller un objet) est un bug, pas
  un réglage.
- Ne jamais valider sur les seuls tests hors moteur : le contrôle dans le moteur trouve ce
  que le prototype ne voit pas.
- Valider **une** famille, **un** coin et **une** jonction à l'écran avant de généraliser.
  Trop de génération et pas assez de regard est l'échec type.
- Ne jamais relancer à l'aveugle une commande d'historique d'un outil de pilotage du
  moteur : son contexte a changé.
