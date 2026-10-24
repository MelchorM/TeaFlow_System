#include <TeaFlowKitchenDisplay.h>

TeaFlowKitchenDisplay screen;
void setup() {
  Serial.begin(115200);
  delay(1000);
  if (!screen.begin()) {
    while (true) {
      Serial.printf("Kitchen display init failed: %s. PSRAM=%u bytes, free=%u bytes\n", screen.initError, unsigned(ESP.getPsramSize()), unsigned(ESP.getFreePsram()));
      delay(1000);
    }
  }
  auto& g = screen.gfx;
  g.setTextWrap(false); g.setTextColor(0x022A); g.setTextSize(2);
  g.setCursor(44, 50); g.println("TeaFlow kitchen test");
  g.setCursor(44, 80); g.println("ES3C35P / ST77922 QSPI");
  g.setCursor(44, 110); g.printf("PSRAM: %u MB  Touch: 0x%02X", unsigned(ESP.getPsramSize() / 1048576), screen.touchAddress);
  g.setCursor(44, 145); g.println("Tap all corners, then drag.");
  g.setCursor(44, 177); g.println("No Wi-Fi or order actions.");
  const uint16_t colors[] = {0xF800, 0x07E0, 0x001F, 0xFFE0};
  const int positions[][2] = {{20,20}, {459,20}, {20,299}, {459,299}};
  for (int i = 0; i < 4; ++i) g.fillCircle(positions[i][0], positions[i][1], 16, colors[i]);
  if (!screen.touchAddress) {
    g.setTextColor(0xF800); g.setCursor(44, 210); g.println("Touch missing - check board.");
  }
  screen.flush();
  Serial.printf("Kitchen test: PSRAM=%u touch=0x%02X\n", unsigned(ESP.getPsramSize()), screen.touchAddress);
}
void loop() {
  static uint32_t lastReport = 0;
  if (uint32_t(millis() - lastReport) >= 3000) {
    lastReport = millis();
    Serial.printf("Kitchen display test alive: PSRAM=%u touch=0x%02X backlight=%d\n", unsigned(ESP.getPsramSize()), screen.touchAddress, digitalRead(41));
  }
  bool down; int16_t x = 0, y = 0;
  if (screen.readTouch(down, x, y) && down) {
    auto& g = screen.gfx;
    g.fillCircle(x, y, 3, 0x022A);
    g.fillRect(44, 250, 385, 20, 0xFFFF);
    g.setTextColor(0x022A); g.setCursor(44, 250); g.printf("Touch x=%d y=%d", x, y);
    screen.flush();
    Serial.printf("Touch x=%d y=%d\n", x, y);
  }
  delay(15);
}
