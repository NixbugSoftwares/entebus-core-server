from fastapi import (
    APIRouter,
    Depends,
    status,
    Form,
    Response,
)
from typing import Annotated
from fastapi.encoders import jsonable_encoder

from app.api.bearer import bearer_executive, bearer_operator
from app.src import exceptions
from app.src.db import (
    sessionMaker,
    OperatorToken,
)
from app.src.functions import (
    getRequestInfo,
    logOperatorEvent,
    makeExceptionResponses,
    getOperatorToken,
    getOperatorRole,
)

route_operator = APIRouter()
route_executive = APIRouter()


@route_operator.post("/company/account/token", tags=["Token"])
async def create_token():
    pass


@route_operator.patch("/company/account/token", tags=["Token"])
async def update_token(credential=Depends(bearer_operator)):
    pass


@route_operator.get("/company/account/token", tags=["Token"])
async def fetch_tokens(credential=Depends(bearer_operator)):
    pass


@route_operator.delete(
    "/company/account/token",
    tags=["Token"],
    status_code=status.HTTP_204_NO_CONTENT,
    responses=makeExceptionResponses(
        [exceptions.InvalidToken, exceptions.NoPermission]
    ),
    description="""
    Revokes an active access token associated with an executive account.

    - This endpoint deletes an access token based on the token ID (optional).
    - If no ID is provided, it deletes the token used in the request (self-revocation).
    - If an ID is provided, the caller must either: 
        Own the token being deleted, or have a role with `manage_ex_token` permission.
    - If the token ID is invalid or already deleted, the operation is silently ignored.
    - Returns 204 No Content upon success.
    - Logs the token revocation event for audit tracking.
    """,
)
async def delete_tokens(
    id: Annotated[int | None, Form()] = None,
    bearer=Depends(bearer_operator),
    request_info=Depends(getRequestInfo),
):
    try:
        session = sessionMaker()
        token = getOperatorToken(bearer.credentials, session)
        role = getOperatorRole(token, session)

        if id is None:
            tokenToDelete = token
        else:
            tokenToDelete = (
                session.query(OperatorToken)
                .filter(OperatorToken.id == id)
                .filter(OperatorToken.company_id == token.company_id)
                .first()
            )
            if tokenToDelete is not None:
                forSelf = token.operator_id == tokenToDelete.operator_id
                canManageToken = bool(role and role.manage_op_token)
                if not forSelf and not canManageToken:
                    raise exceptions.NoPermission()
            else:
                return Response(status_code=status.HTTP_204_NO_CONTENT)

        session.delete(tokenToDelete)
        session.commit()
        logOperatorEvent(
            token,
            request_info,
            jsonable_encoder(tokenToDelete, exclude={"access_token"}),
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        exceptions.handle(e)
    finally:
        session.close()


@route_executive.get("/company/account/token", tags=["Operator token"])
async def fetch_tokens(credential=Depends(bearer_executive)):
    pass


@route_executive.delete("/company/account/token", tags=["Operator token"])
async def delete_tokens(credential=Depends(bearer_executive)):
    pass
