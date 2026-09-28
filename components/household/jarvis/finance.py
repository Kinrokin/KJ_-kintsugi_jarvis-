"""Preserved pure V2 analysis functions; no actions, ledger or permission code.
Inputs are normalized evidence provided by the caller, not authenticated bank data.
Forecasts are not spending authorizations. See SOURCE_COVERAGE.md before live use.
"""
from __future__ import annotations
import json, hashlib
from datetime import datetime, date, timedelta, timezone
from typing import Any
UTC=timezone.utc

class GuardError(ValueError):
    """A fail-closed safety or validation error, not permission to bypass a control."""

def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)

def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()

def timestamp() -> str:
    return datetime.now(UTC).isoformat()

def instant(value: str) -> datetime:
    if not isinstance(value, str):
        raise GuardError('Timezone-aware timestamp required')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise GuardError('Invalid timestamp') from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise GuardError('Naive timestamps are not accepted')
    return result.astimezone(UTC)

def recent(value: str | None, now: datetime, maximum_seconds: int) -> bool:
    if not value:
        return False
    try:
        age = (now - instant(value)).total_seconds()
        return 0 <= age <= maximum_seconds
    except (GuardError, TypeError):
        return False

def exact_int(value: Any, label: str, minimum: int | None = None) -> int:
    if type(value) is not int or (minimum is not None and value < minimum):
        raise GuardError(f'{label} must be an integer' + (f' >= {minimum}' if minimum is not None else ''))
    return value

def fields(record: dict, required: set[str], optional: set[str] | None = None) -> None:
    if not isinstance(record, dict):
        raise GuardError('Object required')
    missing = required - record.keys()
    extra = record.keys() - required - (optional or set())
    if missing or extra:
        raise GuardError(f'Invalid fields: missing={sorted(missing)}, extra={sorted(extra)}')

def nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GuardError(f'{label} must be nonempty text')
    return value

def affordability(data: dict, *, now: datetime | None = None) -> dict:
    """Dated cash forecast, not a credit decision or promise of future deposits.
    Inflows are positive, outflows negative in this normalized forecast ONLY.
    Finances raw transaction signs are the opposite: normalize explicitly first.
    """
    now = now or datetime.now(UTC)
    fields(data, {'as_of','balance_source','coverage_complete','obligations_complete','currency',
                  'cash_cents','protected_floor_cents','horizon_start','horizon_end','events','purchase'})
    if data['balance_source'] != 'source_reported' or not recent(data['as_of'], now, 4*3600):
        return {'verdict':'NOT_VERIFIED','reason':'Balance age/source not independently established'}
    if data['coverage_complete'] is not True or data['obligations_complete'] is not True:
        return {'verdict':'NOT_VERIFIED','reason':'Accounts or obligations incomplete'}
    if data['currency'] != 'USD':
        return {'verdict':'NOT_VERIFIED','reason':'Single-currency USD model only'}
    if data['protected_floor_cents'] is None:
        return {'verdict':'NOT_VERIFIED','reason':'Protected cash floor not agreed'}
    cash = exact_int(data['cash_cents'],'cash_cents')
    floor = exact_int(data['protected_floor_cents'],'protected_floor_cents',0)
    start, end = date.fromisoformat(data['horizon_start']), date.fromisoformat(data['horizon_end'])
    if end < start or (end-start).days > 366:
        raise GuardError('Invalid forecast horizon')
    if start != datetime.fromisoformat(data['as_of'].replace('Z','+00:00')).date():
        return {'verdict':'NOT_VERIFIED','reason':'Forecast start must match source balance local date; normalize as_of to household timezone first'}
    if not isinstance(data['events'], list):
        raise GuardError('Forecast events must be an array')
    p = data['purchase']
    fields(p,{'date','amount_cents'})
    pd, price = date.fromisoformat(p['date']), exact_int(p['amount_cents'],'purchase amount',0)
    if not start <= pd <= end:
        raise GuardError('Purchase outside horizon')
    seen, stream, forecast_income, pending_credits_excluded = set(), [], False, 0
    for e in data['events']:
        fields(e,{'id','date','amount_cents','status','already_in_cash','source_ref'})
        nonempty(e['id'],'event id'); nonempty(e['source_ref'],'source_ref')
        if e['id'] in seen:
            raise GuardError('Duplicate forecast event id')
        seen.add(e['id'])
        amount = exact_int(e['amount_cents'],'event amount')
        d = date.fromisoformat(e['date'])
        if e['status'] not in {'verified_scheduled','pending','posted','unverified'} or type(e['already_in_cash']) is not bool:
            raise GuardError('Invalid forecast event status')
        if not start <= d <= end:
            raise GuardError('Event outside forecast horizon; curate explicit scope first')
        if e['already_in_cash']:
            continue
        if e['status'] == 'unverified':
            return {'verdict':'NOT_VERIFIED','reason':'Unresolved amount/timing in forecast'}
        if amount > 0 and e['status'] == 'pending':
            pending_credits_excluded += amount
            continue
        if amount > 0:
            forecast_income = True
        stream.append((d, amount, e['id']))
    # Conservative order for same-day uncertain posting: all debits before credits.
    stream.append((pd,-price,'proposed-purchase'))
    stream.sort(key=lambda x: (x[0], x[1] >= 0, x[2]))
    remaining, minimum, cash_only = cash, cash, cash
    cash_only_min, trace = cash, []
    first_breach = start.isoformat() if cash < floor else None
    for d, amount, event_id in stream:
        remaining += amount
        if amount < 0:
            cash_only += amount
        cash_only_min = min(cash_only_min,cash_only)
        minimum = min(minimum,remaining)
        if remaining < floor and first_breach is None:
            first_breach = d.isoformat()
        trace.append({'date':d.isoformat(),'event_id':event_id,'after_cents':remaining})
    if minimum < floor:
        verdict = 'NOT_AFFORDABLE_IN_THIS_FORECAST'
    elif cash_only_min < floor and forecast_income:
        verdict = 'PROJECTED_AFFORDABLE_DEPENDS_ON_FUTURE_INCOME'
    else:
        verdict = 'CASH_COVERED_WITHIN_VERIFIED_HORIZON'
    return {'verdict':verdict,'as_of':data['as_of'],'minimum_cents':minimum,
            'cash_only_minimum_cents':cash_only_min,'protected_floor_cents':floor,
            'headroom_cents':minimum-floor,'first_breach':first_breach,
            'pending_credits_excluded_cents':pending_credits_excluded,'trace':trace,
            'limitations':'Forecast only; omitted expenses and changes invalidate it. No money moved.'}

def classify_inflows(rows: list[dict]) -> dict:
    """Input is an explicit normalized reconciliation dataset, not raw connector output.
    Raw negative amounts are inflows. Ambiguous transfers stay visible.
    """
    totals = {k:0 for k in ('income','internal_transfer','refund','loan_proceeds','ambiguous','pending')}
    ids = set()
    if not isinstance(rows, list):
        raise GuardError('Inflows must be an array')
    for r in rows:
        fields(r,{'id','amount_cents','pending','linked_own_counterpart','classification','confidence'})
        nonempty(r['id'],'transaction id')
        if r['id'] in ids:
            raise GuardError('Duplicate transaction id')
        ids.add(r['id']); amount=exact_int(r['amount_cents'],'amount_cents')
        if amount >= 0:
            raise GuardError('First-pass inflow reconciliation accepts only raw negative amounts')
        if type(r['pending']) is not bool or type(r['linked_own_counterpart']) is not bool:
            raise GuardError('Boolean reconciliation flags required')
        if r['confidence'] not in {'HIGH','MEDIUM','LOW','UNKNOWN'}:
            raise GuardError('Unknown confidence')
        value=-amount
        if r['pending']:
            bucket='pending'
        elif r['linked_own_counterpart']:
            bucket='internal_transfer'
        elif r['confidence'] == 'HIGH' and r['classification'] in {'income','refund','loan_proceeds'}:
            bucket=r['classification']
        else:
            bucket='ambiguous'
        totals[bucket] += value
    return {'cents':totals, 'confirmed_income_cents':totals['income'],
            'reconciled_total_cents':sum(totals.values()), 'tax_classification':'NOT_DETERMINED'}

def calendar_identity(event: dict) -> dict:
    fields(event,{'calendar_role','uid','recurrence_id','start','organizer','subject','timezone'})
    if event['calendar_role'] not in {'primary','family'}:
        raise GuardError('Unknown calendar role')
    nonempty(event['timezone'],'timezone')
    instant(event['start'])
    if event['uid']:
        return {'key':digest({'role':event['calendar_role'],'uid':event['uid'],'recurrence_id':event['recurrence_id']}),
                'confidence':'exact_uid','automatic_merge_candidate':True}
    return {'key':digest({'role':event['calendar_role'],'organizer':event['organizer'].strip().casefold(),
                         'subject':event['subject'].strip().casefold(),'start':instant(event['start']).isoformat()}),
            'confidence':'heuristic','automatic_merge_candidate':False}

def schedule_plan(existing: list[dict], desired: list[dict], active_limit: int) -> list[dict]:
    """Pure reconciliation proposal; never modifies a saved task. Existing fields preserved."""
    exact_int(active_limit,'active_limit',1)
    by_id = {x['id']:x for x in existing}
    active = sum(1 for x in existing if x.get('is_enabled') is True)
    result = []
    for item in desired:
        match = by_id.get(item.get('existing_id'))
        if match:
            changed = {k:{'old':match.get(k),'proposed':v} for k,v in item.get('requested_changes',{}).items() if match.get(k)!=v}
            result.append({'key':item['key'],'decision':'KEEP_EXISTING' if not changed else 'REVIEW_UPDATE',
                           'existing_id':match['id'],'preserved_record':match,'diff':changed})
        elif item.get('existing_id'):
            result.append({'key':item['key'],'decision':'BLOCK_STALE_EXISTING_ID'})
        elif active >= active_limit:
            result.append({'key':item['key'],'decision':'BLOCK_CAPACITY_NO_AUTO_DELETE'})
        else:
            result.append({'key':item['key'],'decision':'PROPOSE_NEW_REQUIRES_APPROVAL','spec':item})
            active += 1
    return result

def heartbeat(last_success: str | None, expected_interval_seconds: int, *, now: datetime | None = None) -> dict:
    now=now or datetime.now(UTC)
    exact_int(expected_interval_seconds,'interval',1)
    if last_success is None:
        return {'health':'NEVER_VERIFIED','alert':'No successful full run recorded'}
    age=(now-instant(last_success)).total_seconds()
    if age < 0:
        return {'health':'CLOCK_ANOMALY'}
    return {'health':'MISSED_OR_DELAYED' if age > 2*expected_interval_seconds else 'WITHIN_EXPECTED_WINDOW',
            'age_seconds':age,'note':'Silence is not proof that nothing required action.'}
