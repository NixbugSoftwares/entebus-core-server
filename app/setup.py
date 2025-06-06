import argparse

from app.src import argon2
from app.src.db import (
    Executive,
    ExecutiveRole,
    ExecutiveRoleMap,
    Business,
    Vendor,
    VendorRole,
    VendorRoleMap,
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
    password = argon2.makePassword("password")
    business = Business(
        name="Test Business",
        contact_person="John Doe",
        phone="+911234567890",
        email="testbusiness@gmail.com",
    )
    session.add(business)
    session.flush()
    adminRole = VendorRole(
        name="Admin",
        business_id=business.id,
        manage_token=True,
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
    session.commit()
    print("* Test population completed")


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
