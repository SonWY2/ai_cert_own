"""Behavioral oracles for the development-only clean/mutated fixture."""

import asyncio
import unittest

from fastapi.testclient import TestClient

import service


class FixtureOracle(unittest.TestCase):
    def test_page_boundary(self):
        self.assertEqual(service.page([11, 22, 33], 1, 1), [22])
        self.assertEqual(service.page([11, 22, 33], 3, 1), [])

    def test_linear_operation_bound(self):
        total, operations = service.count_pairs(list(range(50)))
        self.assertEqual(total, sum(range(50)))
        self.assertLessEqual(operations, 50)

    def test_event_loop_progress(self):
        async def observe():
            events = []

            async def heartbeat():
                events.append("tick")

            await asyncio.gather(service.scheduled(events), heartbeat())
            return events

        self.assertEqual(asyncio.run(observe()), ["tick", "done"])

    def test_cancellation_propagates(self):
        async def cancel():
            task = asyncio.create_task(service.cancellable())
            await asyncio.sleep(0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        asyncio.run(cancel())

    def test_missing_item_is_404(self):
        with TestClient(service.app) as client:
            response = client.get("/items/2")
        self.assertEqual(response.status_code, 404)

    def test_cross_file_normalization(self):
        with TestClient(service.app) as client:
            response = client.get("/items/1")
        self.assertEqual(response.json(), {"name": "sample"})


if __name__ == "__main__":
    unittest.main()
