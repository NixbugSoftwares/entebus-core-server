import argparse

from app.src import argon2
from app.src.enums import CompanyStatus
from app.src.db import (
    Executive,
    ExecutiveRole,
    ExecutiveRoleMap,
    Company,
    Operator,
    OperatorRole,
    OperatorRoleMap,
    Landmark,
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
        address="Edava, Thiruvananthapuram, Kerala",
        location="POINT(76.68899711264336 8.761725176790257)",
    )
    session.add(company)
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
    )
    guestRole = ExecutiveRole(
        name="Guest",
        manage_ex_token=False,
        manage_op_token=False,
        manage_ve_token=False,
        create_executive=False,
        update_executive=False,
        delete_executive=False,
    )
    session.add_all([admin, guest, adminRole, guestRole])
    session.flush()
    adminToRoleMapping = ExecutiveRoleMap(executive_id=admin.id, role_id=adminRole.id)
    guestToRoleMapping = ExecutiveRoleMap(executive_id=guest.id, role_id=guestRole.id)
    session.add_all([adminToRoleMapping, guestToRoleMapping])
    session.commit()
    print("* Initialization completed")
    session.close()


def testDB():
    session = sessionMaker()
    company = Company(
        name="Test company",
        status=CompanyStatus.VERIFIED,
        contact_person="Bismilla Motors(Edava)",
        phone_number="+911212121212",
        address="Edava, TVM",
        location="POINT(76.68899711264336 8.761725176790257)",
    )
    session.add(company)
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
        manage_bus=True,
        manage_role=True,
        manage_operator=True,
        manage_company=True,
        manage_route=True,
        manage_schedule=True,
        manage_fare=True,
        manage_duty=True,
        manage_service=True,
    )
    guestRole = OperatorRole(company_id=company.id, name="Guest")
    session.add_all([admin, guest, adminRole, guestRole])
    session.flush()
    adminMapping = OperatorRoleMap(
        company_id=company.id, operator_id=admin.id, role_id=adminRole.id
    )
    guestMapping = OperatorRoleMap(
        company_id=company.id, operator_id=guest.id, role_id=guestRole.id
    )
    session.add_all([adminMapping, guestMapping])
    session.commit()
    session = sessionMaker()
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
