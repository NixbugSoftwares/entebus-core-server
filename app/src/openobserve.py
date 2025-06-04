import base64, json, requests

from app.src.constants import (
    OPENOBSERVE_HOST,
    OPENOBSERVE_ORG,
    OPENOBSERVE_PASSWORD,
    OPENOBSERVE_PORT,
    OPENOBSERVE_PROTOCOL,
    OPENOBSERVE_STREAM,
    OPENOBSERVE_USERNAME,
)


credentials = base64.b64encode(
    bytes(OPENOBSERVE_USERNAME + ":" + OPENOBSERVE_PASSWORD, "utf-8")
).decode("utf-8")
headers = {"Content-type": "application/json", "Authorization": "Basic " + credentials}
openobserve_host = f"{OPENOBSERVE_PROTOCOL}://{OPENOBSERVE_HOST}:{OPENOBSERVE_PORT}"
openobserve_url = f"{openobserve_host}/api/{OPENOBSERVE_ORG}/{OPENOBSERVE_STREAM}/_json"


def logEvent(eventData: dict):
    requests.post(openobserve_url, headers=headers, data=json.dumps(eventData))
