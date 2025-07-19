from py_mini_racer import MiniRacer
from app.src.constants import TIMEOUT_LIMIT, MAX_MEMORY_SIZE


# Load the JS function into memory
# This can also be used to check if the JS code is proper
class DynamicFare:
    def validate(jsCode, ticketType, totalDistance) -> bool:
        try:
            jsContext = MiniRacer()
            jsContext.eval(jsCode, timeout=TIMEOUT_LIMIT, max_memory=MAX_MEMORY_SIZE)
            jsContext.eval(
                f'function getFare("{ticketType}", {totalDistance})',
                timeout=TIMEOUT_LIMIT,
                max_memory=MAX_MEMORY_SIZE,
            )
            jsContext.call(
                "getFare",
                ticketType,
                totalDistance,
                timeout=TIMEOUT_LIMIT,
                max_memory=MAX_MEMORY_SIZE,
            )
            return True
        except Exception as e:
            return False

    def evaluate(jsCode, ticketType, totalDistance) -> float:
        jsContext = MiniRacer()
        jsContext.eval(jsCode, timeout=TIMEOUT_LIMIT, max_memory=MAX_MEMORY_SIZE)
        return jsContext.call(
            "getFare",
            ticketType,
            totalDistance,
            timeout=TIMEOUT_LIMIT,
            max_memory=MAX_MEMORY_SIZE,
        )
