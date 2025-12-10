#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

__author__ = "bibow"

from typing import Any, Dict

import humps

# Import centralized error handling utilities
from .error_handler import handle_errors, propagate_error_if_present, validate_not_empty

# Import status management
from .quote_processor import QuoteProcessor


class PricingProcessor(QuoteProcessor):
    # ==================== Pricing Tools ====================

    # * MCP Function.
    @handle_errors(operation_name="resolve item price tiers")
    def get_item_price_tiers(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get tiered pricing for items using batch loader optimization.
        Maps to GraphQL: itemPriceTiers query (uses resolve_item_price_tiers)

        This function uses the optimized batch loader approach from ai_rfq_engine that:
        1. Looks up segment_uuid from email address via segment_contact_loader
        2. Efficiently loads price tiers for multiple items using batch loaders
        3. Filters tiers based on quantity thresholds at the database level
        4. Returns only matching tiers for each item's quantity

        Required parameters:
        - email: Customer email for segment lookup
        - quote_items: List of quote items with item_uuid, provider_item_uuid, and qty

        Example quote_items structure:
        [
            {
                "item_uuid": "item-123",
                "provider_item_uuid": "provider-item-456",
                "qty": 100
            }
        ]

        Returns:
            {
                "item_price_tiers": [
                    {
                        "item_uuid": "...",
                        "provider_item_uuid": "...",
                        "item_price_tier_uuid": "...",
                        "quantity_greater_then": 50,
                        "quantity_less_then": 200,
                        "price_per_uom": 10.5,
                        ...
                    }
                ]
            }
        """
        # Validate required parameters
        validate_not_empty(
            arguments.get("email"), "email", "Email is required for segment lookup"
        )

        email = arguments["email"]
        quote_items = arguments.get("quote_items", [])

        # Validate quote_items structure
        if not isinstance(quote_items, list):
            return {
                "error": "quote_items must be a list",
                "error_type": "ValidationError",
            }

        query = """
        query GetItemPriceTiers($email: String!, $quoteItems: [JSON]) {
            itemPriceTiers(email: $email, quoteItems: $quoteItems) {
                itemUuid
                providerItemUuid
                itemPriceTierUuid
                quantityGreaterThen
                quantityLessThen
                pricePerUom
                marginPerUom
                status
            }
        }
        """

        variables = {
            "email": email,
            "quoteItems": quote_items,
        }

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "itemPriceTiers",
            "Query",
            variables,
            query=query,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        # Return decamelized list of price tiers
        return {"item_price_tiers": humps.decamelize(result["itemPriceTiers"])}

    # * MCP Function.
    @handle_errors(operation_name="get discount prompts")
    def get_discount_prompts(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get discount prompts for items using batch loader optimization.
        Maps to GraphQL: discountPrompts query (uses resolve_discount_prompts)

        This function uses the optimized batch loader approach from ai_rfq_engine that:
        1. Looks up segment_uuid from email address via segment_contact_loader
        2. Efficiently loads discount prompts from all hierarchical scopes:
           - GLOBAL scope (applies to all quotes)
           - SEGMENT scope (applies to customer segment)
           - ITEM scope (applies to specific items)
           - PROVIDER_ITEM scope (applies to specific provider items)
        3. Deduplicates prompts across scopes
        4. Returns combined discount prompts with conditions and rules

        Required parameters:
        - email: Customer email for segment lookup
        - quote_items: List of quote items with item_uuid and provider_item_uuid

        Example quote_items structure:
        [
            {
                "item_uuid": "item-123",
                "provider_item_uuid": "provider-item-456"
            }
        ]

        Returns:
            {
                "discount_prompts": [
                    {
                        "discount_prompt_uuid": "...",
                        "scope": "GLOBAL|SEGMENT|ITEM|PROVIDER_ITEM",
                        "tags": ["tag1", "tag2"],
                        "discount_prompt": "Prompt text",
                        "conditions": {...},
                        "discount_rules": {...},
                        "priority": 1,
                        "status": "active"
                    }
                ]
            }
        """
        # Validate required parameters
        validate_not_empty(
            arguments.get("email"), "email", "Email is required for segment lookup"
        )

        email = arguments["email"]
        quote_items = arguments.get("quote_items", [])

        # Validate quote_items structure
        if not isinstance(quote_items, list):
            return {
                "error": "quote_items must be a list",
                "error_type": "ValidationError",
            }

        query = """
        query GetDiscountPrompts($email: String!, $quoteItems: [JSON]) {
            discountPrompts(email: $email, quoteItems: $quoteItems) {
                discountPromptUuid
                scope
                tags
                discountPrompt
                conditions
                discountRules
                priority
                status
            }
        }
        """

        variables = {
            "email": email,
            "quoteItems": quote_items,
        }

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "discountPrompts",
            "Query",
            variables,
            query=query,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        # Return decamelized list of discount prompts
        return {"discount_prompts": humps.decamelize(result["discountPrompts"])}

    # * MCP Function.
    @handle_errors(operation_name="calculate quote pricing")
    def calculate_quote_pricing(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate pricing information for an RFQ request grouped by provider.

        Uses batch-optimized approach for loading price tiers.

        Reads from request items with provider_items arrays and provides:
        - Group-level subtotals (sum of item subtotals)
        - Item-level details with guardrail pricing, batch info, and price tiers

        Returns pricing structure for decision-making.

        Args:
            request_uuid: UUID of the RFQ request
            email: Customer email for segment lookup and batch-optimized price tier queries

        Returns:
            Grouped pricing structure with subtotals and per-item price tiers
        """
        self.logger.info(f"Calculating quote pricing info: {arguments}")

        request_uuid = arguments["request_uuid"]
        email = arguments["email"]

        # Step 1: Get the request with items and provider_items
        request = self.get_rfq_request(request_uuid=request_uuid)
        if error := propagate_error_if_present(request):
            return error

        request_items = request.get("items", [])
        if not request_items:
            return {
                "request_uuid": request_uuid,
                "groups": [],
            }

        # Step 2: Extract and group provider_items by provider_corp_external_id
        # Note: We no longer need segment_uuid as parameter since we use email
        grouped_items = self._group_provider_items_from_request(request_items, email)

        # Step 3: Batch load price tiers for all items
        all_quote_items = []
        for group_data in grouped_items.values():
            for item in group_data["items"]:
                all_quote_items.append(
                    {
                        "item_uuid": item.get("item_uuid"),
                        "provider_item_uuid": item.get("provider_item_uuid"),
                        "qty": item.get("qty", 0),
                    }
                )

        # Load all price tiers in one batch call
        all_price_tiers = []
        if all_quote_items:
            price_tiers_result = self.get_item_price_tiers(
                email=email,
                quote_items=all_quote_items,
            )
            if not propagate_error_if_present(price_tiers_result):
                all_price_tiers = price_tiers_result.get("item_price_tiers", [])

        # Create lookup maps for efficient access
        price_tier_map = {}
        for tier in all_price_tiers:
            key = (tier.get("item_uuid"), tier.get("provider_item_uuid"))
            if key not in price_tier_map:
                price_tier_map[key] = []
            price_tier_map[key].append(tier)

        # Step 4: Build output structure with price tiers
        pricing_groups = []

        for group_key, group_data in grouped_items.items():
            provider_id = group_key

            # Prepare item details with guardrail, batch info, and price tiers
            items_info = []
            for item in group_data["items"]:
                item_qty = item.get("qty", 0)
                item_uuid = item.get("item_uuid")
                provider_item_uuid = item.get("provider_item_uuid")
                item_subtotal = item.get("subtotal", 0)

                # Get price tiers from the batch-loaded results
                tier_key = (item_uuid, provider_item_uuid)
                price_tiers = price_tier_map.get(tier_key, [])

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

        return {
            "request_uuid": request_uuid,
            "groups": pricing_groups,
        }

    def _group_provider_items_from_request(
        self, request_items: list, email: str
    ) -> Dict[str, Dict]:
        """
        Extract provider_items from request items and group by provider_corp_external_id.

        This method groups items and calculates subtotals based on base pricing.
        Price tiers are loaded separately via batch optimization in calculate_quote_pricing.

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
            email: Customer email (for potential future use in pricing lookups)

        Returns:
            Dictionary with provider_id as keys and aggregated data:
            {
                "PROV-001": {
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

                    # Use base_price_per_uom for subtotal calculation
                    # Price tiers will be loaded separately via batch optimization
                    price_per_uom = base_price_per_uom

                    # Ensure price_per_uom is not None before calculation
                    if price_per_uom is None or price_per_uom <= 0:
                        self.logger.warning(
                            f"Invalid price_per_uom for provider item {provider_item_uuid}, using 0"
                        )
                        price_per_uom = 0

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

                    # Group by provider_corp_external_id only
                    # Segment lookup is handled by email in the batch-optimized queries
                    group_key = provider_id

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
