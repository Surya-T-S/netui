import sys
import asyncio
import logging
from pathlib import Path


def setup_logging():
    log_dir = Path.home() / ".netui"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "netui.log",
        level=logging.ERROR,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )


def run():
    setup_logging()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    from netui.app import NetUIApp
    app = NetUIApp()
    app.run()


if __name__ == "__main__":
    run()
