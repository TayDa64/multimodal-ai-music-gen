"""
Motif patterns library - Genre-specific motif definitions

This package contains pre-defined motif patterns for various genres.
"""

from .jazz_motifs import get_jazz_motifs
from .common_motifs import get_common_motifs

__all__ = ['get_jazz_motifs', 'get_common_motifs']
