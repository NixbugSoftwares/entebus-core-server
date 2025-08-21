from datetime import datetime
from enum import IntEnum
from typing import List
from fastapi import APIRouter, Depends, Query, Response, status, Form, UploadFile, File
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from io import BytesIO

from app.api.bearer import bearer_executive
from app.src.constants import EXECUTIVE_PICTURES
from app.src.db import ExecutiveImage, sessionMaker
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
    created_on: datetime


class createForm(BaseModel):
    executive_id: int | None = Field(Form(default=None))
    file: UploadFile = Field(File())


class DeleteForm(BaseModel):
    id: int | None = Field(Form(default=None))


## Query Parameters
class OrderIn(IntEnum):
    ASC = 1
    DESC = 2


class OrderBy(IntEnum):
    id = 1
    created_on = 2
    file_size = 3


class ImageQueryParams(BaseModel):
    id: int
    width: int | None = Field(Query(default=None, ge=16, le=2048))
    height: int | None = Field(Query(default=None, ge=16, le=2048))


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
        [exceptions.InvalidToken, exceptions.NoPermission, exceptions.InvalidImage]
    ),
    description="""
    Upload the executive's profile picture. 
    Executives can update their own profile picture.     
    Authorized users with `update_executive` permission can update any executive profile picture.      
    Stores the image in the `executive_pictures` bucket in MinIO and saves the metadata in `executive_image` table.
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

        if fParam.executive_id is None:
            fParam.executive_id = token.executive_id
        isSelfUpdate = fParam.executive_id == token.executive_id
        hasUpdatePermission = bool(role and role.update_executive)
        if not isSelfUpdate and not hasUpdatePermission:
            raise exceptions.NoPermission()

        fileBytes = await fParam.file.read()
        mimeInfo = splitMIME(fParam.file.content_type)
        mimeType = mimeInfo["type"]
        if mimeType != "image":
            raise exceptions.InvalidImage()

        executiveImage = ExecutiveImage(
            executive_id=fParam.executive_id,
            file_name=fParam.file.filename,
            file_type=fParam.file.content_type,
            file_size=len(fileBytes),
        )
        session.add(executiveImage)
        session.commit()
        session.refresh(executiveImage)
        uploadFile(
            EXECUTIVE_PICTURES,
            str(executiveImage.id),
            len(fileBytes),
            BytesIO(fileBytes),
        )

        executiveImageData = jsonable_encoder(executiveImage)
        logEvent(token, request_info, executiveImageData)
        return executiveImageData
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.delete(
    URL_EXECUTIVE_PICTURE,
    tags=["Account Picture"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Delete an executive's profile picture.  
    Executives can delete their own profile picture.     
    Authorized users with `update_executive` permission can update any executive profile picture.   
    Removes the image from `executive_pictures` bucket in MinIO and deletes metadata from executive_image table.     
    """,
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

        if fParam.id is None:
            executiveImage = (
                session.query(ExecutiveImage)
                .filter(ExecutiveImage.executive_id == token.executive_id)
                .first()
            )
        else:
            executiveImage = (
                session.query(ExecutiveImage)
                .filter(ExecutiveImage.id == fParam.id)
                .first()
            )
            if executiveImage is not None:
                isSelfUpdate = executiveImage.executive_id == token.executive_id
                hasUpdatePermission = bool(role and role.update_executive)
                if not isSelfUpdate and not hasUpdatePermission:
                    raise exceptions.NoPermission()
            else:
                return Response(status_code=status.HTTP_204_NO_CONTENT)

        session.delete(executiveImage)
        session.commit()
        deleteFile(EXECUTIVE_PICTURES, str(executiveImage.id))
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
    responses=makeExceptionResponses([exceptions.InvalidToken]),
    description="""
    Fetch metadata of all executive profile pictures with filtering, sorting, and pagination.   
    Filter by file name file type, file size, id's and creation/update timestamps.   
    Filter by ID ranges or lists.   
    Sort by ID, creation date, or update date, file size in ascending or descending order.  
    Paginate using offset and limit.    
    Returns a list of executive profile pictures metadata, matching the criteria.
    """,
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
        # created_on based
        if qParam.created_on_ge is not None:
            query = query.filter(ExecutiveImage.created_on >= qParam.created_on_ge)
        if qParam.created_on_le is not None:
            query = query.filter(ExecutiveImage.created_on <= qParam.created_on_le)

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


@route_executive.get(
    f"{URL_EXECUTIVE_PICTURE}" + "/{id}",
    tags=["Account Picture"],
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.InvalidIdentifier]
    ),
    description="""
    Download executive profile picture in original or resized resolution.   
    Requires a valid executive token.   
    Return the image file from `executive_pictures` bucket in MinIO in original resolution or specified resolution.     
    Returns the original image file.
    """,
)
async def download_executive_picture(
    qParam: ImageQueryParams = Depends(),
    bearer=Depends(bearer_executive),
):
    try:
        session = sessionMaker()
        validators.executiveToken(bearer.credentials, session)

        executiveImage = (
            session.query(ExecutiveImage).filter(ExecutiveImage.id == qParam.id).first()
        )
        if executiveImage is not None:
            fileBytes = downloadFile(EXECUTIVE_PICTURES, str(executiveImage.id))
            mimeInfo = splitMIME(executiveImage.file_type)
            resizedBytes = resizeImage(
                fileBytes,
                mimeInfo["sub_type"],
                width=qParam.width,
                height=qParam.height,
            )

            return StreamingResponse(
                BytesIO(resizedBytes),
                media_type=executiveImage.file_type,
                headers={
                    "Content-Disposition": f"file_name={executiveImage.file_name}",
                    "Cache-Control": "public, max-age=31536000, immutable",
                },
            )
        raise exceptions.InvalidIdentifier()
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()
