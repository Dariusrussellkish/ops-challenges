from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseSettings, TimeError
from aioredis import ConnectionError
from crud import *
from typing import Optional, Union, List

# In the path ops is where we could implement OAuth2 with dependency injection
# we could use JWTs from FastAPI or just store tokens in our redis db with expiration times

# Scalability for the service is easy, as it's stateless and can naively scale horizontally
# but the tricky bit would be how to scale the db. We're using redis timeseries with a single
# node, as that's likely sufficient (for this). We could switch to Prometheus/InfluxDB if better cluster supp. is needed
# or if we were stuck with Redis then we could use consistent hashing like Cassandra to load balance
# sensor_ids across disjoint Redis instances naively since redis clusters aren't supported by aioredis
app = FastAPI()


# Here is where we could configure logging and monitoring options, break into its own file as needed
# for example we could use opentelemetry and datadog for monitoring/profiling
class Config(BaseSettings):
    redis_host = "redis"
    redis_port = 6379

    class Config:
        env_file = ".env"


config: Optional[Config] = Config()


async def get_redis_connection():
    redis = await setup_redis(f"redis://{config.redis_host}:{config.redis_port}")
    try:
        yield redis
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"{e}")
    finally:
        await redis.close()


@app.post("/data")
async def put_sensor_entries(sensor_entries: Union[SensorEntry, List[SensorEntry]],
                             redis=Depends(get_redis_connection)):
    if isinstance(sensor_entries, SensorEntry):
        sensor_entries = [sensor_entries]

    try:
        await put_keys(redis, sensor_entries)
    except TimeError:
        raise HTTPException(status_code=400, detail="Could not understand time format")


@app.get("/statistics/{sensor_id}")
async def get_sensor_statistics(sensor_id: str, redis=Depends(get_redis_connection)):
    res = await get_statistics(redis, sensor_id)
    return res


@app.get("/healthz", status_code=204)
async def health_check(redis=Depends(get_redis_connection)):
    res = await redis.ping()
    if not res:
        raise HTTPException(status_code=503)


@app.delete("/statistics/{sensor_id}")
async def delete_sensor_data(sensor_id: str, redis=Depends(get_redis_connection)):
    await delete(redis, sensor_id)
