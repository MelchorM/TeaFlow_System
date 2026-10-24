// SPDX-FileCopyrightText: 2015-2022 Espressif Systems (Shanghai) CO LTD
// SPDX-License-Identifier: Apache-2.0
// Fixed-rate ES8311 clock/register setup adapted from the supplier's Espressif
// ES8311 example. See ES8311_NOTICE.md and LICENSE-ES8311.txt.
#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <driver/i2s.h>
#include <math.h>

class KitchenAudio {
 public:
  volatile bool ready = false, busy = false;
  volatile uint8_t volume = 50;
  const char* error = "not initialized";

  // Display.begin() has already started the shared touch/codec Wire bus.
  bool begin() {
    pinMode(1, OUTPUT); digitalWrite(1, HIGH); // Active-low amplifier, muted.
    Wire.beginTransmission(0x18);
    if (Wire.endTransmission() != 0) { error = "ES8311 not detected"; return false; }
    i2s_config_t config = {};
    config.mode = i2s_mode_t(I2S_MODE_MASTER | I2S_MODE_TX);
    config.sample_rate = RATE;
    config.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
    config.channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT;
    config.communication_format = I2S_COMM_FORMAT_STAND_I2S;
    config.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
    config.dma_buf_count = 4; config.dma_buf_len = 128;
    config.tx_desc_auto_clear = true;
    config.mclk_multiple = I2S_MCLK_MULTIPLE_256;
    if (i2s_driver_install(I2S_NUM_0, &config, 0, nullptr) != ESP_OK) { error = "I2S driver init failed"; return false; }
    i2s_pin_config_t pins = {};
    pins.mck_io_num = 17; pins.bck_io_num = 18; pins.ws_io_num = 21;
    pins.data_out_num = 15; pins.data_in_num = I2S_PIN_NO_CHANGE;
    if (i2s_set_pin(I2S_NUM_0, &pins) != ESP_OK || !initializeCodec()) {
      i2s_driver_uninstall(I2S_NUM_0); error = "I2S pins or codec setup failed"; return false;
    }
    i2s_zero_dma_buffer(I2S_NUM_0);
    if (xTaskCreate(worker, "kitchen-alert", 4096, this, 1, &task_) != pdPASS) {
      i2s_driver_uninstall(I2S_NUM_0); error = "Audio task allocation failed"; return false;
    }
    ready = true; error = "";
    uint8_t id1 = 0, id2 = 0;
    read(0xFD, id1); read(0xFE, id2);
    Serial.printf("Kitchen speaker ready: ES8311=0x%02X%02X | PCM=16000 Hz | volume=%u%%\n", id1, id2, unsigned(volume));
    return true;
  }

  void play() {
    if (!ready || !task_ || busy) return;
    stopRequested_ = false;
    busy = true;
    xTaskNotifyGive(task_); // Playback never blocks touch or HTTP polling.
  }
  void stop() { stopRequested_ = true; }

 private:
  static constexpr int RATE = 16000;
  TaskHandle_t task_ = nullptr;
  volatile bool stopRequested_ = false;
  bool write(uint8_t reg, uint8_t value) {
    Wire.beginTransmission(0x18); Wire.write(reg); Wire.write(value);
    return Wire.endTransmission() == 0;
  }
  bool read(uint8_t reg, uint8_t& value) {
    Wire.beginTransmission(0x18); Wire.write(reg);
    if (Wire.endTransmission(false) != 0 || Wire.requestFrom(uint8_t(0x18), uint8_t(1)) != 1) return false;
    value = Wire.read(); return true;
  }
  bool update(uint8_t reg, uint8_t keep, uint8_t value) {
    uint8_t previous;
    return read(reg, previous) && write(reg, (previous & keep) | value);
  }
  bool initializeCodec() {
    if (!write(0x00, 0x1F)) return false;
    delay(20);
    if (!write(0x00, 0x00) || !write(0x00, 0x80)) return false;
    // Supplier coefficient: 4.096 MHz MCLK / 16 kHz, 256fs, slave I2S,
    // 16-bit stereo slots. Clock inversion disabled.
    if (!write(0x01, 0x3F) || !update(0x06, 0xDF, 0)
        || !update(0x02, 0x07, 0) || !write(0x03, 0x10) || !write(0x04, 0x10)
        || !write(0x05, 0) || !update(0x06, 0xE0, 0x03)
        || !update(0x07, 0xC0, 0) || !write(0x08, 0xFF)
        || !update(0x00, 0xBF, 0) || !write(0x09, 0x0C) || !write(0x0A, 0x0C)) return false;
    const uint8_t analog[][2] = {{0x0D,0x01},{0x0E,0x02},{0x12,0x00},{0x13,0x10},
      // ES8311 0xBF is 0 dB. Scale PCM below full scale rather than clipping
      // it with the codec's positive digital gain range.
      {0x1C,0x6A},{0x37,0x08},{0x32,0xBF}};
    for (const auto& reg : analog) if (!write(reg[0], reg[1])) return false;
    return update(0x31, 0x9F, 0); // Unmute DAC; amplifier remains off until playback.
  }
  bool tone(float frequency, int milliseconds, uint8_t level) {
    const int count = RATE * milliseconds / 1000;
    int16_t samples[128 * 2];
    float phase = 0, step = 6.28318530718f * frequency / RATE;
    float decay = 1, decayStep = expf(-1.0f / (RATE * 0.40f));
    for (int offset = 0; offset < count; offset += 128) {
      if (stopRequested_) return false;
      int frames = min(128, count - offset);
      for (int i = 0; i < frames; ++i) {
        int edge = min(offset + i, count - 1 - offset - i);
        float envelope = min(1.0f, edge / 128.0f) * decay;
        float bell = 0.75f * sinf(phase) + 0.18f * sinf(2 * phase) + 0.07f * sinf(3 * phase);
        // Coefficients sum to one, envelope <= 1, level <= 100: peak <= 31000.
        int16_t sample = frequency > 0 ? int16_t(bell * envelope * level * 310.0f) : 0;
        decay *= decayStep;
        samples[2 * i] = samples[2 * i + 1] = sample;
        phase += step; if (phase >= 6.28318530718f) phase -= 6.28318530718f;
      }
      size_t sent = 0, bytes = frames * 2 * sizeof(int16_t);
      if (i2s_write(I2S_NUM_0, samples, bytes, &sent, pdMS_TO_TICKS(200)) != ESP_OK || sent != bytes) return false;
    }
    return true;
  }
  static void worker(void* context) {
    auto& audio = *static_cast<KitchenAudio*>(context);
    for (;;) {
      ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
      if (audio.stopRequested_) { audio.busy = false; continue; }
      audio.busy = true;
      uint8_t level = audio.volume;
      i2s_zero_dma_buffer(I2S_NUM_0);
      digitalWrite(1, LOW);
      bool ok = audio.tone(1046.50f, 240, level) && audio.tone(0, 40, level)
        && audio.tone(1318.51f, 240, level) && audio.tone(0, 40, level)
        && audio.tone(1567.98f, 460, level) && audio.tone(0, 50, level);
      vTaskDelay(pdMS_TO_TICKS(40));
      digitalWrite(1, HIGH); // Mute on success AND failure.
      i2s_zero_dma_buffer(I2S_NUM_0);
      if (!ok && !audio.stopRequested_) { audio.ready = false; audio.error = "Audio transfer failed"; }
      Serial.println(audio.stopRequested_ ? "Kitchen speaker: stopped" : ok ? "Kitchen speaker: cafe chime played" : "Kitchen speaker: playback failed");
      audio.busy = false;
    }
  }
};
