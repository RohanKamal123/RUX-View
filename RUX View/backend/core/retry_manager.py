"""Retry with exponential backoff + jitter for transient failures.

Handles transient failures gracefully with configurable retry logic,
exponential backoff, and random jitter to prevent thundering herd.
"""

from typing import Callable, Any, Optional
import asyncio
import random
import logging

logger = logging.getLogger(__name__)


class RetryManager:
    """Retry with exponential backoff + jitter for transient failures.

    Features:
    - Configurable max retries, base delay, max delay
    - Exponential backoff: delay = min(base * 2^attempt, max_delay)
    - Random jitter: delay * (1 + random * jitter)
    - Retryable exception filtering
    - Structured logging of retry attempts
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        jitter: float = 0.1,
    ):
        """Initialize retry manager.

        Args:
            max_retries: Maximum retry attempts (default: 3)
            base_delay: Initial delay in seconds (default: 1.0)
            max_delay: Maximum delay in seconds (default: 30.0)
            jitter: Random jitter fraction 0.0-1.0 (default: 0.1)
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter

    async def execute(
        self,
        func: Callable,
        *args,
        retryable_exceptions: Optional[tuple] = None,
        **kwargs,
    ) -> Any:
        """Execute a function with retry logic.

        Args:
            func: Async function to execute
            retryable_exceptions: Tuple of exception types to retry on.
                If None, retries on all exceptions.
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Function result

        Raises:
            Last exception after max retries exhausted
        """
        if retryable_exceptions is None:
            retryable_exceptions = (Exception,)

        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except retryable_exceptions as e:
                last_exception = e

                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Retry attempt {attempt + 1}/{self.max_retries} "
                        f"for {func.__name__} after {delay:.2f}s. "
                        f"Error: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"All {self.max_retries} retry attempts exhausted "
                        f"for {func.__name__}. Last error: {e}"
                    )

        # All retries exhausted, raise the last exception
        raise last_exception  # type: ignore

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff + jitter.

        delay = min(base * 2^attempt, max_delay) * (1 + random * jitter)

        Args:
            attempt: Current attempt number (0-based)

        Returns:
            Delay in seconds
        """
        exponential_delay = min(
            self.base_delay * (2 ** attempt),
            self.max_delay,
        )
        jitter_amount = 1.0 + (random.random() * self.jitter)
        return exponential_delay * jitter_amount

    def _is_retryable(
        self,
        exception: Exception,
        retryable_exceptions: Optional[tuple],
    ) -> bool:
        """Check if exception type is retryable.

        Args:
            exception: The exception to check
            retryable_exceptions: Tuple of retryable exception types

        Returns:
            True if exception type is retryable
        """
        if retryable_exceptions is None:
            return True
        return isinstance(exception, retryable_exceptions)
