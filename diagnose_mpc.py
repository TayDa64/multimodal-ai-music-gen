#!/usr/bin/env python3
"""
MPC Studio MIDI Diagnostic Tool

Run this script to troubleshoot MIDI connectivity with your Akai MPC Studio.
It will show real-time MIDI messages as you tap pads, turn knobs, etc.

Usage:
    python diagnose_mpc.py
    python diagnose_mpc.py --device 3
    python diagnose_mpc.py --device "MPC Studio"
"""

import sys
import time
import argparse

try:
    import pygame.midi as pm
except ImportError:
    print("ERROR: pygame is required. Install with: pip install pygame")
    sys.exit(1)


def list_devices():
    """Print all MIDI devices."""
    pm.init()
    count = pm.get_count()
    
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║              MIDI DEVICE DIAGNOSTIC                          ║")
    print("╚══════════════════════════════════════════════════════════════╝\n")
    
    inputs = []
    outputs = []
    
    for i in range(count):
        info = pm.get_device_info(i)
        name = info[1].decode("utf-8", errors="replace") if isinstance(info[1], bytes) else str(info[1])
        is_input = bool(info[2])
        is_output = bool(info[3])
        is_opened = bool(info[4])
        
        status = "🔒 IN USE" if is_opened else "✅ Available"
        
        if is_input:
            inputs.append((i, name, status))
        if is_output:
            outputs.append((i, name, status))
    
    print("🎹 MIDI INPUT DEVICES (can receive from):")
    if inputs:
        for dev_id, name, status in inputs:
            print(f"   [{dev_id}] {name}  {status}")
    else:
        print("   (none detected)")
    
    print("\n🔊 MIDI OUTPUT DEVICES (can send to):")
    if outputs:
        for dev_id, name, status in outputs:
            print(f"   [{dev_id}] {name}  {status}")
    else:
        print("   (none detected)")
    
    pm.quit()
    return inputs


def monitor_device(device_id: int, duration: int = 30):
    """Monitor a MIDI input device and print all incoming messages."""
    pm.init()
    
    info = pm.get_device_info(device_id)
    if not info:
        print(f"ERROR: Device {device_id} not found")
        pm.quit()
        return
    
    name = info[1].decode("utf-8", errors="replace") if isinstance(info[1], bytes) else str(info[1])
    is_input = bool(info[2])
    is_opened = bool(info[4])
    
    if not is_input:
        print(f"ERROR: Device [{device_id}] {name} is not an input device")
        pm.quit()
        return
    
    if is_opened:
        print(f"WARNING: Device [{device_id}] {name} may be in use by another application")
        print("         Try closing MPC Software or other MIDI apps\n")
    
    try:
        midi_in = pm.Input(device_id)
    except Exception as e:
        print(f"ERROR: Could not open device: {e}")
        print("\nTroubleshooting:")
        print("  1. Close MPC Software (it holds exclusive access)")
        print("  2. Ensure MPC is in Controller Mode, not Standalone Mode")
        print("  3. Try unplugging and re-plugging the USB cable")
        pm.quit()
        return
    
    print(f"\n🎤 Monitoring [{device_id}] {name}")
    print(f"   Duration: {duration} seconds")
    print("   Press Ctrl+C to stop early\n")
    print("─" * 60)
    print("   Tap pads, turn knobs, move faders on your MPC...")
    print("─" * 60)
    
    msg_count = 0
    start = time.time()
    
    try:
        while time.time() - start < duration:
            if midi_in.poll():
                events = midi_in.read(32)
                for event in events:
                    data, timestamp = event
                    msg_count += 1
                    
                    status = data[0]
                    msg_type = status & 0xF0
                    channel = (status & 0x0F) + 1  # 1-based for display
                    
                    if msg_type == 0x90 and len(data) >= 3:
                        note, velocity = data[1], data[2]
                        if velocity > 0:
                            print(f"   🟢 NOTE ON   Ch:{channel:2d}  Note:{note:3d}  Vel:{velocity:3d}")
                        else:
                            print(f"   🔴 NOTE OFF  Ch:{channel:2d}  Note:{note:3d}")
                    
                    elif msg_type == 0x80 and len(data) >= 3:
                        note = data[1]
                        print(f"   🔴 NOTE OFF  Ch:{channel:2d}  Note:{note:3d}")
                    
                    elif msg_type == 0xB0 and len(data) >= 3:
                        cc, value = data[1], data[2]
                        print(f"   🎛️  CC       Ch:{channel:2d}  CC:{cc:3d}    Val:{value:3d}")
                    
                    elif msg_type == 0xE0 and len(data) >= 3:
                        lsb, msb = data[1], data[2]
                        pitch = ((msb << 7) | lsb) - 8192
                        print(f"   🎚️  PITCH    Ch:{channel:2d}  Bend:{pitch:+5d}")
                    
                    elif msg_type == 0xC0 and len(data) >= 2:
                        program = data[1]
                        print(f"   🎹 PROGRAM  Ch:{channel:2d}  Prog:{program:3d}")
                    
                    elif msg_type == 0xD0 and len(data) >= 2:
                        pressure = data[1]
                        print(f"   👆 PRESSURE Ch:{channel:2d}  Press:{pressure:3d}")
                    
                    else:
                        print(f"   📨 RAW      {[hex(b) for b in data]}")
            
            time.sleep(0.001)
    
    except KeyboardInterrupt:
        print("\n\n   (Stopped by user)")
    
    finally:
        midi_in.close()
        pm.quit()
    
    print("─" * 60)
    print(f"\n📊 Summary: Received {msg_count} MIDI messages")
    
    if msg_count == 0:
        print("\n⚠️  NO MIDI MESSAGES RECEIVED!")
        print("\nTroubleshooting for MPC Studio mk2:")
        print("  1. MODE CHECK: Press MODE + PAD 1 to enter Controller Mode")
        print("     The screen should show 'Controller Mode'")
        print("  2. Close MPC Software completely (check Task Manager)")
        print("  3. Try the other MIDI port:")
        print("     - 'MPC Studio mk2 Public' = pads/knobs/faders")
        print("     - 'MPC Studio mk2 MIDI Port' = standard MIDI")
        print("  4. Check USB connection (try a different port)")
        print("  5. On the MPC: Menu > Preferences > MIDI > ensure output is enabled")
    else:
        print("\n✅ MIDI connection is working!")
        print(f"   Your MPC is sending data correctly.")
        print(f"\n   To record drums, use:")
        print(f"   python main.py \"trap beat\" --midi-in {device_id} --record-part drums")


def main():
    parser = argparse.ArgumentParser(
        description="Diagnose MIDI connectivity with MPC Studio",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python diagnose_mpc.py                    # List all devices
  python diagnose_mpc.py --device 3         # Monitor device ID 3
  python diagnose_mpc.py --device "MPC"     # Monitor device matching "MPC"
  python diagnose_mpc.py --device 3 --time 60  # Monitor for 60 seconds
        """
    )
    parser.add_argument(
        "--device", "-d",
        type=str,
        default=None,
        help="Device ID or name substring to monitor"
    )
    parser.add_argument(
        "--time", "-t",
        type=int,
        default=30,
        help="Seconds to monitor (default: 30)"
    )
    
    args = parser.parse_args()
    
    inputs = list_devices()
    
    if args.device is None:
        print("\n💡 Tip: Run with --device <id> to monitor a specific input")
        print("   Example: python diagnose_mpc.py --device 3")
        return
    
    # Find device
    device_id = None
    
    if args.device.isdigit():
        device_id = int(args.device)
    else:
        # Search by name
        pm.init()
        count = pm.get_count()
        for i in range(count):
            info = pm.get_device_info(i)
            name = info[1].decode("utf-8", errors="replace") if isinstance(info[1], bytes) else str(info[1])
            if args.device.lower() in name.lower() and bool(info[2]):
                device_id = i
                break
        pm.quit()
    
    if device_id is None:
        print(f"\nERROR: Could not find input device matching '{args.device}'")
        return
    
    monitor_device(device_id, args.time)


if __name__ == "__main__":
    main()
