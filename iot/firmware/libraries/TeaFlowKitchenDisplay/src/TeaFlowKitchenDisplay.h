#pragma once
#include <Arduino_GFX_Library.h>
#include <Wire.h>
#include <driver/spi_master.h>
#include <esp_heap_caps.h>
#include "ST77922Init.h"

// ES3C35P only. Pin map, protocol, and init table come from the manufacturer's
// resource pack linked in iot/firmware/README.md. Never use this on the cashier PCB.
class KitchenCanvas : public Arduino_Canvas {
 public:
  KitchenCanvas() : Arduino_Canvas(320, 480, nullptr, 0, 0, 1) {}
  bool begin(int32_t = GFX_NOT_DEFINED) override {
    if (!_framebuffer) _framebuffer = static_cast<uint16_t*>(
      heap_caps_malloc(320 * 480 * 2, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    return _framebuffer != nullptr;
  }
};

class TeaFlowKitchenDisplay {
 public:
  KitchenCanvas gfx;
  uint8_t touchAddress = 0;
  const char* initError = "none";
  bool begin() {
    // Keep the active-low amplifier muted while the display initializes.
    // KitchenAudio unmutes it only during an alert or an explicit sound test.
    pinMode(1, OUTPUT); digitalWrite(1, HIGH);
    pinMode(41, OUTPUT); digitalWrite(41, LOW);
    pinMode(10, OUTPUT); digitalWrite(10, HIGH);
    if (!psramFound()) { initError = "PSRAM not detected"; return false; }
    if (!gfx.begin()) { initError = "framebuffer allocation"; return false; }
    tx_ = static_cast<uint16_t*>(heap_caps_malloc(320 * 4 * 2, MALLOC_CAP_DMA));
    if (!tx_) { initError = "DMA allocation"; return false; }
    spi_bus_config_t bus = {};
    bus.mosi_io_num = 11; bus.miso_io_num = 13; bus.sclk_io_num = 12;
    bus.quadwp_io_num = 14; bus.quadhd_io_num = 9;
    bus.data4_io_num = bus.data5_io_num = bus.data6_io_num = bus.data7_io_num = -1;
    bus.max_transfer_sz = 320 * 4 * 2;
    bus.flags = SPICOMMON_BUSFLAG_MASTER | SPICOMMON_BUSFLAG_GPIO_PINS | SPICOMMON_BUSFLAG_QUAD;
    if (spi_bus_initialize(SPI2_HOST, &bus, SPI_DMA_CH_AUTO) != ESP_OK) { initError = "QSPI bus init"; return false; }
    spi_device_interface_config_t device = {};
    device.command_bits = 8; device.address_bits = 24;
    device.clock_speed_hz = 40000000; device.spics_io_num = -1;
    device.flags = SPI_DEVICE_HALFDUPLEX; device.queue_size = 1;
    if (spi_bus_add_device(SPI2_HOST, &device, &spi_) != ESP_OK) { initError = "QSPI device init"; return false; }
    delay(150);
    for (const auto& init : kitchenPanelInit) {
      if (!command(init.cmd, init.data, init.length)) { initError = "panel register write"; return false; }
      if (init.delayMs) delay(init.delayMs);
    }
    gfx.fillScreen(0xFFFF);
    if (!flush()) { initError = "panel framebuffer write"; return false; }
    digitalWrite(41, HIGH);

    Wire.begin(38, 39, 100000); Wire.setTimeOut(30);
    pinMode(47, INPUT);
    pinMode(48, OUTPUT); digitalWrite(48, LOW); delay(100);
    digitalWrite(48, HIGH); delay(100);
    // Integrated ST77922 touch has 16-bit registers at 0x55; it is NOT the
    // common FT6336 0x38 / 8-bit-register protocol described in some listings.
    uint8_t status = 0xFF;
    for (int i = 0; i < 30; ++i) {
      if (readRegister(0x0001, &status, 1) && !(status & 0x0F)) {
        touchAddress = 0x55; break;
      }
      delay(10);
    }
    return true;
  }

  // Only complete reports may release or press a button. Bus errors are not
  // releases. Ignore multiple fingers so gestures cannot trigger an action.
  bool readTouch(bool& down, int16_t& x, int16_t& y) {
    if (!touchAddress) return false;
    uint8_t info, points[70];
    if (!readRegister(0x0010, &info, 1)) return false;
    if (!(info & 0x08)) { down = false; x = lastTouchX_; y = lastTouchY_; return true; }
    if (!readRegister(0x0014, points, sizeof(points))) return false;
    int active = 0, rawX = 0, rawY = 0;
    for (int i = 0; i < 10; ++i) {
      const uint8_t* p = points + i * 7;
      if (!(p[0] & 0x80)) continue;
      ++active; rawX = ((p[0] & 0x3F) << 8) | p[1];
      rawY = ((p[2] & 0x3F) << 8) | p[3];
    }
    down = active == 1 && rawX < 320 && rawY < 480;
    x = down ? rawY : -1;
    y = down ? 319 - rawX : -1;
    if (down) { lastTouchX_ = x; lastTouchY_ = y; }
    return true;
  }

  // Always flush a complete portrait framebuffer (4-column-aligned windows).
  // Canvas rotation handles landscape without the vendor driver's partial
  // rectangle rotation/indexing bugs. Swap RGB565 into DMA RAM, not in PSRAM.
  bool flush() {
    if (!spi_ || !tx_) return false;
    const uint8_t columns[] = {0, 0, 1, 0x3F}, rows[] = {0, 0, 1, 0xDF};
    if (!command(0x2A, columns, 4) || !command(0x2B, rows, 4)) return false;
    uint16_t* frame = gfx.getFramebuffer();
    bool ok = true;
    digitalWrite(10, LOW);
    for (int offset = 0; offset < 320 * 480; offset += 320 * 4) {
      for (int i = 0; i < 320 * 4; ++i) {
        const uint16_t pixel = frame[offset + i];
        tx_[i] = (pixel >> 8) | (pixel << 8);
      }
      spi_transaction_ext_t t = {};
      t.base.flags = SPI_TRANS_MODE_QIO | SPI_TRANS_VARIABLE_CMD | SPI_TRANS_VARIABLE_ADDR;
      t.base.cmd = 0x32; t.base.addr = 0x003C00;
      t.command_bits = offset == 0 ? 8 : 0;
      t.address_bits = offset == 0 ? 24 : 0;
      t.base.tx_buffer = tx_; t.base.length = 320 * 4 * 16;
      if (spi_device_polling_transmit(spi_, &t.base) != ESP_OK) { ok = false; break; }
    }
    digitalWrite(10, HIGH);
    return ok;
  }

 private:
  spi_device_handle_t spi_ = nullptr;
  int16_t lastTouchX_ = -1, lastTouchY_ = -1;
  uint16_t* tx_ = nullptr;
  bool command(uint8_t cmd, const uint8_t* data, uint8_t length) {
    spi_transaction_t t = {};
    t.cmd = 0x02; t.addr = uint32_t(cmd) << 8;
    // ESP-IDF rejects a non-null TX buffer with zero data bits. Commands such
    // as sleep-out/display-on have only command/address phases.
    t.tx_buffer = length ? data : nullptr; t.length = length * 8;
    digitalWrite(10, LOW);
    const bool ok = spi_device_polling_transmit(spi_, &t) == ESP_OK;
    digitalWrite(10, HIGH);
    return ok;
  }
  bool readRegister(uint16_t reg, uint8_t* output, size_t length) {
    Wire.beginTransmission(0x55); Wire.write(reg >> 8); Wire.write(reg & 0xFF);
    if (Wire.endTransmission(false) != 0) return false;
    // ESP32 Wire defaults to a 128-byte buffer; 10 seven-byte points fit.
    if (Wire.requestFrom(uint8_t(0x55), uint8_t(length)) != length) return false;
    for (size_t i = 0; i < length; ++i) output[i] = Wire.read();
    return true;
  }
};
