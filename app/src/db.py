from secrets import token_hex
from geoalchemy2 import Geometry
from sqlalchemy import (
    ARRAY,
    TEXT,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Time,
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
    BusStatus,
    TicketingMode,
    TriggeringMode,
    ServiceStatus,
    DutyStatus,
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

        create_company (Boolean):
            Whether this role permits the creation of a new company.

        update_company (Boolean):
            Whether this role permits editing the existing company.

        delete_company (Boolean):
            Whether this role permits deletion of a company.

        create_operator (Boolean):
            Whether this role permits the creation of a new operator.

        update_operator (Boolean):
            Whether this role permits editing the existing operator.

        delete_operator (Boolean):
            Whether this role permits deletion of a operator.

        create_business (Boolean):
            Whether this role permits the creation of a new business.

        update_business (Boolean):
            Whether this role permits editing the existing business.

        delete_business (Boolean):
            Whether this role permits deletion of a business.

        create_route (Boolean):
            Whether this role permits the creation of a new route.

        update_route (Boolean):
            Whether this role permits editing the existing route.

        delete_route (Boolean):
            Whether this role permits deletion of a route.

        create_bus (Boolean):
            Whether this role permits the creation of a new bus.

        update_bus (Boolean):
            Whether this role permits editing the existing bus.

        delete_bus (Boolean):
            Whether this role permits deletion of a bus.

        create_vendor (Boolean):
            Whether this role permits the creation of a new vendor.

        update_vendor (Boolean):
            Whether this role permits editing the existing vendor.

        delete_vendor (Boolean):
            Whether this role permits deletion of a vendor.

        create_schedule (Boolean):
            Grants permission to create schedules.

        update_schedule (Boolean):
            Grants permission to modify schedules.

        delete_schedule (Boolean):
            Grants permission to delete schedules.

        updated_on (DateTime):
            Timestamp automatically updated whenever the role record is modified.

        create_service (Boolean):
            Whether this role permits the creation of a new service.

        update_service (Boolean):
            Whether this role permits editing the existing service.

        delete_service (Boolean):
            Whether this role permits deletion of a service.

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
    # Company management permission
    create_company = Column(Boolean, nullable=False)
    update_company = Column(Boolean, nullable=False)
    delete_company = Column(Boolean, nullable=False)
    # Operator management permission
    create_operator = Column(Boolean, nullable=False)
    update_operator = Column(Boolean, nullable=False)
    delete_operator = Column(Boolean, nullable=False)
    # Business management permission
    create_business = Column(Boolean, nullable=False)
    update_business = Column(Boolean, nullable=False)
    delete_business = Column(Boolean, nullable=False)
    # Route management permission
    create_route = Column(Boolean, nullable=False)
    update_route = Column(Boolean, nullable=False)
    delete_route = Column(Boolean, nullable=False)
    # Bus management permission
    create_bus = Column(Boolean, nullable=False)
    update_bus = Column(Boolean, nullable=False)
    delete_bus = Column(Boolean, nullable=False)
    # Vendor management permission
    create_vendor = Column(Boolean, nullable=False)
    update_vendor = Column(Boolean, nullable=False)
    delete_vendor = Column(Boolean, nullable=False)
    # Schedule management permission
    create_schedule = Column(Boolean, nullable=False)
    update_schedule = Column(Boolean, nullable=False)
    delete_schedule = Column(Boolean, nullable=False)
    # Service management permission
    create_service = Column(Boolean, nullable=False)
    update_service = Column(Boolean, nullable=False)
    delete_service = Column(Boolean, nullable=False)
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
            Maximum 32 characters long.

        status (Integer):
            Enum representing the verification status of the company
            Defaults to `CompanyStatus.UNDER_VERIFICATION`.

        type (Integer):
            Enum representing the type/category of the company.
            Defaults to `CompanyType.OTHER`.

        address (TEXT):
            Physical or mailing address of the company.
            Must not be null.
            Used for communication or locating the company.
            Maximum 512 characters long.

        contact_person (TEXT):
            Name of the primary contact person for the company.
            Must not be null.
            Maximum 32 characters long.

        phone_number (TEXT):
            Phone number associated with the company, must not be null
            Maximum 32 characters long.
            Saved and processed in RFC3966 format (https://datatracker.ietf.org/doc/html/rfc3966).
            Phone number start with a plus sign followed by country code and local number.

        email_id (TEXT):
            Email address for company-related communication.
            Must not be null.
            Maximum 256 characters long
            Enforce the format prescribed by RFC 5322

        location (Geometry):
            Geographical location of the company represented as a `POINT`
            geometry with SRID 4326. Required for location-based features.
            Must not be null.

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
    address = Column(TEXT, nullable=False)
    contact_person = Column(TEXT, nullable=False)
    phone_number = Column(TEXT, nullable=False)
    email_id = Column(TEXT, nullable=False)
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

        manage_token (Boolean):
            Determines whether the role grants permission to manage operator tokens.

        update_company (Boolean):
            Whether this role permits editing the company details.

        create_operator (Boolean):
            Whether this role permits the creation of a new operator.

        update_operator (Boolean):
            Whether this role permits editing the existing operator.

        delete_operator (Boolean):
            Whether this role permits deletion of a operator.

        create_route (Boolean):
            Whether this role permits the creation of a new route.

        update_route (Boolean):
            Whether this role permits editing the existing route.

        delete_route (Boolean):
            Whether this role permits deletion of a route.

        create_bus (Boolean):
            Whether this role permits the creation of a new bus.

        update_bus (Boolean):
            Whether this role permits editing the existing bus.

        delete_bus (Boolean):
            Whether this role permits deletion of a bus.

        create_schedule (Boolean):
            Grants permission to create schedules.

        update_schedule (Boolean):
            Grants permission to modify schedules.

        delete_schedule (Boolean):
            Grants permission to delete schedules.

        create_service (Boolean):
            Whether this role permits the creation of a new service.

        update_service (Boolean):
            Whether this role permits editing the existing service.

        delete_service (Boolean):
            Whether this role permits deletion of a service.

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
    manage_token = Column(Boolean, nullable=False)
    # Company management permission
    update_company = Column(Boolean, nullable=False)
    # Operator management permission
    create_operator = Column(Boolean, nullable=False)
    update_operator = Column(Boolean, nullable=False)
    delete_operator = Column(Boolean, nullable=False)
    # Route management permission
    create_route = Column(Boolean, nullable=False)
    update_route = Column(Boolean, nullable=False)
    delete_route = Column(Boolean, nullable=False)
    # Bus management permission
    create_bus = Column(Boolean, nullable=False)
    update_bus = Column(Boolean, nullable=False)
    delete_bus = Column(Boolean, nullable=False)
    # Schedule management permission
    create_schedule = Column(Boolean, nullable=False)
    update_schedule = Column(Boolean, nullable=False)
    delete_schedule = Column(Boolean, nullable=False)
    # Service management permission
    create_service = Column(Boolean, nullable=False)
    update_service = Column(Boolean, nullable=False)
    delete_service = Column(Boolean, nullable=False)
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
            Global fare have None as company_id.

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
            Must be unique and not null.
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
            Physical or mailing address of the business.
            Must not be null.
            Used for communication or locating the business.
            Maximum 512 characters long.

        contact_person (TEXT):
            Name of the primary contact person for the business.
            Must not be null.
            Maximum 32 characters long.

        phone_number (TEXT):
            Phone number associated with the business, must not be null
            Maximum 32 characters long.
            Saved and processed in RFC3966 format (https://datatracker.ietf.org/doc/html/rfc3966).
            Phone number start with a plus sign followed by country code and local number.

        email_id (TEXT):
            Email address for business-related communication.
            Must not be null.
            Maximum 256 characters long
            Enforce the format prescribed by RFC 5322

        location (Geometry):
            Geographical location of the business represented as a `POINT`
            geometry with SRID 4326. Required for location-based features.
            Must not be null.

        updated_on (DateTime):
            Timestamp automatically updated whenever the business record is modified.
            Useful for tracking updates and synchronization.

        created_on (DateTime):
            Timestamp indicating when the business record was created.
            Automatically set to the current timestamp at insertion.
    """

    __tablename__ = "business"

    id = Column(Integer, primary_key=True)
    name = Column(String(32), nullable=False, unique=True)
    status = Column(Integer, nullable=False, default=BusinessStatus.ACTIVE)
    type = Column(Integer, nullable=False, default=BusinessType.OTHER)
    # Contact details
    address = Column(TEXT, nullable=False)
    contact_person = Column(TEXT, nullable=False)
    phone_number = Column(TEXT, nullable=False)
    email_id = Column(TEXT, nullable=False)
    location = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
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

        update_business (Boolean):
            Whether this role permits editing the business details.

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
    # Business management permission
    update_business = Column(Boolean, nullable=False)
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


class Bus(ORMbase):
    """
    Represents a bus entity that is part of a company's fleet.

    Each bus record stores registration and operational details and is uniquely
    identified by a combination of its registration number and company ID.

    Columns:
        id (Integer):
            Primary key. Unique identifier for the bus.

        company_id (Integer):
            Foreign key referencing the company that owns the bus.
            Must be non-null. Deletion of the company cascades to its buses.
            Indexed for optimized grouping and filtering.

        registration_number (String(16)):
            This should be an immutable value.
            Vehicle registration number.
            Must be unique per company and non-null.
            Indexed for fast lookup.

        name (String(32)):
            Display name or label for the bus.
            Must be non-null.
            Indexed for fast lookup.

        capacity (Integer):
            Seating or passenger capacity of the bus.
            Must be non-null.

        manufactured_on (DateTime):
            Manufacture date of the bus.
            Must be non-null.

        insurance_upto (DateTime):
            Date until which the bus is insured.
            Nullable.

        pollution_upto (DateTime):
            Date until which the pollution certificate is valid.
            Nullable.

        fitness_upto (DateTime):
            Date until which the fitness certificate is valid.
            Nullable.

        road_tax_upto (DateTime):
            Date until which road tax is paid.
            Nullable.

        status (Integer):
            Operational status of the bus (ACTIVE, MAINTENANCE, SUSPENDED).
            Must be non-null.
            Defaults to `BusStatus.ACTIVE`.

        updated_on (DateTime):
            Timestamp automatically updated whenever the record is modified.
            Useful for auditing or syncing purposes.

        created_on (DateTime):
            Timestamp indicating when the bus record was initially created.
            Must be non-null. Defaults to the current time.
    """

    __tablename__ = "bus"
    __table_args__ = (UniqueConstraint("registration_number", "company_id"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(
        Integer,
        ForeignKey("company.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    registration_number = Column(String(16), nullable=False, index=True)
    name = Column(String(32), nullable=False, index=True)
    capacity = Column(Integer, nullable=False)
    manufactured_on = Column(DateTime(timezone=True), nullable=False)
    insurance_upto = Column(DateTime(timezone=True))
    pollution_upto = Column(DateTime(timezone=True))
    fitness_upto = Column(DateTime(timezone=True))
    road_tax_upto = Column(DateTime(timezone=True))
    status = Column(Integer, nullable=False, default=BusStatus.ACTIVE)
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())


class Route(ORMbase):
    """
    Represents a route associated with a company.

    Each route defines a path that begins at a specific landmark and ends at another landmark.
    It is used for transportation or logistics operations.

    Columns:
        id (Integer):
            Primary key. Unique identifier for the route.

        company_id (Integer):
            Foreign key referencing the company that owns or operates the route.
            Must be non-null. Deletion of the company cascades to its routes.

        name (String(4096)):
            Descriptive name or label for the route.
            Must be non-null and unique within the company.
            ex:- Varkala -> Edava -> Kappil -> Paravoor

        start_time (Time):
            The time of day when the route operation starts.
            Must be non-null. Used for scheduling and time-based operations.

        updated_on (DateTime):
            Timestamp automatically updated when the route record is modified.
            Useful for audit logs, syncing, or change tracking.

        created_on (DateTime):
            Timestamp indicating when the route was initially created.
            Must be non-null. Defaults to the current timestamp.
    """

    __tablename__ = "route"
    __table_args__ = (UniqueConstraint("name", "company_id"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(
        Integer, ForeignKey("company.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(4096), nullable=False)
    start_time = Column(Time(timezone=True), nullable=False)
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())


class LandmarkInRoute(ORMbase):
    """
    Represents a landmark positioned within a specific route.

    This table defines the sequence and timing metadata of landmarks along a route.
    It helps determine the structure and scheduling of transportation or logistics operations.

    Columns:
        id (Integer):
            Primary key. Unique identifier for the landmark-in-route entry.

        company_id (Integer):
            Foreign key referencing the company that operates on the route.
            Must be non-null. Deletion of the company cascades to its entries.
            Indexed for optimized lookup.

        route_id (Integer):
            Foreign key referencing the associated route.
            Must be non-null. Deletion of the route cascades to its landmarks.
            Indexed for performance.

        landmark_id (Integer):
            Foreign key referencing the physical landmark.
            Indicates the location this entry refers to.
            Landmarks referenced here cannot be removed.

        distance_from_start (Integer):
            Distance in meters from the starting landmark of the route.
            Must be non-null. Used to determine ordering and physical spacing.
            Must be unique per route.

        arrival_delta (Integer):
            Time in minutes expected to arrive at this landmark from the start of the route.
            Helps in estimating arrival schedules for route traversal.

        departure_delta (Integer):
            Time in minutes expected to depart from this landmark after the route starts.
            Used to define dwell times or stop durations.

        updated_on (DateTime):
            Timestamp automatically updated whenever the record is modified.
            Useful for auditing and syncing operations.

        created_on (DateTime):
            Timestamp indicating when this record was created.
            Must be non-null. Defaults to the current timestamp.
    """

    __tablename__ = "landmark_in_route"
    __table_args__ = (UniqueConstraint("route_id", "distance_from_start"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(
        Integer,
        ForeignKey("company.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    route_id = Column(
        Integer, ForeignKey("route.id", ondelete="CASCADE"), nullable=False, index=True
    )
    landmark_id = Column(Integer, ForeignKey("landmark.id"))
    distance_from_start = Column(Integer, nullable=False)
    arrival_delta = Column(Integer, nullable=False)
    departure_delta = Column(Integer, nullable=False)
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())


class Schedule(ORMbase):
    """
    Represents a scheduled service configuration for a company.

    This table manages the schedule logic including timing, associated route, fare, and bus,
    as well as automatic or manual triggering of the service. It is crucial for recurring
    transport operations, allowing operators to define when and how a specific route runs.

    Columns:
        id (Integer):
            Primary key. Unique identifier for the schedule.

        company_id (Integer):
            Foreign key referencing the company that owns the schedule.
            Must be non-null. Deletion of the company cascades to its schedules.

        name (String(128)):
            Human-readable name of the schedule.
            Must be non-null and unique within a company.
            Indexed for efficient lookup.

        description (TEXT):
            Optional textual description of the schedule.
            Used to provide additional details or annotations.
            Maximum 2048 characters long.

        route_id (Integer):
            Foreign key referencing the associated route.
            If the route is deleted, the field is set to NULL.
            Determines which route this schedule is linked to.

        fare_id (Integer):
            Foreign key referencing the fare configuration.
            Nullable. If deleted, set to NULL.
            Controls pricing and ticket rules.

        bus_id (Integer):
            Foreign key referencing the bus to be assigned to this schedule.
            Nullable. If deleted, set to NULL.

        frequency (ARRAY(Integer)):
            List of days in which the schedule is to be triggered.
            Used to define repeated service patterns on daily intervals.

        ticketing_mode (Integer):
            Ticketing mode of the service created by this schedule.
            Mapped from the `TicketingMode`.
            Defaults to `HYBRID`.

        triggering_mode (Integer):
            Controls how the schedule is activated:
            Mapped from the `TriggeringMode`.
              - `AUTO` (system triggers automatically),
              - `MANUAL` (requires operator intervention).
            Defaults to `AUTO`.

        next_trigger_on (DateTime):
            Timestamp indicating the next scheduled execution time.
            Automatically calculated based on `frequency` and `trigger_mode`.

        last_trigger_on (DateTime):
            Timestamp when the schedule was last triggered.
            Useful for auditing or retry logic.

        updated_on (DateTime):
            Timestamp automatically updated whenever the schedule is modified.

        created_on (DateTime):
            Timestamp when the schedule was created.
            Must be non-null. Defaults to the current time.
    """

    __tablename__ = "schedule"
    __table_args__ = (UniqueConstraint("company_id", "name"),)

    id = Column(Integer, primary_key=True)
    company_id = Column(
        Integer, ForeignKey("company.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(128), nullable=False, index=True)
    description = Column(TEXT)
    # Service related data
    route_id = Column(Integer, ForeignKey("route.id", ondelete="SET NULL"))
    fare_id = Column(Integer, ForeignKey("fare.id", ondelete="SET NULL"))
    bus_id = Column(Integer, ForeignKey("bus.id", ondelete="SET NULL"))
    frequency = Column(ARRAY(Integer))
    ticketing_mode = Column(Integer, nullable=False, default=TicketingMode.HYBRID)
    # Scheduler data
    triggering_mode = Column(Integer, nullable=False, default=TriggeringMode.AUTO)
    next_trigger_on = Column(DateTime(timezone=True))
    last_trigger_on = Column(DateTime(timezone=True))
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())


class BusinessWallet(ORMbase):
    """
    Represents the association between a business entity and its wallet.

    This table links a specific business to a wallet for managing its
    service usage.

    Each business can have only one wallet. The wallet relationship
    supports cascading delete to remove the wallet if the business is deleted.

    Columns:
        id (Integer):
            Primary key. Unique identifier for the business wallet entry.

        wallet_id (Integer):
            Foreign key referencing the `wallet.id`.
            Must not be null.
            Deletion of the business cascades to its business wallet.

        business_id (Integer):
            Foreign key referencing `business.id`.
            Must not be null and must be unique.
            Each business can have only one wallet.

        updated_on (DateTime):
            Timestamp automatically updated whenever the business wallet record is modified.
            Useful for auditing or syncing purposes.

        created_on (DateTime):
            Timestamp indicating when the business wallet record was created.
            Automatically set to the current timestamp at insertion.
    """

    __tablename__ = "business_wallet"

    id = Column(Integer, primary_key=True)
    wallet_id = Column(
        Integer, ForeignKey("wallet.id", ondelete="CASCADE"), nullable=False
    )
    business_id = Column(
        Integer,
        ForeignKey("business.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())


class CompanyWallet(ORMbase):
    """
    Represents the association between a company and its wallet.

    This table links a company to a wallet used for managing
    company-level financial operations and balance tracking.

    Each company can have only one wallet. The relationship supports
    cascading delete to maintain referential integrity.

    Columns:
        id (Integer):
            Primary key. Unique identifier for the company wallet entry.

        wallet_id (Integer):
            Foreign key referencing the `wallet.id`.
            Must not be null.
            Deletion of the company cascades to its company wallet.

        company_id (Integer):
            Foreign key referencing `company.id`.
            Must not be null and must be unique.
            Each company can have only one wallet.

        updated_on (DateTime):
            Timestamp automatically updated whenever the company wallet record is modified.
            Useful for auditing or syncing purposes.

        created_on (DateTime):
            Timestamp indicating when the company wallet record was created.
            Automatically set to the current timestamp at insertion.
    """

    __tablename__ = "company_wallet"

    id = Column(Integer, primary_key=True)
    wallet_id = Column(
        Integer, ForeignKey("wallet.id", ondelete="CASCADE"), nullable=False
    )
    company_id = Column(
        Integer,
        ForeignKey("company.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())


class Service(ORMbase):
    """
    Represents a transport service operated by a company.

    This table stores details about individual service instances,
    including their assigned route, fare, bus, and operational timeframes.
    It also maintains cryptographic keys for secure ticketing
    and records various states and modes related to the service.

    Columns:
        id (Integer):
            Primary key. Unique identifier for the service.

        company_id (Integer):
            Foreign key referencing `company.id`.
            Indicates the company that owns this service.
            Indexed for faster queries.

        name (String):
            Name of the service.
            Must not be null.
            Maximum 128 characters.

        route (JSONB):
            JSON object storing the route data associated with the service.
            Route once set cannot be changed.
            Must not be null.

        fare (JSONB):
            JSON object storing the fare data associated with the service.
            Fare once set cannot be changed.
            Must not be null.

        bus_id (Integer):
            Foreign key referencing `bus.id`.
            Specifies the bus assigned to this service.

        ticket_mode (Integer):
            Enum representing the ticketing mode.
            Defaults to `TicketingMode.HYBRID`.
            Mapped from the `TicketingMode` enum.

        status (Integer):
            Enum representing the current status of the service.
            Defaults to `ServiceStatus.CREATED`.
            A service cannot be created before 24 hours from the `starting_at` time.
            Mapped from the `ServiceStatus` enum.

        starting_at (DateTime):
            Timestamp indicating the actual start time
            when the service begins operation,  based on route information.

        ending_at (DateTime):
            Timestamp indicating the actual ending time
            when the service finishes operation, based on route information.

        private_key (TEXT):
            Private cryptographic key for the service.
            Used for secure ticket generation and validation.
            Must not be null.

        public_key (TEXT):
            Public cryptographic key corresponding to the private key.
            Shared for ticket verification.
            Must not be null.

        remark (TEXT):
            Optional text field for additional remarks or notes related to the service.
            Maximum 1024 characters.

        started_on (DateTime):
            Time at which the first operator joined the duty.

        finished_on (DateTime):
            Time at which the Service is ended by the operator or when the statement is generated.

        updated_on (DateTime):
            Timestamp automatically updated whenever the company wallet record is modified.
            Useful for auditing or syncing purposes.

        created_on (DateTime):
            Timestamp indicating when the service record was created.
            Automatically set to the current timestamp at insertion.
    """

    __tablename__ = "service"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("company.id"), index=True)
    name = Column(String(128), nullable=False)
    route = Column(JSONB, nullable=False)
    fare = Column(JSONB, nullable=False)
    bus_id = Column(Integer, ForeignKey("bus.id"))
    ticket_mode = Column(Integer, nullable=False, default=TicketingMode.HYBRID)
    status = Column(Integer, nullable=False, default=ServiceStatus.CREATED)
    starting_at = Column(DateTime(timezone=True), nullable=False)
    ending_at = Column(DateTime(timezone=True), nullable=False)
    private_key = Column(TEXT, nullable=False)
    public_key = Column(TEXT, nullable=False)
    remark = Column(TEXT)
    started_on = Column(DateTime(timezone=True))
    finished_on = Column(DateTime(timezone=True))
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())


class LandmarkInService(ORMbase):
    """
    Temporal representation of all landmarks in a service based on the time.

    This table tracks the relationship between landmarks and services,
    including the expected arrival and departure times at each landmark
    during the course of a service.

    Columns:
        landmark_id (Integer):
            Foreign key referencing `landmark.id`.
            Identifies the specific landmark associated with the service.

        service_id (Integer):
            Foreign key referencing `service.id`.
            Identifies the transport service to which the landmark belongs.

        arrival_time (DateTime):
            Timestamp indicating the expected arrival time at the landmark.
            Must not be null.

        departure_time (DateTime):
            Timestamp indicating the expected departure time from the landmark.
            Must not be null.
    """

    __tablename__ = "landmark_in_service"

    id = Column(Integer, primary_key=True)
    landmark_id = Column(Integer, ForeignKey("landmark.id"))
    service_id = Column(Integer, ForeignKey("service.id"))
    arrival_time = Column(DateTime(timezone=True), nullable=False)
    departure_time = Column(DateTime(timezone=True), nullable=False)


class Duty(ORMbase):
    """
    Represents a duty assignment where an operator is assigned to a service under a specific company.

    This table tracks operator responsibilities and service execution over time, capturing key
    lifecycle events like assignment, start, and completion. It is essential for scheduling,
    monitoring, and auditing operator activities.

    Columns:
        id (Integer):
            Primary key. Unique identifier for the duty record.

        company_id (Integer):
            Foreign key referencing the `company.id`.
            Indicates the company under which this duty is assigned.
            Required and cascades on delete.

        operator_id (Integer):
            Foreign key referencing the `operator.id`.
            Identifies the operator assigned to this duty.
            Required and cascades on delete.

        service_id (Integer):
            Foreign key referencing the `service.id`.
            Indicates the service the operator is assigned to perform.
            Required and cascades on delete.

        status (Integer):
            Enum representing the current status of the duty.
            Required. Defaults to `DutyStatus.ASSIGNED`.

        starting_at (DateTime):
            Scheduled start time of the duty.
            Required and timezone-aware.

        started_on (DateTime):
            Actual timestamp when the duty started.
            Optional and timezone-aware. Set when the operator begins the duty after the buffer time.

        finished_on (DateTime):
            Timestamp marking when the duty was completed.
            Optional and timezone-aware.

        updated_on (DateTime):
            Timestamp automatically updated whenever the duty record is modified.
            Useful for change tracking and auditing.

        created_on (DateTime):
            Timestamp indicating when the duty was created.
            Automatically set to the current timestamp at insertion.
    """

    __tablename__ = "duty"

    id = Column(Integer, primary_key=True)
    company_id = Column(
        Integer,
        ForeignKey("company.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operator_id = Column(
        Integer, ForeignKey("operator.id", ondelete="CASCADE"), nullable=False
    )
    service_id = Column(
        Integer, ForeignKey("service.id", ondelete="CASCADE"), nullable=False
    )
    status = Column(Integer, nullable=False, default=DutyStatus.ASSIGNED)
    starting_at = Column(DateTime(timezone=True), nullable=False)
    started_on = Column(DateTime(timezone=True))
    finished_on = Column(DateTime(timezone=True))
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())
