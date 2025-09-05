from typing import List, Type, Union, Dict, Optional
from fastapi import Request
from shapely import Polygon, wkt
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.geometry import Polygon
from shapely.ops import transform
import pyproj
from PIL import Image
from io import BytesIO

from app.src import schemas
from app.src.exceptions import APIException
from pydantic import BaseModel


def getRequestInfo(request: Request) -> schemas.RequestInfo:
    app_id: int = request.scope["app"].state.id
    return {"method": request.method, "path": request.url.path, "app_id": app_id}


def fuseExceptionResponses(exceptions: List[APIException]) -> Dict[int, dict]:
    """
    Generate OpenAPI response documentation by fusing multiple APIException instances.

    Args:
        exceptions (List[APIException]): List of instantiated exceptions.

    Returns:
        Dict[int, dict]: A dictionary of OpenAPI response specs grouped by status code.
    """
    responses = {}

    for exception in exceptions:
        status_code = exception.status_code
        example_key = type(exception).__name__
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


def resizeImage(
    imageBytes: bytes, format: str, height: int = None, width: int = None
) -> bytes:
    image = Image.open(BytesIO(imageBytes))
    if height is None:
        height = image.height
    if width is None:
        width = image.width

    outputBuffer = BytesIO()
    newSize = (width, height)
    image.thumbnail(newSize)
    if image.mode != "RGB":
        image = image.convert("RGB")
    image.save(outputBuffer, format)
    imageBytes = outputBuffer.getvalue()
    outputBuffer.close()
    return imageBytes


def splitMIME(mimeType: str) -> Dict:
    mimeElements = mimeType.split("/")
    type = mimeElements[0]
    subTypeWithParamElement = mimeElements[1].split(";")
    subType = subTypeWithParamElement[0]
    parameter = subTypeWithParamElement[1] if 1 < len(subTypeWithParamElement) else None

    return {"type": type, "sub_type": subType, "parameter": parameter}
