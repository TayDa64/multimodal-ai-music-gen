"""
Common Motif Patterns

This module contains cross-genre motif patterns that work across
multiple musical styles.
"""

from typing import List
import sys
import os

# Add parent directory to path for imports when run standalone
if __name__ == '__main__':
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from multimodal_gen.motif_engine import Motif


def get_common_motifs() -> List[Motif]:
    """
    Get common cross-genre motif patterns.
    
    Returns:
        List of common Motif instances
    """
    motifs = []
    
    # 1. Major scale ascending
    motifs.append(Motif(
        name="Major Scale Ascending",
        intervals=[0, 2, 4, 5, 7, 9, 11, 12],
        rhythm=[0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
        accent_pattern=[1.0, 0.8, 0.85, 0.8, 0.9, 0.85, 0.9, 0.95],
        genre_tags=["common", "scale", "major"],
        description="Major scale ascending pattern"
    ))
    
    # 2. Minor scale ascending
    motifs.append(Motif(
        name="Natural Minor Scale Ascending",
        intervals=[0, 2, 3, 5, 7, 8, 10, 12],
        rhythm=[0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
        accent_pattern=[1.0, 0.8, 0.85, 0.8, 0.9, 0.85, 0.9, 0.95],
        genre_tags=["common", "scale", "minor"],
        description="Natural minor scale ascending"
    ))
    
    # 3. Triad arpeggio (major)
    motifs.append(Motif(
        name="Major Triad Arpeggio",
        intervals=[0, 4, 7, 12],
        rhythm=[0.5, 0.5, 0.5, 1.5],
        accent_pattern=[1.0, 0.85, 0.9, 0.95],
        genre_tags=["common", "arpeggio", "major"],
        description="Major triad arpeggio"
    ))
    
    # 4. Triad arpeggio (minor)
    motifs.append(Motif(
        name="Minor Triad Arpeggio",
        intervals=[0, 3, 7, 12],
        rhythm=[0.5, 0.5, 0.5, 1.5],
        accent_pattern=[1.0, 0.85, 0.9, 0.95],
        genre_tags=["common", "arpeggio", "minor"],
        description="Minor triad arpeggio"
    ))
    
    # 5. Stepwise motion
    motifs.append(Motif(
        name="Stepwise Ascending",
        intervals=[0, 2, 4, 5],
        rhythm=[1.0, 0.5, 0.5, 1.0],
        accent_pattern=[1.0, 0.8, 0.85, 0.9],
        genre_tags=["common", "stepwise"],
        description="Simple stepwise ascending motion"
    ))
    
    # 6. Leap and return
    motifs.append(Motif(
        name="Leap and Return",
        intervals=[0, 7, 5, 4],
        rhythm=[1.0, 0.5, 0.5, 1.0],
        accent_pattern=[1.0, 0.9, 0.8, 0.95],
        genre_tags=["common", "leap"],
        description="Leap up and stepwise return"
    ))
    
    return motifs


# =============================================================================
# MODULE TEST
# =============================================================================

if __name__ == '__main__':
    print("=== Common Motifs Test ===\n")
    
    motifs = get_common_motifs()
    print(f"Total common motifs: {len(motifs)}\n")
    
    for motif in motifs:
        print(f"- {motif.name}")
        print(f"  Intervals: {motif.intervals}")
        print(f"  Duration: {motif.get_total_duration()} beats")
        print(f"  Tags: {motif.genre_tags}")
        print()
    
    print("✅ Common motifs loaded successfully!")
