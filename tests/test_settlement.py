from __future__ import annotations

import unittest

from weather_polymarket.settlement import (
    EventInterval,
    build_standard_11_event_book,
    certify_book,
    classify_temperature,
    validate_partition,
)


class SettlementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events = build_standard_11_event_book(
            lower_cut_c=25,
            upper_cut_c=34,
        )

    def test_book_has_eleven_events(self) -> None:
        self.assertEqual(
            len(self.events),
            11,
        )

    def test_one_decimal_value_is_not_rounded(self) -> None:
        winner = classify_temperature(
            self.events,
            30.9,
        )

        self.assertEqual(
            winner.event_id,
            "30_to_31",
        )

    def test_integer_boundary_enters_next_interval(self) -> None:
        winner = classify_temperature(
            self.events,
            31.0,
        )

        self.assertEqual(
            winner.event_id,
            "31_to_32",
        )

    def test_lower_tail(self) -> None:
        winner = classify_temperature(
            self.events,
            24.9,
        )

        self.assertEqual(
            winner.event_id,
            "below_25",
        )

    def test_upper_tail(self) -> None:
        winner = classify_temperature(
            self.events,
            34.0,
        )

        self.assertEqual(
            winner.event_id,
            "34_or_higher",
        )

    def test_certification_has_one_winner(self) -> None:
        winner = certify_book(
            self.events,
            30.9,
        )

        self.assertEqual(
            winner,
            "30_to_31",
        )

    def test_gap_is_rejected(self) -> None:
        invalid = list(self.events)

        invalid[1] = EventInterval(
            event_id=invalid[1].event_id,
            lower_c=25.1,
            upper_c=26.0,
            lower_closed=True,
            upper_closed=False,
        )

        with self.assertRaises(ValueError):
            validate_partition(
                invalid,
                expected_count=11,
            )

    def test_double_boundary_membership_is_rejected(self) -> None:
        invalid = list(self.events)

        invalid[0] = EventInterval(
            event_id=invalid[0].event_id,
            lower_c=None,
            upper_c=25.0,
            lower_closed=False,
            upper_closed=True,
        )

        with self.assertRaises(ValueError):
            validate_partition(
                invalid,
                expected_count=11,
            )


if __name__ == "__main__":
    unittest.main()
