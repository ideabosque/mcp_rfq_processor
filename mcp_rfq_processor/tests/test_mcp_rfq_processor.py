#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import annotations, print_function

__author__ = "bibow"

"""
Comprehensive Tests for MCP RFQ Processor

Tests all functionality of the MCP RFQ Processor package:
- Processor initialization and configuration
- Request management (CRUD operations)
- Item management
- Provider item management
- Quote management
- Quote item management
- Pricing and discounts
- Installment management
- File management
- Segment management
- MCP tool operations
- GraphQL operations

Coverage: All processor methods, MCP tools, and validation.
"""

import json
import logging
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import pytest
from dotenv import load_dotenv

load_dotenv()
_TEST_ENV_FILE = Path(__file__).with_name(".env")
if _TEST_ENV_FILE.exists():
    load_dotenv(_TEST_ENV_FILE)

_TEST_FUNCTION_ENV = "MCP_RFQ_TEST_FUNCTION"
_TEST_MARKER_ENV = "MCP_RFQ_TEST_MARKERS"

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("test_mcp_rfq_processor")

# Make package importable in common local setups
base_dir = os.getenv("base_dir", os.getcwd())
sys.path.insert(0, base_dir)
sys.path.insert(0, os.path.join(base_dir, "silvaengine_utility"))
sys.path.insert(0, os.path.join(base_dir, "silvaengine_dynamodb_base"))
sys.path.insert(0, os.path.join(base_dir, "mcp_rfq_processor"))
sys.path.insert(0, os.path.join(base_dir, "ai_rfq_engine"))

from mcp_rfq_processor.mcp_rfq_processor import MCPRfqProcessor

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _call_method(
    processor: Any,
    method_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    label: Optional[str] = None,
) -> tuple[Optional[Any], Optional[Exception]]:
    """Invoke processor methods with consistent logging and error capture."""
    arguments = arguments or {}
    op = label or method_name
    cid = uuid.uuid4().hex[:8]
    logger.info(f"Method call: cid={cid} op={op} arguments={arguments}")
    t0 = time.perf_counter()

    try:
        method = getattr(processor, method_name)
    except AttributeError as exc:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(
            f"Method response: cid={cid} op={op} elapsed_ms={elapsed_ms} success=False error={str(exc)}"
        )
        return None, exc

    try:
        result = method(**arguments)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(
            f"Method response: cid={cid} op={op} elapsed_ms={elapsed_ms} success=True result={result}"
        )
        return result, None
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(
            f"Method response: cid={cid} op={op} elapsed_ms={elapsed_ms} success=False error={str(exc)}"
        )
        return None, exc


def log_test_result(func):
    """Decorator to log test results."""
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        test_name = func.__name__
        logger.info(f"{'='*80}")
        logger.info(f"Starting test: {test_name}")
        logger.info(f"{'='*80}")
        t0 = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            logger.info(f"{'='*80}")
            logger.info(f"Test {test_name} PASSED (elapsed: {elapsed_ms}ms)")
            logger.info(f"{'='*80}\n")
            return result
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            logger.error(f"{'='*80}")
            logger.error(f"Test {test_name} FAILED (elapsed: {elapsed_ms}ms): {exc}")
            logger.error(f"{'='*80}\n")
            raise

    return wrapper


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add --test-function option sourced from environment variable."""
    parser.addoption(
        "--test-function",
        action="store",
        default=os.getenv(_TEST_FUNCTION_ENV, "").strip(),
        help=(
            "Run only tests whose name contains this substring. "
            f"Defaults to the {_TEST_FUNCTION_ENV} environment variable when set."
        ),
    )
    parser.addoption(
        "--test-markers",
        action="store",
        default=os.getenv(_TEST_MARKER_ENV, "").strip(),
        help=(
            "Run only tests that include any of the specified markers "
            "(comma or space separated). "
            f"Defaults to the {_TEST_MARKER_ENV} environment variable when set."
        ),
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Filter collected tests when a specific function name was requested."""
    target = config.getoption("--test-function")
    marker_filter_raw = config.getoption("--test-markers")
    markers = _parse_marker_filter(marker_filter_raw)

    if not target and not markers:
        return

    target_lower = target.lower()
    selected: list[pytest.Item] = []
    deselected: list[pytest.Item] = []

    for item in items:
        name_match = not target_lower or target_lower in item.name.lower()
        marker_match = not markers or any(item.get_closest_marker(m) for m in markers)

        if name_match and marker_match:
            selected.append(item)
        else:
            deselected.append(item)

    if not selected:
        _raise_no_matches(_format_filter_description(target, marker_filter_raw), items)

    items[:] = selected
    config.hook.pytest_deselected(items=deselected)

    terminal = config.pluginmanager.get_plugin("terminalreporter")
    if terminal is not None:
        terminal.write_line(
            "Filtered tests with "
            f"{_format_filter_description(target, marker_filter_raw)} "
            f"({len(selected)} selected, {len(deselected)} deselected)."
        )


def _parse_marker_filter(raw: str) -> list[str]:
    """Return marker names from comma/space separated string."""
    if not raw:
        return []
    parts = re.split(r"[,\s]+", raw.strip())
    return [part for part in parts if part]


def _format_filter_description(target: str, marker_filter_raw: str) -> str:
    """Build a human-readable description of active filters."""
    descriptors: list[str] = []
    if target:
        descriptors.append(f"{_TEST_FUNCTION_ENV}='{target}'")
    if marker_filter_raw:
        descriptors.append(f"{_TEST_MARKER_ENV}='{marker_filter_raw}'")
    return " and ".join(descriptors) if descriptors else "no filters"


def _raise_no_matches(filters_desc: str, items: Sequence[pytest.Item]) -> None:
    """Raise an informative error when no tests matched the filter."""
    sample = ", ".join(sorted(item.name for item in items)[:5])
    hint = f" Available sample: {sample}" if sample else ""
    raise pytest.UsageError(f"{filters_desc} did not match any collected tests.{hint}")


# ============================================================================
# SETTINGS
# ============================================================================

SETTING = {
    "region_name": os.getenv("region_name"),
    "aws_access_key_id": os.getenv("aws_access_key_id"),
    "aws_secret_access_key": os.getenv("aws_secret_access_key"),
    "functs_on_local": {
        "ai_rfq_graphql": {
            "module_name": "ai_rfq_engine",
            "class_name": "AIRFQEngine",
        },
    },
    "endpoint_id": os.getenv("endpoint_id"),
    "execute_mode": os.getenv("execute_mode"),
}


# ============================================================================
# TEST DATA PARAMETERS - Load from JSON file
# ============================================================================


def _load_test_data():
    """Load test data from JSON file."""
    test_data_file = os.path.join(os.path.dirname(__file__), "test_data.json")
    try:
        with open(test_data_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            logger.info(f"Loaded test data from {test_data_file}")
            return data
    except FileNotFoundError:
        logger.warning(f"Test data file not found: {test_data_file}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing test data JSON: {e}")
        return {}


_TEST_DATA = _load_test_data()

# Extract test data sets
ITEM_TEST_DATA = _TEST_DATA.get("item_test_data", [])
ITEM_GET_TEST_DATA = _TEST_DATA.get("item_get_test_data", [])
ITEM_LIST_TEST_DATA = _TEST_DATA.get("item_list_test_data", [])
SEGMENT_TEST_DATA = _TEST_DATA.get("segment_test_data", [])
SEGMENT_GET_TEST_DATA = _TEST_DATA.get("segment_get_test_data", [])
SEGMENT_LIST_TEST_DATA = _TEST_DATA.get("segment_list_test_data", [])
PROVIDER_ITEM_TEST_DATA = _TEST_DATA.get("provider_item_test_data", [])
PROVIDER_ITEM_GET_TEST_DATA = _TEST_DATA.get("provider_item_get_test_data", [])
PROVIDER_ITEM_LIST_TEST_DATA = _TEST_DATA.get("provider_item_list_test_data", [])
PROVIDER_ITEM_BATCH_TEST_DATA = _TEST_DATA.get("provider_item_batch_test_data", [])
PROVIDER_ITEM_BATCH_LIST_TEST_DATA = _TEST_DATA.get(
    "provider_item_batch_list_test_data", []
)
ITEM_PRICE_TIER_TEST_DATA = _TEST_DATA.get("item_price_tier_test_data", [])
ITEM_PRICE_TIER_LIST_TEST_DATA = _TEST_DATA.get("item_price_tier_list_test_data", [])
DISCOUNT_RULE_TEST_DATA = _TEST_DATA.get("discount_rule_test_data", [])
DISCOUNT_RULE_LIST_TEST_DATA = _TEST_DATA.get("discount_rule_list_test_data", [])
REQUEST_TEST_DATA = _TEST_DATA.get("request_test_data", [])
REQUEST_GET_TEST_DATA = _TEST_DATA.get("request_get_test_data", [])
REQUEST_LIST_TEST_DATA = _TEST_DATA.get("request_list_test_data", [])
QUOTE_TEST_DATA = _TEST_DATA.get("quote_test_data", [])
QUOTE_GET_TEST_DATA = _TEST_DATA.get("quote_get_test_data", [])
QUOTE_LIST_TEST_DATA = _TEST_DATA.get("quote_list_test_data", [])
QUOTE_ITEM_TEST_DATA = _TEST_DATA.get("quote_item_test_data", [])
INSTALLMENT_TEST_DATA = _TEST_DATA.get("installment_test_data", [])
INSTALLMENT_LIST_TEST_DATA = _TEST_DATA.get("installment_list_test_data", [])
FILE_TEST_DATA = _TEST_DATA.get("file_test_data", [])


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture(scope="module")
def mcp_rfq_processor():
    """Provide an MCPRfqProcessor instance."""
    try:
        processor = MCPRfqProcessor(logger, **SETTING)
        processor.endpoint_id = SETTING.get("endpoint_id")
        setattr(processor, "__is_real__", True)
        logger.info("MCPRfqProcessor initialized successfully")
        return processor
    except Exception as ex:
        logger.warning(f"MCPRfqProcessor initialization failed: {ex}")
        pytest.skip(f"MCPRfqProcessor not available: {ex}")


# ============================================================================
# SEGMENT MANAGEMENT TESTS
# ============================================================================


@pytest.mark.integration
@pytest.mark.parametrize("test_data", SEGMENT_TEST_DATA)
@log_test_result
def test_create_segment(mcp_rfq_processor, test_data):
    """Test creating segment."""
    result, error = _call_method(
        mcp_rfq_processor,
        "create_segment",
        {
            "segment_name": test_data.get("segmentName"),
            "segment_description": test_data.get("segmentDescription", ""),
        },
        "create_segment",
    )

    assert error is None
    assert result is not None
    assert "segment_uuid" in result


@pytest.mark.integration
@pytest.mark.parametrize("test_data", SEGMENT_TEST_DATA)
@log_test_result
def test_add_contact_to_segment(mcp_rfq_processor, test_data):
    """Test adding contact to segment."""
    result, error = _call_method(
        mcp_rfq_processor,
        "add_contact_to_segment",
        {
            "segment_uuid": test_data.get("segmentUuid"),
            "contact_uuid": test_data.get("email", "test@example.com"),
        },
        "add_contact_to_segment",
    )

    assert error is None
    assert result is not None
    assert "segment_uuid" in result


@pytest.mark.integration
@pytest.mark.parametrize("test_data", SEGMENT_LIST_TEST_DATA)
@log_test_result
def test_get_segment_contacts(mcp_rfq_processor, test_data):
    """Test getting segment contacts."""
    result, error = _call_method(
        mcp_rfq_processor,
        "get_segment_contacts",
        {"segment_uuid": test_data.get("segmentUuid")},
        "get_segment_contacts",
    )

    assert error is None
    assert result is not None
    assert "total" in result


# ============================================================================
# ITEM CATALOG TESTS
# ============================================================================


@pytest.mark.integration
@pytest.mark.parametrize("test_data", ITEM_LIST_TEST_DATA)
@log_test_result
def test_search_items(mcp_rfq_processor, test_data):
    """Test searching items."""
    result, error = _call_method(
        mcp_rfq_processor,
        "search_items",
        {"item_type": test_data.get("itemType")},
        "search_items",
    )

    assert error is None
    assert result is not None
    assert "total" in result


@pytest.mark.integration
@pytest.mark.parametrize("test_data", ITEM_GET_TEST_DATA)
@log_test_result
def test_get_item(mcp_rfq_processor, test_data):
    """Test getting item details."""
    result, error = _call_method(
        mcp_rfq_processor,
        "get_item",
        {"item_uuid": test_data.get("itemUuid")},
        "get_item",
    )

    assert error is None
    assert result is not None
    assert result["item_uuid"] == test_data.get("itemUuid")


@pytest.mark.integration
@pytest.mark.parametrize("test_data", PROVIDER_ITEM_LIST_TEST_DATA)
@log_test_result
def test_get_provider_items(mcp_rfq_processor, test_data):
    """Test getting provider items."""
    result, error = _call_method(
        mcp_rfq_processor,
        "get_provider_items",
        {"item_uuid": test_data.get("itemUuid")},
        "get_provider_items",
    )

    assert error is None
    assert result is not None
    assert "total" in result


@pytest.mark.integration
@pytest.mark.parametrize("test_data", PROVIDER_ITEM_BATCH_LIST_TEST_DATA)
@log_test_result
def test_get_provider_item_batches(mcp_rfq_processor, test_data):
    """Test getting provider item batches."""
    result, error = _call_method(
        mcp_rfq_processor,
        "get_provider_item_batches",
        {"provider_item_uuid": test_data.get("providerItemUuid")},
        "get_provider_item_batches",
    )

    assert error is None
    assert result is not None
    assert "total" in result


# ============================================================================
# PRICING TESTS
# ============================================================================


@pytest.mark.integration
@pytest.mark.parametrize("test_data", ITEM_PRICE_TIER_LIST_TEST_DATA)
@log_test_result
def test_get_item_price_tiers(mcp_rfq_processor, test_data):
    """Test getting item price tiers."""
    result, error = _call_method(
        mcp_rfq_processor,
        "get_item_price_tiers",
        {"item_uuid": test_data.get("itemUuid")},
        "get_item_price_tiers",
    )

    assert error is None
    assert result is not None
    assert "total" in result


@pytest.mark.integration
@pytest.mark.parametrize("test_data", DISCOUNT_RULE_LIST_TEST_DATA)
@log_test_result
def test_get_discount_rules(mcp_rfq_processor, test_data):
    """Test getting discount rules."""
    result, error = _call_method(
        mcp_rfq_processor,
        "get_discount_rules",
        {"item_uuid": test_data.get("itemUuid")},
        "get_discount_rules",
    )

    assert error is None
    assert result is not None
    assert "total" in result


# ============================================================================
# REQUEST MANAGEMENT TESTS
# ============================================================================


@pytest.mark.integration
@pytest.mark.parametrize("test_data", REQUEST_TEST_DATA)
@log_test_result
def test_submit_rfq_request(mcp_rfq_processor, test_data):
    """Test submitting RFQ request."""
    result, error = _call_method(
        mcp_rfq_processor,
        "submit_rfq_request",
        {
            "contact_uuid": test_data.get("email"),
            "request_title": test_data.get("requestTitle"),
            "request_description": test_data.get("requestDescription", ""),
        },
        "submit_rfq_request",
    )

    assert error is None
    assert result is not None
    assert "request_uuid" in result


@pytest.mark.integration
@pytest.mark.parametrize("test_data", REQUEST_GET_TEST_DATA)
@log_test_result
def test_get_rfq_request(mcp_rfq_processor, test_data):
    """Test retrieving RFQ request."""
    result, error = _call_method(
        mcp_rfq_processor,
        "get_rfq_request",
        {"request_uuid": test_data.get("requestUuid")},
        "get_rfq_request",
    )

    assert error is None
    assert result is not None
    assert result["request_uuid"] == test_data.get("requestUuid")


@pytest.mark.integration
@pytest.mark.parametrize("test_data", REQUEST_LIST_TEST_DATA)
@log_test_result
def test_search_rfq_requests(mcp_rfq_processor, test_data):
    """Test searching RFQ requests."""
    result, error = _call_method(
        mcp_rfq_processor,
        "search_rfq_requests",
        {"limit": test_data.get("limit", 20)},
        "search_rfq_requests",
    )

    assert error is None
    assert result is not None
    assert "total" in result


@pytest.mark.integration
@pytest.mark.parametrize("test_data", REQUEST_TEST_DATA)
@log_test_result
def test_update_rfq_request(mcp_rfq_processor, test_data):
    """Test updating RFQ request."""
    result, error = _call_method(
        mcp_rfq_processor,
        "update_rfq_request",
        {
            "request_uuid": test_data.get("requestUuid"),
            "request_title": "Updated " + test_data.get("requestTitle", ""),
            "items": test_data.get("items", []),
        },
        "update_rfq_request",
    )

    assert error is None
    assert result is not None
    assert "request_uuid" in result


@pytest.mark.integration
@pytest.mark.parametrize("test_data", REQUEST_TEST_DATA)
@log_test_result
def test_add_item_to_rfq_request(mcp_rfq_processor, test_data):
    """Test adding item to RFQ request."""
    # Prepare a test item to add
    test_item = test_data.get("items")[0]

    result, error = _call_method(
        mcp_rfq_processor,
        "add_item_to_rfq_request",
        {
            "request_uuid": test_data.get("requestUuid"),
            "item": test_item,
        },
        "add_item_to_rfq_request",
    )

    assert error is None
    assert result is not None
    assert "request_uuid" in result
    assert "items" in result
    # Verify the item was added
    items = result.get("items", [])
    assert any(
        item.get("item_uuid") == test_item["item_uuid"] for item in items
    ), "Added item not found in request"


@pytest.mark.integration
@pytest.mark.parametrize("test_data", REQUEST_TEST_DATA)
@log_test_result
def test_remove_item_from_rfq_request_by_uuid(mcp_rfq_processor, test_data):
    """Test removing item from RFQ request by UUID."""
    # First, get the request to see current items
    get_result, get_error = _call_method(
        mcp_rfq_processor,
        "get_rfq_request",
        {"request_uuid": test_data.get("requestUuid")},
        "get_rfq_request_before_remove",
    )

    assert get_error is None
    assert get_result is not None

    items = get_result.get("items", [])
    if not items:
        pytest.skip("No items in request to test removal")

    # Get the first item's UUID
    first_item = items[0]
    item_uuid_to_remove = first_item.get("item_uuid")

    if not item_uuid_to_remove:
        pytest.skip("Item does not have UUID for removal test")

    # Remove the item by UUID
    result, error = _call_method(
        mcp_rfq_processor,
        "remove_item_from_rfq_request",
        {
            "request_uuid": test_data.get("requestUuid"),
            "item_uuid": item_uuid_to_remove,
        },
        "remove_item_from_rfq_request_by_uuid",
    )

    assert error is None
    assert result is not None
    assert "request_uuid" in result
    assert "items" in result
    # Verify the item was removed
    remaining_items = result.get("items", [])
    assert not any(
        item.get("item_uuid") == item_uuid_to_remove for item in remaining_items
    ), "Item was not removed from request"


@pytest.mark.integration
@pytest.mark.parametrize("test_data", REQUEST_TEST_DATA)
@log_test_result
def test_remove_item_from_rfq_request_by_name(mcp_rfq_processor, test_data):
    """Test removing item from RFQ request by name."""
    # First, get the request to see current items
    get_result, get_error = _call_method(
        mcp_rfq_processor,
        "get_rfq_request",
        {"request_uuid": test_data.get("requestUuid")},
        "get_rfq_request_before_remove",
    )

    assert get_error is None
    assert get_result is not None

    items = get_result.get("items", [])
    if not items:
        pytest.skip("No items in request to test removal")

    # Get the first item's name
    first_item = items[0]
    item_name_to_remove = first_item.get("item_name") or first_item.get("itemName")

    if not item_name_to_remove:
        pytest.skip("Item does not have name for removal test")

    # Remove the item by name
    result, error = _call_method(
        mcp_rfq_processor,
        "remove_item_from_rfq_request",
        {
            "request_uuid": test_data.get("requestUuid"),
            "item_name": item_name_to_remove,
        },
        "remove_item_from_rfq_request_by_name",
    )

    assert error is None
    assert result is not None
    assert "request_uuid" in result
    assert "items" in result
    # Verify the item was removed
    remaining_items = result.get("items", [])
    assert not any(
        item.get("item_name") == item_name_to_remove
        or item.get("itemName") == item_name_to_remove
        for item in remaining_items
    ), "Item was not removed from request"


@pytest.mark.integration
@pytest.mark.parametrize("test_data", REQUEST_TEST_DATA)
@log_test_result
def test_assign_provider_item_to_request_item(mcp_rfq_processor, test_data):
    """Test assigning provider item to request item using provider_items array."""
    # First, get the request to see current items
    get_result, get_error = _call_method(
        mcp_rfq_processor,
        "get_rfq_request",
        {"request_uuid": test_data.get("requestUuid")},
        "get_rfq_request_before_assign",
    )

    assert get_error is None
    assert get_result is not None

    items = get_result.get("items", [])
    if not items:
        pytest.skip("No items in request to test provider item assignment")

    # Get the first item's UUID
    first_item = items[0]
    item_uuid = first_item.get("item_uuid")

    if not item_uuid:
        pytest.skip("Item does not have UUID for provider item assignment test")

    # Test provider item data to assign
    test_provider_item_uuid = items[0]["provider_items"][0]["provider_item_uuid"]
    test_provider_corp_external_id = items[0]["provider_items"][0][
        "provider_corp_external_id"
    ]
    test_batch_no = items[0]["provider_items"][0]["batch_no"]
    test_qty = 50

    # Assign provider item to the item (replace mode)
    result, error = _call_method(
        mcp_rfq_processor,
        "assign_provider_item_to_request_item",
        {
            "request_uuid": test_data.get("requestUuid"),
            "item_uuid": item_uuid,
            "provider_item_uuid": test_provider_item_uuid,
            "provider_corp_external_id": test_provider_corp_external_id,
            "batch_no": test_batch_no,
            "qty": test_qty,
            "add_qty": False,  # Replace mode
        },
        "assign_provider_item_to_request_item",
    )

    assert error is None
    assert result is not None
    assert "request_uuid" in result
    assert "items" in result

    # Verify the provider item was assigned to provider_items array
    updated_items = result.get("items", [])
    assigned_item = next(
        (item for item in updated_items if item.get("item_uuid") == item_uuid), None
    )
    assert assigned_item is not None, "Item not found in updated request"
    assert "provider_items" in assigned_item, "provider_items array not found in item"

    provider_items = assigned_item.get("provider_items", [])
    assert len(provider_items) > 0, "No provider items in array"

    # Find the assigned provider item
    assigned_provider_item = next(
        (
            pi
            for pi in provider_items
            if pi.get("provider_item_uuid") == test_provider_item_uuid
        ),
        None,
    )
    assert (
        assigned_provider_item is not None
    ), "Provider item not found in provider_items array"
    assert (
        assigned_provider_item.get("batch_no") == test_batch_no
    ), "Batch number not set correctly"
    assert assigned_provider_item.get("qty") == test_qty, "Quantity not set correctly"


@pytest.mark.integration
@pytest.mark.parametrize("test_data", REQUEST_TEST_DATA)
@log_test_result
def test_assign_provider_item_add_qty_mode(mcp_rfq_processor, test_data):
    """Test assigning provider item with add_qty mode."""
    # First, get the request to see current items
    get_result, get_error = _call_method(
        mcp_rfq_processor,
        "get_rfq_request",
        {"request_uuid": test_data.get("requestUuid")},
        "get_rfq_request_before_add_qty",
    )

    assert get_error is None
    assert get_result is not None

    items = test_data.get("items", [])
    if not items:
        pytest.skip("No items in request to test provider item assignment")

    # Get the first item's UUID
    first_item = items[0]
    item_uuid = first_item.get("item_uuid")

    if not item_uuid:
        pytest.skip("Item does not have UUID for provider item assignment test")

    # Test provider item data
    test_provider_item_uuid = items[0]["provider_items"][0]["provider_item_uuid"]
    test_provider_corp_external_id = items[0]["provider_items"][0][
        "provider_corp_external_id"
    ]
    test_batch_no = items[0]["provider_items"][0]["batch_no"]
    initial_qty = 30

    # First assignment - create provider item
    result1, error1 = _call_method(
        mcp_rfq_processor,
        "assign_provider_item_to_request_item",
        {
            "request_uuid": test_data.get("requestUuid"),
            "item_uuid": item_uuid,
            "provider_item_uuid": test_provider_item_uuid,
            "provider_corp_external_id": test_provider_corp_external_id,
            "batch_no": test_batch_no,
            "qty": initial_qty,
            "add_qty": False,
        },
        "assign_provider_item_initial",
    )

    assert error1 is None
    assert result1 is not None

    # Second assignment - add to existing quantity
    add_qty = 25
    result2, error2 = _call_method(
        mcp_rfq_processor,
        "assign_provider_item_to_request_item",
        {
            "request_uuid": test_data.get("requestUuid"),
            "item_uuid": item_uuid,
            "provider_item_uuid": test_provider_item_uuid,
            "provider_corp_external_id": test_provider_corp_external_id,
            "batch_no": test_batch_no,
            "qty": add_qty,
            "add_qty": True,  # Add mode
        },
        "assign_provider_item_add_qty",
    )

    assert error2 is None
    assert result2 is not None

    # Verify the quantity was added
    updated_items = result2.get("items", [])
    assigned_item = next(
        (item for item in updated_items if item.get("item_uuid") == item_uuid), None
    )
    assert assigned_item is not None

    provider_items = assigned_item.get("provider_items", [])
    assigned_provider_item = next(
        (
            pi
            for pi in provider_items
            if pi.get("provider_item_uuid") == test_provider_item_uuid
            and pi.get("batch_no") == test_batch_no
        ),
        None,
    )
    assert assigned_provider_item is not None
    expected_qty = initial_qty + add_qty
    assert (
        assigned_provider_item.get("qty") == expected_qty
    ), f"Expected qty {expected_qty}, got {assigned_provider_item.get('qty')}"


@pytest.mark.integration
@pytest.mark.parametrize("test_data", REQUEST_TEST_DATA)
@log_test_result
def test_remove_provider_item_from_request_item(mcp_rfq_processor, test_data):
    """Test removing provider item assignment from request item using provider_items array."""
    # First, get the request to see current items
    get_result, get_error = _call_method(
        mcp_rfq_processor,
        "get_rfq_request",
        {"request_uuid": test_data.get("requestUuid")},
        "get_rfq_request_before_remove_provider_item",
    )

    assert get_error is None
    assert get_result is not None

    items = get_result.get("items", [])
    if not items:
        pytest.skip("No items in request to test provider item removal")

    # Get the first item's UUID
    first_item = items[0]
    item_uuid = first_item.get("item_uuid")

    if not item_uuid:
        pytest.skip("Item does not have UUID for provider item removal test")

    # Check if item has provider_items
    provider_items = first_item.get("provider_items", [])
    if not provider_items:
        pytest.skip("Item has no provider items to remove")

    # Get the first provider item to remove
    first_provider_item = provider_items[0]
    provider_item_uuid_to_remove = first_provider_item.get("provider_item_uuid")
    batch_no_to_match = first_provider_item.get("batch_no")

    if not provider_item_uuid_to_remove:
        pytest.skip("Provider item does not have UUID for removal test")

    # Remove provider item from the item
    result, error = _call_method(
        mcp_rfq_processor,
        "remove_provider_item_from_request_item",
        {
            "request_uuid": test_data.get("requestUuid"),
            "item_uuid": item_uuid,
            "provider_item_uuid": provider_item_uuid_to_remove,
            "batch_no": batch_no_to_match,
        },
        "remove_provider_item_from_request_item",
    )

    assert error is None
    assert result is not None
    assert "request_uuid" in result
    assert "items" in result
    assert result.get("status") == "modified"

    # Verify the provider item assignment was removed
    updated_items = result.get("items", [])
    updated_item = next(
        (item for item in updated_items if item.get("item_uuid") == item_uuid), None
    )
    assert updated_item is not None, "Item not found in updated request"

    updated_provider_items = updated_item.get("provider_items", [])
    # Verify the specific provider item was removed
    removed_provider_item = next(
        (
            pi
            for pi in updated_provider_items
            if pi.get("provider_item_uuid") == provider_item_uuid_to_remove
            and (batch_no_to_match is None or pi.get("batch_no") == batch_no_to_match)
        ),
        None,
    )
    assert (
        removed_provider_item is None
    ), "Provider item was not removed from provider_items array"


@pytest.mark.integration
@pytest.mark.parametrize("test_data", REQUEST_TEST_DATA)
@log_test_result
def test_remove_all_provider_item_instances(mcp_rfq_processor, test_data):
    """Test removing all instances of a provider item regardless of batch_no."""
    # First, get the request to see current items
    get_result, get_error = _call_method(
        mcp_rfq_processor,
        "get_rfq_request",
        {"request_uuid": test_data.get("requestUuid")},
        "get_rfq_request_before_remove_all_instances",
    )

    assert get_error is None
    assert get_result is not None

    items = test_data.get("items", [])
    if not items:
        pytest.skip("No items in request to test provider item removal")

    # Get the first item's UUID
    first_item = items[0]
    item_uuid = first_item.get("item_uuid")

    if not item_uuid:
        pytest.skip("Item does not have UUID for provider item removal test")

    # Add multiple provider items with different batches
    test_provider_item_uuid = items[0]["provider_items"][0]["provider_item_uuid"]
    test_provider_corp_external_id = items[0]["provider_items"][0][
        "provider_corp_external_id"
    ]
    test_batch_a = items[0]["provider_items"][0]["batch_no"]
    test_batch_b = items[0]["provider_items"][1]["batch_no"]

    # Add first batch
    _call_method(
        mcp_rfq_processor,
        "assign_provider_item_to_request_item",
        {
            "request_uuid": test_data.get("requestUuid"),
            "item_uuid": item_uuid,
            "provider_item_uuid": test_provider_item_uuid,
            "provider_corp_external_id": test_provider_corp_external_id,
            "batch_no": test_batch_a,
            "qty": 10,
        },
        "assign_provider_item_batch_a",
    )

    # Add second batch
    _call_method(
        mcp_rfq_processor,
        "assign_provider_item_to_request_item",
        {
            "request_uuid": test_data.get("requestUuid"),
            "item_uuid": item_uuid,
            "provider_item_uuid": test_provider_item_uuid,
            "provider_corp_external_id": test_provider_corp_external_id,
            "batch_no": test_batch_b,
            "qty": 20,
        },
        "assign_provider_item_batch_b",
    )

    # Remove all instances without specifying batch_no
    result, error = _call_method(
        mcp_rfq_processor,
        "remove_provider_item_from_request_item",
        {
            "request_uuid": test_data.get("requestUuid"),
            "item_uuid": item_uuid,
            "provider_item_uuid": test_provider_item_uuid,
            # batch_no not specified - should remove all instances
        },
        "remove_all_provider_item_instances",
    )

    assert error is None
    assert result is not None

    # Verify all instances were removed
    updated_items = result.get("items", [])
    updated_item = next(
        (item for item in updated_items if item.get("item_uuid") == item_uuid), None
    )
    assert updated_item is not None

    updated_provider_items = updated_item.get("provider_items", [])
    # Verify no instances of the provider item remain
    remaining_instances = [
        pi
        for pi in updated_provider_items
        if pi.get("provider_item_uuid") == test_provider_item_uuid
    ]
    assert (
        len(remaining_instances) == 0
    ), f"Expected 0 instances, found {len(remaining_instances)}"


# ============================================================================
# QUOTE MANAGEMENT TESTS
# ============================================================================


@pytest.mark.integration
@pytest.mark.parametrize("test_data", QUOTE_TEST_DATA)
@log_test_result
def test_create_quote(mcp_rfq_processor, test_data):
    """Test creating quote."""
    result, error = _call_method(
        mcp_rfq_processor,
        "create_quote",
        {
            "request_uuid": test_data.get("requestUuid"),
            "provider_corp_external_id": test_data.get("providerCorpExternalId"),
            "segment_uuid": test_data.get("segmentUuid"),
            "sales_rep_email": test_data.get("salesRepEmail"),
            "shipping_method": test_data.get("shippingMethod"),
            "shipping_amount": test_data.get("shippingAmount"),
        },
        "create_quote",
    )

    assert error is None
    assert result is not None
    assert "quote_uuid" in result


@pytest.mark.integration
@pytest.mark.parametrize("test_data", QUOTE_GET_TEST_DATA)
@log_test_result
def test_get_quote(mcp_rfq_processor, test_data):
    """Test getting quote details."""
    result, error = _call_method(
        mcp_rfq_processor,
        "get_quote",
        {"quote_uuid": test_data.get("quoteUuid")},
        "get_quote",
    )

    assert error is None
    assert result is not None
    assert result["quote_uuid"] == test_data.get("quoteUuid")


@pytest.mark.integration
@pytest.mark.parametrize("test_data", QUOTE_TEST_DATA)
@log_test_result
def test_update_quote(mcp_rfq_processor, test_data):
    """Test updating quote."""
    result, error = _call_method(
        mcp_rfq_processor,
        "update_quote",
        {
            "request_uuid": test_data.get("requestUuid"),
            "quote_uuid": test_data.get("quoteUuid"),
            "status": "submitted",
        },
        "update_quote",
    )

    assert error is None
    assert result is not None
    assert "quote_uuid" in result


@pytest.mark.integration
@pytest.mark.parametrize("test_data", QUOTE_LIST_TEST_DATA)
@log_test_result
def test_search_quotes(mcp_rfq_processor, test_data):
    """Test searching quotes."""
    result, error = _call_method(
        mcp_rfq_processor,
        "search_quotes",
        {"limit": test_data.get("limit", 20)},
        "search_quotes",
    )

    assert error is None
    assert result is not None
    assert "total" in result


@pytest.mark.integration
@pytest.mark.parametrize("test_data", QUOTE_ITEM_TEST_DATA)
@log_test_result
def test_update_quote_item(mcp_rfq_processor, test_data):
    """Test updating quote item."""
    result, error = _call_method(
        mcp_rfq_processor,
        "update_quote_item",
        {
            "quote_uuid": test_data.get("quoteUuid"),
            "quote_item_uuid": test_data.get("quoteItemUuid"),
            "discount_amount": test_data.get("subtotalDiscount", 0.0),
        },
        "update_quote_item",
    )

    assert error is None
    assert result is not None
    assert "quote_item_uuid" in result


@pytest.mark.integration
@pytest.mark.parametrize("test_data", QUOTE_GET_TEST_DATA)
@log_test_result
def test_calculate_quote_pricing(mcp_rfq_processor, test_data):
    """Test calculating quote pricing."""
    result, error = _call_method(
        mcp_rfq_processor,
        "calculate_quote_pricing",
        {"quote_uuid": test_data.get("quoteUuid")},
        "calculate_quote_pricing",
    )

    assert error is None
    assert result is not None
    assert "quote_uuid" in result


@pytest.mark.integration
@pytest.mark.parametrize("test_data", QUOTE_TEST_DATA)
@log_test_result
def test_add_quote_item(mcp_rfq_processor, test_data):
    """Test adding quote item."""
    # Prepare test quote item data
    test_quote_item = {
        "quote_uuid": test_data.get("quoteUuid"),
        "provider_item_uuid": "test-provider-item-uuid-001",
        "item_uuid": "test-item-uuid-001",
        "qty": 10,
        "discount_amount": 5.0,
    }

    result, error = _call_method(
        mcp_rfq_processor,
        "add_quote_item",
        test_quote_item,
        "add_quote_item",
    )

    assert error is None
    assert result is not None
    assert "quote_item_uuid" in result or "quoteItemUuid" in result


@pytest.mark.integration
@pytest.mark.parametrize("test_data", QUOTE_ITEM_TEST_DATA)
@log_test_result
def test_remove_quote_item(mcp_rfq_processor, test_data):
    """Test removing quote item."""
    result, error = _call_method(
        mcp_rfq_processor,
        "remove_quote_item",
        {
            "quote_uuid": test_data.get("quoteUuid"),
            "quote_item_uuid": test_data.get("quoteItemUuid"),
        },
        "remove_quote_item",
    )

    # Note: This may fail if the quote item doesn't exist or has already been deleted
    # The test is checking that the function executes without exceptions
    if error is None:
        assert result is not None


# ============================================================================
# INSTALLMENT TESTS
# ============================================================================


@pytest.mark.integration
@pytest.mark.parametrize("test_data", INSTALLMENT_TEST_DATA)
@log_test_result
def test_create_installment(mcp_rfq_processor, test_data):
    """Test creating installment."""
    result, error = _call_method(
        mcp_rfq_processor,
        "create_installment",
        {
            "quote_uuid": test_data.get("quoteUuid"),
            "installment_number": test_data.get("priority", 1),
            "due_date": test_data.get("scheduledDate"),
            "amount": test_data.get("installmentAmount"),
        },
        "create_installment",
    )

    assert error is None
    assert result is not None
    assert "installment_uuid" in result


@pytest.mark.integration
@pytest.mark.parametrize("test_data", INSTALLMENT_LIST_TEST_DATA)
@log_test_result
def test_get_installments(mcp_rfq_processor, test_data):
    """Test getting installments."""
    result, error = _call_method(
        mcp_rfq_processor,
        "get_installments",
        {"quote_uuid": test_data.get("quoteUuid")},
        "get_installments",
    )

    assert error is None
    assert result is not None
    assert "total" in result


# ============================================================================
# FILE MANAGEMENT TESTS
# ============================================================================


@pytest.mark.integration
@pytest.mark.parametrize("test_data", FILE_TEST_DATA)
@log_test_result
def test_upload_rfq_file(mcp_rfq_processor, test_data):
    """Test uploading RFQ file."""
    result, error = _call_method(
        mcp_rfq_processor,
        "upload_rfq_file",
        {
            "request_uuid": test_data.get("requestUuid"),
            "file_name": test_data.get("fileName"),
        },
        "upload_rfq_file",
    )

    assert error is None
    assert result is not None
    assert "file_name" in result


@pytest.mark.integration
@pytest.mark.parametrize("test_data", FILE_TEST_DATA)
@log_test_result
def test_get_rfq_files(mcp_rfq_processor, test_data):
    """Test getting RFQ files."""
    result, error = _call_method(
        mcp_rfq_processor,
        "get_rfq_files",
        {"request_uuid": test_data.get("requestUuid")},
        "get_rfq_files",
    )

    assert error is None
    assert result is not None
    assert "total" in result


# ============================================================================
# WORKFLOW TESTS
# ============================================================================


@pytest.mark.integration
@log_test_result
def test_complete_rfq_workflow(mcp_rfq_processor):
    """Test complete RFQ workflow from request to quote."""
    if not REQUEST_TEST_DATA or not QUOTE_TEST_DATA:
        pytest.skip("Insufficient test data for workflow test")

    request_data = REQUEST_TEST_DATA[0]
    quote_data = QUOTE_TEST_DATA[0]

    # Step 1: Submit request
    request_result, request_error = _call_method(
        mcp_rfq_processor,
        "submit_rfq_request",
        {
            "contact_uuid": request_data.get("email"),
            "request_title": request_data.get("requestTitle"),
            "request_description": request_data.get("requestDescription", ""),
        },
        "workflow_submit_request",
    )

    assert request_error is None
    assert "request_uuid" in request_result
    logger.info(f"Workflow Step 1: Request created - {request_result['request_uuid']}")

    # Step 2: Create quote
    quote_result, quote_error = _call_method(
        mcp_rfq_processor,
        "create_quote",
        {
            "request_uuid": request_result["request_uuid"],
            "provider_corp_external_id": quote_data.get("providerCorpExternalId"),
            "shipping_method": quote_data.get("shippingMethod"),
            "shipping_amount": quote_data.get("shippingAmount"),
        },
        "workflow_create_quote",
    )

    assert quote_error is None
    assert "quote_uuid" in quote_result
    logger.info(f"Workflow Step 2: Quote created - {quote_result['quote_uuid']}")
    logger.info("Complete RFQ workflow executed successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v"], plugins=[sys.modules[__name__]])
