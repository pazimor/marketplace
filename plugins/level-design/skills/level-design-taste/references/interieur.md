# Salle, couloir, intérieur

Complète `SKILL.md`. Aucune distance n'est fixée ici : hauteurs, largeurs, espacements,
portées et densités se dérivent du **kit de l'utilisateur** (contrat de grille ci-dessous)
et de sa scène de référence mesurée (`level-design-build`, recettes). Les règles
s'expriment en modules, en cellules et en proportions.

## La boîte

- **Contrat de grille posé avant toute pièce** : module horizontal, slot de mur, module
  vertical, hauteur d'étage (dessus à dessus), épaisseurs, tolérance de coïncidence. Valeurs
  **mesurées sur les assets de l'utilisateur**, jamais inventées.
- Couloir standard = 1 module ; galerie majeure = 2 modules. Hauteur libre = celle que le
  kit donne sous un étage. Mezzanines à + 1 étage. Un seul niveau de sol principal par salle.
- Pivots conventionnels (mur : bas, début, sur la ligne ; sol : coin min, dessus de dalle ;
  plafond : coin min, sous-face) ; nommage `Famille_Type_Variante_Longueur` ; ancres nommées
  aux coutures.

## Murs

- 4–5 variantes seulement (elles portent 80 % des murs), ≈ 1 variante pour 3 murs standard.
- Un run est uniforme ; une variante entre **en grappe contiguë** à un endroit justifié.
  Jamais d'alternance régulière. Changer de famille de mur en milieu de pièce = rupture de
  langage.
- Mur haut = socle + n × fût + tête. Jamais deux murs complets empilés (socle flottant à
  mi-hauteur).
- Changement de hauteur de mur = pilier au joint. Un pilier d'angle qui « fait pièce
  rajoutée » est un défaut.
- ≈ 20 % d'éléments hors grille permis **une fois la boîte posée** (remplissages, panneaux).

## Règles de pose (à refuser en bloc, avec un message nommé)

- Porte jamais dans un angle, en bout de mur, adjacente à une autre porte, au bord d'un vide,
  ni contre un seul mur.
- Fenêtre jamais en bout libre ni dans un angle ; fenêtre de façade appariée à sa moitié
  intérieure.
- Puits d'escalier = mur continu pleine hauteur ; trémie ≥ 2 modules au-dessus d'un escalier,
  pas de plafond au-dessus.
- Nez de dalle fermé côté vide ; embout fermé sur toute extrémité exposée.
- Plafond débordant sous le haut des murs, sinon un regard rasant passe.
- Léger recouvrement entre dalles voisines (dans la tolérance du contrat de grille), sinon
  un cheveu de jour se voit. Un jour visible entre deux éléments se remarque toujours.
- Retrait d'étage vers l'intérieur, sinon une fente sous le plafond.
- On n'étire que les bandes plates conçues pour ça (faces sur un aplat de texture) ; jamais
  un biseau, un détail, un motif. **Un défaut de pièce se corrige à la source**, jamais par
  une mise à l'échelle dans la passe de pose.

## Lumière intérieure

- Ambiance trois couleurs plus forte qu'en extérieur (≈ 1,7).
- Budget : ≤ 1 lampe par cellule de grille ; la densité maximale se mesure sur la
  référence du projet.
- Couloir : lampes au pas de la grille, alternées gauche/droite, blanc chaud, sans ombre,
  portée juste au-delà du pas.
- Remplissage de salle : ≈ 0,4 × l'intensité du couloir, portée plus large que le couloir.
- Focal : **une** lampe teintée, ≈ 2 × le couloir, portée la plus large, seule à porter une
  ombre douce. Aucun spot, aucune directionnelle en intérieur.
- Accent d'alerte rouge et écrans à courte portée.
- Volumes de rayons lumineux : 3 au maximum, aux focaux seulement.
- **Éclairage à 3 étages** sans lampes supplémentaires : barres au plafond ou en haut de mur ;
  liserés émissifs au ras du sol et en plinthe ; bandes intégrées au mobilier. Liserés
  **discontinus** (tirets de longueurs variées), pas une ligne continue.

## Identité et habillage

- **Identité de salle sans géométrie** : bandeau mural coloré par fonction, casiers et
  pictogrammes assortis, liserés de plafond d'une autre teinte.
- Signalétique au-dessus des portes, dans la bande haute du mur, émission faible (le bloom
  fait le néon).
- Sol : plaque ou anneau peint à intervalle régulier de modules dans l'axe ; chevrons en
  rive de vide ;
  caillebotis en gouttière contre les murs.
- Plafond : tuyauterie dans l'axe des couloirs, sinon il se lit comme un plan vide. Une
  grande galerie technique peut n'avoir **aucun** plafond : le noir au-dessus donne l'échelle.
- **Lignes de vue** : une arche ou un seuil tous les 2–3 modules ; une vue longue reste
  permise si elle traverse 2–3 seuils et se perd dans le fog noir.
- Props : densité mesurée sur la référence du projet, ≈ 90 % en grappes, adossés aux murs,
  centre libre sauf focal, ≈ 30 % en lacet libre. **Couloir de circulation interdit aux
  props par construction** (polygone de circulation rétréci d'une marge issue du gabarit
  joueur).
- Éléments de vie : détritus, une marque récurrente, écrans jamais identiques, **un seul**
  désordre de biais sur un sol orthogonal.
- Fenêtre vers l'espace : ambiance plate bleu nuit, pas de fog, far clip très grand ; le
  vide porte une texture sombre non nulle.
- Hiérarchie de scène : racines par catégorie (structure / props / signalétique / plafonds)
  désactivables, salles comme conteneurs.

## Vérifications propres à l'intérieur

- **Test d'étanchéité** : fond d'une couleur impossible (magenta), rendu depuis le centre,
  chaque baie, chaque porte et chaque angle sortant ; compter les pixels magenta → 0.
  C'est le seul verdict objectif « aucun trou ».
- ≤ 1 lumière par cellule de grille.
- Captures fixes à hauteur d'œil du joueur.
- Barème : bloquant (trou, joint ouvert, pivot ou échelle faux) > majeur (étirement visible,
  rupture de silhouette, répétition flagrante, z-fighting) > mineur (invisible depuis une
  caméra de jeu). Un défaut visible seulement d'un point jamais vu en jeu est mineur — sauf
  pour ce qui se voit de l'extérieur.
