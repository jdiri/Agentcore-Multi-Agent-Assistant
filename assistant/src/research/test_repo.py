
from research.repository import ResearchRepository

repo = ResearchRepository()

# Test 1: Fund lookup
fund = repo.get_fund("LFTS1")
assert fund is not None
print("Fund:", fund["name"])

# Test 2: All funds
funds = repo.list_funds()
assert len(funds) == 25
print("Total funds:", len(funds))

# Test 3: User lookup
user = repo.get_user("u-001")
assert user is not None
print("User:", user["display_name"])

# Test 4: Holdings lookup
holdings = repo.get_holdings_by_user("u-001")
assert len(holdings) == 5
print("User holdings:", len(holdings))

# Test 5: Advisor lookup
advisor = repo.get_advisor(user["advisor_id"])
assert advisor is not None
print("Advisor:", advisor["name"])

# Test 6: User with no holdings
empty_holdings = repo.get_holdings_by_user("u-004")
assert empty_holdings == []
print("u-004 holdings:", len(empty_holdings))

print("All repository tests passed!")
