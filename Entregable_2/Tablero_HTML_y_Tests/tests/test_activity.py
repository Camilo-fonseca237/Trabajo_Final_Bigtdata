import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import _activity_summary, _date_value, _frequency_category


class ActivityAnalyticsTests(unittest.TestCase):
    def test_excel_serial_and_text_dates_are_parsed(self):
        self.assertEqual(_date_value("46142"), dt.date(2026, 4, 30))
        self.assertEqual(_date_value("18/11/2026"), dt.date(2026, 11, 18))
        self.assertIsNone(_date_value("fecha pendiente"))

    def test_frequency_metrics_are_aggregated_without_exporting_people(self):
        years = {year: None for year in range(2008, 2027)}
        years[2024] = 100.0
        years[2025] = 200.0
        activity = _activity_summary(
            [
                {"ULT  PAGO": "46142", "Frecuencia": "2 MESES"},
                {"ULT  PAGO": "2026-11-19", "Frecuencia": "dato libre"},
                {"ULT  PAGO": "15", "Frecuencia": "2 MESES"},
            ],
            [years, years, years],
            dt.date(2026, 11, 18),
        )

        frequencies = {
            row["category"]: row["beneficiaries"]
            for row in activity["frequency_distribution"]
        }
        recency = {
            row["category"]: row["beneficiaries"]
            for row in activity["last_payment_date"]["recency_distribution"]
        }
        source_frequency = {
            row["category"]: row["records"]
            for row in activity["reported_frequency_values"]
        }
        self.assertEqual(frequencies["2–4 años"], 3)
        self.assertEqual(recency["181–365 días"], 1)
        self.assertEqual(activity["last_payment_date"]["dates_after_as_of"], 1)
        self.assertEqual(activity["last_payment_date"]["dates_before_2000"], 1)
        self.assertEqual(source_frequency["2 meses"], 2)
        self.assertEqual(source_frequency["No estandarizada"], 1)
        self.assertNotIn("beneficiaries", activity)

    def test_unrecognized_frequency_text_is_not_exported(self):
        self.assertEqual(_frequency_category("texto con información libre"), "No estandarizada")
        self.assertEqual(_frequency_category("SEMESTRAL"), "Semestral")


if __name__ == "__main__":
    unittest.main()
