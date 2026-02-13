"""Strategy registry for dynamic genre loading."""
from typing import Dict, List, Optional
from .base import GenreStrategy


class StrategyRegistry:
    """
    Registry for genre strategies with auto-discovery.
    
    Provides a centralized way to look up the appropriate strategy
    for any genre. Supports:
    - Multiple genre aliases per strategy
    - Lazy initialization (strategies loaded on first access)
    - Default fallback for unknown genres
    
    Usage:
        strategy = StrategyRegistry.get_or_default('trap')
        drums = strategy.generate_drums(section, parsed, tension)
    """
    
    _strategies: Dict[str, GenreStrategy] = {}
    _initialized: bool = False
    
    @classmethod
    def register(cls, strategy: GenreStrategy) -> None:
        """
        Register a strategy for its genre(s).
        
        The strategy will be registered under all names returned by
        its supported_genres property.
        """
        for genre in strategy.supported_genres:
            cls._strategies[genre.lower()] = strategy
    
    @classmethod
    def get(cls, genre: str) -> Optional[GenreStrategy]:
        """
        Get strategy for a genre, or None if not found.
        
        Args:
            genre: Genre name (case-insensitive)
            
        Returns:
            GenreStrategy instance or None
        """
        cls._ensure_initialized()
        return cls._strategies.get(genre.lower())
    
    @classmethod
    def get_or_default(cls, genre: str) -> GenreStrategy:
        """
        Get strategy for genre, falling back to default.
        
        This is the recommended method for most use cases as it
        always returns a valid strategy.
        
        Args:
            genre: Genre name (case-insensitive)
            
        Returns:
            GenreStrategy instance (never None)
        """
        strategy = cls.get(genre)
        if strategy is None:
            from .default_strategy import DefaultStrategy
            return DefaultStrategy()
        return strategy
    
    @classmethod
    def _ensure_initialized(cls) -> None:
        """
        Lazy-load all strategies on first access.
        
        This avoids circular import issues by deferring the import
        of concrete strategies until they're actually needed.
        """
        if cls._initialized:
            return
        
        # Import and register all strategies
        from .trap_strategy import TrapStrategy
        from .trap_soul_strategy import TrapSoulStrategy
        from .rnb_strategy import RnBStrategy
        from .lofi_strategy import LofiStrategy
        from .gfunk_strategy import GFunkStrategy
        from .house_strategy import HouseStrategy
        from .drill_strategy import DrillStrategy
        from .boom_bap_strategy import BoomBapStrategy
        from .ethiopian_strategy import (
            EthiopianStrategy,
            EthioJazzStrategy,
            EthiopianTraditionalStrategy,
            EskistaStrategy
        )
        from .default_strategy import DefaultStrategy
        
        cls.register(TrapStrategy())
        cls.register(TrapSoulStrategy())
        cls.register(RnBStrategy())
        cls.register(LofiStrategy())
        cls.register(GFunkStrategy())
        cls.register(HouseStrategy())
        cls.register(EthiopianStrategy())
        cls.register(EthioJazzStrategy())
        cls.register(EthiopianTraditionalStrategy())
        cls.register(EskistaStrategy())
        cls.register(DefaultStrategy())
        cls.register(DrillStrategy())      # overrides 'drill' from TrapStrategy
        cls.register(BoomBapStrategy())    # overrides 'boom_bap'/'boombap' from DefaultStrategy
        
        cls._initialized = True
    
    @classmethod
    def list_genres(cls) -> List[str]:
        """
        List all registered genre names.
        
        Returns:
            List of all genre names (including aliases)
        """
        cls._ensure_initialized()
        return list(cls._strategies.keys())
    
    @classmethod
    def reset(cls) -> None:
        """
        Reset the registry (mainly for testing).
        
        Clears all registered strategies and resets initialization flag.
        """
        cls._strategies.clear()
        cls._initialized = False
