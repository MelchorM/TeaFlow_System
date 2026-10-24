#pragma once
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <esp_random.h>

inline String newRequestKey() {
  uint8_t bytes[16];
  esp_fill_random(bytes, sizeof(bytes));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  char key[37];
  snprintf(key, sizeof(key), "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
    bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], bytes[6], bytes[7],
    bytes[8], bytes[9], bytes[10], bytes[11], bytes[12], bytes[13], bytes[14], bytes[15]);
  return String(key);
}

class TeaFlowClient {
 public:
  TeaFlowClient(const char* base, const char* key) : base_(base), key_(key) {}
  bool fresh = false;
  int lastStatus = 0;
  String error;
  void setBase(const String& base) { base_ = base; }
  void setOperatorToken(const String& token) { operatorToken_ = token; }
  bool get(const char* path, JsonDocument& output) { return send(path, "", output, false); }
  bool post(const String& path, const String& body, JsonDocument& output) { return send(path.c_str(), body, output, true); }
 private:
  String base_;
  const char* key_;
  String operatorToken_;
  bool send(const char* path, const String& body, JsonDocument& output, bool post) {
    fresh = false;
    lastStatus = 0;
    if (WiFi.status() != WL_CONNECTED) { error = "OFFLINE - action not confirmed"; WiFi.reconnect(); return false; }
    WiFiClient client;
    HTTPClient http;
    if (!http.begin(client, String(base_) + path)) { error = "Server connection failed"; return false; }
    http.setConnectTimeout(1000);
    http.setTimeout(3000);
    // HTTP/1.0 avoids chunked encoding so large queues can be parsed directly
    // into the caller's JSON allocator without a second String in internal RAM.
    http.useHTTP10(true);
    http.addHeader("X-Device-Key", key_);
    if (!operatorToken_.isEmpty()) http.addHeader("X-Operator-Token", operatorToken_);
    http.addHeader("Content-Type", "application/json");
    lastStatus = post ? http.POST(body) : http.GET();
    if (lastStatus < 200 || lastStatus >= 300) {
      String response = lastStatus > 0 ? http.getString() : "";
      http.end();
      JsonDocument detail;
      deserializeJson(detail, response);
      error = "SYNC FAILED (" + String(lastStatus) + "): " + (detail["message"].is<const char*>() ? detail["message"].as<String>() : "Server request failed.");
      return false;
    }
    DeserializationError parseError = deserializeJson(output, http.getStream());
    http.end();
    if (parseError || output.overflowed()) { error = "Invalid JSON - action not confirmed"; return false; }
    fresh = true;
    error = "";
    return true;
  }
};

inline void printQueue(JsonDocument& state) {
  for (JsonObject order : state["orders"].as<JsonArray>()) {
    Serial.printf("#%d | %s | %s\n", order["id"].as<int>(), order["customer_name"].as<const char*>(), order["status"].as<const char*>());
    for (JsonObject item : order["items"].as<JsonArray>()) {
      Serial.printf("  %d x %s | %s | sugar %d%% | %s ice\n", item["quantity"].as<int>(), item["product_name"].as<const char*>(), item["size"].as<const char*>(), item["sugar"].as<int>(), item["ice"].as<const char*>());
      for (JsonObject topping : item["addons"].as<JsonArray>()) Serial.printf("    + %s\n", topping["name"].as<const char*>());
    }
  }
  if (state["low_stock"] | false) Serial.println("LOW STOCK - see low_stock_items");
}
