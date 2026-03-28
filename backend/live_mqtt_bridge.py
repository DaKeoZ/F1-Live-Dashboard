"""
Pont OpenF1 MQTT (v1/car_data) → file d'événements filtrés par session / pilote.
Le jeton OAuth2 reste côté backend (paho utilise le mot de passe MQTT = access_token).
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
TOPIC_CAR_DATA = "v1/car_data"


class CarDataMqttBridge:
    """Souscrit à v1/car_data et ne garde que les messages pour session_key + driver_number."""

    def __init__(self, session_key: int, driver_number: int) -> None:
        self.session_key = int(session_key)
        self.driver_number = int(driver_number)
        self._q: queue.Queue[dict | None] = queue.Queue(maxsize=800)
        self._client: mqtt.Client | None = None
        self._thread: threading.Thread | None = None

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        try:
            data = json.loads(msg.payload.decode())
        except Exception:
            return
        try:
            sk = int(data.get("session_key", -1))
            dn = int(data.get("driver_number", -1))
        except (TypeError, ValueError):
            return
        if sk != self.session_key or dn != self.driver_number:
            return
        try:
            self._q.put_nowait(data)
        except queue.Full:
            try:
                self._q.get_nowait()
            except queue.Empty:
                pass
            try:
                self._q.put_nowait(data)
            except queue.Full:
                pass

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        rc: int,
    ) -> None:
        if rc == 0:
            client.subscribe(TOPIC_CAR_DATA, qos=0)
            logger.info("MQTT connecté, abonnement %s", TOPIC_CAR_DATA)
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
            client_id=f"f1dash-{self.session_key}-{self.driver_number}"[:22],
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
        """None = timeout ; dict = message filtré."""
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None
