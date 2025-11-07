#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

__author__ = "bibow"

import logging
import re
import traceback
from typing import Any, Dict, List

import boto3
import humps
import pendulum

from silvaengine_utility import Utility


class MCPRfqProcessor:
    def __init__(self, logger: logging.Logger, **setting: Dict[str, Any]):
        self.logger = logger
        self.setting = setting
        self._endpoint_id = None
        self._schemas = {}
        self._aws_lambda = self._initialize_aws_lambda_client(**setting)

    @property
    def endpoint_id(self) -> str:
        return self._endpoint_id

    @endpoint_id.setter
    def endpoint_id(self, value: str):
        self._endpoint_id = value

    def _initialize_aws_lambda_client(self, **setting: Dict[str, Any]) -> boto3.client:
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

    def _fetch_graphql_schema(
        self,
        function_name: str,
    ) -> Dict[str, Any]:
        try:
            if self._schemas.get(function_name) is None:
                self._schemas[function_name] = Utility.fetch_graphql_schema(
                    self.logger,
                    self.endpoint_id,
                    function_name,
                    setting=self.setting,
                    execute_mode=self.setting.get("execute_mode"),
                    aws_lambda=self._aws_lambda,
                )
            return self._schemas[function_name]
        except Exception as e:
            log = traceback.format_exc()
            self.logger.error(log)
            raise Exception(
                f"Failed to fetch GraphQL schema: {function_name}/{self.endpoint_id}. Please check the configuration and ensure all required settings are properly. Error: {e}"
            )

    def _execute_graphql_query(
        self,
        function_name: str,
        operation_name: str,
        operation_type: str,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            schema = self._fetch_graphql_schema(function_name)
            query = Utility.generate_graphql_operation(
                operation_name, operation_type, schema
            )
            self.logger.info(f"Query: {query}/{function_name}")
            return Utility.execute_graphql_query(
                self.logger,
                self.endpoint_id,
                function_name,
                query,
                variables,
                setting=self.setting,
                execute_mode=self.setting.get("execute_mode"),
                aws_lambda=self._aws_lambda,
            )
        except Exception as e:
            log = traceback.format_exc()
            self.logger.error(log)
            raise Exception(
                f"Failed to execute GraphQL query ({function_name}/{self.endpoint_id}). Error: {e}"
            )
