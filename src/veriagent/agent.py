"""AI Agent orchestration with strict security controls.

SECURITY PRINCIPLES:
- Agent generates action proposals ONLY
- Agent NEVER executes tools directly
- Agent NEVER accesses database
- Agent CANNOT approve reviews
- Agent CANNOT supply verification results
- User role comes from trusted context, not LLM
- All proposals go through SecureExecutor
- Fail-closed on any error
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .action_parser import ActionParser, ActionParseError, ActionSchemaRegistry
from .executor import ExecutionResult, ExecutionStatus, SecureExecutor
from .llm.base import BaseLLM, LLMError, LLMTimeout
from .models import ProposedAction


@dataclass(frozen=True, slots=True)
class AgentResponse:
    """Response from the agent after processing a user request."""

    success: bool
    message: str
    execution_result: ExecutionResult | None
    error: str | None


class VeriAgent:
    """AI Agent that generates proposals and submits them through SecureExecutor.

    SECURITY ARCHITECTURE:
    User Request → Agent → LLM → Parse → Validate → Executor → Decision → Tool
                                                      ↓
                                               Verification happens here
                                          (Agent has no control over this)
    """

    def __init__(
        self,
        llm: BaseLLM,
        executor: SecureExecutor,
        user_role: str,
        schema_registry: ActionSchemaRegistry | None = None,
    ) -> None:
        """Initialize agent with LLM and executor.

        Args:
            llm: Language model for generating actions
            executor: Secure executor for verified execution
            user_role: Trusted user role from application context
            schema_registry: Optional custom schema registry
        """
        self.llm = llm
        self.executor = executor
        self.user_role = user_role
        self.parser = ActionParser(schema_registry)

    def process_request(self, user_request: str, timeout: float = 30.0) -> AgentResponse:
        """Process a user request through the agent pipeline.

        SECURITY FLOW:
        1. User request → LLM (agent cannot influence this)
        2. LLM response → Strict parser (fail-closed validation)
        3. Parsed action → ProposedAction (user_role from trusted context)
        4. ProposedAction → SecureExecutor (verification happens here)
        5. Decision → ALLOW/REVIEW/BLOCK
        6. Return result to user

        Args:
            user_request: Natural language request from user
            timeout: Maximum seconds for LLM call

        Returns:
            AgentResponse with execution result or error
        """
        try:
            # Step 1: Generate LLM response
            try:
                llm_response = self.llm.generate(self._build_prompt(user_request), timeout)
            except LLMTimeout:
                return AgentResponse(
                    success=False,
                    message="LLM request timed out",
                    execution_result=None,
                    error="Timeout",
                )
            except LLMError as e:
                return AgentResponse(
                    success=False,
                    message=f"LLM error: {e}",
                    execution_result=None,
                    error=str(e),
                )

            # Step 2: Parse and validate LLM output (fail-closed)
            try:
                parsed_action = self.parser.parse(llm_response.content)
            except ActionParseError as e:
                return AgentResponse(
                    success=False,
                    message=f"Action parsing failed: {e}",
                    execution_result=None,
                    error=f"ParseError: {e}",
                )

            # Step 3: Create proposal with trusted user role
            proposal = self.parser.create_proposal(parsed_action, self.user_role)

            # Step 4: Submit to secure executor (verification happens here)
            execution_result = self.executor.submit(proposal)

            # Step 5: Return result based on decision
            return self._handle_execution_result(execution_result)

        except Exception as e:
            # Fail closed on unexpected errors
            return AgentResponse(
                success=False,
                message=f"Unexpected error: {e}",
                execution_result=None,
                error=f"UnexpectedError: {e}",
            )

    def _build_prompt(self, user_request: str) -> str:
        """Build prompt for LLM.

        This includes:
        - User request
        - Available actions
        - Required JSON format
        - Examples

        SECURITY: Prompt does NOT include:
        - User role (agent should not know this)
        - Verification logic (agent should not understand this)
        - Database structure (agent should not access this)
        - Approval mechanism (agent cannot approve)
        """
        return f"""You are a helpful assistant that converts user requests into structured actions.

Available actions:
- get_customer: Retrieve customer information
- get_invoice: Retrieve invoice information
- calculate_balance: Calculate customer's outstanding balance
- create_invoice: Create a new invoice
- update_customer: Update customer information
- refund_customer: Process a customer refund
- send_email: Send an email

USER REQUEST:
{user_request}

OUTPUT FORMAT:
Return ONLY a JSON object with this exact structure:
{{"action": "action_name", "parameters": {{"param1": value1, "param2": value2}}}}

RULES:
- Output pure JSON only, no explanatory text
- No Markdown code fences (```json)
- Only one action per request
- Include all required parameters for the action
- Do not include: "decision", "user_role", "verification", or "approved" fields

Example:
{{"action": "get_customer", "parameters": {{"customer_id": 101}}}}

Now convert the user request above into a JSON action:"""

    def _handle_execution_result(self, result: ExecutionResult) -> AgentResponse:
        """Convert ExecutionResult to AgentResponse."""
        if result.status == ExecutionStatus.EXECUTED:
            return AgentResponse(
                success=True,
                message=f"Action executed successfully: {result.proposal.action}",
                execution_result=result,
                error=None,
            )
        elif result.status == ExecutionStatus.PENDING_REVIEW:
            return AgentResponse(
                success=False,  # Not executed yet
                message=f"Action requires human review (ID: {result.execution_id})",
                execution_result=result,
                error=None,
            )
        elif result.status == ExecutionStatus.BLOCKED:
            return AgentResponse(
                success=False,
                message=f"Action blocked: {result.error_message}",
                execution_result=result,
                error=result.error_message,
            )
        elif result.status == ExecutionStatus.FAILED:
            return AgentResponse(
                success=False,
                message=f"Tool execution failed: {result.error_message}",
                execution_result=result,
                error=result.error_message,
            )
        else:
            return AgentResponse(
                success=False,
                message=f"Unknown execution status: {result.status}",
                execution_result=result,
                error="Unknown status",
            )

    def get_pending_reviews(self) -> list[dict[str, Any]]:
        """Retrieve pending reviews from executor.

        Agent can VIEW pending reviews but CANNOT approve them.
        Approval requires authenticated human reviewer.
        """
        return self.executor.get_pending_reviews()
