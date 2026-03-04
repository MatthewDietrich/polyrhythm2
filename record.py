#!/usr/bin/env python3
"""
OBS Recorder - Records a Python/pygame app using OBS WebSocket API.

Prints the path to the recording file on stdout when complete.
All status messages go to stderr.
"""

import subprocess
import time
import sys
from pathlib import Path

import obsws_python as obs


def main():
    project_dir = Path(".")
    scene = "bouncyballs"
    duration = 5.0
    startup_wait = 8.0
    host = "localhost"
    port = 4455
    password = ""

    if not project_dir.exists():
        print(f"Error: Project directory not found: {project_dir}", file=sys.stderr)
        sys.exit(1)

    # Connect to OBS WebSocket
    print(f"Connecting to OBS at {host}:{port}...", file=sys.stderr)
    try:
        cl = obs.ReqClient(host=host, port=port, password=password, timeout=10)
    except Exception as e:
        print(f"Error: Could not connect to OBS WebSocket: {e}", file=sys.stderr)
        print(
            "Make sure OBS is running and WebSocket server is enabled (Tools > WebSocket Server Settings)",
            file=sys.stderr,
        )
        sys.exit(1)

    # Switch to the specified scene
    print(f"Switching to scene: '{scene}'", file=sys.stderr)
    try:
        cl.set_current_program_scene(scene)
    except Exception as e:
        print(f"Error switching scene: {e}", file=sys.stderr)
        sys.exit(1)
    time.sleep(0.5)

    # Start recording
    print("Starting recording", file=sys.stderr)
    try:
        cl.start_record()
    except Exception as e:
        print(f"Error starting recording: {e}", file=sys.stderr)
        sys.exit(1)
    time.sleep(1.0)

    # Launch the Python app
    print(f"Launching app", file=sys.stderr)
    proc = subprocess.Popen(["uv", "run", "python", "main.py"], cwd=str(project_dir))

    # Wait for app/window to appear
    print(f"Waiting {startup_wait}s for app to start", file=sys.stderr)
    time.sleep(startup_wait)

    # Record for specified duration
    print(f"Recording for {duration}s", file=sys.stderr)
    time.sleep(duration)

    # Stop recording — response contains the output file path
    print("Stopping recording", file=sys.stderr)
    try:
        stop_resp = cl.stop_record()
        time.sleep(1.5)  # Give OBS time to finalize the file
        recording_path = Path(stop_resp.output_path)
    except Exception as e:
        print(f"Error stopping recording: {e}", file=sys.stderr)
        recording_path = None

    # Terminate the app process
    print("Closing app", file=sys.stderr)
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

    if recording_path is None or not recording_path.exists():
        print("Error: Recording file not found after stopping OBS.", file=sys.stderr)
        sys.exit(1)

    print(f"Recording saved: {recording_path}", file=sys.stderr)
    print(str(recording_path))  # stdout: just the path, for the agent to capture

    subprocess.run(
        ["ffmpeg", "-y", "-i", recording_path, "-codec", "copy", "recording.mp4"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


if __name__ == "__main__":
    main()
