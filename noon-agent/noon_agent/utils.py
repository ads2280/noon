"""Assorted utilities that don't belong anywhere else."""

from collections.abc import Iterable
from typing import Any, Generator


def chunk_messages(
    messages: Iterable[Any], chunk_size: int = 4
) -> Generator[list[Any], None, None]:
    """Yield fixed-size chunks from an iterable."""

    batch: list[Any] = []
    for item in messages:
        batch.append(item)
        if len(batch) == chunk_size:
            yield batch
            batch = []
    if batch:
        yield batch
