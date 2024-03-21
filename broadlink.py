import logging
from hashlib import md5, sha1
import json
import base64
from pprint import pprint
from time import time
from copy import copy
import requests
from Crypto.Cipher import AES


class HttpRequestor:
    loginURL = "https://app-service-deu-f0e9ebbb.smarthomecs.de/account/login"
    familylistURL = "https://app-service-deu-f0e9ebbb.smarthomecs.de/appsync/group/member/getfamilylist"
    roomlistURL = (
        "https://app-service-deu-f0e9ebbb.smarthomecs.de/appsync/group/room/query"
    )
    devicelistURL = "https://app-service-deu-f0e9ebbb.smarthomecs.de/appsync/group/dev/query?action=select"
    stateURL = (
        "https://app-service-deu-f0e9ebbb.smarthomecs.de/device/control/v2/querystate"
    )
    sdkcURL = (
        "https://app-service-deu-f0e9ebbb.smarthomecs.de/device/control/v2/sdkcontrol"
    )

    aeskeypart = b"kdixkdqp54545^#*"
    aeskeytokenpart = b"xgx3d*fe3478$ukx"
    passwordsha1 = b"4969fj#k23#"
    # Static IV
    aesiv = b"\xea\xaa\xaa:\xbbXb\xa2\x19\x18\xb5w\x1d\x16\x15\xaa"
    licenseId = "3c015b249dd66ef0f11f9bef59ecd737"
    companyID = "48eb1b36cf0202ab2ef07b880ecda60d"
    session = None
    familyid = None
    roomlist = None
    devlist = None

    license = "PAFbJJ3WbvDxH5vvWezXN5BujETtH/iuTtIIW5CE/SeHN7oNKqnEajgljTcL0fBQQWM0XAAAAAAnBhJyhMi7zIQMsUcwR/PEwGA3uB5HLOnr+xRrci+FwHMkUtK7v4yo0ZHa+jPvb6djelPP893k7SagmffZmOkLSOsbNs8CAqsu8HuIDs2mDQAAAAA="  # pylint: disable=C0301

    generichdr = {
        "system": "android",
        "appPlatform": "android",
        "language": "en-",
        "appVersion": "3.2.1.acfreendom-base125.14d116b97",
        "loginmode": "mutuallyexclusive",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 14; SM-F731B Build/UP1A.231005.007)",
    }

    def __init__(self, email, password):
        self.email = email
        self.password = password

    def HashPassword(self, password):
        return sha1(password.encode() + self.passwordsha1).hexdigest()

    @staticmethod
    def maketimestamp():

        timestamp = str(int(time()))
        messageId = timestamp + "123"
        return {
            "timestamp": timestamp,
            "messageId": messageId,
        }

    def login(self):
        form = {
            "companyid": self.companyID,
            "lid": self.licenseId,
            "email": self.email,
            "password": self.HashPassword(self.password),
        }
        formstring = json.dumps(form)
        token = md5(formstring.encode() + self.aeskeytokenpart).hexdigest()
        headers = copy(self.generichdr)
        headers.update(
            {
                "lid": self.licenseId,
                "licenseId": self.licenseId,
                "email": self.email,
                "token": token,
                "Content-type": "application/x-java-serialized-object",
            }
        )
        headers.update(self.maketimestamp())
        cipher = AES.new(
            md5(str(headers["timestamp"]).encode() + self.aeskeypart).digest(),
            AES.MODE_CBC,
            self.aesiv,
        )
        padsize = 16 - len(formstring) % 16
        encrypteddata = cipher.encrypt(formstring.encode() + b"\x00" * padsize)
        response = requests.post(
            self.loginURL, headers=headers, data=encrypteddata, timeout=30
        )
        self.session = response.json()
        return True

    def familylist(self):
        headers = copy(self.generichdr)
        headers.update(
            {
                "loginsession": self.session["loginsession"],
                "userid": self.session["userid"],
                "licenseid": self.licenseId,
            }
        )
        headers.update(self.maketimestamp())
        familyresponse = requests.post(self.familylistURL, headers=headers, timeout=30)
        self.familyid = familyresponse.json()["data"]["familyList"][0]["familyid"]
        return True

    def listrooms(self):
        headers = copy(self.generichdr)
        headers.update(
            {
                "loginsession": self.session["loginsession"],
                "userid": self.session["userid"],
                "licenseid": self.licenseId,
                "familyId": self.familyid,
            }
        )
        headers.update(self.maketimestamp())
        roomlistresponse = requests.post(self.roomlistURL, headers=headers, timeout=30)
        self.roomlist = {
            x["roomid"]: x for x in roomlistresponse.json()["data"]["roomList"]
        }

    def listdevices(self):
        headers = copy(self.generichdr)
        headers.update(
            {
                "loginsession": self.session["loginsession"],
                "userid": self.session["userid"],
                "licenseid": self.licenseId,
                "familyId": self.familyid,
                "Content-Type": "application/json; charset=UTF-8",
            }
        )
        headers.update(self.maketimestamp())
        pidlist = {"pids": []}
        devlistresponse = requests.post(
            self.devicelistURL, headers=headers, data=json.dumps(pidlist), timeout=30
        )
        self.devlist = devlistresponse.json()["data"]["endpoints"]
        print(self.devlist)
        # self.devlist = self.devlist[0:3]
        return True

    def sdkgetset(self, modejson):
        """
        gotdata = {
            'params': ['envtemp', 'model', 'ac_errcode1', 'err_flag', 'new_type'],
            'vals': [
                [{'val': 176, 'idx': 1}],
                [{'val': 1, 'idx': 1}],
                [{'val': 0, 'idx': 1}],
                [{'val': 0, 'idx': 1}],
                [{'val': 1, 'idx': 1}]
            ]
        }
        =>
        envtemp: 176, model: 1, ac_errcode1: 0, err_flag: 0, new_type: 1
        """
        headers = copy(self.generichdr)
        headers.update(
            {
                "loginsession": self.session["loginsession"],
                "userid": self.session["userid"],
                "licenseid": self.licenseId,
                "lid": self.licenseId,
                "Content-Type": "application/x-java-serialized-object",
            }
        )
        sdkresp = requests.post(
            self.sdkcURL,
            params={"license": self.license},
            headers=headers,
            data=json.dumps(modejson),
            timeout=30,
        )
        pprint(sdkresp.text)
        gotdata = json.loads(sdkresp.json()["event"]["payload"]["data"])
        return dict(zip(gotdata["params"], (x[0]["val"] for x in gotdata["vals"])))


class Airco:
    device = None
    http = None
    values = None
    last = 0

    def __init__(self, http, device):
        self.http = http
        self.device = device
        self.values = {}

    def getmode(self, modes):
        cookieorig = json.loads(base64.b64decode(self.device["cookie"]))
        cookie = {
            "device": {
                "aeskey": cookieorig["aeskey"],
                "did": self.device["endpointId"],
                "id": 1,
                "key": cookieorig["aeskey"],
                "mac": self.device["mac"],
                "pid": self.device["productId"],
            }
        }

        timestamp = str(int(time()))
        modejson = {
            "directive": {
                "endpoint": {
                    "cookie": {},
                    "devSession": self.device["devSession"],
                    "devicePairedInfo": {
                        "cookie": base64.b64encode(
                            json.dumps(cookie).encode()
                        ).decode(),
                        "devicetypeflag": 0,
                        "did": self.device["endpointId"],
                        "mac": self.device["mac"],
                        "pid": self.device["productId"],
                    },
                    "endpointId": self.device["endpointId"],
                },
                "header": {
                    "interfaceVersion": "2",
                    "messageId": self.device["endpointId"] + "-" + str(timestamp),
                    "name": "KeyValueControl",
                    "namespace": "DNA.KeyValueControl",
                    "timstamp": timestamp,
                },
                "payload": {
                    "act": "get",
                    "did": self.device["endpointId"],
                    "params": list(modes.keys()),
                    "srv": ["108.1.40"],
                    "vals": [[{"idx": 1, "val": x}] for x in list(modes.values())],
                },
            }
        }
        return self.http.sdkgetset(modejson)

    def setmode(self, modes, extrapayload=None):
        cookieorig = json.loads(base64.b64decode(self.device["cookie"]))
        cookie = {
            "device": {
                "aeskey": cookieorig["aeskey"],
                "did": self.device["endpointId"],
                "id": 1,
                "key": cookieorig["aeskey"],
                "mac": self.device["mac"],
                "pid": self.device["productId"],
            }
        }

        timestamp = str(int(time()))
        modes.update(
            {"H5_msgId": "H5_msgId_" + self.device["endpointId"] + timestamp + "000"}
        )
        modejson = {
            "directive": {
                "endpoint": {
                    "cookie": {},
                    "devSession": self.device["devSession"],
                    "devicePairedInfo": {
                        "cookie": base64.b64encode(
                            json.dumps(cookie).encode()
                        ).decode(),
                        "devicetypeflag": 0,
                        "did": self.device["endpointId"],
                        "mac": self.device["mac"],
                        "pid": self.device["productId"],
                    },
                    "endpointId": self.device["endpointId"],
                },
                "header": {
                    "interfaceVersion": "2",
                    "messageId": self.device["endpointId"] + "-" + str(timestamp),
                    "name": "KeyValueControl",
                    "namespace": "DNA.KeyValueControl",
                    "timstamp": timestamp,
                },
                "payload": {
                    "act": "set",
                    "did": self.device["endpointId"],
                    "params": list(modes.keys()),
                    "srv": ["108.1.40"],
                    "vals": [[{"idx": 1, "val": x}] for x in list(modes.values())],
                },
            }
        }
        if extrapayload:
            modejson["directive"]["payload"].update(extrapayload)
        try:
            self.http.sdkgetset(modejson)
        except KeyError:
            pass

    def getinfo(self):
        try:
            self.values.update(self.getmode({"mode": 0}))
            self.values.update(self.getmode({"ac_mode": 0}))
            self.last = time()
        except KeyError:
            pass  # komt later wel
        pprint(self.values)


class AircoList:
    http = None
    aircos = {}

    def __init__(self, email, password):
        logging.info("Setup")
        self.http = HttpRequestor(email, password)
        logging.info("Login")
        self.http.login()
        logging.info("Familylist")
        self.http.familylist()
        logging.info("List Rooms")
        self.http.listrooms()
        logging.info("List Devices")
        self.http.listdevices()
        for dev in self.http.devlist:
            self.aircos[dev["endpointId"]] = Airco(self.http, dev)
        for name, airco in self.aircos.items():
            logging.info("Getting values from %s", name)
            airco.getinfo()
