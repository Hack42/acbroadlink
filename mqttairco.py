#!/usr/bin/python3
import yaml
import logging
import json
import paho.mqtt.client as mqtt
from broadlink import AircoList

logging.basicConfig(level=logging.DEBUG)
from pprint import pprint
import time


ACMODES = ["off", "cool", "heat", "fan_only", "dry"]
FANMODES = ["Auto", "Low", "Medium", "High", "Turbo", "Mute"]
SWINGMODES = ["Off", "Vertical", "Horizontal", "3D"]


def on_connect(client, userdata, flags, reason_code):
    print(f"Connected with result code {reason_code}")
    client.publish("acbroadlink/LWT", payload="Online", qos=0, retain=True)
    client.subscribe("acbroadlink/+/+/set")


def on_message(client, userdata, msg):
    print(msg.topic + " " + str(msg.payload))
    parts = msg.topic.split("/")
    device = parts[1]
    cmd = parts[2]
    isset = parts[3]
    if isset != "set":
        return
    logging.debug("Set command for: %s", device)
    if device not in al.aircos:
        logging.debug("Device not found: %s", device)
        return
    airco = al.aircos[device]
    payload = msg.payload.decode()
    if cmd == "mode":
        if payload == "off":
            airco.setmode({"pwr": 0}, {"prop": "stdctrl"})
        else:
            ac_mode = ACMODES.index(payload) - 1
            airco.setmode(
                {
                    "pwr": 1,
                    "ac_mode": ac_mode,
                    "ac_clean": airco.values["ac_clean"],
                    "mldprf": airco.values["mldprf"],
                    "scrdisp": airco.values["scrdisp"],
                    "ac_vdir": airco.values["ac_vdir"],
                    "ac_hdir": airco.values["ac_hdir"],
                    "model": airco.values["model"],
                }
            )
        airco.last = 1
        return
    if cmd == "temp":
        newtemp = float(msg.payload) * 10
        airco.setmode(
            {
                "temp": newtemp,
                "tempunit": 1,
                "ac_tempdec": 0,
                "ac_tempconvert": 0,
                "model": airco.values["model"],
            }
        )
        airco.last = 1
        return
    if cmd == "power":
        if payload == "off":
            airco.setmode({"pwr": 0}, {"prop": "stdctrl"})
        else:
            airco.setmode({"pwr": 1}, {"prop": "stdctrl"})
        airco.last = 1
        return
    if cmd == "fan":
        airco.setmode(
            {
                "ac_mark": FANMODES.index(msg.payload.decode()),
                "model": airco.values["model"],
            }
        )
        airco.last = 1
        return
    if cmd == "health":
        airco.setmode(
            {
                "ac_health": 1 if msg.payload == b"ON" else 0,
                "model": airco.values["model"],
            }
        )
        airco.last = 1
        return
    if cmd == "clean":
        airco.setmode(
            {
                "ac_clean": 1 if msg.payload == b"ON" else 0,
                "model": airco.values["model"],
            }
        )
        airco.last = 1
        return
    if cmd == "display":
        airco.setmode(
            {
                "scrdisp": 1 if msg.payload == b"ON" else 0,
                "model": airco.values["model"],
            }
        )
        airco.last = 1
        return
    if cmd == "swing":
        num = SWINGMODES.index(msg.payload.decode())
        vdir = num & 1
        hdir = int((num & 2) / 2)
        airco.setmode(
            {"ac_vdir": vdir, "ac_hdir": hdir, "model": airco.values["model"]}
        )
        airco.last = 1
        return


def gen_ha_config(device):
    device_name = device.device["endpointId"]
    haac_topic = "homeassistant/climate/" + device_name + "/config"
    mqtt_base_topic = "acbroadlink/" + device_name
    """Generate a automatic configuration for Home Assistant."""
    json_config = {
        "avail_t": "acbroadlink/LWT",
        "name": device.device["friendlyName"],
        "obj_id": "climate_" + device.device["endpointId"],
        "uniq_id": "climate_" + device.device["endpointId"],
        "stat_t": mqtt_base_topic + "/status",
        "cmd_t": mqtt_base_topic + "/cmd",
        "current_temperature_topic": mqtt_base_topic + "/env_temp",
        "fan_mode_command_topic": mqtt_base_topic + "/fan/set",
        "fan_mode_state_topic": mqtt_base_topic + "/fan/state",
        "min_temp": 16,
        "max_temp": 32,
        "fan_modes": FANMODES,
        "modes": ACMODES,
        "swing_modes": SWINGMODES,
        "temperature_unit": "C",
        "temp_step": 0.5,
        "precision": 0.5,
        "mode_command_topic": mqtt_base_topic + "/mode/set",
        "mode_state_topic": mqtt_base_topic + "/mode/state",
        "power_command_topic": mqtt_base_topic + "/power/set",
        "swing_mode_command_topic": mqtt_base_topic + "/swing/set",
        "swing_mode_state_topic": mqtt_base_topic + "/swing/state",
        "temperature_command_topic": mqtt_base_topic + "/temp/set",
        "temperature_state_topic": mqtt_base_topic + "/temp/state",
        "pl_avail": "online",
        "pl_not_avail": "offline",
        "device": {
            "connections": [["mac", device.device["mac"]]],
            "identifiers": [
                device.device["friendlyName"],
                device.device["mac"],
                device.device["endpointId"],
            ],
            "ids": "acbroadlink",
            "name": "BroadlinkCloud2MQTT",
            "mf": "Broadlink",
            "model": "Aircon",
        },
    }
    haac_stopic_temp = "homeassistant/sensor/" + device_name + "_temp/config"
    temp_json_config = {
        "avail_t": "acbroadlink/LWT",
        "name": device.device["friendlyName"],
        "obj_id": "sensor_t_" + device.device["endpointId"],
        "uniq_id": "sensor_t_" + device.device["endpointId"],
        "stat_t": mqtt_base_topic + "/env_temp",
        "device_class": "temperature",
        "device": {
            "connections": [["mac", device.device["mac"]]],
            "identifiers": [
                device.device["friendlyName"],
                device.device["mac"],
                device.device["endpointId"],
            ],
            "ids": "acbroadlink",
            "name": "BroadlinkCloud2MQTT",
            "mf": "Broadlink",
            "model": "Aircon",
        },
    }

    haac_stopic_display = "homeassistant/switch/" + device_name + "_display/config"
    display_json_config = {
        "avail_t": "acbroadlink/LWT",
        "name": device.device["friendlyName"] + " Display",
        "obj_id": "sensor_display_" + device.device["endpointId"],
        "uniq_id": "sensor_display_" + device.device["endpointId"],
        "command_topic": mqtt_base_topic + "/display/set",
        "state_topic": mqtt_base_topic + "/display/state",
        "state_on": 1,
        "state_off": 0,
        "device": {
            "connections": [["mac", device.device["mac"]]],
            "identifiers": [
                device.device["friendlyName"],
                device.device["mac"],
                device.device["endpointId"],
            ],
            "ids": "acbroadlink",
            "name": "BroadlinkCloud2MQTT",
            "mf": "Broadlink",
            "model": "Aircon",
        },
    }
    haac_stopic_clean = "homeassistant/switch/" + device_name + "_clean/config"
    clean_json_config = {
        "avail_t": "acbroadlink/LWT",
        "name": device.device["friendlyName"] + " Clean",
        "obj_id": "sensor_clean_" + device.device["endpointId"],
        "uniq_id": "sensor_clean_" + device.device["endpointId"],
        "command_topic": mqtt_base_topic + "/clean/set",
        "state_topic": mqtt_base_topic + "/clean/state",
        "state_on": 1,
        "state_off": 0,
        "device": {
            "connections": [["mac", device.device["mac"]]],
            "identifiers": [
                device.device["friendlyName"],
                device.device["mac"],
                device.device["endpointId"],
            ],
            "ids": "acbroadlink",
            "name": "BroadlinkCloud2MQTT",
            "mf": "Broadlink",
            "model": "Aircon",
        },
    }
    haac_stopic_health = "homeassistant/switch/" + device_name + "_health/config"
    health_json_config = {
        "avail_t": "acbroadlink/LWT",
        "name": device.device["friendlyName"] + " Health",
        "obj_id": "sensor_health_" + device.device["endpointId"],
        "uniq_id": "sensor_health_" + device.device["endpointId"],
        "command_topic": mqtt_base_topic + "/health/set",
        "state_topic": mqtt_base_topic + "/health/state",
        "state_on": 1,
        "state_off": 0,
        "device": {
            "connections": [["mac", device.device["mac"]]],
            "identifiers": [
                device.device["friendlyName"],
                device.device["mac"],
                device.device["endpointId"],
            ],
            "ids": "acbroadlink",
            "name": "BroadlinkCloud2MQTT",
            "mf": "Broadlink",
            "model": "Aircon",
        },
    }

    mqttl.set(haac_topic, json.dumps(json_config))
    mqttl.set(haac_stopic_temp, json.dumps(temp_json_config))
    mqttl.set(haac_stopic_display, json.dumps(display_json_config))
    mqttl.set(haac_stopic_clean, json.dumps(clean_json_config))
    mqttl.set(haac_stopic_health, json.dumps(health_json_config))


def gen_ha_status(device):
    device_name = device.device["endpointId"]
    mqtt_base_topic = "acbroadlink/" + device_name
    if not device.values:
        return {}
    mqttl.set(mqtt_base_topic + "/available", "online")
    mqttl.set(mqtt_base_topic + "/env_temp", device.values["envtemp"] / 10)
    mqttl.set(mqtt_base_topic + "/temp/state", device.values["temp"] / 10)
    mqttl.set(mqtt_base_topic + "/fan/state", FANMODES[device.values["ac_mark"]])
    mqttl.set(mqtt_base_topic + "/display/state", device.values["scrdisp"])
    mqttl.set(mqtt_base_topic + "/clean/state", device.values["ac_clean"])
    mqttl.set(mqtt_base_topic + "/health/state", device.values["ac_health"])
    mqttl.set(mqtt_base_topic + "/sleep/state", device.values["ac_slp"])
    mqttl.set(
        mqtt_base_topic + "/mode/state",
        ACMODES[
            (
                device.values["ac_mode"] + device.values["pwr"]
                if device.values["pwr"]
                else 0
            )
        ],
    )
    mqttl.set(
        mqtt_base_topic + "/swing/state",
        SWINGMODES[device.values["ac_vdir"] + device.values["ac_hdir"] * 2],
    )


class MqttTopic:
    topic = None
    payload = None
    retain = None

    def update(self, client, topic, payload, retain=True):
        if topic == self.topic and payload == self.payload and retain == self.retain:
            return
        self.topic = topic
        self.payload = payload
        self.retain = retain
        client.publish(topic, payload, retain=retain)


class MqttTopics:
    topics = None

    def __init__(self, client):
        self.topics = {}
        self.client = client

    def set(self, topic, payload, retain=True):
        if topic not in self.topics:
            self.topics[topic] = MqttTopic()
        self.topics[topic].update(self.client, topic, payload, retain)


with open("config.yaml", "r") as f:
    config = yaml.load(f)

al = AircoList(config['email'], config['password'])
mqttc = mqtt.Client()
mqttc.on_connect = on_connect
mqttc.on_message = on_message
mqttc.will_set("acbroadlink/LWT", payload="Offline", qos=0, retain=True)
mqttc.connect("monitor", 1883, 60)
mqttc.loop_start()
mqttl = MqttTopics(mqttc)

for dev in al.aircos.values():
    gen_ha_config(dev)
    gen_ha_status(dev)

while True:
    pass
    for dev in al.aircos.values():
        if dev.last:
            if dev.last < time.time() - 60:
                dev.getinfo()
                gen_ha_status(dev)
    time.sleep(1)
