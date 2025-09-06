from typing import List, Type, Dict, Optional
from fastapi import Request
from shapely.geometry import Polygon, MultiPolygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform
import pyproj
from PIL import Image
from io import BytesIO

from app.src import schemas
from app.src.exceptions import APIException
from pydantic import BaseModel


def getRequestInfo(request: Request) -> schemas.RequestInfo:
    """
    Extract request metadata and return it as a `RequestInfo` schema.

    This function pulls essential information about the incoming request,
    including the HTTP method, request path, and the `app_id` stored in the
    application state. It is typically used for logging, auditing, or
    generating contextual information about requests.

    Args:
        request (Request): The incoming FastAPI request object.

    Returns:
        schemas.RequestInfo: A dictionary (pydantic model) containing:
            - method (str): The HTTP method of the request (e.g., GET, POST).
            - path (str): The request URL path (e.g., "/api/v1/routes").
            - app_id (int): The application identifier (e.g., AppID.EXECUTIVE, AppID.VENDOR)
    """
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
    """
    Convert an Enum class into a comma-separated string of its members.

    Each enum member is formatted as "<NAME>: <VALUE>".

    Args:
        enumClass (Type[Enum]): The Enum class to be stringified.

    Returns:
        str: A human-readable string representation of the enum members.

    Example:
        >>> from enum import Enum
        >>> class Color(Enum):
        ...     RED = 1
        ...     GREEN = 2
        ...     BLUE = 3
        >>> enumStr(Color)
        'RED: 1, GREEN: 2, BLUE: 3'
    """
    return ", ".join(f"{x.name}: {x.value}" for x in enumClass)


def isSRID4326(wktGeom: BaseGeometry) -> bool:
    """
    Validate whether a Shapely geometry uses coordinates consistent with SRID 4326 (WGS84).

    SRID 4326 (WGS84) represents geographic coordinates where:
      - Latitude must be within [-90, 90].
      - Longitude must be within [-180, 180].

    Supported geometries:
      - Point
      - LineString
      - Polygon (exterior ring only, not interiors/holes by default)
      - MultiPoint, MultiLineString, MultiPolygon (checked recursively)

    Args:
        wktGeom (BaseGeometry): A Shapely geometry.

    Returns:
        bool: True if all coordinates fall within valid latitude/longitude ranges,
        otherwise False.

    Example:
        >>> from shapely.geometry import Point, Polygon, LineString, MultiPoint
        >>> isSRID4326(Point(77.5946, 12.9716))
        True
        >>> isSRID4326(Point(200, 95))  # invalid lon/lat
        False
        >>> polygon = Polygon([(77, 12), (78, 12), (78, 13), (77, 13), (77, 12)])
        >>> isSRID4326(polygon)
        True
        >>> line = LineString([(77, 12), (200, 50)])
        >>> isSRID4326(line)
        False
        >>> multi = MultiPoint([(77, 12), (78, 13)])
        >>> isSRID4326(multi)
        True
    """

    def check_coords(coords):
        for longitude, latitude in coords:
            if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                return False
        return True

    # Point, LineString, Polygon (and similar)
    if hasattr(wktGeom, "coords"):
        if not check_coords(wktGeom.coords):
            return False

    # Multi* geometries (recursive check)
    if hasattr(wktGeom, "geoms"):
        for geom in wktGeom.geoms:
            if not isSRID4326(geom):
                return False

    return True


def getArea(geom: BaseGeometry) -> float:
    """
    Compute the area of a Polygon or MultiPolygon in square meters.

    The geometry is assumed to be in WGS84 (EPSG:4326, lat/lon). It is
    projected into an equal-area CRS (EPSG:6933, Cylindrical Equal Area)
    before area calculation for higher accuracy.

    Args:
        geom (BaseGeometry): A Shapely Polygon or MultiPolygon geometry in WGS84.

    Returns:
        float: The area of the geometry in square meters.

    Raises:
        TypeError: If the input is not a Polygon or MultiPolygon.

    Example:
        >>> from shapely.geometry import Polygon
        >>> square = Polygon([(0,0), (0,1), (1,1), (1,0), (0,0)])
        >>> round(getArea(square), 2)
        12308691685.53  # area in square meters
    """
    if not isinstance(geom, (Polygon, MultiPolygon)):
        raise TypeError("getArea() supports only Polygon or MultiPolygon geometries")

    projection = pyproj.Transformer.from_crs(
        "EPSG:4326", "EPSG:6933", always_xy=True
    ).transform

    projectedGeom = transform(projection, geom)
    return projectedGeom.area


def updateIfChanged(targetObj, sourceObj, fields: List[str]) -> None:
    """
    Update attributes on a target object from a source object
    only if the values differ and the new value is not None.

    Designed for use with SQLAlchemy models, where `fields` are typically
    provided as `Model.field.key`.

    Args:
        targetObj (object): The object whose attributes may be updated
            (e.g., a SQLAlchemy model instance).
        sourceObj (object): The object providing new values
            (e.g., another model instance or a DTO).
        fields (List[str]): A list of attribute names to check and update.
            Commonly passed as `[Model.field.key, ...]`.

    Example:
        >>> updateIfChanged(
        ...     bus,
        ...     fParam,
        ...     [
        ...         Bus.name.key,
        ...         Bus.capacity.key,
        ...         Bus.status.key,
        ...     ],
        ... )
        # bus will be updated where values differ; unchanged fields are skipped silently
    """
    for field in fields:
        new_value = getattr(sourceObj, field, None)
        if new_value is not None:
            old_value = getattr(targetObj, field)
            if old_value != new_value:
                setattr(targetObj, field, new_value)


def promoteToParent(
    childObj: BaseModel, targetCls: Type[BaseModel], **overrides
) -> BaseModel:
    """
    Promote one Pydantic model into another, applying overrides
    and defaulting missing fields to None.

    Useful when a more specialized model (`childObj`) needs to be
    adapted into a broader model (`targetCls`) for downstream
    operations such as queries, searches, or API calls.

    Args:
        childObj (BaseModel): The source Pydantic model instance.
        targetCls (Type[BaseModel]): The target Pydantic model class.
        **overrides: Explicit field values to override in the target model.

    Returns:
        BaseModel: An instance of `targetCls` with fields populated
        from `childObj`, overridden where specified, and filled with
        `None` when missing.

    Example:
        >>> class Child(BaseModel):
        ...     name: str
        ...
        >>> class Parent(BaseModel):
        ...     name: str
        ...     company_id: int | None
        ...
        >>> promoteToParent(Child(name="Bus A"), Parent, company_id=42)
        Parent(name='Bus A', company_id=42)
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
    """
    Resize an image (bytes) to the given width and height while preserving aspect ratio.

    If `height` or `width` is not provided, the original dimension is used.
    The output image is always converted to RGB mode to avoid format issues
    (e.g., when saving PNG with transparency to JPEG).

    Args:
        imageBytes (bytes): The input image in bytes format.
        format (str): The target format (e.g., "JPEG", "PNG").
        height (int, optional): Target height in pixels. Defaults to original height.
        width (int, optional): Target width in pixels. Defaults to original width.

    Returns:
        bytes: The resized image as bytes in the requested format.

    Example:
        >>> with open("input.jpg", "rb") as f:
        ...     img_bytes = f.read()
        >>> resized = resizeImage(img_bytes, format="JPEG", width=200, height=200)
        >>> with open("output.jpg", "wb") as f:
        ...     f.write(resized)
    """
    image = Image.open(BytesIO(imageBytes))

    if height is None:
        height = image.height
    if width is None:
        width = image.width

    newSize = (width, height)
    image.thumbnail(newSize)  # preserves aspect ratio, fits inside box

    if image.mode != "RGB":
        image = image.convert("RGB")

    with BytesIO() as outputBuffer:
        image.save(outputBuffer, format)
        return outputBuffer.getvalue()


def splitMIME(mimeType: str) -> Dict[str, Optional[str]]:
    """
    Safely split a MIME type string into type, subtype, and optional parameters.

    A MIME type generally follows the format:
        type/subtype[;parameter[;parameter...]]

    This function:
      - Handles missing parts gracefully (returns None instead of crashing).
      - Trims whitespace around parts.
      - Keeps parameters as a single string if multiple are provided.

    Args:
        mimeType (str): The MIME type string.
            Examples:
                "image/jpeg"
                "text/html; charset=UTF-8"
                "video/mp4; bitrate=128k; profile=high"

    Returns:
        Dict[str, Optional[str]]: A dictionary with:
            - "type": The main type (e.g., "image", "text") or None if missing.
            - "sub_type": The subtype (e.g., "jpeg", "html") or None if missing.
            - "parameter": The parameters as a single string if present,
              otherwise None.

    Example:
        >>> splitMIME("image/jpeg")
        {'type': 'image', 'sub_type': 'jpeg', 'parameter': None}

        >>> splitMIME("text/html; charset=UTF-8")
        {'type': 'text', 'sub_type': 'html', 'parameter': 'charset=UTF-8'}

        >>> splitMIME("video/mp4; bitrate=128k; profile=high")
        {'type': 'video', 'sub_type': 'mp4', 'parameter': 'bitrate=128k; profile=high'}

        >>> splitMIME("invalidstring")
        {'type': 'invalidstring', 'sub_type': None, 'parameter': None}
    """
    if not mimeType or "/" not in mimeType:
        return {"type": mimeType or None, "sub_type": None, "parameter": None}

    type_part, rest = mimeType.split("/", 1)
    type_part = type_part.strip() or None

    if ";" in rest:
        subType, *params = [p.strip() for p in rest.split(";")]
        parameter = "; ".join(params) if params else None
    else:
        subType, parameter = rest.strip() or None, None

    return {"type": type_part, "sub_type": subType, "parameter": parameter}
