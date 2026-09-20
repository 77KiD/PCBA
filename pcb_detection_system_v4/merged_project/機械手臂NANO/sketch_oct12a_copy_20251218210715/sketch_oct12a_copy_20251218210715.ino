#include <Servo.h>

// 創建6個舵機對象
Servo servos[6];

// 舵機引腳定義
const uint8_t SERVO_PINS[6] PROGMEM = {4, 5, 6, 7, 8, 9};

// 舵機角度限制 (min, max, home)
const uint8_t limits[6][3] PROGMEM = {
  {0, 180, 0},      // Joint1 - 預設0°
  {0, 180, 180},    // Joint2 - 預設180°
  {0, 180, 90},     // Joint3
  {0, 180, 90},     // Joint4
  {0, 180, 90},     // Joint5
  {30, 73, 73}      // Joint6 - 夾爪
};

// 當前角度
uint8_t currentAngles[6];

// 移動速度
uint8_t moveSpeed = 15;

// 串口緩衝區
#define CMD_SIZE 64
char cmd[CMD_SIZE];
uint8_t cmdIdx = 0;

// 狀態標誌
bool isMoving = false;
bool emergencyStop = false;

// ---- 延遲啟動設定 ----
const unsigned long ARM_DELAY_MS = 1000;  // 1 秒
bool seq_pending = false;
unsigned long seq_request_time = 0;
uint8_t pending_seq = 0;  // 0=無, 1=PASS, 2=FAIL, 3=DEMO

void setup() {
  Serial.begin(115200);
  
  // 初始化舵機
  for (uint8_t i = 0; i < 6; i++) {
    servos[i].attach(pgm_read_byte(&SERVO_PINS[i]));
    currentAngles[i] = pgm_read_byte(&limits[i][2]);
    servos[i].write(currentAngles[i]);
  }
  
  delay(500);
  Serial.println(F("# Ready"));
  printHelp();
}

void loop() {
  // ---- 處理串口指令 ----
  if (Serial.available()) {
    char c = Serial.read();
    
    if (c == '\n' || c == '\r') {
      if (cmdIdx > 0) {
        cmd[cmdIdx] = '\0';
        processCommand();
        cmdIdx = 0;
      }
    } else if (cmdIdx < CMD_SIZE - 1) {
      cmd[cmdIdx++] = c;
    }
  }

  // ---- 延遲 1 秒後執行序列 ----
  if (seq_pending && !emergencyStop && !isMoving) {
    if (millis() - seq_request_time >= ARM_DELAY_MS) {
      seq_pending = false;

      if (pending_seq == 1) execPassSeq();
      else if (pending_seq == 2) execFailSeq();
      else if (pending_seq == 3) execDemoSeq();

      pending_seq = 0;
    }
  }
}

void processCommand() {
  // 轉大寫並移除前導空格
  uint8_t start = 0;
  while (cmd[start] == ' ') start++;
  
  for (uint8_t i = start; cmd[i]; i++) {
    if (cmd[i] >= 'a' && cmd[i] <= 'z') {
      cmd[i] -= 32;
    }
  }
  
  // 如果有前導空格,移動字串
  if (start > 0) {
    uint8_t i = 0;
    while (cmd[start + i]) {
      cmd[i] = cmd[start + i];
      i++;
    }
    cmd[i] = '\0';
  }
  
  // 指令處理
  if (strcmp_P(cmd, PSTR("HELP")) == 0 || strcmp(cmd, "?") == 0) {
    printHelp();
  }
  else if (strcmp_P(cmd, PSTR("STATUS")) == 0) {
    printStatus();
  }
  else if (strcmp_P(cmd, PSTR("HOME")) == 0) {
    moveToHome();
  }
  else if (strcmp_P(cmd, PSTR("STOP")) == 0) {
    emergencyStop = true;
    isMoving = false;
    Serial.println(F("OK STOP"));
  }
  else if (strcmp_P(cmd, PSTR("RESUME")) == 0) {
    emergencyStop = false;
    Serial.println(F("OK RESUME"));
  }
  else if (strcmp_P(cmd, PSTR("GETPOS")) == 0) {
    printPos();
  }
  else if (strncmp_P(cmd, PSTR("MOVE "), 5) == 0) {
    parseMove();
  }
  else if (strncmp_P(cmd, PSTR("MOVEALL "), 8) == 0) {
    parseMoveAll();
  }
  else if (strncmp_P(cmd, PSTR("SPEED "), 6) == 0) {
    moveSpeed = constrain(atoi(cmd + 6), 1, 100);
    Serial.println(F("OK SPEED"));
  }
  else if (strcmp_P(cmd, PSTR("OPEN")) == 0) {
    moveServo(5, 73, moveSpeed);
    Serial.println(F("OK OPEN"));
  }
  else if (strcmp_P(cmd, PSTR("CLOSE")) == 0) {
    moveServo(5, 30, moveSpeed);
    Serial.println(F("OK CLOSE"));
  }
  else if (strncmp_P(cmd, PSTR("SEQUENCE "), 9) == 0) {
    parseSequence();
  }
  else if (strncmp_P(cmd, PSTR("CALIBRATE"), 9) == 0) {
    parseCalibrate();
  }
  else {
    Serial.println(F("ERROR CMD"));
  }
}

void parseMove() {
  if (emergencyStop) {
    Serial.println(F("ERROR STOP"));
    return;
  }
  
  uint8_t joint = 0, angle = 0, speed = moveSpeed;
  char* p = cmd + 5;
  
  joint = atoi(p);
  while (*p && *p != ' ') p++;
  if (*p) p++;
  
  angle = atoi(p);
  while (*p && *p != ' ') p++;
  if (*p) {
    p++;
    speed = atoi(p);
  }
  
  if (joint > 5) {
    Serial.println(F("ERROR JOINT"));
    return;
  }
  
  uint8_t minA = pgm_read_byte(&limits[joint][0]);
  uint8_t maxA = pgm_read_byte(&limits[joint][1]);
  
  if (angle < minA || angle > maxA) {
    Serial.println(F("ERROR RANGE"));
    return;
  }
  
  moveServo(joint, angle, speed);
  Serial.println(F("OK MOVE"));
}

void parseMoveAll() {
  if (emergencyStop) {
    Serial.println(F("ERROR STOP"));
    return;
  }
  
  uint8_t angles[6];
  uint8_t speed = moveSpeed;
  char* p = cmd + 8;
  
  for (uint8_t i = 0; i < 6; i++) {
    angles[i] = atoi(p);
    while (*p && *p != ' ') p++;
    if (*p) p++;
  }
  
  if (*p) {
    speed = atoi(p);
  }
  
  for (uint8_t i = 0; i < 6; i++) {
    uint8_t minA = pgm_read_byte(&limits[i][0]);
    uint8_t maxA = pgm_read_byte(&limits[i][1]);
    if (angles[i] < minA || angles[i] > maxA) {
      Serial.println(F("ERROR RANGE"));
      return;
    }
  }
  
  moveAllServos(angles, speed);
  Serial.println(F("OK MOVEALL"));
}

void parseSequence() {
  if (emergencyStop) {
    Serial.println(F("ERROR STOP"));
    return;
  }

  char* type = cmd + 9;
  uint8_t target = 0;
  
  if (strcmp_P(type, PSTR("PASS")) == 0) target = 1;
  else if (strcmp_P(type, PSTR("FAIL")) == 0) target = 2;
  else if (strcmp_P(type, PSTR("DEMO")) == 0) target = 3;
  else {
    Serial.println(F("ERROR SEQ"));
    return;
  }

  if (isMoving || seq_pending) {
    Serial.println(F("ERROR BUSY"));
    return;
  }

  // 排程延遲執行
  pending_seq = target;
  seq_pending = true;
  seq_request_time = millis();
  
  Serial.println(F("OK SEQ_SCHEDULED"));
}

void parseCalibrate() {
  if (cmd[9] == '\0') {
    for (uint8_t i = 0; i < 6; i++) {
      if (emergencyStop) break;
      calibJoint(i);
    }
    Serial.println(F("OK CALIB_ALL"));
  } else {
    uint8_t joint = atoi(cmd + 10);
    if (joint < 6) {
      calibJoint(joint);
      Serial.println(F("OK CALIB"));
    } else {
      Serial.println(F("ERROR JOINT"));
    }
  }
}

void moveServo(uint8_t joint, uint8_t target, uint8_t spd) {
  if (emergencyStop) return;
  
  isMoving = true;
  uint8_t curr = currentAngles[joint];
  
  if (curr < target) {
    for (uint8_t a = curr; a <= target; a++) {
      if (emergencyStop) break;
      servos[joint].write(a);
      currentAngles[joint] = a;
      delay(spd);
    }
  } else {
    for (uint8_t a = curr; a >= target; a--) {
      if (emergencyStop) break;
      servos[joint].write(a);
      currentAngles[joint] = a;
      delay(spd);
      if (a == 0) break;
    }
  }
  
  isMoving = false;
}

void moveAllServos(uint8_t targets[6], uint8_t spd) {
  if (emergencyStop) return;
  
  isMoving = true;
  
  uint8_t maxSteps = 0;
  for (uint8_t i = 0; i < 6; i++) {
    uint8_t steps = abs(targets[i] - currentAngles[i]);
    if (steps > maxSteps) maxSteps = steps;
  }
  
  for (uint8_t step = 0; step <= maxSteps; step++) {
    if (emergencyStop) break;
    
    for (uint8_t i = 0; i < 6; i++) {
      int diff = targets[i] - currentAngles[i];
      if (diff != 0) {
        uint8_t newAngle = currentAngles[i] + (diff > 0 ? 1 : -1);
        servos[i].write(newAngle);
        currentAngles[i] = newAngle;
      }
    }
    delay(spd);
  }
  
  isMoving = false;
}

void moveToHome() {
  uint8_t home[6];
  for (uint8_t i = 0; i < 6; i++) {
    home[i] = pgm_read_byte(&limits[i][2]);
  }
  moveAllServos(home, moveSpeed);
  Serial.println(F("OK HOME"));
}

void calibJoint(uint8_t joint) {
  uint8_t minA = pgm_read_byte(&limits[joint][0]);
  uint8_t maxA = pgm_read_byte(&limits[joint][1]);
  uint8_t homeA = pgm_read_byte(&limits[joint][2]);
  
  moveServo(joint, minA, 20);
  delay(500);
  moveServo(joint, maxA, 20);
  delay(500);
  moveServo(joint, homeA, 20);
}

void execPassSeq() {
  Serial.println(F("# PASS"));
  
  uint8_t p1[6] = {90, 45, 135, 90, 90, 30};
  moveAllServos(p1, 15);
  delay(500);
  
  moveServo(5, 73, 15);
  delay(500);
  
  uint8_t p2[6] = {90, 90, 90, 90, 90, 73};
  moveAllServos(p2, 15);
  delay(500);
  
  uint8_t p3[6] = {135, 90, 90, 90, 90, 73};
  moveAllServos(p3, 20);
  delay(500);
  
  uint8_t p4[6] = {135, 45, 135, 90, 90, 73};
  moveAllServos(p4, 15);
  delay(300);
  
  moveServo(5, 30, 15);
  delay(500);
  
  moveToHome();
  Serial.println(F("OK PASS_SEQ"));
}

void execFailSeq() {
  Serial.println(F("# FAIL"));
  
  uint8_t p1[6] = {90, 45, 135, 90, 90, 30};
  moveAllServos(p1, 15);
  delay(500);
  
  moveServo(5, 73, 15);
  delay(500);
  
  uint8_t p2[6] = {90, 90, 90, 90, 90, 73};
  moveAllServos(p2, 15);
  delay(500);
  
  uint8_t p3[6] = {45, 90, 90, 90, 90, 73};
  moveAllServos(p3, 20);
  delay(500);
  
  uint8_t p4[6] = {45, 45, 135, 90, 90, 73};
  moveAllServos(p4, 15);
  delay(300);
  
  moveServo(5, 30, 15);
  delay(500);
  
  moveToHome();
  Serial.println(F("OK FAIL_SEQ"));
}

void execDemoSeq() {
  Serial.println(F("# DEMO"));
  
  moveToHome();
  delay(1000);
  
  moveServo(0, 45, 20);
  delay(500);
  moveServo(0, 135, 20);
  delay(500);
  moveServo(0, 90, 20);
  delay(500);
  
  uint8_t p1[6] = {90, 45, 135, 90, 90, 30};
  moveAllServos(p1, 15);
  delay(1000);
  
  moveServo(5, 73, 15);
  delay(1000);
  
  moveToHome();
  Serial.println(F("OK DEMO"));
}

void printStatus() {
  Serial.println(F("# STATUS"));
  Serial.print(F("# HW: "));
  Serial.println(emergencyStop ? F("STOP") : F("OK"));
  Serial.print(F("# Moving: "));
  Serial.println(isMoving ? F("Y") : F("N"));
  Serial.print(F("# Speed: "));
  Serial.println(moveSpeed);
  Serial.println(F("OK STATUS"));
}

void printPos() {
  Serial.print(F("POS"));
  for (uint8_t i = 0; i < 6; i++) {
    Serial.print(' ');
    Serial.print(currentAngles[i]);
  }
  Serial.println();
}

void printHelp() {
  Serial.println(F("# === COMMANDS ==="));
  Serial.println(F("# HELP - Show help"));
  Serial.println(F("# STATUS - Show status"));
  Serial.println(F("# HOME - Go home"));
  Serial.println(F("# STOP - Emergency stop"));
  Serial.println(F("# RESUME - Resume"));
  Serial.println(F("# GETPOS - Get position"));
  Serial.println(F("# MOVE j a s - Move joint"));
  Serial.println(F("# MOVEALL a0..a5 s - Move all"));
  Serial.println(F("# SPEED s - Set speed"));
  Serial.println(F("# OPEN - Open gripper"));
  Serial.println(F("# CLOSE - Close gripper"));
  Serial.println(F("# SEQUENCE type - Run sequence"));
  Serial.println(F("# CALIBRATE [j] - Calibrate"));
  Serial.println(F("# ================"));
}