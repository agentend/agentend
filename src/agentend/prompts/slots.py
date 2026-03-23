"""Base Capability class using Template Method pattern."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class PromptContext:
    """Context for prompt building."""

    user_input: str
    session_id: str
    memory_context: Optional[str] = None
    conversation_history: Optional[List[Dict[str, str]]] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseCapability(ABC):
    """
    Base class for capabilities using Template Method pattern.

    Subclasses implement specific methods to customize prompt building.
    """

    def __init__(self, name: str, description: str):
        """
        Initialize capability.

        Args:
            name: Capability name.
            description: Capability description.
        """
        self.name = name
        self.description = description

    def build_prompt(self, context: PromptContext) -> str:
        """
        Build final prompt through template method.

        Args:
            context: Prompt context with user input and metadata.

        Returns:
            Complete prompt string.
        """
        sections = []

        # Assemble prompt sections in order
        persona = self.get_persona()
        if persona:
            sections.append(f"<|system_prompt|>\n{persona}\n</|system_prompt|>")

        constraints = self.get_constraints()
        if constraints:
            sections.append(f"<|developer_instructions|>\n{constraints}\n</|developer_instructions|>")

        domain = self.get_domain_context()
        if domain:
            sections.append(f"Domain Context:\n{domain}")

        memory = self.get_memory_context(context.memory_context)
        if memory:
            sections.append(f"Relevant Memory:\n{memory}")

        examples = self.get_examples()
        if examples:
            sections.append(f"Examples:\n{examples}")

        output_format = self.get_output_format()
        if output_format:
            sections.append(f"Output Format:\n{output_format}")

        # Add conversation history if available
        if context.conversation_history:
            history_str = self._format_conversation_history(context.conversation_history)
            sections.append(f"Conversation History:\n{history_str}")

        # User input (last)
        sections.append(f"<|user_input|>\n{context.user_input}\n</|user_input|>")

        return "\n\n".join(sections)

    @abstractmethod
    def get_persona(self) -> str:
        """
        Return system persona/instructions.

        Returns:
            Persona string.
        """
        pass

    @abstractmethod
    def get_constraints(self) -> str:
        """
        Return developer constraints and guidelines.

        Returns:
            Constraints string.
        """
        pass

    def get_domain_context(self) -> Optional[str]:
        """
        Return domain-specific context.

        Optional to override. Returns None by default.

        Returns:
            Domain context or None.
        """
        return None

    def get_examples(self) -> Optional[str]:
        """
        Return in-context examples.

        Optional to override. Returns None by default.

        Returns:
            Examples or None.
        """
        return None

    def get_output_format(self) -> Optional[str]:
        """
        Return expected output format (JSON schema, etc).

        Optional to override. Returns None by default.

        Returns:
            Output format or None.
        """
        return None

    def get_memory_context(self, memory: Optional[str] = None) -> Optional[str]:
        """
        Return memory context to inject.

        Optional to override. Uses provided memory parameter by default.

        Args:
            memory: Memory context string.

        Returns:
            Formatted memory or None.
        """
        return memory

    def _format_conversation_history(
        self,
        history: List[Dict[str, str]],
    ) -> str:
        """
        Format conversation history.

        Args:
            history: List of {role, content} dicts.

        Returns:
            Formatted history string.
        """
        lines = []
        for msg in history:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)


class SearchCapability(BaseCapability):
    """Example semantic search capability."""

    def get_persona(self) -> str:
        return """You are an expert semantic search assistant.
Your role is to understand user queries and find relevant information.
You should consider synonyms, related concepts, and user intent."""

    def get_constraints(self) -> str:
        return """
- Always search for both exact matches and semantic similarities
- Return results ranked by relevance
- Explain your search strategy
- Acknowledge if no suitable results exist
- Suggest related searches if appropriate
"""

    def get_output_format(self) -> Optional[str]:
        return """
{
  "search_strategy": "description of approach",
  "results": [
    {
      "content": "found text",
      "relevance_score": 0.95,
      "source": "source identifier"
    }
  ],
  "total_results": number
}
"""


class SummarizationCapability(BaseCapability):
    """Example document summarization capability."""

    def get_persona(self) -> str:
        return """You are an expert at creating clear, concise summaries.
Your summaries capture key points without losing important details.
You adapt your style based on the document type and user needs."""

    def get_constraints(self) -> str:
        return """
- Keep summaries 20-30% of original length
- Include all critical information
- Use clear, simple language
- Preserve important numbers and dates
- Note any assumptions or uncertainties
"""

    def get_examples(self) -> Optional[str]:
        return """
Example long text: "The company reported revenue of $50M in Q1..."
Example summary: "Q1 revenue reached $50M, exceeding targets by 15%."
"""


class CodeCapability(BaseCapability):
    """Example code generation capability."""

    def get_persona(self) -> str:
        return """You are an expert software engineer.
Write clean, maintainable, well-documented code.
Follow best practices and industry standards."""

    def get_constraints(self) -> str:
        return """
- Write production-ready code
- Include type hints and docstrings
- Add error handling
- Follow the specified language conventions
- Make code readable and maintainable
"""

    def get_output_format(self) -> Optional[str]:
        return """
```language
[code here]
```

Explanation: [brief description of the code]
"""
