# common/config/settings.py
from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    base_currency: str = os.getenv("BASE_CURRENCY", "EUR")

    alphavantage_key: str = os.getenv("ALPHAVANTAGE_API_KEY", "")
    fred_key: str = os.getenv("FRED_API_KEY", "")

    # Cache (aqui usamos só arquivo; se quiser Redis no futuro, é plug-and-play)
    ttl_price: int = int(os.getenv("TTL_PRICE_SECONDS", "900"))            # 15 min
    ttl_intraday: int = int(os.getenv("TTL_INTRADAY_SECONDS", "300"))      # 5 min (reserva)
    ttl_fundamentals: int = int(os.getenv("TTL_FUNDAMENTALS_SECONDS", "2592000"))  # 30 dias
    ttl_macro: int = int(os.getenv("TTL_MACRO_SECONDS", "86400"))          # 24h

SETTINGS = Settings()
