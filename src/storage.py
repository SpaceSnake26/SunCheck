import json
import os
from datetime import datetime

class Storage:
    def __init__(self, log_file="opportunities.jsonl"):
        self.log_file = log_file

    def log_opportunity(self, opportunity):
        """
        Logs a trade recommendation to a JSONL file.
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            **opportunity
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def log_backtest(self, results):
        """
        Saves backtest results to a report file.
        """
        with open("backtest_report.json", "w") as f:
            json.dump(results, f, indent=4)
