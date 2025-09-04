import base64, json, requests
from requests import Response

from app.src.constants import (
    OPENOBSERVE_HOST,
    OPENOBSERVE_ORG,
    OPENOBSERVE_PASSWORD,
    OPENOBSERVE_PORT,
    OPENOBSERVE_PROTOCOL,
    OPENOBSERVE_STREAM,
    OPENOBSERVE_USERNAME,
)

# Prepare Basic Auth credentials
credentials = base64.b64encode(
    bytes(OPENOBSERVE_USERNAME + ":" + OPENOBSERVE_PASSWORD, "utf-8")
).decode("utf-8")

# Default headers for all requests
headers = {"Content-type": "application/json", "Authorization": "Basic " + credentials}

# Construct OpenObserve endpoint URL
openobserve_host = f"{OPENOBSERVE_PROTOCOL}://{OPENOBSERVE_HOST}:{OPENOBSERVE_PORT}"
openobserve_url = f"{openobserve_host}/api/{OPENOBSERVE_ORG}/{OPENOBSERVE_STREAM}/_json"


def logEvent(eventData: dict) -> Response:
    """
    Send an event log to the configured OpenObserve instance.

    This function serializes the given event data as JSON and sends it
    to the OpenObserve API using HTTP POST with Basic authentication.

    Args:
        eventData (dict): A dictionary representing the event log to be sent.
            Example:
                {
                    "_method": "POST",
                    "_path": "/api/v1/routes",
                    "_app_id": "EXECUTIVE",
                    "_executive_id": "1"
                }

    Returns:
        requests.Response: The HTTP response object returned by the OpenObserve API.
    """
    return requests.post(openobserve_url, headers=headers, data=json.dumps(eventData))
