"""
Traveller Hexkarte  ·  SVG-Renderer im SPECTRUM-Look
====================================================

Baut aus den Welt-Objekten (aus sektor_generator.py) oder aus plain dicts
(aus welt_zu_row) eine Subsektor-Hexkarte als SVG.

Geometrie: flache-Oberkante-Hexe in senkrechten Spalten; gerade Spalten
(02,04,06,08,...) sind um ein halbes Hex nach unten versetzt -- die kanonische
Traveller-Subsektordarstellung (8 Spalten x 10 Zeilen).

SPECTRUM-Konventionen (DESIGN.md §7.5 Map Theming, §7.1 Semantik):
  * Stiller dunkler Canvas, Hexgitter als Ghost-Linien (niedrige Deckung).
  * Farbe nur fuer Bedeutung -> Reisezone ueber die semantische Skala:
        gruen = ruhig (kein Ring) | amber = tertiary (solider Ring)
        rot   = interdiziert (error, GESTRICHELTER Ring = Nicht-Farb-Signal)
  * Weltscheibe neutral (on-surface). Gasriese = kleiner offener Kreis.
  * Basen als Mono-Initialen (N/S) links der Scheibe. UWP als Mono-Lockup.

Reine Standardbibliothek.
"""

from __future__ import annotations
from math import cos, sin, radians

try:
    from sektor_generator import erzeuge_subsektor, Welt  # fuer die Demo
except Exception:
    Welt = None

# --- SPECTRUM Tokens -------------------------------------------------
C = {
    "surface":            "#131313",
    "container_lowest":   "#0e0e0e",
    "container_low":      "#1a1a1a",
    "container":          "#212121",
    "primary":            "#A6FF00",
    "secondary":          "#00E0FF",   # informativ (Kommunikationsrouten)
    "tertiary":           "#FF8A00",   # amber / Vorsicht
    "error":              "#FF4D4D",   # rot / interdiziert
    "on_surface":         "#e2e2e2",
    "on_variant":         "#7a7a7a",
    "outline":            "#414a34",
}
FONT_SANS = "'Manrope','Space Grotesk',system-ui,sans-serif"
FONT_MONO = "ui-monospace,'JetBrains Mono',Menlo,Consolas,monospace"

# --- Hex-Geometrie ---------------------------------------------------
R        = 48                 # Umkreisradius (Mitte -> Ecke)
H        = R * 3 ** 0.5       # Hexhoehe (Flaeche -> Flaeche)
MARGIN_X = 28
MARGIN_Y = 40                 # Platz fuer Subsektor-Label oben


def _g(w, key):
    """Lesezugriff, der sowohl fuer Welt-Objekte als auch dicts funktioniert."""
    return getattr(w, key) if hasattr(w, key) else w[key]


def _hex_points(cx: float, cy: float) -> str:
    pts = []
    for deg in (0, 60, 120, 180, 240, 300):
        a = radians(deg)
        pts.append(f"{cx + R * cos(a):.1f},{cy + R * sin(a):.1f}")
    return " ".join(pts)


def _center(lc: int, lr: int, global_col: int) -> tuple[float, float]:
    cx = MARGIN_X + R + (lc - 1) * 1.5 * R
    cy = MARGIN_Y + H / 2 + (lr - 1) * H + (H / 2 if global_col % 2 == 0 else 0)
    return cx, cy


def _svg_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# =====================================================================
#  SVG eines Subsektors
# =====================================================================
def render_svg(welten, ss_index: int, routen=None) -> str:
    ss_col, ss_row = ss_index % 4, ss_index // 4
    nach_hex = {_g(w, "hex"): w for w in welten}
    routen = routen or []

    breite = round(2 * MARGIN_X + 2 * R + 7 * 1.5 * R)
    hoehe  = round(2 * MARGIN_Y + 11.5 * H)

    out: list[str] = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {breite} {hoehe}" '
        f'width="{breite}" height="{hoehe}" font-family="{FONT_SANS}">'
    )
    out.append(f"""<style>
    .hex      {{ fill: {C['container_low']}; stroke: {C['outline']}; stroke-opacity:.18; stroke-width:1; }}
    .hex-amber{{ fill: {C['tertiary']}; fill-opacity:.07; stroke: {C['tertiary']}; stroke-opacity:.85; stroke-width:1.6; }}
    .hex-red  {{ fill: {C['error']};    fill-opacity:.07; stroke: {C['error']};    stroke-opacity:.85; stroke-width:1.6; stroke-dasharray:6 4; }}
    .coord    {{ fill: {C['on_variant']}; font-family:{FONT_MONO}; font-size:9px; text-anchor:middle; }}
    .world    {{ fill: {C['on_surface']}; }}
    .gg       {{ fill:none; stroke: {C['on_variant']}; stroke-width:1.3; }}
    .name     {{ fill: {C['on_surface']}; font-size:12px; font-weight:600; text-anchor:middle; }}
    .uwp      {{ fill: {C['on_variant']}; font-family:{FONT_MONO}; font-size:11px; text-anchor:middle; letter-spacing:.04em; }}
    .base     {{ fill: {C['on_variant']}; font-family:{FONT_MONO}; font-size:10px; font-weight:600; text-anchor:end; }}
    .route-komm  {{ stroke: {C['secondary']}; stroke-width:1.6; stroke-opacity:.55; fill:none; }}
    .route-handel{{ stroke: {C['on_variant']}; stroke-width:1.4; stroke-opacity:.5; fill:none; stroke-dasharray:5 4; }}
    </style>""")
    out.append(f'<rect width="{breite}" height="{hoehe}" fill="{C["surface"]}"/>')

    # Subsektor-Label oben links
    letter = chr(ord("A") + ss_index)
    out.append(
        f'<text x="{MARGIN_X}" y="24" fill="{C["on_variant"]}" '
        f'font-family="{FONT_MONO}" font-size="11px" letter-spacing="0.12em">'
        f'SUBSEKTOR {letter}</text>'
    )

    # Zentren aller Welt-Hexe vormerken (fuer Routenlinien + 2. Durchgang)
    zentren: dict[str, tuple[float, float]] = {}

    # --- Durchgang 1: Hexgitter (Polygone + Koordinaten) ----------------
    for lc in range(1, 9):
        for lr in range(1, 11):
            gcol = ss_col * 8 + lc
            grow = ss_row * 10 + lr
            hexcode = f"{gcol:02d}{grow:02d}"
            cx, cy = _center(lc, lr, gcol)

            w = nach_hex.get(hexcode)
            if w:
                zentren[hexcode] = (cx, cy)
            zone = _g(w, "reisezone") if w else "gruen"
            cls = {"amber": "hex-amber", "rot": "hex-red"}.get(zone, "hex")
            cellcls = " cell" if w else ""
            out.append(f'<polygon class="{cls}{cellcls}" data-hex="{hexcode}" points="{_hex_points(cx, cy)}"/>')
            out.append(f'<text class="coord" x="{cx:.1f}" y="{cy - H/2 + 12:.1f}">{hexcode}</text>')

    # --- Routen-Layer (ueber dem Gitter, unter den Weltscheiben) --------
    # Nur Routen zeichnen, deren beide Enden in DIESEM Subsektor liegen.
    for r in routen:
        a, b = r.get("a"), r.get("b")
        if a in zentren and b in zentren:
            (x1, y1), (x2, y2) = zentren[a], zentren[b]
            klass = "route-komm" if r.get("typ") == "kommunikation" else "route-handel"
            out.append(f'<line class="{klass}" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')

    # --- Durchgang 2: Weltscheiben, Gasriesen, Basen, Namen, UWP --------
    for hexcode, (cx, cy) in zentren.items():
        w = nach_hex[hexcode]

        # Gasriese: kleiner offener Kreis oben rechts
        if _g(w, "gasriesen"):
            out.append(f'<circle class="gg" cx="{cx + R*0.42:.1f}" cy="{cy - H*0.30:.1f}" r="3"/>')

        # Basen-Initialen links der Scheibe (M/S/F/T/K/P)
        basen = _g(w, "basen") or []
        if basen:
            ini = "".join(b[0] for b in basen)
            out.append(f'<text class="base" x="{cx - 12:.1f}" y="{cy + 4:.1f}">{ini}</text>')

        # Weltscheibe
        out.append(f'<circle class="world" cx="{cx:.1f}" cy="{cy:.1f}" r="6.5"/>')

        # Name + UWP unter der Scheibe
        name = _svg_escape(str(_g(w, "name")))
        out.append(f'<text class="name" x="{cx:.1f}" y="{cy + 22:.1f}">{name}</text>')
        out.append(f'<text class="uwp"  x="{cx:.1f}" y="{cy + 36:.1f}">{_g(w, "uwp")}</text>')

    out.append('<polygon class="pin-ring" points="" fill="none"/>')
    out.append("</svg>")
    return "\n".join(out)


# =====================================================================
#  Vollstaendige HTML-Seite mit Studio-Header (SPECTRUM)
# =====================================================================
def render_html(welten, ss_index: int, sektor_name: str = "UNBENANNT", routen=None) -> str:
    svg = render_svg(welten, ss_index, routen=routen)
    letter = chr(ord("A") + ss_index)
    n = len(welten)
    n_amber = sum(1 for w in welten if _g(w, "reisezone") == "amber")
    n_rot   = sum(1 for w in welten if _g(w, "reisezone") == "rot")

    legend = f"""
      <div class="legend">
        <span class="leg"><span class="dot" style="background:{C['on_surface']}"></span>WELT</span>
        <span class="leg"><span class="ring-gg"></span>GASRIESE</span>
        <span class="leg"><span class="swatch amber"></span>AMBER</span>
        <span class="leg"><span class="swatch red"></span>ROT</span>
        <span class="leg"><span class="line-komm"></span>KOMMUNIKATION</span>
        <span class="leg"><span class="line-handel"></span>HANDEL</span>
        <span class="leg"><span class="mono">M</span>MARINE <span class="mono">S</span>SCOUT <span class="mono">F</span>FORSCHUNG <span class="mono">T</span>TAS <span class="mono">K</span>KONSULAT <span class="mono">P</span>PIRATEN</span>
      </div>"""

    return f"""<!doctype html>
<html lang="de"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_svg_escape(sektor_name)} · Subsektor {letter}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&family=Space+Grotesk:wght@500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{{
  --surface:#131313; --container-lowest:#0e0e0e; --container-low:#1a1a1a;
  --container-high:#2a2a2a; --container-highest:#333;
  --primary:#A6FF00; --primary-container:#467000; --on-primary:#0a0a0a;
  --tertiary:#FF8A00; --error:#FF4D4D;
  --on-surface:#e2e2e2; --on-variant:#7a7a7a; --outline:#414a34;
  --radius-sm:.125rem; --radius-md:.375rem;
  --font-body:'Manrope',system-ui,sans-serif;
  --font-mono:ui-monospace,'JetBrains Mono',monospace;
  --gradient:linear-gradient(45deg,var(--primary) 0%,var(--primary-container) 100%);
}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--surface);color:var(--on-surface);font-family:var(--font-body);}}

/* Studio Header (DESIGN.md §5.1) */
.studio-header{{display:flex;align-items:center;justify-content:space-between;height:64px;padding:0 24px;background:var(--surface);}}
.brand{{display:flex;align-items:center;gap:12px;}}
.logo-tile{{display:grid;place-items:center;width:36px;height:36px;border-radius:var(--radius-md);
  background:var(--gradient);color:var(--on-primary);font-family:var(--font-mono);font-weight:700;font-size:1rem;}}
.product{{font-weight:700;font-size:1rem;}}
.tag{{font-family:var(--font-mono);font-size:.75rem;color:var(--on-variant);}}
.actions{{display:flex;align-items:center;gap:8px;}}
.btn{{display:inline-flex;align-items:center;gap:8px;height:40px;padding:0 20px;border:none;border-radius:var(--radius-sm);
  font-family:var(--font-body);font-size:.875rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;cursor:pointer;
  transition:background 120ms cubic-bezier(.2,.8,.2,1),box-shadow 200ms cubic-bezier(.2,.8,.2,1);}}
.btn--ghost{{background:var(--container-high);color:var(--on-surface);}}
.btn--ghost:hover{{background:var(--container-highest);}}
.btn--primary{{background:var(--gradient);color:var(--on-primary);}}
.btn--primary:hover{{box-shadow:0 0 12px rgba(166,255,0,.30);}}
.btn__chevron{{font-family:var(--font-mono);font-size:.7em;opacity:.85;}}

/* Section strip (§5.2) */
.section-strip{{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;padding:12px 24px;background:var(--surface);}}
.slot{{font-family:var(--font-mono);font-size:.68rem;font-weight:500;letter-spacing:.12em;text-transform:uppercase;color:var(--on-variant);}}
.slot--left{{justify-self:start;}} .slot--center{{justify-self:center;display:inline-flex;align-items:center;gap:8px;}}
.slot--right{{justify-self:end;}}
.slot--center b{{color:var(--primary);font-weight:500;}}
.pulse{{width:6px;height:6px;border-radius:9999px;background:var(--primary);box-shadow:0 0 12px rgba(166,255,0,.3);}}

/* Content */
.wrap{{padding:8px 24px 40px;}}
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
</style></head>
<body>
  <header class="studio-header">
    <div class="brand">
      <div class="logo-tile">T</div>
      <span class="product">TRAVELLER</span>
      <span class="tag">STUDIO // v0.1</span>
    </div>
    <div class="actions">
      <button class="btn btn--ghost" type="button">NEU WÜRFELN</button>
      <button class="btn btn--primary" type="button"><span>EXPORT</span><span class="btn__chevron">▼</span></button>
    </div>
  </header>
  <div class="section-strip">
    <span class="slot slot--left">SEKTOR // {_svg_escape(sektor_name)}</span>
    <span class="slot slot--center"><span class="pulse"></span><b>SUBSEKTOR {letter}</b></span>
    <span class="slot slot--right">{n} WELTEN&nbsp;&nbsp;{n_amber} AMBER&nbsp;&nbsp;{n_rot} ROT</span>
  </div>
  <div class="wrap">
    {legend}
    <div class="mapcard">
      {svg}
    </div>
  </div>
</body></html>"""


# =====================================================================
#  Demo
# =====================================================================
if __name__ == "__main__":
    SEED = "Demo-Sektor-2026"
    welten = erzeuge_subsektor(SEED, ss_index=0, dichte="normal")

    with open("subsektor_A.svg", "w", encoding="utf-8") as f:
        f.write(render_svg(welten, ss_index=0))
    with open("subsektor_A.html", "w", encoding="utf-8") as f:
        f.write(render_html(welten, ss_index=0, sektor_name="DEMO"))

    print(f"{len(welten)} Welten gerendert -> subsektor_A.svg / subsektor_A.html")
