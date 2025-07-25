from typing import List, Optional, Union

from pydantic import BaseModel, Field

from letta.schemas.block import Block
from letta.schemas.enums import ToolRuleType
from letta.schemas.tool_rule import (
    BaseToolRule,
    ChildToolRule,
    ConditionalToolRule,
    ContinueToolRule,
    InitToolRule,
    MaxCountPerStepToolRule,
    ParentToolRule,
    RequiredBeforeExitToolRule,
    TerminalToolRule,
)


class ToolRuleValidationError(Exception):
    """Custom exception for tool rule validation errors in ToolRulesSolver."""

    def __init__(self, message: str):
        super().__init__(f"ToolRuleValidationError: {message}")


class ToolRulesSolver(BaseModel):
    init_tool_rules: List[InitToolRule] = Field(
        default_factory=list, description="Initial tool rules to be used at the start of tool execution."
    )
    continue_tool_rules: List[ContinueToolRule] = Field(
        default_factory=list, description="Continue tool rules to be used to continue tool execution."
    )
    # TODO: This should be renamed?
    # TODO: These are tools that control the set of allowed functions in the next turn
    child_based_tool_rules: List[Union[ChildToolRule, ConditionalToolRule, MaxCountPerStepToolRule]] = Field(
        default_factory=list, description="Standard tool rules for controlling execution sequence and allowed transitions."
    )
    parent_tool_rules: List[ParentToolRule] = Field(
        default_factory=list, description="Filter tool rules to be used to filter out tools from the available set."
    )
    terminal_tool_rules: List[TerminalToolRule] = Field(
        default_factory=list, description="Terminal tool rules that end the agent loop if called."
    )
    required_before_exit_tool_rules: List[RequiredBeforeExitToolRule] = Field(
        default_factory=list, description="Tool rules that must be called before the agent can exit."
    )
    tool_call_history: List[str] = Field(default_factory=list, description="History of tool calls, updated with each tool call.")

    def __init__(
        self,
        tool_rules: Optional[List[BaseToolRule]] = None,
        init_tool_rules: Optional[List[InitToolRule]] = None,
        continue_tool_rules: Optional[List[ContinueToolRule]] = None,
        child_based_tool_rules: Optional[List[Union[ChildToolRule, ConditionalToolRule, MaxCountPerStepToolRule]]] = None,
        parent_tool_rules: Optional[List[ParentToolRule]] = None,
        terminal_tool_rules: Optional[List[TerminalToolRule]] = None,
        required_before_exit_tool_rules: Optional[List[RequiredBeforeExitToolRule]] = None,
        tool_call_history: Optional[List[str]] = None,
        **kwargs,
    ):
        super().__init__(
            init_tool_rules=init_tool_rules or [],
            continue_tool_rules=continue_tool_rules or [],
            child_based_tool_rules=child_based_tool_rules or [],
            parent_tool_rules=parent_tool_rules or [],
            terminal_tool_rules=terminal_tool_rules or [],
            required_before_exit_tool_rules=required_before_exit_tool_rules or [],
            tool_call_history=tool_call_history or [],
            **kwargs,
        )

        if tool_rules:
            for rule in tool_rules:
                if rule.type == ToolRuleType.run_first:
                    assert isinstance(rule, InitToolRule)
                    self.init_tool_rules.append(rule)
                elif rule.type == ToolRuleType.constrain_child_tools:
                    assert isinstance(rule, ChildToolRule)
                    self.child_based_tool_rules.append(rule)
                elif rule.type == ToolRuleType.conditional:
                    assert isinstance(rule, ConditionalToolRule)
                    self.validate_conditional_tool(rule)
                    self.child_based_tool_rules.append(rule)
                elif rule.type == ToolRuleType.exit_loop:
                    assert isinstance(rule, TerminalToolRule)
                    self.terminal_tool_rules.append(rule)
                elif rule.type == ToolRuleType.continue_loop:
                    assert isinstance(rule, ContinueToolRule)
                    self.continue_tool_rules.append(rule)
                elif rule.type == ToolRuleType.max_count_per_step:
                    assert isinstance(rule, MaxCountPerStepToolRule)
                    self.child_based_tool_rules.append(rule)
                elif rule.type == ToolRuleType.parent_last_tool:
                    assert isinstance(rule, ParentToolRule)
                    self.parent_tool_rules.append(rule)
                elif rule.type == ToolRuleType.required_before_exit:
                    assert isinstance(rule, RequiredBeforeExitToolRule)
                    self.required_before_exit_tool_rules.append(rule)

    def register_tool_call(self, tool_name: str):
        """Update the internal state to track tool call history."""
        self.tool_call_history.append(tool_name)

    def clear_tool_history(self):
        """Clear the history of tool calls."""
        self.tool_call_history.clear()

    def get_allowed_tool_names(
        self, available_tools: set[str], error_on_empty: bool = True, last_function_response: str | None = None
    ) -> List[str]:
        """Get a list of tool names allowed based on the last tool called.

        The logic is as follows:
            1. if there are no previous tool calls and we have InitToolRules, those are the only options for the first tool call
            2. else we take the intersection of the Parent/Child/Conditional/MaxSteps as the options
            3. Continue/Terminal/RequiredBeforeExit rules are applied in the agent loop flow, not to restrict tools
        """
        # TODO: This piece of code here is quite ugly and deserves a refactor
        # TODO: -> Tool rules should probably be refactored to take in a set of tool names?
        if not self.tool_call_history and self.init_tool_rules:
            return [rule.tool_name for rule in self.init_tool_rules]
        else:
            valid_tool_sets = []
            for rule in self.child_based_tool_rules + self.parent_tool_rules:
                tools = rule.get_valid_tools(self.tool_call_history, available_tools, last_function_response)
                valid_tool_sets.append(tools)

            # Compute intersection of all valid tool sets
            final_allowed_tools = set.intersection(*valid_tool_sets) if valid_tool_sets else available_tools

            if error_on_empty and not final_allowed_tools:
                raise ValueError("No valid tools found based on tool rules.")

            return list(final_allowed_tools)

    def is_terminal_tool(self, tool_name: str) -> bool:
        """Check if the tool is defined as a terminal tool in the terminal tool rules or required-before-exit tool rules."""
        return any(rule.tool_name == tool_name for rule in self.terminal_tool_rules)

    def has_children_tools(self, tool_name):
        """Check if the tool has children tools"""
        return any(rule.tool_name == tool_name for rule in self.child_based_tool_rules)

    def is_continue_tool(self, tool_name):
        """Check if the tool is defined as a continue tool in the tool rules."""
        return any(rule.tool_name == tool_name for rule in self.continue_tool_rules)

    def has_required_tools_been_called(self, available_tools: set[str]) -> bool:
        """Check if all required-before-exit tools have been called."""
        return len(self.get_uncalled_required_tools(available_tools=available_tools)) == 0

    def get_uncalled_required_tools(self, available_tools: set[str]) -> List[str]:
        """Get the list of required-before-exit tools that have not been called yet."""
        if not self.required_before_exit_tool_rules:
            return []  # No required tools means no uncalled tools

        required_tool_names = {rule.tool_name for rule in self.required_before_exit_tool_rules}
        called_tool_names = set(self.tool_call_history)

        # Get required tools that are uncalled AND available
        return list((required_tool_names & available_tools) - called_tool_names)

    def get_ending_tool_names(self) -> List[str]:
        """Get the names of tools that are required before exit."""
        return [rule.tool_name for rule in self.required_before_exit_tool_rules]

    def compile_tool_rule_prompts(self) -> Optional[Block]:
        """
        Compile prompt templates from all tool rules into an ephemeral Block.

        Returns:
            Optional[str]: Compiled prompt string with tool rule constraints, or None if no templates exist.
        """
        compiled_prompts = []

        all_rules = (
            self.init_tool_rules
            + self.continue_tool_rules
            + self.child_based_tool_rules
            + self.parent_tool_rules
            + self.terminal_tool_rules
        )

        for rule in all_rules:
            rendered = rule.render_prompt()
            if rendered:
                compiled_prompts.append(rendered)

        if compiled_prompts:
            return Block(
                label="tool_usage_rules",
                value="\n".join(compiled_prompts),
                description="The following constraints define rules for tool usage and guide desired behavior. These rules must be followed to ensure proper tool execution and workflow. A single response may contain multiple tool calls.",
            )
        return None

    def guess_rule_violation(self, tool_name: str) -> List[str]:
        """
        Check if the given tool name or the previous tool in history matches any tool rule,
        and return rendered prompt templates for matching rules.

        Args:
            tool_name: The name of the tool to check for rule violations

        Returns:
            List of rendered prompt templates from matching tool rules
        """
        violated_rules = []

        # Get the previous tool from history if it exists
        previous_tool = self.tool_call_history[-1] if self.tool_call_history else None

        # Check all tool rules for matches
        all_rules = (
            self.init_tool_rules
            + self.continue_tool_rules
            + self.child_based_tool_rules
            + self.parent_tool_rules
            + self.terminal_tool_rules
        )

        for rule in all_rules:
            # Check if the current tool name or previous tool matches this rule's tool_name
            if rule.tool_name == tool_name or (previous_tool and rule.tool_name == previous_tool):
                rendered_prompt = rule.render_prompt()
                if rendered_prompt:
                    violated_rules.append(rendered_prompt)

        return violated_rules

    @staticmethod
    def validate_conditional_tool(rule: ConditionalToolRule):
        """
        Validate a conditional tool rule

        Args:
            rule (ConditionalToolRule): The conditional tool rule to validate

        Raises:
            ToolRuleValidationError: If the rule is invalid
        """
        if len(rule.child_output_mapping) == 0:
            raise ToolRuleValidationError("Conditional tool rule must have at least one child tool.")
        return True
