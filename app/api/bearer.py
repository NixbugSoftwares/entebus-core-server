from fastapi.security import HTTPBearer


bearer_executive = HTTPBearer(scheme_name="Executive HTTPBearer")
bearer_vendor = HTTPBearer(scheme_name="Vendor HTTPBearer")
bearer_operator = HTTPBearer(scheme_name="Operator HTTPBearer")
