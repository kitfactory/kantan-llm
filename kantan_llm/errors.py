from __future__ import annotations


class KantanLLMError(RuntimeError):
    """Base error for kantan-llm. / kantan-llm の基底例外。"""


class ProviderInferenceError(KantanLLMError):
    """Raised when provider cannot be inferred. / provider 推測不能。"""

    def __init__(self, model: str):
        super().__init__(f"[kantan-llm][E1] Provider inference failed for model: {model}")


class MissingConfigError(KantanLLMError):
    """Raised when required config is missing. / 必須設定不足。"""


class UnsupportedProviderError(KantanLLMError):
    """Raised when provider is not supported. / 未対応 provider。"""

    def __init__(self, provider: str):
        super().__init__(f"[kantan-llm][E5] Unsupported provider: {provider}")


class ProviderUnavailableError(KantanLLMError):
    """Raised when no provider is available. / 利用可能 provider なし。"""

    def __init__(self, reasons: str):
        super().__init__(f"[kantan-llm][E4] No available provider. Reasons: {reasons}")


class WrongAPIError(KantanLLMError):
    """Raised when using wrong API for provider. / provider に対し誤ったAPIを使用。"""


class InvalidOptionsError(KantanLLMError):
    """Raised when options are inconsistent. / オプション不整合。"""

    def __init__(self):
        super().__init__("[kantan-llm][E8] Specify only one of provider=... or providers=[...]")


class InvalidTracerError(KantanLLMError):
    """Raised when tracer is invalid. / tracer が不正。"""

    def __init__(self, tracer: object):
        super().__init__(f"[kantan-llm][E14] Invalid tracer (expected TracingProcessor): {tracer!r}")


class MissingDependencyError(KantanLLMError):
    """Raised when optional dependency is missing. / オプション依存が不足。"""

    def __init__(self, dependency: str):
        super().__init__(f"[kantan-llm][E15] Missing optional dependency for tracer: {dependency}")


class NotSupportedError(KantanLLMError):
    """Raised when feature is not supported. / 未対応機能。"""

    def __init__(self, feature: str):
        super().__init__(f"[kantan-llm][E16] Not supported: {feature}")
