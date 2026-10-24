#include <TeaFlowDisplay.h>

TeaFlowDisplay screen;
void setup() {
  Serial.begin(115200);
  if (!screen.begin()) {
    Serial.println("Display init failed. Select ESP32-S3 with OPI PSRAM, 16MB flash and USB CDC disabled.");
    while (true) delay(1000);
  }
  auto& g = screen.gfx;
  g.fillScreen(0xFFFF);
  g.setTextColor(0x022A); g.setTextSize(3);
  g.setCursor(70, 80); g.println("TeaFlow cashier display test");
  g.setTextSize(2); g.setCursor(70, 140);
  g.printf("PSRAM: %u MB | Touch: 0x%02X", unsigned(ESP.getPsramSize() / 1048576), screen.touchAddress);
  g.setCursor(70, 180); g.println("Tap each corner, then drag across the screen.");
  g.setCursor(70, 215); g.println("No Wi-Fi or orders are used in this test.");
  const uint16_t colors[] = {0xF800, 0x07E0, 0x001F, 0xFFE0};
  const int positions[][2] = {{20,20}, {760,20}, {20,440}, {760,440}};
  for (int i = 0; i < 4; ++i) g.fillCircle(positions[i][0], positions[i][1], 16, colors[i]);
  if (!screen.touchAddress) {
    g.setTextColor(0xF800); g.setCursor(70, 270); g.println("Touch not detected. Do not upload cashier yet.");
  }
}
void loop() {
  bool down; int16_t x = 0, y = 0;
  if (screen.readTouch(down, x, y) && down) {
    screen.gfx.fillCircle(x, y, 4, 0x022A);
    screen.gfx.fillRect(70, 320, 600, 30, 0xFFFF);
    screen.gfx.setCursor(70, 320);
    screen.gfx.printf("Touch x=%d y=%d", x, y);
    Serial.printf("Touch x=%d y=%d\n", x, y);
  }
  delay(10);
}
