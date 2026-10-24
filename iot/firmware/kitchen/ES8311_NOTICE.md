# ES8311 attribution

The fixed 16 kHz register/clock initialization in `KitchenAudio.h` is adapted
from the Espressif ES8311 driver distributed with the supplier's ES3C35P
`Example_16_music` demonstration.

Copyright 2015-2022 Espressif Systems (Shanghai) CO LTD.
Licensed under Apache License 2.0; see `LICENSE-ES8311.txt`.

TeaFlow uses Arduino Wire for the already initialized touch/codec I2C bus and
the pinned ESP-IDF 4.4 I2S transmit driver. Its generated two-tone notification
does not need a recording, SD card, microphone input, or network audio stream.

Supplier resources: https://www.lcdwiki.com/3.5inch_ESP32-S3_Display
