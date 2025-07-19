import argparse, datetime, logging
from app.src.db import sessionMaker, ExecutiveToken, OperatorToken, VendorToken
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Cleaner")


def removeExpiredTokens(session: Session, model, tokenName: str):
    currentTime = datetime.datetime.now(datetime.timezone.utc)
    expiredTokens = session.query(model).filter(model.expires_at < currentTime).all()

    if expiredTokens:
        for token in expiredTokens:
            session.delete(token)
        session.commit()
        logger.info(f"Removed {len(expiredTokens)} expired {tokenName} tokens.")
    else:
        logger.info(f"No expired {tokenName} tokens found.")


def executeCleaner():
    try:
        with sessionMaker() as session:
            removeExpiredTokens(session, ExecutiveToken, "executive")
            removeExpiredTokens(session, OperatorToken, "operator")
            removeExpiredTokens(session, VendorToken, "vendor")
    except Exception as e:
        logger.exception(f"Cleaning failed: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-ct", action="store_true", help="cleaner token")
    args = parser.parse_args()

    if args.ct:
        executeCleaner()
