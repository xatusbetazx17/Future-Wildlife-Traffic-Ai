import cv2
import numpy as np
import pytest

from src.capture import CaptureWorker
from src.comms import OutboxWorker
from src.config import AppConfig
from src.evaluation import Dataset, evaluate
from src.runtime import Runtime
from src.simulation import demo_config


def test_evaluation_counts_and_unknown_denominators():
    dataset = Dataset.model_validate(
        {
            "provenance": "synthetic",
            "description": "test",
            "windows": [
                {
                    "id": "1",
                    "species": "deer",
                    "condition": "dry",
                    "animal_present": True,
                    "warned": True,
                    "duration_s": 3600,
                    "warning_latency_ms": 200,
                },
                {
                    "id": "2",
                    "species": "deer",
                    "condition": "night",
                    "animal_present": True,
                    "warned": False,
                    "duration_s": 3600,
                },
                {
                    "id": "3",
                    "species": "none",
                    "condition": "dry",
                    "animal_present": False,
                    "warned": True,
                    "duration_s": 3600,
                },
            ],
        }
    )
    result = evaluate(dataset)["metrics"]
    assert result["precision"] == 0.5 and result["recall"] == 0.5
    assert result["false_warning_windows_per_hour"] == pytest.approx(1 / 3)
    assert result["latency_p95_ms"] == 200
    assert result["recall_wilson_95"][0] < 0.5 < result["recall_wilson_95"][1]
    assert evaluate(dataset)["by_species"]["none"]["recall"] is None


def test_duplicate_evaluation_windows_rejected():
    from pydantic import ValidationError

    window = {
        "id": "same",
        "species": "deer",
        "condition": "dry",
        "animal_present": True,
        "warned": False,
        "duration_s": 1,
    }
    with pytest.raises(ValidationError):
        Dataset.model_validate({"provenance": "field", "description": "test", "windows": [window, window]})


def test_outbox_retry_only_acknowledges_success(runtime):
    class Publisher:
        def __init__(self):
            self.calls = 0

        def publish(self, event, now):
            self.calls += 1
            if self.calls == 1:
                return False
            worker.stop.set()
            return True

        def close(self):
            pass

    publisher = Publisher()
    worker = OutboxWorker(runtime, publisher)
    worker.thread.start()
    worker.thread.join(timeout=2)
    assert publisher.calls == 2
    assert runtime.store.pending_count(runtime.wall()) == 0
    worker.close()


def test_mqtt_exception_keeps_pending(runtime):
    class Publisher:
        def publish(self, event, now):
            worker.stop.set()
            raise OSError("simulated outage")

        def close(self):
            pass

    worker = OutboxWorker(runtime, Publisher())
    worker.thread.start()
    worker.thread.join(timeout=2)
    assert runtime.store.pending_count(runtime.wall()) == 1
    assert worker.last_error == "OSError"
    worker.close()


def test_real_video_eof_exits_and_motion_is_not_coverage(tmp_path):
    path = tmp_path / "frames.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 30, (64, 64))
    assert writer.isOpened()
    for _ in range(3):
        writer.write(np.zeros((64, 64, 3), np.uint8))
    writer.release()
    raw = demo_config().model_dump()
    raw["sites"][0]["sensors"] = [
        {
            "id": "north",
            "kind": "video",
            "source": str(path),
            "detector": "motion",
            "max_fps": 60,
            "allowed_conditions": ["unknown"],
        }
    ]
    cfg = AppConfig.model_validate(raw)
    rt = Runtime(cfg)
    try:
        worker = CaptureWorker(rt, cfg.sites[0], cfg.sites[0].sensors[0])
        worker.thread.start()
        worker.thread.join(timeout=3)
        assert not worker.thread.is_alive()
        assert worker.last_error == "end_of_video"
        state = rt.status()["sites"][0]
        assert not state["monitoring_healthy"]
        assert not state["animal_detected"]
    finally:
        rt.close()


def test_mqtt_transport_contract_preserves_expiry_tls_and_qos(runtime, tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    import paho.mqtt.client as mqtt

    from src.comms import MqttPublisher
    from src.config import MqttConfig

    fake = MagicMock()
    fake.is_connected.return_value = True
    fake.publish.return_value.rc = mqtt.MQTT_ERR_SUCCESS
    fake.publish.return_value.is_published.return_value = True
    monkeypatch.setattr(mqtt, "Client", MagicMock(return_value=fake))
    cfg = MqttConfig(enabled=True, host="broker.example.com", ca_file=str(tmp_path / "ca.pem"))
    publisher = MqttPublisher(cfg)
    event = runtime.store.events(runtime.wall())[0]
    assert publisher.publish(event, runtime.wall())
    fake.tls_set.assert_called_once()
    kwargs = fake.publish.call_args.kwargs
    assert kwargs["qos"] == 1 and kwargs["retain"] is False
    assert kwargs["properties"].MessageExpiryInterval == 30
    assert not publisher.publish(event, runtime.wall() + 31)
    publisher.close()
