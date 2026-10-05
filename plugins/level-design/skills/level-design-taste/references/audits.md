# Audits automatiques : quoi mesurer, avec quelle cible

Chaque passe de construction expose un **audit en lecture seule** qui imprime ces mesures.
Cibles par défaut ; la spec du niveau ou le canon du projet les ajuste. Chaque ligne vient
d'un défaut réellement rencontré.

**Règle d'or : on ne montre pas un niveau sur la foi d'un audit.** Audit vert + captures
jugées + revue indépendante + jeu. Et on annonce ce qui n'a pas pu être vérifié.

## Forme et sol
| Contrôle | Cible | Pourquoi |
|---|---|---|
| Aire de l'enveloppe | aire décidée ± 3 % | l'humain fixe une aire, pas une forme |
| Plus long bord rectiligne du contour | ≤ ~24 × la hauteur du joueur | arène jugée « trop carrée » |
| Sol continu | 0 dalle visible ; plateaux taillés dans le maillage du sol | « tout repose sur des dalles » |
| Part de sol aplati | listée ; ne mange pas la plaine | 54 plateaux aplatissaient 85 % |
| Pente praticable | ≥ 99 % du sol jouable sous la pente max ; pente max listée | — |
| Relief lisible | pentes > 10° ≥ ~15 % hors zones plates imposées | sol uni, relief invisible |
| Marche au bord des plateaux | sous la hauteur de pas du contrôleur | marche à peine plus haute ressentie |

## Trous, bords, chutes
| Contrôle | Cible | Pourquoi |
|---|---|---|
| Trous de rive (rayons tout autour de chaque liquide/gouffre) | 0 | encoches, trous de rive |
| Recul du sol derrière la rive dessinée | ≤ 0,8 × la hauteur du joueur | — |
| Écart pièce de rive / ligne d'eau | moyenne ≤ 0,2 × la hauteur du joueur | festons |
| Coins des plans liquides exposés | 0 | — |
| Filet sous CHAQUE chute | 100 % | — |
| Hauteur du filet | sous la surface praticable la plus basse au-dessus | fausse alerte sous une passerelle |
| Plancher anti-évasion | **déclaré** par layout, pas déduit | 21 faux positifs sur 27 |
| Points sûrs | ≥ 2 × la hauteur du joueur de toute cassure ; capsule libre ; re-validés après toute passe qui rebâtit un groupe voisin | point sûr resté sous une roche neuve |

## Décor
| Contrôle | Cible | Pourquoi |
|---|---|---|
| Pièces flottantes | 0, test sur le **sommet le plus bas** de chaque pièce | un seul sommet testé = faux positifs et faux négatifs |
| Pièces enfouies | enfoncement conforme à la hauteur visée | montagnes enfouies de 1 à 3 hauteurs de joueur |
| Réseaux (tuyaux, câbles, rails) | 0 bout dans le vide ; raccords par les ports mesurés du mesh | 12 bouts libres |
| Matériaux interdits (autre biome, refusés par le canon) | 0 | matériau d'un autre biome par défaut |
| Matériau projeté (triplanaire) sur primitive ou face verticale | 0 case d'atlas parasite | atlas entier affiché, paroi rose |
| Colliders creux (modules, bâtiments) | chambres fermées comblées | poche où l'on reste coincé |
| Lisibilité à l'ombre | luminance de zone ≥ ~30 | lèvres sombres illisibles |
| Hors-carte dans l'enveloppe jouable + 2 × la hauteur du joueur | 0 sommet | décor lointain posé au cœur de la carte |
| Mesh de corps d'ennemi dans le décor | 0 | drone de décor = drone ennemi |
| Décor lointain annoncé visible | visible depuis la zone de jeu | base invisible derrière un rebord |
| Particules qui projettent une ombre | 0 | — |
| Retouches de l'humain | poses strictement identiques avant/après chaque passe | objets déplacés à la main écrasés |

## Circulation et combat
| Contrôle | Cible | Pourquoi |
|---|---|---|
| Couloirs principaux | ≥ 6 diamètres de joueur (visé 8–15 pour 2–6 joueurs) | rue bouchée à un diamètre |
| Pincements **obligés** (aucun détour ≤ 2 s de sprint) | 0 sous 3,5 diamètres de joueur | 47 annoncés, majorité de recoins |
| Recoins, creux de massif, portes | listés en information, pas en défaut | faux positifs |
| Dans un îlot de pièces | se touchent (≤ 0,6 diamètre) ou s'écartent (≥ 3,5 diamètres), jamais entre les deux | fentes d'un diamètre |
| Connexité depuis l'entrée | ≥ 97 % du sol libre | — |
| Poches inaccessibles à l'air libre | 0 | 2 poches |
| Obstruction des zones « qui coupent la vue » | cible de la spec (ex. ≥ 50 % à 16 × la hauteur du joueur) | décharge à 29 % |
| Couverts sur zones de combat ouvertes | présents à portée d'engagement | esplanade vide |
| Trous/dangers près de l'objectif, de l'entrée, des goulets | 0 | — |

## Budget
| Contrôle | Cible |
|---|---|
| Renderers actifs | sous le plafond du projet ; fusionner le décor répétitif plutôt que relever le plafond |
| Lumières actives | sous le plafond du projet (intérieur : ≤ 1 par cellule de grille) |
| Décor instancié au runtime | 0 sauf décision explicite |

## Captures
| Contrôle | Cible |
|---|---|
| Luminance moyenne par capture | 60–160 / 255 |
| Pixels > 250 | < 5 % (vues de liquide, neige, émissifs) |
| Étanchéité (intérieur, fond magenta) | 0 pixel magenta depuis chaque point de contrôle |

## Pièges d'audit
- **L'audit ment s'il est calculé ailleurs.** Un harnais hors moteur (boîtes de catalogue,
  bounds de renderers) n'est pas les colliders réels : bâtiments creux, murs réels en retrait
  jusqu'à ~2 hauteurs de joueur. Annoncer les chiffres de l'audit joué **dans le moteur** ;
  pour trier vrai défaut et faux positif, rejouer sur les colliders de la scène.
- Un collider non convexe est creux : une sphère posée dedans ne le touche pas. Tester par un
  rayon qui traverse la paroi.
- Les bounds d'un plan tourné trompent sur sa taille réelle ; ceux d'un objet fusionné
  (renderers désactivés) sont vides : mesurer par les maillages.
- Compter une alerte depuis le début de la session seulement, pas sur tout l'historique.
- Mesurer l'existant **avant** de chiffrer une cible ; si deux règles de l'humain divergent
  (écart d'un facteur 3 constaté), demander.
