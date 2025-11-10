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
**Total MCP Tools**: 27 (fully implemented and tested)

### What's New in v0.1.1

- **Slow Move Item Tracking**: Automatically identify slow-moving inventory with `slow_move_item` flag and guardrail pricing
- **Auto-calculated Negotiation Rounds**: Backend now automatically tracks quote rounds per provider
- **Simplified Request Model**: Totals now calculated at quote level for better accuracy
- **Enhanced Quote Items**: Quote responses include embedded items array with full details

See [CHANGELOG.md](CHANGELOG.md) for detailed migration guide and breaking changes.

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
)

processor.endpoint_id = "your-endpoint-id"
```

## Available MCP Tools

All 27 tools are fully implemented and production-ready.

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

**Input:**
```json
{
  "request_uuid": "request-uuid",
  "provider_corp_external_id": "PROVIDER-001",
  "shipping_method": "standard",
  "shipping_amount": 25.00,
  "tax_amount": 0.00,
  "status": "draft"
}
```

**Output:**
```json
{
  "quote_uuid": "generated-quote-uuid",
  "request_uuid": "request-uuid",
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
Update quote metadata (shipping, negotiation rounds, status, notes).

**Input:**
```json
{
  "request_uuid": "request-uuid",
  "quote_uuid": "quote-uuid",
  "shipping_amount": 75.00,
  "negotiation_rounds": 2,
  "status": "submitted",
  "notes": "Updated pricing"
}
```

**Output:** Updated quote object.

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

**Input:**
```json
{
  "item_uuid": "item-uuid",
  "provider_item_uuid": "optional-provider-item-uuid",
  "segment_uuid": "optional-segment-uuid"
}
```

**Output:** List of price tiers (quantity ranges and prices).

#### `get_discount_rules`
Get applicable discount rules.

**Input:**
```json
{
  "item_uuid": "item-uuid",
  "provider_item_uuid": "optional-provider-item-uuid",
  "segment_uuid": "optional-segment-uuid"
}
```

**Output:** List of discount rules with conditions and percentages.

#### `calculate_quote_pricing`
Calculate final pricing with all discounts applied.

**Input:**
```json
{
  "quote_uuid": "quote-uuid"
}
```

**Output:** Quote with updated totals including all applicable discounts.

---

### 5. Installment Management (2 tools)

#### `create_installment`
Set up a payment installment for a quote.

**Input:**
```json
{
  "quote_uuid": "quote-uuid",
  "priority": 1,
  "scheduled_date": "2025-12-01T00:00:00Z",
  "installment_ratio": 0.30,
  "status": "scheduled",
  "notes": "30% down payment"
}
```

**Output:** Installment record with calculated amount.

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

### 7. Segment Management (3 tools)

#### `create_segment`
Create a customer or provider segment for pricing.

**Input:**
```json
{
  "provider_corp_external_id": "PROVIDER-001",
  "segment_name": "Premium Customers",
  "segment_description": "High-volume customers with special pricing"
}
```

**Output:** Segment record with UUID.

#### `add_contact_to_segment`
Associate a contact with a pricing segment.

**Input:**
```json
{
  "segment_uuid": "segment-uuid",
  "contact_uuid": "contact-uuid",
  "consumer_corp_external_id": "CUSTOMER-001",
  "email": "contact@customer.com"
}
```

**Output:** Segment contact association record.

#### `get_segment_contacts`
List contacts in a segment.

**Input:**
```json
{
  "segment_uuid": "segment-uuid"
}
```

**Output:** List of contacts with their segment associations.

---

## Usage Examples

### Complete RFQ Workflow

```python
# 1. Submit RFQ Request
result = processor.submit_rfq_request(
    contact_uuid="customer-uuid",
    request_title="Need 1000 widgets",
    request_description="Standard grade, blue color",
    expired_at="2025-12-31T23:59:59Z"
)
request_uuid = result["request_uuid"]

# 2. Search for matching items
items = processor.search_items(
    item_name="widget",
    item_type="product"
)

# 3. Check provider inventory
provider_items = processor.get_provider_items(
    item_uuid=items[0]["item_uuid"],
    provider_corp_external_id="PROVIDER-001"
)

# 4. Create quote
quote = processor.create_quote(
    request_uuid=request_uuid,
    provider_corp_external_id="PROVIDER-001",
    shipping_method="express",
    shipping_amount=50.00
)

# 5. Add line items to quote
quote_item = processor.add_quote_item(
    quote_uuid=quote["quote_uuid"],
    provider_item_uuid=provider_items[0]["provider_item_uuid"],
    item_uuid=items[0]["item_uuid"],
    qty=1000,
    uom="EA",
    price_per_uom=12.50
)

# 6. Calculate final pricing with discounts
final_quote = processor.calculate_quote_pricing(
    quote_uuid=quote["quote_uuid"]
)

# 7. Create installment plan
installment1 = processor.create_installment(
    quote_uuid=quote["quote_uuid"],
    priority=1,
    scheduled_date="2025-12-01T00:00:00Z",
    installment_ratio=0.50
)

installment2 = processor.create_installment(
    quote_uuid=quote["quote_uuid"],
    priority=2,
    scheduled_date="2026-01-01T00:00:00Z",
    installment_ratio=0.50
)

# 8. Update quote status
processor.update_quote_status(
    request_uuid=request_uuid,
    quote_uuid=quote["quote_uuid"],
    status="submitted"
)
```

### AI Assistant Conversation Example

```
User: I need a quote for 500 units of part ABC-123