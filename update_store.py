with open('apps/api/app/services/store.py', 'r', encoding='utf-8') as f:
    content = f.read()

sql_add = """    def add(self, record):
        record.data = {**record.data, "owner_id": self.owner}
        self.session.add(record)

    def delete(self, record):
        self.session.delete(record)"""

content = content.replace("""    def add(self, record):
        record.data = {**record.data, "owner_id": self.owner}
        self.session.add(record)""", sql_add, 1)

mongo_init = """class MongoStore:
    def __init__(self, database, owner):
        self.database, self.owner, self.loaded, self.original = database, owner, {}, {}
        self.deleted = set()"""

content = content.replace("""class MongoStore:
    def __init__(self, database, owner):
        self.database, self.owner, self.loaded, self.original = database, owner, {}, {}""", mongo_init, 1)

mongo_add = """    def add(self, record):
        record.data = {**record.data, "owner_id": self.owner}
        self.loaded[record.id] = record

    def delete(self, record):
        self.deleted.add(record.id)
        self.loaded.pop(record.id, None)
        self.original.pop(record.id, None)"""

content = content.replace("""    def add(self, record):
        record.data = {**record.data, "owner_id": self.owner}
        self.loaded[record.id] = record""", mongo_add, 1)

mongo_commit = """    def commit(self):
        if self.deleted:
            with self.database.client.start_session() as session:
                with session.start_transaction():
                    for record_id in self.deleted:
                        self.database.records.delete_one({"_id": record_id, "owner_id": self.owner}, session=session)
            self.deleted.clear()

        # Atlas or a replica set is required. A conflict rolls back the entire workflow mutation."""

content = content.replace("""    def commit(self):
        # Atlas or a replica set is required. A conflict rolls back the entire workflow mutation.""", mongo_commit, 1)

mongo_rollback = """    def rollback(self):
        self.loaded.clear()
        self.original.clear()
        self.deleted.clear()"""

content = content.replace("""    def rollback(self):
        self.loaded.clear()
        self.original.clear()""", mongo_rollback, 1)

with open('apps/api/app/services/store.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Updated store.py successfully')
