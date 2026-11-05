/*
  Retail Store Smart Shelf - ESP32 + 3x HX711 Load Cells
  ------------------------------------------------------
  Reads three load cells (one per shelf) and publishes the live weight
  readings once every second to a public HiveMQ MQTT broker as JSON, e.g.

      {"shelf1":123.45,"shelf2":0.00,"shelf3":58.10,"ts":123456}

  Broker : broker.hivemq.com (HiveMQ public broker, port 1883, no credentials)
  Topic  : retailstore/<STORE_ID>/loadcell/data

  IMPORTANT: broker.hivemq.com is a shared PUBLIC broker used by developers
  worldwide. Anyone can publish/subscribe to any topic on it. Change
  STORE_ID below to something unique to your project so you don't collide
  with (or read data from) someone else's device. The Flask app's .env
  MQTT_TOPIC_PREFIX must be set to the exact same value.

  Required libraries (install via Arduino Library Manager):
    - HX711 by Bogdan Necula
    - PubSubClient by Nick O'Leary
    - ArduinoJson by Benoit Blanchon (v6+)
    - WiFi (bundled with ESP32 board package)
*/

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "HX711.h"

// ---------------------------------------------------------------------------
// WiFi credentials - EDIT THESE
// ---------------------------------------------------------------------------
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// ---------------------------------------------------------------------------
// MQTT (HiveMQ public broker, no credentials required) - EDIT STORE_ID
// ---------------------------------------------------------------------------
const char* MQTT_BROKER = "broker.hivemq.com";
const int   MQTT_PORT   = 1883;
const char* STORE_ID    = "retailstore_8f3k2";  // <-- make this unique, must match Flask .env

String MQTT_TOPIC     = String("retailstore/") + STORE_ID + "/loadcell/data";
String MQTT_CLIENT_ID = String("esp32-") + STORE_ID + "-" + String((uint32_t)ESP.getEfuseMac(), HEX);

WiFiClient   espClient;
PubSubClient mqttClient(espClient);

// ---------------------------------------------------------------------------
// HX711 wiring (unchanged from original sketch)
// ---------------------------------------------------------------------------
// HX711 #1 (Shelf 1)
#define DOUT1 4
#define CLK1  5
// HX711 #2 (Shelf 2)
#define DOUT2 22
#define CLK2  23
// HX711 #3 (Shelf 3)
#define DOUT3 18
#define CLK3  19

HX711 scale1;
HX711 scale2;
HX711 scale3;

// Calibration factors (adjust separately if needed)
float cal1 = -745.6;
float cal2 = -745.6;
float cal3 = -745.6;

// Fine calibration offset in grams, applied AFTER get_units() to correct a
// consistent bias measured with a known reference weight. Positive = the
// scale reads too HIGH by this much (subtract it); negative = the scale
// reads too LOW by this much (adding it back).
//   Shelf 1 read 3.5 g less   -> offset1 = -3.5
//   Shelf 2 read 4.9 g extra  -> offset2 =  4.9
//   Shelf 3 read 8.9 g less   -> offset3 = -8.9
// Re-measure with a known weight and adjust these if they drift over time.
float offset1 = -3.5;
float offset2 = 4.9;
float offset3 = -8.9;

// ---------------------------------------------------------------------------
// Publish timing
// ---------------------------------------------------------------------------
unsigned long lastPublish = 0;
const unsigned long PUBLISH_INTERVAL_MS = 1000; // every 1 second

// ---------------------------------------------------------------------------
void connectWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
    // Keep retrying indefinitely; reset after 30s of no luck to recover from bad state
    if (millis() - start > 30000) {
      Serial.println("\nWiFi connect timeout, retrying...");
      WiFi.disconnect(true);
      delay(500);
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
      start = millis();
    }
  }
  Serial.println("\nWiFi connected. IP address: ");
  Serial.println(WiFi.localIP());
}

void connectMQTT() {
  while (!mqttClient.connected()) {
    Serial.print("Connecting to HiveMQ broker as ");
    Serial.print(MQTT_CLIENT_ID);
    Serial.print(" ... ");
    if (mqttClient.connect(MQTT_CLIENT_ID.c_str())) {
      Serial.println("connected");
      Serial.print("Publishing to topic: ");
      Serial.println(MQTT_TOPIC);
    } else {
      Serial.print("failed, rc=");
      Serial.print(mqttClient.state());
      Serial.println(" retrying in 2s");
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);

  scale1.begin(DOUT1, CLK1);
  scale2.begin(DOUT2, CLK2);
  scale3.begin(DOUT3, CLK3);

  scale1.set_scale(cal1);
  scale2.set_scale(cal2);
  scale3.set_scale(cal3);

  Serial.println("Remove all weight...");
  delay(5000);

  scale1.tare(50);
  scale2.tare(50);
  scale3.tare(50);

  Serial.println("Scale Ready");

  connectWiFi();

  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setBufferSize(256);
  connectMQTT();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }
  if (!mqttClient.connected()) {
    connectMQTT();
  }
  mqttClient.loop();

  if (millis() - lastPublish >= PUBLISH_INTERVAL_MS) {
    lastPublish = millis();

    float weight1 = scale1.get_units(5) - offset1;
    float weight2 = scale2.get_units(5) - offset2;
    float weight3 = scale3.get_units(5) - offset3;

    // Remove small zero errors. This runs AFTER the offset correction above,
    // so an empty scale reports exactly 0 instead of leftover +/- offset.
    if (abs(weight1) < 10) weight1 = 0;
    if (abs(weight2) < 10) weight2 = 0;
    if (abs(weight3) < 10) weight3 = 0;

    StaticJsonDocument<200> doc;
    doc["shelf1"] = round(weight1 * 100) / 100.0;
    doc["shelf2"] = round(weight2 * 100) / 100.0;
    doc["shelf3"] = round(weight3 * 100) / 100.0;
    doc["ts"] = millis();

    char payload[200];
    size_t len = serializeJson(doc, payload);

    if (mqttClient.publish(MQTT_TOPIC.c_str(), payload, len)) {
      Serial.print("Published: ");
      Serial.println(payload);
    } else {
      Serial.println("MQTT publish failed");
    }
  }
}
