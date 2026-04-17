#include <WiFi.h>
#include <WiFiUdp.h>

// Access Point credentials
const char* ssid = "ESP32_Car";
const char* password = "12345678";
const int fr_1 = 25;
const int fr_2 = 26;
const int fl_1 = 27;
const int fl_2 = 14;

// UDP settings
WiFiUDP udp;
const int udpPort = 3333;
char incomingPacket[255];

// Motor control will be added later

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  // Configure ESP32 as Access Point
  Serial.println("Setting up Access Point...");
  WiFi.mode(WIFI_AP);
  WiFi.softAP(ssid, password);
  
  IPAddress IP = WiFi.softAPIP();
  Serial.print("AP IP address: ");
  Serial.println(IP);
  Serial.println("Expected: 192.168.4.1");
  
  // Start UDP server
  udp.begin(udpPort);
  Serial.printf("UDP server started on port %d\n", udpPort);
  Serial.println("\nWaiting for client connection...");

  pinMode(fr_1,OUTPUT);
  pinMode(fr_2,OUTPUT);
  pinMode(fl_1,OUTPUT);
  pinMode(fl_2,OUTPUT);
  digitalWrite(fr_1, LOW);
  digitalWrite(fr_2, LOW);
  digitalWrite(fl_1, LOW);
  digitalWrite(fl_2, LOW);
  
}

void loop() {
  int packetSize = udp.parsePacket();

  if (packetSize) {
    int len = udp.read(incomingPacket, 255);
    if (len > 0) {
      incomingPacket[len] = '\0';
    }

    processCommand(incomingPacket);
  }

  delay(10);
}



void processCommand(char* cmd) {
  // Just display the received command for now
  Serial.print("Command received: ");
  Serial.println(cmd);
  
  // Decode what action it represents
  switch(cmd[0]) {
    case 'F':
      Serial.println("→ Action: FORWARD");
      forward();
      break;
      
    case 'B':
      Serial.println("→ Action: BACKWARD");
      backward();
      break;
      
    case 'L':
      Serial.println("→ Action: LEFT");
      left();
      break;
      
    case 'R':
      Serial.println("→ Action: RIGHT");
      right();
      break;
      
    case 'S':
      Serial.println("→ Action: STOP");
      stopMotors();
      break;
      
    default:
      Serial.println("→ Unknown command");
      stopMotors();
      break;
  }
  Serial.println("---");
}

void forward(){
  digitalWrite(fr_1, HIGH);
  digitalWrite(fr_2, LOW);
  digitalWrite(fl_1, HIGH);
  digitalWrite(fl_2, LOW);
}

void backward(){
  digitalWrite(fr_1, LOW);
  digitalWrite(fr_2, HIGH);
  digitalWrite(fl_1, LOW);
  digitalWrite(fl_2, HIGH);
}

void left(){
  digitalWrite(fr_1, LOW);
  digitalWrite(fr_2, HIGH);
  digitalWrite(fl_1, HIGH);
  digitalWrite(fl_2, LOW);
}

void right(){
  digitalWrite(fr_1, HIGH);
  digitalWrite(fr_2, LOW);
  digitalWrite(fl_1, LOW);
  digitalWrite(fl_2, HIGH);
}

void stopMotors() {
  digitalWrite(fr_1, LOW);
  digitalWrite(fr_2, LOW);
  digitalWrite(fl_1, LOW);
  digitalWrite(fl_2, LOW);
}
