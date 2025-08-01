from dataclasses import dataclass
from datetime import timezone, datetime
import psycopg2


TABLE_NAME = "ffxiv_market_board_sales"

INSERT_ROW_QUERY = f"""
INSERT INTO {TABLE_NAME} (time, world_id, item_id, price, quantity, hq)
VALUES (%s, %s, %s, %s, %s, %s);
"""

CREATE_TABLE_QUERY = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    time TIMESTAMP NOT NULL,
    world_id SMALLINT NOT NULL,
    item_id INTEGER NOT NULL,
    price INTEGER NOT NULL,
    quantity SMALLINT NOT NULL,
    hq BOOLEAN NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_item_time ON {TABLE_NAME} (item_id, time DESC);
"""

HYPERTABLE_QUERY = f"""
SELECT create_hypertable('{TABLE_NAME}', 'time', if_not_exists => TRUE);
"""

BUFFER_SIZE = 100
row_buffer = []

@dataclass
class DbParameters:
    host: str
    port: int
    user: str
    password: str
    database_name: str
    def is_valid(self):
        return all([self.host, self.port, self.user, self.password, self.database_name])
    def as_dict(self):
        return {
            "dbname": self.database_name,
            "user": self.user,
            "password": self.password,
            "host": self.host,
            "port": self.port
        }


def initialize_database(db_params: DbParameters, use_timescale_db=False):
    with psycopg2.connect(**db_params.as_dict()) as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_QUERY)
            if use_timescale_db:
                cur.execute(HYPERTABLE_QUERY)


def db_insert_row(unix_time: int, world_id: int, item_id: int, price: int, quantity: int, hq: bool, db_params: DbParameters):
    global row_buffer
    time = datetime.fromtimestamp(unix_time, tz=timezone.utc)
    row_buffer.append((time, world_id, item_id, price, quantity, hq))
    if len(row_buffer) >= BUFFER_SIZE:
        db_flush_rows(db_params)


def db_flush_rows(db_params: DbParameters):
    global row_buffer
    if not row_buffer:
        return
    print("DATABASE: Writing row buffer to database.")
    with psycopg2.connect(**db_params.as_dict()) as conn:
        with conn.cursor() as cur:
            cur.executemany(INSERT_ROW_QUERY, row_buffer)
    row_buffer.clear()
