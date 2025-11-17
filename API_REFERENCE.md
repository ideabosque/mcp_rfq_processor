# API Reference: MCP RFQ Processor

## Overview

This document provides a comprehensive reference for the GraphQL API operations used by the MCP RFQ Processor, including all queries, mutations, and type definitions from the `ai_rfq_engine` GraphQL backend.

**Version**: 1.2.0
**Total MCP Tools**: 26 (all implemented)
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

#### `itemPriceTierList`
Get active tiered pricing for items based on item, provider, and customer segments.

**Note:** Typically used via `calculate_quote_pricing` which automatically filters tiers by quantity. Direct use is available for LLM-driven price exploration.

**Variables:**
```graphql
{
  pageNumber: Int
  limit: Int
  itemUuid: String
  providerItemUuid: String
  segmentUuid: String
  quantityValue: Int  # Find tier where quantityGreaterThen <= value < quantityLessThen
  minPrice: Float     # Filter: tier.price >= value
  maxPrice: Float     # Filter: tier.price <= value
  status: String      # Fixed to "active"
}
```

**Updated in v1.1.0**: Simplified to use `quantityValue` parameter instead of min/max quantity filters.

**Returns:** `ItemPriceTierListType`

**Response Fields:**
- `itemPriceTierList`: Array of price tiers
  - `itemPriceTierUuid`: Unique identifier
  - `itemUuid`: Item UUID
  - `providerItemUuid`: Provider item UUID
  - `segment`: Segment details (JSON)
  - `quantityGreaterThen`: Minimum quantity threshold for this tier
  - `quantityLessThen`: Maximum quantity threshold for this tier
  - `marginPerUom`: Margin per unit of measure
  - `status`: Tier status (always "active")
  - `createdAt`: Creation timestamp
  - `updatedAt`: Last update timestamp
  - `updatedBy`: Last updated by user
- `pageSize`: Items per page
- `pageNumber`: Current page number
- `total`: Total number of active price tiers

#### `discountRuleList`
Get discount rules for item-level pricing with filtering options for subtotal and discount percentages.

**Note:** Typically used via `calculate_quote_pricing` which automatically filters rules by item subtotal. Direct use is available for LLM-driven discount exploration.

**Variables:**
```graphql
{
  pageNumber: Int
  limit: Int
  itemUuid: String!              # REQUIRED - Item UUID for item-specific rules
  providerItemUuid: String!      # REQUIRED - Provider item UUID for provider-specific pricing
  segmentUuid: String!           # REQUIRED - Segment UUID for segment-specific pricing
  subtotalValue: Float           # Find rule where subtotalGreaterThan <= value < subtotalLessThan
  maxDiscountPercentage: Float   # Filter: rule.discount <= value
  minDiscountPercentage: Float   # Filter: rule.discount >= value
  status: String                 # Filter by status (e.g., "active", "inreview")
}
```

**Updated in v1.1.0**: Simplified to use `subtotalValue` parameter and made item/provider/segment parameters required. Rules are now item-level (not group-level).

**Returns:** `DiscountRuleListType`

**Response Fields:**
- `discountRuleList`: Array of discount rules
  - `discountRuleUuid`: Unique identifier
  - `providerItem`: Provider item details (JSON)
  - `segment`: Segment details (JSON)
  - `subtotalGreaterThan`: Minimum subtotal threshold for rule to apply
  - `subtotalLessThan`: Maximum subtotal threshold for rule to apply
  - `maxDiscountPercentage`: Maximum discount percentage allowed
  - `status`: Rule status (e.g., "inreview")
  - `createdAt`: Creation timestamp
  - `updatedAt`: Last update timestamp
  - `updatedBy`: Last updated by user
- `pageSize`: Items per page
- `pageNumber`: Current page number
- `total`: Total number of discount rules

#### `calculate_quote_pricing` (Business Logic)
Calculate grouped pricing from request with provider_items, including applicable discount rules and price tiers.

**Note:** This is a business logic function that reads from REQUEST (not quote) and groups items by (provider_corp_external_id, segment_uuid).

**Parameters:**
```python
{
  request_uuid: String!     # RFQ request UUID
  segment_uuid: String!     # Customer segment UUID for pricing rules
}
```

**Returns:** Custom pricing structure (not a GraphQL query)

**Process:**
1. Reads request items with provider_items arrays
2. Fetches provider_item details (base_price_per_uom)
3. Fetches batch details if batch_no specified (guardrail_price_per_uom, slow_move_item)
4. Groups items by (provider_corp_external_id, segment_uuid)
5. Calculates subtotals per group
6. Fetches applicable discount_rules filtered by group subtotal
7. Fetches applicable price_tiers filtered by item quantity

**Response Structure:**
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
          "price_tiers": [
            {
              "itemPriceTierUuid": "tier-uuid",
              "quantityGreaterThen": 500,
              "quantityLessThen": 1000,
              "marginPerUom": 8.75
            }
          ]
        }
      ],
      "subtotal": 4750.00,
      "discount_rules": [
        {
          "discountRuleUuid": "rule-uuid",
          "subtotalGreaterThan": 1000.00,
          "subtotalLessThan": 10000.00,
          "maxDiscountPercentage": 5.0
        }
      ]
    }
  ],
  "subtotal": 4750.00
}
```

**Key Features:**
- **Information Provider Pattern**: Returns discount_rules and price_tiers WITHOUT applying them
- **LLM Decision Making**: LLM presents options to user and applies discounts only after confirmation
- **Multi-Provider Support**: Groups enable comparison across multiple providers
- **Batch-Specific Pricing**: Includes guardrail pricing and slow-move flags when available

**Usage Notes:**
- Call this BEFORE creating quotes (Step 7 in main workflow)
- Use returned discount_rules to present options to user
- Use returned price_tiers to suggest quantity adjustments
- Create quotes only after user confirms pricing (Step 8)

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
  contactUuid: String!
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
    contactUuid: "contact-123",
    requestTitle: "Office supplies Q1",
    requestDescription: "Need supplies for new office",
    expiredAt: "2025-12-31",
    status: "pending",
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
    status: "draft",
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

**Total MCP Tools**: 27 (all implemented)

| # | MCP Tool | GraphQL Operation | Type | Category | Notes |
|---|----------|-------------------|------|----------|-------|
| 1 | submit_rfq_request | insertUpdateRequest | Mutation | Request | Create new request |
| 2 | update_rfq_request | insertUpdateRequest | Mutation | Request | Update existing request |
| 3 | add_item_to_rfq_request | insertUpdateRequest | Mutation | Request | Convenience: add single item |
| 4 | remove_item_from_rfq_request | insertUpdateRequest | Mutation | Request | Convenience: remove single item |
| 5 | get_rfq_request | request | Query | Request | Retrieve single request |
| 6 | search_rfq_requests | requestList | Query | Request | Search with filters |
| 7 | search_items | itemList | Query | Item | Search catalog |
| 8 | get_item | item | Query | Item | Get item details |
| 9 | get_provider_items | providerItemList | Query | Item | Search inventory |
| 10 | get_provider_item_batches | providerItemBatchList | Query | Item | Get batch info |
| 11 | create_quote | insertUpdateQuote | Mutation | Quote | Create new quote |
| 12 | update_quote | insertUpdateQuote | Mutation | Quote | Update quote metadata |
| 13 | add_quote_item | insertUpdateQuoteItem | Mutation | Quote | Add item to quote (initial status only) |
| 14 | update_quote_item | insertUpdateQuoteItem | Mutation | Quote | Update quote item (in_progress status only, discount modifications) |
| 15 | remove_quote_item | deleteQuoteItem | Mutation | Quote | **DEPRECATED** - Do not use |
| 16 | get_quote | quote | Query | Quote | Retrieve quote |
| 17 | search_quotes | quoteList | Query | Quote | Search quotes |
| 18 | get_item_price_tiers | itemPriceTierList | Query | Pricing | Get tiered pricing (with qty filters) |
| 19 | get_discount_rules | discountRuleList | Query | Pricing | Get discount rules (with subtotal filters) |
| 20 | calculate_quote_pricing | Multiple Queries | Business Logic | Pricing | Groups request items, returns pricing + rules |
| 21 | create_installment | insertUpdateInstallment | Mutation | Installment | Create installment |
| 22 | update_installment | insertUpdateInstallment | Mutation | Installment | Update installment status/SO |
| 23 | create_installments | insertUpdateInstallment | Mutation | Installment | Create multiple installments |
| 24 | get_installments | installmentList | Query | Installment | Get installment schedule |
| 25 | upload_rfq_file | insertUpdateFile | Mutation | File | Upload document |
| 26 | get_rfq_files | fileList | Query | File | Get files |
| 27 | get_segment_contacts | segmentContactList | Query | Segment | List contacts (read-only) |

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
    contactUuid: "buyer@customer.com",
    requestTitle: "Q1 Production Materials",
    requestDescription: "Need materials for production",
    expiredAt: "2025-12-31",
    items: [],
    status: "pending",
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
    status: "draft",
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
    status: "submitted",
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

1. **Status-Based Quote Item Management** (v1.2.0): Quote item operations are restricted by quote status:
   - **initial status**: Only `add_quote_item` allowed to add new items
   - **in_progress status**: Only `update_quote_item` allowed for discount modifications
   - **remove_quote_item**: Deprecated and should not be used
   - To change quote items after creation, modify the request and create a new quote

2. **Request Item Convenience Methods**: Use `add_item_to_rfq_request` and `remove_item_from_rfq_request` for convenient single-item operations on requests.

3. **Pricing Calculation**: The backend automatically recalculates `totalQuoteAmount` when quote items or metadata (shipping, negotiation_rounds) are updated.

4. **Date Format**: All dates use ISO 8601 format (e.g., "2025-12-31T23:59:59Z").

5. **Currency**: All monetary values are in the configured default currency (USD by default).

6. **Pagination**: Default page limit is 50. Use `pageNumber` and `limit` for pagination.

7. **Contact UUID**: In the implementation, `contact_uuid` typically refers to email addresses for contact identification.

8. **Error Handling**: All tools include comprehensive error handling with detailed logging via Python's logging module.
