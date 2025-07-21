import datetime, logging
from app.src.db import sessionMaker, ExecutiveToken, OperatorToken, VendorToken
from sqlalchemy.orm import Session
from sqlalchemy import delete

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Cleaner")


def removeExpiredTokens(session: Session, model, tokenName: str):
    currentTime = datetime.datetime.now(datetime.timezone.utc)
    result = session.execute(delete(model).where(model.expires_at < currentTime))
    session.commit()
    deleted_count = result.rowcount
    logger.info(
        f"Removed {deleted_count} expired {tokenName} tokens."
        if deleted_count > 0
        else f"No expired {tokenName} tokens found."
    )


try:
    with sessionMaker() as session:
        removeExpiredTokens(session, ExecutiveToken, "executive")
        removeExpiredTokens(session, OperatorToken, "operator")
        removeExpiredTokens(session, VendorToken, "vendor")
except Exception as e:
    logger.exception(f"Cleaning failed: {e}")
