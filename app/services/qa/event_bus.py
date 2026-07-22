"""per-turn 事件总线，解耦生产者和消费者。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class StreamBus:
    """per-turn 事件总线，解耦生产者和消费者。

    生产者通过 emit() 发布事件，多个消费者通过 subscribe() 独立消费。
    新订阅者可选择是否回放历史事件。
    """
    max_history: int = 100
    _queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    _history: list = field(default_factory=list)
    _subscribers: dict[str, asyncio.Queue] = field(default_factory=dict)
    _done: asyncio.Event = field(default_factory=asyncio.Event)

    def emit(self, event: dict) -> None:
        """发布事件到所有订阅者，同时保留历史。"""
        self._history.append(event)
        if len(self._history) > self.max_history:
            self._history.pop(0)
        for q in self._subscribers.values():
            q.put_nowait(event)

    async def subscribe(self, name: str, replay: bool = True) -> AsyncIterator[dict]:
        """订阅事件流，支持历史快照回放。

        遍历事件流，直到总线关闭。使用 asyncio.wait_for 实现非阻塞等待。
        """
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers[name] = q
        if replay:
            for event in self._history:
                yield event
        try:
            while not self._done.is_set():
                try:
                    event = await asyncio.wait_for(q.get(), timeout=1.0)
                    yield event
                except asyncio.TimeoutError:
                    continue
        finally:
            self._subscribers.pop(name, None)

    def close(self) -> None:
        """标记结束，所有订阅者将在下一次超时后停止。"""
        self._done.set()

    @property
    def is_closed(self) -> bool:
        return self._done.is_set()