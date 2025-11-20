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
)

# Import status management

from .installment_processor import InstallmentProcessor

class FileProcessor(InstallmentProcessor):
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
