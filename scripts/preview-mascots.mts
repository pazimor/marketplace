// Génère docs/mascots-preview.html à partir du vrai code des mascottes (crabSvg).
// Usage : node --experimental-strip-types scripts/preview-mascots.mts
// Image (macOS) : qlmanage -t -s 1400 -o docs docs/mascots-preview.html
import { writeFileSync } from 'node:fs'
import { crabSvg, MASCOT_EMOJI } from '../plugins/session-recap/hooks/recap.ts'

type O = Parameters<typeof crabSvg>[0]
const rows: [string, O][] = [
  [`${MASCOT_EMOJI.scribe} scribe — capuche, plume, parchemin`, { mascot: 'scribe' }],
  [`${MASCOT_EMOJI.chef} chef — toque à insigne cerveau, veste, cuillère`, { mascot: 'chef' }],
  [`${MASCOT_EMOJI.artiste} artiste — béret, palette, pinceau`, { mascot: 'artiste' }],
  [`${MASCOT_EMOJI.inspecteur} inspecteur — casquette de détective, loupe, pipe (tests, débogage)`, { mascot: 'inspecteur' }],
  [`${MASCOT_EMOJI.coursier} coursier — métier par défaut du modèle le plus économe`, { tier: 'haiku' }],
  [`${MASCOT_EMOJI.artisan} artisan — métier par défaut du modèle intermédiaire`, { tier: 'sonnet' }],
  [`${MASCOT_EMOJI.savant} savant — métier par défaut du modèle le plus capable`, { tier: 'opus' }],
  [`${MASCOT_EMOJI.mage} mage — métier par défaut de la gamme au-dessus`, { tier: 'fable' }],
]
const big = (o: O) => crabSvg({ ...o, height: 96 })
let tr = ''
for (const [label, o] of rows)
  tr += `<tr><th>${label}</th><td>${big({ ...o, animated: true })}</td><td>${big({ ...o, mono: true })}</td><td>${big({ ...o, body: '#ef4444' })}</td><td class="small">${crabSvg({ ...o, animated: true })}</td></tr>`
const card = (o: O, task: string, m: string, done = false) =>
  `<div class="cell"><div class="card ${done ? 'dim' : ''}">${crabSvg({ ...o, animated: !done, mono: done })}<div class="txt"><div>${task}</div><div class="d">${m}</div></div></div></div>`
const html = `<!doctype html><meta charset="utf-8"><title>Mascottes</title><style>
body{font:14px system-ui;background:#1f1e1d;color:#e8e6e3;padding:16px}table{border-collapse:collapse}th{text-align:left;padding:8px 16px 8px 0;font-weight:600;max-width:300px}td{padding:6px 14px;text-align:center}
thead td{font-size:12px;color:#9a9893}.small{background:#2a2928}code{color:#e8b07a}
.grid{display:flex;flex-wrap:wrap;row-gap:10px;width:780px;margin-top:12px;font:12px ui-monospace,Menlo,monospace}.cell{width:33.33%;padding-right:9px;box-sizing:border-box}
.card{display:flex;gap:8px;border:1px solid #5a5856;border-radius:8px;padding:4px 8px}.dim{opacity:.6}.d{color:#9a9893;font-weight:400}svg{display:block}</style>
<h2>Mascottes du bandeau</h2>
<p>Un agent choisit la sienne par <code>mascot: &lt;nom&gt;</code> dans son frontmatter ; sans ce champ, il porte le métier de son modèle.</p>
<table><thead><tr><td></td><td>actif</td><td>inactif</td><td>échec</td><td>taille réelle</td></tr></thead>${tr}</table>
<h2>Bandeau (maquette CSS des cartes, mascottes du vrai code)</h2>
<div class="grid">${card({ mascot: 'chef' }, 'orchestrateur', 'opus-5-5 · high (Agent) — 1 min')}${card({ mascot: 'scribe' }, 'noter les décisions', 'haiku-5-5 · xhigh (Edit) — 21s')}${card({ mascot: 'artiste' }, 'revoir les captures', 'opus-5-5 · high (Read) — 48s')}${card({ tier: 'haiku' }, 'relever les sorties', 'haiku-5-5 · low (Bash) — 9s')}${card({ tier: 'sonnet' }, 'implémenter le parseur', 'sonnet-5-5 · medium — 42s')}${card({ tier: 'sonnet' }, 'lire le canon', 'sonnet-5-5 · low — 1 min', true)}</div>`
writeFileSync(new URL('../docs/mascots-preview.html', import.meta.url), html)
console.log('docs/mascots-preview.html')
