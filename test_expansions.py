#!/usr/bin/env python3
"""
Test Expansion Manager - Verify intelligent instrument resolution.

This script tests the ExpansionManager's ability to:
1. Load expansion packs
2. Resolve exact instrument matches
3. Find substitutes for missing instruments (e.g., krar -> guitar)
4. Use semantic role matching
5. Use spectral similarity matching
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from multimodal_gen.expansion_manager import (
    ExpansionManager,
    MatchType,
    InstrumentRole,
    create_expansion_manager,
)


def print_header(text: str):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def print_result(requested: str, result):
    """Print resolution result in a readable format."""
    status = "✓" if result.confidence > 0 else "✗"
    print(f"\n{status} Requested: '{requested}' (genre: {result.genre})")
    print(f"  → Resolved: {result.name or 'NOT FOUND'}")
    print(f"  → Match Type: {result.match_type.value}")
    print(f"  → Confidence: {result.confidence:.0%}")
    if result.note:
        print(f"  → Note: {result.note}")
    if result.path:
        print(f"  → Path: {Path(result.path).name if result.path else 'N/A'}")


def main():
    print_header("EXPANSION MANAGER TEST")
    
    # Create expansion manager
    project_root = Path(__file__).parent
    expansions_dir = project_root.parent / "expansions"
    
    print(f"\nProject root: {project_root}")
    print(f"Expansions dir: {expansions_dir}")
    
    manager = ExpansionManager()
    
    # Scan for expansions
    print_header("SCANNING EXPANSIONS")
    count = manager.scan_expansions(str(expansions_dir))
    print(f"\nLoaded {count} expansion pack(s)")
    
    # List loaded expansions
    for exp in manager.list_expansions():
        print(f"\n📦 {exp['name']}")
        print(f"   Instruments: {exp['instruments_count']}")
        print(f"   Target genres: {', '.join(exp['target_genres'])}")
        print(f"   Enabled: {exp['enabled']}")
    
    # Show categories
    print_header("CATEGORIES")
    categories = manager.get_categories()
    for cat, cnt in sorted(categories.items()):
        print(f"  {cat}: {cnt} instruments")
    
    # Test instrument resolution
    print_header("INSTRUMENT RESOLUTION TESTS")
    
    # Test cases: (requested_instrument, genre)
    test_cases = [
        # Exact matches
        ("piano", "rnb"),
        ("bass", "g_funk"),
        ("kick", "trap"),
        
        # Ethiopian instruments (should find substitutes)
        ("krar", "eskista"),           # Should map to guitar
        ("masenqo", "eskista"),         # Should map to synth
        ("washint", "eskista"),         # Should map to flute-like synth
        ("kebero", "eskista"),          # Should map to percussion
        
        # Genre-specific resolution
        ("808", "trap"),
        ("pad", "trap_soul"),
        ("synth", "g_funk"),
        
        # Test with non-existent instrument
        ("didgeridoo", "trap"),
    ]
    
    for requested, genre in test_cases:
        result = manager.resolve_instrument(requested, genre)
        print_result(requested, result)
    
    # Test batch resolution for Eskista
    print_header("BATCH RESOLUTION: ESKISTA FULL KIT")
    
    eskista_instruments = ["krar", "kebero", "masenqo", "washint"]
    results = manager.resolve_instrument_set(eskista_instruments, "eskista")
    
    for inst, result in results.items():
        print_result(inst, result)
    
    # Show resolution summary
    print_header("RESOLUTION SUMMARY")
    match_types = {}
    for result in results.values():
        mt = result.match_type.value
        match_types[mt] = match_types.get(mt, 0) + 1
    
    for mt, cnt in sorted(match_types.items()):
        print(f"  {mt}: {cnt}")
    
    print("\n✓ Expansion Manager test complete!")
    

if __name__ == "__main__":
    main()
