import json
import random
import time
import uuid

from locust import HttpUser, task, between
from random import choice, uniform
import datetime


class WebsiteTestUser(HttpUser):
    wait_time = between(0.1, 3.0)

    def on_start(self):
        self.key_set = [str(uuid.uuid4().hex) for _ in range(4)]

    @task(1)
    def health_check(self):
        self.client.get(f"http://localhost:8080/healthz")

    @task(2)
    def put_some_keys(self):
        entries = []
        for _ in range(random.randint(1, 10)):
            entries.append({
                "sensor": choice(self.key_set),
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z"),
                "value": uniform(0., 10_000.)
            })
            time.sleep(0.01)
        print(json.dumps(entries))
        self.client.post(f"http://localhost:8080/data", json.dumps(entries))

    @task(3)
    def get_stats_on_a_key(self):
        key = choice(self.key_set)
        self.client.get(f"http://localhost:8080/statistics/{key}")

    @task(4)
    def delete_a_key(self):
        key = choice(self.key_set)
        self.client.delete(f"http://localhost:8080/statistics/{key}")