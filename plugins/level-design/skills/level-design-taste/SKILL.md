---
name: level-design-taste
description: Goût anti-défauts pour le level design 3D — arène, map, biome, salle, couloir, niveau, blockout, habillage ou éclairage d'une scène jouable. Lire le brief, régler quatre curseurs, bannir les réflexes de l'IA (contour carré, sol en dalles, props saupoudrés, tapis de lampes, arc-en-ciel de teintes) et passer une checklist pre-flight mesurable avant de montrer. Utiliser dès qu'il faut concevoir, construire, habiller, éclairer, critiquer ou faire évoluer un niveau, même si les mots « level design » ne sont jamais prononcés.
---

# Level design 3D — le goût, écrit

> Arènes, maps extérieures, salles et couloirs intérieurs, nouvelles versions d'un niveau
> existant. Pas les menus, pas l'UI, pas le code de gameplay.
> Chaque règle ci-dessous est **contextuelle** : on lit d'abord le brief, puis on ne tire que
> ce qui s'applique.

Un LLM qui construit une scène 3D a des réflexes : contour rectangulaire, sol plat pavé,
props saupoudrés uniformément, une lampe partout, six teintes qui crient, un centre vide, et
« livré » dès que le script tourne sans erreur. Ce skill existe pour les casser.

**Hiérarchie des sources, toujours** : canon du projet `[USER]` > extensions du projet
(`.claude/level-design/index.md` et les fichiers qu'il cite) > spec du niveau > ce skill >
références mesurées (démos du pack d'assets) > ton intuition.

**Avant d'appliquer quoi que ce soit ici** :
1. Si `.claude/level-design/index.md` existe, lis-le, puis ses sections `Contexte`,
   `Attentes`, `Toujours lire` et celle du type de scène en cours (grammaire :
   `level-design-build/references/extensions.md`). Ses règles complètent et remplacent les
   tiennes.
2. Si le projet tient un canon (`.claude/canon/`), lis ses entrées sur le décor, la
   lumière, la couleur, les maps. Les chiffres de ce skill sont des **valeurs de départ**
mesurées sur un projet réel : le canon du projet les remplace dès qu'il en fixe d'autres.

Références à charger selon le cas :

| On travaille sur… | Lire en plus |
|---|---|
| Une arène ou une map extérieure | [references/exterieur.md](references/exterieur.md) |
| Une salle, un couloir, un intérieur | [references/interieur.md](references/interieur.md) |
| Lumière, fog, couleur, densité, profondeur (toujours utile) | [references/rendu.md](references/rendu.md) |
| Un audit automatique à écrire ou à lire | [references/audits.md](references/audits.md) |
| Les règles propres au projet | `.claude/level-design/index.md` du projet, s'il existe |

Pour la **procédure** (spec, questions, passe de construction, captures, livraison), c'est le
skill `level-design-build`. Pour **juger** des captures, l'agent `level-design-reviewer`.

---

## 0. LECTURE DU BRIEF (avant tout)

### 0.A Les signaux à lire d'abord
1. **Type de scène** — arène de combat, arène de défense, traversée, hub, salle, couloir,
   niveau linéaire, nouvelle version d'une scène existante.
2. **Joueurs** — combien (solo, coop 2–6, PvP), comment ils bougent (marche, sprint, saut,
   véhicule, vol), leur gabarit **mesuré** (hauteur, rayon, vitesse). Toute échelle en découle.
3. **Ennemis** — d'où ils viennent, combien au maximum, à quelle portée ils tirent. La
   portée d'engagement fixe la distance entre couverts.
4. **Mots d'ambiance** — « désolé », « industriel », « vivant », « oppressant », « aéré »,
   « planète hostile », « station propre », « bricolé ».
5. **Références** — une scène démo du pack d'assets, un jeu cité, un croquis, un plan
   d'intention donné par l'humain. Un plan d'intention de l'humain est le point de départ,
   pas une suggestion.
6. **Contraintes silencieuses** — budget de rendu, plateforme, réseau (ce qui doit être
   répliqué), sauvegarde, IDs référencés par le code. Elles priment sur l'esthétique.

### 0.B Écrire une « Lecture du niveau » en une ligne, avant de produire
> **« Je lis ça comme : \<type de scène> pour \<joueurs / mode>, dans une ambiance
> \<mots>, en m'appuyant sur \<référence mesurée>. Curseurs O/D/R/N = x/x/x/x. »**

Exemples :
- *« Je lis ça comme : arène de défense coop 2–6 joueurs autour d'un objet à protéger, dans
  une ambiance planète minière désolée, en m'appuyant sur la démo désert du pack. Curseurs
  O/D/R/N = 7/4/6/8. »*
- *« Je lis ça comme : couloir de station entre deux salles de combat, ambiance propre et
  froide, en m'appuyant sur la démo intérieur du pack. Curseurs O/D/R/N = 2/5/2/1. »*

### 0.C Brief ambigu : une question, pas un questionnaire
Si la lecture diverge vraiment (arène ouverte ou vallée cloisonnée ?), pose **une** question
avec options (a)/(b)/(c) et ta recommandation en premier. Si tu peux inférer, n'interroge
pas : déclare la lecture et avance. Les grandes séries de questions appartiennent à la spec
(skill `level-design-build`), pas à la conversation.

### 0.D Discipline anti-défaut
Ne pars **jamais** de : rectangle, sol plat, grille de couverts, lampe à chaque pas,
palette arc-en-ciel, centre vide, décor copié tel quel de la démo. Ce sont les réflexes du
modèle. Écarte-les délibérément à partir de la lecture du niveau.

---

## 1. LES QUATRE CURSEURS

Après la lecture, fixe quatre curseurs. Chaque décision de forme, de densité et de relief
ci-dessous en dépend. Ne les invente pas sous d'autres noms.

* **`OUVERTURE`** — 1 = couloir scripté, une seule route · 10 = arène ouverte, toutes
  directions.
* **`DENSITE`** — 1 = sol nu, respiration maximale · 10 = encombré, couvert partout.
* **`RELIEF`** — 1 = plat · 10 = verticalité forte (crêtes, niveaux superposés, gouffres).
* **`NATURE`** — 1 = bâti orthogonal sur grille · 10 = organique, rien d'aplomb.

Pas de valeur par défaut universelle : un niveau de station et une arène de planète n'ont
rien en commun. Pars du preset le plus proche, puis ajuste.

### 1.A Des mots d'ambiance aux curseurs
| Signal | OUVERTURE | DENSITE | RELIEF | NATURE |
|---|---|---|---|---|
| « aéré / hangar / grand espace » | 7–9 | 2–3 | 2–4 | selon le lieu |
| « oppressant / étouffant / labyrinthe » | 2–4 | 6–8 | 3–5 | selon le lieu |
| « désolé / planète hostile / friche » | 7–8 | 3–4 | 6–8 | 8–9 |
| « industriel / usine / raffinerie » | 5–6 | 5–7 | 4–6 | 3–4 |
| « bricolé / camp / colonie » | 6 | 5–6 | 4–5 | 5–6 |
| « station propre / vaisseau » | 2–3 | 4–5 | 2 | 1–2 |
| « vivant / animé » | ne change pas les curseurs : décor vivant **hors** zone jouable (§3.F) |

### 1.B Presets par type de scène
| Type de scène | OUVERTURE | DENSITE | RELIEF | NATURE |
|---|---|---|---|---|
| Arène de défense (objet à protéger) | 7 | 4 | 5 | selon biome |
| Arène de combat (vagues, pas d'objet) | 8 | 5 | 6 | selon biome |
| Traversée / exploration | 4 | 3 | 7 | 8 |
| Hub, zone sociale | 6 | 3 | 2 | 3 |
| Couloir d'intérieur | 1–2 | 4 | 1 | 1 |
| Salle de combat intérieure | 4 | 6 | 3 | 2 |
| Nouvelle version — retouches | = existant | = existant | = existant | = existant |
| Nouvelle version — refonte | à rediscuter avec l'humain | | | |

### 1.C Ce que chaque curseur pilote
- **OUVERTURE** → forme du contour, nombre de routes entre deux points, longueur des lignes
  de vue, largeur des goulets.
- **DENSITE** → props par m², part de sol nu dans le cadre, distance entre couverts,
  obstruction mesurée des zones « qui coupent la vue ».
- **RELIEF** → amplitude du terrain, part de pentes > 10°, nombre de niveaux praticables,
  nombre de dangers de chute.
- **NATURE** → part de placement libre contre placement sur grille, bascule et enfoncement
  des pièces organiques, courbure des bords.

---

## 2. LES DEUX GRAMMAIRES DE PLACEMENT

L'œil distingue l'artificiel du naturel **avant** de lire les formes. Deux grammaires, qui
ne se mélangent jamais sur un même objet :

- **Structure** (murs, sols, plafonds, bâtiments, modules) — sur la grille du projet,
  rotation par pas de 90°, échelle exactement 1, pivots sur la grille. Conformité visée
  ≥ 99 %, exceptions nommées.
- **Habillage et nature** (props, roches, végétation, débris) — hors grille, lacet libre,
  échelle par paliers (≈ 3 tailles par espèce, pas en continu), miroir autorisé.
  **Rien d'organique n'est d'aplomb** : roches basculées, écrasées, enfoncées.
- **Bâti dans un monde libre** : poser le bâti sur une embase ou une plateforme qui règle
  les raccords, jamais un module collé sur une pente. La jonction sol/bâti se cache par des
  débris semés sur la frontière et par l'ombre, pas par de la maçonnerie en plus.
- **Répétition avec variation motivée** : un run de murs est uniforme ; une variante entre
  en **grappe** à un endroit justifié (baie technique, accès, focal). Jamais d'alternance
  mécanique A/B/A/B. Un « beat » : 3–5 éléments rythmés, un seul différent.
- **Pièce remarquable en un exemplaire.** 2–4 pour une fonction doublée. Au-delà, c'est du
  sol, pas un repère.

---

## 3. DIRECTIVES (correction des biais)

### 3.A Forme et contour
- Une aire n'est pas une forme. « N × N modules » donne une **surface** ; le contour est
  **organique** : lobes, anses, goulets, isthmes. Plus long bord rectiligne ≤ ~24 × la hauteur
  du joueur.
- Les limites se lisent comme du **relief ou de l'architecture** (talus, falaise, surplomb,
  cuvette), jamais comme un mur invisible seul ni un contour géométrique. Poser la zone
  jouable dans une dépression aide.
- Une partie de l'emprise peut rester non jouable (transition, vue) si elle se lit comme
  telle.

### 3.B Sol et relief
- **Jamais « tout repose sur des dalles ».** Sol continu et organique ; les plateaux de
  gameplay sont taillés dans le sol, sans marche visible (écart sous la hauteur de pas du contrôleur).
- Jamais plat partout : base de bruit (Perlin ou équivalent), puis on **aplatit ce qui doit
  l'être** (liquides, zones bâties, places). Ajouter le relief **après** les plateaux, sinon
  leurs fondus l'effacent.
- L'IA sur-aplatit : compter la part de sol aplati. Si les plateaux mangent la plaine, le
  relief a disparu.
- Pente jouable : ≥ 99 % du sol praticable sous la pente max du contrôleur ; le relief doit
  pourtant **se lire** (part de pentes > 10° mesurée, voir `references/audits.md`).

### 3.C Bords, chutes, liquides
- Gouffres, lacs, fosses : **peu de pièces**, pièces courbes au bord, en **chaîne** qui se
  recouvre, et le sol modifié **sous** la chaîne. Jamais de pièces isolées posées sur un
  sol qu'on ne touche pas.
- Pièce de falaise courbe = bord de gouffre ou de ravin. Nulle part ailleurs.
- Zéro trou de rive, zéro pierre flottante : ça se **mesure** (rayons), ça ne se juge pas.
- Toute chute a une conséquence décidée par l'humain (mort, repêchage, pénalité) et un
  filet sous **chaque** chute. Un seuil de chute se signale par la **forme** (chevrons,
  tranche) ou une couleur au rôle « danger », jamais par la couleur « interactif ».

### 3.D Composition
- **Un seul point focal par champ de vision.** Deux choses qui crient, c'est aucune.
- Props en **grappes qui racontent une fonction** (3–5 objets serrés : poste de réparation,
  campement, stock). Saupoudrés, ils sont du bruit. Visé : ≈ 90 % des props en grappes.
- **Le centre respire, les grappes s'adossent aux bords.** Le vide autour du focal est
  voulu. Mais attention au contraire : un centre à découvert sans couvert est un
  « stand de tir ».
- **Plans de profondeur** : premier plan, milieu, lointain en silhouette. Voir
  `references/rendu.md` pour les mécanismes (coquilles, fog, répétition à distance).
- **Logique du lieu** : le décor raconte quelque chose (les canons côté base, la foreuse sur
  la fosse, les tuyaux vers la pompe). Un réseau (tuyaux, câbles, rails) n'a **aucun bout
  libre** : chaque extrémité aboutit à un mur, une cuve, le sol ou un coude.

### 3.E Couleur et lumière (résumé, détail dans `references/rendu.md`)
- **Budget couleur** : 1 dominante + 1 complémentaire + 2 accents au maximum. Au-delà, défaut.
- **Une couleur = un rôle** et un seul (ex. rouge = danger/ennemi, cyan = interactif). Le
  plan de circulation reste calme ; les grands aplats colorés vont au loin ou en hauteur.
- **L'objectif est le seul point chaud** de couleur de la scène.
- **Hiérarchie lumineuse** : l'ambiance éclaire, quelques sources guident. Pas de tapis de
  lampes. Un émissif n'éclaire rien : il se lit comme un trait.
- **Pas de blanc écrêté** ; luminance mesurée sur capture, pas estimée.
- **Les couleurs d'une démo ne sont pas une recette** : elles se valident avec l'humain.

### 3.F Décor lointain et décor vivant
- Le hors-carte est **vivant** (véhicules, vaisseaux, machines, débris) mais **n'empiète
  jamais** sur la zone jouable : aucun sommet dans l'enveloppe jouable + marge.
- Ce qui est annoncé visible (une base, un repère) **se voit** depuis la zone de jeu, pas
  derrière un rebord ni noyé dans le fog.
- Le décor vivant ne vole jamais la caméra, ne tire pas sur les joueurs, n'est pas exploité
  par les ennemis. S'il devient gameplay, il change de statut (réplication, règles).
- **Aucun modèle qu'on joue comme ennemi n'est posé en décor.** Confusion garantie en jeu.

### 3.G Circulation et combat
- On comprend **où circuler, où se couvrir, d'où viennent les ennemis**, sans panneau.
- Largeur des passages dérivée du gabarit et du nombre de joueurs : pour 2–6 joueurs, couloirs
  principaux 8–15 diamètres de joueur, jamais < 6. Un pincement n'est un défaut que si on est
  **obligé** d'y passer (pas de détour court).
- Couverts **à portée d'engagement** des ennemis sur toute zone de combat ouverte ; 2–3
  grappes de couverts près de l'objectif.
- Pas de trou ni de danger près de l'objectif, de l'entrée, des goulets.
- L'objectif se reconnaît **de loin et depuis l'entrée** (ordre de grandeur : 5–7 × la
  hauteur du joueur).
- Chaque zone a **un nom court et un repère visible** : on doit pouvoir s'orienter à la voix
  en coop (« à la foreuse », « côté lac »).

### 3.H Échelle
- Toute cote se dérive du gabarit joueur **mesuré** (hauteur, rayon, saut, vitesse). Une
  traversée se chiffre en secondes de course, pas seulement en unités de longueur.
- Donner l'échelle du monde : un prop connu agrandi au loin, des objets moyens sur les
  crêtes, **un seul** élément vertical par quartier.
- Juger une scène de jeu au FOV de jeu (55–65), jamais au FOV poster.

---

## 4. TICS DE L'IA (interdits sauf demande explicite)

### 4.A Forme
* **PAS de contour carré ou rectangulaire** lisible en plongée.
* **PAS de sol plat partout**, ni de sol pavé de dalles.
* **PAS de plateaux plats sous chaque emplacement** de gameplay (la plaine disparaît).
* **PAS de mur invisible seul** comme limite.
* **PAS de symétrie parfaite** d'une arène, sauf mode compétitif qui l'exige.

### 4.B Placement
* **PAS de props saupoudrés** uniformément ; pas de caisse isolée au milieu d'une allée.
* **PAS de couverts alignés en grille** régulière.
* **PAS d'élément organique d'aplomb** (roche droite, arbre vertical parfait en série).
* **PAS de pièce qui flotte**, qui s'interpénètre sans raison ou qui s'arrête dans le vide
  (escalier, pont, tuyau, bord de sol).
* **PAS de pièce étirée** : on n'étire jamais un détail, un biseau ou un motif ; seules les
  bandes plates conçues pour ça s'étirent.
* **PAS de porte ou fenêtre en bout libre de mur**, dans un angle, ou contre un seul mur.
* **PAS d'empilement de deux murs complets** pour faire un mur haut : socle + n × fût + tête.
* **PAS de réseau à bouts libres** (tuyau, câble, rail qui s'arrête dans le vide).

### 4.C Rendu
* **PAS de tapis de lampes** : l'ambiance éclaire, les lampes guident.
* **PAS d'émissif qui écrête** au blanc ; pas de néon fait avec des lumières.
* **PAS de palette arc-en-ciel** : compter les teintes.
* **PAS de couleur à deux rôles** (le rouge « danger » ne décore pas).
* **PAS de couleurs de démo recopiées** sans validation de l'humain.
* **PAS de matériau d'un autre biome** laissé par défaut sur une pièce.
* **PAS de ciel spectaculaire** qui tue les silhouettes.

### 4.D Contenu et lisibilité
* **PAS de numéros, d'étiquettes ou de lignes de danger** au sol que l'humain n'a pas
  demandés.
* **PAS de modèle d'ennemi en décor.**
* **PAS de décor lointain qui empiète** sur la zone jouable ou qui écrase le cadre.
* **PAS de végétation exotique en masse** hors du biome ; compter les essences.
* **PAS de hors-carte pauvre** : comparer la densité du fond à la référence mesurée.

### 4.E Procédé
* **PAS de pose à la main** d'une pièce qu'une passe scriptée devrait poser.
* **PAS de « livré » sur la foi d'un script qui tourne** ou d'un audit vert : captures
  jugées + revue + jeu.
* **PAS d'impression chiffrée** (« ~600 plantes ») : un chiffre sans compte n'en est pas un.
* **PAS de retouche de l'humain écrasée**, jamais.

---

## 5. VOCABULAIRE (les noms à connaître)

Un vocabulaire, pas une bibliothèque. Sers-t'en pour parler juste et pour choisir.

- **Forme** : emprise, enveloppe, contour organique, lobe, anse, goulet, isthme, cuvette,
  butte, crête, terrasse, éperon, lèvre, talus, gorge, gouffre, puits, ravin, pont naturel.
- **Structure du niveau** : chemin critique, hub & spoke, boucle de retour (loop-back),
  gating, lock & key, secteurs, zonation, arène, choke point, pinch point, allée,
  « stand de tir » (anti-pattern), poche fermée, connexité.
- **Guidage** : weenie (repère lointain qui attire), breadcrumbing, vista, amorce, contre-
  jour, figure en V, seuil, arche, ligne de vue hachée, repère d'orientation.
- **Combat** : couvert statique / mobile, grappe de couverts, portée d'engagement, ligne de
  tir, flanc, point de repli, ancre d'apparition, exclusion de spawn, télégraphe, préavis.
- **Chutes** : seuil, chevrons, filet de repêchage, point sûr, plancher anti-évasion.
- **Assemblage** : greybox / blockout, habillage (dressing), module, slot, grille, pivot,
  couture, embout, insert, socle / fût / tête, run, variante, raccord, couvre-joint.
- **Rendu** : ambiance trois couleurs, key / fill / kicker, flaque de lumière, budget
  couleur, dominante, accent, rôle sémantique, émission, bloom, écrêtage, luminance, fog
  accordé au ciel, coquilles de distance, silhouette, parallaxe.

---

## 6. NOUVELLE VERSION D'UN NIVEAU EXISTANT

Mal classer le mode est la première source de mauvaise nouvelle version.

### 6.A Détecter le mode (première action)
* **Retouches** — l'humain s'est promené et liste ce qui le dérange. On corrige ces points,
  rien d'autre.
* **Nouvelle version** — même lieu, même intention, défauts de fond à reprendre.
* **Refonte** — nouvelle forme ou nouvelle intention : c'est un nouveau niveau (spec neuve).

Ambigu → une question : *« On corrige ces points, ou on reprend la forme ? »*

### 6.B Auditer avant de toucher
* Rejouer l'audit automatique et les captures fixes de la version actuelle : c'est le point
  de départ chiffré.
* Lister les défauts de la version précédente **vérifiés** (image ou mesure), puis les
  classer : corrigés, partiels, toujours présents, nouveaux.
* Relire le canon depuis la dernière version livrée : les retours de l'humain y sont.

### 6.C Ce qui ne change jamais en silence
Sans accord explicite de l'humain, on ne modifie pas :
* **ses retouches à la main** (détectées par empreinte ; la passe les préserve et les nomme) ;
* les points d'entrée, d'apparition, l'objectif et les points sûrs ;
* les noms et IDs d'objets référencés par le code ou la sauvegarde ;
* l'ordre des listes qui entrent dans un tirage à graine (ajout en fin seulement) ;
* l'aire et le contrat d'échelle décidés ;
* le statut réseau d'un élément (décor local ↔ gameplay répliqué).

### 6.D Leviers de correction, par ordre
Arrête-toi dès que les retours sont traités :
1. **Construction** — flottants, trous, raccords, bouts libres (bloquants).
2. **Lisibilité** — focal unique, objectif visible, orientation, danger lisible.
3. **Lumière et couleur** — budget couleur, hiérarchie lumineuse, luminance.
4. **Composition** — grappes, respiration, plans de profondeur, hors-carte.
5. **Forme** — contour, relief, routes : le plus cher, en dernier, et seulement si le mode
   l'autorise.

---

## 7. HORS PÉRIMÈTRE

Ce skill n'est pas pour : les menus et HUD, l'équilibrage chiffré des ennemis, le code
réseau, la cinématique pure (une séquence scriptée n'est pas un niveau). Si le brief en est
un, **dis-le** et n'applique ce skill qu'aux parties spatiales.

---

## 8. PRE-FLIGHT (avant de montrer quoi que ce soit)

**Pas optionnel.** Chaque case se coche honnêtement ou le niveau n'est pas prêt. Ce qui n'a
pas pu être vérifié est **annoncé** comme tel, jamais coché.

- [ ] **Lecture du niveau** déclarée (§0.B), curseurs chiffrés et justifiés ?
- [ ] **Canon du projet** et **extensions** (`.claude/level-design/`) relus ; aucune entrée
      `[USER]` violée ? La checklist du projet, si l'index en cite une, est passée aussi ?
- [ ] **Contour** : plus long bord rectiligne ≤ ~24 × la hauteur du joueur, aucune forme
      géométrique en plongée ?
- [ ] **Sol** : continu, pas de dalles visibles, marche aux bords de plateaux sous la hauteur
      de pas du contrôleur ?
- [ ] **Relief lisible** : part de pentes > 10° mesurée et conforme à `RELIEF` ?
- [ ] **Aplatissement** : la part de sol aplati est mesurée et ne mange pas la plaine ?
- [ ] **Flottants = 0** (test sur le sommet le plus bas de chaque pièce) ?
- [ ] **Trous de rive = 0** (rayons tout autour de chaque liquide/gouffre) ?
- [ ] **Filet sous chaque chute** : 100 % ?
- [ ] **Réseaux** : 0 bout libre (tuyaux, câbles, rails) ?
- [ ] **Hors-carte** : 0 sommet dans l'enveloppe jouable + marge ; le lointain annoncé se voit ?
- [ ] **Aucun modèle d'ennemi** dans le décor ?
- [ ] **Matériaux** : 0 matériau d'un autre biome, 0 matériau refusé par le canon ?
- [ ] **Focal unique** dans chaque capture fixe ?
- [ ] **Objectif** identifiable depuis l'entrée et en plongée ?
- [ ] **Budget couleur** : teintes comptées ≤ 1 + 1 + 2, chaque accent a un seul rôle ?
- [ ] **Luminance** de chaque capture dans la cible (défaut 60–160), pixels écrêtés < 5 % ?
- [ ] **Lumières** : nombre ≤ budget, hiérarchie ambiance → guides → focal ?
- [ ] **Grappes** : ≈ 90 % des props groupés, aucune caisse isolée dans une allée ?
- [ ] **Circulation** : connexité depuis l'entrée ≥ 97 %, 0 poche inaccessible, 0 pincement
      obligé sous la largeur minimale ?
- [ ] **Couverts** à portée d'engagement sur chaque zone de combat ouverte ?
- [ ] **Orientation** : chaque zone a un nom court et un repère visible ?
- [ ] **Budget** : renderers et lumières actives sous les plafonds du projet ?
- [ ] **Idempotence** : la passe rejouée annonce « rien à faire » ?
- [ ] **Retouches de l'humain** : strictement identiques avant/après la passe ?
- [ ] **Captures fixes** prises dans un seul état de la scène, depuis des caméras nommées ?
- [ ] **Revue indépendante** (`level-design-reviewer`) faite, et ses bloquants traités ?
- [ ] **Joué** : on tient debout sur chaque surface, chaque chute a été testée ?
- [ ] **Livraison honnête** prête : mesuré, restant, non vérifié ?

Si une case ne peut pas être cochée honnêtement, le niveau n'est pas prêt. Corrige avant de
montrer, ou annonce-le.

---

## Garde-fous

- Le canon `[USER]` du projet bat ce skill, toujours. Conflit → signalé, jamais tranché seul.
- Une valeur de ce skill non confirmée par le projet reste un défaut de départ : ne la grave
  pas dans le canon comme exigence de l'humain.
- Chaque leçon nouvelle (défaut vécu, refus de l'humain) se capture dans le canon du projet
  avec sa provenance, via le skill `canon-tracker` s'il est installé.
- Ce skill ne nomme aucun moteur ni pack d'assets : leurs pièges vivent dans le canon du
  projet et dans `level-design-build/references/pieges.md` sous forme générique.
