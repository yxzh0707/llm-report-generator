"""Run the installed, unmodified Hermes in a fresh task profile.

Only credentials are inherited from the existing dissertation environment.
The user's normal Hermes profile, memories and model settings are not loaded.
"""
import json,os,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HERMES=Path(os.environ.get('HERMES_SOURCE', str(Path.home()/'.hermes/hermes-agent'))).expanduser()
def main():
    out=Path(sys.argv[1]).resolve()
    sys.path.insert(0,str(ROOT/'src'))
    from runtime_config import load_project_environment,provider_settings
    load_project_environment();settings=provider_settings()
    assert settings['model']=='Qwen3.8-27B'
    workspace=out/'workspace';workspace.mkdir(exist_ok=True)
    profile=out/'profile';profile.mkdir(exist_ok=True)
    os.environ['HERMES_HOME']=str(profile)
    os.environ['TERMINAL_CWD']=str(workspace)
    # Configuration uses the official profile mechanism; no global config edit.
    import yaml
    (profile/'config.yaml').write_text(yaml.safe_dump({
        'model':{'default':settings['model'],'provider':'custom','base_url':settings['base_url']},
        'terminal':{'backend':'local','cwd':str(workspace),'timeout':60},
        'compression':{'enabled':False},'memory':{'memory_enabled':False,'user_profile_enabled':False},
        'agent':{'max_turns':16}}))
    os.chdir(workspace);sys.path.insert(0,str(HERMES))
    from run_agent import AIAgent
    agent=AIAgent(model=settings['model'],base_url=settings['base_url'],
        api_key=os.getenv(settings['api_key_env']) or 'local',provider='custom',api_mode='chat_completions',
        max_iterations=16,max_tokens=12000,enabled_toolsets=['terminal','file','todo'],
        request_overrides={'temperature':0.2,'extra_body':settings['extra_body']},
        skip_context_files=True,skip_memory=True,load_soul_identity=False,
        save_trajectories=True,quiet_mode=True,session_id=out.name)
    (out/'tool_schemas.json').write_text(json.dumps(agent.tools,ensure_ascii=False,indent=2,default=str))
    start=time.monotonic()
    result=agent.run_conversation(json.dumps(json.loads((out/'agent_input.json').read_text()),ensure_ascii=False))
    (out/'hermes_output.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str))
    usage={k:getattr(agent,k,None) for k in ['session_total_tokens','session_prompt_tokens','session_completion_tokens','session_api_calls']}
    (out/'hermes_usage.json').write_text(json.dumps({'elapsed_seconds':time.monotonic()-start,**usage},indent=2))
    report_path=workspace/'work/outputs/final_report.md'
    report=report_path.read_text() if report_path.exists() else ''
    final=result.get('final_response') or ''
    (out/'final_answer.md').write_text(final)
    if not report.strip() and len(final.split())>80:report=final
    (out/'evaluated_report.md').write_text(report)

if __name__=='__main__':main()
