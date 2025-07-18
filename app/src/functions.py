from typing import List, Type, Union
from fastapi import Request
from shapely import Polygon, wkt
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from typing import Optional
from shapely.geometry import Polygon
from shapely.ops import transform
import pyproj

from app.src import schemas
from app.src.exceptions import APIException
from pydantic import BaseModel


def getRequestInfo(request: Request) -> schemas.RequestInfo:
    app_id: int = request.scope["app"].state.id
    return {"method": request.method, "path": request.url.path, "app_id": app_id}


def makeExceptionResponses(exceptions: List[Union[Type[APIException], APIException]]):
    responses = {}

    for exc in exceptions:
        if isinstance(exc, APIException):
            # It's an instance — use it directly
            exception = exc
            example_key = type(exc).__name__
        else:
            # It's a class — try to instantiate with no args
            try:
                exception = exc()
                example_key = exc.__name__
            except Exception:
                continue  # skip if we can't instantiate

        status_code = exception.status_code
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


def getArea(geom: BaseGeometry) -> float:
    projection = pyproj.Transformer.from_crs(
        "EPSG:4326", "EPSG:3857", always_xy=True
    ).transform
    castedGeom = Polygon(geom) if isinstance(geom, Polygon) else geom
    projectedGeom = transform(projection, castedGeom)
    return projectedGeom.area


def updateIfChanged(targetObj, sourceObj, fields: list[str]):
    # Update fields from source_obj only if the field is not None and its value differs from the current value
    for field in fields:
        updatedData = getattr(sourceObj, field, None)
        if updatedData is not None:
            existingData = getattr(targetObj, field)
            if existingData != updatedData:
                setattr(targetObj, field, updatedData)


def promoteToParent(
    childObj: BaseModel, targetCls: Type[BaseModel], **overrides
) -> BaseModel:
    """
    Promote `childObj` to `targetCls`, applying `overrides` and
    setting any missing fields to None by default.
    """

    baseData = childObj.model_dump()
    targetFields = targetCls.model_fields.keys()
    finalData = {
        field: overrides.get(field, baseData.get(field, None)) for field in targetFields
    }
    return targetCls(**finalData)
