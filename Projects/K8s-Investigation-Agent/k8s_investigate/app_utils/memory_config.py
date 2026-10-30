# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Agent Platform Memory Bank configuration for the Kubernetes Investigation Agent.

Defines the managed and custom memory topics that Agent Platform Memory Bank
extracts and persists across Kubernetes troubleshooting sessions.
"""

from __future__ import annotations

import os
from typing import Any

try:
    from agentplatform._genai.types import (
        AgentEngineConfig,
        ManagedTopicEnum,
        ReasoningEngineContextSpec,
    )
    from agentplatform._genai.types import (
        MemoryBankCustomizationConfig as CustomizationConfig,
    )
    from agentplatform._genai.types import (
        MemoryBankCustomizationConfigMemoryTopic as MemoryTopic,
    )
    from agentplatform._genai.types import (
        MemoryBankCustomizationConfigMemoryTopicCustomMemoryTopic as CustomMemoryTopic,
    )
    from agentplatform._genai.types import (
        MemoryBankCustomizationConfigMemoryTopicManagedMemoryTopic as ManagedMemoryTopic,
    )
    from agentplatform._genai.types import (
        ReasoningEngineContextSpecMemoryBankConfig as MemoryBankConfig,
    )
except ImportError:
    from vertexai._genai.types import (
        AgentEngineConfig,
        ManagedTopicEnum,
        ReasoningEngineContextSpec,
    )
    from vertexai._genai.types import (
        MemoryBankCustomizationConfig as CustomizationConfig,
    )
    from vertexai._genai.types import (
        MemoryBankCustomizationConfigMemoryTopic as MemoryTopic,
    )
    from vertexai._genai.types import (
        MemoryBankCustomizationConfigMemoryTopicCustomMemoryTopic as CustomMemoryTopic,
    )
    from vertexai._genai.types import (
        MemoryBankCustomizationConfigMemoryTopicManagedMemoryTopic as ManagedMemoryTopic,
    )
    from vertexai._genai.types import (
        ReasoningEngineContextSpecMemoryBankConfig as MemoryBankConfig,
    )


KUBERNETES_INCIDENT_FINDINGS_TOPIC = CustomMemoryTopic(
    label="kubernetes_incident_findings",
    description=(
        "Findings from Kubernetes cluster investigations, including affected pod "
        "names, namespaces, deployments, nodes, container images, failure "
        "categories (such as OOMKilled, CrashLoopBackOff, ImagePullBackOff, "
        "ConfigError, ProbeFailure), causal root causes, log or event evidence, "
        "and blast radius."
    ),
)

KUBERNETES_REMEDIATIONS_TOPIC = CustomMemoryTopic(
    label="kubernetes_remediations_and_rollouts",
    description=(
        "Remediation actions, kubectl commands, configuration changes, resource "
        "limit adjustments, or deployment rollbacks recommended or applied to "
        "resolve Kubernetes cluster incidents."
    ),
)

memory_bank_config = MemoryBankConfig(
    customization_configs=[
        CustomizationConfig(
            memory_topics=[
                MemoryTopic(
                    managed_memory_topic=ManagedMemoryTopic(
                        managed_topic_enum=ManagedTopicEnum.KEY_CONVERSATION_DETAILS,
                    ),
                ),
                MemoryTopic(
                    managed_memory_topic=ManagedMemoryTopic(
                        managed_topic_enum=ManagedTopicEnum.EXPLICIT_INSTRUCTIONS,
                    ),
                ),
                MemoryTopic(
                    managed_memory_topic=ManagedMemoryTopic(
                        managed_topic_enum=ManagedTopicEnum.USER_PREFERENCES,
                    ),
                ),
                MemoryTopic(
                    managed_memory_topic=ManagedMemoryTopic(
                        managed_topic_enum=ManagedTopicEnum.USER_PERSONAL_INFO,
                    ),
                ),
                MemoryTopic(
                    custom_memory_topic=KUBERNETES_INCIDENT_FINDINGS_TOPIC,
                ),
                MemoryTopic(
                    custom_memory_topic=KUBERNETES_REMEDIATIONS_TOPIC,
                ),
            ],
        ),
    ],
)

context_spec = ReasoningEngineContextSpec(
    memory_bank_config=memory_bank_config,
)


def apply_memory_bank_config(
    agent_engine_name: str,
    project: str | None = None,
    location: str | None = None,
) -> Any:
    """Applies ``memory_bank_config`` to an Agent Runtime ReasoningEngine resource."""
    import agentplatform

    resolved_project = project or os.environ.get("GOOGLE_CLOUD_PROJECT")
    resolved_location = (
        location
        or os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_LOCATION")
        or os.environ.get("GOOGLE_CLOUD_REGION")
        or "us-east1"
    )
    client = agentplatform.Client(
        project=resolved_project,
        location=resolved_location,
    )
    return client.agent_engines.update(
        name=agent_engine_name,
        config=AgentEngineConfig(
            context_spec=context_spec,
        ),
    )
