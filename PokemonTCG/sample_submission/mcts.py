"""Monte Carlo Tree Search using the SDK search API.

Uses UCB1 for selection, heuristic evaluation at leaves,
and backpropagates average scores up the tree.
"""
import math
import time
import random
from dataclasses import dataclass, field

from cg.api import (
    Observation, SelectContext, OptionType,
    search_begin, search_step, search_end, search_release,
)
from card_tracker import predict_hidden_cards
from lookahead import evaluate_state
from heuristics import score_option


UCB_C = 1.414
MAX_TIME_S = 2.0
MAX_SIMULATIONS = 50
MIN_SIMULATIONS = 5


@dataclass
class MCTSNode:
    search_id: int
    observation: Observation
    parent: "MCTSNode | None" = None
    action_index: int = -1
    children: list["MCTSNode"] = field(default_factory=list)
    untried_actions: list[int] = field(default_factory=list)
    visit_count: int = 0
    total_value: float = 0.0
    is_terminal: bool = False

    @property
    def avg_value(self) -> float:
        if self.visit_count == 0:
            return 0.0
        return self.total_value / self.visit_count

    def ucb1(self, parent_visits: int) -> float:
        if self.visit_count == 0:
            return float("inf")
        exploitation = self.avg_value
        exploration = UCB_C * math.sqrt(math.log(parent_visits) / self.visit_count)
        return exploitation + exploration


def mcts_search(obs: Observation) -> list[tuple[int, float]] | None:
    """Run MCTS for a MAIN phase decision.

    Returns list of (option_index, visit_count) or None if search fails.
    """
    if obs.select is None or obs.current is None:
        return None
    if obs.select.context != SelectContext.MAIN:
        return None
    if obs.search_begin_input is None:
        return None

    options = obs.select.option
    if len(options) <= 1:
        return None

    try:
        predictions = predict_hidden_cards(obs)
        root_state = search_begin(
            obs,
            predictions["your_deck"],
            predictions["your_prize"],
            predictions["opp_deck"],
            predictions["opp_prize"],
            predictions["opp_hand"],
            predictions["opp_active"],
        )
    except (ValueError, RuntimeError):
        return None

    root = MCTSNode(
        search_id=root_state.searchId,
        observation=root_state.observation,
        untried_actions=list(range(len(options))),
    )

    allocated_ids = {root.search_id}
    start_time = time.time()
    simulations = 0

    try:
        while simulations < MAX_SIMULATIONS:
            if simulations >= MIN_SIMULATIONS and (time.time() - start_time) > MAX_TIME_S:
                break

            leaf = _select(root)

            child = _expand(leaf, allocated_ids)
            if child is None:
                value = _evaluate(leaf)
            else:
                value = _evaluate(child)
                leaf = child

            _backpropagate(leaf, value)
            simulations += 1

    except Exception:
        pass

    max_visits = max((c.visit_count for c in root.children), default=1)

    results = []
    for child in root.children:
        h_score = score_option(options[child.action_index], obs)
        mcts_bonus = (child.visit_count / max(max_visits, 1)) * 200.0
        value_bonus = child.avg_value * 100.0
        results.append((child.action_index, h_score + mcts_bonus + value_bonus))

    for action_idx in root.untried_actions:
        h_score = score_option(options[action_idx], obs)
        results.append((action_idx, h_score))

    _cleanup(root, allocated_ids)

    try:
        search_end()
    except Exception:
        pass

    if not results:
        return None

    return results


def _select(node: MCTSNode) -> MCTSNode:
    """Walk down the tree picking the best UCB1 child."""
    while node.children and not node.untried_actions and not node.is_terminal:
        node = max(node.children, key=lambda c: c.ucb1(node.visit_count))
    return node


def _expand(node: MCTSNode, allocated_ids: set) -> MCTSNode | None:
    """Expand one untried action from the node."""
    if node.is_terminal or not node.untried_actions:
        return None

    action_idx = node.untried_actions.pop(random.randrange(len(node.untried_actions)))

    try:
        next_state = search_step(node.search_id, [action_idx])
    except (ValueError, RuntimeError):
        return None

    is_terminal = False
    if next_state.observation.current and next_state.observation.current.result >= 0:
        is_terminal = True

    child = MCTSNode(
        search_id=next_state.searchId,
        observation=next_state.observation,
        parent=node,
        action_index=action_idx,
        untried_actions=_get_actions(next_state.observation) if not is_terminal else [],
        is_terminal=is_terminal,
    )
    allocated_ids.add(child.search_id)
    node.children.append(child)
    return child


def _evaluate(node: MCTSNode) -> float:
    """Evaluate a leaf node using the heuristic state evaluator."""
    raw = evaluate_state(node.observation)
    return _normalize(raw)


def _normalize(value: float) -> float:
    """Squash evaluation into [0, 1] range."""
    return 1.0 / (1.0 + math.exp(-value / 500.0))


def _backpropagate(node: MCTSNode, value: float):
    """Propagate the evaluation up the tree."""
    while node is not None:
        node.visit_count += 1
        node.total_value += value
        node = node.parent


def _get_actions(obs: Observation) -> list[int]:
    """Get available action indices for an observation."""
    if obs.select is None:
        return []
    return list(range(len(obs.select.option)))


def _cleanup(node: MCTSNode, allocated_ids: set):
    """Release all search IDs except the root."""
    for child in node.children:
        _cleanup(child, allocated_ids)
        if child.search_id in allocated_ids:
            try:
                search_release(child.search_id)
            except Exception:
                pass
            allocated_ids.discard(child.search_id)
    node.children.clear()
