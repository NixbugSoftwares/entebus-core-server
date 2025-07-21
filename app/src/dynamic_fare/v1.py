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
            fareFunction = self.jsContext.eval(
                f"{self.jsCode}; typeof getFare === 'function';",
                timeout=TIMEOUT_LIMIT,
                max_memory=MAX_MEMORY_SIZE,
            )
            if not fareFunction:
                return False
            return True
        except Exception as e:
            return False

    def evaluate(self, ticketType, totalDistance) -> float:
        return self.jsContext.call("getFare", ticketType, totalDistance)
