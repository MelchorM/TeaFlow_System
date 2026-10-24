#pragma once
#include <TeaFlowClient.h>
#include <TeaFlowOrderWait.h>
#include <TeaFlowKitchenDisplay.h>
#include <TeaFlowTheme.h>
#include <TeaFlowScreenCapture.h>
#include <TeaFlowDeviceStatus.h>
#include <Preferences.h>
#include <utility>
#include "KitchenAudio.h"

struct KitchenJsonRam : ArduinoJson::Allocator {
  void* allocate(size_t n) override { return heap_caps_malloc(n, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT); }
  void deallocate(void* p) override { heap_caps_free(p); }
  void* reallocate(void* p, size_t n) override { return heap_caps_realloc(p, n, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT); }
} kitchenJsonRam;
TeaFlowKitchenDisplay screen;
TeaFlowIdleBacklight backlight(41);
bool wakeTouch = false;
KitchenAudio speaker;
TeaFlowClient api(API_BASE, DEVICE_KEY);
String wifiName = WIFI_SSID, wifiPassword = WIFI_PASSWORD, apiAddress = API_BASE;
JsonDocument state(&kitchenJsonRam);
Preferences kitchenSettings;
const uint16_t K_WHITE = TeaFlowTheme::white, K_INK = TeaFlowTheme::ink, K_GREEN = TeaFlowTheme::green,
  K_PALE = TeaFlowTheme::pale, K_RED = TeaFlowTheme::red, K_GRAY = TeaFlowTheme::muted,
  K_YELLOW = TeaFlowTheme::yellow;
bool configured = false, stateGood = false, touching = false;
uint32_t lastState = 0, lastPoll = 0, lastTouch = 0;
int queuePage = 0, orderId = 0, detailPage = 0, pressed = -1;
int queueFilter = 0;
const char* queueFilters[] = {"all", "queued", "preparing", "ready"};
const char* queueFilterNames[] = {"All", "Queued", "Preparing", "Ready"};
enum KitchenView { QUEUE, ORDER, CONFIRM_READY, CONNECTION, NETWORK, NETWORK_SCAN, KEYBOARD };
KitchenView view = QUEUE;
String message = "Connecting to TeaFlow...", lastPaidEvent;
bool newPaidOrders = false, eventStorage = false;
bool soundEnabled = true;
String kitchenDiagnosticLine;
uint32_t lastAlertSound = 0;
uint8_t reminderRepeats = 0;
struct KitchenButton { int id, x, y, w, h; bool enabled; };
KitchenButton buttons[60]; int buttonCount = 0;
void renderKitchen();

bool kitchenFresh() { return configured && stateGood && WiFi.status() == WL_CONNECTED && uint32_t(millis() - lastState) < 10000; }
String shortText(String text, int count) {
  text.replace("\n", " "); text.replace("\r", " ");
  if (int(text.length()) > count) text = text.substring(0, count - 2) + "..";
  return text;
}
void label(int x, int y, String text, int size = 2, uint16_t color = K_INK, int count = 38) {
  auto& g = screen.gfx;
  g.setTextWrap(false); g.setTextSize(size); g.setTextColor(color);
  g.setCursor(x, y); g.print(shortText(text, count));
}
void button(int id, int x, int y, int w, int h, String text, bool enabled = true) {
  if (buttonCount >= 60) return;
  buttons[buttonCount++] = {id, x, y, w, h, enabled};
  const bool primary = id == 8 || id == 9 || id == 10 || id == 16 || id == 55 || id == 65;
  const uint16_t fill = !enabled ? TeaFlowTheme::disabled : id == 15 ? K_YELLOW : primary ? K_GREEN : K_WHITE;
  screen.gfx.fillRoundRect(x, y, w, h, 7, fill);
  screen.gfx.drawRoundRect(x, y, w, h, 7, primary && enabled ? K_GREEN : TeaFlowTheme::border);
  String display = shortText(text, max(1, (w - 16) / 12));
  label(x + (w - int(display.length()) * 12) / 2, y + (h - 16) / 2, display, 2,
    !enabled ? K_GRAY : primary ? K_WHITE : K_INK, max(1, (w - 16) / 12));
}
void kitchenStatusPill(int x, int y, int w, String status) {
  const uint16_t fill = status == "ready" ? K_GREEN : status == "preparing" ? TeaFlowTheme::blue : K_PALE;
  status.toUpperCase();
  screen.gfx.fillRoundRect(x, y, w, 20, 10, fill);
  label(x + (w - int(status.length()) * 6) / 2, y + 6, status, 1, fill == K_PALE ? K_GREEN : K_WHITE, (w - 10) / 6);
}
int hit(int x, int y) {
  for (int i = 0; i < buttonCount; ++i) {
    const auto& b = buttons[i];
    if (b.enabled && x >= b.x && x < b.x + b.w && y >= b.y && y < b.y + b.h) return b.id;
  }
  return -1;
}
JsonObject selectedOrder(int id) {
  for (JsonObject order : state["orders"].as<JsonArray>()) if (order["id"].as<int>() == id) return order;
  return JsonObject();
}

int filteredCount(int filter) {
  int count = 0;
  for (JsonObject order : state["orders"].as<JsonArray>())
    if (!filter || order["status"] == queueFilters[filter]) ++count;
  return count;
}
int filteredIndex(int position) {
  int index = 0;
  for (JsonObject order : state["orders"].as<JsonArray>()) {
    if ((!queueFilter || order["status"] == queueFilters[queueFilter]) && position-- == 0) return index;
    ++index;
  }
  return -1;
}

int32_t waitMinutes(JsonObject order) {
  return teaFlowWaitMinutes(order["paid_at_unix"].as<uint32_t>(), state["server_unix"].as<uint32_t>(),
    lastState, millis(), kitchenFresh());
}
String waitingText(JsonObject order) {
  const int32_t minutes = waitMinutes(order);
  return minutes < 0 ? "Wait --" : minutes < 1 ? "Wait <1m" : "Wait " + String(minutes) + "m";
}
uint16_t waitingColor(JsonObject order) {
  if (order["status"] == "ready") return K_GREEN;
  const int32_t minutes = waitMinutes(order);
  return minutes >= 10 ? K_RED : minutes >= 5 ? K_YELLOW : K_GREEN;
}

#include "KitchenConnection.h"

// Hash visible content only; changing server timestamps must not flash the LCD.
class KitchenHash : public Print {
 public:
  using Print::write;
  uint64_t value = 14695981039346656037ULL;
  size_t write(uint8_t byte) override { value = (value ^ byte) * 1099511628211ULL; return 1; }
};

// Wrap and paginate every recipe field, including every topping.
void recipeLines(JsonObject order, int page, int& totalLines) {
  totalLines = 0;
  auto line = [&](String text, uint16_t color) {
    while (text.length()) {
      int length = min(36, int(text.length()));
      if (length < int(text.length())) {
        int space = text.lastIndexOf(' ', length);
        if (space > 10) length = space;
      }
      if (totalLines >= page * 6 && totalLines < (page + 1) * 6)
        label(24, 122 + (totalLines % 6) * 19, text.substring(0, length), 2, color, 36);
      ++totalLines;
      text = text.substring(length); text.trim();
    }
  };
  for (JsonObject item : order["items"].as<JsonArray>()) {
    line(String(item["quantity"].as<int>()) + " x " + item["product_name"].as<String>(), K_INK);
    line(item["size"].as<String>() + " | " + String(item["sugar"].as<int>()) + "% sugar | " + item["ice"].as<String>() + " ice", K_GRAY);
    for (JsonObject addon : item["addons"].as<JsonArray>()) line("  + " + addon["name"].as<String>(), K_GREEN);
  }
}

void renderKitchen() {
  static bool painted = false;
  static uint64_t lastHash = 0;
  KitchenHash hash;
  queuePage = constrain(queuePage, 0, max(0, (filteredCount(queueFilter) - 1) / 2));
  const int ui[] = {int(view), queuePage, orderId, detailPage, int(configured), int(kitchenFresh()),
    int(WiFi.status()), int(screen.touchAddress), int(newPaidOrders), int(state["low_stock"].as<bool>()), queueFilter};
  hash.write(reinterpret_cast<const uint8_t*>(ui), sizeof(ui));
  hash.print(message); serializeJson(state["orders"], hash);
  hash.print(teaFlowSignalBars()); hash.print(teaFlowSyncLabel(lastState));
  // Minute changes only affect the visible queue/detail timers. Do not redraw
  // the whole screen every second or let a timer repaint cancel a held touch.
  if (view == QUEUE) {
    for (int i = 0; i < 2; ++i) {
      const int index = filteredIndex(queuePage * 2 + i);
      if (index < 0) break;
      JsonObject order = state["orders"][index];
      if (order["status"] != "ready") hash.print(waitMinutes(order));
    }
  } else if (view == ORDER) {
    JsonObject order = selectedOrder(orderId);
    if (!order.isNull() && order["status"] != "ready") hash.print(waitMinutes(order));
  }
  if (connectionView()) hash.print(connectionScreenState());
  if (view == CONNECTION) {
    hash.print(WiFi.localIP().toString()); hash.print(int(speaker.ready));
    hash.print(int(speaker.busy)); hash.print(int(speaker.volume)); hash.print(soundEnabled);
  }
  if (painted && hash.value == lastHash) return;
  buttonCount = 0; pressed = -1;
  auto& g = screen.gfx;
  g.fillScreen(TeaFlowTheme::background); g.fillRect(0, 0, 480, 34, K_INK);
  label(12, 9, "TeaFlow", 2, K_WHITE);
  label(108, 13, "KITCHEN", 1, K_PALE);
  teaFlowSignalIcon(g, 306, 6, kitchenFresh() ? K_YELLOW : K_RED, K_GRAY);
  label(342, 5, teaFlowSyncLabel(lastState), 1, K_PALE, 21);
  label(342, 21, kitchenFresh() ? "CONNECTED" : "OFFLINE / STALE", 1, K_WHITE, 21);
  if (connectionView()) renderConnectionView();
  else if (view == QUEUE) {
    const int count = filteredCount(queueFilter), pages = max(1, (count + 1) / 2);
    if (!state["orders"].size()) {
      TeaFlowTheme::logo(g, 240, 105, 52);
      label(156, 171, "TeaFlow", 4, K_INK, 7);
      String subtitle = kitchenFresh() ? "Waiting for paid orders" : "Waiting for connection";
      label((480 - int(subtitle.length()) * 6) / 2, 219, subtitle, 1, K_GRAY, 70);
      button(2, 12, 248, 132, 40, "Refresh", configured);
      button(3, 366, 248, 102, 40, "Info");
      if (state["low_stock"] == true) label(204, 264, "LOW STOCK", 1, K_RED);
    } else {
    queuePage = constrain(queuePage, 0, pages - 1);
    if (newPaidOrders) button(15, 12, 40, 342, 30, "NEW - view queued orders");
    else {
      label(12, 45, String(state["orders"].size()) + " paid orders", 2);
      label(204, 50, state["low_stock"] == true ? "LOW STOCK" : "OLDEST FIRST", 1, state["low_stock"] == true ? K_RED : K_GRAY);
    }
    button(3, 366, 40, 102, 30, "Info");
    for (int f = 0; f < 4; ++f) {
      const int x = 12 + f * 116;
      const bool selected = queueFilter == f;
      button(17 + f, x, 78, 108, 38, "");
      if (selected) g.fillRoundRect(x, 78, 108, 38, 7, K_GREEN);
      label(x + (108 - int(strlen(queueFilterNames[f])) * 6) / 2, 84, queueFilterNames[f], 1, selected ? K_WHITE : K_INK, 16);
      String quantity = String(filteredCount(f));
      label(x + (108 - int(quantity.length()) * 12) / 2, 97, quantity, 2, selected ? K_WHITE : K_GREEN, 7);
    }
    if (!count) {
      label(24, 151, String("No ") + queueFilters[queueFilter] + " orders", 2, K_GRAY, 34);
      label(24, 189, "Choose another status above.", 1, K_GRAY, 65);
    }
    for (int i = 0; i < 2 && queuePage * 2 + i < count; ++i) {
      const int index = filteredIndex(queuePage * 2 + i);
      if (index < 0) break;
      JsonObject order = state["orders"][index];
      const int y = 124 + i * 60;
      button(100 + index, 12, y, 456, 54, "");
      const uint16_t urgency = waitingColor(order);
      g.fillRect(13, y + 7, 4, 36, urgency);
      label(24, y + 8, order["code"].as<String>(), 2, K_INK, 14);
      kitchenStatusPill(204, y + 6, 120, order["status"].as<String>());
      const bool normal = urgency == K_GREEN;
      g.fillRoundRect(336, y + 6, 122, 38, 6, normal ? K_PALE : urgency);
      String timer = shortText(order["status"] == "ready" ? "READY" : waitingText(order), 9);
      label(397 - int(timer.length()) * 6, y + 17, timer, 2, normal ? K_GREEN : urgency == K_YELLOW ? K_INK : K_WHITE, 9);
      label(24, y + 33, order["customer_name"].as<String>(), 1, K_GRAY, 34);
      label(260, y + 33, String(order["qty"].as<int>()) + " drinks", 1, K_GRAY, 11);
    }
    button(1, 12, 248, 104, 40, "Prev", queuePage > 0);
    button(2, 126, 248, 116, 40, "Refresh", configured);
    label(257, 262, String(queuePage + 1) + "/" + String(pages), 1);
    button(4, 364, 248, 104, 40, "Next", queuePage + 1 < pages);
    }
  } else if (view == CONNECTION) {
    label(12, 48, "Sound & connection");
    button(16, 354, 38, 114, 34, "Wi-Fi");
    TeaFlowTheme::card(g, 12, 80, 456, 87);
    label(24, 90, "Wi-Fi: " + wifiName, 1, K_INK, 70);
    label(24, 110, "IP: " + WiFi.localIP().toString(), 1, K_GRAY);
    label(24, 130, "API: " + apiAddress, 1, K_GRAY, 70);
    label(24, 150, "Signal: " + String(WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0) + " dBm | " + teaFlowSyncLabel(lastState), 1, K_GRAY, 70);
    label(12, 180, speaker.ready ? String("Alerts ") + (soundEnabled ? "ON" : "MUTED") + "  " + String(speaker.volume) + "%" : String("Speaker: ") + speaker.error, 1, K_INK, 37);
    g.fillRoundRect(254, 179, 214, 10, 5, TeaFlowTheme::border);
    if (speaker.ready) g.fillRoundRect(254, 179, 214 * speaker.volume / 100, 10, 5, K_GREEN);
    button(11, 12, 199, 220, 38, speaker.busy ? "Playing..." : "Test speaker", speaker.ready && !speaker.busy);
    button(12, 244, 199, 224, 38, soundEnabled ? "Mute alerts" : "Enable alerts", speaker.ready);
    button(5, 12, 248, 104, 40, "Back");
    button(2, 126, 248, 116, 40, "Refresh", configured);
    button(13, 254, 248, 102, 40, "Vol -", speaker.ready && speaker.volume > 10);
    button(14, 366, 248, 102, 40, "Vol +", speaker.ready && speaker.volume < 100);
  } else {
    JsonObject order = selectedOrder(orderId);
    button(5, 12, 248, 104, 40, "Back");
    if (order.isNull()) {
      label(12, 70, "Order left the active queue.");
    } else if (view == CONFIRM_READY) {
      TeaFlowTheme::card(g, 12, 46, 456, 186);
      g.fillCircle(57, 88, 26, K_PALE);
      TeaFlowTheme::check(g, 45, 77, K_GREEN);
      label(102, 64, order["code"].as<String>(), 3, K_INK, 19);
      label(102, 106, "All drinks done?", 2, K_INK, 28);
      label(24, 157, "Check every drink and topping before confirming.", 1, K_GRAY, 70);
      label(24, 190, "The cashier will see the READY notification.", 1, K_GRAY, 70);
      button(9, 232, 248, 236, 40, "Confirm ready", kitchenFresh() && order["status"] == "preparing");
    } else {
      label(12, 43, order["code"].as<String>(), 3, K_INK, 17);
      label(12, 74, order["customer_name"].as<String>(), 1, K_GRAY, 50);
      kitchenStatusPill(12, 90, 120, order["status"].as<String>());
      const uint16_t urgency = waitingColor(order);
      g.fillRoundRect(144, 90, 178, 20, 10, urgency == K_GREEN ? K_PALE : urgency);
      label(154, 96, order["status"] == "ready" ? "Ready for handover" : waitingText(order) + " since payment", 1, urgency == K_GREEN ? K_GREEN : urgency == K_YELLOW ? K_INK : K_WHITE, 26);
      TeaFlowTheme::card(g, 12, 116, 456, 122);
      int lines = 0; recipeLines(order, detailPage, lines);
      const int pages = max(1, (lines + 5) / 6);
      if (detailPage >= pages) { detailPage = pages - 1; painted = false; renderKitchen(); return; }
      button(6, 332, 40, 62, 35, "<", detailPage > 0);
      button(7, 404, 40, 64, 35, ">", detailPage + 1 < pages);
      label(332, 92, String(detailPage + 1) + "/" + String(pages) + " recipe", 1, K_GRAY);
      if (order["status"] == "queued") button(8, 232, 248, 236, 40, "Start preparing", kitchenFresh());
      else if (order["status"] == "preparing") button(10, 232, 248, 236, 40, "Mark ready", kitchenFresh());
      else label(250, 262, "Waiting for handover", 1);
    }
  }
  g.fillRect(0, 296, 480, 24, kitchenFresh() ? K_PALE : TeaFlowTheme::amberPale);
  label(12, 304, kitchenFresh() ? message : "OFFLINE - timers paused. " + message, 1, kitchenFresh() ? K_INK : K_RED, 76);
  if (screen.flush()) { lastHash = hash.value; painted = true; }
}

bool refreshKitchen() {
  lastPoll = millis();
  JsonDocument next(&kitchenJsonRam);
  if (!api.get("/iot/state", next)) {
    stateGood = false; message = api.error; return false;
  }
  bool valid = next["orders"].is<JsonArray>() && next["event_id"].is<const char*>();
  for (JsonObject order : next["orders"].as<JsonArray>()) {
    valid &= order["id"].is<int>() && order["id"].as<int>() > 0 && order["paid"] == true &&
      order["items"].is<JsonArray>() && (order["status"] == "queued" || order["status"] == "preparing" || order["status"] == "ready");
  }
  if (!valid) { stateGood = false; message = "Invalid queue. Refresh before continuing."; return false; }
  const String event = next["event_id"].as<String>();
  bool hasQueued = false;
  for (JsonObject order : next["orders"].as<JsonArray>()) hasQueued |= order["status"] == "queued";
  if (event != lastPaidEvent) {
    if (hasQueued) {
      newPaidOrders = true;
      reminderRepeats = 2; lastAlertSound = millis();
      if (soundEnabled && speaker.ready) {
        speaker.play();
        Serial.printf("Kitchen speaker: new paid event %s\n", event.c_str());
      }
    }
    lastPaidEvent = event;
    if (eventStorage) kitchenSettings.putString("paid-event", event);
  }
  if (!hasQueued) { newPaidOrders = false; reminderRepeats = 0; }
  state = std::move(next); stateGood = true; lastState = millis();
  if (!state["orders"].size()) { queueFilter = 0; queuePage = 0; }
  if (state["orders"].size() == 0 && (view == ORDER || view == CONFIRM_READY)) {
    view = QUEUE; orderId = 0; detailPage = 0;
  }
  message = newPaidOrders ? "New paid order - tap an order to review." : state["orders"].size() ? "Queue synced. Tap an order to view its recipe." : "All caught up. Waiting for paid orders.";
  return true;
}

void kitchenStatus(const char* target) {
  if (!kitchenFresh()) { message = "Refresh the queue before changing an order."; return; }
  const String expected = String(target) == "preparing" ? "queued" : "preparing";
  if (!refreshKitchen()) return;
  JsonObject order = selectedOrder(orderId);
  if (order.isNull()) { message = "Order left the active queue."; return; }
  if (order["status"] == target) { message = "Server already confirmed this status."; view = ORDER; return; }
  if (order["status"].as<String>() != expected) { message = "Order changed. Review its current status."; view = ORDER; return; }
  JsonDocument result(&kitchenJsonRam);
  const bool ok = api.post("/orders/" + String(orderId) + "/status", String("{\"status\":\"") + target + "\"}", result);
  const bool confirmed = ok && result["id"].as<int>() == orderId && result["status"] == target;
  const String actionError = ok ? "Unexpected response" : api.error;
  stateGood = false;
  const bool refreshed = refreshKitchen();
  if (confirmed) message = String("Confirmed #") + orderId + " " + target + (refreshed ? "." : ". Queue refresh failed.");
  else message = actionError + ". Check this order before retrying.";
  view = ORDER;
}

void kitchenAction(int id) {
  if (actConnection(id) || connectionView()) return;
  if (id >= 100) {
    const int index = id - 100;
    if (index >= int(state["orders"].size())) return;
    orderId = state["orders"][index]["id"].as<int>(); detailPage = 0; view = ORDER;
    newPaidOrders = false; reminderRepeats = 0; speaker.stop();
  } else switch (id) {
    case 17: case 18: case 19: case 20:
      queueFilter = id - 17; queuePage = 0; break;
    case 1: --queuePage; break;
    case 2: refreshKitchen(); break;
    case 3: view = CONNECTION; break;
    case 4: ++queuePage; break;
    case 5: view = view == CONFIRM_READY ? ORDER : QUEUE; break;
    case 6: --detailPage; break;
    case 7: ++detailPage; break;
    case 8: kitchenStatus("preparing"); break;
    case 9: kitchenStatus("ready"); break;
    case 10: if (kitchenFresh()) view = CONFIRM_READY; break;
    case 11:
      speaker.play(); message = "Playing the speaker test. Volume controls are below."; break;
    case 12:
      soundEnabled = !soundEnabled;
      if (!soundEnabled) { speaker.stop(); reminderRepeats = 0; }
      if (eventStorage) kitchenSettings.putBool("sound-on", soundEnabled);
      message = soundEnabled ? "New paid-order sound enabled." : "Sound muted. New paid-order notices still appear.";
      break;
    case 13: case 14:
      speaker.volume = constrain(int(speaker.volume) + (id == 13 ? -10 : 10), 10, 100);
      if (eventStorage) kitchenSettings.putUChar("sound-vol", speaker.volume);
      message = "Speaker volume: " + String(speaker.volume) + "%. Tap Test speaker to listen.";
      break;
    case 15:
      newPaidOrders = false; reminderRepeats = 0; speaker.stop();
      queueFilter = 1; queuePage = 0; view = QUEUE;
      message = "New-order alert acknowledged. Review the queued drinks.";
      break;
  }
}

void kitchenSetup() {
  Serial.begin(115200);
  if (!screen.begin()) {
    Serial.println("Kitchen ST77922 display failed. Check board/PSRAM settings.");
    while (true) delay(1000);
  }
  backlight.begin();
  eventStorage = kitchenSettings.begin("tf-kitchen", false);
  if (eventStorage) {
    lastPaidEvent = kitchenSettings.getString("paid-event", "");
    soundEnabled = kitchenSettings.getBool("sound-on", true);
    speaker.volume = constrain(int(kitchenSettings.getUChar("sound-vol", 50)), 10, 100);
  }
  if (!speaker.begin()) Serial.printf("Kitchen speaker unavailable: %s\n", speaker.error);
  loadConnection();
  WiFi.persistent(false); WiFi.mode(WIFI_STA); WiFi.setAutoReconnect(true);
  if (configured) WiFi.begin(wifiName.c_str(), wifiPassword.c_str());
  else { view = CONNECTION; message = "Open Info > Wi-Fi to set the network and laptop address."; }
  Serial.printf("TeaFlow kitchen | ST77922 | PSRAM=%u MB | touch=0x%02X\n",
    unsigned(ESP.getPsramSize() / 1048576), screen.touchAddress);
  renderKitchen();
}

void kitchenLoop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      kitchenDiagnosticLine.trim();
      if (kitchenDiagnosticLine == "screen-dump") {
        if (speaker.busy) Serial.println("Screen capture: wait for chime to finish.");
        else { renderKitchen(); teaFlowScreenCapture(Serial, screen.gfx.getFramebuffer(), 320, 480, 1); }
      } else if (kitchenDiagnosticLine == "display-info") {
        Serial.printf("Backlight PWM=%s | brightness=%u%% | idle=%s | signal=%d/4 | %s\n", backlight.ready ? "yes" : "no", backlight.brightness, view == QUEUE && !state["orders"].size() ? "yes" : "no", teaFlowSignalBars(), teaFlowSyncLabel(lastState).c_str());
      } else if (kitchenDiagnosticLine == "show-info" && !touching && !connectionView()) {
        backlight.touch(); view = CONNECTION; renderKitchen();
      } else if (kitchenDiagnosticLine == "show-queue" && !touching && !connectionView()) {
        backlight.touch(); view = QUEUE; renderKitchen();
      } else if (kitchenDiagnosticLine == "speaker-test") {
        speaker.play();
        Serial.println(speaker.ready ? "Kitchen speaker: test requested" : speaker.error);
      } else if (kitchenDiagnosticLine == "speaker-louder") {
        speaker.volume = 100;
        bool saved = eventStorage && kitchenSettings.putUChar("sound-vol", 100) == 1;
        message = "Speaker volume set to 100%. Use Info to adjust it.";
        Serial.printf("Kitchen speaker: volume=100%% | saved=%s\n", saved ? "yes" : "no");
        speaker.play();
      }
      kitchenDiagnosticLine = "";
    } else if (c != '\r' && kitchenDiagnosticLine.length() < 40) kitchenDiagnosticLine += c;
  }
  bool down = false; int16_t x = -1, y = -1;
  if (screen.readTouch(down, x, y)) {
    lastTouch = millis();
    if ((down || touching) && backlight.touch()) wakeTouch = true;
    if (x < 0 || y < 0) pressed = -1;
    if (down && !touching) { touching = true; pressed = wakeTouch ? -1 : hit(x, y); }
    else if (down && pressed >= 0 && hit(x, y) != pressed) pressed = -1;
    else if (!down && touching) {
      const int action = pressed;
      touching = false; pressed = -1;
      if (action >= 0) kitchenAction(action);
      wakeTouch = false;
    }
  }
  // A failed touch bus must cancel a held press, never synthesize a click.
  if (touching && uint32_t(millis() - lastTouch) > 300) pressed = -1;
  pollConnection();
  if (configured && !touching && !connectionView() && uint32_t(millis() - lastPoll) >= 3000) {
    refreshKitchen();
    Serial.printf("Kitchen Wi-Fi=%d | IP=%s | touch=0x%02X | queue=%s | paid-orders=%u\n",
      int(WiFi.status()), WiFi.localIP().toString().c_str(), screen.touchAddress,
      kitchenFresh() ? "current" : "stale", unsigned(state["orders"].size()));
    if (!api.error.isEmpty()) Serial.println(api.error);
  }
  if (newPaidOrders && reminderRepeats && soundEnabled && speaker.ready && !speaker.busy
      && kitchenFresh() && !connectionView() && uint32_t(millis() - lastAlertSound) >= 15000) {
    speaker.play(); lastAlertSound = millis(); --reminderRepeats;
    Serial.printf("Kitchen speaker: unacknowledged order reminder; remaining=%u\n", reminderRepeats);
  }
  if (!touching) renderKitchen();
  backlight.update(view == QUEUE && !state["orders"].size() && kitchenFresh() && !touching);
  delay(15);
}
