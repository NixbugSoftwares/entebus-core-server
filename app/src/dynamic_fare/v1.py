from py_mini_racer import MiniRacer


# Load the JS function into memory
# This can also be used to check if the JS code is proper
class DynamicFare:
    def validate(jsCode, ticketType, totalDistance) -> bool:
        try:
            jsContext = MiniRacer()
            jsContext.eval(jsCode)
            jsContext.call("getFare", ticketType, totalDistance)
            return True
        except Exception as e:
            return False

    def evaluate(jsCode, ticketType, totalDistance) -> float:
        jsContext = MiniRacer()
        jsContext.eval(jsCode)
        return jsContext.call("getFare", ticketType, totalDistance)
