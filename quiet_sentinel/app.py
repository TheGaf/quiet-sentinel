"""Zero-third-party-dependency local web dashboard and API."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import json
import os
from .core import Sentinel

INDEX = (Path(__file__).resolve().parent / 'index.html').read_text(encoding='utf8')


def run(host='127.0.0.1', port=8765, use_ai=False, model=None, ollama_url=None, provider=None):
    sentinel = Sentinel(model=model or os.getenv('SENTINEL_MODEL', 'qwen2.5:3b'),
                        ollama_url=ollama_url or os.getenv('SENTINEL_OLLAMA_URL', 'http://127.0.0.1:11434'),
                        provider=provider or os.getenv('SENTINEL_PROVIDER', 'ollama'))

    class Handler(BaseHTTPRequestHandler):
        def send(self, status, body, content_type='application/json'):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Access-Control-Allow-Origin', 'http://127.0.0.1:'+str(port))
            self.end_headers()
            self.wfile.write(body if isinstance(body, bytes) else body.encode())

        def do_GET(self):
            if self.path == '/':
                return self.send(200, INDEX, 'text/html; charset=utf-8')
            if self.path == '/api/state':
                return self.send(200, json.dumps(sentinel.snapshot()))
            self.send(404, '{"error":"not_found"}')

        def do_POST(self):
            if self.path != '/api/observe':
                return self.send(404, '{"error":"not_found"}')
            try:
                size = int(self.headers.get('Content-Length', 0))
                if not 0 < size <= 8192:
                    raise ValueError('Payload must be <= 8192 bytes')
                obj = json.loads(self.rfile.read(size))
                if not isinstance(obj.get('host'), str) or not isinstance(obj.get('metric'), str):
                    raise ValueError('host and metric must be strings')
                val = float(obj['value'])
                if not -1e15 < val < 1e15:
                    raise ValueError('value out of range')
                result = sentinel.observe(obj['host'][:100], obj['metric'][:100], val, use_ai=use_ai)
                return self.send(200, json.dumps(result))
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as err:
                return self.send(400, json.dumps({'error': str(err)}))

    print(f'Quiet Sentinel running at http://{host}:{port} (AI={use_ai})', flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


def main():
    parser = argparse.ArgumentParser(description='Private infrastructure signal dashboard')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--ai', action='store_true', help='Enable local Ollama explanations for alerts')
    parser.add_argument('--model', default=None, help='Ollama model (or SENTINEL_MODEL)')
    parser.add_argument('--ollama-url', default=None, help='Ollama endpoint (or SENTINEL_OLLAMA_URL)')
    parser.add_argument('--provider', choices=['ollama', 'openai'], default=None)
    a = parser.parse_args()
    run(a.host, a.port, a.ai, a.model, a.ollama_url, a.provider)

if __name__ == '__main__':
    main()
