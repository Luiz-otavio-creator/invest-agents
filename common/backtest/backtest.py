# common/backtest/backtest.py
# Esqueleto de backtest (preparar no futuro com dados reais).
def backtest_signals(signals):
    # Placeholder: sumariza sinais por lado.
    summary = {"BUY": 0, "SELL": 0, "HOLD": 0}
    for s in signals:
        summary[s.get("side","HOLD")] = summary.get(s.get("side","HOLD"),0) + 1
    return summary
