import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from solidworks_mcp.recovery_snapshot import fingerprint
from solidworks_mcp.package_repair import validate_private_package,materialize_step_aliases,validate_repair_result

class PackageRepairTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.base=Path(temp.name);self.root=self.base/'generation';self.root.mkdir()
        self.source=self.base/'source';self.source.mkdir()
        self.files={}
        for name in ('assembly.SLDASM','part.SLDPRT','sensor.stp'):
            source=self.source/name;source.write_bytes(b'source')
            output=self.root/('r-'+name);output.write_bytes(b'source');self.files[str(source)]=str(output)
        self.evidence={'manifest_path':str(self.root/'manifest.json'),'package_files':self.files,
                       'snapshot_path':self.files[str(self.source/'assembly.SLDASM')],
                       'assembly_occurrence_state':{'configuration':'MR12','occurrences':[]},
                       'source_files_sha256':{p:fingerprint(p) for p in self.files}}
        self.evidence['pid']=123
        def dependencies(path,*args):
            return ['sensor',str(self.source/'sensor.stp')] if Path(path).suffix.casefold()=='.sldprt' else []
        self.app=SimpleNamespace(GetDocumentDependencies2=dependencies)
    def test_valid_package_does_not_require_source_cad_operations(self):
        root,mapping,state=validate_private_package(self.evidence)
        self.assertEqual(root,self.root.resolve());self.assertEqual(mapping,self.files)
        self.assertEqual(state['configuration'],'MR12')
    def test_original_step_basename_copy_is_hashed_and_recorded(self):
        result=materialize_step_aliases(self.app,self.evidence)
        alias=str(self.root/'sensor.stp')
        self.assertEqual(result[alias]['sha256'],fingerprint(str(self.source/'sensor.stp')))
        self.assertEqual(Path(alias).read_bytes(),b'source')
        self.assertEqual(materialize_step_aliases(self.app,self.evidence),result)
    def test_alias_collision_is_not_overwritten(self):
        (self.root/'sensor.stp').write_bytes(b'other')
        with self.assertRaisesRegex(ValueError,'collision'):materialize_step_aliases(self.app,self.evidence)
        self.assertEqual((self.root/'sensor.stp').read_bytes(),b'other')
    def test_modified_primary_is_not_used(self):
        (self.root/'r-sensor.stp').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'source hash'):materialize_step_aliases(self.app,self.evidence)
        self.assertFalse((self.root/'sensor.stp').exists())
    def test_source_overwrite_and_output_escape_are_rejected(self):
        source=str(self.source/'part.SLDPRT');self.files[source]=source
        with self.assertRaisesRegex(ValueError,'non-private'):validate_private_package(self.evidence)
    def test_duplicate_output_is_rejected(self):
        self.files[str(self.source/'part.SLDPRT')]=self.files[str(self.source/'assembly.SLDASM')]
        with self.assertRaisesRegex(ValueError,'ambiguous'):validate_private_package(self.evidence)
    def test_unknown_step_reference_cannot_create_alias(self):
        self.app.GetDocumentDependencies2=lambda *args:['unknown',str(self.source/'unknown.stp')]
        with self.assertRaisesRegex(ValueError,'unique'):materialize_step_aliases(self.app,self.evidence)
        self.assertFalse((self.root/'unknown.stp').exists())
    def result(self):
        return {'status':'repaired','helper_pid':456,'helper_start_time':'start',
                'assembly_state_restoration':{'verified_occurrences':0},'reopen_errors':0,
                'step_aliases':{},'package_files_sha256':{p:fingerprint(p) for p in self.files.values()}}
    def test_source_owner_accepts_only_complete_unchanged_repair_inventory(self):
        result=self.result();self.assertEqual(validate_repair_result(self.evidence,result),result['package_files_sha256'])
        (self.root/'r-part.SLDPRT').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'content changed'):validate_repair_result(self.evidence,result)
    def test_missing_file_hash_does_not_finalize(self):
        result=self.result();result['package_files_sha256'].pop(str(self.root/'r-part.SLDPRT'))
        with self.assertRaisesRegex(ValueError,'inventory'):validate_repair_result(self.evidence,result)
    def test_source_pid_and_unresolved_open_error_are_rejected(self):
        result=self.result();result['helper_pid']=123
        with self.assertRaisesRegex(ValueError,'independent'):validate_repair_result(self.evidence,result)
        result=self.result();result['reopen_errors']=2
        with self.assertRaisesRegex(ValueError,'load errors'):validate_repair_result(self.evidence,result)
    def test_only_unchanged_missing_suppressed_baseline_allows_file_not_found(self):
        baseline={'d:/old/missing.sldprt':{'active':0,'suppressed':2}}
        self.evidence['assembly_occurrence_state']['missing_references']=baseline
        result=self.result();result.update(reopen_errors=2,missing_references_after=baseline,
                                         source_missing_references_preserved=True)
        self.assertTrue(validate_repair_result(self.evidence,result))
        result['missing_references_after']={'d:/new/missing.sldprt':{'active':0,'suppressed':2}}
        with self.assertRaisesRegex(ValueError,'load errors'):validate_repair_result(self.evidence,result)
    def test_missing_active_baseline_and_other_error_flags_never_allow_completion(self):
        baseline={'d:/old/missing.sldprt':{'active':1,'suppressed':2}}
        self.evidence['assembly_occurrence_state']['missing_references']=baseline
        result=self.result();result.update(reopen_errors=2,missing_references_after=baseline,
                                         source_missing_references_preserved=True)
        with self.assertRaisesRegex(ValueError,'load errors'):validate_repair_result(self.evidence,result)
        baseline['d:/old/missing.sldprt']['active']=0;result['reopen_errors']=3
        with self.assertRaisesRegex(ValueError,'load errors'):validate_repair_result(self.evidence,result)

if __name__=='__main__':unittest.main()
