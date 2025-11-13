#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

__author__ = "bibow"

import logging
import traceback
from typing import Any, Dict

import boto3
import humps

from silvaengine_utility import Utility

# Import centralized error handling utilities
from .error_handler import (
    ErrorCode,
    GraphQLError,
    ValidationError,
    build_error_response,
    extract_error_message,
    handle_errors,
    propagate_error_if_present,
    validate_not_empty,
)

# MCP Configuration
MCP_CONFIGURATION = {
    "tools": [
        # Request Management Tools (4)
        {
            "name": "submit_rfq_request",
            "description": "Submit a new RFQ request with contact information, title, items, and optional description. Returns the created request UUID and status.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "contact_uuid": {
                        "type": "string",
                        "description": "Email address of the contact submitting the request",
                    },
                    "request_title": {
                        "type": "string",
                        "description": "Title of the RFQ request",
                    },
                    "request_description": {
                        "type": "string",
                        "description": "Detailed description of the request",
                    },
                    "billing_address": {
                        "type": "object",
                        "description": "Billing address (JSON object)",
                    },
                    "shipping_address": {
                        "type": "object",
                        "description": "Shipping address (JSON object)",
                    },
                    "items": {
                        "type": "array",
                        "description": "List of items in the request (array of JSON objects)",
                        "items": {"type": "object"},
                    },
                    "notes": {
                        "type": "string",
                        "description": "Additional notes",
                    },
                    "expired_at": {
                        "type": "string",
                        "description": "Expiration date (ISO 8601 format)",
                    },
                    "status": {
                        "type": "string",
                        "description": "Request status (default: pending)",
                        "enum": ["pending", "active", "completed", "cancelled"],
                    },
                },
                "required": ["contact_uuid", "request_title"],
            },
        },
        {
            "name": "update_rfq_request",
            "description": "Update existing RFQ request including title, description, addresses, notes, status, and items. For individual item modifications, you can also use add_item_to_rfq_request or remove_item_from_rfq_request. Returns updated request information.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "request_uuid": {
                        "type": "string",
                        "description": "UUID of the request to update",
                    },
                    "contact_uuid": {
                        "type": "string",
                        "description": "Updated contact email address",
                    },
                    "request_title": {
                        "type": "string",
                        "description": "Updated request title",
                    },
                    "request_description": {
                        "type": "string",
                        "description": "Updated request description",
                    },
                    "billing_address": {
                        "type": "object",
                        "description": "Updated billing address (JSON object)",
                    },
                    "shipping_address": {
                        "type": "object",
                        "description": "Updated shipping address (JSON object)",
                    },
                    "items": {
                        "type": "array",
                        "description": "Updated list of items (array of JSON objects)",
                        "items": {"type": "object"},
                    },
                    "notes": {
                        "type": "string",
                        "description": "Updated notes",
                    },
                    "expired_at": {
                        "type": "string",
                        "description": "Updated expiration date",
                    },
                    "status": {
                        "type": "string",
                        "description": "Updated status",
                        "enum": [
                            "pending",
                            "active",
                            "modified",
                            "completed",
                            "cancelled",
                        ],
                    },
                },
                "required": ["request_uuid"],
            },
        },
        {
            "name": "get_rfq_request",
            "description": "Retrieve detailed information about a specific RFQ request by UUID. Returns complete request data including quotes and files.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "request_uuid": {
                        "type": "string",
                        "description": "UUID of the request to retrieve",
                    }
                },
                "required": ["request_uuid"],
            },
        },
        {
            "name": "search_rfq_requests",
            "description": "Search and filter RFQ requests by contact, status, and date range. Returns paginated list of matching requests.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "page_number": {
                        "type": "integer",
                        "description": "Page number for pagination (default: 1)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Results per page (default: 20)",
                    },
                    "contact_uuid": {
                        "type": "string",
                        "description": "Filter by contact UUID",
                    },
                    "statuses": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by status list",
                    },
                    "from_expired_at": {
                        "type": "string",
                        "description": "Filter by expiration start date",
                    },
                    "to_expired_at": {
                        "type": "string",
                        "description": "Filter by expiration end date",
                    },
                },
            },
        },
        {
            "name": "add_item_to_rfq_request",
            "description": "Add a single item to an existing RFQ request. Automatically fetches the current request, adds the new item, and updates the request. Returns the updated request with status set to 'modified'.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "request_uuid": {
                        "type": "string",
                        "description": "UUID of the request to update",
                    },
                    "item": {
                        "type": "object",
                        "description": "Item object to add (JSON object with item details such as item_uuid, quantity, etc.)",
                    },
                },
                "required": ["request_uuid", "item"],
            },
        },
        {
            "name": "remove_item_from_rfq_request",
            "description": "Remove a single item from an existing RFQ request. Can remove by item UUID or item name. Returns the updated request with status set to 'modified'.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "request_uuid": {
                        "type": "string",
                        "description": "UUID of the request to update",
                    },
                    "item_uuid": {
                        "type": "string",
                        "description": "UUID of the item to remove (mutually exclusive with item_name)",
                    },
                    "item_name": {
                        "type": "string",
                        "description": "Name of the item to remove (mutually exclusive with item_uuid)",
                    },
                },
                "required": ["request_uuid"],
            },
        },
        # Item Management Tools (4)
        {
            "name": "search_items",
            "description": "Search available items in the catalog by type, name, or unit of measure. Returns paginated list of items with details.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "page_number": {
                        "type": "integer",
                        "description": "Page number (default: 1)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Results per page (default: 50)",
                    },
                    "item_type": {
                        "type": "string",
                        "description": "Filter by item type",
                    },
                    "item_name": {
                        "type": "string",
                        "description": "Search by item name",
                    },
                    "uoms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by units of measure",
                    },
                },
            },
        },
        {
            "name": "get_item",
            "description": "Get detailed information about a specific item by UUID. Returns complete item data including provider items and pricing.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "item_uuid": {
                        "type": "string",
                        "description": "UUID of the item to retrieve",
                    }
                },
                "required": ["item_uuid"],
            },
        },
        {
            "name": "get_provider_items",
            "description": "Search provider inventory for specific items. Returns available provider items with pricing and availability.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "page_number": {
                        "type": "integer",
                        "description": "Page number (default: 1)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Results per page (default: 50)",
                    },
                    "item_uuid": {
                        "type": "string",
                        "description": "Filter by item UUID",
                    },
                    "provider_corp_external_id": {
                        "type": "string",
                        "description": "Filter by provider ID",
                    },
                    "min_base_price_per_uom": {
                        "type": "number",
                        "description": "Minimum price filter",
                    },
                    "max_base_price_per_uom": {
                        "type": "number",
                        "description": "Maximum price filter",
                    },
                },
            },
        },
        {
            "name": "get_provider_item_batches",
            "description": "Get batch/lot information for provider items including slow_move_item flag and guardrail pricing. Useful for tracking inventory batches, lot numbers, and identifying slow-moving inventory that may need special pricing.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "page_number": {
                        "type": "integer",
                        "description": "Page number (default: 1)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Results per page (default: 50)",
                    },
                    "provider_item_uuid": {
                        "type": "string",
                        "description": "Filter by provider item UUID",
                    },
                    "batch_number": {
                        "type": "string",
                        "description": "Filter by batch number",
                    },
                },
            },
        },
        # Quote Management Tools (5)
        {
            "name": "create_quote",
            "description": "Create new quote for RFQ request. Returns quote UUID and total amount. Note: shipping_method and shipping_amount cannot be set during creation - use update_quote after creation to set these fields. The 'rounds' field (negotiation rounds) is automatically calculated by the backend.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "request_uuid": {
                        "type": "string",
                        "description": "UUID of the RFQ request",
                    },
                    "provider_corp_external_id": {
                        "type": "string",
                        "description": "Provider corporation external ID",
                    },
                    "sales_rep_email": {
                        "type": "string",
                        "description": "Email of the sales representative",
                    },
                    "status": {
                        "type": "string",
                        "description": "Quote status (default: draft)",
                        "enum": [
                            "draft",
                            "submitted",
                            "approved",
                            "rejected",
                            "superseded",
                        ],
                    },
                    "notes": {"type": "string", "description": "Additional notes"},
                },
                "required": ["request_uuid", "provider_corp_external_id"],
            },
        },
        {
            "name": "update_quote",
            "description": "Update quote metadata (shipping, status, notes). Returns updated quote information. Note: rounds (negotiation rounds) are auto-calculated by the backend based on existing quotes from the same provider.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "request_uuid": {
                        "type": "string",
                        "description": "UUID of the request",
                    },
                    "quote_uuid": {
                        "type": "string",
                        "description": "UUID of the quote to update",
                    },
                    "shipping_method": {
                        "type": "string",
                        "description": "Updated shipping method",
                    },
                    "shipping_amount": {
                        "type": "number",
                        "description": "Updated shipping cost",
                    },
                    "status": {
                        "type": "string",
                        "description": "Updated status",
                        "enum": [
                            "draft",
                            "submitted",
                            "approved",
                            "rejected",
                            "superseded",
                        ],
                    },
                    "notes": {"type": "string", "description": "Updated notes"},
                },
                "required": ["request_uuid", "quote_uuid"],
            },
        },
        {
            "name": "get_quote",
            "description": "Retrieve detailed quote information by UUID. Returns complete quote data including embedded quote_items array with slow_move_item flags and guardrail pricing, and installments.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "quote_uuid": {
                        "type": "string",
                        "description": "UUID of the quote to retrieve",
                    }
                },
                "required": ["quote_uuid"],
            },
        },
        {
            "name": "search_quotes",
            "description": "Search quotes with filters for request, provider, status, and date range. Returns paginated list of matching quotes.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "page_number": {
                        "type": "integer",
                        "description": "Page number (default: 1)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Results per page (default: 20)",
                    },
                    "request_uuid": {
                        "type": "string",
                        "description": "Filter by request UUID",
                    },
                    "provider_corp_external_id": {
                        "type": "string",
                        "description": "Filter by provider ID",
                    },
                    "statuses": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by status list",
                    },
                    "from_created_at": {
                        "type": "string",
                        "description": "Filter by creation start date",
                    },
                    "to_created_at": {
                        "type": "string",
                        "description": "Filter by creation end date",
                    },
                },
            },
        },
        {
            "name": "update_quote_item",
            "description": "Update quote item including quantity, discount, and other properties. Returns updated item totals with slow_move_item flag (indicates slow-moving inventory) and guardrail_price_per_uom (minimum acceptable price for profitability).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "quote_uuid": {
                        "type": "string",
                        "description": "UUID of the quote",
                    },
                    "quote_item_uuid": {
                        "type": "string",
                        "description": "UUID of the quote item to update",
                    },
                    "provider_item_uuid": {
                        "type": "string",
                        "description": "UUID of the provider item",
                    },
                    "item_uuid": {
                        "type": "string",
                        "description": "UUID of the item",
                    },
                    "segment_uuid": {
                        "type": "string",
                        "description": "UUID of the segment",
                    },
                    "batch_no": {
                        "type": "string",
                        "description": "Batch number",
                    },
                    "request_uuid": {
                        "type": "string",
                        "description": "UUID of the request",
                    },
                    "request_data": {
                        "type": "object",
                        "description": "Request data (JSON object)",
                    },
                    "qty": {
                        "type": "integer",
                        "description": "Quantity",
                    },
                    "discount_amount": {
                        "type": "number",
                        "description": "Discount amount (subtotal discount)",
                    },
                },
                "required": ["quote_uuid"],
            },
        },
        {
            "name": "add_quote_item",
            "description": "Add a new item to an existing quote. Returns the created quote item with calculated totals, slow_move_item flag (indicates slow-moving inventory), and guardrail_price_per_uom (minimum acceptable price). If batch_no is provided, these values come from the batch; otherwise slow_move_item defaults to false.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "quote_uuid": {
                        "type": "string",
                        "description": "UUID of the quote",
                    },
                    "provider_item_uuid": {
                        "type": "string",
                        "description": "UUID of the provider item",
                    },
                    "item_uuid": {
                        "type": "string",
                        "description": "UUID of the item",
                    },
                    "qty": {
                        "type": "integer",
                        "description": "Quantity",
                    },
                    "segment_uuid": {
                        "type": "string",
                        "description": "UUID of the segment (optional)",
                    },
                    "batch_no": {
                        "type": "string",
                        "description": "Batch number (optional)",
                    },
                    "request_data": {
                        "type": "object",
                        "description": "Request data (JSON object, optional)",
                    },
                    "discount_amount": {
                        "type": "number",
                        "description": "Discount amount (optional)",
                    },
                },
                "required": ["quote_uuid", "provider_item_uuid", "item_uuid", "qty"],
            },
        },
        {
            "name": "remove_quote_item",
            "description": "Remove an item from an existing quote. Returns success confirmation.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "quote_uuid": {
                        "type": "string",
                        "description": "UUID of the quote",
                    },
                    "quote_item_uuid": {
                        "type": "string",
                        "description": "UUID of the quote item to remove",
                    },
                },
                "required": ["quote_uuid", "quote_item_uuid"],
            },
        },
        # Pricing Tools (3)
        {
            "name": "get_item_price_tiers",
            "description": "Get tiered pricing for items based on quantity thresholds and customer segments. Returns applicable price tiers.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "page_number": {
                        "type": "integer",
                        "description": "Page number (default: 1)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Results per page (default: 50)",
                    },
                    "item_uuid": {
                        "type": "string",
                        "description": "Filter by item UUID",
                    },
                    "segment_uuid": {
                        "type": "string",
                        "description": "Filter by customer segment",
                    },
                    "min_quantity": {
                        "type": "integer",
                        "description": "Minimum quantity threshold",
                    },
                },
            },
        },
        {
            "name": "get_discount_rules",
            "description": "Get applicable discount rules based on item, segment, and date range. Returns active discount rules.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "page_number": {
                        "type": "integer",
                        "description": "Page number (default: 1)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Results per page (default: 50)",
                    },
                    "item_uuid": {
                        "type": "string",
                        "description": "Filter by item UUID",
                    },
                    "segment_uuid": {
                        "type": "string",
                        "description": "Filter by customer segment",
                    },
                    "valid_from": {"type": "string", "description": "Valid from date"},
                    "valid_to": {"type": "string", "description": "Valid to date"},
                },
            },
        },
        {
            "name": "calculate_quote_pricing",
            "description": "Calculate final pricing for a quote with applicable discounts and price tiers. Returns detailed pricing breakdown for each item.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "quote_uuid": {
                        "type": "string",
                        "description": "UUID of the quote",
                    },
                    "segment_uuid": {
                        "type": "string",
                        "description": "Customer segment for pricing",
                    },
                },
                "required": ["quote_uuid"],
            },
        },
        # Installment Tools (2)
        {
            "name": "create_installment",
            "description": "Create payment installment for a quote. Used to set up payment schedules. Returns created installment details.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "quote_uuid": {
                        "type": "string",
                        "description": "UUID of the quote",
                    },
                    "request_uuid": {
                        "type": "string",
                        "description": "UUID of the request",
                    },
                    "installment_number": {
                        "type": "integer",
                        "description": "Installment sequence number (priority)",
                    },
                    "salesorder_no": {
                        "type": "string",
                        "description": "Sales order number",
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Payment due date / scheduled date (ISO 8601 format)",
                    },
                    "amount": {
                        "type": "number",
                        "description": "Installment amount (installment_ratio will be auto-calculated based on quote total)",
                    },
                    "status": {
                        "type": "string",
                        "description": "Installment status (default: pending)",
                        "enum": ["pending", "paid", "overdue", "cancelled"],
                    },
                },
                "required": ["quote_uuid"],
            },
        },
        {
            "name": "get_installments",
            "description": "Get installment schedule for a quote. Returns paginated list of installments.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "page_number": {
                        "type": "integer",
                        "description": "Page number (default: 1)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Results per page (default: 50)",
                    },
                    "quote_uuid": {
                        "type": "string",
                        "description": "Filter by quote UUID",
                    },
                    "statuses": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by status list",
                    },
                },
            },
        },
        # File Tools (2)
        {
            "name": "upload_rfq_file",
            "description": "Upload document attachment to RFQ request (quotes, specifications, terms). Returns file UUID and metadata.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "request_uuid": {
                        "type": "string",
                        "description": "UUID of the request",
                    },
                    "file_name": {
                        "type": "string",
                        "description": "Name of the file",
                    },
                    "email": {
                        "type": "string",
                        "description": "Email of the uploader",
                    },
                },
                "required": ["request_uuid", "file_name"],
            },
        },
        {
            "name": "get_rfq_files",
            "description": "Get files associated with RFQ request. Returns paginated list of files with URLs.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "page_number": {
                        "type": "integer",
                        "description": "Page number (default: 1)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Results per page (default: 50)",
                    },
                    "request_uuid": {
                        "type": "string",
                        "description": "Filter by request UUID",
                    },
                    "file_type": {
                        "type": "string",
                        "description": "Filter by file type",
                    },
                },
            },
        },
        # Segment Tools (3)
        {
            "name": "create_segment",
            "description": "Create pricing segment for customer grouping. Used to apply segment-specific pricing and discounts. Returns created segment details.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "segment_uuid": {
                        "type": "string",
                        "description": "UUID of the segment (for updates)",
                    },
                    "provider_corp_external_id": {
                        "type": "string",
                        "description": "Provider corporation external ID",
                    },
                    "segment_name": {
                        "type": "string",
                        "description": "Name of the segment",
                    },
                    "segment_description": {
                        "type": "string",
                        "description": "Description of the segment",
                    },
                },
                "required": ["segment_name"],
            },
        },
        {
            "name": "add_contact_to_segment",
            "description": "Add contact to pricing segment. Associates customer with segment for pricing rules. Returns segment contact details.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "segment_uuid": {
                        "type": "string",
                        "description": "UUID of the segment",
                    },
                    "contact_uuid": {
                        "type": "string",
                        "description": "Email or UUID of the contact",
                    },
                    "contact_uuid_field": {
                        "type": "string",
                        "description": "UUID field of the contact",
                    },
                    "consumer_corp_external_id": {
                        "type": "string",
                        "description": "Consumer corporation external ID",
                    },
                },
                "required": ["segment_uuid", "contact_uuid"],
            },
        },
        {
            "name": "get_segment_contacts",
            "description": "List contacts in a pricing segment. Returns paginated list of segment contacts.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "page_number": {
                        "type": "integer",
                        "description": "Page number (default: 1)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Results per page (default: 50)",
                    },
                    "segment_uuid": {
                        "type": "string",
                        "description": "Filter by segment UUID",
                    },
                    "contact_uuid": {
                        "type": "string",
                        "description": "Filter by contact UUID",
                    },
                },
            },
        },
    ],
    "module_links": [
        # Request Management Tools
        {
            "type": "tool",
            "name": "submit_rfq_request",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "submit_rfq_request",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "update_rfq_request",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "update_rfq_request",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "get_rfq_request",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "get_rfq_request",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "search_rfq_requests",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "search_rfq_requests",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "add_item_to_rfq_request",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "add_item_to_rfq_request",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "remove_item_from_rfq_request",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "remove_item_from_rfq_request",
            "return_type": "text",
        },
        # Item Management Tools
        {
            "type": "tool",
            "name": "search_items",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "search_items",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "get_item",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "get_item",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "get_provider_items",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "get_provider_items",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "get_provider_item_batches",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "get_provider_item_batches",
            "return_type": "text",
        },
        # Quote Management Tools
        {
            "type": "tool",
            "name": "create_quote",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "create_quote",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "update_quote",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "update_quote",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "get_quote",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "get_quote",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "search_quotes",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "search_quotes",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "update_quote_item",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "update_quote_item",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "add_quote_item",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "add_quote_item",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "remove_quote_item",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "remove_quote_item",
            "return_type": "text",
        },
        # Pricing Tools
        {
            "type": "tool",
            "name": "get_item_price_tiers",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "get_item_price_tiers",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "get_discount_rules",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "get_discount_rules",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "calculate_quote_pricing",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "calculate_quote_pricing",
            "return_type": "text",
        },
        # Installment Tools
        {
            "type": "tool",
            "name": "create_installment",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "create_installment",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "get_installments",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "get_installments",
            "return_type": "text",
        },
        # File Tools
        {
            "type": "tool",
            "name": "upload_rfq_file",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "upload_rfq_file",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "get_rfq_files",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "get_rfq_files",
            "return_type": "text",
        },
        # Segment Tools
        {
            "type": "tool",
            "name": "create_segment",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "create_segment",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "add_contact_to_segment",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "add_contact_to_segment",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "get_segment_contacts",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "get_segment_contacts",
            "return_type": "text",
        },
    ],
    "modules": [
        {
            "package_name": "mcp_rfq_processor",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "setting": {},
        }
    ],
}


class MCPRfqProcessor:
    def __init__(self, logger: logging.Logger, **setting: Dict[str, Any]):
        self.logger = logger
        self.setting = setting
        self._endpoint_id = None
        self._schemas = {}
        self._aws_lambda = self._initialize_aws_lambda_client(**setting)

    @property
    def endpoint_id(self) -> str:
        return self._endpoint_id

    @endpoint_id.setter
    def endpoint_id(self, value: str):
        self._endpoint_id = value

    def _initialize_aws_lambda_client(self, **setting: Dict[str, Any]) -> boto3.client:
        region_name = setting.get("region_name")
        aws_access_key_id = setting.get("aws_access_key_id")
        aws_secret_access_key = setting.get("aws_secret_access_key")
        if region_name and aws_access_key_id and aws_secret_access_key:
            return boto3.client(
                "lambda",
                region_name=region_name,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
            )
        else:
            return boto3.client("lambda")

    def _fetch_graphql_schema(
        self,
        function_name: str,
    ) -> Dict[str, Any]:
        try:
            if self._schemas.get(function_name) is None:
                self._schemas[function_name] = Utility.fetch_graphql_schema(
                    self.logger,
                    self.endpoint_id,
                    function_name,
                    setting=self.setting,
                    execute_mode=self.setting.get("execute_mode"),
                    aws_lambda=self._aws_lambda,
                )
            return self._schemas[function_name]
        except Exception as e:
            log = traceback.format_exc()
            self.logger.error(log)
            raise GraphQLError(
                message=f"Failed to fetch GraphQL schema: {function_name}/{self.endpoint_id}. Please check the configuration and ensure all required settings are properly. Error: {e}",
                error_code=ErrorCode.GRAPHQL_SCHEMA_FETCH_FAILED,
                details={
                    "function_name": function_name,
                    "endpoint_id": self.endpoint_id,
                },
            )

    def _execute_graphql_query(
        self,
        function_name: str,
        operation_name: str,
        operation_type: str,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            schema = self._fetch_graphql_schema(function_name)
            query = Utility.generate_graphql_operation(
                operation_name, operation_type, schema
            )
            self.logger.info(f"Query: {query}/{function_name}")
            return Utility.execute_graphql_query(
                self.logger,
                self.endpoint_id,
                function_name,
                query,
                variables,
                setting=self.setting,
                execute_mode=self.setting.get("execute_mode"),
                aws_lambda=self._aws_lambda,
            )
        except GraphQLError as e:
            # GraphQL-specific errors from _fetch_graphql_schema
            log = traceback.format_exc()
            self.logger.error(log)
            return build_error_response(e.message, e.error_code, e.details)
        except Exception as e:
            # Other unexpected errors
            log = traceback.format_exc()
            self.logger.error(log)
            return build_error_response(
                extract_error_message(str(e)),
                ErrorCode.GRAPHQL_QUERY_FAILED,
                {"function_name": function_name, "operation": operation_name},
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
        """
        variables = {
            "pageNumber": arguments.get("page_number", 1),
            "limit": arguments.get("limit", 50),
            "providerItemUuid": arguments.get("provider_item_uuid"),
            "batchNumber": arguments.get("batch_number"),
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
        Create new quote for RFQ request.
        Maps to GraphQL: insertUpdateQuote mutation

        Note:
        - 'rounds' (negotiation rounds) is auto-calculated by backend based on existing quotes from the same provider
        - shipping_method and shipping_amount cannot be set during creation, use update_quote instead
        - After creation, quote items can be managed using add_quote_item, update_quote_item, and remove_quote_item
        """
        self.logger.info(f"Creating quote: {arguments}")

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

    # * MCP Function.
    @handle_errors(operation_name="add quote item")
    def add_quote_item(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
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
            "segmentUuid": arguments.get("segment_uuid"),
            "batchNo": arguments.get("batch_no"),
            "requestData": arguments.get("request_data"),
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

        self.logger.info(
            f"Successfully added quote item to quote {arguments['quote_uuid']}"
        )
        return quote_item

    # * MCP Function.
    @handle_errors(operation_name="remove quote item")
    def remove_quote_item(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
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
        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "quote",
            "Query",
            {"quoteUuid": arguments["quote_uuid"]},
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
        """
        variables = {
            "pageNumber": arguments.get("page_number", 1),
            "limit": arguments.get("limit", 50),
            "itemUuid": arguments.get("item_uuid"),
            "segmentUuid": arguments.get("segment_uuid"),
            "minQuantity": arguments.get("min_quantity"),
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
        """
        variables = {
            "pageNumber": arguments.get("page_number", 1),
            "limit": arguments.get("limit", 50),
            "itemUuid": arguments.get("item_uuid"),
            "segmentUuid": arguments.get("segment_uuid"),
            "validFrom": arguments.get("valid_from"),
            "validTo": arguments.get("valid_to"),
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
        Calculate final pricing for a quote with discounts and tiers.
        This is a business logic method that combines multiple GraphQL queries.
        """
        self.logger.info(f"Calculating quote pricing: {arguments}")

        # Get the quote details
        quote = self.get_quote(quote_uuid=arguments["quote_uuid"])

        # Check if quote has an error and propagate if present
        if error := propagate_error_if_present(quote):
            return error

        # For each quote item, get applicable discounts
        quote_items = quote.get("quote_items", [])
        pricing_details = []

        for item in quote_items:
            # Get discount rules for this item
            discount_rules = self.get_discount_rules(
                item_uuid=item["item_uuid"],
                segment_uuid=arguments.get("segment_uuid"),
            )

            # Get price tiers
            price_tiers = self.get_item_price_tiers(
                item_uuid=item["item_uuid"],
                segment_uuid=arguments.get("segment_uuid"),
                min_quantity=item["quantity"],
            )

            pricing_details.append(
                {
                    "quote_item_uuid": item["quote_item_uuid"],
                    "item_uuid": item["item_uuid"],
                    "quantity": item["quantity"],
                    "unit_price": item["unit_price"],
                    "applicable_discounts": discount_rules.get("discount_rules", []),
                    "applicable_price_tiers": price_tiers.get("item_price_tiers", []),
                    "current_total": item["total_amount"],
                }
            )

        return {
            "quote_uuid": quote["quote_uuid"],
            "pricing_details": pricing_details,
            "quote_total": quote["total_quote_amount"],
        }

    # ==================== Installment Tools ====================

    # * MCP Function.
    @handle_errors(operation_name="create installment")
    def create_installment(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create payment installment.
        Maps to GraphQL: insertUpdateInstallment mutation

        Note: installment_ratio is automatically calculated by the backend
        based on installment_amount / quote's final_total_quote_amount.
        """
        self.logger.info(f"Creating installment: {arguments}")

        variables = {
            "quoteUuid": arguments["quote_uuid"],
            "requestUuid": arguments.get("request_uuid"),
            "priority": arguments.get("installment_number"),
            "salesorderNo": arguments.get("salesorder_no"),
            "scheduledDate": arguments.get("due_date"),
            "installmentAmount": arguments.get("amount"),
            "status": arguments.get("status", "pending"),
            "updatedBy": "MCP",
        }

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
    @handle_errors(operation_name="create segment")
    def create_segment(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create pricing segment.
        Maps to GraphQL: insertUpdateSegment mutation
        """
        self.logger.info(f"Creating segment: {arguments}")

        variables = {
            "segmentUuid": arguments.get("segment_uuid"),
            "providerCorpExternalId": arguments.get("provider_corp_external_id"),
            "segmentName": arguments["segment_name"],
            "segmentDescription": arguments.get("segment_description", ""),
            "updatedBy": "MCP",
        }

        # Remove None values
        variables = {k: v for k, v in variables.items() if v is not None}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "insertUpdateSegment",
            "Mutation",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        segment = humps.decamelize(result["insertUpdateSegment"]["segment"])

        return segment

    # * MCP Function.
    @handle_errors(operation_name="add contact to segment")
    def add_contact_to_segment(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add contact to segment.
        Maps to GraphQL: insertUpdateSegmentContact mutation
        """
        self.logger.info(f"Adding contact to segment: {arguments}")

        variables = {
            "segmentUuid": arguments["segment_uuid"],
            "email": arguments["contact_uuid"],
            "contactUuid": arguments.get("contact_uuid_field"),
            "consumerCorpExternalId": arguments.get("consumer_corp_external_id"),
            "updatedBy": "MCP",
        }

        # Remove None values
        variables = {k: v for k, v in variables.items() if v is not None}

        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "insertUpdateSegmentContact",
            "Mutation",
            variables,
        )

        # Check for error in response and propagate if present
        if error := propagate_error_if_present(result):
            return error

        segment_contact = humps.decamelize(
            result["insertUpdateSegmentContact"]["segmentContact"]
        )

        return segment_contact

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
            "segmentUuid": arguments.get("segment_uuid"),
            "contactUuid": arguments.get("contact_uuid"),
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
