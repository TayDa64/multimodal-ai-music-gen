# XML Schema Validation for Music Production Formats

## Research Report

**Date:** January 20, 2026  
**Scope:** MusicXML validation, Akai MPC file formats, Python XML validation libraries, DAW plugin validation, schema inference

---

## Executive Summary

This research report addresses XML schema validation strategies for music production formats, specifically targeting:
1. Validation without official XSD schemas (common in proprietary DAW formats)
2. Schema inference from known-good MPC project exports
3. CI/CD integration for automated validation
4. Graceful degradation patterns when validation fails

---

## 1. MusicXML Schema Validation Approaches

### Official MusicXML XSD Schemas

MusicXML 4.0 (released June 2021) provides **official W3C XML Schema (XSD) definitions**:

| Schema File | Purpose |
|-------------|---------|
| `musicxml.xsd` | Main score/part schema |
| `container.xsd` | Compressed MXL container |
| `opus.xsd` | Multi-score collections |
| `sounds.xsd` | Standard instrument sounds |
| `xlink.xsd` | XLink support |
| `xml.xsd` | Base XML namespace |

**Source:** [W3C MusicXML 4.0](https://www.w3.org/2021/06/musicxml40/)

### Python Validation with MusicXML

```python
import xmlschema
from pathlib import Path

# Load official MusicXML schema
musicxml_schema = xmlschema.XMLSchema('musicxml.xsd')

# Validate a MusicXML file
def validate_musicxml(file_path: str) -> tuple[bool, list]:
    """Validate MusicXML file against official schema."""
    try:
        musicxml_schema.validate(file_path)
        return True, []
    except xmlschema.XMLSchemaValidationError as e:
        return False, list(musicxml_schema.iter_errors(file_path))
```

### Key MusicXML Validation Features

1. **XSD 1.0 compliant** - Works with all major XML validators
2. **Namespace-aware** - Uses `http://www.musicxml.com/ns/...` namespaces
3. **Versioned schemas** - Backward compatible from 1.0 → 4.0
4. **XSLT transforms** - Includes `to31.xsl`, `to30.xsl` for version conversion

---

## 2. Akai MPC Project File Format Documentation

### Overview

Akai MPC Software (2.x+) uses **XML-based project files** with the following structure:

| Extension | Format | Purpose |
|-----------|--------|---------|
| `.xpj` | XML | Main project file |
| `.xpm` | XML | Drum program definitions |
| `.xal` | XML | Audio layer references |

### MPC Project Structure

```
project.xpj                  # Main project XML
[ProjectData]/              # Sibling folder (required naming)
    ├── Drums.xpm           # Drum program files
    ├── Samples/            # Audio samples
    │   ├── kick.wav
    │   └── snare.wav
    └── ...
```

### XPJ File Format (Reverse-Engineered Structure)

Based on analysis of the existing `mpc_exporter.py`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<MPCVObject Version="2.0" Application="MPC" ApplicationVersion="2.13.1">
    <Metadata>
        <Name>Project Name</Name>
        <CreatedDate>2026-01-20T12:00:00</CreatedDate>
        <ModifiedDate>2026-01-20T12:00:00</ModifiedDate>
        <UUID>XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX</UUID>
    </Metadata>
    
    <MasterSettings>
        <Tempo>120.0</Tempo>
        <TimeSignatureNumerator>4</TimeSignatureNumerator>
        <TimeSignatureDenominator>4</TimeSignatureDenominator>
        <MasterVolume>0.8</MasterVolume>
        <PPQ>480</PPQ>
        <Metronome>
            <Enabled>false</Enabled>
            <Volume>0.5</Volume>
            <CountIn>1</CountIn>
        </Metronome>
    </MasterSettings>
    
    <Programs>
        <Program Index="0">
            <Name>Drums</Name>
            <Type>Drum</Type>
            <FilePath>[ProjectData]/Drums.xpm</FilePath>
            <UUID>...</UUID>
            <MasterVolume>0.8</MasterVolume>
        </Program>
    </Programs>
    
    <Sequences>
        <Sequence Index="0">
            <Name>Sequence 1</Name>
            <UUID>...</UUID>
            <Bars>4</Bars>
            <Tempo>120.0</Tempo>
            <TimeSignatureNumerator>4</TimeSignatureNumerator>
            <TimeSignatureDenominator>4</TimeSignatureDenominator>
            <LengthTicks>7680</LengthTicks>
            <Tracks>
                <Track Index="0">
                    <Name>Track 1</Name>
                    <ProgramName>Drums</ProgramName>
                    <Volume>0.8</Volume>
                    <Pan>0.5</Pan>
                    <Mute>false</Mute>
                    <Solo>false</Solo>
                    <MidiChannel>10</MidiChannel>
                    <Events>
                        <NoteEvent>
                            <Tick>0</Tick>
                            <Note>36</Note>
                            <Velocity>100</Velocity>
                            <Duration>240</Duration>
                        </NoteEvent>
                    </Events>
                </Track>
            </Tracks>
        </Sequence>
    </Sequences>
    
    <AudioPool>
        <AudioFile Index="0">
            <Name>kick</Name>
            <FilePath>[ProjectData]/Samples/kick.wav</FilePath>
            <UUID>...</UUID>
        </AudioFile>
    </AudioPool>
</MPCVObject>
```

### XPM Drum Program Format

```xml
<?xml version="1.0" encoding="utf-8"?>
<MPCVObject Version="2.0" Application="MPC" ApplicationVersion="2.13.1" Type="DrumProgram">
    <Metadata>
        <Name>Drums</Name>
        <UUID>...</UUID>
        <MasterVolume>0.8</MasterVolume>
    </Metadata>
    
    <PadBanks>
        <Bank Name="A">
            <Pad Number="0">
                <Name>Kick</Name>
                <MidiNote>36</MidiNote>
                <Volume>1.0</Volume>
                <Pan>0.5</Pan>
                <Tune>0.0</Tune>
                <Attack>0.0</Attack>
                <Decay>1.0</Decay>
                <MuteGroup>0</MuteGroup>
                <Layers>
                    <Layer Index="0">
                        <FilePath>[ProjectData]/Samples/kick.wav</FilePath>
                        <VelocityLow>0</VelocityLow>
                        <VelocityHigh>127</VelocityHigh>
                    </Layer>
                </Layers>
            </Pad>
        </Bank>
    </PadBanks>
</MPCVObject>
```

### Important MPC Technical Specifications

| Property | Value | Notes |
|----------|-------|-------|
| **PPQ** | 480 | Pulses Per Quarter note (matches MIDI standard) |
| **Pad Banks** | A-H | 8 banks |
| **Pads per Bank** | 16 | 0-15 index |
| **MIDI Note Range** | 0-127 | Bank A starts at 36 (C1) |
| **Path Format** | Relative | Uses `[ProjectData]/` prefix |
| **Audio Formats** | WAV | 16/24-bit, 44.1/48kHz |

---

## 3. XML Schema Validation in Python

### Library Comparison

| Library | XSD Support | Features | Performance |
|---------|-------------|----------|-------------|
| **xmlschema** | XSD 1.0/1.1 | Validation, encoding, decoding | Moderate |
| **lxml** | XSD, DTD, RelaxNG, Schematron | Fast C-based, full featured | Fast |
| **defusedxml** | N/A | Security-focused parsing | Fast |

### xmlschema Library (Recommended)

```python
import xmlschema

# Create schema from XSD file
schema = xmlschema.XMLSchema('schema.xsd')

# Validation methods
schema.is_valid('document.xml')        # Returns bool
schema.validate('document.xml')         # Raises on error
list(schema.iter_errors('document.xml')) # Returns all errors

# Decode to Python dict
data = schema.to_dict('document.xml')

# Encode Python dict to XML
schema.encode(data, path='output.xml')

# XSD 1.1 support
schema11 = xmlschema.XMLSchema11('schema11.xsd')
```

### lxml Library (Performance-Critical)

```python
from lxml import etree
from io import StringIO

# XSD validation
xsd_doc = etree.parse('schema.xsd')
xsd_schema = etree.XMLSchema(xsd_doc)

# Validate
xml_doc = etree.parse('document.xml')
is_valid = xsd_schema.validate(xml_doc)

# Get errors
if not is_valid:
    for error in xsd_schema.error_log:
        print(f"Line {error.line}: {error.message}")

# RelaxNG validation
rng_doc = etree.parse('schema.rng')
relaxng = etree.RelaxNG(rng_doc)
relaxng.validate(xml_doc)

# Schematron validation (ISO-Schematron)
from lxml import isoschematron
schematron = isoschematron.Schematron(etree.parse('rules.sch'))
schematron.validate(xml_doc)
```

### Validation at Parse Time

```python
from lxml import etree

# DTD validation during parsing
parser = etree.XMLParser(dtd_validation=True)
tree = etree.parse('document.xml', parser)

# XSD validation during parsing
schema = etree.XMLSchema(etree.parse('schema.xsd'))
parser = etree.XMLParser(schema=schema)
root = etree.fromstring(xml_content, parser)
```

---

## 4. DAW Plugin Format Validation Approaches

### VST3 Module Architecture

VST3 uses **COM-like interface architecture** (not XML-based):

- **Binary format** with defined interfaces
- **IPluginFactory** for component discovery
- **Version-controlled interfaces** (never change after release)
- **UUID-based identification** for components

### Plugin State Validation Patterns

DAW plugins typically validate state through:

1. **Magic bytes/headers** - Binary format identification
2. **Version fields** - Forward/backward compatibility checks
3. **Checksum/CRC** - Data integrity verification
4. **Schema versioning** - Migrate old formats automatically

### Lessons for MPC Validation

```python
class MpcValidator:
    """Validation patterns inspired by DAW plugins."""
    
    MAGIC_HEADER = "MPCVObject"
    SUPPORTED_VERSIONS = ["1.0", "2.0"]
    
    def validate_structure(self, root: ET.Element) -> bool:
        """Check basic structure validity."""
        if root.tag != self.MAGIC_HEADER:
            return False
        
        version = root.get("Version")
        if version not in self.SUPPORTED_VERSIONS:
            return False
            
        return True
    
    def validate_with_migration(self, root: ET.Element) -> ET.Element:
        """Validate and migrate older formats."""
        version = root.get("Version")
        
        if version == "1.0":
            root = self._migrate_v1_to_v2(root)
            
        return root
```

---

## 5. Schema Inference from Example Files

### Approaches Without Official XSD

When no official schema exists (like MPC formats), use these strategies:

#### Strategy 1: Trang Schema Inference

[Trang](https://relaxng.org/jclark/trang.html) can infer schemas from XML examples:

```bash
# Generate RelaxNG from examples
java -jar trang.jar example1.xpj example2.xpj mpc.rng

# Convert RelaxNG to XSD
java -jar trang.jar mpc.rng mpc.xsd
```

#### Strategy 2: Python-Based Schema Mining

```python
from collections import defaultdict
from typing import Set, Dict
import xml.etree.ElementTree as ET

class SchemaInferencer:
    """Infer XML schema from example files."""
    
    def __init__(self):
        self.elements: Dict[str, Set[str]] = defaultdict(set)  # tag -> child tags
        self.attributes: Dict[str, Set[str]] = defaultdict(set)  # tag -> attr names
        self.required_children: Dict[str, Set[str]] = defaultdict(set)
        self.text_elements: Set[str] = set()
        
    def analyze_file(self, file_path: str) -> None:
        """Analyze XML file structure."""
        tree = ET.parse(file_path)
        self._analyze_element(tree.getroot())
        
    def _analyze_element(self, elem: ET.Element, parent: str = None) -> None:
        """Recursively analyze element structure."""
        tag = elem.tag
        
        # Track parent-child relationships
        if parent:
            self.elements[parent].add(tag)
            
        # Track attributes
        for attr in elem.attrib:
            self.attributes[tag].add(attr)
            
        # Track text content
        if elem.text and elem.text.strip():
            self.text_elements.add(tag)
            
        # Recurse
        for child in elem:
            self._analyze_element(child, tag)
            
    def generate_xsd(self) -> str:
        """Generate XSD from analysis."""
        lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        lines.append('<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">')
        
        for tag, children in self.elements.items():
            lines.append(f'  <xs:element name="{tag}">')
            lines.append('    <xs:complexType>')
            
            if children:
                lines.append('      <xs:sequence>')
                for child in sorted(children):
                    lines.append(f'        <xs:element ref="{child}" minOccurs="0" maxOccurs="unbounded"/>')
                lines.append('      </xs:sequence>')
                
            for attr in sorted(self.attributes.get(tag, [])):
                lines.append(f'      <xs:attribute name="{attr}" type="xs:string"/>')
                
            lines.append('    </xs:complexType>')
            lines.append('  </xs:element>')
            
        lines.append('</xs:schema>')
        return '\n'.join(lines)


# Usage
inferencer = SchemaInferencer()
inferencer.analyze_file('known_good_1.xpj')
inferencer.analyze_file('known_good_2.xpj')
xsd_content = inferencer.generate_xsd()
```

#### Strategy 3: Structural Validation (No Schema)

```python
class MpcStructuralValidator:
    """Validate MPC XML structure without XSD."""
    
    REQUIRED_ROOT_CHILDREN = {'Metadata', 'MasterSettings', 'Programs', 'Sequences'}
    REQUIRED_METADATA = {'Name', 'UUID'}
    REQUIRED_MASTER = {'Tempo', 'PPQ'}
    
    def validate(self, file_path: str) -> tuple[bool, list[str]]:
        """Validate MPC file structure."""
        errors = []
        
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except ET.ParseError as e:
            return False, [f"XML parse error: {e}"]
            
        # Check root element
        if root.tag != 'MPCVObject':
            errors.append(f"Invalid root element: {root.tag}")
            
        # Check version attribute
        version = root.get('Version')
        if not version:
            errors.append("Missing Version attribute")
        elif version not in ['1.0', '2.0']:
            errors.append(f"Unknown version: {version}")
            
        # Check required sections
        child_tags = {child.tag for child in root}
        missing = self.REQUIRED_ROOT_CHILDREN - child_tags
        if missing:
            errors.append(f"Missing sections: {missing}")
            
        # Validate Metadata
        metadata = root.find('Metadata')
        if metadata is not None:
            metadata_tags = {child.tag for child in metadata}
            missing_meta = self.REQUIRED_METADATA - metadata_tags
            if missing_meta:
                errors.append(f"Missing metadata fields: {missing_meta}")
                
        # Validate numeric fields
        errors.extend(self._validate_numeric_fields(root))
        
        return len(errors) == 0, errors
        
    def _validate_numeric_fields(self, root: ET.Element) -> list[str]:
        """Validate numeric field values."""
        errors = []
        
        # Tempo validation
        master = root.find('MasterSettings')
        if master is not None:
            tempo_elem = master.find('Tempo')
            if tempo_elem is not None and tempo_elem.text:
                try:
                    tempo = float(tempo_elem.text)
                    if not (20 <= tempo <= 999):
                        errors.append(f"Tempo out of range: {tempo}")
                except ValueError:
                    errors.append(f"Invalid tempo value: {tempo_elem.text}")
                    
            ppq_elem = master.find('PPQ')
            if ppq_elem is not None and ppq_elem.text:
                try:
                    ppq = int(ppq_elem.text)
                    if ppq not in [96, 120, 240, 480, 960]:
                        errors.append(f"Non-standard PPQ: {ppq}")
                except ValueError:
                    errors.append(f"Invalid PPQ value: {ppq_elem.text}")
                    
        return errors
```

---

## 6. Automated Validation in CI/CD

### GitHub Actions Workflow

```yaml
# .github/workflows/validate-mpc.yml
name: Validate MPC Exports

on:
  push:
    paths:
      - 'multimodal_gen/mpc_exporter.py'
      - 'tests/test_mpc_*.py'
  pull_request:
    paths:
      - 'multimodal_gen/mpc_exporter.py'

jobs:
  validate:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          pip install xmlschema lxml pytest
          pip install -r requirements.txt
          
      - name: Generate test exports
        run: |
          python -c "
          from multimodal_gen.mpc_exporter import MpcExporter, create_default_drum_program
          exporter = MpcExporter('./test_output')
          program = create_default_drum_program()
          # Generate test files...
          "
          
      - name: Validate XML structure
        run: python tests/validate_mpc_structure.py
        
      - name: Validate against inferred schema
        run: python tests/validate_mpc_schema.py
        
      - name: Upload validation report
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: validation-errors
          path: test_output/validation_report.json
```

### pytest Integration

```python
# tests/test_mpc_validation.py
import pytest
import xml.etree.ElementTree as ET
from pathlib import Path
from multimodal_gen.mpc_exporter import MpcExporter, generate_xpj, generate_xpm

class TestMpcValidation:
    """Comprehensive MPC export validation tests."""
    
    @pytest.fixture
    def sample_project(self, tmp_path):
        """Create sample MPC project for testing."""
        from multimodal_gen.mpc_exporter import MpcProject, create_default_drum_program
        return MpcProject(
            name="Test Project",
            bpm=120.0,
            programs=[create_default_drum_program()],
        )
    
    def test_xpj_is_valid_xml(self, sample_project):
        """Verify XPJ output is valid XML."""
        xpj_content = generate_xpj(sample_project)
        
        # Should not raise
        root = ET.fromstring(xpj_content)
        assert root.tag == "MPCVObject"
        
    def test_xpj_has_required_sections(self, sample_project):
        """Verify XPJ has all required sections."""
        xpj_content = generate_xpj(sample_project)
        root = ET.fromstring(xpj_content)
        
        required = {'Metadata', 'MasterSettings', 'Programs', 'Sequences', 'AudioPool'}
        present = {child.tag for child in root}
        
        assert required.issubset(present), f"Missing: {required - present}"
        
    def test_xpj_version_attribute(self, sample_project):
        """Verify version attribute is correct."""
        xpj_content = generate_xpj(sample_project)
        root = ET.fromstring(xpj_content)
        
        assert root.get('Version') == '2.0'
        assert root.get('Application') == 'MPC'
        
    def test_tempo_in_valid_range(self, sample_project):
        """Verify tempo is within MPC valid range."""
        xpj_content = generate_xpj(sample_project)
        root = ET.fromstring(xpj_content)
        
        tempo = float(root.find('.//Tempo').text)
        assert 20 <= tempo <= 999, f"Tempo {tempo} out of range"
        
    def test_ppq_is_standard(self, sample_project):
        """Verify PPQ is MPC standard 480."""
        xpj_content = generate_xpj(sample_project)
        root = ET.fromstring(xpj_content)
        
        ppq = int(root.find('.//PPQ').text)
        assert ppq == 480, f"Non-standard PPQ: {ppq}"
        
    def test_relative_paths_only(self, sample_project):
        """Verify no absolute paths in project."""
        xpj_content = generate_xpj(sample_project)
        root = ET.fromstring(xpj_content)
        
        for elem in root.iter():
            if elem.text and ('FilePath' in elem.tag or 'Path' in elem.tag):
                path = elem.text
                assert path.startswith('[ProjectData]') or not Path(path).is_absolute(), \
                    f"Absolute path found: {path}"
                    
    def test_uuid_format(self, sample_project):
        """Verify UUIDs are properly formatted."""
        import re
        uuid_pattern = re.compile(
            r'^[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}$'
        )
        
        xpj_content = generate_xpj(sample_project)
        root = ET.fromstring(xpj_content)
        
        for uuid_elem in root.iter('UUID'):
            if uuid_elem.text:
                assert uuid_pattern.match(uuid_elem.text), \
                    f"Invalid UUID format: {uuid_elem.text}"
```

---

## 7. Graceful Degradation When Validation Fails

### Error Classification

```python
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional

class ValidationSeverity(Enum):
    """Validation error severity levels."""
    CRITICAL = auto()  # Cannot load/use file
    ERROR = auto()     # Missing required data, may cause issues
    WARNING = auto()   # Non-standard but loadable
    INFO = auto()      # Minor deviation, informational

@dataclass
class ValidationError:
    """Structured validation error."""
    severity: ValidationSeverity
    code: str
    message: str
    path: str  # XPath to problematic element
    suggestion: Optional[str] = None
    
    def __str__(self):
        return f"[{self.severity.name}] {self.code}: {self.message} at {self.path}"
```

### Graceful Degradation Strategy

```python
class MpcValidatorWithFallback:
    """Validator with graceful degradation support."""
    
    def validate_with_fallback(self, file_path: str) -> tuple[ET.Element, list[ValidationError]]:
        """
        Validate and attempt to fix/degrade gracefully.
        
        Returns:
            Tuple of (possibly-fixed root element, list of errors/warnings)
        """
        errors = []
        
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except ET.ParseError as e:
            # CRITICAL: Cannot even parse
            raise ValidationException(f"Invalid XML: {e}")
            
        # Fix missing version (WARNING level - can default)
        if not root.get('Version'):
            root.set('Version', '2.0')
            errors.append(ValidationError(
                severity=ValidationSeverity.WARNING,
                code='MISSING_VERSION',
                message='Version attribute missing, defaulting to 2.0',
                path='/MPCVObject',
                suggestion='Add Version="2.0" attribute to root element'
            ))
            
        # Fix missing sections (ERROR level - may cause issues)
        required_sections = {
            'Metadata': self._create_default_metadata,
            'MasterSettings': self._create_default_master,
        }
        
        for section, factory in required_sections.items():
            if root.find(section) is None:
                root.append(factory())
                errors.append(ValidationError(
                    severity=ValidationSeverity.ERROR,
                    code=f'MISSING_{section.upper()}',
                    message=f'{section} section missing, using defaults',
                    path=f'/MPCVObject/{section}',
                    suggestion=f'Add required {section} element'
                ))
                
        # Validate and clamp numeric ranges (WARNING level)
        master = root.find('MasterSettings')
        if master is not None:
            tempo_elem = master.find('Tempo')
            if tempo_elem is not None and tempo_elem.text:
                try:
                    tempo = float(tempo_elem.text)
                    if tempo < 20:
                        tempo_elem.text = '20.0'
                        errors.append(ValidationError(
                            severity=ValidationSeverity.WARNING,
                            code='TEMPO_TOO_LOW',
                            message=f'Tempo {tempo} below minimum, clamped to 20',
                            path='/MPCVObject/MasterSettings/Tempo'
                        ))
                    elif tempo > 999:
                        tempo_elem.text = '999.0'
                        errors.append(ValidationError(
                            severity=ValidationSeverity.WARNING,
                            code='TEMPO_TOO_HIGH',
                            message=f'Tempo {tempo} above maximum, clamped to 999',
                            path='/MPCVObject/MasterSettings/Tempo'
                        ))
                except ValueError:
                    tempo_elem.text = '120.0'
                    errors.append(ValidationError(
                        severity=ValidationSeverity.ERROR,
                        code='INVALID_TEMPO',
                        message='Invalid tempo value, using default 120',
                        path='/MPCVObject/MasterSettings/Tempo'
                    ))
                    
        return root, errors
        
    def _create_default_metadata(self) -> ET.Element:
        """Create default metadata section."""
        meta = ET.Element('Metadata')
        ET.SubElement(meta, 'Name').text = 'Untitled'
        ET.SubElement(meta, 'UUID').text = str(uuid.uuid4()).upper()
        return meta
        
    def _create_default_master(self) -> ET.Element:
        """Create default master settings."""
        master = ET.Element('MasterSettings')
        ET.SubElement(master, 'Tempo').text = '120.0'
        ET.SubElement(master, 'PPQ').text = '480'
        return master
```

### Error Reporting

```python
import json
from typing import List

def generate_validation_report(errors: List[ValidationError], output_path: str) -> None:
    """Generate JSON validation report for CI/CD."""
    
    report = {
        'summary': {
            'total': len(errors),
            'critical': sum(1 for e in errors if e.severity == ValidationSeverity.CRITICAL),
            'errors': sum(1 for e in errors if e.severity == ValidationSeverity.ERROR),
            'warnings': sum(1 for e in errors if e.severity == ValidationSeverity.WARNING),
            'info': sum(1 for e in errors if e.severity == ValidationSeverity.INFO),
        },
        'passed': all(e.severity not in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR] 
                      for e in errors),
        'errors': [
            {
                'severity': e.severity.name,
                'code': e.code,
                'message': e.message,
                'path': e.path,
                'suggestion': e.suggestion,
            }
            for e in errors
        ]
    }
    
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
        
    # Also output human-readable summary
    print(f"\n{'='*60}")
    print("VALIDATION REPORT")
    print(f"{'='*60}")
    print(f"Total issues: {report['summary']['total']}")
    print(f"  Critical: {report['summary']['critical']}")
    print(f"  Errors:   {report['summary']['errors']}")
    print(f"  Warnings: {report['summary']['warnings']}")
    print(f"  Info:     {report['summary']['info']}")
    print(f"\nResult: {'PASSED' if report['passed'] else 'FAILED'}")
    print(f"{'='*60}\n")
```

---

## 8. Recommendations for This Project

### Immediate Actions

1. **Create inferred schema from known-good exports**
   - Collect 5-10 MPC project files created by official MPC Software
   - Run schema inference to generate baseline XSD/RelaxNG
   - Store in `docs/schemas/mpc_inferred.xsd`

2. **Implement structural validator**
   - Add `MpcValidator` class to `mpc_exporter.py`
   - Validate before writing output files
   - Return detailed error reports

3. **Add CI/CD validation**
   - Create GitHub Action workflow
   - Run on every PR touching MPC export code
   - Block merge if CRITICAL/ERROR issues found

### Suggested File Structure

```
multimodal-ai-music-gen/
├── docs/
│   └── schemas/
│       ├── mpc_inferred.xsd        # Inferred XSD schema
│       └── mpc_validation_rules.md # Business logic rules
├── multimodal_gen/
│   ├── mpc_exporter.py             # Existing exporter
│   └── mpc_validator.py            # New validation module
└── tests/
    ├── test_mpc_validation.py      # Validation tests
    └── fixtures/
        └── known_good_mpc/         # Reference MPC files
            ├── simple_project.xpj
            └── complex_project.xpj
```

### Validation Priority Matrix

| Check | Severity | Blocks Export? | Notes |
|-------|----------|----------------|-------|
| Valid XML syntax | CRITICAL | Yes | Cannot proceed |
| Root element correct | CRITICAL | Yes | Wrong format |
| Version supported | ERROR | Yes | May be incompatible |
| Required sections present | ERROR | No (can default) | Degraded mode |
| Tempo in range | WARNING | No (clamp) | Auto-correct |
| PPQ standard value | WARNING | No | MPC may adjust |
| Paths are relative | WARNING | No | Convert |
| UUIDs valid format | INFO | No | Regenerate |

---

## 9. References

### Official Documentation
- [MusicXML 4.0 W3C Specification](https://www.w3.org/2021/06/musicxml40/)
- [xmlschema Python Library](https://xmlschema.readthedocs.io/)
- [lxml Validation](https://lxml.de/validation.html)
- [VST3 Developer Portal](https://steinbergmedia.github.io/vst3_dev_portal/)

### Tools
- [Trang Schema Converter](https://relaxng.org/jclark/trang.html)
- [xmllint](http://xmlsoft.org/xmllint.html) - Command-line XML validator

### Related RFCs/Standards
- [RFC 3076 - XML Canonicalization](https://www.ietf.org/rfc/rfc3076.txt)
- [W3C XML Schema](https://www.w3.org/XML/Schema)

---

*Document generated: January 20, 2026*  
*Research conducted by: GitHub Copilot*
