# MCP RFQ Processor

Model Context Protocol (MCP) server for processing Request for Quotation (RFQ) operations, providing AI assistants with tools to manage the complete RFQ lifecycle.

## Overview

The MCP RFQ Processor connects AI assistants to the `ai_rfq_engine` GraphQL backend, enabling intelligent automation of:

- **RFQ Request Management**: Submit, update, and track customer quotation requests with flexible item management
- **Item & Inventory Search**: Find available items and provider inventory with batch tracking
- **Quote Generation**: Create and manage detailed quotes with flexible item operations, pricing, and discounts
- **Installment Planning**: Set up payment schedules for quotes
- **Document Management**: Upload and track RFQ-related files
- **Segment Management**: Organize customers and providers into pricing segments

**Current Version**: 1.2.0
**Total MCP Tools**: 26 (fully implemented and tested)

### What's New in v1.2.0

**Workflow Restrictions:**
- **Quote Item Management**: Added status-based workflow restrictions
  - `initial` status: Only `add_quote_item` allowed (add new items to quote)
  - `in_progress` status: Only `update_quote_item` allowed (discount modifications only)
  - `remove_quote_item` functionality is deprecated and should not be used
- **Request Item Management**: Enhanced provider assignment workflow
  - Use `assign_provider_item_to_request_item` to assign providers to request items
  - Use `remove_provider_item_from_request_item` to remove provider assignments

### What's New in v1.1.0

**Status Management System:**
- **NEW: Comprehensive Status Management**: Enforces request/quote/installment status flows with transition validation
- **Status Constants**: RequestStatus, QuoteStatus, InstallmentStatus classes for type-safe status values
- **Automatic Business Rules**:
  - Auto-disapprove all quotes when request is modified
  - Auto-complete quote when all installments are paid
  - Auto-transition request to "in_progress" when items are modified
- **Operation Guards**: Prevent invalid operations (e.g., can't create quotes from non-confirmed requests)
- **Default Status Values**: Requests default to "initial", quotes default to "initial"

**API Improvements:**
- **Simplified Price Tier Lookup**: `get_item_price_tiers` now uses `quantity_value` parameter (finds matching tier for specific quantity)
- **Simplified Discount Rules**: `get_discount_rules` now uses `subtotal_value` parameter with required item/provider/segment parameters
- **Item-Level Discount Rules**: `calculate_quote_pricing` returns discount rules per item (based on item subtotal) instead of group-level

**Enhanced Testing:**
- Updated test suite to validate status transitions and business rules
- Tests for item-level discount rules in quote pricing

### v0.1.0 Features

**Major Features:**
- **Complete RFQ Workflow**: End-to-end request for quotation processing from customer inquiry to final quote submission
- **`calculate_quote_pricing` Tool**: Groups request items by provider/segment, returns pricing with applicable discount rules and price tiers for LLM-driven decision making
- **Flexible Quote Management**: Direct quote item operations (add/update/remove) for better usability
- **Comprehensive Testing**: Unit tests covering all 25 tools

**Backend Integration Features:**
- **Slow Move Item Tracking**: Automatically identify slow-moving inventory with `slow_move_item` flag and guardrail pricing
- **Auto-calculated Negotiation Rounds**: Backend automatically tracks quote `rounds` per provider
- **Auto-calculated Installment Ratio**: `installment_ratio` computed automatically based on `installment_amount` and quote total
- **Simplified Quote Creation**: `shipping_method` and `shipping_amount` can only be set via `update_quote`, not during creation

**Streamlined Tools (25 total):**
- **Removed**: `create_segment` and `add_contact_to_segment` (segments managed via backend admin)
- **Kept**: `get_segment_contacts` for read-only segment lookups
- **Added**: Convenience methods `add_item_to_rfq_request` and `remove_item_from_rfq_request`

See [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) for complete workflow documentation.

## Architecture

```
AI Assistant (Claude, etc.)
    ↓ MCP Protocol
MCP RFQ Processor (this package)
    ↓ GraphQL over AWS Lambda
ai_rfq_engine (backend)
    ↓
DynamoDB Tables
```

## Installation

### Prerequisites

- Python >= 3.8
- AWS credentials with Lambda execution permissions
- Access to deployed `ai_rfq_engine` GraphQL endpoint

### Install from Source

```bash
cd mcp_rfq_processor
pip install -e .
```

### Install Dependencies

```bash
pip install boto3 humps pendulum silvaengine-utility
```

## Configuration

### MCP Server Configuration

Add to your MCP settings file (e.g., `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "rfq_processor": {
      "command": "python",
      "args": ["-m", "mcp_rfq_processor"],
      "env": {
        "ENDPOINT_ID": "your-endpoint-id",
        "AWS_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "your-access-key",
        "AWS_SECRET_ACCESS_KEY": "your-secret-key"
      }
    }
  }
}
```

### Module Settings

When using as a Python module:

```python
from mcp_rfq_processor import MCPRfqProcessor
import logging

logger = logging.getLogger(__name__)

processor = MCPRfqProcessor(
    logger=logger,
    region_name="us-east-1",
    aws_access_key_id="your-access-key",
    aws_secret_access_key="your-secret-key",
    execute_mode="aws_lambda",  # or "local" for testing
    default_batch_expiration_filter_days=90,  # Default: 90 days (~3 months)
    installment_scheduled_day=15,  # Default: 15th day of month for installment schedules
)

processor.endpoint_id = "your-endpoint-id"
```

**Configuration Options:**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `region_name` | string | - | AWS region where Lambda functions are deployed |
| `aws_access_key_id` | string | - | AWS access key ID |
| `aws_secret_access_key` | string | - | AWS secret access key |
| `execute_mode` | string | - | Execution mode: `aws_lambda` or `local` |
| `default_batch_expiration_filter_days` | integer | 90 | Default minimum expiration days for `get_provider_item_batches`. When no expiration filters are provided, only returns batches expiring this many days or more in the future. |
| `installment_scheduled_day` | integer | 15 | Day of month (1-31) for scheduled installment dates in `create_installments`. If day doesn't exist in a month (e.g., Feb 31), uses last day of that month. |

## Available MCP Tools

All 25 tools are fully implemented and production-ready.

### 1. Request Management (6 tools)

#### `submit_rfq_request`
Submit a new RFQ request from a customer.

**Default Status**: `initial` - Request has been created but not yet being worked on.

**Input:**
```json
{
  "contact_uuid": "customer@example.com",
  "request_title": "Need 500 units of Product X",
  "request_description": "Detailed requirements...",
  "billing_address": {},
  "shipping_address": {},
  "items": [],
  "notes": "Urgent order",
  "expired_at": "2025-12-31T23:59:59Z",
  "status": "initial"
}
```

**Output:**
```json
{
  "request_uuid": "generated-uuid",
  "status": "initial",
  "created_at": "2025-11-05T10:30:00Z",
  "items": []
}
```

#### `update_rfq_request`
Update an existing RFQ request (title, description, addresses, items, status, etc.).

**Status Transitions**: All status changes are validated according to the request status flow.

**Automatic Business Rules**:
- When status changes to `modified`, all related quotes are automatically set to `disapproved`
- When items are modified while in `modified` status, automatically transitions to `in_progress`

**Input:**
```json
{
  "request_uuid": "request-uuid-string",
  "request_title": "Updated title",
  "items": [...],
  "status": "confirmed"
}
```

**Output:** Updated request object.

#### `add_item_to_rfq_request`
Convenience method to add a single item to an existing request.

**Input:**
```json
{
  "request_uuid": "request-uuid-string",
  "item": {
    "item_uuid": "item-uuid",
    "quantity": 100
  }
}
```

**Output:** Updated request with new item added.

#### `remove_item_from_rfq_request`
Convenience method to remove a single item from an existing request.

**Input:**
```json
{
  "request_uuid": "request-uuid-string",
  "item_uuid": "item-uuid-to-remove"
}
```

**Output:** Updated request with item removed.

#### `get_rfq_request`
Retrieve details of an existing RFQ request.

**Input:**
```json
{
  "request_uuid": "request-uuid-string"
}
```

**Output:** Complete request object with contact info and associated quotes.

#### `search_rfq_requests`
Search and filter RFQ requests.

**Input:**
```json
{
  "contact_uuid": "optional-contact-uuid",
  "statuses": ["pending", "quoted"],
  "from_expired_at": "2025-01-01T00:00:00Z",
  "to_expired_at": "2025-12-31T23:59:59Z",
  "page_number": 1,
  "limit": 20
}
```

**Output:** Paginated list of matching requests.

---

### 2. Item & Inventory Management (4 tools)

#### `search_items`
Search for available items in the catalog.

**Input:**
```json
{
  "item_type": "product",
  "item_name": "Widget",
  "uoms": ["EA", "BOX"],
  "page_number": 1,
  "limit": 50
}
```

**Output:** List of items with descriptions, types, and UOM options.

#### `get_item`
Get detailed information about a specific item.

**Input:**
```json
{
  "item_uuid": "item-uuid-string"
}
```

**Output:** Complete item details including pricing tiers.

#### `get_provider_items`
Search provider inventory with batch information merged.

For each provider item, automatically fetches and merges batch information including:
- **batches**: Array of batch details with slow_move_item flags and guardrail pricing
- Each batch includes: batch_no, expired_at, produced_at, slow_move_item, guardrail_price_per_uom

Optional batch filters (applied when fetching batches):
- **expired_at_gt**: Filter batches expiring after this date
- **expired_at_lt**: Filter batches expiring before this date  
- **slow_move_item**: Filter for slow-moving inventory (default: false)
- **in_stock**: Filter for in-stock batches (default: true)

**Input:**
```json
{
  "item_uuid": "optional-item-uuid",
  "provider_corp_external_id": "PROVIDER-001",
  "min_base_price_per_uom": 10.00,
  "max_base_price_per_uom": 50.00,
  "expired_at_gt": "2025-11-05T00:00:00Z",
  "slow_move_item": false,
  "in_stock": true,
  "page_number": 1,
  "limit": 50
}
```

**Output:** List of provider items with pricing, availability, and merged batch information.

**Note:** If no expiration filters provided, defaults to batches expiring 90+ days from now.

#### `get_provider_item_batches`
Get batch/lot information for provider items including slow_move_item flag and guardrail pricing.

**Input:**
```json
{
  "provider_item_uuid": "provider-item-uuid",
  "in_stock": true,
  "expired_at_gt": "2025-11-05T00:00:00Z"
}
```

**Output:** List of batches with lot numbers, expiry dates, and stock levels.

**Note:** If neither expired_at_gt nor expired_at_lt is provided, defaults to filtering batches expiring 90+ days from now.

#### `get_provider_item_batches`
Get batch information for provider inventory.

**Input:**
```json
{
  "provider_item_uuid": "provider-item-uuid",
  "in_stock": true,
  "expired_at_gt": "2025-11-05T00:00:00Z"
}
```

**Output:** List of batches with lot numbers, expiry dates, and stock levels.

---

### 3. Quote Management (8 tools)

#### `create_quote`
Generate a new quote for an RFQ request.

**Default Status**: `initial` - Quote has been created but not yet being worked on.

**Requirements**:
- Request must be in `confirmed` status to create quotes

**Note**:
- `shipping_method` and `shipping_amount` cannot be set during creation - use `update_quote` after creation
- `rounds` (negotiation rounds) is auto-calculated by the backend

**Input:**
```json
{
  "request_uuid": "request-uuid",
  "provider_corp_external_id": "PROVIDER-001",
  "sales_rep_email": "sales@provider.com",
  "status": "initial",
  "notes": "Initial quote"
}
```

**Output:**
```json
{
  "quote_uuid": "generated-quote-uuid",
  "request_uuid": "request-uuid",
  "rounds": 0,
  "total_quote_amount": 0.00,
  "status": "initial"
}
```

#### `get_quote`
Retrieve quote details.

**Input:**
```json
{
  "request_uuid": "request-uuid",
  "quote_uuid": "quote-uuid"
}
```

**Output:** Complete quote with line items, totals, and discount information.

#### `update_quote`
Update quote metadata (shipping, status, notes).

**Status Transitions**: All status changes are validated according to the quote status flow.

**Note**: `rounds` (negotiation rounds) is auto-calculated by the backend and cannot be manually set.

**Input:**
```json
{
  "request_uuid": "request-uuid",
  "quote_uuid": "quote-uuid",
  "shipping_method": "express",
  "shipping_amount": 75.00,
  "status": "confirmed",
  "notes": "Updated pricing and shipping"
}
```

**Output:** Updated quote object with auto-calculated `rounds`.

#### `search_quotes`
Search and filter quotes.

**Input:**
```json
{
  "request_uuid": "optional-request-uuid",
  "provider_corp_external_id": "PROVIDER-001",
  "statuses": ["submitted", "accepted"],
  "min_total_quote_amount": 1000.00,
  "page_number": 1,
  "limit": 20
}
```

**Output:** Paginated list of matching quotes.

#### `add_quote_item`
Add a line item to an existing quote.

**Requirements**:
- Quote must be in `initial` status to add new items
- Once quote moves to `in_progress` status, no new items can be added

**Input:**
```json
{
  "quote_uuid": "quote-uuid",
  "provider_item_uuid": "provider-item-uuid",
  "item_uuid": "item-uuid",
  "qty": 100,
  "batch_no": "BATCH-2025-001",
  "discount_amount": 50.00
}
```

**Output:** Created quote item with calculated totals.

#### `update_quote_item`
Update an existing quote item (discount amount only).

**Requirements**:
- Quote must be in `in_progress` status to apply discounts
- Only discount modifications are allowed (discount amount adjustments)

**Note**: Only `discount_amount` can be updated. Other fields (qty, provider_item_uuid, etc.) are read-only after creation.

**Input:**
```json
{
  "quote_uuid": "quote-uuid",
  "quote_item_uuid": "quote-item-uuid",
  "discount_amount": 75.00
}
```

**Output:** Updated quote item with recalculated totals.

---

### 4. Pricing & Discounts (3 tools)

#### `get_item_price_tiers`
Retrieve tiered pricing for an item.

**Note**: Typically used via `calculate_quote_pricing` which automatically filters by quantity. Direct use available for LLM-driven price exploration.

**Input:**
```json
{
  "item_uuid": "item-uuid",
  "provider_item_uuid": "optional-provider-item-uuid",
  "segment_uuid": "optional-segment-uuid",
  "quantity_value": 100,
  "min_price": "optional-float",
  "max_price": "optional-float"
}
```

**Parameters:**
- `quantity_value`: Find the price tier that matches this specific quantity (finds tiers where quantity_greater_then <= value < quantity_less_then)
- Other filters available for price range exploration

**Output:** List of price tiers (quantity ranges and prices).

**Updated in v1.1.0**: Simplified to use `quantity_value` parameter instead of min/max filters for finding matching tiers.

#### `get_discount_rules`
Get applicable discount rules for item-level pricing.

**Note**: Typically used via `calculate_quote_pricing` which automatically filters by item subtotal. Direct use available for LLM-driven discount exploration.

**Input:**
```json
{
  "item_uuid": "item-uuid",
  "provider_item_uuid": "provider-item-uuid",
  "segment_uuid": "segment-uuid",
  "subtotal_value": 1000.0,
  "max_discount_percentage": "optional-float",
  "min_discount_percentage": "optional-float"
}
```

**Required Parameters:**
- `item_uuid`: Item UUID (required for item-specific discount rules)
- `provider_item_uuid`: Provider item UUID (required for provider-specific pricing)
- `segment_uuid`: Customer segment UUID (required for segment-specific pricing)

**Optional Parameters:**
- `subtotal_value`: Find rules applicable to a specific subtotal amount (finds rules where subtotal_greater_than <= value < subtotal_less_than)
- `max_discount_percentage`: Filter by maximum discount percentage threshold
- `min_discount_percentage`: Filter by minimum discount percentage threshold

**Output:** List of discount rules with conditions and percentages (only 'active' status).

**Updated in v1.1.0**: Simplified to use `subtotal_value` parameter and made item/provider/segment parameters required.

#### `calculate_quote_pricing`
Calculate grouped pricing from request with provider_items, returning applicable discount rules and price tiers for LLM-driven decision making.

**Note**: This reads from REQUEST (not quote) and groups items by (provider_corp_external_id, segment_uuid). Use this BEFORE creating quotes (Step 7 in workflow).

**Input:**
```json
{
  "request_uuid": "request-uuid",
  "segment_uuid": "segment-uuid"
}
```

**Output:** Grouped pricing structure with item-level discount rules and price tiers.

```json
{
  "request_uuid": "req-uuid",
  "segment_uuid": "seg-uuid",
  "groups": [
    {
      "provider_corp_external_id": "PROVIDER-001",
      "items": [
        {
          "provider_item_uuid": "prov-item-uuid",
          "item_uuid": "item-uuid",
          "batch_no": "LOT-2025-001",
          "qty": 500,
          "price_per_uom": 9.50,
          "guardrail_price_per_uom": 9.50,
          "slow_move_item": true,
          "expired_at": "2026-03-15T00:00:00Z",
          "subtotal": 4750.00,
          "price_tiers": [...],
          "discount_rules": [...]
        }
      ],
      "subtotal": 4750.00
    }
  ],
  "subtotal": 4750.00
}
```

**Key Features:**
- Groups items by provider for multi-provider comparison
- Returns item-level discount_rules (based on item subtotal) and price_tiers WITHOUT applying them
- LLM presents options to user and applies discounts only after confirmation
- Includes batch-specific pricing with slow_move_item flags

**Updated in v1.1.0**: Discount rules moved to item-level (based on item subtotal) instead of group-level.

---

### 5. Installment Management (4 tools)

#### `create_installment`
Set up a payment installment for a quote.

**Requirements**:
- Quote must be in `confirmed` status to create installments

**Workflow:**
- Create installments with `status=pending` when quote status changes to `confirmed`
- Update installment `status=paid` when payment is received
- When all installments are `paid`, quote status is automatically set to `completed`

**Automatic Behavior:**
- **Amount**: If `installment_amount` not provided, uses full remaining balance. If provided, uses `min(requested_amount, remaining_balance)` (auto-caps at remaining balance)
- **Priority**: Automatically set to `max(existing_priorities) + 1` for sequential ordering (starts at 0 for first installment)
- **Due Date**: Automatically sets to current time (no need to specify)
- **installment_ratio**: Auto-calculated by backend based on `installment_amount` / `final_total_quote_amount`
- **Auto-Capping**: Requested amount > remaining balance automatically uses remaining balance instead

**Input Options:**

**Option 1: Full remaining balance (automatic)**
```json
{
  "quote_uuid": "quote-uuid",
  "request_uuid": "request-uuid",
  "status": "pending"
}
```

**Option 2: Partial installment (custom amount)**
```json
{
  "quote_uuid": "quote-uuid",
  "request_uuid": "request-uuid",
  "installment_amount": 3000.00,
  "status": "pending"
}
```

**Installment Status Values:**
- `pending`: Payment scheduled but not yet received (default when quote is confirmed)
- `paid`: Payment has been received and verified
- `cancelled`: Payment was cancelled or refunded

**Validation Rules:**
- **Without installment_amount**: Uses full remaining balance (`final_total_quote_amount - existing_pending_paid_total`)
- **With installment_amount**: Must be > 0. If exceeds remaining balance, automatically capped at remaining balance
- If remaining balance ≤ 0 (quote fully covered), installment creation is blocked
- Cancelled installments are not counted in the total
- Supports multiple partial installments that add up to quote total
- Auto-capping ensures you can never exceed quote total (safe to request any amount)

**Output:** Installment record with auto-calculated amount, due_date, and installment_ratio.

#### `update_installment`
Update installment status and sales order number.

**Status Transitions**: All status changes are validated according to the installment status flow.

**Automatic Business Rules**:
- When all installments are marked as `paid`, the quote is automatically set to `completed`

**Use Cases:**
- Mark installment as `paid` when payment is received
- Mark installment as `cancelled` if payment is cancelled or refunded
- Link installment to a sales order number for tracking

**Input:**
```json
{
  "quote_uuid": "quote-uuid",
  "installment_uuid": "installment-uuid",
  "status": "paid",
  "salesorder_no": "SO-12345"
}
```

**Common Usage:**
```json
// Mark as paid (triggers auto-complete check)
{
  "quote_uuid": "quote-uuid",
  "installment_uuid": "installment-uuid",
  "status": "paid"
}

// Link to sales order
{
  "quote_uuid": "quote-uuid",
  "installment_uuid": "installment-uuid",
  "salesorder_no": "SO-12345"
}

// Both at once
{
  "quote_uuid": "quote-uuid",
  "installment_uuid": "installment-uuid",
  "status": "paid",
  "salesorder_no": "SO-12345"
}
```

**Output:** Updated installment record.

#### `create_installments`
Create multiple payment installments for a quote based on a payment schedule. Automates the process of setting up installment plans (e.g., monthly payments over a year).

**Workflow:**
- Calculates remaining balance (`final_total_quote_amount - existing_pending_paid_total`)
- Divides remaining balance equally across `interval_num` installments
- Calculates scheduled dates based on `interval_num` and `total_pay_period`
- Creates all installments with `status=pending`
- Auto-increments priority for sequential ordering

**Automatic Behavior:**
- **Amount per installment**: `remaining_balance / interval_num` (equal distribution)
- **Scheduled dates**: First installment scheduled for the next payment period (not current period), then subsequent installments follow at regular intervals. All scheduled on the configured day of month (default: 15th) using `installment_scheduled_day` setting. If the day doesn't exist in a month (e.g., Feb 31), uses the last day of that month. Uses pendulum library for accurate date calculations.
- **Priority**: Auto-increments sequentially for each installment
- **Status**: All installments created with `pending` status

**Input:**
```json
{
  "quote_uuid": "quote-uuid",
  "request_uuid": "request-uuid",
  "interval_num": 12,
  "total_pay_period": 12
}
```

**Examples:**

**12 monthly payments over 1 year:**
```json
{
  "quote_uuid": "quote-uuid",
  "request_uuid": "request-uuid",
  "interval_num": 12,
  "total_pay_period": 12
}
// Creates 12 installments, scheduled monthly (every 1 month)
// First installment: Next month on 15th (or configured day)
// Last installment: 12 months from now on 15th
// Amount per installment: remaining_balance / 12
```

**6 bi-monthly payments over 1 year:**
```json
{
  "quote_uuid": "quote-uuid",
  "request_uuid": "request-uuid",
  "interval_num": 6,
  "total_pay_period": 12
}
// Creates 6 installments, scheduled bi-monthly (every 2 months)
// First installment: 2 months from now on 15th
// Last installment: 12 months from now on 15th
// Amount per installment: remaining_balance / 6
```

**4 quarterly payments over 2 years:**
```json
{
  "quote_uuid": "quote-uuid",
  "request_uuid": "request-uuid",
  "interval_num": 4,
  "total_pay_period": 24
}
// Creates 4 installments, scheduled every 6 months
// First installment: 6 months from now on 15th
// Last installment: 24 months from now on 15th
// Amount per installment: remaining_balance / 4
```

**Validation Rules:**
- `interval_num` must be > 0
- `total_pay_period` must be > 0
- Remaining balance must be > 0 (quote not already fully covered)
- If any installment creation fails, returns error with details of what was created

**Output:**
```json
{
  "installments": [ /* array of created installment objects */ ],
  "total_created": 12,
  "installment_amount_per": 833.33,
  "total_installment_amount": 10000.00
}
```

#### `get_installments`
Retrieve installments for a quote.

**Input:**
```json
{
  "quote_uuid": "quote-uuid"
}
```

**Output:** List of installments with payment schedule.

---

### 6. Document Management (2 tools)

#### `upload_rfq_file`
Upload a document related to an RFQ request.

**Input:**
```json
{
  "request_uuid": "request-uuid",
  "file_name": "specifications.pdf",
  "file_url": "s3://bucket/path/to/file",
  "file_type": "application/pdf",
  "email": "requester@company.com",
  "notes": "Technical specifications"
}
```

**Output:** File record with metadata.

#### `get_rfq_files`
Retrieve files associated with a request.

**Input:**
```json
{
  "request_uuid": "request-uuid"
}
```

**Output:** List of uploaded files with download URLs.

---

### 7. Segment Management (1 tool)

**Note:** Segments are typically managed through the backend admin interface. This tool provides read-only access to segment-contact associations for pricing lookups.

#### `get_segment_contacts`
List contacts in a segment by consumer corporation or email.

**Input:**
```json
{
  "consumer_corp_external_id": "CUSTOMER-001",
  "email": "buyer@customer.com",
  "page_number": 1,
  "limit": 50
}
```

**Output:** List of contacts with their segment associations.

---

## Usage Examples

### Complete RFQ to Quote Workflow

For the detailed 14-step workflow from customer inquiry to final quote confirmation, see [DEVELOPMENT_PLAN.md - Complete RFQ to Quote Workflow](DEVELOPMENT_PLAN.md#complete-rfq-to-quote-workflow).

**Quick Overview:**
0. Find Customer Segment
1. Submit RFQ Request
2. Lookup Items with End User
3. Add Items to Request
4. Lookup Provider Items for Each Item
5. Lookup Batches for Each Provider Item (Optional)
6. Assign Provider Items to Request Items
7. **Calculate Quote Pricing** (NEW - groups by provider/segment, returns discount rules)
8. Generate Quotes by Confirmation
9. Negotiate with End User
10. Apply Discounts with User Confirmation
11. Update Quote with Shipping
12. Confirm Quote and Generate Installment Plan
13. Complete Quote and Process Payment

### Practical Example: End-to-End Quote Generation

```python
# Step 0: Find customer segment
segment_contacts = processor.get_segment_contacts(
    consumer_corp_external_id="CUSTOMER-001",
    email="buyer@customer.com"
)
segment_uuid = segment_contacts[0]["segment_uuid"]

# Step 1-3: Create request and add items
request = processor.submit_rfq_request(
    contact_uuid="buyer@customer.com",
    request_title="Q1 Production Materials",
    items=[]
)
request_uuid = request["request_uuid"]

processor.add_item_to_rfq_request(
    request_uuid=request_uuid,
    item={"item_uuid": "item-uuid-1", "qty": 500}
)

# Step 4-6: Assign provider items to request
current_request = processor.get_rfq_request(request_uuid=request_uuid)
updated_items = current_request["items"].copy()
updated_items[0]["provider_items"] = [
    {
        "provider_corp_external_id": "PROVIDER-001",
        "provider_item_uuid": "prov-item-uuid-1",
        "batch_no": "LOT-2025-001",
        "qty": 500
    }
]
processor.update_rfq_request(request_uuid=request_uuid, items=updated_items)

# Step 7: Calculate pricing with discount rules (NEW)
pricing = processor.calculate_quote_pricing(
    request_uuid=request_uuid,
    segment_uuid=segment_uuid
)
# Returns grouped pricing with item-level discount_rules and price_tiers for LLM decision-making
# {
#   "groups": [{
#     "provider_corp_external_id": "PROVIDER-001",
#     "items": [{
#       "provider_item_uuid": "prov-item-uuid-1",
#       "item_uuid": "item-uuid-1",
#       "batch_no": "LOT-2025-001",
#       "qty": 500,
#       "price_per_uom": 9.50,
#       "guardrail_price_per_uom": 9.50,
#       "slow_move_item": true,
#       "expired_at": "2026-03-15T00:00:00Z",
#       "subtotal": 4750.00,
#       "price_tiers": [...],      # Available pricing tiers for this item
#       "discount_rules": [...]    # Applicable discount rules for this item (based on item subtotal)
#     }],
#     "subtotal": 4750.00
#   }],
#   "subtotal": 4750.00
# }

# Step 8-10: Create quote and add items with user-confirmed discount
quote = processor.create_quote(
    request_uuid=request_uuid,
    provider_corp_external_id="PROVIDER-001",
    sales_rep_email="sales@provider1.com"
)

processor.add_quote_item(
    quote_uuid=quote["quote_uuid"],
    provider_item_uuid="prov-item-uuid-1",
    item_uuid="item-uuid-1",
    segment_uuid=segment_uuid,
    qty=500,
    batch_no="LOT-2025-001",
    discount_amount=237.50  # 5% slow-move discount (user confirmed)
)

# Step 11: Add shipping
processor.update_quote(
    request_uuid=request_uuid,
    quote_uuid=quote["quote_uuid"],
    shipping_method="express",
    shipping_amount=75.00
)

# Step 12-13: Create installment plan and submit
# Installment automatically uses quote's final_total_quote_amount
processor.create_installment(
    request_uuid=request_uuid,
    quote_uuid=quote["quote_uuid"],
    status="pending"  # Default status when quote is confirmed
)

processor.update_quote(
    request_uuid=request_uuid,
    quote_uuid=quote["quote_uuid"],
    status="submitted"
)
```

### Key Principles

- **LLM-Driven**: LLM asks user questions at each step
- **Segment-Based**: Always identify customer segment first for correct pricing
- **Information Provider**: `calculate_quote_pricing` provides discount rules; LLM makes decisions with user input
- **User Confirmation**: Apply discounts only after user confirms
- **Multi-Provider**: Create separate quotes per provider for comparison

### AI Assistant Conversation Example

```
User: I need a quote for 500 units of part ABC-123