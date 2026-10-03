from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
RUN_SCRIPT = ROOT_DIR / 'scripts' / 'run_ros_voice_nodes.sh'
LOG_FILE = ROOT_DIR / 'logs' / 'ros2_voice_pipeline.log'
EXPECTED_NODES = ['stt_node', 'nlu_node', 'decision_node', 'action_node', 'tts_node']


class ROSProcessManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._log_handle = None
        self._started_at: float | None = None

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return self._status_unlocked()

            workspace_setup = ROOT_DIR / 'ros2_ws' / 'install' / 'setup.bash'
            if not workspace_setup.exists():
                raise FileNotFoundError(
                    'ROS2 워크스페이스가 빌드되지 않았습니다. 먼저 colcon build를 실행해주세요.'
                )
            if not RUN_SCRIPT.exists():
                raise FileNotFoundError(f'실행 스크립트를 찾을 수 없습니다: {RUN_SCRIPT}')

            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._log_handle = LOG_FILE.open('a', encoding='utf-8')
            self._process = subprocess.Popen(
                ['bash', str(RUN_SCRIPT)],
                cwd=ROOT_DIR,
                stdout=self._log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
            self._started_at = time.time()
            time.sleep(0.5)

            if self._process.poll() is not None:
                self._close_log()
                raise RuntimeError(f'ROS2 노드 실행에 실패했습니다. 로그: {LOG_FILE}')

            return self._status_unlocked()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                try:
                    os.killpg(self._process.pid, signal.SIGTERM)
                    self._process.wait(timeout=8)
                except ProcessLookupError:
                    pass
                except subprocess.TimeoutExpired:
                    os.killpg(self._process.pid, signal.SIGKILL)
                    self._process.wait(timeout=2)

            self._process = None
            self._started_at = None
            self._close_log()
            return self._status_unlocked()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return self._status_unlocked()

    def _status_unlocked(self) -> dict[str, Any]:
        running = self._process is not None and self._process.poll() is None
        return {
            'running': running,
            'pid': self._process.pid if running and self._process is not None else None,
            'started_at': self._started_at if running else None,
            'nodes': EXPECTED_NODES,
            'log_file': str(LOG_FILE),
        }

    def _close_log(self) -> None:
        if self._log_handle is not None:
            self._log_handle.close()
            self._log_handle = None


ros_process_manager = ROSProcessManager()
