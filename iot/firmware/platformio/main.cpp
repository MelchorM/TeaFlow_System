#include <Arduino.h>
#ifdef TEAFLOW_KITCHEN
#include <TeaFlowKitchenDisplay.h>
#ifndef TEAFLOW_DISPLAY_TEST
#include <TeaFlowClient.h>
#include <Preferences.h>
#endif
#ifdef TEAFLOW_DISPLAY_TEST
#include "../kitchen-display-test/kitchen-display-test.ino"
#else
#include "../kitchen/kitchen.ino"
#endif
#else
#include <TeaFlowDisplay.h>
#ifndef TEAFLOW_DISPLAY_TEST
#include <TeaFlowClient.h>
#include <Preferences.h>
#endif
#ifdef TEAFLOW_DISPLAY_TEST
#include "../display-test/display-test.ino"
#else
#include "../cashier/cashier.ino"
#endif
#endif
