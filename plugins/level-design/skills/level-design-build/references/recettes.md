# Recettes de la référence : mesurer au lieu d'imiter

Une scène de référence (démo du pack d'assets, niveau déjà validé) se **mesure** à la
source. Une analyse à l'œil se trompe : sur un projet réel, des « nuages » étaient
désactivés, « 28 dalles » étaient une seule plaque écrasée, un « 17 » valait 14.

## Comment

1. Lire la scène **dans son fichier source** : hiérarchie parsée, identifiants d'assets
   résolus en chemins, poses locales composées en poses monde.
2. Reconstruire hors moteur si besoin (outil 3D en mode script) pour mesurer les maillages.
3. Lancer des rayons sur une grille (pas fixé par le kit, ex. un demi-module) : carte de
   hauteur « sol seul » et « tout ».
4. Compter par script ; livrer une section « reproduire les mesures » avec les commandes.
5. Repère explicite : origine, azimut, distance depuis un centre ; dimensions à l'échelle
   posée.

## Quoi mesurer

- **Inventaire** par famille (comptes).
- **Relief** par anneaux de distance : hauteurs p5/p50/p95, pente p50/p90, % > 10° et > 35°,
  pièce dominante.
- **Transformations** par famille : échelles min/méd/max, rapport hauteur/largeur, bascule,
  enfoncement (pivot − sol), part en miroir, lacet.
- **Placement** : plus proche voisin (p25/méd/p75/p90) ; grappes (seuil ≈ 2 × la médiane du
  plus proche voisin : isolés, paires, taille, rayon, nombre d'espèces) ; « ce qui borde
  quoi » ; paliers d'échelle.
- **Densités** par bande de distance et par catégorie, en objets par cellule de grille du kit.
- **Matériaux** par instance : surcharges, couleurs, pente de bascule, intensités émissives.
- **Rendu** : réglages globaux, lumières actives, fog, post-process, ciel, far clip.
- **Pièges** de la référence : matériau par défaut d'un autre biome, texture peinte
  parasite, émissif au-dessus du plafond, objets au-delà du far clip, objets sans collider,
  éléments en lévitation qu'un audit compterait comme flottants.
- Pour un réseau (tuyaux, câbles) : les **ports** de raccord mesurés sur le mesh.

Chaque recette se termine par une checklist **« recette → conséquence pour notre niveau »**.

## Ce qui n'est PAS une recette

- **Les couleurs** de la référence : elles se valident avec l'humain. Ordre de priorité :
  canon de l'humain > bible de rendu du projet > recettes par biome.
- **Ses défauts de production** : pas de flags statiques, pas de LOD, colliders partout,
  lumières à intensité aberrante, émetteurs de particules démesurés, ombres coupées par une
  distance trop courte, doublons de ciel.
- **Son échelle** : une démo est une vitrine (base et piste décorative démesurées face au
  gabarit du joueur). Le jeu remet la figure au centre du jouable.
- **Une impression** (« ~600 plantes », « jalons à intervalles réguliers ») : sans compte
  vérifié, ce n'est pas un chiffre.
- Un réglage qui contredit une contrainte du jeu (0 lumière contre une luminance imposée,
  émissif HDR contre un plafond LDR).
