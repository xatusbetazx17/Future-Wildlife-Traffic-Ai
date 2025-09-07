import json
import socket
from typing import Dict, Any, Optional

try:
    import paho.mqtt.client as mqtt
    _HAS_MQTT = True
except Exception:
    _HAS_MQTT = False

class Broadcaster:
    def __init__(self, mqtt_host: str, mqtt_port: int, topic: str, udp_port: int, enable_mqtt: bool, enable_udp: bool):
        self.enable_mqtt = enable_mqtt and _HAS_MQTT
        self.enable_udp = enable_udp
        self.topic = topic
        self.udp_port = udp_port
        self.sock = None
        self.client = None

        if self.enable_udp:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        if self.enable_mqtt:
            self.client = mqtt.Client()
            try:
                self.client.connect(mqtt_host, mqtt_port, 60)
            except Exception:
                self.client = None
                self.enable_mqtt = False

    def publish(self, event: Dict[str, Any]):
        payload = json.dumps(event).encode("utf-8")
        if self.enable_udp and self.sock:
            self.sock.sendto(payload, ("255.255.255.255", self.udp_port))
        if self.enable_mqtt and self.client:
            self.client.publish(self.topic, payload)