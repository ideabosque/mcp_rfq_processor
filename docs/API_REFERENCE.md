# API Reference: MCP RFQ Processor

## Overview

This document provides a comprehensive reference for the GraphQL API operations used by the MCP RFQ Processor, including all queries, mutations, and type definitions from the `ai_rfq_engine` GraphQL backend.

**Version**: 0.1.1
**Total MCP Tools**: 28 (all implemented)
**GraphQL Endpoint**: ai_rfq_graphql (AWS Lambda)

## Table of Contents

1. [GraphQL Schema Overview](#graphql-schema-overview)
2. [Query Operations](#query-operations)
3. [Mutation Operations](#mutation-operations)
4. [Type Definitions](#type-definitions)
5. [MCP Tool to GraphQL Mapping](#mcp-tool-to-graphql-mapping)
6. [Example Queries](#example-queries)

---

## GraphQL Schema Overview

The `ai_rfq_engine` GraphQL API provides comprehensive management of:
- **Items**: Product/service catalog
- **Segments**: Customer/provider pricing groups
- **Provider Items**: Supplier inventory
- **Requests**: RFQ submissions
- **Quotes**: Price quotations
- **Quote Items**: Quote line items
- **Installments**: Payment schedules
- **Files**: Document attachments
- **Discounts**: Pricing rules

---

## Query Operations

### Request Queries

#### `request`
Retrieve a single RFQ request by UUID.

**Variables:**
```graphql
{
  requestUuid: String!
}
```

**Returns:** `Request`

**Example:**
```graphql
query {
  request(requestUuid: "req-123") {
    requestUuid
    contactUuid
    requestTitle
    requestDescription
    status
    expiredAt
    createdAt
    updatedAt
  }
}
```

#### `requestList`
Search and filter RFQ requests.

**Variables:**
```graphql
{
  pageNumber: Int
  limit: Int
  contactUuid: String
  statuses: [String]
  fromExpiredAt: String
  toExpiredAt: String
}
```

**Returns:** `RequestListType`

**Example:**
```graphql
query {
  requestList(
    pageNumber: 1,
    limit: 20,
    contactUuid: "contact-123",
    statuses: ["pending", "active"]
  ) {
    totalCount
    requests {
      requestUuid
      requestTitle
      status
      expiredAt
    }
  }
}
```

### Item Queries

#### `item`
Get item details by UUID.

**Variables:**
```graphql
{
  itemUuid: String!
}
```

**Returns:** `Item`

#### `itemList`
Search items catalog.

**Variables:**
```graphql
{
  pageNumber: Int
  limit: Int
  itemType: String
  itemName: String
  uoms: [String]
}
```

**Returns:** `ItemListType`

### Provider Item Queries

#### `providerItem`
Get provider item details.

**Variables:**
```graphql
{
  providerItemUuid: String!
}
```

**Returns:** `ProviderItem`

#### `providerItemList`
Search provider inventory.

**Variables:**
```graphql
{
  pageNumber: Int
  limit: Int
  itemUuid: String
  providerCorpExternalId: String
  minBasePricePerUom: Float
  maxBasePricePerUom: Float
}
```

**Returns:** `ProviderItemListType`

#### `providerItemBatchList`
Get batch information for provider items.

**Variables:**
```graphql
{
  pageNumber: Int
  limit: Int
  providerItemUuid: String
  batchNumber: String
}
```

**Returns:** `ProviderItemBatchListType`

### Quote Queries

#### `quote`
Retrieve quote details.

**Variables:**
```graphql
{
  quoteUuid: String!
}
```

**Returns:** `Quote`

#### `quoteList`
Search quotes.

**Variables:**
```graphql
{
  pageNumber: Int
  limit: Int
  requestUuid: String
  providerCorpExternalId: String
  statuses: [String]
  fromCreatedAt: String
  toCreatedAt: String
}
```

**Returns:** `QuoteListType`

### Pricing Queries

#### `itemPriceTiers` (Batch-Optimized)
Get tiered pricing for multiple items using batch loader optimization.

**Note:** This is the preferred method for fetching price tiers. Uses email-based segment lookup and DataLoader pattern for efficient multi-item queries.

**Variables:**
```graphql
{
  email: String!          # Customer email for segment lookup
  quoteItems: [JSON]      # Array of {item_uuid, provider_item_uuid, qty}
}
```

**Updated in v0.1.1**: New batch-optimized query replacing individual `itemPriceTierList` calls. Uses DataLoaders to prevent N+1 queries.

**Returns:** Array of `ItemPriceTierType` objects with merged provider_item_batches

**Response Fields:**
- Array of price tier objects:
  - `itemUuid`: Item UUID
  - `providerItemUuid`: Provider item UUID
  - `itemPriceTierUuid`: Unique identifier
  - `quantityGreaterThen`: Minimum quantity threshold for this tier
  - `quantityLessThen`: Maximum quantity threshold for this tier
  - `pricePerUom`: Price per unit of measure (if specified)
  - `marginPerUom`: Margin per unit of measure (if specified)
  - `providerItemBatches`: Array of batch-specific pricing overrides
    - `batchNo`: Batch number
    - `pricePerUom`: Batch-specific price override
  - `status`: Tier status (always "active")

#### `discountPrompts` (Batch-Optimized)
Get discount prompts for items using hierarchical scope loading.

**Note:** This is the preferred method for fetching discount prompts. Loads from all scopes (GLOBAL, SEGMENT, ITEM, PROVIDER_ITEM) and deduplicates.

**Variables:**
```graphql
{
  email: String!          # Customer email for segment lookup
  quoteItems: [JSON]      # Array of {item_uuid, provider_item_uuid}
}
```

**New in v0.1.1**: Replaces `discountRuleList` with hierarchical prompt loading across all scopes.

**Returns:** Array of `DiscountPromptType` objects

**Response Fields:**
- Array of discount prompt objects:
  - `scope`: Scope level (GLOBAL, SEGMENT, ITEM, PROVIDER_ITEM)
  - `prompt`: Discount prompt text with conditions
  - `maxDiscountPercentage`: Maximum allowed discount percentage
  - `conditions`: Conditions for applying this prompt (e.g., "slow_move_item=true")

#### `calculate_quote_pricing` (Business Logic)
Calculate pricing information for an RFQ request using batch-optimized queries.

**Note:** This is a business logic function that reads from REQUEST (not quote) and groups items by provider_corp_external_id. Uses batch loaders for efficient multi-item processing.

**Parameters:**
```python
{
  request_uuid: String!     # RFQ request UUID
  email: String!            # Customer email for segment lookup and batch-optimized queries
}
```

**Updated in v0.1.1**: Changed from `segment_uuid` to `email` parameter to leverage batch-optimized segment lookup.

**Returns:** Custom pricing structure (not a GraphQL query)

**Process:**
1. Reads request items with provider_items arrays
2. Builds all_quote_items array with (item_uuid, provider_item_uuid, qty)
3. Makes single batch call to get_item_price_tiers(email, all_quote_items)
4. Fetches provider_item details (base_price_per_uom)
5. Fetches batch details if batch_no specified (guardrail_price_per_uom, slow_move_item)
6. Groups items by provider_corp_external_id
7. Applies tier pricing with client-side quantity filtering
8. Calculates subtotals per group and overall total

**Response Structure:**
```json
{
  "request_uuid": "req-uuid",
  "groups": [
    {
      "provider_corp_external_id": "PROVIDER-001",
      "items": [
        {
          "item_uuid": "item-uuid",
          "provider_item_uuid": "prov-item-uuid",
          "batch_no": "LOT-2025-001",
          "qty": 500,
          "price_per_uom": 9.50,
          "guardrail_price_per_uom": 9.50,
          "slow_move_item": true,
          "expired_at": "2026-03-15T00:00:00Z",
          "subtotal": 4750.00
        }
      ],
      "group_subtotal": 4750.00
    }
  ]
}
```

**Key Features:**
- **Batch-Optimized**: Single GraphQL query loads all price tiers using DataLoader pattern
- **Client-Side Filtering**: Filters price tiers by quantity for each line item
- **Multi-Provider Support**: Groups enable comparison across multiple providers
- **Batch-Specific Pricing**: Includes guardrail pricing and slow-move flags when available
- **Separate Discount Prompts**: Use `get_discount_prompts` separately for LLM-driven discount suggestions

**Usage Notes:**
- Call this BEFORE creating quotes (Step 7 in main workflow)
- Use `get_discount_prompts` separately to fetch discount suggestions
- Pricing is calculated with tier-based pricing and batch overrides
- Create quotes only after user confirms pricing (Step 8)

**Performance Improvement:**
- **Before v0.1.1**: O(N) GraphQL queries (1 per item for price tiers)
- **After v0.1.1**: O(1) GraphQL queries (1 batch query for all items)
- **Example**: For 10 provider items: 11 queries → 2 queries = 82% reduction

### Installment Queries

#### `installmentList`
Get installment schedule.

**Variables:**
```graphql
{
  pageNumber: Int
  limit: Int
  quoteUuid: String
  statuses: [String]
}
```

**Returns:** `InstallmentListType`

### File Queries

#### `fileList`
Get files associated with requests.

**Variables:**
```graphql
{
  pageNumber: Int
  limit: Int
  requestUuid: String
  fileType: String
}
```

**Returns:** `FileListType`

### Segment Queries

**Note:** Only `segmentContactList` is exposed through MCP tools for read-only segment lookups.

#### `segmentContactList`
List contacts in a segment (read-only access for pricing lookups).

**Variables:**
```graphql
{
  pageNumber: Int
  limit: Int
  consumerCorpExternalId: String
  email: String
}
```

**Returns:** `SegmentContactListType`

---

## Mutation Operations

### Request Mutations

#### `insertUpdateRequest`
Create or update an RFQ request.

**Variables:**
```graphql
{
  requestUuid: String
  email: String!
  requestTitle: String!
  requestDescription: String
  expiredAt: String
  status: String
  updatedBy: String!
}
```

**Returns:** `InsertUpdateRequestType`

**Example:**
```graphql
mutation {
  insertUpdateRequest(
    email: "buyer@customer.com",
    requestTitle: "Office supplies Q1",
    requestDescription: "Need supplies for new office",
    expiredAt: "2025-12-31",
    status: "initial",
    updatedBy: "MCP"
  ) {
    request {
      requestUuid
      requestTitle
      status
      createdAt
    }
  }
}
```

### Quote Mutations

#### `insertUpdateQuote`
Create or update a quote.

**Variables:**
```graphql
{
  quoteUuid: String
  requestUuid: String!
  providerCorpExternalId: String!
  shippingMethod: String
  shippingAmount: Float
  taxAmount: Float
  status: String
  notes: String
  items: [QuoteItemInput]
  updatedBy: String!
}
```

**Returns:** `InsertUpdateQuoteType`

**Example:**
```graphql
mutation {
  insertUpdateQuote(
    requestUuid: "req-123",
    providerCorpExternalId: "provider-789",
    shippingMethod: "express",
    shippingAmount: 50.0,
    taxAmount: 125.0,
    status: "initial",
    items: [
      {
        itemUuid: "item-A",
        providerItemUuid: "pitem-1",
        quantity: 100,
        unitPrice: 10.0
      }
    ],
    updatedBy: "MCP"
  ) {
    quote {
      quoteUuid
      totalQuoteAmount
      status
    }
  }
}
```

#### `insertUpdateQuoteItem`
Update quote item (discount only).

**Variables:**
```graphql
{
  quoteItemUuid: String!
  discountAmount: Float
  discountPercent: Float
  discountNotes: String
  updatedBy: String!
}
```

**Returns:** `InsertUpdateQuoteItemType`

**Example:**
```graphql
mutation {
  insertUpdateQuoteItem(
    quoteItemUuid: "qi-123",
    discountPercent: 10.0,
    discountNotes: "Volume discount",
    updatedBy: "MCP"
  ) {
    quoteItem {
      quoteItemUuid
      discountAmount
      discountPercent
      totalAmount
    }
  }
}
```

### Installment Mutations

#### `insertUpdateInstallment`
Create or update payment installment.

**Variables:**
```graphql
{
  installmentUuid: String
  quoteUuid: String!
  installmentNumber: Int!
  dueDate: String!
  amount: Float!
  paymentMethod: String
  status: String
  updatedBy: String!
}
```

**Returns:** `InsertUpdateInstallmentType`

### File Mutations

#### `insertUpdateFile`
Upload file attachment.

**Variables:**
```graphql
{
  fileUuid: String
  requestUuid: String!
  fileName: String!
  fileType: String!
  fileData: String!
  updatedBy: String!
}
```

**Returns:** `InsertUpdateFileType`

### Segment Mutations

**Note:** Segment creation and contact assignment mutations (`insertUpdateSegment`, `insertUpdateSegmentContact`) are managed via backend admin interface and not exposed through MCP tools.

---

## Type Definitions

### Request
```graphql
type Request {
  requestUuid: String!
  contactUuid: String!
  requestTitle: String!
  requestDescription: String
  status: String!
  expiredAt: String
  createdAt: String!
  updatedAt: String!
  quotes: [Quote]
  files: [File]
}
```

### Item
```graphql
type Item {
  itemUuid: String!
  itemType: String!
  itemName: String!
  itemDescription: String
  uom: String!
  createdAt: String!
  updatedAt: String!
  providerItems: [ProviderItem]
  priceTiers: [ItemPriceTier]
}
```

### ProviderItem
```graphql
type ProviderItem {
  providerItemUuid: String!
  itemUuid: String!
  providerCorpExternalId: String!
  basePricePerUom: Float!
  availableQuantity: Int
  leadTimeDays: Int
  createdAt: String!
  updatedAt: String!
  item: Item
  batches: [ProviderItemBatch]
}
```

### Quote
```graphql
type Quote {
  quoteUuid: String!
  requestUuid: String!
  providerCorpExternalId: String!
  shippingMethod: String
  shippingAmount: Float
  taxAmount: Float
  totalQuoteAmount: Float!
  status: String!
  notes: String
  createdAt: String!
  updatedAt: String!
  request: Request
  quoteItems: [QuoteItem]
  installments: [Installment]
}
```

### QuoteItem
```graphql
type QuoteItem {
  quoteItemUuid: String!
  quoteUuid: String!
  itemUuid: String!
  providerItemUuid: String!
  quantity: Int!
  unitPrice: Float!
  discountAmount: Float
  discountPercent: Float
  discountNotes: String
  totalAmount: Float!
  createdAt: String!
  updatedAt: String!
  item: Item
  providerItem: ProviderItem
}
```

### Installment
```graphql
type Installment {
  installmentUuid: String!
  quoteUuid: String!
  installmentNumber: Int!
  dueDate: String!
  amount: Float!
  status: String!
  paidAt: String
  createdAt: String!
  updatedAt: String!
}
```

### File
```graphql
type File {
  fileUuid: String!
  requestUuid: String!
  fileName: String!
  fileType: String!
  fileUrl: String!
  createdAt: String!
  updatedAt: String!
}
```

### Segment
```graphql
type Segment {
  segmentUuid: String!
  segmentName: String!
  segmentDescription: String
  createdAt: String!
  updatedAt: String!
  contacts: [SegmentContact]
}
```

---

## MCP Tool to GraphQL Mapping

**Total MCP Tools**: 28 (all implemented)

| # | MCP Tool | GraphQL Operation | Type | Category | Notes |
|---|----------|-------------------|------|----------|-------|
| 1 | submit_rfq_request | insertUpdateRequest | Mutation | Request | Create new request |
| 2 | update_rfq_request | insertUpdateRequest | Mutation | Request | Update existing request |
| 3 | add_item_to_rfq_request | insertUpdateRequest | Mutation | Request | Convenience: add single item |
| 4 | remove_item_from_rfq_request | insertUpdateRequest | Mutation | Request | Convenience: remove single item |
| 5 | assign_provider_item_to_request_item | providerItem + insertUpdateRequest | Composite | Request | Validate provider item, then attach to request item |
| 6 | remove_provider_item_from_request_item | insertUpdateRequest | Mutation | Request | Remove provider assignments |
| 7 | get_rfq_request | request | Query | Request | Retrieve single request |
| 8 | search_rfq_requests | requestList | Query | Request | Search with filters |
| 9 | search_items | itemList | Query | Item | Search catalog |
| 10 | get_item | item | Query | Item | Get item details |
| 11 | get_provider_items | providerItemList | Query | Item | Search inventory with batches |
| 12 | get_provider_item_batches | providerItemBatchList | Query | Item | Get batch info |
| 13 | create_quote | insertUpdateQuote (+ insertUpdateQuoteItem) | Mutation | Quote | Creates quote and quote items from provider assignments |
| 14 | update_quote | insertUpdateQuote | Mutation | Quote | Update quote metadata/status |
| 15 | get_quote | quote | Query | Quote | Retrieve quote |
| 16 | search_quotes | quoteList | Query | Quote | Search quotes |
| 17 | update_quote_item | insertUpdateQuoteItem | Mutation | Quote | Update quote item discount |
| 18 | get_item_price_tiers | itemPriceTiers | Query | Pricing | Batch-optimized tier loading with email + quote_items |
| 19 | get_discount_prompts | discountPrompts | Query | Pricing | Batch-optimized prompt loading from all scopes |
| 20 | calculate_quote_pricing | itemPriceTiers + Multiple | Business Logic | Pricing | Batch-optimized pricing with email-based segment lookup |
| 21 | create_installment | insertUpdateInstallment | Mutation | Installment | Create installment |
| 22 | update_installment | insertUpdateInstallment | Mutation | Installment | Update installment status/SO |
| 23 | create_installments | insertUpdateInstallment | Mutation | Installment | Create multiple installments |
| 24 | get_installments | installmentList | Query | Installment | Get installment schedule |
| 25 | confirm_request_and_create_quotes | insertUpdateRequest + insertUpdateQuote | Composite | Workflow | Confirm request and create provider quotes |
| 26 | confirm_quote_and_create_installments | insertUpdateQuote + insertUpdateInstallment | Composite | Workflow | Confirm quote, disapprove others, create installments |
| 27 | upload_rfq_file | insertUpdateFile | Mutation | File | Upload document |
| 28 | get_rfq_files | fileList | Query | File | Get files |
| -- | get_segment_contacts | segmentContactList | Query | Segment | DEPRECATED: Segment lookup now via email in pricing tools |

---

## Example Queries

### Complete RFQ to Quote Workflow Example (Updated)

For the complete 14-step workflow, see [DEVELOPMENT_PLAN.md - Complete RFQ to Quote Workflow](DEVELOPMENT_PLAN.md#complete-rfq-to-quote-workflow).

```graphql
# Step 0: Find Customer Segment
query {
  segmentContactList(
    consumerCorpExternalId: "CUSTOMER-001",
    email: "buyer@customer.com"
  ) {
    totalCount
    segmentContacts {
      segment {
        segmentUuid
        segmentName
        segmentDescription
      }
    }
  }
}

# Step 1: Submit RFQ Request (with empty items array)
mutation {
  insertUpdateRequest(
    email: "buyer@customer.com",
    requestTitle: "Q1 Production Materials",
    requestDescription: "Need materials for production",
    expiredAt: "2025-12-31",
    items: [],
    status: "initial",
    updatedBy: "MCP"
  ) {
    request {
      requestUuid
      requestTitle
      status
    }
  }
}

# Step 2-3: Search Items and Add to Request
query {
  itemList(
    itemName: "widget",
    itemType: "product"
  ) {
    items {
      itemUuid
      itemName
      uom
    }
  }
}

# Step 4-5: Get Provider Items and Batches
query {
  providerItemList(
    itemUuid: "item-123",
    providerCorpExternalId: "PROVIDER-001",
    inStock: true
  ) {
    providerItems {
      providerItemUuid
      basePricePerUom
      availableQuantity
    }
  }
}

query {
  providerItemBatchList(
    providerItemUuid: "prov-item-123",
    inStock: true
  ) {
    providerItemBatches {
      batchNo
      guardrailPricePerUom
      slowMoveItem
      expiredAt
    }
  }
}

# Step 6: Assign Provider Items to Request Items
mutation {
  insertUpdateRequest(
    requestUuid: "req-456",
    items: [
      {
        itemUuid: "item-123",
        qty: 500,
        providerItems: [
          {
            providerCorpExternalId: "PROVIDER-001",
            providerItemUuid: "prov-item-123",
            batchNo: "LOT-2025-001",
            qty: 500
          }
        ]
      }
    ],
    updatedBy: "MCP"
  ) {
    request {
      requestUuid
      items {
        itemUuid
        qty
        providerItems
      }
    }
  }
}

# Step 7: Calculate Quote Pricing (MCP business logic - not pure GraphQL)
# This is handled by the calculate_quote_pricing MCP tool
# Returns grouped pricing with discount_rules and price_tiers

# Step 8: Create Quote (after user confirms pricing)
mutation {
  insertUpdateQuote(
    requestUuid: "req-456",
    providerCorpExternalId: "PROVIDER-001",
    salesRepEmail: "sales@provider1.com",
    status: "initial",
    updatedBy: "MCP"
  ) {
    quote {
      quoteUuid
      status
    }
  }
}

# Step 10: Add Quote Items with User-Confirmed Discount
mutation {
  insertUpdateQuoteItem(
    quoteUuid: "quote-789",
    providerItemUuid: "prov-item-123",
    itemUuid: "item-123",
    segmentUuid: "seg-uuid",
    qty: 500,
    batchNo: "LOT-2025-001",
    discountAmount: 237.50,
    updatedBy: "MCP"
  ) {
    quoteItem {
      quoteItemUuid
      qty
      discountAmount
      totalAmount
    }
  }
}

# Step 11: Update Quote with Shipping
mutation {
  insertUpdateQuote(
    requestUuid: "req-456",
    quoteUuid: "quote-789",
    shippingMethod: "express",
    shippingAmount: 75.0,
    updatedBy: "MCP"
  ) {
    quote {
      quoteUuid
      shippingMethod
      shippingAmount
      totalQuoteAmount
    }
  }
}

# Step 12: Create Installment Plan
mutation {
  insertUpdateInstallment(
    quoteUuid: "quote-789",
    installmentNumber: 1,
    dueDate: "2025-12-01",
    amount: 2293.75,
    paymentMethod: "bank_transfer",
    status: "pending",
    updatedBy: "MCP"
  ) {
    installment {
      installmentUuid
      installmentNumber
      amount
      paymentMethod
      installmentRatio  # Auto-calculated by backend
    }
  }
}

# Step 13: Submit Quote
mutation {
  insertUpdateQuote(
    quoteUuid: "quote-789",
    status: "confirmed",
    updatedBy: "MCP"
  ) {
    quote {
      quoteUuid
      status
      totalQuoteAmount
    }
  }
}
```

### Pricing Queries with Filters (New)

```graphql
# Get price tier for specific quantity (v1.1.0)
query {
  itemPriceTierList(
    itemUuid: "item-123",
    providerItemUuid: "prov-item-123",
    segmentUuid: "seg-uuid",
    quantityValue: 500,  # Find tier where quantityGreaterThen <= 500 < quantityLessThen
    status: "active"
  ) {
    itemPriceTierList {
      itemPriceTierUuid
      quantityGreaterThen
      quantityLessThen
      marginPerUom
    }
  }
}

# Get discount rules for specific item subtotal (v1.1.0)
query {
  discountRuleList(
    itemUuid: "item-123",
    providerItemUuid: "prov-item-123",
    segmentUuid: "seg-uuid",
    subtotalValue: 4750.00,  # Find rule where subtotalGreaterThan <= 4750 < subtotalLessThan
    status: "active"
  ) {
    discountRuleList {
      discountRuleUuid
      subtotalGreaterThan
      subtotalLessThan
      maxDiscountPercentage
    }
  }
}
```

### Modify Request Workflow Example

```graphql
# Step 1: Update Request
mutation {
  insertUpdateRequest(
    requestUuid: "req-456",
    requestDescription: "Updated: Added item-C, removed item-B",
    status: "modified",
    updatedBy: "MCP"
  ) {
    request {
      requestUuid
      requestDescription
      status
      updatedAt
    }
  }
}

# Step 2: Create New Quote with Modified Items
mutation {
  insertUpdateQuote(
    requestUuid: "req-456",
    providerCorpExternalId: "provider-789",
    items: [
      {
        itemUuid: "item-A",
        providerItemUuid: "pitem-1",
        quantity: 100,
        unitPrice: 10.0
      },
      {
        itemUuid: "item-C",
        providerItemUuid: "pitem-3",
        quantity: 75,
        unitPrice: 15.0
      }
    ],
    updatedBy: "MCP"
  ) {
    quote {
      quoteUuid
      totalQuoteAmount
      quoteItems {
        itemUuid
        quantity
      }
    }
  }
}

# Step 3: Mark Old Quote as Superseded
mutation {
  insertUpdateQuote(
    quoteUuid: "quote-old",
    status: "superseded",
    notes: "Replaced by quote-new",
    updatedBy: "MCP"
  ) {
    quote {
      quoteUuid
      status
    }
  }
}
```

---

## Error Codes

| Code | Description | Resolution |
|------|-------------|------------|
| INVALID_UUID | UUID format invalid | Ensure UUID follows standard format |
| NOT_FOUND | Resource not found | Verify UUID exists |
| VALIDATION_ERROR | Input validation failed | Check required fields |
| QUOTE_LOCKED | Quote cannot be modified | Items locked after creation |
| DUPLICATE_ENTRY | Entry already exists | Use update instead |
| EXPIRED_REQUEST | Request past expiration | Update expiredAt date |

---

## Notes

1. **Status-Based Quote Item Management**: Quote items are created automatically from provider assignments when a quote is created. Item changes are limited to discount updates via `update_quote_item` while the quote is `initial` or `in_progress`. To change items or providers, update the request assignments and create a new quote.

2. **Request Item Convenience Methods**: Use `add_item_to_rfq_request` and `remove_item_from_rfq_request` for convenient single-item operations on requests.

3. **Pricing Calculation**: The backend automatically recalculates `totalQuoteAmount` when quote items or metadata (shipping, negotiation_rounds) are updated.

4. **Date Format**: All dates use ISO 8601 format (e.g., "2025-12-31T23:59:59Z").

5. **Currency**: All monetary values are in the configured default currency (USD by default).

6. **Pagination**: Default page limit is 50. Use `pageNumber` and `limit` for pagination.

7. **Contact UUID**: In the implementation, `contact_uuid` typically refers to email addresses for contact identification.

8. **Error Handling**: All tools include comprehensive error handling with detailed logging via Python's logging module.
