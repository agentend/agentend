"""Prompt segregation for PALADIN Layer 2."""

from dataclasses import dataclass
from enum import Enum


class PromptSection(str, Enum):
    """Prompt section types."""

    SYSTEM = "system"
    DEVELOPER = "developer"
    USER = "user"


@dataclass
class SegmentedPrompt:
    """Segmented prompt with clear section boundaries."""

    system: str
    developer: str
    user: str

    def to_combined_string(self) -> str:
        """Combine segments with clear markers."""
        segments = []

        if self.system:
            segments.append(f"<|system_prompt|>\n{self.system}\n</|system_prompt|>")

        if self.developer:
            segments.append(f"<|developer_instructions|>\n{self.developer}\n</|developer_instructions|>")

        if self.user:
            segments.append(f"<|user_input|>\n{self.user}\n</|user_input|>")

        return "\n\n".join(segments)


class PromptSegregator:
    """
    Separates system, developer, and user content with markers.

    Implements PALADIN Layer 2: ensures clear boundaries between different
    prompt sources to prevent prompt injection attacks.
    """

    SYSTEM_MARKER = "<|system_prompt|>"
    DEVELOPER_MARKER = "<|developer_instructions|>"
    USER_MARKER = "<|user_input|>"

    MARKER_END = {
        SYSTEM_MARKER: "</|system_prompt|>",
        DEVELOPER_MARKER: "</|developer_instructions|>",
        USER_MARKER: "</|user_input|>",
    }

    def __init__(self, strict: bool = True):
        """
        Initialize segregator.

        Args:
            strict: If True, raise on unexpected markers in content.
        """
        self.strict = strict

    def segment(
        self,
        system: str = "",
        developer: str = "",
        user: str = "",
    ) -> SegmentedPrompt:
        """
        Create segmented prompt with clear boundaries.

        Args:
            system: System/instructions content.
            developer: Developer-provided context.
            user: User input.

        Returns:
            SegmentedPrompt with markers.

        Raises:
            ValueError: If strict mode and markers found in content.
        """
        if self.strict:
            for content in [system, developer, user]:
                if self._contains_markers(content):
                    raise ValueError("Prompt markers detected in content (potential injection)")

        # Remove any accidentally included markers from user input
        user_clean = self._remove_markers(user)

        return SegmentedPrompt(
            system=system,
            developer=developer,
            user=user_clean,
        )

    def _contains_markers(self, content: str) -> bool:
        """Check if content contains prompt markers."""
        markers = list(self.MARKER_END.keys())
        return any(marker in content for marker in markers)

    def _remove_markers(self, content: str) -> str:
        """Remove any markers from content."""
        result = content
        for marker, end_marker in self.MARKER_END.items():
            result = result.replace(marker, "").replace(end_marker, "")
        return result

    def extract_sections(self, combined_prompt: str) -> dict[str, str]:
        """
        Extract sections from combined prompt.

        Args:
            combined_prompt: Combined prompt with markers.

        Returns:
            Dictionary with 'system', 'developer', 'user' keys.
        """
        sections = {
            "system": "",
            "developer": "",
            "user": "",
        }

        # Extract system section
        if self.SYSTEM_MARKER in combined_prompt:
            start = combined_prompt.find(self.SYSTEM_MARKER) + len(self.SYSTEM_MARKER)
            end = combined_prompt.find(self.MARKER_END[self.SYSTEM_MARKER], start)
            if end != -1:
                sections["system"] = combined_prompt[start:end].strip()

        # Extract developer section
        if self.DEVELOPER_MARKER in combined_prompt:
            start = combined_prompt.find(self.DEVELOPER_MARKER) + len(self.DEVELOPER_MARKER)
            end = combined_prompt.find(self.MARKER_END[self.DEVELOPER_MARKER], start)
            if end != -1:
                sections["developer"] = combined_prompt[start:end].strip()

        # Extract user section
        if self.USER_MARKER in combined_prompt:
            start = combined_prompt.find(self.USER_MARKER) + len(self.USER_MARKER)
            end = combined_prompt.find(self.MARKER_END[self.USER_MARKER], start)
            if end != -1:
                sections["user"] = combined_prompt[start:end].strip()

        return sections
