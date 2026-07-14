from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from apps.api.policy_schemas import (
    AllocationItemInput,
    AllocationReplaceRequest,
    AllocationResponse,
    PolicyDraftUpdate,
    PolicyVersionResponse,
    normalize_asset_class_name,
)


@pytest.mark.parametrize("value", [12.5, 12, Decimal("12.50"), None])
def test_allocation_rejects_non_string_percentages(value) -> None:
    with pytest.raises(ValidationError):
        AllocationItemInput(asset_class_name="Cash", target_percentage=value)


@pytest.mark.parametrize("value", ["1.234", "0.00", "-1.00", "100.01", "NaN"])
def test_allocation_rejects_invalid_precision_and_range(value: str) -> None:
    with pytest.raises(ValidationError):
        AllocationItemInput(asset_class_name="Cash", target_percentage=value)


def test_allocation_normalizes_decimal_string_without_binary_float() -> None:
    item = AllocationItemInput(asset_class_name="Cash", target_percentage="12.5")
    assert item.target_percentage == "12.50"


def test_unicode_name_normalization_is_nfkc_whitespace_collapsed_and_casefolded() -> None:
    display, canonical = normalize_asset_class_name("  Ｇlobal\u2003EQUITY  ")
    assert display == "Global EQUITY"
    assert canonical == "global equity"


def test_allocation_collection_rejects_canonical_duplicates() -> None:
    with pytest.raises(ValidationError):
        AllocationReplaceRequest(
            expected_revision=1,
            items=[
                {"asset_class_name": "Cash", "target_percentage": "50.00"},
                {"asset_class_name": "  CASH ", "target_percentage": "50.00"},
            ],
        )


def test_policy_patch_trims_text_and_rejects_extra_or_null_fields() -> None:
    payload = PolicyDraftUpdate(expected_revision=1, objectives="  Owner goal  ")
    assert payload.objectives == "Owner goal"
    with pytest.raises(ValidationError):
        PolicyDraftUpdate(expected_revision=1, unknown="private")
    with pytest.raises(ValidationError):
        PolicyDraftUpdate(expected_revision=1, objectives=None)


def test_response_serializes_percentage_as_decimal_string_and_hides_internal_fields() -> None:
    allocation = AllocationResponse.model_validate(
        {
            "id": uuid4(),
            "asset_class_name": "Cash",
            "target_percentage": Decimal("12.50"),
            "sort_order": 0,
            "normalized_asset_class_name": "cash",
        }
    )
    version = PolicyVersionResponse.model_validate(
        {
            "id": uuid4(),
            "policy_id": uuid4(),
            "version_number": 1,
            "status": "published",
            "objectives": "Owner goal",
            "time_horizon": "Long term",
            "liquidity": "",
            "diversification": "",
            "contribution_policy": "",
            "rebalancing_policy": "",
            "prohibited_assets": "",
            "leverage_policy": "",
            "decision_process": "Owner process",
            "notes": "",
            "published_at": datetime.now(timezone.utc),
            "superseded_at": None,
            "allocations": [allocation],
        }
    )
    body = version.model_dump(mode="json")
    assert body["allocations"][0]["target_percentage"] == "12.50"
    assert "normalized_asset_class_name" not in str(body)
    assert "sealed_at" not in body
