"""Scheduler worker that runs at 6 AM IST daily to create services for all schedules.

This module:
- Wakes up at 6 AM IST every day
- Processes ALL schedules in the database
- Creates service entries for the current date using route timings
- Performs status checks before creating services

Call `trigger_schedules_worker()` from your application startup to run
this continuously in a background thread/process.
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm.session import Session
from fastapi.encoders import jsonable_encoder

from app.src.db import (
    sessionMaker,
    Schedule,
    Route,
    Fare,
    Bus,
    Company,
    Service,
    LandmarkInRoute,
    Landmark,
)
from app.src.constants import TMZ_SECONDARY
from app.src.digital_ticket import v1
from app.src.enums import (
    BusStatus,
    CompanyStatus,
    RouteStatus,
)


def process_schedule(session: Session, schedule: Schedule, service_date: datetime) -> Optional[int]:
    """Create a service entry for a schedule using the given date."""
    # load required relations
    route = session.query(Route).filter(Route.id == schedule.route_id).first()
    fare = session.query(Fare).filter(Fare.id == schedule.fare_id).first()
    bus = session.query(Bus).filter(Bus.id == schedule.bus_id).first()
    company = session.query(Company).filter(Company.id == schedule.company_id).first()

    if not route or not fare or not bus or not company:
        return None

    # verify status
    if bus.status != BusStatus.ACTIVE:
        return None
    if company.status != CompanyStatus.VERIFIED:
        return None
    if route.status != RouteStatus.VALID:
        return None

    # compute ending_at using landmarks in route
    landmarks_in_route = (
        session.query(LandmarkInRoute)
        .filter(LandmarkInRoute.route_id == route.id)
        .order_by(LandmarkInRoute.distance_from_start.desc())
        .all()
    )
    if not landmarks_in_route:
        return None

    # Ensure service_date is timezone-aware in TMZ_SECONDARY
    if service_date.tzinfo is None:
        service_date = service_date.replace(tzinfo=TMZ_SECONDARY)

    # Set service starting time using route's start_time for the given date
    # route.start_time is a time object (naive). Create a timezone-aware datetime.
    starting_at = datetime.combine(service_date.date(), route.start_time).astimezone(TMZ_SECONDARY)
    
    last_landmark = landmarks_in_route[0]
    ending_at = starting_at + timedelta(seconds=last_landmark.arrival_delta)

    first_landmark = (
        session.query(Landmark)
        .join(LandmarkInRoute, Landmark.id == LandmarkInRoute.landmark_id)
        .filter(LandmarkInRoute.route_id == route.id)
        .order_by(LandmarkInRoute.distance_from_start.asc())
        .first()
    )
    last_landmark = (
        session.query(Landmark)
        .join(LandmarkInRoute, Landmark.id == LandmarkInRoute.landmark_id)
        .filter(LandmarkInRoute.route_id == route.id)
        .order_by(LandmarkInRoute.distance_from_start.desc())
        .first()
    )
    if not first_landmark or not last_landmark:
        return None

    # create name using IST (TMZ_SECONDARY) with portable time formatting
    IST_starting_at = starting_at.astimezone(TMZ_SECONDARY)
    # Use portable hour formatting by removing leading zeros manually
    hour = IST_starting_at.strftime("%I").lstrip('0')
    starting_at_str = f"{IST_starting_at.strftime('%Y-%m-%d')} {hour}:{IST_starting_at.strftime('%M %p')}"

    name = f"{starting_at_str} {first_landmark.name} -> {last_landmark.name} ({bus.registration_number})"

    # route and fare json
    routeData = jsonable_encoder(route)
    routeData["landmark"] = [jsonable_encoder(l) for l in landmarks_in_route]
    fareData = jsonable_encoder(fare)

    # generate keys
    ticketCreator = v1.TicketCreator()
    privateKey = ticketCreator.getPEMprivateKeyString()
    publicKey = ticketCreator.getPEMpublicKeyString()

    service = Service(
        company_id=company.id,
        name=name,
        route=routeData,
        fare=fareData,
        bus_id=bus.id,
        schedule_id=schedule.id,
        ticket_mode=schedule.ticketing_mode,
        starting_at=starting_at,
        ending_at=ending_at,
        private_key=privateKey,
        public_key=publicKey,
    )

    session.add(service)

    session.flush()
    return service.id


def trigger_schedules_worker(run_once: bool = False) -> None:
    """Main worker function that runs every day at 6 AM IST."""
    logger = logging.getLogger(__name__)
    while True:
        try:
            # Calculate next run time (6 AM IST)
            now = datetime.now(TMZ_SECONDARY)

            # Create today's 6:00 AM IST
            next_run = now.replace(hour=6, minute=0, second=0, microsecond=0)
            # If it's past 6 AM, schedule for next day
            if now >= next_run:
                next_run = next_run + timedelta(days=1)
            
            # Sleep until next run time
            sleep_seconds = (next_run - now).total_seconds()
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

            service_date = datetime.now(TMZ_SECONDARY)

            # Get schedules and process
            with sessionMaker() as session:
                schedules = session.query(Schedule).all()
                for schedule in schedules:
                    try:
                        sid = process_schedule(session, schedule, service_date)
                        if sid:
                            session.commit()
                            logger.info("Created service %s for schedule %s", sid, schedule.id)
                        else:
                            session.rollback()
                    except Exception as e:
                        logger.exception("Failed to process schedule %s: %s", schedule.id, e)
                        session.rollback()
        except Exception:
            pass
            logging.getLogger(__name__).exception("Scheduler main loop failed")
            
        if run_once:
            break
        time.sleep(60)

