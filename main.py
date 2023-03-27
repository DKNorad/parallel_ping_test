import json
import asyncio
from file_handler import FileHandler
from pyping import ping

with open("hosts.json", "r") as f:
    host_details_json = json.load(f)


async def create():
    tasks = []
    for host, details in host_details_json.items():
        tasks.append(loop.create_task(ping(host, details["timeout"], details["count"], details["sleep_period"], details["max_rtt"]), name=host))
    return tasks

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    asyncio.run(create())
    asyncio.run(FileHandler("./hosts.json").run())
    loop.run_forever()
