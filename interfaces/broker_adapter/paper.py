# interfaces/broker_adapter/paper.py
# -----------------------------------------------------------------------------
# Paper broker (simulador de execução)
#
# Principais melhorias vs. sua versão:
# - Usa a camada de providers unificada: latest_price() (Yahoo/CG + cache).
# - Fallback defensivo por mapa de preços caso as fontes falhem.
# - Imports de datetime padronizados (sem conflito entre `datetime` e `from datetime import ...`).
# - Timestamps em UTC ISO 8601 consistentes: execuções e histórico do portfólio.
# - Mantém sua regra de lotes: cripto com fração; ações/ETFs inteiros (floor).
# - Sem chamadas diretas a common.utils.providers (legadas).
# -----------------------------------------------------------------------------

import json
import os
import uuid
import math
from typing import Dict
import datetime as dt  # usar dt.datetime, dt.timezone em todo o arquivo

# Camada de providers (unificada). latest_price já escolhe a melhor fonte.
# Se no seu repo ainda não existir, crie common/providers/__init__.py com latest_price.
from common.providers import latest_price

PORTFOLIO = "out/portfolio.json"
PLAN = "out/orchestrator_plan.json"
EXEC_LOG = "out/executions.log"

# ---------------------------
# Utilidades básicas
# ---------------------------

def load_json(p: str):
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(p: str, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def now_utc_iso() -> str:
    """Timestamp UTC em ISO8601, sem microssegundos (ex.: 2025-09-05T19:55:00+00:00)."""
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

def current_nav(port: Dict) -> float:
    """NAV = caixa + soma das posições (estas são market values)."""
    cash = float(port.get("cash_eur", 0.0))
    mv = sum(float(v) for v in (port.get("positions", {}) or {}).values())
    return cash + mv

def is_crypto(inst: str) -> bool:
    return inst.upper() in {"BTC", "ETH", "SOL", "ADA", "DOGE"}

# ---------------------------
# Preço ao vivo com fallback
# ---------------------------

_FALLBACK_PRICE_MAP = {
    # Crypto
    "BTC": 65000.0, "ETH": 3500.0, "SOL": 160.0, "ADA": 0.42, "DOGE": 0.15,
    # Equities/ETFs US/EU
    "VOO": 520.0, "QQQ": 470.0, "VGK": 70.0, "EZU": 55.0,
    "AAPL": 230.10, "MSFT": 415.30, "NVDA": 122.90, "GOOGL": 175.10, "AMZN": 190.75,
    "ASML": 1150.0, "LVMH": 730.0, "SAP": 200.0,
    # Bonds ETFs
    "IEF": 100.0, "TLT": 100.0, "SHY": 100.0, "IEGA": 100.0, "IEAC": 100.0, "LQD": 100.0,
    # REITs
    "VNQ": 90.0, "IPRP": 6.0, "PLD": 120.0, "O": 55.0, "SPG": 150.0,
}

def get_exec_price(inst: str) -> float:
    """
    Obtém preço via providers.latest_price() com fallback.
    - latest_price já tenta Yahoo/CG (com cache, headers, mapeamento EU/UK).
    - Se None/<=0, usa fallback estático por símbolo; por fim, 100.0.
    """
    sym = inst.strip().upper()
    try:
        p = latest_price(sym)
        if p is not None and float(p) > 0:
            return float(p)
    except Exception:
        pass
    return float(_FALLBACK_PRICE_MAP.get(sym, 100.0))

# ---------------------------
# Execução (paper trading)
# ---------------------------

def main():
    # Checagens iniciais
    if not os.path.exists(PORTFOLIO) or not os.path.exists(PLAN):
        print("Precisa de portfolio.json e orchestrator_plan.json")
        return

    port = load_json(PORTFOLIO) or {}
    plan = load_json(PLAN) or {}

    # Garantir estrutura mínima
    port.setdefault("cash_eur", 0.0)
    port.setdefault("positions", {})
    port.setdefault("history", [])

    positions: Dict[str, float] = port.get("positions", {}) or {}
    cash: float = float(port.get("cash_eur", 0.0))

    # ---- Construir mapa de target weights por instrumento ----
    target_w: Dict[str, float] = {}
    for order in plan.get("orders", []):
        inst = str(order.get("instrument_id", "")).strip().upper()
        if not inst:
            continue
        tw = float(order.get("target_weight") or 0.0)
        # Se houver múltiplas entradas (não deveria), pegue a maior
        target_w[inst] = max(tw, target_w.get(inst, 0.0))

    # ---- Vender 100% de instrumentos QUE NÃO ESTÃO NO PLANO ----
    executions = []
    for inst in list(positions.keys()):
        if inst not in target_w:
            cur_mv = float(positions.get(inst, 0.0))
            if cur_mv <= 0.0:
                continue

            price = get_exec_price(inst)
            if price <= 0:
                continue

            # qty para zerar
            if is_crypto(inst):
                qty = round(cur_mv / price, 6)  # cripto: fração
            else:
                qty = math.floor(cur_mv / price)  # ações/ETFs: inteiro
            if qty <= 0:
                continue

            exec_value = qty * price
            # atualização de caixa e posição (armazenamos MV no portfólio)
            cash += exec_value
            positions[inst] = max(0.0, cur_mv - exec_value)

            executions.append({
                "order_id": str(uuid.uuid4()),
                "instrument_id": inst,
                "status": "FILLED",
                "avg_fill": round(price, 6),
                "qty": round(-qty, 6),   # negativo = venda
                "fees": 0.0,
                "timestamp": now_utc_iso()
            })

    # ---- Recalcular NAV após vendas de "fora do plano" ----
    port["positions"] = positions
    port["cash_eur"] = round(cash, 6)
    nav = current_nav(port)

    # ---- Rebalance por delta para instrumentos COM target ----
    # Compra/venda a diferença até atingir market value = nav * target_weight
    for inst, tw in target_w.items():
        price = get_exec_price(inst)
        if price <= 0:
            continue

        desired_mv = nav * tw
        cur_mv = float(positions.get(inst, 0.0))
        delta = desired_mv - cur_mv  # >0 compra | <0 venda

        if abs(delta) < 1e-6:
            continue

        if delta > 0:
            # COMPRA até onde o caixa permitir
            buy_amt = min(delta, cash)
            if buy_amt <= 0:
                continue

            if is_crypto(inst):
                qty = round(buy_amt / price, 6)
                exec_value = qty * price
            else:
                qty = math.floor(buy_amt / price)
                if qty <= 0:
                    continue
                exec_value = qty * price

            positions[inst] = cur_mv + exec_value
            cash -= exec_value

            executions.append({
                "order_id": str(uuid.uuid4()),
                "instrument_id": inst,
                "status": "FILLED",
                "avg_fill": round(price, 6),
                "qty": round(qty, 6),
                "fees": 0.0,
                "timestamp": now_utc_iso()
            })

        else:
            # VENDA (libera caixa)
            sell_amt = min(-delta, cur_mv)  # não vender mais do que tem
            if sell_amt <= 0:
                continue

            if is_crypto(inst):
                qty = round(sell_amt / price, 6)
                exec_value = qty * price
            else:
                qty = math.floor(sell_amt / price)
                if qty <= 0:
                    continue
                exec_value = qty * price

            positions[inst] = cur_mv - exec_value
            cash += exec_value

            executions.append({
                "order_id": str(uuid.uuid4()),
                "instrument_id": inst,
                "status": "FILLED",
                "avg_fill": round(price, 6),
                "qty": round(-qty, 6),  # negativo = venda
                "fees": 0.0,
                "timestamp": now_utc_iso()
            })

    # ---- Limpar posições ~zero por estética ----
    positions = {k: (0.0 if abs(v) < 1e-6 else float(v)) for k, v in positions.items()}
    positions = {k: v for k, v in positions.items() if v > 0.0}

    # ---- Atualizar portfolio e histórico ----
    port["positions"] = positions
    port["cash_eur"] = round(cash, 6)
    new_nav = current_nav(port)
    port["history"].append({
        "event": "rebalance",
        "nav": round(new_nav, 6),
        "ts": now_utc_iso()
    })
    save_json(PORTFOLIO, port)

    # ---- Registrar execuções ----
    os.makedirs(os.path.dirname(EXEC_LOG), exist_ok=True)
    with open(EXEC_LOG, "a", encoding="utf-8") as f:
        for e in executions:
            f.write(json.dumps(e) + "\n")

    print(f"[paper] Execuções: {len(executions)} | Caixa: {round(cash,2)} EUR | NAV: {round(new_nav,2)} EUR.")

if __name__ == "__main__":
    os.makedirs("out", exist_ok=True)
    main()
