# Gabarit de spec d'un niveau

Ordre tiré de la dernière spec d'arène validée sur un projet réel. Chaque section a une
raison d'être ; ne pas en sauter une sans le dire. Les chiffres d'une spec sont des valeurs
de **première création**, réglables ensuite par l'humain.

```markdown
# <Type> <Nom> — spec vN

Tâche : <ID roadmap> · Procédure : level-design-build · Modèle : <spec validée la plus proche>
Recettes : <fichier de recettes> · Contrôle : <checklist du projet> · Repère : <axes, origine>

## 0. Décisions du commanditaire
<vide à l'écriture ; rempli verbatim après les questions. Rien ne se construit avant.>

## 1. Exigences
1. <exigence, avec sa source : citation de l'humain ou ID canon>
2. …
<chacune recevra un verdict atteint / partiel / raté à la livraison>

## 2. Défauts à ne pas reproduire
- <leçon des niveaux précédents, avec ID canon>
- <piège propre à la référence>
- <erreur d'une analyse antérieure corrigée>

## 3. Déjà vérifié automatiquement
| Asset candidat | Dimensions mesurées | Objets / colliders | Rôle proposé |
Ce qui MANQUE (mesuré) : …
Contraintes techniques constatées : …

## 4. Intention
<un paragraphe : l'histoire du lieu.>
Ce qu'on garde de la référence : … · Ce qu'on refait à l'échelle du jeu : …

## 5. Trois concepts de plan masse
### Concept A — <nom>
<croquis ASCII, légende commune aux trois>
| Aire | Boîte | Plus long bord droit | Entrée → objectif (s de course) |
| Zone | Emprise | Contenu | Relief |
Circulation · lignes de vue · dangers · force · faiblesse
### Concept B — …
### Concept C — …
Recommandation : <lequel, pourquoi>

## 5bis. Plan détaillé du concept recommandé
- Relief : fonction, amplitudes, plateaux, cibles de pente
- Danger principal et sa lisibilité
- Cœur du niveau et objectif
- Hors-carte : bandes de densité
- Arrivées ennemies, points de repli, plancher de sécurité
- **S'orienter à la voix** : un nom court et un repère visible par zone

## 6. Variantes et modularité
Groupes de layouts (modes) · slots et modules par zone · exclusions · nombre de slots
dérivé de l'aire.

## 7. Environnement vivant
| Option | Principe | Où | Coût | Gameplay | Risque |
Recommandation · liste des éléments vivants avec leur cadence

## 8. Objectif, lumière, performance
Candidats d'objet central (assemblage, taille cible, lecture) · rendu / ciel / fog / budget
couleur · **caméras de capture nommées** (position, direction, FOV) ·
| Poste | Renderers estimés | Plafond |

## 9. Passe de construction
Fichiers, commandes, racines · briques réutilisées · briques à mutualiser · audits intégrés
· plan chiffré réalisé et écarts assumés · passes correctives versionnées.

## 10. Questions au commanditaire
1. <question structurante> — (a) … (b) … (c) … — **Reco : (x)**, parce que …
2. …

## 11. Definition of Done
- [ ] Spec validée (§0 rempli)
- [ ] Construction idempotente : 2ᵉ passage « rien à faire »
- [ ] Audit vert, chiffré
- [ ] Captures fixes : luminance, écrêtage, lisibilité par vue
- [ ] Jeu scénarisé : surfaces, chutes, modes
- [ ] Revue `level-design-reviewer` sans bloquant
- [ ] Livraison honnête : mesuré / restant / non vérifié
```

## Pourquoi cet ordre

- **§0 vide au départ** : on ne construit pas sur une décision imaginée.
- **§1 numéroté** : la livraison devient auditable exigence par exigence.
- **§2** est la mémoire anti-régression ; **§3** sépare le mesuré du supposé.
- **§5 trois concepts** : force un vrai choix plutôt que la première idée.
- **§5bis « à la voix »** : en coop, un niveau se joue en se parlant.
- **§10 en dernier** mais relayé en premier : les questions découlent de tout ce qui précède.
