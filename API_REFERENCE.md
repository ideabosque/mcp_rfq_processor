# API Reference: MCP RFQ Processor

## Overview

This document provides a comprehensive reference for the GraphQL API operations used by the MCP RFQ Processor, including all queries, mutations, and type definitions from the `ai_rfq_engine` GraphQL backend.

**Version**: 0.1.0  
**Total MCP Tools**: 27 (all implemented)  
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
Get tiered pricing for items.

**Variables:**
```graphql
{
  pageNumber: Int
  limit: Int
  itemUuid: String
  segmentUuid: String
  minQuantity: Int
}
```

**Returns:** `ItemPriceTierListType`

#### `discountRuleList`
Get discount rules.

**Variables:**
```graphql
{
  pageNumber: Int
  limit: Int
  itemUuid: String
  segmentUuid: String
  validFrom: String
  validTo: String
}
```

**Returns:** `DiscountRuleListType`

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

#### `segment`
Get segment details.

**Variables:**
```graphql
{
  segmentUuid: String!
}
```

**Returns:** `Segment`

#### `segmentContactList`
List contacts in a segment.

**Variables:**
```graphql
{
  pageNumber: Int
  limit: Int
  segmentUuid: String
  contactUuid: String
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

#### `insertUpdateSegment`
Create or update pricing segment.

**Variables:**
```graphql
{
  segmentUuid: String
  segmentName: String!
  segmentDescription: String
  updatedBy: String!
}
```

**Returns:** `InsertUpdateSegmentType`

#### `insertUpdateSegmentContact`
Add contact to segment.

**Variables:**
```graphql
{
  segmentContactUuid: String
  segmentUuid: String!
  contactUuid: String!
  updatedBy: String!
}
```

**Returns:** `InsertUpdateSegmentContactType`

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
| 13 | add_quote_item | insertUpdateQuoteItem | Mutation | Quote | Add item to quote |
| 14 | update_quote_item | insertUpdateQuoteItem | Mutation | Quote | Update quote item |
| 15 | remove_quote_item | deleteQuoteItem | Mutation | Quote | Remove item from quote |
| 16 | get_quote | quote | Query | Quote | Retrieve quote |
| 17 | search_quotes | quoteList | Query | Quote | Search quotes |
| 18 | get_item_price_tiers | itemPriceTierList | Query | Pricing | Get tiered pricing |
| 19 | get_discount_rules | discountRuleList | Query | Pricing | Get discount rules |
| 20 | calculate_quote_pricing | Multiple | Query | Pricing | Business logic combining queries |
| 21 | create_installment | insertUpdateInstallment | Mutation | Installment | Create installment |
| 22 | get_installments | installmentList | Query | Installment | Get installment schedule |
| 23 | upload_rfq_file | insertUpdateFile | Mutation | File | Upload document |
| 24 | get_rfq_files | fileList | Query | File | Get files |
| 25 | create_segment | insertUpdateSegment | Mutation | Segment | Create segment |
| 26 | add_contact_to_segment | insertUpdateSegmentContact | Mutation | Segment | Add contact |
| 27 | get_segment_contacts | segmentContactList | Query | Segment | List contacts |

---

## Example Queries

### Complete RFQ Workflow Example

```graphql
# Step 1: Submit RFQ Request
mutation {
  insertUpdateRequest(
    contactUuid: "contact-123",
    requestTitle: "Office Supplies Q1 2025",
    requestDescription: "Need supplies for new office location",
    expiredAt: "2025-12-31",
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

# Step 2: Search Items
query {
  itemList(
    pageNumber: 1,
    limit: 50,
    itemType: "supplies",
    itemName: "paper"
  ) {
    totalCount
    items {
      itemUuid
      itemName
      itemDescription
      uom
    }
  }
}

# Step 3: Get Provider Items
query {
  providerItemList(
    itemUuid: "item-123",
    providerCorpExternalId: "provider-789"
  ) {
    totalCount
    providerItems {
      providerItemUuid
      basePricePerUom
      availableQuantity
      leadTimeDays
    }
  }
}

# Step 4: Create Quote
mutation {
  insertUpdateQuote(
    requestUuid: "req-456",
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
      },
      {
        itemUuid: "item-B",
        providerItemUuid: "pitem-2",
        quantity: 50,
        unitPrice: 25.0
      }
    ],
    updatedBy: "MCP"
  ) {
    quote {
      quoteUuid
      totalQuoteAmount
      status
      quoteItems {
        quoteItemUuid
        itemUuid
        quantity
        unitPrice
        totalAmount
      }
    }
  }
}

# Step 5: Apply Discount to Quote Item
mutation {
  insertUpdateQuoteItem(
    quoteItemUuid: "qi-123",
    discountPercent: 10.0,
    discountNotes: "Volume discount for 100+ units",
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

# Step 6: Update Quote Status
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
      updatedAt
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

1. **Flexible Quote Item Management**: The implementation allows adding, updating, and removing quote items directly using dedicated tools (`add_quote_item`, `update_quote_item`, `remove_quote_item`).

2. **Request Item Convenience Methods**: Use `add_item_to_rfq_request` and `remove_item_from_rfq_request` for convenient single-item operations on requests.

3. **Pricing Calculation**: The backend automatically recalculates `totalQuoteAmount` when quote items or metadata (shipping, negotiation_rounds) are updated.

4. **Date Format**: All dates use ISO 8601 format (e.g., "2025-12-31T23:59:59Z").

5. **Currency**: All monetary values are in the configured default currency (USD by default).

6. **Pagination**: Default page limit is 50. Use `pageNumber` and `limit` for pagination.

7. **Contact UUID**: In the implementation, `contact_uuid` typically refers to email addresses for contact identification.

8. **Error Handling**: All tools include comprehensive error handling with detailed logging via Python's logging module.
