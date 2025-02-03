# esp32-firmwares

This is a generic firmware with support for esp32
This firmware support the following sensors:
* DS18B20 Temperature sensor.
* DHT 11, 21 and 22 sensors Temperature & Humidity.
* SR501 Movement sensor with led flash when movement status changes.

It also supports:
* Wifi.
* HTTP client, so SR501 can update movement detection through a POST request to an application server in json.
* HTTP server so the DHT and DS18B20 can provide temperature and humidity through a web browser i the form of HTML or json.
* * The code uses http client also to register esp32 endpoints to an application server (more on this in the future), so you don't need to look at the serial console to find out the ESP32 IP address.
