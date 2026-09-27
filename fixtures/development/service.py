"""Development-only FastAPI/asyncio fixture; never a hidden final case."""

import asyncio
from fastapi import FastAPI, HTTPException

from helper import normalize

app = FastAPI()


def page(items: list[int], offset: int, count: int) -> list[int]:
    return items[offset:offset + count]


def count_pairs(items: list[int]) -> tuple[int, int]:
    operations = 0
    total = 0
    for item in items:
        total += item
        operations += 1
    return total, operations


async def scheduled(events: list[str]) -> None:
    await asyncio.sleep(0)
    events.append("done")


async def cancellable() -> None:
    await asyncio.sleep(60)


@app.get("/items/{item_id}")
async def item(item_id: int):
    if item_id != 1:
        raise HTTPException(status_code=404, detail="item not found")
    return {"name": normalize(" sample ")}
