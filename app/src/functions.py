from typing import Any, List
from fastapi import Request
from sqlalchemy.orm.session import Session
from sqlalchemy import Column
from datetime import timezone, datetime
from sqlalchemy.orm.session import Session
from sqlalchemy import Column
from datetime import timezone, datetime
from shapely import Polygon, wkt
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from typing import Optional

from app.src import openobserve, schemas
from app.src.db import (
    ExecutiveToken,
    ExecutiveRole,
    ExecutiveRoleMap,
)


def getRequestInfo(request: Request):
    return {"method": request.method, "path": request.url.path}


def logExecutiveEvent(token: ExecutiveToken, request: dict, data: dict):
    logDetails = {
        "_method": request["method"],
        "_path": request["path"],
        "_executive_id": token.executive_id,
        "_app": "Executive",
    }
    logDetails.update(data)
    openobserve.logEvent(logDetails)


def makeExceptionResponses(exceptions: List[Any]):
    responses = {}

    for exception in exceptions:
        status_code = exception.status_code
        example_key = exception.__name__
        example_value = {
            "summary": str(exception.headers),
            "value": {"detail": exception.detail},
        }

        if status_code not in responses:
            responses[status_code] = {
                "model": schemas.ErrorResponse,
                "content": {
                    "application/json": {"examples": {example_key: example_value}}
                },
            }
        else:
            responses[status_code]["content"]["application/json"]["examples"][
                example_key
            ] = example_value
    return responses


def enumStr(enumClass):
    return ", ".join(f"{x.name}: {x.value}" for x in enumClass)


def getExecutiveToken(access_token: str, session: Session) -> ExecutiveToken | None:
    current_time = datetime.now(timezone.utc)
    return (
        session.query(ExecutiveToken)
        .filter(
            ExecutiveToken.access_token == access_token,
            ExecutiveToken.expires_at > current_time,
        )
        .first()
    )


def getExecutiveRole(token: ExecutiveToken, session: Session) -> ExecutiveRole | None:
    return (
        session.query(ExecutiveRole)
        .join(ExecutiveRoleMap, ExecutiveRole.id == ExecutiveRoleMap.role_id)
        .filter(ExecutiveRoleMap.executive_id == token.executive_id)
        .first()
    )


def checkExecutivePermission(role: ExecutiveRole, permission: Column) -> bool:
    if role and getattr(role, permission.name, False):
        return True
    else:
        return False


def toWKTgeometry(wktString: str, type) -> Optional[BaseGeometry]:
    try:
        geom = wkt.loads(wktString)
        if not isinstance(geom, type):
            return None
        return geom
    except Exception as e:
        return None


def isSRID4326(wktGeom: BaseGeometry) -> bool:
    if isinstance(wktGeom, Point):
        coords = [(wktGeom.x, wktGeom.y)]
    else:
        coords = wktGeom.exterior.coords
    for longitude, latitude in coords:
        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            return False
    return True


def isAABB(wktGeom: BaseGeometry) -> bool:
    if not isinstance(wktGeom, Polygon):
        return False

    coords = list(wktGeom.exterior.coords)
    if len(coords) != 5:
        return False
    # Remove the duplicate last point
    coords = coords[:-1]
    # Check all sides are either horizontal or vertical
    for i in range(4):
        x1, y1 = coords[i]
        x2, y2 = coords[(i + 1) % 4]
        if not (x1 == x2 or y1 == y2):
            return False
    return True
