# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

import asyncio
from typing import Any, Dict, List, Optional, Tuple, Union
from dojo.core.solvers.utils.response import extract_code
from dojo.solvers.mcts.mcts import MCTS, MCTSNode
from dojo.solvers.utils import get_complextiy_level
from dojo.core.solvers.operators.core import async_execute_op_plan_code
from dojo.config_dataclasses.solver.fore_ts import ForeTSSolverConfig
import urllib.request as _rq
import json
import random

class ForeTS(MCTS):
    """Tree search that enquiry a critic before expanding a node."""

    search_name = "ForeTS"

    def __init__(self, cfg: ForeTSSolverConfig, task_info):
        super().__init__(cfg, task_info)
        self.critic_host = cfg.critic_host
        self.critic_port = cfg.critic_port
        self.critic_top_k = cfg.critic_top_k
        self.num_children_to_choose = cfg.num_children_to_choose
        self.task_name = str(task_info.get("name", task_info.get("competition_id", "")))
        self.critic_max_attempts = cfg.critic_max_attempts

    def _expand_leaf_and_backprop(self, path: List[MCTSNode], state: Any, task: Any) -> Tuple[Any, int]:
        """
        Expand a leaf node and backpropagate results.

        Args:
            path: List of nodes from root to leaf
            state: Current state object
            task: Task object for evaluation

        Returns:
            Tuple of (updated state, number of trials performed)
        """
        async def _gather():
            return await asyncio.gather(*child_nodes_evalue)
        
        leaf_node = path[-1]
        num_children_to_create = min(self.cfg.num_children, self.remaining_steps)
        
        # Generate num_children_to_create childrens at the same time
        # If root node, we draft otherwise we improve
        if not leaf_node.parents:
            child_nodes_evalue = [self._draft(leaf_node) for _ in range(num_children_to_create)]
        else:
            child_nodes_evalue = [self._improve(leaf_node) for _ in range(num_children_to_create)]

        # Wait for all child nodes to be created
        child_nodes_evalue = asyncio.run(_gather())

        # Query the critic for value estimates of all child nodes
        child_nodes, critic_values = zip(*child_nodes_evalue)

        # Get the top k child nodes based on critic's evaluation
        top_k_indices = sorted(range(len(critic_values)), key=lambda i: critic_values[i], reverse=True)[:self.critic_top_k]
        top_k_child_nodes = [child_nodes[i] for i in top_k_indices]

        # Finally, randomly select num_children_to_choose from the top k child nodes
        chosen_child_nodes = random.sample(top_k_child_nodes, self.num_children_to_choose)

        # Log the chosen child nodes
        for chosen_node in chosen_child_nodes:
            self.logger.info(f"Chosen Child Node - Code: {chosen_node.code}")

        # Log the unselected child nodes for debugging purposes
        unselected_child_nodes = [child_nodes[i] for i in range(len(child_nodes)) if i not in top_k_indices or child_nodes[i] not in chosen_child_nodes]
        for unselected_node in unselected_child_nodes:
            self.journal.append(unselected_node)
            self.log_journal()

        for i in range(self.num_children_to_choose):
            child_node = chosen_child_nodes[i]
            # Evaluate the code
            self.logger.debug(f"Step {self.state.current_step}: Executing generated code")
            state, eval_result = task.step_task(state, extract_code(child_node.code))
            self.parse_eval_result(node=child_node, eval_result=eval_result)

            # Add the child to the journal
            self.journal.append(child_node)
            self.log_journal()
            self.state.current_step += 1

            # If the child node is not buggy, we backpropagate
            if not child_node.is_buggy:
                self._backprop_step(path=path + [child_node], value_estimate=child_node.metric.value)
                self.set_global_q_values(child_node.metric.value)
            else:
                # Execute debug cycle
                state, debug_path, fixed_metric = self.debug_cycle(state, task, child_node)
                # We now exclude the child node from the path and backprop the fixed metric up the rest of the tree
                if fixed_metric is not None:
                    self._backprop_step(path=path + debug_path, value_estimate=fixed_metric)
                    self.set_global_q_values(fixed_metric)

            # If we have used up all the steps we break
            if self.state.current_step > self.cfg.step_limit:
                self.logger.info(f"Step limit reached: {self.state.current_step} steps")
                break

        return state

    async def _query_critic(self, node: MCTSNode) -> float:
        """
        Query the critic for a value estimate of the given node.

        Args:
            node: The node for which to query the critic
        """
        # Query the critic for a value estimate of the node
        key = id(node)
        for _ in range(self.critic_max_attempts):
            try:
                request = _rq.Request(
                    f"http://{self.critic_host}:{self.critic_port}/score",
                    json.dumps({
                        "task": self._rm_task_name,
                        "code": (node.code or "")[:40000],
                    }).encode(),
                    {"Content-Type": "application/json"},
                )
                with _rq.urlopen(request, timeout=600) as response:
                    response_data = json.loads(response.read().decode())
                    value_estimate = float(response_data["score"])
                return value_estimate
            except Exception as e:
                self.logger.warning(f"Critic query failed for node {key}: {e}. Retrying...")
                await asyncio.sleep(1)  # Wait a bit before retrying
                continue
                
    async def _draft(self, parent: Optional[MCTSNode] = None) -> MCTSNode:
        """
        Generate a new solution from scratch using the draft LLM operator.

        Uses the draft operator to create a new code solution based on the task description.
        The resulting code is packaged into a new Node object with relevant metadata.

        Returns:
            Node: A new node containing the drafted solution
        """
        plan, code, metrics = await async_execute_op_plan_code(
            self.draft_fn,
            self.task_desc,
            self.journal,
            self.state.current_step,
            self.cfg.time_limit_secs - self.state.running_time,
            self.data_preview,
            get_complextiy_level(parent) if self.cfg.use_complexity else None,
            self.root_node,
            max_operator_tries=self.cfg.max_llm_call_retries,
        )
        node = MCTSNode(plan=plan, code=code, parents=[parent], operators_used=["draft"], operators_metrics=[metrics])

        value_estimate = await self._query_critic(node)
        self.logger.info(f"One Draft Node Created - Metrics: {metrics}, Estimated Value: {value_estimate}")

        return node, value_estimate

    async def _improve(self, parent_node: MCTSNode) -> MCTSNode:
        """
        Improve an existing solution using the improve LLM operator.

        Takes a parent node with a working solution and attempts to enhance it
        using the improve operator.

        Args:
            parent_node: The node containing the solution to improve

        Returns:
            Node: A new node containing the improved solution
        """
        plan, code, metrics = await async_execute_op_plan_code(
            self.improve_fn,
            self.task_desc,
            self.journal,
            parent_node,
            self.state.current_step,
            self.cfg.time_limit_secs - self.state.running_time,
            get_complextiy_level(parent_node) if self.cfg.use_complexity else None,
            self.data_preview,
            max_operator_tries=self.cfg.max_llm_call_retries,
        )
        node = MCTSNode(
            plan=plan, code=code, parents=[parent_node], operators_used=["improve"], operators_metrics=[metrics]
        )

        value_estimate = await self._query_critic(node)
        self.logger.info(f"One Improve Node Created - Estimated Value: {value_estimate}, Metrics: {metrics}")

        return node, value_estimate