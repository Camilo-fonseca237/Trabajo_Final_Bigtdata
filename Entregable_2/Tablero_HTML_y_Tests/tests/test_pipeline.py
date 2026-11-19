import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import _batch


class BatchTests(unittest.TestCase):
    def test_batch_selects_previous_day_and_excludes_opted_out_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "transactions.csv"
            output = root / "batch.html"
            fields = [
                "transaction_date",
                "beneficiary_ref",
                "resource",
                "amount",
                "telemarketer_alias",
                "shared_phone_group_token",
                "authorized_channel",
                "preferred_time_window",
                "do_not_contact",
            ]
            rows = [
                ["2026-11-18", "private-person", "Bono", "12000", "Agent-A", "", "SMS", "AM", "false"],
                ["2026-11-18", "opted-out-person", "Bono", "9000", "Agent-A", "", "SMS", "AM", "true"],
                ["2026-11-17", "older-person", "Rifa", "7000", "Agent-B", "", "Call", "PM", "false"],
            ]
            with source.open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(fields)
                writer.writerows(rows)

            result = _batch(source, output, "2026-11-19")
            report = output.read_text(encoding="utf-8")

            self.assertEqual(result["records_examined"], 3)
            self.assertEqual(result["logistic_groups"], 1)
            self.assertIn("12,000", report)
            self.assertNotIn("private-person", report)
            self.assertNotIn("opted-out-person", report)


if __name__ == "__main__":
    unittest.main()
