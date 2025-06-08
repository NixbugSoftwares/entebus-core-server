from secrets import token_hex
from geoalchemy2 import Geometry
from sqlalchemy import (
    TEXT,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    create_engine,
    func,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.src.constants import PSQL_DB_DRIVER, PSQL_DB_HOST, PSQL_DB_PASSWORD
from app.src.constants import PSQL_DB_NAME, PSQL_DB_PORT, PSQL_DB_USERNAME
from app.src.enums import AccountStatus, GenderType, LandmarkType, PlatformType


# Global DBMS variables
dbURL = f"{PSQL_DB_DRIVER}://{PSQL_DB_USERNAME}:{PSQL_DB_PASSWORD}@{PSQL_DB_HOST}:{PSQL_DB_PORT}/{PSQL_DB_NAME}"
engine = create_engine(url=dbURL, echo=False)
sessionMaker = sessionmaker(bind=engine, expire_on_commit=False)
ORMbase = declarative_base()


# ----------------------------------- General DB Models ---------------------------------------#
class ExecutiveRole(ORMbase):
    """
    Represents a predefined role assigned to executives, defining what actions
    they are permitted to perform within the system.

    Each role can be assigned to one or more executive accounts.

    Columns:
        id (Integer):
            Primary key. Unique identifier for the role.

        name (String(32)):
            Name of the role.
            Must be unique and non-null.

        create_executive (Boolean):
            Whether this role permits the creation of new executive accounts.

        update_executive (Boolean):
            Whether this role permits editing existing executive accounts.

        delete_executive (Boolean):
            Whether this role permits deletion of executive accounts.

        manage_ex_token (Boolean):
            Whether this role permits listing and deletion of executive tokens.

        manage_op_token (Boolean):
            Whether this role permits listing and deletion of operator tokens.

        manage_ve_token (Boolean):
            Whether this role permits listing and deletion of vendor tokens.

        create_landmark (Boolean):
            Whether this role permits the creation of a new landmark.

        update_landmark (Boolean):
            Whether this role permits editing existing the landmark.

        delete_landmark (Boolean):
            Whether this role permits deletion of a landmark.

        updated_on (DateTime):
            Timestamp automatically updated whenever the role record is modified.

        created_on (DateTime):
            Timestamp indicating when the role was initially created.
    """

    __tablename__ = "executive_role"

    id = Column(Integer, primary_key=True)
    name = Column(String(32), nullable=False, unique=True)
    # Token management permission
    manage_ex_token = Column(Boolean, nullable=False)
    manage_op_token = Column(Boolean, nullable=False)
    manage_ve_token = Column(Boolean, nullable=False)
    # Executive management permission
    create_executive = Column(Boolean, nullable=False)
    update_executive = Column(Boolean, nullable=False)
    delete_executive = Column(Boolean, nullable=False)
    # Landmark management permission
    create_landmark = Column(Boolean, nullable=False)
    update_landmark = Column(Boolean, nullable=False)
    delete_landmark = Column(Boolean, nullable=False)
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())


class Executive(ORMbase):
    """
    Represents an executive user within the system, typically someone with elevated
    permissions such as admins, supervisors, or marketing members.

    This model stores authentication credentials, profile details, and status metadata
    necessary to manage executive-level access and communication.

    Columns:
        id (Integer):
            Primary key. Unique identifier for the executive.

        username (String(32)):
            Unique username used for login or identification within the system.
            Ideally, the username shouldn't be changed once set.
            It should start with an alphabet (uppercase or lowercase).
            It can contain uppercase and lowercase letters, as well as digits from 0 to 9.
            It should be 4-32 characters long.
            May include hyphen (-), period (.), at symbol (@), and underscore (_).
            Must be non-null and unique.

        password (TEXT):
            Hashed password used for authentication.
            It should be 8-32 characters long.
            Passwords can contain uppercase and lowercase letters, as well as digits from 0 to 9.
            Plaintext should never be stored here. Argon2 is used for secure hashing.
            May include hyphen (-), plus (+), comma (,), period (.), at symbol (@), underscore (_),
            dollar sign ($), percent (%), ampersand (&), asterisk (*), hash (#),
            exclamation mark (!), caret (^), equals (=), forward slash (/), question mark (?).

        gender (Integer):
            Represents the executive's gender. Mapped from the `GenderType` enum.
            Defaults to `GenderType.OTHER`.

        full_name (TEXT):
            Full name of the executive. Optional field used for display and communication.
            Maximum 32 characters long.

        designation (TEXT):
            Job title or role description of the executive.
            Maximum  32 characters long.

        status (Integer):
            Indicates the account status.
            Mapped from the `AccountStatus` enum. Defaults to `AccountStatus.ACTIVE`.

        phone_number (TEXT):
            Optional contact number of the executive.
            Maximum 32 characters long.
            Saved and processed in RFC3966 format (https://datatracker.ietf.org/doc/html/rfc3966).
            Phone number start with a plus sign followed by country code and local number.

        email_id (TEXT):
            Optional email address for communication and recovery purposes.
            Maximum 256 characters long.
            Enforce the format prescribed by RFC 5322 (https://en.wikipedia.org/wiki/Email_address).

        updated_on (DateTime):
            Timestamp of the last update to the executive's profile or credentials.
            Timestamp automatically updated whenever the executive's profile is modified.

        created_on (DateTime):
            Timestamp of when the executive account was created.
    """

    __tablename__ = "executive"

    id = Column(Integer, primary_key=True)
    username = Column(String(32), nullable=False, unique=True)
    password = Column(TEXT, nullable=False)
    gender = Column(Integer, nullable=False, default=GenderType.OTHER)
    full_name = Column(TEXT)
    designation = Column(TEXT)
    status = Column(Integer, nullable=False, default=AccountStatus.ACTIVE)
    # Contact details
    phone_number = Column(TEXT)
    email_id = Column(TEXT)
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())


class ExecutiveRoleMap(ORMbase):
    """
    Represents the mapping between executives and their assigned roles,
    enabling a many-to-many relationship between `executive` and `executive_role`.

    This table allows an executive to be assigned multiple roles and a role
    to be assigned to multiple executives. Useful for implementing a flexible
    Role-Based Access Control (RBAC) system.

    Columns:
        id (Integer):
            Primary key. Unique identifier for this role mapping record.

        role_id (Integer):
            Foreign key referencing `executive_role.id`.
            Specifies the role assigned to the executive.
            Cascades on delete — if the role is removed, related mappings are deleted.

        executive_id (Integer):
            Foreign key referencing `executive.id`.
            Identifies the executive receiving the role.
            Cascades on delete — if the executive is removed, related mappings are deleted.

        updated_on (DateTime):
            Timestamp automatically updated whenever the mapping record is modified.
            Useful for auditing or synchronization.

        created_on (DateTime):
            Timestamp indicating when this mapping was created.
            Defaults to the current timestamp at insertion.
    """

    __tablename__ = "executive_role_map"

    id = Column(Integer, primary_key=True)
    role_id = Column(
        Integer, ForeignKey("executive_role.id", ondelete="CASCADE"), nullable=False
    )
    executive_id = Column(
        Integer, ForeignKey("executive.id", ondelete="CASCADE"), nullable=False
    )
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())


class ExecutiveToken(ORMbase):
    """
    Represents an authentication token issued to an executive,
    enabling secure access to the platform with support for token expiration
    and client metadata tracking.

    This table stores unique access tokens mapped to executives along with
    details about the device or client used and timestamps for auditing.
    Useful for session management, device tracking, and implementing token-based authentication.

    Columns:
        id (Integer):
            Primary key. Unique identifier for this token record.

        executive_id (Integer):
            Foreign key referencing `executive.id`.
            Identifies the executive associated with this token.
            Cascades on delete — if the executive is removed, related tokens are deleted.

        access_token (String):
            Unique, securely generated 64-character hexadecimal access token.
            Automatically generated using a secure random function.
            Used to authenticate the executive on subsequent requests.

        expires_in (Integer):
            Token expiration time in seconds.
            Defines the duration after which the token becomes invalid.

        expires_at (DateTime):
            Token expiration date and time.
            Defines the date and time after which the token becomes invalid.

        platform_type (Integer):
            Enum value indicating the client platform type.
            Defaults to `PlatformType.OTHER`.

        client_details (TEXT):
            Optional description of the client device or environment.
            May include user agent, app version, IP address, etc.

        updated_on (DateTime):
            Timestamp automatically updated whenever the token record is modified.
            Useful for auditing or tracking last usage.

        created_on (DateTime):
            Timestamp indicating when this token was created.
            Defaults to the current timestamp at insertion.
    """

    __tablename__ = "executive_token"

    id = Column(Integer, primary_key=True)
    executive_id = Column(
        Integer,
        ForeignKey("executive.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    access_token = Column(
        String(64), unique=True, nullable=False, default=lambda: token_hex(32)
    )
    expires_in = Column(Integer, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    # Device related details
    platform_type = Column(Integer, default=PlatformType.OTHER)
    client_details = Column(TEXT)
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())


class Landmark(ORMbase):
    """
    Represents a geo-spatial landmark used for mapping, zoning, or location-aware operations.

    Landmarks are stored as named polygonal areas with versioning and type categorization,
    allowing for geographic indexing, change tracking, and spatial queries (containment,
    overlap, proximity).

    Frontend-Backend Note:
        Although circles are shown and drawn on the frontend UI, they are **converted to
        axis-aligned bounding box (AABB) polygons** before being send to the backend.
        This simplifies spatial operations and indexing in the backend.
        The AABB polygon is a square bounding box tightly enclosing the circle.

    Columns:
        id (Integer):
            Primary key. Unique identifier for the landmark record.

        name (String(32)):
            Human-readable name of the landmark.
            Used for identification in user interfaces or spatial queries.

        version (Integer):
            An integer version number that can be incremented on updates.
            Useful for tracking changes or syncing updated landmark boundaries.

        boundary (Geometry):
            Geo-spatial boundary defined as a PostGIS `POLYGON` with SRID 4326 (WGS 84).
            Represents the physical area covered by the landmark.
            Must be unique — no two landmarks can share the same geometry.

        type (Integer):
            Enum value indicating the type of landmark.
            Defaults to `LandmarkType.LOCAL`.

        updated_on (DateTime):
            Timestamp automatically updated whenever the record is modified.
            Useful for auditing or syncing purposes.

        created_on (DateTime):
            Timestamp indicating when the record was first created.
            Defaults to the current time on insertion.
    """

    __tablename__ = "landmark"

    id = Column(Integer, primary_key=True)
    name = Column(String(32), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    boundary = Column(
        Geometry(geometry_type="POLYGON", srid=4326), nullable=False, unique=True
    )
    type = Column(Integer, nullable=False, default=LandmarkType.LOCAL)
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())
