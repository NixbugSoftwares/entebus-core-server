"""
Validation and permission checks for EnteBus API.

This module centralizes guard logic such as:
- Token validation
- Role-based permission checks
- Geometry validation (WKT, SRID, AABB)
- State transition enforcement
- Fare function verification

All functions raise appropriate exceptions from `app.src.exceptions`
when validation fails, ensuring consistent error handling.
"""

import random, string
from datetime import datetime, timezone
from sqlalchemy.orm.session import Session
from sqlalchemy import Column
from shapely.geometry.base import BaseGeometry
from typing import Type, Any

from app.src.db import (
    ExecutiveRole,
    ExecutiveToken,
    OperatorRole,
    OperatorToken,
    VendorRole,
    VendorToken,
    LandmarkInRoute,
)
from app.src.constants import MIN_LANDMARK_IN_ROUTE, DYNAMIC_FARE_VERSION
from app.src import exceptions
from app.src.dynamic_fare.v1 import DynamicFare


from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.src.db import ExecutiveToken
from app.src import exceptions
from app.src.functions import isAABB, isSRID4326, isValidTransition, toWKTgeometry


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------
def _validate_token(model_cls, access_token: str, session: Session):
    """
    Generic token validator for any token model.

    Args:
        model_cls: The SQLAlchemy model class (e.g., ExecutiveToken).
        access_token (str): The bearer token string provided by the client.
        session (Session): Active SQLAlchemy session for DB lookup.

    Returns:
        model_cls: The valid token object from the database.

    Raises:
        exceptions.InvalidToken: If the token is not found or has expired.
    """
    current_time = datetime.now(timezone.utc)

    token = (
        session.query(model_cls)
        .filter(
            model_cls.access_token == access_token,
            model_cls.expires_at > current_time,
        )
        .first()
    )

    if token is None:
        raise exceptions.InvalidToken()

    return token


def executiveToken(access_token: str, session: Session) -> ExecutiveToken:
    """Validate an executive access token."""
    return _validate_token(ExecutiveToken, access_token, session)


def vendorToken(access_token: str, session: Session) -> VendorToken:
    """Validate a vendor access token."""
    return _validate_token(VendorToken, access_token, session)


def operatorToken(access_token: str, session: Session) -> OperatorToken:
    """Validate an operator access token."""
    return _validate_token(OperatorToken, access_token, session)


# ---------------------------------------------------------------------------
# Permission checks
# ---------------------------------------------------------------------------
def _validate_permission(role, permission: Column) -> bool:
    """
    Generic permission validator.

    Args:
        role: Role object (e.g., ExecutiveRole, VendorRole, OperatorRole).
        permission (Column): SQLAlchemy Column representing the permission flag.

    Returns:
        bool: True if the role has the permission.

    Raises:
        exceptions.NoPermission: If the role does not have the required permission.
    """
    if role and getattr(role, permission.name, False):
        return True
    raise exceptions.NoPermission()


def executivePermission(role: ExecutiveRole, permission: Column) -> bool:
    """Validate that an executive has the required permission."""
    return _validate_permission(role, permission)


def vendorPermission(role: VendorRole, permission: Column) -> bool:
    """Validate that a vendor has the required permission."""
    return _validate_permission(role, permission)


def operatorPermission(role: OperatorRole, permission: Column) -> bool:
    """Validate that an operator has the required permission."""
    return _validate_permission(role, permission)


# ---------------------------------------------------------------------------
# Geometry validation
# ---------------------------------------------------------------------------
def WKTstring(wktString: str, expected_type: Type[BaseGeometry]) -> BaseGeometry:
    """
    Validate and parse a WKT string into a Shapely geometry of the expected type.

    Args:
        wktString (str): The WKT representation of the geometry.
        expected_type (Type[BaseGeometry]): The expected Shapely geometry type
            (e.g., `Point`, `Polygon`, `LineString`).

    Returns:
        BaseGeometry: Parsed Shapely geometry object.

    Raises:
        exceptions.InvalidWKTStringOrType: If parsing fails or type mismatches.
    """
    wktGeometry = toWKTgeometry(wktString, expected_type)
    if wktGeometry is None:
        raise exceptions.InvalidWKTStringOrType()
    return wktGeometry


def SRID4326(wktGeometry: BaseGeometry) -> bool:
    """
    Validate that the given geometry uses SRID 4326 (WGS84 lat/long bounds).

    Args:
        wktGeometry (BaseGeometry): Geometry to validate.

    Returns:
        bool: True if geometry is within valid SRID 4326 coordinate ranges.

    Raises:
        exceptions.InvalidSRID4326: If geometry has invalid latitude/longitude.
    """
    if not isSRID4326(wktGeometry):
        raise exceptions.InvalidSRID4326()
    return True


def AABB(wktGeometry: BaseGeometry) -> bool:
    """
    Validate that the geometry is an Axis-Aligned Bounding Box (AABB).

    Returns:
        bool: True if valid AABB.

    Raises:
        exceptions.InvalidAABB: If geometry is not a valid AABB.
    """
    if not isAABB(wktGeometry):
        raise exceptions.InvalidAABB()
    return True


# ---------------------------------------------------------------------------
# Other validations
# ---------------------------------------------------------------------------
def stateTransition(
    transitions: dict[Any, list[Any]], old_state: Any, new_state: Any, state: Column
) -> bool:
    """
    Validate whether a state transition is allowed.

    Args:
        transitions (dict[Any, list[Any]]): Mapping of valid transitions.
        old_state (Any): Current state value.
        new_state (Any): Desired new state value.
        state (Column): SQLAlchemy column representing the state
            (used to format error messages).

    Returns:
        bool: True if the transition is valid.

    Raises:
        exceptions.InvalidStateTransition: If the transition is not permitted.
    """
    if not isValidTransition(transitions, old_state, new_state):
        raise exceptions.InvalidStateTransition(state.name)
    return True


def landmarkInRoute(route_id: int, session: Session) -> bool:
    """
    Validate that a route has a correct sequence of landmarks.

    Conditions:
        - Must contain at least MIN_LANDMARK_IN_ROUTE landmarks.
        - The first landmark must start at distance 0.
        - The first landmark cannot have arrival/departure deltas set.
        - The last landmark must have matching arrival and departure deltas.
        - Arrival deltas must be non-decreasing and unique.
        - Departure deltas must be unique.

    Args:
        route_id (int): The route ID to validate.
        session (Session): Active SQLAlchemy session.

    Returns:
        bool: True if the route passes validation, False otherwise.
    """
    landmarks = (
        session.query(LandmarkInRoute)
        .filter(LandmarkInRoute.route_id == route_id)
        .order_by(LandmarkInRoute.distance_from_start.asc())
        .all()
    )

    # Minimum landmarks & must start at 0
    if len(landmarks) < MIN_LANDMARK_IN_ROUTE or landmarks[0].distance_from_start != 0:
        return False

    # First landmark must not have deltas
    # The last landmark must have matching arrival and departure deltas.
    if (
        landmarks[0].arrival_delta
        or landmarks[0].departure_delta
        or landmarks[-1].arrival_delta != landmarks[-1].departure_delta
    ):
        return False

    seenArrivals, seenDepartures = set(), set()

    for i in range(1, len(landmarks)):
        # Arrival must not be earlier than previous departure
        if landmarks[i].arrival_delta < landmarks[i - 1].departure_delta:
            return False

        # Arrival and departure deltas must be unique
        if landmarks[i].arrival_delta in seenArrivals:
            return False
        if landmarks[i].departure_delta in seenDepartures:
            return False

        seenArrivals.add(landmarks[i].arrival_delta)
        seenDepartures.add(landmarks[i].departure_delta)

    return True


def fareFunction(function: str, attributes: dict) -> DynamicFare:
    """
    Validate and build a dynamic fare function against system rules.

    Validation rules:
        - The fare function must use the current dynamic fare version.
        - It must return valid (>= 0) fares for all known ticket types.
        - It must return -1.0 when evaluated with an unknown ticket type.

    Args:
        function (str): String expression of the fare function.
        attributes (dict): Fare configuration, expected keys:
            - "df_version" (int): Dynamic fare version.
            - "ticket_types" (list[dict]): List of ticket types with "name" fields.

    Returns:
        DynamicFare: A validated `DynamicFare` object that can be used
        to compute fares at runtime.

    Raises:
        exceptions.InvalidFareVersion: If the dynamic fare version is unsupported.
        exceptions.UnknownTicketType: If a known ticket type produces invalid fares.
        exceptions.InvalidFareFunction: If unknown ticket types are not rejected.
    """
    if attributes["df_version"] != DYNAMIC_FARE_VERSION:
        raise exceptions.InvalidFareVersion()

    fareFunction = DynamicFare(function)

    for ticket_type in attributes["ticket_types"]:
        name = ticket_type["name"]
        if fareFunction.evaluate(name, 0) < 0 or fareFunction.evaluate(name, 1) < 0:
            raise exceptions.UnknownTicketType(name)

    # Random ticket type should always return -1.0
    bogus_type = "".join(random.choices(string.ascii_letters, k=32))
    if fareFunction.evaluate(bogus_type, 0) != -1.0:
        raise exceptions.InvalidFareFunction()

    return fareFunction
