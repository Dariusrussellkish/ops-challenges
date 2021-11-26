import json
from datetime import datetime
from typing import *

import aioredis
from aioredis import ResponseError
from dateutil import parser
from pydantic import BaseModel, TimeError


class SensorEntry(BaseModel):
    sensor: str
    timestamp: str
    value: float


class SensorStatistic(BaseModel):
    last_measurement: Optional[str]
    count: int
    avg: float


async def setup_redis(address: str, username=None, password=None) -> aioredis.Redis:
    redis = await aioredis.from_url(address, username=username, password=password)
    return redis


def format_key(sensor_id: str, timestamp: str, value: float, convert_to_utc=True, **kwargs) -> Tuple[str, str, int]:
    """ Format a put request into a k,v pair with optional timezone conversion

    :param sensor_id: id of sensor
    :param timestamp: timestamp of measurement
    :param value: value of measurement
    :param convert_to_utc: optional, default True, convert timestamp to UTC
    :return: key, value pair
    """
    try:
        timestamp = parser.parse(timestamp)
    except parser.ParserError:
        raise TimeError
    unix_time = int(timestamp.timestamp() * 1000)
    if convert_to_utc:
        timestamp = timestamp.utcnow()
    ts_str = timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f%z")
    return sensor_id, json.dumps({'timestamp': ts_str, 'unix_time': unix_time, 'value': value}), unix_time


async def put_keys(redis: aioredis.Redis, sensor_entries: List[SensorEntry], **kwargs):
    """Put a list of keys into Redis TimeSeries obj

    :param redis: aioredis Redis connection
    :param sensor_entries: list of SensorEntrys to be put into the db
    :param kwargs: see format_key
    :return:
    """
    res = []
    async with redis.pipeline(transaction=True) as pipe:
        for entry in sensor_entries:
            k, v, ts = format_key(entry.sensor, entry.timestamp, entry.value, **kwargs)
            res.append(pipe.execute_command('TS.ADD', f"{k}:ts", ts, entry.value))
        res = await pipe.execute()

    for r in res:
        assert r

    return res


async def get_statistics(redis: aioredis.Redis, sensor_id: str) -> SensorStatistic:
    """Gets all statistics about a key

    :param redis: aioredis Redis connection
    :param sensor_id: sensor ID/Key to search
    :return: statistics about the sensor
    """
    try:  # try to get the key and return the zero value if it doesn't exist
        latest_ts = await redis.execute_command('TS.GET', f"{sensor_id}:ts")
    except ResponseError as err:
        if "key does not exist" in str(err):
            latest_ts = None
        else:
            raise err
    if latest_ts is None:
        return SensorStatistic(last_measurement=None, count=0, avg=0)

    else:
        latest_ts = float(latest_ts[0]) / 1000  # convert the timestamp from ms to float s which is what datetime wants

    # get the number of measurments for the key, stored as the second value in the return array
    count = (await redis.execute_command('TS.INFO', f"{sensor_id}:ts"))[1]

    # this is a little hacky but it keeps the aggregation on Redis' end
    # we are requesting all measurements and aggregating the avg over a window larger than the lifetime of the sensor
    avg = await redis.execute_command('TS.RANGE', f"{sensor_id}:ts", '-', '+', 'AGGREGATION', 'avg', int(latest_ts) * 10_000)
    # take the millisecond timestamp from the timeseries and convert back to ISO 8601
    return SensorStatistic(last_measurement=datetime.fromtimestamp(latest_ts).strftime("%Y-%m-%dT%H:%M:%S.%f%z"),
                           count=int(count), avg=float(avg[0][1]))


async def delete(redis: aioredis.Redis, sensor_id: str):
    """Delete a key from the db

    :param redis: aioredis Redis connection
    :param sensor_id: sensor ID/Key to be deleted
    :return:
    """
    res = await redis.execute_command('DEL', f"{sensor_id}:ts")
    return res
