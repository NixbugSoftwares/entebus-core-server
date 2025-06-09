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
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import JSONB

from app.src.constants import PSQL_DB_DRIVER, PSQL_DB_HOST, PSQL_DB_PASSWORD
from app.src.constants import PSQL_DB_NAME, PSQL_DB_PORT, PSQL_DB_USERNAME
from app.src.enums import (
    AccountStatus,
    GenderType,
    LandmarkType,
    PlatformType,
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

        username (String):
            The operator's login username.
            Must be unique within the same company.

        password (TEXT):
            Hashed password used for authentication.
            Stored securely; should never be stored in plain text.

        gender (Integer):
            Enum representing the operator’s gender.
            Defaults to `GenderType.OTHER`.

        full_name (TEXT):
            The full name of the operator (optional).

        status (Integer):
            Enum representing the account's current status.
            Defaults to `AccountStatus.ACTIVE`.

        phone_number (TEXT):
            Optional contact phone number for the operator.

        email_id (TEXT):
            Optional contact email address for the operator.

        created_on (DateTime):
            Timestamp of when the operator account was created.
            Automatically set to the current time during insertion.

    Constraints:
        UniqueConstraint (username, company_id):
            Ensures that usernames are unique within each company.
            The same username may exist in different companies.
    """

    __tablename__ = "operator"
    __table_args__ = (UniqueConstraint("username", "company_id"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(
        Integer, ForeignKey("company.id", ondelete="CASCADE"), nullable=False
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

        client_version (TEXT):
            Optional field for storing the version of the client application.
            Helps in enforcing version constraints and debugging issues related to client behavior.

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
    client_version = Column(TEXT)
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

        name (String):
            Name of the role. Must be unique across the system.

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

    id = Column(Integer, primary_key=True)
    name = Column(String(32), nullable=False, unique=True)
    company_id = Column(
        Integer, ForeignKey("company.id", ondelete="CASCADE"), nullable=False
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
    Represents a fare configuration used for pricing, rules, or fare computation logic.
    Fares are defined per company and versioned for consistency. Each fare may contain
    custom attributes and a logic function, and is scoped as either global or local.

    Columns:
        id (Integer):
            Primary key. Unique identifier for the fare record.

        company_id (Integer):
            Foreign key referencing `company.id`. Indicates the company this fare belongs to.
            On company deletion, associated fares are also deleted (CASCADE).

        version (Integer):
            Integer version number used for versioning fare definitions.
            Helps manage and track updates to fare logic or structure.

        name (String(32)):
            Name of the fare, used for display and identification.
            Must be unique per company (enforced with a unique constraint on name + company_id).

        attributes (JSONB):
            JSON-formatted attributes for flexible storage of fare-related parameters.
            Schema-free design allows dynamic addition of custom fields without migrations.

        function (TEXT):
            Text field for storing fare calculation logic.
            Used in runtime fare processing or pricing evaluation.

        scope (Integer):
            Enum value defined by `FareScope`, indicating the scope of the fare:
                - `FareScope.globalScope` (1): Fare applies globally across contexts.
                - `FareScope.localScope` (2): Fare is context-specific.
            Defaults to `FareScope.globalScope`.

        starts_at (DateTime):
            Optional start time for fare validity.
            Defines when the fare becomes active.

        expires_on (DateTime):
            Optional end time for fare validity.
            Defines when the fare becomes inactive or expired.

        updated_on (DateTime):
            Timestamp automatically updated whenever the fare record is modified.
            Useful for tracking changes and syncing.

        created_on (DateTime):
            Timestamp set when the fare record is first created.
            Defaults to the current time on insertion.
    """

    __tablename__ = "fare"
    __table_args__ = (UniqueConstraint("name", "company_id"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("company.id", ondelete="CASCADE"))
    version = Column(Integer, nullable=False)
    name = Column(String(32), nullable=False, index=True)
    attributes = Column(JSONB, nullable=False)
    function = Column(TEXT, nullable=False)
    scope = Column(Integer, nullable=False, default=FareScope.GLOBAL)
    starts_at = Column(DateTime(timezone=True))
    expires_on = Column(DateTime(timezone=True))
    # Metadata
    updated_on = Column(DateTime(timezone=True), nullable=False, default=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())
