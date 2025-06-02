from fastapi import APIRouter, Depends

from app.api.bearer import bearer_executive, bearer_vendor

route_vendor = APIRouter()
route_executive = APIRouter()


@route_vendor.post("/merchant/account/token", tags=["Token"])
async def create_token():
    pass


@route_vendor.patch("/merchant/account/token", tags=["Token"])
async def update_token(credential=Depends(bearer_vendor)):
    pass


@route_vendor.get("/merchant/account/token", tags=["Token"])
async def fetch_tokens(credential=Depends(bearer_vendor)):
    pass


@route_vendor.delete("/merchant/account/token", tags=["Token"])
async def delete_tokens(credential=Depends(bearer_vendor)):
    pass


@route_executive.get("/merchant/account/token", tags=["Vendor token"])
async def fetch_tokens(credential=Depends(bearer_executive)):
    pass


@route_executive.delete("/merchant/account/token", tags=["Vendor token"])
async def delete_tokens(credential=Depends(bearer_executive)):
    pass
