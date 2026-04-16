"""DAG-based pipeline runner for Lens.

Each processing step is registered as a *task* with explicit dependency
declarations.  The runner resolves execution order via topological sort
and can (in future) parallelise independent tasks.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Task:
    """A single unit of work in the pipeline."""

    name: str
    fn: Callable[..., Any]
    depends_on: list[str] = field(default_factory=list)


class Dag:
    """Directed acyclic graph of pipeline tasks."""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    def add_task(
        self,
        name: str,
        fn: Callable[..., Any],
        depends_on: list[str] | None = None,
    ) -> None:
        self._tasks[name] = Task(name=name, fn=fn, depends_on=depends_on or [])

    def execution_order(self) -> list[str]:
        """Return a topologically-sorted list of task names."""
        in_degree: dict[str, int] = defaultdict(int)
        adj: dict[str, list[str]] = defaultdict(list)

        for name, task in self._tasks.items():
            in_degree.setdefault(name, 0)
            for dep in task.depends_on:
                adj[dep].append(name)
                in_degree[name] += 1

        queue: deque[str] = deque(
            n for n, d in in_degree.items() if d == 0
        )
        order: list[str] = []
        while queue:
            current = queue.popleft()
            order.append(current)
            for child in adj[current]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if len(order) != len(self._tasks):
            executed = set(order)
            remaining = set(self._tasks) - executed
            raise RuntimeError(
                f"Cycle detected in pipeline DAG; unresolvable tasks: {remaining}"
            )
        return order

    def run(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute all tasks in dependency order.

        Each task receives *context* (a shared dict) and may mutate it.
        Returns the final context.
        """
        if context is None:
            context = {}
        for name in self.execution_order():
            task = self._tasks[name]
            task.fn(context)
        return context

    @property
    def task_names(self) -> list[str]:
        return list(self._tasks.keys())
