import pythonmonkey


# Load the JS function into memory
# This can also be used to check if the JS code is proper
class DynamicFare:
    def validate(js_code) -> bool:
        try:
            pythonmonkey.eval(js_code)
            return True
        except pythonmonkey.SpiderMonkeyError as e:
            return False

    def evaluate(ticket_type, total_distance) -> float:
        return pythonmonkey.eval(f'getFare("{ticket_type}", {total_distance})')
