import pytest

from matchbook.measure import _against

# Two invoices, one invoice cancellation, three receipts, one receipt cancellation:
# i = 2, c = 1, r = 3, g = 1, so the stored difference is consistent strictly inside (-3, 4).
INVOICED_BACK = [10.0]
RECEIVED = [30.0, 30.0, 30.0]
RECEIVED_BACK = [30.0]


def against(difference: float) -> str:
    # Net received is 90 - 30 = 60; the invoices net to 60 + difference after the cancellation.
    invoiced = [40.0, 30.0 + difference]
    return _against(invoiced, INVOICED_BACK, RECEIVED, RECEIVED_BACK)


@pytest.mark.criterion("C6")
@pytest.mark.parametrize("difference", [-2.99, -1.0, 0.0, 2.5, 3.99])
def test_against_is_consistent_strictly_inside_the_bound(difference: float) -> None:
    assert against(difference) == "consistent"


@pytest.mark.criterion("C6")
@pytest.mark.parametrize("difference", [4.0, 4.01, 50.0])
def test_against_is_invoiced_above_at_r_plus_c_and_above(difference: float) -> None:
    assert against(difference) == "invoiced above"


@pytest.mark.criterion("C6")
@pytest.mark.parametrize("difference", [-3.0, -3.01, -50.0])
def test_against_is_invoiced_below_at_minus_i_plus_g_and_below(difference: float) -> None:
    assert against(difference) == "invoiced below"
