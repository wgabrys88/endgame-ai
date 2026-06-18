"""Test desktop observation only - no actions executed."""
import sys
import time
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, ".")
from desktop import Desktop

desktop = Desktop()
print("Desktop initialized. Running observe()...")
t0 = time.time()
obs = desktop.observe()
elapsed = time.time() - t0

print(f"\n=== OBSERVATION ({elapsed:.1f}s) ===")
print(f"Focused: {obs.focused_title}")
print(f"Elements: {len(obs.elements)}")
print(f"Windows: {len(obs.windows)}")
print(f"\n--- Desktop Summary ---")
print(obs.desktop_summary)
print(f"\n--- Screen Context ---")
print(obs.context_text)
print(f"\n--- Elements Book ---")
for eid, el in list(obs.elements.items())[:20]:
    print(f"  [{eid}] {el.role} '{el.name}' action={el.action} enabled={el.enabled} wnd='{el.wnd}'")
if len(obs.elements) > 20:
    print(f"  ... and {len(obs.elements) - 20} more")
