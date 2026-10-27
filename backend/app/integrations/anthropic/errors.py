class ClaudeUnavailable(RuntimeError):
    """Claude isn't configured or the API call failed. Callers should use their non-AI fallback."""
