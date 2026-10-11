"""Outside services behind swappable providers (decision X13, docs/integrations.md).

Each capability (payments, invoicing, messaging, email, AI, storage) has an interface in the
system's own words, built-in providers that need no account, and a registry: a vendor is one
class registered under a name. Nothing outside this package names a vendor."""
