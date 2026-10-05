# Pièges déjà payés (génériques)

Chaque ligne vient d'un défaut réellement rencontré sur un projet de jeu 3D, reformulé sans
moteur ni pack. Les pièges propres à **ton** moteur et à **tes** assets vont dans le canon
et le fichier de pièges du projet, pas ici.

## Pilotage du moteur par un agent

- **Muter puis rendre dans le même appel rend l'état d'avant.** Mutation et capture (ou
  lecture) = deux appels, toujours.
- Un dialogue natif bloquant (« enregistrer les scènes modifiées ? ») fige l'agent : la passe
  ne doit jamais en ouvrir ; sauver ou refuser explicitement avant.
- Code compilé périmé dans l'éditeur : un comportement « impossible » vient souvent d'une
  bibliothèque non rechargée. Vérifier l'horodatage du binaire ou la présence d'un champ
  neuf avant de conclure.
- Scène périmée en mémoire prise pour une régression : rouvrir depuis le disque avant de
  juger — mais d'abord vérifier qu'elle ne porte pas de retouches non sauvées de l'humain.
- Sessions de jeu longues = rechargements spontanés et états fantômes : les garder courtes.
- Ne jamais relancer une entrée d'historique d'un outil d'exécution de code : une ancienne
  commande a redémarré un serveur réseau hors jeu.
- Une caméra temporaire au far clip par défaut cache le lointain : capturer avec les
  réglages de la caméra joueur, depuis des caméras nommées.
- Un matériau cloné en mémoire peut ne pas rendre comme l'asset : tester sur un vrai asset.
- Téléporter un joueur place sa racine, pas ses pieds : viser racine = surface + hauteur des
  pieds + marge, sinon on traverse les surfaces minces et on croit à un bug de collider.

## Géométrie et construction

- Les bounds d'un plan tourné trompent sur sa taille (un lac y paraît ≈ 35 % plus grand qu'il
  n'est).
- Les emprises se lisent sur les colliders ou bounds réels, jamais sur les pivots.
- Un harnais hors moteur qui route sur des boîtes de catalogue se trompe jusqu'à ~2 hauteurs de
  joueur sur des façades détaillées : mesurer les vrais colliders.
- Enfoncer une pièce rigide sur une butte la fait plonger de la hauteur de la butte :
  aplanir un socle sous son emprise, poser, puis étirer en hauteur si besoin.
- Un sol maillé en grands triangles à cheval sur la lèvre d'un lac interpole la pente : le
  liquide « remonte ». Couper le sol le long de la lèvre et de la ligne d'eau.
- Ajouter le relief **après** les plateaux, sinon les fondus l'effacent ; garder la hauteur
  exacte sous chaque repère posé.
- Une retouche de l'humain dans un groupe empreinté = le groupe n'est plus régénéré ; le
  décor neuf va dans un groupe neuf, hors des boîtes de ses pièces.
- Quand une passe rebâtit un groupe, re-valider les repères voisins qui, eux, n'ont pas bougé.
- Un module à collider creux crée une poche fermée où l'on reste coincé : collider plein.
- Prototyper la géométrie hors moteur (code pur + outil 3D) règle les conflits d'emprise
  avant la première passe jouée — puis vérifier la parité dans le moteur : l'import y a
  trouvé 39 défauts invisibles hors moteur.
- Vérifier rotation 0 / échelle 1 sur un cube test dès le départ : une conversion d'axes
  laissée sur un nœud a coûté deux tours complets.
- Découper un kit sur le **dessin** (bandes et liserés alignés entre familles), pas sur la
  section la plus épaisse. Une pièce se livre fermée (étanche) ou pas du tout.

## Matériaux et rendu

- Un matériau projeté (triplanaire) lit l'atlas aux UV du mesh : sur une primitive, il
  affiche tout l'atlas ; sur une face verticale générée, une case parasite (rose). Matériau
  dédié à dégradé pour les parois.
- Les familles d'assets portent souvent le matériau de sol d'un **autre** biome par défaut :
  surcharger à chaque instance et auditer.
- Des « taches sombres sans objet » au sol sont souvent un motif peint par le shader, pas des
  ombres : diagnostiquer la cause avant de corriger.
- Une teinte brune inexpliquée venait d'une lumière d'appoint chaude ; une traînée blanche,
  d'un spéculaire de key rasante sur un sol trop lisse.
- Les particules et objets créés à l'exécution n'existent qu'en jeu : capturer en jeu, ou
  poser un aperçu éditeur désactivé à l'entrée en jeu.
- Fonds de fosse clairs et piste sombre se lisent comme des crevasses ; des roches
  flottantes décoratives masquent le focal ; un astre au-dessus de l'objectif lui vole le
  regard.

## Audit

- Tester un seul sommet d'une pièce pour « flottant » donne des faux positifs : le sommet le
  plus bas.
- Un pincement n'est un défaut que si on est obligé d'y passer.
- Avant de corriger un audit qui contredit le prototype, le rejouer sur les colliders de la
  scène : on sépare en une heure les vrais défauts des faux positifs.
- Une ligne d'eau calculée hors moteur se remesure dans le moteur, avec la même définition
  que l'audit.
- Un plancher anti-évasion en plan unique ne suit pas le relief : le déclarer par layout.
