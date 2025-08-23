import os
import time
import logging
import requests
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from http import HTTPStatus

from app.src.urls import URL_SERVICE, URL_EXECUTIVE_TOKEN
from app.src import exceptions
from app.src.db import sessionMaker, Schedule
from app.src.redis import acquireLock, releaseLock


BASE_URL = "http://127.0.0.1:8080//executive"
SCHEDULER_USERNAME = os.getenv("SCHEDULER_USERNAME")
SCHEDULER_PASSWORD = os.getenv("SCHEDULER_PASSWORD")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Scheduler")

BASE_URL = "http://127.0.0.1:8080/executive"


def loginScheduler():
    """Login with scheduler credentials and return Authorization header."""
    username = os.getenv("SCHEDULER_USERNAME")
    password = os.getenv("SCHEDULER_PASSWORD")
    if not username or not password:
        raise exceptions.InvalidCredentials()
    response = requests.post(
        BASE_URL + URL_EXECUTIVE_TOKEN,
        data={"username": username, "password": password},
    )
    if response.status_code != HTTPStatus.CREATED:
        raise exceptions.InvalidCredentials()
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def createService(schedule: Schedule, header: dict):
    serviceData = {
        "company_id": schedule.company_id,
        "route": schedule.route_id,
        "fare": schedule.fare_id,
        "bus_id": schedule.bus_id,
        "starting_at": schedule.next_trigger_on.isoformat(),
    }

    response = requests.post(
        BASE_URL + URL_SERVICE,
        headers=header,
        data=serviceData,
    )

    if response.status_code == HTTPStatus.CREATED:
        logger.info(f" Service created for schedule {schedule.id}")
    else:
        logger.error(
            f" Failed to create service: {response.status_code}, {response.text}"
        )


def runScheduler(session: Session):
    while True:
        header = loginScheduler()
        lock = None
        try:
            lock = acquireLock(Schedule.__tablename__)
            now = datetime.now(timezone.utc)
            cutoff = now + timedelta(minutes=1)
            schedules = (
                session.query(Schedule).filter(Schedule.next_trigger_on <= cutoff).all()
            )
            for schedule in schedules:
                createService(schedule, header)
                schedule.last_trigger_on = datetime.now(timezone.utc)
                if schedule.frequency:
                    schedule.next_trigger_on = schedule.next_trigger_on + timedelta(
                        days=1
                    )
                session.add(schedule)
            session.commit()
        except Exception as e:
            logger.exception("Scheduler loop failed")
        finally:
            releaseLock(lock)
            time.sleep(60)


def main():
    try:
        with sessionMaker() as session:
            runScheduler(session)
    except Exception as e:
        logger.exception("scheduler.py failed")


if __name__ == "__main__":
    main()
