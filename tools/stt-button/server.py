from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import json
import subprocess


STATUS_FILE = Path('/tmp/pumpkin_stt_status')


HTML = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pumpkin 음성 주문</title>

  <style>
    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: Arial, sans-serif;
      background: #f4f4f4;
    }

    .card {
      width: min(430px, 90vw);
      padding: 36px 24px;
      border-radius: 22px;
      background: white;
      box-shadow: 0 12px 35px rgba(0, 0, 0, 0.12);
      text-align: center;
    }

    h1 {
      margin: 0 0 12px;
      font-size: 28px;
    }

    .description {
      color: #666;
      line-height: 1.6;
    }

    .indicator {
      width: 110px;
      height: 110px;
      margin: 26px auto 18px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 44px;
      background: #eeeeee;
      transition: 0.25s;
    }

    .indicator.listening {
      background: #ffe2e2;
      animation: pulse 1.2s infinite;
    }

    .indicator.processing {
      background: #fff1c7;
      animation: pulse 1.2s infinite;
    }

    .indicator.done {
      background: #dff5e5;
    }

    @keyframes pulse {
      0% {
        transform: scale(1);
        box-shadow: 0 0 0 0 rgba(220, 60, 60, 0.35);
      }

      70% {
        transform: scale(1.06);
        box-shadow: 0 0 0 18px rgba(220, 60, 60, 0);
      }

      100% {
        transform: scale(1);
        box-shadow: 0 0 0 0 rgba(220, 60, 60, 0);
      }
    }

    #status {
      min-height: 31px;
      font-size: 20px;
      font-weight: 700;
    }

    #detail {
      min-height: 24px;
      margin-top: 7px;
      color: #777;
      font-size: 14px;
    }

    button {
      width: 100%;
      margin-top: 25px;
      padding: 19px;
      border: 0;
      border-radius: 14px;
      background: #222;
      color: white;
      font-size: 19px;
      font-weight: 700;
      cursor: pointer;
    }

    button:disabled {
      opacity: 0.45;
      cursor: not-allowed;
    }
  </style>
</head>

<body>
  <main class="card">
    <h1>음성 주문</h1>

    <div class="description">
      버튼을 누른 뒤<br>
      마이크 표시가 켜지면 말씀해 주세요.
    </div>

    <div id="indicator" class="indicator">🎙️</div>

    <div id="status">대기 중</div>
    <div id="detail">음성 주문 버튼을 눌러 주세요.</div>

    <button id="startButton" onclick="startListening()">
      음성 주문 시작
    </button>
  </main>

  <script>
    const button = document.getElementById("startButton");
    const indicator = document.getElementById("indicator");
    const statusText = document.getElementById("status");
    const detailText = document.getElementById("detail");

    let activeRequest = false;
    let previousStatus = "";

    function renderStatus(status) {
      indicator.className = "indicator";

      if (status === "ready") {
        statusText.textContent = "대기 중";
        detailText.textContent = "음성 주문 버튼을 눌러 주세요.";
        indicator.textContent = "🎙️";
        button.disabled = false;
        activeRequest = false;
        return;
      }

      if (status === "starting") {
        statusText.textContent = "마이크 준비 중...";
        detailText.textContent = "잠시만 기다려 주세요.";
        indicator.textContent = "⏳";
        button.disabled = true;
        return;
      }

      if (status === "listening") {
        statusText.textContent = "듣고 있습니다";
        detailText.textContent = "지금 말씀해 주세요.";
        indicator.textContent = "🎤";
        indicator.classList.add("listening");
        button.disabled = true;
        return;
      }

      if (status === "speech_detected") {
        statusText.textContent = "음성을 듣고 있습니다";
        detailText.textContent = "말씀을 계속해 주세요.";
        indicator.textContent = "🎤";
        indicator.classList.add("listening");
        button.disabled = true;
        return;
      }

      if (status === "transcribing") {
        statusText.textContent = "음성 인식 중...";
        detailText.textContent = "주문 내용을 확인하고 있습니다.";
        indicator.textContent = "•••";
        indicator.classList.add("processing");
        button.disabled = true;
        return;
      }

      if (status === "done") {
        statusText.textContent = "인식 완료";
        detailText.textContent = "주문 내용을 전송했습니다.";
        indicator.textContent = "✓";
        indicator.classList.add("done");
        button.disabled = false;
        activeRequest = false;
        return;
      }

      if (status === "no_speech") {
        statusText.textContent = "음성이 들리지 않았습니다";
        detailText.textContent = "버튼을 눌러 다시 시도해 주세요.";
        indicator.textContent = "!";
        button.disabled = false;
        activeRequest = false;
        return;
      }

      if (
        status === "empty" ||
        status === "rejected" ||
        status === "too_quiet"
      ) {
        statusText.textContent = "인식하지 못했습니다";
        detailText.textContent = "조금 더 가까이에서 다시 말씀해 주세요.";
        indicator.textContent = "?";
        button.disabled = false;
        activeRequest = false;
        return;
      }

      if (status.startsWith("error:")) {
        statusText.textContent = "오류가 발생했습니다";
        detailText.textContent = "STT 노드와 마이크를 확인해 주세요.";
        indicator.textContent = "!";
        button.disabled = false;
        activeRequest = false;
      }
    }

    async function pollStatus() {
      try {
        const response = await fetch("/status", {
          cache: "no-store"
        });

        const result = await response.json();
        const currentStatus = result.status || "ready";

        if (currentStatus !== previousStatus) {
          previousStatus = currentStatus;
          renderStatus(currentStatus);
        }
      } catch (error) {
        statusText.textContent = "상태 연결 실패";
        detailText.textContent = "버튼 서버를 확인해 주세요.";
      }
    }

    async function startListening() {
      activeRequest = true;
      button.disabled = true;
      renderStatus("starting");

      try {
        const response = await fetch("/trigger", {
          method: "POST"
        });

        if (!response.ok) {
          throw new Error("trigger failed");
        }
      } catch (error) {
        activeRequest = false;
        statusText.textContent = "STT 실행 실패";
        detailText.textContent = "ROS 노드가 실행 중인지 확인해 주세요.";
        indicator.textContent = "!";
        button.disabled = false;
      }
    }

    pollStatus();
    setInterval(pollStatus, 200);
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def send_body(
        self,
        status_code: int,
        body: bytes,
        content_type: str,
    ) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self.send_body(
                200,
                HTML.encode("utf-8"),
                "text/html; charset=utf-8",
            )
            return

        if self.path == "/status":
            if STATUS_FILE.exists():
                status = STATUS_FILE.read_text(
                    encoding="utf-8"
                ).strip()
            else:
                status = "ready"

            body = json.dumps(
                {"status": status},
                ensure_ascii=False,
            ).encode("utf-8")

            self.send_body(
                200,
                body,
                "application/json; charset=utf-8",
            )
            return

        self.send_error(404)

    def do_POST(self):
        if self.path != "/trigger":
            self.send_error(404)
            return

        STATUS_FILE.write_text(
            "starting",
            encoding="utf-8",
        )

        command = """
        source /opt/ros/humble/setup.bash
        source ~/pumpkin/ros2_ws/install/setup.bash
        ros2 topic pub --once /stt/trigger std_msgs/msg/String "{data: start}"
        """

        try:
            subprocess.run(
                ["bash", "-lc", command],
                check=True,
                timeout=10,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            body = b'{"ok": true}'

            self.send_body(
                200,
                body,
                "application/json",
            )

        except Exception as error:
            STATUS_FILE.write_text(
                f"error:{error}",
                encoding="utf-8",
            )

            body = json.dumps(
                {"ok": False, "error": str(error)}
            ).encode("utf-8")

            self.send_body(
                500,
                body,
                "application/json",
            )

    def log_message(self, format, *args):
        print(format % args)


if __name__ == "__main__":
    host = "0.0.0.0"
    port = 8088

    print(f"STT button server: http://localhost:{port}")
    HTTPServer((host, port), Handler).serve_forever()
