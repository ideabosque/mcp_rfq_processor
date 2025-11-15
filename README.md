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

**Current Version**: 0.1.1  
**Total MCP Tools**: 25 (fully implemented and tested)

### What's New in v0.1.1

**Major Features:**
- **NEW: `calculate_quote_pricing` Tool**: Groups request items by provider/segment, returns pricing with applicable discount rules and price tiers for LLM-driven decision making
- **Enhanced Pricing Filters**: `get_item_price_tiers` and `get_discount_rules` now support quantity/subtotal filtering parameters
- **14-Step RFQ to Quote Workflow**: Comprehensive workflow guide from customer inquiry to final quote submission

**Backend Integration Updates:**
- **Slow Move Item Tracking**: Automatically identify slow-moving inventory with `slow_move_item` flag and guardrail pricing
- **Auto-calculated Negotiation Rounds**: Backend now automatically tracks quote `rounds` per provider (renamed from `negociation_rounds`)
- **Auto-calculated Installment Ratio**: `installment_ratio` is now computed automatically based on `installment_amount` and quote total
- **Simplified Quote Creation**: `shipping_method` and `shipping_amount` can only be set via `update_quote`, not during creation

**Streamlined Tools (27→25):**
- **Removed**: `create_segment` and `add_contact_to_segment` (segments managed via backend admin)
- **Kept**: `get_segment_contacts` for read-only segment lookups

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

## Available MCP Tools

All 25 tools are fully implemented and production-ready.

### 1. Request Management (6 tools)

#### `submit_rfq_request`
Submit a new RFQ request from a customer.

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
  "status": "pending"
}
```

**Output:**
```json
{
  "request_uuid": "generated-uuid",
  "status": "pending",
  "created_at": "2025-11-05T10:30:00Z",
  "items": []
}
```

#### `update_rfq_request`
Update an existing RFQ request (title, description, addresses, items, status, etc.).

**Input:**
```json
{
  "request_uuid": "request-uuid-string",
  "request_title": "Updated title",
  "items": [...],
  "status": "modified"
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
Search provider inventory for specific items.

**Input:**
```json
{
  "item_uuid": "optional-item-uuid",
  "provider_corp_external_id": "PROVIDER-001",
  "min_base_price_per_uom": 10.00,
  "max_base_price_per_uom": 50.00,
  "page_number": 1,
  "limit": 50
}
```

**Output:** List of provider items with pricing, availability, and batch info.

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

**Note**:
- `shipping_method` and `shipping_amount` cannot be set during creation - use `update_quote` after creation
- `rounds` (negotiation rounds) is auto-calculated by the backend

**Input:**
```json
{
  "request_uuid": "request-uuid",
  "provider_corp_external_id": "PROVIDER-001",
  "sales_rep_email": "sales@provider.com",
  "status": "draft",
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
  "status": "draft"
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

**Note**: `rounds` (negotiation rounds) is auto-calculated by the backend and cannot be manually set.

**Input:**
```json
{
  "request_uuid": "request-uuid",
  "quote_uuid": "quote-uuid",
  "shipping_method": "express",
  "shipping_amount": 75.00,
  "status": "submitted",
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
Update an existing quote item (quantity, discount, etc.).

**Input:**
```json
{
  "quote_uuid": "quote-uuid",
  "quote_item_uuid": "quote-item-uuid",
  "qty": 150,
  "discount_amount": 75.00
}
```

**Output:** Updated quote item with recalculated totals.

#### `remove_quote_item`
Remove a line item from a quote.

**Input:**
```json
{
  "quote_uuid": "quote-uuid",
  "quote_item_uuid": "quote-item-uuid"
}
```

**Output:** Confirmation of deletion.

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
  "min_quantity_greater_then": "optional-int",
  "max_quantity_greater_then": "optional-int",
  "min_quantity_less_then": "optional-int",
  "max_quantity_less_then": "optional-int",
  "min_price": "optional-float",
  "max_price": "optional-float"
}
```

**Output:** List of price tiers (quantity ranges and prices).

**NEW in v0.1.1**: Added quantity and price filter parameters for more precise tier selection.

#### `get_discount_rules`
Get applicable discount rules.

**Note**: Typically used via `calculate_quote_pricing` which automatically filters by group subtotal. Direct use available for LLM-driven discount exploration.

**Input:**
```json
{
  "item_uuid": "item-uuid",
  "provider_item_uuid": "optional-provider-item-uuid",
  "segment_uuid": "optional-segment-uuid",
  "max_subtotal_greater_than": "optional-float",
  "min_subtotal_greater_than": "optional-float",
  "max_subtotal_less_than": "optional-float",
  "min_subtotal_less_than": "optional-float",
  "max_discount_percentage": "optional-float",
  "min_discount_percentage": "optional-float"
}
```

**Output:** List of discount rules with conditions and percentages.

**NEW in v0.1.1**: Added subtotal and percentage filter parameters for more precise rule selection.

#### `calculate_quote_pricing`
**NEW in v0.1.1**: Calculate grouped pricing from request with provider_items, returning applicable discount rules and price tiers for LLM-driven decision making.

**Note**: This reads from REQUEST (not quote) and groups items by (provider_corp_external_id, segment_uuid). Use this BEFORE creating quotes (Step 7 in workflow).

**Input:**
```json
{
  "request_uuid": "request-uuid",
  "segment_uuid": "segment-uuid"
}
```

**Output:** Grouped pricing structure with discount rules and price tiers.

```json
{
  "request_uuid": "req-uuid",
  "segment_uuid": "seg-uuid",
  "groups": [
    {
      "provider_corp_external_id": "PROVIDER-001",
      "segment_uuid": "seg-uuid",
      "items": [
        {
          "item_uuid": "item-uuid",
          "provider_item_uuid": "prov-item-uuid",
          "batch_no": "LOT-2025-001",
          "qty": 500,
          "price_per_uom": 9.50,
          "guardrail_price_per_uom": 9.50,
          "slow_move_item": true,
          "subtotal": 4750.00,
          "price_tiers": [...]
        }
      ],
      "subtotal": 4750.00,
      "discount_rules": [...]
    }
  ],
  "subtotal": 4750.00
}
```

**Key Features:**
- Groups items by provider and segment for multi-provider comparison
- Returns discount_rules and price_tiers WITHOUT applying them
- LLM presents options to user and applies discounts only after confirmation
- Includes batch-specific pricing with slow_move_item flags

---

### 5. Installment Management (2 tools)

#### `create_installment`
Set up a payment installment for a quote.

**Note**: `installment_ratio` is auto-calculated by the backend based on `installment_amount` / `final_total_quote_amount`.

**Input:**
```json
{
  "quote_uuid": "quote-uuid",
  "installment_number": 1,
  "salesorder_no": "SO-12345",
  "due_date": "2025-12-01T00:00:00Z",
  "amount": 3000.00,
  "status": "pending"
}
```

**Output:** Installment record with auto-calculated `installment_ratio`.

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
# Returns grouped pricing with discount_rules and price_tiers for LLM decision-making
# {
#   "groups": [{
#     "provider_corp_external_id": "PROVIDER-001",
#     "items": [{
#       "qty": 500,
#       "price_per_uom": 9.50,
#       "guardrail_price_per_uom": 9.50,
#       "slow_move_item": true,
#       "subtotal": 4750.00,
#       "price_tiers": [...]  # Available pricing tiers
#     }],
#     "subtotal": 4750.00,
#     "discount_rules": [...]  # Applicable discount rules
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
processor.create_installment(
    quote_uuid=quote["quote_uuid"],
    installment_number=1,
    due_date="2025-12-01T00:00:00Z",
    amount=2293.75  # 50% of final total
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