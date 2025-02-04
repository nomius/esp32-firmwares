#!/usr/bin/env python

import sqlite3

class datalayer(object):
    _cur = None;
    _conn = None
    DB_NAME = "data.db"

    def __new__(cls, *args, **kwargs):
        if not cls._cur:
            cls._conn = sqlite3.connect(cls.DB_NAME, check_same_thread=False);
            cls._cur = cls._conn.cursor();
            cls._create_tables(cls)
        return cls

    def _create_tables(self):
        """Creates the table if it doesn't exist."""
        self._cur.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ADDR TEXT,
                NAME TEXT
            )
        ''')
        self._cur.execute('''
            CREATE TABLE IF NOT EXISTS devices_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                DEVICE_NAME TEXT,
                EVENT_TYPE TEXT,
                DATE_EPOCH INTEGER,
                STATE TEXT
            )
        ''')
        self._conn.commit()

db = datalayer();
cur = db._cur
conn = db._conn

