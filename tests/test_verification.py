"""Evidence and arithmetic checks with independently observable failure conditions."""
import copy
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from green_claims.pipeline import prepare, run_review
from green_claims.verification.facts import check_facts
from green_claims.verification.judge import validate_judgments
from green_claims.reporting.html import render_report
from green_claims.generation.client import ChatCompletionsClient

CLAIM = 'Our company-wide absolute emissions in tonnes CO2e decreased by 30% in 2025 from 2024.'
DISCLOSURE = 'Company-wide absolute emissions in 2024 were 100 tonnes CO2e.\n\nCompany-wide absolute emissions in 2025 were 108 tonnes CO2e.'


def fact(context, kind='relative_change_pct'):
    d1, d2 = context['disclosure']
    dimensions = {'metric': 'absolute emissions', 'unit': 'tonnes CO2e', 'period': '2025',
                  'baseline_period': '2024', 'scope': 'company-wide', 'metric_basis': 'absolute', 'nature': 'actual'}
    c_ref = {'id': 'C1', 'quote': CLAIM}
    d_ref = {'id': d1.id, 'quote': d1.text}
    e_ref = {'id': d2.id, 'quote': d2.text}
    return {'pairs': [{'claim_id': 'C1', 'claim_fact': {
        **dimensions, 'references': [c_ref], 'quantity': {'kind': kind, 'direction': 'decrease',
            'value': {'text': '30', 'reference': c_ref}}},
        'disclosure_fact': {**dimensions, 'references': [d_ref, e_ref], 'quantity': {
            'kind': kind, 'baseline': {'text': '100', 'reference': d_ref},
            'current': {'text': '108', 'reference': e_ref}}}, 'note': ''}]}


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.context = prepare(CLAIM, DISCLOSURE, None)
        self.raw = fact(self.context)

    def test_conditional_percent_calculation_detects_opposite_sign(self):
        row = check_facts(self.raw, self.context)[0]
        self.assertEqual(row['status'], 'aligned')
        self.assertEqual(row['arithmetic']['status'], 'mismatch')
        self.assertEqual(row['arithmetic']['claimed_value'], '-30')
        self.assertEqual(row['arithmetic']['calculated_value'], '8.00')
        self.assertEqual(row['arithmetic']['formula'], '(current / baseline - 1) * 100')
        self.assertFalse(row['semantic_extraction_verified'])
        self.assertTrue(all(op['reference']['quote_verified'] for op in row['arithmetic']['operands'].values()))

    def test_metric_or_scope_mismatch_prevents_arithmetic(self):
        for dimension, value in [('metric_basis', 'intensity'), ('scope', 'Product A'), ('period', '2026'), ('unit', 'kg CO2e')]:
            raw = copy.deepcopy(self.raw)
            raw['pairs'][0]['disclosure_fact'][dimension] = value
            result = check_facts(raw, self.context)[0]
            self.assertEqual(result['status'], 'unverified' if dimension in {'period', 'unit'} else 'not_aligned', dimension)
            self.assertEqual(result['arithmetic']['status'], 'not_computed')

    def test_missing_metadata_or_fabricated_quote_does_not_claim_numeric_verification(self):
        raw = copy.deepcopy(self.raw)
        raw['pairs'][0]['claim_fact']['scope'] = None
        self.assertEqual(check_facts(raw, self.context)[0]['status'], 'incomplete')
        raw = copy.deepcopy(self.raw)
        raw['pairs'][0]['disclosure_fact']['references'][0]['quote'] = 'Invented company figures for 2024 and 2025.'
        self.assertEqual(check_facts(raw, self.context)[0]['status'], 'unverified')
        raw = copy.deepcopy(self.raw)
        raw['pairs'][0]['disclosure_fact']['quantity']['current']['text'] = '999'
        self.assertEqual(check_facts(raw, self.context)[0]['arithmetic']['status'], 'not_computed')
        raw = copy.deepcopy(self.raw)
        raw['pairs'][0]['claim_fact']['unit'] = 'kg CO2e'
        raw['pairs'][0]['disclosure_fact']['unit'] = 'kg CO2e'
        self.assertEqual(check_facts(raw, self.context)[0]['status'], 'unverified')

    def test_percent_points_and_extrapolated_or_ranged_numbers_are_rejected(self):
        raw = copy.deepcopy(self.raw)
        raw['pairs'][0]['claim_fact']['quantity']['kind'] = 'percentage_point_change'
        self.assertEqual(check_facts(raw, self.context)[0]['arithmetic']['status'], 'not_computed')
        raw = copy.deepcopy(self.raw)
        raw['pairs'][0]['claim_fact']['quantity']['value']['text'] = '100'
        self.assertEqual(check_facts(raw, self.context)[0]['arithmetic']['status'], 'not_computed')
        raw = copy.deepcopy(self.raw)
        raw['pairs'][0]['disclosure_fact']['quantity']['current']['text'] = '108-120'
        self.assertEqual(check_facts(raw, self.context)[0]['arithmetic']['status'], 'not_computed')

    def test_judge_source_id_and_regulation_limits(self):
        raw = {'reviews': [{'claim_id': 'C1', 'comparison_verdict': 'agree', 'regulation_verdict': 'agree',
                           'issues': [], 'disclosure_references': [{'id': 'R0001', 'quote': DISCLOSURE}],
                           'regulation_references': [], 'explanation': 'Claim seems supported.'}]}
        opinion = validate_judgments(raw, self.context)[0]
        self.assertEqual(opinion['comparison_verdict'], 'uncertain')
        self.assertEqual(opinion['regulation_verdict'], 'not_assessed')
        self.assertEqual(opinion['status'], 'uncertain')
        self.assertFalse(opinion['authoritative'])

    def test_stage_failures_keep_primary_result_and_mark_human_review(self):
        from green_claims.demo.fixtures import demo_regulation
        case = prepare(CLAIM, DISCLOSURE, demo_regulation())
        class Generator:
            def generate(self, context, language):
                return {'findings': [{'claim_id': 'C1', 'status': 'supported', 'test_types': ['numeric'],
                    'explanation': 'Numbers appear sound.', 'evidence': [{'id': context['disclosure'][0].id,
                    'quote': context['disclosure'][0].text}], 'regulation_status': 'not_assessed',
                    'regulation_explanation': 'No assessment.', 'regulation_references': [],
                    'follow_up_question': 'Review the sources.'}]}
            def extract_facts(self, context, language):
                raise RuntimeError('private-provider-payload')
            def judge(self, context, findings, facts, language):
                raise RuntimeError('private-provider-payload')
        report = run_review(CLAIM, DISCLOSURE, case['regulation'], 'Live AI', generator=Generator(),
                            verification='facts_and_judge')
        self.assertEqual(report['findings'][0]['status'], 'supported')
        self.assertTrue(report['findings'][0]['verification']['human_review_required'])
        self.assertEqual(report['verification']['stages'], {'fact_extraction': 'failed', 'judge': 'failed'})
        self.assertNotIn('private-provider-payload', str(report))
        self.assertIn('Evidence cross-check', render_report(report))

    def test_numeric_conflict_remains_visible_beside_primary_supported_finding(self):
        from green_claims.verification.execution import verify
        class Generator:
            def extract_facts(self, context, language):
                return self_raw
        self_raw = self.raw
        finding = {'claim_id': 'C1', 'status': 'supported'}
        result, warnings = verify(self.context, [finding], Generator(), 'facts', 'English')
        self.assertEqual(result['stages']['fact_extraction'], 'completed')
        self.assertIn('Arithmetic conflicts with primary supported finding', finding['verification']['review_reasons'])
        self.assertEqual(warnings, [])

    def test_explicit_opt_in_and_one_claim_per_row(self):
        with self.assertRaisesRegex(ValueError, 'require Live AI'):
            run_review(CLAIM, DISCLOSURE, mode='Offline demo', verification='facts')
        with self.assertRaisesRegex(ValueError, 'fact extraction'):
            run_review(CLAIM, DISCLOSURE, mode='Live AI', generator=object(), verification='facts')
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            check_facts({'pairs': []}, self.context)

    def test_three_live_calls_have_separate_inputs_and_preserve_regulatory_axis(self):
        context = self.context
        disclosure = context['disclosure'][0]
        finding = {'findings': [{'claim_id': 'C1', 'status': 'contradicted', 'test_types': ['numeric'],
            'explanation': 'The arithmetic differs.', 'evidence': [{'id': disclosure.id, 'quote': disclosure.text}],
            'regulation_status': 'not_assessed', 'regulation_explanation': 'No rule supplied.',
            'regulation_references': [], 'follow_up_question': 'Confirm the numbers.'}]}
        opinion = {'reviews': [{'claim_id': 'C1', 'comparison_verdict': 'agree',
            'regulation_verdict': 'not_assessed', 'issues': [], 'explanation': 'The quoted figures imply an increase.',
            'disclosure_references': [{'id': disclosure.id, 'quote': disclosure.text}],
            'regulation_references': []}]}
        replies = [finding, self.raw, opinion]
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                result = {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(replies[len(requests)-1])}}]}
                payload = json.dumps(result).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(payload)
            def log_message(self, *args):
                pass
        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = ChatCompletionsClient(f'http://127.0.0.1:{server.server_port}/chat/completions', 'model', 'test', 'api-key')
            report = run_review(CLAIM, DISCLOSURE, mode='Live AI', generator=client,
                                verification='facts_and_judge', model='model')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        self.assertEqual(len(requests), 3)
        messages = [json.loads(request['messages'][1]['content']) for request in requests]
        self.assertNotIn('initial_findings', messages[1])
        self.assertNotIn('regulation_passages', messages[1])
        self.assertIn('initial_findings', messages[2])
        self.assertEqual(report['verification']['stages'], {'fact_extraction': 'completed', 'judge': 'completed'})
        self.assertEqual(report['findings'][0]['status'], 'contradicted')
        self.assertEqual(report['findings'][0]['verification']['judge']['regulation_verdict'], 'not_assessed')
        self.assertEqual(report['findings'][0]['verification']['facts']['arithmetic']['status'], 'mismatch')


if __name__ == '__main__':
    unittest.main()
