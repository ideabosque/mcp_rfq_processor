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
                    "total_amount": {
                        "type": "number",
                        "description": "Total amount for the request",
                    },
                    "total_discount": {
                        "type": "number",
                        "description": "Total discount applied",
                    },
                    "final_total_amount": {
                        "type": "number",
                        "description": "Final total amount after discounts",
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
            "description": "Update existing RFQ request. Use when modifying request details or items (note: changing items requires creating a new quote). Returns updated request information.",
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
                    "total_amount": {
                        "type": "number",
                        "description": "Updated total amount",
                    },
                    "total_discount": {
                        "type": "number",
                        "description": "Updated total discount",
                    },
                    "final_total_amount": {
                        "type": "number",
                        "description": "Updated final total amount",
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
            "description": "Get batch/lot information for provider items. Useful for tracking inventory batches and lot numbers.",
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
            "description": "Create new quote for RFQ request. IMPORTANT: Items cannot be added/deleted after creation. To modify items, update the request and create a new quote. Returns quote UUID and total amount.",
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
                    "shipping_method": {
                        "type": "string",
                        "description": "Shipping method (default: standard)",
                    },
                    "shipping_amount": {
                        "type": "number",
                        "description": "Shipping cost",
                    },
                    "tax_amount": {"type": "number", "description": "Tax amount"},
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
                    "items": {
                        "type": "array",
                        "description": "Quote items to create",
                        "items": {
                            "type": "object",
                            "properties": {
                                "item_uuid": {"type": "string"},
                                "provider_item_uuid": {"type": "string"},
                                "quantity": {"type": "integer"},
                                "unit_price": {"type": "number"},
                            },
                            "required": [
                                "item_uuid",
                                "provider_item_uuid",
                                "quantity",
                                "unit_price",
                            ],
                        },
                    },
                },
                "required": ["request_uuid", "provider_corp_external_id"],
            },
        },
        {
            "name": "update_quote",
            "description": "Update quote metadata (shipping, tax, status, notes). Cannot modify quote items - use update_quote_item_discount for item discounts. Returns updated quote information.",
            "inputSchema": {
                "type": "object",
                "properties": {
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
                    "tax_amount": {
                        "type": "number",
                        "description": "Updated tax amount",
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
                "required": ["quote_uuid"],
            },
        },
        {
            "name": "get_quote",
            "description": "Retrieve detailed quote information by UUID. Returns complete quote data including items and installments.",
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
            "name": "update_quote_item_discount",
            "description": "Update discount for a specific quote item. This is the ONLY allowed modification to quote items after creation. Can set discount amount or percentage. Returns updated item totals.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "quote_item_uuid": {
                        "type": "string",
                        "description": "UUID of the quote item to update",
                    },
                    "discount_amount": {
                        "type": "number",
                        "description": "Fixed discount amount",
                    },
                    "discount_percent": {
                        "type": "number",
                        "description": "Percentage discount (0-100)",
                    },
                    "discount_notes": {
                        "type": "string",
                        "description": "Notes about the discount",
                    },
                },
                "required": ["quote_item_uuid"],
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
                    "installment_number": {
                        "type": "integer",
                        "description": "Installment sequence number",
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Payment due date (ISO 8601 format)",
                    },
                    "amount": {"type": "number", "description": "Installment amount"},
                    "status": {
                        "type": "string",
                        "description": "Installment status (default: pending)",
                        "enum": ["pending", "paid", "overdue", "cancelled"],
                    },
                },
                "required": ["quote_uuid", "installment_number", "due_date", "amount"],
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
            "description": "Upload document attachment to RFQ request (quotes, specifications, terms). Returns file UUID and URL.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "request_uuid": {
                        "type": "string",
                        "description": "UUID of the request",
                    },
                    "file_name": {"type": "string", "description": "Name of the file"},
                    "file_type": {
                        "type": "string",
                        "description": "File type/category",
                    },
                    "file_data": {
                        "type": "string",
                        "description": "Base64 encoded file data",
                    },
                },
                "required": ["request_uuid", "file_name", "file_type", "file_data"],
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
                        "description": "UUID of the contact",
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
            "name": "update_quote_item_discount",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "update_quote_item_discount",
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
            raise Exception(
                f"Failed to fetch GraphQL schema: {function_name}/{self.endpoint_id}. Please check the configuration and ensure all required settings are properly. Error: {e}"
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
        except Exception as e:
            log = traceback.format_exc()
            self.logger.error(log)
            raise Exception(
                f"Failed to execute GraphQL query ({function_name}/{self.endpoint_id}). Error: {e}"
            )

    # ==================== Request Management Tools ====================

    # * MCP Function.
    def submit_rfq_request(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit new RFQ request.
        Maps to GraphQL: insertUpdateRequest mutation
        """
        try:
            self.logger.info(f"Submitting RFQ request: {arguments}")

            variables = {
                "email": arguments["contact_uuid"],
                "requestTitle": arguments["request_title"],
                "requestDescription": arguments.get("request_description", ""),
                "billingAddress": arguments.get("billing_address"),
                "shippingAddress": arguments.get("shipping_address"),
                "items": arguments.get("items"),
                "totalAmount": arguments.get("total_amount"),
                "totalDiscount": arguments.get("total_discount"),
                "finalTotalAmount": arguments.get("final_total_amount"),
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

            request = humps.decamelize(result["insertUpdateRequest"]["request"])

            return request
        except Exception as e:
            self.logger.error(f"Failed to submit RFQ: {e}")
            raise

    # * MCP Function.
    def update_rfq_request(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update existing RFQ request.
        Maps to GraphQL: insertUpdateRequest mutation

        Use this when:
        - Modifying request details
        - Changing requested items (requires creating new quote)
        - Updating deadline or description
        """
        try:
            self.logger.info(f"Updating RFQ request: {arguments}")

            variables = {
                "requestUuid": arguments["request_uuid"],
                "email": arguments.get("contact_uuid"),
                "requestTitle": arguments.get("request_title"),
                "requestDescription": arguments.get("request_description"),
                "billingAddress": arguments.get("billing_address"),
                "shippingAddress": arguments.get("shipping_address"),
                "items": arguments.get("items"),
                "totalAmount": arguments.get("total_amount"),
                "totalDiscount": arguments.get("total_discount"),
                "finalTotalAmount": arguments.get("final_total_amount"),
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

            request = humps.decamelize(result["insertUpdateRequest"]["request"])

            return request
        except Exception as e:
            self.logger.error(f"Failed to update RFQ: {e}")
            raise

    # * MCP Function.
    def get_rfq_request(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieve RFQ request details.
        Maps to GraphQL: request query
        """
        try:
            result = self._execute_graphql_query(
                "ai_rfq_graphql",
                "request",
                "Query",
                {"requestUuid": arguments["request_uuid"]},
            )

            return humps.decamelize(result["request"])
        except Exception as e:
            self.logger.error(f"Failed to get request: {e}")
            raise

    # * MCP Function.
    def search_rfq_requests(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search RFQ requests with filters.
        Maps to GraphQL: requestList query
        """
        try:
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

            return humps.decamelize(result["requestList"])
        except Exception as e:
            self.logger.error(f"Failed to search requests: {e}")
            raise

    # ==================== Item Management Tools ====================

    # * MCP Function.
    def search_items(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search items catalog.
        Maps to GraphQL: itemList query
        """
        try:
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

            return humps.decamelize(result["itemList"])
        except Exception as e:
            self.logger.error(f"Failed to search items: {e}")
            raise

    # * MCP Function.
    def get_item(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get item details.
        Maps to GraphQL: item query
        """
        try:
            result = self._execute_graphql_query(
                "ai_rfq_graphql",
                "item",
                "Query",
                {"itemUuid": arguments["item_uuid"]},
            )

            return humps.decamelize(result["item"])
        except Exception as e:
            self.logger.error(f"Failed to get item: {e}")
            raise

    # * MCP Function.
    def get_provider_items(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search provider inventory.
        Maps to GraphQL: providerItemList query
        """
        try:
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

            return humps.decamelize(result["providerItemList"])
        except Exception as e:
            self.logger.error(f"Failed to get provider items: {e}")
            raise

    # * MCP Function.
    def get_provider_item_batches(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get batch information for provider items.
        Maps to GraphQL: providerItemBatchList query
        """
        try:
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

            return humps.decamelize(result["providerItemBatchList"])
        except Exception as e:
            self.logger.error(f"Failed to get provider item batches: {e}")
            raise

    # ==================== Quote Management Tools ====================

    # * MCP Function.
    def create_quote(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create new quote for RFQ request.
        Maps to GraphQL: insertUpdateQuote mutation

        Note: After creation, quote items cannot be added/deleted.
        To change items, update the request and create a new quote.
        """
        try:
            self.logger.info(f"Creating quote: {arguments}")

            variables = {
                "requestUuid": arguments["request_uuid"],
                "providerCorpExternalId": arguments["provider_corp_external_id"],
                "salesRepEmail": arguments.get("sales_rep_email"),
                "shippingMethod": arguments.get("shipping_method", "standard"),
                "shippingAmount": arguments.get("shipping_amount", 0.0),
                "negotiationRounds": arguments.get("negotiation_rounds", 0.0),
                "status": arguments.get("status", "draft"),
                "notes": arguments.get("notes", ""),
                "updatedBy": "MCP",
            }

            result = self._execute_graphql_query(
                "ai_rfq_graphql",
                "insertUpdateQuote",
                "Mutation",
                variables,
            )

            quote = humps.decamelize(result["insertUpdateQuote"]["quote"])

            return quote
        except Exception as e:
            self.logger.error(f"Failed to create quote: {e}")
            raise

    # * MCP Function.
    def update_quote(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update quote metadata (shipping, status, notes).
        Maps to GraphQL: insertUpdateQuote mutation

        Can update:
        - shipping_method, shipping_amount
        - negotiation_rounds
        - status
        - notes

        Cannot modify quote items - use update_quote_item_discount instead
        """
        try:
            self.logger.info(f"Updating quote: {arguments}")

            variables = {
                "requestUuid": arguments["request_uuid"],
                "quoteUuid": arguments["quote_uuid"],
                "shippingMethod": arguments.get("shipping_method"),
                "shippingAmount": arguments.get("shipping_amount"),
                "negotiationRounds": arguments.get("negotiation_rounds"),
                "status": arguments.get("status"),
                "notes": arguments.get("notes"),
                "updatedBy": "MCP",
            }

            # Remove None values to only update provided fields
            variables = {k: v for k, v in variables.items() if v is not None}

            result = self._execute_graphql_query(
                "ai_rfq_graphql",
                "insertUpdateQuote",
                "Mutation",
                variables,
            )

            quote = humps.decamelize(result["insertUpdateQuote"]["quote"])

            return quote
        except Exception as e:
            self.logger.error(f"Failed to update quote: {e}")
            raise

    # * MCP Function.
    def update_quote_item_discount(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update discount for a specific quote item.
        Maps to GraphQL: insertUpdateQuoteItem mutation

        This is the ONLY allowed modification to quote items after creation.
        To add/remove items, update the request and create a new quote.
        """
        try:
            self.logger.info(f"Updating quote item discount: {arguments}")

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

            quote_item = humps.decamelize(result["insertUpdateQuoteItem"]["quoteItem"])

            return quote_item
        except Exception as e:
            self.logger.error(f"Failed to update quote item discount: {e}")
            raise

    # * MCP Function.
    def get_quote(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieve quote details.
        Maps to GraphQL: quote query
        """
        try:
            result = self._execute_graphql_query(
                "ai_rfq_graphql",
                "quote",
                "Query",
                {"quoteUuid": arguments["quote_uuid"]},
            )

            return humps.decamelize(result["quote"])
        except Exception as e:
            self.logger.error(f"Failed to get quote: {e}")
            raise

    # * MCP Function.
    def search_quotes(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search quotes with filters.
        Maps to GraphQL: quoteList query
        """
        try:
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

            return humps.decamelize(result["quoteList"])
        except Exception as e:
            self.logger.error(f"Failed to search quotes: {e}")
            raise

    # ==================== Pricing Tools ====================

    # * MCP Function.
    def get_item_price_tiers(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get tiered pricing for items.
        Maps to GraphQL: itemPriceTierList query
        """
        try:
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

            return humps.decamelize(result["itemPriceTierList"])
        except Exception as e:
            self.logger.error(f"Failed to get item price tiers: {e}")
            raise

    # * MCP Function.
    def get_discount_rules(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get discount rules.
        Maps to GraphQL: discountRuleList query
        """
        try:
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

            return humps.decamelize(result["discountRuleList"])
        except Exception as e:
            self.logger.error(f"Failed to get discount rules: {e}")
            raise

    # * MCP Function.
    def calculate_quote_pricing(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate final pricing for a quote with discounts and tiers.
        This is a business logic method that combines multiple GraphQL queries.
        """
        try:
            self.logger.info(f"Calculating quote pricing: {arguments}")

            # Get the quote details
            quote = self.get_quote(quote_uuid=arguments["quote_uuid"])

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
                        "applicable_discounts": discount_rules.get(
                            "discount_rules", []
                        ),
                        "applicable_price_tiers": price_tiers.get(
                            "item_price_tiers", []
                        ),
                        "current_total": item["total_amount"],
                    }
                )

            return {
                "quote_uuid": quote["quote_uuid"],
                "pricing_details": pricing_details,
                "quote_total": quote["total_quote_amount"],
            }
        except Exception as e:
            self.logger.error(f"Failed to calculate quote pricing: {e}")
            raise

    # ==================== Installment Tools ====================

    # * MCP Function.
    def create_installment(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create payment installment.
        Maps to GraphQL: insertUpdateInstallment mutation
        """
        try:
            self.logger.info(f"Creating installment: {arguments}")

            variables = {
                "quoteUuid": arguments["quote_uuid"],
                "requestUuid": arguments.get("request_uuid"),
                "priority": arguments.get("installment_number"),
                "salesorderNo": arguments.get("salesorder_no"),
                "scheduledDate": arguments.get("due_date"),
                "installmentRatio": arguments.get("installment_ratio"),
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

            installment = humps.decamelize(
                result["insertUpdateInstallment"]["installment"]
            )

            return installment
        except Exception as e:
            self.logger.error(f"Failed to create installment: {e}")
            raise

    # * MCP Function.
    def get_installments(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get installment schedule.
        Maps to GraphQL: installmentList query
        """
        try:
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

            return humps.decamelize(result["installmentList"])
        except Exception as e:
            self.logger.error(f"Failed to get installments: {e}")
            raise

    # ==================== File Tools ====================

    # * MCP Function.
    def upload_rfq_file(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upload RFQ document.
        Maps to GraphQL: insertUpdateFile mutation
        """
        try:
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

            file_obj = humps.decamelize(result["insertUpdateFile"]["file"])

            return file_obj
        except Exception as e:
            self.logger.error(f"Failed to upload RFQ file: {e}")
            raise

    # * MCP Function.
    def get_rfq_files(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get RFQ files.
        Maps to GraphQL: fileList query
        """
        try:
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

            return humps.decamelize(result["fileList"])
        except Exception as e:
            self.logger.error(f"Failed to get RFQ files: {e}")
            raise

    # ==================== Segment Tools ====================

    # * MCP Function.
    def create_segment(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create pricing segment.
        Maps to GraphQL: insertUpdateSegment mutation
        """
        try:
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

            segment = humps.decamelize(result["insertUpdateSegment"]["segment"])

            return segment
        except Exception as e:
            self.logger.error(f"Failed to create segment: {e}")
            raise

    # * MCP Function.
    def add_contact_to_segment(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add contact to segment.
        Maps to GraphQL: insertUpdateSegmentContact mutation
        """
        try:
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

            segment_contact = humps.decamelize(
                result["insertUpdateSegmentContact"]["segmentContact"]
            )

            return segment_contact
        except Exception as e:
            self.logger.error(f"Failed to add contact to segment: {e}")
            raise

    # * MCP Function.
    def get_segment_contacts(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        List segment contacts.
        Maps to GraphQL: segmentContactList query
        """
        try:
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

            return humps.decamelize(result["segmentContactList"])
        except Exception as e:
            self.logger.error(f"Failed to get segment contacts: {e}")
            raise
