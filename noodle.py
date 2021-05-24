"""
Noodle

Create clones of Moodle environments with all resources for archival purposes.
"""

import urllib.parse

import requests

import parameters


class Auth():
    def login(self):
        self.s = requests.Session()

        payload = {
            "username": parameters.username,
            "password": parameters.password,
            "execution": parameters.execution,
            "_eventId": "submit"
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        r = self.s.post(url=parameters.url, data=payload, headers=headers)

        print(r.text)


if __name__ == "__main__":
    a = Auth()
    a.login()
