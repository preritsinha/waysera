#!/usr/bin/env python3
"""Rebuild the source-evidenced Waysera artifact graph using Python's stdlib.

Run from any directory. No application code is executed and no network is used.
Inventories existing tracked/nonignored files, excluding this tool and its output.
This is a conservative file/reference graph, not a complete JavaScript call graph.
"""
from __future__ import annotations

import ast
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/knowledge-graph'
EXCLUDE = ('docs/knowledge-graph/', 'tools/build_knowledge_graph.py')
nodes, edges, edge_keys, unresolved = {}, [], set(), []


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args]).decode().strip()


def node(ident, label=None, kind='file', **kwargs):
    nodes.setdefault(ident, dict(id=ident, label=label or ident, kind=kind, **kwargs))
    return ident


def edge(source, target, relation, file=None, line=None, basis='source', detail=''):
    assert source in nodes, source
    assert target in nodes, target
    key = (source, target, relation)
    ev = dict(file=file, line=line) if file else None
    if key in edge_keys:
        existing = next(e for e in edges if (e['source'], e['target'], e['relation']) == key)
        if ev and ev not in existing['evidence']:
            existing['evidence'].append(ev)
        return
    edge_keys.add(key)
    edges.append(dict(source=source, target=target, relation=relation,
                      evidence=[ev] if ev else [], basis=basis, detail=detail))


def group_for(path):
    if '/src/main/res/' in path: return 'Android resources'
    if '/assets/vendor/' in path: return 'Bundled map assets'
    if '/assets/brand/' in path: return 'Brand assets'
    if path.startswith('android_app/www/'): return 'Android client'
    if path.startswith('android_app/android/'): return 'Android native project'
    if path.startswith('android_app/'): return 'Android build'
    if '/tests/' in path or path.startswith('web/tools/') or '/tests.' in path: return 'Tests and harnesses'
    if path.startswith('web/frontend/'): return 'Web client'
    if path.endswith(('.py', '.ini')) and path.startswith('web/backend/'): return 'Relay server'
    if path.startswith('web/'): return 'Web operations'
    return 'Project documentation'


def fid(path): return 'file:' + path


def line_of(path, anchor):
    for i, line in enumerate(texts.get(path, '').splitlines(), 1):
        if anchor in line: return i
    raise ValueError(f'Missing evidence anchor {path}: {anchor}')


files = sorted(p for p in set(git('ls-files', '-z', '--cached', '--others', '--exclude-standard').split('\0'))
               if p and not p.startswith(EXCLUDE) and (ROOT / p).is_file())
tracked = set(git('ls-files', '-z').split('\0'))
texts = {}
project = node('project:waysera', 'Waysera', 'group')
for p in files:
    data = (ROOT / p).read_bytes()
    try:
        if b'\0' not in data and len(data) < 1_000_000:
            texts[p] = data.decode('utf-8')
    except UnicodeDecodeError: pass
    group = group_for(p)
    gid = node('group:' + group, group, 'group')
    edge(gid, project, 'belongs_to', basis='inventory')
    node(fid(p), Path(p).name, path=p, group=group, bytes=len(data),
         sha256=hashlib.sha256(data).hexdigest(), tracked=p in tracked)
    edge(fid(p), gid, 'belongs_to', basis='inventory', detail='Inventory grouping only; does not imply a runtime dependency.')


def resolve_ref(source, value, relation, line):
    value = value.split('#')[0].split('?')[0]
    if not value or value.startswith(('data:', 'mailto:', 'javascript:', '#')): return
    if value.startswith(('https://', 'http://', '//')):
        target = node('url:' + value, value, 'service')
        edge(fid(source), target, relation, source, line)
        return
    if '${' in value or '{{' in value: return
    base = ROOT / Path(source).parent
    if source.endswith('.js') and (value.startswith('assets/') or value.endswith('.html')):
        base = ROOT / ('android_app/www' if source.startswith('android_app/www/') else 'web/frontend')
    try: path = (base / value).resolve().relative_to(ROOT).as_posix()
    except ValueError: return
    if path in files:
        edge(fid(source), fid(path), relation, source, line)
    else:
        unresolved.append(dict(file=source, line=line, reference=value, resolved_path=path))


class PageRefs(HTMLParser):
    def __init__(self, path):
        super().__init__(); self.path = path; self.scripts = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'img', 'source') and 'src' in attrs:
            rel = 'loads_script' if tag == 'script' else 'loads_asset'
            resolve_ref(self.path, attrs['src'], rel, self.getpos()[0])
            if tag == 'script': self.scripts.append(attrs['src'])
        if tag in ('a', 'link') and 'href' in attrs:
            resolve_ref(self.path, attrs['href'], 'navigates_to' if tag == 'a' else 'loads_asset', self.getpos()[0])


symbols = {
    'WayseraCrypto': 'crypto.js', 'WayseraJourney': 'journey.js',
    'WayseraValidate': 'validate.js', 'WayseraStore': 'store.js',
    'WayseraSearch': 'search.js', 'WayseraExport': 'export.js',
    'WayseraReplayInternals': 'replay.js', 'WAYSERA_CONFIG': 'config.js',
    'CONFIG': 'app.js', 'showError': 'app.js', 'haversineDistance': 'app.js',
    'copyToClipboard': 'app.js', 'selectDestination': 'index.js',
    'updateLocation': 'index.js', 'startLocationTracking': 'index.js',
    'stopLocationTracking': 'index.js', 'publishPosition': 'index.js',
}
for p, body in texts.items():
    if p.endswith('.html'):
        parser = PageRefs(p); parser.feed(body)
        nodes[fid(p)]['script_order'] = parser.scripts
    if p.endswith('.py'):
        try: tree = ast.parse(body)
        except SyntaxError: continue
        for item in ast.walk(tree):
            if not isinstance(item, ast.ImportFrom) or not item.module: continue
            candidates = ['web/backend/' + item.module.replace('.', '/') + '.py',
                          str(Path(p).parent / (item.module.replace('.', '/') + '.py'))]
            for target in dict.fromkeys(candidates):
                if target in files and p != target:
                    edge(fid(p), fid(target), 'imports', p, item.lineno)
    if ('/vendor/' in p and not p.endswith('.css')) or p.endswith('package-lock.json'): continue
    for n, line in enumerate(body.splitlines(), 1):
        # References are lexical, not an assertion that this line executes.
        if p.endswith('.js') and not line.strip().startswith(('//', '/*', '*')):
            prefix = 'android_app/www/assets/' if p.startswith('android_app/www/') else 'web/frontend/assets/'
            for symbol, name in symbols.items():
                target = prefix + name
                if target != p and target in files and re.search(r'\b' + symbol + r'\b', line):
                    edge(fid(p), fid(target), 'uses_global', p, n,
                         basis='lexical-reference', detail='Named global reference; classic script order supplies the dependency.')
            for ref in re.findall(r'''["'`](assets/[\w./-]+|replay\.html[^"'`]*|index\.html)["'`]''', line):
                resolve_ref(p, ref, 'navigates_to' if '.html' in ref else 'references_asset', n)
        if p.endswith('.css'):
            for ref in re.findall(r'''url\(["']?([^)'"\s]+)''', line): resolve_ref(p, ref, 'loads_asset', n)
        if p.endswith('.md'):
            for ref in re.findall(r'\]\(([^)\s]+)\)', line): resolve_ref(p, ref, 'documents_link', n)
        if p.endswith(('.xml', '.gradle')) and p.startswith('android_app/android/'):
            for typ, name in re.findall(r'@(drawable|mipmap|layout|xml|string|style|color)/([\w.]+)', line):
                for target, target_body in texts.items():
                    match_file = f'/res/{typ}' in target and Path(target).stem == name
                    match_value = '/res/values/' in target and re.search(r'name=["\']' + re.escape(name) + r'["\']', target_body)
                    if (match_file or match_value) and target != p:
                        edge(fid(p), fid(target), 'references_resource', p, n)
                # Binary PNG variants are also distinct inventory artifacts.
                for target in files:
                    if target not in texts and f'/res/{typ}' in target and Path(target).stem == name:
                        edge(fid(p), fid(target), 'references_resource', p, n)

# Exact mirrored-path comparison. Direction indicates correspondence only.
mirrors = []
for p in files:
    if not p.startswith('web/frontend/'): continue
    other = p.replace('web/frontend/', 'android_app/www/', 1)
    if other not in files: continue
    same = nodes[fid(p)]['sha256'] == nodes[fid(other)]['sha256']
    relation = 'identical_to' if same else 'diverges_from'
    edge(fid(p), fid(other), relation, basis='sha256-comparison',
         detail='Independent source trees; equality does not imply automatic synchronization.')
    mirrors.append(dict(web=p, android=other, identical=same))

# Semantic edges retain an exact source anchor and resolve its current line.
semantic = json.loads((OUT / 'relationships.json').read_text())
for item in semantic['nodes']:
    node(item['id'], item['label'], item['kind'], summary=item.get('summary', ''))
# Declared packages are not automatically runtime usage.
package = 'android_app/package.json'
pkg = json.loads(texts[package])
for section in ('dependencies', 'devDependencies'):
    for name, version in pkg.get(section, {}).items():
        target = node('package:' + name, name, 'package', version=version)
        edge(fid(package), target, 'declares_dev_dependency' if section == 'devDependencies' else 'declares_dependency',
             package, line_of(package, '"' + name + '"'))
        native_settings = 'android_app/android/capacitor.settings.gradle'
        for n, line in enumerate(texts[native_settings].splitlines(), 1):
            if '../node_modules/' + name + '/' in line:
                edge(fid(native_settings), target, 'links_native_package', native_settings, n)
for p in ('web/backend/requirements.txt', 'web/backend/requirements-dev.txt'):
    for n, line in enumerate(texts[p].splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'): continue
        if line.startswith('-r '): resolve_ref(p, line[3:], 'includes_requirements', n); continue
        name = re.split(r'[<>=!~\[]', line)[0]
        target = node('package:python:' + name, name, 'package', requirement=line)
        edge(fid(p), target, 'declares_dependency', p, n)

for item in semantic['edges']:
    edge(item['source'], item['target'], item['relation'], item['file'],
         line_of(item['file'], item['anchor']), basis=item.get('basis', 'source'), detail=item.get('detail', ''))

# Validate integrity and inventory coverage before writing artifacts.
for e in edges:
    assert e['source'] in nodes and e['target'] in nodes
    for ev in e['evidence']:
        assert ev['file'] in texts and 1 <= ev['line'] <= len(texts[ev['file']].splitlines())
assert sum(n['kind'] == 'file' for n in nodes.values()) == len(files)
semantic_counts = {fid(p): 0 for p in files}
for e in edges:
    if e['relation'] == 'belongs_to': continue
    for ident in (e['source'], e['target']):
        if ident in semantic_counts: semantic_counts[ident] += 1
inventory_only = [p for p in files if semantic_counts[fid(p)] == 0]
graph = dict(schema_version=1, metadata=dict(
    project='Waysera', commit=git('rev-parse', 'HEAD'), branch=git('branch', '--show-current'),
    snapshot='Current working files, including uncommitted edits and nonignored additions.',
    scope='Existing tracked and nonignored files. Excludes graph documentation/tool itself and deleted paths. Current Git ignore rules omit local dependencies, builds, caches, environment files, blog drafts and screenshots. Tracked files remain included regardless of ignore rules; this is not content-based secret detection.',
    limitations='Static file references and reviewed semantic edges; not a complete call graph, runtime trace, security audit, or live deployment verification. Structural edges indicate grouping only. Package declarations do not establish usage.',
    file_count=len(files), node_count=len(nodes), edge_count=len(edges),
    inventory_only_files=inventory_only, unresolved_references=unresolved, mirrors=mirrors),
    nodes=sorted(nodes.values(), key=lambda x: x['id']),
    edges=sorted(edges, key=lambda x: (x['source'], x['relation'], x['target'])))
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'graph.json').write_text(json.dumps(graph, indent=2) + '\n')
rows = ['# Artifact inventory', '', f"{len(files)} files · {len(nodes)} nodes · {len(edges)} relationships.", '',
        'Every in-scope file appears below. Connection counts exclude structural grouping. A zero is an explicit absence of a discovered semantic relationship, not a claim that the file is unused.', '',
        '| Artifact | Group | Connections | Worktree |', '| --- | --- | ---: | --- |']
for p in files:
    rows.append(f'| [{p}](../../{p}) | {group_for(p)} | {semantic_counts[fid(p)]} | {"tracked" if p in tracked else "untracked"} |')
rows += ['', '## Client correspondence', '', '| Web artifact | Android counterpart | Comparison |', '| --- | --- | --- |']
for item in mirrors:
    rows.append(f'| [{item["web"]}](../../{item["web"]}) | [{item["android"]}](../../{item["android"]}) | {"Identical bytes" if item["identical"] else "Different bytes"} |')
rows += ['', '## Unresolved local references', '', 'These literal references did not resolve to an in-scope file. This records missing assets and scope limitations rather than silently dropping them.', '']
for item in unresolved:
    rows.append(f'- {item["file"]}:{item["line"]} → `{item["reference"]}` (resolved path: `{item["resolved_path"]}`)')
(OUT / 'artifacts.md').write_text('\n'.join(rows) + '\n')
template = OUT / 'explorer.template.html'
if template.exists():
    inline = json.dumps(graph, separators=(',', ':')).replace('<', '\\u003c')
    (OUT / 'index.html').write_text(template.read_text().replace('__GRAPH_JSON__', inline))
print(json.dumps({'files': len(files), 'nodes': len(nodes), 'edges': len(edges),
                  'inventory_only_files': inventory_only, 'identical_pairs': sum(m['identical'] for m in mirrors),
                  'divergent_pairs': sum(not m['identical'] for m in mirrors)}, indent=2))
