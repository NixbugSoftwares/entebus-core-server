from fastapi import APIRouter, Depends

from app.api.bearer import bearer_executive

route_executive = APIRouter()


@route_executive.post("/entebus/account/token", tags=["Token"])
async def create_token():
    pass


@route_executive.patch("/entebus/account/token", tags=["Token"])
async def update_token(credential=Depends(bearer_executive)):
    pass


@route_executive.get("/entebus/account/token", tags=["Token"])
async def fetch_tokens(credential=Depends(bearer_executive)):
    pass


@route_executive.delete("/entebus/account/token", tags=["Token"])
async def delete_tokens(credential=Depends(bearer_executive)):
    pass
