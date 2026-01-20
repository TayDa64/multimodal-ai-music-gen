"""Tests for Genre Strategy Pattern."""
import pytest


class TestStrategyRegistry:
    """Test suite for StrategyRegistry."""
    
    def test_import(self):
        """Test strategy registry can be imported."""
        from multimodal_gen.strategies.registry import StrategyRegistry
        assert StrategyRegistry is not None
    
    def test_get_strategy_trap(self):
        """Test getting trap strategy."""
        from multimodal_gen.strategies.registry import StrategyRegistry
        
        StrategyRegistry.reset()  # Clear for clean test
        strategy = StrategyRegistry.get('trap')
        
        assert strategy is not None
        assert hasattr(strategy, 'generate_drums')
    
    def test_get_strategy_lofi(self):
        """Test getting lofi strategy."""
        from multimodal_gen.strategies.registry import StrategyRegistry
        
        StrategyRegistry.reset()
        strategy = StrategyRegistry.get('lofi')
        
        assert strategy is not None
        assert hasattr(strategy, 'genre_name')
    
    def test_get_strategy_ethiopian(self):
        """Test getting ethiopian/eskista strategy."""
        from multimodal_gen.strategies.registry import StrategyRegistry
        
        StrategyRegistry.reset()
        # Try possible names
        strategy = (
            StrategyRegistry.get('eskista') or 
            StrategyRegistry.get('ethiopian') or
            StrategyRegistry.get('ethio')
        )
        
        assert strategy is not None
    
    def test_get_or_default_unknown_genre(self):
        """Test unknown genre falls back to default."""
        from multimodal_gen.strategies.registry import StrategyRegistry
        
        StrategyRegistry.reset()
        strategy = StrategyRegistry.get_or_default('unknown_genre_xyz_12345')
        
        # Should return default strategy, not None
        assert strategy is not None
        assert hasattr(strategy, 'generate_drums')
    
    def test_list_genres(self):
        """Test listing available genres."""
        from multimodal_gen.strategies.registry import StrategyRegistry
        
        StrategyRegistry.reset()
        genres = StrategyRegistry.list_genres()
        
        assert isinstance(genres, list)
        assert len(genres) > 0
        assert 'trap' in genres or 'default' in genres
    
    def test_reset(self):
        """Test registry reset clears strategies."""
        from multimodal_gen.strategies.registry import StrategyRegistry
        
        # Ensure initialized
        StrategyRegistry.get_or_default('trap')
        
        # Reset
        StrategyRegistry.reset()
        
        # Should require re-initialization
        assert StrategyRegistry._initialized == False


class TestGenreStrategyBase:
    """Test suite for GenreStrategy base class."""
    
    def test_import_base(self):
        """Test GenreStrategy base can be imported."""
        from multimodal_gen.strategies.base import GenreStrategy, DrumConfig
        
        assert GenreStrategy is not None
        assert DrumConfig is not None
    
    def test_drum_config_defaults(self):
        """Test DrumConfig has sensible defaults."""
        from multimodal_gen.strategies.base import DrumConfig
        
        config = DrumConfig()
        
        assert config.base_velocity == 100
        assert config.swing == 0.0
        assert config.half_time == False
        assert config.include_ghost_notes == True
        assert config.density == '8th'


class TestTrapStrategy:
    """Test suite for TrapStrategy."""
    
    def test_import(self):
        """Test TrapStrategy can be imported."""
        from multimodal_gen.strategies.trap_strategy import TrapStrategy
        assert TrapStrategy is not None
    
    def test_genre_name(self):
        """Test trap strategy reports correct genre."""
        from multimodal_gen.strategies.trap_strategy import TrapStrategy
        
        strategy = TrapStrategy()
        assert strategy.genre_name == 'trap'
    
    def test_supported_genres(self):
        """Test trap strategy supported genres."""
        from multimodal_gen.strategies.trap_strategy import TrapStrategy
        
        strategy = TrapStrategy()
        supported = strategy.supported_genres
        
        assert isinstance(supported, list)
        assert 'trap' in supported
    
    def test_has_generate_drums(self):
        """Test trap strategy has generate_drums method."""
        from multimodal_gen.strategies.trap_strategy import TrapStrategy
        
        strategy = TrapStrategy()
        assert hasattr(strategy, 'generate_drums')
        assert callable(strategy.generate_drums)


class TestLofiStrategy:
    """Test suite for LofiStrategy."""
    
    def test_import(self):
        """Test LofiStrategy can be imported."""
        from multimodal_gen.strategies.lofi_strategy import LofiStrategy
        assert LofiStrategy is not None
    
    def test_genre_name(self):
        """Test lofi strategy reports correct genre."""
        from multimodal_gen.strategies.lofi_strategy import LofiStrategy
        
        strategy = LofiStrategy()
        assert 'lofi' in strategy.genre_name.lower() or 'lo-fi' in strategy.genre_name.lower()


class TestEthiopianStrategy:
    """Test suite for Ethiopian strategies."""
    
    def test_import(self):
        """Test Ethiopian strategies can be imported."""
        from multimodal_gen.strategies.ethiopian_strategy import (
            EthiopianStrategy,
            EthioJazzStrategy,
            EthiopianTraditionalStrategy,
            EskistaStrategy,
        )
        
        assert EthiopianStrategy is not None
        assert EthioJazzStrategy is not None
        assert EthiopianTraditionalStrategy is not None
        assert EskistaStrategy is not None
    
    def test_eskista_genre_name(self):
        """Test eskista strategy reports correct genre."""
        from multimodal_gen.strategies.ethiopian_strategy import EskistaStrategy
        
        strategy = EskistaStrategy()
        assert 'eskista' in strategy.genre_name.lower()


class TestGenreStrategyInterface:
    """Test all strategies implement the interface correctly."""
    
    @pytest.mark.parametrize("strategy_name", [
        'trap', 'trap_soul', 'lofi', 
        'rnb', 'g_funk', 'house', 'default'
    ])
    def test_strategy_has_required_methods(self, strategy_name):
        """Test each strategy has required methods."""
        from multimodal_gen.strategies.registry import StrategyRegistry
        
        StrategyRegistry.reset()
        strategy = StrategyRegistry.get(strategy_name)
        
        if strategy is None:
            pytest.skip(f"Strategy {strategy_name} not registered")
        
        # All strategies should have these methods
        assert hasattr(strategy, 'generate_drums'), f"{strategy_name} missing generate_drums"
        assert hasattr(strategy, 'genre_name'), f"{strategy_name} missing genre_name"
        assert hasattr(strategy, 'supported_genres'), f"{strategy_name} missing supported_genres"
        assert hasattr(strategy, 'get_default_config'), f"{strategy_name} missing get_default_config"
    
    @pytest.mark.parametrize("strategy_name", [
        'trap', 'lofi', 'rnb', 'house', 'default'
    ])
    def test_strategy_default_config_valid(self, strategy_name):
        """Test each strategy returns valid default config."""
        from multimodal_gen.strategies.registry import StrategyRegistry
        from multimodal_gen.strategies.base import DrumConfig
        
        StrategyRegistry.reset()
        strategy = StrategyRegistry.get(strategy_name)
        
        if strategy is None:
            pytest.skip(f"Strategy {strategy_name} not registered")
        
        config = strategy.get_default_config()
        
        assert isinstance(config, DrumConfig)
        assert 0 <= config.base_velocity <= 127
        assert 0.0 <= config.swing <= 1.0
