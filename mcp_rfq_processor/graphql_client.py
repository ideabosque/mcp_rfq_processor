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

import httpx
from silvaengine_dynamodb_base.models import GraphqlSchemaModel
from silvaengine_utility.graphql import Graphql
from silvaengine_utility.serializer import Serializer

from .error_handler import (
    ErrorCode,
    GraphQLError,
    build_error_response,
    extract_error_message,
)


class GraphQLModule:
    """Encapsulates GraphQL module configuration and schema management."""

    def __init__(
        self,
        endpoint_id: str,
        module_name: str | None = None,
        class_name: str | None = None,
        endpoint: str | None = None,
        x_api_key: str | None = None,
    ):
        """
        Initialize GraphQL module configuration.

        Args:
            endpoint_id: Identifier for the endpoint
            module_name: Optional module name for schema generation
            class_name: Optional class name for schema generation
            endpoint: Optional endpoint URL template with {endpoint_id} placeholder
        """
        self.endpoint_id = endpoint_id
        self._module_name = module_name
        self._class_name = class_name
        self._endpoint = endpoint.format(endpoint_id=endpoint_id) if endpoint else None
        self._x_api_key = x_api_key
        self._schema = None

    @property
    def module_name(self) -> str | None:
        """Get the module name used for schema generation."""
        return self._module_name

    @property
    def class_name(self) -> str | None:
        """Get the class name used for schema generation."""
        return self._class_name

    @property
    def endpoint(self) -> str | None:
        """Get the formatted endpoint URL."""
        return self._endpoint

    @property
    def x_api_key(self) -> str | None:
        """Get the API key for authentication."""
        return self._x_api_key

    @property
    def schema(self):
        """Get the cached GraphQL schema, loading it if necessary."""
        if self._schema is None and self._module_name and self._class_name:
            self.refresh_schema()
        return self._schema

    def refresh_schema(self):
        """Load or reload the GraphQL schema from the configured module and class."""
        if self._module_name and self._class_name:
            self._schema = Graphql.get_graphql_schema(
                module_name=self._module_name,
                class_name=self._class_name,
            )


class GraphQLClient:
    """Client for executing GraphQL operations via AWS Lambda."""

    def __init__(self, logger: logging.Logger, **setting: Dict[str, Any]):
        self.logger = logger
        self.setting = setting
        self._endpoint_id = None
        self._part_id = None
        self._graphql_modules = {}

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

    @property
    def graphql_modules(self) -> Dict[str, GraphQLModule]:
        return self._graphql_modules

    def get_graphql_module(self, module_name: str) -> GraphQLModule | None:
        """Get a GraphQL module by name."""
        if not self._graphql_modules.get(module_name):
            self._graphql_modules[module_name] = GraphQLModule(
                endpoint_id=self.endpoint_id,
                module_name=module_name,
                class_name=self.setting.get("graphql_modules", {})
                .get(module_name, {})
                .get("class_name"),
                endpoint=self.setting.get("graphql_modules", {})
                .get(module_name, {})
                .get("endpoint"),
                x_api_key=self.setting.get("graphql_modules", {})
                .get(module_name, {})
                .get("x_api_key"),
            )

        return self._graphql_modules.get(module_name)

    def execute_query(
        self,
        function_name: str,
        operation_name: str,
        operation_type: str,
        variables: Dict[str, Any],
        query: str = None,
        module_name: str = "ai_rfq_engine",
    ) -> Dict[str, Any]:
        """Execute a GraphQL query or mutation."""
        try:
            graphql_module = self.get_graphql_module(module_name)

            if not all([isinstance(query, str), str(query).strip()]):
                query = GraphqlSchemaModel.get_schema(
                    endpoint_id=graphql_module.endpoint_id,
                    operation_type=operation_type,
                    operation_name=operation_name,
                    module_name=module_name,
                    enable_preferred_custom_schema=True,
                )

            if not query:
                query = Graphql.generate_graphql_operation(
                    operation_name, operation_type, graphql_module.schema
                )

            payload = Serializer.json_dumps({"query": query, "variables": variables})

            headers = {
                "x-api-key": graphql_module.x_api_key,
                "Part-Id": self.part_id,
                "Content-Type": "application/json",
            }

            # httpx rejects None-valued headers with a TypeError. Drop any
            # that came out None so the request goes through cleanly. The
            # common case is Part-Id when the tool is invoked via
            # /{endpoint_id}/mcp instead of /{endpoint_id}/{part_id}/mcp;
            # x-api-key can also be None when no API-key auth is configured.
            headers = {k: v for k, v in headers.items() if v is not None}

            with httpx.Client(http2=True) as client:
                print(f">>>>>>>>>>>>>>>>>>>{payload}")
                print(f">>>>>>>>>>>>>>>>>>> graphql_module.endpoint: {graphql_module.endpoint} \n headers: {headers}")
                response = client.post(
                    graphql_module.endpoint,
                    headers=headers,
                    content=payload,
                )

            result = response.json()

            if "errors" in result:
                error_message = result["errors"][0].get("message", "GraphQL error")
                raise Exception(f"GraphQL error: {error_message}")

            return result.get("data", {}).get(operation_name)

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
