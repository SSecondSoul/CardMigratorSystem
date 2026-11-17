"""Only project already compiler-verified Vue for-key / San trackBy identities.

Raw template/DOM evidence is never modified. This does not waive DOM attributes,
controls, pixel scores, or an unverified/missing/different trackBy expression.
"""
from copy import deepcopy


def project_tree(tree, policies, *, source):
    result = deepcopy(tree)
    index = 0
    changes = []

    def visit(node):
        nonlocal index
        label = node.get('label', '')
        if not label.startswith('#'):
            if index >= len(policies):
                raise ValueError('business_projection_shape_mismatch')
            policy = policies[index]
            parts = label.split('|')
            if parts[0] != policy['tag']:
                raise ValueError('business_projection_tag_mismatch')
            if policy.get('key'):
                if source:
                    if parts.count('binding:key') != 1:
                        raise ValueError('business_projection_source_key_missing')
                    parts.remove('binding:key')
                elif 'binding:key' in parts:
                    raise ValueError('business_projection_target_key_attribute_unexpected')
                if 'directive:for' not in parts:
                    raise ValueError('business_projection_loop_missing')
                before = node['label']
                parts.append('identity:' + policy['key'])
                node['label'] = parts[0] + '|' + '|'.join(sorted(parts[1:]))
                changes.append({'element_index': index, 'before': before, 'after': node['label']})
            index += 1
        for child in node.get('children', []):
            visit(child)

    visit(result)
    if index != len(policies):
        raise ValueError('business_projection_node_count_mismatch')
    return result, changes
