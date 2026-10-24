#pragma once

// A laptop is the USB host. Only the cashier UART accepts this protocol;
// kitchen firmware does not. Input uses the existing hit targets/actions.
struct CashierMouse {
  bool linked = false, held = false, painted = false, wakeOnly = false;
  int x = 400, y = 240, savedX = 0, savedY = 0, savedW = 0, savedH = 0;
  int pressId = -1, downX = 0, downY = 0;
  uint32_t lastPacket = 0, downAt = 0, sequence = 0;
  uint16_t under[14 * 22] = {};

  void cancel() { held = false; pressId = -1; wakeOnly = false; }
  void hide(Arduino_RGB_Display& g) {
    if (!painted) return;
    g.draw16bitRGBBitmap(savedX, savedY, under, savedW, savedH);
    painted = false;
  }
  void show(Arduino_RGB_Display& g) {
    if (!linked || painted) return;
    savedX = x; savedY = y; savedW = min(14, 800 - x); savedH = min(22, 480 - y);
    const uint16_t* pixels = g.getFramebuffer();
    for (int row = 0; row < savedH; ++row)
      for (int col = 0; col < savedW; ++col)
        under[row * savedW + col] = pixels[(y + row) * 800 + x + col];
    g.fillTriangle(x, y, x, y + 20, x + 13, y + 13, 0x0000);
    g.fillTriangle(x + 2, y + 5, x + 2, y + 15, x + 9, y + 12, 0xFFFF);
    painted = true;
  }
} mouse;

bool mouseOnly = false;
