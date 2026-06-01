"""
Traveller Hexkarte — interaktiv  ·  SPECTRUM Detail-Overlay-Card
=================================================================

Erweitert die Hexkarte um Klick-Interaktion: Klick auf eine Welt setzt einen
Pin-Ring (gestrichelt, Primary) auf das Hex und blendet unten eine Overlay-Card
ein (DESIGN.md §6.9) mit:
  * dekodierter UWP (Raumhafen, Atmosphaere, Regierung, Gesetz, TL ... auf Deutsch)
  * Handelscodes als Tag-Badges
  * Reisezone / Basen / Gasriese
  * Verknuepfungen: NSCs, Auftraege, Fraktionen  <- die Bruecke Prep <-> Tisch

Die Dekodier-Tabellen (RAUMHAFEN/ATMO/REG/GESETZ/TL ...) liegen unten im JS und
sind frei an die exakte 13Mann-Terminologie anpassbar.  # PRUEFEN gegen Buch.

Verknuepfungsdaten kommen hier als Beispiel; spaeter aus der DB
(welt 1-n nsc, auftrag, fraktion ueber FKs + Tabelle `verknuepfung`).
"""

from __future__ import annotations
import json
from hexmap import render_svg, _g
from sektor_generator import erzeuge_subsektor
from routes import gen_alle_routen

_FELDER = ["name", "uwp", "raumhafen", "groesse", "atmosphaere", "hydrographie",
           "bevoelkerung", "regierung", "gesetz", "techlevel",
           "handelscodes", "basen", "reisezone", "gasriesen", "zugehoerigkeit",
           "temperatur", "raumhafen_details", "kultur"]


def _welt_json(w) -> dict:
    return {k: _g(w, k) for k in _FELDER}


def render_app(welten, ss_index: int, sektor_name: str = "DEMO",
               links: dict | None = None, routen=None,
               nav_html: str = "", home_url: str = "#", export_url: str = "#") -> str:
    svg = render_svg(welten, ss_index, routen=routen)
    letter = chr(ord("A") + ss_index)
    n = len(welten)
    n_amber = sum(1 for w in welten if _g(w, "reisezone") == "amber")
    n_rot   = sum(1 for w in welten if _g(w, "reisezone") == "rot")

    welten_json = {_g(w, "hex"): _welt_json(w) for w in welten}
    links = links or {}

    return f"""<!doctype html>
<html lang="de"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{sektor_name} · Subsektor {letter}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&family=Space+Grotesk:wght@500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{{
  --surface:#131313; --container-lowest:#0e0e0e; --container-low:#1a1a1a;
  --container:#212121; --container-high:#2a2a2a; --container-highest:#333;
  --primary:#A6FF00; --primary-container:#467000; --on-primary:#0a0a0a;
  --secondary:#00E0FF; --tertiary:#FF8A00; --error:#FF4D4D;
  --on-surface:#e2e2e2; --on-variant:#7a7a7a; --outline:#414a34;
  --radius-sm:.125rem; --radius-xs:.25rem; --radius-md:.375rem;
  --font-body:'Manrope',system-ui,sans-serif;
  --font-disp:'Space Grotesk','Manrope',sans-serif;
  --font-mono:ui-monospace,'JetBrains Mono',monospace;
  --gradient:linear-gradient(45deg,var(--primary) 0%,var(--primary-container) 100%);
  --ease:cubic-bezier(.2,.8,.2,1);
}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--surface);color:var(--on-surface);font-family:var(--font-body);
  font-feature-settings:"tnum";}}

/* Studio Header */
.studio-header{{display:flex;align-items:center;justify-content:space-between;height:64px;padding:0 24px;background:var(--surface);}}
.brand{{display:flex;align-items:center;gap:12px;}}
.logo-tile{{display:grid;place-items:center;width:36px;height:36px;border-radius:var(--radius-md);
  background:var(--gradient);color:var(--on-primary);font-family:var(--font-mono);font-weight:700;font-size:1rem;}}
.product{{font-weight:700;font-size:1rem;}}
.tag{{font-family:var(--font-mono);font-size:.75rem;color:var(--on-variant);}}
.actions{{display:flex;align-items:center;gap:8px;}}
.btn{{display:inline-flex;align-items:center;gap:8px;height:40px;padding:0 20px;border:none;border-radius:var(--radius-sm);
  font-family:var(--font-body);font-size:.875rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;cursor:pointer;
  transition:background 120ms var(--ease),box-shadow 200ms var(--ease);}}
.btn--ghost{{background:var(--container-high);color:var(--on-surface);}}
.btn--ghost:hover{{background:var(--container-highest);}}
.btn--primary{{background:var(--gradient);color:var(--on-primary);}}
.btn--primary:hover{{box-shadow:0 0 12px rgba(166,255,0,.30);}}
.btn__chevron{{font-family:var(--font-mono);font-size:.7em;opacity:.85;}}

/* Section strip */
.section-strip{{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;padding:12px 24px;background:var(--surface);}}
.slot{{font-family:var(--font-mono);font-size:.68rem;font-weight:500;letter-spacing:.12em;text-transform:uppercase;color:var(--on-variant);}}
.slot--left{{justify-self:start;}} .slot--center{{justify-self:center;display:inline-flex;align-items:center;gap:8px;}}
.slot--right{{justify-self:end;}} .slot--center b{{color:var(--primary);font-weight:500;}}
.pulse{{width:6px;height:6px;border-radius:9999px;background:var(--primary);box-shadow:0 0 12px rgba(166,255,0,.3);}}

/* Map */
.wrap{{padding:8px 24px 120px;}}
.legend{{display:flex;flex-wrap:wrap;gap:20px;align-items:center;background:var(--container-lowest);
  border-radius:var(--radius-md);padding:12px 16px;margin:8px 0 20px;}}
.leg{{display:inline-flex;align-items:center;gap:8px;font-family:var(--font-mono);font-size:.68rem;
  letter-spacing:.08em;text-transform:uppercase;color:var(--on-variant);}}
.dot{{width:9px;height:9px;border-radius:9999px;}}
.ring-gg{{width:9px;height:9px;border-radius:9999px;border:1.3px solid var(--on-variant);}}
.swatch{{width:14px;height:9px;border-radius:2px;}}
.swatch.amber{{border:1.6px solid var(--tertiary);background:rgba(255,138,0,.07);}}
.swatch.red{{border:1.6px dashed var(--error);background:rgba(255,77,77,.07);}}
.line-komm{{width:18px;height:0;border-top:1.6px solid var(--secondary);opacity:.8;}}
.line-handel{{width:18px;height:0;border-top:1.6px dashed var(--on-variant);}}
.legend .mono{{font-weight:600;color:var(--on-surface);}}
.mapcard{{background:var(--container-lowest);border-radius:var(--radius-md);padding:16px;overflow:auto;}}
.mapcard svg{{display:block;margin:0 auto;}}

/* Clickable hexes + pin ring */
.cell{{cursor:pointer;}}
.cell:hover{{filter:brightness(1.5);}}
.pin-ring{{stroke:var(--primary);stroke-width:2.2;fill:none;stroke-dasharray:9 6;
  filter:drop-shadow(0 0 6px rgba(166,255,0,.5));animation:march 1.2s linear infinite;}}
@keyframes march{{to{{stroke-dashoffset:-30;}}}}

/* Detail overlay card (§6.9) */
.scrim{{position:fixed;inset:0;background:rgba(0,0,0,.35);opacity:0;pointer-events:none;
  transition:opacity 200ms var(--ease);z-index:10;}}
.scrim.open{{opacity:1;pointer-events:auto;}}
.detail{{position:fixed;left:50%;bottom:0;transform:translate(-50%,110%);width:min(560px,calc(100% - 32px));
  background:rgba(14,14,14,.95);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
  border:1px solid rgba(166,255,0,.6);border-bottom:none;border-radius:var(--radius-md) var(--radius-md) 0 0;
  padding:20px;z-index:11;transition:transform 220ms var(--ease);max-height:80vh;overflow:auto;}}
.detail.open{{transform:translate(-50%,0);}}
.detail__eyebrow{{font-family:var(--font-mono);font-size:.68rem;letter-spacing:.12em;text-transform:uppercase;
  color:var(--on-variant);margin-bottom:6px;}}
.detail__title{{font-family:var(--font-mono);font-size:1.5rem;font-weight:600;margin:0 0 2px;}}
.detail__uwp{{font-family:var(--font-mono);font-size:1rem;color:var(--on-variant);letter-spacing:.06em;margin-bottom:16px;}}

.statstrip{{display:flex;gap:32px;margin-bottom:18px;}}
.stat__v{{font-family:var(--font-mono);font-size:1.4rem;font-weight:500;}}
.stat__l{{font-size:.78rem;color:var(--on-variant);}}

.kv{{display:grid;grid-template-columns:130px 1fr;gap:2px 12px;margin-bottom:16px;}}
.kv dt{{font-family:var(--font-mono);font-size:.7rem;letter-spacing:.08em;text-transform:uppercase;
  color:var(--on-variant);padding:5px 0;}}
.kv dd{{margin:0;padding:5px 0;font-size:.9rem;}}
.kv .row:nth-child(odd){{background:var(--container-lowest);}}
.kv dt,.kv dd{{align-self:stretch;}}

.badges{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px;}}
.badge{{font-family:var(--font-mono);font-size:.68rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;
  padding:3px 9px;border-radius:9999px;}}
.badge--code{{background:rgba(0,224,255,.12);color:var(--secondary);}}
.badge--amber{{background:rgba(255,138,0,.14);color:var(--tertiary);}}
.badge--red{{background:rgba(255,77,77,.14);color:var(--error);}}
.badge--ok{{background:rgba(166,255,0,.12);color:var(--primary);}}
.badge--mut{{background:var(--container);color:var(--on-variant);}}
.badge--secret{{background:rgba(255,77,77,.14);color:var(--error);border-radius:var(--radius-xs);}}

.sec-label{{font-family:var(--font-mono);font-size:.68rem;letter-spacing:.12em;text-transform:uppercase;
  color:var(--on-variant);margin:18px 0 8px;}}
.link-row{{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:var(--radius-sm);}}
.link-row:nth-child(even){{background:var(--container-lowest);}}
.link-row__name{{font-size:.9rem;flex:1;}}
.link-row__meta{{font-size:.78rem;color:var(--on-variant);}}
.empty{{font-size:.82rem;color:var(--on-variant);padding:4px 0 8px;}}
.kv2{{display:grid;grid-template-columns:130px 1fr;gap:2px 12px;margin-bottom:10px;}}
.kv2 .k{{font-family:var(--font-mono);font-size:.7rem;letter-spacing:.08em;text-transform:uppercase;color:var(--on-variant);padding:4px 0;}}
.kv2 .v{{font-size:.88rem;padding:4px 0;}}
.kultur{{font-size:.88rem;color:var(--on-surface);padding:2px 0 6px;line-height:1.5;}}

.close{{width:100%;height:44px;margin-top:18px;background:var(--container-high);color:var(--on-surface);
  border:none;border-radius:var(--radius-sm);font-family:var(--font-body);font-weight:600;font-size:.85rem;
  letter-spacing:.06em;text-transform:uppercase;cursor:pointer;}}
.close:hover{{background:var(--container-highest);}}

@media (prefers-reduced-motion: reduce){{
  .pin-ring{{animation:none;}}
  .detail,.scrim{{transition:none;}}
}}
</style></head>
<body>
  <header class="studio-header">
    <div class="brand">
      <div class="logo-tile">T</div><span class="product">TRAVELLER</span>
      <span class="tag">STUDIO // v0.1</span>
    </div>
    <div class="actions">
      <a class="btn btn--ghost" href="{home_url}">ÜBERSICHT</a>
      <a class="btn btn--primary" href="{export_url}">UWP-EXPORT</a>
    </div>
  </header>
  <div class="section-strip">
    <span class="slot slot--left">SEKTOR // {sektor_name}</span>
    <span class="slot slot--center"><span class="pulse"></span><b>SUBSEKTOR {letter}</b></span>
    <span class="slot slot--right">{n} WELTEN&nbsp;&nbsp;{n_amber} AMBER&nbsp;&nbsp;{n_rot} ROT</span>
  </div>
  {nav_html}
  <div class="wrap">
    <div class="legend">
      <span class="leg"><span class="dot" style="background:var(--on-surface)"></span>WELT</span>
      <span class="leg"><span class="ring-gg"></span>GASRIESE</span>
      <span class="leg"><span class="swatch amber"></span>AMBER</span>
      <span class="leg"><span class="swatch red"></span>ROT</span>
      <span class="leg"><span class="line-komm"></span>KOMMUNIKATION</span>
      <span class="leg"><span class="line-handel"></span>HANDEL</span>
      <span class="leg"><span class="mono">M</span>MARINE <span class="mono">S</span>SCOUT <span class="mono">F</span>FORSCHUNG <span class="mono">T</span>TAS <span class="mono">K</span>KONSULAT <span class="mono">P</span>PIRATEN</span>
      <span class="leg" style="color:var(--primary)">↳ HEX ANKLICKEN FÜR DETAILS</span>
    </div>
    <div class="mapcard">{svg}</div>
  </div>

  <div class="scrim" id="scrim"></div>
  <aside class="detail" id="detail" role="dialog" aria-modal="true" aria-label="Weltdetails">
    <div class="detail__eyebrow" id="d-eyebrow">WELT · ESC ODER TIPPEN ZUM SCHLIESSEN</div>
    <h2 class="detail__title" id="d-name"></h2>
    <div class="detail__uwp" id="d-uwp"></div>
    <div class="statstrip" id="d-stats"></div>
    <dl class="kv" id="d-kv"></dl>
    <div class="badges" id="d-badges"></div>
    <div id="d-links"></div>
    <button class="close" id="d-close" type="button">Schließen</button>
  </aside>

<script>
const WELTEN = {json.dumps(welten_json, ensure_ascii=False)};
const LINKS  = {json.dumps(links, ensure_ascii=False)};

// --- Dekodier-Tabellen (Deutsch)  # PRUEFEN gegen 13Mann-Grundregelwerk ---
const RAUMHAFEN = {{A:"Erstklassig — Treibstoff, Werft, Schiffsbau",B:"Gut — Treibstoff, Werft",
  C:"Routine — Treibstoff, begrenzte Reparatur",D:"Einfach — unraffinierter Treibstoff",
  E:"Grenzwertig — nur Landefeld",X:"Kein Raumhafen"}};
const GROESSE = {{0:"800 km · vernachl. g",1:"1.600 km · 0,05 g",2:"3.200 km · 0,15 g",3:"4.800 km · 0,25 g",
  4:"6.400 km · 0,35 g",5:"8.000 km · 0,45 g",6:"9.600 km · 0,7 g",7:"11.200 km · 0,9 g",
  8:"12.800 km · 1,0 g",9:"14.400 km · 1,25 g",10:"16.000 km · 1,4 g"}};
const ATMO = {{0:"Keine",1:"Spuren",2:"Sehr dünn, verseucht",3:"Sehr dünn",4:"Dünn, verseucht",5:"Dünn",
  6:"Standard",7:"Standard, verseucht",8:"Dicht",9:"Dicht, verseucht",10:"Exotisch",11:"Korrosiv",
  12:"Insidiös",13:"Dicht, hoch",14:"Dünn, niedrig",15:"Ungewöhnlich"}};
const HYDRO = {{0:"0–5% · Wüstenwelt",1:"6–15% · Trockenwelt",2:"16–25%",3:"26–35%",4:"36–45% · feucht",
  5:"46–55%",6:"56–65%",7:"66–75% · erdähnlich",8:"76–85% · Wasserwelt",9:"86–95%",10:"96–100% · fast nur Wasser"}};
const BEV = {{0:"Keine",1:"Wenige (1+)",2:"Hunderte",3:"Tausende",4:"Zehntausende",5:"Hunderttausende",
  6:"Millionen",7:"Zehn Mio.",8:"Hunderte Mio.",9:"Milliarden",10:"Zehn Mrd.",11:"Hunderte Mrd.",12:"Billionen"}};
const REG = {{0:"Keine",1:"Firma/Konzern",2:"Partizipative Demokratie",3:"Selbsterhaltende Oligarchie",
  4:"Repräsentative Demokratie",5:"Feudale Technokratie",6:"Marionettenregierung",7:"Balkanisiert",
  8:"Beamtenbürokratie",9:"Unpersönliche Bürokratie",10:"Charismatischer Diktator",
  11:"Nicht-charism. Diktator",12:"Charismatische Oligarchie",13:"Religiöse Diktatur"}};
const GESETZ = {{0:"Keine Beschränkungen",1:"Verbot: WMD, Gifte, Sprengstoff",2:"Verbot: tragbare Energiewaffen",
  3:"Verbot: schwere Waffen",4:"Verbot: leichte Sturmwaffen, MPs",5:"Verbot: versteckbare Waffen",
  6:"Verbot: Schusswaffen (außer Schrot/Betäuber)",7:"Verbot: Schrotflinten",8:"Verbot: Klingen, Betäuber",
  9:"Verbot: alle Waffen"}};
const TL = {{0:"Steinzeit",1:"Bronze / Eisen",2:"Renaissance",3:"Schießpulver",4:"Industriell",
  5:"Verbrennungsmotor",6:"Atomzeitalter",7:"Frühe Raumfahrt",8:"Frühes Informationszeitalter",
  9:"Gravitationskontrolle",10:"Interstellar (früh)",11:"Mittlere Stufe",12:"Imperialer Durchschnitt",
  13:"Hoch",14:"Sehr hoch",15:"Imperiales Maximum",16:"Experimentell"}};
const TRADE = {{Ag:"Agrarwelt",As:"Asteroid",Ba:"Öde",De:"Wüste",Fl:"Flüssige Ozeane",Ga:"Gartenwelt",
  Hi:"Hohe Bevölkerung",Ht:"Hochtechnologie",Ic:"Eisbedeckt",In:"Industriewelt",Lo:"Geringe Bevölkerung",
  Lt:"Niedrige Technologie",Na:"Nicht-agrarisch",Ni:"Nicht-industriell",Po:"Arm",Ri:"Reich",
  Wa:"Wasserwelt",Va:"Vakuum"}};
const ZONE = {{gruen:["Ruhig","badge--ok"],amber:["Amber","badge--amber"],rot:["Rot — interdiziert","badge--red"]}};
const dec = (t,v,cap)=> t[v] ?? t[Math.min(v,cap)] ?? String(v);

const detail=document.getElementById("detail"), scrim=document.getElementById("scrim");

function openHex(hex){{
  const w = WELTEN[hex]; if(!w) return;
  document.getElementById("d-eyebrow").textContent = `WELT ${{hex}} · ESC ODER TIPPEN ZUM SCHLIESSEN`;
  document.getElementById("d-name").textContent = w.name;
  document.getElementById("d-uwp").textContent  = w.uwp + (w.zugehoerigkeit ? "   " + w.zugehoerigkeit : "");

  document.getElementById("d-stats").innerHTML =
    stat(w.raumhafen, "Raumhafen") + stat("TL " + w.techlevel, "Tech-Level")
    + stat(w.basen.length ? w.basen.join("+") : "—", "Basen");

  document.getElementById("d-kv").innerHTML =
      kv("Raumhafen", RAUMHAFEN[w.raumhafen])
    + kv("Größe", dec(GROESSE,w.groesse,10))
    + kv("Atmosphäre", dec(ATMO,w.atmosphaere,15))
    + kv("Hydrographie", dec(HYDRO,w.hydrographie,10))
    + kv("Temperatur", tempHtml(w.temperatur))
    + kv("Bevölkerung", dec(BEV,w.bevoelkerung,12))
    + kv("Regierung", dec(REG,w.regierung,13))
    + kv("Gesetz", dec(GESETZ,w.gesetz,9))
    + kv("Tech-Level", dec(TL,w.techlevel,16))
    + kv("Gasriese", w.gasriesen ? "Vorhanden" : "Keiner");

  let b = (w.handelscodes||[]).map(c=>`<span class="badge badge--code">${{c}} · ${{TRADE[c]||c}}</span>`).join("");
  const z = ZONE[w.reisezone]||ZONE.gruen;
  b += `<span class="badge ${{z[1]}}">${{z[0]}}</span>`;
  document.getElementById("d-badges").innerHTML = b;

  document.getElementById("d-links").innerHTML = renderExtras(w) + renderLinks(LINKS[hex]);

  pin(hex);
  scrim.classList.add("open"); detail.classList.add("open");
}}

function stat(v,l){{ return `<div><div class="stat__v">${{v}}</div><div class="stat__l">${{l}}</div></div>`; }}
function kv(k,v){{ return `<div class="row" style="display:contents"></div><dt>${{k}}</dt><dd>${{v}}</dd>`; }}

const TEMP_FARBE = {{Gefroren:"var(--secondary)", Kalt:"var(--secondary)",
  "Gemäßigt":"var(--on-surface)", "Heiß":"var(--tertiary)", "Glühend":"var(--error)"}};
function tempHtml(t){{ return t ? `<span style="color:${{TEMP_FARBE[t]||'var(--on-surface)'}}">${{t}}</span>` : "—"; }}
function cap(s){{ return s ? s[0].toUpperCase()+s.slice(1) : s; }}
function row2(k,v){{ return `<span class="k">${{k}}</span><span class="v">${{v}}</span>`; }}

function renderExtras(w){{
  const rd = w.raumhafen_details || {{}};
  const kosten = rd.anlegekosten ? "Cr. " + Number(rd.anlegekosten).toLocaleString("de-DE") : "—";
  let sp = `<div class="sec-label">Raumhafen-Details</div><div class="kv2">`
    + row2("Treibstoff", rd.treibstoff ? cap(rd.treibstoff) : "keiner")
    + row2("Anlegekosten", kosten)
    + row2("Werft", rd.werft || "—")
    + row2("Reparatur", rd.reparatur ? cap(rd.reparatur) : "—")
    + `</div>`;
  let ku = "";
  if(w.kultur){{
    ku = `<div class="sec-label">Kultur</div>`
       + `<div class="kultur"><b>${{w.kultur.name}}</b> — ${{w.kultur.beschreibung}}</div>`;
  }}
  return sp + ku;
}}

function renderLinks(L){{
  L = L || {{}};
  const sect = (label,items,fmt)=>{{
    let h = `<div class="sec-label">${{label}}</div>`;
    if(!items || !items.length) return h + `<div class="empty">— keine —</div>`;
    return h + items.map(fmt).join("");
  }};
  const nsc = sect("NSCs", L.nscs, n=>
    `<div class="link-row"><span class="link-row__name">${{n.name}}`
    + (n.geheim?` <span class="badge badge--secret">geheim</span>`:``)
    + `</span><span class="link-row__meta">${{n.rolle||""}} · ${{n.status||""}}</span></div>`);
  const auf = sect("Aufträge", L.auftraege, a=>
    `<div class="link-row"><span class="link-row__name">${{a.titel}}</span>`
    + `<span class="link-row__meta">${{a.status||""}}</span></div>`);
  const fra = sect("Fraktionen", L.fraktionen, f=>
    `<div class="link-row"><span class="link-row__name">${{f.name}}</span>`
    + `<span class="link-row__meta">${{f.typ||""}}${{f.staerke?" · "+f.staerke:""}}</span></div>`);
  return nsc + auf + fra;
}}

const svg = document.querySelector(".mapcard svg");
const pinRing = svg.querySelector(".pin-ring");
function pin(hex){{
  const poly = svg.querySelector(`polygon[data-hex="${{hex}}"]`);
  if(poly) pinRing.setAttribute("points", poly.getAttribute("points"));
}}
function closeDetail(){{
  scrim.classList.remove("open"); detail.classList.remove("open");
  pinRing.setAttribute("points","");
}}

svg.addEventListener("click", e=>{{
  const poly = e.target.closest("polygon[data-hex]");
  if(poly && WELTEN[poly.getAttribute("data-hex")]) openHex(poly.getAttribute("data-hex"));
}});
document.getElementById("d-close").addEventListener("click", closeDetail);
scrim.addEventListener("click", closeDetail);
document.addEventListener("keydown", e=>{{ if(e.key==="Escape") closeDetail(); }});
</script>
</body></html>"""


# =====================================================================
#  Demo  (mit Beispiel-Verknuepfungen an drei Welten)
# =====================================================================
if __name__ == "__main__":
    from faktionen import erzeuge_fraktionen
    SEED = "Demo-Sektor-2026"
    welten = erzeuge_subsektor(SEED, ss_index=0, dichte="normal")

    # Fraktionen fuer ALLE Welten generieren -> in die Links einspeisen
    beispiel_links: dict = {}
    for wlt in welten:
        frs = erzeuge_fraktionen(wlt, SEED)
        if frs:
            beispiel_links[wlt.hex] = {"fraktionen": [
                {"name": f["name"], "typ": f["art"], "staerke": f["staerke"]} for f in frs
            ]}

    # Manuelle NSC-/Auftrags-Beispiele an drei Welten ergaenzen (mergen,
    # damit die generierten Fraktionen dort erhalten bleiben).
    def _merge(hexc, daten):
        beispiel_links.setdefault(hexc, {}).update(daten)

    _merge("0709", {
        "nscs": [
            {"name": "Sasha Vorne", "rolle": "Patron", "status": "lebendig", "geheim": False},
            {"name": "Kapitän Doric", "rolle": "Schmuggler-Kontakt", "status": "lebendig", "geheim": True},
        ],
        "auftraege": [{"titel": "Verlorene Fracht im Sprungtunnel", "status": "offen"}],
    })
    _merge("0502", {
        "nscs": [{"name": "Dr. Helmer Aung", "rolle": "Forscher", "status": "lebendig", "geheim": False}],
    })
    _merge("0405", {
        "auftraege": [{"titel": "Sabotage am Hydro-Werk", "status": "aktiv"}],
    })

    html = render_app(welten, ss_index=0, sektor_name="DEMO", links=beispiel_links,
                      routen=gen_alle_routen(welten))
    with open("subsektor_A_interaktiv.html", "w", encoding="utf-8") as f:
        f.write(html)
    n_frak = sum(len(v.get("fraktionen", [])) for v in beispiel_links.values())
    print(f"{len(welten)} Welten · {n_frak} Fraktionen · -> subsektor_A_interaktiv.html")
