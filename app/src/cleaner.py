import datetime, logging
from app.src.db import sessionMaker, ExecutiveToken, OperatorToken, VendorToken
from sqlalchemy.orm import Session
from sqlalchemy import delete

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Cleaner")


def removeExpiredTokens(session: Session, tableName: str):
    currentTime = datetime.datetime.now(datetime.timezone.utc)
    result = session.execute(delete(tableName).where(tableName.expire_at < currentTime))
    session.commit()
    deletedCount = result.rowcount
    logger.info(f"Removed {deletedCount} tokens from {tableName} table")


def main():
    try:
        with sessionMaker() as session:
            removeExpiredTokens(session, ExecutiveToken.__name__)
            removeExpiredTokens(session, OperatorToken.__name__)
            removeExpiredTokens(session, VendorToken.__name__)
    except Exception as e:
        logger.exception("cleaner.py failed")


if __name__ == "__main__":
    main()
