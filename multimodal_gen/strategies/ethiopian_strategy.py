"""Ethiopian genre strategies - kebero patterns, 12/8 feel."""
from typing import List

from .base import GenreStrategy, DrumConfig
from ..arranger import SongSection, SectionType
from ..prompt_parser import ParsedPrompt
from ..midi_generator import NoteEvent, generate_ethiopian_drum_pattern
from ..utils import GM_DRUM_NOTES, GM_DRUM_CHANNEL


class EthiopianStrategy(GenreStrategy):
    """
    Modern Ethiopian pop drum strategy:
    - Compound meters (6/8, 12/8) creating "triplet" feel
    - Blend of traditional and modern elements
    - Syncopated kick patterns
    - 16th note hi-hats with swing
    """
    
    @property
    def genre_name(self) -> str:
        return 'ethiopian'
    
    @property
    def supported_genres(self) -> List[str]:
        return ['ethiopian', 'ethio']
    
    def get_default_config(self) -> DrumConfig:
        return DrumConfig(
            base_velocity=95,
            swing=0.15,
            half_time=False,
            include_ghost_notes=True,
            include_rolls=False,
            density='12_8'  # Compound meter
        )
    
    def generate_drums(
        self,
        section: SongSection,
        parsed: ParsedPrompt,
        tension: float = 0.5
    ) -> List[NoteEvent]:
        """Generate Ethiopian-style drum pattern."""
        notes: List[NoteEvent] = []
        config = section.config
        
        vel_mult = self._tension_multiplier(tension, 0.90, 1.10)
        
        patterns = generate_ethiopian_drum_pattern(
            section.bars,
            style='ethiopian',
            base_velocity=int(95 * config.drum_density * vel_mult)
        )
        
        # Map Ethiopian drum types to GM percussion notes
        ethiopian_drum_mapping = {
            'kebero_bass': 'conga_low',      # Deep kebero "doom"
            'kebero_slap': 'conga_high',     # Kebero slap "tek"
            'atamo': 'bongo_high',           # Small drum
            'shaker': 'shaker',              # Maracas/shaker
            # Fallback for old-style patterns
            'kick': 'conga_low',
            'snare': 'conga_high',
            'hihat': 'shaker',
            'perc': 'bongo_high',
        }
        
        for drum_type, note_name in ethiopian_drum_mapping.items():
            if drum_type in patterns:
                for tick, dur, vel in patterns[drum_type]:
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES[note_name],
                        start_tick=section.start_tick + tick,
                        duration_ticks=dur,
                        velocity=vel,
                        channel=GM_DRUM_CHANNEL
                    ))
        
        return notes


class EthioJazzStrategy(GenreStrategy):
    """
    Ethio-Jazz drum strategy (Mulatu Astatke style):
    - Jazz kit with Ethiopian rhythmic influence
    - Ride cymbal with 12/8 feel
    - Syncopated kick patterns
    - Ghost notes for jazz feel
    """
    
    @property
    def genre_name(self) -> str:
        return 'ethio_jazz'
    
    @property
    def supported_genres(self) -> List[str]:
        return ['ethio_jazz', 'ethio-jazz', 'ethiopian_jazz']
    
    def get_default_config(self) -> DrumConfig:
        return DrumConfig(
            base_velocity=90,
            swing=0.12,
            half_time=False,
            include_ghost_notes=True,
            include_rolls=False,
            density='12_8'
        )
    
    def generate_drums(
        self,
        section: SongSection,
        parsed: ParsedPrompt,
        tension: float = 0.5
    ) -> List[NoteEvent]:
        """Generate ethio-jazz fusion pattern."""
        notes: List[NoteEvent] = []
        config = section.config
        
        vel_mult = self._tension_multiplier(tension, 0.90, 1.10)
        
        patterns = generate_ethiopian_drum_pattern(
            section.bars,
            style='ethio_jazz',
            base_velocity=int(90 * config.drum_density * vel_mult)
        )
        
        ethiopian_drum_mapping = {
            'kebero_bass': 'conga_low',
            'kebero_slap': 'conga_high',
            'atamo': 'bongo_high',
            'shaker': 'shaker',
            'kick': 'conga_low',
            'snare': 'conga_high',
            'hihat': 'shaker',
            'perc': 'bongo_high',
        }
        
        for drum_type, note_name in ethiopian_drum_mapping.items():
            if drum_type in patterns:
                for tick, dur, vel in patterns[drum_type]:
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES[note_name],
                        start_tick=section.start_tick + tick,
                        duration_ticks=dur,
                        velocity=vel,
                        channel=GM_DRUM_CHANNEL
                    ))
        
        return notes


class EthiopianTraditionalStrategy(GenreStrategy):
    """
    Traditional Ethiopian drum strategy:
    - Authentic kebero patterns
    - Slower, more deliberate
    - Call-and-response between drums
    - 12/8 time feel
    """
    
    @property
    def genre_name(self) -> str:
        return 'ethiopian_traditional'
    
    @property
    def supported_genres(self) -> List[str]:
        return ['ethiopian_traditional', 'traditional_ethiopian']
    
    def get_default_config(self) -> DrumConfig:
        return DrumConfig(
            base_velocity=95,
            swing=0.10,
            half_time=False,
            include_ghost_notes=False,
            include_rolls=False,
            density='12_8'
        )
    
    def generate_drums(
        self,
        section: SongSection,
        parsed: ParsedPrompt,
        tension: float = 0.5
    ) -> List[NoteEvent]:
        """Generate traditional Ethiopian kebero pattern."""
        notes: List[NoteEvent] = []
        config = section.config
        
        vel_mult = self._tension_multiplier(tension, 0.90, 1.10)
        
        patterns = generate_ethiopian_drum_pattern(
            section.bars,
            style='ethiopian_traditional',
            base_velocity=int(95 * config.drum_density * vel_mult)
        )
        
        ethiopian_drum_mapping = {
            'kebero_bass': 'conga_low',
            'kebero_slap': 'conga_high',
            'atamo': 'bongo_high',
            'shaker': 'shaker',
            'kick': 'conga_low',
            'snare': 'conga_high',
            'hihat': 'shaker',
            'perc': 'bongo_high',
        }
        
        for drum_type, note_name in ethiopian_drum_mapping.items():
            if drum_type in patterns:
                for tick, dur, vel in patterns[drum_type]:
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES[note_name],
                        start_tick=section.start_tick + tick,
                        duration_ticks=dur,
                        velocity=vel,
                        channel=GM_DRUM_CHANNEL
                    ))
        
        return notes


class EskistaStrategy(GenreStrategy):
    """
    Eskista drum strategy - fast shoulder dance rhythm:
    - Energetic 6/8 with strong accents
    - Characteristic bounce for shoulder movement
    - Fast tempo (100-140 BPM)
    - Strong syncopation
    """
    
    @property
    def genre_name(self) -> str:
        return 'eskista'
    
    @property
    def supported_genres(self) -> List[str]:
        return ['eskista', 'eskesta']
    
    def get_default_config(self) -> DrumConfig:
        return DrumConfig(
            base_velocity=100,
            swing=0.18,
            half_time=False,
            include_ghost_notes=True,
            include_rolls=False,
            density='12_8'
        )
    
    def generate_drums(
        self,
        section: SongSection,
        parsed: ParsedPrompt,
        tension: float = 0.5
    ) -> List[NoteEvent]:
        """Generate eskista dance rhythm."""
        notes: List[NoteEvent] = []
        config = section.config
        
        vel_mult = self._tension_multiplier(tension, 0.90, 1.10)
        
        patterns = generate_ethiopian_drum_pattern(
            section.bars,
            style='eskista',
            base_velocity=int(100 * config.drum_density * vel_mult)
        )
        
        ethiopian_drum_mapping = {
            'kebero_bass': 'conga_low',
            'kebero_slap': 'conga_high',
            'atamo': 'bongo_high',
            'shaker': 'shaker',
            'kick': 'conga_low',
            'snare': 'conga_high',
            'hihat': 'shaker',
            'perc': 'bongo_high',
        }
        
        for drum_type, note_name in ethiopian_drum_mapping.items():
            if drum_type in patterns:
                for tick, dur, vel in patterns[drum_type]:
                    notes.append(NoteEvent(
                        pitch=GM_DRUM_NOTES[note_name],
                        start_tick=section.start_tick + tick,
                        duration_ticks=dur,
                        velocity=vel,
                        channel=GM_DRUM_CHANNEL
                    ))
        
        return notes
