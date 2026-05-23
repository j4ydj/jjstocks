"""Central thresholds for v2 high-selectivity pipeline (target ~90% win rate)."""
from __future__ import annotations

import os

# Selection target (walk-forward pair history must meet this)
TARGET_WIN_RATE = float(os.getenv("PIPELINE_TARGET_WIN_RATE", "90"))
MIN_PAIR_HISTORY = int(os.getenv("PIPELINE_MIN_PAIR_HISTORY", "8"))
PLAYBOOK_FILE = os.getenv(
    "PIPELINE_PLAYBOOK_FILE",
    os.path.join(os.path.dirname(__file__), "data", "pair_playbook.json"),
)

# Correlation / lag
CORR_WINDOW = int(os.getenv("PIPELINE_CORR_WINDOW", "60"))
MIN_CORR = float(os.getenv("PIPELINE_MIN_CORR", "0.58"))
DISCOVERY_MIN_CORR = float(os.getenv("PIPELINE_DISCOVERY_MIN_CORR", "0.55"))
DISCOVERY_MAX_LINKS = int(os.getenv("PIPELINE_DISCOVERY_MAX", "40"))
MIN_HIT = float(os.getenv("PIPELINE_MIN_HIT", "58"))
DISCOVERY_MIN_HIT = float(os.getenv("PIPELINE_DISCOVERY_MIN_HIT", "0"))  # 0 = no hit filter
MIN_LAG_DAYS = int(os.getenv("PIPELINE_MIN_LAG_DAYS", "1"))
LEADER_MOVE_MIN = float(os.getenv("PIPELINE_LEADER_MOVE", "2.0"))
GAP_MIN = float(os.getenv("PIPELINE_GAP_MIN", "1.0"))
RESIDUAL_Z_MIN = float(os.getenv("PIPELINE_RESIDUAL_Z_MIN", "0.75"))

# Risk / hold
HOLD_DAYS = int(os.getenv("PIPELINE_HOLD_DAYS", "5"))
TIME_STOP_DAYS = int(os.getenv("PIPELINE_TIME_STOP_DAYS", "2"))
COST_BPS_PER_SIDE = float(os.getenv("PIPELINE_COST_BPS", "10"))
PARTIAL_TARGET_R = float(os.getenv("PIPELINE_PARTIAL_R", "1.0"))
SPREAD_STOP_Z = float(os.getenv("PIPELINE_SPREAD_STOP_Z", "2.5"))

# Portfolio
MAX_TRADES_PER_SCAN = int(os.getenv("PIPELINE_MAX_TRADES", "3"))
MAX_PER_THEME = int(os.getenv("PIPELINE_MAX_PER_THEME", "1"))

# Regime (prior-day % moves)
REGIME_SPY_SHORT_MAX = float(os.getenv("REGIME_SPY_SHORT_MAX", "0.35"))
REGIME_SPY_LONG_MIN = float(os.getenv("REGIME_SPY_LONG_MIN", "-0.75"))
VIX_PANIC_1D = float(os.getenv("REGIME_VIX_PANIC", "8.0"))

# Walk-forward backtest
WF_TRAIN_FRAC = float(os.getenv("WF_TRAIN_FRAC", "0.65"))

# Backtests showed momentum catch-up loses; fade (contrarian) wins ~3:1 on v2 candidates.
FADE_MODE = os.getenv("PIPELINE_FADE_MODE", "1") == "1"
DISABLE_BUY = os.getenv("PIPELINE_DISABLE_BUY", "0") == "1"

# Approved-trade layer (Telegram): US liquid only, min unconventional edge score
MIN_ALT_SCORE = float(os.getenv("PIPELINE_MIN_ALT_SCORE", "42"))
FALLBACK_ALT_SCORE = float(os.getenv("PIPELINE_FALLBACK_ALT_SCORE", "32"))
TARGET_MIN_TRADES_PER_SCAN = int(os.getenv("PIPELINE_TARGET_MIN_TRADES", "1"))
PIPELINE_ACTIONABLE_US = os.getenv("PIPELINE_ACTIONABLE_US", "1") == "1"
MIN_CORR_ACTIONABLE = float(os.getenv("PIPELINE_MIN_CORR_ACTIONABLE", "0.60"))
MIN_CORR_FALLBACK = float(os.getenv("PIPELINE_MIN_CORR_FALLBACK", "0.65"))
