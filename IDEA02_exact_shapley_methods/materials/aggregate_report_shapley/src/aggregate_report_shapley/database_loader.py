from __future__ import annotations

import duckdb

from .d1 import D1_RECORDS


def create_d1_database(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE OR REPLACE TABLE Region(region_id VARCHAR PRIMARY KEY);
        CREATE OR REPLACE TABLE City(
            city_id VARCHAR PRIMARY KEY,
            region_id VARCHAR NOT NULL REFERENCES Region(region_id)
        );
        CREATE OR REPLACE TABLE Category(category_id VARCHAR PRIMARY KEY);
        CREATE OR REPLACE TABLE Fact(
            player_index INTEGER PRIMARY KEY,
            record_id VARCHAR UNIQUE NOT NULL,
            city_id VARCHAR NOT NULL REFERENCES City(city_id),
            category_id VARCHAR NOT NULL REFERENCES Category(category_id),
            amount INTEGER NOT NULL
        );
        """
    )
    connection.executemany("INSERT INTO Region VALUES (?)", [("S",), ("L",)])
    connection.executemany(
        "INSERT INTO City VALUES (?, ?)",
        [("S1", "S"), ("S2", "S"), ("L1", "L"), ("L2", "L")],
    )
    connection.executemany("INSERT INTO Category VALUES (?)", [("X",), ("Y",)])
    connection.executemany(
        "INSERT INTO Fact VALUES (?, ?, ?, ?, ?)",
        [
            (
                record.player_index,
                record.record_id,
                record.city_id,
                record.category_id,
                record.amount,
            )
            for record in D1_RECORDS
        ],
    )

