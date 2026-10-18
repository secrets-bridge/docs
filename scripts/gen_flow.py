"""Generate includes/flow.html, the home page's 'follow a request' diagram.

Run: python3 scripts/gen_flow.py
The home page pulls the output in with a snippet (--8<--). Colours come
from CSS (brand.css / landing.css), so this file only holds geometry and words.
"""
import html
import math
import os

def arrowhead(x1, y1, x2, y2, size=8):
    # A filled triangle pointing from (x1,y1) to (x2,y2), tip at (x2,y2).
    a = math.atan2(y2 - y1, x2 - x1)
    l = (x2 - size * math.cos(a) + size * 0.5 * math.sin(a), y2 - size * math.sin(a) - size * 0.5 * math.cos(a))
    r = (x2 - size * math.cos(a) - size * 0.5 * math.sin(a), y2 - size * math.sin(a) + size * 0.5 * math.cos(a))
    return f'M{x2:.1f} {y2:.1f}L{l[0]:.1f} {l[1]:.1f}L{r[0]:.1f} {r[1]:.1f}Z'

def path_el(points, step, ret=False, head=True):
    d = 'M' + ' L'.join(f'{x} {y}' for x, y in points)
    # stop the line short of the tip so the head stays crisp
    (x1, y1), (x2, y2) = points[-2], points[-1]
    out = [f'<path class="sb-d-line s{step}{" sb-d-line--return" if ret else ""}" d="{d}"/>']
    if head:
        out.append(f'<path class="sb-d-head s{step}" d="{arrowhead(x1, y1, x2, y2)}"/>')
    return '\n'.join(out)

def badge(x, y, n):
    return f'<g class="sb-d-badge s{n}"><circle cx="{x}" cy="{y}" r="11"/><text x="{x}" y="{y}">{n}</text></g>'

def box(x, y, w, h, title, subs, steps, kind=''):
    cls = ' '.join(f'b{s}' for s in steps)
    t = [f'<g class="sb-d-box {cls} {kind}">', f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3"/>']
    ty = y + 25
    for line in (title if isinstance(title, list) else [title]):
        t.append(f'<text class="sb-d-title" x="{x+14}" y="{ty}">{html.escape(line)}</text>'); ty += 19
    for s in subs:
        t.append(f'<text class="sb-d-sub" x="{x+14}" y="{ty}">{html.escape(s)}</text>'); ty += 17
    t.append('</g>')
    return '\n'.join(t)

def zone(x, y, w, h, label, kind):
    return (f'<rect class="sb-d-zone sb-d-zone--{kind}" x="{x}" y="{y}" width="{w}" height="{h}" rx="4"/>'
            f'<text class="sb-d-label" x="{x+16}" y="{y+24}">{html.escape(label)}</text>')

def note(x, y, text, anchor='middle'):
    return f'<text class="sb-d-note" x="{x}" y="{y}" text-anchor="{anchor}">{html.escape(text)}</text>'

ALT = ("Six steps between people, the Secrets Bridge control plane and an agent in your infrastructure. "
       "1, the requester asks for access. 2, an approver decides. 3, the agent calls out and claims the job. "
       "4, the agent reads the provider. 5, the agent returns the values as a sealed, single-use wrap. "
       "6, the requester reveals each value once. Providers connect only to the agent.")

def desktop():
    e = []
    e.append(zone(16, 40, 200, 384, 'PEOPLE', 'people'))
    e.append(box(36, 96, 160, 70, 'Requester', ['asks, then reveals'], [1, 6]))
    e.append(box(36, 296, 160, 70, 'Approver', ['decides'], [2]))
    e.append(zone(310, 40, 380, 384, 'SECRETS BRIDGE CONTROL PLANE', 'cp'))
    e.append(box(330, 96, 340, 70, 'Console and API', ['sign-in, policy, second factor'], [1, 2, 6], 'sb-d-box--cp'))
    e.append(box(330, 196, 340, 70, 'Requests, approvals, audit', ['metadata only; audit is append-only'], [2], 'sb-d-box--cp'))
    e.append(box(330, 296, 340, 70, 'Jobs and single-use wraps', ['values sealed, opened once'], [3, 5, 6], 'sb-d-box--cp'))
    e.append(note(500, 404, 'No plaintext values are kept here.'))
    e.append(zone(784, 40, 360, 384, 'YOUR INFRASTRUCTURE', 'infra'))
    e.append(box(804, 96, 136, 270, 'Agent', ['calls out only', 'no inbound port', 'its own credentials'], [3, 4, 5]))
    e.append(f'<text class="sb-d-label" x="988" y="124">PROVIDERS</text>')
    e.append(box(988, 140, 140, 78, ['AWS Secrets', 'Manager'], [], [4]))
    e.append(box(988, 256, 140, 78, ['HashiCorp', 'Vault'], ['KV v2'], [4]))
    e.append(note(964, 404, 'Values leave only as a sealed wrap.'))
    # connections
    e.append(path_el([(196, 120), (330, 120)], 1))
    e.append(path_el([(330, 146), (196, 146)], 6, ret=True))
    e.append(path_el([(196, 331), (253, 331), (253, 231), (330, 231)], 2))
    e.append(path_el([(804, 316), (670, 316)], 3))
    e.append(path_el([(804, 346), (670, 346)], 5))
    # One link from the agent that splits to each provider.
    e.append(path_el([(940, 237), (964, 237)], 4, head=False))
    e.append(path_el([(964, 179), (964, 295)], 4, head=False))
    e.append(path_el([(964, 179), (988, 179)], 4))
    e.append(path_el([(964, 295), (988, 295)], 4))
    e.append(badge(240, 120, 1)); e.append(badge(286, 146, 6)); e.append(badge(253, 281, 2))
    e.append(badge(715, 316, 3)); e.append(badge(759, 346, 5)); e.append(badge(952, 237, 4))
    # legend
    e.append('<g class="sb-d-legend">'
             + path_el([(16, 452), (52, 452)], 0) + '<text class="sb-d-note" x="60" y="456">opens the connection</text>'
             + path_el([(222, 452), (258, 452)], 0, ret=True) + '<text class="sb-d-note" x="266" y="456">comes back</text>'
             + '<text class="sb-d-note" x="380" y="456">Providers are reached only by the agent, inside your infrastructure.</text>'
             + '</g>')
    return f'<svg class="sb-d sb-d--wide" viewBox="0 0 1160 470" role="img" aria-label="{html.escape(ALT)}">\n' + '\n'.join(e) + '\n</svg>'

def narrow():
    e = []
    e.append(zone(8, 16, 344, 150, 'PEOPLE', 'people'))
    e.append(box(24, 52, 148, 70, 'Requester', ['asks, then reveals'], [1, 6]))
    e.append(box(188, 52, 148, 70, 'Approver', ['decides'], [2]))
    e.append(zone(8, 236, 344, 392, 'CONTROL PLANE', 'cp'))
    e.append(box(24, 280, 312, 70, 'Console and API', ['sign-in, policy, second factor'], [1, 2, 6], 'sb-d-box--cp'))
    e.append(box(24, 380, 312, 70, 'Requests, approvals, audit', ['metadata only; append-only audit'], [2], 'sb-d-box--cp'))
    e.append(box(24, 480, 312, 70, 'Jobs and single-use wraps', ['values sealed, opened once'], [3, 5, 6], 'sb-d-box--cp'))
    e.append(note(180, 604, 'No plaintext values are kept here.'))
    e.append(zone(8, 698, 344, 280, 'YOUR INFRASTRUCTURE', 'infra'))
    e.append(box(24, 742, 312, 70, 'Agent', ['calls out only; no inbound port'], [3, 4, 5]))
    e.append(box(24, 872, 148, 78, ['AWS Secrets', 'Manager'], [], [4]))
    e.append(box(188, 872, 148, 78, ['HashiCorp', 'Vault'], ['KV v2'], [4]))
    e.append(path_el([(72, 122), (72, 280)], 1))
    e.append(path_el([(124, 280), (124, 122)], 6, ret=True))
    e.append(path_el([(262, 122), (262, 280)], 2))
    e.append(path_el([(124, 742), (124, 550)], 3))
    e.append(path_el([(236, 742), (236, 550)], 5))
    e.append(path_el([(180, 812), (180, 842)], 4, head=False))
    e.append(path_el([(98, 842), (262, 842)], 4, head=False))
    e.append(path_el([(98, 842), (98, 872)], 4))
    e.append(path_el([(262, 842), (262, 872)], 4))
    e.append(badge(72, 200, 1)); e.append(badge(124, 200, 6)); e.append(badge(262, 200, 2))
    e.append(badge(124, 662, 3)); e.append(badge(236, 662, 5)); e.append(badge(180, 827, 4))
    return f'<svg class="sb-d sb-d--narrow" viewBox="0 0 360 990" role="img" aria-label="{html.escape(ALT)}">\n' + '\n'.join(e) + '\n</svg>'

STEPS = [
    ('Ask for access', 'The requester names the secret, the keys and why. No value is sent.'),
    ('Someone approves', 'The policy for the project and environment decides how many approvals it needs and from whom.'),
    ('The agent claims the job', 'The agent calls out to the control plane for work. Nothing calls in, so you open no inbound port.'),
    ('It reads the provider', 'The agent reads only the approved keys, with its own credentials, inside your infrastructure.'),
    ('It sends back a sealed wrap', 'The values travel back encrypted for this request and are held only as a single-use wrap with a short lifetime.'),
    ('Reveal once', 'The requester confirms with a second factor and sees each value once. Every step is in the audit log.'),
]

controls = ['<div class="sb-flow-controls" role="radiogroup" aria-label="Follow a request, step by step">',
            '<span class="sb-flow-controls__label" aria-hidden="true">Follow a request</span>',
            '<input type="radio" name="sb-flow" id="sb-flow-all" checked><label for="sb-flow-all">All steps</label>']
for i, (t, _) in enumerate(STEPS, 1):
    controls.append(f'<input type="radio" name="sb-flow" id="sb-flow-{i}"><label for="sb-flow-{i}"><span class="sb-sr">Step </span>{i}<span class="sb-sr">: {html.escape(t)}</span></label>')
controls.append('</div>')

captions = ['<ol class="sb-flow-steps">']
for i, (t, d) in enumerate(STEPS, 1):
    captions.append(f'<li class="c{i}"><span class="sb-flow-steps__n" aria-hidden="true">{i}</span><span><strong>{html.escape(t)}.</strong> {html.escape(d)}</span></li>')
captions.append('</ol>')

out = ('<!-- Generated by scripts/gen_flow.py. Edit the script, not this file. -->\n'
       '<div class="sb-flow">\n' + '\n'.join(controls) + '\n<div class="sb-flow-figure">\n'
       + desktop() + '\n' + narrow() + '\n</div>\n' + '\n'.join(captions) + '\n</div>\n')
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'includes', 'flow.html'), 'w').write(out)
print(len(out), 'bytes')
