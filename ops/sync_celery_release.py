#!/usr/bin/env python3
"""Keep the existing production Celery services on the running web release.

Run on the Docker Swarm manager. No credentials or application settings change.
"""
import fcntl
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WEB = "reklam-analiz-analiz-8dzpai"
WORKER = "reklam-analiz-worker-j2xrq4"
BEAT = "reklam-analiz-beats-hcni7b"
STATE_DIR = Path("/var/lib/reklamanaliz")
BEAT_PATH = "/app/instagram_reklam_analiz/runtime/celerybeat"


def docker(*args):
    result = subprocess.run(["docker", *args], check=True, capture_output=True, text=True, timeout=120)
    return result.stdout.strip()


def main():
    STATE_DIR.mkdir(mode=0o750, parents=True, exist_ok=True)
    with (STATE_DIR / "celery-release.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        web = json.loads(docker("service", "inspect", WEB))[0]
        update = web.get("UpdateStatus", {}).get("State")
        if update and update not in {"completed", "rollback_completed"}:
            print("Web deployment is not stable; deferring Celery update.")
            return
        ids = docker("ps", "--filter", f"label=com.docker.swarm.service.name={WEB}", "--format", "{{.ID}}").splitlines()
        if len(ids) != 1:
            print("Expected one running web container; deferring Celery update.")
            return
        current = json.loads(docker("inspect", ids[0]))[0]
        started = datetime.fromisoformat(current["State"]["StartedAt"].replace("Z", "+00:00"))
        if (datetime.now(timezone.utc) - started).total_seconds() < 60:
            return
        image = current["Image"]
        state_file = STATE_DIR / "celery-release-state.json"
        attempts = json.loads(state_file.read_text()).get("requested", {}) if state_file.exists() else {}
        for service in (WORKER, BEAT):
            spec = json.loads(docker("service", "inspect", service))[0]
            replicas = spec["Spec"].get("Mode", {}).get("Replicated", {}).get("Replicas")
            if replicas != 1:
                raise RuntimeError(f"Expected one replica for {service}; refusing to change replica count.")
            state = spec.get("UpdateStatus", {}).get("State")
            if state and state not in {"completed", "rollback_completed"}:
                print(f"{service} update pending ({state}); deferring.")
                continue
            container = spec["Spec"]["TaskTemplate"]["ContainerSpec"]
            mounts = container.get("Mounts", [])
            needs_mount = service == BEAT and not any(m.get("Target") == BEAT_PATH for m in mounts)
            if container["Image"] == image and not needs_mount:
                continue
            if state == "rollback_completed" and attempts.get(service) == image:
                raise RuntimeError(f"{service} rolled back this image; manual investigation required.")
            cmd = ["service", "update", "--detach=true", "--no-resolve-image", "--image", image,
                   "--update-order", "stop-first", "--update-failure-action", "rollback",
                   "--update-monitor", "30s", "--stop-grace-period", "30m" if service == WORKER else "60s"]
            if needs_mount:
                beat_dir = STATE_DIR / "celerybeat"
                beat_dir.mkdir(mode=0o750, parents=True, exist_ok=True)
                cmd += ["--mount-add", f"type=bind,source={beat_dir},target={BEAT_PATH}"]
            docker(*cmd, service)
            attempts[service] = image
            state_file.write_text(json.dumps({"web_image": image, "requested": attempts,
                "checked_at": datetime.now(timezone.utc).isoformat()}) + "\n")
            print(f"Requested {service} update to {image[:23]}.")
        state_file.write_text(json.dumps({
            "web_image": image, "requested": attempts, "checked_at": datetime.now(timezone.utc).isoformat(),
        }) + "\n")


if __name__ == "__main__":
    main()
