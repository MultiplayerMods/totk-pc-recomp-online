// ModRelay mods built into the game (docs/modrelay.md): their constructors and the ModRelay Hub.
#pragma once
#include <stdint.h>

#include "host.h"

// boot.c cb_module_inits, after the game's DT_INIT: runs each mod module's constructor once, as rtld runs DT_INIT,
// then opens the Hub when Hub.dll is next to the executable. Nothing in a build without ModRelay mods.
void rt_modrelay_init(Cpu *c);
// A mod module has no constructor flag the loader decodes: 1 and its state (2 once constructed) for one, 0 otherwise.
int rt_modrelay_ctor_state(const RtLoaded *m, uint32_t *state);
