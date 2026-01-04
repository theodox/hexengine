"""
Quick toggle script to enable/disable the new state system.

Usage:
    python toggle_new_system.py on   # Enable new system
    python toggle_new_system.py off  # Disable new system (default)
"""

import sys
from pathlib import Path


def toggle_flag(file_path: Path, enable: bool):
    """Toggle USE_NEW_STATE_SYSTEM flag in a file."""
    content = file_path.read_text(encoding='utf-8')
    
    target_value = "True" if enable else "False"
    old_true = "USE_NEW_STATE_SYSTEM = True"
    old_false = "USE_NEW_STATE_SYSTEM = False"
    
    if enable:
        new_content = content.replace(old_false, old_true)
    else:
        new_content = content.replace(old_true, old_false)
    
    if new_content != content:
        file_path.write_text(new_content, encoding='utf-8')
        return True
    return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python toggle_new_system.py [on|off]")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    enable = command == "on"
    
    if command not in ["on", "off"]:
        print("Error: Command must be 'on' or 'off'")
        sys.exit(1)
    
    # Files containing the flag
    src_dir = Path("src/hexengine")
    files = [
        src_dir / "game/events/mouse.py",
        src_dir / "game/history.py",
    ]
    
    print(f"{'Enabling' if enable else 'Disabling'} new state system...")
    
    changed_count = 0
    for file_path in files:
        if not file_path.exists():
            print(f"  ⚠️  Warning: {file_path} not found")
            continue
        
        if toggle_flag(file_path, enable):
            print(f"  ✓ Updated {file_path}")
            changed_count += 1
        else:
            print(f"  - {file_path} (no change needed)")
    
    if changed_count > 0:
        print(f"\n✅ New state system {'ENABLED' if enable else 'DISABLED'}")
        print(f"   Changed {changed_count} file(s)")
        
        if enable:
            print("\n📝 Next steps:")
            print("   1. Test unit selection and dragging")
            print("   2. Test undo/redo (Ctrl+Z / Ctrl+Y)")
            print("   3. Verify preview doesn't corrupt state")
            print("   4. Check TRANSITION_COMPLETE.md for full checklist")
    else:
        print(f"\nNo changes needed - system already {'enabled' if enable else 'disabled'}")


if __name__ == "__main__":
    main()
