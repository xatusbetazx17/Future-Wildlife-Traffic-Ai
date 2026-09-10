"""Optional MQTT 5 transport. JSON advisories are not standardized V2X messages."""

import json
import math
import os
import threading
from datetime import datetime


class MqttPublisher:
    def __init__(self, config):
        import paho.mqtt.client as mqtt

        self.mqtt = mqtt
        self.config = config
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)
        self.client.max_queued_messages_set(100)
        self.client.max_inflight_messages_set(10)
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        if config.ca_file:
            self.client.tls_set(ca_certs=config.ca_file, certfile=config.cert_file, keyfile=config.key_file)
        if config.username_env:
            user, password = os.environ.get(config.username_env), os.environ.get(config.password_env)
            if not user or not password:
                raise ValueError("configured MQTT credential environment variables are missing")
            self.client.username_pw_set(user, password)
        self.client.connect_async(config.host, config.port, keepalive=30)
        self.client.loop_start()

    def publish(self, event, now):
        if not self.client.is_connected():
            return False
        ttl = math.floor(datetime.fromisoformat(event["expires_at"]).timestamp() - now)
        if ttl <= 0:
            return False
        props = self.mqtt.Properties(self.mqtt.PacketTypes.PUBLISH)
        props.MessageExpiryInterval = ttl
        info = self.client.publish(
            self.config.topic_prefix + "/" + event["site_id"],
            json.dumps(event, allow_nan=False),
            qos=1,
            retain=False,
            properties=props,
        )
        if info.rc != self.mqtt.MQTT_ERR_SUCCESS:
            return False
        info.wait_for_publish(timeout=2)
        return info.is_published()

    def close(self):
        self.client.disconnect()
        self.client.loop_stop()


class OutboxWorker:
    def __init__(self, runtime, publisher):
        self.runtime, self.publisher = runtime, publisher
        self.stop = threading.Event()
        self.last_error = None
        self.thread = threading.Thread(target=self.run, name="wildlife-outbox", daemon=True)

    def run(self):
        while not self.stop.is_set():
            try:
                events = self.runtime.store.events(self.runtime.wall(), limit=20, pending=True)
                for event in events:
                    if self.stop.is_set():
                        break
                    if self.publisher.publish(event, self.runtime.wall()):
                        self.runtime.store.delivered(event["event_id"])
                    else:
                        break
                self.last_error = None
            except Exception as exc:
                # Do not expose broker URLs, credentials or remote payloads.
                self.last_error = type(exc).__name__
            self.stop.wait(0.5)

    def close(self):
        self.stop.set()
        if self.thread.is_alive():
            self.thread.join(timeout=4)
        self.publisher.close()
