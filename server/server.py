#!/usr/bin/env python

import cherrypy
import json
import time
import requests
from threading import Thread

from datalayer import cur, conn

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
        for device in discovery_response["payload"]["devices"]:
            event_type = device["dev_type"]
            if event_type == "climate":
                name = device["name"]
                state = device["data"]["current_temperature"] / 10
            elif event_type == "light":
                name = device["name"]
                state = device["data"]["state"]
            elif event_type == "switch":
                name = device["name"]
                state = state = device["data"]["state"]
            else:
                continue
            date_epoch = int(time.time())
            source = "TUYA"
            # TODO: use the expand API to get the device addr https://developer.tuya.com/en/docs/cloud/62e69f6d81?id=Kb65exx1cc47b
            addr = "unknown"

            # Let's save this one into the devices list first
            cur.execute('SELECT NAME, ADDR, SOURCE FROM devices WHERE NAME = ? AND SOURCE = ? ORDER BY id DESC LIMIT 1', (name, source,))
            row = cur.fetchone()
            if row:
                cur.execute('UPDATE devices SET ADDR = ? WHERE NAME = ? AND SOURCE = ?', (addr, name, source,))
            else:
                cur.execute('INSERT INTO devices (NAME, ADDR, SOURCE) VALUES (?, ?, ?)', (name, addr, source,))

            # Let's save "the event"... I probably need to revisit this, specially for things that are not climate devices
            cur.execute('INSERT INTO DEVICES_DATA (DEVICE_NAME, EVENT_TYPE, DATE_EPOCH, STATE) VALUES (?, ?, ?, ?)', (name, event_type, date_epoch, state,))
            conn.commit()
        return
    except Exception as e:
        print('An exception occurred: {}'.format(e))
        pass


# Below function sucks...
# TODO: I should probably move to midea-beautiful-air library
def UpdateMideaACData(name):
    midea_client_mngr = midea_client(MIDEA_API_KEY, MIDEA_USERNAME, MIDEA_PASSWORD)
    midea_client_mngr.setup()

    try:
        device = midea_client_mngr.devices()[0]
        device.refresh()

        indoor_temperature = device.indoor_temperature
        outdoor_temperature = device.outdoor_temperature
        date_epoch = int(time.time())

        source = "Midea"
        addr = "unknown"

        # NOTE: These AC normally comes with two sensors, one for the indoor temperature and another one for the outdoor temperature.
        #       I'll base myself on this so I'll add two items to the devices sensors and two items to the device data... For now.
        # Let's save this one into the devices list first (indoor & outdoor)
        cur.execute('SELECT NAME, ADDR, SOURCE FROM devices WHERE NAME = ? AND SOURCE = ? ORDER BY id DESC LIMIT 1', (name + "-indoor", source,))
        row = cur.fetchone()
        if row:
            cur.execute('UPDATE devices SET ADDR = ? WHERE NAME = ? AND SOURCE = ?', (addr, name + "-indoor", source,))
        else:
            cur.execute('INSERT INTO devices (NAME, ADDR, SOURCE) VALUES (?, ?, ?)', (name + "-indoor", addr, source,))

        cur.execute('SELECT NAME, ADDR, SOURCE FROM devices WHERE NAME = ? AND SOURCE = ? ORDER BY id DESC LIMIT 1', (name + "-outdoor", source,))
        row = cur.fetchone()
        if row:
            cur.execute('UPDATE devices SET ADDR = ? WHERE NAME = ? AND SOURCE = ?', (addr, name + "-outdoor", source,))
        else:
            cur.execute('INSERT INTO devices (NAME, ADDR, SOURCE) VALUES (?, ?, ?)', (name + "-outdoor", addr, source,))

        # Let's save "the event"... I probably need to revisit this, as with the tuya one anyways
        cur.execute('INSERT INTO DEVICES_DATA (DEVICE_NAME, EVENT_TYPE, DATE_EPOCH, STATE) VALUES (?, ?, ?, ?)', (name + "-indoor", "climate", date_epoch, indoor_temperature,))
        cur.execute('INSERT INTO DEVICES_DATA (DEVICE_NAME, EVENT_TYPE, DATE_EPOCH, STATE) VALUES (?, ?, ?, ?)', (name + "-outdoor", "climate", date_epoch, outdoor_temperature,))
        conn.commit()
        return

    except Exception as e:
        print('An exception occurred: {}'.format(e))
        pass


def SendAlert():
    True

@cherrypy.expose
class EndpointRegister:

    def get_data(self, name, source):
        """Fetch data from the SQLite database."""
        if name and source:
            cur.execute('SELECT NAME, ADDR, SOURCE FROM devices WHERE NAME = ? AND SOURCE = ? ORDER BY id', (name, source,))
        elif name:
            cur.execute('SELECT NAME, ADDR, SOURCE FROM devices WHERE NAME = ? ORDER BY id', (name,))
        elif source:
            cur.execute('SELECT NAME, ADDR, SOURCE FROM devices WHERE SOURCE = ? ORDER BY id', (source,))
        else:
            cur.execute('SELECT NAME, ADDR, SOURCE FROM devices ORDER BY id', ())

        rows = cur.fetchall()
        if rows:
            ret_data = []
            for item in rows:
                ret_data.append({ "name" : item[0], "addr" : item[1], "source" : item[2]})
            return ret_data
        return {"message": "No data found"}

    def set_data(self, addr, name, source):
        """Insert data into the SQLite database."""
        ret = self.get_data(name, source)
        if not ret.get('name'):
            cur.execute('INSERT INTO devices (ADDR, NAME, SOURCE) VALUES (?, ?)', (addr, name, source,))
            conn.commit()
            return True
        else:
            return False
    
    def update_data(self, addr, name, source):
        """Update the most recent record in the database."""
        cur.execute('UPDATE devices SET ADDR = ? WHERE NAME = ? AND SOURCE = ?', (addr, name, source,))
        conn.commit()

    def delete_data(self, name, source):
        """Delete all records in the database."""
        cur.execute('DELETE FROM devices WHERE NAME = ? AND SOURCE = ?', (name, source,))
        conn.commit()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def GET(self, **params):
        name = params.get('name')
        source = params.get('source')
        return self.get_data(name, source)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def POST(self, **params):
        input_json = cherrypy.request.json
        addr = input_json['addr']
        name = input_json['name']
        source = input_json['source']
        if name and addr and source:
            if self.set_data(addr, name, source):
                cherrypy.response.status = 201
                return {"status": "success", "message": "Data added"}
            else:
                cherrypy.response.status = 200
                return {"status": "success", "message": "Device already registered"}
        return {"status": "error", "message": "No information provided"}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def PUT(self, **params):
        addr = input_json['addr']
        name = input_json['name']
        source = input_json['source']

        if name and addr and source:
            self.update_data(addr, name, source)
            return {"status": "success", "message": "Data updated"}
        return {"status": "error", "message": "No information provided"}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def DELETE(self, **params):
        name = params.get('name')
        source = params.get('source')
        self.delete_data(name, source)
        return {"status": "success", "message": "Data deleted"}

@cherrypy.expose
class EndpointData:

    def get_data(self, device_name, event_type="%", date_from=-1, date_to=-1):
        """Fetch data from the SQLite database."""
        if date_from > 0 and date_to > 0:
            cur.execute('SELECT DEVICE_NAME, EVENT_TYPE, DATE_EPOCH, STATE FROM devices_data WHERE DEVICE_NAME = ? AND EVENT_TYPE like ? AND DATE_EPOCH BETWEEN ? AND ? ORDER BY id DESC', (device_name, event_type, date_from, date_to,))
        elif date_from > 0:
            cur.execute('SELECT DEVICE_NAME, EVENT_TYPE, DATE_EPOCH, STATE FROM devices_data WHERE DEVICE_NAME = ? AND EVENT_TYPE like ? AND DATE_EPOCH >= ? ORDER BY id DESC', (device_name, event_type, date_from,))
        elif date_to > 0:
            cur.execute('SELECT DEVICE_NAME, EVENT_TYPE, DATE_EPOCH, STATE FROM devices_data WHERE DEVICE_NAME = ? AND EVENT_TYPE like ? AND DATE_EPOCH <= ? ORDER BY id DESC', (device_name, event_type, date_to,))
        else:
            cur.execute('SELECT DEVICE_NAME, EVENT_TYPE, DATE_EPOCH, STATE FROM devices_data WHERE DEVICE_NAME = ? AND EVENT_TYPE like ? ORDER BY id DESC', (device_name, event_type,))

        rows = cur.fetchall()
        if rows:
            ret_data = []
            for item in rows:
                ret_data.append({ "device_name" : item[0], "event_type" : item[1], "event_time" : item[2], "event_data" : item[3]})
            return ret_data
        return {"message": "No data found"}

    def set_data(self, device_name, event_type, state, date_epoch):
        """Insert data into the SQLite database."""
        cur.execute('INSERT INTO devices_data (DEVICE_NAME, EVENT_TYPE, DATE_EPOCH, STATE) VALUES (?, ?, ?, ?)', (device_name, event_type, date_epoch, state,))
        conn.commit()
    
    # I don't find this very useful for now... But let's implement this anyways.
    def update_data(self, device_name, event_type, date_epoch, state):
        """Update the most recent record in the database."""
        cur.execute('UPDATE devices_data SET STATE = ?, EVENT_TYPE = ? WHERE DEVICE_NAME = ? AND DATE_EPOCH = ?', (state, event_type, device_name, date_epoch,))
        conn.commit()

    def delete_data(self, device_name, event_type="%", date_from=-1, date_to=-1):
        """Delete all records in the database."""
        if date_from > 0 and date_to > 0:
            cur.execute('DELETE FROM devices_data WHERE DEVICE_NAME = ? AND EVENT_TYPE like ? AND DATE_EPOCH BETWEEN ? AND ?', (device_name, event_type, date_from, date_to,))
        elif date_from > 0:
            cur.execute('DELETE FROM devices_data WHERE DEVICE_NAME = ? AND EVENT_TYPE like ? AND DATE_EPOCH >= ?', (device_name, event_type, date_from,))
        elif date_to > 0:
            cur.execute('DELETE FROM devices_data WHERE DEVICE_NAME = ? AND EVENT_TYPE like ? AND DATE_EPOCH <= ?', (device_name, event_type, date_to,))
        else:
            cur.execute('DELETE FROM devices_data WHERE DEVICE_NAME = ? AND EVENT_TYPE like ?', (device_name,event_type,))
        conn.commit()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def GET(self, **params):
        device_name = params.get('device_name')
        event_type = params.get('event_type')
        date_from = params.get('date_from')
        date_to = params.get('date_to')
        if not date_from: date_from = -1
        if not date_to: date_to = -1
        if not event_type: event_type = '%'
        return self.get_data(device_name, event_type, date_from, date_to)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def POST(self, **params):
        input_json = cherrypy.request.json
        device_name = input_json['device_name']
        event_type = input_json['event_type']
        state = input_json['state']
        alert = input_json['alert']
        date_epoch = int(time.time())
        if alert != None:
            if alert == "True":
                SendAlert()
        if device_name and state:
            self.set_data(device_name, event_type, state, date_epoch)
            return json.dumps({"status": "success", "message": "Data added"})
        return {"status": "error", "message": "No information provided"}


    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def PUT(self, **params):
        input_json = cherrypy.request.json
        device_name = input_json['device_name']
        event_type = input_json['event_type']
        state = input_json['state']
        alert = input_json['alert']
        date_epoch = int(time.time())
        if alert != None:
            if alert == "True":
                SendAlert()

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
    # TODO: Handle better threading with cherrypy
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
    thread.interrupt()
    thread.join()
    conn.close()

