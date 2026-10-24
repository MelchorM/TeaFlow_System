#pragma once
#include <Arduino.h>
#include <WiFi.h>

// Both boards have active-high backlights. Arduino ESP32 2.0.17 uses the
// channel-based LEDC API. Never stop polling, touch or audio while dimmed.
class TeaFlowIdleBacklight {
 public:
  explicit TeaFlowIdleBacklight(uint8_t pin) : pin_(pin) {}
  uint8_t brightness = 100;
  bool ready = false;
  void begin() {
    ready = ledcSetup(7, 5000, 8) != 0;
    // Configure the output channel before writing its duty. Writing before
    // attach can leave an uninitialized channel dark until the first change.
    if (ready) { ledcAttachPin(pin_, 7); ledcWrite(7, 255); }
    else digitalWrite(pin_, HIGH);
  }
  bool touch() {
    const bool wasDimmed = brightness < 100;
    idleSince_ = millis(); set(100);
    return wasDimmed;
  }
  void update(bool idle) {
    const uint32_t now = millis();
    if (!idle) { eligible_ = false; idleSince_ = now; set(100); return; }
    if (!eligible_) { eligible_ = true; idleSince_ = now; }
    set(uint32_t(now - idleSince_) >= 30000 ? 25 : 100);
  }
 private:
  uint8_t pin_;
  bool eligible_ = false;
  uint32_t idleSince_ = 0;
  void set(uint8_t percent) {
    if (brightness == percent) return;
    brightness = ready ? percent : 100;
    if (ready) ledcWrite(7, (255 * brightness + 50) / 100);
  }
};

inline int teaFlowSignalBars() {
  static uint32_t sampled = 0;
  static int bars = 0;
  if (WiFi.status() != WL_CONNECTED) { bars = 0; sampled = 0; return 0; }
  if (!sampled || uint32_t(millis() - sampled) >= 5000) {
    sampled = millis();
    const int rssi = WiFi.RSSI();
    const int thresholds[] = {-85, -75, -67, -55};
    // Hysteresis avoids repainting for a one-dBm fluctuation at a boundary.
    while (bars < 4 && rssi >= thresholds[bars] + 3) ++bars;
    while (bars > 0 && rssi < thresholds[bars - 1] - 3) --bars;
  }
  return bars;
}

inline String teaFlowSyncLabel(uint32_t lastSync) {
  if (!lastSync) return "No sync yet";
  const uint32_t seconds = uint32_t(millis() - lastSync) / 1000;
  if (seconds < 10) return "Sync now";
  if (seconds < 60) return "Sync " + String(seconds / 10 * 10) + "s ago";
  if (seconds < 3600) return "Sync " + String(seconds / 60) + "m ago";
  return "Sync " + String(seconds / 3600) + "h ago";
}

template <typename Canvas>
inline void teaFlowSignalIcon(Canvas& g, int x, int y, uint16_t active, uint16_t inactive) {
  const int bars = teaFlowSignalBars();
  for (int i = 0; i < 4; ++i) g.fillRect(x + i * 6, y + 15 - i * 4, 4, 5 + i * 4, i < bars ? active : inactive);
}
