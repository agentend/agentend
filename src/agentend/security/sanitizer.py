"""Input sanitization for PALADIN Layer 1."""

import re
from typing import Optional


class InputSanitizer:
    """
    Input sanitizer for injection prevention.

    Implements PALADIN Layer 1: removes injection patterns, validates input length,
    and strips control characters.
    """

    # Injection patterns to detect and remove
    INJECTION_PATTERNS = [
        r"(?i)<script[^>]*>.*?</script>",  # JavaScript
        r"(?i)<iframe[^>]*>.*?</iframe>",  # Iframes
        r"(?i)<object[^>]*>.*?</object>",  # Objects
        r"(?i)javascript:",  # JavaScript protocol
        r"(?i)data:text/html",  # Data URLs
        r"(?i)on\w+\s*=",  # Event handlers
        r"\$\{.*?\}",  # Template injection
        r"\{\{.*?\}\}",  # Jinja/Django injection
        r"(?i)exec\s*\(",  # Python exec
        r"(?i)eval\s*\(",  # Python eval
        r"(?i)__import__",  # Python imports
    ]

    SQL_PATTERNS = [
        r"(?i)(\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b)",
    ]

    COMMAND_PATTERNS = [
        r";\s*(rm|cat|curl|wget|bash|sh|chmod|chown|sudo|kill)\b",  # Shell command chains
        r"\|\s*(bash|sh|zsh)\b",  # Pipe to shell
        r"`[^`]+`",  # Backtick command substitution
        r"\$\([^)]+\)",  # $() command substitution
    ]

    def __init__(
        self,
        max_length: int = 100000,
        allow_html: bool = False,
        allow_sql: bool = False,
        allow_shell: bool = False,
    ):
        """
        Initialize sanitizer.

        Args:
            max_length: Maximum allowed input length.
            allow_html: If False, remove HTML/script patterns.
            allow_sql: If False, block SQL keywords.
            allow_shell: If False, block shell metacharacters.
        """
        self.max_length = max_length
        self.allow_html = allow_html
        self.allow_sql = allow_sql
        self.allow_shell = allow_shell

    def sanitize(self, input_text: str) -> str:
        """
        Sanitize input text.

        Args:
            input_text: Text to sanitize.

        Returns:
            Sanitized text.

        Raises:
            ValueError: If input is invalid.
        """
        if not isinstance(input_text, str):
            raise ValueError("Input must be string")

        if len(input_text) > self.max_length:
            raise ValueError(f"Input exceeds maximum length of {self.max_length}")

        # Remove null bytes and control characters
        sanitized = "".join(
            c for c in input_text
            if ord(c) >= 32 or c in "\n\r\t"
        )

        # Remove injection patterns
        for pattern in self.INJECTION_PATTERNS:
            sanitized = re.sub(pattern, "", sanitized)

        # Check SQL patterns if not allowed
        if not self.allow_sql:
            for pattern in self.SQL_PATTERNS:
                if re.search(pattern, sanitized):
                    raise ValueError("SQL injection pattern detected")

        # Check shell patterns if not allowed
        if not self.allow_shell:
            for pattern in self.COMMAND_PATTERNS:
                if re.search(pattern, sanitized):
                    raise ValueError("Shell injection pattern detected")

        return sanitized.strip()

    def validate_length(self, text: str, max_length: Optional[int] = None) -> bool:
        """
        Validate text length.

        Args:
            text: Text to validate.
            max_length: Maximum allowed length (defaults to self.max_length).

        Returns:
            True if valid.

        Raises:
            ValueError: If too long.
        """
        limit = max_length or self.max_length
        if len(text) > limit:
            raise ValueError(f"Text exceeds maximum length of {limit}")
        return True

    def has_injection_patterns(self, text: str) -> list[str]:
        """
        Check for injection patterns in text.

        Args:
            text: Text to check.

        Returns:
            List of detected patterns.
        """
        detected = []

        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, text):
                detected.append(pattern)

        return detected
