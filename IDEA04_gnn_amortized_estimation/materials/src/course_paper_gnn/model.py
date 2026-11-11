from __future__ import annotations

import torch
from torch import nn

from .constants import (
    EDGE_TYPES,
    NODE_TYPES,
    NUMERIC_FEATURE_DIM,
    SUBTYPES,
    VALUE_DESCRIPTOR_DIM,
)


def _segment_softmax(scores: torch.Tensor, segment: torch.Tensor) -> torch.Tensor:
    output = torch.empty_like(scores)
    for graph_id in torch.unique(segment):
        mask = segment == graph_id
        output[mask] = torch.softmax(scores[mask], dim=0)
    return output


class RelationGraphLayer(nn.Module):
    def __init__(self, hidden_dim: int, num_relations: int, dropout: float) -> None:
        super().__init__()
        self.self_projection = nn.Linear(hidden_dim, hidden_dim)
        self.relation_layers = nn.ModuleList(
            nn.Linear(hidden_dim, hidden_dim, bias=False)
            for _ in range(num_relations)
        )
        self.normalization = nn.LayerNorm(hidden_dim)
        self.dropout = nn.Dropout(dropout)

    def forward(
        self,
        hidden: torch.Tensor,
        edge_index: torch.Tensor,
        edge_type: torch.Tensor,
    ) -> torch.Tensor:
        source, target = edge_index
        aggregated = torch.zeros_like(hidden)
        for relation_id, relation_layer in enumerate(self.relation_layers):
            selected = edge_type == relation_id
            if not torch.any(selected):
                continue
            selected_source = source[selected]
            selected_target = target[selected]
            messages = relation_layer(hidden[selected_source])
            denominator = torch.bincount(
                selected_target,
                minlength=hidden.shape[0],
            ).clamp_min(1).to(hidden.dtype)
            aggregated.index_add_(
                0,
                selected_target,
                messages / denominator[selected_target].unsqueeze(-1),
            )
        update = self.self_projection(hidden) + aggregated
        return self.normalization(hidden + self.dropout(torch.relu(update)))


class GraphPooling(nn.Module):
    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.score = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(
        self,
        hidden: torch.Tensor,
        graph_index: torch.Tensor,
        num_graphs: int,
    ) -> torch.Tensor:
        logits = self.score(hidden).squeeze(-1)
        contexts = torch.zeros(
            num_graphs,
            hidden.shape[1],
            dtype=hidden.dtype,
            device=hidden.device,
        )
        for graph_id in range(num_graphs):
            mask = graph_index == graph_id
            if not torch.any(mask):
                continue
            weights = torch.softmax(logits[mask], dim=0)
            contexts[graph_id] = torch.sum(hidden[mask] * weights.unsqueeze(-1), dim=0)
        return contexts


class AllocationHead(nn.Module):
    def __init__(
        self,
        hidden_dim: int,
        value_dim: int,
        *,
        use_anchor: bool = True,
        use_zero_mask: bool = True,
        use_simplex: bool = True,
    ) -> None:
        super().__init__()
        self.use_anchor = use_anchor
        self.use_zero_mask = use_zero_mask
        self.use_simplex = use_simplex
        self.value_projection = nn.Sequential(
            nn.Linear(value_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
        )
        self.residual_head = nn.Sequential(
            nn.Linear(hidden_dim * 3 + 1, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, 1),
        )
        # Start close to the analytically computed additive allocation and let
        # training learn only the non-additive residual.
        torch.nn.init.zeros_(self.residual_head[-1].weight)
        torch.nn.init.zeros_(self.residual_head[-1].bias)
        # softplus(0.54132485) is approximately one, so the initialized model
        # starts at the analytic additive allocation before learning residuals.
        self.anchor_scale = nn.Parameter(torch.tensor(0.54132485))
        self.residual_scale = nn.Parameter(torch.tensor(-2.19722458))

    def forward(
        self,
        player_hidden: torch.Tensor,
        graph_context: torch.Tensor,
        player_graph: torch.Tensor,
        value_descriptor: torch.Tensor,
        base_share: torch.Tensor,
        structural_zero: torch.Tensor,
    ) -> torch.Tensor:
        graph_value = self.value_projection(value_descriptor)[player_graph]
        residual = self.residual_head(
            torch.cat(
                (player_hidden, graph_context, graph_value, base_share.unsqueeze(-1)),
                dim=-1,
            )
        ).squeeze(-1) * torch.sigmoid(self.residual_scale)
        raw = residual
        if self.use_anchor:
            log_base = torch.log(base_share.clamp_min(1e-8))
            raw = residual + torch.nn.functional.softplus(self.anchor_scale) * log_base
        if self.use_zero_mask:
            raw = raw.masked_fill(structural_zero, -1e9)
        if self.use_simplex:
            return _segment_softmax(raw, player_graph)
        return torch.relu(raw)


class RPVGNN(nn.Module):
    def __init__(
        self,
        *,
        hidden_dim: int = 64,
        num_layers: int = 2,
        value_dim: int = VALUE_DESCRIPTOR_DIM,
        dropout: float = 0.1,
        use_edges: bool = True,
        use_anchor: bool = True,
        use_zero_mask: bool = True,
        use_simplex: bool = True,
    ) -> None:
        super().__init__()
        self.use_edges = use_edges
        self.node_type_embedding = nn.Embedding(len(NODE_TYPES), hidden_dim)
        self.subtype_embedding = nn.Embedding(len(SUBTYPES), hidden_dim)
        self.input_projection = nn.Sequential(
            nn.Linear(NUMERIC_FEATURE_DIM, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
        )
        self.layers = nn.ModuleList(
            RelationGraphLayer(hidden_dim, len(EDGE_TYPES), dropout)
            for _ in range(num_layers)
        )
        self.pooling = GraphPooling(hidden_dim)
        self.allocation = AllocationHead(
            hidden_dim,
            value_dim,
            use_anchor=use_anchor,
            use_zero_mask=use_zero_mask,
            use_simplex=use_simplex,
        )

    def forward(self, batch: object) -> torch.Tensor:
        hidden = (
            self.input_projection(batch.x)
            + self.node_type_embedding(batch.node_type)
            + self.subtype_embedding(batch.subtype)
        )
        if self.use_edges:
            for layer in self.layers:
                hidden = layer(hidden, batch.edge_index, batch.edge_type)
        num_graphs = int(batch.value_descriptor.shape[0])
        contexts = self.pooling(hidden, batch.graph_index, num_graphs)
        player_hidden = hidden[batch.player_index]
        player_context = contexts[batch.player_graph_index]
        return self.allocation(
            player_hidden=player_hidden,
            graph_context=player_context,
            player_graph=batch.player_graph_index,
            value_descriptor=batch.value_descriptor,
            base_share=batch.base_share,
            structural_zero=batch.structural_zero,
        )


class FeatureMLP(nn.Module):
    def __init__(
        self,
        *,
        hidden_dim: int = 64,
        value_dim: int = VALUE_DESCRIPTOR_DIM,
        dropout: float = 0.1,
        use_anchor: bool = True,
        use_zero_mask: bool = True,
        use_simplex: bool = True,
    ) -> None:
        super().__init__()
        self.player_projection = nn.Sequential(
            nn.Linear(NUMERIC_FEATURE_DIM, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
        )
        self.global_projection = nn.Sequential(
            nn.Linear(NUMERIC_FEATURE_DIM, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
        )
        self.allocation = AllocationHead(
            hidden_dim,
            value_dim,
            use_anchor=use_anchor,
            use_zero_mask=use_zero_mask,
            use_simplex=use_simplex,
        )
        self.dropout = nn.Dropout(dropout)

    def forward(self, batch: object) -> torch.Tensor:
        player_hidden = self.player_projection(batch.x[batch.player_index])
        num_graphs = int(batch.value_descriptor.shape[0])
        graph_mean = torch.zeros(
            num_graphs,
            batch.x.shape[1],
            dtype=batch.x.dtype,
            device=batch.x.device,
        )
        counts = torch.bincount(
            batch.graph_index,
            minlength=num_graphs,
        ).clamp_min(1).to(batch.x.dtype)
        graph_mean.index_add_(0, batch.graph_index, batch.x)
        graph_mean = graph_mean / counts.unsqueeze(-1)
        player_context = self.global_projection(
            graph_mean[batch.player_graph_index]
        )
        return self.allocation(
            player_hidden=self.dropout(player_hidden),
            graph_context=player_context,
            player_graph=batch.player_graph_index,
            value_descriptor=batch.value_descriptor,
            base_share=batch.base_share,
            structural_zero=batch.structural_zero,
        )


def build_model(
    name: str,
    *,
    hidden_dim: int = 64,
    num_layers: int = 2,
    value_dim: int = VALUE_DESCRIPTOR_DIM,
    dropout: float = 0.1,
    use_edges: bool = True,
    use_anchor: bool = True,
    use_zero_mask: bool = True,
    use_simplex: bool = True,
) -> nn.Module:
    if name == "rpv_gnn":
        return RPVGNN(
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            value_dim=value_dim,
            dropout=dropout,
            use_edges=use_edges,
            use_anchor=use_anchor,
            use_zero_mask=use_zero_mask,
            use_simplex=use_simplex,
        )
    if name == "feature_mlp":
        return FeatureMLP(
            hidden_dim=hidden_dim,
            value_dim=value_dim,
            dropout=dropout,
            use_anchor=use_anchor,
            use_zero_mask=use_zero_mask,
            use_simplex=use_simplex,
        )
    raise ValueError(f"Unknown model: {name}")
