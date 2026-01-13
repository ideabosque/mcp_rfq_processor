#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

__author__ = "bibow"

from typing import Any, Dict

import humps

# Import centralized error handling utilities
from .error_handler import handle_errors, propagate_error_if_present
from .item_processor import ItemProcessor

# Import status management
from .status_manager import (
    QuoteOperationGuard,
    QuoteStatus,
    QuoteStatusTransitions,
    RequestOperationGuard,
)


class QuoteProcessor(ItemProcessor):
    # ==================== Quote Management Tools ====================

    # * Private helper method (not exposed as MCP tool)
    @handle_errors(operation_name="create quote")
    def _create_quote(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create new quote for RFQ request based on request items.
        Maps to GraphQL: insertUpdateQuote mutation

        This method automatically creates quote items from the request's items.
        For each request item with provider_items assigned, a corresponding quote item is created.

        Note:
        - Default status: 'initial' - Quote has been created but not yet being worked on
        - 'rounds' (negotiation rounds) is auto-calculated by backend based on existing quotes from the same provider
        - shipping_method and shipping_amount cannot be set during creation, use update_quote instead
        - Quote items are automatically created from request items with provider_items
        - After creation, quote items can be managed using update_quote_item
        - Request must be in 'confirmed' status to create quotes
        """
        self.logger.info(f"Creating quote: {arguments}")

        # Validate request status allows quote creation
        request = self.get_rfq_request(request_uuid=arguments["request_uuid"])
        if error := propagate_error_if_present(request):
            return error

        request_status = request.get("status", "")
        RequestOperationGuard.validate_can_create_quote(request_status)

        # First, create the quote
        variables = {
            "requestUuid": arguments["request_uuid"],
            "providerCorpExternalId": arguments["provider_corp_external_id"],
            "salesRepEmail": arguments.get("sales_rep_email"),
            "status": arguments.get("status", QuoteStatus.INITIAL),
            "notes": arguments.get("notes", ""),
            "updatedBy": "MCP",
        }

        # Remove None values to only send provided fields
        # Note: 'rounds' is auto-calculated, shipping_method/shipping_amount not allowed on creation
        variables = {k: v for k, v in variables.items() if v is not None and v != ""}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "insertUpdateQuote",
            "Mutation",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        quote = humps.decamelize(result["quote"])

        # We already have the request from validation above
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
        - shipping_method, shipping_amount (only in 'initial' or 'in_progress' status)
        - status (validated according to status flow)
        - notes

        Note: 'rounds' (negotiation rounds) are auto-calculated by the backend based on existing quotes from the same provider.
        Cannot modify quote items - use update_quote_item, add_quote_item, or remove_quote_item instead

        Status transitions are validated according to the quote status flow.
        Shipping/notes updates require quote to be in 'initial' or 'in_progress' status.
        """
        self.logger.info(f"Updating quote: {arguments}")

        # Get current quote to check current status
        current_quote = self.get_quote(
            request_uuid=arguments["request_uuid"],
            quote_uuid=arguments["quote_uuid"],
        )
        if error := propagate_error_if_present(current_quote):
            return error

        current_status = current_quote.get("status", "")

        # Validate status transition if status is being updated
        if "status" in arguments:
            new_status = arguments["status"]
            # Validate the transition
            QuoteStatusTransitions.validate_transition(current_status, new_status)

        # Validate that quote status allows metadata modifications (shipping, notes)
        # Only apply this validation if we're NOT doing a status change
        # (Status changes can include notes to document the reason for the change)
        is_updating_metadata = any(
            key in arguments for key in ["shipping_method", "shipping_amount", "notes"]
        )
        if is_updating_metadata and "status" not in arguments:
            QuoteOperationGuard.validate_can_modify_items(current_status)

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
        variables = {k: v for k, v in variables.items() if v is not None and v != ""}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "insertUpdateQuote",
            "Mutation",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        quote = humps.decamelize(result["quote"])

        return quote

    # * MCP Function.
    @handle_errors(operation_name="update quote item")
    def update_quote_item(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing quote item (discount amount only).
        Maps to GraphQL: insertUpdateQuoteItem mutation

        Note: Only discount_amount can be updated. Other fields (qty, provider_item_uuid, etc.)
        are read-only after creation. To modify other properties, remove and re-add the item.

        Requirements:
        - Quote must be in 'initial' or 'in_progress' status to modify items

        Response includes:
        - slow_move_item: Boolean flag indicating if item is from slow-moving inventory
        - guardrail_price_per_uom: Minimum acceptable price for profitability
        """
        self.logger.info(f"Updating quote item: {arguments}")

        # Get current quote to check status
        get_quote_args = {"quote_uuid": arguments["quote_uuid"]}
        if "request_uuid" in arguments:
            get_quote_args["request_uuid"] = arguments["request_uuid"]

        current_quote = self.get_quote(**get_quote_args)
        if error := propagate_error_if_present(current_quote):
            return error

        # Validate that quote status allows item modifications
        current_status = current_quote.get("status", "")
        QuoteOperationGuard.validate_can_modify_items(current_status)

        variables = {
            "quoteUuid": arguments["quote_uuid"],
            "quoteItemUuid": arguments.get("quote_item_uuid"),
            "subtotalDiscount": arguments.get("discount_amount", 0.0),
            "updatedBy": "MCP",
        }

        # Remove None values
        variables = {k: v for k, v in variables.items() if v is not None and v != ""}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "insertUpdateQuoteItem",
            "Mutation",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        quote_item = humps.decamelize(result["quoteItem"])

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

        # Get current quote to check status
        get_quote_args = {"quote_uuid": arguments["quote_uuid"]}
        if "request_uuid" in arguments:
            get_quote_args["request_uuid"] = arguments["request_uuid"]

        current_quote = self.get_quote(**get_quote_args)
        if error := propagate_error_if_present(current_quote):
            return error

        # Validate that quote status allows item modifications
        current_status = current_quote.get("status", "")
        QuoteOperationGuard.validate_can_modify_items(current_status)

        # Check if quote status should be auto-updated to in_progress
        should_update_status = False
        if current_status == QuoteStatus.INITIAL:
            should_update_status = True
            self.logger.info(
                f"Quote status will be changed to 'in_progress' because items are being actively added"
            )

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
        variables = {k: v for k, v in variables.items() if v is not None and v != ""}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "insertUpdateQuoteItem",
            "Mutation",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        quote_item = humps.decamelize(result["quoteItem"])

        self.logger.info(
            f"Successfully added quote item to quote {arguments['quote_uuid']}"
        )

        # Update quote status to in_progress if needed
        if should_update_status:
            update_args = {
                "quote_uuid": arguments["quote_uuid"],
                "status": QuoteStatus.IN_PROGRESS,
            }
            if "request_uuid" in arguments:
                update_args["request_uuid"] = arguments["request_uuid"]

            update_result = self.update_quote(**update_args)
            if error := propagate_error_if_present(update_result):
                self.logger.warning(
                    f"Failed to update quote status to in_progress: {error}"
                )

        return quote_item

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

        return humps.decamelize(result)

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

        variables = {k: v for k, v in variables.items() if v is not None and v != ""}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "quoteList",
            "Query",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        return humps.decamelize(result)
