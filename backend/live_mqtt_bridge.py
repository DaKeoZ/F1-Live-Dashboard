"""
Pont OpenF1 MQTT → file d'événements typés (car_data, location, stints).
Le jeton OAuth2 reste côté backend (mot de passe MQTT = access_token).
"""

from __future__ import annotations

import json
import logging
import os
import queue
import ssl
import threading
from typing import Any

import paho.mqtt.client as mqtt

from telemetry_service import _get_openf1_bearer_token

logger = logging.getLogger(__name__)

MQTT_BROKER = "mqtt.openf1.org"
MQTT_PORT = 8883
# Topics alignés sur la doc OpenF1 (chemins REST équivalents)
TOPICS = ("v1/car_data", "v1/location", "v1/stints")


class TelemetrySessionMqttBridge:
    """
    Souscrit à car_data + location + stints pour une session.
    - car_data : filtré par session_key + driver_number (pilote sélectionné)
    - location : tous les pilotes de la session (carte)
    - stints : tous les pilotes de la session (stratégie pneus)
    """

    def __init__(self, session_key: int, driver_number: int) -> None:
        self.session_key = int(session_key)
        self.driver_number = int(driver_number)
        self._q: queue.Queue[dict | None] = queue.Queue(maxsize=2000)
        self._client: mqtt.Client | None = None
        self._thread: threading.Thread | None = None

    def _put(self, item: dict) -> None:
        try:
            self._q.put_nowait(item)
        except queue.Full:
            try:
                self._q.get_nowait()
            except queue.Empty:
                pass
            try:
                self._q.put_nowait(item)
            except queue.Full:
                pass

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        topic = msg.topic or ""
        try:
            data = json.loads(msg.payload.decode())
        except Exception:
            return
        try:
            sk = int(data.get("session_key", -1))
        except (TypeError, ValueError):
            return
        if sk != self.session_key:
            return

        if topic.endswith("car_data") or topic == "v1/car_data":
            try:
                dn = int(data.get("driver_number", -1))
            except (TypeError, ValueError):
                return
            if dn != self.driver_number:
                return
            self._put({"ch": "car_data", "d": data})
            return

        if "location" in topic:
            try:
                dn = int(data.get("driver_number", -1))
            except (TypeError, ValueError):
                return
            if dn < 0:
                return
            self._put({"ch": "location", "d": data})
            return

        if "stint" in topic:
            self._put({"ch": "stint", "d": data})
            return

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        rc: int,
    ) -> None:
        if rc == 0:
            for t in TOPICS:
                client.subscribe(t, qos=0)
            logger.info("MQTT connecté, abonnements : %s", ", ".join(TOPICS))
        else:
            logger.warning("MQTT connect rc=%s", rc)

    def start(self) -> None:
        token = _get_openf1_bearer_token()
        if not token:
            raise RuntimeError(
                "Aucun jeton OpenF1 : définissez OPENF1_ACCESS_TOKEN ou OPENF1_USERNAME + OPENF1_PASSWORD."
            )

        mqtt_user = os.getenv("OPENF1_USERNAME", "openf1").strip() or "openf1"

        self._client = mqtt.Client(
            client_id=f"f1live-{self.session_key}-{self.driver_number}"[:22],
            callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
        )
        self._client.username_pw_set(mqtt_user, token)
        self._client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

        self._client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        self._thread = threading.Thread(target=self._client.loop_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception:
                pass
            self._client = None

    def get_blocking(self, timeout: float) -> dict | None:
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None


# Alias rétrocompatibilité éventuelle
CarDataMqttBridge = TelemetrySessionMqttBridge
