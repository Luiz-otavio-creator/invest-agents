# Invest Agents — Starter (MVP)

Este pacote cria um **MVP funcional** do sistema de agentes para investimentos.
Ele é 100% Python **stdlib** (sem dependências externas) e usa um **barramento baseado em arquivos** para mensagens.

## O que está incluso

- **config/strategy.yaml** — diretrizes da carteira (alvos, bandas, risco, execução).
- **agents/** — quatro agentes especialistas (ações, cripto, renda fixa, FIIs) que geram sinais.
- **orchestrator/** — orquestra sinais, aplica alocação alvo e bandas, gera um plano.
- **interfaces/broker_adapter/** — simulador de execução (paper trading) e estado de portfólio.
- **interfaces/reporting/** — gera um relatório HTML simples em `out/report.html`.
- **data/mock/** — universos e dados fictícios para o MVP.
- **out/** — mensagens trocadas e artefatos (sinais, plano, execuções, relatório).

## Como rodar

1. (Opcional) Crie um venv.
2. Rode o pipeline completo:

```bash
python run_all.py
```

3. Veja o **relatório** em: `out/report.html`

### Rodar por partes

```bash
# Gerar sinais
python agents/equities/agent.py
python agents/crypto/agent.py
python agents/fixed_income/agent.py
python agents/fiis/agent.py

# Orquestrar (gera plano consolidado)
python orchestrator/main.py

# Executar plano (paper trading) e atualizar carteira
python interfaces/broker_adapter/paper.py

# Gerar relatório
python interfaces/reporting/report_html.py
```

## Observações

- O arquivo `config/strategy.yaml` tem comentários para orientar ajustes.
- O sistema está pronto para evoluir para mensageria real (Kafka/RabbitMQ) e APIs.
- Você pode substituir os dados de `data/mock/` por dados reais e plugar suas fontes/APIs.
- # O código foi escrito para ser **didático e extensível**.

Para tornar a sua ferramenta realmente excepcional na análise de investimentos e recomendação de portfólios, é preciso otimizar várias frentes – desde a coleta de dados até o modelo de decisão, passando por gestão de risco e usabilidade. Abaixo um plano profissional para evoluir sua plataforma para “estado da arte”:

1- Fortalecer as fontes de dados

Múltiplos provedores: mantenha o Yahoo Finance e CoinGecko como base, mas adicione AlphaVantage/FRED (séries macroeconómicas e dados fundamentalistas), IEX Cloud (preços intradiários e volume) e fontes especializadas em bonds (ex. índice Bloomberg Barclays). Combine preços de várias APIs para reduzir falhas.

Caching e atualização: implemente um serviço de cache/distribuição (Redis) para armazenar dados mais recentes e reduzir chamadas repetidas às APIs. Agende atualizações em background em intervalos definidos (ex.: 15 min para ações, 1 h para bonds).

Dados fundamentais e qualitativos: incorpore indicadores como margem operacional, dívida/EBITDA, crescimento de receitas e lucros, bem como métricas ESG e insights de relatórios corporativos. Isso enriquece o ranking dos ativos.

2- Melhorar os agentes de sinal

Algoritmos multifatoriais: em vez de heurísticas simples, treine modelos baseados em aprendizado de máquina (ML) para ranking de ações (ex.: Gradient Boosting ou Random Forest) usando features técnicos (momentum, volatilidade), fundamentalistas (ROE, P/L), macroeconómicos e de sentimento (notícias, mídias sociais).

Agente de bonds sofisticado: em vez de durations fixas e yields aproximados, extraia os “SEC yield” e “option-adjusted spreads”, e use modelos de curva de juros (ex.: Nelson-Siegel) para estimar retorno/risco.

Especialização regional/sectorial: crie subagentes focados por região (EUA, Europa, Emergentes) ou por setor (tecnologia, energia, saúde). Isso melhora a granularidade das recomendações.

Aprendizado online e feedback: permita que os agentes ajustem seus parâmetros com base na performance (ex.: se um sinal repetidamente falhar, diminua seu peso). Use métricas como Sharpe/Sortino, drawdown e hit rate para retroalimentar o sistema.

3- Otimização e gestão de risco

Modelo de alocação baseado em fronteira eficiente: incorpore otimização moderna de portfólios (ex.: média-variância, Black-Litterman, CVaR) para encontrar pesos ótimos dados os retornos esperados e a matriz de covariância.

Controle de risco dinâmico: implemente limites por ativo e por setor/região; use Value-at-Risk (VaR) e Expected Shortfall para monitorar caudas; ajuste a alocação conforme a volatilidade implícita do mercado.

Simulações de stress: rode cenários adversos (ex.: aumento de juros, choque de commodities) para avaliar impacto na carteira e recomendar ajustes proativos.

Integração com hedge: como sua base é em euros, defina políticas de hedge para activos em outras moedas (USD, GBP). Use forwards/ETFs hedged para reduzir risco cambial.

4- Execução e automação

Integração com corretoras: conecte APIs de brokers (Interactive Brokers, Saxo, Degiro) para executar ordens de forma automatizada. Implemente lógicas de lote, slippage e controle de custos.

Rebalanceamento inteligente: automatize decisões de rebalanceamento usando gatilhos combinados (tempo + desvios de pesos + mudanças de risco). Respeite custos de transação e impostos (ex.: limite para realizar lucros de longo prazo).

Controle de liquidez e alavancagem: monitore liquidez dos ativos e evite ordens grandes em ativos ilíquidos; impeça alavancagem indesejada, a não ser que seja parte da estratégia.

5- Relatórios e interface de usuário

Dashboard interativo: evolua o report em HTML para um painel em tempo real (usando frameworks como Dash ou Streamlit) com gráficos dinâmicos, drill-down por ativo, comparação com benchmarks e cálculo de indicadores (Sharpe, Treynor, Alpha).

Insights de analista: além das estatísticas, gere textos automáticos comentando motivos de cada recomendação (ex.: “GOOGL recomendado por forte crescimento de receitas e múltiplos atrativos”) e alertas sobre concentrações de risco.

Comparações com estratégias consagradas: mostre ao usuário como sua carteira se alinha ou difere de portfólios famosos (ex.: All Weather, 60/40, Value), permitindo misturar estilos (Buffett, Dalio, Marks) de forma flexível.

Acompanhamento de performance: disponibilize histórico de NAV, retornos acumulados vs benchmark (MSCI ACWI, Bloomberg Global Aggregate), drawdowns e contribuição por ativo/classe.

6- Arquitetura e escalabilidade

Serviços desacoplados: separe coleta de dados, geração de sinais, otimização de portfólio, execução e reporting em microserviços comunicando por filas (ex.: Kafka). Isso facilita escalar e dar manutenção.

Testes e monitoramento: crie suíte de testes unitários para cada agente e monitore em produção (logs, métricas de latência, alertas). Use versionamento de modelos para poder reverter se uma nova versão degradar performance.

Segurança e conformidade: implemente autenticação segura, criptografe chaves API, proteja dados pessoais e alinhe-se à legislação financeira (MiFID II na UE, SEC nos EUA).

7- Pesquisa contínua e benchmark

Análises externas: regularmente leia relatórios e papers de gestores de renome (ex.: cartas do Howard Marks, Bridgewater, BlackRock) e atualize os critérios dos agentes.

Machine learning avançado: explore redes neurais para previsão de séries financeiras, reinforcement learning para rebalanceamento dinâmico e análises de NLP em larga escala para medir sentimento de mercado (Twitter, notícias).

Backtests e simulações: mantenha uma infraestrutura de backtest para testar novas estratégias em dados históricos (e.g., 10 anos de dados), inclusive levando em conta custos, impostos e períodos de crise.

## Em síntese, o caminho para transformar sua solução em “a melhor do mundo” passa por combinar dados de qualidade, modelos robustos, gestão de risco inteligente, automação segura e uma experiência de usuário clara e justificável. Ao incorporar tanto as técnicas de ponta do mercado financeiro quanto princípios de gestores renomados, sua plataforma se torna uma poderosa aliada para decisões de investimento informad

aplicando etapa1 :

1. Múltiplos provedores de dados

Crie uma camada de abstração para provedores

Defina uma interface DataProvider com métodos como get_price(symbol), get_historical_prices(symbol, start_date, end_date), get_fundamentals(symbol) e get_macro_series(series_name).

Cada provedor (Yahoo, CoinGecko, AlphaVantage, FRED, IEX, Bloomberg) implementará essa interface; assim, o orquestrador não precisa conhecer detalhes de cada API.

Use arquivos separados (providers/yahoo.py, providers/coingecko.py, etc.) e documente cada método com docstrings explicando o que retorna e quais erros podem ser lançados.

Adicionar AlphaVantage e FRED

AlphaVantage: utilize o Economic Indicators API para indicadores macroeconómicos (GDP, yields, inflação, etc.)
alphavantage.co
; também oferece cotações históricas, intraday e dados fundamentalistas (earnings, balanços).

FRED (St. Louis Fed): oferece séries macroeconómicas oficiais (PIB, desemprego, índice de preços, curvas de juros). A maioria dos endpoints é gratuita, mas requer um api_key.

Crie módulos que façam chamadas HTTP, tratem códigos de erro e convertam os dados brutos em pandas DataFrames.

Adicionar IEX Cloud

O IEX Cloud fornece preços intradiários (tick‑by‑tick), volume de negociação, book de ofertas e dados fundamentalistas (dividendos, splits).

Para usar, registre uma conta e configure um token. No módulo providers/iex.py, implemente get_intraday(symbol) para buscar candles de 1 min; crie uma função get_volume(symbol) para volume acumulado do dia.

Dados de bonds (Bloomberg ou alternativo)

Se tiver acesso a APIs Bloomberg (por ex. Bloomberg Barclays Bond Indices), crie um módulo providers/bloomberg.py que busca curvas de rendimento, spreads de crédito e índices de renda fixa.

Caso não tenha, use fontes gratuitas como FRED para Treasury yield curves (ex.: série “DGS10” para o T‑10 anos).

Combinação de preços

Para reduzir falhas de provedores, implemente um método get_composite_price(symbol) que tente múltiplas fontes na ordem de confiabilidade. Ex.:

def get_composite_price(symbol):
for prov in [iex_provider, alpha_provider, yahoo_provider]:
try:
price = prov.get_price(symbol)
if price:
return price
except Exception:
continue
return None # ou raise para o chamador tratar

Comente explicando a escolha da ordem (por ex. IEX para intraday, AlphaVantage/Yahoo para diários).

2. Caching e atualização

Configurar Redis

Instale redis e redis-py. No módulo cache.py, crie funções get_cached(key) e set_cached(key, value, ttl) para armazenar respostas de APIs.

Use chaves consistentes, como f"price:{provider}:{symbol}" ou f"macro:{series_name}".

Explique em comentários que o TTL (time‑to‑live) deve ser curto para preços (10–15 min) e mais longo para indicadores macro (1–24 h).

Agendar tarefas de atualização

Use um agendador como Celery Beat, APScheduler ou cron para rodar “jobs” que atualizam o cache periodicamente.

Ex.: agendar update_equities() a cada 15 min, update_bonds() a cada hora e update_macro() 1 vez por dia.

Cada job chama provider.get\_\* e salva no Redis; comente claramente no código qual a frequência e por quê (ex.: ações são mais voláteis, bonds mudam menos).

Fallback em caso de falha de provedor

Nos módulos de provedores, encapsule chamadas de API em blocos try/except e retorne None ou um valor do cache caso haja exceção.

Comente que essa prática garante resiliência: se uma API cair, o sistema continua respondendo com dados frescos de outras fontes ou do cache.

3. Dados fundamentais e qualitativos

Margens e alavancagem

Use o endpoint de fundamental data do AlphaVantage (função BALANCE_SHEET e INCOME_STATEMENT) para extrair margem operacional, margem líquida, dívida/EBITDA, cobertura de juros, etc.

No código, construa DataFrames com essas métricas e explique via comentários que elas serão normalizadas (ex.: dividir por sector para ver desvio).

Crescimento de receita e lucros

A partir dos mesmos endpoints, calcule crescimento QoQ/YoY de receitas e EPS. Guarde no banco e use nos scores dos agentes (ex.: maior crescimento + maior margem → maior confiança).

Comente que os dados fundamentalistas são atualizados somente a cada trimestre, então podem ter TTL maior no cache (30 dias).

Métricas ESG

Integre APIs de ESG (ex.: Sustainalytics, Refinitiv, ou serviços gratuitos como esg.Datasets) para obter scores ambientais, sociais e de governança.

Crie campos como esg_score, environmental_score e documente que serão usados para filtrar empresas “controversas” ou premiar empresas sustentáveis.

Insights qualitativos

Desenvolva um módulo de NLP que faça parse de relatórios de resultados, transcrições de conference calls ou notícias para extrair “sentimento corporativo”.

Por exemplo, use modelos como FinBERT para classificar frases em positivas/negativas, e registre uma pontuação de sentimento para cada ação.

Comente no código que esse processamento é mais pesado e deve rodar em batch (talvez diário).

4. Comentários e boas práticas no projeto

Docstrings e type hints: para cada módulo e função, escreva comentários claros sobre parâmetros, retornos e exceções. Isso facilita manutenção e onboarding.

Configuração por ambiente: salve chaves de API e endpoints em um arquivo .env ou config.py, nunca no código. Explique em comentários que isso é importante por questões de segurança e escalabilidade.

Logs estruturados: registre em log (preferencialmente JSON) cada chamada a provedores, com tempo de resposta e status; isso ajuda a monitorar falhas.

Testes unitários: escreva testes para cada provedor e função de cache; comente o objetivo de cada teste (ex.: “garante que o cache retorna dados se a API falhar”).

Versionamento e reprodutibilidade: use um controle de versão para scripts de coleta e modelos. Anote no README as dependências e instruções de uso.

Exemplo de estrutura de diretórios comentada
invest-agents/
├── providers/
│ ├── **init**.py # expõe classes dos provedores
│ ├── base.py # define a interface DataProvider
│ ├── yahoo.py # implementa métodos do Yahoo Finance
│ ├── alphavantage.py
│ ├── fred.py
│ ├── iex.py
│ ├── bloomberg.py
│ └── ...
├── cache.py # funções de get/set em Redis
├── jobs/
│ ├── update_equities.py # tarefas agendadas de atualização
│ ├── update_macro.py
│ └── ...
├── agents/
│ ├── equities/
│ ├── fixed_income/
│ ├── reits/
│ ├── crypto/
│ └── ...
└── README.md # documentação de setup e uso

Cada arquivo deve estar bem comentado, explicando a responsabilidade do módulo, as dependências externas e a forma de integração com o restante do sistema.

Conclusão

Fortalecer as fontes de dados passa por tornar o sistema multifonte, resiliente, documentado e automatizado. Ao integrar AlphaVantage e FRED para macro e fundamentals
alphavantage.co
, IEX Cloud para intraday e volumes, e fontes de bonds, você aumenta a qualidade e abrangência dos dados. Implementar caching com Redis e jobs de atualização evita sobrecarregar as APIs e garante frescor. Incorporar métricas fundamentais (margens, dívida/EBITDA, crescimento) e ESG eleva a análise para além dos preços, permitindo recomendações mais acertadas. Documente tudo com comentários claros e type hints para facilitar a manutenção e a evolução do projeto.

---

chaves api:
Bem-vindo ao Alpha Vantage! Sua chave de acesso dedicada é: 1QO75EJ1DSFS8GNQ. Guarde esta chave de API em um local seguro para acesso futuro aos seus dados.

Your registered API key is: 74fd1270347296b8c6d1deda69ffac83 Documentation is available on the St. Louis Fed web services website.

---

✅ Já feito

1. Fortalecer as fontes de dados

Yahoo Finance integrado (preços, históricos, dividendos).

CoinGecko integrado com fallback (mock + cache + backoff).

AlphaVantage integrado (overview → PE, ROE, Profit Margin).

FRED integrado (macro séries, ex.: juros DGS10).

Cache local (FileCache) implementado → TTLs definidos no .env.

2. Agentes de sinal

Equities → já usam histórico + fundamentos AlphaVantage + boost de ETFs.

Crypto → já usam médias móveis (MA50, MA200) + fallback robusto.

Fixed income → usam heurísticas com yield aproximado + duração + FRED.

REITs → já avaliando dividend yield.

Todos publicam sinais consistentes em JSON, com rationale.

4. Execução e automação

Paper broker → implementado:

Suporte a cripto (frações) vs. ações/ETFs (inteiros).

NAV atualizado com histórico.

Execuções logadas (executions.log).

Rebalanceamento automático vs. plano.

5. Relatórios

Report HTML já consolidado:

NAV, classes, posições e ordens.

Validação do plano.

Estrutura pronta para gráficos interativos (precisa do Plotly instalado).

🟡 Em andamento

CoinGecko ainda limita requests (401/429). Solução → cache agressivo + backoff (já sugeri o patch).

Paper broker → ainda sem custos de corretagem e slippage (já te passei o plano de patch).

Relatórios → HTML ainda estático, sem gráficos dinâmicos. Precisa de:

Instalar Plotly (pip install plotly).

Renderizar alocação, NAV curve e sinais.

🔜 Próximos passos (do plano maior)

1. Fontes de dados

Adicionar IEX Cloud (gratuito até certo limite → preços intraday).

Explorar proxies gratuitos para bonds (já que Bloomberg Barclays é pago).

Expandir fundamentals (ex.: dívida/EBITDA, crescimento de receitas).

2. Agentes de sinal

Evoluir heurísticas → modelos multifatoriais/ML.

Criar subagentes regionais e setoriais.

Aprendizado online → feedback loop com métricas (Sharpe, drawdown).

3. Gestão de risco

Otimização de portfólio (média-variância, Black-Litterman, CVaR).

Value-at-Risk e stress tests.

Regras de hedge cambial (EUR base).

4. Execução

Custos e slippage no paper broker.

Bandas por ativo e ticket mínimo.

Integração com brokers reais (IBKR, Saxo).

5. Relatórios/UI

Evoluir de HTML → dashboard interativo (Dash/Streamlit).

Cálculo e exibição de Sharpe, Sortino, drawdown.

Comparação com benchmarks (60/40, All Weather).

6. Arquitetura

Quebrar em microserviços (coleta, sinal, otimização, execução, reporting).

Testes unitários + monitoramento.

7. Pesquisa contínua

Infra de backtest (10+ anos de dados).

Incorporar estratégias de gestores renomados.

Explorar ML avançado (XGBoost, RL, NLP).

👉 Resumindo:

Etapa 1 (dados) → ✅ quase completa (só falta IEX Cloud e bonds mais ricos).

Etapa 2 (sinais) → 🟡 bem montada, precisa evoluir para multifator/ML.

Etapa 3 (risco) → 🔜 ainda não começamos.

Etapa 4 (execução) → 🟡 funcionando no paper, falta custos/slippage/bandas.

Etapa 5 (relatórios) → 🟡 funcionando, mas precisa gráficos e métricas avançadas.

Etapa 6-7 → 🚧 ainda no planejamento.

Quer que eu prepare agora os patches imediatos (curto prazo, alto impacto) para:

Paper broker com custos + slippage + ticket mínimo

Report com gráficos Plotly interativos (pizza alocação, curva NAV, tabela sinais)

## Assim você já eleva a ferramenta para “nível pro”?

etapa 2:

Milestone 1 — Base de ML multifatorial (dados, features, rótulos)

1. Estrutura de pastas

Criar:

features/ → extração/transformação de fatores

ml/datasets/ → montagem de dataset tabular (parquet/csv)

ml/trainers/ → treino e validação

ml/models/ → artefatos .joblib e metadados

ml/utils/ → utilidades (split temporal, métricas, seeds)

config/ml/\*.yaml → hiperparâmetros por agente

DoD: pastas versionadas; placeholders com **init**.py.

2. Feature library (gratuito)

features/base_features.py

Preço (yfinance): retornos 1/3/6/12m, volatilidade (EWMA), drawdown, beta com benchmark (VOO/VGK).

Técnicos: SMA(20/50/200), RSI(14), MACD (rápido).

Fundamental (AlphaVantage): PE, PB, ROE, margem, FCF/Revenue, Debt/EBITDA, crescimento (receita/EPS).

Macro (FRED): DGS2, DGS10, spread HY (BAMLH0A0HYM2) com lag de 1 dia para evitar look-ahead.

Setoriais: dummies GICS set/industry; participação regional.

Limpeza: winsorizar p5/p95, padronizar z-score por setor/região.

DoD: pytest simples para winsorize(), zscore() e merge sem NaN explosivo.

3. Target/rotulagem (rank/retorno futuro)

ml/datasets/targets.py

forward_return(df_prices, horizon_days=21) (aprox. 1 mês útil).

Opção ranking: quantil (Q5 melhor, Q1 pior) por data & região/setor.

DoD: gráfico sanity-check: distribuição de y; sem vazamentos (usa somente dados ≤ t).

4. Montagem do dataset

ml/datasets/build_equities.py

Agregar features + target por data-ticker.

Split temporal: train (2016-2022), valid (2023), test (2024-hoje).

Salvar parquet em ml/datasets/equities\_\*.parquet.

DoD: print(shape) e % de NaNs < 1%; tempos coerentes (sem look-ahead).

Milestone 2 — Treinadores multifatoriais 5. Baselines + GBM (gratuito)

ml/trainers/equities_ranker.py

Modelos: RandomForestRegressor, GradientBoostingRegressor (sklearn).

Objetivo: prever retorno 21d (regressão) e avaliar como ranking.

Hiperparâmetros via config/ml/equities_ranker.yaml.

Métricas: IC (Spearman corr), Top-decile spread (Q10-Q1), Precision@K, Sharpe simulado sem custos.

Persistir: joblib.dump(model, ml/models/equities_ranker.joblib) e metrics.json.

DoD: IC_valid > 0.03 ou Top10–Bottom10 > 5% anualizado em validação.

6. Explicar o modelo (interpretação)

ml/utils/importance.py

Importância de features (permutation importance).

Partial dependence para 5 principais fatores.

DoD: salvar png/html em ml/models/equities*ranker*_\_importance._.

Milestone 3 — Sub-agentes regionais e setoriais 7. Datasets segmentados

ml/datasets/build_equities_by_region.py (US, EU)

ml/datasets/build_equities_by_sector.py (Tech, Health, Energy, Financials…)

DoD: arquivos parquet por segmento; logs com contagens de tickers/datas.

8. Treinadores por segmento

ml/trainers/train_by_region.py

ml/trainers/train_by_sector.py

Mesmo pipeline; salva ml/models/equities_ranker_us.joblib, etc.

DoD: cada sub-modelo com métricas registradas; fallback para global se dados escassos.

9. Orquestração de blending

config/agents/weights.yaml

equities:
global: 0.4
region:
US: 0.3
EU: 0.3
sector:
TECH: 0.2
HEALTH: 0.2
ENERGY: 0.2
FINANCIALS: 0.2

agents/equities_ml/agent.py

Carrega features do dia (mesma função do dataset, modo online).

Score final = média ponderada dos sub-modelos disponíveis.

Gera out/signals_equities_ml.json (mesmo schema de sinais).

DoD: arquivo JSON gerado e integrado ao orchestrator.main (escolher ML vs heurística por flag).

Milestone 4 — Feedback loop (online learning) 10. Métricas contínuas por sinal

analytics/ledger.py

Registrar, para cada ordem/sinal: data, preço de entrada, PnL realizado (ou mark-to-market), holding period.

analytics/metrics.py

Sharpe/Sortino rolling (63/126 dias), max drawdown, hit rate por modelo/sub-agente.

DoD: out/analytics/metrics.json atualizado ao fim do pipeline.

11. Atualização de pesos (meta-aprendizado simples)

ml/online/update_agent_weights.py

Recalcular pesos de config/agents/weights.yaml com base no Sharpe rolling dos sub-agentes (exponencial, meia-vida 90 dias).

Restringir variação por step (ex: ±5 p.p.) para estabilidade.

DoD: weights.yaml ajustado; log de decisão arquivado em out/analytics/weights_log.jsonl.

12. Auto-retreino (programado)

ml/schedule/retrain.py

Retreinar mensalmente (ou quando IC 30D < 0). Salvar v2, v3… no ml/models/.

models/registry.json com active_model por segmento e data.

DoD: swap de modelo controlado por registry; rollback simples.

Milestone 5 — Integração com pipeline & relatórios 13. Orquestração

run_all.py:

Adicionar etapa opcional python -m agents.equities_ml.agent --use-ml true.

Flag em config/strategy.yaml: equities_signal_source: "ml"|"heuristic"|"blend".

DoD: pipeline roda ponta-a-ponta gerando plano com sinais ML.

14. Relatório (já tens Plotly)

interfaces/reporting/report_html.py:

Nova seção “Desempenho dos Sub-Agentes”: barras com Sharpe rolling (US/EU/Sectores).

Tabela dos Top Features por importância (texto + valor).

“Diferença vs Heurística”: barra com retorno mensal ML – heurística.

DoD: out/report.html inclui gráficos e melhora tomada de decisão.

Milestone 6 — Qualidade, testes e segurança 15. Testes mínimos (gratuitos)

tests/test_features.py (sem NaN pós-processamento, estabilidade de escalas)

tests/test_split.py (walk-forward sem leak)

tests/test_signals_schema.py (JSON schema dos sinais)

DoD: pytest -q verde no CI local.

16. Reprodutibilidade

ml/utils/seeds.py (fixar seeds)

requirements-ml.txt (scikit-learn, numpy, pandas, joblib, plotly)

DoD: treino reproduzível ±1% em métricas.

Milestone 7 — Roadmap de melhorias (opcionais, ainda grátis)

RankNet/LightGBM ranking (instalar lightgbm) para aprendizado direto de ranking.

Stacking: combinar regressão (retorno) + classificação (top-quintil?).

Regime switching: clusterizar regimes de mercado (KMeans sobre macro) e ter pesos condicionais.

Como isso “plug-a” no que já existe

Dados: continuas em yfinance/AlphaVantage/FRED → as funções já criadas nas providers são reutilizadas na features/.

Sinais: o novo agente agents/equities*ml/agent.py grava o mesmo formato de out/signals*\*.json, então o orchestrator.main e o paper broker não mudam.

Feedback: analytics/ lê execuções do interfaces/broker_adapter/paper.py e marca as posições diariamente; daí calcula métricas por sub-agente e ajusta config/agents/weights.yaml.

Checklist de “pronto para produção leve”

Dataset montado e versionado (parquet + script determinístico).

Modelo baseline GBM com IC>0.03 em validação.

Sub-modelos regionais/sectoriais treinados e registrados.

Agente ML gerando sinais consistentes e explicáveis (importância/PD plots).

Feedback loop rodando: Sharpe/drawdown por sub-agente + ajuste de pesos mensal.

Report com métricas dos sub-agentes e comparação vs heurística.

Testes automatizados mínimos passando.

Se quiser, no próximo passo eu já te mando os arquivos-esqueleto dos módulos (com funções e docstrings) para começar a preencher rapidamente.
#   i n v e s t - a g e n t s  
 #   i n v e s t - a g e n t s  
 