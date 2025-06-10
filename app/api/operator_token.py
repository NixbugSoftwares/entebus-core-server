from fastapi import APIRouter, Depends

from app.api.bearer import bearer_executive, bearer_operator

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


@route_operator.delete("/company/account/token", tags=["Token"])
async def delete_tokens(credential=Depends(bearer_operator)):
    pass


@route_executive.get("/company/account/token", tags=["Operator token"])
async def fetch_tokens(credential=Depends(bearer_executive)):
    pass


@route_executive.delete("/company/account/token", tags=["Operator token"])
async def delete_tokens(credential=Depends(bearer_executive)):
    pass
