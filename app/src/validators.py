import random, string
from datetime import datetime, timezone
from sqlalchemy.orm.session import Session
from sqlalchemy import Column
from shapely import Polygon, wkt
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from app.src.db import (
    ExecutiveRole,
    ExecutiveToken,
    OperatorRole,
    OperatorToken,
    VendorRole,
    VendorToken,
    LandmarkInRoute,
)
from app.src.constants import MIN_LANDMARK_IN_ROUTE
from app.src import exceptions
from app.src.dynamic_fare import v1


# Validate token (raise exceptions.InvalidToken())
def executiveToken(access_token: str, session: Session) -> ExecutiveToken:
    current_time = datetime.now(timezone.utc)
    token = (
        session.query(ExecutiveToken)
        .filter(
            ExecutiveToken.access_token == access_token,
            ExecutiveToken.expires_at > current_time,
        )
        .first()
    )
    if token is None:
        raise exceptions.InvalidToken()
    return token


def vendorToken(access_token: str, session: Session) -> VendorToken:
    current_time = datetime.now(timezone.utc)
    token = (
        session.query(VendorToken)
        .filter(
            VendorToken.access_token == access_token,
            VendorToken.expires_at > current_time,
        )
        .first()
    )
    if token is None:
        raise exceptions.InvalidToken()
    return token


def operatorToken(access_token: str, session: Session) -> OperatorToken:
    current_time = datetime.now(timezone.utc)
    token = (
        session.query(OperatorToken)
        .filter(
            OperatorToken.access_token == access_token,
            OperatorToken.expires_at > current_time,
        )
        .first()
    )
    if token is None:
        raise exceptions.InvalidToken()
    return token


# Validate permission (raise exceptions.NoPermission())
def executivePermission(role: ExecutiveRole, permission: Column) -> bool:
    if role and getattr(role, permission.name, False):
        return True
    else:
        raise exceptions.NoPermission()


def vendorPermission(role: VendorRole, permission: Column) -> bool:
    if role and getattr(role, permission.name, False):
        return True
    else:
        raise exceptions.NoPermission()


def operatorPermission(role: OperatorRole, permission: Column) -> bool:
    if role and getattr(role, permission.name, False):
        return True
    else:
        raise exceptions.NoPermission()


# Functions to validate WKT string (raise exceptions.InvalidWKTStringOrType())
def WKTstring(wktString: str, type) -> BaseGeometry:
    try:
        wktGeometry = wkt.loads(wktString)
        if not isinstance(wktGeometry, type):
            raise exceptions.InvalidWKTStringOrType()
        return wktGeometry
    except Exception as e:
        raise exceptions.InvalidWKTStringOrType()


# Function to validate SRID 4326 (raise exceptions.InvalidSRID4326())
def SRID4326(wktGeometry: BaseGeometry) -> bool:
    if isinstance(wktGeometry, Point):
        coords = [(wktGeometry.x, wktGeometry.y)]
    else:
        coords = wktGeometry.exterior.coords
    for longitude, latitude in coords:
        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            raise exceptions.InvalidSRID4326()
    return True


# Function to validate AABB (raise exceptions.InvalidAABB())
def AABB(wktGeometry: BaseGeometry) -> bool:
    if not isinstance(wktGeometry, Polygon):
        raise exceptions.InvalidAABB()

    coords = list(wktGeometry.exterior.coords)
    if len(coords) != 5:
        raise exceptions.InvalidAABB()
    # Remove the duplicate last point
    coords = coords[:-1]
    # Check all sides are either horizontal or vertical
    for i in range(4):
        x1, y1 = coords[i]
        x2, y2 = coords[(i + 1) % 4]
        if not (x1 == x2 or y1 == y2):
            raise exceptions.InvalidAABB()
    return True


# FUnction to check valid status transitions
def stateTransition(transitions: dict, old_state, new_state, state: Column) -> bool:
    if new_state in transitions.get(old_state, []):
        return True
    else:
        raise exceptions.InvalidStateTransition(state.name)


def landmarkInRoute(route: int, session: Session) -> bool:
    landmarkInRoute = (
        session.query(LandmarkInRoute)
        .filter(LandmarkInRoute.route_id == route)
        .order_by(LandmarkInRoute.distance_from_start.asc())
        .all()
    )
    if (
        len(landmarkInRoute) < MIN_LANDMARK_IN_ROUTE
        or landmarkInRoute[0].distance_from_start != 0
    ):
        return False
    if (
        landmarkInRoute[0].arrival_delta
        or landmarkInRoute[0].departure_delta
        or landmarkInRoute[-1].arrival_delta != landmarkInRoute[-1].departure_delta
    ):
        return False

    for i in range(1, len(landmarkInRoute)):
        if landmarkInRoute[i].arrival_delta < landmarkInRoute[i - 1].departure_delta:
            return False

    return True


def fareFunction(function, attributes) -> str:
    fareFunction = v1.DynamicFare(function)

    ticketTypes = attributes["ticket_types"]
    ticketTypeNames = []
    for ticketType in ticketTypes:
        ticketTypeName = ticketType["name"]
        totalFareFor0m = fareFunction.evaluate(ticketTypeName, 0)
        totalFareFor1m = fareFunction.evaluate(ticketTypeName, 1)
        if totalFareFor0m < 0 or totalFareFor1m < 0:
            raise exceptions.UnknownTicketType(ticketTypeName)
        ticketTypeNames.append(ticketTypeName)

    newTicketTypeName = "".join(random.choices(string.ascii_letters, k=32))
    totalFareFor0m = fareFunction.evaluate(newTicketTypeName, 0)
    if totalFareFor0m != -1.0:
        raise exceptions.InvalidFareFunction()
