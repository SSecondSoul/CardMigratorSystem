from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from typing import Any


@dataclass
class DomDiffNode:
    path: str
    vue_node: dict[str, Any] | None = None
    san_node: dict[str, Any] | None = None
    reason: str = ""
    cost: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DomCompareResult:
    tree_edit_distance: float
    normalized_tree_edit_distance: float
    structure_similarity: float
    tag_sequence_similarity: float
    text_similarity: float
    missing_nodes: list[dict[str, Any]] = field(default_factory=list)
    extra_nodes: list[dict[str, Any]] = field(default_factory=list)
    changed_nodes: list[dict[str, Any]] = field(default_factory=list)
    vue_node_count: int = 0
    san_node_count: int = 0
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DomTreeComparator:
    INSERT_COST = 1.0
    DELETE_COST = 1.0
    TAG_REPLACE_COST = 1.0
    ATTR_CHANGE_COST = 0.25
    TEXT_CHANGE_COST = 0.5
    TYPE_CHANGE_COST = 1.0

    def compare(self, vue_tree: dict[str, Any] | None, san_tree: dict[str, Any] | None) -> DomCompareResult:
        normalized_vue = self._normalize_node(vue_tree)
        normalized_san = self._normalize_node(san_tree)

        missing_nodes: list[DomDiffNode] = []
        extra_nodes: list[DomDiffNode] = []
        changed_nodes: list[DomDiffNode] = []

        distance = self._compare_node(
            normalized_vue,
            normalized_san,
            path="/",
            missing_nodes=missing_nodes,
            extra_nodes=extra_nodes,
            changed_nodes=changed_nodes,
        )

        vue_nodes = self._count_element_nodes(normalized_vue)
        san_nodes = self._count_element_nodes(normalized_san)
        max_nodes = max(vue_nodes, san_nodes, 1)
        normalized_distance = min(1.0, distance / max_nodes)
        structure_similarity = max(0.0, 1.0 - normalized_distance)
        tag_sequence_similarity = self._sequence_similarity(
            self._tag_sequence(normalized_vue),
            self._tag_sequence(normalized_san),
        )
        text_similarity = self._sequence_similarity(
            self._text_content(normalized_vue),
            self._text_content(normalized_san),
        )

        result = DomCompareResult(
            tree_edit_distance=round(distance, 4),
            normalized_tree_edit_distance=round(normalized_distance, 4),
            structure_similarity=round(structure_similarity, 4),
            tag_sequence_similarity=round(tag_sequence_similarity, 4),
            text_similarity=round(text_similarity, 4),
            missing_nodes=[node.to_dict() for node in missing_nodes],
            extra_nodes=[node.to_dict() for node in extra_nodes],
            changed_nodes=[node.to_dict() for node in changed_nodes],
            vue_node_count=vue_nodes,
            san_node_count=san_nodes,
        )
        result.summary = self._build_summary(result)
        return result

    def _compare_node(
        self,
        vue_node: dict[str, Any] | None,
        san_node: dict[str, Any] | None,
        path: str,
        missing_nodes: list[DomDiffNode],
        extra_nodes: list[DomDiffNode],
        changed_nodes: list[DomDiffNode],
    ) -> float:
        if vue_node is None and san_node is None:
            return 0.0
        if vue_node is None:
            cost = self.INSERT_COST * self._subtree_size(san_node)
            extra_nodes.append(DomDiffNode(path=path, san_node=self._node_summary(san_node), reason="san_extra_node", cost=cost))
            return cost
        if san_node is None:
            cost = self.DELETE_COST * self._subtree_size(vue_node)
            missing_nodes.append(DomDiffNode(path=path, vue_node=self._node_summary(vue_node), reason="san_missing_node", cost=cost))
            return cost

        cost = self._node_replace_cost(vue_node, san_node)
        if cost:
            changed_nodes.append(DomDiffNode(
                path=path,
                vue_node=self._node_summary(vue_node),
                san_node=self._node_summary(san_node),
                reason=self._change_reason(vue_node, san_node),
                cost=cost,
            ))

        vue_children = self._children(vue_node)
        san_children = self._children(san_node)
        max_len = max(len(vue_children), len(san_children))
        for index in range(max_len):
            child_vue = vue_children[index] if index < len(vue_children) else None
            child_san = san_children[index] if index < len(san_children) else None
            child_path = f"{path.rstrip('/')}/{self._child_label(child_vue or child_san, index)}"
            cost += self._compare_node(child_vue, child_san, child_path, missing_nodes, extra_nodes, changed_nodes)
        return cost

    def _node_replace_cost(self, vue_node: dict[str, Any], san_node: dict[str, Any]) -> float:
        vue_type = vue_node.get("type")
        san_type = san_node.get("type")
        if vue_type != san_type:
            return self.TYPE_CHANGE_COST

        if vue_type == "text":
            return 0.0 if self._normalize_text(vue_node.get("text", "")) == self._normalize_text(san_node.get("text", "")) else self.TEXT_CHANGE_COST

        cost = 0.0
        if vue_node.get("tag") != san_node.get("tag"):
            cost += self.TAG_REPLACE_COST
        if self._normalize_attrs(vue_node.get("attrs", {})) != self._normalize_attrs(san_node.get("attrs", {})):
            cost += self.ATTR_CHANGE_COST
        return cost

    def _change_reason(self, vue_node: dict[str, Any], san_node: dict[str, Any]) -> str:
        if vue_node.get("type") != san_node.get("type"):
            return "node_type_changed"
        if vue_node.get("type") == "text":
            return "text_changed"
        reasons = []
        if vue_node.get("tag") != san_node.get("tag"):
            reasons.append("tag_changed")
        if self._normalize_attrs(vue_node.get("attrs", {})) != self._normalize_attrs(san_node.get("attrs", {})):
            reasons.append("attrs_changed")
        return ",".join(reasons) or "node_changed"

    def _normalize_node(self, node: dict[str, Any] | None) -> dict[str, Any] | None:
        if not node:
            return None
        node_type = node.get("type", "element")
        if node_type == "text":
            text = self._normalize_text(node.get("text", ""))
            if not text:
                return None
            return {"type": "text", "text": text}

        normalized_children = []
        for child in node.get("children", []) or []:
            normalized_child = self._normalize_node(child)
            if normalized_child:
                normalized_children.append(normalized_child)

        return {
            "type": "element",
            "tag": str(node.get("tag", "")).lower(),
            "attrs": self._normalize_attrs(node.get("attrs", {})),
            "children": normalized_children,
            "is_root": bool(node.get("is_root", False)),
        }

    def _normalize_attrs(self, attrs: dict[str, Any] | None) -> dict[str, str]:
        if not isinstance(attrs, dict):
            return {}
        ignored_attrs = {"data-vue-hidden", "data-san-hidden"}
        normalized: dict[str, str] = {}
        for key, value in attrs.items():
            if key in ignored_attrs or key.startswith("data-v-") or key.startswith("data-san-"):
                continue
            if value is True:
                normalized[key] = "true"
            elif value is False or value is None:
                continue
            elif key == "class":
                normalized[key] = " ".join(sorted(str(value).split()))
            else:
                normalized[key] = self._normalize_text(str(value))
        return dict(sorted(normalized.items()))

    def _children(self, node: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not node:
            return []
        return node.get("children", []) or []

    def _subtree_size(self, node: dict[str, Any] | None) -> int:
        if not node:
            return 0
        return 1 + sum(self._subtree_size(child) for child in self._children(node))

    def _count_element_nodes(self, node: dict[str, Any] | None) -> int:
        if not node:
            return 0
        count = 1 if node.get("type") == "element" and not node.get("is_root") else 0
        return count + sum(self._count_element_nodes(child) for child in self._children(node))

    def _tag_sequence(self, node: dict[str, Any] | None) -> list[str]:
        if not node:
            return []
        tags = []
        if node.get("type") == "element" and not node.get("is_root"):
            tags.append(node.get("tag", ""))
        for child in self._children(node):
            tags.extend(self._tag_sequence(child))
        return tags

    def _text_content(self, node: dict[str, Any] | None) -> str:
        if not node:
            return ""
        if node.get("type") == "text":
            return self._normalize_text(node.get("text", ""))
        return self._normalize_text(" ".join(self._text_content(child) for child in self._children(node)))

    def _node_summary(self, node: dict[str, Any] | None) -> dict[str, Any] | None:
        if not node:
            return None
        if node.get("type") == "text":
            return {"type": "text", "text": node.get("text", "")}
        return {
            "type": "element",
            "tag": node.get("tag", ""),
            "attrs": node.get("attrs", {}),
            "child_count": len(self._children(node)),
        }

    def _child_label(self, node: dict[str, Any] | None, index: int) -> str:
        if not node:
            return f"missing[{index}]"
        if node.get("type") == "text":
            return f"text[{index}]"
        return f"{node.get('tag', 'node')}[{index}]"

    def _sequence_similarity(self, left: list[str] | str, right: list[str] | str) -> float:
        return round(SequenceMatcher(a=left, b=right).ratio(), 4)

    def _normalize_text(self, value: str) -> str:
        return " ".join(str(value).split())

    def _build_summary(self, result: DomCompareResult) -> str:
        return (
            f"DOM 对比完成：tree_edit_distance={result.tree_edit_distance}，"
            f"structure_similarity={result.structure_similarity}，"
            f"tag_sequence_similarity={result.tag_sequence_similarity}，"
            f"text_similarity={result.text_similarity}。"
        )


def compare_dom_trees(vue_tree: dict[str, Any] | None, san_tree: dict[str, Any] | None) -> DomCompareResult:
    return DomTreeComparator().compare(vue_tree, san_tree)


def compare_dom_snapshots(vue_snapshot: dict[str, Any] | None, san_snapshot: dict[str, Any] | None) -> DomCompareResult:
    vue_tree = (vue_snapshot or {}).get("tree")
    san_tree = (san_snapshot or {}).get("tree")
    return compare_dom_trees(vue_tree, san_tree)
