# Rendu : lumière, fog, couleur, densité, profondeur

Valeurs **de départ**, mesurées sur six scènes de référence d'un pack d'assets low-poly
stylisé, puis confrontées aux retours d'un humain. Le canon du projet les remplace dès qu'il
en fixe d'autres. Un style réaliste (PBR, GI calculée) déplace les chiffres, pas les
principes.

## Lumière

- **L'ambiance est la source principale.** Une ambiance trois couleurs (ciel / équateur /
  sol) fait office de GI : ciel chaud désaturé, équateur bleu franc, sol quasi noir teinté.
  Test : une zone à l'ombre vire au bleu nuit **sans** lumière d'appoint.
- **Anti-défaut n°1 : remplacer l'ambiance par des lampes.** Référence mesurée : 84 lampes
  sur une scène ; la version IA en avait posé 1 025 sur la même aire.
- **Hiérarchie** : ambiance → quelques guides → **un** focal. Le focal est la seule lampe
  teintée qui porte une ombre douce, ≈ 2 × l'intensité des guides.
- **Ombres** sur ≤ 20 % des lumières.
- **Un émissif n'éclaire rien** en temps réel : ne jamais compter dessus pour déboucher une
  zone. Les luminaires sont des meshes émissifs, pas des lampes.
- Les lumières vivent sous une racine dédiée, désactivable d'un clic.
- Détail intérieur et extérieur : [interieur.md](interieur.md), [exterieur.md](exterieur.md).

## Émissif, bloom, étalonnage

- Sans tonemapping, tout émissif > 1,0 sature au blanc : **plafond LDR à 1,0**.
- **Le néon vient du bloom**, pas des lumières : seuil 0,5–0,7, intensité 1,0–1,5 ; seuil
  ~0,85 quand la luminance doit rester sous contrôle (neige, liquide, acide).
- **L'intensité émissive est un levier narratif** :
  - ×1 partout = installation propre ;
  - ×2 sur 2–3 familles = équipement actif ;
  - ×6 sur **une** famille = LE point chaud ;
  - ×2–6 partout = bazar assumé (rarement voulu).
- Écrans et hologrammes : surfaces transparentes (alpha 0,03–0,5), non émissives ; le bloom
  fait le reste. Le verre ne brille jamais.
- Un effet fin (laser, trait) tire son éclat de sa **forme** (halo autour d'un cœur), jamais
  d'une luminosité qui sature.
- **Post-process : 4 à 6 réglages, toujours les mêmes** — bloom ; contraste +8…+15 ;
  saturation +5…+12 ; ombres baissées et chaudes, tons moyens remontés et froids ; vignette
  0,4–0,5. Pas de profondeur de champ, de grain, d'aberration chromatique ni de flou de
  mouvement par défaut.
- **Mesures sur capture** : luminance moyenne 60–160 / 255 ; pixels > 250 < 5 % (0 % hors
  émissifs voulus). On règle la lumière **d'après la mesure**, pas au jugé.
- Surface réfléchissante (sol lisse, liquide) : prévoir le reflet de la key. Une « traînée
  blanche » au sol est souvent un spéculaire de key rasante sur un sol trop lisse.

## Fog et ciel

- **Fog accordé au ciel** : couleur ≈ 0,7 × la couleur du bas du ciel, sinon l'horizon
  montre une couture.
- Extérieur : fog linéaire, fin = distance du dernier plan lisible (fixée par la taille de
  la map). Rien d'important au-delà de 0,7 × la fin du fog.
- Intérieur : fog exponentiel noir, densité faible, mesurée sur la référence du projet.
- Les astres ignorent le fog : seule chose nette au loin, ils créent la distance. Corps
  célestes loin au-delà du dernier plan de décor (mesuré sur la référence) contre la
  parallaxe ; 10–15° de diamètre apparent ; jamais tangents à une arête du décor.
- Brume au sol = particules additives, pas le fog.
- **Un ciel spectaculaire tue les silhouettes** : le ciel sert le premier plan.

## Couleur

- **Budget : 1 dominante quasi monochrome + 1 complémentaire + 2 accents au maximum.**
  Compter : 6 teintes sur une scène = défaut constaté.
- **Un accent = un rôle.** Exemple de charte : cyan = interactif / ce qui s'ouvre ; rouge =
  danger / ennemi / périmètre ; ambre = aplat structurel, jamais lumineux. Un bord de vide
  ne se marque pas avec la couleur « interactif ».
- **Un seul focal saturé par champ de vision**, plus un contre-accent minuscule. Dans une
  scène froide, une seule note chaude, et grosse (ou l'inverse).
- La variété chromatique est dans **l'albédo**, pas dans l'éclairage.
- Grands aplats colorés au loin ou en hauteur ; **le plan de circulation reste calme**.
- Un signal de danger de la teinte du sol ne se lit pas : changer de teinte ou de forme.
- Un sombre saturé (violet, bleu nuit) placé dans une ombre bleue ne renvoie rien et rend
  la vue illisible : éclaircir. Vérifier la lisibilité **à l'ombre** (luminance de zone
  ≥ ~30).
- Toute la roche d'un biome = **une** famille de matériau validée par l'humain.
- Budget matériaux : 23–46 par scène ; une page d'atlas porte la majorité des objets. Le
  relief est dans le chanfrein du mesh, pas dans la normal map.

## Densité et grappes

- Intérieur : props par cellule de grille mesurés sur la référence. Répartition verticale
  (× hauteur du joueur) : 60 % sous 0,25, 25 % entre 0,25 et 0,65, 7 % entre 0,65 et 1,3,
  9 % au-dessus (tuyaux, luminaires).
- ≈ 89 % des props en grappes ; ≤ 11 % sans voisin à moins de ≈ 1,2 × la hauteur du
  joueur. Plus proche voisin : médiane ≈ 1,2 × la hauteur du joueur.
- **Rayon d'une grappe par rôle** : (× hauteur du joueur) : thématique 2–4 (3–5 objets qui
  racontent une fonction) ; générique 15–22 ; parallaxe : échelle du hors-carte.
- Grappe végétale type (rayon ≈ 2 × la hauteur du joueur, 4 espèces) : 1 grande + 2–3 moyennes
  + 4–8 couvre-sol, au pied d'une roche.
- Distance au mur : médiane ≈ 1,2 × la hauteur du joueur, 35 % à moins d'une hauteur.
  Grappes adossées, centre libre sauf pour LE focal.
- Extérieur : le **sol nu occupe ≈ 55 % du cadre**. C'est la respiration.
- **Gradient de densité aligné sur le fog** (relatif au premier plan, référence) : 100 % ;
  ≈ 11 % ; ≈ 7 % ; ≈ 2 % ; ≈ 0,25 % au dernier plan lisible ; puis grandes masses seules.
  Bornes des bandes et densité absolue mesurées sur la référence du projet.
- Répétition : ≈ 10 familles répétées 20–140 fois font le « sol » ; bâtiment remarquable en
  **un** exemplaire ; 8–12 variantes de détail posées 1–5 fois chacune.
- Presets riches (17–44 objets) construits 2–3 fois puis dupliqués le long d'un axe.

## Plans de profondeur (à cumuler)

- **3 coquilles de distance**, population ≈ 5 : 2 : 1.
- **4 étages de contraste** (part de la fin du fog) : net 0–8 %, moyen 8–30 %, grisé
  30–60 %, fantôme 60–100 %.
- **Étagement des valeurs**, trois bandes qui ne se croisent pas :
  - diurne : bas sombre / milieu contrasté / haut clair ;
  - nocturne ou intérieur : bas le plus clair / milieu lisible / haut en silhouettes (guide
    l'œil vers la zone jouable).
- Le même prop géant répété à 3–7 distances dans l'axe de vue (le fog masque la répétition) ;
  une exception à échelle 1, avec ses accessoires, fait le point d'intérêt.
- **Occultation** : un plan moyen devant la source lumineuse. **Amorce** : un objet
  partiellement hors cadre au premier plan.
- **Contre-jour** : la composition la plus forte, elle ne coûte qu'un placement de caméra.
- **Figure en V** : deux masses convergent vers un jalon lointain, le fog remplit le V.
- Skyline rapide : un même élément agrandi ×2,5 posé 20–60 × la hauteur du joueur au-delà
  de la limite et 12–20 × en hauteur.
- **Hacher les lignes de vue** : un seuil ou une arche tous les 2–3 modules ; une vue longue
  reste permise si elle traverse 2–3 seuils et se noie dans le fog.

## Échelle

- Ratio de silhouettes (grand paysage) ≈ 1 : 20 : 100 : 250.
- Un prop iconique agrandi ×10 au loin donne l'échelle du monde ; des objets moyens sur les
  crêtes donnent celle des collines.
- **Un seul** objet vertical résume un quartier ; la retenue (peu de détails lumineux) rend
  la hauteur crédible.
- Un événement spectaculaire peut naître d'un seul détail agrandi (×9) plutôt que d'un
  modèle neuf.
- FOV : 55–65 en jeu ; 38 téléobjectif ; 25–30 poster ; 84 monumental. On juge au FOV de jeu.
