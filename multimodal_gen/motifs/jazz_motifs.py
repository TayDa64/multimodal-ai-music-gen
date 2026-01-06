"""
Jazz Motif Patterns

This module contains 20+ pre-defined jazz motif patterns including:
- Bebop vocabulary (enclosures, chromatic approaches, bebop scales)
- ii-V-I patterns (standard jazz voice leading)
- Blues licks (minor pentatonic, blue notes)
- Rhythmic motifs (swing eighths, anticipations, triplets)
- Call-and-response patterns

All motifs are interval-based for easy transposition.
"""

from typing import List
import sys
import os

# Add parent directory to path for imports when run standalone
if __name__ == '__main__':
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from multimodal_gen.motif_engine import Motif


def get_jazz_motifs() -> List[Motif]:
    """
    Get all jazz motif patterns.
    
    Returns:
        List of jazz Motif instances (20+ patterns)
    """
    motifs = []
    
    # =========================================================================
    # BEBOP VOCABULARY
    # =========================================================================
    
    # 1. Chromatic enclosure from above and below
    motifs.append(Motif(
        name="Bebop Chromatic Enclosure",
        intervals=[1, -1, 0],  # Half step above, half below, target
        rhythm=[0.25, 0.25, 0.5],
        accent_pattern=[0.8, 0.7, 1.0],
        genre_tags=["jazz", "bebop", "enclosure"],
        description="Classic bebop enclosure: approach target note from above and below"
    ))
    
    # 2. Chromatic approach from above
    motifs.append(Motif(
        name="Bebop Chromatic Approach Above",
        intervals=[1, 0],  # Half step above, target
        rhythm=[0.25, 0.75],
        accent_pattern=[0.7, 1.0],
        genre_tags=["jazz", "bebop", "chromatic"],
        description="Bebop chromatic approach from above"
    ))
    
    # 3. Chromatic approach from below
    motifs.append(Motif(
        name="Bebop Chromatic Approach Below",
        intervals=[-1, 0],  # Half step below, target
        rhythm=[0.25, 0.75],
        accent_pattern=[0.7, 1.0],
        genre_tags=["jazz", "bebop", "chromatic"],
        description="Bebop chromatic approach from below"
    ))
    
    # 4. Bebop scale run (major bebop: adds passing tone between 5 and 6)
    # Assumption: bebop major scale = major scale + chromatic passing tone between 5 and 6
    motifs.append(Motif(
        name="Bebop Major Scale Run",
        intervals=[0, 2, 4, 5, 7, 8, 9, 11],  # C D E F G G# A B
        rhythm=[0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],
        accent_pattern=[1.0, 0.8, 0.85, 0.8, 0.9, 0.7, 0.85, 0.9],
        genre_tags=["jazz", "bebop", "scale"],
        description="Bebop major scale with chromatic passing tone"
    ))
    
    # 5. Bebop dominant scale (adds passing tone between b7 and root)
    motifs.append(Motif(
        name="Bebop Dominant Scale Run",
        intervals=[0, 2, 4, 5, 7, 9, 10, 11],  # C D E F G A Bb B
        rhythm=[0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],
        accent_pattern=[1.0, 0.8, 0.85, 0.8, 0.9, 0.85, 0.8, 0.9],
        genre_tags=["jazz", "bebop", "scale", "dominant"],
        chord_context="dominant7",
        description="Bebop dominant scale for V7 chords"
    ))
    
    # 6. Parker lick (classic Charlie Parker phrase)
    motifs.append(Motif(
        name="Parker Lick",
        intervals=[0, 4, 7, 9, 7, 5, 4],  # Root, 3rd, 5th, 6th, 5th, 4th, 3rd
        rhythm=[0.5, 0.25, 0.25, 0.5, 0.25, 0.25, 0.5],
        accent_pattern=[1.0, 0.9, 0.85, 0.95, 0.8, 0.8, 0.9],
        genre_tags=["jazz", "bebop", "classic"],
        description="Classic Charlie Parker-style bebop lick"
    ))
    
    # =========================================================================
    # II-V-I PATTERNS
    # =========================================================================
    
    # 7. ii-V-I voice leading (minor7 to dominant7 to major7)
    motifs.append(Motif(
        name="ii-V-I Voice Leading",
        intervals=[0, 3, 7, 10, 0, 4, 7, 10],  # ii: Dm7 chord tones, then V: G7 tones
        rhythm=[0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
        accent_pattern=[1.0, 0.85, 0.9, 0.85, 1.0, 0.9, 0.9, 0.85],
        genre_tags=["jazz", "ii-V-I", "voice-leading"],
        description="Classic ii-V-I progression voice leading"
    ))
    
    # 8. ii-V resolution to I (targeting 3rd of tonic)
    motifs.append(Motif(
        name="ii-V Resolution",
        intervals=[10, 9, 7, 4],  # b7 of V, 6th, 5th, 3rd of I
        rhythm=[0.5, 0.25, 0.25, 1.0],
        accent_pattern=[0.85, 0.8, 0.85, 1.0],
        genre_tags=["jazz", "ii-V-I", "resolution"],
        description="ii-V resolution targeting 3rd of I chord"
    ))
    
    # 9. ii-V approach with enclosure
    motifs.append(Motif(
        name="ii-V Enclosure Approach",
        intervals=[0, 2, 1, 0, 4],  # Enclosure to root, then 3rd
        rhythm=[0.25, 0.25, 0.25, 0.25, 1.0],
        accent_pattern=[0.8, 0.7, 0.75, 0.9, 1.0],
        genre_tags=["jazz", "ii-V-I", "enclosure"],
        chord_context="dominant7",
        description="ii-V approach using chromatic enclosure"
    ))
    
    # =========================================================================
    # BLUES LICKS
    # =========================================================================
    
    # 10. Minor pentatonic blues lick
    motifs.append(Motif(
        name="Minor Pentatonic Blues",
        intervals=[0, 3, 5, 7, 10],  # Minor pentatonic: root, b3, 4th, 5th, b7
        rhythm=[0.5, 0.5, 0.5, 0.5, 1.0],
        accent_pattern=[1.0, 0.9, 0.85, 0.9, 0.95],
        genre_tags=["jazz", "blues", "pentatonic"],
        description="Classic minor pentatonic blues lick"
    ))
    
    # 11. Blue note lick (with b5)
    motifs.append(Motif(
        name="Blue Note Lick",
        intervals=[0, 3, 6, 7],  # Root, b3, b5 (blue note), 5th
        rhythm=[0.5, 0.5, 0.25, 0.75],
        accent_pattern=[1.0, 0.9, 0.85, 0.95],
        genre_tags=["jazz", "blues", "blue-note"],
        description="Blues lick featuring the b5 blue note"
    ))
    
    # 12. Blues turnaround
    motifs.append(Motif(
        name="Blues Turnaround",
        intervals=[0, -1, -2, -3, -5],  # Descending chromatic
        rhythm=[0.5, 0.5, 0.5, 0.5, 1.0],
        accent_pattern=[1.0, 0.85, 0.8, 0.85, 0.9],
        genre_tags=["jazz", "blues", "turnaround"],
        description="Classic blues turnaround phrase"
    ))
    
    # 13. Blues scale ascending
    motifs.append(Motif(
        name="Blues Scale Ascending",
        intervals=[0, 3, 5, 6, 7, 10],  # Blues scale: root, b3, 4, b5, 5, b7
        rhythm=[0.5, 0.5, 0.25, 0.25, 0.5, 1.0],
        accent_pattern=[1.0, 0.9, 0.8, 0.75, 0.9, 0.95],
        genre_tags=["jazz", "blues", "scale"],
        description="Ascending blues scale phrase"
    ))
    
    # =========================================================================
    # RHYTHMIC MOTIFS
    # =========================================================================
    
    # 14. Swing eighth notes with anticipation
    motifs.append(Motif(
        name="Swing Eighths",
        intervals=[0, 2, 4, 5, 7],
        rhythm=[0.67, 0.33, 0.67, 0.33, 1.0],  # Swung rhythms
        accent_pattern=[1.0, 0.7, 0.9, 0.7, 0.95],
        genre_tags=["jazz", "swing", "rhythmic"],
        description="Swung eighth note pattern with anticipation"
    ))
    
    # 15. Triplet figure
    motifs.append(Motif(
        name="Jazz Triplet",
        intervals=[0, 2, 4],
        rhythm=[0.33, 0.33, 0.34],  # Eighth note triplet
        accent_pattern=[1.0, 0.8, 0.9],
        genre_tags=["jazz", "triplet", "rhythmic"],
        description="Eighth note triplet figure"
    ))
    
    # 16. Anticipation motif (landing on "and" of 4)
    motifs.append(Motif(
        name="Anticipation",
        intervals=[0, 2, 4, 7],
        rhythm=[1.0, 0.5, 0.5, 1.0],  # Last note anticipated
        accent_pattern=[1.0, 0.8, 0.85, 0.95],
        genre_tags=["jazz", "anticipation", "rhythmic"],
        description="Phrase with rhythmic anticipation"
    ))
    
    # 17. Syncopated rhythm
    motifs.append(Motif(
        name="Syncopated Jazz Phrase",
        intervals=[0, 4, 7, 9, 7],
        rhythm=[0.75, 0.25, 0.5, 0.25, 1.25],  # Syncopated
        accent_pattern=[1.0, 0.75, 0.9, 0.8, 0.95],
        genre_tags=["jazz", "syncopation", "rhythmic"],
        description="Syncopated jazz phrase"
    ))
    
    # =========================================================================
    # CALL AND RESPONSE
    # =========================================================================
    
    # 18. Call phrase (question)
    motifs.append(Motif(
        name="Call Phrase",
        intervals=[0, 2, 4, 5],  # Ascending, open-ended
        rhythm=[0.5, 0.5, 0.5, 1.5],
        accent_pattern=[1.0, 0.85, 0.9, 0.85],
        genre_tags=["jazz", "call-response", "call"],
        description="Call phrase - asks a musical question"
    ))
    
    # 19. Response phrase (answer)
    motifs.append(Motif(
        name="Response Phrase",
        intervals=[7, 5, 4, 0],  # Descending, resolving
        rhythm=[0.5, 0.5, 0.5, 1.5],
        accent_pattern=[0.9, 0.85, 0.9, 1.0],
        genre_tags=["jazz", "call-response", "response"],
        description="Response phrase - answers the call"
    ))
    
    # 20. Call-response pair (complete)
    motifs.append(Motif(
        name="Call-Response Complete",
        intervals=[0, 2, 4, 5, 7, 5, 4, 0],
        rhythm=[0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 1.5],
        accent_pattern=[1.0, 0.85, 0.9, 0.85, 0.9, 0.85, 0.9, 1.0],
        genre_tags=["jazz", "call-response"],
        description="Complete call-response phrase"
    ))
    
    # =========================================================================
    # ADDITIONAL JAZZ VOCABULARY
    # =========================================================================
    
    # 21. Tritone substitution lick
    motifs.append(Motif(
        name="Tritone Sub Lick",
        intervals=[0, 4, 6, 10],  # Root, 3rd, tritone, b7
        rhythm=[0.5, 0.25, 0.25, 1.0],
        accent_pattern=[1.0, 0.85, 0.8, 0.95],
        genre_tags=["jazz", "tritone", "substitution"],
        chord_context="dominant7",
        description="Tritone substitution approach"
    ))
    
    # 22. Diminished scale pattern
    motifs.append(Motif(
        name="Diminished Scale Pattern",
        intervals=[0, 2, 3, 5, 6, 8, 9, 11],  # Whole-half diminished
        rhythm=[0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25],
        accent_pattern=[1.0, 0.8, 0.85, 0.8, 0.9, 0.8, 0.85, 0.9],
        genre_tags=["jazz", "diminished", "scale"],
        chord_context="dominant7",
        description="Diminished scale pattern for dominant chords"
    ))
    
    # 23. Arpeggiated dominant 7th
    motifs.append(Motif(
        name="Dominant 7th Arpeggio",
        intervals=[0, 4, 7, 10, 12],  # Root, 3, 5, b7, octave
        rhythm=[0.5, 0.5, 0.5, 0.5, 1.0],
        accent_pattern=[1.0, 0.85, 0.9, 0.85, 0.95],
        genre_tags=["jazz", "arpeggio", "dominant"],
        chord_context="dominant7",
        description="Dominant 7th chord arpeggio"
    ))
    
    # 24. Minor 7th arpeggio
    motifs.append(Motif(
        name="Minor 7th Arpeggio",
        intervals=[0, 3, 7, 10, 12],  # Root, b3, 5, b7, octave
        rhythm=[0.5, 0.5, 0.5, 0.5, 1.0],
        accent_pattern=[1.0, 0.85, 0.9, 0.85, 0.95],
        genre_tags=["jazz", "arpeggio", "minor"],
        chord_context="minor7",
        description="Minor 7th chord arpeggio"
    ))
    
    # 25. Major 7th arpeggio
    motifs.append(Motif(
        name="Major 7th Arpeggio",
        intervals=[0, 4, 7, 11, 12],  # Root, 3, 5, 7, octave
        rhythm=[0.5, 0.5, 0.5, 0.5, 1.0],
        accent_pattern=[1.0, 0.85, 0.9, 0.85, 0.95],
        genre_tags=["jazz", "arpeggio", "major"],
        chord_context="major7",
        description="Major 7th chord arpeggio"
    ))
    
    return motifs


# =============================================================================
# MODULE TEST
# =============================================================================

if __name__ == '__main__':
    print("=== Jazz Motifs Test ===\n")
    
    motifs = get_jazz_motifs()
    print(f"Total jazz motifs: {len(motifs)}\n")
    
    # Group by category
    categories = {}
    for motif in motifs:
        # Find primary category from tags
        category = "other"
        if "bebop" in motif.genre_tags:
            category = "bebop"
        elif "ii-V-I" in motif.genre_tags:
            category = "ii-V-I"
        elif "blues" in motif.genre_tags:
            category = "blues"
        elif "rhythmic" in motif.genre_tags:
            category = "rhythmic"
        elif "call-response" in motif.genre_tags:
            category = "call-response"
        elif "arpeggio" in motif.genre_tags:
            category = "arpeggios"
        
        if category not in categories:
            categories[category] = []
        categories[category].append(motif)
    
    # Print by category
    for category, cat_motifs in categories.items():
        print(f"[{category.upper()}] ({len(cat_motifs)} motifs)")
        for motif in cat_motifs:
            print(f"  - {motif.name}")
            print(f"    Intervals: {motif.intervals}")
            print(f"    Duration: {motif.get_total_duration()} beats")
            if motif.chord_context:
                print(f"    Context: {motif.chord_context}")
        print()
    
    print("✅ Jazz motifs loaded successfully!")
