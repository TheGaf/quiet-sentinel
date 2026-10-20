"""Small, auditable event processing pipeline for quiet infrastructure alerts."""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from collections import deque
from typing import Optional
import json
import os
import statistics
import urllib.request
import urllib.error


@dataclass
class Event:
    host: str
    metric: str
    value: float
    at: str


class Sentinel:
    def __init__(self, window=12, threshold=3.0, cooldown=900, model='qwen2.5:3b', ollama_url='http://127.0.0.1:11434', provider='ollama'):
        if provider not in ("ollama", "openai"):
            raise ValueError("Unsupported AI provider")
        self.provider = provider
        self.ai_status = "not_tested"
        self.window = window
        self.threshold = threshold
        self.cooldown = cooldown
        self.model = model
        self.ollama_url = ollama_url.rstrip('/')
        self.history = {}
        self.last_alert = {}
        self.events = deque(maxlen=200)
        self.alerts = deque(maxlen=100)

    def observe(self, host, metric, value, at=None, use_ai=False):
        at = at or datetime.now(timezone.utc).isoformat()
        event = Event(str(host), str(metric), float(value), at)
        key = (event.host, event.metric)
        h = self.history.setdefault(key, deque(maxlen=self.window))
        baseline = list(h)
        h.append(event.value)
        self.events.append(asdict(event))
        if len(baseline) < 5:
            return {'state': 'learning', 'samples': len(h)}
        center = statistics.median(baseline)
        deviations = [abs(x-center) for x in baseline]
        mad = statistics.median(deviations)
        scale = max(1.4826 * mad, abs(center) * 0.03, 0.01)
        score = abs(event.value-center)/scale
        if score < self.threshold or (event.metric == 'cpu_percent' and abs(event.value - center) < 15):
            return {'state': 'normal', 'score': round(score, 2)}
        try:
            ts = datetime.fromisoformat(at.replace('Z', '+00:00')).timestamp()
        except ValueError:
            ts = datetime.now(timezone.utc).timestamp()
        previous = self.last_alert.get(key, -float('inf'))
        if ts - previous < self.cooldown:
            return {'state': 'suppressed', 'score': round(score,2), 'cooldown_seconds': self.cooldown}
        self.last_alert[key] = ts
        message = f'{event.host}: {event.metric} is {event.value:g} (baseline {center:g}; anomaly score {score:.1f}).'
        assessment = self.assess(event, baseline, message) if use_ai else None
        alert = {'event': asdict(event), 'score': round(score, 2), 'baseline': round(center,3), 'message': message, 'ai_assessment': assessment}
        self.alerts.appendleft(alert)
        return {'state': 'alert', 'alert': alert}

    def assess(self, event, baseline, message):
        """Explain alerts through the configured provider; keys never leave the server."""
        prompt = ("You triage server monitoring anomalies. Return exactly one short sentence "
                  "describing likely impact and ONE safe verification step. Do not suggest "
                  "destructive commands. Say uncertain if evidence is insufficient.\n"
                  f"Observation: {message}\nPrevious readings: {baseline[-8:]}")
        headers = {'Content-Type': 'application/json'}
        if self.provider == 'openai':
            key = os.getenv('OPENAI_API_KEY', '')
            if not key:
                self.ai_status = 'missing_key'
                return 'AI unavailable: OpenAI key is not configured. Monitoring continues.'
            headers['Authorization'] = 'Bearer ' + key
            url = 'https://api.openai.com/v1/responses'
            body = {'model': self.model, 'input': prompt, 'max_output_tokens': 200, 'store': False}
        else:
            url = self.ollama_url + '/api/generate'
            body = {'model': self.model, 'prompt': prompt, 'stream': False,
                    'options': {'temperature': 0.1, 'num_predict': 120}}
        request = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                result = json.load(response)
            if self.provider == 'openai':
                text = ' '.join(part.get('text', '') for item in result.get('output', [])
                                if item.get('type') == 'message' for part in item.get('content', [])
                                if part.get('type') == 'output_text')
            else:
                text = str(result.get('response', ''))
            if not text.strip():
                raise ValueError('Empty explanation')
            self.ai_status = 'connected'
            return text.strip()[:350]
        except urllib.error.HTTPError as error:
            self.ai_status = 'http_' + str(error.code)
        except (OSError, ValueError, TimeoutError):
            self.ai_status = 'unavailable'
        return 'AI unavailable (' + self.ai_status + '). Monitoring continues; inspect the metric and system logs.'

    def snapshot(self):
        return {'events': list(self.events)[-40:], 'alerts': list(self.alerts),
                'monitored_series': len(self.history), 'model': self.model,
                'ai_provider': self.provider, 'ai_status': self.ai_status}
