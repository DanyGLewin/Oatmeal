from __future__ import division, absolute_import, print_function, unicode_literals


class OtmlBaseException(Exception):
    def __init__(self, msg, data=None):
        super().__init__(msg)
        self.msg = msg
        self.data = data or {}

    def __str__(self):
        if self.data:
            return f'"{self.msg}" - {self.data}'
        return f"{self.msg}"


class ConfigurationManagerError(OtmlBaseException):
    pass


class ConstraintError(OtmlBaseException):
    pass


class CostVectorOperationError(OtmlBaseException):
    pass


class FeatureParseError(OtmlBaseException):
    pass


class UnknownFeatureError(FeatureParseError):
    pass


class GrammarError(OtmlBaseException):
    pass

class GrammarParseError(OtmlBaseException):
    pass


class OtmlConfigurationError(OtmlBaseException):
    pass


class OtmlError(OtmlBaseException):
    pass


class StochasticTestError(OtmlBaseException):
    pass


class TransducerError(OtmlBaseException):
    pass


class TransducerOptimizationError(OtmlBaseException):
    pass
