from __future__ import annotations

from abc import ABC, abstractmethod

from httpx import AsyncClient

from app.models import TrackingSnapshot


class BaseTracker(ABC):
    source_name: str

    def __init__(self, client: AsyncClient) -> None:
        self.client = client

    @abstractmethod
    async def track(self, tracking_number: str) -> TrackingSnapshot:
        raise NotImplementedError
