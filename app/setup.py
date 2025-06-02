import argparse

from app.src.db import sessionMaker, engine, ORMbase


# ----------------------------------- Project Setup -------------------------------------------#
def removeTables():
    session = sessionMaker()
    ORMbase.metadata.drop_all(engine)
    session.commit()
    print("* All tables deleted")


def createTables():
    session = sessionMaker()
    ORMbase.metadata.create_all(engine)
    session.commit()
    print("* All tables created")


def initDB():
    print("* Initialization completed")


def testDB():
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
