# run_all.py
import subprocess, sys, os

def run(mod):
    print(f"\n$ python -m {mod}")
    subprocess.run([sys.executable, "-m", mod], check=True)

def run_script(path):
    print(f"\n$ python {path}")
    subprocess.run([sys.executable, path], check=True)

def main():
    os.makedirs("out", exist_ok=True)

    # Etapas dos agentes
    run("agents.equities.agent")
    run("agents.crypto.agent")
    run("agents.fixed_income.agent")
    run("agents.reits.agent")

    # Orquestração e execução
    run("orchestrator.main")
    run("interfaces.broker_adapter.paper")

    # Validação (rodar antes do relatório)
    run_script("run_validate.py")

    # Relatório final
    run("interfaces.reporting.report_html")

    print("\n✅ Pipeline concluído. Veja out/report.html")

if __name__ == "__main__":
    main()
