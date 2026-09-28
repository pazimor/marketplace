# Grammaire formelle — canon et roadmap

Ce document **décrit** la grammaire que définissent les deux skills du plugin `roadmap`.
Il n'en invente aucune variante : les SKILL.md restent seuls propriétaires de la grammaire
(`CANON:3`). En cas d'écart entre ce document et un SKILL.md, le SKILL.md fait foi et ce
document est à corriger.

- Canon : `plugins/roadmap/skills/canon-tracker/SKILL.md`, § « Où vit le canon »,
  § « Grammaire d'une entrée », § « Provenance », § « Opérations courantes ».
- Roadmap : `plugins/roadmap/skills/roadmap-tracker/SKILL.md`, § « Où vit la roadmap »,
  § « Grammaire du fichier » (bloc « Structure du fichier » + « Conventions »),
  § « Opérations courantes ».

Le validateur exécutable est `scripts/validate.py` (python3 stdlib, aucune dépendance,
aucun appel réseau) :

```sh
python3 scripts/validate.py [RACINE] [--strict]     # RACINE par défaut : .
python3 -m unittest discover -s scripts/tests -v    # tests du validateur
```

Sortie : une ligne par constat, `ERROR|WARN <fichier>:<ligne>: [<code>] <message>`, puis un
bilan. Code de sortie `0` sans erreur, `1` avec au moins une erreur (ou un avertissement sous
`--strict`), `2` si la racine n'existe pas. Chaque partie absente (manifestes, canon,
roadmap) est simplement ignorée, ce qui rend le script utilisable sur n'importe quel projet
qui utilise le plugin.

Les colonnes **Niveau** ci-dessous distinguent ce qui viole une règle écrite dans un SKILL.md
(`ERROR`) de ce qui est seulement suspect ou relève d'une lecture non tranchée (`WARN`).

## Notation

EBNF ISO simplifiée : `=` définit, `,` concatène, `|` alterne, `[ … ]` optionnel,
`{ … }` zéro ou plus, `"…"` littéral, `? … ?` description informelle. `SP` est une espace,
`NL` une fin de ligne, `INDENT` une ou plusieurs espaces/tabulations en début de ligne.

```ebnf
digit      = "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" ;
number     = digit , { digit } ;
date       = digit , digit , digit , digit , "-" , digit , digit , "-" , digit , digit ;
             (* AAAA-MM-JJ, et une date calendaire réelle *)
text       = ? un ou plusieurs caractères, hors fin de ligne ? ;
blank-line = { SP } , NL ;
```

---

## 1. Canon — `.claude/canon/*.md`

Source : canon-tracker, § « Où vit le canon » et § « Grammaire d'une entrée ».

### 1.1 Emplacement

- Un dossier `.claude/canon/` à la racine du repo, un **thème par fichier** `*.md`
  (`attentes.md`, `conventions.md`, `tests.md`, `invariants.md`, plus tout thème
  clairement distinct).
- **Jamais de `divers.md`** (§ « Où vit le canon »).

### 1.2 Fichier

```ebnf
canon-file   = { blank-line } , title-line , { blank-line | entry | heading-line } ;
title-line   = "# " , text , NL ;                 (* « # Tests », « # Invariants »… *)
heading-line = "#" , { "#" } , SP , text , NL ;   (* toléré, cf. point ambigu A3 *)
entry        = "- " , entry-body , NL , { continuation } ;
continuation = INDENT , text , NL ;               (* ligne repliée, ou ligne « — obsolète » *)
```

Une entrée tient sur une ligne logique : la ligne `- …` et ses lignes de continuation
indentées, jointes par une espace. Une ligne vide termine l'entrée. **Toute ligne non vide
qui n'est ni un titre, ni une entrée, ni une continuation est de la prose flottante,
interdite** (« Jamais de prose flottante, jamais de paragraphe hors entrée »).

### 1.3 Entrée

```ebnf
entry-body   = live-entry | struck-entry | struck-point ;

live-entry   = head , SP , point ;
head         = "`CANON:" , number , "`" , SP , provenance ;
provenance   = "[USER:" , name , SP , date , "]"
             | "[MODEL" , SP , date , "]" ;
name         = ? texte non vide sans « ] », sans espace en tête ni en fin ? ;
point        = text , [ SP , "(promu de MODEL)" ] ;   (* promotion : USER uniquement *)

(* Dépréciation — deux lectures acceptées, cf. point ambigu A1 *)
struck-entry = "~~" , live-entry , "~~" , obsolete-tail ;          (* forme de l'exemple *)
struck-point = head , SP , "~~" , point , "~~" , obsolete-tail ;   (* « barrer le texte » *)
obsolete-tail = SP , obsolete | NL , INDENT , obsolete ;             (* fin de ligne ou dessous *)
obsolete     = "— obsolète" , SP , date , SP , ":" , SP , reason ;
reason       = text ;   (* peut citer l'ID remplaçant, ex. « remplacé par `CANON:12` » *)
```

Exemple réel accepté (`.claude/canon/invariants.md`) :

```markdown
- ~~`CANON:7` [USER:eddy 2026-09-24] Le plugin memory est retiré du repo immédiatement…~~
  — obsolète 2026-09-24 : la décision explicite est venue, remplacé par `CANON:10`.
```

### 1.4 Règles vérifiées

| Code | Niveau | Règle | Source (canon-tracker) |
|---|---|---|---|
| `canon.title` | ERROR | Le fichier commence par `# <Thème>` | § « Initialiser le canon » |
| `canon.prose` | ERROR | Aucune ligne hors entrée | § « Grammaire d'une entrée » |
| `canon.entry` | ERROR | Entrée conforme à `entry-body` (ID entre backticks, provenance `[USER:<nom> date]` ou `[MODEL date]`, point non vide) | § « Grammaire d'une entrée » |
| `canon.date` | ERROR | Dates calendaires valides | § « Grammaire d'une entrée » |
| `canon.duplicate-id` | ERROR | `CANON:n` unique **sur tout le dossier**, entrées barrées comprises (jamais réutilisé) | § « Grammaire d'une entrée » |
| `canon.strike` | ERROR | `~~` ouvrant fermé ; pas de `~~` partiel au milieu d'un point | § « Déprécier une entrée » |
| `canon.obsolete-missing` | ERROR | Une entrée barrée porte `— obsolète AAAA-MM-JJ : <raison>` | § « Déprécier une entrée » |
| `canon.obsolete-unstruck` | ERROR | Une marque `— obsolète` n'apparaît que sur une entrée barrée | § « Déprécier une entrée » |
| `canon.promotion` | ERROR | `(promu de MODEL)` seulement sur une entrée `[USER:…]` | § « Promouvoir » |
| `canon.divers` | ERROR | Pas de `divers.md` | § « Où vit le canon » |
| `canon.obsolete-before-entry` | WARN | Date d'obsolescence ≥ date de l'entrée | — (cohérence) |
| `canon.unknown-ref` | WARN | Un `CANON:n` cité dans une entrée existe | — (cohérence) |

Hors de portée du validateur (non décidable mécaniquement) : « une phrase, deux au plus »,
la légitimité d'une provenance `[USER]`, le choix du bon fichier thématique, le caractère
« durable » d'une entrée.

---

## 2. Roadmap — `.claude/roadmap.md`

Source : roadmap-tracker, § « Grammaire du fichier ». Le validateur lit le **miroir
versionné** `.claude/roadmap.md` (la source en mémoire auto,
`~/.claude/projects/<projet>/memory/roadmap.md`, est hors repo et en est une copie
identique, § « Où vit la roadmap »).

### 2.1 Fichier

```ebnf
roadmap-file    = { blank-line } , "# Roadmap" , NL , { section } ;
section         = specs-section | milestone-section | backlog-section ;

specs-section   = "## Specs" , NL , { blank-line | spec } , [ rules ] ;
spec            = "- " , spec-id , SP , "**" , text , "**" , SP , "[" , spec-status , "]" , NL ,
                  { continuation } ;           (* dont « - Canon : … » attendu *)
spec-status     = "draft" | "active" | "retired" ;
rules           = "Règles :" , NL , { "- " , text , NL , { continuation } | blank-line } ;

milestone-section = "## M" , number , " — " , text ,
                    " (`ROADMAP:MILESTONE:" , number , "`, " , ms-status , ")" , NL ,
                    { blank-line | description-line | dod-line | task } ;
ms-status       = "planned" | "active" | "done" ;
description-line = text , NL ;                 (* prose libre, décisions datées *)
dod-line        = "DoD du milestone :" , SP , text , NL ;

backlog-section = "## Backlog (no milestone)" , NL , { blank-line | task } ;
```

### 2.2 Tâche

```ebnf
task        = "- [" , box , "] " , task-id , SP , title , [ SP , suffix ] , [ trailer ] , NL ,
              { continuation } ;
box         = " " | "~" | "x" ;                (* todo · in_progress · done *)
title       = [ prefix , SP ] , text ;
prefix      = "[BUG]" | "[JALON]" | "[RÉCURRENT]" | "[FOND]" | "[RÉFLEXION]" ;
suffix      = "_(" , part , { "; " , part } , ")_" ;
part        = "implements " , spec-id , { ", " , spec-id }
            | "depends on " , task-id-ref , { ", " , task-id-ref }
            | "claimed by " , text
            | "blocked: " , text ;             (* toujours dernier : peut contenir « ; » *)
trailer     = SP , text ;                      (* annotation datée après le suffixe, cf. A5 *)

spec-id     = "`ROADMAP:SPEC:" , number , "`" | "ROADMAP:SPEC:" , number ;
                                               (* avec backticks en tête de spec, sans dans le suffixe *)
task-id     = "`ROADMAP:TASK:" , number , "`" ;
task-id-ref = "ROADMAP:TASK:" , number ;
```

Les éléments du suffixe apparaissent chacun au plus une fois, **dans l'ordre**
`implements`, `depends on`, `claimed by`, `blocked:` (§ « Conventions »).

### 2.3 Règles vérifiées

| Code | Niveau | Règle | Source (roadmap-tracker) |
|---|---|---|---|
| `roadmap.title` | ERROR | Premier titre `# Roadmap` | « Structure du fichier » |
| `roadmap.section` | ERROR | Sections `## Specs`, `## M<n> — …`, `## Backlog (no milestone)` uniquement | « Structure du fichier » |
| `roadmap.spec` | ERROR | Spec conforme, statut `draft|active|retired` ; pas de puce libre avant `Règles :` | « Structure du fichier » |
| `roadmap.milestone` | ERROR | En-tête de milestone conforme, statut `planned|active|done` | « Structure du fichier » |
| `roadmap.task` / `roadmap.checkbox` | ERROR | Tâche conforme, case `[ ]`, `[~]` ou `[x]` | « Conventions » |
| `roadmap.duplicate-id` | ERROR | IDs uniques **par famille** (SPEC, MILESTONE, TASK) | « Trois familles d'IDs stables » |
| `roadmap.suffix` / `roadmap.suffix-order` / `roadmap.suffix-id` | ERROR | Suffixe `_( … )_` : éléments connus, ordre imposé, IDs complets de la bonne famille | « Conventions » |
| `roadmap.unknown-ref` | ERROR | `implements` → spec existante ; `depends on` → tâche existante | « Ajouter une tâche » |
| `roadmap.self-dependency` / `roadmap.dependency-cycle` | ERROR | Pas de dépendance circulaire (une tâche du cycle ne serait jamais débloquée) | « Prendre une tâche » |
| `roadmap.claim-missing` | ERROR | `[~]` porte `claimed by <user>` **ou** `blocked: <raison>` | « Conventions », cf. A4 |
| `roadmap.claim-on-done` | ERROR | `[x]` ne porte plus `claimed by` | « Terminer une tâche » |
| `roadmap.milestone-done` | ERROR | Milestone `done` ⇒ toutes ses tâches `[x]` | « Conventions » |
| `roadmap.dependency-not-done` | WARN | Tâche `[~]`/`[x]` dont une dépendance n'est pas `[x]` | « Prendre une tâche », cf. A6 |
| `roadmap.claim-on-todo` | WARN | `[ ]` avec `claimed by` | « Conventions » |
| `roadmap.blocked-not-in-progress` | WARN | `blocked:` hors `[~]` | « Conventions » |
| `roadmap.title-prefix` | WARN | Préfixe de titre entre crochets hors liste normalisée | « Conventions » |
| `roadmap.milestone-dod` | WARN | Milestone sans ligne `DoD du milestone :` | « Structure du fichier » |
| `roadmap.milestone-number` | WARN | `M<k>` ≠ `ROADMAP:MILESTONE:<k>` | « Structure du fichier » (exemple) |
| `roadmap.spec-canon` | WARN | Spec sans sous-puce `- Canon : …` | « Structure du fichier » |
| `roadmap.bullet` | WARN | Puce non-tâche dans un milestone ou le backlog | « Structure du fichier » |
| `roadmap.unknown-canon-ref` | WARN | Un `CANON:n` cité existe dans `.claude/canon/` | — (cohérence) |

---

## 3. Manifestes et frontmatter (marketplace uniquement)

Ne concernent que le repo du marketplace ; ignorés ailleurs.

| Code | Niveau | Règle |
|---|---|---|
| `manifest.json` | ERROR | `.claude-plugin/marketplace.json` et chaque `plugins/*/.claude-plugin/plugin.json` se chargent en JSON (`CANON:4`) |
| `manifest.plugin-name` / `manifest.plugin-version` | ERROR | `plugin.json` : `name` non vide, `version` semver 2.0 |
| `manifest.marketplace-*` | ERROR | `marketplace.json` : `name`, `owner.name`, `plugins[]` avec `name` + `source` ; `version` semver si présente ; source locale en `./…` contenant un `plugin.json` |
| `manifest.name-mismatch` / `manifest.version-mismatch` | ERROR | Nom (et version si l'entrée en porte une) de l'entrée catalogue = ceux du `plugin.json` pointé |
| `manifest.unlisted-plugin` | WARN | Plugin sous `plugins/` absent du catalogue |
| `frontmatter.syntax` | ERROR | `plugins/*/agents/*.md` et `plugins/*/skills/*/SKILL.md` commencent par un frontmatter `---` … `---` lisible |
| `frontmatter.name` / `frontmatter.description` | ERROR | Champs présents et non vides |
| `frontmatter.model` | ERROR | `model` ∈ {`opus`, `sonnet`, `haiku`, `fable`, `inherit`} ou ID `claude-*` |
| `frontmatter.effort` | ERROR | `effort` ∈ {`low`, `medium`, `high`, `xhigh`, `max`} (`CANON:11`) |
| `frontmatter.plugin-agent-ignored` | WARN | `hooks`, `mcpServers`, `permissionMode` dans un agent de plugin : ignorés par Claude Code (`CANON:11`) |
| `frontmatter.name-format` / `frontmatter.name-dir` | WARN | `name` en kebab-case ; `name` d'un skill = nom de son dossier |

Le frontmatter est lu par un mini-parseur YAML (clés de premier niveau, scalaires simples ou
entre guillemets, blocs `|`/`>`, commentaires) : suffisant pour ces fichiers, sans
dépendance à PyYAML.

---

## 4. Points ambigus des SKILL.md (non tranchés, les deux lectures sont acceptées)

- **A1 — Que barre-t-on ?** canon-tracker, § « Déprécier » dit « barrer le texte (`~~…~~`) » ;
  l'exemple de § « Grammaire d'une entrée » barre **toute** l'entrée, ID et provenance
  compris. Le validateur accepte `~~`CANON:n` [...] point~~` et `` `CANON:n` [...] ~~point~~ ``.
- **A2 — Où va la marque d'obsolescence ?** « en dessous ou en fin de ligne » : les deux sont
  acceptés (continuation indentée ou même ligne logique).
- **A3 — Sous-titres dans un fichier canon.** Rien ne les autorise ni ne les interdit
  explicitement ; « jamais de prose flottante » vise les paragraphes. Les lignes `#…` sont
  tolérées.
- **A4 — Tâche bloquée.** « `[~]` toujours accompagné de `claimed by` » vs « une tâche bloquée
  reste `[~]` avec `blocked:` » : `blocked:` exige-t-il aussi `claimed by` ? Le validateur
  accepte `[~]` avec l'un **ou** l'autre.
- **A5 — Texte après le suffixe.** La roadmap réelle porte des annotations datées après
  `)_` (« — décision 2026-09-24 : retiré (CANON:10) »). La grammaire ne les prévoit pas mais
  « les décisions de portée se datent dans le texte » ; elles sont acceptées.
- **A6 — Dépendance non terminée.** La règle de claim (« si une dépendance n'est pas done :
  le signaler et s'arrêter ») est une règle d'opération, pas de grammaire, et la roadmap
  réelle contient des exceptions décidées par l'utilisateur (TASK:10 fait « par
  anticipation ») : avertissement, pas erreur.
- **A7 — Nom dans `[USER:<nom>]`.** Aucun jeu de caractères n'est fixé ; tout texte sans `]`
  est accepté (espaces internes compris).
- **A8 — Tiret de la marque d'obsolescence.** Le SKILL écrit `—` (tiret cadratin) ; seul ce
  caractère est reconnu. Un `-` ou `--` produit `canon.obsolete-missing`.
