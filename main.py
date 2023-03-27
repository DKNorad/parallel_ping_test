import json
import asyncio
from file_handler import FileHandler
from logging_setup import logger
from pyping import ping


async def check_modification(_loop, old, new):
    old_keys = set(old.keys())
    new_keys = set(new.keys())

    only_old = sorted(old_keys - new_keys)
    only_new = sorted(new_keys - old_keys)
    both = sorted(old_keys & new_keys)

    the_same = True

    for key in both:
        old_file = old[key]
        new_file = new[key]
        if old_file["timeout"] != new_file["timeout"]:
            logger.info(f'FILE HANDLER | {key:10} | changed | timeout from {old_file["timeout"]} to {new_file["timeout"]}')
            the_same = False
        if old_file["sleep_period"] != new_file["sleep_period"]:
            logger.info(f'FILE HANDLER | {key:10} | changed | sleep_period from {old_file["sleep_period"]} to {new_file["sleep_period"]}')
            the_same = False
        if old_file["count"] != new_file["count"]:
            logger.info(f'FILE HANDLER | {key:10} | changed | count from {old_file["count"]} to {new_file["count"]}')
            the_same = False
        if old_file["max_rtt"] != new_file["max_rtt"]:
            logger.info(f'FILE HANDLER | {key:10} | changed | max_rtt from {old_file["max_rtt"]} to {new_file["max_rtt"]}')
            the_same = False
        if not the_same:
            await remove(_loop, key, new_file, "update")

    for key in only_old:
        item = old[key]
        logger.info(f'FILE HANDLER | {key:10} | removed | with timeout {item["timeout"]}, '
                    f'sleep_period {item["sleep_period"]}, count {item["count"]} and max_rtt {item["max_rtt"]}')
        the_same = False
        await remove(_loop, key, item, "remove")

    for key in only_new:
        item = new[key]
        logger.info(f'FILE HANDLER | {key:10} | added   | with timeout {item["timeout"]}, '
                    f'sleep_period {item["sleep_period"]}, count {item["count"]} and max_rtt {item["max_rtt"]}')
        await create(_loop, key, item)
        the_same = False

    if the_same:
        logger.info(f'FILE HANDLER | No changes found.')


async def monitor_host_changes(_loop):
    old_details = {}
    while True:
        if FileHandler.is_modified:
            with open("hosts.json", "r") as f:
                host_details_json = json.load(f)
            FileHandler.is_modified = False
            await check_modification(_loop, old_details, host_details_json)
            old_details = host_details_json
        else:
            await asyncio.sleep(1)
            continue


async def remove(_loop, host, details, action):
    for task in asyncio.all_tasks():
        if task.get_name() == host:
            task.cancel()
    if action == "update":
        await create(_loop, host, details)


async def create(_loop, host, details):
    _loop.create_task(ping(host, details["timeout"], details["count"], details["sleep_period"], details["max_rtt"]),
                      name=host)


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(FileHandler("./hosts.json").run(), name="File Handler")
    loop.create_task(monitor_host_changes(loop), name="Task manager")
    loop.run_forever()
