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


class OptionalAgentError(Exception):
    """Carry completed core data to the endpoint when additional work fails."""

    def __init__(self, endpoint_result: dict, cause: Exception):
        super().__init__("Optional agent task failed")
        self.endpoint_result = endpoint_result
        self.cause = cause
