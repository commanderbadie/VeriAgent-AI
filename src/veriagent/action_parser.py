"""Strict JSON action parser with fail-closed validation.

CRITICAL SECURITY:
- Only accepts exact JSON format
- Rejects Markdown fences, explanatory text
- Validates against action-specific schemas
- Rejects unknown tools
- Rejects extra/unknown fields
- User role NEVER comes from LLM output
- Fails closed on any validation error
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .models import ProposedAction


class ActionParseError(Exception):
    """Action parsing or validation failed."""


class ActionSchemaRegistry:
    """Registry of valid action schemas with required/optional parameters."""

    def __init__(self) -> None:
        # Define schemas for each action
        # Format: action_name -> {"required": [...], "optional": [...], "types": {...}}
        self._schemas: dict[str, dict[str, Any]] = {
            "get_customer": {
                "required": ["customer_id"],
                "optional": [],
                "types": {"customer_id": int},
            },
            "get_invoice": {
                "required": ["invoice_id"],
                "optional": [],
                "types": {"invoice_id": str},
            },
            "calculate_balance": {
                "required": ["customer_id"],
                "optional": [],
                "types": {"customer_id": int},
            },
            "create_invoice": {
                "required": ["customer_id", "amount", "due_date"],
                "optional": ["status"],
                "types": {
                    "customer_id": int,
                    "amount": (int, float),
                    "due_date": str,
                    "status": str,
                },
            },
            "update_customer": {
                "required": ["customer_id"],
                "optional": ["name", "email", "phone", "status"],
                "types": {
                    "customer_id": int,
                    "name": str,
                    "email": str,
                    "phone": str,
                    "status": str,
                },
            },
            "refund_customer": {
                "required": ["customer_id", "amount", "reason"],
                "optional": [],
                "types": {
                    "customer_id": int,
                    "amount": (int, float),
                    "reason": str,
                },
            },
            "send_email": {
                "required": ["recipient", "subject", "body"],
                "optional": [],
                "types": {
                    "recipient": str,
                    "subject": str,
                    "body": str,
                },
            },
        }

    def get_schema(self, action: str) -> dict[str, Any]:
        """Get schema for an action. Raises ActionParseError if unknown."""
        if action not in self._schemas:
            raise ActionParseError(f"Unknown action: {action}")
        return self._schemas[action]

    def is_registered(self, action: str) -> bool:
        """Check if action has a registered schema."""
        return action in self._schemas


@dataclass(frozen=True, slots=True)
class ParsedAction:
    """Successfully parsed and validated action."""

    action: str
    tool: str  # Same as action for now
    parameters: dict[str, Any]


class ActionParser:
    """Parse and validate LLM-generated action JSON with strict fail-closed rules."""

    def __init__(self, schema_registry: ActionSchemaRegistry | None = None) -> None:
        self.schema_registry = schema_registry or ActionSchemaRegistry()

    def parse(self, llm_output: str) -> ParsedAction:
        """Parse LLM output into a validated action.

        SECURITY RULES:
        1. Must be valid JSON
        2. Must be a single JSON object (not array, not multiple objects)
        3. No Markdown fences (```json) allowed
        4. No explanatory text before/after JSON
        5. Must contain exactly: {"action": "...", "parameters": {...}}
        6. "tool" field optional but if present must match "action"
        7. "decision", "user_role", "verification" fields FORBIDDEN
        8. Action must be in schema registry
        9. Parameters must match schema (required fields, types, no extras)

        Args:
            llm_output: Raw string from LLM

        Returns:
            ParsedAction if valid

        Raises:
            ActionParseError: On any validation failure (fail-closed)
        """
        # Step 1: Strip whitespace
        output = llm_output.strip()

        if not output:
            raise ActionParseError("Empty LLM output")

        # Step 2: Detect and reject Markdown fences
        if output.startswith("```"):
            raise ActionParseError("Markdown code fences not allowed")

        # Step 3: Must start with { (must be a JSON object, not array or text)
        if not output.startswith("{"):
            raise ActionParseError("must be a JSON object (pure JSON, not array or text)")

        # Step 4: Check for text after JSON (find first } and ensure nothing after)
        try:
            # Find the end of the JSON object
            decoder = json.JSONDecoder()
            obj, end_idx = decoder.raw_decode(output)

            # Check if there's non-whitespace content after the JSON
            remaining = output[end_idx:].strip()
            if remaining:
                raise ActionParseError(
                    "Output must be pure JSON object, no text after JSON"
                )

        except json.JSONDecodeError as e:
            raise ActionParseError(f"Invalid JSON: {e}")

        # Step 5: Must be a dict (not array, not primitive)
        if not isinstance(obj, dict):
            raise ActionParseError("Output must be a JSON object, not array or primitive")

        # Step 6: Validate exact allowed fields
        allowed_fields = {"action", "parameters", "tool"}
        actual_fields = set(obj.keys())

        # Check for forbidden fields
        forbidden_fields = {"decision", "user_role", "verification", "approved", "allow"}
        forbidden_present = actual_fields & forbidden_fields
        if forbidden_present:
            raise ActionParseError(
                f"Forbidden fields detected: {forbidden_present}. "
                "LLM cannot supply decision, user_role, or verification."
            )

        # Check for unknown fields
        unknown_fields = actual_fields - allowed_fields
        if unknown_fields:
            raise ActionParseError(f"Unknown fields: {unknown_fields}")

        # Step 7: Validate required fields
        if "action" not in obj:
            raise ActionParseError("Missing required field: action")

        if "parameters" not in obj:
            raise ActionParseError("Missing required field: parameters")

        # Step 8: Validate field types
        if not isinstance(obj["action"], str):
            raise ActionParseError("Field 'action' must be a string")

        if not isinstance(obj["parameters"], dict):
            raise ActionParseError("Field 'parameters' must be an object")

        action_name = obj["action"]

        # Step 9: If tool is provided, it must match action
        if "tool" in obj:
            if not isinstance(obj["tool"], str):
                raise ActionParseError("Field 'tool' must be a string")
            if obj["tool"] != action_name:
                raise ActionParseError(f"Field 'tool' must match 'action': {action_name}")

        # Step 10: Validate action exists in schema registry
        if not self.schema_registry.is_registered(action_name):
            raise ActionParseError(f"Unknown action: {action_name}")

        # Step 11: Validate parameters against schema
        schema = self.schema_registry.get_schema(action_name)
        parameters = obj["parameters"]

        # Check required parameters
        for required_param in schema["required"]:
            if required_param not in parameters:
                raise ActionParseError(
                    f"Missing required parameter '{required_param}' for action '{action_name}'"
                )

        # Check for unknown parameters
        allowed_params = set(schema["required"]) | set(schema["optional"])
        actual_params = set(parameters.keys())
        unknown_params = actual_params - allowed_params
        if unknown_params:
            raise ActionParseError(
                f"Unknown parameters for '{action_name}': {unknown_params}"
            )

        # Check parameter types
        for param_name, param_value in parameters.items():
            expected_type = schema["types"].get(param_name)
            if expected_type is None:
                continue  # Type not specified

            # Handle union types (e.g., (int, float))
            if isinstance(expected_type, tuple):
                if not isinstance(param_value, expected_type):
                    raise ActionParseError(
                        f"Parameter '{param_name}' must be one of {expected_type}, "
                        f"got {type(param_value).__name__}"
                    )
            else:
                if not isinstance(param_value, expected_type):
                    raise ActionParseError(
                        f"Parameter '{param_name}' must be {expected_type.__name__}, "
                        f"got {type(param_value).__name__}"
                    )

        # Step 12: Return validated action
        return ParsedAction(
            action=action_name,
            tool=action_name,  # Tool name same as action
            parameters=parameters,
        )

    def create_proposal(
        self, parsed_action: ParsedAction, user_role: str
    ) -> ProposedAction:
        """Create a ProposedAction from parsed and validated LLM output.

        SECURITY: user_role comes from trusted application context, NOT from LLM.

        Args:
            parsed_action: Validated action from parse()
            user_role: Trusted user role from application session/auth

        Returns:
            ProposedAction ready for executor.submit()
        """
        return ProposedAction(
            action=parsed_action.action,
            user_role=user_role,
            parameters=parsed_action.parameters,
            tool=parsed_action.tool,
        )
