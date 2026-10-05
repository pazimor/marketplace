# Arène et map extérieure

Complète `SKILL.md`. Valeurs de départ tirées d'un jeu coop 2–6 joueurs (gabarit joueur
mesuré : rayon ≈ 0,2 × la hauteur, sprint ≈ 5 hauteurs par seconde) ; recalcule-les sur le
gabarit de ton projet.

## Taille et forme

- **L'aire se dérive des joueurs** : pour 6 joueurs qui courent et sautent, les arènes
  validées se traversent en ≈ 26 s de sprint ; une aire ≈ 25 fois plus petite a été jugée
  trop petite. L'humain fixe l'aire par map.
- **Contour organique obligatoire** : lobes, anses, goulets. Plus long bord droit ≤ ~24 × la
  hauteur du joueur.
- Zonage type : arène ouverte · 4 secteurs · deux moitiés opposées séparées par un danger
  en diagonale · vallée orientée avec une gorge en travers et 2 passages. Proposer **trois
  concepts de plan masse** avant d'en choisir un (skill `level-design-build`).

## Relief

- Base de bruit (houle ±1,4 × la hauteur du joueur + ondulations ±0,5 ×), puis aplatir ce qui
  doit l'être.
- Crêtes et « montagnes » infranchissables de 5–10 × la hauteur du joueur qui **coupent
  vraiment la vue** depuis le sol (obstruction mesurée, ex. ≥ 50 % à 16 × la hauteur du joueur
  dans les zones prévues pour).
- Cuvette de +0,8 à +1,2 × la hauteur du joueur aux bords : la zone jouable posée dans une
  dépression borne par la lecture.
- Canyon, gorge : parois lisibles (pas de matériau qui se déforme sur face verticale),
  fonds sombres (un fond clair se lit comme une crevasse de lumière).
- Ne jamais enfoncer une pièce rigide (tas, talus) sur une butte : elle plonge de la hauteur
  de la butte. Aplanir un socle sous son emprise d'abord.

## Liquides, gouffres, chutes

- Un lac est plat. La rive est une **chaîne** de pièces qui se recouvrent (≥ 20°), le sol
  relevé à la lèvre et coupé sous la crête, la ligne d'eau remesurée sur le résultat.
- Écart pièce de rive / ligne d'eau : moyenne ≤ 0,2 × la hauteur du joueur. Coins des plans
  liquides cachés sous le sol.
- Nombre de dangers de chute selon `RELIEF` : ex. 3 gouffres fixes + 2 en mode combat.
- Conséquence d'une chute décidée par l'humain. Pattern validé en coop : **repêchage sans
  mort** vers le point sûr le plus proche (sinon le dernier sol touché), filet à ≈ 0,2 × la
  hauteur du joueur sous le bord, sans bande brûlante.
- Points sûrs à ≥ 2 × la hauteur du joueur de toute cassure, capsule libre.
- Réflexion du soleil sur un liquide : prévoir l'éblouissement (émission ≤ 1, bloom seuil
  ~0,85, pixels écrêtés contrôlés).

## Modularité du gameplay

- Deux groupes de layouts sur une même scène (ex. « défense » et « combat ») plutôt que
  deux scènes.
- **Slots** répartis sur l'aire (≈ 40–55 par arène validée), chacun avec ≥ 3 modules (trou /
  bouché / couvert) tirés par graine répliquée. Rejouabilité sans nouvelle géométrie.
- Modules fondus dans le décor, apparition et disparition en fondu, jamais on/off sec.
- Exclusions : pas de trou près de l'objectif, de l'entrée, des goulets ; exclusion de spawn
  autour du centre et de l'entrée ; pas d'apparition à < 12 × la hauteur du joueur d'un
  événement.
- Postes de tir en hauteur utiles seulement à portée de l'objectif (au-delà de ≈ 60 × la
  hauteur du joueur = inutile).

## Objectif et combat

- Objet à protéger : 5–7 × la hauteur du joueur, propre au biome, intégré au décor mais
  identifiable, **seul point chaud** de couleur. À ≈ 7 hauteurs de joueur de l'entrée.
- 2–3 grappes de couverts garanties autour de l'objectif. Une allée de ≈ 9 s de course sans
  couvert est un stand de tir.
- Aucun groupe d'ennemis attribué à un endroit fixe ; les tireurs à distance apparaissent
  loin.
- Densité d'ennemis observée : ≈ 20–27 sur une arène validée, plafond dur fixé par le projet.
- Préavis de danger ≥ 4 s ; un projectile en cloche montre son impact au sol.

## Rendu extérieur

- **Planète** : 0 lumière, ou exactement 1 directionnelle (élévation ≈ 40–50°, ombres
  douces). Rien entre les deux ; aucune lampe ponctuelle, même dans un camp.
- **Espace** : exactement 3 directionnelles — key chaude (≈ 2,0), kicker par-dessous
  (rebond planétaire, ≈ 2,25), fill froid (≈ 0,3) — ambiance plate bleu nuit, pas de fog,
  ciel presque noir, 60–75 % du cadre en noir texturé.
- Sol : le contraste clair/sombre du relief vient du shader piloté par la pente, pas de la
  lumière. Si un shader triplanaire ne bascule en roche qu'à forte pente, le relief ne se
  lit pas : régler la bascule sur le sol généré.
- Brillance du sol faible (smoothness ≈ 0,2–0,3) : un sol à 0,55 se lit comme de la glace.
- Deux biomes = une variante de matériau (3 couleurs + la pente de bascule), rien de plus.

## Hors-carte

- **Bandes de densité** au-delà de la limite (voir le gradient de `rendu.md`), vivantes
  (vaisseaux, véhicules, canons qui tirent vers l'horizon, foreuses, convois) mais locales,
  non répliquées.
- 0 sommet dans l'enveloppe jouable + 2 × la hauteur du joueur.
- Comparer la densité du fond à la référence mesurée : un fond pauvre est un retour
  fréquent de l'humain.
- Le décor lointain voulu visible (base, jalon) est vérifié **depuis la zone de jeu**.

## Captures minimales d'une arène

Plongée générale (contour lisible) · plongée sur chaque repère (lac, gouffre) · entrée (et
entrée en hauteur) · objectif (en jeu s'il n'existe qu'au runtime) · chaque zone · chaque
rive ou bord de danger · fond / horizon. Toutes à la résolution de référence du projet, au
far clip du jeu.
