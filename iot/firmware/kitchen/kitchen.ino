#include "config.h"
#ifdef TEAFLOW_KITCHEN
#include "KitchenApp.h"
void setup() { kitchenSetup(); }
void loop() { kitchenLoop(); }
#else
// Legacy Serial prototype for Arduino IDE, without the ES3C35P build flag.
#include <TeaFlowClient.h>
#include <Preferences.h>

TeaFlowClient api(API_BASE, DEVICE_KEY);
Preferences settings;
JsonDocument state;
String lastEvent;
String serialLine;
unsigned long lastRefresh = 0;

void handleCommand(String command) {
  command.trim();
  int id = 0;
  bool preparing = sscanf(command.c_str(), "prepare %d", &id) == 1;
  if (!preparing && sscanf(command.c_str(), "ready %d", &id) != 1) return;
  JsonDocument result;
  if (api.post("/orders/" + String(id) + "/status", preparing ? "{\"status\":\"preparing\"}" : "{\"status\":\"ready\"}", result)) {
    Serial.printf("CONFIRMED #%d %s\n", id, result["status"].as<const char*>());
  } else Serial.println(api.error + " - refresh before continuing");
}

void setup() {
  Serial.begin(115200);
  settings.begin("teaflow", false);
  lastEvent = settings.getString("paid-event", "");
  if (BUZZER_PIN >= 0) { pinMode(BUZZER_PIN, OUTPUT); digitalWrite(BUZZER_PIN, LOW); }
  WiFi.mode(WIFI_STA); WiFi.setAutoReconnect(true); WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.println("TeaFlow kitchen prototype. Commands: prepare ID | ready ID");
}
void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') { handleCommand(serialLine); serialLine = ""; }
    else if (c != '\r' && serialLine.length() < 100) serialLine += c;
  }
  if (millis() - lastRefresh >= 3000) {
    lastRefresh = millis();
    if (!api.get("/iot/state", state)) { Serial.println(api.error + " - displayed state is outdated"); return; }
    if (!state["orders"].is<JsonArray>()) { Serial.println("Invalid state - displayed data is outdated"); return; }
    String event = state["event_id"] | "";
    if (event != lastEvent) {
      if (state["orders"].size() > 0 && BUZZER_PIN >= 0) {
        digitalWrite(BUZZER_PIN, HIGH); delay(150); digitalWrite(BUZZER_PIN, LOW);
      }
      lastEvent = event; settings.putString("paid-event", event);
    }
    printQueue(state);
  }
}
#endif
