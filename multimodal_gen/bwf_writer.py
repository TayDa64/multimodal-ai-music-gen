"""
BWF (Broadcast Wave Format) Writer Module

Implements professional BWF support with AI provenance metadata.
Ensures DAW compatibility by following strict chunk alignment and ordering.

Key Features:
- AI provenance stored in 'axml' (additional XML) chunk
- Two-byte chunk alignment for compatibility
- Strict 'fmt' before 'data' chunk ordering
- JUNK chunk handling/ignoring
- Compatible with Logic Pro X, Pro Tools, and other professional DAWs

Compliance:
- EU AI Act content disclosure requirements
- China's Deep Synthesis Regulation
- Transparent but "soft" metadata (invisible to casual listeners)
"""

import struct
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
import numpy as np

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False
    import wave

from .utils import SAMPLE_RATE, BIT_DEPTH


class BWFWriter:
    """
    Professional BWF writer with AI provenance metadata.
    
    Follows EBU Tech 3285 specification for Broadcast Wave Format.
    """
    
    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        bit_depth: int = BIT_DEPTH
    ):
        self.sample_rate = sample_rate
        self.bit_depth = bit_depth
    
    def write_bwf(
        self,
        audio_data: np.ndarray,
        output_path: str,
        ai_metadata: Optional[Dict[str, Any]] = None,
        description: str = "",
        originator: str = "Multimodal AI Music Generator",
        originator_reference: str = ""
    ):
        """
        Write audio as BWF file with AI provenance metadata.
        
        Args:
            audio_data: Audio data (numpy array, mono or stereo)
            output_path: Output file path
            ai_metadata: Dictionary of AI generation metadata
            description: Brief description for bext chunk
            originator: Software/hardware that created the file
            originator_reference: Unique identifier
        """
        # Ensure stereo format
        if len(audio_data.shape) == 1:
            audio_data = np.stack([audio_data, audio_data], axis=-1)
        elif audio_data.shape[1] == 1:
            audio_data = np.concatenate([audio_data, audio_data], axis=1)
        
        # Normalize to int16 range
        if audio_data.dtype != np.int16:
            audio_data = (audio_data * 32767).astype(np.int16)
        
        with open(output_path, 'wb') as f:
            # Calculate sizes
            num_samples = len(audio_data)
            num_channels = audio_data.shape[1]
            bytes_per_sample = self.bit_depth // 8
            data_size = num_samples * num_channels * bytes_per_sample
            
            # Prepare chunks
            fmt_chunk = self._create_fmt_chunk(num_channels, bytes_per_sample)
            bext_chunk = self._create_bext_chunk(description, originator, originator_reference)
            axml_chunk = self._create_axml_chunk(ai_metadata) if ai_metadata else b''
            data_chunk_header = self._create_data_chunk_header(data_size)
            
            # Calculate total file size
            total_size = (
                4  # 'WAVE'
                + len(fmt_chunk)
                + len(bext_chunk)
                + len(axml_chunk)
                + len(data_chunk_header)
                + data_size
            )
            
            # Ensure data_size is even (two-byte alignment)
            padding = data_size % 2
            if padding:
                total_size += 1
            
            # Write RIFF header
            f.write(b'RIFF')
            f.write(struct.pack('<I', total_size))
            f.write(b'WAVE')
            
            # CRITICAL: Write fmt chunk FIRST (before data)
            # This is required by many DAWs
            f.write(fmt_chunk)
            
            # Write bext chunk (broadcast extension)
            f.write(bext_chunk)
            
            # Write axml chunk (AI provenance)
            if axml_chunk:
                f.write(axml_chunk)
            
            # Write data chunk header
            f.write(data_chunk_header)
            
            # Write audio data
            audio_data.tofile(f)
            
            # Add padding byte if needed for alignment
            if padding:
                f.write(b'\x00')
    
    def _create_fmt_chunk(self, num_channels: int, bytes_per_sample: int) -> bytes:
        """
        Create format chunk.
        
        Format:
        - Chunk ID: 'fmt '
        - Chunk size: 16 (for PCM)
        - Audio format: 1 (PCM)
        - Num channels
        - Sample rate
        - Byte rate
        - Block align
        - Bits per sample
        """
        chunk_id = b'fmt '
        chunk_size = 16
        audio_format = 1  # PCM
        byte_rate = self.sample_rate * num_channels * bytes_per_sample
        block_align = num_channels * bytes_per_sample
        
        chunk = struct.pack(
            '<4sIHHIIHH',
            chunk_id,
            chunk_size,
            audio_format,
            num_channels,
            self.sample_rate,
            byte_rate,
            block_align,
            self.bit_depth
        )
        
        return chunk
    
    def _create_bext_chunk(
        self,
        description: str,
        originator: str,
        originator_reference: str
    ) -> bytes:
        """
        Create broadcast extension chunk.
        
        Contains professional metadata like originator, timestamp, etc.
        """
        chunk_id = b'bext'
        
        # Prepare fields (fixed-length, null-padded)
        desc_bytes = description.encode('utf-8')[:256].ljust(256, b'\x00')
        orig_bytes = originator.encode('utf-8')[:32].ljust(32, b'\x00')
        orig_ref_bytes = originator_reference.encode('utf-8')[:32].ljust(32, b'\x00')
        
        # Origination date and time
        now = datetime.now()
        date_bytes = now.strftime('%Y-%m-%d').encode('ascii').ljust(10, b'\x00')
        time_bytes = now.strftime('%H:%M:%S').encode('ascii').ljust(8, b'\x00')
        
        # Time reference (samples since midnight)
        time_ref_low = 0
        time_ref_high = 0
        
        # Version
        version = 2  # BWF version 2
        
        # UMID (Unique Material Identifier) - 64 bytes, zeros for now
        umid = b'\x00' * 64
        
        # Loudness info (version 2 extension)
        loudness_value = 0  # 0 = not measured
        loudness_range = 0
        max_true_peak = 0
        max_momentary = 0
        max_short_term = 0
        
        # Reserved
        reserved = b'\x00' * 180
        
        # Coding history (variable length, empty for now)
        coding_history = b''
        
        # Calculate chunk size
        chunk_size = (
            256 + 32 + 32 + 10 + 8 + 8 + 2 + 64 +  # Fixed fields
            2 + 2 + 2 + 2 + 2 +  # Loudness fields
            180 +  # Reserved
            len(coding_history)
        )
        
        # Ensure even size (two-byte alignment)
        if chunk_size % 2:
            chunk_size += 1
            coding_history += b'\x00'
        
        chunk = struct.pack('<4sI', chunk_id, chunk_size)
        chunk += desc_bytes
        chunk += orig_bytes
        chunk += orig_ref_bytes
        chunk += date_bytes
        chunk += time_bytes
        chunk += struct.pack('<II', time_ref_low, time_ref_high)
        chunk += struct.pack('<H', version)
        chunk += umid
        chunk += struct.pack('<HHHHH',
            loudness_value, loudness_range,
            max_true_peak, max_momentary, max_short_term
        )
        chunk += reserved
        chunk += coding_history
        
        return chunk
    
    def _create_axml_chunk(self, ai_metadata: Dict[str, Any]) -> bytes:
        """
        Create axml (additional XML) chunk for AI provenance.
        
        This is the SAFE way to store AI metadata without breaking DAW compatibility.
        The axml chunk is designed for XML-compliant structured data.
        """
        chunk_id = b'axml'
        
        # Create XML structure
        root = ET.Element('AIProv', version='1.0')
        
        # Generator info
        generator = ET.SubElement(root, 'Generator')
        ET.SubElement(generator, 'Name').text = 'Multimodal AI Music Generator'
        ET.SubElement(generator, 'Version').text = ai_metadata.get('version', '0.1.0')
        ET.SubElement(generator, 'Timestamp').text = datetime.now().isoformat()
        
        # Generation parameters
        if 'prompt' in ai_metadata:
            params = ET.SubElement(root, 'GenerationParameters')
            ET.SubElement(params, 'Prompt').text = ai_metadata['prompt']
            
            if 'bpm' in ai_metadata:
                ET.SubElement(params, 'BPM').text = str(ai_metadata['bpm'])
            if 'key' in ai_metadata:
                ET.SubElement(params, 'Key').text = ai_metadata['key']
            if 'genre' in ai_metadata:
                ET.SubElement(params, 'Genre').text = ai_metadata['genre']
        
        # Seed for reproducibility
        if 'seed' in ai_metadata:
            ET.SubElement(root, 'Seed').text = str(ai_metadata['seed'])
        
        # Synthesis parameters
        if 'synthesis_params' in ai_metadata:
            synth = ET.SubElement(root, 'SynthesisParameters')
            for key, value in ai_metadata['synthesis_params'].items():
                ET.SubElement(synth, key).text = str(value)
        
        # Regulatory compliance
        compliance = ET.SubElement(root, 'Compliance')
        ET.SubElement(compliance, 'AIGenerated').text = 'true'
        ET.SubElement(compliance, 'Standard').text = 'EU AI Act 2025, China Deep Synthesis Regulation'
        
        # Convert to bytes
        xml_str = ET.tostring(root, encoding='utf-8', method='xml')
        xml_bytes = b'<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
        
        chunk_size = len(xml_bytes)
        
        # Ensure even size (two-byte alignment)
        if chunk_size % 2:
            xml_bytes += b'\x00'
            chunk_size += 1
        
        chunk = struct.pack('<4sI', chunk_id, chunk_size)
        chunk += xml_bytes
        
        return chunk
    
    def _create_data_chunk_header(self, data_size: int) -> bytes:
        """Create data chunk header."""
        chunk_id = b'data'
        return struct.pack('<4sI', chunk_id, data_size)


def save_wav_with_ai_provenance(
    audio_data: np.ndarray,
    output_path: str,
    ai_metadata: Optional[Dict[str, Any]] = None,
    sample_rate: int = SAMPLE_RATE,
    description: str = ""
):
    """
    Convenience function to save WAV with AI provenance metadata.
    
    Args:
        audio_data: Audio data (numpy array)
        output_path: Output file path
        ai_metadata: Dictionary of AI generation metadata
        sample_rate: Sample rate
        description: Brief description
    """
    writer = BWFWriter(sample_rate=sample_rate)
    writer.write_bwf(
        audio_data,
        output_path,
        ai_metadata=ai_metadata,
        description=description
    )


def read_bwf_metadata(bwf_path: str) -> Optional[Dict[str, Any]]:
    """
    Read AI provenance metadata from BWF file.
    
    Args:
        bwf_path: Path to BWF file
        
    Returns:
        Dictionary of AI metadata or None if not found
    """
    try:
        with open(bwf_path, 'rb') as f:
            # Read RIFF header
            riff_id = f.read(4)
            if riff_id != b'RIFF':
                return None
            
            file_size = struct.unpack('<I', f.read(4))[0]
            wave_id = f.read(4)
            if wave_id != b'WAVE':
                return None
            
            # Read chunks
            metadata = {}
            
            while f.tell() < file_size + 8:
                chunk_id = f.read(4)
                if len(chunk_id) < 4:
                    break
                
                chunk_size = struct.unpack('<I', f.read(4))[0]
                
                if chunk_id == b'axml':
                    # Read AI provenance XML
                    xml_data = f.read(chunk_size)
                    
                    # Remove null padding
                    xml_data = xml_data.rstrip(b'\x00')
                    
                    # Parse XML
                    try:
                        root = ET.fromstring(xml_data)
                        
                        # Extract metadata
                        generator = root.find('Generator')
                        if generator is not None:
                            metadata['generator_name'] = generator.findtext('Name')
                            metadata['generator_version'] = generator.findtext('Version')
                            metadata['timestamp'] = generator.findtext('Timestamp')
                        
                        params = root.find('GenerationParameters')
                        if params is not None:
                            metadata['prompt'] = params.findtext('Prompt')
                            # Convert BPM to numeric type
                            bpm_text = params.findtext('BPM')
                            if bpm_text:
                                try:
                                    metadata['bpm'] = float(bpm_text)
                                except ValueError:
                                    metadata['bpm'] = bpm_text
                            metadata['key'] = params.findtext('Key')
                            metadata['genre'] = params.findtext('Genre')
                        
                        seed_elem = root.find('Seed')
                        if seed_elem is not None and seed_elem.text:
                            try:
                                metadata['seed'] = int(seed_elem.text)
                            except ValueError:
                                # If seed is not a valid integer, store as string
                                metadata['seed'] = seed_elem.text
                        
                        synth = root.find('SynthesisParameters')
                        if synth is not None:
                            metadata['synthesis_params'] = {
                                elem.tag: elem.text for elem in synth
                            }
                    
                    except ET.ParseError:
                        pass
                    
                    # Skip padding if odd size
                    if chunk_size % 2:
                        f.read(1)
                else:
                    # Skip other chunks
                    f.seek(chunk_size, 1)
                    # Skip padding if odd size
                    if chunk_size % 2:
                        f.read(1)
            
            return metadata if metadata else None
    
    except Exception as e:
        print(f"Error reading BWF metadata: {e}")
        return None
