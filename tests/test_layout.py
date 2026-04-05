"""Tests for dify_workflow.layout — auto-layout engine."""

import pytest

from dify_workflow.editor import add_edge, add_node
from dify_workflow.layout import (
    NODE_HEIGHT,
    NODE_WIDTH,
    START_X,
    START_Y,
    _assign_layers,
    _build_branch_order,
    _layout_dag,
    _layout_linear,
    _minimize_crossings,
    _topo_order,
    auto_layout,
)
from dify_workflow.models import (
    DifyDSL,
    Edge,
    Node,
    NodeData,
    NodeType,
    Position,
)


@pytest.fixture
def empty_dsl():
    return DifyDSL()


@pytest.fixture
def linear_dsl():
    """A → B → C sequential workflow."""
    dsl = DifyDSL()
    add_node(dsl, NodeType.START, node_id="a")
    add_node(dsl, NodeType.LLM, node_id="b")
    add_node(dsl, NodeType.END, node_id="c")
    add_edge(dsl, "a", "b")
    add_edge(dsl, "b", "c")
    return dsl


@pytest.fixture
def branching_dsl():
    """A → B, A → C, B → D, C → D (diamond pattern)."""
    dsl = DifyDSL()
    add_node(dsl, NodeType.START, node_id="a")
    add_node(dsl, NodeType.IF_ELSE, node_id="b")
    add_node(dsl, NodeType.LLM, node_id="c")
    add_node(dsl, NodeType.END, node_id="d")
    add_edge(dsl, "a", "b")
    add_edge(dsl, "b", "c", source_handle="true")
    add_edge(dsl, "b", "d", source_handle="false")
    add_edge(dsl, "c", "d")
    return dsl


@pytest.fixture
def wide_dsl():
    """A → B, A → C, A → D (fan-out)."""
    dsl = DifyDSL()
    add_node(dsl, NodeType.START, node_id="a")
    add_node(dsl, NodeType.LLM, node_id="b")
    add_node(dsl, NodeType.CODE, node_id="c")
    add_node(dsl, NodeType.END, node_id="d")
    add_edge(dsl, "a", "b")
    add_edge(dsl, "a", "c")
    add_edge(dsl, "a", "d")
    return dsl


# ── auto_layout (public API) ──────────────────────────────────────────

class TestAutoLayout:
    def test_empty_dsl(self, empty_dsl):
        result = auto_layout(empty_dsl)
        assert result == {}

    def test_single_node(self, empty_dsl):
        add_node(empty_dsl, NodeType.START, node_id="s")
        result = auto_layout(empty_dsl, strategy="hierarchical")
        assert "s" in result
        x, y = result["s"]
        assert x == START_X

    def test_linear_layout_strategy(self, linear_dsl):
        result = auto_layout(linear_dsl, strategy="linear")
        assert len(result) == 3
        # All nodes should be at the same y
        ys = {y for _, y in result.values()}
        assert len(ys) == 1

    def test_hierarchical_layout_strategy(self, linear_dsl):
        result = auto_layout(linear_dsl, strategy="hierarchical")
        assert len(result) == 3
        # x should increase left to right
        xs = [result["a"][0], result["b"][0], result["c"][0]]
        assert xs[0] < xs[1] < xs[2]

    def test_vertical_layout_strategy(self, linear_dsl):
        result = auto_layout(linear_dsl, strategy="vertical")
        assert len(result) == 3
        # y should increase top to bottom
        ys = [result["a"][1], result["b"][1], result["c"][1]]
        assert ys[0] < ys[1] < ys[2]

    def test_compact_layout_strategy(self, linear_dsl):
        result_compact = auto_layout(linear_dsl, strategy="compact")
        # Re-create for hierarchical comparison
        linear2 = DifyDSL()
        add_node(linear2, NodeType.START, node_id="a")
        add_node(linear2, NodeType.LLM, node_id="b")
        add_node(linear2, NodeType.END, node_id="c")
        add_edge(linear2, "a", "b")
        add_edge(linear2, "b", "c")
        result_hier = auto_layout(linear2, strategy="hierarchical")
        # Compact should have smaller x spread
        spread_compact = result_compact["c"][0] - result_compact["a"][0]
        spread_hier = result_hier["c"][0] - result_hier["a"][0]
        assert spread_compact < spread_hier

    def test_positions_applied_to_dsl(self, linear_dsl):
        auto_layout(linear_dsl, strategy="hierarchical")
        for node in linear_dsl.workflow.graph.nodes:
            assert node.position.x >= START_X
            assert node.positionAbsolute is not None
            assert node.position.x == node.positionAbsolute.x
            assert node.position.y == node.positionAbsolute.y

    def test_branching_separates_vertically(self, branching_dsl):
        result = auto_layout(branching_dsl, strategy="hierarchical")
        # c and d should be at different y if they're in different layers
        # At minimum, b and c should be at different positions
        assert result["a"] != result["b"]
        assert result["b"] != result["c"]


# ── _topo_order ─────────────────────────────────────────────────

class TestTopoOrder:
    def test_simple_chain(self):
        ids = ["a", "b", "c"]
        adj = {"a": ["b"], "b": ["c"]}
        rev = {"b": ["a"], "c": ["b"]}
        order = _topo_order(ids, adj, rev)
        assert order.index("a") < order.index("b") < order.index("c")

    def test_fan_out(self):
        ids = ["a", "b", "c"]
        adj = {"a": ["b", "c"]}
        rev = {"b": ["a"], "c": ["a"]}
        order = _topo_order(ids, adj, rev)
        assert order[0] == "a"

    def test_cycle_still_returns_all(self):
        ids = ["a", "b", "c"]
        adj = {"a": ["b"], "b": ["c"], "c": ["a"]}
        rev = {"a": ["c"], "b": ["a"], "c": ["b"]}
        order = _topo_order(ids, adj, rev)
        assert set(order) == {"a", "b", "c"}

    def test_disconnected_nodes(self):
        ids = ["a", "b", "c"]
        adj = {"a": ["b"]}
        rev = {"b": ["a"]}
        order = _topo_order(ids, adj, rev)
        assert set(order) == {"a", "b", "c"}


# ── _assign_layers ────────────────────────────────────────────

class TestAssignLayers:
    def test_simple_chain(self):
        ids = ["a", "b", "c"]
        adj = {"a": ["b"], "b": ["c"]}
        rev = {"b": ["a"], "c": ["b"]}
        layers = _assign_layers(ids, adj, rev)
        assert layers["a"] == 0
        assert layers["b"] == 1
        assert layers["c"] == 2

    def test_diamond(self):
        ids = ["a", "b", "c", "d"]
        adj = {"a": ["b", "c"], "b": ["d"], "c": ["d"]}
        rev = {"b": ["a"], "c": ["a"], "d": ["b", "c"]}
        layers = _assign_layers(ids, adj, rev)
        assert layers["a"] == 0
        assert layers["b"] == 1
        assert layers["c"] == 1
        assert layers["d"] == 2

    def test_fan_out(self):
        ids = ["a", "b", "c", "d"]
        adj = {"a": ["b", "c", "d"]}
        rev = {"b": ["a"], "c": ["a"], "d": ["a"]}
        layers = _assign_layers(ids, adj, rev)
        assert layers["a"] == 0
        assert layers["b"] == 1
        assert layers["c"] == 1
        assert layers["d"] == 1

    def test_isolated_node(self):
        ids = ["a", "b"]
        adj = {}
        rev = {}
        layers = _assign_layers(ids, adj, rev)
        # Both are sources
        assert layers["a"] == 0
        assert layers["b"] == 0

    def test_longer_path_wins(self):
        """a→b→d, a→c→d→e. e should be layer 3, not 2."""
        ids = ["a", "b", "c", "d", "e"]
        adj = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": ["e"]}
        rev = {"b": ["a"], "c": ["a"], "d": ["b", "c"], "e": ["d"]}
        layers = _assign_layers(ids, adj, rev)
        assert layers["a"] == 0
        assert layers["d"] == 2
        assert layers["e"] == 3


# ── _minimize_crossings ──────────────────────────────────────

class TestMinimizeCrossings:
    def test_simple_no_crossings(self):
        layers = [["a"], ["b", "c"], ["d"]]
        adj = {"a": ["b", "c"], "b": ["d"], "c": ["d"]}
        rev = {"b": ["a"], "c": ["a"], "d": ["b", "c"]}
        result = _minimize_crossings(layers, adj, rev, {})
        assert len(result) == 3
        assert set(result[1]) == {"b", "c"}

    def test_single_layer_unchanged(self):
        layers = [["a", "b", "c"]]
        result = _minimize_crossings(layers, {}, {}, {})
        assert result == [["a", "b", "c"]]


# ── _layout_linear ────────────────────────────────────────────

class TestLayoutLinear:
    def test_simple_chain(self):
        ids = ["a", "b", "c"]
        adj = {"a": ["b"], "b": ["c"]}
        rev = {"b": ["a"], "c": ["b"]}
        pos = _layout_linear(ids, adj, rev, {})
        # x should increase
        assert pos["a"][0] < pos["b"][0] < pos["c"][0]
        # all y should be same
        assert pos["a"][1] == pos["b"][1] == pos["c"][1]

    def test_spacing(self):
        ids = ["a", "b"]
        adj = {"a": ["b"]}
        rev = {"b": ["a"]}
        pos = _layout_linear(ids, adj, rev, {})
        expected_gap = NODE_WIDTH + 100  # linear layer_gap
        assert abs(pos["b"][0] - pos["a"][0] - expected_gap) < 0.01


# ── _layout_dag ───────────────────────────────────────────────

class TestLayoutDag:
    def test_horizontal_direction(self):
        ids = ["a", "b", "c"]
        adj = {"a": ["b"], "b": ["c"]}
        rev = {"b": ["a"], "c": ["b"]}
        pos = _layout_dag(ids, adj, rev, {},
                          direction="horizontal",
                          spacing={"layer_gap": 100, "node_gap": 80})
        # x increases across layers
        assert pos["a"][0] < pos["b"][0] < pos["c"][0]

    def test_vertical_direction(self):
        ids = ["a", "b", "c"]
        adj = {"a": ["b"], "b": ["c"]}
        rev = {"b": ["a"], "c": ["b"]}
        pos = _layout_dag(ids, adj, rev, {},
                          direction="vertical",
                          spacing={"layer_gap": 100, "node_gap": 100})
        # y increases across layers
        assert pos["a"][1] < pos["b"][1] < pos["c"][1]

    def test_fan_out_spreads_vertically(self):
        ids = ["a", "b", "c"]
        adj = {"a": ["b", "c"]}
        rev = {"b": ["a"], "c": ["a"]}
        pos = _layout_dag(ids, adj, rev, {},
                          direction="horizontal",
                          spacing={"layer_gap": 100, "node_gap": 80})
        # b and c should be at different y positions
        assert pos["b"][1] != pos["c"][1]
        # both at same x (same layer)
        assert pos["b"][0] == pos["c"][0]

    def test_diamond_merge(self):
        ids = ["a", "b", "c", "d"]
        adj = {"a": ["b", "c"], "b": ["d"], "c": ["d"]}
        rev = {"b": ["a"], "c": ["a"], "d": ["b", "c"]}
        pos = _layout_dag(ids, adj, rev, {},
                          direction="horizontal",
                          spacing={"layer_gap": 100, "node_gap": 80})
        # a at layer 0, b/c at layer 1, d at layer 2
        assert pos["a"][0] < pos["b"][0]
        assert pos["b"][0] == pos["c"][0]
        assert pos["b"][0] < pos["d"][0]

    def test_compact_smaller_than_normal(self):
        ids = ["a", "b", "c"]
        adj = {"a": ["b"], "b": ["c"]}
        rev = {"b": ["a"], "c": ["b"]}
        pos_normal = _layout_dag(ids, adj, rev, {},
                                 direction="horizontal",
                                 spacing={"layer_gap": 100, "node_gap": 80})
        pos_compact = _layout_dag(ids, adj, rev, {},
                                  direction="horizontal",
                                  spacing={"layer_gap": 60, "node_gap": 40})
        spread_normal = pos_normal["c"][0] - pos_normal["a"][0]
        spread_compact = pos_compact["c"][0] - pos_compact["a"][0]
        assert spread_compact < spread_normal


# ── _build_branch_order ───────────────────────────────────────

class TestBuildBranchOrder:
    def test_if_else_branch_order(self):
        dsl = DifyDSL()
        add_node(dsl, NodeType.IF_ELSE, node_id="if1")
        add_node(dsl, NodeType.LLM, node_id="t1")
        add_node(dsl, NodeType.END, node_id="t2")
        add_edge(dsl, "if1", "t1", source_handle="true")
        add_edge(dsl, "if1", "t2", source_handle="false")
        order = _build_branch_order(dsl.workflow.graph.nodes, dsl.workflow.graph.edges)
        assert "if1" in order
        assert order["if1"]["t1"] < order["if1"]["t2"]

    def test_regular_node_preserves_edge_order(self):
        dsl = DifyDSL()
        add_node(dsl, NodeType.START, node_id="s")
        add_node(dsl, NodeType.LLM, node_id="a")
        add_node(dsl, NodeType.CODE, node_id="b")
        add_edge(dsl, "s", "a")
        add_edge(dsl, "s", "b")
        order = _build_branch_order(dsl.workflow.graph.nodes, dsl.workflow.graph.edges)
        assert "s" in order
        assert order["s"]["a"] == 0
        assert order["s"]["b"] == 1


# ── Integration tests ────────────────────────────────────────

class TestLayoutIntegration:
    def test_no_overlap(self, branching_dsl):
        """No two nodes should overlap after layout."""
        result = auto_layout(branching_dsl, strategy="hierarchical")
        items = list(result.items())
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                id1, (x1, y1) = items[i]
                id2, (x2, y2) = items[j]
                # Check bounding boxes don't overlap
                overlap_x = x1 < x2 + NODE_WIDTH and x2 < x1 + NODE_WIDTH
                overlap_y = y1 < y2 + NODE_HEIGHT and y2 < y1 + NODE_HEIGHT
                assert not (overlap_x and overlap_y), f"Nodes {id1} and {id2} overlap"

    def test_all_strategies_no_overlap(self, wide_dsl):
        """All 5 strategies should produce non-overlapping layouts."""
        for strategy in ["linear", "hierarchical", "vertical", "compact", "tree"]:
            dsl = DifyDSL()
            add_node(dsl, NodeType.START, node_id="a")
            add_node(dsl, NodeType.LLM, node_id="b")
            add_node(dsl, NodeType.CODE, node_id="c")
            add_node(dsl, NodeType.END, node_id="d")
            add_edge(dsl, "a", "b")
            add_edge(dsl, "a", "c")
            add_edge(dsl, "a", "d")
            result = auto_layout(dsl, strategy=strategy)
            items = list(result.items())
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    id1, (x1, y1) = items[i]
                    id2, (x2, y2) = items[j]
                    overlap_x = x1 < x2 + NODE_WIDTH and x2 < x1 + NODE_WIDTH
                    overlap_y = y1 < y2 + NODE_HEIGHT and y2 < y1 + NODE_HEIGHT
                    assert not (overlap_x and overlap_y), \
                        f"Strategy {strategy}: nodes {id1} and {id2} overlap"

    def test_disconnected_nodes_still_laid_out(self, empty_dsl):
        """Nodes with no edges should still get valid positions."""
        add_node(empty_dsl, NodeType.START, node_id="a")
        add_node(empty_dsl, NodeType.END, node_id="b")
        result = auto_layout(empty_dsl, strategy="hierarchical")
        assert len(result) == 2
        assert "a" in result
        assert "b" in result

    def test_complex_workflow(self, empty_dsl):
        """Test a more complex workflow with multiple branches and merges."""
        dsl = empty_dsl
        add_node(dsl, NodeType.START, node_id="start")
        add_node(dsl, NodeType.IF_ELSE, node_id="if1")
        add_node(dsl, NodeType.LLM, node_id="llm1")
        add_node(dsl, NodeType.LLM, node_id="llm2")
        add_node(dsl, NodeType.CODE, node_id="code1")
        add_node(dsl, NodeType.END, node_id="end")

        add_edge(dsl, "start", "if1")
        add_edge(dsl, "if1", "llm1", source_handle="true")
        add_edge(dsl, "if1", "llm2", source_handle="false")
        add_edge(dsl, "llm1", "code1")
        add_edge(dsl, "llm2", "code1")
        add_edge(dsl, "code1", "end")

        result = auto_layout(dsl, strategy="hierarchical")
        assert len(result) == 6

        # start should be leftmost
        assert result["start"][0] == min(x for x, _ in result.values())
        # end should be rightmost
        assert result["end"][0] == max(x for x, _ in result.values())
        # llm1 and llm2 should be at same x (same layer) but different y
        assert result["llm1"][0] == result["llm2"][0]
        assert result["llm1"][1] != result["llm2"][1]


# ── Tree layout ───────────────────────────────────────────────

class TestTreeLayout:
    def test_linear_chain(self, linear_dsl):
        """Linear chain: x increases, all same y band."""
        result = auto_layout(linear_dsl, strategy="tree")
        assert len(result) == 3
        assert result["a"][0] < result["b"][0] < result["c"][0]

    def test_branches_grouped_vertically(self):
        """Two branches from a router should occupy separate y bands."""
        dsl = DifyDSL()
        add_node(dsl, NodeType.START, node_id="s")
        add_node(dsl, NodeType.IF_ELSE, node_id="if1")
        add_node(dsl, NodeType.LLM, node_id="branch_a")
        add_node(dsl, NodeType.END, node_id="end_a")
        add_node(dsl, NodeType.CODE, node_id="branch_b")
        add_node(dsl, NodeType.END, node_id="end_b")
        add_edge(dsl, "s", "if1")
        add_edge(dsl, "if1", "branch_a", source_handle="true")
        add_edge(dsl, "branch_a", "end_a")
        add_edge(dsl, "if1", "branch_b", source_handle="false")
        add_edge(dsl, "branch_b", "end_b")

        result = auto_layout(dsl, strategy="tree")
        # branch_a subtree should be fully above or below branch_b subtree
        a_ys = {result["branch_a"][1], result["end_a"][1]}
        b_ys = {result["branch_b"][1], result["end_b"][1]}
        assert max(a_ys) < min(b_ys) or max(b_ys) < min(a_ys)

    def test_four_way_branch_all_separated(self):
        """4 branches from a classifier should have no y overlap."""
        dsl = DifyDSL()
        add_node(dsl, NodeType.START, node_id="s")
        add_node(dsl, NodeType.QUESTION_CLASSIFIER, node_id="qc")
        branches = ["b1", "b2", "b3", "b4"]
        for b in branches:
            add_node(dsl, NodeType.END, node_id=b)
            add_edge(dsl, "qc", b, source_handle=b)
        add_edge(dsl, "s", "qc")

        result = auto_layout(dsl, strategy="tree")
        ys = [result[b][1] for b in branches]
        # All branch endpoints at different y values, sorted
        assert len(set(ys)) == 4
        assert ys == sorted(ys)

    def test_tree_no_overlap(self):
        """Complex tree should have no overlapping nodes."""
        dsl = DifyDSL()
        add_node(dsl, NodeType.START, node_id="start")
        add_node(dsl, NodeType.IF_ELSE, node_id="if1")
        add_node(dsl, NodeType.LLM, node_id="llm1")
        add_node(dsl, NodeType.LLM, node_id="llm2")
        add_node(dsl, NodeType.CODE, node_id="code1")
        add_node(dsl, NodeType.END, node_id="end1")
        add_node(dsl, NodeType.END, node_id="end2")
        add_edge(dsl, "start", "if1")
        add_edge(dsl, "if1", "llm1", source_handle="true")
        add_edge(dsl, "if1", "llm2", source_handle="false")
        add_edge(dsl, "llm1", "code1")
        add_edge(dsl, "code1", "end1")
        add_edge(dsl, "llm2", "end2")

        result = auto_layout(dsl, strategy="tree")
        items = list(result.items())
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                _, (x1, y1) = items[i]
                _, (x2, y2) = items[j]
                overlap_x = x1 < x2 + NODE_WIDTH and x2 < x1 + NODE_WIDTH
                overlap_y = y1 < y2 + NODE_HEIGHT and y2 < y1 + NODE_HEIGHT
                assert not (overlap_x and overlap_y)

    def test_positions_applied_to_dsl(self, linear_dsl):
        auto_layout(linear_dsl, strategy="tree")
        for node in linear_dsl.workflow.graph.nodes:
            assert node.position is not None
            assert node.positionAbsolute is not None
            assert node.position.x == node.positionAbsolute.x
