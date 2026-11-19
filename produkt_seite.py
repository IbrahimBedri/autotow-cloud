# local_cloud/produkt_seite.py
"""
Öffentliche Produktseite einer fertigen Spule (Route /p/<Nummer> in server.py).

Bewusst ohne Flask und Datenbank: nur Eingabe prüfen und Text/HTML erzeugen,
damit sich das ohne Server testen lässt (tests/test_produkt_seite.py).
Die Seite ist ÖFFENTLICH - sie zeigt nur, was produkte.oeffentliche_daten() an
das Etikett gibt (kein Versuchsname, kein Bediener, keine Reglerdaten).
"""

import html
import re

ID_MUSTER = re.compile(r"^(PR|SIM)-\d{5,}-\d$")
MAX_CSV_BYTES = 8 * 1024 * 1024


def id_gueltig(produkt_id):
    return bool(ID_MUSTER.match(str(produkt_id or "")))


def nutzdaten_pruefen(daten, csv_text):
    """
    Prüft, was die Anlage hochlädt. Wirft ValueError mit lesbarer Meldung.
    Rückgabe: bereinigtes dict (nur die erlaubten Felder).
    """
    if not isinstance(daten, dict) or not id_gueltig(daten.get("id")):
        raise ValueError("invalid product id")
    if csv_text is not None and len(str(csv_text).encode("utf-8")) > MAX_CSV_BYTES:
        raise ValueError("data file too large")
    erlaubt = ("id", "sim", "created", "length_m", "avg_speed", "raw_spool_id", "manufacturer",
               "product", "linear_density", "filament_count", "strength", "modulus",
               "avg_width", "width_mean", "width_std", "oven_mean", "width_target", "width_tol",
               "storage", "contact")
    sauber = {k: daten.get(k) for k in erlaubt}
    # Ein SIM-Kennzeichen kann nicht gegen die Nummer ausgespielt werden
    sauber["sim"] = str(daten["id"]).startswith("SIM-")
    return sauber


def _wert(w, einheit="", stellen=None):
    if w is None or w == "":
        return "-"
    if stellen is not None:
        try:
            w = f"{float(w):.{stellen}f}"
        except (TypeError, ValueError):
            pass
    return html.escape(f"{w}{(' ' + einheit) if einheit else ''}")


_CSS = """
body{font-family:'Segoe UI',Tahoma,sans-serif;background:#f0f2f5;margin:0;padding:16px;color:#222}
.card{max-width:560px;margin:0 auto;background:#fff;border-radius:14px;
      box-shadow:0 4px 15px rgba(0,0,0,.1);overflow:hidden}
.head{background:#2c3e50;color:#fff;padding:18px 20px}
.head h1{margin:0;font-size:22px}.head p{margin:4px 0 0;opacity:.8;font-size:14px}
.sim{background:#c0392b;color:#fff;text-align:center;padding:12px;font-weight:700;letter-spacing:.5px}
.body{padding:8px 20px 20px}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.6px;color:#667;margin:18px 0 4px}
.row{display:flex;justify-content:space-between;gap:12px;border-bottom:1px solid #eee;padding:9px 0}
.row span:first-child{color:#556}.row span:last-child{font-weight:600;text-align:right}
a.btn{display:block;text-align:center;margin-top:20px;padding:12px;border-radius:8px;
      background:#2c3e50;color:#fff;text-decoration:none;font-weight:600}
.foot{text-align:center;color:#889;font-size:12px;margin-top:14px}
"""


def seite_html(daten, csv_vorhanden):
    """Die Produktseite als HTML-Text. 'daten' stammt aus nutzdaten_pruefen()."""
    pid = html.escape(str(daten["id"]))
    zeilen = lambda paare: "".join(
        f'<div class="row"><span>{html.escape(n)}</span><span>{w}</span></div>' for n, w in paare)
    breiten = daten.get("avg_width") or {}
    breite_zeilen = [(f"Sensor {k[1:]}", _wert(v, "mm", 3))
                     for k, v in sorted(breiten.items()) if v is not None]
    if daten.get("width_mean") is not None:
        mittel = f"{float(daten['width_mean']):.3f}"
        if daten.get("width_std") is not None:
            mittel += f" ± {float(daten['width_std']):.3f}"
        breite_block = zeilen([("Width, mean ± std", html.escape(mittel + " mm"))]) + zeilen(breite_zeilen)
    else:
        breite_block = zeilen(breite_zeilen) or zeilen([("Width", "-")])

    if daten.get("width_target") is not None:
        ziel = f"{float(daten['width_target']):.1f}"
        if daten.get("width_tol") is not None:
            ziel += f" ± {float(daten['width_tol']):.1f}"
        breite_block = zeilen([("Target width", html.escape(ziel + " mm"))]) + breite_block
    hinweise = zeilen([(n, _wert(daten.get(k))) for n, k in (("Storage", "storage"), ("Contact", "contact"))
                       if daten.get(k)])

    sim = ('<div class="sim">SIMULATION - TEST LABEL - NOT A REAL PRODUCT</div>'
           if daten.get("sim") else "")
    knopf = (f'<a class="btn" href="/p/{pid}/data.csv">Download measurement data (CSV, 1 Hz)</a>'
             if csv_vorhanden else "")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{pid} - ITA TapeCenter</title><style>{_CSS}</style></head>
<body><div class="card">{sim}
<div class="head"><h1>{pid}</h1><p>ITA TapeCenter · RWTH Aachen University</p></div>
<div class="body">
<h2>Product</h2>
{zeilen([("Produced", _wert(str(daten.get("created") or "")[:10] or None)),
         ("Length", _wert(daten.get("length_m"), "m", 0)),
         ("Mean speed", _wert(daten.get("avg_speed"), "m/min", 2))]
        + ([("Mean oven temperature", _wert(daten.get("oven_mean"), "°C", 0))]
           if daten.get("oven_mean") is not None else []))}
<h2>Starting material (raw roving)</h2>
{zeilen([("Manufacturer", _wert(daten.get("manufacturer"))),
         ("Product", _wert(daten.get("product"))),
         ("Linear density", _wert(daten.get("linear_density"), "tex")),
         ("Filaments", _wert(daten.get("filament_count"))),
         ("Tensile strength", _wert(daten.get("strength"), "MPa", 0)),
         ("Young's modulus", _wert(daten.get("modulus"), "GPa", 0)),
         ("Raw spool", _wert(daten.get("raw_spool_id")))])}
<h2>Measured tape width</h2>
{breite_block}
{('<h2>Notes</h2>' + hinweise) if hinweise else ''}
{knopf}
<div class="foot">Research material · Produced on the ITA AutoTow test rig</div>
</div></div></body></html>"""
