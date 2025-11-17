#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

__author__ = "bibow"

"""
Status management module for MCP RFQ Processor.

This module provides:
- Status constants for Requests, Quotes, and Installments
- Status transition validation
- Status-based operation guards
- Automatic status update logic
"""

from typing import Dict, List, Optional, Set

from .error_handler import ErrorCode, ValidationError

# ==================== Status Constants ====================


class RequestStatus:
    """Valid statuses for RFQ Requests."""

    INITIAL = "initial"
    IN_PROGRESS = "in_progress"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    MODIFIED = "modified"

    @classmethod
    def all_values(cls) -> Set[str]:
        """Get all valid request status values."""
        return {
            cls.INITIAL,
            cls.IN_PROGRESS,
            cls.CONFIRMED,
            cls.COMPLETED,
            cls.MODIFIED,
        }

    @classmethod
    def is_valid(cls, status: str) -> bool:
        """Check if status is valid."""
        return status in cls.all_values()


class QuoteStatus:
    """Valid statuses for Quotes."""

    INITIAL = "initial"
    IN_PROGRESS = "in_progress"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    DISAPPROVED = "disapproved"

    @classmethod
    def all_values(cls) -> Set[str]:
        """Get all valid quote status values."""
        return {
            cls.INITIAL,
            cls.IN_PROGRESS,
            cls.CONFIRMED,
            cls.COMPLETED,
            cls.DISAPPROVED,
        }

    @classmethod
    def is_valid(cls, status: str) -> bool:
        """Check if status is valid."""
        return status in cls.all_values()


class InstallmentStatus:
    """Valid statuses for Installments."""

    PENDING = "pending"
    PAID = "paid"
    CANCELLED = "cancelled"

    @classmethod
    def all_values(cls) -> Set[str]:
        """Get all valid installment status values."""
        return {cls.PENDING, cls.PAID, cls.CANCELLED}

    @classmethod
    def is_valid(cls, status: str) -> bool:
        """Check if status is valid."""
        return status in cls.all_values()


# ==================== Status Transition Rules ====================


class RequestStatusTransitions:
    """Valid status transitions for Requests."""

    # Map of: current_status -> allowed_next_statuses
    ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
        RequestStatus.INITIAL: {
            RequestStatus.IN_PROGRESS,
            RequestStatus.CONFIRMED,
        },
        RequestStatus.IN_PROGRESS: {
            RequestStatus.CONFIRMED,
            RequestStatus.MODIFIED,
        },
        RequestStatus.CONFIRMED: {
            RequestStatus.COMPLETED,
            RequestStatus.MODIFIED,
        },
        RequestStatus.MODIFIED: {
            RequestStatus.IN_PROGRESS,
            RequestStatus.CONFIRMED,
        },
        RequestStatus.COMPLETED: set(),  # Terminal state
    }

    @classmethod
    def is_valid_transition(cls, from_status: str, to_status: str) -> bool:
        """Check if status transition is valid."""
        # Allow staying in same status
        if from_status == to_status:
            return True

        allowed = cls.ALLOWED_TRANSITIONS.get(from_status, set())
        return to_status in allowed

    @classmethod
    def validate_transition(cls, from_status: str, to_status: str) -> None:
        """
        Validate status transition, raise error if invalid.

        Args:
            from_status: Current status
            to_status: Desired new status

        Raises:
            ValidationError: If transition is not allowed
        """
        if not cls.is_valid_transition(from_status, to_status):
            allowed = cls.ALLOWED_TRANSITIONS.get(from_status, set())
            raise ValidationError(
                message=f"Invalid request status transition: '{from_status}' → '{to_status}'. "
                f"Allowed transitions from '{from_status}': {sorted(allowed)}",
                error_code=ErrorCode.VALIDATION_FAILED,
                details={
                    "from_status": from_status,
                    "to_status": to_status,
                    "allowed_transitions": sorted(allowed),
                },
            )


class QuoteStatusTransitions:
    """Valid status transitions for Quotes."""

    # Map of: current_status -> allowed_next_statuses
    ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
        QuoteStatus.INITIAL: {
            QuoteStatus.IN_PROGRESS,
            QuoteStatus.CONFIRMED,
            QuoteStatus.DISAPPROVED,
        },
        QuoteStatus.IN_PROGRESS: {
            QuoteStatus.CONFIRMED,
            QuoteStatus.DISAPPROVED,
        },
        QuoteStatus.CONFIRMED: {
            QuoteStatus.COMPLETED,
            QuoteStatus.DISAPPROVED,
        },
        QuoteStatus.COMPLETED: set(),  # Terminal state
        QuoteStatus.DISAPPROVED: set(),  # Terminal state
    }

    @classmethod
    def is_valid_transition(cls, from_status: str, to_status: str) -> bool:
        """Check if status transition is valid."""
        # Allow staying in same status
        if from_status == to_status:
            return True

        allowed = cls.ALLOWED_TRANSITIONS.get(from_status, set())
        return to_status in allowed

    @classmethod
    def validate_transition(cls, from_status: str, to_status: str) -> None:
        """
        Validate status transition, raise error if invalid.

        Args:
            from_status: Current status
            to_status: Desired new status

        Raises:
            ValidationError: If transition is not allowed
        """
        if not cls.is_valid_transition(from_status, to_status):
            allowed = cls.ALLOWED_TRANSITIONS.get(from_status, set())
            raise ValidationError(
                message=f"Invalid quote status transition: '{from_status}' → '{to_status}'. "
                f"Allowed transitions from '{from_status}': {sorted(allowed)}",
                error_code=ErrorCode.VALIDATION_FAILED,
                details={
                    "from_status": from_status,
                    "to_status": to_status,
                    "allowed_transitions": sorted(allowed),
                },
            )


class InstallmentStatusTransitions:
    """Valid status transitions for Installments."""

    # Map of: current_status -> allowed_next_statuses
    ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
        InstallmentStatus.PENDING: {
            InstallmentStatus.PAID,
            InstallmentStatus.CANCELLED,
        },
        InstallmentStatus.PAID: set(),  # Terminal state
        InstallmentStatus.CANCELLED: set(),  # Terminal state
    }

    @classmethod
    def is_valid_transition(cls, from_status: str, to_status: str) -> bool:
        """Check if status transition is valid."""
        # Allow staying in same status
        if from_status == to_status:
            return True

        allowed = cls.ALLOWED_TRANSITIONS.get(from_status, set())
        return to_status in allowed

    @classmethod
    def validate_transition(cls, from_status: str, to_status: str) -> None:
        """
        Validate status transition, raise error if invalid.

        Args:
            from_status: Current status
            to_status: Desired new status

        Raises:
            ValidationError: If transition is not allowed
        """
        if not cls.is_valid_transition(from_status, to_status):
            allowed = cls.ALLOWED_TRANSITIONS.get(from_status, set())
            raise ValidationError(
                message=f"Invalid installment status transition: '{from_status}' → '{to_status}'. "
                f"Allowed transitions from '{from_status}': {sorted(allowed)}",
                error_code=ErrorCode.VALIDATION_FAILED,
                details={
                    "from_status": from_status,
                    "to_status": to_status,
                    "allowed_transitions": sorted(allowed),
                },
            )


# ==================== Operation Guards ====================


class RequestOperationGuard:
    """Guards for request operations based on status."""

    # Statuses that allow item modifications
    ALLOW_ITEM_MODIFICATIONS = {
        RequestStatus.INITIAL,
        RequestStatus.IN_PROGRESS,
        RequestStatus.MODIFIED,
    }

    # Statuses that allow creating quotes
    ALLOW_QUOTE_CREATION = {
        RequestStatus.CONFIRMED,
    }

    @classmethod
    def can_modify_items(cls, status: str) -> bool:
        """Check if request status allows item modifications."""
        return status in cls.ALLOW_ITEM_MODIFICATIONS

    @classmethod
    def validate_can_modify_items(cls, status: str) -> None:
        """
        Validate that request status allows item modifications.

        Raises:
            ValidationError: If operation is not allowed
        """
        if not cls.can_modify_items(status):
            raise ValidationError(
                message=f"Cannot modify items: Request status is '{status}'. "
                f"Item modifications are only allowed in statuses: {sorted(cls.ALLOW_ITEM_MODIFICATIONS)}",
                error_code=ErrorCode.VALIDATION_FAILED,
                details={
                    "current_status": status,
                    "allowed_statuses": sorted(cls.ALLOW_ITEM_MODIFICATIONS),
                },
            )

    @classmethod
    def can_create_quote(cls, status: str) -> bool:
        """Check if request status allows quote creation."""
        return status in cls.ALLOW_QUOTE_CREATION

    @classmethod
    def validate_can_create_quote(cls, status: str) -> None:
        """
        Validate that request status allows quote creation.

        Raises:
            ValidationError: If operation is not allowed
        """
        if not cls.can_create_quote(status):
            raise ValidationError(
                message=f"Cannot create quote: Request status is '{status}'. "
                f"Quotes can only be created from requests with status: {sorted(cls.ALLOW_QUOTE_CREATION)}",
                error_code=ErrorCode.VALIDATION_FAILED,
                details={
                    "current_status": status,
                    "allowed_statuses": sorted(cls.ALLOW_QUOTE_CREATION),
                },
            )


class QuoteOperationGuard:
    """Guards for quote operations based on status."""

    # Statuses that allow item modifications
    ALLOW_ITEM_MODIFICATIONS = {
        QuoteStatus.INITIAL,
        QuoteStatus.IN_PROGRESS,
    }

    # Statuses that allow creating installments
    ALLOW_INSTALLMENT_CREATION = {
        QuoteStatus.CONFIRMED,
    }

    @classmethod
    def can_modify_items(cls, status: str) -> bool:
        """Check if quote status allows item modifications."""
        return status in cls.ALLOW_ITEM_MODIFICATIONS

    @classmethod
    def validate_can_modify_items(cls, status: str) -> None:
        """
        Validate that quote status allows item modifications.

        Raises:
            ValidationError: If operation is not allowed
        """
        if not cls.can_modify_items(status):
            raise ValidationError(
                message=f"Cannot modify quote items: Quote status is '{status}'. "
                f"Item modifications are only allowed in statuses: {sorted(cls.ALLOW_ITEM_MODIFICATIONS)}",
                error_code=ErrorCode.VALIDATION_FAILED,
                details={
                    "current_status": status,
                    "allowed_statuses": sorted(cls.ALLOW_ITEM_MODIFICATIONS),
                },
            )

    @classmethod
    def can_create_installment(cls, status: str) -> bool:
        """Check if quote status allows installment creation."""
        return status in cls.ALLOW_INSTALLMENT_CREATION

    @classmethod
    def validate_can_create_installment(cls, status: str) -> None:
        """
        Validate that quote status allows installment creation.

        Raises:
            ValidationError: If operation is not allowed
        """
        if not cls.can_create_installment(status):
            raise ValidationError(
                message=f"Cannot create installment: Quote status is '{status}'. "
                f"Installments can only be created for quotes with status: {sorted(cls.ALLOW_INSTALLMENT_CREATION)}",
                error_code=ErrorCode.VALIDATION_FAILED,
                details={
                    "current_status": status,
                    "allowed_statuses": sorted(cls.ALLOW_INSTALLMENT_CREATION),
                },
            )


# ==================== Automatic Status Update Logic ====================


def should_request_be_modified(
    current_status: str, items_changed: bool, has_quotes: bool
) -> bool:
    """
    Determine if request status should be changed to 'modified'.

    Business Rule: When a confirmed request's items are changed and quotes exist,
    the request should be marked as 'modified'.

    Args:
        current_status: Current request status
        items_changed: Whether items were added/removed/updated
        has_quotes: Whether the request has associated quotes

    Returns:
        True if request should be marked as modified
    """
    # Only auto-modify if request is confirmed and has quotes
    if current_status == RequestStatus.CONFIRMED and items_changed and has_quotes:
        return True
    return False


def should_request_be_in_progress(current_status: str, items_changed: bool) -> bool:
    """
    Determine if request status should be changed to 'in_progress'.

    Business Rule: When a request in 'initial' or 'modified' status has items being actively worked on,
    the request should move to 'in_progress' to indicate ongoing changes.

    Args:
        current_status: Current request status
        items_changed: Whether items were added/removed/updated

    Returns:
        True if request should be marked as in_progress
    """
    # Auto-transition from initial or modified to in_progress when items are being changed
    if (
        current_status == RequestStatus.MODIFIED
        or current_status == RequestStatus.INITIAL
    ) and items_changed:
        return True
    return False


def should_quotes_be_disapproved(request_status: str) -> bool:
    """
    Determine if all quotes should be disapproved.

    Business Rule: When a request status changes to 'modified',
    all related quotes should be disapproved.

    Args:
        request_status: Current/new request status

    Returns:
        True if quotes should be disapproved
    """
    return request_status == RequestStatus.MODIFIED


def should_quote_be_completed(installments: List[Dict]) -> bool:
    """
    Determine if quote status should be changed to 'completed'.

    Business Rule: When all installments are marked as 'paid',
    the quote should be marked as 'completed'.

    Args:
        installments: List of installment objects with 'status' field

    Returns:
        True if quote should be marked as completed
    """
    if not installments:
        return False

    # Check if all non-cancelled installments are paid
    active_installments = [
        inst
        for inst in installments
        if inst.get("status") != InstallmentStatus.CANCELLED
    ]

    if not active_installments:
        return False

    all_paid = all(
        inst.get("status") == InstallmentStatus.PAID for inst in active_installments
    )

    return all_paid
