#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

__author__ = "bibow"

from typing import Any, Dict

import humps

# Import centralized error handling utilities
from .error_handler import handle_errors, propagate_error_if_present

# Import status management
from .request_processor import RequestProcessor


class ItemProcessor(RequestProcessor):
    # ==================== Item Management Tools ====================

    # * MCP Function.
    @handle_errors(operation_name="search items")
    def search_items(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search items catalog.
        Maps to GraphQL: itemList query
        """
        variables = {
            "pageNumber": arguments.get("page_number", 1),
            "limit": arguments.get("limit", 50),
            "itemType": arguments.get("item_type"),
            "itemName": arguments.get("item_name"),
            "uoms": arguments.get("uoms"),
        }

        variables = {k: v for k, v in variables.items() if v is not None and v != ""}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "itemList",
            "Query",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        return humps.decamelize(result["itemList"])

    # * MCP Function.
    @handle_errors(operation_name="get item")
    def get_item(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get item details.
        Maps to GraphQL: item query
        """
        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "item",
            "Query",
            {"itemUuid": arguments["item_uuid"]},
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        return humps.decamelize(result["item"])

    # * MCP Function.
    @handle_errors(operation_name="get provider items")
    def get_provider_items(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search provider inventory with batch information merged.
        Maps to GraphQL: providerItemList query

        For each provider item, fetches and merges batch information including:
        - batches: Array of batch details with slow_move_item flags and guardrail pricing
        - Each batch includes: batch_no, expired_at, produced_at, slow_move_item, guardrail_price_per_uom

        Optional batch filters (applied when fetching batches):
        - expired_at_gt: Filter batches expiring after this date
        - slow_move_item: Filter for slow-moving inventory (default: False)
        - in_stock: Filter for in-stock batches (default: True)

        Note: If expired_at_gt not provided, defaults to batches expiring 90+ days from now.
        """
        variables = {
            "pageNumber": arguments.get("page_number", 1),
            "limit": arguments.get("limit", 50),
            "itemUuid": arguments["item_uuid"],
        }

        variables = {k: v for k, v in variables.items() if v is not None and v != ""}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "providerItemList",
            "Query",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        provider_items_result = humps.decamelize(result["providerItemList"])
        provider_item_list = provider_items_result.get("provider_item_list", [])

        # Extract batch filter parameters from arguments (optional)
        batch_expired_at_gt = arguments.get("expired_at_gt")
        batch_slow_move_item = arguments.get("slow_move_item", False)
        batch_in_stock = arguments.get("in_stock", True)

        # Merge batch information into each provider item
        for provider_item in provider_item_list:
            provider_item_uuid = provider_item.get("provider_item_uuid")

            if provider_item_uuid:
                # Fetch batches for this provider item using the batch filter parameters
                batch_arguments = {
                    "provider_item_uuid": provider_item_uuid,
                    "expired_at_gt": batch_expired_at_gt,
                    "slow_move_item": batch_slow_move_item,
                    "in_stock": batch_in_stock,
                    "limit": 100,  # Get all batches for this item
                }

                batches_result = self._get_provider_item_batches(**batch_arguments)

                # Check if batch fetch was successful
                if not propagate_error_if_present(batches_result):
                    batch_list = batches_result.get("provider_item_batch_list", [])
                    provider_item["batches"] = batch_list
                else:
                    # If error fetching batches, set empty array
                    provider_item["batches"] = []
            else:
                provider_item["batches"] = []

        return provider_items_result

    # * Private helper method (not exposed as MCP tool)
    @handle_errors(operation_name="get provider item batches")
    def _get_provider_item_batches(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get batch information for provider items.
        Maps to GraphQL: providerItemBatchList query

        Response includes:
        - slow_move_item: Boolean flag indicating slow-moving inventory
        - guardrail_price_per_uom: Minimum acceptable price for profitability
        - Batch details: expired_at, produced_at, cost breakdown

        Note: If expired_at_gt is not provided, defaults to filtering batches
        expiring 90+ days from now.
        """
        from datetime import datetime, timedelta, timezone

        # Set default expired_at_gt based on configured days if not provided
        expired_at_gt = arguments.get("expired_at_gt")

        if not expired_at_gt:
            # Get default expiration filter days from settings (default: 90 days / ~3 months)
            default_expiration_days = self.setting.get(
                "default_batch_expiration_filter_days", 90
            )
            expiration_date = datetime.now(timezone.utc) + timedelta(
                days=default_expiration_days
            )
            expired_at_gt = expiration_date.strftime("%Y-%m-%dT%H:%M:%S+0000")

        variables = {
            "pageNumber": arguments.get("page_number", 1),
            "limit": arguments.get("limit", 50),
            "providerItemUuid": arguments.get("provider_item_uuid"),
            "itemUuid": arguments.get("item_uuid"),
            "expiredAtGt": expired_at_gt,
            "slowMoveItem": arguments.get("slow_move_item", False),
            "inStock": arguments.get("in_stock", True),
        }

        variables = {k: v for k, v in variables.items() if v is not None and v != ""}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "providerItemBatchList",
            "Query",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        return humps.decamelize(result["providerItemBatchList"])
