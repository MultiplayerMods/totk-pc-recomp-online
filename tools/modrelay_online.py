"""Build the game with a ModRelay mod in it (docs/modrelay.md): the mod's patch applied to a copy of the ExeFS, the
lift, and a build of its own beside the ordinary one.

    .venv\\Scripts\\python tools\\modrelay_online.py [--patch DIR] [--sdk DIR] [--hub DIR] [--version v121] [--jobs N]
                                                     [--skip-lift] [--skip-build]

The [modrelay] table of config.local.toml gives the defaults: `sdk` (the ModRelay checkout, whose backends/recomp
holds the toolkit), `patch` (the mod's Recomp/<mod> folder: modrelay-patch.json and exefs/<module>) and `hub` (the
folder of Hub.dll and steam_api64.dll). The steps (tools/modrelay.py), none of which writes the extracted ExeFS:

1. layout: the extracted ExeFS plus the mod's module, through recomp/layout.py, which alone decides module bases.
2. apply: the toolkit writes main with the mod's hooks and the module with its hook slots and module table into
   <work>/modrelay/<version>/exefs, beside the other ExeFS files, copied; expected.json there lists their hashes.
3. lift: recomp/gen.py on that ExeFS into generated/<version>-modrelay, with the toolkit's entry points added to the
   function starts of each module (the returns into main after a hook, the mod's functions, the main functions the mod
   calls through a pointer); then modrelay_recomp.h, the constructors runtime/modrelay.c runs.
4. build: tools/build_game.py into build/<version>-modrelay, then the ordinary build's prepared shaders and settings
   (build/<version>) and the Hub copied next to totk.exe when they are not there yet.

The build reads the RomFS and keeps its saves where the ordinary build does (tools/build_game.py defaults).
Standard library, recomp/ and the toolkit only.
"""
import argparse
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'recomp'))
sys.path.insert(0, str(ROOT / 'tools'))

import modrelay  # noqa: E402
from build_game import DISPLAY_VERSIONS, work_dir  # noqa: E402

# What a build folder keeps from the ordinary build: the prepared shaders and pipelines, and the settings.
CARRIED = ('shader-cache', 'pipeline-*.bin', 'shader-*.bin', 'seed-*.bin', 'totk.ini')
HUB_FILES = ('Hub.dll', 'steam_api64.dll')
say = modrelay.say


def config():
    path = ROOT / 'config.local.toml'
    return tomllib.loads(path.read_text(encoding='utf-8')).get('modrelay', {}) if path.is_file() else {}


def build(version, gen, out, exefs, jobs, hub):
    """Step 4."""
    command = [sys.executable, str(ROOT / 'tools' / 'build_game.py'), '--version', version, '--gen', str(gen),
               '--out', str(out), '--exefs', str(exefs), '--expected', str(exefs / modrelay.EXPECTED)]
    if jobs:
        command += ['--jobs', str(jobs)]
    say('build: ' + ' '.join(command[2:]))
    if subprocess.run(command, cwd=ROOT).returncode:
        sys.exit('modrelay: the build failed')
    ordinary = ROOT / 'build' / version
    for pattern in CARRIED:
        for source in ordinary.glob(pattern):
            target = out / source.name
            if target.exists():
                continue
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copyfile(source, target)
            say(f'kept {source.name} of {ordinary}')
    for name in HUB_FILES if hub else ():
        source = Path(hub) / name
        if source.is_file() and (not (out / name).exists() or modrelay.digest(source) != modrelay.digest(out / name)):
            shutil.copyfile(source, out / name)
            say(f'{name} from {hub}')
    say(f'done: {out / "totk.exe"}')


def main():
    settings = config()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--patch', type=Path, default=settings.get('patch'), help='the mod\'s Recomp/<mod> folder')
    ap.add_argument('--sdk', type=Path, default=settings.get('sdk'), help='the ModRelay checkout')
    ap.add_argument('--hub', type=Path, default=settings.get('hub'), help='folder of Hub.dll and steam_api64.dll')
    ap.add_argument('--version', default='v121', choices=sorted(DISPLAY_VERSIONS))
    ap.add_argument('--jobs', type=int, help='lift and compile jobs (default: theirs)')
    ap.add_argument('--skip-lift', action='store_true', help='keep the generated C of an earlier run')
    ap.add_argument('--skip-build', action='store_true', help='stop after the lift')
    args = ap.parse_args()
    if not args.patch or not args.sdk:
        sys.exit('modrelay: give --patch and --sdk, or patch and sdk under [modrelay] in config.local.toml')
    kit = modrelay.toolkit(Path(args.sdk) / 'backends' / 'recomp')
    game = work_dir() / 'extracted' / args.version / 'exefs'
    if not (game / 'main').is_file():
        sys.exit(f'modrelay: no extracted ExeFS in {game} (tools/extract.py)')
    exefs = work_dir() / 'modrelay' / args.version / 'exefs'
    gen = ROOT / 'generated' / f'{args.version}-modrelay'
    out = ROOT / 'build' / f'{args.version}-modrelay'
    integration = modrelay.apply(kit, args.patch.resolve(), args.version, game, exefs)
    header = gen / 'modrelay_recomp.h'
    if args.skip_lift:
        modrelay.write_header(integration, header)
    else:
        lift_args = ['--out', str(gen), '--patches', str(ROOT / 'recomp' / f'patches-{args.version}.txt')]
        modrelay.lift(exefs, lift_args + (['--jobs', str(args.jobs)] if args.jobs else []), header)
    if not args.skip_build:
        build(args.version, gen, out, exefs, args.jobs, args.hub)


if __name__ == '__main__':
    main()
