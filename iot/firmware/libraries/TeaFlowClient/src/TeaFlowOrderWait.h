#pragma once
#include <stdint.h>

// Use server time, never the ESP32's unset wall clock. Freeze the displayed
// snapshot when stale; the next successful poll restores the true elapsed age.
inline int32_t teaFlowWaitMinutes(uint32_t paidAt, uint32_t serverAt,
    uint32_t receivedAt, uint32_t now, bool fresh) {
  if (!paidAt || !serverAt) return -1;
  const uint64_t current = uint64_t(serverAt) + (fresh ? uint32_t(now - receivedAt) / 1000 : 0);
  return current > paidAt ? int32_t((current - paidAt) / 60) : 0;
}
