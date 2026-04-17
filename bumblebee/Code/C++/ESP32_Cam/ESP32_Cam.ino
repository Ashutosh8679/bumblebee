#include <WiFi.h>
#include "esp_camera.h"

// ---------- ESP32-CAM PIN MAP (AI THINKER) ----------
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// ---------- WIFI (STA MODE) ----------
const char* ssid     = "ESP32_Car";
const char* password = "12345678";

// ---------- HTTP SERVER ----------
WiFiServer server(80);

// ---------- CAMERA INIT ----------
void startCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;

  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;

  config.pin_xclk  = XCLK_GPIO_NUM;
  config.pin_pclk  = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href  = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn  = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;

  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  // Stable, conservative defaults
  config.frame_size   = FRAMESIZE_QVGA;
  config.jpeg_quality = 10;
  config.fb_count     = 1;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed: 0x%x\n", err);
    while (true) delay(1000);
  }

  Serial.println("Camera initialized");
}

// ---------- MJPEG STREAM HANDLER ----------
void streamMJPEG(WiFiClient client) {
  const char* boundary = "frame";

  client.print(
    "HTTP/1.1 200 OK\r\n"
    "Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
    "Cache-Control: no-cache\r\n\r\n"
  );

  while (client.connected()) {
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Camera frame failed");
      break;
    }

    client.print("--frame\r\n");
    client.print("Content-Type: image/jpeg\r\n");
    client.print("Content-Length: ");
    client.print(fb->len);
    client.print("\r\n\r\n");

    client.write(fb->buf, fb->len);
    client.print("\r\n");

    esp_camera_fb_return(fb);

    delay(40);   // ~20–25 FPS
    yield();
  }

  client.stop();
  Serial.println("Stream client disconnected");
}

// ---------- SETUP ----------
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("Starting ESP32-CAM (Camera Stream Only)");

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  Serial.print("Connecting to WiFi");
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(250);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("Connected. IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("STA failed. Starting AP fallback.");
    WiFi.mode(WIFI_AP);
    WiFi.softAP("ESP32_CAM_AP", "12345678");
    Serial.print("AP IP: ");
    Serial.println(WiFi.softAPIP());
  }

  startCamera();
  server.begin();

  Serial.println("Open stream at: http://<ESP_IP>/stream");
}

// ---------- LOOP ----------
void loop() {
  WiFiClient client = server.available();
  if (!client) return;

  String request = client.readStringUntil('\n');
  Serial.println(request);

  if (request.indexOf("GET /stream") >= 0) {
    // Flush headers
    while (client.connected()) {
      String line = client.readStringUntil('\n');
      if (line == "\r" || line.length() == 0) break;
    }
    streamMJPEG(client);
  } else {
    client.print(
      "HTTP/1.1 200 OK\r\n"
      "Content-Type: text/html\r\n\r\n"
      "<html><body>"
      "<h3>ESP32-CAM</h3>"
      "<a href=\"/stream\">Open Camera Stream</a>"
      "</body></html>"
    );
    client.stop();
  }
}
