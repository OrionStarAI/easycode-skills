#!/usr/bin/env python3
"""Per-line voiceover through the EasyRouter gateway, assembled into one track.

Reads audio.voiceover.lines[] from plan.json (text and shot are authored with the copy, 'at' with
the storyboard), synthesises each line, measures the real duration, and assembles
assets/voice/voiceover.wav. Writes evidence/voiceover.json with a planSnippet to paste back into
the plan. The API key is read from the environment or a .env file; it is never written to output.
"""
import argparse
import base64
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

DEFAULT_BASE_URL = 'https://llm-endpoint.net/v1'
DEFAULT_MODEL = 'gemini-3.1-flash-tts-preview'
DEFAULT_VOICE = 'Aoede'
SAMPLE_RATE = 48000
TRANSPORTS = ['speech', 'chat', 'gemini']
VOICES = ('Zephyr Puck Charon Kore Fenrir Leda Orus Aoede Callirrhoe Autonoe Enceladus Iapetus '
          'Umbriel Algieba Despina Erinome Algenib Rasalgethi Laomedeia Achernar Alnilam Schedar '
          'Gacrux Pulcherrima Achird Zubenelgenubi Vindemiatrix Sadachbia Sadaltager Sulafat').split()


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def open_network():
    for name in ['https_proxy', 'HTTPS_PROXY', 'http_proxy', 'HTTP_PROXY', 'all_proxy', 'ALL_PROXY']:
        value = os.environ.get(name)
        if value:
            return build_opener(ProxyHandler({'http': value, 'https': value}))
    for port in (7890, 7897, 1087):
        try:
            connection = socket.create_connection(('127.0.0.1', port), timeout=1)
        except OSError:
            continue
        connection.close()
        proxy = 'http://127.0.0.1:%d' % port
        return build_opener(ProxyHandler({'http': proxy, 'https': proxy}))
    return build_opener()


def resolve_key(project):
    value = os.environ.get('EASYROUTER_API_KEY')
    if value:
        return value, 'env:EASYROUTER_API_KEY'
    candidates = [project / '.env', Path(__file__).resolve().parents[1] / '.env']
    for path in candidates:
        if not path.is_file():
            continue
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line.startswith('EASYROUTER_API_KEY='):
                found = line.split('=', 1)[1].strip().strip('"').strip("'")
                if found:
                    label = path.name if path.parent == project else 'skill-dir/.env'
                    return found, 'file:' + label
    raise ValueError('No EASYROUTER_API_KEY. Put it in the environment or in <video-dir>/.env; '
                     'request one at https://ezr.sh/ and never commit it.')


def call(opener, url, key, payload=None, timeout=120):
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    headers = {'Authorization': 'Bearer ' + key, 'x-api-key': key, 'Content-Type': 'application/json'}
    request = Request(url, data=data, headers=headers, method='POST' if data else 'GET')
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()
    except URLError as error:
        raise RuntimeError('Network error reaching %s: %s' % (url, error.reason))


def excerpt(body):
    return body[:300].decode('utf-8', 'replace')


def synthesize(opener, base, key, model, voice, text, transport):
    """Return (payload, kind) where kind is 'container' for encoded audio or 'pcm' for raw samples."""
    if transport == 'speech':
        status, body = call(opener, base + '/audio/speech', key,
                            {'model': model, 'input': text, 'voice': voice, 'response_format': 'wav'})
        if status != 200 or body[:1] == b'{':
            raise RuntimeError('audio/speech returned %s: %s' % (status, excerpt(body)))
        return body, 'container'
    if transport == 'chat':
        status, body = call(opener, base + '/chat/completions', key,
                            {'model': model, 'messages': [{'role': 'user', 'content': text}],
                             'modalities': ['audio'], 'audio': {'voice': voice, 'format': 'wav'}})
        if status != 200:
            raise RuntimeError('chat/completions returned %s: %s' % (status, excerpt(body)))
        payload = json.loads(body)
        choices = payload.get('choices') or []
        audio = (choices[0].get('message', {}).get('audio') or {}) if choices else {}
        if not audio.get('data'):
            raise RuntimeError('chat/completions returned no audio: ' + excerpt(body))
        return base64.b64decode(audio['data']), 'container'
    status, body = call(opener, '%s/v1beta/models/%s:generateContent' % (base, model), key,
                        {'contents': [{'role': 'user', 'parts': [{'text': text}]}],
                         'generationConfig': {'responseModalities': ['AUDIO'],
                                              'speechConfig': {'voiceConfig': {'prebuiltVoiceConfig': {'voiceName': voice}}}}})
    if status != 200:
        raise RuntimeError('generateContent returned %s: %s' % (status, excerpt(body)))
    payload = json.loads(body)
    candidates = payload.get('candidates') or []
    parts = (candidates[0].get('content', {}).get('parts') or []) if candidates else []
    inline = (parts[0].get('inlineData') or parts[0].get('inline_data') or {}) if parts else {}
    if not inline.get('data'):
        raise RuntimeError('generateContent returned no audio: ' + excerpt(body))
    return base64.b64decode(inline['data']), 'pcm'


def write_wav(payload, kind, target):
    with tempfile.TemporaryDirectory(prefix='voiceover-') as tmp:
        source = Path(tmp) / 'raw.bin'
        source.write_bytes(payload)
        for label in ([kind] if kind == 'container' else []) + ['pcm']:
            prefix = ['-f', 's16le', '-ar', '24000', '-ac', '1'] if label == 'pcm' else []
            result = subprocess.run(['ffmpeg', '-v', 'error', '-y', *prefix, '-i', str(source),
                                     '-ar', str(SAMPLE_RATE), '-ac', '1', '-c:a', 'pcm_s16le', str(target)],
                                    capture_output=True, text=True)
            if result.returncode == 0 and target.is_file() and target.stat().st_size > 1024:
                return
        raise RuntimeError('Could not decode the returned audio: ' + result.stderr.strip()[:300])


def duration_of(path):
    measured = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                               '-of', 'default=nw=1:nk=1', str(path)], capture_output=True, text=True, check=True)
    return float(measured.stdout.strip())


def assemble(lines, duration, target):
    args = ['ffmpeg', '-v', 'error', '-y']
    for line in lines:
        args += ['-i', str(line['path'])]
    filters = ['[%d:a]aresample=%d,adelay=%d:all=1[l%d]' % (index, SAMPLE_RATE, round(line['at'] * 1000), index)
               for index, line in enumerate(lines)]
    voices = ''.join('[l%d]' % index for index in range(len(lines)))
    filters.append(voices + 'amix=inputs=%d:normalize=0,apad,atrim=duration=%s[voice]' % (len(lines), duration))
    args += ['-filter_complex', ';'.join(filters), '-map', '[voice]', '-ar', str(SAMPLE_RATE), '-ac', '1',
             '-c:a', 'pcm_s16le', str(target)]
    subprocess.run(args, check=True, capture_output=True)


def plan_lines(plan):
    audio = plan.get('audio') if isinstance(plan.get('audio'), dict) else {}
    voiceover = audio.get('voiceover') if isinstance(audio.get('voiceover'), dict) else {}
    lines = voiceover.get('lines')
    if not isinstance(lines, list) or not lines:
        raise ValueError('plan.json has no audio.voiceover.lines; author one entry per spoken line '
                         'with shot, at and text before generating audio')
    return voiceover, lines


def check_authored_lines(lines, duration):
    for position, line in enumerate(lines, start=1):
        label = 'line %d' % position
        if not isinstance(line, dict):
            raise ValueError(label + ' must be an object')
        if not isinstance(line.get('text'), str) or not line['text'].strip():
            raise ValueError(label + ' needs the spoken text')
        if not isinstance(line.get('shot'), str) or not line['shot'].strip():
            raise ValueError(label + ' needs the shot it belongs to')
        if not finite(line.get('at')) or line['at'] < 0:
            raise ValueError(label + ' needs an authored start time in "at" seconds')
        if finite(duration) and line['at'] >= duration:
            raise ValueError(label + ' starts after the film ends')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=Path('plan.json'))
    parser.add_argument('--output', type=Path, help='Video project directory; defaults to the plan folder')
    parser.add_argument('--voice', help='Gemini prebuilt voice name, e.g. Aoede or Kore')
    parser.add_argument('--model', help='TTS model id; verify with --list-models instead of guessing')
    parser.add_argument('--base-url', help='EasyRouter OpenAI-compatible base URL')
    parser.add_argument('--transport', choices=['auto'] + TRANSPORTS, default='auto')
    parser.add_argument('--list-models', action='store_true', help='Print the gateway TTS model ids and exit')
    parser.add_argument('--force', action='store_true', help='Overwrite existing generated audio')
    args = parser.parse_args()

    project = (args.output or args.plan.resolve().parent).expanduser().resolve()
    try:
        key, key_source = resolve_key(project)
        opener = open_network()
        if args.list_models:
            base = (args.base_url or DEFAULT_BASE_URL).rstrip('/')
            status, body = call(opener, base + '/models', key)
            if status != 200:
                raise RuntimeError('/models returned %s: %s' % (status, excerpt(body)))
            ids = [item.get('id', '') for item in json.loads(body).get('data', []) if isinstance(item, dict)]
            matches = [model for model in ids if any(token in model.lower() for token in ['tts', 'speech', 'audio'])]
            print(json.dumps({'baseUrl': base, 'modelCount': len(ids), 'ttsCandidates': matches}, ensure_ascii=False, indent=2))
            return 0
        plan = json.loads(args.plan.read_text(encoding='utf-8'))
        duration = plan.get('duration')
        voiceover, lines = plan_lines(plan)
        check_authored_lines(lines, duration)
        base = (args.base_url or voiceover.get('endpoint') or DEFAULT_BASE_URL).rstrip('/')
        model = args.model or voiceover.get('model') or DEFAULT_MODEL
        voice = args.voice or voiceover.get('voice') or DEFAULT_VOICE
        if voice not in VOICES:
            print('Warning: %s is not a known Gemini prebuilt voice; the gateway will accept or reject it.' % voice,
                  file=sys.stderr)
        voice_dir = project / 'assets/voice'
        evidence_dir = project / 'evidence'
        voice_dir.mkdir(parents=True, exist_ok=True)
        evidence_dir.mkdir(parents=True, exist_ok=True)
        assembled = voice_dir / 'voiceover.wav'
        if not args.force and assembled.is_file():
            raise ValueError('%s exists; pass --force to regenerate, or delete it first' % assembled)
        transports = TRANSPORTS if args.transport == 'auto' else [args.transport]
        used_transport = None
        records = []
        for position, line in enumerate(lines, start=1):
            target = voice_dir / ('line-%02d.wav' % position)
            if target.is_file() and not args.force:
                raise ValueError('%s exists; pass --force to regenerate, or delete it first' % target)
            failures = []
            for transport in transports:
                try:
                    payload, kind = synthesize(opener, base, key, model, voice, line['text'], transport)
                except (RuntimeError, ValueError) as error:
                    failures.append('%s: %s' % (transport, error))
                    continue
                write_wav(payload, kind, target)
                used_transport = transport
                break
            else:
                raise RuntimeError('All transports failed for line %d:\n  %s' % (position, '\n  '.join(failures)))
            line_duration = duration_of(target)
            records.append({'index': position, 'shot': line['shot'], 'at': line['at'], 'duration': round(line_duration, 3),
                            'text': line['text'], 'textSha256': sha256_bytes(line['text'].encode('utf-8')),
                            'file': str(target.relative_to(project)), 'sha256': sha256_file(target),
                            'sampleRate': SAMPLE_RATE, 'path': target})
        warnings = []
        ordered = sorted(records, key=lambda item: item['at'])
        for previous, current in zip(ordered, ordered[1:]):
            if previous['at'] + previous['duration'] > current['at'] + 0.01:
                raise ValueError('Lines %d and %d overlap; move one "at" later' % (previous['index'], current['index']))
        for record in ordered:
            end = record['at'] + record['duration']
            if finite(duration) and end > duration + 0.05:
                warnings.append('Line %d ends at %.2fs, past the %.2fs film; shorten it or move it earlier'
                                % (record['index'], end, duration))
                print('Warning: ' + warnings[-1], file=sys.stderr)
        assemble(ordered, duration, assembled)
        for record in records:
            record.pop('path', None)
        snippet = {'file': str(assembled.relative_to(project)), 'gain': voiceover.get('gain', 1.0),
                   'provider': 'easyrouter', 'endpoint': base, 'model': model, 'voice': voice,
                   'duck': voiceover.get('duck', {'db': 6, 'attack': 0.15, 'release': 0.4}),
                   'lines': [{key: record[key] for key in ['shot', 'at', 'duration', 'text', 'file']} for record in records]}
        report = {'schema': 1, 'provider': 'easyrouter', 'endpoint': base, 'model': model, 'voice': voice,
                  'transport': used_transport, 'apiKeySource': key_source,
                  'generatedAt': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'lines': records,
                  'assembled': {'file': str(assembled.relative_to(project)), 'sha256': sha256_file(assembled),
                                'duration': round(duration_of(assembled), 3)},
                  'warnings': warnings, 'planSnippet': snippet,
                  'listeningStatus': 'Not auditioned by script; listen to each line and the assembled track.'}
        (evidence_dir / 'voiceover.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'project': str(project), 'lines': len(records), 'transport': used_transport,
                          'assembled': report['assembled'], 'planSnippet': snippet,
                          'next': 'Paste planSnippet into plan.json audio.voiceover, then mix and audition.'},
                         ensure_ascii=False, indent=2))
        return 0
    except (ValueError, RuntimeError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
