# orchestrator/main.py
import json, os
from common.utils.io import read_yaml_or_json, write_json
from common.risk.risk import cap_position_weights

STRATEGY = "config/strategy.yaml"
OUT_PLAN = "out/orchestrator_plan.json"

def load_signals():
    paths = [
        "out/signals_equities.json",
        "out/signals_crypto.json",
        "out/signals_fixed_income.json",
        "out/signals_reits.json",   # REITs
    ]
    all_sigs = []
    for p in paths:
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                try:
                    all_sigs.extend(json.load(f))
                except Exception:
                    pass
    return all_sigs

def infer_class(instrument_id: str) -> str:
    # REITs (tickers/ETFs comuns)
    if instrument_id in {"VNQ", "IPRP", "IWDP", "PLD", "O", "SPG"}:
        return "reits"
    # Crypto
    if instrument_id in {"BTC", "ETH"}:
        return "crypto"
    # Fixed income (ETFs/códigos)
    if instrument_id in {"IEF", "TLT", "SHY", "IEGA", "IEAC", "LQD", "BUND"}:
        return "fixed_income"
    # Ações/ETFs de ações como padrão
    return "equities"

def build_plan(strategy, signals):
    # Agrupa por classe dinamicamente (evita KeyError ao surgir 'reits' ou outras classes)
    by_class = {}
    for s in signals:
        inst = s["instrument_id"]
        cls = infer_class(inst)
        conf = float(s.get("confidence", 0.5))
        by_class.setdefault(cls, {})
        by_class[cls][inst] = max(conf, by_class[cls].get(inst, 0.0))

    target_alloc = strategy.get("alloc_target", {})
    pos_max = float(strategy["risk_limits"]["position_max_pct"])

    plan = {"classes": {}, "orders": []}

    for cls, insts in by_class.items():
        if not insts:
            continue
        s = sum(insts.values())
        if s <= 0:
            continue

        # Pesos intra-classe por confiança, com teto por posição
        intra = {k: v / s for k, v in insts.items()}
        intra = cap_position_weights(intra, pos_max)

        # Peso da classe conforme strategy (0.0 se não houver)
        class_weight = float(target_alloc.get(cls, 0.0))
        class_weight = max(0.0, min(1.0, class_weight))

        class_plan = {k: round(class_weight * w, 6) for k, w in intra.items()}
        plan["classes"][cls] = class_plan

        for inst, tw in class_plan.items():
            plan["orders"].append({
                "instrument_id": inst,
                "action": "INCREASE" if tw > 0 else "HOLD",
                "target_weight": tw,
                "max_notional": None
            })

    return plan

def main():
    strategy = read_yaml_or_json(STRATEGY)
    signals = load_signals()
    plan = build_plan(strategy, signals)
    write_json(OUT_PLAN, plan)
    print(f"[orchestrator] plano salvo em {OUT_PLAN}")

if __name__ == "__main__":
    os.makedirs("out", exist_ok=True)
    main()
