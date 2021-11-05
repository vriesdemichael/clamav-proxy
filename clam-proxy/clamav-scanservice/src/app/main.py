import logging
import os
import shlex
import uuid
from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE
from pathlib import Path

from aiofile import async_open
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.background import BackgroundTasks
from urllib.parse import urljoin

import aioredis
import aiohttp

# https://files.pythonhosted.org/packages/59/2f/2c24c065dd6002afd5e1814f872100f33dfd65dd05e826ab83efe1661b6a/pulp-file-1.10.1.tar.gz
# packages/59/2f/2c24c065dd6002afd5e1814f872100f33dfd65dd05e826ab83efe1661b6a/pulp-file-1.10.1.tar.gz
# TODO GET THIS FROM PROXY HEADER
prefix = "https://files.pythonhosted.org/"

logging.basicConfig(level=logging.INFO)
debug = True
log = logging.getLogger("main")
log.setLevel(logging.INFO)

scan_cmd = "clamdscan -c /opt/src/clamd.remote.conf --fdpass --stream "
CONTAINS_VIRUS = "contains virus"
CONTAINS_NO_VIRUS = "contains no virus"

app = FastAPI()


async def yield_chunks_from_url(url, chunk_size=1024):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            async for chunk in resp.content.iter_chunked(chunk_size):
                if chunk:
                    yield chunk


async def yield_chunks_from_file(filepath: Path, chunk_size=1024):
    async with async_open(filepath, "rb") as afp:
        async for chunk in afp.iter_chunked(chunk_size):
            yield chunk


@app.get("/{relative_url:path}", response_class=FileResponse, )
async def scan(relative_url: str, background_tasks: BackgroundTasks) -> FileResponse:
    real_url = urljoin(prefix, relative_url)
    log.info(f"Got relative url {relative_url}, resolving to {real_url}")

    redis = aioredis.Redis(host="redis")
    redis_key = f"{relative_url}|{scan_cmd}"
    stored_scan_result = await redis.get(redis_key)
    log.info(f"Stored scan result: {stored_scan_result}")

    if not stored_scan_result or True:
        log.info("No stored scan result, downloading now")

        tmpfile = Path(f"/tmp/{uuid.uuid4().hex}")
        log.info(f"Storing download in {tmpfile}")

        async with async_open(tmpfile, "wb") as afp:
            async with aiohttp.ClientSession() as session:
                async with session.get(real_url) as resp:
                    async for chunk in resp.content.iter_chunked(1024):
                        if chunk:
                            await afp.write(chunk)

        log.info("Scanning downloaded file")
        complete_scan_cmd = shlex.split(scan_cmd + str(tmpfile.absolute()))
        log.info(f"{complete_scan_cmd=}")
        proc = await create_subprocess_exec(*complete_scan_cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = await proc.communicate()
        if stdout and debug:
            log.info(f'[stdout]\n{stdout.decode()}')
        if stderr:
            log.error(f'[stderr]\n{stderr.decode()}')
        log.info(f'[{complete_scan_cmd!r} exited with {proc.returncode}]')

        log.info("Storing scan result in redis")
        if proc.returncode != 0:
            await redis.set(redis_key, CONTAINS_VIRUS)
            raise HTTPException(status_code=409, detail="This resource contains a virus!")
        else:
            await redis.set(redis_key, CONTAINS_NO_VIRUS, ex=60 * 60 * 24)  # 24 hour expiry

        background_tasks.add_task(os.unlink, str(tmpfile.absolute()))  # delete the temp file afterwards
        return FileResponse(str(tmpfile.absolute()))
    elif stored_scan_result.decode("utf-8") == CONTAINS_VIRUS:
        log.info("File contained virus stopping request")
        raise HTTPException(status_code=409, detail="This resource contains a virus!")
    elif stored_scan_result.decode("utf-8") == CONTAINS_NO_VIRUS:
        log.info("File did not contain virus, streaming result")
        StreamingResponse(yield_chunks_from_url(real_url))
    else:

        raise NotImplemented()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
