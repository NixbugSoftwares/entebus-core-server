"""Simple scheduler worker that wakes every minute, reads due schedules
and creates Service entries directly in the database.

This module purposefully keeps the behavior minimal:
- sleeps for 60 seconds between runs
- selects schedules with triggering_mode AUTO and next_trigger_on <= now
- performs minimal status checks and creates a Service record directly
- updates schedule.last_trigger_on and clears next_trigger_on (no recurrence logic)

Call `trigger_schedules_worker()` from your application startup if you want
this to run continuously in a background thread/process.
"""

import time
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


def process_schedule(session: Session, schedule: Schedule) -> Optional[int]:

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
    current_date = datetime.now(TMZ_SECONDARY).date()
    starting_at = datetime.combine(current_date, route.start_time)

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

    # create name using IST (TMZ_SECONDARY)
    IST_starting_at = starting_at.astimezone(TMZ_SECONDARY)
    starting_at_str = IST_starting_at.strftime("%Y-%m-%d %-I:%M %p")

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
        ticket_mode=schedule.ticketing_mode,
        starting_at=starting_at,
        ending_at=ending_at,
        private_key=privateKey,
        public_key=publicKey,
    )

    session.add(service)

    schedule.last_trigger_on = datetime.now(TMZ_SECONDARY)
    schedule.next_trigger_on = starting_at + timedelta(days=1)

    session.flush()
    return service.id


def trigger_schedules_worker(run_once: bool = False) -> None:
    while True:
        time.sleep(60)
        now = datetime.now(TMZ_SECONDARY)
        with sessionMaker() as session:
            try:
                schedules = (
                    session.query(Schedule)
                    .filter(Schedule.next_trigger_on <= now)
                    .all()
                )
                for s in schedules:
                    try:
                        sid = process_schedule(session, s)
                        if sid:
                            session.commit()
                        else:
                            session.rollback()
                    except Exception:
                        session.rollback()
                # continue loop
            except Exception:
                # keep the worker alive on unexpected errors
                session.rollback()
        if run_once:
            break
