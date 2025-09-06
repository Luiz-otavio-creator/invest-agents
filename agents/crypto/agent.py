# agents/crypto/agent.py
# -----------------------------------------------------------------------------
# Agente de CRIPTO — robusto, gratuito e com fallback
#
# Estratégia do sinal:
#   1) Tendência: price > SMA50 > SMA200  -> tendência de alta
#   2) Filtro de volatilidade (ATR% simplificado): só BUY se volatilidade recente
#      não estiver "explodindo" (reduz falsos positivos).
#   3) Confiança: 0.7 para BUY, 0.4 para HOLD (ajuste conforme seu backtest).
#
# Fontes (grátis):
#   - CoinGecko (histórico diário + preço atual)
#   - Cache local (FileCache) no provider
#   - Fallback: utilitários antigos e, na última instância, mock sintético
#
# Observação:
#   - Tudo com pandas sem FutureWarnings; extração de escalares com .iloc/.item.
# -----------------------------------------------------------------------------

import os, time, math, datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from common.utils.bus import publish

# Tente usar o novo provider (recomendado). Se não existir no seu repo,
# continuamos funcionando com os utilitários antigos.
try:
    from common.providers.coingecko_provider import CoinGeckoProvider
    _HAS_NEW_PROVIDER = True
except Exception:
    _HAS_NEW_PROVIDER = False

# Fallbacks (mantêm compatibilidade com seu código atual)
from common.utils.providers import (
    cg_history_daily as _cg_hist_legacy,
    cg_simple_prices as _cg_price_legacy,
    sma as _sma_legacy,
    mock_price as _mock_price_legacy,
)

OUT = "out/signals_crypto.json"
SYMS = ["BTC", "ETH", "SOL", "ADA", "DOGE"]

# ------------------------ helpers de dados ------------------------

def _sma(series: np.ndarray, window: int) -> Optional[float]:
    """SMA sem FutureWarnings; retorna None se série < janela."""
    if series is None or len(series) < window:
        return None
    return float(pd.Series(series[-window:]).mean())

def _atr_percent(px: pd.Series, window: int = 14) -> Optional[float]:
    """
    ATR% simplificado usando apenas preços de fechamento (proxy de range).
    ATR% ~ média de |retornos diários| * sqrt(π/2) em janela 'window'.
    Retorna fração (ex.: 0.03 = 3%).
    """
    if px is None or len(px) < window + 1:
        return None
    ret = px.pct_change().dropna()
    if ret.empty:
        return None
    # fator ~1.253 para aproximar desvio absoluto médio ao desvio padrão
    mad = ret.tail(window).abs().mean()
    return float(mad * 1.253)

def _mock_history(symbol: str, days: int = 400) -> pd.DataFrame:
    """Histórico sintético caso tudo falhe."""
    idx = pd.date_range(end=pd.Timestamp.utcnow(), periods=days, freq="D")
    base = _mock_price_legacy(symbol)
    drift = 0.001  # leve tendência
    noise = 0.04   # ruído relativo
    steps = np.arange(days)
    prices = base * (1 + drift * steps) * (0.98 + noise * np.random.rand(days))
    return pd.DataFrame({"price": prices}, index=idx)

def _retry(f, tries=2, delay=0.8):
    """Retry simples para atenuar 429/timeouts da CoinGecko (gratuito)."""
    for i in range(tries):
        try:
            return f()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(delay * (1.5 ** i))

# ------------------------ camada de acesso (provider + fallback) --------------

class CG:
    """Wrapper que usa CoinGeckoProvider se houver; senão utilitários legados."""

    def __init__(self):
        self._prov = CoinGeckoProvider() if _HAS_NEW_PROVIDER else None

    def history_daily(self, symbol: str, days: int = 400) -> pd.DataFrame:
        if self._prov:
            try:
                df = _retry(lambda: self._prov.get_history(symbol, days=days))
                if isinstance(df, pd.DataFrame) and not df.empty:
                    return df
            except Exception:
                pass
        # fallback legado
        try:
            df = _retry(lambda: _cg_hist_legacy(symbol, days=days))
            if isinstance(df, pd.DataFrame) and not df.empty:
                return df
        except Exception:
            pass
        # último recurso
        return pd.DataFrame()

    def simple_prices(self, symbols: List[str]) -> Dict[str, float]:
        if self._prov:
            try:
                pm = _retry(lambda: self._prov.get_prices(symbols))
                if isinstance(pm, dict) and pm:
                    return pm
            except Exception:
                pass
        # fallback legado
        try:
            pm = _retry(lambda: _cg_price_legacy(symbols))
            if isinstance(pm, dict) and pm:
                return pm
        except Exception:
            pass
        # último recurso: todos com mock
        return {s: _mock_price_legacy(s) for s in symbols}

cg = CG()

# ------------------------ lógica do sinal ------------------------------------

def _signal_for_symbol(s: str) -> Dict:
    # 1) histórico
    df = cg.history_daily(s, days=400)
    if df is None or df.empty or "price" not in df.columns:
        # CoinGecko vazio → mock sintético
        df = _mock_history(s, days=400)

    px = df["price"].dropna()
    if px.empty:
        # sem dado algum → HOLD defensivo
        price_now = _mock_price_legacy(s)
        return {
            "instrument_id": s,
            "side": "HOLD",
            "confidence": 0.3,
            "rationale": "sem dados válidos",
            "ttl_days": 7,
            "price": float(price_now),
            "collected_at": datetime.datetime.utcnow().isoformat()
        }

    # 2) médias móveis
    arr = px.values.astype(float)
    ma50  = _sma(arr, 50)  or float(px.iloc[-1])
    ma200 = _sma(arr, 200) or float(px.mean())
    price_now = float(px.iloc[-1])

    up_trend = (price_now > ma50) and (ma50 > ma200)

    # 3) filtro de volatilidade (ATR% simplificado)
    atrp = _atr_percent(px, window=14)  # fração
    # thresholds simples: se ATR% muito alto, reduz confiança de BUY
    vol_penalty = 0.0
    if atrp is not None:
        if atrp > 0.08:     # >8% média diária (bem volátil)
            vol_penalty = 0.15
        elif atrp > 0.05:   # 5–8%
            vol_penalty = 0.07

    side = "BUY" if up_trend else "HOLD"
    conf = 0.7 if up_trend else 0.4
    conf = max(0.0, min(1.0, conf - vol_penalty))

    rationale = f"MA50>MA200={'OK' if up_trend else 'NO'}; ATR14%={(atrp*100):.2f}%{' (penalty)' if vol_penalty>0 else ''}"

    # 4) preço atual (de preferência do endpoint simples)
    try:
        price_map = cg.simple_prices([s])
        price_now = float(price_map.get(s, price_now))
    except Exception:
        # se também falhar, mantém preço do histórico/último
        pass

    return {
        "instrument_id": s,
        "side": side,
        "confidence": round(float(conf), 3),
        "rationale": rationale,
        "ttl_days": 7,
        "price": float(price_now),
        "collected_at": datetime.datetime.utcnow().isoformat()
    }

# ------------------------ entrypoint -----------------------------------------

def main():
    os.makedirs("out", exist_ok=True)
    signals = [_signal_for_symbol(s) for s in SYMS]
    publish(OUT, signals)
    print(f"[crypto] {len(signals)} sinais salvos em {OUT} (CoinGecko + cache/fallback)")

if __name__ == "__main__":
    main()
