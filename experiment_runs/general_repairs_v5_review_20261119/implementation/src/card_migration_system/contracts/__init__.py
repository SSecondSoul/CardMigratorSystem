"""P1 contract boundary. No duplicate model definitions or implicit legacy import.

Use load_p1_contracts(explicit_repository_root).contracts for the pinned API.
Old and new module class identities differ; interchange is versioned JSON.
"""
from ..adapters.legacy_contracts import ContractBindingError, LegacyContractBinding, load_p1_contracts

__all__ = ["ContractBindingError", "LegacyContractBinding", "load_p1_contracts"]
