"""Single-task CLI using the reused runtime; no independent model loop."""
from __future__ import annotations
import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import re
import time

from phase1_request_policy import ReportRequest, required_headings, word_limits
from phase1_report_pipeline import render_report_sources
from report_checks import check_report
from customization import check_customization
from report_outcome import delivery_outcome
from runtime_config import load_project_environment, provider_settings
from provenance import environment, snapshot, write_json, digest

DEFAULT_BUDGET = {'model_calls': 8, 'output_tokens_per_call': 6000, 'model_retries': 0,
    'prompt_utf8_bytes_per_call': 60000, 'model_timeout_seconds': 180,
    'run_timeout_seconds': 480, 'tool_calls': 6, 'web_search_calls': 2,
    'tool_timeout_seconds': 60, 'embedding_calls': 40, 'embedding_input_chars': 1000000,
    'automatic_revisions': 0, 'cost_limit': 0}


async def run(config, *, fake_model=None, web_replay=None, out=None):
    from runtime_adapter import assemble, agent_input, tool_names
    root = Path(__file__).resolve().parents[1]
    request = ReportRequest(**config['request'])
    request.validate()
    budget = {**DEFAULT_BUDGET, **config.get('budget', {})}
    length_control = config.get('experiment_options', {}).get('length_control', 'enforce')
    calculation_control = config.get('experiment_options', {}).get('calculation_control', 'tool')
    report_validation = config.get('experiment_options', {}).get('report_validation', 'enforce')
    web_period_filter = config.get('experiment_options', {}).get('web_period_filter','off')
    web_period_scope = config.get('web_period_scope')
    financial_period_scope=config.get('financial_period_scope')
    financial_period_filter=config.get('experiment_options',{}).get('financial_period_filter','off')
    sec_fact_limit=config.get('financial_sec_fact_limit',12)
    from financial_period import validate_financial_scope
    validate_financial_scope(financial_period_scope)
    if financial_period_filter not in {'off','enforce'} or (financial_period_filter=='enforce' and financial_period_scope is None):
        raise ValueError('Invalid financial period filter/scope')
    if type(sec_fact_limit)is not int or not 1<=sec_fact_limit<=100:
        raise ValueError('SEC fact limit must be between1and100')
    quote_binding=config.get('experiment_options',{}).get('quote_binding','off')
    quote_rows=config.get('quote_binding_rows',[])
    from quote_binding import validate_quote_config
    validate_quote_config(quote_rows,quote_binding)
    evidence_workspace=config.get('experiment_options',{}).get('evidence_workspace','off')
    if evidence_workspace not in {'off','on','full_original'}:raise ValueError('Invalid evidence workspace mode')
    web_acquisition = config.get('experiment_options',{}).get('web_acquisition','legacy')
    if web_acquisition not in {'legacy','bounded'}:raise ValueError('Invalid acquisition mode')
    from web_period import validate_scope
    validate_scope(web_period_scope)
    if web_period_filter not in {'off','enforce'} or (web_period_filter=='enforce' and web_period_scope is None):
        raise ValueError('Invalid web period filter/scope')
    if length_control not in {'enforce','planning_only'}:
        raise ValueError('Invalid length-control experiment mode')
    if calculation_control not in {'off','planning_only','tool'}:
        raise ValueError('Invalid calculation-control experiment mode')
    if report_validation not in {'off','enforce'}:
        raise ValueError('Invalid report-validation mode')
    frozen = None
    uploaded_evidence=None
    if config.get('uploaded_evidence_file'):
        raw=Path(config['uploaded_evidence_file']).read_bytes()
        if digest(raw)!=config['uploaded_evidence_sha256']:raise ValueError('Frozen uploads hash mismatch')
        uploaded_evidence=json.loads(raw)
        if request.source_mode=='web_only' or uploaded_evidence.get('web') or config.get('frozen_evidence_file'):
            raise ValueError('Frozen upload subset cannot contain web evidence or coexist with frozen full input')
    if config.get('frozen_evidence_file'):
        frozen_bytes = Path(config['frozen_evidence_file']).read_bytes()
        if digest(frozen_bytes) != config['frozen_evidence_sha256']:
            raise ValueError('Frozen evidence hash mismatch')
        frozen = json.loads(frozen_bytes)
        if frozen['source_mode'] != request.source_mode:
            raise ValueError('Frozen evidence source mode mismatch')
        permitted = {'uploaded','web'} if request.source_mode == 'hybrid' else {
            'web' if request.source_mode == 'web_only' else 'uploaded'}
        for kind in ('uploaded','web'):
            if kind not in permitted and frozen[kind]:
                raise ValueError('Forbidden source in frozen input')
    if budget['model_calls'] < 8:
        raise ValueError('Current report gate requires at least 8 bounded turns')
    if budget['model_retries'] != 0 or budget['automatic_revisions'] != 0:
        raise ValueError('Development profile fixes retries and automatic revisions to zero')
    out = Path(out) if out else root / 'artifacts/runs' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    corpus_root = Path(config.get('corpus_root', root / 'data/corpus/processed'))
    ids = config.get('document_ids', [])
    if request.source_mode != 'web_only' and not ids:
        raise ValueError('Select uploaded document IDs explicitly')
    write_json(out / 'request.json', asdict(request))
    write_json(out / 'resolved_config.json', {**config, 'budget': budget,
        'retrieval_limits': {'local_parent_chars':18000, 'top_k':8,
                             'web_search_num':3, 'web_excerpt_chars':6000},
        'enhanced': {'scope_review':True,'evidence_projection':True,'report_gate':True,
                     'evidence_audit':True,'automatic_scope_rewrite':False,'attachment_links':False,
                     'word_limit_save_gate':bool(word_limits(request) and word_limits(request)['max'] is not None and length_control=='enforce'),
                     'length_control_mode':length_control,
                     'calculation_control_mode':calculation_control,
                     'report_validation_mode':report_validation,
                     'web_period_filter':web_period_filter,'web_period_scope':web_period_scope,
                     'financial_period_scope':financial_period_scope,'financial_period_filter':financial_period_filter,'sec_fact_limit':sec_fact_limit,
                     'quote_binding':quote_binding,'quote_binding_rows':quote_rows,
                     'evidence_workspace':evidence_workspace,
                     'web_acquisition':web_acquisition,'worker_attachment_discovery':web_acquisition=='bounded',
                     'explicit_word_limits':word_limits(request), 'draft_target_maximum_ratio':0.85 if word_limits(request) else None,
                     'pre_save_corrections':'within existing model turn budget'},
        'tool_closure': sorted(tool_names(request.source_mode, frozen=frozen is not None, length_control=bool(word_limits(request)) and length_control=='enforce',calculation_control=calculation_control,evidence_workspace=evidence_workspace))})
    write_json(out / 'retrieval_results.json', {'status': 'not_called'})
    write_json(out / 'evidence_ledger.json', [])
    (out / 'raw_report.md').write_text('')
    (out / 'report.md').write_text('')
    write_json(out / 'audit.json', {'status': 'not_generated'})
    from autoresearch_agent_langchain import LangChainRuntimeFactory
    import autoresearch_frontier_finance
    runtime_root = Path(autoresearch_frontier_finance.__file__).resolve().parents[2]
    manifest = {'run_id': out.name, 'purpose': config.get('purpose', 'development_integration'),
        'generation_stage': 'first_generation', 'parent_run_id': None, 'status': 'started',
        'retry_of': config.get('retry_of'),
        'condition_id': config.get('condition_id'), 'repetition': config.get('repetition'),
        'customization_pair': config.get('customization_pair'),
        'paired_base_run': config.get('paired_base_run'),
        'frozen_evidence_sha256': config.get('frozen_evidence_sha256'),
        'uploaded_evidence_sha256': config.get('uploaded_evidence_sha256'),
        'experiment_freeze_sha256': config.get('experiment_freeze_sha256'),
        'started_at': datetime.now(timezone.utc).isoformat(), 'environment': environment(),
        'request': asdict(request), 'budget': budget, 'config_sha256': digest(json.dumps(config, sort_keys=True).encode()),
        'code': snapshot(root, root / 'artifacts/versions/project'),
        'runtime': snapshot(runtime_root, root / 'artifacts/versions/runtime'),
        'model': 'fake_fixture' if fake_model else 'configured_vllm',
        'cost': {'amount':0,'basis':'user_declared_free_services'} if budget['cost_limit']==0 else 'unknown',
        'randomness': 'temperature=0.2, no seed/provider weight revision available; not bitwise reproducible',
        'packages': {p: importlib.metadata.version(p) for p in ('langchain', 'langgraph', 'langchain-openai',
                                                               'pysbd', 'pydantic', 'httpx', 'openai')}}
    from phase1_document_retrieval import load_documents
    write_json(out / 'run_manifest.json', manifest)
    runtime, evidence, embeddings = None, None, None
    try:
        docs = load_documents(corpus_root, ids) if request.source_mode != 'web_only' else []
        corpus = [{'id': d.document_id, 'file_sha256': d.file_sha256,
                   'normalized_text_sha256': d.sha256} for d in docs]
        if frozen is not None and sorted(corpus,key=lambda d:d['id']) != sorted(frozen['corpus'],key=lambda d:d['id']):
            raise ValueError('Corpus bytes differ from frozen evidence inputs')
        if uploaded_evidence is not None and sorted(corpus,key=lambda d:d['id'])!=sorted(uploaded_evidence['corpus'],key=lambda d:d['id']):
            raise ValueError('Corpus differs from frozen upload subset')
        write_json(out / 'corpus_manifest.json', corpus)
        manifest['corpus_sha256'] = digest(json.dumps(corpus, sort_keys=True).encode())
        if docs:
            inputs = out / 'inputs'; inputs.mkdir()
            for doc in docs:
                (inputs / Path(doc.path).name).write_bytes(Path(doc.path).read_bytes())
            corpus_root = inputs
        write_json(out / 'run_manifest.json', manifest)
        if fake_model is None:
            load_project_environment()
            selected_provider = provider_settings()
            manifest.update(model=selected_provider['model'], provider=selected_provider,
                randomness={'temperature': 0.2, 'seed': None,
                            'model_options': selected_provider['extra_body']})
            if selected_provider['kind'] == 'tokenhub_openai':
                manifest['cost'] = {'amount': None, 'basis': 'TokenHub billing not measured; token usage recorded'}
            if config.get('expected_model'):
                if selected_provider['model'] != config['expected_model']:
                    raise ValueError('Configured model differs from frozen model')
            if request.source_mode != 'web_only' and frozen is None and uploaded_evidence is None:
                from embedding_adapter import CachedEmbeddings
                embeddings = CachedEmbeddings(root / 'artifacts/cache/bge_m3.json',
                    max_calls=budget['embedding_calls'], max_input_chars=budget['embedding_input_chars'])
        runtime, evidence = assemble(out, request, corpus_root, ids, config.get('queries'),
            embeddings, budget, model=fake_model, web_replay=web_replay, frozen_evidence=frozen, length_control=length_control,calculation_control=calculation_control,report_validation=report_validation,web_period_scope=web_period_scope,web_period_filter=web_period_filter,web_acquisition=web_acquisition,uploaded_evidence=uploaded_evidence,financial_period_scope=financial_period_scope,financial_period_filter=financial_period_filter,sec_fact_limit=sec_fact_limit,evidence_workspace=evidence_workspace,quote_binding=quote_binding,quote_rows=quote_rows)
        manifest['package_fingerprint'] = runtime.package.fingerprint
        manifest['execution_identity'] = runtime.execution_identity
        write_json(out / 'run_manifest.json', manifest)
        input_request = agent_input(request, length_control=length_control)
        if frozen is not None:
            # Reuse the task input contract; explain replay tool names to the
            # model without adding any evidence from forbidden source classes.
            from autoresearch_agent_core import MessageRecord
            from dataclasses import replace
            payload = json.loads(input_request.messages[0].content)
            payload['input_mode'] = 'immutable_evidence_replay'
            payload['source_requirements'] = ('Call the permitted retrieve_* tools and cite every required source class in the body. '
                'retrieve_web_documents returns frozen opened web text; no live search is needed.')
            input_request = input_request.model_copy(update={'messages':(MessageRecord(role='user', content=json.dumps(payload)),)})
            write_json(out / 'frozen_evidence.json', frozen)
        write_json(out / 'agent_input.json', input_request.model_dump(mode='json'))
        output = await runtime.arun(input_request, run_id='execution')
        write_json(out / 'runtime_output.json', output.model_dump(mode='json'))
        trajectory = [e.model_dump(mode='json') for e in output.trajectory]
        (out / 'trajectory.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in trajectory))
        (out / 'final_answer.md').write_text(output.final_answer or '')
        report = (out / 'raw_report.md').read_text()
        package = {'required_headings': list(required_headings(request.structure)),
                   'sources': evidence.sources}
        finish = next((e.data.get('provider_response', {}).get('finish_reason')
                       for e in reversed(output.trajectory) if e.type == 'model_completed'), None)
        checks = check_report(report, package, finish)
        latest_reason, generation_reason = None, None
        for event in output.trajectory:
            if event.type == 'model_completed':
                latest_reason = event.data.get('provider_response', {}).get('finish_reason')
            elif event.type == 'tool_requested':
                call = event.data.get('tool_call', {})
                if call.get('name') == 'write_file':
                    generation_reason = latest_reason
        checks['report_generation_finish_reason'] = generation_reason
        if generation_reason == 'length':
            checks['mechanical_checks_passed'] = False
        body_ids = set(re.findall(r'\[S\d+\]', re.split(r'^#{1,2}[ \t]+Sources[ \t]*$', report,
                                                      maxsplit=1, flags=re.M)[0]))
        cited = [s for s in evidence.sources if s['citation'] in body_ids]
        kinds = {s['source_kind'] for s in cited}
        mode_pass = (kinds == {'uploaded', 'web'} if request.source_mode == 'hybrid' else
                     kinds == ({'web'} if request.source_mode == 'web_only' else {'uploaded'}))
        custom = check_customization(report, request)
        gate_state = (evidence.context.metadata or {}).get('_report_gate', {}) if evidence.context else {}
        report_current = bool(gate_state.get('report_content')) and not gate_state.get('report_invalidated')
        coverage = not docs or {d.document_id for d in docs} <= {s['document_id'] for s in cited}
        audit = {'automatic': checks, 'customization': custom,
                 'structured_validation': evidence.validation_checks[-1] if evidence.validation_checks else {'performed':False},
                 'selected_documents': [d.document_id for d in docs],
                 'body_cited_source_kinds': sorted(kinds), 'source_mode_passed': mode_pass,
                 'selected_document_body_coverage': coverage,
                 'report_current': report_current,
                 'assistant_development_review': 'not_performed', 'actual_human_review': 'pending',
                 'factual_support_validated': False}
        audit['automatic_passed'] = bool(report) and output.status == 'succeeded' and all((
            checks['mechanical_checks_passed'], custom['passed'], mode_pass, coverage, report_current))
        if report_validation=='enforce':
            audit['automatic_passed'] = audit['automatic_passed'] and bool(evidence.validation_checks) and evidence.validation_checks[-1]['passed']
        write_json(out / 'audit.json', audit)
        # Formatting is for display only; all checks above use saved raw output.
        (out / 'report.md').write_text(render_report_sources(report, evidence.sources) if report else '')
        manifest.update(**delivery_outcome(output.status,output.terminal.error_code,report,audit['automatic_passed'],
                source_count=len(evidence.sources),validation_checks=evidence.validation_checks),
            report_status='automatic_passed' if audit['automatic_passed'] else 'invalid_or_incomplete',
            automatic_passed=audit['automatic_passed'], usage=output.usage.model_dump() if output.usage else None,
            model_calls=len(json.loads((out/'provider_attempts.json').read_text())) if (out/'provider_attempts.json').exists() else 0,
            model_completed_calls=sum(e.type == 'model_completed' for e in output.trajectory),
            tool_calls=len(output.tool_calls), raw_report_sha256=digest(report.encode()))
    except Exception as exc:
        manifest.update(status='failed', error_type=type(exc).__name__)
        # Exceptions can contain HTTP URLs/headers. Keep type; native runtime has
        # its own sanitized failure record when execution reached the loop.
        if not (out / 'trajectory.jsonl').exists():
            (out / 'trajectory.jsonl').write_text(json.dumps({'type': 'setup_failed',
                                                           'error_type': type(exc).__name__})+'\n')
        raise
    finally:
        if runtime:
            await runtime.aclose()
        manifest.update(elapsed_seconds=round(time.perf_counter()-started, 3),
            embedding_calls=embeddings.calls if embeddings else 0,
            embedding_usage=embeddings.usage if embeddings else [],
            report_path=str(out / 'report.md'))
        write_json(out / 'run_manifest.json', manifest)
        print(json.dumps({'run_dir': str(out), 'status': manifest['status'],
                          'automatic_passed': manifest.get('automatic_passed')}))
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--output-dir', type=Path, help='New output directory; existing directories are rejected')
    args = parser.parse_args()
    asyncio.run(run(json.loads(args.config.read_text()), out=args.output_dir))


if __name__ == '__main__':
    main()
