#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

__author__ = "bibow"

import logging
from typing import Any, Dict

from .graphql_client import GraphQLClient


class GraphQLBackedProcessor:
    def __init__(self, logger: logging.Logger, **setting: Dict[str, Any]):
        self.logger = logger
        self.setting = setting
        self.graphql_client = GraphQLClient(logger, **setting)

    @property
    def endpoint_id(self) -> str | None:
        return self.graphql_client.endpoint_id

    @endpoint_id.setter
    def endpoint_id(self, value: str):
        self.graphql_client.endpoint_id = value

    def _execute_graphql_query(
        self,
        function_name: str,
        operation_name: str,
        operation_type: str,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        return self.graphql_client.execute_query(
            function_name, operation_name, operation_type, variables
        )
