from secrets import token_hex
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

from app.src.constants import PSQL_DB_DRIVER, PSQL_DB_HOST, PSQL_DB_PASSWORD
from app.src.constants import PSQL_DB_NAME, PSQL_DB_PORT, PSQL_DB_USERNAME
from app.src.enums import (
    AccountStatus,
    GenderType,
    PlatformType,
    CompanyStatus,
    CompanyType,
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
            Token expiration time in minutes.
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
    Represents an access token issued to an operator for authentication and session management.

    This table tracks active sessions and access tokens for operators, linking them to their
    respective company and device information. It is essential for enforcing secure access
    and managing token expiration within the system.

    Columns:
        id (Integer):
            Primary key. Unique identifier for this token record.

        operator_id (Integer):
            Foreign key referencing `operator.id`.
            Identifies the operator to whom the token belongs.
            Cascades on delete — if the operator is removed, related tokens are deleted.

        company_id (Integer):
            Foreign key referencing `company.id`.
            Associates the token with the operator's company.
            Cascades on delete — if the company is removed, related tokens are deleted.

        access_token (String):
            Unique string used for authenticating the operator's requests.
            Automatically generated as a 64-character hexadecimal string.

        platform_type (TEXT):
            Optional. Describes the platform or device type (e.g., Android, iOS, Web)
            from which the operator accessed the system.

        client_version (TEXT):
            Optional. Version of the client application used during authentication.
            Useful for debugging or enforcing version control.

        created_on (DateTime):
            Timestamp indicating when the token was created.
            Defaults to the current timestamp at insertion.

        expires_in (DateTime):
            Timestamp indicating when the token will expire.
            Required to enforce session timeout and token validity.
    """

    __tablename__ = "operator_token"

    id = Column(Integer, primary_key=True)
    operator_id = Column(
        Integer, ForeignKey("operator.id", ondelete="CASCADE"), nullable=False
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
    Represents the mapping between operators and their assigned roles,
    enabling a many-to-many relationship between `operator` and `operator_role`.

    This table allows an operator to be assigned multiple roles and a role
    to be assigned to multiple operators. Useful for implementing a flexible
    Role-Based Access Control (RBAC) system.

    Columns:
        id (Integer):
            Primary key. Unique identifier for this role mapping record.

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
            Useful for auditing or synchronization.

        created_on (DateTime):
            Timestamp indicating when this mapping was created.
            Defaults to the current timestamp at insertion.
    """

    __tablename__ = "operator_role_map"

    id = Column(Integer, primary_key=True)
    role_id = Column(
        Integer, ForeignKey("operator_role.id", ondelete="CASCADE"), nullable=False
    )
    operator_id = Column(
        Integer, ForeignKey("operator.id", ondelete="CASCADE"), nullable=False
    )
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())
