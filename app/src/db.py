from secrets import token_hex
from geoalchemy2 import Geometry
from sqlalchemy import (
    TEXT,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import JSONB

from app.src.constants import (
    PSQL_DB_DRIVER,
    PSQL_DB_HOST,
    PSQL_DB_PASSWORD,
    PSQL_DB_NAME,
    PSQL_DB_PORT,
    PSQL_DB_USERNAME,
)
from app.src.enums import (
    AccountStatus,
    BankAccountType,
    GenderType,
    LandmarkType,
    PlatformType,
    BusinessStatus,
    BusinessType,
    CompanyStatus,
    CompanyType,
    FareScope,
)


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
            Must be unique and not null.

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

        create_bus_stop (Boolean):
            Whether this role permits the creation of a new bus stop.

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
    # Bus Stop management permission
    create_bus_stop = Column(Boolean, nullable=False)
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
            Must not be null and unique.

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
            Maximum 1024 characters long.

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


class Company(ORMbase):
    """
    Represents a company registered in the system, along with its status,
    type, contact information, and geographical location.

    This table stores core organizational data and is linked to other entities
    such as operators, roles, and tokens. It supports categorization, status tracking,
    and location-based operations.

    Columns:
        id (Integer):
            Primary key. Unique identifier for the company.

        name (String):
            Name of the company.
            Must be unique and is required.

        status (Integer):
            Enum representing the verification status of the company
            Defaults to `CompanyStatus.UNDER_VERIFICATION`.

        type (Integer):
            Enum representing the type/category of the company.
            Defaults to `CompanyType.OTHER`.

        address (TEXT):
            Optional physical or mailing address of the company.

        contact_person (TEXT):
            Optional name of the primary contact person for the company.

        phone_number (TEXT):
            Optional phone number associated with the company.

        email_id (TEXT):
            Optional email address for company-related communication.

        location (Geometry):
            Geographical location of the company represented as a `POINT`
            geometry with SRID 4326. Required for location-based features.

        updated_on (DateTime):
            Timestamp automatically updated whenever the company record is modified.
            Useful for tracking updates and synchronization.

        created_on (DateTime):
            Timestamp indicating when the company record was created.
            Automatically set to the current timestamp at insertion.
    """

    __tablename__ = "company"

    id = Column(Integer, primary_key=True)
    name = Column(String(32), nullable=False, unique=True)
    status = Column(Integer, nullable=False, default=CompanyStatus.UNDER_VERIFICATION)
    type = Column(Integer, nullable=False, default=CompanyType.OTHER)
    # Contact details
    address = Column(TEXT)
    contact_person = Column(TEXT)
    phone_number = Column(TEXT)
    email_id = Column(TEXT)
    location = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())


class Operator(ORMbase):
    """
    Represents an operator account within a company, containing authentication
    credentials, contact information, and metadata related to account status.

    This table defines the core identity and login profile for operators who
    perform various operational tasks in a multi-tenant system. Each operator
    is linked to a specific company and can be uniquely identified by a
    username within that company.

    The design supports reuse of usernames across different companies while
    enforcing uniqueness within each company to maintain account separation
    and security in multi-organization deployments.

    Columns:
        id (Integer):
            Primary key. Unique identifier for the operator account.

        company_id (Integer):
            Foreign key referencing `company.id`.
            Identifies the company to which the operator belongs.
            Cascades on delete — if the company is deleted, all its operators are removed.

        username (String(32)):
            Unique username used for login or identification within the system.
            Ideally, the username shouldn't be changed once set.
            It should start with an alphabet (uppercase or lowercase).
            It can contain uppercase and lowercase letters, as well as digits from 0 to 9.
            It should be 4-32 characters long.
            May include hyphen (-), period (.), at symbol (@), and underscore (_).
            Must not be null and unique.

        password (TEXT):
            Hashed password used for authentication.
            It should be 8-32 characters long.
            Passwords can contain uppercase and lowercase letters, as well as digits from 0 to 9.
            Plaintext should never be stored here. Argon2 is used for secure hashing.
            May include hyphen (-), plus (+), comma (,), period (.), at symbol (@), underscore (_),
            dollar sign ($), percent (%), ampersand (&), asterisk (*), hash (#),
            exclamation mark (!), caret (^), equals (=), forward slash (/), question mark (?).

        gender (Integer):
            Enum representing the operator’s gender.
            Defaults to `GenderType.OTHER`.

        full_name (TEXT):
            The full name of the operator (optional).
            Maximum 32 characters long.

        status (Integer):
            Enum representing the account's current status.
            Defaults to `AccountStatus.ACTIVE`.

        phone_number (TEXT):
            Optional contact phone number for the operator.
            Maximum 32 characters long.
            Saved and processed in RFC3966 format (https://datatracker.ietf.org/doc/html/rfc3966).
            Phone number start with a plus sign followed by country code and local number.

        email_id (TEXT):
            Optional contact email address for the operator.
            Maximum 256 characters long.
            Enforce the format prescribed by RFC 5322 (https://en.wikipedia.org/wiki/Email_address).

        updated_on (DateTime):
            Timestamp of the last update to the operator's profile or credentials.
            Timestamp automatically updated whenever the operators's profile is modified.

        created_on (DateTime):
            Timestamp of when the operators account was created.

    Constraints:
        UniqueConstraint (username, company_id):
            Ensures that usernames are unique within each company.
            The same username may exist in different companies.
    """

    __tablename__ = "operator"
    __table_args__ = (UniqueConstraint("username", "company_id"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(
        Integer,
        ForeignKey("company.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    username = Column(String(32), nullable=False)
    password = Column(TEXT, nullable=False)
    gender = Column(Integer, nullable=False, default=GenderType.OTHER)
    full_name = Column(TEXT)
    status = Column(Integer, nullable=False, default=AccountStatus.ACTIVE)
    # Contact details
    phone_number = Column(TEXT)
    email_id = Column(TEXT)
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())


class OperatorToken(ORMbase):
    """
    Represents authentication tokens issued to operators, enabling secure access and session management
    within a specific company context. This table supports device-level tracking, token expiration,
    and audit metadata for robust token-based authentication systems.

    Columns:
        id (Integer):
            Primary key. A unique identifier for each operator token record.

        operator_id (Integer):
            Foreign key referencing `operator.id`.
            Identifies the operator to whom the token is issued.
            Indexed to improve lookup speed for operator-based queries.
            Cascades on delete — removing an operator deletes associated tokens.

        company_id (Integer):
            Foreign key referencing `company.id`.
            Specifies the company context in which the token is valid.
            Cascades on delete — removing the company deletes related tokens.

        access_token (String(64)):
            Secure token string used for authentication.
            Must be unique and non-null.
            Default is a 64-character random hexadecimal string generated using `token_hex(32)`.

        expires_in (Integer):
            Duration (in seconds) for which the token remains valid from the time of creation.
            Used for calculating token expiry dynamically.

        expires_at (DateTime):
            Absolute timestamp indicating when the token becomes invalid.
            Typically derived from `created_on + expires_in`.

        platform_type (Integer):
            Indicates the type of device or platform from which the token was issued.
            Defaults to `PlatformType.OTHER`.
            Useful for device-aware authentication and access logging.

        client_details (TEXT):
            Optional description of the client device or environment.
            May include user agent, app version, IP address, etc.
            Maximum 1024 characters long.

        updated_on (DateTime):
            Timestamp that updates automatically whenever the record is modified.
            Useful for tracking changes to token details over time.

        created_on (DateTime):
            Timestamp marking when the token was created.
            Automatically set to the current time at the point of insertion.
    """

    __tablename__ = "operator_token"

    id = Column(Integer, primary_key=True)
    operator_id = Column(
        Integer,
        ForeignKey("operator.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id = Column(
        Integer, ForeignKey("company.id", ondelete="CASCADE"), nullable=False
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


class OperatorRole(ORMbase):
    """
    Represents the role assigned to operators within a company for token management and
    access control functionality.

    Defines a simplified role schema focused on permission to manage operator tokens.
    This structure contributes to a modular Role-Based Access Control (RBAC) system
    that can evolve with future expansions.

    Columns:
        id (Integer):
            Primary key. Unique identifier for the operator role.

        name (String(32)):
            Name of the role. Must be unique across the company.

        company_id (Integer):
            Foreign key referencing `company.id`.
            Indicates the company to which this role is assigned.
            Cascades on delete — deleting the company removes related roles.

        manage_op_token (Boolean):
            Determines whether the role grants permission to manage operator tokens.

        updated_on (DateTime):
            Timestamp automatically updated whenever the role record is modified.
            Useful for audit logging and synchronization.

        created_on (DateTime):
            Timestamp indicating when this role was created.
            Defaults to the current timestamp at the time of insertion.
    """

    __tablename__ = "operator_role"
    __table_args__ = (UniqueConstraint("name", "company_id"),)

    id = Column(Integer, primary_key=True)
    name = Column(String(32), nullable=False, unique=True)
    company_id = Column(
        Integer,
        ForeignKey("company.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Token management permission
    manage_op_token = Column(Boolean, nullable=False)
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())


class OperatorRoleMap(ORMbase):
    """
    Represents the mapping between operators and their assigned roles within a company,
    enabling a many-to-many relationship between `operator` and `operator_role` scoped by `company`.

    This table allows:
    - An operator to be assigned multiple roles within a company.
    - A role to be assigned to multiple operators.
    - Support for multi-tenant Role-Based Access Control (RBAC) systems through the `company_id` field.

    Columns:
        id (Integer):
            Primary key. Unique identifier for this operator-role mapping record.

        company_id (Integer):
            Foreign key referencing `company.id`.
            Indicates which company the role-operator mapping belongs to.
            Indexed for efficient querying.
            Cascades on delete — if the company is removed, related mappings are deleted.

        role_id (Integer):
            Foreign key referencing `operator_role.id`.
            Specifies the role assigned to the operator.
            Cascades on delete — if the role is removed, related mappings are deleted.

        operator_id (Integer):
            Foreign key referencing `operator.id`.
            Identifies the operator receiving the role.
            Cascades on delete — if the operator is removed, related mappings are deleted.

        updated_on (DateTime):
            Timestamp automatically updated whenever the mapping record is modified.
            Useful for auditing or synchronization purposes.

        created_on (DateTime):
            Timestamp indicating when this mapping was created.
            Automatically set to the current time at insertion.
    """

    __tablename__ = "operator_role_map"

    id = Column(Integer, primary_key=True)
    company_id = Column(
        Integer,
        ForeignKey("company.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id = Column(
        Integer, ForeignKey("operator_role.id", ondelete="CASCADE"), nullable=False
    )
    operator_id = Column(
        Integer, ForeignKey("operator.id", ondelete="CASCADE"), nullable=False
    )
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


class Fare(ORMbase):
    """
    Represents a fare configuration used by a transport company to determine ticket pricing.

    Each fare defines pricing logic and metadata, optionally scoped by applicability.
    Fares are versioned and uniquely named per company, supporting fare updates, seasonal changes,
    or experimental pricing models. The fare logic is stored as text, and attributes define input
    parameters or configuration details.

    Table Constraints:
        - UniqueConstraint(name, company_id):
            Ensures that a fare with the same name cannot exist more than once per company.
            Enables companies to version or replace fares by name without duplication.

    Columns:
        id (Integer):
            Primary key. Auto-incremented unique identifier for the fare record.

        company_id (Integer):
            References the `company.id` column.
            Indicates which company owns the fare configuration.
            Uses cascading delete — fares are deleted if the associated company is removed.

        version (Integer):
            Numerical version of the fare.
            Used to track changes or revisions to fare logic.

        name (String(32)):
            Human-readable name of the fare.
            Max length is 32 characters.
            Indexed to support fast lookup by name.

        attributes (JSONB):
            A structured set of parameters that define how the fare behaves.
            Stored as binary JSON for efficient querying and indexing in PostgreSQL.

        function (TEXT):
            The implementation logic for the fare, often expressed as a code block or formula.
            This function interprets the `attributes` to calculate fares dynamically.
            Unlimited size (`TEXT`), but should be validated for security/syntax at the application layer.

        scope (Integer):
            Indicates where or how the fare applies.
            Typically mapped to an enum like `FareScope.GLOBAL`.
            Defaults to global scope.

        updated_on (DateTime):
            Timestamp that is automatically updated when the record changes.
            Used for auditing and cache invalidation.

        created_on (DateTime):
            Timestamp indicating when the fare record was created.
            Set automatically at insertion time.
    """

    __tablename__ = "fare"
    __table_args__ = (UniqueConstraint("name", "company_id"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("company.id", ondelete="CASCADE"))
    version = Column(Integer, nullable=False, default=1)
    name = Column(String(32), nullable=False, index=True)
    attributes = Column(JSONB, nullable=False)
    function = Column(TEXT, nullable=False)
    scope = Column(Integer, nullable=False, default=FareScope.GLOBAL)
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())


class BusStop(ORMbase):
    """
    Represents a physical bus stop with a precise geospatial location and a relationship
    to a parent landmark.

    This table supports mapping and location-aware operations within transportation systems.
    Each bus stop is uniquely identified by a combination of its geographic `POINT` location
    and the `landmark` it belongs to. This model is useful for building spatial queries,
    organizing stops within specific zones, and supporting efficient geospatial indexing.

    Columns:
        id (Integer):
            Primary key. Unique identifier for the bus stop record.
            Auto-incremented by the database.

        name (TEXT):
            Human-readable name of the bus stop.
            Used for labeling in interfaces, navigation, and route planning.
            Maximum length is 128 characters.

        landmark_id (Integer):
            Foreign key to the `landmark.id` column.
            Associates the bus stop with a specific landmark.
            Required field. Deleting the associated landmark cascades and deletes the bus stop.

        location (Geometry):
            Geospatial location of the bus stop defined as a PostGIS `POINT` with SRID 4326 (WGS 84).
            Represents a specific latitude and longitude coordinate.
            Must be unique in combination with `landmark_id`.

        updated_on (DateTime):
            Timestamp automatically updated whenever the record is modified.
            Timezone-aware.
            Useful for tracking changes or syncing data.

        created_on (DateTime):
            Timestamp indicating when the bus stop was created.
            Timezone-aware.
            Automatically set at the time of record insertion.

    Table Constraints:
        UniqueConstraint(location, landmark_id):
            Ensures no two bus stops exist at the same geographic point within the same landmark.
            Helps maintain spatial uniqueness and prevents duplication.
    """

    __tablename__ = "bus_stop"
    __table_args__ = (UniqueConstraint("location", "landmark_id"),)

    id = Column(Integer, primary_key=True)
    name = Column(TEXT, nullable=False)
    landmark_id = Column(
        Integer, ForeignKey("landmark.id", ondelete="CASCADE"), nullable=False
    )
    location = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())


class Business(ORMbase):
    """
    Represents a registered business entity within the system, serving as the parent
    organization for vendors, roles, and associated services.

    Each business maintains its own contact and identity information, status,
    classification type, and geographic location. This table supports business-level
    segregation and access control for multi-tenant architecture.

    Columns:
        id (Integer):
            Primary key. Unique identifier for the business.

        name (String(32)):
            Name of the business.
            Must not be null.
            Maximum 32 characters long.
            Used for identification and display across the platform.

        status (Integer):
            Indicates the current status of the business.
            Mapped from the `BusinessStatus`.
            Defaults to `BusinessStatus.ACTIVE`.

        type (Integer):
            Classifies the nature of the business.
            Mapped from the `BusinessType` enum.
            Defaults to `BusinessType.OTHER`.

        address (TEXT):
            Optional physical address of the business.
            Used for communication or billing purposes.
            Maximum 128 characters long.

        contact_person (TEXT):
            Name of the contact person for the business.
            Must not be null.
            Maximum 32 characters long.

        phone_number (TEXT):
            Contact number for the business, must not be null and unique.
            Maximum 32 characters long.
            Saved and processed in RFC3966 format (https://datatracker.ietf.org/doc/html/rfc3966).
            Phone number start with a plus sign followed by country code and local number.

        email_id (TEXT):
            Email address for the business, must not be null and unique.
            Maximum length is 256 characters.
            Enforce the format prescribed by RFC 5322 (https://en.wikipedia.org/wiki/Email_address).

        website (TEXT):
            Optional URL to the business's website or landing page.
            Should be a valid HTTP(S) address if provided.
            Maximum length is 256 characters.

        location (Geometry(Point)):
            Represents the geographic location of the business in (latitude/longitude).
            Stored as a POINT geometry with SRID 4326 (WGS 84).
            Useful for spatial queries, mapping, and proximity-based operations.

        updated_on (DateTime):
            Timestamp automatically updated when the business record is modified.
            Useful for tracking the last administrative change.

        created_on (DateTime):
            Timestamp indicating when the business record was initially created.
            Automatically set during insertion.
    """

    __tablename__ = "business"

    id = Column(Integer, primary_key=True)
    name = Column(String(32), nullable=False)
    status = Column(Integer, nullable=False, default=BusinessStatus.ACTIVE)
    type = Column(Integer, nullable=False, default=BusinessType.OTHER)
    # Contact details
    address = Column(TEXT)
    contact_person = Column(TEXT, nullable=False)
    phone_number = Column(TEXT, nullable=False, unique=True)
    email_id = Column(TEXT, nullable=False, unique=True)
    website = Column(TEXT)
    location = Column(Geometry(geometry_type="POINT", srid=4326))
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())


class Vendor(ORMbase):
    """
    Represents a vendor within the business, typically a business representative or agent
    who interacts with the platform's services.

    This model stores authentication credentials, profile details, and status metadata
    necessary to manage vendor-level access and communication.

    Columns:
        id (Integer):
            Primary key. Unique identifier for the vendor.

        business_id (Integer):
            Foreign key referencing the associated business entity, its indexed.
            Links the vendor to a parent business account.
            Must not be null, Cascading deletion is applied when the business is deleted.

        username (String(32)):
            Unique username used for login or identification within the business entity.
            Ideally, the username shouldn't be changed once set.
            Must start with an alphabet (uppercase or lowercase).
            Can include uppercase and lowercase letters, digits (0 to 9),
            and symbols like hyphen (-), period (.), at symbol (@), and underscore (_).
            Must be 4-32 characters long.
            Must not be null, and unique against business.

        password (TEXT):
            Hashed password used for secure authentication.
            Length must be 8-32 characters.
            Allowed characters include uppercase, lowercase letters, digits, and special characters
            such as hyphen (-), plus (+), comma (,), period (.), at (@), underscore (_),
            dollar sign ($), percent (%), ampersand (&), asterisk (*), hash (#),
            exclamation mark (!), caret (^), equals (=), forward slash (/), question mark (?).
            Plaintext passwords are never stored. Argon2 is used for hashing.

        gender (Integer):
            Represents the vendor's gender.
            Mapped from the `GenderType` enum.
            Defaults to `GenderType.OTHER`.

        full_name (TEXT):
            Full name of the vendor.
            Optional field used for identification or display and communication.
            Maximum length is 32 characters.

        status (Integer):
            Indicates the account status of the vendor.
            Mapped from the `AccountStatus` enum.
            Defaults to `AccountStatus.ACTIVE`.

        phone_number (TEXT):
            Optional contact number of the vendor.
            Must be in RFC3966 format (https://datatracker.ietf.org/doc/html/rfc3966).
            Begins with a plus sign (+) followed by the country code and local number.
            Maximum length is 32 characters.

        email_id (TEXT):
            Optional email address for communication or password recovery.
            Maximum length is 256 characters.
            Should conform to RFC 5322 standards (https://en.wikipedia.org/wiki/Email_address).

        updated_on (DateTime):
            Timestamp of the last update to the vendor's profile or credentials.
            Automatically updated whenever the vendor's profile is modified.

        created_on (DateTime):
            Timestamp indicating when the vendor account was created.
            Automatically set at the time of account creation.
    """

    __tablename__ = "vendor"
    __table_args__ = (UniqueConstraint("business_id", "username"),)

    id = Column(Integer, primary_key=True)
    business_id = Column(
        Integer,
        ForeignKey("business.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    username = Column(String(32), nullable=False)
    password = Column(TEXT, nullable=False)
    gender = Column(Integer, nullable=False, default=GenderType.OTHER)
    full_name = Column(TEXT)
    status = Column(Integer, nullable=False, default=AccountStatus.ACTIVE)
    # Contact details
    phone_number = Column(TEXT)
    email_id = Column(TEXT)
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())


class VendorToken(ORMbase):
    """
    Represents an authentication token issued to a vendor,
    providing secure access to the platform with support for token expiration,
    device tracking, and client metadata tracking.

    This table stores unique access tokens mapped to executives along with
    details about the device or client used and timestamps for auditing.
    Useful for session management, device tracking, and implementing token-based authentication.

    Columns:
        id (Integer):
            Primary key. Unique identifier for this token record.

        business_id (Integer):
            Foreign key referencing the associated business entity.
            Identifies the business associated with the vendor.
            Enforces cascading delete — if the business is deleted, related vendor tokens are also removed.

        vendor_id (Integer):
            Foreign key referencing the associated vendor entity, its indexed.
            Identifies the vendor who owns this token.
            Cascades on delete — if the vendor is removed, associated tokens are deleted.

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
            Maximum 1024 characters long.

        updated_on (DateTime):
            Timestamp automatically updated when the token record is modified.
            Useful for tracking recent activity or token refresh events.

        created_on (DateTime):
            Timestamp indicating when the token was initially created.
            Automatically set to the current time at insertion.
    """

    __tablename__ = "vendor_token"

    id = Column(Integer, primary_key=True)
    business_id = Column(
        Integer,
        ForeignKey("business.id", ondelete="CASCADE"),
        nullable=False,
    )
    vendor_id = Column(
        Integer,
        ForeignKey("vendor.id", ondelete="CASCADE"),
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


class VendorRole(ORMbase):
    """
    Represents a predefined role assigned to vendors, defining their access
    privileges and management capabilities within a business account.

    Each role is scoped to a specific business and can be assigned to one or more vendors,
    allowing granular control over vendor permissions and responsibilities.

    Columns:
        id (Integer):
            Primary key. Unique identifier for the role.

        name (String(32)):
            Name of the role.
            Must not be null, and unique against business.

        business_id (Integer):
            Foreign key referencing the associated business entity, its indexed.
            Identifies the business this role belongs to.
            Enforces cascading delete — if the business is deleted, the role is also removed.

        manage_token (Boolean):
            Indicates whether the role permits listing and deletion of vendor tokens.

        create_vendor (Boolean):
            Whether this role allows creation of new vendor accounts.

        update_vendor (Boolean):
            Whether this role allows editing existing vendor accounts.

        delete_vendor (Boolean):
            Whether this role allows deletion of vendor accounts.

        create_role (Boolean):
            Whether this role permits creation of new vendor roles.

        update_role (Boolean):
            Whether this role permits editing existing vendor roles.

        delete_role (Boolean):
            Whether this role permits deletion of vendor roles.

        updated_on (DateTime):
            Timestamp automatically updated when the role record is modified.

        created_on (DateTime):
            Timestamp indicating when the role was initially created.
    """

    __tablename__ = "vendor_role"
    __table_args__ = (UniqueConstraint("name", "business_id"),)

    id = Column(Integer, primary_key=True)
    name = Column(String(32), nullable=False)
    business_id = Column(
        Integer,
        ForeignKey("business.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Vendor token management permission
    manage_token = Column(Boolean, nullable=False)
    # Vendor management permission
    create_vendor = Column(Boolean, nullable=False)
    update_vendor = Column(Boolean, nullable=False)
    delete_vendor = Column(Boolean, nullable=False)
    # Vendor role management permission
    create_role = Column(Boolean, nullable=False)
    update_role = Column(Boolean, nullable=False)
    delete_role = Column(Boolean, nullable=False)
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())


class VendorRoleMap(ORMbase):
    """
    Represents the mapping between vendors and their assigned roles,
    enabling a many-to-one relationship between `vendor` and `vendor_role`.

    This table allows an vendor to be assigned multiple roles and a role
    to be assigned to multiple vendor. Useful for implementing a flexible
    Role-Based Access Control (RBAC) system.

    Columns:
        id (Integer):
            Primary key. Unique identifier for this role mapping record.

        business_id (Integer):
            Foreign key referencing the associated business entity, its indexed.
            Identifies the business under which the vendor-role mapping exists.
            Cascades on delete — if the business is deleted, related mappings are also deleted.

        role_id (Integer):
            Foreign key referencing `vendor_role.id`.
            Specifies the role assigned to the vendor.
            Cascades on delete — if the role is removed, related mappings are deleted.

        vendor_id (Integer):
            Foreign key referencing `vendor.id`.
            Identifies the vendor receiving the role.
            Cascades on delete — if the vendor is removed, the mapping is deleted.

        updated_on (DateTime):
            Timestamp automatically updated whenever the mapping record is modified.
            Useful for auditing or tracking role changes.

        created_on (DateTime):
            Timestamp indicating when this mapping was created.
            Defaults to the current timestamp at insertion.
    """

    __tablename__ = "vendor_role_map"

    id = Column(Integer, primary_key=True)
    business_id = Column(
        Integer,
        ForeignKey("business.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id = Column(
        Integer,
        ForeignKey("vendor_role.id", ondelete="CASCADE"),
        nullable=False,
    )
    vendor_id = Column(
        Integer,
        ForeignKey("vendor.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())


class Wallet(ORMbase):
    """
    Represents a digital wallet tied to an associated object (e.g: entebus, company, merchant).

    - Wallets must be manually removed when the associated object is removed.
    - Wallets cannot be deleted if the balance is not zero, as it could lead to accounting inconsistencies.
    - Deletion is restricted via a database trigger (for non zero balance).
    - Wallet cannot be deleted if the debit_transfer, credit_transfer or wallet_transfer refer to this wallet.
    - Data cleaner should handle dangling wallets.

    Columns:
        id (Integer):
            Primary key. Unique identifier for the wallet.

        name (TEXT):
            Name of the wallet. This field is required.
            Maximum 32 characters in length

        balance (Numeric(10, 2)):
            The current balance of the wallet.
            Must be zero before deletion is permitted.

        updated_on (DateTime):
            The timestamp of the last balance update or modification.
            This is automatically set to the current time when the wallet is modified.

        created_on (DateTime):
            The timestamp when the wallet was created.
            Automatically set when the wallet is first inserted into the database.
    """

    __tablename__ = "wallet"

    id = Column(Integer, primary_key=True)
    name = Column(TEXT, nullable=False)
    balance = Column(Numeric(10, 2), nullable=False)
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())


class BankAccount(ORMbase):
    """
    Represents a bank account used for financial transactions and settlements.

    This table stores essential details of a bank account, such as the account holder's name,
    account number, IFSC code, and bank/branch details. It can be associated with operators, company,
    or merchants depending on the use case.

    Notes:
        - Bank accounts must be manually removed when the associated object is removed.
        - Bank accounts cannot be deleted if the debit_transfer refer to this bank account.
        - Data cleaner should handle dangling bank accounts.

    Columns:
        id (Integer):
            Primary key. Unique identifier for the bank account.

        bank_name (TEXT):
            Name of the bank. This field is required.
            Maximum 32 characters in length

        branch_name (TEXT):
            Name of the bank branch. Optional field.
            Maximum 32 characters in length

        account_number (TEXT):
            The actual bank account number. Required.
            Maximum 32 characters in length

        holder_name (TEXT):
            Full name of the account holder. Required.
            Maximum 32 characters in length

        ifsc (TEXT):
            The Indian Financial System Code (IFSC) of the branch.
            Used to uniquely identify a bank branch. Required.
            Maximum 16 characters in length

        account_type (Integer):
            Type of the bank account, stored as an integer enum.
            Refers to the `BankAccountType` enumeration.
            Defaults to `BankAccountType.OTHER`.

        updated_on (DateTime):
            The timestamp of the last balance update or modification.
            This is automatically set to the current time when their is a modification.

        created_on (DateTime):
            The timestamp when the account was created.
            Automatically set when the account is first inserted into the database.
    """

    __tablename__ = "bank_account"

    id = Column(Integer, primary_key=True)
    bank_name = Column(TEXT, nullable=False)
    branch_name = Column(TEXT)
    account_number = Column(TEXT, nullable=False)
    holder_name = Column(TEXT, nullable=False)
    ifsc = Column(TEXT, nullable=False)
    account_type = Column(Integer, nullable=False, default=BankAccountType.OTHER)
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())
