from os import environ

# Application constants
API_TITLE = "EnteBus API Server"
API_VERSION = "1.0.0"

# PSQL DB configuration
PSQL_DB_DRIVER = environ.get("PSQL_DB_DRIVER", "postgresql")
PSQL_DB_USERNAME = environ.get("PSQL_DB_USERNAME", "postgres")
PSQL_DB_PORT = environ.get("PSQL_DB_PORT", "5432")
PSQL_DB_PASSWORD = environ.get("PSQL_DB_PASSWORD", "password")
PSQL_DB_HOST = environ.get("PSQL_DB_HOST", "localhost")
PSQL_DB_NAME = environ.get("PSQL_DB_NAME", "postgres")

# OpenObserve configuration
OPENOBSERVE_PROTOCOL = environ.get("OPENOBSERVE_PROTOCOL", "http")
OPENOBSERVE_HOST = environ.get("OPENOBSERVE_HOST", "localhost")
OPENOBSERVE_PORT = environ.get("OPENOBSERVE_PORT", "5080")
OPENOBSERVE_USERNAME = environ.get("OPENOBSERVE_USERNAME", "admin@entebus.com")
OPENOBSERVE_PASSWORD = environ.get("OPENOBSERVE_PASSWORD", "password")
OPENOBSERVE_ORG = environ.get("OPENOBSERVE_ORG", "nixbug")
OPENOBSERVE_STREAM = environ.get("OPENOBSERVE_STREAM", "entebus-core-server")

# Redis DB configuration
REDIS_HOST = environ.get("REDIS_HOST", "localhost")
REDIS_PORT = environ.get("REDIS_PORT", "6379")
REDIS_PASSWORD = environ.get("REDIS_PASSWORD", "password")

# MinIO configuration
MINIO_HOST = environ.get("MINIO_HOST", "localhost")
MINIO_PORT = environ.get("MINIO_PORT", "9000")
MINIO_USERNAME = environ.get("MINIO_USERNAME", "minio")
MINIO_PASSWORD = environ.get("MINIO_PASSWORD", "password")

# MinIO buckets
PROFILE_PICTURES = "profile-pictures"
BUS_PICTURES = "bus-pictures"
BUS_STOP_PICTURES = "bus-stop-pictures"

# Resource upper limits
MAX_EXECUTIVE_TOKENS = 5  # Maximum tokens per executive
MAX_TOKEN_VALIDITY = 7 * 24 * 60 * 60  # Number of seconds in a week
MAX_OPERATOR_TOKENS = 5  # Maximum tokens per operator
MAX_VENDOR_TOKENS = 1  # Maximum tokens per vendor

# Regex constants
REGEX_USERNAME = "^[a-zA-Z][a-zA-Z0-9-.@_]*$"
REGEX_PASSWORD = "^[a-zA-Z0-9-+,.@_$%&*#!^=/?]*$"
REGEX_REGISTRATION_NUMBER = "^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{1,4}$"

# Geometry type constants
MAX_LANDMARK_AREA = 5 * 1000 * 1000  # 5 Square Kilometer in Square Meter
MIN_LANDMARK_AREA = 2  # 2 Square Meter
EPSG_4326 = 4326  # WGS 84
EPSG_3857 = 3857  # Web Mercator

# Route landmarks constants
MIN_LANDMARK_IN_ROUTE = 2  # Minimum number of landmarks needed in a route
MAX_ROUTE_DISTANCE = 10000 * 1000  # Maximum length of a route
MAX_ROUTE_DELTA = 10000 * 1000  # Maximum length between two landmarks in a route

# Service constants
SERVICE_START_BUFFER_TIME = 60 * 60  # Buffer time in minutes for duty initialization before services start time
