from py_mini_racer import MiniRacer, py_mini_racer
from app.src.constants import TIMEOUT_LIMIT, MAX_MEMORY_SIZE
from app.src import exceptions


# Load the JS function into memory
# This can also be used to check if the JS code is proper
class DynamicFare:
    def __init__(self, jsCode):
        self.jsCode = jsCode
        self.jsContext = None

    def validate(self):
        try:
            self.jsContext = MiniRacer()
            getFare = self.jsContext.eval(
                f"{self.jsCode}; typeof getFare === 'function';"
            )
            if not getFare:
                raise exceptions.InvalidFareFunction()
        except Exception:
            raise exceptions.InvalidFareFunction()

    def evaluate(self, ticketType, totalDistance):
        try:
            return self.jsContext.call(
                "getFare",
                ticketType,
                totalDistance,
                timeout=TIMEOUT_LIMIT,
                max_memory=MAX_MEMORY_SIZE,
            )
        except py_mini_racer.JSTimeoutException:
            return exceptions.JSTimeoutExceeded()
        except py_mini_racer.JSOOMException:
            return exceptions.JSMemoryLimitExceeded()

