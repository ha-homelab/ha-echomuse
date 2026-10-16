"""Regression checks for public documentation tooling, without network access."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


docs, wiki = module('check_docs'), module('render_wiki')


class DocumentationTests(unittest.TestCase):
    def test_links_and_unicode_anchors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / 'README.md'
            source.write_text('# Привет мир\n# Привет мир\n')
            self.assertIsNone(docs.check_link(root, source, '#привет-мир-1'))
            self.assertEqual(docs.check_link(root, source, 'missing.md'), 'missing target')
            self.assertEqual(docs.check_link(root, source, '../secret.md'), 'link leaves repository')
            self.assertEqual(docs.check_link(root, source, '#absent'), 'missing Markdown anchor')
            self.assertEqual(docs.check_link(root, source, 'javascript:alert'), 'unsafe link scheme')

    def test_fenced_examples_do_not_become_links(self):
        self.assertEqual(docs.destinations('```md\n[x](missing.md)\n```\n[x](real.md)'), ['real.md'])

    def test_svg_external_resources_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'diagram.svg'
            path.write_text('<svg viewBox="0 0 10 10"><title>Test</title><desc>Diagram</desc><script>alert(1)</script></svg>')
            self.assertIn('SVG contains executable or embedded content', docs.check_svg(path))
            path.write_text('<svg viewBox="0 0 10 10"><title>Test</title><desc>Diagram</desc><path fill="url(#a)"/></svg>')
            self.assertEqual(docs.check_svg(path), [])

    def test_svg_rejects_mixed_case_urls_and_processing_instructions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'diagram.svg'
            wrapper = '<svg viewBox="0 0 10 10"><title>Test</title><desc>Diagram</desc>{}</svg>'
            for body in ('<path fill="URL(https://example.org/p.svg#g)"/>',
                         '<path style="fill: uRl(\'https://example.org/p.svg#g\')"/>'):
                with self.subTest(body=body):
                    path.write_text(wrapper.format(body))
                    self.assertIn('SVG contains external URL', docs.check_svg(path))
            for position in ('before', 'inside', 'after'):
                with self.subTest(position=position):
                    instruction = '<?xml-stylesheet type="text/css" href="https://example.org/style.css"?>'
                    content = wrapper.format(instruction if position == 'inside' else '')
                    if position == 'before':
                        content = instruction + content
                    elif position == 'after':
                        content += instruction
                    path.write_text(content)
                    self.assertIn('SVG contains processing instruction', docs.check_svg(path))
            path.write_text('<?xml version="1.0"?>' + wrapper.format('<path fill="URL(#local)"/>'))
            self.assertEqual(docs.check_svg(path), [])

    def test_wiki_preserves_remote_links_and_anchors(self):
        text = '[Go](../README.md#installation-order) ![Diagram](assets/a.svg) [Other](https://example.org/a)'
        result = wiki.rewrite(text, 'docs/guide.md', {'README.md': 'Home'}, 'a' * 40)
        self.assertIn('[Go](./Home#installation-order)', result)
        self.assertIn('/' + 'a' * 40 + '/docs/assets/a.svg)', result)
        self.assertIn('[Other](https://example.org/a)', result)

    def test_wiki_preserves_fenced_markdown_examples(self):
        examples = (
            '```md\n[x](../../private.md)\n```\n',
            '````md\r\n```\r\n[x](../../private.md)\r\n`````\r\n',
            '  ~~~md\n[x](../../private.md)\n  ~~~~\n',
            '```md\n[x](../../private.md)\n',
        )
        for example in examples:
            with self.subTest(example=example):
                text = '[Home](../README.md)\n\n' + example
                result = wiki.rewrite(text, 'docs/guide.md', {'README.md': 'Home'}, 'a' * 40)
                self.assertEqual(result, '[Home](./Home)\n\n' + example)
        text = examples[0] + '[Home](../README.md)'
        self.assertEqual(wiki.rewrite(text, 'docs/guide.md', {'README.md': 'Home'}, 'a' * 40),
                         examples[0] + '[Home](./Home)')

    def test_wiki_preserves_inline_code_and_multibacktick_examples(self):
        for example in ('`[x](../../private.md)`', '`` `[x](../../private.md)` ``',
                        '`first line\n[x](../../private.md)`', '`[x](../../private.md)\\`'):
            with self.subTest(example=example):
                text = example + ' and [Home](../README.md)'
                self.assertEqual(wiki.rewrite(text, 'docs/guide.md', {'README.md': 'Home'}, 'a' * 40),
                                 example + ' and [Home](./Home)')
        # Unmatched or escaped backticks do not turn following links into code.
        for prefix in ('` unmatched ', '\\` escaped ', '` previous paragraph\n\n'):
            with self.subTest(prefix=prefix):
                text = prefix + '[Home](../README.md)'
                self.assertEqual(wiki.rewrite(text, 'docs/guide.md', {'README.md': 'Home'}, 'a' * 40),
                                 prefix + '[Home](./Home)')
        self.assertEqual(wiki.rewrite('[`Home`](../README.md)', 'docs/guide.md', {'README.md': 'Home'}, 'a' * 40),
                         '[`Home`](./Home)')

    def test_wiki_reads_commit_not_dirty_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
            git('init', '-q')
            git('config', 'user.name', 'Documentation test')
            git('config', 'user.email', 'test@example.org')
            (root / 'README.md').write_text('# Reviewed overview\n')
            git('add', 'README.md')
            git('commit', '-qm', 'Fixture')
            sha = git('rev-parse', 'HEAD')
            (root / 'README.md').write_text('# Private draft must not export\n')
            output, count = wiki.render(root, sha)
            self.assertEqual(count, 2)
            self.assertIn('Reviewed overview', (output / 'Home.md').read_text())
            self.assertNotIn('Private draft', (output / 'Home.md').read_text())
            with self.assertRaises(ValueError):
                wiki.render(root, 'main')
            (output / 'Home.md').unlink()
            (output / 'Home.md').symlink_to(root / 'README.md')
            with self.assertRaises(ValueError):
                wiki.render(root, sha)
            self.assertIn('Private draft', (root / 'README.md').read_text())


if __name__ == '__main__':
    unittest.main()
