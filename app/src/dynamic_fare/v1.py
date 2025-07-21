from py_mini_racer import MiniRacer
from app.src.constants import TIMEOUT_LIMIT, MAX_MEMORY_SIZE


# Load the JS function into memory
# This can also be used to check if the JS code is proper
class DynamicFare:
    def __init__(self, jsCode):
        self.jsCode = jsCode
        self.jsContext = None

    def validate(self) -> bool:
        try:
            self.jsContext = MiniRacer()
            self.jsContext.eval(
                self.jsCode, timeout=TIMEOUT_LIMIT, max_memory=MAX_MEMORY_SIZE
            )
            # Check if getFare is a function in the JS context
            fareFunction = self.jsContext.eval("typeof getFare === 'function';")
            if not fareFunction:
                self.jsContext = None
                return False
            return True
        except Exception as e:
            self.jsContext = None
            return False

    def evaluate(self, ticketType, totalDistance) -> float:
        return self.jsContext.call("getFare", ticketType, totalDistance)
