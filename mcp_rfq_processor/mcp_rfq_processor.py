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

# Import status management
from .status_manager import (
    InstallmentStatus,
    InstallmentStatusTransitions,
    QuoteOperationGuard,
    QuoteStatus,
    QuoteStatusTransitions,
    RequestOperationGuard,
    RequestStatus,
    RequestStatusTransitions,
    should_quote_be_completed,
    should_quotes_be_disapproved,
    should_request_be_completed,
    should_request_be_in_progress,
)


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

    def _disapprove_all_quotes_for_request(self, request_uuid: str) -> None:
        """
        Disapprove all quotes associated with a request.

        This implements the critical business rule:
        "When a request status changes to 'modified', all related quotes
        (regardless of their current status) are automatically changed to 'disapproved'"

        Args:
            request_uuid: UUID of the request whose quotes should be disapproved
        """
        self.logger.info(f"Auto-disapproving all quotes for request {request_uuid}")

        # Get all quotes for this request
        quotes_result = self.search_quotes(request_uuid=request_uuid, limit=100)

        # Check for errors
        if error := propagate_error_if_present(quotes_result):
            self.logger.error(f"Failed to fetch quotes for auto-disapproval: {error}")
            return

        quote_list = quotes_result.get("quote_list", [])

        if not quote_list:
            self.logger.info(f"No quotes found for request {request_uuid}")
            return

        # Disapprove each quote (except those already disapproved)
        disapproved_count = 0
        for quote in quote_list:
            quote_uuid = quote.get("quote_uuid")
            current_status = quote.get("status", "")

            # Skip if already disapproved
            if current_status == QuoteStatus.DISAPPROVED:
                continue

            # Update quote status to disapproved
            try:
                update_result = self.update_quote(
                    request_uuid=request_uuid,
                    quote_uuid=quote_uuid,
                    status=QuoteStatus.DISAPPROVED,
                    notes=f"Auto-disapproved: Request was modified",
                )

                if error := propagate_error_if_present(update_result):
                    self.logger.error(
                        f"Failed to disapprove quote {quote_uuid}: {error}"
                    )
                else:
                    disapproved_count += 1
                    self.logger.info(
                        f"Disapproved quote {quote_uuid} (was {current_status})"
                    )
            except Exception as e:
                self.logger.error(f"Error disapproving quote {quote_uuid}: {e}")

        self.logger.info(
            f"Auto-disapproved {disapproved_count} quote(s) for request {request_uuid}"
        )

    # ==================== Request Management Tools ====================

    # * MCP Function.
    @handle_errors(operation_name="submit RFQ request")
    def submit_rfq_request(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit new RFQ request.
        Maps to GraphQL: insertUpdateRequest mutation

        Default status: 'initial' - Request has been created but not yet being worked on.
        """
        self.logger.info(f"Submitting RFQ request: {arguments}")

        variables = {
            "email": arguments["email"],
            "requestTitle": arguments["request_title"],
            "requestDescription": arguments.get("request_description", ""),
            "billingAddress": arguments.get("billing_address"),
            "shippingAddress": arguments.get("shipping_address"),
            "items": arguments.get("items"),
            "notes": arguments.get("notes"),
            "expiredAt": arguments.get("expired_at"),
            "status": arguments.get("status", RequestStatus.INITIAL),
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

        Status transitions are validated according to the request status flow.
        """
        self.logger.info(f"Updating RFQ request: {arguments}")

        # Get current request to check current status
        current_request = self.get_rfq_request(request_uuid=arguments["request_uuid"])
        if error := propagate_error_if_present(current_request):
            return error

        current_status = current_request.get("status", "")

        # Validate status transition if status is being updated
        if "status" in arguments:
            new_status = arguments["status"]
            # Validate the transition
            RequestStatusTransitions.validate_transition(current_status, new_status)

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

        # Critical Business Rule: Auto-disapprove quotes if request status changed to 'modified'
        new_status = request.get("status", "")
        if should_quotes_be_disapproved(new_status):
            request_uuid = arguments["request_uuid"]
            self.logger.info(
                f"Request {request_uuid} status changed to '{new_status}', "
                f"triggering auto-disapproval of all quotes"
            )
            self._disapprove_all_quotes_for_request(request_uuid)

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
        new_item_uuid = new_item.get("item_uuid")

        # Check if item already exists and merge quantity if so
        item_found = False
        if new_item_uuid:
            for existing_item in current_items:
                existing_item_uuid = existing_item.get("item_uuid")
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

        # Check if request status should be auto-updated to in_progress
        current_status = current_request.get("status", "")
        new_status = None
        if should_request_be_in_progress(current_status, items_changed=True):
            new_status = RequestStatus.IN_PROGRESS
            self.logger.info(
                f"Request status will be changed to 'in_progress' because items are being actively modified"
            )

        # Update request with new items array
        variables = {
            "requestUuid": arguments["request_uuid"],
            "items": current_items,
            "updatedBy": "MCP",
        }

        # Add status if it should be changed to in_progress
        if new_status:
            variables["status"] = new_status

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

        # Check if request status should be auto-updated to in_progress
        current_status = current_request.get("status", "")
        new_status = None
        if should_request_be_in_progress(current_status, items_changed=True):
            new_status = RequestStatus.IN_PROGRESS
            self.logger.info(
                f"Request status will be changed to 'in_progress' because items are being actively modified"
            )

        # Update request with modified items array
        variables = {
            "requestUuid": arguments["request_uuid"],
            "items": current_items,
            "updatedBy": "MCP",
        }

        # Add status if it should be changed to in_progress
        if new_status:
            variables["status"] = new_status

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
    @handle_errors(operation_name="confirm request and create quotes")
    def confirm_request_and_create_quotes(
        self, **arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update request to confirmed status and create quotes for selected provider groups.

        This is a convenience method that:
        1. Updates the request status to 'confirmed'
        2. Creates quotes for each selected provider_corp_external_id
        3. Returns summary of created quotes

        Args:
            request_uuid: UUID of the request to confirm
            provider_corp_external_ids: List of provider corporation external IDs to create quotes for
            segment_uuid: Customer segment UUID (required for quote creation)

        Note:
            Sales rep emails are retrieved from settings, grouped by provider_corp_external_id.
            Settings should contain a 'sales_rep_emails' dictionary mapping provider_corp_external_id to email.

        Returns:
            Dictionary with confirmed request and list of created quotes with full details (including quote items)
        """
        self.logger.info(f"Confirming request and creating quotes: {arguments}")

        request_uuid = arguments["request_uuid"]
        provider_corp_external_ids = arguments["provider_corp_external_ids"]
        segment_uuid = arguments["segment_uuid"]

        # Get sales_rep_emails from settings instead of arguments
        sales_rep_emails = self.setting.get("sales_rep_emails", {})

        # Validate inputs
        validate_not_empty(request_uuid, "request_uuid", "Request UUID is required")
        validate_not_empty(
            provider_corp_external_ids,
            "provider_corp_external_ids",
            "Provider corporation external IDs list is required",
        )
        validate_not_empty(segment_uuid, "segment_uuid", "Segment UUID is required")

        if (
            not isinstance(provider_corp_external_ids, list)
            or len(provider_corp_external_ids) == 0
        ):
            return build_error_response(
                message="provider_corp_external_ids must be a non-empty list",
                error_code=ErrorCode.VALIDATION_FAILED,
            )

        # Validate request status allows confirmation
        current_request = self.get_rfq_request(request_uuid=request_uuid)
        if error := propagate_error_if_present(current_request):
            return error

        current_status = current_request.get("status", "")
        # Validate the transition to confirmed
        RequestStatusTransitions.validate_transition(
            current_status, RequestStatus.CONFIRMED
        )

        # Step 1: Update request status to confirmed
        self.logger.info(f"Updating request {request_uuid} status to confirmed")

        confirmed_request = self.update_rfq_request(
            request_uuid=request_uuid, status=RequestStatus.CONFIRMED
        )

        if error := propagate_error_if_present(confirmed_request):
            return error

        # Step 2: Create quotes for each selected provider
        created_quotes = []
        failed_quotes = []

        for provider_corp_external_id in provider_corp_external_ids:
            self.logger.info(f"Creating quote for provider {provider_corp_external_id}")

            try:
                # Get sales rep email for this provider (if provided)
                sales_rep_email = sales_rep_emails.get(provider_corp_external_id)

                quote_result = self._create_quote(
                    request_uuid=request_uuid,
                    provider_corp_external_id=provider_corp_external_id,
                    sales_rep_email=sales_rep_email,
                    segment_uuid=segment_uuid,
                )

                if error := propagate_error_if_present(quote_result):
                    failed_quotes.append(
                        {
                            "provider_corp_external_id": provider_corp_external_id,
                            "error": error,
                        }
                    )
                    self.logger.error(
                        f"Failed to create quote for provider {provider_corp_external_id}: {error}"
                    )
                else:
                    # Get full quote details including quote items
                    quote_uuid = quote_result.get("quote_uuid")
                    full_quote = self.get_quote(
                        request_uuid=request_uuid, quote_uuid=quote_uuid
                    )

                    if error := propagate_error_if_present(full_quote):
                        # If we can't get full details, use the basic quote result
                        created_quotes.append(quote_result)
                        self.logger.warning(
                            f"Created quote {quote_uuid} but failed to get full details: {error}"
                        )
                    else:
                        created_quotes.append(full_quote)

                    self.logger.info(
                        f"Successfully created quote {quote_uuid} for provider {provider_corp_external_id}"
                    )

            except Exception as e:
                failed_quotes.append(
                    {
                        "provider_corp_external_id": provider_corp_external_id,
                        "error": {"message": str(e)},
                    }
                )
                self.logger.error(
                    f"Exception creating quote for provider {provider_corp_external_id}: {e}"
                )

        # Return summary
        result = {
            "request": confirmed_request,
            "created_quotes": created_quotes,
            "total_quotes_created": len(created_quotes),
            "total_quotes_requested": len(provider_corp_external_ids),
        }

        # Include failed quotes if any
        if failed_quotes:
            result["failed_quotes"] = failed_quotes
            result["total_quotes_failed"] = len(failed_quotes)

        self.logger.info(
            f"Request confirmation completed: {len(created_quotes)}/{len(provider_corp_external_ids)} quotes created successfully"
        )

        return result

    # * MCP Function.
    @handle_errors(operation_name="confirm quote and create installments")
    def confirm_quote_and_create_installments(
        self, **arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Confirm a selected quote and create installment plan.

        This is a convenience method that:
        1. Updates the quote status to 'confirmed'
        2. Creates either a single installment for full amount or multiple installments
        3. Returns confirmed quote and created installments

        Args:
            request_uuid: UUID of the request
            quote_uuid: UUID of the quote to confirm
            create_single_installment: If True, creates one installment for full amount (default: True)
            interval_num: Number of installments (required if create_single_installment=False)
            total_pay_period: Total payment period in months (required if create_single_installment=False)
            payment_method: Optional payment method for installments

        Returns:
            Dictionary with confirmed quote and created installments
        """
        self.logger.info(f"Confirming quote and creating installments: {arguments}")

        request_uuid = arguments["request_uuid"]
        quote_uuid = arguments["quote_uuid"]
        create_single_installment = arguments.get("create_single_installment", True)
        payment_method = arguments.get("payment_method")

        # Validate inputs
        validate_not_empty(request_uuid, "request_uuid", "Request UUID is required")
        validate_not_empty(quote_uuid, "quote_uuid", "Quote UUID is required")

        if not create_single_installment:
            interval_num = arguments.get("interval_num")
            total_pay_period = arguments.get("total_pay_period")

            validate_not_empty(
                interval_num,
                "interval_num",
                "interval_num is required for multiple installments",
            )
            validate_not_empty(
                total_pay_period,
                "total_pay_period",
                "total_pay_period is required for multiple installments",
            )

            if interval_num <= 0:
                return build_error_response(
                    message="interval_num must be greater than 0",
                    error_code=ErrorCode.VALIDATION_FAILED,
                )

            if total_pay_period <= 0:
                return build_error_response(
                    message="total_pay_period must be greater than 0",
                    error_code=ErrorCode.VALIDATION_FAILED,
                )

        # Validate quote status allows confirmation
        current_quote = self.get_quote(request_uuid=request_uuid, quote_uuid=quote_uuid)
        if error := propagate_error_if_present(current_quote):
            return error

        current_status = current_quote.get("status", "")
        # Validate the transition to confirmed
        QuoteStatusTransitions.validate_transition(
            current_status, QuoteStatus.CONFIRMED
        )

        # Step 1: Update quote status to confirmed
        self.logger.info(f"Updating quote {quote_uuid} status to confirmed")

        confirmed_quote = self.update_quote(
            request_uuid=request_uuid,
            quote_uuid=quote_uuid,
            status=QuoteStatus.CONFIRMED,
        )

        if error := propagate_error_if_present(confirmed_quote):
            return error

        # Business Rule: Disapprove all other quotes for this request when one is confirmed
        self.logger.info(
            f"Quote {quote_uuid} confirmed, disapproving all other quotes for request {request_uuid}"
        )

        # Get all quotes for this request
        quotes_result = self.search_quotes(
            request_uuid=request_uuid,
            limit=100,
        )

        if not propagate_error_if_present(quotes_result):
            all_quotes = quotes_result.get("quote_list", [])

            # Filter quotes that should be disapproved
            # Exclude: the confirmed quote, already in terminal states (disapproved, completed)
            terminal_statuses = [
                QuoteStatus.DISAPPROVED,
                QuoteStatus.COMPLETED,
            ]
            quotes_to_disapprove = [
                q
                for q in all_quotes
                if q.get("quote_uuid") != quote_uuid
                and q.get("status") not in terminal_statuses
            ]

            # Disapprove each quote
            for quote_to_disapprove in quotes_to_disapprove:
                disapprove_quote_uuid = quote_to_disapprove.get("quote_uuid")
                self.logger.info(f"Disapproving quote {disapprove_quote_uuid}")

                disapprove_result = self.update_quote(
                    request_uuid=request_uuid,
                    quote_uuid=disapprove_quote_uuid,
                    status=QuoteStatus.DISAPPROVED,
                    notes="Auto-disapproved: Another quote was confirmed",
                )

                if error := propagate_error_if_present(disapprove_result):
                    self.logger.error(
                        f"Failed to disapprove quote {disapprove_quote_uuid}: {error}"
                    )
                else:
                    self.logger.info(
                        f"Successfully disapproved quote {disapprove_quote_uuid}"
                    )

        # Step 2: Create installments
        installments_result = None

        if create_single_installment:
            # Create single installment for full amount
            self.logger.info(f"Creating single installment for full quote amount")

            installment_args = {
                "request_uuid": request_uuid,
                "quote_uuid": quote_uuid,
                "status": "pending",
            }

            if payment_method:
                installment_args["payment_method"] = payment_method

            installments_result = self._create_installment(**installment_args)

            if error := propagate_error_if_present(installments_result):
                return build_error_response(
                    message=f"Quote confirmed but failed to create installment: {error.get('message', 'Unknown error')}",
                    error_code=ErrorCode.OPERATION_FAILED,
                    details={
                        "confirmed_quote": confirmed_quote,
                        "installment_error": error,
                    },
                )

            # Wrap single installment in array for consistent response format
            installments_result = {
                "installments": [installments_result],
                "total_created": 1,
                "installment_amount_per": installments_result.get("installment_amount"),
                "total_installment_amount": installments_result.get(
                    "installment_amount"
                ),
            }

        else:
            # Create multiple installments
            self.logger.info(
                f"Creating {arguments['interval_num']} installments over {arguments['total_pay_period']} months"
            )

            installments_args = {
                "request_uuid": request_uuid,
                "quote_uuid": quote_uuid,
                "interval_num": arguments["interval_num"],
                "total_pay_period": arguments["total_pay_period"],
            }

            if payment_method:
                installments_args["payment_method"] = payment_method

            installments_result = self._create_installments(**installments_args)

            if error := propagate_error_if_present(installments_result):
                return build_error_response(
                    message=f"Quote confirmed but failed to create installments: {error.get('message', 'Unknown error')}",
                    error_code=ErrorCode.OPERATION_FAILED,
                    details={
                        "confirmed_quote": confirmed_quote,
                        "installments_error": error,
                    },
                )

        # Get updated quote with full details
        final_quote = self.get_quote(request_uuid=request_uuid, quote_uuid=quote_uuid)

        if error := propagate_error_if_present(final_quote):
            # Use confirmed_quote if we can't get updated details
            final_quote = confirmed_quote

        # Return summary
        result = {
            "quote": final_quote,
            "installments": installments_result.get("installments", []),
            "total_installments_created": installments_result.get("total_created", 0),
            "installment_amount_per": installments_result.get("installment_amount_per"),
            "total_installment_amount": installments_result.get(
                "total_installment_amount"
            ),
            "installment_type": "single" if create_single_installment else "multiple",
        }

        self.logger.info(
            f"Quote confirmation completed: Quote {quote_uuid} confirmed with {result['total_installments_created']} installment(s) created"
        )

        return result

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
        Search provider inventory with batch information merged.
        Maps to GraphQL: providerItemList query

        For each provider item, fetches and merges batch information including:
        - batches: Array of batch details with slow_move_item flags and guardrail pricing
        - Each batch includes: batch_no, expired_at, produced_at, slow_move_item, guardrail_price_per_uom

        Optional batch filters (applied when fetching batches):
        - expired_at_gt: Filter batches expiring after this date
        - expired_at_lt: Filter batches expiring before this date
        - slow_move_item: Filter for slow-moving inventory (default: False)
        - in_stock: Filter for in-stock batches (default: True)

        Note: If no expiration filters provided, defaults to batches expiring 90+ days from now.
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

        provider_items_result = humps.decamelize(result["providerItemList"])
        provider_item_list = provider_items_result.get("provider_item_list", [])

        # Extract batch filter parameters from arguments (optional)
        batch_expired_at_gt = arguments.get("expired_at_gt")
        batch_expired_at_lt = arguments.get("expired_at_lt")
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
                    "expired_at_lt": batch_expired_at_lt,
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

        Note: If neither expired_at_gt nor expired_at_lt is provided, defaults to
        filtering batches expiring 90+ days from now.
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
            key in arguments
            for key in ["shipping_method", "shipping_amount", "notes"]
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

    # ==================== Installment Tools ====================

    # * Private helper method (not exposed as MCP tool)
    @handle_errors(operation_name="create installment")
    def _create_installment(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
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

        # Validate that quote status allows installment creation
        current_status = quote_result.get("status", "")
        QuoteOperationGuard.validate_can_create_installment(current_status)

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

        Status transitions are validated according to the installment status flow.
        When all installments are marked as 'paid', the quote is auto-completed.
        """
        self.logger.info(f"Updating installment: {arguments}")

        # Validate status transition if status is being updated
        if "status" in arguments:
            new_status = arguments["status"]

            # Get all installments for this quote to find the current one
            installments_result = self.get_installments(
                quote_uuid=arguments["quote_uuid"],
                limit=100,
            )

            if error := propagate_error_if_present(installments_result):
                return error

            all_installments = installments_result.get("installment_list", [])
            current_installment = None

            for inst in all_installments:
                if inst.get("installment_uuid") == arguments["installment_uuid"]:
                    current_installment = inst
                    break

            if current_installment:
                current_status = current_installment.get("status", "")
                # Validate the transition
                InstallmentStatusTransitions.validate_transition(
                    current_status, new_status
                )

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

        # Business Rule: Auto-complete quote if all installments are paid
        # Check if status was updated to 'paid' and if we should check for quote completion
        updated_status = installment.get("status", "")
        if updated_status == InstallmentStatus.PAID:
            self.logger.info(
                f"Installment {arguments['installment_uuid']} marked as paid, "
                f"checking if quote should be completed"
            )

            # Get all installments for this quote
            installments_result = self.get_installments(
                quote_uuid=arguments["quote_uuid"],
                limit=100,
            )

            if not propagate_error_if_present(installments_result):
                all_installments = installments_result.get("installment_list", [])

                # Check if all installments are paid
                if should_quote_be_completed(all_installments):
                    self.logger.info(
                        f"All installments paid for quote {arguments['quote_uuid']}, "
                        f"auto-completing quote"
                    )

                    # Get the request_uuid from the quote object in the installment
                    request_uuid = installment.get("quote", {}).get("request", {}).get(
                        "request_uuid"
                    )

                    # Update quote status to completed
                    update_quote_result = self.update_quote(
                        request_uuid=request_uuid,
                        quote_uuid=arguments["quote_uuid"],
                        status=QuoteStatus.COMPLETED,
                        notes="Auto-completed: All installments paid",
                    )

                    if error := propagate_error_if_present(update_quote_result):
                        self.logger.error(
                            f"Failed to auto-complete quote {arguments['quote_uuid']}: {error}"
                        )
                    else:
                        self.logger.info(
                            f"Successfully auto-completed quote {arguments['quote_uuid']}"
                        )

                        # Business Rule: Auto-complete request if at least one quote is completed
                        self.logger.info(
                            f"Quote {arguments['quote_uuid']} completed, "
                            f"checking if request should be completed"
                        )

                        # Get all quotes for this request
                        quotes_result = self.search_quotes(
                            request_uuid=request_uuid,
                            limit=100,
                        )

                        if not propagate_error_if_present(quotes_result):
                            all_quotes = quotes_result.get("quote_list", [])

                            # Check if at least one quote is completed
                            if should_request_be_completed(all_quotes):
                                self.logger.info(
                                    f"At least one quote completed for request {request_uuid}, "
                                    f"auto-completing request"
                                )

                                # Update request status to completed
                                update_request_result = self.update_rfq_request(
                                    request_uuid=request_uuid,
                                    status=RequestStatus.COMPLETED,
                                )

                                if error := propagate_error_if_present(
                                    update_request_result
                                ):
                                    self.logger.error(
                                        f"Failed to auto-complete request {request_uuid}: {error}"
                                    )
                                else:
                                    self.logger.info(
                                        f"Successfully auto-completed request {request_uuid}"
                                    )

        return installment

    # * Private helper method (not exposed as MCP tool)
    @handle_errors(operation_name="create installments")
    def _create_installments(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
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
