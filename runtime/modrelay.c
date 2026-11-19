// ModRelay mods built into the game (docs/modrelay.md). tools/modrelay_online.py applies a mod's patch to a copy of the
// ExeFS before the lift, so the mod's module (subsdk9) is lifted and loaded like the game's, and writes
// modrelay_recomp.h (the ModRelay toolkit's integration report) next to layout.h in the generated folder. The mod's
// constructors are not in any init_array the game runs: they run here once, after the game's DT_INIT, as rtld would
// run DT_INIT. A mod exchanges its data with other players through memory buses that the ModRelay Hub finds in this
// process; the Hub is a Windows DLL with a window of its own, opened here when Hub.dll is next to the executable.
// Without modrelay_recomp.h (an ordinary build) nothing here runs.
#include <string.h>

#include "modrelay.h"
#include "platform/platform.h"

#if __has_include("modrelay_recomp.h")
#include "modrelay_recomp.h"
#define MODRELAY_INITS MODRELAY_RECOMP_INIT_COUNT
#else
#define MODRELAY_INITS 0u
#endif

#define CTOR_DONE 2   // boot.c: a module's constructor state once its DT_INIT ran

static volatile int32_t constructed;

static int is_mod_module(const RtLoaded *m) {
#if MODRELAY_INITS
    for (unsigned i = 0; i < MODRELAY_INITS; i++)
        if (!strcmp(modrelay_recomp_inits[i].module, m->name)) return 1;
#else
    (void)m;
#endif
    return 0;
}

int rt_modrelay_ctor_state(const RtLoaded *m, uint32_t *state) {
    if (!is_mod_module(m)) return 0;
    *state = plat_cas32(&constructed, 0, 0) ? CTOR_DONE : 0;
    return 1;
}

#if MODRELAY_INITS && defined(_WIN32)
// The Hub's window runs on a thread of its own; OpenHubWindow starts it and returns (ModRelay host/window.cpp).
static void open_hub(void) {
    char path[1024];
    if (!plat_exe_path(path, sizeof path)) return;
    char *dir = strrchr(path, '\\');
    if (!dir || (size_t)(dir + 1 - path) + sizeof "Hub.dll" > sizeof path) return;
    strcpy(dir + 1, "Hub.dll");
    void *hub = plat_lib_open(path);
    if (!hub) {
        rt_log("modrelay: no Hub (%s not loaded): open the Launcher on this process to connect", path);
        return;
    }
    unsigned long (*open)(void *) = (unsigned long (*)(void *))plat_lib_sym(hub, "OpenHubWindow");
    unsigned long error = open ? open(NULL) : 1;
    rt_log("modrelay: Hub %s", error ? "found without a window to open" : "opened");
}
#else
static void open_hub(void) {}
#endif

void rt_modrelay_init(Cpu *c) {
#if MODRELAY_INITS
    if (!plat_cas32(&constructed, 0, 0)) {
        for (unsigned i = 0; i < MODRELAY_INITS; i++) {
            rt_log("modrelay: ENTER %s constructor %#llx", modrelay_recomp_inits[i].module,
                   (unsigned long long)modrelay_recomp_inits[i].address);
            rt_call(c, modrelay_recomp_inits[i].address, 0);
        }
        plat_xchg32(&constructed, 1);
        open_hub();
    }
#else
    (void)c;
#endif
}
