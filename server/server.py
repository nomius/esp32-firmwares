#!/usr/bin/env python

import cherrypy
import json
import sqlite3
import time
import requests
from threading import Thread
from midea.client import client as midea_client
from midea.device import air_conditioning_device as ac

from api_data import *

current_tuya_token = ""

def iot_thread_function():
    while True:
        UpdateTuyaData()
        UpdateMideaACData("carrier")
        time.sleep(300)

def RenewTuyaToken(TUYACLOUDURL, TUYA_API_REGION, TUYA_USERNAME, TUYA_PASSWORD, TUYA_COUNTRY_CODE, TUYA_BIZ_TYPE, FROM):
    auth_response = requests.post((TUYACLOUDURL + "/homeassistant/auth.do").format(TUYA_API_REGION),
        data = {
            "userName": TUYA_USERNAME,
            "password": TUYA_PASSWORD,
            "countryCode": TUYA_COUNTRY_CODE,
            "bizType": TUYA_BIZ_TYPE,
            "from": FROM,
        },
    )
    auth_response = auth_response.json()
    err = auth_response.get('errorMsg')
    if err and err.startswith('you cannot auth exceed'):
        print("err: " + err)
        time.sleep(182)
        current_tuya_token = ""
        return RenewTuyaToken(TUYACLOUDURL, TUYA_API_REGION, TUYA_USERNAME, TUYA_PASSWORD, TUYA_COUNTRY_CODE, TUYA_BIZ_TYPE, FROM)
    else:
        return auth_response["access_token"]

def UpdateTuyaData():
    global current_tuya_token
    if current_tuya_token == "":
        current_tuya_token = RenewTuyaToken(TUYACLOUDURL, TUYA_API_REGION, TUYA_USERNAME, TUYA_PASSWORD, TUYA_COUNTRY_CODE, TUYA_BIZ_TYPE, FROM)
    header = { "name": "Discovery", "namespace": "discovery", "payloadVersion": 1 }
    payload = { "accessToken": current_tuya_token }
    data = { "header": header, "payload": payload }
    try:
        discovery_response = requests.post((TUYACLOUDURL + "/homeassistant/skill").format(TUYA_API_REGION), json=data)
        discovery_response = discovery_response.json()

        """Insert data into the SQLite database."""
        db = 'data.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        for device in discovery_response["payload"]["devices"]:
            event_type = device["dev_type"]
            if event_type == "climate":
                name = device["name"]
                state = device["data"]["current_temperature"] / 10
            elif event_type == "light":
                name = device["name"]
                state = device["data"]["state"]
            else:
                continue
            date_epoch = int(time.time())
            cursor.execute('INSERT INTO devices_data (DEVICE_NAME, EVENT_TYPE, DATE_EPOCH, STATE) VALUES (?, ?, ?, ?)', (name, event_type, date_epoch, state,))
        conn.commit()
        conn.close()
        return
    except Exception as e:
        print('An exception occurred: {}'.format(e))
        pass


def UpdateMideaACData(name):
    midea_client_mngr = midea_client(MIDEA_API_KEY, MIDEA_USERNAME, MIDEA_PASSWORD)
    midea_client_mngr.setup()

    try:
        device = midea_client_mngr.devices()[0]
        device.refresh()

        indoor_temperature = device.indoor_temperature
        outdoor_temperature = device.outdoor_temperature
        date_epoch = int(time.time())

        """Insert data into the SQLite database."""
        db = 'data.db'
        conn = sqlite3.connect(db)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO devices_data (DEVICE_NAME, EVENT_TYPE, DATE_EPOCH, STATE) VALUES (?, ?, ?, ?)', (name + "-indoor", "climate", date_epoch, indoor_temperature,))
        cursor.execute('INSERT INTO devices_data (DEVICE_NAME, EVENT_TYPE, DATE_EPOCH, STATE) VALUES (?, ?, ?, ?)', (name + "-outdoor", "climate", date_epoch, outdoor_temperature,))
        conn.commit()
        conn.close()
        return

    except Exception as e:
        print('An exception occurred: {}'.format(e))
        pass


def SendAlert():
    True

@cherrypy.expose
class EndpointRegister:
    def __init__(self):
        self.db = 'devices.db'
        self.create_table()

    def create_table(self):
        """Creates the table if it doesn't exist."""
        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ADDR TEXT,
                NAME TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def get_data(self, name):
        """Fetch data from the SQLite database."""
        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()
        cursor.execute('SELECT NAME, ADDR FROM devices WHERE NAME = ? ORDER BY id DESC LIMIT 1', (name,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"name": row[0], "addr" : row[1]}
        return {"message": "No data found"}

    # TODO: Add a control to check if name doesn't exist yet
    def set_data(self, addr, name):
        """Insert data into the SQLite database."""
        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO devices (ADDR, NAME) VALUES (?, ?)', (addr,name,))
        conn.commit()
        conn.close()
    
    def update_data(self, addr, name):
        """Update the most recent record in the database."""
        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()
        cursor.execute('UPDATE devices SET ADDR = ? WHERE NAME = ?', (addr, name,))
        conn.commit()
        conn.close()

    def delete_data(self, name):
        """Delete all records in the database."""
        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM devices WHERE NAME = ?', (name,))
        conn.commit()
        conn.close()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def GET(self, **params):
        name = params.get('name')
        return self.get_data(name)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def POST(self, **params):
        input_json = cherrypy.request.json
        addr = input_json['addr']
        name = input_json['name']
        if name and addr:
            self.set_data(addr, name)
            return {"status": "success", "message": "Data added"}
        return {"status": "error", "message": "No information provided"}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def PUT(self, **params):
        addr = input_json['addr']
        name = input_json['name']

        if name and addr:
            self.update_data(addr, name)
            return {"status": "success", "message": "Data updated"}
        return {"status": "error", "message": "No information provided"}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def DELETE(self, **params):
        name = params.get('name')
        self.delete_data(name)
        return {"status": "success", "message": "Data deleted"}

@cherrypy.expose
class EndpointData:
    def __init__(self):
        self.db = 'data.db'
        self.create_table()

    def create_table(self):
        """Creates the table if it doesn't exist."""
        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS devices_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                DEVICE_NAME TEXT,
                EVENT_TYPE TEXT,
                DATE_EPOCH INTEGER,
                STATE TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def get_data(self, device_name, event_type="%", date_from=-1, date_to=-1):
        """Fetch data from the SQLite database."""
        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()
        if date_from > 0 and date_to > 0:
            cursor.execute('SELECT DEVICE_NAME, EVENT_TYPE, DATE_EPOCH, STATE FROM devices_data WHERE DEVICE_NAME = ? AND EVENT_TYPE like ? AND DATE_EPOCH BETWEEN ? AND ? ORDER BY id DESC', (device_name, event_type, date_from, date_to,))
        elif date_from > 0:
            cursor.execute('SELECT DEVICE_NAME, EVENT_TYPE, DATE_EPOCH, STATE FROM devices_data WHERE DEVICE_NAME = ? AND EVENT_TYPE like ? AND DATE_EPOCH >= ? ORDER BY id DESC', (device_name, event_type, date_from,))
        elif date_to > 0:
            cursor.execute('SELECT DEVICE_NAME, EVENT_TYPE, DATE_EPOCH, STATE FROM devices_data WHERE DEVICE_NAME = ? AND EVENT_TYPE like ? AND DATE_EPOCH <= ? ORDER BY id DESC', (device_name, event_type, date_to,))
        else:
            cursor.execute('SELECT DEVICE_NAME, EVENT_TYPE, DATE_EPOCH, STATE FROM devices_data WHERE DEVICE_NAME = ? AND EVENT_TYPE like ? ORDER BY id DESC', (device_name,event_type,))

        rows = cursor.fetchall()
        conn.close()
        if rows:
            return ( [dict(ix) for ix in rows] )
        return {"message": "No data found"}

    def set_data(self, device_name, event_type, state, date_epoch):
        """Insert data into the SQLite database."""
        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO devices_data (DEVICE_NAME, EVENT_TYPE, DATE_EPOCH, STATE) VALUES (?, ?, ?, ?)', (device_name, event_type, date_epoch, state,))
        conn.commit()
        conn.close()
    
    # I don't find this very useful for now... But let's implement this anyways.
    def update_data(self, device_name, event_type, date_epoch, state):
        """Update the most recent record in the database."""
        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()
        cursor.execute('UPDATE devices_data SET STATE = ?, EVENT_TYPE = ? WHERE DEVICE_NAME = ? AND DATE_EPOCH = ?', (state, event_type, device_name, date_epoch,))
        conn.commit()
        conn.close()

    def delete_data(self, device_name, event_type="%", date_from=-1, date_to=-1):
        """Delete all records in the database."""
        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()

        if date_from > 0 and date_to > 0:
            cursor.execute('DELETE FROM devices_data WHERE DEVICE_NAME = ? AND EVENT_TYPE like ? AND DATE_EPOCH BETWEEN ? AND ?', (device_name, event_type, date_from, date_to,))
        elif date_from > 0:
            cursor.execute('DELETE FROM devices_data WHERE DEVICE_NAME = ? AND EVENT_TYPE like ? AND DATE_EPOCH >= ?', (device_name, event_type, date_from,))
        elif date_to > 0:
            cursor.execute('DELETE FROM devices_data WHERE DEVICE_NAME = ? AND EVENT_TYPE like ? AND DATE_EPOCH <= ?', (device_name, event_type, date_to,))
        else:
            cursor.execute('DELETE FROM devices_data WHERE DEVICE_NAME = ? AND EVENT_TYPE like ?', (device_name,event_type,))
        conn.commit()
        conn.close()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def GET(self, **params):
        device_name = params.get('device_name')
        date_from = params.get('date_from')
        date_to = params.get('date_to')
        if date_from == "": date_from = None
        if date_to == "": date_to = None
        return self.get_data(device_name, date_from, date_to)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def POST(self, **params):
        input_json = cherrypy.request.json
        device_name = input_json['device_name']
        date_epoch = int(time.time())
        state = input_json['state']
        alert = input_json['alert']
        if alert != "" and alert != None:
            SendAlert()
        if device_name and state:
            self.set_data(device_name, state, date_epoch)
            return json.dumps({"status": "success", "message": "Data added"})
        return {"status": "error", "message": "No information provided"}


    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def PUT(self, **params):
        input_json = cherrypy.request.json
        device_name = input_json['device_name']
        date_epoch = int(time.time())
        state = input_json['state']

        if device_name and state:
            self.update_data(device_name, date_epoch, state)
            return {"status": "success", "message": "Data updated"}
        return {"status": "error", "message": "No information provided"}

    @cherrypy.expose
    def DELETE(self):
        device_name = params.get('device_name')
        date_from = params.get('date_from')
        date_to = params.get('date_to')
        if date_from == "": date_from = None
        if date_to == "": date_to = None

        self.delete_data(device_name, date_from, date_to)
        return json.dumps({"status": "success", "message": "Data deleted"})

# Set up the CherryPy application and add routes
class Root:
    er = EndpointRegister()
    ed = EndpointData()

    @cherrypy.expose
    def index(self):
        return "Welcome to the CherryPy API with SQLite backend example!"

# Configuring CherryPy
if __name__ == '__main__':

    config = {
        '/': { 'request.dispatch': cherrypy.dispatch.MethodDispatcher() }
    }

    time.sleep(1)
    thread = Thread(target = iot_thread_function, args = ())
    thread.start()

    cherrypy.tree.mount(Root(), "/", config)
    cherrypy.tree.mount(EndpointRegister(), "/api/register", config)
    cherrypy.tree.mount(EndpointData(), "/api/endpoint", config)

    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',  # Accept all incoming connections
        'server.socket_port': 8080        # Port to listen on
    })

    cherrypy.engine.start()
    cherrypy.engine.block()
    thread.join()

