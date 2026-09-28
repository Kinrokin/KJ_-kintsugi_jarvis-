import json
from pathlib import Path
from tests.support import Case
from kintsugi_bridge.schema import example_candidate,validate
from kintsugi_bridge.common import canonical
from kintsugi_bridge.surface import TOOLS
ROOT=Path(__file__).resolve().parents[1]

class ContractTests(Case):
    def test_tool_manifest_matches_exact_surface(self):
        manifest=json.loads((ROOT/'contracts/producer_tools.json').read_text())
        self.assertEqual(tuple(x['name'] for x in manifest['tools']),TOOLS)
    def test_submission_not_mislabeled_readonly(self):
        manifest=json.loads((ROOT/'contracts/producer_tools.json').read_text())
        self.assertFalse(manifest['tools'][0]['annotations']['readOnlyHint'])
    def test_live_gates_not_claimed_complete(self):
        gates=json.loads((ROOT/'contracts/live_acceptance.json').read_text())
        self.assertEqual(gates['overall_public_deployment'],'BLOCKED')
        self.assertTrue(all(x['status']!='PASS' and x['evidence'] is None for x in gates['gates']))
    def test_shipped_example_is_valid(self):
        validate((ROOT/'examples/synthetic_school_candidate.json').read_bytes())
    def test_all_variants_disallow_extra_fields(self):
        schema=json.loads((ROOT/'contracts/candidate.schema.json').read_text())
        self.assertEqual(len(schema['oneOf']),4)
        for variant in schema['oneOf']:
            self.assertFalse(variant['additionalProperties'])
            self.assertFalse(variant['properties']['claims']['additionalProperties'])
    def test_no_secrets_in_static_candidate(self):
        text=(ROOT/'examples/synthetic_school_candidate.json').read_text()
        self.assertNotIn('hotmail.com',text)
        self.assertNotIn('gmail.com',text)
        self.assertIn('demo-message-1',text)
