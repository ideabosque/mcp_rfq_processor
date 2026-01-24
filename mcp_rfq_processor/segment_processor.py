#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

__author__ = "bibow"

from typing import Any, Dict

import humps

# Import centralized error handling utilities
from .error_handler import handle_errors, propagate_error_if_present
from .file_processor import FileProcessor

SEGMENT_CONTACT = """query segmentContact($segmentUuid: String, $email: String!) {
	segmentContact(segmentUuid: $segmentUuid, email: $email) {
		partitionKey email contactUuid consumerCorpExternalId segmentUuid segment { 
			partitionKey endpointId partId segmentUuid providerCorpExternalId segmentName segmentDescription
		} updatedBy createdAt updatedAt
	}    
}"""
# Import status management


class SegmentProcessor(FileProcessor):
    # ==================== Segment Tools ====================

    # * MCP Function.
    @handle_errors(operation_name="get segment contacts")
    def get_segment_contacts(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        List segment contacts.
        Maps to GraphQL: segmentContactList query
        """
        # Email is required
        email = arguments.get("email")
        if not email:
            return {
                "error": {
                    "message": "Email is required for get_segment_contacts",
                    "error_code": "MISSING_REQUIRED_FIELD",
                    "details": {"field": "email"},
                }
            }

        consumer_corp_external_id = arguments.get("consumer_corp_external_id")
        if not consumer_corp_external_id or consumer_corp_external_id == "":
            variables = {
                "email": email,
            }
            result = self._execute_graphql_query(
                "ai_rfq_graphql",
                "segmentContact",
                "Query",
                variables,
                query=SEGMENT_CONTACT,
            )

            # Check for error in response and propagate if present
            if error := propagate_error_if_present(result):
                return error

            return humps.decamelize(result)

        variables = {
            "pageNumber": arguments.get("page_number", 1),
            "limit": arguments.get("limit", 50),
            "consumerCorpExternalId": consumer_corp_external_id,
            "email": email,
        }
        variables = {k: v for k, v in variables.items() if v is not None and v != ""}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "segmentContactList",
            "Query",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        return humps.decamelize(result)
