#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

__author__ = "bibow"

from typing import Any, Dict

import humps

# Import centralized error handling utilities
from .error_handler import (
    handle_errors,
    propagate_error_if_present,
    validate_not_empty,
)

# Import status management
from .quote_processor import QuoteProcessor


class PricingProcessor(QuoteProcessor):
    # ==================== Pricing Tools ====================

    # * MCP Function.
    @handle_errors(operation_name="get item price tiers")
    def get_item_price_tiers(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get tiered pricing for items.
        Maps to GraphQL: itemPriceTierList query

        Supports quantity-based filtering to find applicable price tiers:
        - Use quantity_value to find the matching tier for a specific quantity
        - Example: For qty=100, use quantity_value=100
          to find tiers where quantity_greater_then <= 100 < quantity_less_then
        """
        variables = {
            "pageNumber": arguments.get("page_number", 1),
            "limit": arguments.get("limit", 50),
            "itemUuid": arguments.get("item_uuid"),
            "providerItemUuid": arguments.get("provider_item_uuid"),
            "segmentUuid": arguments.get("segment_uuid"),
            "quantityValue": arguments.get("quantity_value"),
            "minPrice": arguments.get("min_price"),
            "maxPrice": arguments.get("max_price"),
            "status": "active",
        }

        variables = {k: v for k, v in variables.items() if v is not None and v != ""}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "itemPriceTierList",
            "Query",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        return humps.decamelize(result["itemPriceTierList"])

    # * MCP Function.
    @handle_errors(operation_name="get discount rules")
    def get_discount_rules(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get discount rules for item-level pricing.
        Maps to GraphQL: discountRuleList query

        Required parameters:
        - item_uuid: Item UUID (required for item-specific discount rules)
        - provider_item_uuid: Provider item UUID (required for provider-specific pricing)
        - segment_uuid: Customer segment UUID (required for segment-specific pricing)

        Optional parameters:
        - subtotal_value: Find rules applicable to a specific subtotal amount
          (finds rules where subtotal_greater_than <= value < subtotal_less_than)
        - max_discount_percentage: Filter by maximum discount percentage threshold
        - min_discount_percentage: Filter by minimum discount percentage threshold

        Returns only 'active' discount rules.
        """
        # Validate required parameters
        validate_not_empty(
            arguments.get("item_uuid"), "item_uuid", "Item UUID is required"
        )
        validate_not_empty(
            arguments.get("provider_item_uuid"),
            "provider_item_uuid",
            "Provider item UUID is required",
        )
        validate_not_empty(
            arguments.get("segment_uuid"),
            "segment_uuid",
            "Segment UUID is required",
        )

        variables = {
            "pageNumber": arguments.get("page_number", 1),
            "limit": arguments.get("limit", 50),
            "itemUuid": arguments["item_uuid"],
            "providerItemUuid": arguments["provider_item_uuid"],
            "segmentUuid": arguments["segment_uuid"],
            "subtotalValue": arguments.get("subtotal_value"),
            "maxDiscountPercentage": arguments.get("max_discount_percentage"),
            "minDiscountPercentage": arguments.get("min_discount_percentage"),
            "status": "active",
        }

        variables = {k: v for k, v in variables.items() if v is not None and v != ""}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "discountRuleList",
            "Query",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        return humps.decamelize(result["discountRuleList"])

    # * MCP Function.
    @handle_errors(operation_name="calculate quote pricing")
    def calculate_quote_pricing(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate pricing information for an RFQ request grouped by provider and segment.

        Reads from request items with provider_items arrays and provides:
        - Group-level subtotals (sum of item subtotals)
        - Item-level details with guardrail pricing, batch info, price tiers, and discount rules
        - Each item has its own applicable discount rules based on item subtotal

        Returns pricing structure with discount options for decision-making.
        Does NOT apply discounts - only provides information.

        Args:
            request_uuid: UUID of the RFQ request
            segment_uuid: Customer segment UUID for pricing rules

        Returns:
            Grouped pricing structure with subtotals, and per-item price tiers and discount rules
        """
        self.logger.info(f"Calculating quote pricing info: {arguments}")

        request_uuid = arguments["request_uuid"]
        segment_uuid = arguments["segment_uuid"]

        # Step 1: Get the request with items and provider_items
        request = self.get_rfq_request(request_uuid=request_uuid)
        if error := propagate_error_if_present(request):
            return error

        request_items = request.get("items", [])
        if not request_items:
            return {
                "request_uuid": request_uuid,
                "segment_uuid": segment_uuid,
                "groups": [],
                "subtotal": 0,
            }

        # Step 2: Extract and group provider_items by (provider_corp_external_id, segment_uuid)
        grouped_items = self._group_provider_items_from_request(
            request_items, segment_uuid
        )

        # Step 4: Build output structure with discount rules and price tiers
        pricing_groups = []
        overall_subtotal = 0

        for group_key, group_data in grouped_items.items():
            provider_id, seg_uuid = group_key

            # Prepare item details with guardrail, batch info, price tiers, and discount rules
            items_info = []
            for item in group_data["items"]:
                item_qty = item.get("qty", 0)
                item_uuid = item.get("item_uuid")
                provider_item_uuid = item.get("provider_item_uuid")
                item_subtotal = item.get("subtotal", 0)

                # Get price tiers applicable to this item's quantity
                # Find tiers where quantity_greater_then <= item_qty < quantity_less_then
                price_tiers_result = self.get_item_price_tiers(
                    item_uuid=item_uuid,
                    provider_item_uuid=provider_item_uuid,
                    segment_uuid=seg_uuid,
                    quantity_value=item_qty,
                    limit=50,
                )

                price_tiers = []
                if not propagate_error_if_present(price_tiers_result):
                    raw_price_tiers = price_tiers_result.get("item_price_tier_list", [])
                    # Process price tiers: set price_per_uom and remove provider_item_batches
                    for tier in raw_price_tiers:
                        # Get batch_no from item if present
                        batch_no = item.get("batch_no")

                        if batch_no and "provider_item_batches" in tier:
                            # Find matching batch and use its price_per_uom
                            for batch in tier.get("provider_item_batches", []):
                                if batch.get("batch_no") == batch_no:
                                    tier["price_per_uom"] = batch.get("price_per_uom")
                                    break
                        else:
                            # No batch, use base_price_per_uom from provider_item
                            if (
                                "provider_item" in tier
                                and "base_price_per_uom" in tier["provider_item"]
                            ):
                                tier["price_per_uom"] = tier["provider_item"][
                                    "base_price_per_uom"
                                ]

                        # Keep provider_item and provider_item_batches fields
                        price_tiers.append(tier)

                # Get applicable discount rules for this item's subtotal
                # Find rules where subtotal_greater_than <= item_subtotal < subtotal_less_than
                # Filter by item_uuid, provider_item_uuid, segment_uuid, and subtotal_value
                discount_rules_result = self.get_discount_rules(
                    item_uuid=item_uuid,
                    provider_item_uuid=provider_item_uuid,
                    segment_uuid=seg_uuid,
                    subtotal_value=item_subtotal,
                    limit=50,
                )

                discount_rules = []
                if not propagate_error_if_present(discount_rules_result):
                    raw_discount_rules = discount_rules_result.get(
                        "discount_rule_list", []
                    )
                    # Remove provider_item field from each discount rule
                    discount_rules = [
                        {k: v for k, v in rule.items() if k != "provider_item"}
                        for rule in raw_discount_rules
                    ]

                item_data = {
                    "provider_item_uuid": provider_item_uuid,
                    "item_uuid": item_uuid,
                    "batch_no": item.get("batch_no"),
                    "qty": item_qty,
                    "price_per_uom": item.get("price_per_uom"),
                    "guardrail_price_per_uom": item.get("guardrail_price_per_uom"),
                    "subtotal": item_subtotal,
                    "slow_move_item": item.get("slow_move_item", False),
                    "expired_at": item.get("expired_at"),
                    "price_tiers": price_tiers,
                    "discount_rules": discount_rules,
                }
                items_info.append(item_data)

            # Calculate group subtotal
            group_subtotal = group_data["group_subtotal"]

            group_info = {
                "provider_corp_external_id": provider_id,
                "subtotal": group_subtotal,
                "items": items_info,
            }

            pricing_groups.append(group_info)
            overall_subtotal += group_subtotal

        # Step 3: Return clean structure
        return {
            "request_uuid": request_uuid,
            "segment_uuid": segment_uuid,
            "groups": pricing_groups,
            "subtotal": overall_subtotal,
        }

    def _group_provider_items_from_request(
        self, request_items: list, segment_uuid: str
    ) -> Dict[tuple, Dict]:
        """
        Extract provider_items from request items and group by (provider_corp_external_id, segment_uuid).

        Request item structure:
        {
            "item_uuid": "...",
            "item_name": "...",
            "qty": 100,
            "provider_items": [
                {
                    "provider_item_uuid": "...",
                    "provider_corp_external_id": "PROV-001",
                    "batch_no": "BATCH-001",
                    "qty": 50
                },
                {
                    "provider_item_uuid": "...",
                    "provider_corp_external_id": "PROV-002",
                    "batch_no": null,
                    "qty": 50
                }
            ]
        }

        Args:
            request_items: List of items from request with provider_items arrays
            segment_uuid: Segment UUID for grouping

        Returns:
            Dictionary with group keys and aggregated data:
            {
                (provider_id, segment_uuid): {
                    "items": [list of provider items with pricing],
                    "group_subtotal": sum of subtotals
                }
            }
        """
        groups = {}

        for req_item in request_items:
            item_uuid = req_item.get("item_uuid")
            provider_items = req_item.get("provider_items", [])

            if not provider_items:
                self.logger.warning(
                    f"Request item {item_uuid} has no provider_items, skipping"
                )
                continue

            # Process each provider_item in the array
            for prov_item in provider_items:
                provider_id = prov_item.get("provider_corp_external_id")
                provider_item_uuid = prov_item.get("provider_item_uuid")
                batch_no = prov_item.get("batch_no")
                qty = prov_item.get("qty", req_item.get("qty", 0))

                if not provider_id or not provider_item_uuid:
                    self.logger.warning(
                        f"Provider item missing required fields: {prov_item}"
                    )
                    continue

                # Fetch provider item details for pricing
                try:
                    provider_items_result = self.get_provider_items(
                        provider_item_uuid=provider_item_uuid, limit=1
                    )

                    if error := propagate_error_if_present(provider_items_result):
                        self.logger.error(
                            f"Failed to fetch provider item {provider_item_uuid}: {error}"
                        )
                        continue

                    provider_items_list = provider_items_result.get(
                        "provider_item_list", []
                    )
                    if not provider_items_list:
                        self.logger.warning(
                            f"Provider item {provider_item_uuid} not found"
                        )
                        continue

                    provider_item_data = provider_items_list[0]
                    base_price_per_uom = provider_item_data.get("base_price_per_uom", 0)

                    # Validate pricing exists
                    if base_price_per_uom <= 0:
                        self.logger.warning(
                            f"Provider item {provider_item_uuid} has invalid base_price_per_uom: {base_price_per_uom}"
                        )

                    # Get batch-specific data and guardrail pricing from embedded batches
                    slow_move_item = False
                    expired_at = None
                    batch_guardrail = None

                    if batch_no:
                        # Use the batches already embedded in provider_item_data
                        batch_list = provider_item_data.get("batches", [])

                        for batch_data in batch_list:
                            if batch_data.get("batch_no") == batch_no:
                                batch_guardrail = batch_data.get(
                                    "guardrail_price_per_uom"
                                )
                                slow_move_item = batch_data.get("slow_move_item", False)
                                expired_at = batch_data.get("expired_at")
                                break

                    # Set guardrail: base_price if no batch, else min(base_price, batch_guardrail)
                    if batch_no and batch_guardrail is not None:
                        guardrail_price_per_uom = min(
                            base_price_per_uom, batch_guardrail
                        )
                    else:
                        guardrail_price_per_uom = base_price_per_uom

                    # Get price_per_uom from matched price tier
                    price_per_uom = base_price_per_uom  # Default fallback
                    price_tiers_result = self.get_item_price_tiers(
                        item_uuid=item_uuid,
                        provider_item_uuid=provider_item_uuid,
                        segment_uuid=segment_uuid,
                        quantity_value=qty,
                        limit=1,
                    )

                    if not propagate_error_if_present(price_tiers_result):
                        price_tier_list = price_tiers_result.get(
                            "item_price_tier_list", []
                        )
                        if price_tier_list:
                            price_tier = price_tier_list[0]
                            # Use batch-specific price_per_uom if available; otherwise use tier price_per_uom
                            price_per_uom = price_tier.get("price_per_uom")
                            if batch_no and "provider_item_batches" in price_tier:
                                # Find matching batch and use its margin_per_uom if available
                                for batch in price_tier.get(
                                    "provider_item_batches", []
                                ):
                                    if batch.get("batch_no") == batch_no:
                                        price_per_uom = batch.get("price_per_uom")
                                        break

                    # Ensure price_per_uom is not None before calculation
                    if price_per_uom is None:
                        raise ValueError(
                            f"price_per_uom cannot be None for provider item {provider_item_uuid}"
                        )
                    subtotal = qty * price_per_uom

                    # Build item data
                    item_data = {
                        "provider_item_uuid": provider_item_uuid,
                        "item_uuid": item_uuid,
                        "batch_no": batch_no,
                        "qty": qty,
                        "price_per_uom": price_per_uom,
                        "guardrail_price_per_uom": guardrail_price_per_uom,
                        "subtotal": subtotal,
                        "slow_move_item": slow_move_item,
                        "expired_at": expired_at,
                    }

                    # Group by (provider_corp_external_id, segment_uuid)
                    group_key = (provider_id, segment_uuid)

                    if group_key not in groups:
                        groups[group_key] = {
                            "items": [],
                            "group_subtotal": 0,
                        }

                    groups[group_key]["items"].append(item_data)
                    groups[group_key]["group_subtotal"] += subtotal

                except Exception as e:
                    self.logger.error(
                        f"Error processing provider item {provider_item_uuid}: {e}"
                    )
                    continue

        return groups
