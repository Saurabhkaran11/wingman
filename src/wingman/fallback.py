"""A model that fails over to the next provider when one runs out of quota.

Free LLM tiers are small and per-model: on a hackathon laptop the binding
constraint is not money, it is a daily request cap. During one evening's
testing a Gemini model hit `RESOURCE_EXHAUSTED` at 20 requests/day and took
the whole brief down mid-run.

FallbackModel wraps an ordered list of models and moves to the next one when
the current one reports a quota or rate-limit failure. A dead model is skipped
permanently for the rest of the process, so the next call does not waste a
request rediscovering that it is exhausted.
"""

from typing import Any, AsyncGenerator, Callable, Iterable

from strands.models.model import Model

from wingman import events

# Substrings that mean "this provider is out of capacity, try another".
# Matched case-insensitively against the exception text, because each SDK
# raises its own type (google.genai.errors.ClientError, openai.RateLimitError,
# botocore ThrottlingException) with no shared base class.
_QUOTA_MARKERS = (
    "429",
    "resource_exhausted",
    "quota",
    "rate limit",
    "rate_limit",
    "too many requests",
    "throttl",
    "insufficient_quota",
    "overloaded",
    "503",
)


def is_quota_error(exc: BaseException) -> bool:
    """True when an exception looks like a quota, rate-limit or overload failure.

    Example: is_quota_error(ClientError("429 RESOURCE_EXHAUSTED ...")) -> True
             is_quota_error(ValueError("bad schema"))                  -> False
    """
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status in (429, 503):
        return True
    text = f"{type(exc).__name__} {exc}".lower()
    return any(marker in text for marker in _QUOTA_MARKERS)


class FallbackModel(Model):
    """Delegates to the first model in the chain that still has capacity.

    Args:
        specs: (label, factory) pairs, best first. The factory is only called
            when that model is actually reached, so a provider whose SDK is
            missing or whose key is bad costs nothing until it is needed.

    Example:
        FallbackModel([("groq/llama-3.3-70b", make_groq), ("gemini/3.5-flash", make_gemini)])
        -> uses Groq; on a 429 from Groq, silently continues on Gemini.
    """

    def __init__(self, specs: Iterable[tuple[str, Callable[[], Model]]]):
        self._specs = list(specs)
        if not self._specs:
            raise ValueError("FallbackModel needs at least one model")
        self._built: dict[int, Model] = {}
        self._first = 0  # everything before this is exhausted or broken

    # -- chain plumbing ----------------------------------------------------

    def _model(self, index: int) -> Model:
        if index not in self._built:
            self._built[index] = self._specs[index][1]()
        return self._built[index]

    @property
    def label(self) -> str:
        """The provider currently in use, e.g. "groq/llama-3.3-70b-versatile"."""
        return self._specs[self._first][0]

    def _retire(self, index: int, exc: BaseException) -> None:
        """Skip this model for the rest of the process and say so once."""
        if index >= self._first:
            self._first = index + 1
        remaining = self._specs[self._first][0] if self._first < len(self._specs) else "nothing left"
        events.emit(
            "warn",
            f"{self._specs[index][0]} is out of quota",
            f"{str(exc)[:120]} — falling back to {remaining}",
        )

    def _exhausted(self, last: BaseException | None) -> BaseException:
        return RuntimeError(
            "every model in the chain is out of quota. Add another provider key "
            f"(GROQ_API_KEY is the most generous free tier). Last error: {last}"
        )

    # -- the Model interface ----------------------------------------------

    async def stream(self, *args: Any, **kwargs: Any) -> AsyncGenerator[Any, None]:
        last: BaseException | None = None
        for index in range(self._first, len(self._specs)):
            started = False
            try:
                async for event in self._model(index).stream(*args, **kwargs):
                    started = True
                    yield event
                return
            except Exception as exc:
                # Once events have been yielded the turn is half-emitted, and
                # restarting it on another provider would duplicate output.
                # A quota refusal always arrives before the first event, so
                # this still covers the case it exists for.
                if started or not is_quota_error(exc):
                    raise
                self._retire(index, exc)
                last = exc
        raise self._exhausted(last)

    async def structured_output(self, *args: Any, **kwargs: Any) -> AsyncGenerator[Any, None]:
        last: BaseException | None = None
        for index in range(self._first, len(self._specs)):
            started = False
            try:
                async for event in self._model(index).structured_output(*args, **kwargs):
                    started = True
                    yield event
                return
            except Exception as exc:
                if started or not is_quota_error(exc):
                    raise
                self._retire(index, exc)
                last = exc
        raise self._exhausted(last)

    def get_config(self) -> Any:
        return self._model(self._first).get_config()

    def update_config(self, **model_config: Any) -> None:
        # Apply to every model already built, so a later fallback keeps the setting.
        for model in self._built.values():
            model.update_config(**model_config)
