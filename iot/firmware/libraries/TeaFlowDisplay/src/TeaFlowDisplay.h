#pragma once
#include <Arduino_GFX_Library.h>
#include <Wire.h>

// Board references and build settings are documented in iot/firmware/README.md.
// GPIO19/20 are touch I2C, so native USB CDC must remain disabled.
class TeaFlowDisplay {
 public:
  Arduino_ESP32RGBPanel panel{
    40, 41, 39, 42,                     // DE, VSYNC, HSYNC, PCLK
    45, 48, 47, 21, 14,                 // R0..R4
    5, 6, 7, 15, 16, 4,                // G0..G5
    8, 3, 46, 9, 1,                     // B0..B4
    0, 8, 4, 8, 0, 8, 4, 8, 1, 16000000
  };
  Arduino_RGB_Display gfx{800, 480, &panel, 0, true};
  uint8_t touchAddress = 0;
  bool begin() {
    pinMode(2, OUTPUT);
    digitalWrite(2, LOW);
    if (!psramFound() || !gfx.begin()) return false;
    gfx.fillScreen(0xFFFF);
    digitalWrite(2, HIGH);
    Wire.begin(19, 20, 400000);
    Wire.setTimeOut(30);
    // Preserve factory touch configuration. No speculative INT/RST pins.
    for (uint8_t address : {uint8_t(0x5D), uint8_t(0x14)}) {
      Wire.beginTransmission(address);
      if (Wire.endTransmission() == 0) {
        touchAddress = address;
        break;
      }
    }
    return true;
  }

  // Returns true only for a new valid controller report. A release is a
  // report with zero points; absence of a new report is not a release.
  bool readTouch(bool& down, int16_t& x, int16_t& y) {
    if (!touchAddress) return false;
    uint8_t status;
    if (!readRegister(0x814E, &status, 1) || !(status & 0x80)) return false;
    const uint8_t count = status & 0x0F;
    uint8_t point[8];
    bool valid = count == 0 || (count == 1 && readRegister(0x814F, point, sizeof(point)));
    Wire.beginTransmission(touchAddress);
    Wire.write(0x81); Wire.write(0x4E); Wire.write(0);
    if (Wire.endTransmission() != 0) return false;
    if (!valid) { down = false; x = y = -1; return true; }
    down = count == 1;
    if (down) {
      x = point[1] | (point[2] << 8);
      y = point[3] | (point[4] << 8);
      if (x >= 800 || y >= 480) { down = false; x = y = -1; }
    }
    return true;
  }
 private:
  bool readRegister(uint16_t reg, uint8_t* output, uint8_t length) {
    Wire.beginTransmission(touchAddress);
    Wire.write(reg >> 8); Wire.write(reg & 0xFF);
    if (Wire.endTransmission(false) != 0) return false;
    if (Wire.requestFrom(touchAddress, length) != length) return false;
    for (uint8_t i = 0; i < length; ++i) output[i] = Wire.read();
    return true;
  }
};
