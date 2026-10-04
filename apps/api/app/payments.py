"""Payment providers for client checkouts (see migration 0019).

Only the simulated provider exists until the business's payment provider is chosen (O1).
A real provider will add: creating a hosted payment page for a checkout (returning its URL),
and verifying the provider's webhook before completing the checkout on a system connection."""

SIMULATED = "simulated"


def provider_for_business() -> str:
    """The provider new checkouts use."""
    return SIMULATED
