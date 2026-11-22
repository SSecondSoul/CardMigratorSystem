"""All configured jobs remain in the denominator. Manual and automatic evidence stay separate."""
from sqlalchemy import select
from ..persistence.database import transaction
from ..persistence.migrations import MigrationJob


def statistics(service):
    with transaction(service.engine) as session:keys=list(session.scalars(select(MigrationJob.id)))
    rows=[service.report(key) for key in keys]
    count=len(rows)
    def rate(k):
        passed=sum((r.get('assessment') or {}).get('dimensions',{}).get(k)=='pass' for r in rows)
        return {'passed':passed,'configured':count,'rate':passed/count if count else None}
    summaries={name:rate(name) for name in ('static','compile_runtime','structure','visual','interaction')}
    summaries['composite']={'passed':sum(r['status']=='finished' for r in rows),'configured':count}
    # Repeated confirmations do not create extra successes; only the latest
    # confirmation bound to the final accepted bytes participates in the count.
    manual=[]
    for row in rows:
        matches=[f for f in row['manual_feedback'] if row['final_artifact'] and f['revision_sha256']==row['final_artifact']['sha256']]
        if matches:manual.append(matches[-1])
    return {'schema_version':1,'evidence_class':'development_or_disclosed_exploratory',
        'configured':count,'dimensions':summaries,'statuses':{s:sum(r['status']==s for r in rows) for s in sorted({r['status'] for r in rows})},
        'known_total_tokens':sum(r['usage']['known_total_tokens'] for r in rows),
        'usage_complete':all(r['usage']['complete'] for r in rows),'model_calls_started':sum(r['model_calls_started'] for r in rows),
        'manual_confirmations':len(manual),'manual_small_edits':sum(f['passed'] and f['changed_lines'] is not None and f['changed_lines']<10 for f in manual),
        'limitations':['no_independent_test_attestation','no_historical_time_imputation','no_efficiency_claim_without_matched_manual_baseline']}
