//#define DS18B20_SENSOR         /* Defines if should build code for the DS18B20 temperature sensor */
#define DHT_SENSOR             /* Defines if should build code for the DHT type temperature & humidity sensors */
#define SR501_SENSOR           /* Defines if should build code for the SR501 movement sensor */

#define WEB_SERVER             /* Defines if the code should build a web server, comment it out if not needed*/
#define HTTP_ENDPOINT_REGISTER /* Defines if should build code to register an HTTP endpoint. See function RegisterEndpoint */
#define HTTP_REPORTING_API     /* Defines if reporting API should be built. This doesn't cause anything but a bigger firmware */


/* TODO: I should fix this by instead of doing all this bunch of ifdefs within one file split into multiples */
/* Bah! Let's do that later */
#define JSON 1  /* See function SendJSON */
#define HTML 2  /* See function SendHTML */

#define WEB_RESPONSE JSON     /* Defines if the WEB_SERVER response should be either HTML or JSON */

#include <WiFi.h>

#ifdef WEB_SERVER
#include <WebServer.h>
#endif

#ifdef HTTP_ENDPOINT_REGISTER || HTTP_REPORTING_API
#include <HTTPClient.h>
#endif

#ifdef DS18B20
#include <OneWire.h>
#include <DallasTemperature.h>
#endif

#ifdef DHT_SENSOR
#include "DHTesp.h"
#endif
/* ESP32 nodemcu with 38 pins has LED_BUILTIN in 2, while ESP32 C3 Supermicro has it in 8 */
#define LED_BUILTIN 2

/* Update the below */
const char *ssid = "";          /* Wifi Access Point ESSID */
const char *password = "";      /* Wifi Access Point ESSID WPA2 password */
const char *hostname = "";      /* How you want the ESP32 to register as */
const char *servername = "";    /* When using HTTP_ENDPOINT_REGISTER or HTTP_REPORTING_API this is required, as it's the API/server endpoint */
const char *serverport = "80";  /* When using HTTP_ENDPOINT_REGISTER or HTTP_REPORTING_API this is required, as it's the API/server endpoint listening port*/

#ifdef WEB_SERVER
#define ROOT_CONNECT_HANDLER handle_OnConnect
#define NOT_FOUND_HANDLER handle_NotFound
#endif

#define DEBUG

#ifdef DEBUG
	#define DEBUG_PRINT(x) Serial.print(x)
	#define DEBUG_PRINTLN(x) Serial.println(x)
#else
	#define DEBUG_PRINT(x)
	#define DEBUG_PRINTLN(x)
#endif

#ifdef WEB_SERVER
WebServer server(80);
#endif

#ifdef SR501_SENSOR
const int sr501_sensor = 27; // GPIO where the SR501 data is connected to
int sr501_state = LOW;
#endif

#ifdef DS18B20_SENSOR
const int oneWireBus = 4;  // GPIO where the DS18B20 is connected to

// Setup a oneWire instance to communicate with any OneWire devices
OneWire oneWire(oneWireBus);

// Pass our oneWire reference to Dallas Temperature sensor
DallasTemperature DS18B20_sensors(&oneWire);
#endif

#ifdef DHT_SENSOR
#define DHTTYPE (DHTesp::DHT11)  // DHT 11
/*
#define DHTTYPE DHTesp::DHT21    // DHT 21 (AM2301)
#define DHTTYPE DHTesp::DHT22    // DHT 22 (AM2302), AM2321
*/
uint8_t pinDHT = 26;  // GPIO where the DHT data is connected to

DHTesp dht;
#endif

#ifdef HTTP_ENDPOINT_REGISTER
void RegisterEndpoint(String ip)
{
	HTTPClient httpc;
	DEBUG_PRINTLN("Registering " + String(hostname) + " as " + ip);
	String serverPath = "http://" + String(servername) + ":" + String(serverport) + "/api/register";
	uint8_t json_data[128];
	sprintf((char *)json_data, "{\n  \"addr\": \"%s\",\n  \"name\" :  \"%s\"\n}", hostname, ip);
	httpc.begin(serverPath.c_str());
	int httpResponseCode = httpc.POST(json_data, strlen((char *)json_data));
	if (httpResponseCode > 0) {
		DEBUG_PRINT("HTTP Response code: ");
		DEBUG_PRINT(httpResponseCode);
	}
	else {
		DEBUG_PRINTLN("Error code: ");
		DEBUG_PRINTLN(httpResponseCode);
	}
}

String IpAddressToString(const IPAddress &ipAddress) {
	return String(ipAddress[0]) + "." + String(ipAddress[1]) + "." + String(ipAddress[2]) + "." + String(ipAddress[3]);
}
#endif

void ConnectWifi(void)
{
	int tryDelay = 1000;
	int numberOfTries = 20;

	pinMode(LED_BUILTIN, OUTPUT);
	digitalWrite(LED_BUILTIN, HIGH);

	delay(1000);
	WiFi.disconnect(true);
 
restart:
	delay(1000);

	DEBUG_PRINTLN("Connecting to WiFi: " + String(ssid) + "...");
	delay(5000);

	WiFi.setHostname(hostname);
	WiFi.begin(ssid, password);

	delay(2000);

	while (true) {

		switch (WiFi.status()) {
			case WL_NO_SSID_AVAIL:
				DEBUG_PRINTLN("[WiFi] SSID not found");
				break;
			case WL_CONNECT_FAILED:
				Serial.print("[WiFi] Failed - WiFi not connected! Reason: ");
				break;
			case WL_CONNECTION_LOST:
				DEBUG_PRINTLN("[WiFi] Connection was lost");
				break;
			case WL_SCAN_COMPLETED:
				DEBUG_PRINTLN("[WiFi] Scan is completed");
				break;
			case WL_DISCONNECTED:
				DEBUG_PRINTLN("[WiFi] WiFi is disconnected");
				delay(2000);
				break;
			case WL_CONNECTED:
				digitalWrite(LED_BUILTIN, LOW);
				DEBUG_PRINTLN("[WiFi] WiFi is connected!");
				DEBUG_PRINT("[WiFi] IP address: ");
				DEBUG_PRINTLN(WiFi.localIP());

#ifdef HTTP_ENDPOINT_REGISTER
				RegisterEndpoint(IpAddressToString(WiFi.localIP()));
#endif
				return;
			default:
				DEBUG_PRINT("[WiFi] WiFi Status: ");
				DEBUG_PRINTLN(WiFi.status());
				break;
		}
		delay(tryDelay);

		if (numberOfTries <= 0) {
			DEBUG_PRINTLN("[WiFi] Failed to connect to WiFi!");
			/* Force stop trying to connect */
			WiFi.mode(WIFI_OFF);
			delay(5000);
			goto restart;
		}
		else {
			numberOfTries--;
		}
	}
}

#ifdef WEB_SERVER
void InitWebServer(void)
{
	server.on("/", ROOT_CONNECT_HANDLER);
	server.onNotFound(NOT_FOUND_HANDLER);
	server.begin();
	DEBUG_PRINTLN("HTTP server started");
}
#endif


#ifdef SR501_SENSOR
void InitSR501(void)
{
	pinMode(sr501_sensor, INPUT);
	DEBUG_PRINTLN("SR501 sensor initialized");
}
#endif

#ifdef DHT_SENSOR
void InitDHT(void)
{
	dht.setup(pinDHT, DHTTYPE);
	DEBUG_PRINTLN("DHT sensor initialized");
}
#endif

#ifdef DS18B20_SENSOR
void InitDS18B20(void)
{
	DS18B20_sensors.begin();
	DEBUG_PRINTLN("DS18B20 sensor initialized");
}
#endif

void setup() {
	Serial.begin(115200);
	ConnectWifi();

#ifdef WEB_SERVER
	InitWebServer();
#endif

#ifdef DS18B20_SENSOR
	InitDS18B20();
#endif

#ifdef DHT_SENSOR
	InitDHT();
#endif

#ifdef SR501_SENSOR
	InitSR501();
#endif
}

/*You should modify from below */
void loop() {
#ifdef SR501_SENSOR
	DetectSR501Movement();
#endif
#ifdef WEB_SERVER
	server.handleClient();
#endif
}

#ifdef HTTP_REPORTING_API
void ReportSensorStateChange(char *state)
{
	HTTPClient httpc;
	String serverPath = "http://" + String(servername) + ":" + String(serverport) + "/api/endpoint?device=" + String(hostname);
	uint8_t json_data[128];
	sprintf((char *)json_data, "{\n  \"device\": \"%s\",\n  \"state\" :  \"%s\"\n}", hostname, state);
	DEBUG_PRINTLN("Sending state to server:\n" + String((char*)json_data));
	httpc.begin(serverPath.c_str());
	int httpResponseCode = httpc.POST(json_data, strlen((char *)json_data));
	if (httpResponseCode > 0) {
		DEBUG_PRINT("HTTP Response code: ");
		DEBUG_PRINTLN(httpResponseCode);
	}
	else {
		DEBUG_PRINT("Error code: ");
		DEBUG_PRINTLN(httpResponseCode);
	}
}
#endif

#ifdef SR501_SENSOR
void DetectSR501Movement(void)
{
	int val;
	val = digitalRead(sr501_sensor);     // read sensor value
	if (val == HIGH) {                   // check if the sensor is HIGH
		digitalWrite(LED_BUILTIN, HIGH); // turn LED ON

		if (sr501_state == LOW) {
			DEBUG_PRINTLN("Motion detected!");
			sr501_state = HIGH; // update variable state to HIGH
			ReportSensorStateChange("Motion detected");
		}
	}
	else {
		digitalWrite(LED_BUILTIN, LOW); // turn LED OFF

		if (sr501_state == HIGH){
			DEBUG_PRINTLN("Motion stopped!");
			sr501_state = LOW; // update variable state to LOW
			ReportSensorStateChange("Motion stopped");
		}
	}
	delay(500);
}
#endif

#ifdef DS18B20_SENSOR
float ReadTempFromDS18B20(void)
{
	DS18B20_sensors.requestTemperatures();
	float temperatureC = DS18B20_sensors.getTempCByIndex(0);
	return temperatureC;
}
#endif

#ifdef WEB_SERVER
void handle_OnConnect() {
#if WEB_RESPONSE == HTML
	server.send(200, "text/html", SendHTML(""));
#elif WEB_RESPONSE == JSON
	server.send(200, "application/json", SendJSON(""));
#endif
}

void handle_NotFound() {
#if WEB_RESPONSE == HTML
	server.send(404, "text/plain", "Not found");
#elif WEB_RESPONSE == JSON
	server.send(404, "application/json", "{}");
#endif
}

// Generate the HTML content to display
String SendHTML(String something) {

#ifdef DS18B20_SENSOR
	float temperatureC = ReadTempFromDS18B20();
	DEBUG_PRINTLN("Temperature from DS18B20 (" + String(oneWireBus) + "): " + String(temperatureC));
#endif

#ifdef DHT_SENSOR
	TempAndHumidity data = dht.getTempAndHumidity();
	if (isnan(data.temperature) || isnan(data.humidity)) {
		DEBUG_PRINTLN("Failed to read from DHT sensor (" + String(pinDHT) + ")!");
	}
	else {
		DEBUG_PRINT("Temperature: ");
		DEBUG_PRINTLN(data.temperature);
		DEBUG_PRINT("Humidity: ");
		DEBUG_PRINTLN(data.humidity);
	}
#endif
	String ptr = "<!DOCTYPE html> <html>\n";
	ptr += "<head><meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0, user-scalable=no\">\n";
	ptr += "<title>Landing page... You should tweak this</title>\n";
	ptr += "<style>html { font-family: Helvetica; display: inline-block; margin: 0px auto; text-align: center;}\n";
	ptr += "body{margin-top: 50px;} h1 {color: #444444;margin: 50px auto 30px;}\n";
	ptr += "p {font-size: 24px;color: #444444;margin-bottom: 10px;}\n";
	ptr += "</style>\n";
	ptr += "</head>\n";
	ptr += "<body>\n";
	ptr += "<div id=\"webpage\">\n";
	ptr += "<h1>Landing page... You should tweak my response now</h1>\n";
	ptr += "</div>\n";
	ptr += "</body>\n";
	ptr += "</html>\n";
	return ptr;
}

String SendJSON(String something)
{
#ifdef DS18B20_SENSOR
	float temperatureC = ReadTempFromDS18B20();
#endif

#ifdef DHT_SENSOR
	TempAndHumidity data = dht.getTempAndHumidity();
	if (isnan(data.temperature) || isnan(data.humidity)) {
		DEBUG_PRINTLN("Failed to read from DHT sensor (" + String(pinDHT) + ")!");
	}
	else {
		DEBUG_PRINT("Temperature: ");
		DEBUG_PRINTLN(data.temperature);
		DEBUG_PRINT("Humidity: ");
		DEBUG_PRINTLN(data.humidity);
	}
#endif

	uint8_t json_data[128];
	sprintf((char *)json_data, "{\n  \"tweak\": \"%s\",\n  \"response\" :  \"%s\"\n}", "my", "now");
	return String((char *)json_data);
}
#endif
