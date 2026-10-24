#pragma once
#include <Arduino.h>

// Read-only UART diagnostic. Run-length RGB565 keeps a capture brief even on
// the cashier's 115200-baud CH340. No order actions or settings are changed.
inline void teaFlowScreenCapture(Print& out, const uint16_t* pixels, int width, int height, int rotation) {
  const uint32_t count = uint32_t(width) * height;
  uint32_t runs = 0;
  for (uint32_t i = 0; i < count;) {
    const uint16_t pixel = pixels[i]; uint32_t end = i + 1;
    while (end < count && end - i < 65535 && pixels[end] == pixel) ++end;
    ++runs; i = end;
  }
  out.printf("\nTFSCREEN %d %d %d %u\n", width, height, rotation, unsigned(runs * 4));
  for (uint32_t i = 0; i < count;) {
    const uint16_t pixel = pixels[i]; uint32_t end = i + 1;
    while (end < count && end - i < 65535 && pixels[end] == pixel) ++end;
    const uint16_t length = end - i;
    const uint8_t packet[] = {uint8_t(length), uint8_t(length >> 8), uint8_t(pixel), uint8_t(pixel >> 8)};
    out.write(packet, sizeof(packet)); i = end;
  }
  out.println("\nTFSCREEN END");
}
