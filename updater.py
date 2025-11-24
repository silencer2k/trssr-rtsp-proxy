import logging
import os
import re
import sys
import time

import jstyleson
import requests
import urllib3
from cachetools import TTLCache, cached
from transliterate import translit

TRASSIR_API_HOST = os.environ["API_HOST"]
TRASSIR_RTSP_HOST = os.environ["RTSP_HOST"]

TRASSIR_LOGIN = os.environ["LOGIN"]
TRASSIR_PASSWORD = os.environ["PASSWORD"]

PATHS = os.environ["PATHS"]

TRASSIR_STREAMS = ["sub"]

API_HOST = "http://localhost:9997"

CHECK_INTERVAL = 15
RELOAD_INTERVAL = 600


logging.basicConfig(stream=sys.stdout, level=logging.INFO)

LOGGER = logging.getLogger()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class TrassirAPI:
    def __init__(self):
        self.sid = None

    def auth(self):
        params = {"username": TRASSIR_LOGIN, "password": TRASSIR_PASSWORD}

        resp = requests.get(f"{TRASSIR_API_HOST}/login", params, verify=False)
        resp_json = jstyleson.loads(resp.text)

        if resp_json.get("success", 1) == 0:
            return None

        self.sid = resp_json.get("sid", None)
        return resp_json

    def request(self, method, reauth=False, **kwargs):
        if reauth or self.sid is None:
            self.auth()
            reauth = True

        params = kwargs
        params.update({"sid": self.sid})

        resp = requests.get(f"{TRASSIR_API_HOST}/{method}", params, verify=False)
        resp_json = jstyleson.loads(resp.text)

        if resp_json.get("success", 1) == 0:
            if not reauth and resp_json.get("error_code", "") == "no session":
                return self.request(method, reauth=True, **kwargs)

            return None

        return resp_json


class API:
    def get(self, method):
        resp = requests.get(f"{API_HOST}/v3/{method}")
        return resp.json()

    def post(self, method, payload=None):
        resp = requests.post(f"{API_HOST}/v3/{method}", json=payload)
        return resp.json() if len(resp.content) > 0 else None

    def delete(self, method):
        resp = requests.delete(f"{API_HOST}/v3/{method}")
        return resp.json()


class Updater:
    def __init__(self):
        self.trassir_api = TrassirAPI()
        self.api = API()

        self.all_paths = []

    def get_id(self, name):
        return re.sub(
            r"[^0-9a-z]+", "_", translit(name, "ru", reversed=True).lower().strip()
        )

    @cached(cache=TTLCache(maxsize=1, ttl=RELOAD_INTERVAL))
    def get_channels(self):
        LOGGER.debug("[updater] update channel list")

        resp = self.trassir_api.request("channels")
        channels = {}

        for channel in sorted(
            resp["channels"], key=lambda x: x["name"] + "|" + x["guid"]
        ):
            channel_id = self.get_id(channel["name"])
            if channel_id in channels:
                n = 2
                while channel_id in channels:
                    channel_id = self.get_id(channel["name"]) + f"_{n}"
                    n += 1

            channels[channel_id] = channel

        return channels

    def get_video(self, channel, stream):
        resp = self.trassir_api.request(
            "get_video",
            channel=channel["guid"],
            stream=stream,
            container="rtsp",
            audio="pcmu",
        )

        return f"{TRASSIR_RTSP_HOST}/{resp['token']}"

    def get_paths(self, channels):
        paths = []

        for channel_id in channels:
            if channels[channel_id]["have_mainstream"] == "1":
                paths += [channel_id]
            for stream in TRASSIR_STREAMS:
                if channels[channel_id][f"have_{stream}stream"] == "1":
                    paths += [channel_id + "/" + stream]

        return paths

    def check(self):
        channels = self.get_channels()

        all_paths = self.get_paths(channels)

        added_paths = sorted(set(all_paths) - set(self.all_paths))
        removed_paths = sorted(set(self.all_paths) - set(all_paths))

        self.all_paths = all_paths

        path_config = {
            item["name"]: item for item in self.api.get("paths/list")["items"]
        }

        if removed_paths:
            for path in removed_paths:
                if path in path_config:
                    LOGGER.info(
                        f"[updater] removing path '{path}': no longer available"
                    )
                    self.api.delete(f"config/paths/delete/{path}")

            path_config = {
                item["name"]: item for item in self.api.get("paths/list")["items"]
            }

        if added_paths:
            LOGGER.info("[updater] new paths available: " + (", ".join(added_paths)))

        paths = all_paths if PATHS == "*" else [x.strip() for x in PATHS.split(",")]

        for path in all_paths:
            if path not in paths:
                continue

            for stream in TRASSIR_STREAMS:
                if path.endswith(f"/{stream}"):
                    channel_id = path[: -(1 + len(stream))]
                    break
            else:
                channel_id, stream = path, "main"

            if path in path_config:
                if path_config[path]["ready"]:
                    continue

                LOGGER.info(f"[updater] removing path '{path}': source is not ready")
                self.api.delete(f"config/paths/delete/{path}")

            source = self.get_video(channels[channel_id], stream)

            LOGGER.info(f"[updater] adding path '{path}': source '{source}'")
            self.api.post(f"config/paths/add/{path}", {"source": source})


if __name__ == "__main__":
    updater = Updater()
    while True:
        updater.check()
        time.sleep(CHECK_INTERVAL)
