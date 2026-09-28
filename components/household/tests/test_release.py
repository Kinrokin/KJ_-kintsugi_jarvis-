import json,sqlite3,tempfile,unittest,ast
from pathlib import Path
from jarvis.household import Household
from jarvis.common import Refused,instant
from jarvis.operations import read_policy_fixture
ROOT=Path(__file__).resolve().parents[1]
class ReleaseTests(unittest.TestCase):
    def test_packaged_policy_fixture_can_actually_be_read(self):
        d=json.loads((ROOT/'config/POLICY_PROBE_DIGEST.json').read_text())
        self.assertEqual(read_policy_fixture(ROOT/d['file'],d['sha256'])['status'],'READ_FROM_BYTES')
    def test_all_routine_examples_are_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            h=Household(tmp)
            try:
                for name in ['routine_morning.json','routine_evening.json','completion_routine.json','event_routine.json']:
                    h.configure_routine(json.loads((ROOT/'examples'/name).read_text()),instant('2026-09-24T13:00:00Z'))
                self.assertEqual(h.db.execute('SELECT count(*) FROM routines').fetchone()[0],4)
            finally:h.close()
    def test_wrong_state_schema_is_not_migrated_implicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'household.sqlite3';db=sqlite3.connect(p);db.execute('CREATE TABLE meta(k TEXT,v TEXT)');db.execute("INSERT INTO meta VALUES('schema','old')");db.commit();db.close()
            before=p.read_bytes()
            with self.assertRaises(Refused):Household(tmp)
            self.assertEqual(before,p.read_bytes())
    def test_python_source_syntax(self):
        import jarvis
        self.assertEqual(jarvis.__version__,'3.2.0')
        for group in ['jarvis','scripts','tests']:
            for p in (ROOT/group).glob('*.py'):ast.parse(p.read_text(),filename=str(p))
