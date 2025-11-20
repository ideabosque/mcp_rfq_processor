#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

__author__ = "bibow"

from typing import Any, Dict

import humps

# Import centralized error handling utilities
from .error_handler import (
    ErrorCode,
    ValidationError,
    build_error_response,
    handle_errors,
    propagate_error_if_present,
    validate_not_empty,
)
from .graphql_backed_processor import GraphQLBackedProcessor

# Import status management
from .status_manager import (
    QuoteStatus,
    QuoteStatusTransitions,
    RequestStatus,
    RequestStatusTransitions,
    should_quotes_be_disapproved,
    should_request_be_in_progress,
)


class RequestProcessor(GraphQLBackedProcessor):
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

        # Validate that the provider item belongs to the specified provider
        provider_item_result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "providerItem",
            "Query",
            {"providerItemUuid": provider_item_uuid},
        )

        if error := propagate_error_if_present(provider_item_result):
            return error

        provider_item = humps.decamelize(provider_item_result.get("providerItem"))

        if not provider_item:
            raise ValidationError(
                message=f"Provider item with UUID '{provider_item_uuid}' not found",
                error_code=ErrorCode.ITEM_NOT_FOUND,
                details={"provider_item_uuid": provider_item_uuid},
            )

        actual_provider_corp_id = provider_item.get("provider_corp_external_id")
        if (
            actual_provider_corp_id
            and actual_provider_corp_id != provider_corp_external_id
        ):
            raise ValidationError(
                message=(
                    f"Provider item '{provider_item_uuid}' belongs to provider "
                    f"'{actual_provider_corp_id}', cannot assign to "
                    f"'{provider_corp_external_id}'"
                ),
                error_code=ErrorCode.VALIDATION_FAILED,
                details={
                    "provider_item_uuid": provider_item_uuid,
                    "expected_provider_corp_external_id": provider_corp_external_id,
                    "actual_provider_corp_external_id": actual_provider_corp_id,
                },
            )

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
