// =======================================================
// Arduino UNO + Sensor Shield
// IR Sensors: TCRT5000 AO -> A0 (IR1), A1 (IR2)
// Relay IN1  -> D4 (CONVEYOR)
// Serial: 115200
//
// Features:
// - Stable IR detection using thresholds + consecutive hits
// - EVT IR1 / EVT IR2 event output for PC/UI
// - Conveyor control via serial commands: CONV_ON / CONV_OFF
// - Delayed stop: stop conveyor 1 second after IR trigger (non-blocking)
// - RAW status print every 2 seconds
//
// Default tuned params (per your field test):
// TH1=30, TH2=33, HIT1=5, HIT2=8
// =======================================================

const int IR1 = A0;
const int IR2 = A1;
const int RELAY = 4;

// Relay levels (you confirmed this mapping works on your setup)
const int STOP_LEVEL = LOW;
const int RUN_LEVEL  = HIGH;

// ---- Delayed stop settings ----
const unsigned long STOP_DELAY_MS = 1000; // delay 1 second

bool stop_pending = false;
unsigned long stop_request_time = 0;

// ---- Tuned thresholds ----
int TH1 = 30;
int TH2 = 31;

// ---- Consecutive-hit debounce ----
int HIT1_N = 10;
int HIT2_N = 6;

// ---- RAW output ----
bool RAW_ON = true;
unsigned long lastRaw = 0;
const unsigned long RAW_PERIOD_MS = 2000;

// ---- Latch to avoid repeated EVT spam for same board ----
bool ir1_latched = false;
bool ir2_latched = false;

// ---- hit counters ----
int hit1 = 0, hit2 = 0;

// Track conveyor state explicitly (more reliable than digitalRead on output pin)
bool conveyor_running = true;

void relayRun(bool on) {
  digitalWrite(RELAY, on ? RUN_LEVEL : STOP_LEVEL);
  conveyor_running = on;
}

void scheduleDelayedStop() {
  // Only schedule once; do not override timing if already pending
  if (!stop_pending) {
    stop_pending = true;
    stop_request_time = millis();
  }
}

void handleDelayedStop() {
  if (stop_pending) {
    if (millis() - stop_request_time >= STOP_DELAY_MS) {
      relayRun(false);     // stop conveyor
      stop_pending = false;
      Serial.println("OK CONV_OFF_DELAYED");
    }
  }
}

void printRaw(int v1, int v2) {
  Serial.print("RAW IR1=");
  Serial.print(v1);
  Serial.print(" IR2=");
  Serial.print(v2);
  Serial.print(" TH1=");
  Serial.print(TH1);
  Serial.print(" TH2=");
  Serial.print(TH2);
  Serial.print(" HIT1=");
  Serial.print(HIT1_N);
  Serial.print(" HIT2=");
  Serial.print(HIT2_N);
  Serial.print(" CONV=");
  Serial.print(conveyor_running ? "ON" : "OFF");
  Serial.print(" PEND=");
  Serial.println(stop_pending ? "Y" : "N");
}

void processIR(int v1, int v2) {
  // consecutive hits
  hit1 = (v1 > TH1) ? (hit1 + 1) : 0;
  hit2 = (v2 > TH2) ? (hit2 + 1) : 0;

  // trigger -> latch -> emit EVT -> schedule delayed stop
  if (!ir1_latched && hit1 >= HIT1_N) {
    ir1_latched = true;
    Serial.println("EVT IR1");
    scheduleDelayedStop();
  }
  if (!ir2_latched && hit2 >= HIT2_N) {
    ir2_latched = true;
    Serial.println("EVT IR2");
    scheduleDelayedStop();
  }

  // unlatch when falling back below threshold
  if (ir1_latched && v1 <= TH1) ir1_latched = false;
  if (ir2_latched && v2 <= TH2) ir2_latched = false;
}

void handleCommand(String s) {
  s.trim();
  if (s.length() == 0) return;

  if (s == "CONV_ON") {
    relayRun(true);
    stop_pending = false;           // cancel any pending delayed stop
    Serial.println("OK CONV_ON");
    return;
  }
  if (s == "CONV_OFF") {
  scheduleDelayedStop();                 // 不覆蓋既有排程
  Serial.println("OK CONV_OFF_SCHEDULED");
  return;
  }

  if (s == "RAWON")  { RAW_ON = true;  Serial.println("OK RAWON");  return; }
  if (s == "RAWOFF") { RAW_ON = false; Serial.println("OK RAWOFF"); return; }

  if (s.startsWith("TH1="))  { TH1 = s.substring(4).toInt(); Serial.println("OK TH1"); return; }
  if (s.startsWith("TH2="))  { TH2 = s.substring(4).toInt(); Serial.println("OK TH2"); return; }
  if (s.startsWith("HIT1=")) { HIT1_N = max(1, s.substring(5).toInt()); Serial.println("OK HIT1"); return; }
  if (s.startsWith("HIT2=")) { HIT2_N = max(1, s.substring(5).toInt()); Serial.println("OK HIT2"); return; }

  if (s == "PING")  { Serial.println("OK PONG"); return; }
  if (s == "IDENT") { Serial.println("OK IR UNO A0/A1 RELAY D4"); return; }

  Serial.print("ERR UNKNOWN: ");
  Serial.println(s);
}

void setup() {
  pinMode(RELAY, OUTPUT);
  relayRun(true);

  Serial.begin(115200);
  Serial.println("OK BOOT");
  Serial.println("OK READY");
  Serial.println("OK CMDS: CONV_ON CONV_OFF RAWON RAWOFF TH1= TH2= HIT1= HIT2= PING IDENT");
}

void loop() {
  int v1 = analogRead(IR1);
  int v2 = analogRead(IR2);

  // IR detection -> events + delayed stop schedule
  processIR(v1, v2);

  // execute delayed stop when time arrives (non-blocking)
  handleDelayedStop();

  // RAW output every 2 seconds
  unsigned long now = millis();
  if (RAW_ON && (now - lastRaw >= RAW_PERIOD_MS)) {
    lastRaw = now;
    printRaw(v1, v2);
  }

  // serial commands from PC/UI
  if (Serial.available()) {
    String s = Serial.readStringUntil('\n');
    handleCommand(s);
  }

  delay(5);
}
