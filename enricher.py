import os
import subprocess
import tempfile
import json
import time
from beets.plugins import BeetsPlugin
from beets import ui

class LLMProvider:
    """Base class for LLM providers."""
    def analyze(self, audio_path, samples, model_name):
        raise NotImplementedError

class GeminiProvider(LLMProvider):
    """Google Gemini Provider (Multimodal Audio)."""
    def __init__(self, config):
        from google import genai
        self.config = config
        if config['use_vertex'].get(bool):
            self.client = genai.Client(vertexai=True, project=config['project'].get(), location=config['location'].get())
        else:
            self.client = genai.Client(api_key=config['api_key'].get())

    def analyze(self, audio_path, samples, model_name):
        from google.genai import types
        mapping = "\n".join([f"Clip {i+1}: Sample from {int(s)}s" for i, (s, d) in enumerate(samples)])
        prompt = f"Analyze these audio clips.\n{mapping}\nProvide MIR Standard, AudioSet Taxonomy, and a one-sentence Temporal Narrative. Return JSON with keys: mir_standard, audioset_taxonomy, temporal_narrative."
        
        audio_file = self.client.files.upload(path=audio_path)
        while audio_file.state == 'PROCESSING':
            time.sleep(1)
            audio_file = self.client.files.get(name=audio_file.name)
        
        response = self.client.models.generate_content(
            model=model_name,
            contents=[types.Content(role="user", parts=[types.Part.from_uri(file_uri=audio_file.uri, mime_type="audio/mp3"), types.Part.from_text(text=prompt)])],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        self.client.files.delete(name=audio_file.name)
        return json.loads(response.text)

class OllamaProvider(LLMProvider):
    """Ollama Provider (Local LLM). 
    Note: Requires a multimodal model like 'minicpm-v' or a text-only workflow with transcription.
    """
    def __init__(self, config):
        import requests
        self.config = config
        self.url = config['ollama_url'].get() or "http://localhost:11434/api/generate"

    def analyze(self, audio_path, samples, model_name):
        # Implementation for Local LLMs (e.g., using a Whisper/VLM pipeline)
        # This is a stub for future local audio-capable models
        return {
            "mir_standard": "Local analysis pending",
            "audioset_taxonomy": "Local analysis pending",
            "temporal_narrative": "Ollama provider connected but local audio analysis requires a multimodal model."
        }

class EnricherPlugin(BeetsPlugin):
    def __init__(self):
        super(EnricherPlugin, self).__init__()
        self.config.add({
            'provider': 'gemini',
            'model': 'gemini-1.5-pro',
            'api_key': os.environ.get('GEMINI_API_KEY', ''),
            'use_vertex': False,
            'project': os.environ.get('GOOGLE_CLOUD_PROJECT', ''),
            'location': 'us-central1',
            'ollama_url': 'http://localhost:11434/api/generate',
            'auto': True
        })
        
        self.provider = self._get_provider()
        if self.config['auto'].get(bool):
            self.register_listener('item_imported', self._on_item_imported)

    def _get_provider(self):
        p_name = self.config['provider'].get()
        if p_name == 'gemini':
            return GeminiProvider(self.config)
        elif p_name == 'ollama':
            return OllamaProvider(self.config)
        return None

    def _on_item_imported(self, lib, item):
        try:
            self._enrich_item(item)
        except Exception as e:
            self._log.error(f"Enrichment failed: {e}")

    def commands(self):
        cmd = ui.Subcommand('enrich', help='enrich tracks')
        cmd.func = lambda lib, opts, args: [self._enrich_item(i) for i in lib.items(ui.decargs(args))]
        return [cmd]

    def _enrich_item(self, item):
        if not item.length: return
        samples = self._get_sample_rules(item.length)
        with tempfile.NamedTemporaryFile(suffix='.mp3', dir='/tmp/beets', delete=False) as tmp:
            tmp_path = tmp.name
        try:
            self._extract_samples(item.path.decode('utf-8'), samples, tmp_path)
            analysis = self.provider.analyze(tmp_path, samples, self.config['model'].get())
            item.ai_summary = json.dumps(analysis)
            summary = f"MIR: {analysis.get('mir_standard')}\nAudioSet: {analysis.get('audioset_taxonomy')}\nNarrative: {analysis.get('temporal_narrative')}"
            item.comments = f"{item.comments}\n\n[AI Analysis]\n{summary}" if item.comments else f"[AI Analysis]\n{summary}"
            item.store()
            item.write()
        finally:
            if os.path.exists(tmp_path): os.remove(tmp_path)

    def _get_sample_rules(self, duration):
        if duration < 300: return [(duration/2-15, 30)]
        elif duration < 600: return [(duration*0.25, 20), (duration*0.75, 20)]
        else: return [(duration*0.05, 15), (duration*0.25, 15), (duration*0.5, 15), (duration*0.85, 15)]

    def _extract_samples(self, input_path, samples, output_path):
        f = "".join([f"[0:a]atrim=start={s}:duration={d},asetpts=PTS-STARTPTS[a{i}];" for i, (s, d) in enumerate(samples)])
        f += "".join([f"[a{i}]" for i in range(len(samples))]) + f"concat=n={len(samples)}:v=0:a=1[outa]"
        subprocess.run(['ffmpeg', '-y', '-i', input_path, '-filter_complex', f, '-map', '[outa]', '-acodec', 'libmp3lame', '-b:a', '128k', output_path], capture_output=True, check=True)
