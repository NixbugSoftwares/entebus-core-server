import argparse
from datetime import time

from app.src import argon2
from app.src.enums import (
    CompanyStatus,
    Day,
    FareScope,
)
from app.src.db import (
    Executive,
    ExecutiveRole,
    ExecutiveRoleMap,
    Company,
    LandmarkInRoute,
    Operator,
    OperatorRole,
    OperatorRoleMap,
    Landmark,
    Fare,
    Business,
    Schedule,
    Vendor,
    VendorRole,
    VendorRoleMap,
    BusStop,
    Bus,
    Route,
    Wallet,
    CompanyWallet,
    BusinessWallet,
    sessionMaker,
    engine,
    ORMbase,
)


# ----------------------------------- Project Setup -------------------------------------------#
def removeTables():
    session = sessionMaker()
    ORMbase.metadata.drop_all(engine)
    session.commit()
    print("* All tables deleted")
    session.close()


def createTables():
    session = sessionMaker()
    ORMbase.metadata.create_all(engine)
    session.commit()
    print("* All tables created")
    session.close()


def initDB():
    session = sessionMaker()
    company = Company(
        name="Nixbug company",
        status=CompanyStatus.VERIFIED,
        contact_person="Managing director",
        phone_number="+919496801157",
        address="Edava, Thiruvananthapuram, Kerala 695311",
        email_id="contact@nixbug.com",
        location="POINT(76.68899711264336 8.761725176790257)",
    )
    session.add(company)
    session.flush()

    password = argon2.makePassword("password")
    admin = Executive(
        username="admin",
        password=password,
        full_name="Entebus admin",
        designation="Administrator",
    )
    guest = Executive(
        username="guest",
        password=password,
        full_name="Entebus guest",
        designation="Guest",
    )
    adminRole = ExecutiveRole(
        name="Admin",
        manage_ex_token=True,
        manage_op_token=True,
        manage_ve_token=True,
        create_executive=True,
        update_executive=True,
        delete_executive=True,
        create_landmark=True,
        update_landmark=True,
        delete_landmark=True,
        create_company=True,
        update_company=True,
        delete_company=True,
        create_operator=True,
        update_operator=True,
        delete_operator=True,
        create_business=True,
        update_business=True,
        delete_business=True,
        create_route=True,
        update_route=True,
        delete_route=True,
        create_bus=True,
        update_bus=True,
        delete_bus=True,
        create_vendor=True,
        update_vendor=True,
        delete_vendor=True,
        create_schedule=True,
        update_schedule=True,
        delete_schedule=True,
    )
    guestRole = ExecutiveRole(
        name="Guest",
        manage_ex_token=False,
        manage_op_token=False,
        manage_ve_token=False,
        create_executive=False,
        update_executive=False,
        delete_executive=False,
        create_landmark=False,
        update_landmark=False,
        delete_landmark=False,
        create_company=False,
        update_company=False,
        delete_company=False,
        create_operator=False,
        update_operator=False,
        delete_operator=False,
        create_business=False,
        update_business=False,
        delete_business=False,
        create_route=False,
        update_route=False,
        delete_route=False,
        create_bus=False,
        update_bus=False,
        delete_bus=False,
        create_vendor=False,
        update_vendor=False,
        delete_vendor=False,
        create_schedule=False,
        update_schedule=False,
        delete_schedule=False,
    )
    session.add_all([admin, guest, adminRole, guestRole])
    session.flush()

    adminToRoleMapping = ExecutiveRoleMap(executive_id=admin.id, role_id=adminRole.id)
    guestToRoleMapping = ExecutiveRoleMap(executive_id=guest.id, role_id=guestRole.id)
    session.add_all([adminToRoleMapping, guestToRoleMapping])
    session.flush()

    session.commit()
    print("* Initialization completed")
    session.close()


def testDB():
    session = sessionMaker()
    companyWallet = Wallet(
        name="Test company wallet",
        balance=0,
    )
    session.add(companyWallet)
    session.flush()

    company = Company(
        name="Test company",
        status=CompanyStatus.VERIFIED,
        contact_person="Bismilla Motors(Edava)",
        phone_number="+911212121212",
        address="Test, Test, Test 695311",
        email_id="example@test.com",
        location="POINT(76.68899711264336 8.761725176790257)",
    )
    session.add(company)
    session.flush()

    companyWalletMapping = CompanyWallet(
        company_id=company.id,
        wallet_id=companyWallet.id,
    )
    session.add(companyWalletMapping)
    session.flush()

    password = argon2.makePassword("password")
    admin = Operator(
        company_id=company.id,
        username="admin",
        password=password,
        full_name="Entebus Operator",
    )
    guest = Operator(
        company_id=company.id,
        username="guest",
        password=password,
        full_name="Entebus Conductor",
    )
    adminRole = OperatorRole(
        company_id=company.id,
        name="Admin",
        manage_token=True,
        update_company=True,
        create_operator=True,
        update_operator=True,
        delete_operator=True,
        create_route=True,
        update_route=True,
        delete_route=True,
        create_bus=True,
        update_bus=True,
        delete_bus=True,
        create_schedule=True,
        update_schedule=True,
        delete_schedule=True,
    )
    guestRole = OperatorRole(
        company_id=company.id,
        name="Guest",
        manage_token=False,
        update_company=False,
        create_operator=False,
        update_operator=False,
        delete_operator=False,
        create_route=False,
        update_route=False,
        delete_route=False,
        create_bus=False,
        update_bus=False,
        delete_bus=False,
        create_schedule=False,
        update_schedule=False,
        delete_schedule=False,
    )
    session.add_all([admin, guest, adminRole, guestRole])
    session.flush()

    adminMapping = OperatorRoleMap(
        company_id=company.id, operator_id=admin.id, role_id=adminRole.id
    )
    guestMapping = OperatorRoleMap(
        company_id=company.id, operator_id=guest.id, role_id=guestRole.id
    )
    session.add_all([adminMapping, guestMapping])
    session.flush()

    landmark1 = Landmark(
        name="Varkala",
        boundary="POLYGON((76.7234906 8.7410323, \
                           76.7234906 8.7401323, \
                           76.7225906 8.7401323, \
                           76.7225906 8.7410323, \
                           76.7234906 8.7410323))",
    )
    landmark2 = Landmark(
        name="Edava",
        boundary="POLYGON((76.6962373 8.7642725, \
                           76.6962373 8.7633725, \
                           76.6953373 8.7633725, \
                           76.6953373 8.7642725, \
                           76.6962373 8.7642725))",
    )
    session.add_all([landmark1, landmark2])
    session.flush()

    busStop1 = BusStop(
        name="Varkala",
        landmark_id=landmark1.id,
        location="POINT(76.7230406 8.7405823)",
    )
    busStop2 = BusStop(
        name="Edava",
        landmark_id=landmark2.id,
        location="POINT(76.6957873 8.7638225)",
    )
    session.add_all([busStop1, busStop2])
    session.flush()

    fare = Fare(
        company_id=company.id,
        name="Test fare",
        scope=FareScope.GLOBAL,
        attributes={
            "df_version": 1,
            "ticket_types": [
                {"id": 1, "name": "Adult"},
                {"id": 2, "name": "Child"},
                {"id": 3, "name": "Student"},
            ],
            "currency_type": "INR",
            "distance_unit": "m",
            "extra": {},
        },
        function="""
        function getFare(ticket_type, distance, extra) {
            const base_fare_distance = 2.5;
            const base_fare = 10;
            const rate_per_km = 1;

            distance = distance / 1000;
            if (ticket_type == "Student") {
                if (distance <= 2.5) {
                    return 1;
                } else if (distance <= 7.5) {
                    return 2;
                } else if (distance <= 17.5) {
                    return 3;
                } else if (distance <= 27.5) {
                    return 4;
                } else {
                    return 5;
                }
            }

            if (ticket_type == "Adult") {
                if (distance <= base_fare_distance) {
                    return base_fare;
                } else {
                    return base_fare + ((distance - base_fare_distance) * rate_per_km);
                }
            }

            if (ticket_type == "Child") {
                if (distance <= base_fare_distance) {
                    return base_fare / 2;
                } else {
                    return (base_fare + ((distance - base_fare_distance) * rate_per_km)) / 2;
                }
            }
            return -1;
        }
        """,
    )
    session.add(fare)
    session.flush()

    route = Route(
        company_id=company.id,
        name="Varkala -> Edava",
        start_time=time(11, 0, 0),
    )
    session.add(route)
    session.flush()

    landmark1InRoute = LandmarkInRoute(
        company_id=company.id,
        route_id=route.id,
        landmark_id=landmark1.id,
        distance_from_start=0,
        arrival_delta=0,
        departure_delta=0,
    )
    landmark2InRoute = LandmarkInRoute(
        company_id=company.id,
        route_id=route.id,
        landmark_id=landmark2.id,
        distance_from_start=5000,
        arrival_delta=30,
        departure_delta=30,
    )
    session.add_all([landmark1InRoute, landmark2InRoute])
    session.flush()

    bus1 = Bus(
        company_id=company.id,
        registration_number="KL02WH3000",
        name="Test Bus 1",
        capacity=100,
        manufactured_on="2025-03-25T11:24:33.649Z",
        insurance_upto="2027-10-25T11:24:33.649Z",
        pollution_upto="2026-03-25T11:24:33.649Z",
        fitness_upto="2026-03-25T11:24:33.649Z",
        road_tax_upto="2026-03-25T11:24:33.649Z",
    )
    bus2 = Bus(
        company_id=company.id,
        registration_number="KL01HW2000",
        name="Test Bus 2",
        capacity=10,
        manufactured_on="2024-03-25T11:24:33.649Z",
        insurance_upto="2028-10-25T11:24:33.649Z",
        pollution_upto="2026-03-25T11:24:33.649Z",
        fitness_upto="2026-03-25T11:24:33.649Z",
        road_tax_upto="2026-03-25T11:24:33.649Z",
    )
    session.add_all([bus1, bus2])
    session.flush()

    schedule = Schedule(
        company_id=company.id,
        name="Test Schedule",
        route_id=route.id,
        bus_id=bus1.id,
        fare_id=fare.id,
        frequency=[
            Day.MONDAY,
            Day.TUESDAY,
            Day.WEDNESDAY,
            Day.THURSDAY,
            Day.FRIDAY,
            Day.SATURDAY,
            Day.SUNDAY,
        ],
    )
    session.add(schedule)
    session.flush()

    wallet2 = Wallet(
        name="Test business wallet",
        balance=0,
    )
    session.add(wallet2)
    session.flush()

    business = Business(
        name="Test business",
        contact_person="RedBus Pvt Ltd",
        phone_number="+911212121212",
        address="Test, Test, Test 695311",
        email_id="example@test.com",
        location="POINT(76.68899711264336 8.761725176790257)",
    )
    session.add(business)
    session.flush()

    businessWallet = BusinessWallet(
        business_id=business.id,
        wallet_id=wallet2.id,
    )
    session.add(businessWallet)
    session.flush()

    adminRole = VendorRole(
        name="Admin",
        business_id=business.id,
        manage_token=True,
        update_business=True,
        create_vendor=True,
        update_vendor=True,
        delete_vendor=True,
        create_role=True,
        update_role=True,
        delete_role=True,
    )
    guestRole = VendorRole(
        name="Guest",
        business_id=business.id,
        manage_token=False,
        update_business=False,
        create_vendor=False,
        update_vendor=False,
        delete_vendor=False,
        create_role=False,
        update_role=False,
        delete_role=False,
    )
    adminVendor = Vendor(
        business_id=business.id,
        username="admin",
        password=password,
        full_name="Admin Vendor",
    )
    guestVendor = Vendor(
        business_id=business.id,
        username="guest",
        password=password,
        full_name="Guest Vendor",
    )
    session.add_all(
        [
            adminRole,
            guestRole,
            adminVendor,
            guestVendor,
        ]
    )
    session.flush()

    adminRoleMap = VendorRoleMap(
        business_id=business.id,
        role_id=adminRole.id,
        vendor_id=adminVendor.id,
    )
    guestRoleMap = VendorRoleMap(
        business_id=business.id,
        role_id=guestRole.id,
        vendor_id=guestVendor.id,
    )
    session.add_all([adminRoleMap, guestRoleMap])
    session.flush()

    session.commit()
    print("* Test population completed")
    session.close()


# Setup database
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # remove tables
    parser.add_argument("-rm", action="store_true", help="remove tables")
    parser.add_argument("-cr", action="store_true", help="create tables")
    parser.add_argument("-init", action="store_true", help="initialize DB")
    parser.add_argument("-test", action="store_true", help="add test data")
    args = parser.parse_args()

    if args.cr:
        createTables()
    if args.init:
        initDB()
    if args.test:
        testDB()
    if args.rm:
        removeTables()
