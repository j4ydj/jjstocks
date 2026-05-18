#!/usr/bin/env python3
"""Backward-compatible wrappers — use trade_tracker.py for new code."""
from __future__ import annotations

from typing import Dict, List, Optional

from chain_setups import TradeSetup
from momentum_chain import MomentumScanResult
from trade_tracker import SETUP_FILE, fill_outcomes, log_proposed_trades, update_outcomes, write_report


def log_setups(
    result: MomentumScanResult,
    setups: List[TradeSetup],
    telegram_sent: bool = False,
) -> str:
    from chain_ping import ALERT_MODE
    log_proposed_trades(result, setups, telegram_sent=telegram_sent, alert_mode=ALERT_MODE)
    return SETUP_FILE


if __name__ == "__main__":
    from trade_tracker import main
    main()
