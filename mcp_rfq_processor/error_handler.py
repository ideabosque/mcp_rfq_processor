"""
Centralized error handling module for MCP RFQ Processor.

This module provides:
- Custom exception classes (MCPError, GraphQLError, ValidationError)
- Error handler decorator for consistent error handling across methods
- Error response builders for standardized API responses
- Error code constants for programmatic error handling
- Validation utilities (validate_not_empty, propagate_error_if_present)
"""

import traceback
import re
from functools import wraps
from typing import Dict, Any, Callable, Optional
from logging import Logger


# Error Code Constants
class ErrorCode:
    """Error codes for programmatic error handling."""

    # GraphQL/API Errors
    GRAPHQL_QUERY_FAILED = "GRAPHQL_QUERY_FAILED"
    GRAPHQL_SCHEMA_FETCH_FAILED = "GRAPHQL_SCHEMA_FETCH_FAILED"
    API_CONNECTION_FAILED = "API_CONNECTION_FAILED"

    # Validation Errors
    VALIDATION_FAILED = "VALIDATION_FAILED"
    ITEM_NOT_FOUND = "ITEM_NOT_FOUND"
    NO_ITEMS_FOUND = "NO_ITEMS_FOUND"
    INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"

    # General Errors
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    OPERATION_FAILED = "OPERATION_FAILED"


# Custom Exception Classes
class MCPError(Exception):
    """Base exception class for MCP RFQ Processor errors."""

    def __init__(self, message: str, error_code: str = ErrorCode.UNKNOWN_ERROR, details: Optional[Dict[str, Any]] = None):
        """
        Initialize MCP error.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional error context/details
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class GraphQLError(MCPError):
    """Exception raised for GraphQL-related errors."""

    def __init__(self, message: str, error_code: str = ErrorCode.GRAPHQL_QUERY_FAILED, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code, details)


class ValidationError(MCPError):
    """Exception raised for validation errors."""

    def __init__(self, message: str, error_code: str = ErrorCode.VALIDATION_FAILED, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code, details)


# Error Message Extraction Utilities
def extract_error_message(error_str: str) -> str:
    """
    Extract clean error message from GraphQL error response.

    Handles GraphQL error format like:
    [{'message': 'Item does not exist', 'locations': [...]}]

    Args:
        error_str: Raw error string

    Returns:
        Cleaned error message
    """
    try:
        # Try to extract GraphQL error message using regex
        message_match = re.search(r"'message':\s*\"([^\"]+)\"", error_str)
        if not message_match:
            message_match = re.search(r"'message':\s*'([^']+)'", error_str)

        if message_match:
            return message_match.group(1)

        return str(error_str)
    except Exception:
        return str(error_str)


# Error Response Builders
def build_error_response(
    message: str,
    error_code: str = ErrorCode.UNKNOWN_ERROR,
    details: Optional[Dict[str, Any]] = None,
    include_code: bool = True
) -> Dict[str, Any]:
    """
    Build standardized error response dictionary.

    Args:
        message: Human-readable error message
        error_code: Machine-readable error code
        details: Additional error context
        include_code: Whether to include error_code in response (default: True)

    Returns:
        Standardized error response dict
    """
    response = {"error": message}

    if include_code:
        response["error_code"] = error_code

    if details:
        response["details"] = details

    return response


def build_error_from_exception(
    exception: Exception,
    include_code: bool = True
) -> Dict[str, Any]:
    """
    Build error response from an exception instance.

    Args:
        exception: The exception to convert
        include_code: Whether to include error_code in response

    Returns:
        Standardized error response dict
    """
    if isinstance(exception, MCPError):
        return build_error_response(
            message=exception.message,
            error_code=exception.error_code,
            details=exception.details,
            include_code=include_code
        )
    else:
        # For standard exceptions, extract clean message
        clean_message = extract_error_message(str(exception))
        return build_error_response(
            message=clean_message,
            error_code=ErrorCode.UNKNOWN_ERROR,
            include_code=include_code
        )


# Error Handler Decorator
def handle_errors(
    operation_name: str,
    log_traceback: bool = False,
    include_error_code: bool = True
) -> Callable:
    """
    Decorator for consistent error handling across methods.

    Automatically catches exceptions, logs them, and returns standardized error responses.

    Args:
        operation_name: Name of the operation for logging (e.g., "submit_rfq")
        log_traceback: Whether to log full traceback (default: False)
        include_error_code: Whether to include error codes in responses (default: True)

    Returns:
        Decorated function

    Example:
        @handle_errors(operation_name="submit_rfq")
        def submit_rfq_request(self, **arguments):
            # Your business logic here
            return {"id": "123"}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs) -> Dict[str, Any]:
            try:
                # Execute the wrapped function
                result = func(self, *args, **kwargs)

                # If result contains an error, ensure it's properly formatted
                if isinstance(result, dict) and "error" in result:
                    # If it's a simple error dict without error_code, add it
                    if include_error_code and "error_code" not in result:
                        result["error_code"] = ErrorCode.OPERATION_FAILED

                return result

            except MCPError as e:
                # Handle custom MCP exceptions
                if log_traceback:
                    log = traceback.format_exc()
                    self.logger.error(log)
                else:
                    self.logger.error(f"Failed to {operation_name}: {e.message}")

                return build_error_from_exception(e, include_error_code)

            except Exception as e:
                # Handle unexpected exceptions
                if log_traceback:
                    log = traceback.format_exc()
                    self.logger.error(log)
                else:
                    self.logger.error(f"Failed to {operation_name}: {e}")

                return build_error_from_exception(e, include_error_code)

        return wrapper
    return decorator


# Validation Utilities
def validate_not_empty(value: Any, field_name: str, error_message: Optional[str] = None) -> None:
    """
    Validate that a value is not empty.

    Args:
        value: Value to check
        field_name: Name of the field being validated
        error_message: Custom error message (optional)

    Raises:
        ValidationError: If value is empty
    """
    if not value:
        message = error_message or f"{field_name} cannot be empty"
        raise ValidationError(
            message=message,
            error_code=ErrorCode.NO_ITEMS_FOUND if "items" in field_name.lower() else ErrorCode.VALIDATION_FAILED,
            details={"field": field_name}
        )


# Error Propagation Utility
def propagate_error_if_present(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Check if result contains an error and return it if present.

    This is useful for cascading operations where one failure should stop execution.

    Args:
        result: Result dictionary to check

    Returns:
        The error dict if present, None otherwise

    Example:
        current_request = self.get_rfq_request(request_uuid=request_uuid)
        if error := propagate_error_if_present(current_request):
            return error
    """
    if isinstance(result, dict) and "error" in result:
        return result
    return None
