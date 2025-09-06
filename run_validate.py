# run_validate.py
import os, json, sys, datetime
from typing import Dict, Any

# Usamos seu utilitário para ler YAML/JSON do strategy
try:
    from common.utils.io import read_yaml_or_json
except Exception:
    read_yaml_or_json = None

STRATEGY_PATH = "config/strategy.yaml"
PLAN_PATH = "out/orchestrator_plan.json"
VAL_JSON = "out/validation.json"
VAL_LOG = "out/validation.log"

EPS = 1e-6

def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def pct(x: float) -> str:
    return f"{x*100:.2f}%"

def main():
    errors = []
    warnings = []
    notes = []

    # --- 1) Ler strategy ---
    if read_yaml_or_json is None:
        print("⚠️  read_yaml_or_json não disponível. Tentando ler strategy como JSON puro...")
        try:
            strategy = load_json(STRATEGY_PATH)
        except Exception as e:
            errors.append(f"Não foi possível ler {STRATEGY_PATH}: {e}")
            strategy = {}
    else:
        try:
            strategy = read_yaml_or_json(STRATEGY_PATH)
        except Exception as e:
            errors.append(f"Não foi possível ler {STRATEGY_PATH}: {e}")
            strategy = {}

    # Campos essenciais
    alloc_target: Dict[str, float] = strategy.get("alloc_target", {})
    bands = float(strategy.get("rebalance", {}).get("bands", 0.0))
    pos_max = float(strategy.get("risk_limits", {}).get("position_max_pct", 1.0))

    if not alloc_target:
        errors.append("alloc_target ausente no strategy.yaml.")
    else:
        # Normaliza alvos só para informação
        s_alloc = sum(alloc_target.values())
        if s_alloc <= 0:
            errors.append("Soma de alloc_target <= 0 no strategy.yaml.")
        elif abs(s_alloc - 1.0) > 1e-6:
            warnings.append(f"Soma de alloc_target = {pct(s_alloc)} (diferente de 100%).")

    # --- 2) Ler plano ---
    if not os.path.exists(PLAN_PATH):
        errors.append(f"Plano não encontrado: {PLAN_PATH}")
        plan = {}
    else:
        try:
            plan = load_json(PLAN_PATH)
        except Exception as e:
            errors.append(f"Erro lendo {PLAN_PATH}: {e}")
            plan = {}

    classes: Dict[str, Dict[str, float]] = plan.get("classes", {}) if isinstance(plan.get("classes"), dict) else {}

    # --- 3) Checks de estrutura ---
    if not classes:
        errors.append("Plano não possui 'classes' ou está vazio.")

    # Classes desconhecidas (no plano mas não no strategy)
    unknown_classes = sorted(set(classes.keys()) - set(alloc_target.keys()))
    if unknown_classes:
        warnings.append(f"Classes no plano que NÃO constam no strategy: {unknown_classes} "
                        f"(ex.: ficou 'fiis' ao invés de 'reits'?)")

    # Classes ausentes (no strategy mas não no plano)
    missing_classes = sorted(set(alloc_target.keys()) - set(classes.keys()))
    if missing_classes:
        warnings.append(f"Classes do strategy AUSENTES no plano: {missing_classes} "
                        f"(sem sinais? plano não somará 100%).")

    # --- 4) Soma por classe vs target ---
    class_sums: Dict[str, float] = {}
    for cls, items in classes.items():
        wsum = sum(float(w) for w in items.values())
        class_sums[cls] = wsum

    # Verifica cada classe-alvo
    for cls, target in alloc_target.items():
        actual = class_sums.get(cls, 0.0)
        lo = target - bands
        hi = target + bands
        if actual < lo - 1e-6 or actual > hi + 1e-6:
            errors.append(
                f"Classe '{cls}': alvo {pct(target)} | obtido {pct(actual)} fora da banda ±{pct(bands)}."
            )
        else:
            notes.append(f"Classe '{cls}': ok (alvo {pct(target)} | obtido {pct(actual)} | banda ±{pct(bands)}).")

    # --- 5) Soma total ~ 100% ---
    total_weight = sum(class_sums.values())
    if abs(total_weight - 1.0) > 1e-3:
        errors.append(f"Soma total do plano = {pct(total_weight)} (não fecha em 100%).")
    else:
        notes.append(f"Soma total = {pct(total_weight)}.")

    # --- 6) Limite por posição (portfolio-level) ---
    violators = []
    for cls, items in classes.items():
        for inst, w in items.items():
            if float(w) > pos_max + 1e-9:
                violators.append((inst, cls, float(w)))
    if violators:
        for inst, cls, w in sorted(violators, key=lambda x: -x[2]):
            errors.append(f"Posição acima do limite: {inst} em {cls} = {pct(w)} > {pct(pos_max)}.")
    else:
        notes.append(f"Nenhum ativo acima de {pct(pos_max)} do portfólio.")

    # --- 7) Resultado ---
    status = "OK" if (not errors) else "FAIL"

    # Print humano-legível
    print("\n========== VALIDAÇÃO DO PLANO ==========")
    print(f"Strategy:  {STRATEGY_PATH}")
    print(f"Plano:     {PLAN_PATH}\n")

    print("Alvos do strategy:")
    for k, v in alloc_target.items():
        print(f"  - {k:<13} {pct(v)}")
    print(f"Bandas: ±{pct(bands)}  |  Limite por posição: {pct(pos_max)}\n")

    if class_sums:
        print("Soma por classe (plano):")
        for k, v in class_sums.items():
            flag = ""
            if k in alloc_target:
                lo, hi = alloc_target[k]-bands, alloc_target[k]+bands
                if v < lo - 1e-6 or v > hi + 1e-6:
                    flag = "  ❌ fora da banda"
                else:
                    flag = "  ✅ ok"
            else:
                flag = "  ⚠️  classe não está no strategy"
            print(f"  - {k:<13} {pct(v)}{flag}")
        print(f"\nTotal: {pct(total_weight)}\n")

    if warnings:
        print("⚠️  Avisos:")
        for w in warnings:
            print("  -", w)
        print()

    if errors:
        print("❌ Erros:")
        for e in errors:
            print("  -", e)
    else:
        print("✅ Tudo certo! Plano dentro das bandas e limites.")

    # --- 8) Persistência (logs) ---
    rec = {
        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "status": status,
        "alloc_target": alloc_target,
        "bands": bands,
        "position_max_pct": pos_max,
        "class_sums": class_sums,
        "total_weight": total_weight,
        "warnings": warnings,
        "errors": errors,
        "notes": notes,
    }

    os.makedirs("out", exist_ok=True)
    with open(VAL_JSON, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    with open(VAL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Exit code útil para CI/automação
    sys.exit(0 if status == "OK" else 1)

if __name__ == "__main__":
    main()
