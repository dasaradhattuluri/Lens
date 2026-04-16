"""Unit tests for lens.pipeline."""

from lens.pipeline import Dag


class TestDag:
    def test_empty_dag(self):
        dag = Dag()
        assert dag.execution_order() == []

    def test_linear_order(self):
        dag = Dag()
        dag.add_task("a", lambda ctx: None)
        dag.add_task("b", lambda ctx: None, depends_on=["a"])
        dag.add_task("c", lambda ctx: None, depends_on=["b"])
        order = dag.execution_order()
        assert order == ["a", "b", "c"]

    def test_diamond_order(self):
        dag = Dag()
        dag.add_task("root", lambda ctx: None)
        dag.add_task("left", lambda ctx: None, depends_on=["root"])
        dag.add_task("right", lambda ctx: None, depends_on=["root"])
        dag.add_task("join", lambda ctx: None, depends_on=["left", "right"])
        order = dag.execution_order()
        assert order.index("root") < order.index("left")
        assert order.index("root") < order.index("right")
        assert order.index("left") < order.index("join")
        assert order.index("right") < order.index("join")

    def test_cycle_detection(self):
        dag = Dag()
        dag.add_task("x", lambda ctx: None, depends_on=["y"])
        dag.add_task("y", lambda ctx: None, depends_on=["x"])
        try:
            dag.execution_order()
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "Cycle" in str(e)

    def test_run_populates_context(self):
        dag = Dag()
        dag.add_task("step1", lambda ctx: ctx.update({"val": 1}))
        dag.add_task("step2", lambda ctx: ctx.update({"val": ctx["val"] + 1}), depends_on=["step1"])
        result = dag.run()
        assert result["val"] == 2

    def test_task_names(self):
        dag = Dag()
        dag.add_task("alpha", lambda ctx: None)
        dag.add_task("beta", lambda ctx: None)
        assert set(dag.task_names) == {"alpha", "beta"}
