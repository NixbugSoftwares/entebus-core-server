from datetime import datetime
from enum import IntEnum
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status, Form, UploadFile, File
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from io import BytesIO
from functools import lru_cache

from app.api.bearer import bearer_executive
from app.src.constants import EXECUTIVE_PICTURES
from app.src.db import ExecutiveRole, ExecutiveImage, sessionMaker
from app.src import exceptions, validators, getters
from app.src.loggers import logEvent
from app.src.urls import URL_EXECUTIVE_PICTURE
from app.src.minio import uploadFile, downloadFile, deleteFile
from app.src.functions import enumStr, makeExceptionResponses, splitMIME, resizeImage

route_executive = APIRouter()


## Output Schema
class ExecutiveImageSchema(BaseModel):
    id: int
    executive_id: int
    file_name: str
    file_type: str
    file_size: int
    updated_on: Optional[datetime]
    created_on: datetime


class createForm(BaseModel):
    executive_id: int | None = Field(Form(default=None))
    file: UploadFile = Field(File())


class UpdateForm(BaseModel):
    id: int | None = Field(Form(default=None))
    file: UploadFile = Field(File())


class DeleteForm(BaseModel):
    id: int | None = Field(Form(default=None))


## Query Parameters
class OrderIn(IntEnum):
    ASC = 1
    DESC = 2


class OrderBy(IntEnum):
    id = 1
    updated_on = 2
    created_on = 3


class QueryParams(BaseModel):
    executive_id: int | None = Field(Query(default=None))
    file_name: str | None = Field(Query(default=None))
    file_type: str | None = Field(Query(default=None))
    # file_size based
    file_size_ge: int | None = Field(Query(default=None))
    file_size_le: int | None = Field(Query(default=None))
    # id based
    id: int | None = Field(Query(default=None))
    id_ge: int | None = Field(Query(default=None))
    id_le: int | None = Field(Query(default=None))
    id_list: List[int] | None = Field(Query(default=None))
    # updated_on based
    updated_on_ge: datetime | None = Field(Query(default=None))
    updated_on_le: datetime | None = Field(Query(default=None))
    # created_on based
    created_on_ge: datetime | None = Field(Query(default=None))
    created_on_le: datetime | None = Field(Query(default=None))
    # Ordering
    order_by: OrderBy = Field(Query(default=OrderBy.id, description=enumStr(OrderBy)))
    order_in: OrderIn = Field(Query(default=OrderIn.DESC, description=enumStr(OrderIn)))
    # Pagination
    offset: int = Field(Query(default=0, ge=0))
    limit: int = Field(Query(default=20, gt=0, le=100))


## API endpoints [Executive]
@route_executive.post(
    URL_EXECUTIVE_PICTURE,
    tags=["Account Picture"],
    response_model=ExecutiveImageSchema,
    status_code=status.HTTP_201_CREATED,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Upload the executive's profile picture.  
    Only authorized users with `update_executive` permission can upload a picture .    
    Stores the image in MinIO and saves metadata in `executive_image` table.
    """,
)
async def upload_executive_picture(
    fParam: createForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_executive)

        fileBytes = await fParam.file.read()
        mimeInfo = splitMIME(fParam.file.content_type)
        resizedBytes = resizeImage(fileBytes, mimeInfo["sub_type"])
        uploadFile(
            EXECUTIVE_PICTURES,
            str(fParam.executive_id),
            len(resizedBytes),
            BytesIO(resizedBytes),
        )

        executiveImage = ExecutiveImage(
            executive_id=fParam.executive_id,
            file_name=fParam.file.filename,
            file_type=fParam.file.content_type,
            file_size=len(resizedBytes),
        )
        session.add(executiveImage)
        session.commit()
        session.refresh(executiveImage)

        executiveImageData = jsonable_encoder(executiveImage)
        logEvent(token, request_info, executiveImageData)
        return executiveImageData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.patch(
    URL_EXECUTIVE_PICTURE,
    tags=["Account Picture"],
    response_model=ExecutiveImageSchema,
    description="Replace an executive's profile picture",
)
async def update_executive_picture(
    fParam: UpdateForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_executive)

        executiveImage = (
            session.query(ExecutiveImage).filter(ExecutiveImage.id == fParam.id).first()
        )
        if executiveImage is None:
            raise exceptions.InvalidIdentifier()

        fileBytes = await fParam.file.read()
        mimeInfo = splitMIME(fParam.file.content_type)
        resizedBytes = resizeImage(fileBytes, mimeInfo["sub_type"])

        uploadFile(
            EXECUTIVE_PICTURES,
            str(executiveImage.executive_id),
            len(resizedBytes),
            BytesIO(resizedBytes),
        )

        if fParam.file is not None and executiveImage.file_name != fParam.file.filename:
            executiveImage.file_name = fParam.file.filename
        if (
            fParam.file is not None
            and executiveImage.file_type != fParam.file.content_type
        ):
            executiveImage.file_type = fParam.file.content_type
        if fParam.file is not None and executiveImage.file_size != len(resizedBytes):
            executiveImage.file_size = len(resizedBytes)
        session.commit()
        session.refresh(executiveImage)

        logEvent(token, request_info, jsonable_encoder(executiveImage))
        return executiveImage
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    URL_EXECUTIVE_PICTURE,
    tags=["Account Picture"],
    status_code=status.HTTP_204_NO_CONTENT,
    description="Delete an executive's profile picture",
)
async def delete_executive_picture(
    fParam: DeleteForm = Depends(),
    bearer=Depends(bearer_executive),
    request_info=Depends(getters.requestInfo),
):
    try:
        session = sessionMaker()
        token = validators.executiveToken(bearer.credentials, session)
        role = getters.executiveRole(token, session)
        validators.executivePermission(role, ExecutiveRole.update_executive)

        executiveImage = (
            session.query(ExecutiveImage).filter(ExecutiveImage.id == fParam.id).first()
        )
        if executiveImage is not None:
            deleteFile(EXECUTIVE_PICTURES, str(executiveImage.executive_id))
            session.delete(executiveImage)
            session.commit()
            logEvent(token, request_info, jsonable_encoder(executiveImage))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get(
    URL_EXECUTIVE_PICTURE,
    tags=["Account Picture"],
    response_model=list[ExecutiveImageSchema],
    description="Get metadata of all executive profile pictures",
)
async def fetch_executive_pictures(
    qParam: QueryParams = Depends(),
    bearer=Depends(bearer_executive),
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        query = session.query(ExecutiveImage)

        # Filters
        if qParam.id is not None:
            query = query.filter(ExecutiveImage.id == qParam.id)
        if qParam.id_ge is not None:
            query = query.filter(ExecutiveImage.id >= qParam.id_ge)
        if qParam.id_le is not None:
            query = query.filter(ExecutiveImage.id <= qParam.id_le)
        if qParam.id_list is not None:
            query = query.filter(ExecutiveImage.id.in_(qParam.id_list))
        if qParam.executive_id is not None:
            query = query.filter(ExecutiveImage.executive_id == qParam.executive_id)
        if qParam.file_name is not None:
            query = query.filter(
                ExecutiveImage.executive_id.ilike(f"%{qParam.file_name}%")
            )
        if qParam.file_type is not None:
            query = query.filter(ExecutiveImage.file_type == qParam.file_type)
        if qParam.file_size_ge is not None:
            query = query.filter(ExecutiveImage.file_size >= qParam.file_size_ge)
        if qParam.file_size_le is not None:
            query = query.filter(ExecutiveImage.file_size <= qParam.file_size_le)

        # Ordering
        orderingAttribute = getattr(ExecutiveImage, OrderBy(qParam.order_by).name)
        if qParam.order_in == OrderIn.ASC:
            query = query.order_by(orderingAttribute.asc())
        else:
            query = query.order_by(orderingAttribute.desc())

        # Pagination
        query = query.offset(qParam.offset).limit(qParam.limit)
        return query.all()
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@lru_cache()
def get_resized_image(file_bytes: bytes, format: str, resolution: str | None):
    """Resize image and cache results"""
    if resolution:
        try:
            width, height = map(int, resolution.lower().split("x"))
        except ValueError:
            raise exceptions.InvalidAABB()
    else:
        width, height = None, None
    return resizeImage(file_bytes, format, width=width, height=height)


@route_executive.get(
    f"{URL_EXECUTIVE_PICTURE}" + "/{id}",
    tags=["Account Picture"],
    description="Download executive profile picture in original or resized resolution",
)
async def download_executive_picture(
    id: int,
    resolution: str | None = Query(
        None, description="Resolution in WIDTHxHEIGHT format"
    ),
    bearer=Depends(bearer_executive),
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        executiveImage = (
            session.query(ExecutiveImage).filter(ExecutiveImage.id == id).first()
        )
        if executiveImage is not None:
            fileBytes = downloadFile(
                EXECUTIVE_PICTURES, str(executiveImage.executive_id)
            )
            mimeInfo = splitMIME(executiveImage.file_type)
            resizedBytes = get_resized_image(
                fileBytes, mimeInfo["sub_type"], resolution
            )

            return StreamingResponse(
                BytesIO(resizedBytes),
                media_type=executiveImage.file_type,
                headers={
                    "Content-Disposition": f"file_name={executiveImage.file_name}"
                },
            )
        return []
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
