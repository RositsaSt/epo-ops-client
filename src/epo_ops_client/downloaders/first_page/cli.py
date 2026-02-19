from __future__ import annotations

import os
from dotenv import load_dotenv

from .auth import OPSAuthClient
from .config import DownloaderConfig
from .downloader import download_many
from .io_tasks import tasks_from_csv
from .logging_csv import CsvRunLog
from .rate_limiter import RateLimiter


def main() -> None:
    load_dotenv()

    ops_key = os.getenv("EPO_OPS_KEY")
    ops_secret = os.getenv("EPO_OPS_SECRET")
    if not ops_key or not ops_secret:
        raise SystemExit("Missing EPO_OPS_KEY / EPO_OPS_SECRET in environment (.env).")

    config = DownloaderConfig()
    auth = OPSAuthClient(config.base_url, ops_key, ops_secret, timeout_s=config.token_timeout_s)
    limiter = RateLimiter(config.rate_per_sec)
    run_log = CsvRunLog(config.log_path)

    tasks = tasks_from_csv("pub_number_kind.csv", default_country=config.country_default)
    download_many(tasks, config=config, auth=auth, limiter=limiter, run_log=run_log)

    print(f"Done. Log: {config.log_path} | Files: {config.out_dir}/")


if __name__ == "__main__":
    main()
