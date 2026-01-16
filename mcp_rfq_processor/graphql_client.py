#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GraphQL Client for MCP RFQ Processor

Handles AWS Lambda invocation and GraphQL query execution.
"""

__author__ = "bibow"

import logging
import traceback
from typing import Any, Dict

import boto3
from botocore.client import BaseClient

from silvaengine_utility.graphql import Graphql

from .error_handler import (
    ErrorCode,
    GraphQLError,
    build_error_response,
    extract_error_message,
)


class GraphQLClient:
    """Client for executing GraphQL operations via AWS Lambda."""

    def __init__(self, logger: logging.Logger, **setting: Dict[str, Any]):
        self.logger = logger
        self.setting = setting
        self._endpoint_id = None
        self._part_id = None
        self._schemas = {}
        self._aws_lambda = self._initialize_aws_lambda_client(**setting)

    @property
    def endpoint_id(self) -> str | None:
        return self._endpoint_id

    @endpoint_id.setter
    def endpoint_id(self, value: str):
        self._endpoint_id = value

    @property
    def part_id(self) -> str | None:
        return self._part_id

    @part_id.setter
    def part_id(self, value: str):
        self._part_id = value

    def _initialize_aws_lambda_client(self, **setting: Dict[str, Any]) -> BaseClient:
        """Initialize AWS Lambda client with credentials from settings."""
        region_name = setting.get("region_name")
        aws_access_key_id = setting.get("aws_access_key_id")
        aws_secret_access_key = setting.get("aws_secret_access_key")
        if region_name and aws_access_key_id and aws_secret_access_key:
            return boto3.client(
                "lambda",
                region_name=region_name,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
            )
        else:
            return boto3.client("lambda")

    def execute_query(
        self,
        function_name: str,
        operation_name: str,
        operation_type: str,
        variables: Dict[str, Any],
        query: str = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL query or mutation."""
        try:
            context = {
                "endpoint_id": self.endpoint_id,
                "part_id": self.part_id,
                "partition_key": f"{self.endpoint_id}#{self.part_id}",
                "setting": self.setting,
                "logger": self.logger,
            }

            result = Graphql.request_graphql(
                context=context,
                module_name="ai_rfq_engine",
                function_name="ai_rfq_graphql",
                graphql_operation_type=operation_type,
                graphql_operation_name=operation_name,
                class_name="AIRFQEngine",
                variables=variables,
                query=query,
            )
            return result

        except GraphQLError as e:
            log = traceback.format_exc()
            self.logger.error(log)
            return build_error_response(e.message, e.error_code, e.details)
        except Exception as e:
            log = traceback.format_exc()
            self.logger.error(log)
            return build_error_response(
                extract_error_message(str(e)),
                ErrorCode.GRAPHQL_QUERY_FAILED,
                {"function_name": function_name, "operation": operation_name},
            )
