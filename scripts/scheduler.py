#!/usr/bin/env python3
"""
KOLMO JSON Data Scheduler
==========================

Unified orchestrator that updates all three JSON export files:
  1. kolmo_history.json       — KOLMO rates & metrics (Frankfurter API)
  2. cbr_of_rub.json          — CBR RUB exchange rates (cbr.ru)
  3. conversion_coefficients.json — computed conversion coefficients

Modes:
  --once          Run the update pipeline once and exit (default).
  --daemon        Run once at startup, then repeat on a daily timer.
  --interval M    Timer interval in minutes (default: use cron-style 22:00 EST).
  --cron HH:MM    Cron-style daily time in scheduler_timezone (default: 22:00).
  --timezone TZ   Timezone for cron schedule (default: US/Eastern).

Examples:
  python scripts/scheduler.py                     # one-shot update & exit
  python scripts/scheduler.py --once              # same as above
  python scripts/scheduler.py --daemon            # run now + daily at 22:00 EST
  python scripts/scheduler.py --daemon --cron 08:00 --timezone Europe/Moscow
  python scripts/scheduler.py --daemon --interval 360   # every 6 hours
"""

from __future__ import annotations

import argparse
import importlib
import logging
import signal
import sys
import threading
import time
from datetime import datetime, date
from pathlib import Path

# Ensure scripts/ is importable and project root is on sys.path
SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_log_fmt = logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s",
                             datefmt="%Y-%m-%d %H:%M:%S")

# Force UTF-8 on stdout for proper emoji/unicode rendering on Windows
if sys.platform == "win32":
    import io
    _stdout_wrapper = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
else:
    _stdout_wrapper = sys.stdout

_console_handler = logging.StreamHandler(_stdout_wrapper)
_console_handler.setFormatter(_log_fmt)

# Ensure logs directory exists early
(ROOT_DIR / "logs").mkdir(exist_ok=True)

_file_handler = logging.FileHandler(
    ROOT_DIR / "logs" / "scheduler.log", encoding="utf-8"
)
_file_handler.setFormatter(_log_fmt)

logging.basicConfig(
    level=logging.INFO,
    handlers=[_console_handler, _file_handler],
)
logger = logging.getLogger("kolmo.scheduler")

# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def _isolated_call(func, *args, **kwargs):
    """Call *func* with sys.argv temporarily replaced to avoid argparse leaks."""
    saved_argv = sys.argv
    sys.argv = [sys.argv[0]]  # only script name — no extra flags
    try:
        return func(*args, **kwargs)
    finally:
        sys.argv = saved_argv


def step_update_kolmo_history() -> bool:
    """Step 1: Update kolmo_history.json via Frankfurter API."""
    logger.info("=" * 60)
    logger.info("STEP 1/3  ▸  kolmo_history.json")
    logger.info("=" * 60)
    try:
        mod = importlib.import_module("update_kolmo_history")
        importlib.reload(mod)
        _isolated_call(mod.main)
        logger.info("✅  kolmo_history.json — updated successfully")
        return True
    except SystemExit as exc:
        if exc.code and exc.code != 0:
            logger.error("❌  kolmo_history.json — exited with code %s", exc.code)
            return False
        logger.info("✅  kolmo_history.json — updated (sys.exit caught)")
        return True
    except Exception:
        logger.exception("❌  kolmo_history.json — update FAILED")
        return False


def step_update_cbr_rub() -> bool:
    """Step 2: Update cbr_of_rub.json from CBR."""
    logger.info("=" * 60)
    logger.info("STEP 2/3  ▸  cbr_of_rub.json")
    logger.info("=" * 60)
    try:
        mod = importlib.import_module("export_cbr_rub")
        importlib.reload(mod)
        _isolated_call(mod.update_to_today)
        logger.info("✅  cbr_of_rub.json — updated successfully")
        return True
    except SystemExit as exc:
        if exc.code and exc.code != 0:
            logger.error("❌  cbr_of_rub.json — exited with code %s", exc.code)
            return False
        logger.info("✅  cbr_of_rub.json — updated (sys.exit caught)")
        return True
    except Exception:
        logger.exception("❌  cbr_of_rub.json — update FAILED")
        return False


def step_update_conversion_coefficients() -> bool:
    """Step 3: Recalculate conversion_coefficients.json."""
    logger.info("=" * 60)
    logger.info("STEP 3/3  ▸  conversion_coefficients.json")
    logger.info("=" * 60)
    try:
        mod = importlib.import_module("kalculator")
        importlib.reload(mod)
        # main(argv=[]) → argparse sees no CLI flags → full recalculation
        mod.main(argv=[])
        logger.info("✅  conversion_coefficients.json — updated successfully")
        return True
    except SystemExit as exc:
        if exc.code and exc.code != 0:
            logger.error("❌  conversion_coefficients.json — exited with code %s", exc.code)
            return False
        logger.info("✅  conversion_coefficients.json — updated (sys.exit caught)")
        return True
    except Exception:
        logger.exception("❌  conversion_coefficients.json — update FAILED")
        return False


def run_pipeline() -> dict[str, bool]:
    """Execute the full 3-step JSON update pipeline."""
    start = time.monotonic()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    logger.info("🚀  KOLMO JSON update pipeline started at %s", ts)
    logger.info("")

    results = {}
    results["kolmo_history"] = step_update_kolmo_history()
    results["cbr_of_rub"] = step_update_cbr_rub()
    results["conversion_coefficients"] = step_update_conversion_coefficients()

    elapsed = time.monotonic() - start
    ok = sum(results.values())
    total = len(results)

    logger.info("")
    logger.info("=" * 60)
    logger.info("PIPELINE SUMMARY  (%d/%d succeeded, %.1fs)", ok, total, elapsed)
    for name, success in results.items():
        icon = "✅" if success else "❌"
        logger.info("  %s  %s", icon, name)
    logger.info("=" * 60)

    return results


# ---------------------------------------------------------------------------
# Daemon scheduler (timer-based or cron-style)
# ---------------------------------------------------------------------------

class DaemonScheduler:
    """
    Simple daemon that runs ``run_pipeline()`` periodically.

    Supports two modes:
    - interval: repeat every N minutes
    - cron: once per day at HH:MM in the given timezone
    """

    def __init__(
        self,
        interval_minutes: int | None = None,
        cron_time: str = "22:00",
        timezone_name: str = "US/Eastern",
    ):
        self._stop = threading.Event()
        self._interval_minutes = interval_minutes
        self._cron_time = cron_time
        self._timezone_name = timezone_name

    # ----- public API -----

    def start(self):
        """Run pipeline immediately, then enter the scheduling loop."""
        # Immediate run on startup
        logger.info("🔄  Running initial update on startup …")
        run_pipeline()

        if self._interval_minutes:
            self._loop_interval()
        else:
            self._loop_cron()

    def stop(self):
        logger.info("🛑  Scheduler stop requested")
        self._stop.set()

    # ----- interval mode -----

    def _loop_interval(self):
        secs = self._interval_minutes * 60
        logger.info("⏲️  Interval mode: every %d min (%d s)", self._interval_minutes, secs)
        while not self._stop.wait(secs):
            logger.info("⏰  Timer fired — running pipeline …")
            run_pipeline()

    # ----- cron mode -----

    def _seconds_until_next_run(self) -> float:
        """Seconds until the next HH:MM in the configured timezone."""
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(self._timezone_name)
        except ImportError:
            # Python < 3.9 fallback — just use local time
            tz = None

        now = datetime.now(tz)
        hh, mm = (int(x) for x in self._cron_time.split(":"))
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if target <= now:
            # Already passed today — schedule for tomorrow
            from datetime import timedelta
            target += timedelta(days=1)
        delta = (target - now).total_seconds()
        return delta

    def _loop_cron(self):
        logger.info(
            "🕐  Cron mode: daily at %s %s",
            self._cron_time,
            self._timezone_name,
        )
        while not self._stop.is_set():
            wait = self._seconds_until_next_run()
            hh_mm = self._cron_time
            logger.info("💤  Next run at %s %s (in %.0f s / %.1f h)",
                        hh_mm, self._timezone_name, wait, wait / 3600)
            if self._stop.wait(wait):
                break  # stop requested
            logger.info("⏰  Cron fired — running pipeline …")
            run_pipeline()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="KOLMO JSON Data Scheduler — updates kolmo_history, cbr_of_rub, conversion_coefficients",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples:")[1] if "Examples:" in __doc__ else "",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--once",
        action="store_true",
        default=True,
        help="Run the pipeline once and exit (default).",
    )
    mode.add_argument(
        "--daemon",
        action="store_true",
        help="Run at startup, then keep running on a schedule.",
    )
    p.add_argument(
        "--interval",
        type=int,
        default=None,
        metavar="MINUTES",
        help="In daemon mode: repeat every N minutes (overrides --cron).",
    )
    p.add_argument(
        "--cron",
        type=str,
        default="22:00",
        metavar="HH:MM",
        help="In daemon mode: daily run time (default: 22:00).",
    )
    p.add_argument(
        "--timezone",
        type=str,
        default="US/Eastern",
        metavar="TZ",
        help="Timezone for --cron (default: US/Eastern).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.daemon:
        # --- One-shot mode ---
        results = run_pipeline()
        return 0 if all(results.values()) else 1

    # --- Daemon mode ---
    sched = DaemonScheduler(
        interval_minutes=args.interval,
        cron_time=args.cron,
        timezone_name=args.timezone,
    )

    # Graceful shutdown on Ctrl+C / SIGTERM
    def _handle_signal(signum, _frame):
        logger.info("Received signal %s", signal.Signals(signum).name)
        sched.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        sched.start()
    except KeyboardInterrupt:
        sched.stop()

    logger.info("👋  Scheduler exiting")
    return 0


if __name__ == "__main__":
    sys.exit(main())
