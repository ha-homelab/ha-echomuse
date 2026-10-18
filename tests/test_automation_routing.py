"""Evaluate actual metadata-only job conditions for trusted and untrusted events."""
import ast
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def permits(source, event, author, same_repo=True, action="opened", draft=False, default_base=True):
    condition = re.search(r'^    if: >-\n((?:      .*\n)+)', source, re.M).group(1)
    values = {
        'github.event.action': action, 'github.event.changes.base': False,
        'github.event.pull_request.base.ref': 'main' if default_base else 'topic',
        'github.event.repository.default_branch': 'main',
        'github.event_name': event, 'github.repository': 'owner/repo',
        'github.event.pull_request.head.repo.full_name': 'owner/repo' if same_repo else 'fork/repo',
        'github.event.pull_request.user.login': author, 'github.event.pull_request.draft': draft,
    }
    expression = re.sub(r'github(?:\.[\w_]+)+', lambda match: repr(values[match.group()]), condition)
    expression = expression.replace('&&', ' and ').replace('||', ' or ')
    expression = re.sub(r'!(?!=)', ' not ', expression)

    def visit(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BoolOp):
            values = [visit(value) for value in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not visit(node.operand)
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left, right = visit(node.left), visit(node.comparators[0])
            if isinstance(node.ops[0], ast.Eq):
                return left == right
            if isinstance(node.ops[0], ast.NotEq):
                return left != right
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            args = [visit(arg) for arg in node.args]
            if node.func.id == 'fromJSON' and len(args) == 1:
                return json.loads(args[0])
            if node.func.id == 'contains' and len(args) == 2:
                return args[1] in args[0]
        raise AssertionError('Unsupported metadata condition syntax')

    return visit(ast.parse('(' + expression.strip() + ')', mode='eval').body)


class AutomationRoutingTests(unittest.TestCase):
    def test_events_receive_only_the_intended_metadata_job(self):
        for name in ('auto-approve.yml', 'auto-merge.yml'):
            source = (ROOT / '.github/workflows' / name).read_text()
            with self.subTest(workflow=name):
                self.assertNotIn('actions/checkout', source)
                self.assertNotRegex(source, r'(?m)^\s+run:')
                for author in ('4alvit', 'californiantiramisu', 'renovate[bot]', 'dependabot[bot]'):
                    for same in (True, False):
                        target = not same or author == 'dependabot[bot]'
                        self.assertEqual(permits(source, 'pull_request_target', author, same), target)
                        self.assertEqual(permits(source, 'pull_request', author, same), not target)
                for event in ('pull_request', 'pull_request_target', 'push', 'issue_comment'):
                    self.assertFalse(permits(source, event, 'stranger'))
                self.assertFalse(permits(source, 'pull_request_target', 'dependabot[bot]', action='edited'))
                self.assertFalse(permits(source, 'pull_request_target', 'dependabot[bot]', default_base=False))


if __name__ == '__main__':
    unittest.main()
