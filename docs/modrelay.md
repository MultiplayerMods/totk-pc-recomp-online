# ModRelay mods

[ModRelay](https://github.com/MultiplayerMods/ModRelay) mods are Switch code mods (an exlaunch `subsdk9`) that the port cannot load from the
`mods` folder (see [mods.md](mods.md), "What does not work"). A ModRelay mod also ships a recompilation patch: its
module plus `modrelay-patch.json`, which describes its hooks into `main` as offsets. The ModRelay toolkit
(`backends/recomp` of the ModRelay checkout) applies that patch to the ExeFS before the lift, so the mod is lifted and
built with the game. The port knows nothing about the mod: any ModRelay patch for the build's game version goes the
same way. Neither this repository nor its releases hold a mod: each player supplies the mod's patch, as they supply
their game files.

## With the setup (players)

The Windows setup ([installer.md](installer.md)) has a "ModRelay mod" field: pick the mod's `Recomp\<mod>` folder (the
one with `modrelay-patch.json`), downloaded with the mod. The setup applies the patch to a copy of the ExeFS
(`modrelay\exefs` in the install folder), builds the game with the mod and puts the ModRelay Hub next to `totk.exe`.
The release carries ModRelay's recomp toolkit and Hub (`modrelay\` of the release, pinned in `tools/make_release.py`).
A later run of the setup on the same folder keeps the mod; empty the field to build the game without it.

## Build from source

1. Build the port as usual first ([building.md](building.md)): the extracted ExeFS and RomFS, and `build\<ver>` with
   its prepared shaders.
2. Get ModRelay:
   - the toolkit: clone the repository, `git clone https://github.com/MultiplayerMods/ModRelay C:\ModRelay`;
   - the Hub (optional): unpack `ModRelay-<version>-Windows-x64.zip` from
     [ModRelay's releases](https://github.com/MultiplayerMods/ModRelay/releases/latest), for example into
     `C:\ModRelay\Release\Win`. Its `Hub.dll` and `steam_api64.dll` are copied next to `totk.exe`.
3. Add to `config.local.toml`:

   ```toml
   [modrelay]
   sdk = 'C:\ModRelay'                              # the ModRelay checkout
   patch = 'C:\MyMod\dist\1.2.1\Recomp\MyMod'        # the mod's Recomp\<mod> folder
   hub = 'C:\ModRelay\Release\Win'                   # optional: the unpacked Hub release
   ```

4. Run:

   ```powershell
   .venv\Scripts\python tools\modrelay_online.py
   ```

   `--patch`, `--sdk` and `--hub` override the configuration; `--version` (default `v121`) picks the game version,
   `--skip-lift` keeps the generated C of an earlier run, `--skip-build` stops after the lift.

5. Play `build\<ver>-modrelay\totk.exe`. It reads the RomFS and keeps its saves where the ordinary build does.

What the script writes, beside the ordinary build and without touching the extracted files:

| Where | What |
|---|---|
| `<work>\modrelay\<ver>\exefs` | the ExeFS with the patch applied (`main` with the hooks, the mod's module), `expected.json` with their hashes, `integration.json` (the toolkit's report) |
| `generated\<ver>-modrelay` | the lifted C, with `modrelay_recomp.h` |
| `build\<ver>-modrelay` | the build, with the ordinary build's prepared shaders and `totk.ini` copied the first time, and the Hub |

## How the mod runs

- **Layout.** The mod's module joins the layout like any `subsdk`, before `sdk` (`recomp/layout.py`); the patch is
  applied for those bases, and the script stops if the lift placed the modules elsewhere.
- **Hooks.** A hook is a `B` in `main` to a slot of the mod's module: the lifter sees a branch out of the function and
  dispatches to the slot (`rt_dispatch`). The toolkit lists the entry points the lifter cannot find alone (the
  returns into `main`, the mod's functions, the `main` functions it calls through a pointer); the script adds them to
  the function starts of each module.
- **Constructor.** `runtime/modrelay.c` runs the mod's constructor once, after the game's `DT_INIT` (`boot.c`
  `cb_module_inits`), as rtld would. The constructor installs the mod's hooks and binds its memory buses.
- **SDK calls.** The mod calls the functions `main` imports through what `main` was linked to, so the port's host
  implementations (`nn::fs`, `nn::swkbd`, `nn::account`) serve it as they serve the game.
- **Network.** A mod built for a recompilation has no network code of its own: it exchanges its data through memory
  buses that the ModRelay Hub, running in this process, relays. `runtime/modrelay.c` opens the Hub's window when
  `Hub.dll` is next to `totk.exe`; otherwise run ModRelay's `Launcher.exe` and pick `totk.exe`.

A build without `modrelay_recomp.h` in its generated folder (an ordinary build) runs nothing of this.
