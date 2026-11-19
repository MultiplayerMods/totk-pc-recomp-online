"""A ModRelay mod built into the game (docs/modrelay.md): the mod's patch applied to a copy of the ExeFS, then the lift
with the ModRelay toolkit's entry points. tools/modrelay_online.py (a repository build) and the setup's lift step
(installer/steps.py, Lift) both run it.

    python tools/modrelay.py apply --toolkit DIR --patch DIR --version v121 --game EXEFS --out EXEFS
    python tools/modrelay.py lift --exefs EXEFS --header FILE <recomp/gen.py arguments without --exefs and --modules>

--toolkit is the folder of the ModRelay recomp toolkit (backends/recomp of a ModRelay checkout, modrelay/recomp of a
release), --patch the mod's Recomp/<mod> folder (modrelay-patch.json and exefs/<module>).

apply never writes --game: it copies its files into --out, adds the mod's module, writes main with the mod's hooks and
the module with its hook slots and module table (recomp/layout.py alone decides the bases), then expected.json (the
hashes of that ExeFS, for build_game.py --expected) and integration.json (the toolkit's report: the entry points the
lifter cannot find alone and the mod's constructors).

lift runs recomp/gen.py on that ExeFS, every module of its layout lifted and the report's entry points added to the
function starts of each module, then writes --header (modrelay_recomp.h, the constructors runtime/modrelay.c runs).
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'recomp'))
sys.path.insert(0, str(ROOT / 'tools'))

from build_game import DISPLAY_VERSIONS  # noqa: E402
from check_content import GENERATED_MARKER  # noqa: E402

INTEGRATION = 'integration.json'
EXPECTED = 'expected.json'


def say(text):
    print(f'modrelay: {text}', flush=True)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def toolkit(folder):
    """The modrelay_recomp package of the toolkit folder."""
    folder = Path(folder)
    if not (folder / 'modrelay_recomp' / '__init__.py').is_file():
        sys.exit(f'modrelay: no ModRelay recomp toolkit in {folder}')
    sys.path.insert(0, str(folder))
    import modrelay_recomp
    return modrelay_recomp


def apply(kit, patch, version, game, out):
    """The patched ExeFS in out, its expected hashes and the toolkit's integration report. Returns the report."""
    from layout import layout
    description = kit.patchfile.load(patch)
    if description['platform'] != 'switch':
        sys.exit(f'modrelay: {patch} is a {description["platform"]} patch')
    module = description['module']['name']
    if (game / module).exists():
        sys.exit(f'modrelay: the game already has a {module}')
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    for path in game.iterdir():
        if path.is_file():
            shutil.copyfile(path, out / path.name)
    shutil.copyfile(patch / description['module']['file'], out / module)
    bases = {name: base for name, base, _ in layout(out)}
    integration = kit.apply(patch, game, out, bases)
    expected = json.loads((ROOT / 'tools' / 'data' / f'expected-v{DISPLAY_VERSIONS[version]}.json').read_text())
    expected['_comment'] = f'{expected.get("_comment", "")} ExeFS with {description["mod"]["name"]} applied.'.strip()
    for name in ('main', module):
        expected['exefs_sha256'][name] = digest(out / name)
    (out / EXPECTED).write_text(json.dumps(expected, indent=2) + '\n')
    (out / INTEGRATION).write_text(json.dumps(integration, indent=2) + '\n')
    say(f'{description["mod"]["name"]} {description["mod"]["version"]}: {integration["hooks"]} hooks into main, '
        f'{module} at {bases[module]:#x} -> {out}')
    return integration


def lift(exefs, gen_args, header):
    """recomp/gen.py on the patched ExeFS with the report's entry points among the function starts, then the header."""
    import gen as generator
    from layout import layout
    integration = json.loads((exefs / INTEGRATION).read_text())
    bases = {name: base for name, base, _ in layout(exefs)}
    extra = {name: {int(a, 16) for a in addresses} for name, addresses in integration['seeds'].items()}
    seeds = generator.Module.seeds

    def with_entries(module):
        return sorted(set(seeds(module)) | {a for a in extra.get(module.name, ()) if module.in_text(a)})

    generator.Module.seeds = with_entries
    modules = [name for name in bases if name != 'rtld']
    sys.argv = ['gen.py', '--exefs', str(exefs), '--modules', ','.join(modules), *gen_args]
    say('lift: ' + ' '.join(sys.argv[1:]))
    generator.main()
    gen = Path(gen_args[gen_args.index('--out') + 1])
    lifted = {m['name']: int(m['base'], 16) for m in json.loads((gen / 'layout.json').read_text())}
    if lifted != bases:
        sys.exit(f'modrelay: the lift placed the modules at {lifted}, the patch was applied for {bases}')
    write_header(integration, header)


def write_header(integration, header):
    from modrelay_recomp import c_header
    text = c_header(integration).replace('/* Generated by the ModRelay recomp toolkit. Do not edit. */',
                                         f'// {GENERATED_MARKER}: ModRelay mod constructors, generated by '
                                         'tools/modrelay.py. Do not edit or commit.', 1)
    header.parent.mkdir(parents=True, exist_ok=True)
    header.write_text(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest='command', required=True)
    a = sub.add_parser('apply', help='the patched ExeFS')
    a.add_argument('--toolkit', type=Path, required=True)
    a.add_argument('--patch', type=Path, required=True)
    a.add_argument('--version', required=True, choices=sorted(DISPLAY_VERSIONS))
    a.add_argument('--game', type=Path, required=True, help='the original ExeFS, only read')
    a.add_argument('--out', type=Path, required=True)
    lf = sub.add_parser('lift', help='recomp/gen.py on the patched ExeFS')
    lf.add_argument('--toolkit', type=Path, required=True)
    lf.add_argument('--exefs', type=Path, required=True, help='the ExeFS apply wrote')
    lf.add_argument('--header', type=Path, required=True, help='modrelay_recomp.h to write')
    args, rest = ap.parse_known_args()
    kit = toolkit(args.toolkit)
    if args.command == 'apply':
        if rest:
            ap.error(f'unknown arguments: {" ".join(rest)}')
        apply(kit, args.patch.resolve(), args.version, args.game.resolve(), args.out.resolve())
    else:
        lift(args.exefs.resolve(), rest, args.header.resolve())


if __name__ == '__main__':
    main()
