import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from contact_manager import phone_group_token, schedule_contacts


class ContactManagerTests(unittest.TestCase):
    def test_shared_phone_does_not_merge_people_and_spreads_daily_contacts(self):
        people = [
            {"beneficiary_ref": f"person-{index}", "shared_phone_group_token": "same-group"}
            for index in range(4)
        ]
        scheduled = schedule_contacts(people, dt.date(2026, 11, 19))

        self.assertEqual(
            [row["beneficiary_ref"] for row in scheduled],
            ["person-0", "person-1", "person-2", "person-3"],
        )
        self.assertEqual(
            [row["scheduled_date"] for row in scheduled],
            ["2026-11-19", "2026-11-20", "2026-11-21", "2026-11-22"],
        )

    def test_no_contact_is_respected(self):
        result = schedule_contacts(
            [
                {"beneficiary_ref": "person-1", "do_not_contact": "true"},
                {"beneficiary_ref": "person-2"},
            ],
            dt.date(2026, 11, 19),
        )
        self.assertEqual(result[0]["status"], "excluded_do_not_contact")
        self.assertEqual(result[1]["status"], "scheduled")

    def test_phone_tokens_are_keyed_and_do_not_return_the_number(self):
        first = phone_group_token("+57 310-123-4567", b"private-test-key")
        same = phone_group_token("573101234567", b"private-test-key")
        other_key = phone_group_token("573101234567", b"another-private-key")

        self.assertEqual(first, same)
        self.assertNotEqual(first, other_key)
        self.assertNotIn("573101234567", first)


if __name__ == "__main__":
    unittest.main()
