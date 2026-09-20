// =======================================================
// UNO Sensor (TCRT5000 AO)
// IR1=A0, IR2=A1
// Relay IN1=D4
// Serial 115200
//
// - EVT IR1 / EVT IR2 (one-shot per conveyor cycle)
// - Delayed stop 1s after first trigger
// - RAW every 2s
// - Commands: CONV_ON, CONV_OFF, RAWON, RAWOFF, TH1=, TH2=, HIT1=, HIT2=, PING, IDENT
//
// Tuned for your environment:
// TH1=30, TH2=33, HIT1=5, HIT2=8
// =======================================================

const int IR1 = A0;
const int IR2 = A1;
const int RELAY = 4;

const int STOP_LEVEL = LOW;
const int RUN_LEVEL  = HIGH;

// Tuned thresholds
int TH1 = 30;
int TH2 = 33;

// Consecutive hit counts
int HIT1_N = 5;
int HIT2_N = 8;

// Delayed stop
const unsigned long STOP_DELAY_MS = 1000;
bool stop_pending = false;
unsigned long stop_request_time = 0;

// RAW output
bool RAW_ON = true;
unsigned long lastRaw = 0;
const unsigned long RAW_PERIOD_MS = 2000;

// States
bool conveyor_running = true;

// Event lock: prevent EVT spam until CONV_ON resets it
bool evt1_locked = false;
bool evt2_locked = false;

// hit counters
int hit1 = 0;
int hit2 = 0;

void relayRun(bool on) {
  digitalWrite(RELAY, on ? RUN_LEVEL : STOP_LEVEL);
  conveyor_running = on;
}

void scheduleDelayedStop() {
  if (!stop_pending && conveyor_running) {
    stop_pending = true;
    stop_request_time = millis();
  }
}

void handleDelayedStop() {
  if (stop_pending) {
    if (millis() - stop_request_time >= STOP_DELAY_MS) {
      relayRun(false);
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
  Serial.print(" CONV=");
  Serial.print(conveyor_running ? "ON" : "OFF");
  Serial.print(" PEND=");
  Serial.print(stop_pending ? "Y" : "N");
  Serial.print(" L1=");
  Serial.print(evt1_locked ? "Y" : "N");
  Serial.print(" L2=");
  Serial.println(evt2_locked ? "Y" : "N");
}

void processIR(int v1, int v2) {
  // consecutive hits based on raw > threshold
  hit1 = (v1 > TH1) ? (hit1 + 1) : 0;
  hit2 = (v2 > TH2) ? (hit2 + 1) : 0;

  // fire EVT once per cycle
  if (!evt1_locked && hit1 >= HIT1_N) {
    evt1_locked = true;
    Serial.println("EVT IR1");
    scheduleDelayedStop();
  }

  if (!evt2_locked && hit2 >= HIT2_N) {
    evt2_locked = true;
    Serial.println("EVT IR2");
    scheduleDelayedStop();
  }
}

void handleCommand(String s) {
  s.trim();
  if (s.length() == 0) return;

  if (s == "CONV_ON") {
    relayRun(true);
    stop_pending = false;

    // reset locks + counters for next board
    evt1_locked = false;
    evt2_locked = false;
    hit1 = 0;
    hit2 = 0;

    Serial.println("OK CONV_ON");
    return;
  }

  if (s == "CONV_OFF") {
    relayRun(false);
    stop_pending = false;
    Serial.println("OK CONV_OFF");
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
}

void loop() {
  int v1 = analogRead(IR1);
  int v2 = analogRead(IR2);

  processIR(v1, v2);
  handleDelayedStop();

  unsigned long now = millis();
  if (RAW_ON && (now - lastRaw >= RAW_PERIOD_MS)) {
    lastRaw = now;
    printRaw(v1, v2);
  }

  if (Serial.available()) {
    String s = Serial.readStringUntil('\n');
    handleCommand(s);
  }

  delay(5);
}
