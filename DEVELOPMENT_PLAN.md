# Development Plan: MCP RFQ Processor Integration

## Project Overview

This document outlines the complete development plan for integrating the `ai_rfq_engine` GraphQL backend with the `mcp_rfq_processor` MCP server, following the proven patterns from `mcp_marketing_collection`.

## Status Flow & Business Rules

### Request Status Flow

```
request (initial)
    ↓
request (in_progress)
    • add items
    • update items  
    • remove items
    ↓
request (confirmed)
    • create quote
    ↓
request (completed) or request (modified)
```

**Request Status Definitions:**
- **initial**: Request has been created but not yet being worked on
- **in_progress**: Request is being edited, items can be added/updated/removed
- **confirmed**: Request is finalized and ready for quote creation
- **completed**: Request has been fulfilled with an approved quote
- **modified**: Request was changed after quote creation (triggers quote disapproval)

### Quote Status Flow

```
quote (initial)
    ↓
quote (in_progress)
    • add quote items
    • update quote items (apply discount, adjust quantity)
    • remove quote items
    ↓
quote (completed) or quote (disapproved)
```

**Quote Status Definitions:**
- **initial**: Quote has been created but not yet being worked on
- **in_progress**: Quote is being edited, items can be added/updated/removed
- **completed**: Quote has been finalized and approved
- **disapproved**: Quote was rejected or invalidated

### Critical Business Rules

1. **Request Modification Impact on Quotes**
   - When a request status changes to `modified`, all related quotes (regardless of their current status) are automatically changed to `disapproved`
   - This ensures quotes always reflect the current request state
   - A request becomes `modified` when items are changed after a quote has been created
   - When the modified request is confirmed again, a new quote must be submitted
   - Old disapproved quotes remain in the system for audit trail purposes

2. **Quote Item Management**
   - Quote items can be freely added, updated, or removed while quote status is `initial` or `in_progress`
   - Use `add_quote_item` to add new items to a quote
   - Use `update_quote_item` to modify existing items (discount, quantity, etc.)
   - Use `remove_quote_item` to remove items from a quote

3. **Request Item Management**
   - Request items can be freely added, updated, or removed while request status is `initial` or `in_progress`
   - Use `update_rfq_request` with `items` array to bulk replace items
   - Use `add_item_to_rfq_request` to add individual items
   - Use `remove_item_from_rfq_request` to remove items by UUID or name

4. **Audit Trail**
   - All status changes are logged with timestamps
   - Modified requests maintain history of previous quotes
   - Disapproved quotes remain in the system for audit purposes

## Reference Architecture

### ai_rfq_engine (Backend)
- **Type**: GraphQL API with Graphene
- **Function**: `ai_rfq_graphql`
- **Data Models**:
  - Items (products/services catalog)
  - Segments (customer/provider pricing groups)
  - SegmentContacts (customer associations)
  - ProviderItems (supplier inventory)
  - ProviderItemBatches (lot tracking)
  - ItemPriceTiers (quantity-based pricing)
  - DiscountRules (promotional discounts)
  - Requests (RFQ submissions)
  - Quotes (price quotations)
  - QuoteItems (quote line items)
  - Installments (payment schedules)
  - Files (document attachments)

### mcp_marketing_collection (Reference Pattern)
- MCP tool definitions with detailed descriptions
- AWS Lambda client initialization
- GraphQL schema caching
- GraphQL query generation and execution
- Response transformation (camelCase → snake_case)
- Error handling patterns

### mcp_rfq_processor (Target Implementation)
- Basic GraphQL execution framework exists
- Needs: MCP tool definitions and business logic

---

## Phase 1: Foundation Setup

### 1.1 Project Structure
**Priority**: Critical
**Estimated Time**: 2 hours

```
mcp_rfq_processor/
├── __init__.py                    # Package initialization
├── mcp_rfq_processor.py          # Main class (existing, to be enhanced)
├── pyproject.toml                # Project dependencies
├── README.md                     # User documentation (COMPLETED)
├── DEVELOPMENT_PLAN.md           # This file
├── API_REFERENCE.md              # GraphQL schema reference
└── tests/
    ├── __init__.py
    ├── test_rfq_request.py       # Request management tests
    ├── test_quote.py             # Quote management tests
    ├── test_items.py             # Item search tests
    └── conftest.py               # Pytest fixtures
```

**Tasks**:
- [x] Create README.md with usage documentation
- [ ] Create pyproject.toml with dependencies
- [ ] Create API_REFERENCE.md
- [ ] Set up test directory structure

### 1.2 Dependencies Configuration
**Priority**: Critical
**Estimated Time**: 1 hour

Create `pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "mcp-rfq-processor"
version = "0.1.0"
description = "MCP server for RFQ processing with ai_rfq_engine integration"
readme = "README.md"
requires-python = ">=3.8"
license = {text = "MIT"}
authors = [
    {name = "Idea Bosque", email = "ideabosque@gmail.com"}
]

dependencies = [
    "boto3>=1.28",
    "humps>=0.2",
    "pendulum>=2.1",
    "silvaengine-utility",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "python-dotenv>=1.0",
    "black>=23.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
```

---

## Phase 2: MCP Tool Definitions

### 2.1 MCP Configuration Structure
**Priority**: Critical
**Estimated Time**: 4 hours

Add to `mcp_rfq_processor.py`:

```python
MCP_CONFIGURATION = {
    "tools": [
        # Request Management Tools (4)
        {
            "name": "submit_rfq_request",
            "description": "Submit a new RFQ request...",
            "inputSchema": {...}
        },
        {
            "name": "update_rfq_request",
            "description": "Update existing RFQ request. Use when modifying items - requires creating new quote...",
            "inputSchema": {...}
        },
        {
            "name": "get_rfq_request",
            "description": "Retrieve RFQ request details...",
            "inputSchema": {...}
        },
        {
            "name": "search_rfq_requests",
            "description": "Search and filter RFQ requests...",
            "inputSchema": {...}
        },
        
        # Item Management Tools (4)
        {
            "name": "search_items",
            "description": "Search available items...",
            "inputSchema": {...}
        },
        {
            "name": "get_item",
            "description": "Get item details...",
            "inputSchema": {...}
        },
        {
            "name": "get_provider_items",
            "description": "Search provider inventory...",
            "inputSchema": {...}
        },
        {
            "name": "get_provider_item_batches",
            "description": "Get batch information...",
            "inputSchema": {...}
        },
        
        # Quote Management Tools (5)
        {
            "name": "create_quote",
            "description": "Create new quote. Items cannot be added/deleted after creation...",
            "inputSchema": {...}
        },
        {
            "name": "update_quote",
            "description": "Update quote metadata (shipping, tax, status, notes)...",
            "inputSchema": {...}
        },
        {
            "name": "get_quote",
            "description": "Retrieve quote details...",
            "inputSchema": {...}
        },
        {
            "name": "search_quotes",
            "description": "Search quotes...",
            "inputSchema": {...}
        },
        {
            "name": "update_quote_item_discount",
            "description": "Update discount for quote item. Only allowed item modification...",
            "inputSchema": {...}
        },
        
        # Pricing Tools (3)
        {
            "name": "get_item_price_tiers",
            "description": "Get tiered pricing...",
            "inputSchema": {...}
        },
        {
            "name": "get_discount_rules",
            "description": "Get discount rules...",
            "inputSchema": {...}
        },
        {
            "name": "calculate_quote_pricing",
            "description": "Calculate final pricing...",
            "inputSchema": {...}
        },
        
        # Installment Tools (2)
        {
            "name": "create_installment",
            "description": "Create payment installment...",
            "inputSchema": {...}
        },
        {
            "name": "get_installments",
            "description": "Get installment schedule...",
            "inputSchema": {...}
        },
        
        # File Tools (2)
        {
            "name": "upload_rfq_file",
            "description": "Upload RFQ document...",
            "inputSchema": {...}
        },
        {
            "name": "get_rfq_files",
            "description": "Get RFQ files...",
            "inputSchema": {...}
        },
        
        # Segment Tools (3)
        {
            "name": "create_segment",
            "description": "Create pricing segment...",
            "inputSchema": {...}
        },
        {
            "name": "add_contact_to_segment",
            "description": "Add contact to segment...",
            "inputSchema": {...}
        },
        {
            "name": "get_segment_contacts",
            "description": "List segment contacts...",
            "inputSchema": {...}
        },
    ],
    "resources": [],
    "prompts": [],
    "module_links": [
        # Map each tool to MCPRfqProcessor methods
        {
            "type": "tool",
            "name": "submit_rfq_request",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
            "function_name": "submit_rfq_request",
            "return_type": "text",
        },
        # ... (23 more mappings)
    ],
    "modules": [
        {
            "package_name": "mcp_rfq_processor",
            "module_name": "mcp_rfq_processor",
            "class_name": "MCPRfqProcessor",
                "setting": {
                    "keyword": "rfq",
                    "default_currency": "USD",
                    "default_page_limit": 50,
                },
        }
    ],
}
```

**Tasks**:
- [ ] Define all 24 MCP tools with complete inputSchema
- [ ] Create module_links mapping
- [ ] Define module settings

---

## Phase 3: Core Implementation (Priority Tools)

### 3.1 Request Management
**Priority**: Critical (Phase 1)
**Estimated Time**: 8 hours

**IMPORTANT BUSINESS RULES**:
1. Requests can be created and updated
2. When quote items need modification (add/delete), the request must be updated and a new quote created
3. This ensures proper audit trail and version control

#### Tool: `submit_rfq_request`
```python
def submit_rfq_request(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Submit new RFQ request.
    Maps to GraphQL: insertUpdateRequest mutation
    """
    try:
        self.logger.info(f"Submitting RFQ request: {arguments}")
        
        variables = {
            "contactUuid": arguments["contact_uuid"],
            "requestTitle": arguments["request_title"],
            "requestDescription": arguments.get("request_description", ""),
            "expiredAt": arguments.get("expired_at"),
            "status": arguments.get("status", "pending"),
            "updatedBy": "MCP",
        }
        
        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "insertUpdateRequest",
            "Mutation",
            variables,
        )
        
        request = humps.decamelize(
            result["insertUpdateRequest"]["request"]
        )
        
        return {
            "request_uuid": request["request_uuid"],
            "status": request["status"],
            "created_at": request["created_at"],
        }
    except Exception as e:
        self.logger.error(f"Failed to submit RFQ: {e}")
        raise
```

#### Tool: `update_rfq_request`
```python
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
            "contactUuid": arguments.get("contact_uuid"),
            "requestTitle": arguments.get("request_title"),
            "requestDescription": arguments.get("request_description"),
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
        
        request = humps.decamelize(
            result["insertUpdateRequest"]["request"]
        )
        
        return {
            "request_uuid": request["request_uuid"],
            "status": request["status"],
            "updated_at": request["updated_at"],
        }
    except Exception as e:
        self.logger.error(f"Failed to update RFQ: {e}")
        raise
```

#### Tool: `get_rfq_request`
```python
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
```

#### Tool: `search_rfq_requests`
```python
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
```

**Tasks**:
- [ ] Implement submit_rfq_request
- [ ] Implement update_rfq_request (NEW)
- [ ] Implement get_rfq_request
- [ ] Implement search_rfq_requests
- [ ] Write unit tests for request management

### 3.2 Item Search & Discovery
**Priority**: Critical (Phase 1)
**Estimated Time**: 5 hours

#### Tool: `search_items`
```python
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
```

#### Tool: `get_item`
```python
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
```

#### Tool: `get_provider_items`
```python
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
```

**Tasks**:
- [ ] Implement search_items
- [ ] Implement get_item
- [ ] Implement get_provider_items
- [ ] Implement get_provider_item_batches
- [ ] Write unit tests for item management

### 3.3 Quote Management
**Priority**: Critical (Phase 1)
**Estimated Time**: 10 hours

**IMPORTANT BUSINESS RULES**:
1. Quote items CANNOT be added or deleted directly after quote creation
2. To modify quote items (add/delete): Update the request → Create new quote
3. Quote item discounts CAN be updated on existing quotes
4. Quote metadata (shipping, tax, status, etc.) CAN be updated

#### Tool: `create_quote`
```python
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
            "shippingMethod": arguments.get("shipping_method", "standard"),
            "shippingAmount": arguments.get("shipping_amount", 0.0),
            "taxAmount": arguments.get("tax_amount", 0.0),
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
        
        return {
            "quote_uuid": quote["quote_uuid"],
            "request_uuid": quote["request_uuid"],
            "total_quote_amount": quote["total_quote_amount"],
            "status": quote["status"],
        }
    except Exception as e:
        self.logger.error(f"Failed to create quote: {e}")
        raise
```

#### Tool: `update_quote`
```python
def update_quote(self, **arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update quote metadata (shipping, tax, status, notes).
    Maps to GraphQL: insertUpdateQuote mutation
    
    Can update:
    - shippingMethod, shippingAmount
    - taxAmount
    - status
    - notes
    
    Cannot modify quote items - use update_quote_item_discount instead
    """
    try:
        self.logger.info(f"Updating quote: {arguments}")
        
        variables = {
            "quoteUuid": arguments["quote_uuid"],
            "shippingMethod": arguments.get("shipping_method"),
            "shippingAmount": arguments.get("shipping_amount"),
            "taxAmount": arguments.get("tax_amount"),
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
        
        return {
            "quote_uuid": quote["quote_uuid"],
            "total_quote_amount": quote["total_quote_amount"],
            "status": quote["status"],
            "updated_at": quote["updated_at"],
        }
    except Exception as e:
        self.logger.error(f"Failed to update quote: {e}")
        raise
```

#### Tool: `update_quote_item_discount`
```python
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
            "quoteItemUuid": arguments["quote_item_uuid"],
            "discountAmount": arguments.get("discount_amount", 0.0),
            "discountPercent": arguments.get("discount_percent", 0.0),
            "discountNotes": arguments.get("discount_notes", ""),
            "updatedBy": "MCP",
        }
        
        result = self._execute_graphql_query(
            "ai_rfq_graphql",
            "insertUpdateQuoteItem",
            "Mutation",
            variables,
        )
        
        quote_item = humps.decamelize(
            result["insertUpdateQuoteItem"]["quoteItem"]
        )
        
        return {
            "quote_item_uuid": quote_item["quote_item_uuid"],
            "discount_amount": quote_item["discount_amount"],
            "discount_percent": quote_item["discount_percent"],
            "total_amount": quote_item["total_amount"],
        }
    except Exception as e:
        self.logger.error(f"Failed to update quote item discount: {e}")
        raise
```

**Tasks**:
- [ ] Implement create_quote
- [ ] Implement update_quote (NEW - replaces update_quote_status)
- [ ] Implement update_quote_item_discount (NEW - replaces add/update/delete_quote_item)
- [ ] Implement get_quote
- [ ] Implement search_quotes
- [ ] Write unit tests for quote management
- [ ] Document workflow: modify items → update request → create new quote

---

## Phase 4: Advanced Features

### 4.1 Pricing & Discounts
**Priority**: High (Phase 2)
**Estimated Time**: 4 hours

**Tools to implement**:
- `get_item_price_tiers` - Query itemPriceTierList
- `get_discount_rules` - Query discountRuleList
- `calculate_quote_pricing` - Custom logic combining multiple queries

**Tasks**:
- [ ] Implement get_item_price_tiers
- [ ] Implement get_discount_rules
- [ ] Implement calculate_quote_pricing (business logic)
- [ ] Write pricing calculation tests

### 4.2 Installment Management
**Priority**: Medium (Phase 2)
**Estimated Time**: 3 hours

**Tools to implement**:
- `create_installment` - Mutation insertUpdateInstallment
- `get_installments` - Query installmentList

**Tasks**:
- [ ] Implement create_installment
- [ ] Implement get_installments
- [ ] Write installment tests

### 4.3 Document Management
**Priority**: Medium (Phase 3)
**Estimated Time**: 3 hours

**Tools to implement**:
- `upload_rfq_file` - Mutation insertUpdateFile
- `get_rfq_files` - Query fileList

**Tasks**:
- [ ] Implement upload_rfq_file
- [ ] Implement get_rfq_files
- [ ] Write file management tests

### 4.4 Segment Management
**Priority**: Low (Phase 3)
**Estimated Time**: 4 hours

**Tools to implement**:
- `create_segment` - Mutation insertUpdateSegment
- `add_contact_to_segment` - Mutation insertUpdateSegmentContact
- `get_segment_contacts` - Query segmentContactList

**Tasks**:
- [ ] Implement create_segment
- [ ] Implement add_contact_to_segment
- [ ] Implement get_segment_contacts
- [ ] Write segment management tests

---

## Phase 5: Testing & Quality

### 5.1 Unit Tests
**Priority**: Critical
**Estimated Time**: 8 hours

**Test Coverage**:
- Request management (3 tools)
- Item search (4 tools)
- Quote management (7 tools)
- Pricing (3 tools)
- Installments (2 tools)
- Files (2 tools)
- Segments (3 tools)

**Mock Strategy**:
```python
# conftest.py
import pytest
from unittest.mock import Mock

@pytest.fixture
def mock_aws_lambda():
    return Mock()

@pytest.fixture
def rfq_processor(mock_aws_lambda):
    from mcp_rfq_processor import MCPRfqProcessor
    import logging
    
    processor = MCPRfqProcessor(
        logger=logging.getLogger("test"),
        region_name="us-east-1",
        execute_mode="local",
    )
    processor._aws_lambda = mock_aws_lambda
    processor.endpoint_id = "test-endpoint"
    return processor

@pytest.fixture
def mock_graphql_response():
    def _mock(operation_name, data):
        return {operation_name: data}
    return _mock
```

**Tasks**:
- [ ] Set up pytest configuration
- [ ] Create test fixtures
- [ ] Write unit tests for each tool
- [ ] Achieve >80% code coverage
- [ ] Test error scenarios

### 5.2 Integration Tests
**Priority**: High
**Estimated Time**: 6 hours

**Test Scenarios**:
1. Complete RFQ workflow (submit → quote → accept)
2. Multi-item quote with discounts
3. Installment payment schedule
4. File upload and retrieval
5. Segment-based pricing

**Tasks**:
- [ ] Set up test environment with ai_rfq_engine
- [ ] Write integration test suite
- [ ] Test with real AWS Lambda
- [ ] Document test data requirements

---

## Phase 6: Documentation

### 6.1 API Reference
**Priority**: High
**Estimated Time**: 4 hours

Create `API_REFERENCE.md` with:
- Complete GraphQL schema mapping
- All query operations
- All mutation operations
- Type definitions
- Example GraphQL queries

**Tasks**:
- [ ] Document all GraphQL operations
- [ ] Map MCP tools to GraphQL operations
- [ ] Include example queries
- [ ] Document error codes

### 6.2 Developer Guide
**Priority**: Medium
**Estimated Time**: 3 hours

Add to README.md:
- Development setup instructions
- How to add new tools
- Testing guide
- Troubleshooting

**Tasks**:
- [ ] Write development setup guide
- [ ] Document architecture decisions
- [ ] Create troubleshooting section
- [ ] Add contribution guidelines

---

## Phase 7: Deployment & Release

### 7.1 Package Preparation
**Priority**: High
**Estimated Time**: 2 hours

**Tasks**:
- [ ] Finalize pyproject.toml
- [ ] Create __init__.py exports
- [ ] Add version management
- [ ] Create CHANGELOG.md

### 7.2 CI/CD Setup (Optional)
**Priority**: Low
**Estimated Time**: 4 hours

**Tasks**:
- [ ] Set up GitHub Actions
- [ ] Add automated testing
- [ ] Add code quality checks (black, flake8)
- [ ] Set up automated releases

---

## Implementation Timeline

### Week 1: Foundation & Core (40 hours)
- Phase 1: Foundation Setup (3 hours)
- Phase 2: MCP Tool Definitions (4 hours)
- Phase 3.1: Request Management (6 hours)
- Phase 3.2: Item Search (5 hours)
- Phase 3.3: Quote Management (8 hours)
- Phase 5.1: Basic Unit Tests (14 hours)

### Week 2: Advanced Features (40 hours)
- Phase 4.1: Pricing & Discounts (4 hours)
- Phase 4.2: Installment Management (3 hours)
- Phase 4.3: Document Management (3 hours)
- Phase 4.4: Segment Management (4 hours)
- Phase 5.1: Complete Unit Tests (12 hours)
- Phase 5.2: Integration Tests (6 hours)
- Phase 6: Documentation (8 hours)

### Week 3: Polish & Release (16 hours)
- Testing refinement (8 hours)
- Documentation review (4 hours)
- Phase 7: Deployment prep (4 hours)

**Total Estimated Time**: 98 hours (12.3 days)

**Updated based on new business requirements (2025-11-06)**:
- Added request update capability
- Removed direct quote item add/delete operations
- Added quote item discount update capability
- Modified workflow: item changes require request update + new quote creation

---

## Workflows

### Core RFQ to Quote Workflow

```
1. Submit RFQ Request
   └─> submit_rfq_request(contact_uuid, request_title, request_description)
       └─> Returns: request_uuid

2. Search Items
   └─> search_items(item_type, item_name)
       └─> Returns: item catalog

3. Check Provider Inventory
   └─> get_provider_items(item_uuid, provider_corp_external_id)
       └─> Returns: available provider items with pricing

4. Get User Confirmation
   └─> Present items and pricing to user for approval
       └─> User confirms or requests modifications

5. Create Quote (After User Confirmation)
   └─> create_quote(request_uuid, provider_corp_external_id, items[])
       └─> Returns: quote_uuid with auto-generated quote items
       └─> Quote items are created automatically based on items array

6. Add Items to Quote
   └─> Items are added during quote creation (step 5)
       └─> Each item becomes a quote_item with:
           ├─> item_uuid
           ├─> provider_item_uuid
           ├─> quantity
           ├─> unit_price
           └─> initial discount (if any)

7. Get Discount Rules
   └─> get_discount_rules(item_uuid, segment_uuid, quantity)
       └─> Returns: applicable discount rules
       └─> Evaluate rules based on:
           ├─> Item type
           ├─> Customer segment
           ├─> Quantity thresholds
           ├─> Date ranges (valid_from, valid_to)
           └─> Promotional campaigns

8. Apply Discounts to Quote Items
   └─> For each applicable discount:
       └─> update_quote_item_discount(
              quote_item_uuid,
              discount_amount OR discount_percent,
              discount_notes="Rule: [rule_name]"
           )
       └─> Backend automatically recalculates pricing

9. Update Quote Metadata
   └─> update_quote(quote_uuid, shipping_amount, tax_amount, notes)
       └─> Add shipping costs
       └─> Add tax calculations
       └─> Update status as needed
       └─> Backend automatically recalculates total_quote_amount

10. Create Payment Installments (optional)
    └─> create_installment(quote_uuid, installment_schedule[])
        └─> For each installment:
            ├─> installment_number
            ├─> due_date
            ├─> amount
            └─> status

11. Attach Supporting Documents (optional)
    └─> upload_rfq_file(request_uuid, file_data, file_type)
        └─> Upload quotes, specifications, terms

12. Finalize Quote
    └─> update_quote(quote_uuid, status="submitted")
        └─> Locks quote for customer review
        └─> Backend provides final calculated totals
```

### New Request Workflow (Complete Process)

```
Scenario: Customer submits a new RFQ request

1. Submit New Request
   └─> submit_rfq_request(
          contact_uuid="contact-123",
          request_title="Office supplies procurement",
          request_description="Need office supplies for Q1",
          expired_at="2025-12-31"
       )
       └─> Returns: request_uuid="req-456"

2. Search and Select Items
   └─> search_items(item_type="supplies")
       └─> User selects items with quantities

3. Get User Confirmation
   └─> Present selected items and estimated pricing
       └─> User confirms: "Yes, proceed with quote"

4. Create Quote with Items
   └─> create_quote(
          request_uuid="req-456",
          provider_corp_external_id="provider-789",
          items=[
             {item_uuid: "item-A", quantity: 100, unit_price: 10.00},
             {item_uuid: "item-B", quantity: 50, unit_price: 25.00}
          ]
       )
       └─> Returns: quote_uuid="quote-101"
       └─> Auto-creates quote_items in database

5. Get Discount Rules
   └─> get_discount_rules(
          item_uuid="item-A",
          segment_uuid="segment-corporate",
          quantity=100
       )
       └─> Returns: applicable discount rules
       └─> Example: 10% discount for quantities > 50

6. Apply Discounts
   └─> update_quote_item_discount(
          quote_item_uuid="qi-A",
          discount_percent=10.0,
          discount_notes="Volume discount rule: CORP-VOL-10"
       )
       └─> Backend automatically recalculates quote totals

7. Update Quote with Shipping/Tax
   └─> update_quote(
          quote_uuid="quote-101",
          shipping_amount=50.00,
          tax_amount=125.00
       )
       └─> Backend automatically recalculates total_quote_amount

8. Finalize and Submit
    └─> update_quote(quote_uuid="quote-101", status="submitted")
        └─> Backend provides final calculated totals
```

### Modify Request Workflow (Complete Process)

**IMPORTANT**: Quote items cannot be added or deleted after quote creation.

```
Scenario: Customer wants to modify an existing request (add/remove items)

1. Current State
   ├─> Request UUID: req-123
   ├─> Quote UUID: quote-456
   └─> Quote Items: [item-A (qty: 100), item-B (qty: 50)]

2. Customer Requests Modification
   └─> "I want to add item-C and remove item-B"

3. Search for New Items
   └─> search_items(item_name="item-C")
       └─> User confirms item-C selection

4. Get User Confirmation for Changes
   └─> Present new item list: [item-A, item-C]
       └─> User confirms: "Yes, create new quote with these items"

5. Update Request
   └─> update_rfq_request(
          request_uuid="req-123",
          request_description="Updated: Added item-C, removed item-B",
          status="modified"
       )
       └─> Returns: updated request

6. Create New Quote with Modified Items
   └─> create_quote(
          request_uuid="req-123",
          provider_corp_external_id="provider-789",
          items=[
             {item_uuid: "item-A", quantity: 100, unit_price: 10.00},
             {item_uuid: "item-C", quantity: 75, unit_price: 15.00}
          ]
       )
       └─> Returns: new quote_uuid="quote-789"

7. Mark Old Quote as Superseded (optional)
   └─> update_quote(
          quote_uuid="quote-456",
          status="superseded",
          notes="Replaced by quote-789"
       )

8. Get Discount Rules for New Quote
   └─> get_discount_rules() for each item in new quote
       └─> Apply to item-A (existing)
       └─> Apply to item-C (new)

9. Apply Discounts to New Quote Items
   └─> update_quote_item_discount() for applicable items
       └─> Backend automatically recalculates quote totals

10. Update Quote Metadata
    └─> update_quote(
           quote_uuid="quote-789",
           shipping_amount=60.00,
           tax_amount=150.00
        )
        └─> Backend automatically recalculates total_quote_amount

11. Finalize New Quote
    └─> update_quote(quote_uuid="quote-789", status="submitted")
        └─> Backend provides final calculated totals

12. Result
    ├─> Old Quote (quote-456): Status "superseded"
    ├─> New Quote (quote-789): Contains updated items [A, C]
    └─> Audit Trail: Both quotes linked to request req-123
```

### Discount Management Workflow

```
Scenario: Apply discounts to quote items

1. Get Quote Details
   └─> get_quote(quote_uuid)
       └─> Returns: quote with quote_items[]

2. Update Individual Item Discounts
   ├─> update_quote_item_discount(
   │      quote_item_uuid=item-1,
   │      discount_percent=10.0,
   │      discount_notes="Volume discount"
   │   )
   │
   ├─> update_quote_item_discount(
   │      quote_item_uuid=item-2,
   │      discount_amount=50.0,
   │      discount_notes="Promotional discount"
   │   )
   │
   └─> Returns: updated quote items with recalculated totals

3. Quote automatically recalculates total_quote_amount
```

---

## Success Criteria

### Functional Requirements
- ✅ All 22 MCP tools implemented (updated count: removed 3 quote item tools, added 2 new tools)
- ✅ GraphQL integration working
- ✅ Complete RFQ workflow functional
- ✅ Error handling robust
- ✅ >80% test coverage

### Quality Requirements
- ✅ Code follows PEP 8
- ✅ All tests passing
- ✅ Documentation complete
- ✅ No security vulnerabilities
- ✅ Performance acceptable (<2s per operation)

### User Experience
- ✅ Clear error messages
- ✅ Comprehensive documentation
- ✅ Working examples
- ✅ Easy configuration

---

## Risk Management

### Technical Risks
1. **GraphQL schema changes**
   - Mitigation: Schema version pinning, validation tests
   
2. **AWS Lambda timeouts**
   - Mitigation: Query optimization, timeout configuration
   
3. **Data consistency**
   - Mitigation: Transaction handling, retry logic

### Project Risks
1. **Scope creep**
   - Mitigation: Strict phase boundaries, MVP first
   
2. **Integration complexity**
   - Mitigation: Follow mcp_marketing_collection pattern
   
3. **Testing challenges**
   - Mitigation: Mock GraphQL responses, isolated testing

---

## Next Steps

1. **Review this plan** with stakeholders
2. **Set up development environment**
3. **Create pyproject.toml** and install dependencies
4. **Start Phase 1**: Foundation setup
5. **Implement Phase 3.1**: Request management (first priority tool)

---

## Questions & Clarifications

- [ ] What is the production endpoint_id for ai_rfq_graphql?
- [ ] Are there specific discount calculation rules to implement?
- [ ] Should we support bulk operations (e.g., bulk quote item creation)?
- [ ] What is the expected request volume?
- [ ] Are there specific compliance requirements?

---

## Change Log

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2025-11-05 | 0.1.0 | Initial development plan | Development Team |
| 2025-11-06 | 0.2.0 | Updated based on business requirements:<br>- Added `update_rfq_request` tool<br>- Removed `add_quote_item`, `update_quote_item`, `delete_quote_item` tools<br>- Added `update_quote` tool (replaces `update_quote_status`)<br>- Added `update_quote_item_discount` tool<br>- Documented new workflows for item modification<br>- Total tools: 22 (was 24) | Development Team |
