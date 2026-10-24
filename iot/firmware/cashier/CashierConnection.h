#pragma once

// Touchscreen Wi-Fi setup. Connection settings are saved separately from pending orders.
String draftSsid, draftPassword, draftApi;
String editValue;
enum EditField { SSID_FIELD, WIFI_PASSWORD_FIELD, API_FIELD };
EditField editField = SSID_FIELD;
bool keyboardUpper = false, keyboardSymbols = false;
View keyboardReturn = NETWORK;
struct NetworkChoice { String ssid; int rssi; bool open; };
NetworkChoice networks[30];
int networkCount = 0, networkPage = 0;
bool scanning = false;
uint32_t scanStarted = 0;
int lastWifiStatus = -1;

bool connectionView() { return view == NETWORK || view == NETWORK_SCAN || view == KEYBOARD; }
String masked(const String& value) {
  String result;
  for (unsigned i = 0; i < value.length(); ++i) result += '*';
  return result;
}
bool validApi(String value) {
  if (!value.startsWith("http://") || value.length() > 120) return false;
  String host = value.substring(7);
  int colon = host.indexOf(':');
  if (colon >= 0) {
    String port = host.substring(colon + 1);
    if (port.isEmpty() || port.length() > 5) return false;
    for (unsigned i = 0; i < port.length(); ++i) if (!isDigit(port[i])) return false;
    if (port.toInt() < 1 || port.toInt() > 65535) return false;
    host = host.substring(0, colon);
  }
  if (host.isEmpty() || host == "localhost" || host == "127.0.0.1") return false;
  for (unsigned i = 0; i < host.length(); ++i)
    if (!isAlphaNumeric(host[i]) && host[i] != '.' && host[i] != '-') return false;
  return true;
}
bool validWifiPassword(const String& value) {
  if (value.isEmpty()) return true; // Open networks have no password.
  if (value.length() == 64) {
    for (unsigned i = 0; i < value.length(); ++i) if (!isHexadecimalDigit(value[i])) return false;
    return true;
  }
  return value.length() >= 8 && value.length() <= 63;
}
void updateConfigured() {
  configured = !wifiName.isEmpty() && wifiName != "YOUR_WIFI_SSID"
    && wifiPassword != "YOUR_WIFI_PASSWORD" && validApi(apiAddress)
    && String(DEVICE_KEY).length() > 0 && String(DEVICE_KEY) != "YOUR_CASHIER_DEVICE_KEY";
}
void loadConnection() {
  if (storageGood) {
    JsonDocument saved;
    if (!deserializeJson(saved, settings.getString("connection", ""))
        && saved["ssid"].is<String>() && saved["password"].is<String>() && saved["api"].is<String>()
        && saved["ssid"].as<String>().length() > 0 && saved["ssid"].as<String>().length() <= 32
        && validWifiPassword(saved["password"].as<String>()) && validApi(saved["api"].as<String>())) {
      wifiName = saved["ssid"].as<String>(); wifiPassword = saved["password"].as<String>(); apiAddress = saved["api"].as<String>();
    }
  }
  api.setBase(apiAddress);
  updateConfigured();
}
void resetConnectionCache() {
  stateGood = false; editValue = "";
  state.clear(); menu.clear(); cart.clear(); lastState = 0; lastMenu = 0; page = 0;
  summary.clear(); summaryGood = false; lastSummary = 0; lastSummaryPoll = 0;
  // The separately persisted pending submission must survive connection changes.
}
void openNetwork() {
  draftSsid = wifiName; draftPassword = wifiPassword; draftApi = apiAddress;
  view = NETWORK;
  message = "Save clears the draft cart. Saved submissions stay. Use a 2.4 GHz network shared with the laptop.";
}
void startScan() {
  if (scanning) return;
  WiFi.mode(WIFI_STA); WiFi.scanDelete();
  networkCount = 0; networkPage = 0;
  scanning = WiFi.scanNetworks(true, false) == WIFI_SCAN_RUNNING;
  scanStarted = millis(); view = NETWORK_SCAN;
  message = scanning ? "Scanning nearby 2.4 GHz networks..." : "Scan could not start. Try Scan again or enter the name.";
}
void finishScan(int found) {
  networkCount = 0;
  for (int i = 0; i < found && networkCount < 30; ++i) {
    String ssid = WiFi.SSID(i);
    if (ssid.isEmpty()) continue;
    bool duplicate = false;
    for (int n = 0; n < networkCount; ++n) if (networks[n].ssid == ssid) duplicate = true;
    if (!duplicate) networks[networkCount++] = {ssid, WiFi.RSSI(i), WiFi.encryptionType(i) == WIFI_AUTH_OPEN};
  }
  WiFi.scanDelete(); scanning = false;
  if (view == NETWORK_SCAN) message = found < 0 ? "Scan failed. Try again or enter the network name." : networkCount ? "Tap a network, then enter its password." : "No networks found. Enter the name for a hidden network.";
}
String fieldName() {
  return editField == SSID_FIELD ? "Wi-Fi network name" : editField == WIFI_PASSWORD_FIELD ? "Wi-Fi password" : "Laptop API address";
}
void openKeyboard(EditField field) {
  editField = field; keyboardReturn = view; keyboardUpper = false; keyboardSymbols = false;
  editValue = field == SSID_FIELD ? draftSsid : field == WIFI_PASSWORD_FIELD ? draftPassword : draftApi;
  view = KEYBOARD; message = "Type on the screen. Done keeps this field; Cancel discards edits.";
}
void renderConnectionView() {
  if (view == NETWORK) {
    textAt(16, 66, "Wi-Fi and laptop connection", UI_INK, 3, 40);
    textAt(16, 108, "Network name (SSID)");
    button(51, 16, 130, 560, 44, draftSsid.isEmpty() ? "Enter network name" : draftSsid);
    button(54, 590, 130, 194, 44, "Scan Wi-Fi");
    textAt(16, 184, "Wi-Fi password (leave empty for open Wi-Fi)");
    button(52, 16, 206, 768, 44, draftPassword.isEmpty() ? "No password" : masked(draftPassword));
    textAt(16, 260, "Laptop API address | http://LAPTOP_IP:5000");
    button(53, 16, 282, 768, 44, draftApi);
    button(55, 16, 356, 490, 52, "Save and connect", storageGood && !scanning);
    button(56, 520, 356, 264, 52, "Cancel");
  } else if (view == NETWORK_SCAN) {
    textAt(16, 66, scanning ? "Scanning Wi-Fi..." : "Choose a 2.4 GHz network", UI_INK, 3, 40);
    networkPage = constrain(networkPage, 0, max(0, (networkCount - 1) / 5));
    for (int i = 0; i < 5 && networkPage * 5 + i < networkCount; ++i) {
      int n = networkPage * 5 + i;
      button(5000 + n, 16, 108 + i * 46, 768, 42, networks[n].ssid + " | " + String(networks[n].rssi) + " dBm | " + (networks[n].open ? "open" : "secured"));
    }
    button(57, 16, 354, 142, 54, "Previous", networkPage > 0 && !scanning);
    button(58, 172, 354, 142, 54, "Next", (networkPage + 1) * 5 < networkCount && !scanning);
    button(54, 328, 354, 190, 54, "Scan again", !scanning);
    button(59, 532, 354, 252, 54, "Enter / Back");
  } else if (view == KEYBOARD) {
    textAt(16, 62, fieldName(), UI_INK, 2, 62);
    bool secret = editField == WIFI_PASSWORD_FIELD;
    String display = secret ? masked(editValue) : editValue;
    textAt(16, 90, display.length() > 62 ? display.substring(display.length() - 62) : display, UI_INK, 2, 63);
    const char* letters[] = {"qwertyuiop", "asdfghjkl", "zxcvbnm"};
    const char* symbols[] = {"1234567890", "!@#$%^&*()", "-_=+[]{}:;", "\"'\\|,.<>/?`~"};
    int rows = keyboardSymbols ? 4 : 3;
    for (int row = 0; row < rows; ++row) {
      String keys = keyboardSymbols ? symbols[row] : letters[row];
      if (keyboardUpper && !keyboardSymbols) keys.toUpperCase();
      for (unsigned col = 0; col < keys.length(); ++col) {
        int width = 768 / keys.length();
        button(6000 + uint8_t(keys[col]), 16 + col * width, 124 + row * 49, width - 5, 44, String(keys[col]));
      }
    }
    button(60, 16, 324, 140, 40, keyboardSymbols ? "ABC" : "123 / #");
    button(61, 166, 324, 116, 40, keyboardUpper ? "lower" : "UPPER", !keyboardSymbols);
    button(62, 292, 324, 200, 40, "Space");
    button(63, 502, 324, 132, 40, "Delete");
    button(64, 644, 324, 140, 40, "Clear");
    button(65, 16, 374, 376, 40, "Done");
    button(66, 408, 374, 376, 40, "Cancel");
  }
}
String connectionScreenState() {
  // Secret content is represented only by length, matching the masked screen.
  String result = String(WiFi.status()) + "|" + wifiName + "|" + WiFi.localIP().toString();
  if (view == NETWORK) result += draftSsid + "|" + String(draftPassword.length()) + "|" + draftApi + "|" + String(scanning);
  if (view == NETWORK_SCAN) {
    result += String(scanning) + "|" + String(networkPage);
    for (int i = 0; i < networkCount; ++i) result += networks[i].ssid + "|" + String(networks[i].rssi) + String(networks[i].open);
  }
  if (view == KEYBOARD) result += String(editField) + String(keyboardUpper) + String(keyboardSymbols)
    + (editField == WIFI_PASSWORD_FIELD ? String(editValue.length()) : editValue);
  return result;
}
void saveConnection() {
  draftApi.trim();
  while (draftApi.endsWith("/")) draftApi.remove(draftApi.length() - 1);
  if (draftSsid.isEmpty() || draftSsid.length() > 32) { message = "Network name must contain 1 to 32 bytes."; return; }
  if (!validWifiPassword(draftPassword)) { message = "Use 8-63 password characters, 64 hex digits, or empty for open Wi-Fi."; return; }
  if (!validApi(draftApi)) { message = "Enter http://LAPTOP_IP:5000 (no paths or localhost)."; return; }
  JsonDocument saved;
  saved["ssid"] = draftSsid; saved["password"] = draftPassword; saved["api"] = draftApi;
  String payload; serializeJson(saved, payload);
  if (!storageGood || settings.putString("connection", payload) != payload.length()) {
    message = "Could not save settings. Current connection kept."; return;
  }
  resetConnectionCache();
  wifiName = draftSsid; wifiPassword = draftPassword; apiAddress = draftApi;
  draftPassword = ""; api.setBase(apiAddress); api.lastStatus = 0; api.error = "";
  updateConfigured();
  WiFi.setAutoReconnect(false); WiFi.disconnect(false, false);
  WiFi.persistent(false); WiFi.mode(WIFI_STA); WiFi.setAutoReconnect(true);
  WiFi.begin(wifiName.c_str(), wifiPassword.c_str());
  view = MENU; message = "Settings saved. Connecting to Wi-Fi...";
}
bool actConnection(int id) {
  if (id == 40) openNetwork();
  else if (id == 51 && view == NETWORK) openKeyboard(SSID_FIELD);
  else if (id == 52 && view == NETWORK) openKeyboard(WIFI_PASSWORD_FIELD);
  else if (id == 53 && view == NETWORK) openKeyboard(API_FIELD);
  else if (id == 54 && (view == NETWORK || view == NETWORK_SCAN)) startScan();
  else if (id == 55 && view == NETWORK) saveConnection();
  else if (id == 56 && view == NETWORK) {
    draftPassword = ""; view = UI_STATUS;
    message = "Network changes discarded.";
  } else if (id == 57 && view == NETWORK_SCAN) --networkPage;
  else if (id == 58 && view == NETWORK_SCAN) ++networkPage;
  else if (id == 59 && view == NETWORK_SCAN) { view = NETWORK; message = "Edit the fields, then Save and connect."; }
  else if (id >= 5000 && id < 5000 + networkCount && view == NETWORK_SCAN && !scanning) {
    String selected = networks[id - 5000].ssid;
    if (selected != draftSsid || networks[id - 5000].open) draftPassword = "";
    draftSsid = selected; view = NETWORK;
    message = "Network selected. Enter its password and check the laptop address.";
  } else if (view == KEYBOARD && id >= 6033 && id <= 6126) {
    unsigned limit = editField == SSID_FIELD ? 32 : editField == WIFI_PASSWORD_FIELD ? 64 : 120;
    if (editValue.length() < limit) editValue += char(id - 6000);
  } else if (id == 60 && view == KEYBOARD) keyboardSymbols = !keyboardSymbols;
  else if (id == 61 && view == KEYBOARD) keyboardUpper = !keyboardUpper;
  else if (id == 62 && view == KEYBOARD) {
    unsigned limit = editField == SSID_FIELD ? 32 : editField == WIFI_PASSWORD_FIELD ? 64 : 120;
    if (editValue.length() < limit) editValue += ' ';
  } else if (id == 63 && view == KEYBOARD && editValue.length()) {
    // Remove a complete UTF-8 codepoint when editing a scanned network name.
    unsigned last = editValue.length() - 1;
    while (last > 0 && (uint8_t(editValue[last]) & 0xC0) == 0x80) --last;
    editValue.remove(last);
  } else if (id == 64 && view == KEYBOARD) editValue = "";
  else if (id == 65 && view == KEYBOARD) {
    if (editField == SSID_FIELD) { if (draftSsid != editValue) draftPassword = ""; draftSsid = editValue; }
    else if (editField == WIFI_PASSWORD_FIELD) draftPassword = editValue;
    else draftApi = editValue;
    editValue = ""; view = keyboardReturn; message = "Field updated. Save and connect when ready.";
  } else if (id == 66 && view == KEYBOARD) { editValue = ""; view = keyboardReturn; message = "Field edits discarded."; }
  else return false;
  return true;
}
void pollConnection() {
  if (scanning && !touching) {
    int found = WiFi.scanComplete();
    if (found != WIFI_SCAN_RUNNING) { finishScan(found); render(); }
    else if (uint32_t(millis() - scanStarted) > 20000) { finishScan(-2); render(); }
  }
  int current = WiFi.status();
  if (current != lastWifiStatus && !touching) {
    lastWifiStatus = current;
    if (view == UI_STATUS || view == NETWORK) {
      if (current == WL_CONNECTED) message = "Wi-Fi connected. Return to ordering or save your network changes.";
      else if (current == WL_CONNECT_FAILED) message = "Wi-Fi connection failed. Open Wi-Fi setup and check the password.";
      else if (current == WL_NO_SSID_AVAIL) message = "Network not found. Choose a nearby 2.4 GHz network.";
    }
    render();
  }
}
