#pragma once

bool handleMouseCommand(const String& line) {
  if (!line.startsWith("mouse ")) return false;
  if (line == "mouse hello") {
    Serial.println("TFMOUSE READY 1 800 480 JC8048W550"); return true;
  }
  if (line == "mouse begin") {
    mouse.hide(screen.gfx); mouse.cancel(); mouse.linked = true;
    mouse.sequence = 0; mouse.lastPacket = millis();
    // Suppress broken-glass ghost touches, including after a restart. The
    // saved order submission and network preferences are separate keys.
    if (!mouseOnly && storageGood) settings.putBool("usb-mouse", true);
    mouseOnly = true; touching = false; pressedButton = -1; wakeTouch = false;
    backlight.touch(); lastInteraction = millis();
    render(); mouse.show(screen.gfx);
    Serial.println("TFMOUSE ACTIVE 1"); return true;
  }
  if (line == "mouse stop" || line == "mouse touch") {
    mouse.hide(screen.gfx); mouse.cancel(); mouse.linked = false;
    if (line == "mouse touch") {
      mouseOnly = false;
      if (storageGood) settings.putBool("usb-mouse", false);
    }
    render(); Serial.println("TFMOUSE STOPPED"); return true;
  }
  unsigned long sequence = 0; char kind = 0, trailing = 0; int x = -1, y = -1;
  if (sscanf(line.c_str(), "mouse %lu %c %d %d %c", &sequence, &kind, &x, &y, &trailing) != 4
      || !sequence || x < 0 || x >= 800 || y < 0 || y >= 480
      || (kind != 'm' && kind != 'd' && kind != 'u' && kind != 'c' && kind != 'p')) {
    mouse.cancel(); Serial.println("TFMOUSE ERROR invalid input"); return true;
  }
  if (!mouse.linked || uint32_t(millis() - mouse.lastPacket) > 8000) {
    mouse.hide(screen.gfx); mouse.cancel(); mouse.linked = false;
    Serial.println("TFMOUSE ERROR reconnect required"); return true;
  }
  // A replayed frame can never produce a second click.
  if (sequence <= mouse.sequence) {
    Serial.printf("TFMOUSE ACK %lu\n", sequence); return true;
  }
  mouse.sequence = sequence; mouse.lastPacket = millis();
  if (kind == 'c') mouse.cancel();
  else if (kind != 'p') {
    const bool wasIdle = cashierIdle();
    const bool dimmed = backlight.touch(); lastInteraction = millis();
    // Keep the displayed idle targets until a deliberate click opens them.
    if (wasIdle) cashierAwake = false;
    mouse.hide(screen.gfx); mouse.x = x; mouse.y = y;
    if (mouse.held && (abs(x - mouse.downX) > 8 || abs(y - mouse.downY) > 8)) mouse.pressId = -1;
    if (kind == 'd') {
      mouse.cancel(); mouse.held = true; mouse.downAt = millis();
      mouse.downX = x; mouse.downY = y;
      mouse.wakeOnly = dimmed;
      mouse.pressId = dimmed ? -1 : hit(x, y);
    } else if (kind == 'u') {
      const int target = mouse.pressId;
      const bool click = mouse.held && !mouse.wakeOnly && target >= 0
        && target == hit(x, y) && uint32_t(millis() - mouse.downAt) <= 1500;
      mouse.cancel();
      if (click) act(target);
    }
    mouse.show(screen.gfx);
  }
  Serial.printf("TFMOUSE ACK %lu\n", sequence);
  return true;
}

void pollMouse() {
  if (mouse.held && uint32_t(millis() - mouse.downAt) > 1500) mouse.cancel();
  if (mouse.linked && uint32_t(millis() - mouse.lastPacket) > 8000) {
    mouse.hide(screen.gfx); mouse.cancel(); mouse.linked = false; render();
  }
}
