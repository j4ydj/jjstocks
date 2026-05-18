#!/usr/bin/env python3
"""
Momentum chain scanner + trade plays (primary entry point).

Usage:
  python run_momentum_chain.py
  python run_momentum_chain.py --chains-only
  python run_momentum_chain.py --telegram
  python run_momentum_chain.py --json
  python system_report.py              # decision report with backtest + live data
"""
import argparse
import json
import logging
import sys
from dataclasses import asdict

from momentum_chain import format_report
from momentum_plays import format_plays, scan_and_save

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Momentum chain finder")
    parser.add_argument("--top", type=int, default=10, help="Number of volatile names to focus on")
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout")
    parser.add_argument("--chains-only", action="store_true", help="Chain map only, no trade plays")
    parser.add_argument("--telegram", action="store_true", help="Send summary to Telegram")
    parser.add_argument("--min-conviction", type=int, default=3, help="Min play conviction (1-5)")
    parser.add_argument("--max-plays", type=int, default=8, help="Max plays after scoring")
    parser.add_argument("--backtest", action="store_true", help="Run play rule backtest and exit")
    parser.add_argument("--outcomes", action="store_true", help="Update outcomes and print report")
    parser.add_argument("--save", action="store_true", default=True, help="Save JSON snapshot (default on)")
    parser.add_argument("--no-save", action="store_true", help="Skip saving JSON file")
    args = parser.parse_args()

    if args.backtest:
        from backtest_plays import main as bt_main
        import sys as _sys
        _sys.argv = ["backtest_plays.py"]
        return bt_main() or 0

    if args.outcomes:
        import outcome_tracker
        outcome_tracker.process_history()
        print(outcome_tracker.report_outcomes())
        return 0

    if args.chains_only:
        from momentum_chain import MomentumChainFinder, save_result
        finder = MomentumChainFinder(top_n=args.top)
        result = finder.scan()
        plays = []
        path = save_result(result) if args.save and not args.no_save else None
    else:
        from momentum_plays import scan_with_plays
        from momentum_chain import save_result
        from momentum_plays import collect_chain_alerts
        result, plays = scan_with_plays(
            top_n=args.top,
            min_conviction=args.min_conviction,
            max_plays=args.max_plays,
        )
        path = None
        if args.save and not args.no_save:
            path = save_result(result, plays=plays)

    if args.json:
        def _enc(obj):
            if hasattr(obj, "__dataclass_fields__"):
                return {k: _enc(v) for k, v in asdict(obj).items()}
            if isinstance(obj, list):
                return [_enc(x) for x in obj]
            return obj
        print(json.dumps(_enc(result), indent=2))
    else:
        print(format_report(result))
        if plays:
            print(format_plays(plays))
        alerts = collect_chain_alerts(result)
        if alerts:
            print("\n  CHAIN ALERTS")
            for a in alerts:
                print(f"    ⚠ {a}")

    if path:
        logger.info("Saved %s", path)

    if args.telegram:
        try:
            from telegram_alerts import TelegramBot
            bot = TelegramBot()
            if bot.enabled:
                bot.send_momentum_scan(result)
                if plays:
                    for pl in plays[: args.max_plays]:
                        bot.send_trade_play(pl)
                for a in collect_chain_alerts(result)[:3]:
                    bot.send_message(f"⚠️ {a}")
                logger.info("Telegram report sent")
            else:
                logger.warning("Telegram not configured")
        except Exception as e:
            logger.error("Telegram failed: %s", e)
            sys.exit(1)

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
