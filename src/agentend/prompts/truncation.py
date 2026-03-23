"""Priority-based prompt truncation system."""

from typing import List, Dict, Any, Optional
import re


class PromptSection:
    """Single section of a prompt."""

    def __init__(
        self,
        content: str,
        priority: int = 0,
        min_tokens: int = 0,
    ):
        """
        Initialize section.

        Args:
            content: Section content.
            priority: Priority (higher = keep first).
            min_tokens: Minimum tokens to preserve.
        """
        self.content = content
        self.priority = priority
        self.min_tokens = min_tokens
        self.tokens = self._estimate_tokens()

    def _estimate_tokens(self) -> int:
        """Estimate token count (rough: ~4 chars per token)."""
        return len(self.content) // 4 + 1


class PromptTruncation:
    """
    Priority-based prompt truncation.

    Uses binary search to find optimal cutoff within token budget.
    """

    def __init__(self, max_tokens: int = 4000):
        """
        Initialize truncator.

        Args:
            max_tokens: Maximum allowed tokens.
        """
        self.max_tokens = max_tokens

    def truncate(self, prompt: str) -> str:
        """
        Truncate prompt to token budget.

        Preserves high-priority sections first.

        Args:
            prompt: Full prompt.

        Returns:
            Truncated prompt.
        """
        sections = self._extract_sections(prompt)

        # Sort by priority (higher first)
        sections.sort(key=lambda s: s.priority, reverse=True)

        # Calculate total tokens
        total_tokens = sum(s.tokens for s in sections)

        if total_tokens <= self.max_tokens:
            # Fits within budget
            return prompt

        # Need to truncate
        selected_sections = self._select_sections(sections)
        return "\n\n".join(s.content for s in selected_sections if s.content)

    def _extract_sections(self, prompt: str) -> List[PromptSection]:
        """
        Extract logical sections from prompt.

        Args:
            prompt: Full prompt.

        Returns:
            List of sections with priorities.
        """
        sections = []

        # Extract marked sections
        system_pattern = r"<\|system_prompt\|>(.*?)</\|system_prompt\|>"
        system_match = re.search(system_pattern, prompt, re.DOTALL)
        if system_match:
            sections.append(PromptSection(
                system_match.group(1).strip(),
                priority=100,  # Highest priority
                min_tokens=200,
            ))

        developer_pattern = r"<\|developer_instructions\|>(.*?)</\|developer_instructions\|>"
        developer_match = re.search(developer_pattern, prompt, re.DOTALL)
        if developer_match:
            sections.append(PromptSection(
                developer_match.group(1).strip(),
                priority=90,
                min_tokens=150,
            ))

        user_pattern = r"<\|user_input\|>(.*?)</\|user_input\|>"
        user_match = re.search(user_pattern, prompt, re.DOTALL)
        if user_match:
            sections.append(PromptSection(
                user_match.group(1).strip(),
                priority=95,  # High priority
                min_tokens=100,
            ))

        # Extract other sections based on headers
        header_pattern = r"^(.*?):\s*\n(.*?)(?=\n\n|\Z)"
        for match in re.finditer(header_pattern, prompt, re.MULTILINE | re.DOTALL):
            header = match.group(1)
            content = match.group(2)

            # Assign priority based on header
            priority = 50  # Default
            if "Example" in header:
                priority = 40
            elif "Memory" in header or "Context" in header:
                priority = 70
            elif "Format" in header or "Output" in header:
                priority = 80

            sections.append(PromptSection(content, priority=priority))

        return sections

    def _select_sections(
        self,
        sections: List[PromptSection],
    ) -> List[PromptSection]:
        """
        Select sections using priority and binary search.

        Args:
            sections: All sections sorted by priority.

        Returns:
            Selected sections fitting budget.
        """
        selected = []
        total_tokens = 0

        # First, ensure minimum tokens for each priority level
        for section in sections:
            if total_tokens + section.min_tokens <= self.max_tokens:
                selected.append(section)
                total_tokens += section.min_tokens
            elif total_tokens + section.tokens <= self.max_tokens:
                # Can fit full section
                selected.append(section)
                total_tokens += section.tokens
            else:
                # Try to add partial content
                remaining = self.max_tokens - total_tokens
                if remaining > 100:  # Only if we have space for meaningful content
                    truncated = self._truncate_section(section, remaining)
                    section_copy = PromptSection(truncated, section.priority)
                    selected.append(section_copy)
                    total_tokens += section_copy.tokens
                    break

        return selected

    def _truncate_section(self, section: PromptSection, token_budget: int) -> str:
        """
        Truncate section to fit token budget.

        Args:
            section: Section to truncate.
            token_budget: Available tokens.

        Returns:
            Truncated content.
        """
        char_budget = token_budget * 4  # Rough conversion
        content = section.content

        if len(content) <= char_budget:
            return content

        # Smart truncation: cut at sentence boundary
        truncated = content[:char_budget]

        # Find last complete sentence
        last_period = truncated.rfind(".")
        last_newline = truncated.rfind("\n")

        cutoff = max(last_period, last_newline)

        if cutoff > char_budget * 0.8:  # Use if reasonably close to budget
            return content[:cutoff + 1]

        return truncated + "..."

    def get_section_tokens(self, prompt: str) -> Dict[str, int]:
        """
        Get token counts for each section.

        Args:
            prompt: Full prompt.

        Returns:
            Dictionary of section name -> token count.
        """
        sections = self._extract_sections(prompt)
        return {
            f"section_{i}": s.tokens
            for i, s in enumerate(sections)
        }

    def get_token_usage(self, prompt: str) -> Dict[str, Any]:
        """
        Get detailed token usage.

        Args:
            prompt: Full prompt.

        Returns:
            Token usage details.
        """
        sections = self._extract_sections(prompt)
        total = sum(s.tokens for s in sections)

        return {
            "total_tokens": total,
            "max_tokens": self.max_tokens,
            "needs_truncation": total > self.max_tokens,
            "sections": [
                {
                    "priority": s.priority,
                    "tokens": s.tokens,
                    "percentage": (s.tokens / total) * 100 if total > 0 else 0,
                }
                for s in sorted(sections, key=lambda s: s.priority, reverse=True)
            ],
        }
