"""Read-only deployment deltas and conservative offline A/B/rollback observations.

Inventory hashes and caller identity attestations are records, not evidence that a
particular guest instruction read a resource. No title execution is performed.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

_SHA = re.compile(r'[0-9a-f]{64}')


def _member(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError('member must be a relative POSIX path')
    parts = value.split('/')
    if any(p in ('', '.', '..') or p.endswith((' ', '.')) or any(ord(c)<32 for c in p) for p in parts):
        raise ValueError('member contains unsafe components')
    if any(any(c in p for c in '<>"|?*') for p in parts):
        raise ValueError('member contains Windows-special characters')
    for part in parts:
        stem=part.split('.')[0].upper()
        if stem in {'CON','PRN','AUX','NUL'} or re.fullmatch(r'(?:COM|LPT)[1-9]',stem):
            raise ValueError('member contains a Windows device name')
    return value


def _sha(value):
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise ValueError('SHA256 must be 64 lowercase hex characters')
    return value


def _files(value):
    if not isinstance(value, dict) or not isinstance(value.get('files'), dict):
        raise ValueError('inventory requires a files dictionary')
    result = value['files']
    seen = set()
    for name, digest in result.items():
        _member(name); _sha(digest)
        if name.casefold() in seen:
            raise ValueError('case-insensitive inventory collision')
        seen.add(name.casefold())
    return {k:v for k,v in result.items() if k != '.staging.json'}


def compare_roots(base_inventory, modified_inventory, member, expected_sha):
    """Audit records; ignore only root .staging.json, not resource differences."""
    member = _member(member); expected_sha = _sha(expected_sha)
    if member == '.staging.json':
        raise ValueError('staging metadata is not a deployable member')
    base, modified = _files(base_inventory), _files(modified_inventory)
    added = sorted(modified.keys()-base.keys())
    removed = sorted(base.keys()-modified.keys())
    changed = sorted(k for k in base.keys() & modified.keys() if base[k] != modified[k])
    errors=[]
    if added != [member]: errors.append('delta must add exactly the requested member')
    if removed: errors.append('common deployment must not remove files')
    if changed: errors.append('common deployment hashes differ')
    if modified.get(member) != expected_sha: errors.append('member SHA256 mismatch')
    if any(k.casefold()==member.casefold() for k in base): errors.append('member already present in baseline')
    return {'valid':not errors, 'errors':errors, 'member':member, 'expected_sha256':expected_sha,
            'added':added, 'removed':removed, 'changed':changed,
            'scope':'Inventory-record delta only; does not establish actual guest reads or unique causality.'}


def _reports(values):
    if isinstance(values,dict): return [values]
    if not isinstance(values,(list,tuple)) or any(not isinstance(v,dict) for v in values):
        raise ValueError('reports must be a dict or sequence of dicts')
    return list(values)


def _filename_matches(text, member):
    if not isinstance(text,str): return False
    # Exactly one known parent prefix is allowed; no resolve, substring or basename match.
    text=text.replace('\\','/')
    if text.startswith('../'): text=text[3:]
    return text==member


def _trial(report, member):
    guards=report.get('inputs_unchanged') is True and report.get('game_input_unchanged') is True
    launched=report.get('image_loaded') is True and report.get('guest_entrypoint_launched') is True
    panic=report.get('panic_capture',{})
    if not isinstance(panic,dict):panic={}
    reads=panic.get('reads',{})
    if not isinstance(reads,dict):reads={}
    filename=reads.get('filename',{})
    message=reads.get('message',{})
    caller=panic.get('caller',{})
    valid_panic=(panic.get('success') is True and panic.get('errors')==[] and
                 isinstance(caller,dict) and caller.get('known') is True and
                 caller.get('saved_lr')==0x824844F4 and isinstance(message,dict) and
                 isinstance(message.get('text'),str) and 'decode_error' not in message)
    valid_filename=(isinstance(filename,dict) and filename.get('status')=='ok' and
                    filename.get('terminated') is True and filename.get('truncated') is False and
                    'decode_error' not in filename)
    target=valid_panic and valid_filename and _filename_matches(filename.get('text'),member)
    other_panic=valid_panic and valid_filename and isinstance(filename.get('text'),str) and not target
    native=report.get('unregistered_guest_target')
    native_fatal=isinstance(native,int) and not isinstance(native,bool) and 0<native<=0xFFFFFFFF
    # A timeout or arbitrary AV is not proof the target access was passed.
    positive_other=(other_panic or native_fatal) and report.get('diagnostic_success') is True
    if not guards: observation='invalid_input_identity'
    elif not launched: observation='not_launched'
    elif target: observation='specified_member_panic'
    elif positive_other: observation='different_positive_failure'
    elif report.get('timed_out') is True: observation='timeout_unresolved'
    else: observation='other_failure_or_observation_unresolved'
    return {'guards_verified':guards,'launched':launched,'observation':observation,
            'specified_member_panic':bool(guards and launched and target),
            'different_positive_failure':bool(guards and launched and positive_other and not target)}


def summarize_trials(baseline_reports, modified_reports, rollback_reports, member, *, identity_verified=False):
    """Describe bounded paired observations, not first-frame or root-cause proof.

    identity_verified is a caller attestation of equal EXE/runtime/code identities
    and validated deployment delta. This function cannot verify it from reports.
    Every supplied report must preserve both input guards; arbitrary AV/timeout
    runs remain unresolved even beside a successful pair.
    """
    member=_member(member)
    if type(identity_verified) is not bool: raise ValueError('identity_verified must be boolean')
    groups={k:[_trial(v,member) for v in _reports(values)] for k,values in
            [('baseline',baseline_reports),('modified',modified_reports),('rollback',rollback_reports)]}
    all_valid=all(v['guards_verified'] and v['launched'] for group in groups.values() for v in group)
    paired=(bool(groups['baseline']) and bool(groups['modified']) and bool(groups['rollback']) and
            all(v['specified_member_panic'] for v in groups['baseline']) and
            all(v['different_positive_failure'] for v in groups['modified']) and
            all(v['specified_member_panic'] for v in groups['rollback']))
    return {'member':member,'identity_verified_by_caller':identity_verified,'trials':groups,
            'all_trial_input_guards_verified':all_valid,
            'limited_deployment_association':bool(identity_verified and all_valid and paired),
            'claim_scope':'Bounded A/B/rollback association only; no unique causality, first-AV cause, actual member read, or first-frame proof.'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-root',required=True,type=Path)
    parser.add_argument('--modified-root',required=True,type=Path)
    parser.add_argument('--member',required=True)
    parser.add_argument('--sha256',required=True)
    args=parser.parse_args(argv)
    try:
        from tools.research.compile_module import inventory
        # Validate request before hashing any deployment.
        _member(args.member);_sha(args.sha256)
        result=compare_roots(inventory(args.baseline_root),inventory(args.modified_root),args.member,args.sha256)
        print(json.dumps(result,indent=2))
        return 0 if result['valid'] else 1
    except (OSError,ValueError) as error:
        print(json.dumps({'valid':False,'error':str(error)}));return 1


if __name__=='__main__': raise SystemExit(main())
