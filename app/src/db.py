from secrets import token_hex
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
    UniqueConstraint,
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
    BusinessStatus,
    BusinessType,
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
            Must be non-null.
            Maximum 32 characters long
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
            Optional physical or mailing address of the business.
            Used for communication, billing, or geolocation purposes.

        contact_person (TEXT):
            Optional name of a primary contact person at the business.

        phone_number (TEXT):
            Contact number for the business, must be non-null and unique.
            Maximum 32 characters long
            Saved and processed in RFC3966 format (https://datatracker.ietf.org/doc/html/rfc3966).
            Phone number start with a plus sign followed by country code and local number.

        email_id (TEXT):
            Email address for the business, must be non-null and unique.
            Maximum length is 256 characters.
            Enforce the format prescribed by RFC 5322 (https://en.wikipedia.org/wiki/Email_address).

        website (TEXT):
            Optional URL to the business's website or landing page.
            Should be a valid HTTP(S) address if provided.

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
    contact_person = Column(TEXT)
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
            Foreign key referencing the associated business entity.
            Links the vendor to a parent business account.
            Must be non-null. Cascading deletion is applied when the business is deleted.

        username (String(32)):
            Unique username used for login or identification within the business entity.
            Ideally, the username shouldn't be changed once set.
            Must start with an alphabet (uppercase or lowercase).
            Can include uppercase and lowercase letters, digits (0 to 9),
            and symbols like hyphen (-), period (.), at symbol (@), and underscore (_).
            Must be 4-32 characters long.
            Must be non-null, and unique against business.

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
        Integer, ForeignKey("business.id", ondelete="CASCADE"), nullable=False
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
            Foreign key referencing `business.id`.
            Identifies the business associated with the vendor.
            Enforces cascading delete — if the business is deleted, related vendor tokens are also removed.

        vendor_id (Integer):
            Foreign key referencing `vendor.id`.
            Identifies the vendor who owns this token.
            Cascades on delete — if the vendor is removed, associated tokens are deleted.

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
            Timestamp automatically updated when the token record is modified.
            Useful for tracking recent activity or token refresh events.

        created_on (DateTime):
            Timestamp indicating when the token was initially created.
            Automatically set to the current time at insertion."""

    __tablename__ = "vendor_token"

    id = Column(Integer, primary_key=True)
    business_id = Column(
        Integer, ForeignKey("business.id", ondelete="CASCADE"), nullable=False
    )
    vendor_id = Column(
        Integer, ForeignKey("vendor.id", ondelete="CASCADE"), nullable=False
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
            Must be unique within the business and non-null.

        business_id (Integer):
            Foreign key referencing `business.id`.
            Identifies the business this role belongs to.
            Enforces cascading delete — if the business is deleted, the role is also removed.

        manage_token (Boolean):
            Indicates whether the role permits listing and deletion of vendor tokens.

        create_vendor (Boolean):
            Whether this role allows creation of new vendor accounts.

        update_vendor (Boolean):
            Whether this role allows editing or deactivation existing vendor accounts.

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

    id = Column(Integer, primary_key=True)
    name = Column(String(32), nullable=False, unique=True)
    business_id = Column(
        Integer,
        ForeignKey("business.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Vendor token management permission
    manage_token = Column(Boolean, nullable=False, default=False)
    # Vendor management permission
    create_vendor = Column(Boolean, nullable=False, default=False)
    update_vendor = Column(Boolean, nullable=False, default=False)
    delete_vendor = Column(Boolean, nullable=False, default=False)
    # Vendor role management permission
    create_role = Column(Boolean, nullable=False, default=False)
    update_role = Column(Boolean, nullable=False, default=False)
    delete_role = Column(Boolean, nullable=False, default=False)
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())


class VendorRoleMap(ORMbase):
    """
    Represents the mapping between vendors and their assigned roles,
    enabling a many-to-one relationship between `vendor` and `vendor_role`.

    Each vendor is associated with exactly one role, while a role can be assigned
    to multiple vendors. This mapping supports Role-Based Access Control (RBAC)
    for vendors within a specific business context.

    Columns:
        id (Integer):
            Primary key. Unique identifier for this role mapping record.

        business_id (Integer):
            Foreign key referencing `business.id`.
            Identifies the business under which the vendor-role mapping exists.
            Cascades on delete — if the business is deleted, related mappings are also deleted.

        role_id (Integer):
            Foreign key referencing `vendor_role.id`.
            Specifies the role assigned to the vendor.
            Cascades on delete — if the role is removed, related mappings are deleted.

        vendor_id (Integer):
            Foreign key referencing `vendor.id`.
            Identifies the vendor receiving the role.
            Each vendor can have only one role mapping.
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
        Integer, ForeignKey("vendor_role.id", ondelete="CASCADE"), nullable=False
    )
    vendor_id = Column(
        Integer,
        ForeignKey("vendor.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # Metadata
    updated_on = Column(DateTime(timezone=True), onupdate=func.now())
    created_on = Column(DateTime(timezone=True), nullable=False, default=func.now())
