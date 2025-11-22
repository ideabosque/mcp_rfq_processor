#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP Configuration for RFQ Processor"""

__author__ = "bibow"

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
                    "email": {
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
                        "description": "Request status (default: initial)",
                        "enum": ["initial", "in_progress", "confirmed", "completed", "modified"],
                    },
                },
                "required": ["email", "request_title"],
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
                        "description": "Updated contact email address (passed through to GraphQL email field)",
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
                            "initial",
                            "in_progress",
                            "confirmed",
                            "completed",
                            "modified",
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
                        "description": "Item object to add with item_uuid, item_name, and qty",
                        "properties": {
                            "item_uuid": {
                                "type": "string",
                                "description": "UUID of the item",
                            },
                            "item_name": {
                                "type": "string",
                                "description": "Name of the item",
                            },
                            "qty": {
                                "type": "integer",
                                "description": "Quantity of the item",
                            },
                        },
                        "required": ["item_uuid", "item_name", "qty"],
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
        {
            "name": "assign_provider_item_to_request_item",
            "description": "Assign a provider item to a specific item in an RFQ request. Adds the provider item to the item's provider_items array with optional batch number and quantity. If the provider item already exists (with matching batch_no), quantity can be added or replaced based on add_qty flag. Returns the updated request with status set to 'modified'.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "request_uuid": {
                        "type": "string",
                        "description": "UUID of the request to update",
                    },
                    "item_uuid": {
                        "type": "string",
                        "description": "UUID of the item in the request to assign provider item to",
                    },
                    "provider_item_uuid": {
                        "type": "string",
                        "description": "UUID of the provider item to assign",
                    },
                    "provider_corp_external_id": {
                        "type": "string",
                        "description": "Provider corporation external ID",
                    },
                    "batch_no": {
                        "type": "string",
                        "description": "Optional batch number for the provider item",
                    },
                    "qty": {
                        "type": "integer",
                        "description": "Optional quantity for this provider item (defaults to item qty if not specified)",
                    },
                    "add_qty": {
                        "type": "boolean",
                        "description": "If true, add to existing quantity; if false, replace quantity (default: false)",
                    },
                },
                "required": [
                    "request_uuid",
                    "item_uuid",
                    "provider_item_uuid",
                    "provider_corp_external_id",
                ],
            },
        },
        {
            "name": "remove_provider_item_from_request_item",
            "description": "Remove provider item assignment from a specific item in an RFQ request. Removes the provider item from the item's provider_items array. If provider_item_uuid is not specified, removes all provider items. If batch_no is not specified, removes all instances of the provider_item_uuid regardless of batch. Returns the updated request with status set to 'modified'.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "request_uuid": {
                        "type": "string",
                        "description": "UUID of the request to update",
                    },
                    "item_uuid": {
                        "type": "string",
                        "description": "UUID of the item in the request to remove provider item from",
                    },
                    "provider_item_uuid": {
                        "type": "string",
                        "description": "UUID of the provider item to remove (optional, removes all provider items if not specified)",
                    },
                    "batch_no": {
                        "type": "string",
                        "description": "Optional batch number to match. If not specified, removes all instances of the provider_item_uuid regardless of batch",
                    },
                },
                "required": ["request_uuid", "item_uuid"],
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
            "description": "Search provider inventory with batch information merged. For each provider item, fetches and merges batch information including slow_move_item flags and guardrail pricing. Each batch includes: batch_no, expired_at, produced_at, slow_move_item, guardrail_price_per_uom. Optional batch filters can be applied when fetching batches. If expired_at_gt not provided, defaults to batches expiring 90+ days from now.",
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
                    "expired_at_gt": {
                        "type": "string",
                        "description": "Filter batches expiring after this date (ISO 8601 format)",
                    },
                    "slow_move_item": {
                        "type": "boolean",
                        "description": "Filter for slow-moving inventory (default: false)",
                    },
                    "in_stock": {
                        "type": "boolean",
                        "description": "Filter for in-stock batches (default: true)",
                    },
                },
                "required": ["item_uuid"],
            },
        },
        # Quote Management Tools (3)
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
                    "segment_uuid": {
                        "type": "string",
                        "description": "Customer segment UUID for pricing",
                    },
                    "sales_rep_email": {
                        "type": "string",
                        "description": "Email of the sales representative",
                    },
                    "status": {
                        "type": "string",
                        "description": "Quote status (default: initial)",
                        "enum": [
                            "initial",
                            "in_progress",
                            "confirmed",
                            "completed",
                            "disapproved",
                        ],
                    },
                    "notes": {"type": "string", "description": "Additional notes"},
                },
                "required": [
                    "request_uuid",
                    "provider_corp_external_id",
                    "segment_uuid",
                ],
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
                            "initial",
                            "in_progress",
                            "confirmed",
                            "completed",
                            "disapproved",
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
                    },
                    "request_uuid": {
                        "type": "string",
                        "description": "UUID of the request (optional, may be required by some GraphQL schemas)",
                    },
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
            "description": "Update quote item discount only. Returns updated item totals with slow_move_item flag (indicates slow-moving inventory) and guardrail_price_per_uom (minimum acceptable price for profitability).",
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
                    "request_uuid": {
                        "type": "string",
                        "description": "UUID of the request",
                    },
                    "discount_amount": {
                        "type": "number",
                        "description": "Discount amount (subtotal discount)",
                    },
                },
                "required": ["quote_uuid", "quote_item_uuid"],
            },
        },
        # Pricing Tools (3)
        {
            "name": "get_item_price_tiers",
            "description": "Get active tiered pricing for items based on item, provider, customer segments, and quantity ranges. Returns applicable price tiers with margin information. Typically used via calculate_quote_pricing, but can be called directly to explore volume pricing scenarios or answer 'what if' questions.",
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
                    "provider_item_uuid": {
                        "type": "string",
                        "description": "Filter by provider item UUID",
                    },
                    "segment_uuid": {
                        "type": "string",
                        "description": "Filter by customer segment UUID",
                    },
                    "quantity_value": {
                        "type": "number",
                        "description": "Find the price tier that matches this specific quantity value (finds tiers where quantity_greater_then <= value < quantity_less_then)",
                    },
                    "min_price": {
                        "type": "number",
                        "description": "Filter tiers where price_per_uom is at least this value",
                    },
                    "max_price": {
                        "type": "number",
                        "description": "Filter tiers where price_per_uom is at most this value",
                    },
                },
                "required": ["item_uuid", "provider_item_uuid", "segment_uuid"],
            },
        },
        {
            "name": "get_discount_rules",
            "description": "Get applicable discount rules based on item, provider item, segment, and subtotal/discount thresholds. Returns discount rules with subtotal ranges and maximum discount percentages. By default, only active rules are returned. Typically used via calculate_quote_pricing, but can be called directly to explore discount options or check rules for specific scenarios.",
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
                    "provider_item_uuid": {
                        "type": "string",
                        "description": "Filter by provider item UUID",
                    },
                    "segment_uuid": {
                        "type": "string",
                        "description": "Filter by customer segment UUID",
                    },
                    "subtotal_value": {
                        "type": "number",
                        "description": "Find the discount rule that matches this specific subtotal value (finds rules where subtotal_greater_than <= value < subtotal_less_than)",
                    },
                    "max_discount_percentage": {
                        "type": "number",
                        "description": "Filter rules where max_discount_percentage is at most this value",
                    },
                    "min_discount_percentage": {
                        "type": "number",
                        "description": "Filter rules where max_discount_percentage is at least this value",
                    },
                },
                "required": ["item_uuid", "provider_item_uuid", "segment_uuid"],
            },
        },
        {
            "name": "calculate_quote_pricing",
            "description": "Calculate pricing information for an RFQ request grouped by provider and segment. Reads from request items with provider_items arrays, groups by (provider_corp_external_id, segment_uuid), and provides group-level subtotals, item-level details with price tiers, and applicable discount rules. Returns pricing structure for LLM to analyze and discuss options with end user. Does NOT apply discounts - only provides information.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "request_uuid": {
                        "type": "string",
                        "description": "UUID of the RFQ request",
                    },
                    "segment_uuid": {
                        "type": "string",
                        "description": "Customer segment for pricing (required for discount rules and price tiers)",
                    },
                },
                "required": ["request_uuid", "segment_uuid"],
            },
        },
        # Installment Tools (3)
        {
            "name": "create_installment",
            "description": "Create payment installment for a quote. If installment_amount not provided, uses remaining balance (final_total_quote_amount - existing_installments_total). If provided, uses the lesser of requested amount or remaining balance (auto-caps). Priority auto-increments based on existing installments. Sets due_date to current time. Typically created when quote status changes to 'confirmed'. Returns created installment details.",
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
                    "installment_amount": {
                        "type": "number",
                        "description": "Optional installment amount. If not provided, uses remaining balance. If provided and exceeds remaining balance, automatically capped at remaining balance. Must be > 0.",
                    },
                    "payment_method": {
                        "type": "string",
                        "description": "Payment method for this installment (e.g., credit_card, bank_transfer, check, cash)",
                    },
                    "status": {
                        "type": "string",
                        "description": "Installment status (default: pending)",
                        "enum": ["pending", "paid", "cancelled"],
                    },
                },
                "required": ["quote_uuid", "request_uuid"],
            },
        },
        {
            "name": "update_installment",
            "description": "Update installment status and sales order number. Used to mark installments as paid or cancelled, and to link them to sales orders. Returns updated installment details.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "quote_uuid": {
                        "type": "string",
                        "description": "UUID of the quote",
                    },
                    "installment_uuid": {
                        "type": "string",
                        "description": "UUID of the installment to update",
                    },
                    "status": {
                        "type": "string",
                        "description": "Installment status",
                        "enum": ["pending", "paid", "cancelled"],
                    },
                    "salesorder_no": {
                        "type": "string",
                        "description": "Sales order number to link to this installment",
                    },
                    "payment_method": {
                        "type": "string",
                        "description": "Payment method for this installment (e.g., credit_card, bank_transfer, check, cash)",
                    },
                },
                "required": ["quote_uuid", "installment_uuid"],
            },
        },
        {
            "name": "create_installments",
            "description": "Create multiple payment installments for a quote based on payment schedule. Calculates remaining balance (final_total_quote_amount - existing_installments_total) and divides equally across installments. Scheduled dates are calculated based on interval and total pay period (e.g., monthly intervals over 12 months). Priority auto-increments for each installment. All installments created with status 'pending'. Returns list of created installments.",
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
                    "interval_num": {
                        "type": "integer",
                        "description": "Number of installments to create (e.g., 12 for monthly payments over a year)",
                    },
                    "total_pay_period": {
                        "type": "integer",
                        "description": "Total payment period in months (e.g., 12 for one year, 24 for two years)",
                    },
                    "payment_method": {
                        "type": "string",
                        "description": "Payment method for all installments (e.g., credit_card, bank_transfer, check, cash)",
                    },
                },
                "required": [
                    "quote_uuid",
                    "request_uuid",
                    "interval_num",
                    "total_pay_period",
                ],
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
        # Convenience/Workflow Tools (2)
        {
            "name": "confirm_request_and_create_quotes",
            "description": "Convenience function to confirm an RFQ request and create quotes for selected providers in one operation. This combines update_rfq_request (to confirmed status) and create_quote (for each provider). Returns confirmed request and list of created quotes with full details.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "request_uuid": {
                        "type": "string",
                        "description": "UUID of the RFQ request to confirm",
                    },
                    "provider_corp_external_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of provider corporation external IDs to create quotes for",
                    },
                    "segment_uuid": {
                        "type": "string",
                        "description": "Customer segment UUID for pricing",
                    },
                },
                "required": [
                    "request_uuid",
                    "provider_corp_external_ids",
                    "segment_uuid",
                ],
            },
        },
        {
            "name": "confirm_quote_and_create_installments",
            "description": "Convenience function to confirm a quote and create installment plan in one operation. This combines update_quote (to confirmed status) and either create_installment or create_installments. Returns confirmed quote and created installments.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "request_uuid": {
                        "type": "string",
                        "description": "UUID of the request",
                    },
                    "quote_uuid": {
                        "type": "string",
                        "description": "UUID of the quote to confirm",
                    },
                    "create_single_installment": {
                        "type": "boolean",
                        "description": "If true, creates one installment for full amount (default: true)",
                    },
                    "interval_num": {
                        "type": "integer",
                        "description": "Number of installments (required if create_single_installment=false)",
                    },
                    "total_pay_period": {
                        "type": "integer",
                        "description": "Total payment period in months (required if create_single_installment=false)",
                    },
                    "payment_method": {
                        "type": "string",
                        "description": "Optional payment method for installments",
                    },
                },
                "required": ["request_uuid", "quote_uuid"],
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
        # Segment Tools (1)
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
                    "consumer_corp_external_id": {
                        "type": "string",
                        "description": "Filter by consumer corporation external ID",
                    },
                    "email": {
                        "type": "string",
                        "description": "Contact email address (required)",
                    },
                },
                "required": ["email"],
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
        {
            "type": "tool",
            "name": "assign_provider_item_to_request_item",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "assign_provider_item_to_request_item",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "remove_provider_item_from_request_item",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "remove_provider_item_from_request_item",
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
        # Quote Management Tools
        {
            "type": "tool",
            "name": "create_quote",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "_create_quote",
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
            "function_name": "_create_installment",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "update_installment",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "update_installment",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "create_installments",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "_create_installments",
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
        # Convenience/Workflow Tools
        {
            "type": "tool",
            "name": "confirm_request_and_create_quotes",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "confirm_request_and_create_quotes",
            "return_type": "text",
        },
        {
            "type": "tool",
            "name": "confirm_quote_and_create_installments",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "confirm_quote_and_create_installments",
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
