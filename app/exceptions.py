"""Application exceptions; HTTP translation belongs to the routes layer."""


class UnknownToolError(Exception):
    pass


class ToolArgumentError(Exception):
    pass


class ToolTimeoutError(Exception):
    pass


class ToolExecutionError(Exception):
    pass


class EmptyModelResponseError(Exception):
    pass


class InvalidModelResponseError(Exception):
    pass


class AgentLoopLimitError(Exception):
    pass


class AgentExecutionError(Exception):
    """Agent failed after completing some tools; keep their successful results."""

    def __init__(self, cause: Exception, documents: list[dict]):
        super().__init__("Agent execution failed")
        self.cause = cause
        self.documents = documents


class OptionalAgentError(Exception):
    """Carry completed core data to the endpoint when additional work fails."""

    def __init__(
        self, endpoint_result: dict, cause: Exception, documents: list[dict] | None = None
    ):
        super().__init__("Optional agent task failed")
        self.endpoint_result = endpoint_result
        self.cause = cause
        self.documents = documents or []
