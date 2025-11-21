#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

__author__ = "bibow"

import logging
from typing import Any, Dict

from .file_processor import FileProcessor
from .graphql_backed_processor import GraphQLBackedProcessor
from .installment_processor import InstallmentProcessor
from .item_processor import ItemProcessor
from .mcp_configuration import MCP_CONFIGURATION
from .pricing_processor import PricingProcessor
from .quote_processor import QuoteProcessor
from .request_processor import RequestProcessor
from .segment_processor import SegmentProcessor

__all__ = [
    "GraphQLBackedProcessor",
    "RequestProcessor",
    "ItemProcessor",
    "QuoteProcessor",
    "PricingProcessor",
    "InstallmentProcessor",
    "FileProcessor",
    "SegmentProcessor",
    "MCPRfqProcessor",
    "MCP_CONFIGURATION",
]


class MCPRfqProcessor(SegmentProcessor):
    """Public interface aggregating RFQ request, quote, pricing, installment, and supporting utilities."""

    def __init__(self, logger: logging.Logger, **setting: Dict[str, Any]):
        super().__init__(logger, **setting)
