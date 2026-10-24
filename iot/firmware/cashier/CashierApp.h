#pragma once
#include <TeaFlowClient.h>
#include <TeaFlowDisplay.h>
#include <TeaFlowTheme.h>
#include <TeaFlowScreenCapture.h>
#include <TeaFlowDeviceStatus.h>
#include <Preferences.h>
#include <esp_heap_caps.h>
#include <utility>
#include <limits.h>

struct ExternalRam : ArduinoJson::Allocator {
  void* allocate(size_t n) override { return heap_caps_malloc(n, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT); }
  void deallocate(void* p) override { heap_caps_free(p); }
  void* reallocate(void* p, size_t n) override { return heap_caps_realloc(p, n, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT); }
} jsonRam;
TeaFlowDisplay screen;
TeaFlowIdleBacklight backlight(2);
TeaFlowClient api(API_BASE, DEVICE_KEY);
Preferences settings;
JsonDocument menu(&jsonRam), state(&jsonRam), cart(&jsonRam), summary(&jsonRam);
bool summaryGood = false, wakeTouch = false;
uint32_t lastSummary = 0, lastSummaryPoll = 0;
String pendingOrder, message = "Connecting to TeaFlow...";
bool configured = false, stateGood = false, storageGood = false;
String wifiName = WIFI_SSID, wifiPassword = WIFI_PASSWORD, apiAddress = API_BASE;
uint32_t lastState = 0, lastMenu = 0, lastPoll = 0;
uint32_t lastInteraction = 0;
bool cashierAwake = false;
int page = 0, productIndex = 0, variantIndex = 0, sugar = 100, iceIndex = 2, quantity = 1;
int addonPage = 0, addonIds[4] = {}, addonCount = 0, selectedOrderId = 0, itemPage = 0;
bool confirmPay = true;
enum View { MENU, CUSTOMIZE, CART, ORDERS, READY_ORDERS, DETAILS, UI_STATUS, SUMMARY, CONFIRM, NETWORK, NETWORK_SCAN, KEYBOARD };
View view = MENU;
const char* iceNames[] = {"none", "light", "regular"};
const uint16_t UI_WHITE = TeaFlowTheme::white, UI_INK = TeaFlowTheme::ink,
  UI_GREEN = TeaFlowTheme::green, UI_PALE = TeaFlowTheme::pale,
  UI_GRAY = TeaFlowTheme::muted, UI_RED = TeaFlowTheme::red;
struct Button { int id, x, y, w, h; bool enabled; };
Button buttons[60]; int buttonCount = 0, pressedButton = -1;
bool touching = false;
int16_t touchX = 0, touchY = 0;
uint32_t lastTouchReport = 0;
String diagnosticLine;
#include "CashierMouse.h"

void render();
void act(int id);
bool refreshState();
bool refreshMenu();
bool refreshSummary();

String money(int cents) { return String("PHP ") + String(cents / 100) + "." + (cents % 100 < 10 ? "0" : "") + String(cents % 100); }
String clipped(String value, int chars) {
  value.replace("\n", " "); value.replace("\r", " ");
  if (int(value.length()) > chars) return value.substring(0, chars - 2) + "..";
  return value;
}
void textAt(int x, int y, String value, uint16_t color = UI_INK, int size = 2, int chars = 64) {
  screen.gfx.setTextWrap(false); screen.gfx.setTextSize(size); screen.gfx.setTextColor(color);
  screen.gfx.setCursor(x, y); screen.gfx.print(clipped(value, chars));
}
void button(int id, int x, int y, int w, int h, String label, bool enabled = true, bool selected = false) {
  if (buttonCount >= 60) return;
  buttons[buttonCount++] = {id, x, y, w, h, enabled};
  const bool primary = id == 23 || id == 24 || id == 27 || id == 29 || id == 55 || id == 65;
  const bool filled = enabled && (selected || primary);
  screen.gfx.fillRoundRect(x, y, w, h, 8, filled ? UI_GREEN : enabled ? UI_WHITE : TeaFlowTheme::disabled);
  screen.gfx.drawRoundRect(x, y, w, h, 8, filled ? UI_GREEN : TeaFlowTheme::border);
  String display = clipped(label, max(1, (w - 20) / 12));
  textAt(x + (w - int(display.length()) * 12) / 2, y + (h - 16) / 2, display, filled ? UI_WHITE : enabled ? UI_INK : UI_GRAY, 2, max(1, (w - 20) / 12));
}
void statusPill(int x, int y, int w, String status) {
  uint16_t fill = status == "ready" ? UI_GREEN : status == "preparing" ? TeaFlowTheme::blue : status == "unpaid" ? TeaFlowTheme::amberPale : UI_PALE;
  status.toUpperCase();
  screen.gfx.fillRoundRect(x, y, w, 24, 12, fill);
  textAt(x + 10, y + 8, status, fill == UI_GREEN || fill == TeaFlowTheme::blue ? UI_WHITE : UI_INK, 1, (w - 20) / 6);
}
int hit(int x, int y) {
  for (int i = 0; i < buttonCount; ++i) {
    const auto& b = buttons[i];
    if (b.enabled && x >= b.x && x < b.x + b.w && y >= b.y && y < b.y + b.h) return b.id;
  }
  return -1;
}
bool fresh() { return stateGood && WiFi.status() == WL_CONNECTED && uint32_t(millis() - lastState) < 10000; }
JsonObject findOrder(int id) {
  for (JsonObject order : state["orders"].as<JsonArray>()) if (order["id"].as<int>() == id) return order;
  return JsonObject();
}
int readyOrderCount() {
  int count = 0;
  for (JsonObject order : state["orders"].as<JsonArray>())
    if (order["paid"] == true && order["status"] == "ready") ++count;
  return count;
}
JsonObject readyOrderAt(int index) {
  // The cashier state is newest first. Show ready drinks oldest first.
  JsonArray orders = state["orders"].as<JsonArray>();
  for (int i = int(orders.size()) - 1; i >= 0; --i) {
    JsonObject order = orders[i];
    if (order["paid"] == true && order["status"] == "ready" && index-- == 0) return order;
  }
  return JsonObject();
}
int total() {
  int result = 0;
  for (JsonObject line : cart["lines"].as<JsonArray>()) result += line["estimate_cents"].as<int>() * line["quantity"].as<int>();
  return result;
}
void pagination(int count, int perPage, int y = 366) {
  const int pages = max(1, (count + perPage - 1) / perPage);
  page = constrain(page, 0, pages - 1);
  button(10, 16, y, 140, 42, "Previous", page > 0);
  textAt(320, y + 13, String(page + 1) + " / " + String(pages), UI_GRAY);
  button(11, 644, y, 140, 42, "Next", page + 1 < pages);
}
#include "CashierConnection.h"

bool cashierIdle() {
  return fresh() && state["orders"].size() == 0 && pendingOrder.isEmpty()
    && cart["lines"].size() == 0 && (view == MENU || view == ORDERS || view == READY_ORDERS)
    && (!cashierAwake || uint32_t(millis() - lastInteraction) >= 60000);
}
void renderCashierIdle() {
  auto& g = screen.gfx;
  g.fillScreen(TeaFlowTheme::background);
  textAt(24, 30, "CASHIER", UI_GRAY, 1);
  teaFlowSignalIcon(g, 224, 18, UI_GREEN, TeaFlowTheme::border);
  textAt(260, 26, teaFlowSyncLabel(lastState), UI_GRAY, 1, 26);
  button(4, 632, 16, 152, 40, "Settings");
  TeaFlowTheme::logo(g, 400, 154, 72);
  textAt(295, 247, "TeaFlow", UI_INK, 5, 7);
  textAt(232, 309, "Your next order starts here.", UI_GRAY, 2, 30);
  button(36, 220, 354, 360, 52, "Start an order", true, true);
  textAt(274, 445, "CONNECTED  |  NO ACTIVE ORDERS", UI_GREEN, 1, 44);
  if (state["low_stock"] == true) textAt(262, 465, "LOW STOCK - check Inventory", UI_RED, 1, 44);
  // Any background tap wakes the menu. Named buttons above take priority.
  buttons[buttonCount++] = {36, 0, 0, 800, 480, true};
}

class ScreenHash : public Print {
 public:
  using Print::write;
  uint64_t value = 14695981039346656037ULL;
  size_t write(uint8_t byte) override {
    value = (value ^ byte) * 1099511628211ULL;
    return 1;
  }
};
uint64_t visibleScreenHash() {
  ScreenHash hash;
  const int controls[] = {int(view), page, productIndex, variantIndex, sugar, iceIndex,
    quantity, addonPage, addonCount, selectedOrderId, itemPage, int(confirmPay),
    int(configured), int(storageGood), int(fresh()), int(screen.touchAddress),
    int(state["low_stock"].as<bool>()), int(cashierIdle()), int(mouseOnly), int(mouse.linked)};
  hash.write(reinterpret_cast<const uint8_t*>(controls), sizeof(controls));
  hash.write(reinterpret_cast<const uint8_t*>(addonIds), sizeof(addonIds));
  hash.print(message);
  // Ready notices appear on every normal screen, including menu/cart. Hash
  // only their stable identity so ordinary polling cannot cause flashing.
  for (JsonObject order : state["orders"].as<JsonArray>()) {
    if (order["paid"] == true && order["status"] == "ready") { hash.print(order["id"].as<int>()); hash.print(order["code"].as<String>()); }
  }
  if (connectionView()) hash.print(connectionScreenState());
  serializeJson(cart, hash);
  if (view == MENU || view == CUSTOMIZE) serializeJson(menu, hash);
  if (view == ORDERS || view == READY_ORDERS || view == DETAILS || view == CONFIRM) serializeJson(state["orders"], hash);
  if (view == UI_STATUS) {
    hash.print(WiFi.localIP().toString()); hash.print(touchX); hash.print(touchY);
    hash.print(wifiName); hash.print(apiAddress);
  }
  if (view == SUMMARY) {
    for (const char* field : {"day", "paid_orders", "drinks_sold", "total_cents"}) hash.print(summary[field].as<String>());
    hash.print(summaryGood);
  }
  // server_time and event timestamps are not displayed; polling them must
  // not clear and redraw an otherwise unchanged screen.
  return hash.value;
}
void updateCashierIndicators(bool force = false) {
  // These small, changing indicators must not trigger a whole-page clear.
  static String previous;
  const bool idle = cashierIdle();
  const bool current = summaryGood && fresh() && uint32_t(millis() - lastSummary) < 45000;
  String key = String(int(view)) + ":" + String(idle) + ":" + String(teaFlowSignalBars()) + ":" + teaFlowSyncLabel(lastState);
  if (view == SUMMARY) key += ":" + String(current) + ":" + teaFlowSyncLabel(lastSummary);
  if (!force && key == previous) return;
  previous = key;
  auto& g = screen.gfx;
  if (idle) {
    g.fillRect(224, 16, 300, 26, TeaFlowTheme::background);
    teaFlowSignalIcon(g, 224, 18, UI_GREEN, TeaFlowTheme::border);
    textAt(260, 26, teaFlowSyncLabel(lastState), UI_GRAY, 1, 26);
  } else {
    g.fillRect(410, 8, 28, 32, UI_INK);
    teaFlowSignalIcon(g, 410, 13, fresh() ? TeaFlowTheme::yellow : UI_RED, UI_GRAY);
    g.fillRect(446, 28, 200, 12, UI_INK);
    textAt(446, 29, teaFlowSyncLabel(lastState), UI_PALE, 1, 31);
    if (view == SUMMARY) {
      g.fillRect(16, 326, 768, 20, TeaFlowTheme::background);
      textAt(16, 330, (current ? "Updated | " : "LAST RECEIVED VIEW - refresh needed | ") + teaFlowSyncLabel(lastSummary), current ? UI_GRAY : UI_RED, 1, 110);
    }
  }
}
void render() {
  static bool painted = false;
  static uint64_t lastPaint = 0;
  uint64_t nextPaint = visibleScreenHash();
  mouse.hide(screen.gfx);
  if (painted && nextPaint == lastPaint) { updateCashierIndicators(); mouse.show(screen.gfx); return; }
  mouse.cancel();
  pressedButton = -1; buttonCount = 0;
  if (cashierIdle()) {
    renderCashierIdle(); updateCashierIndicators(true); lastPaint = visibleScreenHash(); painted = true; mouse.show(screen.gfx); return;
  }
  screen.gfx.fillScreen(TeaFlowTheme::background);
  screen.gfx.fillRect(0, 0, 800, 48, UI_INK);
  TeaFlowTheme::cup(screen.gfx, 16, 8, UI_WHITE);
  textAt(52, 13, "TeaFlow", UI_WHITE);
  textAt(158, 18, "CASHIER", UI_PALE, 1);
  teaFlowSignalIcon(screen.gfx, 410, 13, fresh() ? TeaFlowTheme::yellow : UI_RED, UI_GRAY);
  textAt(446, 13, !configured ? "SETUP NEEDED" : fresh() ? "CONNECTED" : "OFFLINE / STALE", UI_WHITE, 1, 31);
  textAt(446, 29, teaFlowSyncLabel(lastState), UI_PALE, 1, 31);
  if (state["low_stock"].as<bool>()) {
    screen.gfx.fillRoundRect(660, 12, 124, 25, 12, TeaFlowTheme::yellow);
    textAt(675, 21, "LOW STOCK", UI_INK, 1);
  }
  if (!connectionView()) {
    button(1, 16, 56, 182, 42, "New order", true, view == MENU || view == CUSTOMIZE);
    button(2, 210, 56, 182, 42, "Cart (" + String(cart["lines"].size()) + ")", true, view == CART);
    const int ready = fresh() ? readyOrderCount() : 0;
    button(3, 404, 56, 182, 42, ready ? "Orders (" + String(ready) + "R)" : "Orders", true, view == ORDERS || view == READY_ORDERS || view == DETAILS);
    button(4, 598, 56, 186, 42, "Status", true, view == UI_STATUS || view == SUMMARY);
  }
  if (connectionView()) renderConnectionView();
  else if (view == MENU) {
    JsonArray products = menu["products"].as<JsonArray>();
    page = constrain(page, 0, max(0, (int(products.size()) - 1) / 6));
    if (!products.size()) textAt(20, 150, "No menu loaded. Check Status, then Refresh.");
    for (int i = 0; i < 6 && page * 6 + i < int(products.size()); ++i) {
      JsonObject product = products[page * 6 + i]; bool available = false; int price = INT_MAX;
      for (JsonObject variant : product["variants"].as<JsonArray>()) {
        available |= variant["available"].as<bool>();
        if (variant["available"].as<bool>()) price = min(price, variant["price_cents"].as<int>());
      }
      const int x = 16 + (i % 2) * 390, y = 112 + (i / 2) * 80;
      button(1000 + page * 6 + i, x, y, 378, 72, "", available && pendingOrder.isEmpty());
      String name = product["name"].as<String>();
      int split = min(28, int(name.length()));
      if (split < int(name.length()) && name.lastIndexOf(' ', split) > 10) split = name.lastIndexOf(' ', split);
      textAt(x + 14, y + 10, name.substring(0, split), available ? UI_INK : UI_GRAY, 2, 28);
      String secondLine = name.substring(split); secondLine.trim();
      textAt(x + 14, y + 30, secondLine, available ? UI_INK : UI_GRAY, 2, 28);
      textAt(x + 14, y + 50, price == INT_MAX ? "Out of stock" : "From " + money(price), available ? UI_GREEN : UI_GRAY, 2, 25);
      textAt(x + 346, y + 50, available ? ">" : "-", available ? UI_GREEN : UI_GRAY, 2, 1);
    }
    pagination(products.size(), 6);
  } else if (view == CUSTOMIZE) {
    JsonObject product = menu["products"][productIndex];
    textAt(16, 111, product["name"].as<String>(), UI_INK, 2, 45);
    JsonArray variants = product["variants"].as<JsonArray>();
    int shown = min(4, int(variants.size()));
    int width = shown ? (768 - 12 * (shown - 1)) / shown : 768;
    textAt(612, 111, money(variants[variantIndex]["price_cents"]), UI_INK, 2, 14);
    for (int i = 0; i < shown; ++i) {
      JsonObject variant = variants[i];
      button(2000 + i, 16 + i * (width + 12), 136, width, 42, variant["size"].as<String>(), variant["available"], i == variantIndex);
    }
    textAt(16, 191, "Sugar");
    for (int i = 0; i < 5; ++i) button(2100 + i, 100 + i * 88, 184, 80, 40, String(i * 25) + "%", true, sugar == i * 25);
    textAt(16, 238, "Ice");
    for (int i = 0; i < 3; ++i) button(2200 + i, 100 + i * 150, 231, 140, 40, iceNames[i], true, iceIndex == i);
    JsonArray addons = menu["addons"].as<JsonArray>();
    for (int i = 0; i < 4 && addonPage * 4 + i < int(addons.size()); ++i) {
      JsonObject addon = addons[addonPage * 4 + i]; bool chosen = false;
      for (int j = 0; j < addonCount; ++j) chosen |= addonIds[j] == addon["id"].as<int>();
      button(2300 + addonPage * 4 + i, 16 + (i % 2) * 390, 279 + (i / 2) * 44, 378, 40,
        addon["name"].as<String>() + " +" + money(addon["price_cents"]), true, chosen);
    }
    button(20, 16, 372, 70, 40, "-", quantity > 1);
    textAt(100, 384, String(quantity));
    button(21, 140, 372, 70, 40, "+", quantity < 20);
    if (addons.size() > 4) button(22, 226, 372, 190, 40, "More toppings");
    button(23, 500, 372, 284, 40, "Add to cart", cart["lines"].size() < 12 && pendingOrder.isEmpty());
  } else if (view == CART) {
    JsonArray lines = cart["lines"].as<JsonArray>();
    textAt(16, 112, !pendingOrder.isEmpty() && !lines.size() ? "Saved submission: retry to recover the order." : "Estimated: " + money(total()) + " | Walk-in Customer");
    page = constrain(page, 0, max(0, (int(lines.size()) - 1) / 3));
    for (int i = 0; i < 3 && page * 3 + i < int(lines.size()); ++i) {
      int index = page * 3 + i; JsonObject line = lines[index]; int y = 143 + i * 56;
      TeaFlowTheme::card(screen.gfx, 16, y, 768, 50);
      textAt(28, y + 7, String(line["quantity"].as<int>()) + " x " + line["name"].as<String>() + " " + line["size"].as<String>(), UI_INK, 2, 49);
      textAt(28, y + 32, "Sugar " + line["sugar"].as<String>() + "% | " + line["ice"].as<String>() + " ice | toppings " + String(line["addon_ids"].size()), UI_GRAY, 1);
      button(3000 + index, 650, y + 4, 122, 42, "Remove", pendingOrder.isEmpty());
    }
    button(10, 16, 318, 140, 42, "Previous", page > 0);
    button(11, 170, 318, 140, 42, "Next", (page + 1) * 3 < int(lines.size()));
    button(24, 330, 318, 454, 42, pendingOrder.isEmpty() ? "Create unpaid order" : "Retry saved submission",
      configured && storageGood && WiFi.status() == WL_CONNECTED && (lines.size() || !pendingOrder.isEmpty()));
    textAt(16, 380, pendingOrder.isEmpty() ? "Check payment after reviewing the saved order total." : "Saved request retained. Retry to avoid duplicate orders.", UI_GRAY, 2, 63);
  } else if (view == READY_ORDERS) {
    const int count = readyOrderCount();
    page = constrain(page, 0, max(0, (count - 1) / 4));
    if (!count) textAt(16, 140, fresh() ? "All ready orders have been handed over." : "Refresh to check ready orders.");
    for (int i = 0; i < 4 && page * 4 + i < count; ++i) {
      JsonObject order = readyOrderAt(page * 4 + i);
      const int y = 112 + i * 60;
      button(4200 + i, 16, y, 768, 52, "");
      screen.gfx.fillRoundRect(24, y + 7, 230, 38, 6, fresh() ? UI_GREEN : UI_GRAY);
      textAt(34, y + 15, order["code"].as<String>(), UI_WHITE, 2, 17);
      textAt(274, y + 8, fresh() ? "READY FOR HANDOVER" : "LAST SEEN READY", UI_GREEN, 2, 37);
      textAt(274, y + 32, order["customer_name"].as<String>() + " | " + String(order["qty"].as<int>()) + " drinks", UI_GRAY, 1, 76);
    }
    pagination(count, 4);
  } else if (view == ORDERS) {
    JsonArray orders = state["orders"].as<JsonArray>();
    page = constrain(page, 0, max(0, (int(orders.size()) - 1) / 4));
    if (!orders.size()) textAt(16, 140, fresh() ? "No active orders." : "Refresh to load orders.");
    for (int i = 0; i < 4 && page * 4 + i < int(orders.size()); ++i) {
      JsonObject order = orders[page * 4 + i];
      const int y = 112 + i * 60;
      button(4000 + page * 4 + i, 16, y, 768, 52, "");
      textAt(30, y + 8, order["code"].as<String>(), UI_INK, 3, 12);
      statusPill(264, y + 7, 128, order["status"].as<String>());
      textAt(568, y + 9, money(order["total_cents"]), UI_GREEN, 2, 17);
      textAt(264, y + 35, order["customer_name"].as<String>() + " | " + String(order["qty"].as<int>()) + " drinks", UI_GRAY, 1, 78);
    }
    pagination(orders.size(), 4);
  } else if (view == DETAILS || view == CONFIRM) {
    JsonObject order = findOrder(selectedOrderId);
    if (order.isNull()) textAt(16, 140, "Order left the active queue. Refresh Orders.");
    else {
      textAt(16, 111, order["code"].as<String>(), UI_INK, 3, 12);
      statusPill(264, 111, 144, order["status"].as<String>());
      textAt(568, 114, money(order["total_cents"]), UI_GREEN, 2, 17);
      textAt(16, 143, order["customer_name"].as<String>(), UI_GRAY, 1, 100);
      if (view == DETAILS) {
        JsonArray items = order["items"].as<JsonArray>();
        itemPage = constrain(itemPage, 0, max(0, (int(items.size()) - 1) / 2));
        for (int i = 0; i < 2 && itemPage * 2 + i < int(items.size()); ++i) {
          JsonObject item = items[itemPage * 2 + i]; int y = 167 + i * 78;
          TeaFlowTheme::card(screen.gfx, 16, y, 768, 70);
          textAt(28, y + 8, String(item["quantity"].as<int>()) + " x " + item["product_name"].as<String>() + " " + item["size"].as<String>(), UI_INK, 2, 61);
          textAt(28, y + 32, "Sugar " + item["sugar"].as<String>() + "% | " + item["ice"].as<String>() + " ice", UI_GRAY, 1);
          String extras = "Toppings: ";
          for (JsonObject addon : item["addons"].as<JsonArray>()) extras += addon["name"].as<String>() + ", ";
          textAt(28, y + 51, extras, UI_GRAY, 1, 120);
        }
        button(25, 16, 327, 170, 40, "Prev items", itemPage > 0);
        button(26, 202, 327, 170, 40, "Next items", (itemPage + 1) * 2 < int(items.size()));
        bool unpaid = order["status"] == "unpaid" && !order["paid"].as<bool>();
        bool ready = order["status"] == "ready" && order["paid"].as<bool>();
        button(27, 404, 372, 380, 40, unpaid ? "Review payment" : ready ? "Complete handover" : "Waiting for kitchen", fresh() && (unpaid || ready));
      } else {
        TeaFlowTheme::card(screen.gfx, 16, 173, 768, 137);
        screen.gfx.fillCircle(65, 231, 28, UI_PALE);
        TeaFlowTheme::check(screen.gfx, 53, 220, UI_GREEN);
        textAt(112, 202, confirmPay ? "Check payment" : "Confirm handover", UI_INK, 3, 35);
        textAt(112, 247, confirmPay ? "Payment received? This sends the order to the kitchen." : "Only confirm after the customer receives every drink.", UI_GRAY, 1, 106);
        button(28, 16, 330, 300, 62, "Back");
        button(29, 332, 330, 452, 62, confirmPay ? "Payment checked - confirm" : "Handover done - confirm", fresh());
      }
    }
  } else if (view == UI_STATUS) {
    textAt(16, 120, "Board: JC8048W550 | 800 x 480 | GT911");
    textAt(16, 155, "PSRAM: " + String(ESP.getPsramSize() / 1048576) + " MB | Input: " + (mouseOnly ? mouse.linked ? "USB mouse connected" : "USB mouse - open laptop control" : "touchscreen"), UI_INK, 2, 63);
    textAt(16, 190, "Wi-Fi: " + wifiName + " | " + String(WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString() : "disconnected"), UI_INK, 2, 62);
    textAt(16, 225, "API: " + apiAddress, UI_INK, 2, 62);
    textAt(16, 260, configured ? "Configuration loaded" : "Set Wi-Fi/API/key in cashier/config.h.", configured ? UI_INK : UI_RED);
    textAt(16, 295, String("Pending order: ") + (pendingOrder.isEmpty() ? "none" : "saved - use Cart to retry"));
    textAt(16, 330, "Signal: " + String(WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0) + " dBm | " + teaFlowSyncLabel(lastState));
    button(30, 16, 372, 246, 40, "Refresh", configured);
    button(37, 274, 372, 246, 40, "Daily summary", configured);
    button(40, 532, 372, 252, 40, "Wi-Fi setup");
  } else if (view == SUMMARY) {
    textAt(16, 120, "Today's sales", UI_INK, 3);
    textAt(16, 160, summary["day"].is<const char*>() ? summary["day"].as<String>() + " | Asia/Manila | All paid orders" : "Waiting for sales totals...", UI_GRAY, 1, 100);
    const char* titles[] = {"PAID ORDERS", "DRINKS SOLD", "TOTAL SALES"};
    for (int i = 0; i < 3; ++i) {
      int x = 16 + i * 260;
      TeaFlowTheme::card(screen.gfx, x, 198, 248, 112);
      textAt(x + 16, 216, titles[i], UI_GRAY, 1);
      String value = summary.isNull() ? "--" : i == 0 ? summary["paid_orders"].as<String>() : i == 1 ? summary["drinks_sold"].as<String>() : "PHP " + String(summary["total_cents"].as<double>() / 100.0, 2);
      textAt(x + 16, 253, value, UI_GREEN, value.length() > 11 ? 2 : 3, value.length() > 11 ? 18 : 12);
    }
    const bool current = summaryGood && fresh() && uint32_t(millis() - lastSummary) < 45000;
    textAt(16, 330, (current ? "Updated | " : "LAST RECEIVED VIEW - refresh needed | ") + teaFlowSyncLabel(lastSummary), current ? UI_GRAY : UI_RED, 1, 110);
    button(38, 16, 372, 376, 40, "Refresh totals", configured);
    button(39, 408, 372, 376, 40, "Back to status");
  }
  screen.gfx.fillRect(0, 424, 800, 56, fresh() ? UI_PALE : TeaFlowTheme::amberPale);
  String banner = message;
  if (!screen.touchAddress && !mouseOnly) banner = "Touch not detected. Run cashier-display-test first.";
  const int ready = readyOrderCount();
  if (fresh() && ready && !connectionView() && (screen.touchAddress || mouseOnly)) {
    JsonObject first = readyOrderAt(0);
    screen.gfx.fillRect(0, 424, 800, 56, UI_GREEN);
    textAt(16, 429, "READY: " + first["code"].as<String>() + (ready > 1 ? " +" + String(ready - 1) : ""), UI_WHITE, 3, 32);
    // Keep payment/submission errors and other action messages visible.
    textAt(16, 462, banner, UI_WHITE, 1, 98);
    button(31, 632, 430, 152, 42, "View ready");
  } else {
    textAt(16, 430, banner.substring(0, 63), UI_INK, 2, 63);
    textAt(16, 451, banner.substring(63, 126), UI_INK, 2, 63);
  }
  updateCashierIndicators(true);
  lastPaint = visibleScreenHash();
  painted = true;
  mouse.show(screen.gfx);
}
bool refreshState() {
  JsonDocument next(&jsonRam);
  if (!api.get("/iot/state", next) || !next["orders"].is<JsonArray>()) {
    stateGood = false; message = api.error.isEmpty() ? "Invalid queue response." : api.error; return false;
  }
  state = std::move(next); stateGood = true; lastState = millis(); return true;
}
bool refreshMenu() {
  JsonDocument next(&jsonRam);
  if (!api.get("/iot/menu", next) || !next["products"].is<JsonArray>() || !next["addons"].is<JsonArray>()) {
    message = api.error.isEmpty() ? "Invalid menu response." : api.error; return false;
  }
  menu = std::move(next); lastMenu = millis(); return true;
}
bool refreshSummary() {
  lastSummaryPoll = millis();
  JsonDocument next(&jsonRam);
  if (!api.get("/iot/summary", next) || !next["day"].is<const char*>() || next["timezone"] != "Asia/Manila"
      || !next["paid_orders"].is<uint64_t>() || !next["drinks_sold"].is<uint64_t>() || !next["total_cents"].is<uint64_t>()) {
    summaryGood = false; message = api.error.isEmpty() ? "Invalid daily summary response." : api.error; return false;
  }
  summary = std::move(next); summaryGood = true; lastSummary = millis();
  message = "Daily totals updated for all channels, including handovers."; return true;
}
void submitPending() {
  if (pendingOrder.isEmpty()) return;
  message = "Submitting saved order..."; render();
  JsonDocument result(&jsonRam);
  if (api.post("/orders", pendingOrder, result) && result["id"].as<int>() > 0) {
    selectedOrderId = result["id"]; itemPage = 0;
    // Reboot before removal safely replays the UUID, never a new order.
    if (!settings.remove("pending")) {
      message = "Order saved; storage cleanup failed. Retry saved request."; return;
    }
    pendingOrder = ""; cart.clear(); page = 0;
    if (refreshState()) { view = DETAILS; message = "Order saved unpaid. Check payment before confirming."; }
    else view = ORDERS;
  } else {
    // Explicit validation rejections did not create an order.
    // Timeouts and ambiguous responses retain the exact saved request.
    if (api.lastStatus == 400 || api.lastStatus == 422) {
      if (settings.remove("pending")) pendingOrder = "";
    }
    message = api.error.isEmpty() ? "Invalid acknowledgement. Retry the saved request." : api.error;
  }
}
void act(int id) {
  cashierAwake = true; lastInteraction = millis();
  if (actConnection(id)) { render(); return; }
  if (id >= 1 && id <= 4) {
    view = id == 1 ? MENU : id == 2 ? CART : id == 3 ? ORDERS : UI_STATUS; page = 0;
  } else if (id == 10) --page;
  else if (id == 11) ++page;
  else if (id >= 1000 && id < 2000) {
    productIndex = id - 1000; variantIndex = 0; addonCount = 0; addonPage = 0; quantity = 1; sugar = 100; iceIndex = 2;
    JsonArray variants = menu["products"][productIndex]["variants"].as<JsonArray>();
    for (int i = 0; i < int(variants.size()); ++i) if (variants[i]["available"].as<bool>()) { variantIndex = i; break; }
    view = CUSTOMIZE;
  } else if (id >= 2000 && id < 2004) variantIndex = id - 2000;
  else if (id >= 2100 && id <= 2104) sugar = (id - 2100) * 25;
  else if (id >= 2200 && id <= 2202) iceIndex = id - 2200;
  else if (id >= 2300 && id < 3000) {
    int addonId = menu["addons"][id - 2300]["id"]; int found = -1;
    for (int i = 0; i < addonCount; ++i) if (addonIds[i] == addonId) found = i;
    if (found >= 0) { for (int i = found; i + 1 < addonCount; ++i) addonIds[i] = addonIds[i + 1]; --addonCount; }
    else if (addonCount < 4) addonIds[addonCount++] = addonId;
    else message = "Choose up to four toppings per drink.";
  } else if (id >= 3000 && id < 3012) cart["lines"].as<JsonArray>().remove(id - 3000);
  else if (id >= 4000 && id < 4100) {
    selectedOrderId = state["orders"][id - 4000]["id"]; itemPage = 0; view = DETAILS;
  } else if (id >= 4200 && id < 4204 && view == READY_ORDERS) {
    JsonObject order = readyOrderAt(page * 4 + id - 4200);
    if (!order.isNull()) { selectedOrderId = order["id"].as<int>(); itemPage = 0; view = DETAILS; }
  } else if (id == 31) { view = READY_ORDERS; page = 0; }
  else if (id == 36) { view = MENU; page = 0; }
  else if (id == 37 || id == 38) { view = SUMMARY; refreshSummary(); }
  else if (id == 39) view = UI_STATUS;
  else if (id == 20) --quantity;
  else if (id == 21) ++quantity;
  else if (id == 22) addonPage = (addonPage + 1) % max(1, (int(menu["addons"].size()) + 3) / 4);
  else if (id == 23) {
    JsonObject product = menu["products"][productIndex]; JsonObject variant = product["variants"][variantIndex];
    if (!variant["available"].as<bool>()) { message = "This size is unavailable."; render(); return; }
    if (!cart["lines"].is<JsonArray>()) cart["lines"].to<JsonArray>();
    JsonObject line = cart["lines"].as<JsonArray>().add<JsonObject>();
    line["variant_id"] = variant["id"]; line["quantity"] = quantity; line["sugar"] = sugar; line["ice"] = iceNames[iceIndex];
    line["name"] = product["name"]; line["size"] = variant["size"];
    int estimate = variant["price_cents"];
    JsonArray ids = line["addon_ids"].to<JsonArray>();
    for (int i = 0; i < addonCount; ++i) {
      ids.add(addonIds[i]);
      for (JsonObject addon : menu["addons"].as<JsonArray>()) if (addon["id"].as<int>() == addonIds[i]) estimate += addon["price_cents"].as<int>();
    }
    line["estimate_cents"] = estimate; message = "Added to cart. Select another drink or open Cart."; view = MENU; page = 0;
  } else if (id == 24) {
    if (pendingOrder.isEmpty()) {
      JsonDocument body(&jsonRam); body["request_key"] = newRequestKey(); body["customer_name"] = "Walk-in Customer";
      JsonArray lines = body["lines"].to<JsonArray>();
      for (JsonObject source : cart["lines"].as<JsonArray>()) {
        JsonObject line = lines.add<JsonObject>();
        for (const char* field : {"variant_id", "quantity", "sugar", "ice", "addon_ids"}) line[field] = source[field];
      }
      String payload; serializeJson(body, payload);
      if (body.overflowed() || !storageGood || settings.putString("pending", payload) != payload.length()) {
        message = "Cannot save submission. No order was sent."; render(); return;
      }
      pendingOrder = payload;
    }
    submitPending();
  } else if (id == 25) --itemPage;
  else if (id == 26) ++itemPage;
  else if (id == 27) {
    if (refreshState()) {
      JsonObject order = findOrder(selectedOrderId);
      if (!order.isNull() && (order["status"] == "unpaid" || order["status"] == "ready")) {
        confirmPay = order["status"] == "unpaid"; view = CONFIRM;
      } else message = "Order changed. Review its current status.";
    }
  } else if (id == 28) view = DETAILS;
  else if (id == 29) {
    if (refreshState()) {
      JsonObject order = findOrder(selectedOrderId);
      bool allowed = !order.isNull() && (confirmPay ? order["status"] == "unpaid" && !order["paid"].as<bool>() : order["status"] == "ready" && order["paid"].as<bool>());
      if (allowed) {
        message = "Confirming action with server..."; render();
        JsonDocument result(&jsonRam);
        String path = "/orders/" + String(selectedOrderId) + (confirmPay ? "/pay" : "/status");
        bool ok = api.post(path, confirmPay ? "{}" : "{\"status\":\"completed\"}", result);
        if (ok && (result["id"].as<int>() != selectedOrderId || (confirmPay ? !result["paid"].as<bool>() : result["status"] != "completed"))) {
          ok = false; api.error = "Invalid acknowledgement - action not confirmed.";
        }
        String actionError = api.error;
        bool synced = refreshState();
        view = confirmPay ? DETAILS : ORDERS;
        message = ok ? (confirmPay ? "Payment confirmed; kitchen notified." : "Handover completed.") : actionError + " Refresh before retrying.";
        if (!synced && ok) message += " Queue refresh failed; displayed data is stale.";
      } else { view = DETAILS; message = "Order changed. Review its current status."; }
    }
  } else if (id == 30) {
    bool menuOk = refreshMenu(), stateOk = refreshState();
    if (menuOk && stateOk) message = state["low_stock"].as<bool>() ? "Connected. Low stock: check staff Inventory." : "Menu and orders refreshed.";
  }
  render();
}
#include "CashierMouseInput.h"

void setup() {
  Serial.begin(115200);
  if (!screen.begin()) {
    Serial.println("Display failed. Check OPI PSRAM and the pinned PlatformIO settings.");
    while (true) delay(1000);
  }
  backlight.begin();
  storageGood = settings.begin("teaflow-cash", false);
  if (storageGood) mouseOnly = settings.getBool("usb-mouse", false);
  if (storageGood) pendingOrder = settings.getString("pending", "");
  loadConnection();
  Serial.printf("TeaFlow cashier | JC8048W550 | API %s | direct ordering\n", apiAddress.c_str());
  if (configured) {
    WiFi.onEvent([](WiFiEvent_t event, WiFiEventInfo_t info) {
      if (event == ARDUINO_EVENT_WIFI_STA_DISCONNECTED)
        Serial.printf("Wi-Fi disconnected: reason=%u\n", unsigned(info.wifi_sta_disconnected.reason));
    });
    WiFi.persistent(false); WiFi.mode(WIFI_STA); WiFi.setAutoReconnect(true); WiFi.begin(wifiName.c_str(), wifiPassword.c_str());
    message = "Connecting to Wi-Fi...";
  } else { view = UI_STATUS; message = "Open Wi-Fi setup. Device key must be set in config.h."; }
  if (!storageGood) message = "Device storage failed. New orders are disabled.";
  if (!pendingOrder.isEmpty()) { view = CART; message = "Saved submission retained. Use Cart to retry the same request."; }
  render();
}
void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      diagnosticLine.trim();
      if (handleMouseCommand(diagnosticLine)) {
        // Commands acknowledge only after the existing UI action completes.
      } else if (diagnosticLine == "screen-dump") {
        render(); teaFlowScreenCapture(Serial, screen.gfx.getFramebuffer(), 800, 480, 0);
      } else if (diagnosticLine == "display-info") {
        Serial.printf("Backlight PWM=%s | brightness=%u%% | idle=%s | signal=%d/4 | %s\n", backlight.ready ? "yes" : "no", backlight.brightness, cashierIdle() ? "yes" : "no", teaFlowSignalBars(), teaFlowSyncLabel(lastState).c_str());
      } else if (diagnosticLine == "show-summary" && !touching && !connectionView()) {
        // Read-only page navigation for hardware display verification.
        backlight.touch(); act(37);
      } else if (diagnosticLine == "show-menu" && !touching && !connectionView()) {
        backlight.touch(); act(1);
      } else if (diagnosticLine == "scan") {
        WiFi.setAutoReconnect(false);
        WiFi.disconnect(false, false);
        delay(300);
        int found = WiFi.scanNetworks(false, true);
        int matching = 0;
        String routerPrefix = wifiName;
        int bandSuffix = routerPrefix.lastIndexOf('_');
        if (bandSuffix > 0) routerPrefix = routerPrefix.substring(0, bandSuffix);
        Serial.printf("Wi-Fi scan: %d networks visible\n", found);
        for (int i = 0; i < found; ++i) {
          if (WiFi.SSID(i).startsWith(routerPrefix)) {
            ++matching;
            Serial.printf("Matching router: %s | channel=%d | signal=%d dBm | auth=%d\n",
              WiFi.SSID(i).c_str(), WiFi.channel(i), WiFi.RSSI(i), int(WiFi.encryptionType(i)));
          }
        }
        if (found < 0) Serial.println("Wi-Fi scan failed; no network visibility conclusion available.");
        else if (!matching) Serial.println("No matching router network visible on 2.4 GHz.");
        WiFi.scanDelete();
        WiFi.setAutoReconnect(true);
        WiFi.begin(wifiName.c_str(), wifiPassword.c_str());
      }
      diagnosticLine = "";
    } else if (c != '\r' && diagnosticLine.length() < 40) diagnosticLine += c;
  }
  bool down; int16_t x = touchX, y = touchY;
  if (!mouseOnly && screen.readTouch(down, x, y)) {
    lastTouchReport = millis();
    if (down || touching) {
      if (backlight.touch()) wakeTouch = true;
      lastInteraction = millis();
    }
    if (x < 0 || y < 0) pressedButton = -1;
    if (down) {
      touchX = x; touchY = y;
      if (!touching) pressedButton = wakeTouch ? -1 : hit(x, y);
      else if (hit(x, y) != pressedButton) pressedButton = -1;
    } else if (touching) {
      int id = pressedButton; pressedButton = -1; touching = false;
      if (id >= 0) act(id);
      wakeTouch = false;
    }
    touching = down;
  }
  if (touching && uint32_t(millis() - lastTouchReport) > 1000) { touching = false; pressedButton = -1; wakeTouch = false; }
  pollMouse();
  if (!mouse.held) pollConnection();
  if (!touching && !mouse.held && configured && uint32_t(millis() - lastPoll) >= 3000) {
    lastPoll = millis();
    if (WiFi.status() == WL_CONNECTED && !connectionView()) {
      if (!lastMenu || (view == MENU && uint32_t(millis() - lastMenu) > 60000)) refreshMenu();
      if (refreshState() && (message.startsWith("Connecting") || message.startsWith("OFFLINE") || message.startsWith("SYNC FAILED")))
        message = state["low_stock"].as<bool>() ? "Connected. Low stock: check staff Inventory." : "Connected. Ready for orders.";
    } else if (WiFi.status() != WL_CONNECTED && !connectionView()) {
      stateGood = false;
      message = WiFi.status() == WL_NO_SSID_AVAIL ? String("Wi-Fi network not found: ") + wifiName
        : WiFi.status() == WL_CONNECT_FAILED ? "Wi-Fi connection failed. Check the saved password."
        : "OFFLINE. Check Wi-Fi. No payment action is confirmed.";
    }
    Serial.printf("Wi-Fi status=%d | IP=%s | queue=%s | orders=%u\n",
      int(WiFi.status()), WiFi.localIP().toString().c_str(), fresh() ? "current" : "stale", unsigned(state["orders"].size()));
    if (!api.error.isEmpty()) Serial.println(api.error);
    if (view == SUMMARY && uint32_t(millis() - lastSummaryPoll) >= 30000) refreshSummary();
    render();
  }
  // Keep the cracked-touch cashier readable without requiring a wake tap.
  // Its 25% idle setting was reported as a black screen; full brightness works.
  backlight.update(false);
  delay(10);
}
