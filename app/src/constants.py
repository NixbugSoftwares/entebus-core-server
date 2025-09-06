"""
Application configuration and constants for EnteBus API Server.

This module centralizes environment-based configuration, resource limits,
regular expressions, geometry constraints, timezones, and other constants.

Configuration values can be overridden via environment variables.
"""

from os import environ
from zoneinfo import ZoneInfo


# ---------------------------------------------------------------------------
# Application metadata
# ---------------------------------------------------------------------------
API_TITLE = "EnteBus API Server"
API_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# PostgreSQL configuration
# ---------------------------------------------------------------------------
PSQL_DB_DRIVER = environ.get("PSQL_DB_DRIVER", "postgresql")
PSQL_DB_USERNAME = environ.get("PSQL_DB_USERNAME", "postgres")
PSQL_DB_PORT = environ.get("PSQL_DB_PORT", "5432")
PSQL_DB_PASSWORD = environ.get("PSQL_DB_PASSWORD", "password")
PSQL_DB_HOST = environ.get("PSQL_DB_HOST", "localhost")
PSQL_DB_NAME = environ.get("PSQL_DB_NAME", "postgres")


# ---------------------------------------------------------------------------
# OpenObserve configuration
# ---------------------------------------------------------------------------
OPENOBSERVE_PROTOCOL = environ.get("OPENOBSERVE_PROTOCOL", "http")
OPENOBSERVE_HOST = environ.get("OPENOBSERVE_HOST", "localhost")
OPENOBSERVE_PORT = environ.get("OPENOBSERVE_PORT", "5080")
OPENOBSERVE_USERNAME = environ.get("OPENOBSERVE_USERNAME", "admin@entebus.com")
OPENOBSERVE_PASSWORD = environ.get("OPENOBSERVE_PASSWORD", "password")
OPENOBSERVE_ORG = environ.get("OPENOBSERVE_ORG", "nixbug")
OPENOBSERVE_STREAM = environ.get("OPENOBSERVE_STREAM", "entebus-core-server")


# ---------------------------------------------------------------------------
# Redis configuration
# ---------------------------------------------------------------------------
REDIS_HOST = environ.get("REDIS_HOST", "localhost")
REDIS_PORT = environ.get("REDIS_PORT", "6379")
REDIS_PASSWORD = environ.get("REDIS_PASSWORD", "password")


# ---------------------------------------------------------------------------
# MinIO configuration
# ---------------------------------------------------------------------------
MINIO_HOST = environ.get("MINIO_HOST", "localhost")
MINIO_PORT = environ.get("MINIO_PORT", "9000")
MINIO_USERNAME = environ.get("MINIO_USERNAME", "minio")
MINIO_PASSWORD = environ.get("MINIO_PASSWORD", "password")

# MinIO buckets
EXECUTIVE_PICTURES = "executive-pictures"
OPERATOR_PICTURES = "operator-pictures"
VENDOR_PICTURES = "vendor-pictures"
BUS_PICTURES = "bus-pictures"
BUS_STOP_PICTURES = "bus-stop-pictures"


# ---------------------------------------------------------------------------
# Resource upper limits
# ---------------------------------------------------------------------------
MAX_EXECUTIVE_TOKENS = 5  # Maximum tokens per executive
MAX_OPERATOR_TOKENS = 5  # Maximum tokens per operator
MAX_VENDOR_TOKENS = 1  # Maximum tokens per vendor
MAX_TOKEN_VALIDITY = 7 * 24 * 60 * 60  # Token validity (in seconds, 7 days)


# ---------------------------------------------------------------------------
# Regex constants (input validation)
# ---------------------------------------------------------------------------
REGEX_USERNAME = r"^[a-zA-Z][a-zA-Z0-9-.@_]*$"
REGEX_PASSWORD = r"^[a-zA-Z0-9-+,.@_$%&*#!^=/?]*$"
REGEX_REGISTRATION_NUMBER = r"^[A-Z]{2}[0-9]{2}[A-Z]{0,2}[0-9]{1,4}$"


# ---------------------------------------------------------------------------
# Geometry type constants
# ---------------------------------------------------------------------------
MAX_LANDMARK_AREA = 5 * 1000 * 1000  # 5 km² in m²
MIN_LANDMARK_AREA = 2  # 2 m²
EPSG_4326 = 4326  # WGS 84
EPSG_3857 = 3857  # Web Mercator


# ---------------------------------------------------------------------------
# Route/landmarks constraints
# ---------------------------------------------------------------------------
MIN_LANDMARK_IN_ROUTE = 2  # Minimum number of landmarks per route
MAX_ROUTE_DISTANCE = 10000 * 1000  # Max route length in meters
MAX_ROUTE_DELTA = 10000 * 1000  # Max distance between two landmarks in meters


# ---------------------------------------------------------------------------
# Service/duty constraints
# ---------------------------------------------------------------------------
SERVICE_START_BUFFER_TIME = 60 * 60  # Lead time before duty start (in seconds)
SERVICE_CREATE_BUFFER_TIME = 60 * 60  # Lead time before service creation (in seconds)
MAX_DUTY_PER_SERVICE = 50  # Max duties per service


# ---------------------------------------------------------------------------
# Timezone constants
# ---------------------------------------------------------------------------
TMZ_PRIMARY = ZoneInfo("UTC")
TMZ_SECONDARY = ZoneInfo("Asia/Kolkata")


# ---------------------------------------------------------------------------
# MiniRacer constants (for JS execution limits)
# ---------------------------------------------------------------------------
TIMEOUT_LIMIT = 1000  # Timeout (in ms)
MAX_MEMORY_SIZE = 10 * 1024 * 1024  # Max memory size (10 MB)


# ---------------------------------------------------------------------------
# Redis mutex lock constants
# ---------------------------------------------------------------------------
MUTEX_LOCK_TIMEOUT = 10  # Lock timeout (in seconds)
MUTEX_LOCK_MAX_WAIT_TIME = 60  # Max blocking wait time (in seconds)


# ---------------------------------------------------------------------------
# Fare constants
# ---------------------------------------------------------------------------
DYNAMIC_FARE_VERSION = 1  # Current dynamic fare version
