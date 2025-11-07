# API Reference: MCP RFQ Processor

## GraphQL Backend Integration

The MCP RFQ Processor integrates with `ai_rfq_engine` GraphQL API through AWS Lambda.

### Connection Details

**Function Name**: `ai_rfq_graphql`  
**Protocol**: GraphQL over AWS Lambda  
**Authentication**: AWS IAM credentials  
**Response Format**: JSON (GraphQL standard)

---

## Data Models

### Request
Represents a customer's request for quotation.

**GraphQL Type**: `RequestType`

```graphql
type Request {
  request_uuid: String!
  contact_uuid: String!
  request_title: String!
  request_description: String
  status: String!
  expired_at: DateTime
  created_at: DateTime!
  updated_at: DateTime!
  updated_by: String!
}
```

**Status Values**: `pending`, `quoted`, `accepted`, `rejected`, `expired`

---

### Item
Represents a product or service in the catalog.

**GraphQL Type**: `ItemType`

```graphql
type Item {
  item_uuid: String!
  item_type: String!
  item_name: String!
  item_description: String
  uoms: [String!]!
  attributes: JSONString
  created_at: DateTime!
  updated_at: DateTime!
  updated_by: String!
}
```

**Item Types**: `product`, `service`, `material`, `component`

---

### ProviderItem
Represents a supplier's inventory item with pricing.

**GraphQL Type**: `ProviderItemType`

```graphql
type ProviderItem {
  provider_item_uuid: String!
  item_uuid: String!
  provider_corp_external_id: String!
  provider_item_external_id: String!
  base_price_per_uom: Float!
  currency: String!
  lead_time_days: Int
  min_order_qty: Float
  item: Item!
  created_at: DateTime!
  updated_at: DateTime!
  updated_by: String!
}
```

---

### ProviderItemBatch
Represents inventory batches with lot tracking.

**GraphQL Type**: `ProviderItemBatchType`

```graphql
type ProviderItemBatch {
  provider_item_uuid: String!
  batch_no: String!
  item_uuid: String!
  produced_at: DateTime
  expired_at: DateTime
  cost_per_uom: Float!
  total_cost_per_uom: Float!
  available_qty: Float!
  in_stock: Boolean!
  notes: String
  created_at: DateTime!
  updated_at: DateTime!
  updated_by: String!
}
```

---

### Quote
Represents a price quotation for an RFQ request.

**GraphQL Type**: `QuoteType`

```graphql
type Quote {
  quote_uuid: String!
  request_uuid: String!
  provider_corp_external_id: String!
  shipping_method: String!
  shipping_amount: Float!
  tax_amount: Float!
  total_quote_amount: Float!
  total_quote_discount: Float!
  final_total_quote_amount: Float!
  status: String!
  notes: String
  quote_items: [QuoteItem!]
  created_at: DateTime!
  updated_at: DateTime!
  updated_by: String!
}
```

**Status Values**: `draft`, `submitted`, `accepted`, `rejected`, `expired`

---

### QuoteItem
Represents a line item in a quote.

**GraphQL Type**: `QuoteItemType`

```graphql
type QuoteItem {
  quote_item_uuid: String!
  quote_uuid: String!
  provider_item_uuid: String!
  item_uuid: String!
  batch_no: String
  qty: Float!
  uom: String!
  price_per_uom: Float!
  subtotal: Float!
  subtotal_discount: Float!
  final_subtotal: Float!
  notes: String
  created_at: DateTime!
  updated_at: DateTime!
  updated_by: String!
}
```

---

### ItemPriceTier
Represents quantity-based pricing tiers.

**GraphQL Type**: `ItemPriceTierType`

```graphql
type ItemPriceTier {
  item_price_tier_uuid: String!
  item_uuid: String!
  provider_item_uuid: String
  segment_uuid: String
  min_quantity: Float!
  max_quantity: Float
  price: Float!
  currency: String!
  effective_from: DateTime
  effective_to: DateTime
  created_at: DateTime!
  updated_at: DateTime!
  updated_by: String!
}
```

---

### DiscountRule
Represents promotional discount rules.

**GraphQL Type**: `DiscountRuleType`

```graphql
type DiscountRule {
  discount_rule_uuid: String!
  item_uuid: String!
  provider_item_uuid: String
  segment_uuid: String
  min_subtotal: Float
  max_subtotal: Float
  discount_percentage: Float!
  discount_amount: Float
  effective_from: DateTime
  effective_to: DateTime
  created_at: DateTime!
  updated_at: DateTime!
  updated_by: String!
}
```

---

### Installment
Represents payment installment schedules.

**GraphQL Type**: `InstallmentType`

```graphql
type Installment {
  installment_uuid: String!
  quote_uuid: String!
  request_uuid: String!
  priority: Int!
  scheduled_date: DateTime!
  installment_ratio: Float!
  installment_amount: Float!
  status: String!
  salesorder_no: String
  notes: String
  created_at: DateTime!
  updated_at: DateTime!
  updated_by: String!
}
```

**Status Values**: `scheduled`, `paid`, `overdue`, `cancelled`

---

### File
Represents uploaded documents.

**GraphQL Type**: `FileType`

```graphql
type File {
  request_uuid: String!
  file_name: String!
  file_url: String!
  file_type: String
  file_size: Int
  email: String!
  notes: String
  created_at: DateTime!
  updated_at: DateTime!
  updated_by: String!
}
```

---

### Segment
Represents customer/provider groups for pricing.

**GraphQL Type**: `SegmentType`

```graphql
type Segment {
  segment_uuid: String!
  provider_corp_external_id: String!
  segment_name: String!
  segment_description: String
  created_at: DateTime!
  updated_at: DateTime!
  updated_by: String!
}
```

---

### SegmentContact
Represents contact associations with segments.

**GraphQL Type**: `SegmentContactType`

```graphql
type SegmentContact {
  segment_uuid: String!
  contact_uuid: String!
  email: String!
  consumer_corp_external_id: String
  created_at: DateTime!
  updated_at: DateTime!
  updated_by: String!
}
```

---

## GraphQL Queries

### Request Queries

#### `request`
Get single request by UUID.

```graphql
query GetRequest($requestUuid: String!) {
  request(requestUuid: $requestUuid) {
    request_uuid
    contact_uuid
    request_title
    request_description
    status
    expired_at
    created_at
    updated_at
  }
}
```

#### `requestList`
Search and filter requests.

```graphql
query SearchRequests(
  $pageNumber: Int
  $limit: Int
  $contactUuid: String
  $statuses: [String]
  $fromExpiredAt: DateTime
  $toExpiredAt: DateTime
) {
  requestList(
    pageNumber: $pageNumber
    limit: $limit
    contactUuid: $contactUuid
    statuses: $statuses
    fromExpiredAt: $fromExpiredAt
    toExpiredAt: $toExpiredAt
  ) {
    total
    requestList {
      request_uuid
      contact_uuid
      request_title
      status
      expired_at
    }
  }
}
```

---

### Item Queries

#### `item`
Get single item by UUID.

```graphql
query GetItem($itemUuid: String!) {
  item(itemUuid: $itemUuid) {
    item_uuid
    item_type
    item_name
    item_description
    uoms
    attributes
    created_at
  }
}
```

#### `itemList`
Search items catalog.

```graphql
query SearchItems(
  $pageNumber: Int
  $limit: Int
  $itemType: String
  $itemName: String
  $uoms: [String]
) {
  itemList(
    pageNumber: $pageNumber
    limit: $limit
    itemType: $itemType
    itemName: $itemName
    uoms: $uoms
  ) {
    total
    itemList {
      item_uuid
      item_type
      item_name
      item_description
      uoms
    }
  }
}
```

#### `providerItemList`
Search provider inventory.

```graphql
query SearchProviderItems(
  $pageNumber: Int
  $limit: Int
  $itemUuid: String
  $providerCorpExternalId: String
  $minBasePricePerUom: Float
  $maxBasePricePerUom: Float
) {
  providerItemList(
    pageNumber: $pageNumber
    limit: $limit
    itemUuid: $itemUuid
    providerCorpExternalId: $providerCorpExternalId
    minBasePricePerUom: $minBasePricePerUom
    maxBasePricePerUom: $maxBasePricePerUom
  ) {
    total
    providerItemList {
      provider_item_uuid
      item_uuid
      provider_corp_external_id
      base_price_per_uom
      currency
      lead_time_days
      item {
        item_name
        item_type
      }
    }
  }
}
```

#### `providerItemBatchList`
Get batch inventory.

```graphql
query GetProviderItemBatches(
  $providerItemUuid: String
  $itemUuid: String
  $inStock: Boolean
  $expiredAtGt: DateTime
) {
  providerItemBatchList(
    providerItemUuid: $providerItemUuid
    itemUuid: $itemUuid
    inStock: $inStock
    expiredAtGt: $expiredAtGt
  ) {
    total
    providerItemBatchList {
      provider_item_uuid
      batch_no
      produced_at
      expired_at
      available_qty
      in_stock
      cost_per_uom
    }
  }
}
```

---

### Quote Queries

#### `quote`
Get single quote.

```graphql
query GetQuote($requestUuid: String!, $quoteUuid: String!) {
  quote(requestUuid: $requestUuid, quoteUuid: $quoteUuid) {
    quote_uuid
    request_uuid
    provider_corp_external_id
    shipping_method
    shipping_amount
    tax_amount
    total_quote_amount
    total_quote_discount
    final_total_quote_amount
    status
    created_at
  }
}
```

#### `quoteList`
Search quotes.

```graphql
query SearchQuotes(
  $pageNumber: Int
  $limit: Int
  $requestUuid: String
  $providerCorpExternalId: String
  $statuses: [String]
  $minTotalQuoteAmount: Float
  $maxTotalQuoteAmount: Float
) {
  quoteList(
    pageNumber: $pageNumber
    limit: $limit
    requestUuid: $requestUuid
    providerCorpExternalId: $providerCorpExternalId
    statuses: $statuses
    minTotalQuoteAmount: $minTotalQuoteAmount
    maxTotalQuoteAmount: $maxTotalQuoteAmount
  ) {
    total
    quoteList {
      quote_uuid
      request_uuid
      provider_corp_external_id
      total_quote_amount
      status
    }
  }
}
```

#### `quoteItemList`
Get quote line items.

```graphql
query GetQuoteItems($quoteUuid: String!) {
  quoteItemList(quoteUuid: $quoteUuid) {
    total
    quoteItemList {
      quote_item_uuid
      quote_uuid
      item_uuid
      qty
      uom
      price_per_uom
      subtotal
      subtotal_discount
      final_subtotal
    }
  }
}
```

---

### Pricing Queries

#### `itemPriceTierList`
Get tiered pricing.

```graphql
query GetItemPriceTiers(
  $itemUuid: String
  $providerItemUuid: String
  $segmentUuid: String
) {
  itemPriceTierList(
    itemUuid: $itemUuid
    providerItemUuid: $providerItemUuid
    segmentUuid: $segmentUuid
  ) {
    total
    itemPriceTierList {
      item_price_tier_uuid
      min_quantity
      max_quantity
      price
      currency
      effective_from
      effective_to
    }
  }
}
```

#### `discountRuleList`
Get discount rules.

```graphql
query GetDiscountRules(
  $itemUuid: String
  $providerItemUuid: String
  $segmentUuid: String
) {
  discountRuleList(
    itemUuid: $itemUuid
    providerItemUuid: $providerItemUuid
    segmentUuid: $segmentUuid
  ) {
    total
    discountRuleList {
      discount_rule_uuid
      min_subtotal
      max_subtotal
      discount_percentage
      discount_amount
      effective_from
      effective_to
    }
  }
}
```

---

### Installment Queries

#### `installmentList`
Get payment schedule.

```graphql
query GetInstallments($quoteUuid: String!) {
  installmentList(quoteUuid: $quoteUuid) {
    total
    installmentList {
      installment_uuid
      quote_uuid
      priority
      scheduled_date
      installment_ratio
      installment_amount
      status
      salesorder_no
    }
  }
}
```

---

### File Queries

#### `fileList`
Get RFQ files.

```graphql
query GetRFQFiles($requestUuid: String!) {
  fileList(requestUuid: $requestUuid) {
    total
    fileList {
      request_uuid
      file_name
      file_url
      file_type
      file_size
      email
      created_at
    }
  }
}
```

---

### Segment Queries

#### `segmentList`
Search segments.

```graphql
query SearchSegments(
  $providerCorpExternalId: String
  $segmentName: String
) {
  segmentList(
    providerCorpExternalId: $providerCorpExternalId
    segmentName: $segmentName
  ) {
    total
    segmentList {
      segment_uuid
      provider_corp_external_id
      segment_name
      segment_description
    }
  }
}
```

#### `segmentContactList`
Get segment contacts.

```graphql
query GetSegmentContacts($segmentUuid: String!) {
  segmentContactList(segmentUuid: $segmentUuid) {
    total
    segmentContactList {
      segment_uuid
      contact_uuid
      email
      consumer_corp_external_id
    }
  }
}
```

---

## GraphQL Mutations

### Request Mutations

#### `insertUpdateRequest`
Create or update request.

```graphql
mutation CreateRequest(
  $requestUuid: String
  $contactUuid: String!
  $requestTitle: String!
  $requestDescription: String
  $expiredAt: DateTime
  $status: String
  $updatedBy: String!
) {
  insertUpdateRequest(
    requestUuid: $requestUuid
    contactUuid: $contactUuid
    requestTitle: $requestTitle
    requestDescription: $requestDescription
    expiredAt: $expiredAt
    status: $status
    updatedBy: $updatedBy
  ) {
    request {
      request_uuid
      status
      created_at
    }
  }
}
```

#### `deleteRequest`
Delete request.

```graphql
mutation DeleteRequest($requestUuid: String!) {
  deleteRequest(requestUuid: $requestUuid) {
    success
  }
}
```

---

### Item Mutations

#### `insertUpdateItem`
Create or update item.

```graphql
mutation CreateItem(
  $itemUuid: String
  $itemType: String!
  $itemName: String!
  $itemDescription: String
  $uoms: [String!]!
  $attributes: JSONString
  $updatedBy: String!
) {
  insertUpdateItem(
    itemUuid: $itemUuid
    itemType: $itemType
    itemName: $itemName
    itemDescription: $itemDescription
    uoms: $uoms
    attributes: $attributes
    updatedBy: $updatedBy
  ) {
    item {
      item_uuid
      item_name
    }
  }
}
```

#### `insertUpdateProviderItem`
Create or update provider item.

```graphql
mutation CreateProviderItem(
  $providerItemUuid: String
  $itemUuid: String!
  $providerCorpExternalId: String!
  $providerItemExternalId: String!
  $basePricePerUom: Float!
  $currency: String!
  $leadTimeDays: Int
  $minOrderQty: Float
  $updatedBy: String!
) {
  insertUpdateProviderItem(
    providerItemUuid: $providerItemUuid
    itemUuid: $itemUuid
    providerCorpExternalId: $providerCorpExternalId
    providerItemExternalId: $providerItemExternalId
    basePricePerUom: $basePricePerUom
    currency: $currency
    leadTimeDays: $leadTimeDays
    minOrderQty: $minOrderQty
    updatedBy: $updatedBy
  ) {
    providerItem {
      provider_item_uuid
      base_price_per_uom
    }
  }
}
```

---

### Quote Mutations

#### `insertUpdateQuote`
Create or update quote.

```graphql
mutation CreateQuote(
  $quoteUuid: String
  $requestUuid: String!
  $providerCorpExternalId: String!
  $shippingMethod: String!
  $shippingAmount: Float!
  $taxAmount: Float
  $status: String
  $notes: String
  $updatedBy: String!
) {
  insertUpdateQuote(
    quoteUuid: $quoteUuid
    requestUuid: $requestUuid
    providerCorpExternalId: $providerCorpExternalId
    shippingMethod: $shippingMethod
    shippingAmount: $shippingAmount
    taxAmount: $taxAmount
    status: $status
    notes: $notes
    updatedBy: $updatedBy
  ) {
    quote {
      quote_uuid
      total_quote_amount
      status
    }
  }
}
```

#### `insertUpdateQuoteItem`
Create or update quote line item.

```graphql
mutation AddQuoteItem(
  $quoteItemUuid: String
  $quoteUuid: String!
  $providerItemUuid: String!
  $itemUuid: String!
  $batchNo: String
  $qty: Float!
  $uom: String!
  $pricePerUom: Float!
  $notes: String
  $updatedBy: String!
) {
  insertUpdateQuoteItem(
    quoteItemUuid: $quoteItemUuid
    quoteUuid: $quoteUuid
    providerItemUuid: $providerItemUuid
    itemUuid: $itemUuid
    batchNo: $batchNo
    qty: $qty
    uom: $uom
    pricePerUom: $pricePerUom
    notes: $notes
    updatedBy: $updatedBy
  ) {
    quoteItem {
      quote_item_uuid
      subtotal
      final_subtotal
    }
  }
}
```

#### `deleteQuoteItem`
Remove quote line item.

```graphql
mutation DeleteQuoteItem($quoteUuid: String!, $quoteItemUuid: String!) {
  deleteQuoteItem(quoteUuid: $quoteUuid, quoteItemUuid: $quoteItemUuid) {
    success
  }
}
```

---

### Pricing Mutations

#### `insertUpdateItemPriceTier`
Create or update price tier.

```graphql
mutation CreatePriceTier(
  $itemPriceTierUuid: String
  $itemUuid: String!
  $providerItemUuid: String
  $segmentUuid: String
  $minQuantity: Float!
  $maxQuantity: Float
  $price: Float!
  $currency: String!
  $effectiveFrom: DateTime
  $effectiveTo: DateTime
  $updatedBy: String!
) {
  insertUpdateItemPriceTier(
    itemPriceTierUuid: $itemPriceTierUuid
    itemUuid: $itemUuid
    providerItemUuid: $providerItemUuid
    segmentUuid: $segmentUuid
    minQuantity: $minQuantity
    maxQuantity: $maxQuantity
    price: $price
    currency: $currency
    effectiveFrom: $effectiveFrom
    effectiveTo: $effectiveTo
    updatedBy: $updatedBy
  ) {
    itemPriceTier {
      item_price_tier_uuid
      price
    }
  }
}
```

#### `insertUpdateDiscountRule`
Create or update discount rule.

```graphql
mutation CreateDiscountRule(
  $discountRuleUuid: String
  $itemUuid: String!
  $providerItemUuid: String
  $segmentUuid: String
  $minSubtotal: Float
  $maxSubtotal: Float
  $discountPercentage: Float!
  $discountAmount: Float
  $effectiveFrom: DateTime
  $effectiveTo: DateTime
  $updatedBy: String!
) {
  insertUpdateDiscountRule(
    discountRuleUuid: $discountRuleUuid
    itemUuid: $itemUuid
    providerItemUuid: $providerItemUuid
    segmentUuid: $segmentUuid
    minSubtotal: $minSubtotal
    maxSubtotal: $maxSubtotal
    discountPercentage: $discountPercentage
    discountAmount: $discountAmount
    effectiveFrom: $effectiveFrom
    effectiveTo: $effectiveTo
    updatedBy: $updatedBy
  ) {
    discountRule {
      discount_rule_uuid
      discount_percentage
    }
  }
}
```

---

### Installment Mutations

#### `insertUpdateInstallment`
Create or update installment.

```graphql
mutation CreateInstallment(
  $installmentUuid: String
  $quoteUuid: String!
  $priority: Int!
  $scheduledDate: DateTime!
  $installmentRatio: Float!
  $status: String
  $salesorderNo: String
  $notes: String
  $updatedBy: String!
) {
  insertUpdateInstallment(
    installmentUuid: $installmentUuid
    quoteUuid: $quoteUuid
    priority: $priority
    scheduledDate: $scheduledDate
    installmentRatio: $installmentRatio
    status: $status
    salesorderNo: $salesorderNo
    notes: $notes
    updatedBy: $updatedBy
  ) {
    installment {
      installment_uuid
      installment_amount
      status
    }
  }
}
```

---

### File Mutations

#### `insertUpdateFile`
Upload file.

```graphql
mutation UploadFile(
  $requestUuid: String!
  $fileName: String!
  $fileUrl: String!
  $fileType: String
  $fileSize: Int
  $email: String!
  $notes: String
  $updatedBy: String!
) {
  insertUpdateFile(
    requestUuid: $requestUuid
    fileName: $fileName
    fileUrl: $fileUrl
    fileType: $fileType
    fileSize: $fileSize
    email: $email
    notes: $notes
    updatedBy: $updatedBy
  ) {
    file {
      request_uuid
      file_name
      file_url
    }
  }
}
```

---

### Segment Mutations

#### `insertUpdateSegment`
Create or update segment.

```graphql
mutation CreateSegment(
  $segmentUuid: String
  $providerCorpExternalId: String!
  $segmentName: String!
  $segmentDescription: String
  $updatedBy: String!
) {
  insertUpdateSegment(
    segmentUuid: $segmentUuid
    providerCorpExternalId: $providerCorpExternalId
    segmentName: $segmentName
    segmentDescription: $segmentDescription
    updatedBy: $updatedBy
  ) {
    segment {
      segment_uuid
      segment_name
    }
  }
}
```

#### `insertUpdateSegmentContact`
Add contact to segment.

```graphql
mutation AddContactToSegment(
  $segmentUuid: String!
  $contactUuid: String!
  $email: String!
  $consumerCorpExternalId: String
  $updatedBy: String!
) {
  insertUpdateSegmentContact(
    segmentUuid: $segmentUuid
    contactUuid: $contactUuid
    email: $email
    consumerCorpExternalId: $consumerCorpExternalId
    updatedBy: $updatedBy
  ) {
    segmentContact {
      segment_uuid
      contact_uuid
      email
    }
  }
}
```

---

## MCP Tool to GraphQL Mapping

| MCP Tool | GraphQL Operation | Type | Operation Name |
|----------|-------------------|------|----------------|
| submit_rfq_request | Mutation | insertUpdateRequest | insertUpdateRequest |
| get_rfq_request | Query | request | request |
| search_rfq_requests | Query | requestList | requestList |
| search_items | Query | itemList | itemList |
| get_item | Query | item | item |
| get_provider_items | Query | providerItemList | providerItemList |
| get_provider_item_batches | Query | providerItemBatchList | providerItemBatchList |
| create_quote | Mutation | insertUpdateQuote | insertUpdateQuote |
| get_quote | Query | quote | quote |
| update_quote_status | Mutation | insertUpdateQuote | insertUpdateQuote |
| search_quotes | Query | quoteList | quoteList |
| add_quote_item | Mutation | insertUpdateQuoteItem | insertUpdateQuoteItem |
| update_quote_item | Mutation | insertUpdateQuoteItem | insertUpdateQuoteItem |
| delete_quote_item | Mutation | deleteQuoteItem | deleteQuoteItem |
| get_item_price_tiers | Query | itemPriceTierList | itemPriceTierList |
| get_discount_rules | Query | discountRuleList | discountRuleList |
| calculate_quote_pricing | Custom | Multiple queries | (business logic) |
| create_installment | Mutation | insertUpdateInstallment | insertUpdateInstallment |
| get_installments | Query | installmentList | installmentList |
| upload_rfq_file | Mutation | insertUpdateFile | insertUpdateFile |
| get_rfq_files | Query | fileList | fileList |
| create_segment | Mutation | insertUpdateSegment | insertUpdateSegment |
| add_contact_to_segment | Mutation | insertUpdateSegmentContact | insertUpdateSegmentContact |
| get_segment_contacts | Query | segmentContactList | segmentContactList |

---

## Error Handling

### GraphQL Error Response Format

```json
{
  "errors": [
    {
      "message": "Error description",
      "locations": [{"line": 2, "column": 3}],
      "path": ["operationName"]
    }
  ]
}
```

### Common Error Codes

- **400**: Bad Request - Invalid input parameters
- **401**: Unauthorized - Invalid AWS credentials
- **403**: Forbidden - Insufficient permissions
- **404**: Not Found - Resource does not exist
- **500**: Internal Server Error - Server-side error
- **503**: Service Unavailable - Lambda timeout or unavailable

### MCP Tool Error Response

```json
{
  "error": {
    "code": "GRAPHQL_ERROR",
    "message": "Failed to execute GraphQL query",
    "details": "Original GraphQL error message"
  }
}
```

---

## Performance Considerations

### Query Optimization
- Use pagination for list queries (default limit: 50)
- Request only required fields
- Cache GraphQL schemas (implemented)
- Batch related queries when possible

### Recommended Limits
- **Item List**: 50-100 items per page
- **Request List**: 20-50 requests per page
- **Quote List**: 20-50 quotes per page
- **Quote Items**: 100 items per quote

### Timeout Configuration
- Default Lambda timeout: 120 seconds
- Recommended timeout for complex queries: 60 seconds
- Retry strategy: Exponential backoff (3 attempts)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2025-11-05 | Initial API reference |
