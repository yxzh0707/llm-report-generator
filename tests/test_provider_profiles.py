"""Credential isolation and request compatibility for selectable providers."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from runtime_config import load_project_environment, provider_settings
from llm_adapter import chat_completion


class ProviderProfiles(unittest.TestCase):
    def test_generator_and_judge_are_independent_even_in_same_process(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{},clear=True):
            root=Path(tmp)
            (root/'g.env').write_text('VLLM_API_KEY=generator-secret\n')
            (root/'j.env').write_text('ANTHROPIC_API_KEY=judge-secret\n')
            profile=root/'profile.env'
            profile.write_text('DISSERTATION_PROVIDER=vllm\nDISSERTATION_MODEL=Qwen3.8-27B\nROLLOUT_BASE_URL=https://qwen.example/v1\n'
                'DISSERTATION_CREDENTIALS_FILE=g.env\nDISSERTATION_CREDENTIALS_KEY=VLLM_API_KEY\n'
                'JUDGE_PROVIDER=tokenhub_openai\nJUDGE_MODEL=bailian/deepseek-v4-flash-0731\nJUDGE_BASE_URL=https://judge.example/v1\n'
                'JUDGE_CREDENTIALS_FILE=j.env\nJUDGE_CREDENTIALS_KEY=ANTHROPIC_API_KEY\n')
            os.environ['DISSERTATION_ENV_FILE']=str(profile)
            load_project_environment()
            generator=provider_settings()
            self.assertNotIn('JUDGE_API_KEY',os.environ)
            load_project_environment(role='judge')
            judge=provider_settings(role='judge')
            self.assertEqual(os.environ[generator['api_key_env']],'generator-secret')
            self.assertEqual(os.environ[judge['api_key_env']],'judge-secret')
            self.assertEqual(provider_settings(),generator)
            self.assertNotEqual(generator['base_url'],judge['base_url'])
            self.assertNotIn('chat_template_kwargs',judge['extra_body'])
            del os.environ['JUDGE_API_KEY']
            self.assertEqual(provider_settings(role='judge')['api_key_env'],'JUDGE_API_KEY')

    def test_ui_recognizes_selected_credential_and_unknown_tokenhub_cost(self):
        from report_server import ReportApp
        env={'DISSERTATION_PROVIDER':'tokenhub_openai',
             'ROLLOUT_BASE_URL':'https://tokenhub.example/v1', 'DISSERTATION_API_KEY':'fixture'}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,env,clear=True):
            app=ReportApp(Path(tmp))
            self.assertTrue(app.bootstrap()['services']['model'])
            self.assertIsNone(app.bootstrap()['budget']['cost_limit'])
            del os.environ['DISSERTATION_API_KEY']
            os.environ['VLLM_API_KEY']='stale'
            self.assertFalse(app.bootstrap()['services']['model'])

    def test_reference_credentials_and_tool_settings_do_not_override_model(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            root=Path(tmp)
            (root/'secret.env').write_text('ANTHROPIC_API_KEY="fixture-tokenhub-key"\nANTHROPIC_MODEL=other-model\n')
            (root/'tools.env').write_text('ROLLOUT_BASE_URL=https://wrong.example/v1\nVLLM_API_KEY=wrong-key\nSERPER_API_KEY=fixture-search\n')
            profile=root/'profile.env'
            profile.write_text('DISSERTATION_PROVIDER=tokenhub_openai\nDISSERTATION_MODEL=bailian/deepseek-v4-flash-0731\n'
                'ROLLOUT_BASE_URL=https://tokenhub.example/v1/chat/completions\n'
                'DISSERTATION_CREDENTIALS_FILE=secret.env\nDISSERTATION_CREDENTIALS_KEY=ANTHROPIC_API_KEY\n'
                f'DISSERTATION_TOOL_ENV_FILE={root / "tools.env"}\nDISSERTATION_THINKING=false\n')
            os.environ['DISSERTATION_ENV_FILE']=str(profile)
            load_project_environment()
            cfg=provider_settings()
            self.assertEqual(cfg['base_url'],'https://tokenhub.example/v1')
            self.assertEqual(os.environ[cfg['api_key_env']],'fixture-tokenhub-key')
            self.assertEqual(os.environ['SERPER_API_KEY'],'fixture-search')
            self.assertNotIn('VLLM_API_KEY',os.environ)
            self.assertNotIn('fixture-tokenhub-key',json.dumps(cfg))
            self.assertEqual(cfg['extra_body'],{'thinking':{'type':'disabled'},'enable_thinking':False})
            self.assertNotIn('chat_template_kwargs',cfg['extra_body'])

    def test_tokenhub_ignores_stale_vllm_key_and_rejects_invalid_settings(self):
        env={'DISSERTATION_PROVIDER':'tokenhub_openai','DISSERTATION_MODEL':'bailian/deepseek-v4-flash-0731',
             'ROLLOUT_BASE_URL':'https://tokenhub.example/v1','VLLM_API_KEY':'wrong','TOKENHUB_API_KEY':'right'}
        with patch.dict(os.environ,env,clear=True):
            self.assertEqual(provider_settings()['api_key_env'],'TOKENHUB_API_KEY')
            os.environ['DISSERTATION_THINKING']='maybe'
            with self.assertRaises(ValueError):provider_settings()
            os.environ['DISSERTATION_THINKING']='false'
            os.environ['ROLLOUT_BASE_URL']='https://user:password@example.com/v1'
            with self.assertRaises(ValueError):provider_settings()

    def test_legacy_profile_and_explicit_key_override(self):
        with patch.dict(os.environ,{'ROLLOUT_BASE_URL':'http://localhost:9000/v1','VLLM_API_KEY':'fixture'},clear=True):
            s=provider_settings()
            self.assertEqual(s['model'],'Qwen3.8-27B')
            self.assertEqual(s['kind'],'vllm')
            self.assertEqual(s['extra_body'],{'chat_template_kwargs':{'enable_thinking':False}})
            self.assertEqual(provider_settings(enable_thinking=True)['extra_body']['chat_template_kwargs']['enable_thinking'],True)

    def test_chat_adapter_sends_provider_specific_options_and_correct_key(self):
        env={'DISSERTATION_PROVIDER':'tokenhub_openai','DISSERTATION_MODEL':'bailian/deepseek-v4-flash-0731',
             'ROLLOUT_BASE_URL':'https://tokenhub.example/v1','VLLM_API_KEY':'wrong','DISSERTATION_API_KEY':'right'}
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return b'{"choices":[{"message":{"content":"OK"}}]}'
        with patch.dict(os.environ,env,clear=True), patch('llm_adapter.load_project_environment'), patch('urllib.request.urlopen',return_value=Response()) as send:
            chat_completion(system='Test',user='Hello')
            req=send.call_args.args[0];body=json.loads(req.data)
            self.assertEqual(req.get_header('Authorization'),'Bearer right')
            self.assertEqual(body['thinking'],{'type':'disabled'})
            self.assertFalse(body['enable_thinking'])
            self.assertNotIn('chat_template_kwargs',body)


if __name__=='__main__':unittest.main()
