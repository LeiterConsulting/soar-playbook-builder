"""Ordered deterministic preflight rule set."""

from .actions import ActionResolutionRule
from .assets import AssetBindingRule
from .datapaths import DatapathRule
from .egress import EgressRule
from .graph import GraphPolicyRule
from .index_state import IndexStateRule
from .objects import ReferencedObjectRule
from .parameters import ParameterRule
from .permissions import PermissionRule
from .risk import DestructiveActionRule

RULES = (
    IndexStateRule(),
    ActionResolutionRule(),
    AssetBindingRule(),
    ParameterRule(),
    DatapathRule(),
    PermissionRule(),
    DestructiveActionRule(),
    EgressRule(),
    ReferencedObjectRule(),
    GraphPolicyRule(),
)

__all__ = ["RULES"]
