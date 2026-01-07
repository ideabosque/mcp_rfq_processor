#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

__author__ = "bibow"

from typing import Any, Dict

import humps
import pendulum

# Import centralized error handling utilities
from .error_handler import (
    ErrorCode,
    build_error_response,
    handle_errors,
    propagate_error_if_present,
)
from .pricing_processor import PricingProcessor

# Import status management
from .status_manager import (
    InstallmentStatus,
    InstallmentStatusTransitions,
    QuoteOperationGuard,
    QuoteStatus,
    RequestStatus,
    should_quote_be_completed,
    should_request_be_completed,
)


class InstallmentProcessor(PricingProcessor):
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

        # Convert to float to ensure proper arithmetic operations
        final_total_quote_amount = float(final_total_quote_amount)

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
                existing_total += float(inst.get("installment_amount", 0))

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
            # Convert to float to ensure proper arithmetic operations
            requested_amount = float(requested_amount)
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
                    request_uuid = (
                        installment.get("quote", {})
                        .get("request", {})
                        .get("request_uuid")
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
        interval_num = int(arguments["interval_num"])
        total_pay_period = float(arguments["total_pay_period"])

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

        # Validate that quote status allows installment creation (must be confirmed)
        current_status = quote_result.get("status", "")
        QuoteOperationGuard.validate_can_create_installment(current_status)

        # Get the quote amount
        final_total_quote_amount = quote_result.get("final_total_quote_amount")
        if final_total_quote_amount is None:
            return build_error_response(
                message=f"Quote {quote_uuid} does not have final_total_quote_amount set",
                error_code=ErrorCode.VALIDATION_FAILED,
            )

        # Convert to float to ensure proper arithmetic operations
        final_total_quote_amount = float(final_total_quote_amount)

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
                existing_total += float(inst.get("installment_amount", 0))

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

        variables = {k: v for k, v in variables.items() if v is not None and v != ""}

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
