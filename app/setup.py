import argparse
from http import HTTPStatus
from requests import post
from datetime import datetime, timedelta

from app.src import argon2
from app.src.enums import CompanyStatus, Day
from app.src.minio import createBucket, deleteBucket
from app.src.constants import (
    EXECUTIVE_PICTURES,
    OPERATOR_PICTURES,
    VENDOR_PICTURES,
    BUS_PICTURES,
    BUS_STOP_PICTURES,
)
from app.src.urls import (
    URL_EXECUTIVE_TOKEN,
    URL_LANDMARK,
    URL_BUS_STOP,
    URL_OPERATOR_ACCOUNT,
    URL_OPERATOR_ROLE,
    URL_OPERATOR_ROLE_MAP,
    URL_COMPANY,
    URL_BUSINESS,
    URL_ROUTE,
    URL_LANDMARK_IN_ROUTE,
    URL_BUS,
    URL_SCHEDULE,
    URL_FARE,
    URL_DUTY,
    URL_VENDOR_ROLE,
    URL_VENDOR_ROLE_MAP,
    URL_SERVICE,
    URL_VENDOR_ACCOUNT,
)
from app.src.db import (
    Executive,
    ExecutiveRole,
    ExecutiveRoleMap,
    Company,
    Wallet,
    CompanyWallet,
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
    deleteBucket(EXECUTIVE_PICTURES)
    deleteBucket(OPERATOR_PICTURES)
    deleteBucket(VENDOR_PICTURES)
    deleteBucket(BUS_PICTURES)
    deleteBucket(BUS_STOP_PICTURES)
    print("* All buckets deleted")
    session.close()


def createTables():
    session = sessionMaker()
    ORMbase.metadata.create_all(engine)
    session.commit()
    print("* All tables created")
    createBucket(EXECUTIVE_PICTURES)
    createBucket(OPERATOR_PICTURES)
    createBucket(VENDOR_PICTURES)
    createBucket(BUS_PICTURES)
    createBucket(BUS_STOP_PICTURES)
    print("* All buckets created")
    session.close()


def initDB():
    session = sessionMaker()
    companyWallet = Wallet(
        name="Nixbug company wallet",
        balance=0,
    )
    session.add(companyWallet)
    session.flush()

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

    companyWalletMapping = CompanyWallet(
        company_id=company.id,
        wallet_id=companyWallet.id,
    )
    session.add(companyWalletMapping)
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
        create_service=True,
        update_service=True,
        delete_service=True,
        create_fare=True,
        update_fare=True,
        delete_fare=True,
        create_duty=True,
        update_duty=True,
        delete_duty=True,
        create_ex_role=True,
        update_ex_role=True,
        delete_ex_role=True,
        create_op_role=True,
        update_op_role=True,
        delete_op_role=True,
        create_ve_role=True,
        update_ve_role=True,
        delete_ve_role=True,
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
        create_service=False,
        update_service=False,
        delete_service=False,
        create_fare=False,
        update_fare=False,
        delete_fare=False,
        create_duty=False,
        update_duty=False,
        delete_duty=False,
        create_ex_role=False,
        update_ex_role=False,
        delete_ex_role=False,
        create_op_role=False,
        update_op_role=False,
        delete_op_role=False,
        create_ve_role=False,
        update_ve_role=False,
        delete_ve_role=False,
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


def POST(URL: str, header: dict = {}, status_code: int = HTTPStatus.CREATED, **kwargs):
    response = post(URL, headers=header, **kwargs)
    if response.status_code != status_code:
        assert response.status_code == status_code
    else:
        return response


def testDB():
    # Base URL
    BASE_URL = "http://127.0.0.1:8080//executive"

    # Create Executive Token
    credentials = {"username": "admin", "password": "password"}
    response = POST(
        (BASE_URL + URL_EXECUTIVE_TOKEN),
        data=credentials,
        status_code=HTTPStatus.CREATED,
    )
    if response.status_code == HTTPStatus.CREATED:
        print("* Created token for admin")
    accessToken = {"Authorization": f"Bearer {response.json()['access_token']}"}

    # Create Company
    companyData = {
        "name": "Test company",
        "status": CompanyStatus.VERIFIED,
        "contact_person": "Bismilla Motors(Edava)",
        "phone_number": "+911212121212",
        "address": "Test, Test, Test 695311",
        "email_id": "example@test.com",
        "location": "POINT(76.68899711264336 8.761725176790257)",
    }
    company = POST(
        (BASE_URL + URL_COMPANY),
        header=accessToken,
        data=companyData,
        status_code=HTTPStatus.CREATED,
    )
    if response.status_code == HTTPStatus.CREATED:
        print("* Created company")

    # Create Operator accounts
    adminData = {
        "company_id": company.json()["id"],
        "username": "admin",
        "password": "password",
        "full_name": "Entebus Operator",
    }
    guestData = {
        "company_id": company.json()["id"],
        "username": "guest",
        "password": "password",
        "full_name": "Entebus Conductor",
    }
    admin = POST(
        (BASE_URL + URL_OPERATOR_ACCOUNT),
        header=accessToken,
        data=adminData,
        status_code=HTTPStatus.CREATED,
    )
    guest = POST(
        (BASE_URL + URL_OPERATOR_ACCOUNT),
        header=accessToken,
        data=guestData,
        status_code=HTTPStatus.CREATED,
    )
    if response.status_code == HTTPStatus.CREATED:
        print("* Created operator accounts")

    # Create Operator roles
    adminRoleData = {
        "company_id": company.json()["id"],
        "name": "Admin",
        "manage_token": True,
        "update_company": True,
        "create_operator": True,
        "update_operator": True,
        "delete_operator": True,
        "create_route": True,
        "update_route": True,
        "delete_route": True,
        "create_bus": True,
        "update_bus": True,
        "delete_bus": True,
        "create_schedule": True,
        "update_schedule": True,
        "delete_schedule": True,
        "create_service": True,
        "update_service": True,
        "delete_service": True,
        "create_fare": True,
        "update_fare": True,
        "delete_fare": True,
        "create_duty": True,
        "update_duty": True,
        "delete_duty": True,
        "create_role": True,
        "update_role": True,
        "delete_role": True,
    }
    guestRoleData = {
        "company_id": company.json()["id"],
        "name": "Guest",
        "manage_token": False,
        "update_company": False,
        "create_operator": False,
        "update_operator": False,
        "delete_operator": False,
        "create_route": False,
        "update_route": False,
        "delete_route": False,
        "create_bus": False,
        "update_bus": False,
        "delete_bus": False,
        "create_schedule": False,
        "update_schedule": False,
        "delete_schedule": False,
        "create_service": False,
        "update_service": False,
        "delete_service": False,
        "create_fare": False,
        "update_fare": False,
        "delete_fare": False,
        "create_duty": False,
        "update_duty": False,
        "delete_duty": False,
        "create_role": False,
        "update_role": False,
        "delete_role": False,
    }
    adminRole = POST(
        (BASE_URL + URL_OPERATOR_ROLE),
        header=accessToken,
        data=adminRoleData,
        status_code=HTTPStatus.CREATED,
    )
    guestRole = POST(
        (BASE_URL + URL_OPERATOR_ROLE),
        header=accessToken,
        data=guestRoleData,
        status_code=HTTPStatus.CREATED,
    )
    if response.status_code == HTTPStatus.CREATED:
        print("* Created operator Roles")

    # Create Operator Roles Mapping
    adminMappingData = {
        "operator_id": admin.json()["id"],
        "role_id": adminRole.json()["id"],
        "company_id": company.json()["id"],
    }
    guestMappingData = {
        "operator_id": guest.json()["id"],
        "role_id": guestRole.json()["id"],
        "company_id": company.json()["id"],
    }
    POST(
        (BASE_URL + URL_OPERATOR_ROLE_MAP),
        header=accessToken,
        data=adminMappingData,
        status_code=HTTPStatus.CREATED,
    )
    POST(
        (BASE_URL + URL_OPERATOR_ROLE_MAP),
        header=accessToken,
        data=guestMappingData,
        status_code=HTTPStatus.CREATED,
    )
    if response.status_code == HTTPStatus.CREATED:
        print("* Created operator Role Mappings")

    # Create Landmarks
    landmark1Data = {
        "name": "Varkala",
        "boundary": "POLYGON((76.7234906 8.7410323, 76.7234906 8.7401323, 76.7225906 8.7401323, 76.7225906 8.7410323, 76.7234906 8.7410323))",
    }
    landmark2Data = {
        "name": "Edava",
        "boundary": "POLYGON((76.6962373 8.7642725, 76.6962373 8.7633725, 76.6953373 8.7633725, 76.6953373 8.7642725, 76.6962373 8.7642725))",
    }
    landmark1 = POST(
        (BASE_URL + URL_LANDMARK),
        header=accessToken,
        data=landmark1Data,
        status_code=HTTPStatus.CREATED,
    )
    landmark2 = POST(
        (BASE_URL + URL_LANDMARK),
        header=accessToken,
        data=landmark2Data,
        status_code=HTTPStatus.CREATED,
    )
    if response.status_code == HTTPStatus.CREATED:
        print("* Created landmarks")

    # Create Bus Stop
    busStop1Data = {
        "name": "Varkala",
        "landmark_id": landmark1.json()["id"],
        "location": "POINT(76.7230406 8.7405823)",
    }
    busStop2Data = {
        "name": "Edava",
        "landmark_id": landmark2.json()["id"],
        "location": "POINT(76.6957873 8.7638225)",
    }
    POST(
        (BASE_URL + URL_BUS_STOP),
        header=accessToken,
        data=busStop1Data,
        status_code=HTTPStatus.CREATED,
    )
    POST(
        (BASE_URL + URL_BUS_STOP),
        header=accessToken,
        data=busStop2Data,
        status_code=HTTPStatus.CREATED,
    )
    if response.status_code == HTTPStatus.CREATED:
        print("* Created bus stops")

    # Create Route
    routeData = {
        "company_id": company.json()["id"],
        "name": "Varkala -> Edava",
        "start_time": (datetime.now() + timedelta(minutes=5)).time().isoformat(),
    }
    route = POST(
        (BASE_URL + URL_ROUTE),
        header=accessToken,
        data=routeData,
        status_code=HTTPStatus.CREATED,
    )
    if response.status_code == HTTPStatus.CREATED:
        print("* Created route")

    #  Create Landmarks in Route
    landmark1InRouteData = {
        "route_id": route.json()["id"],
        "landmark_id": landmark1.json()["id"],
        "distance_from_start": 0,
        "arrival_delta": 0,
        "departure_delta": 0,
    }
    landmark2InRouteData = {
        "route_id": route.json()["id"],
        "landmark_id": landmark2.json()["id"],
        "distance_from_start": 5000,
        "arrival_delta": 30,
        "departure_delta": 30,
    }
    POST(
        (BASE_URL + URL_LANDMARK_IN_ROUTE),
        header=accessToken,
        data=landmark1InRouteData,
        status_code=HTTPStatus.CREATED,
    )
    POST(
        (BASE_URL + URL_LANDMARK_IN_ROUTE),
        header=accessToken,
        data=landmark2InRouteData,
        status_code=HTTPStatus.CREATED,
    )
    if response.status_code == HTTPStatus.CREATED:
        print("* Created landmarks in route")

    # Create Buses
    bus1Data = {
        "company_id": company.json()["id"],
        "registration_number": "KL02WH3000",
        "name": "Test Bus 1",
        "capacity": 100,
        "manufactured_on": "2025-03-25T11:24:33.649Z",
    }
    bus2Data = {
        "company_id": company.json()["id"],
        "registration_number": "KL01HW2000",
        "name": "Test Bus 2",
        "capacity": 10,
        "manufactured_on": "2024-03-25T11:24:33.649Z",
    }
    bus1 = POST(
        (BASE_URL + URL_BUS),
        header=accessToken,
        data=bus1Data,
        status_code=HTTPStatus.CREATED,
    )
    bus2 = POST(
        (BASE_URL + URL_BUS),
        header=accessToken,
        data=bus2Data,
        status_code=HTTPStatus.CREATED,
    )
    if response.status_code == HTTPStatus.CREATED:
        print("* Created buses")

    # Create Fare
    fareData = {
        "name": "Test fare",
        "attributes": {
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
        "function": """function getFare(ticket_type, distance, extra) {\n    const base_fare_distance = 2.5;\n    const base_fare = 10;\n    const rate_per_km = 1;\n\n    distance = distance / 1000;\n    if (ticket_type == \"Student\") {\n        if (distance <= 2.5) {\n            return 1;\n        } else if (distance <= 7.5) {\n            return 2;\n        } else if (distance <= 17.5) {\n            return 3;\n        } else if (distance <= 27.5) {\n            return 4;\n        } else {\n            return 5;\n        }\n    }\n\n    if (ticket_type == \"Adult\") {\n        if (distance <= base_fare_distance) {\n            return base_fare;\n        } else {\n            return base_fare + ((distance - base_fare_distance) * rate_per_km);\n        }\n    }\n\n    if (ticket_type == \"Child\") {\n        if (distance <= base_fare_distance) {\n            return base_fare / 2;\n        } else {\n            return (base_fare + ((distance - base_fare_distance) * rate_per_km)) / 2;\n        }\n    }\n    return -1;\n}""",
        "scope": 1,
    }
    fare = POST(
        (BASE_URL + URL_FARE),
        header=accessToken,
        json=fareData,
        status_code=HTTPStatus.CREATED,
    )
    if response.status_code == HTTPStatus.CREATED:
        print("* Created fare")

    # Create Schedule
    scheduleData = {
        "company_id": company.json()["id"],
        "name": "Test Schedule",
        "route_id": route.json()["id"],
        "bus_id": bus1.json()["id"],
        "fare_id": fare.json()["id"],
        "frequency": [
            Day.MONDAY,
            Day.TUESDAY,
            Day.WEDNESDAY,
            Day.THURSDAY,
            Day.FRIDAY,
            Day.SATURDAY,
            Day.SUNDAY,
        ],
    }
    POST(
        (BASE_URL + URL_SCHEDULE),
        header=accessToken,
        json=scheduleData,
        status_code=HTTPStatus.CREATED,
    )
    if response.status_code == HTTPStatus.CREATED:
        print("* Created schedule")

    # Create Service
    serviceData = {
        "company_id": company.json()["id"],
        "route": route.json()["id"],
        "fare": fare.json()["id"],
        "bus_id": bus2.json()["id"],
        "starting_at": (datetime.now() + timedelta(minutes=5)).isoformat(),
    }
    service = POST(
        (BASE_URL + URL_SERVICE),
        header=accessToken,
        data=serviceData,
        status_code=HTTPStatus.CREATED,
    )
    if response.status_code == HTTPStatus.CREATED:
        print("* Created service")

    # Create Duty
    dutyData = {
        "company_id": company.json()["id"],
        "operator_id": admin.json()["id"],
        "service_id": service.json()["id"],
    }
    POST(
        (BASE_URL + URL_DUTY),
        header=accessToken,
        data=dutyData,
        status_code=HTTPStatus.CREATED,
    )
    if response.status_code == HTTPStatus.CREATED:
        print("* Assigned duty")

    # Create Business
    businessData = {
        "name": "Test business",
        "contact_person": "RedBus Pvt Ltd",
        "phone_number": "+911212121212",
        "address": "Test, Test, Test 695311",
        "email_id": "example@test.com",
        "location": "POINT(76.68899711264336 8.761725176790257)",
    }
    business = POST(
        (BASE_URL + URL_BUSINESS),
        header=accessToken,
        data=businessData,
        status_code=HTTPStatus.CREATED,
    )
    if response.status_code == HTTPStatus.CREATED:
        print("* Created business")

    # Create Vendor Account
    vendorAdminData = {
        "business_id": business.json()["id"],
        "username": "admin",
        "password": "password",
        "full_name": "Admin Vendor",
    }
    vendorGuestData = {
        "business_id": business.json()["id"],
        "username": "guest",
        "password": "password",
        "full_name": "Guest Vendor",
    }
    vendorAdmin = POST(
        (BASE_URL + URL_VENDOR_ACCOUNT),
        header=accessToken,
        data=vendorAdminData,
        status_code=HTTPStatus.CREATED,
    )
    vendorGuest = POST(
        (BASE_URL + URL_VENDOR_ACCOUNT),
        header=accessToken,
        data=vendorGuestData,
        status_code=HTTPStatus.CREATED,
    )
    if response.status_code == HTTPStatus.CREATED:
        print("* Created vendor accounts")

    # Create Vendor Role
    vendorAdminRoleData = {
        "name": "Admin",
        "business_id": business.json()["id"],
        "manage_token": True,
        "update_business": True,
        "create_vendor": True,
        "update_vendor": True,
        "delete_vendor": True,
        "create_role": True,
        "update_role": True,
        "delete_role": True,
    }
    vendorGuestRoleData = {
        "name": "Guest",
        "business_id": business.json()["id"],
        "manage_token": False,
        "update_business": False,
        "create_vendor": False,
        "update_vendor": False,
        "delete_vendor": False,
        "create_role": False,
        "update_role": False,
        "delete_role": False,
    }
    vendorAdminRole = POST(
        (BASE_URL + URL_VENDOR_ROLE),
        header=accessToken,
        data=vendorAdminRoleData,
        status_code=HTTPStatus.CREATED,
    )
    vendorGuestRole = POST(
        (BASE_URL + URL_VENDOR_ROLE),
        header=accessToken,
        data=vendorGuestRoleData,
        status_code=HTTPStatus.CREATED,
    )
    if response.status_code == HTTPStatus.CREATED:
        print("* Created vendor Roles")

    # Vendor Role Map
    vendorAdminMapData = {
        "vendor_id": vendorAdmin.json()["id"],
        "role_id": vendorAdminRole.json()["id"],
        "business_id": business.json()["id"],
    }
    vendorGuestMapData = {
        "vendor_id": vendorGuest.json()["id"],
        "role_id": vendorGuestRole.json()["id"],
        "business_id": business.json()["id"],
    }
    POST(
        (BASE_URL + URL_VENDOR_ROLE_MAP),
        header=accessToken,
        data=vendorAdminMapData,
        status_code=HTTPStatus.CREATED,
    )
    POST(
        (BASE_URL + URL_VENDOR_ROLE_MAP),
        header=accessToken,
        data=vendorGuestMapData,
        status_code=HTTPStatus.CREATED,
    )
    if response.status_code == HTTPStatus.CREATED:
        print("* Created vendor Role Mappings")


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
