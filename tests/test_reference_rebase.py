import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from solidworks_mcp import reference_rebase as rr

OLD = r'C:\repo\wt-a\通用貨架'
NEW = r'D:\moved\wt-b\通用貨架'


class FakeApp:
    """Closed-file reference store: file -> list of referenced full paths (what GetDocumentDependencies2 reports)."""

    def __init__(self, refs, replace_ok=True, open_docs=()):
        self.refs = {k: list(v) for k, v in refs.items()}
        self.replace_ok = replace_ok
        self.open_docs = set(open_docs)
        self.replace_calls = []
        self.dependency_calls = []

    def GetOpenDocumentByName(self, path):
        return object() if path in self.open_docs else None

    def GetDocumentDependencies2(self, path, traverse, search, readonly):
        self.dependency_calls.append(path)
        flat = []
        for ref in self.refs.get(path, []):
            flat += [Path(ref).name, ref]
        return tuple(flat)

    def ReplaceReferencedDocument(self, path, old, new):
        self.replace_calls.append((path, old, new))
        if not self.replace_ok:
            return False
        self.refs[path] = [new if r == old else r for r in self.refs[path]]
        return True


def exists_all(_path):
    return True


class PathHelperTests(unittest.TestCase):
    def test_normalisation_ignores_case_and_slash_style(self):
        self.assertEqual(rr.norm('C:/Repo/WT-A\\x'), rr.norm(r'c:\repo\wt-a\X'))

    def test_under_requires_a_path_boundary(self):
        self.assertTrue(rr.under(r'C:\repo\wt-a\通用貨架\a.SLDPRT', r'C:\repo\wt-a\通用貨架'))
        self.assertFalse(rr.under(r'C:\repo\wt-a\通用貨架2\a.SLDPRT', r'C:\repo\wt-a\通用貨架'))
        self.assertFalse(rr.under(r'C:\repo\wt-a\通用貨架', r'C:\repo\wt-a\通用貨架'))

    def test_roots_must_be_absolute_distinct_and_not_nested(self):
        for old, new in [('rel', NEW), (OLD, 'rel'), (OLD, OLD), (OLD, OLD + r'\sub'), (OLD + r'\sub', OLD)]:
            with self.assertRaises(ValueError):
                rr.validate_roots(old, new)
        rr.validate_roots(OLD, NEW)

    def test_ordering_is_parts_then_assemblies_then_drawings(self):
        files = [r'C:\x\b.SLDDRW', r'C:\x\a.SLDASM', r'C:\x\c.SLDPRT', r'C:\x\A.sldprt']
        ordered = rr.order_files(files)
        self.assertEqual([Path(f).suffix.lower() for f in ordered], ['.sldprt', '.sldprt', '.sldasm', '.slddrw'])


class PlanTests(unittest.TestCase):
    def plan(self, refs, exists=exists_all):
        return rr.plan_file(NEW + r'\a.SLDASM', refs, OLD, NEW, exists)

    def test_reference_under_old_root_maps_to_the_same_relative_path(self):
        [action] = self.plan([OLD + r'\橫樑層\橫樑.SLDPRT'])
        self.assertEqual(action.status, 'replace')
        self.assertEqual(action.new, NEW + r'\橫樑層\橫樑.SLDPRT')

    def test_missing_target_is_reported_and_not_replaced(self):
        [action] = self.plan([OLD + r'\x.SLDPRT'], exists=lambda p: False)
        self.assertEqual(action.status, 'missing_target')

    def test_reference_already_in_new_root_is_ok(self):
        [action] = self.plan([NEW + r'\x.SLDPRT'])
        self.assertEqual(action.status, 'ok')

    def test_reference_outside_both_roots_is_left_alone(self):
        [action] = self.plan([r'E:\library\bolt.SLDPRT'])
        self.assertEqual(action.status, 'outside')

    def test_non_native_references_are_skipped(self):
        [action] = self.plan([OLD + r'\import.STEP'])
        self.assertEqual(action.status, 'non_native')

    def test_duplicate_references_are_planned_once(self):
        actions = self.plan([OLD + r'\x.SLDPRT', OLD + r'\X.sldprt'])
        self.assertEqual(len(actions), 1)

    def test_case_and_slash_differences_still_match_the_old_root(self):
        [action] = self.plan([OLD.lower().replace('\\', '/') + '/y.SLDPRT'])
        self.assertEqual(action.status, 'replace')


class RebaseTests(unittest.TestCase):
    def files_and_refs(self):
        asm, drw, prt = NEW + r'\a.SLDASM', NEW + r'\a.SLDDRW', NEW + r'\p.SLDPRT'
        refs = {prt: [], asm: [OLD + r'\p.SLDPRT'], drw: [OLD + r'\a.SLDASM', r'E:\lib\ext.SLDPRT']}
        return [drw, asm, prt], refs

    def run_rebase(self, app, files, apply=True, **kw):
        return rr.rebase(app, files, OLD, NEW, apply=apply, exists=kw.pop('exists', exists_all),
                         locked=kw.pop('locked', lambda f: False), **kw)

    def test_dry_run_reads_references_but_never_replaces(self):
        files, refs = self.files_and_refs()
        app = FakeApp(refs)
        report = self.run_rebase(app, files, apply=False)
        self.assertEqual(app.replace_calls, [])
        self.assertEqual(report['counts']['replace'], 2)
        self.assertEqual(report['mode'], 'dry-run')
        self.assertEqual(len(app.dependency_calls), 3)

    def test_apply_rewrites_each_reference_with_exact_paths_and_verifies(self):
        files, refs = self.files_and_refs()
        app = FakeApp(refs)
        report = self.run_rebase(app, files)
        self.assertEqual(sorted(app.replace_calls), sorted([
            (NEW + r'\a.SLDASM', OLD + r'\p.SLDPRT', NEW + r'\p.SLDPRT'),
            (NEW + r'\a.SLDDRW', OLD + r'\a.SLDASM', NEW + r'\a.SLDASM')]))
        self.assertTrue(report['verified'])
        self.assertEqual(report['remaining_old'], [])
        self.assertEqual(report['replaced'], 2)
        self.assertEqual(report['counts']['outside'], 1)

    def test_apply_twice_changes_nothing_the_second_time(self):
        files, refs = self.files_and_refs()
        app = FakeApp(refs)
        self.run_rebase(app, files)
        app.replace_calls.clear()
        report = self.run_rebase(app, files)
        self.assertEqual(app.replace_calls, [])
        self.assertEqual(report['replaced'], 0)
        self.assertTrue(report['verified'])

    def test_refuses_before_any_change_when_a_target_file_is_open(self):
        files, refs = self.files_and_refs()
        app = FakeApp(refs, open_docs=[files[1]])
        with self.assertRaisesRegex(RuntimeError, 'open'):
            self.run_rebase(app, files)
        self.assertEqual(app.replace_calls, [])

    def test_failed_replacement_is_recorded_and_verification_fails(self):
        files, refs = self.files_and_refs()
        app = FakeApp(refs, replace_ok=False)
        report = self.run_rebase(app, files)
        self.assertFalse(report['verified'])
        self.assertEqual(len(report['failed']), 2)
        self.assertEqual(len(report['remaining_old']), 2)

    def test_locked_files_are_skipped_and_reported(self):
        files, refs = self.files_and_refs()
        app = FakeApp(refs)
        report = self.run_rebase(app, files, locked=lambda f: f.endswith('a.SLDASM'))
        self.assertEqual([c[0] for c in app.replace_calls], [NEW + r'\a.SLDDRW'])
        self.assertEqual(report['locked_skipped'], [NEW + r'\a.SLDASM'])

    def test_missing_targets_are_not_replaced_and_listed(self):
        files, refs = self.files_and_refs()
        app = FakeApp(refs)
        report = self.run_rebase(app, files, exists=lambda p: not p.endswith('p.SLDPRT'))
        self.assertEqual(len(app.replace_calls), 1)
        self.assertEqual(report['counts']['missing_target'], 1)
        self.assertFalse(report['verified'])
        self.assertEqual(report['remaining_old'], [{'file': NEW + r'\a.SLDASM', 'ref': OLD + r'\p.SLDPRT'}])

    def test_files_outside_the_new_root_are_never_modified(self):
        app = FakeApp({r'C:\elsewhere\x.SLDASM': [OLD + r'\p.SLDPRT']})
        with self.assertRaisesRegex(ValueError, 'outside'):
            self.run_rebase(app, [r'C:\elsewhere\x.SLDASM'])
        self.assertEqual(app.replace_calls, [])

    def test_the_old_root_is_never_a_replacement_target(self):
        files, refs = self.files_and_refs()
        app = FakeApp(refs)
        self.run_rebase(app, files)
        self.assertTrue(all(rr.under(call[0], NEW) for call in app.replace_calls))
        self.assertTrue(all(not rr.under(call[2], OLD) for call in app.replace_calls))


class FileSystemTests(unittest.TestCase):
    def test_native_files_skips_lock_files_and_other_extensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'sub').mkdir()
            for name in ('a.SLDPRT', 'sub/b.sldasm', 'sub/c.SLDDRW', '~$a.SLDPRT', 'notes.txt', 'x.step', 'sub/~$b.sldasm'):
                (root / name).write_bytes(b'x')
            found = sorted(Path(p).name for p in rr.native_files(root))
            self.assertEqual(found, ['a.SLDPRT', 'b.sldasm', 'c.SLDDRW'])

    def test_lock_file_next_to_a_document_marks_it_locked(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / '橫樑.SLDPRT'
            doc.write_bytes(b'x')
            self.assertFalse(rr.is_locked(str(doc)))
            (Path(tmp) / '~$橫樑.SLDPRT').write_bytes(b'x')
            self.assertTrue(rr.is_locked(str(doc)))


if __name__ == '__main__':
    unittest.main()
