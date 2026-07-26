"""Certified HKO event partitions and one-decimal settlement."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence


@dataclass(frozen=True)
class EventInterval:
    """One event in a mutually exclusive temperature book."""

    event_id: str
    lower_c: Optional[float]
    upper_c: Optional[float]
    lower_closed: bool
    upper_closed: bool

    def contains(self, value_c: float) -> bool:
        if not math.isfinite(value_c):
            raise ValueError(
                "The settlement temperature must be finite."
            )

        if self.lower_c is None:
            lower_ok = True
        elif self.lower_closed:
            lower_ok = value_c >= self.lower_c
        else:
            lower_ok = value_c > self.lower_c

        if self.upper_c is None:
            upper_ok = True
        elif self.upper_closed:
            upper_ok = value_c <= self.upper_c
        else:
            upper_ok = value_c < self.upper_c

        return lower_ok and upper_ok


def _lower_key(event: EventInterval) -> float:
    return (
        -math.inf
        if event.lower_c is None
        else event.lower_c
    )


def validate_partition(
    events: Sequence[EventInterval],
    expected_count: Optional[int] = 11,
) -> List[EventInterval]:
    if expected_count is not None and len(events) != expected_count:
        raise ValueError(
            f"Expected {expected_count} events; received {len(events)}."
        )

    if len({event.event_id for event in events}) != len(events):
        raise ValueError(
            "Event identifiers must be unique."
        )

    ordered = sorted(events, key=_lower_key)

    if ordered[0].lower_c is not None:
        raise ValueError(
            "The first event must have an unbounded lower tail."
        )

    if ordered[-1].upper_c is not None:
        raise ValueError(
            "The final event must have an unbounded upper tail."
        )

    for event in ordered:
        if (
            event.lower_c is not None
            and event.upper_c is not None
            and event.lower_c >= event.upper_c
        ):
            raise ValueError(
                f"Invalid interval for {event.event_id}."
            )

    for left, right in zip(ordered[:-1], ordered[1:]):
        if left.upper_c is None or right.lower_c is None:
            raise ValueError(
                "Only the first and final events may be unbounded."
            )

        if not math.isclose(
            left.upper_c,
            right.lower_c,
            abs_tol=1e-12,
        ):
            raise ValueError(
                f"Gap or overlap between {left.event_id} "
                f"and {right.event_id}."
            )

        boundary_membership = int(
            left.upper_closed
        ) + int(
            right.lower_closed
        )

        if boundary_membership != 1:
            raise ValueError(
                f"Boundary {left.upper_c} must belong to exactly one event."
            )

    return ordered


def classify_temperature(
    events: Sequence[EventInterval],
    temperature_c: float,
) -> EventInterval:
    ordered = validate_partition(
        events,
        expected_count=None,
    )

    winners = [
        event
        for event in ordered
        if event.contains(temperature_c)
    ]

    if len(winners) != 1:
        raise ValueError(
            f"Temperature {temperature_c} belongs to "
            f"{len(winners)} events."
        )

    return winners[0]


def certify_book(
    events: Sequence[EventInterval],
    temperature_c: float,
    expected_count: int = 11,
) -> str:
    ordered = validate_partition(
        events,
        expected_count=expected_count,
    )

    return classify_temperature(
        ordered,
        temperature_c,
    ).event_id


def build_standard_11_event_book(
    lower_cut_c: int = 25,
    upper_cut_c: int = 34,
) -> List[EventInterval]:
    if upper_cut_c - lower_cut_c != 9:
        raise ValueError(
            "An eleven-event book requires nine "
            "one-degree interior events."
        )

    events: List[EventInterval] = [
        EventInterval(
            event_id=f"below_{lower_cut_c}",
            lower_c=None,
            upper_c=float(lower_cut_c),
            lower_closed=False,
            upper_closed=False,
        )
    ]

    for lower in range(
        lower_cut_c,
        upper_cut_c,
    ):
        events.append(
            EventInterval(
                event_id=f"{lower}_to_{lower + 1}",
                lower_c=float(lower),
                upper_c=float(lower + 1),
                lower_closed=True,
                upper_closed=False,
            )
        )

    events.append(
        EventInterval(
            event_id=f"{upper_cut_c}_or_higher",
            lower_c=float(upper_cut_c),
            upper_c=None,
            lower_closed=True,
            upper_closed=False,
        )
    )

    return validate_partition(
        events,
        expected_count=11,
    )
