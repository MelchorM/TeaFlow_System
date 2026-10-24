#pragma once
#include <Arduino_GFX_Library.h>

namespace TeaFlowTheme {
constexpr uint16_t rgb(int r, int g, int b) { return ((r & 248) << 8) | ((g & 252) << 3) | (b >> 3); }
constexpr uint16_t background = rgb(246, 248, 243), white = 0xFFFF,
  ink = rgb(25, 49, 43), green = rgb(32, 107, 82), pale = rgb(226, 240, 230),
  muted = rgb(104, 122, 112), border = rgb(213, 223, 215), disabled = rgb(233, 236, 230),
  red = rgb(181, 57, 57), yellow = rgb(255, 210, 87), blue = rgb(51, 100, 157),
  bluePale = rgb(226, 235, 246), amberPale = rgb(255, 243, 204);

inline void card(Arduino_GFX& g, int x, int y, int w, int h) {
  g.fillRoundRect(x, y + 2, w, h, 8, border);
  g.fillRoundRect(x, y, w, h, 8, white);
}
inline void cup(Arduino_GFX& g, int x, int y, uint16_t color) {
  g.drawRoundRect(x + 2, y + 7, 19, 23, 3, color);
  g.drawFastHLine(x, y + 6, 24, color);
  g.drawLine(x + 13, y + 7, x + 17, y, color);
  g.drawFastHLine(x + 5, y + 17, 13, color);
  g.fillCircle(x + 8, y + 24, 1, color); g.fillCircle(x + 15, y + 25, 1, color);
}
inline void check(Arduino_GFX& g, int x, int y, uint16_t color) {
  for (int d = 0; d < 3; ++d) {
    g.drawLine(x, y + 9 + d, x + 8, y + 17 + d, color);
    g.drawLine(x + 8, y + 17 + d, x + 25, y + d, color);
  }
}
// Scalable version of the TeaFlow cup mark used in both terminal headers.
inline void logo(Arduino_GFX& g, int cx, int cy, int radius) {
  const int u = radius / 24;
  g.fillCircle(cx, cy, radius, pale);
  g.fillCircle(cx, cy, radius - 6, green);
  for (int d = 0; d < u; ++d)
    g.drawLine(cx + 2 * u + d, cy - 10 * u, cx + 7 * u + d, cy - 21 * u, white);
  g.fillRoundRect(cx - 9 * u, cy - 10 * u, 18 * u, 24 * u, 3 * u, white);
  g.fillRoundRect(cx - 7 * u, cy + u, 14 * u, 11 * u, 2 * u, pale);
  g.fillRoundRect(cx - 11 * u, cy - 12 * u, 22 * u, 3 * u, u, white);
  g.fillCircle(cx - 4 * u, cy + 7 * u, u, green);
  g.fillCircle(cx + 3 * u, cy + 8 * u, u, green);
  g.fillCircle(cx, cy + 4 * u, u, green);
}
}
