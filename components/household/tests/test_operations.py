import copy,hashlib,json,random,tempfile,unittest,uuid
from datetime import timedelta
from pathlib import Path
from jarvis.common import *
from jarvis.operations import *
from jarvis.finance import affordability,classify_inflows,schedule_plan,GuardError
from jarvis.household import Household
NOW=instant('2026-09-24T13:00:00Z')

def forecast():return {'as_of':'2026-09-24T08:00:00-05:00','balance_source':'source_reported','coverage_complete':True,'obligations_complete':True,'currency':'USD','cash_cents':100000,'protected_floor_cents':20000,'horizon_start':'2026-09-24','horizon_end':'2026-10-01','events':[{'id':'rent','date':'2026-09-25','amount_cents':-30000,'status':'verified_scheduled','already_in_cash':False,'source_ref':'synthetic'}],'purchase':{'date':'2026-09-24','amount_cents':10000}}

class OperationsTests(unittest.TestCase):
    def test_I04_policy_read_current_bytes(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'policy.json';p.write_text(canonical({'version':'one','challenge':'actual bytes','minimum_policy':'read only'}));h=hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(read_policy_fixture(p,h)['challenge'],'actual bytes');p.write_text(canonical({'version':'two','challenge':'changed','minimum_policy':'read only'}))
            with self.assertRaises(Refused):read_policy_fixture(p,h)
    def test_I04_missing_policy_degrades(self):
        with self.assertRaises(Refused):read_policy_fixture('/nonexistent/policy.json','x')
    def test_I05_required_source_missing_no_all_clear(self):self.assertFalse(coverage_report(['gmail','outlook'],{'gmail':{'as_of':iso(NOW),'status':'COMPLETE','policy_verified':True}},NOW)['all_clear_eligible'])
    def test_coverage_full_positive(self):self.assertTrue(coverage_report(['gmail'],{'gmail':{'as_of':iso(NOW),'status':'COMPLETE','policy_verified':True}},NOW)['all_clear_eligible'])
    def test_empty_coverage_not_all_clear(self):self.assertFalse(coverage_report([],{},NOW)['all_clear_eligible'])
    def test_future_source_timestamp_not_accepted(self):self.assertFalse(coverage_report(['g'],{'g':{'as_of':iso(NOW+timedelta(hours=1)),'status':'COMPLETE','policy_verified':True}},NOW)['all_clear_eligible'])
    def test_partial_pagination_no_cursor_advance(self):
        s=SyncCoverage();s.begin('gmail');s.page('gmail',[1],next_cursor='old');s.begin('gmail');s.page('gmail',[2],next_page='more');s.fail('gmail');self.assertEqual(s.committed['gmail']['cursor'],'old');self.assertEqual(s.status['gmail'],'DEGRADED')
    def test_full_pagination_positive(self):
        s=SyncCoverage();s.begin('gmail');s.page('gmail',[1],next_page='more');s.page('gmail',[2],next_cursor='new');self.assertEqual(s.committed['gmail']['items'],[1,2])
    def test_final_token_on_partial_page_rejected(self):
        s=SyncCoverage();s.begin('gmail')
        with self.assertRaises(Refused):s.page('gmail',[1],next_page='more',next_cursor='bad')
    def test_U04_coverage_recovers(self):
        s=SyncCoverage();s.begin('g');s.fail('g');s.begin('g');s.page('g',[],next_cursor='recovered');self.assertEqual(s.status['g'],'COMPLETE')
    def test_U05_measurement_not_invented(self):self.assertIsNone(value_report([])['review_sample_median_seconds'])
    def test_U05_metrics_preserve_costs(self):
        r=value_report([{'kind':'review_seconds','value':120},{'kind':'review_seconds','value':240},{'kind':'verified_savings_cents','value':1000},{'kind':'operating_cost_cents','value':1200}]);self.assertEqual(r['review_sample_median_seconds'],180);self.assertEqual(r['net_recorded_savings_cents'],-200)
    def test_dependency_risk_distinguishes_unknown(self):
        r=dependency_risks([{'id':'x','requires':['transport']}],{});self.assertIn('outside',r[0]['unknown']);self.assertIn('inferred_risk',r[0])
    def test_accepted_dependency_satisfies(self):self.assertEqual(dependency_risks([{'id':'x','requires':['transport']}],{('x','transport'):{'status':'accepted'}}),[])
    def test_no_false_scam_opportunity_approval(self):self.assertEqual(opportunity_screen({'exciting':True})['status'],'HOLD_UNVERIFIED')
    def test_verified_opportunity_still_not_auto_apply(self):
        d={k:True for k in ['identity_verified','official_program_verified','eligibility_evidence','no_upfront_fee','purpose_limited_data','worth_review']};self.assertFalse(opportunity_screen(d)['apply_automatically'])
    def test_zero_default_paid_budget(self):
        with self.assertRaises(Refused):Budget().reserve(1)
    def test_bounded_budget_positive_then_block(self):
        b=Budget(2,10);b.reserve(4);b.reserve(6)
        with self.assertRaises(Refused):b.reserve(0)
    def test_running_late_preserves_fixed(self):
        fixed={'id':'work','fixed':True,'start':iso(NOW),'end':iso(NOW+timedelta(hours=1))}
        r=plan_flexible([fixed,{'id':'flex','fixed':False,'minutes':30}],NOW,NOW+timedelta(hours=2));self.assertEqual(r['fixed'],[fixed]);self.assertEqual(instant(r['proposed'][0]['start']),NOW+timedelta(hours=1))
    def test_no_room_marks_unplaced_not_move_fixed(self):
        fixed={'id':'work','fixed':True,'start':iso(NOW),'end':iso(NOW+timedelta(hours=2))};r=plan_flexible([fixed,{'id':'flex','fixed':False,'minutes':30}],NOW,NOW+timedelta(hours=2));self.assertEqual(len(r['unplaced']),1)
    def test_minimum_planner_excludes_clinical(self):
        r=plan_flexible([{'id':'clinical','fixed':False,'minutes':30,'clinical':True}],NOW,NOW+timedelta(hours=1),'minimum');self.assertEqual(len(r['unplaced']),1)
    def test_json_duplicate_keys_rejected(self):
        with self.assertRaises(Refused):strict_json('{"a":1,"a":2}')
    def test_json_nonfinite_rejected(self):
        with self.assertRaises(Refused):strict_json('{"a":NaN}')
    def test_U01_capture_becomes_usable_task(self):
        with tempfile.TemporaryDirectory() as t:
            h=Household(t);h.command({'command_id':'thought','op':'capture','text':'Check school form'},NOW);r=h.command({'command_id':'triage','op':'make_task','object_id':'thought'},NOW);self.assertEqual(h._get('obligations',r['id'])['status'],'OPEN');h.close()
    def test_capture_task_deduplicated(self):
        with tempfile.TemporaryDirectory() as t:
            h=Household(t);h.command({'command_id':'c','op':'capture','text':'Test'},NOW)
            for i in range(2):h.command({'command_id':str(i),'op':'make_task','object_id':'c'},NOW)
            self.assertEqual(len(h.snapshot()['obligations']),1);h.close()

class FinanceTests(unittest.TestCase):
    def test_cash_forecast_positive(self):self.assertEqual(affordability(forecast(),now=NOW)['verdict'],'CASH_COVERED_WITHIN_VERIFIED_HORIZON')
    def test_stale_no_approval(self):
        d=forecast();d['as_of']='2026-09-23T08:00:00-05:00';self.assertEqual(affordability(d,now=NOW)['verdict'],'NOT_VERIFIED')
    def test_incomplete_obligations_no_approval(self):
        d=forecast();d['obligations_complete']=False;self.assertEqual(affordability(d,now=NOW)['verdict'],'NOT_VERIFIED')
    def test_unset_floor_no_approval(self):
        d=forecast();d['protected_floor_cents']=None;self.assertEqual(affordability(d,now=NOW)['verdict'],'NOT_VERIFIED')
    def test_future_income_qualified(self):
        d=forecast();d['cash_cents']=40000;d['events'][0]['date']='2026-09-26';d['events'].append({'id':'pay','date':'2026-09-25','amount_cents':100000,'status':'verified_scheduled','already_in_cash':False,'source_ref':'synthetic'});self.assertEqual(affordability(d,now=NOW)['verdict'],'PROJECTED_AFFORDABLE_DEPENDS_ON_FUTURE_INCOME')
    def test_pending_credit_not_cash(self):
        d=forecast();d['events'].append({'id':'pending','date':'2026-09-25','amount_cents':100000,'status':'pending','already_in_cash':False,'source_ref':'synthetic'});self.assertEqual(affordability(d,now=NOW)['pending_credits_excluded_cents'],100000)
    def test_raw_transfers_not_income(self):
        r=classify_inflows([{'id':'a','amount_cents':-10000,'pending':False,'linked_own_counterpart':True,'classification':'income','confidence':'HIGH'}]);self.assertEqual(r['confirmed_income_cents'],0)
    def test_refund_not_payroll(self):
        r=classify_inflows([{'id':'a','amount_cents':-10000,'pending':False,'linked_own_counterpart':False,'classification':'refund','confidence':'HIGH'}]);self.assertEqual(r['cents']['refund'],10000);self.assertEqual(r['confirmed_income_cents'],0)
    def test_missing_transfer_semantics_visible(self):
        r=classify_inflows([{'id':'a','amount_cents':-10000,'pending':False,'linked_own_counterpart':False,'classification':'income','confidence':'LOW'}]);self.assertEqual(r['cents']['ambiguous'],10000)
    def test_duplicate_raw_transaction_rejected(self):
        x={'id':'a','amount_cents':-10000,'pending':False,'linked_own_counterpart':False,'classification':'income','confidence':'HIGH'}
        with self.assertRaises(GuardError):classify_inflows([x,x])
    def test_same_day_debits_first(self):
        d=forecast();d['cash_cents']=30000;d['events'].append({'id':'pay','date':'2026-09-25','amount_cents':100000,'status':'verified_scheduled','already_in_cash':False,'source_ref':'synthetic'});self.assertEqual(affordability(d,now=NOW)['verdict'],'NOT_AFFORDABLE_IN_THIS_FORECAST')
    def test_500_generated_cash_scenarios(self):
        rng=random.Random(20260924)
        for _ in range(500):
            d=forecast();d['cash_cents']=rng.randint(0,500000);d['protected_floor_cents']=rng.randint(0,100000);d['purchase']['amount_cents']=rng.randint(0,100000);d['events'][0]['amount_cents']=-rng.randint(0,100000)
            r=affordability(d,now=NOW);expected=d['cash_cents']-d['purchase']['amount_cents']+d['events'][0]['amount_cents'];self.assertEqual(r['minimum_cents'],expected)
    def test_existing_schedule_fields_preserved(self):
        old={'id':'1','is_enabled':False,'schedule':'KEEP','prompt':'UNCHANGED','timezone':'America/Chicago'};r=schedule_plan([old],[{'key':'x','existing_id':'1','requested_changes':{}}],10);self.assertEqual(r[0]['preserved_record'],old)
    def test_capacity_does_not_delete_tasks(self):self.assertEqual(schedule_plan([{'id':'x','is_enabled':True}],[{'key':'new'}],1)[0]['decision'],'BLOCK_CAPACITY_NO_AUTO_DELETE')

    def test_300_mixed_household_sequences(self):
        # Random local command order with duplicate/stale revisions. Not an LLM injection test.
        rng=random.Random(9988)
        from test_household import routine
        with tempfile.TemporaryDirectory() as t:
            h=Household(t);h.configure_routine(routine(),NOW);h.tick(NOW)
            for i in range(300):
                row=h.snapshot(NOW)['occurrences'][0];op=rng.choice(['done','undo','snooze','skip'])
                command={'command_id':str(uuid.uuid4()),'op':op,'object_id':row['id'],'expected_revision':max(0,row['revision']-rng.choice([0,0,1]))}
                if op=='snooze':command['minutes']=15
                try:h.command(command,NOW)
                except Refused:pass
                after=h._get('occurrences',row['id'])
                self.assertEqual(after['due'],row['due'])
                if after['status']=='DONE':self.assertEqual(after['basis'],'user_reported')
                self.assertEqual(h.db.execute('SELECT count(*) FROM actions').fetchone()[0],0)
            h.close()
