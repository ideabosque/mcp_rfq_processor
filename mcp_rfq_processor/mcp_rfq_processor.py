#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

__author__ = "bibow"

import logging
import traceback
from typing import Any, Dict

import humps
import pendulum

# Import centralized error handling utilities
from .error_handler import (
    ErrorCode,
    ValidationError,
    build_error_response,
    handle_errors,
    propagate_error_if_present,
    validate_not_empty,
)
from .graphql_client import GraphQLClient
from .mcp_configuration import MCP_CONFIGURATION


class MCPRfqProcessor:
    def __init__(self, logger: logging.Logger, **setting: Dict[str, Any]):
        self.logger = logger
        self.setting = setting
        self.graphql_client = GraphQLClient(logger, **setting)

    @property
    def endpoint_id(self) -> str:
        return self.graphql_client.endpoint_id

    @endpoint_id.setter
    def endpoint_id(self, value: str):
        self.graphql_client.endpoint_id = value

    def _execute_graphql_query(
        self,
        function_name: str,
        operation_name: str,
        operation_type: str,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        return self.graphql_client.execute_query(
            function_name, operation_name, operation_type, variables
        )

    # ==================== Request Management Tools ====================

    # * MCP Function.
    @handle_errors(operation_name="submit RFQ request")
    def submit_rfq_request(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit new RFQ request.
        Maps to GraphQL: insertUpdateRequest mutation
        """
        self.logger.info(f"Submitting RFQ request: {arguments}")

        variables = {
            "email": arguments["contact_uuid"],
            "requestTitle": arguments["request_title"],
            "requestDescription": arguments.get("request_description", ""),
            "billingAddress": arguments.get("billing_address"),
            "shippingAddress": arguments.get("shipping_address"),
            "items": arguments.get("items"),
            "notes": arguments.get("notes"),
            "expiredAt": arguments.get("expired_at"),
            "status": arguments.get("status", "pending"),
            "updatedBy": "MCP",
        }

        # Remove None values
        variables = {k: v for k, v in variables.items() if v is not None}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "insertUpdateRequest",
            "Mutation",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        request = humps.decamelize(result["insertUpdateRequest"]["request"])

        return request

    # * MCP Function.
    @handle_errors(operation_name="update RFQ request")
    def update_rfq_request(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update existing RFQ request metadata.
        Maps to GraphQL: insertUpdateRequest mutation

        Use this when:
        - Modifying request details (title, description, addresses, notes, etc.)
        - Updating items list (note: changing items requires creating a new quote)
        - Updating deadline or status

        Note: You can also use add_item_to_rfq_request or remove_item_from_rfq_request
        for individual item modifications.
        """
        self.logger.info(f"Updating RFQ request: {arguments}")

        variables = {
            "requestUuid": arguments["request_uuid"],
            "email": arguments.get("contact_uuid"),
            "requestTitle": arguments.get("request_title"),
            "requestDescription": arguments.get("request_description"),
            "billingAddress": arguments.get("billing_address"),
            "shippingAddress": arguments.get("shipping_address"),
            "items": arguments.get("items"),
            "notes": arguments.get("notes"),
            "expiredAt": arguments.get("expired_at"),
            "status": arguments.get("status"),
            "updatedBy": "MCP",
        }

        # Remove None values to only update provided fields
        variables = {k: v for k, v in variables.items() if v is not None}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "insertUpdateRequest",
            "Mutation",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        request = humps.decamelize(result["insertUpdateRequest"]["request"])

        return request

    # * MCP Function.
    @handle_errors(operation_name="get RFQ request")
    def get_rfq_request(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieve RFQ request details.
        Maps to GraphQL: request query
        """
        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "request",
            "Query",
            {"requestUuid": arguments["request_uuid"]},
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        return humps.decamelize(result["request"])

    # * MCP Function.
    @handle_errors(operation_name="search RFQ requests")
    def search_rfq_requests(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search RFQ requests with filters.
        Maps to GraphQL: requestList query
        """
        variables = {
            "pageNumber": arguments.get("page_number", 1),
            "limit": arguments.get("limit", 20),
            "contactUuid": arguments.get("contact_uuid"),
            "statuses": arguments.get("statuses"),
            "fromExpiredAt": arguments.get("from_expired_at"),
            "toExpiredAt": arguments.get("to_expired_at"),
        }

        # Remove None values
        variables = {k: v for k, v in variables.items() if v is not None}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "requestList",
            "Query",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        return humps.decamelize(result["requestList"])

    # * MCP Function.
    @handle_errors(operation_name="add item to RFQ request")
    def add_item_to_rfq_request(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add an item to an existing RFQ request.
        This is a convenience method that fetches the current request,
        adds the new item to the items array, and updates the request.

        If the item already exists (matched by item_uuid), the quantity will be merged.

        Args:
            request_uuid: UUID of the request to update
            item: Item object to add (JSON object with item details)

        Returns:
            Updated request with the new item added or quantity merged
        """
        self.logger.info(f"Adding item to RFQ request: {arguments}")

        # Fetch current request
        current_request = self.get_rfq_request(request_uuid=arguments["request_uuid"])

        # Check if current_request has an error and propagate if present
        if error := propagate_error_if_present(current_request):
            return error

        # Get current items or initialize empty array
        current_items = current_request.get("items", [])
        if current_items is None:
            current_items = []

        # Get new item details
        new_item = arguments["item"]
        new_item_uuid = new_item.get("item_uuid") or new_item.get("itemUuid")

        # Check if item already exists and merge quantity if so
        item_found = False
        if new_item_uuid:
            for existing_item in current_items:
                existing_item_uuid = existing_item.get(
                    "item_uuid"
                ) or existing_item.get("itemUuid")
                if existing_item_uuid == new_item_uuid:
                    # Item exists - merge quantities
                    existing_qty = existing_item.get("qty", 0)
                    new_qty = new_item.get("qty", 0)
                    merged_qty = existing_qty + new_qty
                    existing_item["qty"] = merged_qty

                    item_found = True
                    self.logger.info(
                        f"Merged quantity for item {new_item_uuid}: {existing_qty} + {new_qty} = {merged_qty}"
                    )
                    break

        # If item doesn't exist, add it as new
        if not item_found:
            current_items.append(new_item)
            self.logger.info(f"Added new item to request")

        # Update request with new items array
        variables = {
            "requestUuid": arguments["request_uuid"],
            "items": current_items,
            "updatedBy": "MCP",
        }

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "insertUpdateRequest",
            "Mutation",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        request = humps.decamelize(result["insertUpdateRequest"]["request"])

        self.logger.info(
            f"Successfully added item to request {arguments['request_uuid']}"
        )
        return request

    # * MCP Function.
    @handle_errors(operation_name="remove item from RFQ request")
    def remove_item_from_rfq_request(
        self, **arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Remove an item from an existing RFQ request.
        This is a convenience method that fetches the current request,
        removes the specified item from the items array, and updates the request.

        Args:
            request_uuid: UUID of the request to update
            item_uuid: UUID of the item to remove
            OR
            item_name: Name of the item to remove

        Returns:
            Updated request with the item removed
        """
        self.logger.info(f"Removing item from RFQ request: {arguments}")

        # Fetch current request
        current_request = self.get_rfq_request(request_uuid=arguments["request_uuid"])

        # Check if current_request has an error and propagate if present
        if error := propagate_error_if_present(current_request):
            return error

        # Get current items and validate
        current_items = current_request.get("items", [])
        validate_not_empty(current_items, "items", "No items found in the request")

        # Remove item by UUID or name
        original_length = len(current_items)

        if "item_uuid" in arguments:
            item_uuid = arguments["item_uuid"]
            # Find and remove item by UUID (check both snake_case and camelCase)
            current_items = [
                item for item in current_items if item.get("item_uuid") != item_uuid
            ]
            if len(current_items) == original_length:
                raise ValidationError(
                    message=f"Item with UUID '{item_uuid}' not found in request",
                    error_code=ErrorCode.ITEM_NOT_FOUND,
                    details={
                        "item_uuid": item_uuid,
                        "request_uuid": arguments["request_uuid"],
                    },
                )
            self.logger.info(f"Removed item with UUID {item_uuid}")

        elif "item_name" in arguments:
            item_name = arguments["item_name"]
            # Find and remove item by name (check both snake_case and camelCase)
            current_items = [
                item for item in current_items if item.get("item_name") != item_name
            ]
            if len(current_items) == original_length:
                raise ValidationError(
                    message=f"Item with name '{item_name}' not found in request",
                    error_code=ErrorCode.ITEM_NOT_FOUND,
                    details={
                        "item_name": item_name,
                        "request_uuid": arguments["request_uuid"],
                    },
                )
            self.logger.info(f"Removed item with name {item_name}")

        else:
            raise ValidationError(
                message="Must provide either item_uuid or item_name to remove an item",
                error_code=ErrorCode.MISSING_REQUIRED_FIELD,
                details={"required_fields": ["item_uuid", "item_name"]},
            )

        # Update request with modified items array
        variables = {
            "requestUuid": arguments["request_uuid"],
            "items": current_items,
            "updatedBy": "MCP",
        }

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "insertUpdateRequest",
            "Mutation",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        request = humps.decamelize(result["insertUpdateRequest"]["request"])

        self.logger.info(
            f"Successfully removed item from request {arguments['request_uuid']}"
        )
        return request

    # * MCP Function.
    @handle_errors(operation_name="assign provider item to request item")
    def assign_provider_item_to_request_item(
        self, **arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Assign a provider item to a specific item in an RFQ request.
        This is a convenience method that fetches the current request,
        finds the specified item, and adds the provider item to the provider_items array.

        Args:
            request_uuid: UUID of the request to update
            item_uuid: UUID of the item in the request
            provider_item_uuid: UUID of the provider item to assign
            provider_corp_external_id: Provider corporation external ID
            batch_no: Optional batch number
            qty: Quantity for this provider item (optional, defaults to item qty)
            add_qty: If True, add to existing quantity; if False, replace quantity (default: False)

        Returns:
            Updated request with the provider item assigned

        Example item structure:
        {
          "item_uuid": "04540718329890843199",
          "item_name": "Steel Plate",
          "request_data": {},
          "qty": 100,
          "provider_items": [
            {
              "provider_corp_external_id": "PROV-12345",
              "provider_item_uuid": "76109526415051866240",
              "batch_no": "BATCH-001",
              "qty": 100
            }
          ]
        }
        """
        self.logger.info(f"Assigning provider item to request item: {arguments}")

        # Validate required fields
        validate_not_empty(
            arguments.get("request_uuid"), "request_uuid", "Request UUID is required"
        )
        validate_not_empty(
            arguments.get("item_uuid"), "item_uuid", "Item UUID is required"
        )
        validate_not_empty(
            arguments.get("provider_item_uuid"),
            "provider_item_uuid",
            "Provider item UUID is required",
        )
        validate_not_empty(
            arguments.get("provider_corp_external_id"),
            "provider_corp_external_id",
            "Provider corporation external ID is required",
        )

        # Fetch current request
        current_request = self.get_rfq_request(request_uuid=arguments["request_uuid"])

        # Check if current_request has an error and propagate if present
        if error := propagate_error_if_present(current_request):
            return error

        # Get current items and validate
        current_items = current_request.get("items", [])
        validate_not_empty(current_items, "items", "No items found in the request")

        # Find the item and add to provider_items array
        item_found = False
        item_uuid = arguments["item_uuid"]
        provider_item_uuid = arguments["provider_item_uuid"]
        provider_corp_external_id = arguments["provider_corp_external_id"]
        batch_no = arguments.get("batch_no")
        provider_qty = arguments.get("qty")
        add_qty = arguments.get("add_qty", False)  # Default to replace behavior

        for item in current_items:
            if item.get("item_uuid") == item_uuid:
                item_found = True

                # Initialize provider_items array if it doesn't exist
                if "provider_items" not in item or item["provider_items"] is None:
                    item["provider_items"] = []

                # Check if this provider_item already exists
                existing_provider_item = None
                for pi in item["provider_items"]:
                    if pi.get("provider_item_uuid") == provider_item_uuid:
                        # Match by batch_no (including None)
                        if pi.get("batch_no") == batch_no:
                            existing_provider_item = pi
                            break

                if existing_provider_item:
                    if provider_qty is not None:
                        if add_qty:
                            # Add to existing quantity
                            existing_provider_item["qty"] = (
                                existing_provider_item.get("qty", 0) + provider_qty
                            )
                            self.logger.info(
                                f"Added {provider_qty} to existing provider item {provider_item_uuid} for item {item_uuid}, new qty: {existing_provider_item['qty']}"
                            )
                        else:
                            # Replace quantity
                            existing_provider_item["qty"] = provider_qty
                            self.logger.info(
                                f"Replaced quantity for existing provider item {provider_item_uuid} for item {item_uuid}, new qty: {provider_qty}"
                            )
                else:
                    # Add new provider item
                    new_provider_item = {
                        "provider_item_uuid": provider_item_uuid,
                        "provider_corp_external_id": provider_corp_external_id,
                    }
                    if batch_no is not None:
                        new_provider_item["batch_no"] = batch_no
                    if provider_qty is not None:
                        new_provider_item["qty"] = provider_qty
                    else:
                        # Default to item qty if not specified
                        new_provider_item["qty"] = item.get("qty", 0)

                    item["provider_items"].append(new_provider_item)
                    self.logger.info(
                        f"Added provider item {provider_item_uuid} to item {item_uuid}"
                    )

                break

        if not item_found:
            raise ValidationError(
                message=f"Item with UUID '{item_uuid}' not found in request",
                error_code=ErrorCode.ITEM_NOT_FOUND,
                details={
                    "item_uuid": item_uuid,
                    "request_uuid": arguments["request_uuid"],
                },
            )

        # Update request with modified items array
        variables = {
            "requestUuid": arguments["request_uuid"],
            "items": current_items,
            "updatedBy": "MCP",
        }

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "insertUpdateRequest",
            "Mutation",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        request = humps.decamelize(result["insertUpdateRequest"]["request"])

        self.logger.info(
            f"Successfully assigned provider item to item in request {arguments['request_uuid']}"
        )
        return request

    # * MCP Function.
    @handle_errors(operation_name="remove provider item from request item")
    def remove_provider_item_from_request_item(
        self, **arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Remove a provider item assignment from a specific item in an RFQ request.
        This is a convenience method that fetches the current request,
        finds the specified item, and removes the provider item from the provider_items array.

        Args:
            request_uuid: UUID of the request to update
            item_uuid: UUID of the item in the request
            provider_item_uuid: UUID of the provider item to remove (optional, removes all if not specified)
            batch_no: Optional batch number to match (if provider_item_uuid is specified)

        Returns:
            Updated request with the provider item assignment removed
        """
        self.logger.info(f"Removing provider item from request item: {arguments}")

        # Validate required fields
        validate_not_empty(
            arguments.get("request_uuid"), "request_uuid", "Request UUID is required"
        )
        validate_not_empty(
            arguments.get("item_uuid"), "item_uuid", "Item UUID is required"
        )

        # Fetch current request
        current_request = self.get_rfq_request(request_uuid=arguments["request_uuid"])

        # Check if current_request has an error and propagate if present
        if error := propagate_error_if_present(current_request):
            return error

        # Get current items and validate
        current_items = current_request.get("items", [])
        validate_not_empty(current_items, "items", "No items found in the request")

        # Find the item and remove from provider_items array
        item_found = False
        item_uuid = arguments["item_uuid"]
        provider_item_uuid = arguments.get("provider_item_uuid")
        batch_no = arguments.get("batch_no")

        for item in current_items:
            if item.get("item_uuid") == item_uuid:
                item_found = True

                if "provider_items" not in item or item["provider_items"] is None:
                    self.logger.info(f"Item {item_uuid} has no provider items")
                    break

                if provider_item_uuid is None:
                    # Remove all provider items
                    item["provider_items"] = []
                    self.logger.info(
                        f"Removed all provider items from item {item_uuid}"
                    )
                else:
                    # Remove specific provider item(s)
                    original_length = len(item["provider_items"])

                    if batch_no is None:
                        # Remove all instances of this provider_item_uuid regardless of batch_no
                        item["provider_items"] = [
                            pi
                            for pi in item["provider_items"]
                            if pi.get("provider_item_uuid") != provider_item_uuid
                        ]
                        self.logger.info(
                            f"Removed all instances of provider item {provider_item_uuid} from item {item_uuid}"
                        )
                    else:
                        # Remove only the specific provider_item_uuid with matching batch_no
                        item["provider_items"] = [
                            pi
                            for pi in item["provider_items"]
                            if not (
                                pi.get("provider_item_uuid") == provider_item_uuid
                                and pi.get("batch_no") == batch_no
                            )
                        ]
                        self.logger.info(
                            f"Removed provider item {provider_item_uuid} with batch_no {batch_no} from item {item_uuid}"
                        )

                    if len(item["provider_items"]) == original_length:
                        raise ValidationError(
                            message=f"Provider item with UUID '{provider_item_uuid}'{' and batch_no ' + batch_no if batch_no else ''} not found in item",
                            error_code=ErrorCode.ITEM_NOT_FOUND,
                            details={
                                "provider_item_uuid": provider_item_uuid,
                                "batch_no": batch_no,
                                "item_uuid": item_uuid,
                                "request_uuid": arguments["request_uuid"],
                            },
                        )

                break

        if not item_found:
            raise ValidationError(
                message=f"Item with UUID '{item_uuid}' not found in request",
                error_code=ErrorCode.ITEM_NOT_FOUND,
                details={
                    "item_uuid": item_uuid,
                    "request_uuid": arguments["request_uuid"],
                },
            )

        # Update request with modified items array
        variables = {
            "requestUuid": arguments["request_uuid"],
            "items": current_items,
            "updatedBy": "MCP",
        }

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "insertUpdateRequest",
            "Mutation",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        request = humps.decamelize(result["insertUpdateRequest"]["request"])

        self.logger.info(
            f"Successfully removed provider item from item in request {arguments['request_uuid']}"
        )
        return request

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

        variables = {k: v for k, v in variables.items() if v is not None}

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
        Search provider inventory.
        Maps to GraphQL: providerItemList query
        """
        variables = {
            "pageNumber": arguments.get("page_number", 1),
            "limit": arguments.get("limit", 50),
            "itemUuid": arguments.get("item_uuid"),
            "providerCorpExternalId": arguments.get("provider_corp_external_id"),
            "minBasePricePerUom": arguments.get("min_base_price_per_uom"),
            "maxBasePricePerUom": arguments.get("max_base_price_per_uom"),
        }

        variables = {k: v for k, v in variables.items() if v is not None}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "providerItemList",
            "Query",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        return humps.decamelize(result["providerItemList"])

    # * MCP Function.
    @handle_errors(operation_name="get provider item batches")
    def get_provider_item_batches(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get batch information for provider items.
        Maps to GraphQL: providerItemBatchList query

        Response includes:
        - slow_move_item: Boolean flag indicating slow-moving inventory
        - guardrail_price_per_uom: Minimum acceptable price for profitability
        - Batch details: expired_at, produced_at, cost breakdown

        Note: If neither expired_at_gt nor expired_at_lt is provided, defaults to
        filtering batches expiring 3+ months from now (expired_at_gt = current_time + 3 months)
        """
        from datetime import datetime, timedelta, timezone

        # Set default expired_at_gt based on configured days if no expiration filters provided
        expired_at_gt = arguments.get("expired_at_gt")
        expired_at_lt = arguments.get("expired_at_lt")

        if not expired_at_gt and not expired_at_lt:
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
            "expiredAtLt": expired_at_lt,
            "slowMoveItem": arguments.get("slow_move_item", False),
            "inStock": arguments.get("in_stock", True),
        }

        variables = {k: v for k, v in variables.items() if v is not None}

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

    # ==================== Quote Management Tools ====================

    # * MCP Function.
    @handle_errors(operation_name="create quote")
    def create_quote(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create new quote for RFQ request based on request items.
        Maps to GraphQL: insertUpdateQuote mutation

        This method automatically creates quote items from the request's items.
        For each request item with provider_items assigned, a corresponding quote item is created.

        Note:
        - 'rounds' (negotiation rounds) is auto-calculated by backend based on existing quotes from the same provider
        - shipping_method and shipping_amount cannot be set during creation, use update_quote instead
        - Quote items are automatically created from request items with provider_items
        - After creation, quote items can be managed using update_quote_item
        """
        self.logger.info(f"Creating quote: {arguments}")

        # First, create the quote
        variables = {
            "requestUuid": arguments["request_uuid"],
            "providerCorpExternalId": arguments["provider_corp_external_id"],
            "salesRepEmail": arguments.get("sales_rep_email"),
            "status": arguments.get("status", "draft"),
            "notes": arguments.get("notes", ""),
            "updatedBy": "MCP",
        }

        # Remove None values to only send provided fields
        # Note: 'rounds' is auto-calculated, shipping_method/shipping_amount not allowed on creation
        variables = {k: v for k, v in variables.items() if v is not None}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "insertUpdateQuote",
            "Mutation",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        quote = humps.decamelize(result["insertUpdateQuote"]["quote"])

        # Now fetch the request to get items with provider_items
        request = self.get_rfq_request(request_uuid=arguments["request_uuid"])

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(request):
            return error

        # Create quote items from request items that have provider_items assigned
        request_items = request.get("items", [])
        provider_corp_external_id = arguments["provider_corp_external_id"]

        if request_items:
            self.logger.info(
                f"Creating quote items from {len(request_items)} request items for provider {provider_corp_external_id}"
            )

            for req_item in request_items:
                provider_items = req_item.get("provider_items", [])

                if provider_items:
                    # Filter provider_items to only include those matching the quote's provider
                    matching_provider_items = [
                        pi
                        for pi in provider_items
                        if pi.get("provider_corp_external_id")
                        == provider_corp_external_id
                    ]

                    if not matching_provider_items:
                        self.logger.info(
                            f"Skipping request item {req_item.get('item_uuid')} - no provider_items for provider {provider_corp_external_id}"
                        )
                        continue

                    # Create a quote item for each matching provider_item
                    for provider_item in matching_provider_items:
                        quote_item_args = {
                            "quote_uuid": quote["quote_uuid"],
                            "provider_item_uuid": provider_item.get(
                                "provider_item_uuid"
                            ),
                            "item_uuid": req_item.get("item_uuid"),
                            "qty": provider_item.get("qty", req_item.get("qty", 0)),
                            "segment_uuid": arguments["segment_uuid"],
                            "batch_no": provider_item.get("batch_no"),
                            "request_data": req_item.get("request_data"),
                            "request_uuid": arguments["request_uuid"],
                        }

                        # Use the private method to add quote item
                        quote_item_result = self._add_quote_item(**quote_item_args)

                        # Check if there was an error creating the quote item
                        if error := propagate_error_if_present(quote_item_result):
                            self.logger.error(
                                f"Failed to create quote item for provider_item {provider_item.get('provider_item_uuid')}: {error}"
                            )
                            # Continue creating other quote items even if one fails
                            continue

                        self.logger.info(
                            f"Created quote item for provider_item {provider_item.get('provider_item_uuid')}"
                        )
                else:
                    self.logger.info(
                        f"Skipping request item {req_item.get('item_uuid')} - no provider_items assigned"
                    )

        # Return the quote (quote items were already created)
        # Note: The quote object may not include the newly created quote_items
        # If you need the full quote with items, call get_quote separately
        return quote

    # * MCP Function.
    @handle_errors(operation_name="update quote")
    def update_quote(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update quote metadata (shipping, status, notes).
        Maps to GraphQL: insertUpdateQuote mutation

        Can update:
        - shipping_method, shipping_amount
        - status
        - notes

        Note: 'rounds' (negotiation rounds) are auto-calculated by the backend based on existing quotes from the same provider.
        Cannot modify quote items - use update_quote_item, add_quote_item, or remove_quote_item instead
        """
        self.logger.info(f"Updating quote: {arguments}")

        variables = {
            "requestUuid": arguments["request_uuid"],
            "quoteUuid": arguments["quote_uuid"],
            "shippingMethod": arguments.get("shipping_method"),
            "shippingAmount": arguments.get("shipping_amount"),
            "status": arguments.get("status"),
            "notes": arguments.get("notes"),
            "updatedBy": "MCP",
        }

        # Remove None values to only update provided fields
        # Note: 'rounds' is auto-calculated by backend, not sent in updates
        variables = {k: v for k, v in variables.items() if v is not None}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "insertUpdateQuote",
            "Mutation",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        quote = humps.decamelize(result["insertUpdateQuote"]["quote"])

        return quote

    # * MCP Function.
    @handle_errors(operation_name="update quote item")
    def update_quote_item(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a specific quote item (quantity, discount, etc.).
        Maps to GraphQL: insertUpdateQuoteItem mutation

        Can update quote item properties including discount.
        To add/remove items, use add_quote_item or remove_quote_item.

        Response includes:
        - slow_move_item: Boolean flag indicating if item is from slow-moving inventory
        - guardrail_price_per_uom: Minimum acceptable price for profitability
        """
        self.logger.info(f"Updating quote item: {arguments}")

        variables = {
            "quoteUuid": arguments["quote_uuid"],
            "quoteItemUuid": arguments.get("quote_item_uuid"),
            "providerItemUuid": arguments.get("provider_item_uuid"),
            "itemUuid": arguments.get("item_uuid"),
            "segmentUuid": arguments.get("segment_uuid"),
            "batchNo": arguments.get("batch_no"),
            "requestUuid": arguments.get("request_uuid"),
            "requestData": arguments.get("request_data"),
            "qty": arguments.get("qty"),
            "subtotalDiscount": arguments.get("discount_amount", 0.0),
            "updatedBy": "MCP",
        }

        # Remove None values
        variables = {k: v for k, v in variables.items() if v is not None}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "insertUpdateQuoteItem",
            "Mutation",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        quote_item = humps.decamelize(result["insertUpdateQuoteItem"]["quoteItem"])

        return quote_item

    # * Private helper method (not exposed as MCP tool)
    @handle_errors(operation_name="add quote item")
    def _add_quote_item(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a quote item to an existing quote.
        This is a convenience method that adds a new item using insertUpdateQuoteItem mutation.

        Args:
            quote_uuid: UUID of the quote
            provider_item_uuid: UUID of the provider item
            item_uuid: UUID of the item
            qty: Quantity
            segment_uuid: UUID of the segment (optional)
            batch_no: Batch number (optional, enables slow_move_item tracking)
            request_data: Request data (optional)
            discount_amount: Discount amount (optional)

        Returns:
            Created quote item with:
            - slow_move_item: Boolean flag (true if batch has slow-moving inventory)
            - guardrail_price_per_uom: Minimum acceptable price
        """
        self.logger.info(f"Adding quote item: {arguments}")

        variables = {
            "quoteUuid": arguments["quote_uuid"],
            "providerItemUuid": arguments["provider_item_uuid"],
            "itemUuid": arguments["item_uuid"],
            "qty": arguments["qty"],
            "segmentUuid": arguments.get("segment_uuid") or "default",
            "batchNo": arguments.get("batch_no"),
            "requestUuid": arguments.get("request_uuid"),
            "requestData": arguments.get("request_data"),
            "subtotalDiscount": arguments.get("discount_amount", 0.0),
            "updatedBy": "MCP",
        }

        # Remove None values (but keep "default" for segment_uuid)
        variables = {k: v for k, v in variables.items() if v is not None}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "insertUpdateQuoteItem",
            "Mutation",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        quote_item = humps.decamelize(result["insertUpdateQuoteItem"]["quoteItem"])

        self.logger.info(
            f"Successfully added quote item to quote {arguments['quote_uuid']}"
        )
        return quote_item

    # * Private helper method (not exposed as MCP tool)
    @handle_errors(operation_name="remove quote item")
    def _remove_quote_item(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove a quote item from an existing quote.
        Maps to GraphQL: deleteQuoteItem mutation

        Args:
            quote_uuid: UUID of the quote
            quote_item_uuid: UUID of the quote item to remove

        Returns:
            Success message with deleted quote item UUID
        """
        self.logger.info(f"Removing quote item: {arguments}")

        variables = {
            "quoteUuid": arguments["quote_uuid"],
            "quoteItemUuid": arguments["quote_item_uuid"],
            "updatedBy": "MCP",
        }

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "deleteQuoteItem",
            "Mutation",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        response = humps.decamelize(result.get("deleteQuoteItem", {}))

        self.logger.info(
            f"Successfully removed quote item {arguments['quote_item_uuid']} from quote {arguments['quote_uuid']}"
        )
        return response

    # * MCP Function.
    @handle_errors(operation_name="get quote")
    def get_quote(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieve quote details.
        Maps to GraphQL: quote query

        Response includes:
        - quote_items: Array of quote items with slow_move_item flags and guardrail pricing
        - rounds: Negotiation round number (auto-calculated based on provider's quote history for this request)
        """
        variables = {
            "quoteUuid": arguments["quote_uuid"],
        }

        # Add requestUuid if provided (may be required by GraphQL schema)
        if "request_uuid" in arguments:
            variables["requestUuid"] = arguments["request_uuid"]

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "quote",
            "Query",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        return humps.decamelize(result["quote"])

    # * MCP Function.
    @handle_errors(operation_name="search quotes")
    def search_quotes(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search quotes with filters.
        Maps to GraphQL: quoteList query
        """
        variables = {
            "pageNumber": arguments.get("page_number", 1),
            "limit": arguments.get("limit", 20),
            "requestUuid": arguments.get("request_uuid"),
            "providerCorpExternalId": arguments.get("provider_corp_external_id"),
            "statuses": arguments.get("statuses"),
            "fromCreatedAt": arguments.get("from_created_at"),
            "toCreatedAt": arguments.get("to_created_at"),
        }

        variables = {k: v for k, v in variables.items() if v is not None}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "quoteList",
            "Query",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        return humps.decamelize(result["quoteList"])

    # ==================== Pricing Tools ====================

    # * MCP Function.
    @handle_errors(operation_name="get item price tiers")
    def get_item_price_tiers(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get tiered pricing for items.
        Maps to GraphQL: itemPriceTierList query

        Supports quantity-based filtering to find applicable price tiers:
        - Use max_quantity_greater_then and min_quantity_less_then to find tiers for a specific quantity
        - Example: For qty=100, use max_quantity_greater_then=100, min_quantity_less_then=100
          to find tiers where quantity_greater_then <= 100 < quantity_less_then
        """
        variables = {
            "pageNumber": arguments.get("page_number", 1),
            "limit": arguments.get("limit", 50),
            "itemUuid": arguments.get("item_uuid"),
            "providerItemUuid": arguments.get("provider_item_uuid"),
            "segmentUuid": arguments.get("segment_uuid"),
            "minQuantityGreaterThen": arguments.get("min_quantity_greater_then"),
            "maxQuantityGreaterThen": arguments.get("max_quantity_greater_then"),
            "minQuantityLessThen": arguments.get("min_quantity_less_then"),
            "maxQuantityLessThen": arguments.get("max_quantity_less_then"),
            "minPrice": arguments.get("min_price"),
            "maxPrice": arguments.get("max_price"),
            "status": "active",
        }

        variables = {k: v for k, v in variables.items() if v is not None}

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
        Get discount rules.
        Maps to GraphQL: discountRuleList query

        Returns discount rules with filtering options for subtotal thresholds and discount percentages.

        Supports subtotal-based filtering to find applicable discount rules:
        - Use max_subtotal_greater_than and min_subtotal_less_than to find rules for a specific subtotal
        - Example: For subtotal=5000, use max_subtotal_greater_than=5000, min_subtotal_less_than=5000
          to find rules where subtotal_greater_than <= 5000 < subtotal_less_than
        """
        variables = {
            "pageNumber": arguments.get("page_number", 1),
            "limit": arguments.get("limit", 50),
            "itemUuid": arguments.get("item_uuid"),
            "providerItemUuid": arguments.get("provider_item_uuid"),
            "segmentUuid": arguments.get("segment_uuid"),
            "maxSubtotalGreaterThan": arguments.get("max_subtotal_greater_than"),
            "minSubtotalGreaterThan": arguments.get("min_subtotal_greater_than"),
            "maxSubtotalLessThan": arguments.get("max_subtotal_less_than"),
            "minSubtotalLessThan": arguments.get("min_subtotal_less_than"),
            "maxDiscountPercentage": arguments.get("max_discount_percentage"),
            "minDiscountPercentage": arguments.get("min_discount_percentage"),
            "status": "active",
        }

        variables = {k: v for k, v in variables.items() if v is not None}

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
        - Item-level details with guardrail pricing, batch info, and price tiers
        - Applicable discount rules for LLM to discuss with end user

        Returns pricing structure with discount options for decision-making.
        Does NOT apply discounts - only provides information.

        Args:
            request_uuid: UUID of the RFQ request
            segment_uuid: Customer segment UUID for pricing rules

        Returns:
            Grouped pricing structure with subtotals, price tiers, and discount rules
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

            # Prepare item details with guardrail, batch info, and price tiers
            items_info = []
            for item in group_data["items"]:
                item_qty = item.get("qty", 0)
                item_uuid = item.get("item_uuid")
                provider_item_uuid = item.get("provider_item_uuid")

                # Get price tiers applicable to this item's quantity
                # Get tiers where quantity_greater_then <= item_qty
                price_tiers_result = self.get_item_price_tiers(
                    item_uuid=item_uuid,
                    provider_item_uuid=provider_item_uuid,
                    segment_uuid=seg_uuid,
                    max_quantity_greater_then=item_qty,  # Tiers where qty_greater_then <= item_qty
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

                        # Remove provider_item and provider_item_batches
                        tier.pop("provider_item", None)
                        tier.pop("provider_item_batches", None)
                        price_tiers.append(tier)

                item_data = {
                    "provider_item_uuid": provider_item_uuid,
                    "item_uuid": item_uuid,
                    "batch_no": item.get("batch_no"),
                    "qty": item_qty,
                    "price_per_uom": item.get("price_per_uom"),
                    "guardrail_price_per_uom": item.get("guardrail_price_per_uom"),
                    "subtotal": item.get("subtotal"),
                    "slow_move_item": item.get("slow_move_item", False),
                    "expired_at": item.get("expired_at"),
                    "price_tiers": price_tiers,
                }
                items_info.append(item_data)

            # Get applicable discount rules for this group's subtotal
            group_subtotal = group_data["group_subtotal"]
            discount_rules_result = self.get_discount_rules(
                segment_uuid=seg_uuid,
                max_subtotal_greater_than=group_subtotal,
                min_subtotal_less_than=group_subtotal,
                limit=50,
            )

            discount_rules = []
            if not propagate_error_if_present(discount_rules_result):
                raw_discount_rules = discount_rules_result.get("discount_rule_list", [])
                # Remove provider_item field from each discount rule
                discount_rules = [
                    {k: v for k, v in rule.items() if k != "provider_item"}
                    for rule in raw_discount_rules
                ]

            group_info = {
                "provider_corp_external_id": provider_id,
                "subtotal": group_subtotal,
                "items": items_info,
                "discount_rules": discount_rules,
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

                    # Get batch-specific data and guardrail pricing
                    slow_move_item = False
                    expired_at = None
                    batch_guardrail = None

                    if batch_no:
                        batch_result = self.get_provider_item_batches(
                            provider_item_uuid=provider_item_uuid,
                            expired_at_gt="2000-01-01T00:00:00+0000",
                            limit=100,
                        )

                        if not propagate_error_if_present(batch_result):
                            batch_list = batch_result.get(
                                "provider_item_batch_list", []
                            )
                            for batch_data in batch_list:
                                if batch_data.get("batch_no") == batch_no:
                                    batch_guardrail = batch_data.get(
                                        "guardrail_price_per_uom"
                                    )
                                    slow_move_item = batch_data.get(
                                        "slow_move_item", False
                                    )
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
                        max_quantity_greater_then=qty,
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

    # ==================== Installment Tools ====================

    # * MCP Function.
    @handle_errors(operation_name="create installment")
    def create_installment(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create payment installment.
        Maps to GraphQL: insertUpdateInstallment mutation

        Automatically fetches quote's final_total_quote_amount if amount not provided.
        Sets due_date to current time if not provided.
        installment_ratio is automatically calculated by the backend.
        """
        from datetime import datetime, timezone

        self.logger.info(f"Creating installment: {arguments}")

        quote_uuid = arguments["quote_uuid"]
        request_uuid = arguments["request_uuid"]

        # Fetch quote to get final_total_quote_amount
        quote_result = self.get_quote(
            request_uuid=request_uuid,
            quote_uuid=quote_uuid,
        )

        if error := propagate_error_if_present(quote_result):
            return error

        # Get the quote amount
        final_total_quote_amount = quote_result.get("final_total_quote_amount")
        if final_total_quote_amount is None:
            return build_error_response(
                message=f"Quote {quote_uuid} does not have final_total_quote_amount set",
                error_code=ErrorCode.VALIDATION_FAILED,
            )

        # Get all existing installments for the quote (to calculate priority and total)
        all_installments_result = self.get_installments(
            quote_uuid=quote_uuid,
            limit=100,  # Get all installments
        )

        if error := propagate_error_if_present(all_installments_result):
            return error

        # Calculate total of pending/paid installments and find max priority across all
        existing_total = 0
        max_priority = -1  # Start with -1 so first installment gets priority 0
        all_installment_list = all_installments_result.get("installment_list", [])

        for inst in all_installment_list:
            # Only count pending/paid installments toward total
            inst_status = inst.get("status", "")
            if inst_status in ["pending", "paid"]:
                existing_total += inst.get("installment_amount", 0)

            # Track highest priority across ALL installments (including cancelled)
            priority = inst.get("priority", 0)
            if priority is not None and priority > max_priority:
                max_priority = priority

        # Set new installment priority to max + 1
        new_priority = max_priority + 1

        # Calculate remaining balance
        remaining_balance = final_total_quote_amount - existing_total

        # Validate that there's remaining balance to create installment
        if remaining_balance <= 0:
            return build_error_response(
                message=f"Cannot create installment: Quote amount ({final_total_quote_amount}) is already fully covered by existing installments ({existing_total}). "
                f"No remaining balance available.",
                error_code=ErrorCode.VALIDATION_FAILED,
                details={
                    "quote_amount": final_total_quote_amount,
                    "existing_installments_total": existing_total,
                    "remaining_balance": remaining_balance,
                },
            )

        # Determine installment amount
        requested_amount = arguments.get("installment_amount")
        if requested_amount is not None:
            # User provided amount - validate and cap at remaining balance
            if requested_amount <= 0:
                return build_error_response(
                    message=f"Cannot create installment: Requested amount ({requested_amount}) must be greater than 0.",
                    error_code=ErrorCode.VALIDATION_FAILED,
                )
            # Cap at remaining balance if requested amount exceeds it
            installment_amount = min(requested_amount, remaining_balance)
        else:
            # No amount provided - use full remaining balance
            installment_amount = remaining_balance

        # Validate final installment amount is meaningful (greater than 0.01)
        if installment_amount < 0.01:
            return build_error_response(
                message=f"Cannot create installment: Installment amount ({installment_amount}) is too small (must be at least 0.01). "
                f"Quote amount ({final_total_quote_amount}) is already covered by existing installments ({existing_total}).",
                error_code=ErrorCode.VALIDATION_FAILED,
                details={
                    "quote_amount": final_total_quote_amount,
                    "existing_installments_total": existing_total,
                    "remaining_balance": remaining_balance,
                    "installment_amount": installment_amount,
                },
            )

        # Set due_date to current time
        scheduled_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000")

        variables = {
            "quoteUuid": quote_uuid,
            "requestUuid": request_uuid,
            "priority": new_priority,
            "scheduledDate": scheduled_date,
            "installmentAmount": installment_amount,
            "status": arguments.get("status", "pending"),
            "updatedBy": "MCP",
        }

        # Add optional payment_method if provided
        if "payment_method" in arguments:
            variables["paymentMethod"] = arguments["payment_method"]

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "insertUpdateInstallment",
            "Mutation",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        installment = humps.decamelize(result["insertUpdateInstallment"]["installment"])

        return installment

    # * MCP Function.
    @handle_errors(operation_name="update installment")
    def update_installment(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update installment status and sales order number.
        Maps to GraphQL: insertUpdateInstallment mutation

        Used to:
        - Mark installment as paid when payment is received
        - Mark installment as cancelled if needed
        - Link installment to sales order number
        """
        self.logger.info(f"Updating installment: {arguments}")

        # Build variables - only include fields that are provided
        variables = {
            "quoteUuid": arguments["quote_uuid"],
            "installmentUuid": arguments["installment_uuid"],
            "updatedBy": "MCP",
        }

        # Add optional fields if provided
        if "status" in arguments:
            variables["status"] = arguments["status"]

        if "salesorder_no" in arguments:
            variables["salesorderNo"] = arguments["salesorder_no"]

        if "payment_method" in arguments:
            variables["paymentMethod"] = arguments["payment_method"]

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "insertUpdateInstallment",
            "Mutation",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        installment = humps.decamelize(result["insertUpdateInstallment"]["installment"])

        return installment

    # * MCP Function.
    @handle_errors(operation_name="create installments")
    def create_installments(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create multiple payment installments based on payment schedule.
        Maps to GraphQL: insertUpdateInstallment mutation (called multiple times)

        Calculates remaining balance and divides equally across installments.
        Scheduled dates are calculated based on interval_num, total_pay_period, and
        installment_scheduled_day setting (default: 15th of each month).
        Example: interval_num=12, total_pay_period=12 means 12 monthly payments over 1 year.
        """
        self.logger.info(f"Creating installments: {arguments}")

        quote_uuid = arguments["quote_uuid"]
        request_uuid = arguments["request_uuid"]
        interval_num = arguments["interval_num"]
        total_pay_period = arguments["total_pay_period"]

        # Validate interval_num
        if interval_num <= 0:
            return build_error_response(
                message=f"interval_num must be greater than 0, got: {interval_num}",
                error_code=ErrorCode.VALIDATION_FAILED,
            )

        # Validate total_pay_period
        if total_pay_period <= 0:
            return build_error_response(
                message=f"total_pay_period must be greater than 0, got: {total_pay_period}",
                error_code=ErrorCode.VALIDATION_FAILED,
            )

        # Fetch quote to get final_total_quote_amount
        quote_result = self.get_quote(
            request_uuid=request_uuid,
            quote_uuid=quote_uuid,
        )

        if error := propagate_error_if_present(quote_result):
            return error

        # Get the quote amount
        final_total_quote_amount = quote_result.get("final_total_quote_amount")
        if final_total_quote_amount is None:
            return build_error_response(
                message=f"Quote {quote_uuid} does not have final_total_quote_amount set",
                error_code=ErrorCode.VALIDATION_FAILED,
            )

        # Get all existing installments for the quote
        all_installments_result = self.get_installments(
            quote_uuid=quote_uuid,
            limit=100,
        )

        if error := propagate_error_if_present(all_installments_result):
            return error

        # Calculate total of pending/paid installments and find max priority
        existing_total = 0
        max_priority = -1
        all_installment_list = all_installments_result.get("installment_list", [])

        for inst in all_installment_list:
            inst_status = inst.get("status", "")
            if inst_status in ["pending", "paid"]:
                existing_total += inst.get("installment_amount", 0)

            priority = inst.get("priority", 0)
            if priority is not None and priority > max_priority:
                max_priority = priority

        # Calculate remaining balance
        remaining_balance = final_total_quote_amount - existing_total

        # Validate that there's remaining balance
        if remaining_balance <= 0:
            return build_error_response(
                message=f"Cannot create installments: Quote amount ({final_total_quote_amount}) is already fully covered by existing installments ({existing_total}).",
                error_code=ErrorCode.VALIDATION_FAILED,
                details={
                    "quote_amount": final_total_quote_amount,
                    "existing_installments_total": existing_total,
                    "remaining_balance": remaining_balance,
                },
            )

        # Calculate installment amount per installment
        installment_amount_per = remaining_balance / interval_num

        # Validate each installment amount is meaningful (greater than 0.01)
        if installment_amount_per < 0.01:
            return build_error_response(
                message=f"Cannot create installments: Each installment amount ({installment_amount_per}) is too small (must be at least 0.01). "
                f"Remaining balance ({remaining_balance}) divided by {interval_num} installments results in amounts too small to process.",
                error_code=ErrorCode.VALIDATION_FAILED,
                details={
                    "quote_amount": final_total_quote_amount,
                    "existing_installments_total": existing_total,
                    "remaining_balance": remaining_balance,
                    "interval_num": interval_num,
                    "installment_amount_per": installment_amount_per,
                },
            )

        # Calculate interval in months (total_pay_period / interval_num)
        months_per_interval = total_pay_period / interval_num

        # Get the configured day of month for installment scheduled dates (default: 15)
        installment_scheduled_day = self.setting.get("installment_scheduled_day", 15)

        # Create installments
        created_installments = []
        current_time = pendulum.now("UTC")
        total_allocated = 0.0

        for i in range(1, interval_num + 1):
            # Calculate scheduled date for this installment using pendulum
            # Add months_per_interval * i months to current time (starts from 1st interval)
            months_to_add = int(months_per_interval * i)

            # Start with current time and add months
            scheduled_datetime = current_time.add(months=months_to_add)

            # Set to the configured day of month (e.g., 15th)
            # Handle edge case where day doesn't exist in target month (e.g., Feb 30)
            try:
                scheduled_datetime = scheduled_datetime.set(
                    day=installment_scheduled_day
                )
            except ValueError:
                # If day doesn't exist (e.g., 31st in Feb), use last day of month
                scheduled_datetime = scheduled_datetime.end_of("month").start_of("day")

            # Format as ISO 8601 with UTC timezone
            scheduled_date = scheduled_datetime.format("YYYY-MM-DDTHH:mm:ssZ")

            # Set priority (i starts from 1, so i=1 gives max_priority+1, i=2 gives max_priority+2, etc.)
            new_priority = max_priority + i

            # For the last installment, use remaining balance to avoid rounding errors
            if i == interval_num:
                current_installment_amount = float(remaining_balance) - total_allocated
            else:
                current_installment_amount = float(installment_amount_per)
                total_allocated += float(installment_amount_per)

            # Create installment
            variables = {
                "quoteUuid": quote_uuid,
                "requestUuid": request_uuid,
                "priority": new_priority,
                "scheduledDate": scheduled_date,
                "installmentAmount": current_installment_amount,
                "status": "pending",
                "updatedBy": "MCP",
            }

            # Add optional payment_method if provided
            if "payment_method" in arguments:
                variables["paymentMethod"] = arguments["payment_method"]

            result = self._execute_graphql_query(
                "ai_rfq_graphql",
                "insertUpdateInstallment",
                "Mutation",
                variables,
            )

            # Check for error in response
            if error := propagate_error_if_present(result):
                # If one fails, return error with what was created so far
                return build_error_response(
                    message=f"Failed to create installment {i+1}/{interval_num}: {error.get('message', 'Unknown error')}",
                    error_code=ErrorCode.GRAPHQL_ERROR,
                    details={
                        "created_installments": created_installments,
                        "failed_at": i + 1,
                        "total_requested": interval_num,
                    },
                )

            installment = humps.decamelize(
                result["insertUpdateInstallment"]["installment"]
            )
            created_installments.append(installment)

        return {
            "installments": created_installments,
            "total_created": len(created_installments),
            "installment_amount_per": installment_amount_per,
            "total_installment_amount": remaining_balance,
        }

    # * MCP Function.
    @handle_errors(operation_name="get installments")
    def get_installments(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get installment schedule.
        Maps to GraphQL: installmentList query
        """
        variables = {
            "pageNumber": arguments.get("page_number", 1),
            "limit": arguments.get("limit", 50),
            "quoteUuid": arguments.get("quote_uuid"),
            "statuses": arguments.get("statuses"),
        }

        variables = {k: v for k, v in variables.items() if v is not None}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "installmentList",
            "Query",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        return humps.decamelize(result["installmentList"])

    # ==================== File Tools ====================

    # * MCP Function.
    @handle_errors(operation_name="upload RFQ file")
    def upload_rfq_file(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upload RFQ document.
        Maps to GraphQL: insertUpdateFile mutation
        """
        self.logger.info(f"Uploading RFQ file: {arguments}")

        variables = {
            "requestUuid": arguments["request_uuid"],
            "fileName": arguments["file_name"],
            "email": arguments.get("email"),
            "updatedBy": "MCP",
        }

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "insertUpdateFile",
            "Mutation",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        file_obj = humps.decamelize(result["insertUpdateFile"]["file"])

        return file_obj

    # * MCP Function.
    @handle_errors(operation_name="get RFQ files")
    def get_rfq_files(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get RFQ files.
        Maps to GraphQL: fileList query
        """
        variables = {
            "pageNumber": arguments.get("page_number", 1),
            "limit": arguments.get("limit", 50),
            "requestUuid": arguments.get("request_uuid"),
            "fileType": arguments.get("file_type"),
        }

        variables = {k: v for k, v in variables.items() if v is not None}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "fileList",
            "Query",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        return humps.decamelize(result["fileList"])

    # ==================== Segment Tools ====================

    # * MCP Function.
    @handle_errors(operation_name="get segment contacts")
    def get_segment_contacts(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        List segment contacts.
        Maps to GraphQL: segmentContactList query
        """
        variables = {
            "pageNumber": arguments.get("page_number", 1),
            "limit": arguments.get("limit", 50),
            "consumerCorpExternalId": arguments.get("consumer_corp_external_id"),
            "email": arguments.get("email"),
        }

        variables = {k: v for k, v in variables.items() if v is not None}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "segmentContactList",
            "Query",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        return humps.decamelize(result["segmentContactList"])
