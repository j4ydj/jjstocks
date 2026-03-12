#!/usr/bin/env python3
"""
AUTORESEARCH TRADING - EXPERIMENT RUNNER
========================================
Autonomous experiment loop.
Usage:
  python run_experiment.py --baseline    # Run baseline
  python run_experiment.py --iterate     # Modify and test strategy
  python run_experiment.py --reset       # Reset to baseline
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

EXPERIMENT_LOG = "experiments.log"
BASELINE_CONFIG = {
    "TIMEFRAME": "1h",
    "INDICATOR_1": "EMA_CROSS",
    "INDICATOR_2": "NONE",
    "EMA_FAST": 9,
    "EMA_SLOW": 21,
    "RSI_PERIOD": 14,
    "RSI_OVERBOUGHT": 70,
    "RSI_OVERSOLD": 30,
    "STOP_LOSS_PCT": 2.0,
    "TAKE_PROFIT_PCT": 4.0,
    "POSITION_SIZE": 100,
}

def log_experiment(number: int, changes: str, hypothesis: str, metrics: Dict, verdict: str):
    """Log experiment results."""
    entry = {
        "experiment": number,
        "timestamp": datetime.now().isoformat(),
        "changes": changes,
        "hypothesis": hypothesis,
        "metrics": metrics,
        "verdict": verdict,
    }
    
    with open(EXPERIMENT_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    
    logger.info(f"\nLogged Experiment #{number}")
    logger.info(f"  Changes: {changes}")
    logger.info(f"  Hypothesis: {hypothesis}")
    logger.info(f"  Win rate: {metrics.get('win_rate', 0)}%")
    logger.info(f"  Profit factor: {metrics.get('profit_factor', 0)}")
    logger.info(f"  Verdict: {verdict}")

def get_next_experiment_number() -> int:
    """Get next experiment number from log."""
    if not os.path.exists(EXPERIMENT_LOG):
        return 1
    
    count = 0
    with open(EXPERIMENT_LOG) as f:
        for line in f:
            if line.strip():
                count += 1
    return count + 1

def run_baseline():
    """Run baseline strategy and log results."""
    logger.info("=" * 70)
    logger.info("  RUNNING BASELINE STRATEGY")
    logger.info("=" * 70)
    
    # Reset to baseline
    from strategy import STRATEGY_CONFIG
    for key, val in BASELINE_CONFIG.items():
        STRATEGY_CONFIG[key] = val
    
    # Run backtest
    from backtest import run_backtest, score_strategy
    metrics, trades = run_backtest(STRATEGY_CONFIG, verbose=True)
    score = score_strategy(metrics)
    
    # Log
    exp_num = get_next_experiment_number()
    verdict = "BASELINE"
    log_experiment(
        exp_num,
        "Baseline EMA 9/21 crossover on 1h timeframe",
        "Simple trend following baseline",
        metrics,
        verdict
    )
    
    return score

def suggest_improvements(metrics: Dict) -> List[Dict]:
    """Suggest strategy improvements based on metrics."""
    suggestions = []
    
    if metrics["win_rate"] < 50:
        suggestions.append({
            "change": "Add RSI filter (don't buy when RSI > 70)",
            "hypothesis": "Avoid entering overbought conditions",
            "config_changes": {"INDICATOR_2": "RSI"}
        })
        suggestions.append({
            "change": "Increase stop loss to 3%",
            "hypothesis": "2% is too tight, causing whipsaws",
            "config_changes": {"STOP_LOSS_PCT": 3.0}
        })
    
    if metrics["profit_factor"] < 1.3:
        suggestions.append({
            "change": "Switch to RSI mean reversion",
            "hypothesis": "Trend following not working, try mean reversion",
            "config_changes": {
                "INDICATOR_1": "RSI",
                "RSI_OVERSOLD": 30,
                "RSI_OVERBOUGHT": 70
            }
        })
        suggestions.append({
            "change": "Add volume filter",
            "hypothesis": "Only trade when volume confirms move",
            "config_changes": {"INDICATOR_2": "VOLUME"}
        })
    
    if metrics["max_drawdown"] > 20:
        suggestions.append({
            "change": "Tighten stop loss to 1.5%",
            "hypothesis": "Current stop is too loose",
            "config_changes": {"STOP_LOSS_PCT": 1.5}
        })
    
    if metrics["total_trades"] < 20:
        suggestions.append({
            "change": "Use 15m timeframe",
            "hypothesis": "More signals on shorter timeframe",
            "config_changes": {"TIMEFRAME": "15m"}
        })
    
    return suggestions

def run_iterate():
    """Run iterative improvement cycle."""
    logger.info("=" * 70)
    logger.info("  RUNNING ITERATIVE IMPROVEMENT")
    logger.info("=" * 70)
    
    # Load last experiment
    if not os.path.exists(EXPERIMENT_LOG):
        logger.info("No experiment log found. Run baseline first.")
        return run_baseline()
    
    # Get last metrics
    last_metrics = None
    with open(EXPERIMENT_LOG) as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                last_metrics = entry.get("metrics", {})
    
    if not last_metrics:
        logger.info("No previous metrics found.")
        return run_baseline()
    
    # Get suggestions
    suggestions = suggest_improvements(last_metrics)
    
    if not suggestions:
        logger.info("No automatic suggestions. Strategy is working or needs manual tuning.")
        logger.info("Try modifying strategy.py manually and running again.")
        return 0
    
    # Apply first suggestion
    suggestion = suggestions[0]
    logger.info(f"\nApplying suggestion: {suggestion['change']}")
    logger.info(f"Hypothesis: {suggestion['hypothesis']}")
    
    # Apply changes to strategy
    from strategy import STRATEGY_CONFIG
    for key, val in suggestion["config_changes"].items():
        STRATEGY_CONFIG[key] = val
    
    # Run backtest
    from backtest import run_backtest, score_strategy
    metrics, trades = run_backtest(STRATEGY_CONFIG, verbose=True)
    score = score_strategy(metrics)
    
    # Determine verdict
    prev_score = 0
    if last_metrics:
        from backtest import score_strategy as ss
        prev_score = ss(last_metrics)
    
    if score > prev_score:
        verdict = "KEEP"
    elif score >= 50:
        verdict = "ITERATE"
    else:
        verdict = "REVERT"
    
    # Log
    exp_num = get_next_experiment_number()
    log_experiment(exp_num, suggestion["change"], suggestion["hypothesis"], metrics, verdict)
    
    return score

def show_experiment_history():
    """Show experiment history."""
    if not os.path.exists(EXPERIMENT_LOG):
        logger.info("No experiment history found.")
        return
    
    logger.info("\n" + "=" * 70)
    logger.info("  EXPERIMENT HISTORY")
    logger.info("=" * 70)
    
    with open(EXPERIMENT_LOG) as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                m = entry.get("metrics", {})
                logger.info(f"\nExp #{entry['experiment']} - {entry['verdict']}")
                logger.info(f"  Change: {entry['changes'][:60]}...")
                logger.info(f"  Win: {m.get('win_rate', 0)}% | PF: {m.get('profit_factor', 0)} | Sharpe: {m.get('sharpe', 0)}")

def main():
    parser = argparse.ArgumentParser(description="Autoresearch trading experiments")
    parser.add_argument("--baseline", action="store_true", help="Run baseline strategy")
    parser.add_argument("--iterate", action="store_true", help="Run iterative improvement")
    parser.add_argument("--history", action="store_true", help="Show experiment history")
    parser.add_argument("--reset", action="store_true", help="Reset experiments")
    
    args = parser.parse_args()
    
    if args.reset:
        if os.path.exists(EXPERIMENT_LOG):
            os.remove(EXPERIMENT_LOG)
        logger.info("Reset experiments.")
        return 0
    
    if args.history:
        show_experiment_history()
        return 0
    
    if args.iterate:
        score = run_iterate()
    else:
        score = run_baseline()
    
    return 0 if score >= 50 else 1

if __name__ == "__main__":
    sys.exit(main())
