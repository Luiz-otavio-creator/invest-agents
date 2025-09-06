# interfaces/reporting/report_html.py
import os, json, datetime
from html import escape
import plotly.graph_objects as go

PLAN = "out/orchestrator_plan.json"
PORTFOLIO = "out/portfolio.json"
SIGNALS = [
    "out/signals_equities.json",
    "out/signals_crypto.json",
    "out/signals_fixed_income.json",
    "out/signals_reits.json"
]
OUT_HTML = "out/report.html"

# -----------------------------
# Helpers
# -----------------------------
def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def fmt_eur(x):
    try:
        return f"{float(x):,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(x)

def pct(x):
    try:
        return f"{float(x)*100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(x)

def render_table(headers, rows):
    if not rows:
        return "<p class='text-muted mb-0'>Nenhum dado disponível.</p>"
    thead = "".join(f"<th>{escape(h)}</th>" for h in headers)
    trs = []
    for row in rows:
        tds = "".join(f"<td>{cell}</td>" for cell in row)
        trs.append(f"<tr>{tds}</tr>")
    return f"""
    <table class="table table-striped table-bordered table-sm align-middle">
      <thead class="table-light"><tr>{thead}</tr></thead>
      <tbody>{''.join(trs)}</tbody>
    </table>
    """

def truncate(s: str, n: int = 90) -> str:
    """Evita frases longas em tabelas. Retorna HTML com tooltip."""
    if not s:
        return ""
    s = str(s)
    if len(s) <= n:
        return escape(s)
    short = escape(s[:n].rstrip()) + "…"
    # tooltip com o texto completo
    return f"<span title='{escape(s)}'>{short}</span>"

# -----------------------------
# Charts
# -----------------------------
def chart_alloc_by_class(plan):
    classes = plan.get("classes", {})
    labels, values = [], []
    for cls, items in classes.items():
        labels.append(cls)
        values.append(sum(float(w) for w in items.values()))
    if not labels:
        return ""
    fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.4)])
    fig.update_layout(title="Alocação por Classe", margin=dict(l=10, r=10, t=40, b=10))
    return fig.to_html(full_html=False, include_plotlyjs=False)

def chart_positions_bar(port):
    pos = port.get("positions", {})
    if not pos:
        return ""
    items = sorted(pos.items(), key=lambda kv: -float(kv[1]))[:10]
    labels = [k for k, _ in items]
    values = [float(v) for _, v in items]
    fig = go.Figure([go.Bar(x=labels, y=values, text=[fmt_eur(v) for v in values], textposition="auto")])
    fig.update_layout(title="Top Posições (Market Value)", yaxis_title="EUR", margin=dict(l=10, r=10, t=40, b=10))
    return fig.to_html(full_html=False, include_plotlyjs=False)

def chart_nav_curve(port):
    hist = port.get("history", [])
    if not hist:
        return ""
    dates, navs = [], []
    now = datetime.datetime.utcnow()
    for i, x in enumerate(hist):
        navs.append(float(x.get("nav", 0.0)))
        ts = x.get("ts")
        if ts:
            try:
                dates.append(datetime.datetime.fromisoformat(ts.replace("Z","")))
            except Exception:
                dates.append(now - datetime.timedelta(minutes=len(hist)-i))
        else:
            dates.append(now - datetime.timedelta(minutes=len(hist)-i))
    fig = go.Figure([go.Scatter(x=dates, y=navs, mode="lines+markers", name="NAV")])
    fig.update_layout(title="Evolução do NAV", xaxis_title="Data", yaxis_title="NAV (EUR)", margin=dict(l=10, r=10, t=40, b=10))
    return fig.to_html(full_html=False, include_plotlyjs=False)

# -----------------------------
# Signals
# -----------------------------
def collect_signals():
    rows, all_signals = [], []
    for path in SIGNALS:
        sigs = load_json(path, [])
        for s in sigs:
            all_signals.append(s)
            rows.append([
                s.get("instrument_id", ""),
                s.get("side", ""),
                f"{s.get('confidence', 0):.2f}",
                truncate(s.get("rationale", "")),  # <- curta na tabela + tooltip
                f"{s.get('ttl_days', '')}d",
                s.get("collected_at", "")
            ])
    return rows, all_signals

# -----------------------------
# Insights Automáticos
# -----------------------------
def build_insights(plan, port, signals):
    insights = []
    cls = plan.get("classes", {})
    if cls:
        weights = {c: sum(float(w) for w in items.values()) for c, items in cls.items()}
        dom = max(weights, key=weights.get)
        insights.append(f"A classe com maior peso no plano é <b>{escape(dom)}</b> com {pct(weights[dom])}.")
    pos = port.get("positions", {})
    if pos:
        top = max(pos.items(), key=lambda kv: float(kv[1]))
        insights.append(f"A maior posição atual é <b>{escape(str(top[0]))}</b>, no valor de {fmt_eur(top[1])}.")
    strong = [s for s in signals if s.get("side")=="BUY" and s.get("confidence",0)>=0.7]
    if strong:
        tickers = ", ".join(escape(s.get("instrument_id","")) for s in strong[:5])
        insights.append(f"Foram detectados sinais fortes de compra em: <b>{tickers}</b>.")
    else:
        insights.append("Nenhum sinal de compra forte identificado nesta rodada.")
    total = sum(float(v) for v in pos.values()) or 1.0
    for k,v in pos.items():
        if float(v)/total > 0.25:
            insights.append(f"Atenção: <b>{escape(k)}</b> representa mais de 25% do portfólio.")
    return insights

# -----------------------------
# Rankings
# -----------------------------
def build_rankings(signals):
    buys = sorted([s for s in signals if s.get("side")=="BUY"], key=lambda s: -s.get("confidence",0))[:5]
    sells = sorted([s for s in signals if s.get("side")=="SELL"], key=lambda s: -s.get("confidence",0))[:5]

    def rows(data):
        return [
            [s.get("instrument_id",""), f"{s.get('confidence',0):.2f}", truncate(s.get("rationale",""))]
            for s in data
        ]
    return (
        render_table(["Instrumento","Confiança","Rationale"], rows(buys)),
        render_table(["Instrumento","Confiança","Rationale"], rows(sells))
    )

# -----------------------------
# Extra: tabela de alocação por classe
# -----------------------------
def build_alloc_table(plan):
    classes = plan.get("classes", {})
    rows = []
    for cls, items in classes.items():
        wsum = sum(float(w) for w in items.values())
        rows.append([escape(cls), pct(wsum), f"{len(items)}"])
    rows.sort(key=lambda r: r[0])
    return render_table(["Classe", "Peso Total", "# Ativos"], rows)

# -----------------------------
# Main
# -----------------------------
def main():
    os.makedirs("out", exist_ok=True)

    plan = load_json(PLAN, {"classes": {}, "orders": []})
    port = load_json(PORTFOLIO, {"cash_eur": 0.0, "positions": {}, "history": []})
    nav = float(port.get("cash_eur", 0.0)) + sum(float(v) for v in port.get("positions", {}).values())

    sig_rows, signals = collect_signals()
    insights = build_insights(plan, port, signals)
    top_buys, top_sells = build_rankings(signals)
    alloc_tbl = build_alloc_table(plan)

    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    html = f"""
<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <title>Invest Agents — Relatório</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
  <style>
    body {{ margin:20px; }}
    h1 {{ margin-bottom:0; }}
    .muted {{ color:#666; font-size:13px; }}
    .card {{ margin-bottom:20px; }}
    .card h6 {{ color:#666; font-weight:600; letter-spacing:.02em; }}
  </style>
</head>
<body>
  <header class="mb-4">
    <h1>Invest Agents — Relatório</h1>
    <div class="muted">Gerado em {escape(ts)}</div>
  </header>

  <div class="row mb-4">
    <div class="col-md-3 card p-3">
      <h6>NAV</h6><h4>{fmt_eur(nav)}</h4>
    </div>
    <div class="col-md-3 card p-3">
      <h6># Classes</h6><h4>{len(plan.get("classes", {}))}</h4>
    </div>
    <div class="col-md-3 card p-3">
      <h6># Posições</h6><h4>{len(port.get("positions", {}))}</h4>
    </div>
  </div>

  <div class="card p-3">
    <h3>Insights Automáticos</h3>
    <ul class="mb-0">
      {''.join(f"<li>{i}</li>" for i in insights)}
    </ul>
  </div>

  <div class="row">
    <div class="col-md-6 card p-3">
      {chart_alloc_by_class(plan)}
      <div class="mt-3">{alloc_tbl}</div>
    </div>
    <div class="col-md-6 card p-3">{chart_positions_bar(port)}</div>
  </div>

  <div class="row">
    <div class="col card p-3">{chart_nav_curve(port)}</div>
  </div>

  <div class="card p-3">
    <h3>Ranking de Sinais</h3>
    <div class="row">
      <div class="col-md-6">
        <h5>Top 5 Compras (BUY)</h5>
        {top_buys}
      </div>
      <div class="col-md-6">
        <h5>Top 5 Vendas (SELL)</h5>
        {top_sells}
      </div>
    </div>
  </div>

  <div class="card p-3">
    <h3>Sinais Detalhados</h3>
    {render_table(["Instrumento","Side","Confiança","Rationale","TTL","Coletado"], sig_rows)}
  </div>
</body>
</html>
    """
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[report] Relatório salvo em {OUT_HTML}")

if __name__ == "__main__":
    main()
