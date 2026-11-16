import asyncio

import pytest

from coordinator.budget import InMemoryToolBudget


def test_counts_accumulate_per_session():
    async def scenario():
        budget = InMemoryToolBudget()
        await budget.add("s-1", 3)
        await budget.add("s-1", 4)
        await budget.add("s-2", 1)
        return await budget.used("s-1"), await budget.used("s-2"), await budget.used("s-3")

    assert asyncio.run(scenario()) == (7, 1, 0)


def test_least_recently_used_session_is_forgotten_past_the_cap():
    async def scenario():
        budget = InMemoryToolBudget(max_sessions=2)
        await budget.add("old", 5)
        await budget.add("mid", 5)
        await budget.add("old", 1)  # touching "old" makes "mid" the least recent
        await budget.add("new", 5)
        return [await budget.used(s) for s in ("old", "mid", "new")]

    assert asyncio.run(scenario()) == [6, 0, 5]


def test_negative_calls_are_refused():
    with pytest.raises(ValueError):
        asyncio.run(InMemoryToolBudget().add("s-1", -1))


def test_session_cap_must_be_positive():
    with pytest.raises(ValueError):
        InMemoryToolBudget(max_sessions=0)
